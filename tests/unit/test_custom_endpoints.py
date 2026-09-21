"""Tests for custom, user-declared endpoints in bin/nifi.py.

Feature request from a customer (docs/support/2026-09-08-correo-cliente-ta.md):
the fixed `endpoints` table only covers what the app ships with, and there was
no way to poll a NiFi REST path outside that list without a code change.
`custom_endpoints` lets an input declare any number of additional
'sourcetype,path' pairs; the TA polls each one and passes the response
through unchanged under the sourcetype given.
"""

import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response


class ValidateCustomEndpointTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def validate(self, sourcetype, path):
        return self.nifi.NiFiScript._validate_custom_endpoint(sourcetype, path)

    def test_a_normal_endpoint_is_accepted(self):
        self.assertIsNone(self.validate("nifi:api:custom:queue_stats", "/flow/connections/1234/status"))

    def test_an_empty_sourcetype_is_rejected(self):
        self.assertIn("sourcetype is empty", self.validate("", "/flow/status"))

    def test_a_sourcetype_with_spaces_is_rejected(self):
        self.assertIn("letters, digits", self.validate("nifi custom", "/flow/status"))

    def test_an_empty_path_is_rejected(self):
        self.assertIn("path is empty", self.validate("nifi:api:custom:x", ""))

    def test_a_path_without_a_leading_slash_is_rejected(self):
        self.assertIn("must start with /", self.validate("nifi:api:custom:x", "flow/status"))

    def test_a_full_url_is_rejected_instead_of_a_relative_path(self):
        self.assertIn("must be a relative path", self.validate("nifi:api:custom:x", "http://evil.example/x"))

    def test_a_path_with_whitespace_is_rejected(self):
        self.assertIn("must not contain whitespace", self.validate("nifi:api:custom:x", "/flow /status"))


class ParseCustomEndpointsTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def parse(self, raw):
        return self.nifi.NiFiScript._parse_custom_endpoints(raw)

    def test_empty_input_yields_nothing(self):
        self.assertEqual(self.parse(""), [])
        self.assertEqual(self.parse(None), [])

    def test_one_line_per_endpoint(self):
        raw = "nifi:api:custom:a,/path/a\nnifi:api:custom:b,/path/b"
        self.assertEqual(self.parse(raw), [
            {"sourcetype": "nifi:api:custom:a", "path": "/path/a"},
            {"sourcetype": "nifi:api:custom:b", "path": "/path/b"},
        ])

    def test_blank_lines_and_comments_are_ignored(self):
        raw = "\n# a comment\nnifi:api:custom:a,/path/a\n\n"
        self.assertEqual(self.parse(raw), [{"sourcetype": "nifi:api:custom:a", "path": "/path/a"}])

    def test_a_path_with_a_query_string_comma_is_kept_whole(self):
        """Only the first comma splits the line, since a query string is a
        legitimate place for one."""
        raw = "nifi:api:custom:metrics,/flow/metrics/json?includedRegistries=NIFI,JVM"
        self.assertEqual(self.parse(raw), [
            {"sourcetype": "nifi:api:custom:metrics", "path": "/flow/metrics/json?includedRegistries=NIFI,JVM"}
        ])

    def test_a_malformed_line_is_skipped_not_fatal(self):
        raw = "no-comma-here\nnifi:api:custom:a,/path/a"
        self.assertEqual(self.parse(raw), [{"sourcetype": "nifi:api:custom:a", "path": "/path/a"}])

    def test_an_invalid_line_is_skipped_not_fatal(self):
        raw = "bad type,relative/path\nnifi:api:custom:a,/path/a"
        self.assertEqual(self.parse(raw), [{"sourcetype": "nifi:api:custom:a", "path": "/path/a"}])

    def test_malformed_lines_log_a_warning(self):
        ew = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()) as event_writer:
            self.nifi.NiFiScript._parse_custom_endpoints("no-comma-here", ew)
            event_writer.log.assert_called_once()


class CustomEndpointValidationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def validate(self, **params):
        base = {"api_url": "http://nifi:8080/nifi-api/", "auth_type": "none"}
        base.update(params)
        definition = mock.MagicMock()
        definition.parameters = base
        return self.nifi.NiFiScript().validate_input(definition)

    def test_valid_custom_endpoints_are_accepted(self):
        self.validate(custom_endpoints="nifi:api:custom:a,/path/a\nnifi:api:custom:b,/path/b")

    def test_a_malformed_line_is_rejected_with_its_line_number(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(custom_endpoints="nifi:api:custom:a,/path/a\nno-comma-here")
        self.assertIn("line 2", str(caught.exception))

    def test_an_invalid_path_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(custom_endpoints="nifi:api:custom:a,not-relative")
        self.assertIn("must start with /", str(caught.exception))

    def test_an_invalid_sourcetype_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(custom_endpoints="bad sourcetype,/path")
        self.assertIn("letters, digits", str(caught.exception))

    def test_no_custom_endpoints_is_fine(self):
        self.validate()


class CollectCustomEndpointTest(NiFiScriptTestCase):

    def collect(self, sourcetype="nifi:api:custom:x", path="/some/path", status_code=200, body='{"a":1}'):
        self.http.get.side_effect = [response(status_code, body)]
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script._NiFiScript__collect_custom_endpoint(
                writer, "http://nifi:8080/nifi-api", {"sourcetype": sourcetype, "path": path},
                "none", "user", "instance", "sk", "nifi://instance", {"host": "nifi"},
            )
        return writer

    def test_the_response_is_written_under_the_declared_sourcetype(self):
        writer = self.collect(sourcetype="nifi:api:custom:queue_stats")
        event = writer.write_event.call_args.args[0]
        self.assertEqual(event.sourceType, "nifi:api:custom:queue_stats")

    def test_the_response_body_is_passed_through_unchanged(self):
        writer = self.collect(body='{"raw": "whatever nifi returned"}')
        event = writer.write_event.call_args.args[0]
        self.assertEqual(event.data, '{"raw": "whatever nifi returned"}')

    def test_the_requested_path_is_the_one_declared(self):
        self.collect(path="/flow/connections/1234/status")
        url = self.http.get.call_args.args[0]
        self.assertIn("/flow/connections/1234/status", url)

    def test_a_request_error_does_not_raise(self):
        """__get_request already swallows network errors internally; this
        covers __collect_custom_endpoint's own guard in case that changes, so
        one bad custom endpoint cannot abort the whole poll cycle."""
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            with mock.patch.object(self.script, "_NiFiScript__get_request", side_effect=Exception("boom")):
                self.script._NiFiScript__collect_custom_endpoint(
                    writer, "http://nifi:8080/nifi-api", {"sourcetype": "nifi:api:custom:x", "path": "/x"},
                    "none", "user", "instance", "sk", "nifi://instance", {"host": "nifi"},
                )
        writer.write_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()


class ErrorResponsesAreNotIndexedTest(NiFiScriptTestCase):
    """Defect CE-1, found by configuring thirteen endpoints and reading what
    arrived.

    __get_request used to return response.text whatever the status, so a
    failure was written out as though it were data. A custom endpoint pointed
    at a path that does not exist produced one event per poll carrying "The
    specified resource could not be found", under the sourcetype the user
    chose, with nothing marking it as a failure -- so an index with thirteen
    sourcetypes in it looked like thirteen working endpoints. The add-on
    logged the 404 and indexed it anyway, which is the worst of both.
    """

    def collect(self, status, body):
        self.http.get.return_value = response(status, body)
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script._NiFiScript__collect_custom_endpoint(
                writer, "http://nifi:8080/nifi-api",
                {"sourcetype": "nifi:api:custom:x", "path": "/does/not/exist"},
                "none", "user", "instance", "session-key", "nifi://instance",
                {"host": "nifi"},
            )
        return writer

    def test_a_404_writes_no_event(self):
        writer = self.collect(404, "The specified resource could not be found.")
        writer.write_event.assert_not_called()

    def test_a_500_writes_no_event(self):
        writer = self.collect(500, "WebClientServiceException: Request execution failed")
        writer.write_event.assert_not_called()

    def test_a_200_still_writes_the_body(self):
        writer = self.collect(200, '{"ok": true}')
        writer.write_event.assert_called_once()
        self.assertEqual(writer.write_event.call_args.args[0].data, '{"ok": true}')

    def test_a_built_in_endpoint_also_skips_an_error(self):
        """The same defect, wider than custom endpoints: an error body under
        nifi:api:flow_status is no better than under a user's sourcetype."""
        self.http.get.return_value = response(503, "Service Unavailable")
        result = self.script._NiFiScript__get_request(
            mock.MagicMock(), "http://nifi:8080/nifi-api", "/flow/status",
            "none", "user", "instance", "session-key")
        self.assertIsNone(result)


class PlaceholderPathsAreRejectedTest(NiFiScriptTestCase):
    """Defect CE-3. The validator accepted /processors/{id}/status and the
    add-on then requested it literally, which is a 404 every poll. The Status
    History fields a few rows up on the same screen do substitute an id, so
    assuming it carries over is reasonable -- which is what makes silence the
    wrong answer."""

    def test_a_placeholder_is_rejected(self):
        error = self.nifi.NiFiScript._validate_custom_endpoint(
            "nifi:api:custom:x", "/flow/processors/{id}/status/history")
        self.assertIsNotNone(error)
        self.assertIn("placeholder", error)

    def test_the_message_points_at_the_alternative(self):
        error = self.nifi.NiFiScript._validate_custom_endpoint(
            "nifi:api:custom:x", "/processors/{id}")
        self.assertIn("Status History", error)

    def test_a_real_id_is_accepted(self):
        self.assertIsNone(self.nifi.NiFiScript._validate_custom_endpoint(
            "nifi:api:custom:x",
            "/processors/cf866803-b1b8-392d-84c8-50c602e0a615"))


class EveryBadLineIsReportedTest(NiFiScriptTestCase):
    """Three mistakes in a list of thirteen used to mean three save attempts."""

    def validate(self, custom_endpoints):
        definition = mock.MagicMock()
        definition.parameters = {
            "api_url": "http://nifi:8080/nifi-api", "auth_type": "none",
            "interval": "60", "custom_endpoints": custom_endpoints,
        }
        return definition

    def test_all_three_problems_come_back_together(self):
        with self.assertRaises(ValueError) as caught:
            self.script.validate_input(self.validate(
                "ok:a,/flow/status\nno comma here\nok:b,http://absolute/x\nok:c,/p/{id}"))
        message = str(caught.exception)
        for line in ("line 2", "line 3", "line 4"):
            with self.subTest(line=line):
                self.assertIn(line, message)

    def test_a_clean_list_still_passes(self):
        self.script.validate_input(self.validate(
            "ok:a,/flow/status\n# a comment\n\nok:b,/controller/cluster"))
