"""Tests for bulletin board polling in bin/nifi.py (TA-5).

Individual bulletins used to reach Splunk only through
SiteToSiteBulletinReportingTask, which means configuring a reporting task
and a Site-to-Site input port inside the customer's NiFi. Polling
/flow/bulletin-board needs nothing on the NiFi side.

The trade-off is real and deliberate: the board keeps a limited window
(5 minutes by default), so an interval longer than that window loses
bulletins. ?after=<id> keeps the polling from duplicating what it has
already seen, but cannot recover what NiFi already dropped. Both paths stay
supported; polling is the default.
"""

import json
import os
import tempfile
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response


def entry(entry_id, level="ERROR", **bulletin):
    """A /flow/bulletin-board entry, shaped like BulletinEntity."""
    payload = {
        "id": entry_id,
        "category": "Log Message",
        "groupId": "1a66c95c-1283-3811-9208-dc9a6e0d2933",
        "sourceId": "c45766f3-018e-1000-d4c4-8bc3e0de9c9e",
        "sourceName": "InvokeHTTP",
        "level": level,
        "message": "Failed to invoke HTTP request",
    }
    payload.update(bulletin)
    return {
        "id": entry_id,
        "groupId": payload["groupId"],
        "sourceId": payload["sourceId"],
        "canRead": True,
        "bulletin": payload,
    }


def board(*entries):
    return json.dumps({"bulletinBoard": {"bulletins": list(entries)}})


class BulletinParsingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        script = load_nifi_module()[0].NiFiScript
        cls.bulletins_of = staticmethod(script.bulletins_of)
        cls.highest = staticmethod(script.highest_bulletin_id)

    def test_reads_the_entries(self):
        parsed = self.bulletins_of(board(entry(1), entry(2)))
        self.assertEqual([item["id"] for item in parsed], [1, 2])

    def test_an_empty_board_is_an_empty_list_not_a_failure(self):
        """A quiet NiFi is the normal case and must not look like an error."""
        self.assertEqual(self.bulletins_of(json.dumps({"bulletinBoard": {"bulletins": []}})), [])
        self.assertEqual(self.bulletins_of(json.dumps({"bulletinBoard": {"bulletins": None}})), [])

    def test_an_unreadable_response_is_distinguishable_from_an_empty_one(self):
        for payload in (None, "", "not json", "{}"):
            with self.subTest(payload=payload):
                self.assertIsNone(self.bulletins_of(payload))

    def test_highest_id_drives_the_next_poll(self):
        self.assertEqual(self.highest([entry(7), entry(42), entry(13)]), 42)

    def test_highest_id_falls_back_to_the_nested_id(self):
        item = entry(5)
        del item["id"]
        self.assertEqual(self.highest([item]), 5)

    def test_highest_id_of_nothing_is_none(self):
        self.assertIsNone(self.highest([]))


class BulletinCollectionTest(NiFiScriptTestCase):

    def setUp(self):
        super().setUp()
        self.checkpoint_dir = tempfile.mkdtemp()
        self.script._input_definition = mock.MagicMock()
        self.script._input_definition.metadata = {
            "session_key": "sk",
            "checkpoint_dir": self.checkpoint_dir,
        }
        self.writer = mock.MagicMock()

    def collect(self, payload):
        self.http.get.side_effect = [response(200, payload)]
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script._NiFiScript__collect_bulletins(
                self.writer,
                "http://nifi:8080/nifi-api",
                "/flow/bulletin-board",
                "nifi:api:bulletin_board",
                "none",
                "user",
                "instance",
                "sk",
                "nifi://instance",
                {"host": "nifi"},
            )
        return self.http.get.call_args_list[-1].args[0]

    def written(self):
        return [
            json.loads(call.args[0].data)
            for call in self.writer.write_event.call_args_list
        ]

    def test_one_event_per_bulletin(self):
        self.collect(board(entry(1), entry(2), entry(3)))
        self.assertEqual([item["id"] for item in self.written()], [1, 2, 3])

    def test_events_carry_the_declared_sourcetype(self):
        self.collect(board(entry(1)))
        self.assertEqual(
            self.writer.write_event.call_args.args[0].sourceType,
            "nifi:api:bulletin_board",
        )

    def test_the_first_poll_asks_for_everything(self):
        url = self.collect(board(entry(1)))
        self.assertIn("limit=", url)
        self.assertNotIn("after=", url)

    def test_the_next_poll_resumes_after_the_highest_id(self):
        self.collect(board(entry(1), entry(9)))
        self.writer.reset_mock()
        url = self.collect(board(entry(10)))
        self.assertIn("after=9", url)

    def test_an_empty_board_leaves_the_checkpoint_alone(self):
        """Otherwise a quiet interval would reset the cursor and re-index
        everything still on the board."""
        self.collect(board(entry(4)))
        url_after_empty = self.collect(board())
        self.assertIn("after=4", url_after_empty)
        url_next = self.collect(board())
        self.assertIn("after=4", url_next)

    def test_an_unreadable_response_writes_no_events(self):
        self.collect("not json")
        self.assertEqual(self.written(), [])

    def test_the_checkpoint_survives_a_new_script_instance(self):
        """Splunk runs the input as a fresh process each interval, so the
        cursor has to live on disk, not in memory."""
        self.collect(board(entry(21)))
        fresh = self.nifi.NiFiScript()
        fresh._input_definition = self.script._input_definition
        self.http.get.side_effect = [response(200, board())]
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            fresh._NiFiScript__collect_bulletins(
                self.writer, "http://nifi:8080/nifi-api", "/flow/bulletin-board",
                "nifi:api:bulletin_board", "none", "user", "instance", "sk",
                "nifi://instance", {"host": "nifi"},
            )
        self.assertIn("after=21", self.http.get.call_args_list[-1].args[0])

    def test_missing_checkpoint_dir_does_not_break_collection(self):
        """Without a checkpoint the input still works; it just re-reads the
        board each time rather than crashing."""
        self.script._input_definition.metadata = {"session_key": "sk"}
        self.collect(board(entry(1), entry(2)))
        self.assertEqual(len(self.written()), 2)


class BulletinFieldMappingTest(unittest.TestCase):
    """props.conf has to map the board's shape onto the field names the NIFI
    datamodel already uses, or the existing dashboards see nothing."""

    @classmethod
    def setUpClass(cls):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cls.props = open(
            os.path.join(repo, "nifi_TA_monitoring", "default", "props.conf")
        ).read()
        cls.datamodel = json.load(
            open(os.path.join(repo, "nifi_monitoring", "default", "data", "models", "NIFI.json"))
        )

    def stanza(self, name):
        body = self.props.split("[%s]" % name, 1)[1]
        return body.split("\n[", 1)[0]

    def test_the_bulletin_stanza_exists(self):
        self.assertIn("[nifi:api:bulletin_board]", self.props)

    def test_a_stack_trace_is_not_truncated(self):
        """A bulletin carries the stack trace of whatever failed; the 10k
        default would cut it and swallow the following event."""
        self.assertIn("TRUNCATE = 0", self.stanza("nifi:api:bulletin_board"))

    def test_datamodel_bulletin_fields_are_aliased_where_the_board_has_them(self):
        obj = [o for o in self.datamodel["objects"] if o["objectName"] == "Reporting_Bulletin"][0]
        wanted = {f["fieldName"] for f in obj["fields"]}
        stanza = self.stanza("nifi:api:bulletin_board")
        for field in ("bulletinCategory", "bulletinGroupId", "bulletinLevel",
                      "bulletinSourceName", "bulletinSourceType"):
            with self.subTest(field=field):
                self.assertIn(field, wanted, "%s is not in the datamodel" % field)
                self.assertIn("AS %s" % field, stanza)

    def test_the_two_unavailable_fields_are_documented_as_such(self):
        """bulletinGroupName and bulletinGroupPath only come from the reporting
        task: the board carries the group id but never resolves its name."""
        stanza = self.stanza("nifi:api:bulletin_board")
        self.assertNotIn("AS bulletinGroupName", stanza)
        self.assertNotIn("AS bulletinGroupPath", stanza)
        self.assertIn("bulletinGroupName", stanza)  # named in the comment


class CapturedPayloadTest(unittest.TestCase):
    """Validate the field mapping against a bulletin captured from a real
    NiFi, not against the DTO definitions it was written from.

    docs/plans/samples/nifi2.11-bulletin-board.json holds five bulletins
    provoked on purpose (an InvokeHTTP pointed at a closed port) with
    tests/integration/capture_bulletin.py.
    """

    @classmethod
    def setUpClass(cls):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(repo, "docs", "plans", "samples",
                               "nifi2.11-bulletin-board.json")) as handle:
            cls.board = json.load(handle)
        cls.props = open(
            os.path.join(repo, "nifi_TA_monitoring", "default", "props.conf")
        ).read()
        cls.entry = cls.board["bulletinBoard"]["bulletins"][0]
        script = load_nifi_module()[0].NiFiScript
        cls.bulletins_of = staticmethod(script.bulletins_of)
        cls.highest = staticmethod(script.highest_bulletin_id)

    def aliases(self):
        import re
        stanza = self.props.split("[nifi:api:bulletin_board]", 1)[1].split("\n[", 1)[0]
        return re.findall(r'FIELDALIAS-\S+ = "([^"]+)" AS (\S+)', stanza)

    def resolve(self, path, node):
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node

    def test_the_parser_reads_the_captured_board(self):
        parsed = self.bulletins_of(json.dumps(self.board))
        self.assertEqual(len(parsed), 5)

    def test_the_checkpoint_id_is_derived_from_the_captured_board(self):
        parsed = self.bulletins_of(json.dumps(self.board))
        self.assertIsNotNone(self.highest(parsed))

    def test_every_alias_resolves_against_the_captured_bulletin(self):
        """Except nodeAddress, which only a cluster populates."""
        for source, target in self.aliases():
            with self.subTest(alias=target):
                value = self.resolve(source, self.entry)
                if source.endswith("nodeAddress"):
                    self.assertIsNone(value, "standalone NiFi should omit it")
                    continue
                self.assertIsNotNone(value, "%s is absent from a real bulletin" % source)

    def test_the_level_and_category_carry_the_values_dashboards_filter_on(self):
        self.assertEqual(self.resolve("bulletin.level", self.entry), "ERROR")
        self.assertEqual(self.resolve("bulletin.category", self.entry), "Log Message")
        self.assertEqual(self.resolve("bulletin.sourceType", self.entry), "PROCESSOR")

    def test_a_real_bulletin_carries_a_stack_trace_worth_not_truncating(self):
        """The reason TRUNCATE = 0 is on this stanza."""
        trace = self.resolve("bulletin.stackTrace", self.entry)
        self.assertIsNotNone(trace)
        self.assertGreater(len(trace), 500)

    def test_the_plain_timestamp_has_no_date_and_the_iso_one_does(self):
        """Why DATETIME_CONFIG stays CURRENT: bulletin.timestamp is a wall
        clock with no date, and timestampIso does not exist before NiFi 2.0."""
        self.assertNotIn("-", self.resolve("bulletin.timestamp", self.entry))
        self.assertRegex(
            self.resolve("bulletin.timestampIso", self.entry),
            r"^\d{4}-\d{2}-\d{2}T",
        )


if __name__ == "__main__":
    unittest.main()
