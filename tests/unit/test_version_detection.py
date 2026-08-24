"""Tests for NiFi version detection in bin/nifi.py.

The TA has to serve both the 1.x and 2.x lines from one code path, which
means knowing which one it is talking to. /system-diagnostics carries
versionInfo.niFiVersion on every supported release, so detection uses that
rather than the metrics endpoint's VERSION_INFO registry, which answers 404
before NiFi 2.0.

The sample payloads under docs/plans/samples/ were captured from real
containers, so these tests run against what NiFi actually returns.
"""

import json
import os
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response

SAMPLES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs",
    "plans",
    "samples",
)


def sample(name):
    with open(os.path.join(SAMPLES, name)) as handle:
        return handle.read()


class ParseVersionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.parse = staticmethod(load_nifi_module()[0].NiFiScript.parse_version)

    def test_reads_a_three_part_version(self):
        self.assertEqual(self.parse("2.11.0"), (2, 11, 0))
        self.assertEqual(self.parse("1.23.2"), (1, 23, 2))

    def test_a_missing_patch_becomes_zero(self):
        self.assertEqual(self.parse("1.28"), (1, 28, 0))

    def test_ignores_a_qualifier(self):
        """2.0.0-M4 and the like must still compare as 2.0.0."""
        self.assertEqual(self.parse("2.0.0-M4"), (2, 0, 0))
        self.assertEqual(self.parse("1.28.1-RC1"), (1, 28, 1))

    def test_unreadable_input_yields_none(self):
        for value in ("", "   ", "bogus", None):
            with self.subTest(value=value):
                self.assertIsNone(self.parse(value))

    def test_versions_order_as_expected(self):
        self.assertLess(self.parse("1.28.1"), self.parse("2.0.0"))
        self.assertLess(self.parse("1.9.0"), self.parse("1.16.0"))
        self.assertGreater(self.parse("2.11.0"), self.parse("2.2.0"))


class VersionInfoExtractionTest(unittest.TestCase):
    """Against the payloads captured from real NiFi containers."""

    @classmethod
    def setUpClass(cls):
        cls.extract = staticmethod(load_nifi_module()[0].NiFiScript.version_info_of)

    def test_reads_the_1_x_payload(self):
        info = self.extract(sample("nifi1.23-system-diagnostics.json"))
        self.assertEqual(info["niFiVersion"], "1.23.2")
        self.assertEqual(info["javaVersion"], "11.0.20")

    def test_reads_the_2_x_payload(self):
        info = self.extract(sample("nifi2.11-system-diagnostics.json"))
        self.assertEqual(info["niFiVersion"], "2.11.0")
        self.assertEqual(info["javaVersion"], "21.0.12")

    def test_unusable_payloads_yield_none(self):
        for payload in (None, "", "not json", "{}", '{"systemDiagnostics": {}}'):
            with self.subTest(payload=payload):
                self.assertIsNone(self.extract(payload))


class EndpointGatingTest(NiFiScriptTestCase):
    """Endpoints can declare a min_version; the rest are collected always."""

    def supported(self, endpoint, detected):
        self.script.nifi_version = detected
        return self.script._NiFiScript__supported(endpoint, mock.MagicMock())

    def test_an_endpoint_without_a_minimum_is_always_collected(self):
        endpoint = {"name": "endpoint_flow_status"}
        self.assertTrue(self.supported(endpoint, (1, 16, 0)))
        self.assertTrue(self.supported(endpoint, None))

    def test_an_endpoint_is_collected_at_and_above_its_minimum(self):
        endpoint = {"name": "endpoint_flow_metrics", "min_version": (1, 16, 0)}
        self.assertTrue(self.supported(endpoint, (1, 16, 0)))
        self.assertTrue(self.supported(endpoint, (2, 11, 0)))

    def test_an_endpoint_is_skipped_below_its_minimum(self):
        endpoint = {"name": "endpoint_flow_metrics", "min_version": (1, 16, 0)}
        self.assertFalse(self.supported(endpoint, (1, 15, 3)))

    def test_a_version_dependent_endpoint_is_skipped_when_version_is_unknown(self):
        """Guessing would mean logging a 404 as an error on every cycle."""
        endpoint = {"name": "endpoint_flow_metrics", "min_version": (1, 16, 0)}
        self.assertFalse(self.supported(endpoint, None))


class VersionEventTest(NiFiScriptTestCase):
    """stream_events emits the detected version as its own sourcetype."""

    def run_stream(self, diagnostics_payload):
        inputs = mock.MagicMock()
        inputs.inputs.popitem.return_value = (
            "nifi://instance",
            {"api_url": "http://nifi:8080/nifi-api", "auth_type": "none",
             "host": "nifi", "endpoint_flow_status": "0",
             "endpoint_system_diagnostics": "0", "endpoint_site_to_site": "0"},
        )
        self.script._input_definition = mock.MagicMock()
        self.script._input_definition.metadata = {"session_key": "sk"}
        self.http.get.side_effect = [response(200, diagnostics_payload)]
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script.stream_events(inputs, writer)
        return writer

    def test_the_detected_version_is_written_as_an_event(self):
        writer = self.run_stream(sample("nifi2.11-system-diagnostics.json"))

        writer.write_event.assert_called_once()
        event = writer.write_event.call_args.args[0]
        self.assertEqual(event.sourceType, "nifi:api:version_info")
        self.assertEqual(json.loads(event.data)["niFiVersion"], "2.11.0")

    def test_the_parsed_version_is_cached_on_the_script(self):
        self.run_stream(sample("nifi1.23-system-diagnostics.json"))
        self.assertEqual(self.script.nifi_version, (1, 23, 2))

    def test_an_undetectable_version_writes_no_event(self):
        writer = self.run_stream("not json")
        writer.write_event.assert_not_called()
        self.assertIsNone(self.script.nifi_version)


class DiagnosticsReuseTest(NiFiScriptTestCase):
    """The version probe and the system_diagnostics endpoint must not both
    fetch /system-diagnostics."""

    def test_diagnostics_is_fetched_once_when_the_endpoint_is_enabled(self):
        inputs = mock.MagicMock()
        inputs.inputs.popitem.return_value = (
            "nifi://instance",
            {"api_url": "http://nifi:8080/nifi-api", "auth_type": "none",
             "host": "nifi", "endpoint_flow_status": "0",
             "endpoint_system_diagnostics": "1", "endpoint_site_to_site": "0"},
        )
        self.script._input_definition = mock.MagicMock()
        self.script._input_definition.metadata = {"session_key": "sk"}
        payload = sample("nifi2.11-system-diagnostics.json")
        self.http.get.side_effect = [response(200, payload)]
        writer = mock.MagicMock()

        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script.stream_events(inputs, writer)

        requested = [call.args[0] for call in self.http.get.call_args_list]
        self.assertEqual(len(requested), 1, "fetched %s" % requested)

        sourcetypes = [
            call.args[0].sourceType for call in writer.write_event.call_args_list
        ]
        self.assertIn("nifi:api:version_info", sourcetypes)
        self.assertIn("nifi:api:system_diagnostics", sourcetypes)


if __name__ == "__main__":
    unittest.main()
