"""The add-on is generated now, so these check the generator and its output.

Before the UCC migration the setup page, the spec and the code were three
handwritten places that had to agree, and they did not: four flow-metrics
fields -- endpoint_flow_metrics, metrics_registries, metrics_strategy and
metrics_sample_filter -- were implemented and documented in the spec but
never put on the screen, so the only way to switch flow metrics on was to
edit inputs.conf by hand (finding UI-4). globalConfig.json is now the single
source for all three, which removes that class of drift by construction --
but only as long as nothing is added to the code without being declared, and
only as long as what is tested is what the build produces (condition UI-3).
"""

import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ta_paths import REPO, TA_BUILT, TA_SOURCE, require_built  # noqa: E402

GLOBAL_CONFIG = os.path.join(REPO, "nifi_TA_monitoring", "globalConfig.json")
GENERATOR = os.path.join(REPO, "nifi_TA_monitoring", "gen_globalconfig.py")

# Read by the input but not configurable, on purpose.
NOT_FIELDS = {
    # Retired in 2.0.0. The code still looks for it to tell an operator their
    # leftover setting is ignored, which is the opposite of declaring it.
    "endpoint_site_to_site",
}
# Declared but never read by the input, on purpose.
NOT_READ = {
    "name",       # the stanza name
    "index",      # Splunk routes on it; the script never sees it
    "test_connection",  # a button, not a setting
    "endpoint_flow_status",  # read through the endpoints table, not by name
}


def global_config():
    with open(GLOBAL_CONFIG) as handle:
        return json.load(handle)


def entity():
    return global_config()["pages"]["inputs"]["services"][0]["entity"]


class GlobalConfigIsGeneratedTest(unittest.TestCase):
    """globalConfig.json is written by nifi_TA_monitoring/gen_globalconfig.py.

    It is generated rather than hand-edited because the same field list has
    to stay consistent across the form, the table and the group layout, and
    because twenty repeated validator blocks are easier to get wrong than to
    produce. Hand-editing the JSON works right up until the next run of the
    generator silently reverts it.
    """

    def test_the_committed_json_matches_a_clean_run(self):
        with open(GLOBAL_CONFIG) as handle:
            committed = handle.read()
        result = subprocess.run(
            [sys.executable, "-c",
             "import runpy, sys, json; "
             "sys.argv=['gen']; "
             "m = runpy.run_path(%r); "
             "print(json.dumps(m['build'](), indent=4))" % GENERATOR],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertEqual(
            json.loads(committed), json.loads(result.stdout),
            "globalConfig.json differs from what nifi_TA_monitoring/gen_globalconfig.py "
            "produces: edit the generator and re-run it, not the JSON")

    def test_every_field_is_in_exactly_one_group(self):
        groups = global_config()["pages"]["inputs"]["services"][0]["groups"]
        grouped = [field for group in groups for field in group["fields"]]
        self.assertEqual(
            sorted(grouped), sorted(set(grouped)), "a field is in two groups")
        self.assertEqual(
            sorted(grouped), sorted(item["field"] for item in entity()),
            "an entity field is in no group, so it renders outside every "
            "section")


class EveryReadFieldIsConfigurableTest(unittest.TestCase):
    """UI-4, turned into an assertion.

    A field the input reads but nobody declared can only be set by editing
    inputs.conf by hand, and nothing says so -- the feature looks absent. A
    field declared but never read is the other half: it takes a value on
    screen and does nothing with it.
    """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(TA_SOURCE, "bin", "nifi.py")) as handle:
            source = handle.read()
        cls.read = set(re.findall(
            r'(?:input_item|params)\.get\(["\']([a-z_]+)', source))
        # The endpoints table names its own fields.
        cls.read |= set(re.findall(r'"name"\s*:\s*"(endpoint_[a-z_]+)"', source))
        cls.declared = {item["field"] for item in entity()}

    def test_nothing_the_input_reads_is_missing_from_the_form(self):
        missing = sorted(self.read - self.declared - NOT_FIELDS)
        self.assertEqual(
            missing, [],
            "these are read by bin/nifi.py and cannot be set from the UI: %s"
            % missing)

    def test_nothing_on_the_form_is_ignored_by_the_input(self):
        unused = sorted(self.declared - self.read - NOT_READ)
        self.assertEqual(
            unused, [],
            "these are on the form and never read: %s" % unused)


class VersionAgreementTest(unittest.TestCase):
    """One source, three derivations, and a test because nothing enforces it.

    `make bump` writes nifi_monitoring/default/app.conf and stops; the TA's
    globalConfig.json and app.manifest are regenerated from it by
    gen_globalconfig.py. A bump without that regeneration leaves the add-on
    on the old version, and ucc-gen would happily build it. This is what says
    so -- and it is meant to fail between `make bump` and `make version-sync`,
    which is the point.
    """

    def versions(self):
        import configparser
        manifest = json.load(open(os.path.join(
            REPO, "nifi_TA_monitoring", "package", "app.manifest")))
        app_conf = configparser.ConfigParser(strict=False, interpolation=None)
        app_conf.read(os.path.join(REPO, "nifi_monitoring", "default", "app.conf"))
        return {
            "globalConfig.json": global_config()["meta"]["version"],
            "package/app.manifest": manifest["info"]["id"]["version"],
            "nifi_monitoring [launcher]": app_conf["launcher"]["version"],
            "nifi_monitoring [id]": app_conf["id"]["version"],
        }

    def test_they_all_agree(self):
        versions = self.versions()
        self.assertEqual(
            len(set(versions.values())), 1,
            "versions differ: %s" % versions)

    def test_the_version_is_semver(self):
        for where, version in self.versions().items():
            with self.subTest(where=where):
                self.assertRegex(version or "", r"^\d+\.\d+\.\d+$")


class BuiltAddonTest(unittest.TestCase):

    def setUp(self):
        reason = require_built()
        if reason:
            self.skipTest(reason)

    def test_the_spec_covers_every_declared_field(self):
        with open(os.path.join(TA_BUILT, "README", "inputs.conf.spec")) as handle:
            spec = handle.read()
        for item in entity():
            if item["field"] == "name":
                continue
            with self.subTest(field=item["field"]):
                self.assertRegex(spec, r"(?m)^%s\s*=" % re.escape(item["field"]))

    def test_the_defaults_survived_the_monitors_being_appended(self):
        """additional_packaging.py rewrites the generated inputs.conf. If it
        ever appends instead of merging, the [nifi] defaults disappear and an
        input that omits verify_tls stops verifying -- silently."""
        with open(os.path.join(TA_BUILT, "default", "inputs.conf")) as handle:
            built = handle.read()
        stanza = built.split("[monitor://", 1)[0]
        for expected in ("[nifi]", "python.required = 3.13",
                         "verify_tls = 1", "interval = 60", "auth_type = none"):
            with self.subTest(expected=expected):
                self.assertIn(expected, stanza)
        self.assertIn("[monitor:///opt/nifi/nifi-current/logs/", built)

    def test_no_compiled_extension_is_shipped(self):
        """Defect B-15. A .so is built for one CPU architecture and one Python
        minor version, so shipping one means the add-on works on the machine
        it was built on and nowhere else. This is why solnlib is pinned below
        8 and why requests is in exclude.txt rather than requirements.txt."""
        binaries = []
        for root, _, files in os.walk(os.path.join(TA_BUILT, "lib")):
            binaries += [os.path.join(root, name) for name in files
                         if name.endswith((".so", ".pyd", ".dylib"))]
        relative = sorted(os.path.relpath(path, TA_BUILT) for path in binaries)
        self.assertEqual(relative, [], "compiled extensions in lib/: %s" % relative)

    def test_the_excluded_packages_really_are_absent(self):
        """Splunk ships these; a second copy in lib/ takes precedence over
        Splunk's and pins the add-on to whatever was current at build time."""
        present = os.listdir(os.path.join(TA_BUILT, "lib"))
        for package in ("requests", "urllib3", "certifi", "charset_normalizer"):
            with self.subTest(package=package):
                self.assertNotIn(package, present)

    def test_the_input_script_is_byte_identical_to_the_source(self):
        """ucc-gen copies bin/ verbatim. The unit suite imports the source
        copy, so a build step that transformed it would mean the tests and
        the add-on run different code."""
        with open(os.path.join(TA_SOURCE, "bin", "nifi.py"), "rb") as handle:
            source = handle.read()
        with open(os.path.join(TA_BUILT, "bin", "nifi.py"), "rb") as handle:
            built = handle.read()
        self.assertEqual(source, built)


if __name__ == "__main__":
    unittest.main()
