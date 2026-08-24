"""Tests for flow metrics collection in bin/nifi.py (TA-2).

/flow/metrics/json returns Prometheus' data model serialised to JSON:
labelNames and labelValues are parallel arrays. INDEXED_EXTRACTIONS would
index those as two unrelated multivalue fields, so the TA zips them into one
flat event per sample. This is the piece the plan originally got wrong by
reading the documentation instead of the payload.

The assertions run against the samples captured from real 1.23.2 and 2.11.0
containers, so the shape being tested is the shape NiFi actually returns.
"""

import json
import os
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response

SAMPLES = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "docs", "plans", "samples",
)


def sample(name):
    with open(os.path.join(SAMPLES, name)) as handle:
        return handle.read()


class FlattenTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.flatten = staticmethod(load_nifi_module()[0].NiFiScript.flatten_samples)

    def test_labels_are_zipped_into_fields(self):
        payload = json.dumps({"samples": [{
            "name": "nifi_amount_items_queued",
            "labelNames": ["instance", "component_type"],
            "labelValues": ["abc", "RootProcessGroup"],
            "value": 7.0,
        }]})
        self.assertEqual(self.flatten(payload), [{
            "metric_name": "nifi_amount_items_queued",
            "metric_value": 7.0,
            "instance": "abc",
            "component_type": "RootProcessGroup",
        }])

    def test_empty_label_values_are_dropped(self):
        """parent_id is empty on most samples; an empty string reads no
        differently from an absent field in Splunk and costs bytes."""
        payload = json.dumps({"samples": [{
            "name": "m", "labelNames": ["instance", "parent_id"],
            "labelValues": ["abc", ""], "value": 0.0,
        }]})
        self.assertNotIn("parent_id", self.flatten(payload)[0])

    def test_a_zero_value_is_kept(self):
        """Most NiFi metrics are 0 on an idle instance; dropping them would
        drop almost everything."""
        payload = json.dumps({"samples": [{
            "name": "m", "labelNames": ["instance"], "labelValues": ["abc"],
            "value": 0.0,
        }]})
        self.assertEqual(self.flatten(payload)[0]["metric_value"], 0.0)

    def test_mismatched_label_arrays_do_not_raise(self):
        """zip() stops at the shorter array rather than inventing fields."""
        payload = json.dumps({"samples": [{
            "name": "m", "labelNames": ["a", "b", "c"], "labelValues": ["1"],
            "value": 1.0,
        }]})
        self.assertEqual(self.flatten(payload), [{"metric_name": "m", "metric_value": 1.0, "a": "1"}])

    def test_no_samples_is_an_empty_list_not_a_failure(self):
        self.assertEqual(self.flatten(json.dumps({"samples": []})), [])
        self.assertEqual(self.flatten(json.dumps({"samples": None})), [])

    def test_an_unreadable_response_is_distinguishable(self):
        for payload in (None, "", "not json", "{}"):
            with self.subTest(payload=payload):
                self.assertIsNone(self.flatten(payload))


class CapturedSamplesTest(unittest.TestCase):
    """Against what real NiFi containers returned."""

    @classmethod
    def setUpClass(cls):
        cls.flatten = staticmethod(load_nifi_module()[0].NiFiScript.flatten_samples)

    def test_the_2_x_payload_flattens_completely(self):
        flat = self.flatten(sample("nifi2.11-metrics-all.json"))
        raw = json.loads(sample("nifi2.11-metrics-all.json"))["samples"]
        self.assertEqual(len(flat), len(raw))
        self.assertTrue(all(item["metric_name"] for item in flat))

    def test_the_1_x_payload_flattens_completely(self):
        flat = self.flatten(sample("nifi1.23-metrics-all.json"))
        raw = json.loads(sample("nifi1.23-metrics-all.json"))["samples"]
        self.assertEqual(len(flat), len(raw))

    def test_no_flattened_field_collides_with_the_metric_keys(self):
        """A label called metric_name would silently overwrite the metric."""
        for name in ("nifi2.11-metrics-all.json", "nifi1.23-metrics-all.json"):
            raw = json.loads(sample(name))["samples"]
            labels = {label for item in raw for label in (item.get("labelNames") or [])}
            with self.subTest(sample=name):
                self.assertNotIn("metric_name", labels)
                self.assertNotIn("metric_value", labels)

    def test_the_2_x_payload_carries_the_repo_metrics_1_x_lacks(self):
        """These are what make the metrics endpoint able to stand in for
        /system-diagnostics on 2.x but not on 1.x."""
        names_2x = {item["metric_name"] for item in self.flatten(sample("nifi2.11-metrics-all.json"))}
        names_1x = {item["metric_name"] for item in self.flatten(sample("nifi1.23-metrics-all.json"))}
        for metric in ("nifi_content_repo_free_space_bytes",
                       "nifi_provenance_repo_used_space_bytes"):
            with self.subTest(metric=metric):
                self.assertIn(metric, names_2x)
                self.assertNotIn(metric, names_1x)

    def test_1_x_metrics_are_a_subset_of_2_x(self):
        """One parser serves both lines because nothing was removed."""
        names_2x = {item["metric_name"] for item in self.flatten(sample("nifi2.11-metrics-all.json"))}
        names_1x = {item["metric_name"] for item in self.flatten(sample("nifi1.23-metrics-all.json"))}
        self.assertEqual(names_1x - names_2x, set())


class QueryBuildingTest(NiFiScriptTestCase):

    def query(self, version=(2, 11, 0), **item):
        self.script.nifi_version = version
        return self.script.metrics_query(item)

    def test_the_default_strategy_bounds_the_volume(self):
        """ALL_COMPONENTS is NiFi's default and reports per component; this
        endpoint is large enough already."""
        self.assertIn("flowMetricsReportingStrategy=ALL_PROCESS_GROUPS", self.query())

    def test_an_explicit_strategy_is_honoured(self):
        self.assertIn(
            "flowMetricsReportingStrategy=ALL_COMPONENTS",
            self.query(metrics_strategy="all_components"),
        )

    def test_an_unknown_strategy_falls_back_to_the_default(self):
        self.assertIn(
            "flowMetricsReportingStrategy=ALL_PROCESS_GROUPS",
            self.query(metrics_strategy="nonsense"),
        )

    def test_registries_are_passed_as_repeated_parameters(self):
        query = self.query(metrics_registries="JVM, BULLETIN")
        self.assertIn("includedRegistries=JVM", query)
        self.assertIn("includedRegistries=BULLETIN", query)

    def test_version_info_is_dropped_on_nifi_1(self):
        """Requesting it there returns 404, which would be logged as an error
        on every cycle."""
        query = self.query(version=(1, 23, 2), metrics_registries="JVM,VERSION_INFO")
        self.assertIn("includedRegistries=JVM", query)
        self.assertNotIn("VERSION_INFO", query)

    def test_version_info_is_kept_on_nifi_2(self):
        self.assertIn(
            "includedRegistries=VERSION_INFO",
            self.query(version=(2, 0, 0), metrics_registries="VERSION_INFO"),
        )

    def test_an_unknown_registry_is_ignored(self):
        self.assertNotIn("NONSENSE", self.query(metrics_registries="NONSENSE"))

    def test_the_sample_filter_is_url_encoded(self):
        """A regex carries characters that would otherwise break the query."""
        query = self.query(metrics_sample_filter="nifi_jvm.*|nifi_amount.*")
        self.assertNotIn("|", query)
        self.assertIn("sampleName=", query)


class MetricsCollectionTest(NiFiScriptTestCase):

    def collect(self, payload, **item):
        self.script.nifi_version = (2, 11, 0)
        self.http.get.side_effect = [response(200, payload)]
        writer = mock.MagicMock()
        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()):
            self.script._NiFiScript__collect_flow_metrics(
                writer, "http://nifi:8080/nifi-api", "/flow/metrics/json",
                "nifi:api:flow_metrics", "none", "user", "instance", "sk",
                "nifi://instance", dict(item, host="nifi"),
            )
        return writer

    def test_one_event_per_sample(self):
        writer = self.collect(sample("nifi2.11-metrics-all.json"))
        expected = len(json.loads(sample("nifi2.11-metrics-all.json"))["samples"])
        self.assertEqual(writer.write_event.call_count, expected)

    def test_events_carry_the_declared_sourcetype(self):
        writer = self.collect(sample("nifi2.11-metrics-all.json"))
        self.assertEqual(
            writer.write_event.call_args.args[0].sourceType, "nifi:api:flow_metrics"
        )

    def test_each_event_is_a_flat_json_object(self):
        writer = self.collect(sample("nifi2.11-metrics-all.json"))
        first = json.loads(writer.write_event.call_args_list[0].args[0].data)
        self.assertIn("metric_name", first)
        self.assertIn("metric_value", first)
        self.assertFalse(
            [key for key, value in first.items() if isinstance(value, (dict, list))],
            "an event still holds nested structure",
        )

    def test_an_unreadable_response_writes_no_events(self):
        writer = self.collect("not json")
        writer.write_event.assert_not_called()


class MetricsValidationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def validate(self, **params):
        base = {"api_url": "http://nifi:8080/nifi-api/", "auth_type": "none"}
        base.update(params)
        definition = mock.MagicMock()
        definition.parameters = base
        return self.nifi.NiFiScript().validate_input(definition)

    def test_a_bad_strategy_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(metrics_strategy="EVERYTHING")
        self.assertIn("strategy must be", str(caught.exception))

    def test_an_unknown_registry_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(metrics_registries="JVM,NONSENSE")
        self.assertIn("Unknown metric registry", str(caught.exception))

    def test_an_invalid_regex_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(metrics_sample_filter="nifi_[")
        self.assertIn("not a valid regular expression", str(caught.exception))

    def test_valid_settings_are_accepted(self):
        self.validate(
            endpoint_flow_metrics="1",
            metrics_registries="NIFI, JVM, VERSION_INFO",
            metrics_strategy="ALL_COMPONENTS",
            metrics_sample_filter="nifi_jvm.*",
        )


class MetricsDefaultTest(NiFiScriptTestCase):

    def test_the_endpoint_is_off_unless_enabled(self):
        """An idle NiFi already emits ~14 KB per poll and ALL_COMPONENTS
        scales with the flow, so this has to be a deliberate choice."""
        self.assertFalse(self.script._is_enabled(None, default=False))
        self.assertFalse(self.script._is_enabled("", default=False))
        self.assertTrue(self.script._is_enabled("1", default=False))


if __name__ == "__main__":
    unittest.main()
