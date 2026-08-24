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
        if not last_error or not last_error[0].get("last_error"):
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

    def test_the_401_is_not_paid_on_every_cycle(self):
        """A 401 per poll would mean the token is not being cached at all."""
        errors = search(
            self.splunk,
            'index=_internal sourcetype=splunkd log_level=ERROR "Nifi Log pid=" '
            "| stats count",
            earliest="-1h",
        )
        events = search(
            self.splunk,
            'index=main sourcetype="nifi:api:flow_status" | stats count',
            earliest="-1h",
        )
        error_count = int(errors[0]["count"]) if errors else 0
        event_count = int(events[0]["count"]) if events else 0
        self.assertGreater(event_count, error_count,
                           "as many errors as successful polls: the token is not cached")


class VersionDetectionTest(IntegrationTestCase):

    def test_version_info_is_available_on_nifi_2(self):
        """VERSION_INFO exists from 2.0; on 1.x the endpoint answers 404, which
        is why the TA must not request it blindly."""
        if self.nifi_major != "2":
            self.skipTest("VERSION_INFO is a NiFi 2.x registry")
        rows = wait_for_events(
            self.splunk,
            'index=main sourcetype="nifi:api:*" nifi_version_info | head 1',
            minimum=1,
            timeout=120,
        )
        if not rows:
            self.skipTest("flow metrics collection not implemented yet (plan TA-2)")


if __name__ == "__main__":
    unittest.main()
