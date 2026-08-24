"""Does data actually reach Splunk, and are the fields extracted?

The old harness brought up containers and stopped there: nothing verified
that events arrived or that the app could read them. These are the checks
that make "the tests pass" mean something.

Skipped automatically when no stack is running, so `python3 -m unittest
discover` stays safe to run anywhere.
"""

import unittest

from support import IntegrationTestCase, search, wait_for_events

# Sourcetypes the TA's pull path must produce in every supported version.
CORE_SOURCETYPES = [
    "nifi:api:flow_status",
    "nifi:api:system_diagnostics",
]


class IngestTest(IntegrationTestCase):

    def test_the_modular_input_produces_events(self):
        rows = wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:*" | stats count by sourcetype',
            minimum=1,
        )
        self.assertTrue(
            rows, "no nifi:api:* events reached Splunk; check the input and splunkd.log"
        )

    def test_every_core_sourcetype_arrives(self):
        wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:*" | stats count by sourcetype',
            minimum=len(CORE_SOURCETYPES),
        )
        rows = search(
            self.splunk,
            'index=main sourcetype="nifi:api:*" | stats count by sourcetype',
        )
        seen = {row["sourcetype"] for row in rows}
        for sourcetype in CORE_SOURCETYPES:
            with self.subTest(sourcetype=sourcetype):
                self.assertIn(sourcetype, seen)

    def test_flow_status_fields_are_extracted(self):
        """INDEXED_EXTRACTIONS must turn the JSON into the datamodel's fields."""
        rows = wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:flow_status" '
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
            'index=main sourcetype="nifi:api:flow_status" '
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
            'index=main sourcetype="nifi:api:*" | stats max(_time) as last_event',
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

        # flow_status, system_diagnostics and site_to_site are enabled by the
        # harness input; each can pay at most one 401 before the token is
        # cached, and a cold start can happen twice if a container is recreated.
        ceiling = 3 * 2
        self.assertLessEqual(
            error_count,
            ceiling,
            "%d errors is more than a bounded startup (<=%d): the input is "
            "erroring on every request" % (error_count, ceiling),
        )


class VersionDetectionTest(IntegrationTestCase):
    """The TA detects which NiFi it is talking to and records it.

    Detection reads versionInfo.niFiVersion from /system-diagnostics, which
    exists on both the 1.x and 2.x lines, so this must work on every profile.
    """

    def test_the_detected_version_is_indexed(self):
        rows = wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:version_info" '
            "| head 1 | table niFiVersion, javaVersion",
            minimum=1,
        )
        self.assertTrue(rows, "no nifi:api:version_info event was indexed")
        self.assertEqual(rows[0].get("niFiVersion"), self.nifi_version)

    def test_the_detected_version_matches_the_profile(self):
        """A mismatch means the harness and the TA disagree about what is
        running, which would make every other assertion suspect."""
        rows = wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:version_info" '
            "| stats values(niFiVersion) as versions",
            minimum=1,
        )
        self.assertTrue(rows)
        versions = rows[0]["versions"]
        if isinstance(versions, str):
            versions = [versions]
        self.assertEqual(list(versions), [self.nifi_version])

    def test_system_diagnostics_is_not_fetched_twice(self):
        """Version detection reuses the diagnostics response, so enabling the
        endpoint must not double the events."""
        rows = search(
            self.splunk,
            'index=main sourcetype="nifi:api:system_diagnostics" '
            '| bin _time span=1s | stats count by _time | where count > 1',
        )
        self.assertEqual(
            rows, [], "system_diagnostics arrived more than once per cycle: %s" % rows
        )


if __name__ == "__main__":
    unittest.main()
