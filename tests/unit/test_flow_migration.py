"""Tests for flow_definition/migrate_to_nifi2.py.

The 2.x flow is generated, so what needs guarding is the generator. Each
assertion here corresponds to something that made a processor invalid when
the flow was imported into a real NiFi 2.11.0.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FLOW_DIR = os.path.join(REPO, "flow_definition")
SOURCE = os.path.join(FLOW_DIR, "nifi-1.x", "NiFiMonitoring.json")
SHIPPED = os.path.join(FLOW_DIR, "nifi-2.x", "NiFiMonitoring.json")


def walk(group):
    yield group
    for child in group.get("processGroups") or []:
        yield from walk(child.get("flowContents", child))


def processors(flow):
    for group in walk(flow["flowContents"]):
        for processor in group.get("processors") or []:
            yield processor


def properties(processor):
    return (processor.get("properties")
            or processor.get("config", {}).get("properties", {}) or {})


class GeneratedFlowTest(unittest.TestCase):
    """Against the 2.x flow as shipped."""

    @classmethod
    def setUpClass(cls):
        with open(SHIPPED) as handle:
            cls.flow = json.load(handle)
        cls.processors = list(processors(cls.flow))

    def test_no_gethttp_survives(self):
        types = {p["type"] for p in self.processors}
        self.assertNotIn("org.apache.nifi.processors.standard.GetHTTP", types)

    def test_jolt_uses_the_relocated_type_and_bundle(self):
        jolt = [p for p in self.processors if p["type"].endswith("JoltTransformJSON")]
        self.assertTrue(jolt, "the flow has no Jolt processor any more")
        for processor in jolt:
            with self.subTest(name=processor.get("name")):
                self.assertEqual(processor["type"],
                                 "org.apache.nifi.processors.jolt.JoltTransformJSON")
                self.assertEqual(processor["bundle"]["artifact"], "nifi-jolt-nar")

    def test_jolt_properties_use_the_new_names(self):
        for processor in self.processors:
            if not processor["type"].endswith("JoltTransformJSON"):
                continue
            props = properties(processor)
            with self.subTest(name=processor.get("name")):
                self.assertNotIn("jolt-spec", props)
                self.assertNotIn("jolt-transform", props)
                self.assertIn("Jolt Specification", props)

    def test_no_variables_remain(self):
        for group in walk(self.flow["flowContents"]):
            with self.subTest(group=group.get("name")):
                self.assertNotIn("variables", group)

    def test_a_parameter_context_replaces_them(self):
        contexts = self.flow.get("parameterContexts") or {}
        self.assertTrue(contexts, "no parameter context was created")
        names = {p["name"] for c in contexts.values() for p in c["parameters"]}
        self.assertIn("splunk_hec", names)
        self.assertIn("nifi_api_url", names)

    def test_every_group_names_the_context(self):
        """A child group does not inherit its parent's parameter context;
        setting it only on the root left every subgroup invalid."""
        contexts = list((self.flow.get("parameterContexts") or {}))
        for group in walk(self.flow["flowContents"]):
            with self.subTest(group=group.get("name")):
                self.assertIn(group.get("parameterContextName"), contexts)

    def test_no_dollar_references_to_migrated_variables_remain(self):
        names = {p["name"] for c in (self.flow.get("parameterContexts") or {}).values()
                 for p in c["parameters"]}
        blob = json.dumps(self.flow)
        for name in names:
            with self.subTest(parameter=name):
                self.assertNotIn("${%s}" % name, blob)
                self.assertIn("#{%s}" % name, blob)

    def test_the_token_parameter_is_sensitive_and_carries_no_value(self):
        """Marking it sensitive is what keeps NiFi from writing it into an
        exported flow -- which is how the original token leaked."""
        for context in (self.flow.get("parameterContexts") or {}).values():
            for parameter in context["parameters"]:
                if parameter["name"] == "splunk_hec_token":
                    self.assertTrue(parameter["sensitive"])
                    self.assertNotIn("value", parameter)
                    return
        self.fail("splunk_hec_token is not in the parameter context")

    def test_the_authorization_header_is_declared_sensitive(self):
        """A non-sensitive property cannot reference a sensitive parameter."""
        for processor in self.processors:
            props = properties(processor)
            if "#{splunk_hec_token}" in str(props.get("Authorization", "")):
                descriptors = processor.get("propertyDescriptors") or {}
                self.assertTrue(descriptors.get("Authorization", {}).get("sensitive"))
                return
        self.fail("no processor references the token in an Authorization header")

    def test_converted_processors_use_the_accepted_boolean_casing(self):
        """2.x rejects lowercase as outside the allowed set -- but only for the
        properties this script writes. The InvokeHTTP processors that were
        already in the 1.x flow keep their old-style values, and NiFi migrates
        those itself on import; the 39-of-39 result confirms it accepts them."""
        converted = [p for p in self.processors
                     if p["type"].endswith("InvokeHTTP")
                     and p.get("name", "").startswith("GetHTTP-")]
        self.assertTrue(converted, "no converted GetHTTP processors found")
        for processor in converted:
            for key, value in properties(processor).items():
                if isinstance(value, str) and value.lower() in ("true", "false"):
                    with self.subTest(processor=processor.get("name"), prop=key):
                        self.assertIn(value, ("True", "False"))

    def test_connections_out_of_converted_processors_use_Response(self):
        converted = {
            p.get("identifier") for p in self.processors
            if p["type"].endswith("InvokeHTTP") and p.get("name", "").startswith("GetHTTP-")
        }
        self.assertTrue(converted, "no converted GetHTTP processors found")
        for group in walk(self.flow["flowContents"]):
            for connection in group.get("connections") or []:
                if (connection.get("source") or {}).get("id") in converted:
                    with self.subTest(connection=connection.get("identifier")):
                        self.assertNotIn("success", connection.get("selectedRelationships") or [])

    def test_the_retired_sourcetype_is_gone(self):
        """site_to_site was retired from the TA (D-2), so the flow must not
        keep delivering it: props.conf no longer defines that sourcetype, and
        the events would arrive with nothing extracted."""
        blob = json.dumps(self.flow)
        self.assertNotIn("site_to_site", blob)
        self.assertNotIn("site-to-site", blob)

    def test_no_processor_is_left_without_its_branch(self):
        """Dropping a source leaves its labelling processor orphaned, feeding
        the funnel with nothing upstream."""
        names = [p.get("name") for p in self.processors]
        self.assertNotIn("GetHTTP-site_to_site", names)

    def test_no_environment_data_is_shipped(self):
        """The 1.x flow leaked a HEC token and a host this way."""
        blob = json.dumps(self.flow)
        self.assertNotIn("20.81.194.76", blob)
        self.assertNotIn("c91b35d5", blob)


class RegenerationTest(unittest.TestCase):
    """Running the script on the 1.x flow must reproduce what is committed,
    so the shipped file cannot drift from the generator."""

    def test_the_shipped_flow_matches_a_fresh_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "regenerated.json")
            subprocess.run(
                [sys.executable, os.path.join(FLOW_DIR, "migrate_to_nifi2.py"), SOURCE, out],
                check=True, capture_output=True, cwd=FLOW_DIR,
            )
            with open(out) as handle:
                regenerated = json.load(handle)
        with open(SHIPPED) as handle:
            shipped = json.load(handle)
        self.assertEqual(regenerated, shipped,
                         "nifi-2.x/NiFiMonitoring.json is out of date; re-run the script")


class OperatorGuidanceTest(unittest.TestCase):
    """The flow is something a person edits after importing, so every setting
    has to say what it is and what a working value looks like."""

    @classmethod
    def setUpClass(cls):
        with open(SHIPPED) as handle:
            cls.flow = json.load(handle)
        cls.parameters = {
            p["name"]: p
            for c in cls.flow["parameterContexts"].values()
            for p in c["parameters"]
        }

    def test_every_parameter_has_a_description(self):
        """NiFi shows it in the UI; an empty one leaves an unlabelled box."""
        for name, parameter in self.parameters.items():
            with self.subTest(parameter=name):
                self.assertTrue(parameter.get("description", "").strip(),
                                "%s has no description" % name)

    def test_the_two_required_ones_say_so(self):
        for name in ("processors_list", "process_groups_list"):
            with self.subTest(parameter=name):
                self.assertIn("REQUIRED", self.parameters[name]["description"])
                self.assertEqual(self.parameters[name].get("value", ""), "")

    def test_the_defaults_point_at_the_local_test_stack(self):
        """A working example beats a placeholder to decode: these are the
        hostnames tests/docker-compose.yml uses."""
        self.assertEqual(self.parameters["splunk_hec"]["value"], "http://splunk:8088")

    def test_the_hec_endpoint_matches_the_harness(self):
        compose = open(os.path.join(REPO, "tests", "docker-compose.yml")).read()
        host = self.parameters["splunk_hec"]["value"].split("//")[1].split(":")[0]
        self.assertRegex(compose, r"hostname:\s*%s\b" % host)


if __name__ == "__main__":
    unittest.main()
