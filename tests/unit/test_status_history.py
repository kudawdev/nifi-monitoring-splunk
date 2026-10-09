"""Tests for the flat status-history events in bin/nifi.py (R-3).

The input used to index the whole /status/history response -- field
descriptors, component details and the nested snapshot array -- as one event
stamped with the collection time, and the Components view rebuilt the series
at search time with spath and mvexpand. Now the TA writes one event per
snapshot, with the snapshot's own time, and resumes from the newest snapshot
it wrote for each component.
"""

import json
import os
import tempfile
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response

SAMPLES = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                       "docs", "plans", "samples")
PROCESSOR_ID = "8c1e4a2b-0191-1000-3a9e-5f2d7c1b0e44"
GROUP_ID = "1a66c95c-1283-3811-9208-dc9a6e0d2933"


def history(*timestamps, name="PutDatabaseRecord", **details):
    """A /flow/processors/{id}/status/history body, shaped like
    StatusHistoryEntity, with one snapshot per timestamp."""
    component = {
        "Id": PROCESSOR_ID,
        "Name": name,
        "Type": "PutDatabaseRecord",
        "Group Id": GROUP_ID,
    }
    component.update(details)
    return json.dumps({"statusHistory": {
        "generated": "11:58:00 UTC",
        "componentDetails": component,
        "fieldDescriptors": [{"field": "taskMillis", "label": "Total Task Duration",
                              "description": "...", "formatter": "DURATION"}],
        "aggregateSnapshots": [
            {"timestamp": ts, "statusMetrics": {"taskMillis": 100 + i, "inputCount": 10 * i}}
            for i, ts in enumerate(timestamps)
        ],
    }})


class SnapshotParsingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        script = load_nifi_module()[0].NiFiScript
        cls.script = script
        cls.snapshots = staticmethod(script.status_snapshots)
        cls.after = staticmethod(script.snapshots_after)

    def test_one_flat_event_per_snapshot(self):
        events = self.snapshots(history(1790859420000, 1790859480000), "processor")
        self.assertEqual(len(events), 2)
        first = events[0]
        self.assertEqual(first["component_id"], PROCESSOR_ID)
        self.assertEqual(first["component_name"], "PutDatabaseRecord")
        self.assertEqual(first["component_type"], "processor")
        self.assertEqual(first["group_id"], GROUP_ID)
        self.assertEqual(first["timestamp"], 1790859420000)
        self.assertEqual(first["taskMillis"], 100)
        self.assertEqual(first["inputCount"], 0)

    def test_the_field_descriptors_are_not_repeated_in_every_event(self):
        """They describe the metrics, not the snapshot, and moved to the
        app's nifi_status_metrics lookup."""
        for event in self.snapshots(history(1790859420000), "processor"):
            self.assertNotIn("fieldDescriptors", event)
            self.assertNotIn("statusMetrics", event)

    def test_a_numeric_string_timestamp_is_read_as_milliseconds(self):
        events = self.snapshots(history("1790859420000"), "processor")
        self.assertEqual(events[0]["timestamp"], 1790859420000)

    def test_a_snapshot_without_a_usable_time_is_skipped(self):
        events = self.snapshots(history(None, "11:58:00 UTC", 1790859420000), "processor")
        self.assertEqual([e["timestamp"] for e in events], [1790859420000])

    def test_snapshots_come_out_oldest_first(self):
        events = self.snapshots(history(1790859480000, 1790859420000), "processor")
        self.assertEqual([e["timestamp"] for e in events], [1790859420000, 1790859480000])

    def test_an_unreadable_response_is_not_an_empty_history(self):
        for payload in (None, "", "not json", "{}"):
            with self.subTest(payload=payload):
                self.assertIsNone(self.snapshots(payload, "processor"))

    def test_the_first_poll_does_not_backfill_the_whole_window(self):
        """NiFi returns every retained snapshot; indexing days of them the
        first time a component is configured is a licence spike."""
        timestamps = [1790859420000 + 60000 * i for i in range(500)]
        events = self.snapshots(history(*timestamps), "processor")
        fresh = self.after(events, None)
        self.assertEqual(len(fresh), self.script.history_backfill_snapshots)
        self.assertEqual(fresh[-1]["timestamp"], timestamps[-1])

    def test_later_polls_take_only_what_is_newer_than_the_cursor(self):
        events = self.snapshots(history(1, 2, 3, 4), "processor")
        self.assertEqual([e["timestamp"] for e in self.after(events, 2)], [3, 4])
        self.assertEqual(self.after(events, 4), [])


class SnapshotCollectionTest(NiFiScriptTestCase):

    def setUp(self):
        super().setUp()
        self.checkpoint_dir = tempfile.mkdtemp()
        self.script._input_definition = mock.MagicMock()
        self.script._input_definition.metadata = {
            "session_key": "sk",
            "checkpoint_dir": self.checkpoint_dir,
        }
        self.writer = mock.MagicMock()

    def collect(self, *payloads, ids=(PROCESSOR_ID,)):
        self.writer.reset_mock()
        self.http.get.side_effect = [response(200, p) for p in payloads]
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script._NiFiScript__collect_status_history(
                self.writer, "http://nifi:8080/nifi-api",
                "/flow/processors/{id}/status/history", "nifi:api:processors_status",
                "processor", list(ids), "none", "user", "instance", "sk",
                "nifi://instance", {"host": "nifi"},
            )

    def written(self):
        return [call.args[0] for call in self.writer.write_event.call_args_list]

    def test_events_carry_the_new_sourcetype_and_the_snapshot_time(self):
        self.collect(history(1790859420000))
        event = self.written()[0]
        self.assertEqual(event.sourceType, "nifi:api:processors_status")
        self.assertEqual(float(event.time), 1790859420.0)
        self.assertEqual(json.loads(event.data)["component_type"], "processor")

    def test_the_next_poll_does_not_index_a_snapshot_twice(self):
        self.collect(history(1790859420000, 1790859480000))
        self.assertEqual(len(self.written()), 2)
        self.collect(history(1790859420000, 1790859480000, 1790859540000))
        self.assertEqual([json.loads(e.data)["timestamp"] for e in self.written()],
                         [1790859540000])

    def test_a_quiet_poll_leaves_the_cursor_alone(self):
        self.collect(history(1790859420000))
        self.collect(history(1790859420000))
        self.assertEqual(self.written(), [])
        self.collect(history(1790859420000, 1790859480000))
        self.assertEqual(len(self.written()), 1)

    def test_each_component_has_its_own_cursor(self):
        other = "c45766f3-018e-1000-d4c4-8bc3e0de9c9e"
        self.collect(history(5000), history(9000, name="Other", Id=other),
                     ids=(PROCESSOR_ID, other))
        self.assertEqual(len(self.written()), 2)
        self.collect(history(5000, 6000), history(9000), ids=(PROCESSOR_ID, other))
        self.assertEqual([json.loads(e.data)["timestamp"] for e in self.written()], [6000])

    def test_an_unreadable_response_writes_nothing(self):
        self.collect("not json")
        self.assertEqual(self.written(), [])


class EndpointFlagTest(NiFiScriptTestCase):
    """An endpoint flag is any boolean Splunk accepts, not only "1".

    `endpoint_flow_status = True` -- which is what Splunk's REST API writes
    back when an input is updated through it -- used to switch flow status,
    system diagnostics and the bulletin board off without a word, while
    flow metrics, read through _is_enabled, kept going.
    """

    def requested(self, **flags):
        item = {"api_url": "http://nifi:8080/nifi-api", "auth_type": "none", "host": "nifi"}
        item.update(flags)
        inputs = mock.MagicMock()
        inputs.inputs.popitem.return_value = ("nifi://instance", item)
        self.script._input_definition = mock.MagicMock()
        self.script._input_definition.metadata = {"session_key": "sk"}
        with open(os.path.join(SAMPLES, "nifi2.11-system-diagnostics.json")) as handle:
            diagnostics = handle.read()
        self.http.get.side_effect = lambda url, **kw: response(
            200, diagnostics if url.endswith("/system-diagnostics") else "{}")
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script.stream_events(inputs, writer)
        return [call.args[0] for call in self.http.get.call_args_list], writer

    def test_true_enables_an_endpoint(self):
        for value in ("1", "true", "True", "yes"):
            with self.subTest(value=value):
                self.http.get.reset_mock()
                urls, writer = self.requested(endpoint_flow_status=value,
                                              endpoint_system_diagnostics=value)
                self.assertTrue(any(u.endswith("/flow/status") for u in urls), urls)
                sourcetypes = [c.args[0].sourceType for c in writer.write_event.call_args_list]
                self.assertIn("nifi:api:system_diagnostics", sourcetypes)

    def test_false_disables_it(self):
        for value in ("0", "false", "False"):
            with self.subTest(value=value):
                self.http.get.reset_mock()
                urls, _ = self.requested(endpoint_flow_status=value, endpoint_system_diagnostics="0")
                self.assertFalse(any(u.endswith("/flow/status") for u in urls), urls)

    def test_the_bulletin_board_stays_on_when_the_flag_says_true(self):
        urls, _ = self.requested(endpoint_flow_status="0", endpoint_system_diagnostics="0",
                                 endpoint_bulletin_board="True")
        self.assertTrue(any("/flow/bulletin-board" in u for u in urls), urls)


if __name__ == "__main__":
    unittest.main()
