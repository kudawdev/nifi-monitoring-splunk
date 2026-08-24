"""Consistency checks over the apps' .conf files.

These are the invariants that break quietly: a sourcetype added to the TA
without the lookup that enriches it, a version bumped in one stanza but not
the other, a log stanza that fragments stack traces. AppInspect does not
check any of them, and a person reviewing a diff rarely does either.
"""

import configparser
import json
import os
import re
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TA = os.path.join(REPO, "nifi_TA_monitoring")
APP = os.path.join(REPO, "nifi_monitoring")


def conf(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read(path)
    return parser


class VersionStanzaTest(unittest.TestCase):
    """AppInspect reads [id] as well as [launcher], so they have to agree."""

    def app_conf(self, app):
        return conf(os.path.join(REPO, app, "default", "app.conf"))

    def test_launcher_and_id_versions_match(self):
        for app in ("nifi_monitoring", "nifi_TA_monitoring"):
            with self.subTest(app=app):
                parsed = self.app_conf(app)
                self.assertEqual(
                    parsed["launcher"]["version"], parsed["id"]["version"]
                )

    def test_the_id_name_matches_the_package_id(self):
        for app in ("nifi_monitoring", "nifi_TA_monitoring"):
            with self.subTest(app=app):
                parsed = self.app_conf(app)
                self.assertEqual(parsed["id"]["name"], parsed["package"]["id"])
                self.assertEqual(parsed["id"]["name"], app)

    def test_both_apps_are_on_the_same_version(self):
        versions = {
            self.app_conf(app)["launcher"]["version"]
            for app in ("nifi_monitoring", "nifi_TA_monitoring")
        }
        self.assertEqual(len(versions), 1, "apps are on different versions: %s" % versions)

    def test_the_version_is_semver(self):
        for app in ("nifi_monitoring", "nifi_TA_monitoring"):
            with self.subTest(app=app):
                self.assertRegex(self.app_conf(app)["launcher"]["version"], r"^\d+\.\d+\.\d+$")


class SourcetypeCoverageTest(unittest.TestCase):
    """Every sourcetype the TA defines needs the instance lookup in the app,
    or its events never get a cluster and drop out of the dashboards."""

    @classmethod
    def setUpClass(cls):
        cls.ta_props = conf(os.path.join(TA, "default", "props.conf"))
        cls.app_props = conf(os.path.join(APP, "default", "props.conf"))

    def test_every_ta_sourcetype_has_the_instance_lookup(self):
        for sourcetype in self.ta_props.sections():
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(
                    sourcetype,
                    self.app_props.sections(),
                    "%s has no stanza in nifi_monitoring/default/props.conf" % sourcetype,
                )
                self.assertIn(
                    "lookup-instance",
                    [key.lower() for key in self.app_props[sourcetype]],
                )

    def test_the_app_does_not_enrich_sourcetypes_the_ta_never_produces(self):
        """A leftover stanza is how nifi:api:controller_cluster survived with
        nothing generating it."""
        for sourcetype in self.app_props.sections():
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, self.ta_props.sections())

    def test_the_orphan_sourcetype_is_gone(self):
        self.assertNotIn("nifi:api:controller_cluster", self.ta_props.sections())
        self.assertNotIn("nifi:api:controller_cluster", self.app_props.sections())


class LogStanzaTest(unittest.TestCase):
    """The log sourcetypes must keep a stack trace with the event that raised
    it, and must not truncate it."""

    # nifi:log:request is excluded on purpose: it is NCSA combined, one line
    # per event, and has its own stanza tested in RequestLogTest.
    LOG_SOURCETYPES = (
        "nifi:log:app",
        "nifi:log:bootstrap",
        "nifi:log:user",
        "nifi:log:deprecation",
    )

    @classmethod
    def setUpClass(cls):
        cls.props = conf(os.path.join(TA, "default", "props.conf"))

    def test_every_log_sourcetype_exists(self):
        for sourcetype in self.LOG_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, self.props.sections())

    def test_the_breaker_only_breaks_before_a_timestamp(self):
        """A plain ([\\r\\n]+) breaker turned 77% of a clean nifi-app.log into
        separate events with no timestamp and no level."""
        for sourcetype in self.LOG_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                breaker = self.props[sourcetype]["line_breaker"]
                self.assertIn("(?=", breaker, "breaker has no lookahead")
                self.assertIn(r"\d{4}-\d{2}-\d{2}", breaker)

    def test_linemerge_is_declared_rather_than_left_to_the_default(self):
        for sourcetype in self.LOG_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                self.assertEqual(
                    self.props[sourcetype]["should_linemerge"].lower(), "false"
                )

    def test_stack_traces_are_not_truncated(self):
        for sourcetype in self.LOG_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                self.assertEqual(self.props[sourcetype]["truncate"], "0")

    def test_the_breaker_keeps_a_stack_trace_together(self):
        """Applied to real log lines, not just inspected as a string."""
        breaker = re.compile(
            self.props["nifi:log:app"]["line_breaker"].replace("(", "(", 1)
        )
        lines = (
            "2026-08-24 14:32:51,640 INFO [main] o.a.n.App Starting\n"
            "2026-08-24 14:32:51,648 ERROR [main] o.a.n.Fail Broke\n"
            "java.net.ConnectException: Failed to connect\n"
            "\tat okhttp3.internal.ConnectPlan.connectSocket(ConnectPlan.kt:239)\n"
            "2026-08-24 14:32:52,001 INFO [main] o.a.n.Next Recovered\n"
        )
        events = [
            part for part in breaker.split(lines)
            if part.strip() and not re.fullmatch(r"[\r\n]+", part)
        ]
        self.assertEqual(len(events), 3, "got %d events: %r" % (len(events), events))
        self.assertEqual(len(events[1].strip().split("\n")), 3, "trace was split")


class RequestLogTest(unittest.TestCase):
    """nifi-request.log is NCSA combined, not logback, so it gets its own
    treatment: a real timestamp and Splunk's core access extraction."""

    @classmethod
    def setUpClass(cls):
        cls.props = conf(os.path.join(TA, "default", "props.conf"))
        cls.stanza = cls.props["nifi:log:request"]
        with open(os.path.join(REPO, "docs", "plans", "samples",
                               "nifi2.11-request.log")) as handle:
            cls.lines = [line for line in handle.read().splitlines() if line.strip()]

    def test_the_captured_log_is_ncsa_combined(self):
        """Captured from a real NiFi 2.11 after driving traffic at it."""
        pattern = re.compile(
            r'^\S+ \S+ \S+ \[[^\]]+\] "[^"]*" \d{3} \S+ "[^"]*" "[^"]*"$'
        )
        self.assertTrue(self.lines, "no sample lines captured")
        for line in self.lines:
            with self.subTest(line=line[:60]):
                self.assertRegex(line, pattern)

    def test_the_time_format_parses_the_captured_timestamps(self):
        from datetime import datetime
        fmt = self.stanza["time_format"].replace("%", "%")
        for line in self.lines:
            stamp = line.split("[", 1)[1].split("]", 1)[0]
            with self.subTest(stamp=stamp):
                datetime.strptime(stamp, "%d/%b/%Y:%H:%M:%S %z")
        self.assertEqual(fmt, "%d/%b/%Y:%H:%M:%S %z")

    def test_it_reuses_splunk_core_access_extraction(self):
        """Rather than restating the NCSA regex in this app."""
        self.assertEqual(self.stanza["report-access"], "access-extractions")

    def test_it_does_not_use_the_logback_breaker(self):
        self.assertNotIn("(?=", self.stanza["line_breaker"])

    def test_the_event_time_is_the_request_time_not_the_collection_time(self):
        self.assertNotIn("datetime_config", [k.lower() for k in self.stanza])


class MonitorPathTest(unittest.TestCase):
    """The default monitor paths have to match where NiFi actually writes."""

    @classmethod
    def setUpClass(cls):
        cls.inputs = conf(os.path.join(TA, "default", "inputs.conf"))

    def monitors(self):
        return [s for s in self.inputs.sections() if s.startswith("monitor://")]

    def test_paths_point_at_the_container_layout(self):
        """The official image keeps logs under /opt/nifi/nifi-current/logs."""
        for stanza in self.monitors():
            with self.subTest(stanza=stanza):
                self.assertIn("/opt/nifi/nifi-current/logs/", stanza)

    def test_every_monitor_is_disabled_by_default(self):
        """Enabling a monitor whose path does not exist logs errors forever."""
        for stanza in self.monitors():
            with self.subTest(stanza=stanza):
                self.assertEqual(self.inputs[stanza]["disabled"].lower(), "true")

    def test_every_monitor_declares_a_known_sourcetype(self):
        props = conf(os.path.join(TA, "default", "props.conf"))
        for stanza in self.monitors():
            with self.subTest(stanza=stanza):
                self.assertIn(self.inputs[stanza]["sourcetype"], props.sections())

    def test_the_request_log_is_monitored(self):
        sourcetypes = [self.inputs[s]["sourcetype"] for s in self.monitors()]
        self.assertIn("nifi:log:request", sourcetypes)

    def test_the_deprecation_log_is_monitored(self):
        """It names the deprecated components an instance still uses, which is
        the input for planning a move to NiFi 2.x."""
        sourcetypes = [self.inputs[s]["sourcetype"] for s in self.monitors()]
        self.assertIn("nifi:log:deprecation", sourcetypes)

    def test_python_required_is_declared(self):
        """python.version alone no longer satisfies AppInspect."""
        self.assertEqual(self.inputs["nifi"]["python.required"], "python3")
        self.assertEqual(self.inputs["nifi"]["python.version"], "python3")


class RemovedEndpointTest(unittest.TestCase):
    """nifi:api:site_to_site was removed in 2.0.0 (decision D-2): it was
    collected on every cycle and no dashboard or datamodel object read it, so
    it was licence spend on data nobody looked at."""

    def test_it_is_gone_from_both_apps(self):
        for app in (TA, APP):
            with self.subTest(app=os.path.basename(app)):
                props = conf(os.path.join(app, "default", "props.conf"))
                self.assertNotIn("nifi:api:site_to_site", props.sections())

    def test_it_is_gone_from_the_endpoint_table_and_the_scheme(self):
        source = open(os.path.join(TA, "bin", "nifi.py")).read()
        self.assertNotIn('"path":"/site-to-site"', source)
        self.assertNotIn("endpoint_site_to_site_argument", source)

    def test_it_is_gone_from_the_setup_page_and_the_spec(self):
        ui = open(os.path.join(TA, "default", "data", "ui", "manager",
                               "nifi_manager.xml")).read()
        self.assertNotIn("endpoint_site_to_site", ui)
        spec = open(os.path.join(TA, "README", "inputs.conf.spec")).read()
        self.assertNotIn("endpoint_site_to_site", spec)

    def test_a_leftover_setting_is_still_noticed(self):
        """An input saved before 2.0.0 keeps the setting in inputs.conf. The
        input must say it is ignored rather than silently dropping it."""
        source = open(os.path.join(TA, "bin", "nifi.py")).read()
        self.assertIn("endpoint_site_to_site was removed", source)


class IndexConfigurationTest(unittest.TestCase):
    """The index_nifi macro is the single point of control for where the app
    looks. It used to be `index=*`, which made every panel and every
    datamodel acceleration scan every event index on the instance."""

    @classmethod
    def setUpClass(cls):
        cls.macros = conf(os.path.join(APP, "default", "macros.conf"))
        cls.indexes = conf(os.path.join(APP, "default", "indexes.conf"))
        cls.datamodels = conf(os.path.join(APP, "default", "datamodels.conf"))

    def test_the_macro_names_a_single_index(self):
        definition = self.macros["index_nifi"]["definition"]
        self.assertNotIn("*", definition, "the macro is back to scanning every index")
        self.assertRegex(definition, r"^index=\S+$")

    def test_the_app_ships_the_index_it_points_at(self):
        """Otherwise a fresh install has nowhere to put data and every panel
        is empty with no explanation."""
        index = self.macros["index_nifi"]["definition"].split("=", 1)[1].strip()
        self.assertIn(index, self.indexes.sections())

    def test_the_harness_input_writes_to_that_index(self):
        """So the integration profiles exercise the recommended layout rather
        than an exception to it."""
        index = self.macros["index_nifi"]["definition"].split("=", 1)[1].strip()
        for mode in ("none", "singleuser"):
            with self.subTest(auth=mode):
                text = open(os.path.join(
                    REPO, "tests", "provision", "splunk", "inputs.conf.%s" % mode
                )).read()
                self.assertIn("index = %s" % index, text)

    def test_only_the_diagnostic_panel_may_scan_every_index(self):
        """index=* is defensible exactly once: the panel whose job is to find
        out where the data landed."""
        views = os.path.join(APP, "default", "data", "ui", "views")
        for name in os.listdir(views):
            if not name.endswith(".xml"):
                continue
            text = open(os.path.join(views, name)).read()
            with self.subTest(view=name):
                if "index=*" in text:
                    self.assertEqual(
                        name, "nifi_internal_monitoring.xml",
                        "%s scans every index" % name,
                    )

    def test_acceleration_matches_what_the_panels_assume(self):
        """The dashboards use `tstats ... from datamodel=`, which needs an
        accelerated model to perform as intended."""
        self.assertEqual(self.datamodels["NIFI"]["acceleration"], "true")
        self.assertIn("acceleration.earliest_time", self.datamodels["NIFI"])


class DashboardQueryTest(unittest.TestCase):
    """Query-level rules for the shipped dashboards."""

    VIEWS = os.path.join(APP, "default", "data", "ui", "views")

    def views(self):
        for name in sorted(os.listdir(self.VIEWS)):
            if name.endswith(".xml"):
                yield name, open(os.path.join(self.VIEWS, name)).read()

    def test_no_dashboard_uses_a_join(self):
        """A join runs its right side as a subsearch, which is capped (50k
        rows, 60s by default) and truncates silently past the cap. append +
        stats produces the same shape with no cap."""
        for name, text in self.views():
            with self.subTest(view=name):
                self.assertNotIn("join type", text, "%s still joins" % name)

    def test_the_disk_panel_reads_the_numeric_fields(self):
        """It used to read the human-readable strings ("847.61 GB", "16.0%"),
        which display fine but cannot be aggregated or thresholded."""
        text = dict(self.views())["nifi_overview.xml"]
        self.assertIn("usedSpaceBytes", text)
        self.assertIn("totalSpaceBytes", text)
        self.assertNotIn("{}.freeSpace", text)
        self.assertNotIn("{}.utilization", text)

    def test_datamodel_fields_are_object_qualified(self):
        """tstats against a datamodel needs Object.field, not a bare field."""
        text = dict(self.views())["nifi_overview.xml"]
        for match in re.findall(r"latest\((\S+?)\) as", text):
            if match.startswith("systemDiagnostics") or match.startswith("controllerStatus"):
                self.fail("%s is not object-qualified" % match)


class DatamodelCoverageTest(unittest.TestCase):
    """Every sourcetype the TA produces should reach the datamodel, or it is
    indexed and then invisible to the model the dashboards query."""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(APP, "default", "data", "models", "NIFI.json")) as handle:
            cls.model = json.load(handle)
        cls.ta_props = conf(os.path.join(TA, "default", "props.conf"))

    def constraints(self):
        return " ".join(
            c["search"] for o in self.model["objects"] for c in o["constraints"]
        )

    def test_every_sourcetype_is_covered_by_some_object(self):
        constraints = self.constraints()
        for sourcetype in self.ta_props.sections():
            with self.subTest(sourcetype=sourcetype):
                covered = sourcetype in constraints
                if not covered:
                    # a wildcard constraint counts, e.g. nifi:log:* or
                    # nifi:api:process*
                    prefix = sourcetype
                    while ":" in prefix or prefix:
                        prefix = prefix[:-1]
                        if not prefix:
                            break
                        if prefix + "*" in constraints:
                            covered = True
                            break
                self.assertTrue(covered, "%s is in no datamodel object" % sourcetype)

    def test_the_object_name_list_matches_the_objects(self):
        self.assertEqual(
            self.model["objectNameList"],
            [o["objectName"] for o in self.model["objects"]],
        )

    def test_every_object_constrains_the_index(self):
        """A root object without the macro would search every index, which is
        the problem the macro exists to solve."""
        for obj in self.model["objects"]:
            if obj["parentName"] != "BaseEvent":
                continue  # child objects inherit the parent's constraint
            with self.subTest(obj=obj["objectName"]):
                self.assertIn("`index_nifi`", obj["constraints"][0]["search"])

    def test_the_request_log_is_not_swept_into_the_generic_logs_object(self):
        """It is NCSA combined, so it has none of the logback fields."""
        logs = [o for o in self.model["objects"] if o["objectName"] == "Logs"][0]
        self.assertIn("NOT sourcetype=\"nifi:log:request\"", logs["constraints"][0]["search"])

    def test_bulletin_field_names_agree_across_both_collection_paths(self):
        """Reporting_Bulletin and Bulletin_Board must use the same field names,
        or a dashboard has to know which path produced the event."""
        def fields(name):
            obj = [o for o in self.model["objects"] if o["objectName"] == name][0]
            return {f["fieldName"] for f in obj["fields"] if f["fieldName"].startswith("bulletin")}

        board = fields("Bulletin_Board")
        task = fields("Reporting_Bulletin")
        shared = board & task
        self.assertTrue(shared, "the two bulletin objects share no field names")
        # the two the board genuinely cannot provide
        self.assertEqual(task - board, {"bulletinGroupName", "bulletinGroupPath"})


if __name__ == "__main__":
    unittest.main()
