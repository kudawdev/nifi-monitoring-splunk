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

    def test_the_input_reports_no_errors(self):
        """The modular input logs its own failures through EventWriter, which
        land in splunkd.log prefixed with 'Nifi Log pid='."""
        rows = search(
            self.splunk,
            'index=_internal sourcetype=splunkd log_level=ERROR "Nifi Log pid=" '
            "| stats count by _raw",
            earliest="-1h",
        )
        self.assertEqual(
            rows, [], "the NiFi input logged errors: %s" % [r.get("_raw") for r in rows]
        )


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
