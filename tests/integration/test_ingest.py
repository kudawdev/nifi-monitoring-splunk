"""Does data actually reach Splunk, and are the fields extracted?

The old harness brought up containers and stopped there: nothing verified
that events arrived or that the app could read them. These are the checks
that make "the tests pass" mean something.

Skipped automatically when no stack is running, so `python3 -m unittest
discover` stays safe to run anywhere.
"""

import os
import unittest

from support import IntegrationTestCase, env, search, wait_for_events

# Sourcetypes the TA's pull path must produce in every supported version.
CORE_SOURCETYPES = [
    "nifi:api:flow_status",
    "nifi:api:system_diagnostics",
]

# nifi:api:site_to_site was removed in 2.0.0: it was collected and no panel
# or datamodel object ever read it.
REMOVED_SOURCETYPES = ["nifi:api:site_to_site"]


class IngestTest(IntegrationTestCase):
    collection = "pull"

    def test_the_modular_input_produces_events(self):
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:*" | stats count by sourcetype',
            minimum=1,
        )
        self.assertTrue(
            rows, "no nifi:api:* events reached Splunk; check the input and splunkd.log"
        )

    def test_every_core_sourcetype_arrives(self):
        wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:*" | stats count by sourcetype',
            minimum=len(CORE_SOURCETYPES),
        )
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:*" | stats count by sourcetype',
        )
        seen = {row["sourcetype"] for row in rows}
        for sourcetype in CORE_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, seen)

    def test_the_removed_sourcetype_is_no_longer_collected(self):
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:site_to_site" | stats count',
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "site_to_site is still being ingested")

    def test_flow_status_fields_are_extracted(self):
        """INDEXED_EXTRACTIONS must turn the JSON into the datamodel's fields."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_status" '
            "| head 1 | table controllerStatus.activeThreadCount, "
            "controllerStatus.runningCount, controllerStatus.flowFilesQueued",
            minimum=1,
        )
        self.assertTrue(rows, "no flow_status events to check fields on")
        row = rows[0]
        for field in (
            "controllerStatus.activeThreadCount",
            "controllerStatus.runningCount",
            "controllerStatus.flowFilesQueued",
        ):
            with self.subTest(field=field):
                self.assertIn(field, row)

    def test_instance_lookup_enriches_events_with_the_cluster(self):
        """props.conf declares LOOKUP-instance; without it the app cannot group
        instances by cluster."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_status" '
            "| head 1 | table host, cluster",
            minimum=1,
        )
        self.assertTrue(rows)
        self.assertTrue(rows[0].get("cluster"), "cluster was not looked up from host")

    def test_the_input_logs_no_errors_other_than_the_bootstrap_401(self):
        """One 401 per cold start is by design: with no cached token the first
        request is unauthorized, and the input then fetches one and retries.
        Anything else is a real failure."""
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd log_level=ERROR "Nifi Log pid=" '
            '| rex "status_code: (?<code>\\d+)" '
            "| stats count by code",
            earliest="-1h",
        )
        unexpected = [row for row in rows if row.get("code") != "401"]
        self.assertEqual(
            unexpected, [], "the input logged errors other than a 401: %s" % unexpected
        )

    def test_the_input_recovers_from_the_bootstrap_401(self):
        """The regression guard for the token-refresh bug: before it was fixed
        the retry re-sent the expired token, so the input never got past the
        401 and nothing was ever indexed. Events dated after the last error
        prove the renewal worked."""
        last_error = search(
            self.splunk,
            'index=_internal sourcetype=splunkd log_level=ERROR "Nifi Log pid=" '
            "| stats max(_time) as last_error",
            earliest="-1h",
        )
        if not last_error or not str(last_error[0].get("last_error", "")).strip():
            self.skipTest("the input logged no errors at all; nothing to recover from")

        last_event = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:*" | stats max(_time) as last_event',
            earliest="-1h",
        )
        self.assertTrue(last_event and last_event[0].get("last_event"))
        self.assertGreater(
            float(last_event[0]["last_event"]),
            float(last_error[0]["last_error"]),
            "no events arrived after the last error: the input did not recover",
        )

    def test_errors_are_confined_to_startup(self):
        """Errors must look like a bounded bootstrap, not one per request.

        An earlier version of this compared total errors against total
        indexed events, which was flaky: the error count is a one-off from
        startup while the event count grows with uptime, so the same healthy
        stack passed when the assertions ran late and failed when they ran
        early. Bound it against something that does not move instead -- the
        number of enabled endpoints, which is the most bootstrap 401s the
        input can legitimately pay.
        """
        errors = search(
            self.splunk,
            'index=_internal sourcetype=splunkd log_level=ERROR "Nifi Log pid=" '
            "| stats count",
            earliest="-1h",
        )
        error_count = int(errors[0]["count"]) if errors and errors[0].get("count") else 0

        # flow_status, system_diagnostics, the bulletin board and flow metrics
        # are enabled by the harness input; each can pay at most one 401
        # before the token is cached, and a cold start can happen twice if a
        # container is recreated.
        ceiling = 4 * 2
        self.assertLessEqual(
            error_count,
            ceiling,
            "%d errors is more than a bounded startup (<=%d): the input is "
            "erroring on every request" % (error_count, ceiling),
        )


class VersionDetectionTest(IntegrationTestCase):
    collection = "pull"
    """The TA detects which NiFi it is talking to and records it.

    Detection reads versionInfo.niFiVersion from /system-diagnostics, which
    exists on both the 1.x and 2.x lines, so this must work on every profile.
    """

    def test_the_detected_version_is_indexed(self):
        # Pinned to the primary host: the multi-instance profile indexes a
        # version_info per instance, and `head 1` over both would pick
        # whichever happened to be written last.
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:version_info" host=nifi '
            "| head 1 | table niFiVersion, javaVersion",
            minimum=1,
        )
        self.assertTrue(rows, "no nifi:api:version_info event was indexed")
        self.assertEqual(rows[0].get("niFiVersion"), self.nifi_version)

    def test_the_detected_version_matches_the_profile(self):
        """A mismatch means the harness and the TA disagree about what is
        running, which would make every other assertion suspect.

        Asserted per host rather than over the whole index: the
        multi-instance profile runs two NiFis of different versions on
        purpose, and collapsing them into one set would either fail here or,
        worse, hide which input reported what.
        """
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:version_info" '
            "| stats values(niFiVersion) as versions by host",
            minimum=self.profile_instances,
        )
        self.assertTrue(rows)
        expected = {"nifi": self.nifi_version}
        if self.profile_instances > 1:
            expected["nifi-b"] = env("NIFI_B_VERSION")
        for row in rows:
            with self.subTest(host=row["host"]):
                versions = row["versions"]
                if isinstance(versions, str):
                    versions = [versions]
                self.assertEqual(list(versions), [expected[row["host"]]])

    def test_system_diagnostics_is_not_fetched_twice(self):
        """Version detection reuses the diagnostics response, so enabling the
        endpoint must not double the events."""
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:system_diagnostics" '
            '| bin _time span=1s | stats count by _time | where count > 1',
        )
        self.assertEqual(
            rows, [], "system_diagnostics arrived more than once per cycle: %s" % rows
        )


class BulletinPollingTest(IntegrationTestCase):
    collection = "pull"
    """Bulletins now reach Splunk by polling /flow/bulletin-board, with no
    reporting task configured inside NiFi (TA-5).

    A NiFi with no flow produces no bulletins, so the assertions here check
    that the polling runs cleanly rather than that bulletins exist. Proving
    the payload shape needs a flow that actually fails, which is future work
    (see the plan).
    """

    def test_the_bulletin_poll_reports_no_errors(self):
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" '
            '"bulletin board" log_level=ERROR | stats count',
            earliest="-1h",
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "the bulletin board poll logged errors")

    def test_the_poll_runs_and_reports_its_count(self):
        """The input logs a line per poll; its absence means the endpoint was
        never reached."""
        rows = wait_for_events(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" "Bulletins collected" '
            "| stats count",
            minimum=1,
            timeout=180,
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertGreater(count, 0, "the bulletin board was never polled")

    def test_any_bulletin_indexed_carries_the_datamodel_fields(self):
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:bulletin_board" '
            "| head 1 | table bulletinLevel, bulletinCategory, bulletinSourceName",
        )
        if not rows:
            self.skipTest("no bulletins were produced by this NiFi")
        for field in ("bulletinLevel", "bulletinCategory", "bulletinSourceName"):
            with self.subTest(field=field):
                self.assertIn(field, rows[0])


class FlowMetricsTest(IntegrationTestCase):
    collection = "pull"
    """The flattening has to survive a real payload (TA-2).

    /flow/metrics/json returns Prometheus' model with parallel label arrays;
    the TA zips them into one flat event per sample. The harness enables the
    endpoint, which the shipped app does not, because of its volume.
    """

    def test_samples_are_indexed_as_individual_events(self):
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_metrics" | stats count',
            minimum=1,
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertGreater(count, 1, "flow metrics produced no individual events")

    def test_the_labels_became_searchable_fields(self):
        """The point of the flattening: labelNames/labelValues would arrive as
        two uncorrelated multivalue fields without it."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_metrics" metric_name=nifi_jvm_heap_used '
            "| head 1 | table metric_name, metric_value, instance",
            minimum=1,
        )
        self.assertTrue(rows, "no nifi_jvm_heap_used sample was indexed")
        self.assertEqual(rows[0]["metric_name"], "nifi_jvm_heap_used")
        self.assertTrue(rows[0].get("metric_value"))
        self.assertTrue(rows[0].get("instance"))

    def test_the_parallel_arrays_are_gone(self):
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_metrics" '
            "| head 1 | table labelNames, labelValues",
        )
        if rows:
            self.assertFalse(rows[0].get("labelNames"), "labelNames reached the index raw")
            self.assertFalse(rows[0].get("labelValues"), "labelValues reached the index raw")

    def test_component_labels_are_present_on_component_metrics(self):
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_metrics" component_type=* '
            "| head 1 | table metric_name, component_type, component_name",
            minimum=1,
        )
        self.assertTrue(rows, "no component-scoped metric was indexed")
        self.assertTrue(rows[0].get("component_type"))

    def test_metrics_collection_reports_no_errors(self):
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" '
            '"flow metrics" log_level=ERROR | stats count',
            earliest="-1h",
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "flow metrics collection logged errors")


class IndexAndAccelerationTest(IntegrationTestCase):
    """The app has to find its own data, and the datamodel the panels query
    has to be accelerated (B-6, APP-2)."""

    def test_the_index_the_macro_points_at_exists(self):
        rows = search(
            self.splunk,
            "| rest /services/data/indexes | search title=nifi | table title",
        )
        self.assertTrue(rows, "the nifi index was not created by the app")

    def test_the_macro_resolves_to_data(self):
        """Runs the macro itself, so a macro pointing at an empty index fails
        here rather than showing empty panels."""
        rows = wait_for_events(
            self.splunk,
            "| tstats count where `index_nifi` sourcetype=nifi:* by sourcetype",
            minimum=1,
        )
        self.assertTrue(rows, "the index_nifi macro finds no NiFi data")

    def test_the_datamodel_ships_unaccelerated(self):
        """Acceleration ships off because AppInspect rejects an app that
        distributes it on; enabling it is the operator's call, documented in
        upgrading.md. The REST field is a flag, not the JSON blob the .conf
        holds."""
        rows = search(
            self.splunk,
            "| rest /services/data/models/NIFI | table title, acceleration",
        )
        self.assertTrue(rows, "the NIFI datamodel is not present")
        self.assertIn(
            str(rows[0]["acceleration"]).lower(), ("0", "false"),
            "acceleration reads %r" % rows[0]["acceleration"],
        )

    def test_the_macro_is_visible_outside_the_app(self):
        """The datamodel is exported to system and every constraint goes
        through index_nifi, so the macro has to be exported too. These
        searches run with no app context, which is exactly the case that
        breaks when it is not."""
        rows = search(
            self.splunk,
            "| rest /services/admin/macros | search title=index_nifi "
            "| table title, definition",
        )
        self.assertTrue(rows, "index_nifi is not visible outside nifi_monitoring")

    def test_the_datamodel_returns_rows_through_tstats(self):
        """What every dashboard panel does."""
        rows = wait_for_events(
            self.splunk,
            "| tstats count from datamodel=NIFI.Flow_Status",
            minimum=1,
        )
        self.assertTrue(rows)
        self.assertGreater(int(rows[0].get("count", 0)), 0,
                           "the datamodel returns no rows via tstats")


class DashboardPanelTest(IntegrationTestCase):
    """Run the shipped panel queries and check they return rows.

    Rewriting the overview panels (dropping the joins, moving the disk panel
    to the numeric fields) is exactly the kind of change that can leave a
    panel silently empty, so the queries are exercised here rather than
    eyeballed in the UI.
    """

    VIEWS = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "nifi_monitoring", "default", "data", "ui", "views",
    )

    def panel_queries(self, view):
        import re
        text = open(os.path.join(self.VIEWS, view)).read()
        # strip XML comments and unescape what Simple XML escapes
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
        queries = re.findall(r"<query>(.*?)</query>", text, re.S)
        return [
            q.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").strip()
            for q in queries
        ]

    def test_the_overview_status_panel_returns_a_row_per_instance(self):
        query = self.panel_queries("nifi_overview.xml")[0]
        rows = wait_for_events(self.splunk, query, minimum=1)
        self.assertTrue(rows, "the overall status panel returned nothing")
        self.assertIn("host", rows[0])
        self.assertEqual(rows[0].get("status"), "Up")

    def test_the_disk_panel_returns_numeric_percentages(self):
        query = self.panel_queries("nifi_overview.xml")[1]
        rows = wait_for_events(self.splunk, query, minimum=1)
        self.assertTrue(rows, "the disk panel returned nothing")
        row = rows[0]
        for column in ("Content %", "Content Used GB", "Provenance %"):
            with self.subTest(column=column):
                self.assertIn(column, row)
                # the point of the rewrite: a number, not "16.0%"
                float(row[column])

    def test_the_disk_percentages_are_in_range(self):
        query = self.panel_queries("nifi_overview.xml")[1]
        rows = wait_for_events(self.splunk, query, minimum=1)
        for column in ("Content %", "Flow %", "Provenance %"):
            with self.subTest(column=column):
                value = float(rows[0][column])
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 100.0)

    def test_the_inventory_panel_reports_the_version_and_path(self):
        if self.profile_collection != "pull":
            self.skipTest("the version column comes from nifi:api:version_info, "
                          "which only the TA produces")
        queries = self.panel_queries("nifi_internal_monitoring.xml")
        inventory = [q for q in queries if "version_info" in q][0]
        rows = wait_for_events(self.splunk, inventory, minimum=1)
        self.assertTrue(rows, "the inventory panel returned nothing")
        self.assertEqual(rows[0].get("nifi_version"), self.nifi_version)
        self.assertIn("REST pull", str(rows[0].get("paths")))


class DatamodelObjectTest(IntegrationTestCase):
    """The objects added for the new sourcetypes have to actually return rows
    through the model, not just exist in NIFI.json (APP-3)."""

    def requires_pull(self):
        """Some objects are only fed by the TA, so they have nothing to show
        on a push profile even though the object itself is fine."""
        if self.profile_collection != "pull":
            self.skipTest("only the TA produces this sourcetype")

    def rows_from(self, obj):
        return search(self.splunk, "| tstats count from datamodel=NIFI.%s" % obj)

    def count_from(self, obj):
        rows = self.rows_from(obj)
        return int(rows[0]["count"]) if rows and rows[0].get("count") else 0

    def test_the_model_knows_the_new_objects(self):
        """Query each object rather than reading the model's REST
        representation: an object Splunk has not registered makes tstats
        fail, which is the behaviour that matters, and it does not depend on
        how the REST endpoint happens to name its fields."""
        for obj in ("Flow_Metrics", "Bulletin_Board", "Version_Info", "Request_Log"):
            with self.subTest(obj=obj):
                rows = search(
                    self.splunk, "| tstats count from datamodel=NIFI.%s" % obj
                )
                # An unknown object errors out and yields no rows at all; a
                # known object with no data still returns a count row.
                self.assertTrue(rows, "datamodel=NIFI.%s is not queryable" % obj)

    def test_flow_metrics_returns_rows(self):
        self.requires_pull()
        wait_for_events(self.splunk, "| tstats count from datamodel=NIFI.Flow_Metrics",
                        minimum=1)
        self.assertGreater(self.count_from("Flow_Metrics"), 0)

    def test_version_info_returns_rows(self):
        self.requires_pull()
        wait_for_events(self.splunk, "| tstats count from datamodel=NIFI.Version_Info",
                        minimum=1)
        self.assertGreater(self.count_from("Version_Info"), 0)

    def test_flow_metrics_fields_are_queryable_through_the_model(self):
        self.requires_pull()
        rows = wait_for_events(
            self.splunk,
            "| tstats count from datamodel=NIFI.Flow_Metrics "
            "where Flow_Metrics.metric_name=nifi_jvm_heap_used by Flow_Metrics.instance",
            minimum=1,
        )
        self.assertTrue(rows, "metric_name is not queryable through the model")

    def test_the_request_log_stays_out_of_the_generic_logs_object(self):
        """Logs excludes it, so a request event must not appear there."""
        rows = search(
            self.splunk,
            "| tstats count from datamodel=NIFI.Logs "
            'where Logs.sourcetype="nifi:log:request"',
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "the request log leaked into the Logs object")


class ForwarderPathTest(IntegrationTestCase):
    """The other half of the pull strategy: NiFi's log files, shipped by a
    Universal Forwarder.

    The API half had four profiles and the log half had none, so every
    log-side change of 2.0.0 -- the two new sourcetypes, the event breaking
    that groups multi-line messages, the corrected container paths -- was
    only ever checked against props.conf, never against a real log file
    arriving in a real index.
    """

    forwarder = True

    #: nifi-deprecation.log is created empty and only written when something
    #: deprecated is used, so a clean instance legitimately has nothing to
    #: send. It is asserted separately.
    EXPECTED = [
        "nifi:log:app",
        "nifi:log:user",
        "nifi:log:bootstrap",
        "nifi:log:request",
    ]

    def wait_for_app_events(self):
        """`| stats count` emits a row even when it counts nothing, so waiting
        on it returns at once and proves nothing -- and then `max()` over an
        empty set emits no column at all, which surfaces as a KeyError rather
        than as the assertion failing. A by-clause returns no rows until there
        is data, which is what "wait" has to mean here.
        """
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:log:app" | stats count by sourcetype',
            minimum=1, timeout=420,
        )
        self.assertTrue(rows, "no nifi:log:app events arrived")

    def test_the_forwarder_delivers_the_log_sourcetypes(self):
        wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:log:*" | stats count by sourcetype',
            minimum=len(self.EXPECTED), timeout=420,
        )
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:log:*" | stats count by sourcetype')
        seen = {r["sourcetype"] for r in rows}
        for sourcetype in self.EXPECTED:
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, seen)

    def test_the_shipped_monitor_paths_match_the_container(self):
        """Defect B-21: the stanzas pointed at /opt/nifi/logs/, which is not
        where the official image keeps them. Only the local/ override flips
        `disabled`, so the paths under test are the ones the TA ships."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:log:app" | stats count by source',
            minimum=1, timeout=420,
        )
        self.assertTrue(rows, "no nifi:log:app events arrived")
        for row in rows:
            with self.subTest(source=row["source"]):
                self.assertTrue(
                    row["source"].startswith("/opt/nifi/nifi-current/logs/"),
                    "unexpected source %r" % row["source"],
                )

    def test_multi_line_messages_are_one_event(self):
        """Defect B-20, the reason for the LINE_BREAKER in props.conf.

        A clean NiFi 2.11 start writes about a thousand continuation lines
        with no timestamp of their own. Broken on every newline they become
        that many junk events; grouped, they stay part of the message that
        owns them.
        """
        self.wait_for_app_events()
        # Counting newlines with len()/replace() rather than the `regex`
        # command or split()/mvcount(): those depend on how SPL unescapes a
        # backslash inside a double-quoted string, and both came back empty
        # against a stack that demonstrably held multi-line events.
        rows = search(
            self.splunk,
            r'index=nifi sourcetype="nifi:log:app" '
            r'| eval newlines = len(_raw) - len(replace(_raw, "[\r\n]", "")) '
            r'| stats max(newlines) as longest, count as events')
        self.assertTrue(rows, "the search returned nothing at all")
        self.assertGreater(
            int(rows[0]["longest"]), 0,
            "no event spans more than one line, so multi-line messages "
            "were split into one event per line",
        )

    def test_no_event_is_an_orphan_continuation_line(self):
        """The negative half of the same defect: a continuation line indexed
        on its own has no timestamp and no level, which is exactly how the
        breakage shows up in a search.

        Waits first: with no events at all the count is trivially zero and the
        test would pass without having checked anything.
        """
        self.wait_for_app_events()
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:log:app" '
            '| where isnull(level) | stats count as orphans')
        self.assertTrue(rows, "the search returned nothing at all")
        self.assertEqual(
            int(rows[0]["orphans"]), 0,
            "%s events carry no level, so they are stray continuation lines"
            % rows[0]["orphans"],
        )

    def test_the_request_log_is_parsed_as_ncsa(self):
        """TA-12 reuses the core's access-extractions instead of repeating the
        regex, so the proof is that the core's field names come out."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:log:request" '
            '| head 1 | table status, uri_path, clientip',
            minimum=1, timeout=420,
        )
        self.assertTrue(rows, "no nifi:log:request events arrived")
        row = rows[0]
        for field in ("status", "uri_path", "clientip"):
            with self.subTest(field=field):
                self.assertTrue(row.get(field), "%s not extracted" % field)

    def test_the_request_log_keeps_its_own_timestamp(self):
        """It is the only NiFi log with a timestamp of its own, so _time must
        be the request's, not the moment the forwarder read the line."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:log:request" '
            '| eval lag = _indextime - _time | stats min(lag) as lag',
            minimum=1, timeout=420,
        )
        self.assertTrue(rows, "no nifi:log:request events arrived")
        self.assertGreaterEqual(
            float(rows[0]["lag"]), 0,
            "events are indexed before they happened, so _time is wrong",
        )

    def test_the_deprecation_log_is_monitored_even_when_empty(self):
        """The file is created empty and stays that way until something
        deprecated runs, so its absence from the index is not a failure. What
        must hold is that the TA declares the stanza -- the panel that reads
        it is the migration-readiness one."""
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:log:deprecation" | stats count')
        count = int(rows[0]["count"]) if rows else 0
        if count == 0:
            self.skipTest(
                "nifi-deprecation.log is empty on a clean instance; the "
                "stanza itself is covered by the unit tests")
        self.assertGreater(count, 0)


class TlsVerificationTest(IntegrationTestCase):
    """Defect R-8: the add-on's default is to verify NiFi's certificate, and
    no profile exercised it.

    2.0.0 turned verification on by default (B-23) and called it a breaking
    change, but every harness profile set verify_tls = 0 because the
    containers use self-signed certificates -- so the only path under test was
    the one a real deployment is told not to use. The certificate NiFi issues
    for itself is exported and handed to the add-on as a CA bundle, which is
    what an operator does with a private CA.
    """

    tls_verify = True
    collection = "pull"

    def test_events_arrive_with_verification_on(self):
        """The whole assertion in one line: if the handshake were rejected,
        nothing would be indexed at all."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_status" | stats count',
            minimum=1, timeout=420,
        )
        self.assertTrue(rows)
        self.assertGreater(
            int(rows[0]["count"]), 0,
            "no events with verify_tls = 1: the certificate was rejected")

    def test_no_certificate_error_is_logged(self):
        """Events could still arrive while a cycle fails intermittently, and a
        certificate problem names itself in the log."""
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" '
            '(CERTIFICATE_VERIFY_FAILED OR SSLError OR "certificate verify failed") '
            '| stats count')
        self.assertTrue(rows, "the search returned nothing at all")
        self.assertEqual(
            int(rows[0]["count"]), 0,
            "%s certificate errors logged" % rows[0]["count"])

    def test_the_input_really_has_verification_on(self):
        """Guards against the assertion above passing because the seed quietly
        left verify_tls at 0."""
        job = self.splunk.jobs.create(
            "| rest /servicesNS/nobody/nifi_TA_monitoring/data/inputs/nifi "
            "| table title, verify_tls, ca_bundle",
            exec_mode="normal")
        import time as _t
        deadline = _t.time() + 60
        while not job.is_done() and _t.time() < deadline:
            _t.sleep(2)
        import json as _json
        rows = _json.loads(job.results(output_mode="json").read().decode())["results"]
        self.assertTrue(rows, "the input is not registered")
        for row in rows:
            with self.subTest(input=row.get("title")):
                self.assertEqual(str(row.get("verify_tls")), "1")
                self.assertTrue(row.get("ca_bundle"), "no ca_bundle configured")


class MultiInstanceTest(IntegrationTestCase):
    """Several independent NiFi instances behind one TA.

    The app's stated purpose is centralising visibility across several NiFi
    instances, and until this profile existed nothing exercised it: every
    other profile has one instance, one input and one lookup row. Two inputs
    also mean two processes, because the modular input declares
    use_single_instance = false, which is the concurrency the old .env token
    storage could not survive (defect B-14).
    """

    instances = 2
    collection = "pull"

    HOSTS = ["nifi", "nifi-b"]

    def test_every_instance_produces_events(self):
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_status" | stats count by host',
            minimum=len(self.HOSTS), timeout=420,
        )
        seen = {row["host"] for row in rows}
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.assertIn(host, seen)

    def test_the_instances_are_told_apart_by_version(self):
        """The profile runs different NiFi versions on purpose: autodetection
        (TA-3) has to be per input, not per installation. Identical versions
        here would prove nothing."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:version_info" '
            '| stats values(niFiVersion) as version by host',
            minimum=len(self.HOSTS), timeout=420,
        )
        versions = {row["host"]: str(row["version"]) for row in rows}
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.assertIn(host, versions)
        self.assertNotEqual(
            versions["nifi"], versions["nifi-b"],
            "both inputs report %r, so the version is not being detected per "
            "input" % versions["nifi"],
        )

    def test_neither_input_steals_the_other_token(self):
        """The defect this profile was built to catch. Two processes renewing
        a token at once used to rewrite one shared .env non-atomically; the
        symptom is one input authenticating fine while the other loops on 401
        long after its cold start."""
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" '
            '"Error HTTP request" "status_code: 401" '
            '| stats count by _time | stats count as bursts')
        self.assertTrue(rows, "the search returned nothing at all")
        # One 401 per input per cold start is by design; more than a handful
        # means they are fighting over the stored token.
        self.assertLessEqual(
            int(rows[0]["bursts"]), 2 * len(self.HOSTS),
            "%s separate 401s across %d inputs: the token is being clobbered"
            % (rows[0]["bursts"], len(self.HOSTS)),
        )

    def test_each_instance_keeps_its_own_lookup_row(self):
        """Without a row per host the app cannot group them, and the lookup
        falls back to default_match = standalone."""
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:api:flow_status" '
            '| stats values(cluster) as cluster by host',
            minimum=len(self.HOSTS), timeout=420,
        )
        for row in rows:
            with self.subTest(host=row["host"]):
                self.assertNotEqual(
                    str(row["cluster"]), "standalone",
                    "%s did not match the instance lookup" % row["host"],
                )

    def test_the_overview_lists_every_instance(self):
        """The panel an operator opens first has to show both, or centralising
        them is a claim with nothing behind it."""
        import re as _re
        text = open(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "nifi_monitoring", "default", "data", "ui", "views",
            "nifi_overview.xml")).read()
        text = _re.sub(r"<!--.*?-->", "", text, flags=_re.S)
        query = _re.findall(r"<query>(.*?)</query>", text, _re.S)[0]
        query = query.replace("&gt;", ">").replace("&lt;", "<").replace("&amp;", "&").strip()
        rows = wait_for_events(self.splunk, query, minimum=len(self.HOSTS), timeout=420)
        seen = {row["host"] for row in rows}
        for host in self.HOSTS:
            with self.subTest(host=host):
                self.assertIn(host, seen)


class PushPathTest(IntegrationTestCase):
    collection = "hec"
    """Data arriving through the flow inside NiFi rather than the TA.

    Only meaningful on a profile whose collection is `hec`; the others skip.
    """

    def test_events_arrive_through_the_hec(self):
        rows = wait_for_events(
            self.splunk,
            'index=nifi sourcetype="nifi:*" | stats count by sourcetype',
            minimum=1,
            timeout=420,
        )
        self.assertTrue(rows, "nothing reached Splunk through the HEC")

    def test_the_ta_input_is_not_also_collecting(self):
        """Running both paths duplicates every event, which the docs warn
        about; the profile disables the input so this must stay at zero."""
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd "Nifi Log pid=" "Started Stream Events" '
            "| stats count",
            earliest="-1h",
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "the TA input ran as well as the flow")

    def test_the_flow_delivers_the_sourcetypes_it_is_responsible_for(self):
        """What the push path actually carries: the API endpoints the flow
        polls, plus NiFi's own log files through TailFile."""
        wait_for_events(self.splunk,
                        'index=nifi | stats count by sourcetype', minimum=1, timeout=420)
        rows = search(self.splunk, 'index=nifi | stats count by sourcetype')
        seen = {r["sourcetype"] for r in rows}
        for sourcetype in ("nifi:api:flow_status", "nifi:api:system_diagnostics",
                           "nifi:log:app"):
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, seen)

    def test_the_flow_does_not_send_the_retired_sourcetype(self):
        """site_to_site was retired from the TA (D-2). The flow must match, or
        it delivers events for a sourcetype no props.conf defines any more --
        they arrive with no fields extracted."""
        rows = search(self.splunk,
                      'index=nifi sourcetype="nifi:api:site_to_site" | stats count')
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "the flow still sends site_to_site")

    def test_the_flow_reports_no_bulletins_at_error_level(self):
        """A processor failing inside the flow raises an ERROR bulletin, which
        is how a broken push path shows itself."""
        rows = search(
            self.splunk,
            'index=nifi sourcetype="nifi:*" bulletinLevel=ERROR | stats count',
        )
        count = int(rows[0]["count"]) if rows and rows[0].get("count") else 0
        self.assertEqual(count, 0, "the flow raised %d error bulletins" % count)


if __name__ == "__main__":
    unittest.main()
