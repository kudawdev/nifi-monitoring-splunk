"""Tests for tests/matrix.py.

matrix.py has two YAML readers: PyYAML when installed, and a minimal
fallback for the subset matrix.yml uses, because the CI container's
dependencies are not guaranteed. If those two disagree, run.sh silently
brings up a different environment than the one the profile names, so the
parity test matters more than either parser on its own.
"""

import os
import sys
import unittest

TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import matrix  # noqa: E402

REQUIRED_PROFILE_KEYS = {"nifi_version", "splunk_version", "nifi_auth"}


class MatrixFileTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = matrix.load()

    def test_every_profile_declares_the_required_keys(self):
        for name, profile in self.data["profiles"].items():
            with self.subTest(profile=name):
                self.assertTrue(REQUIRED_PROFILE_KEYS.issubset(profile))

    def test_auth_modes_have_a_matching_env_file(self):
        for name, profile in self.data["profiles"].items():
            with self.subTest(profile=name):
                env_file = os.path.join(
                    TESTS_DIR, "env", "nifi-%s.env" % profile["nifi_auth"]
                )
                self.assertTrue(
                    os.path.isfile(env_file), "missing %s" % env_file
                )

    def test_ci_lists_reference_known_profiles(self):
        known = set(self.data["profiles"])
        for stage, names in self.data["ci"].items():
            for name in names:
                with self.subTest(stage=stage, profile=name):
                    self.assertIn(name, known)

    def test_both_nifi_majors_are_covered_on_pull_request(self):
        """A PR must exercise 1.x and 2.x, or a regression on one goes unseen."""
        majors = {
            self.data["profiles"][name]["nifi_version"].split(".")[0]
            for name in self.data["ci"]["pull_request"]
        }
        self.assertEqual(majors, {"1", "2"})


class ParserParityTest(unittest.TestCase):
    """The fallback parser must agree with PyYAML on the real matrix.yml."""

    def test_fallback_matches_pyyaml(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed; nothing to compare against")

        text = open(matrix.MATRIX).read()
        self.assertEqual(matrix._parse_minimal_yaml(text), yaml.safe_load(text))


class EnvGenerationTest(unittest.TestCase):

    def parse_env(self, profile):
        return dict(
            line.split("=", 1)
            for line in matrix.env_for(profile).splitlines()
            if line and not line.startswith("#")
        )

    def test_env_carries_the_profile_versions(self):
        env = self.parse_env("nifi2-current")
        self.assertEqual(env["NIFI_VERSION"], "2.11.0")
        self.assertEqual(env["PROFILE"], "nifi2-current")

    def test_env_points_at_the_auth_profile_file(self):
        self.assertEqual(
            self.parse_env("nifi1-legacy")["NIFI_ENV_FILE"], "./env/nifi-none.env"
        )
        self.assertEqual(
            self.parse_env("nifi2-current")["NIFI_ENV_FILE"],
            "./env/nifi-singleuser.env",
        )

    def test_unknown_profile_is_rejected(self):
        with self.assertRaises(SystemExit):
            matrix.env_for("does-not-exist")


class SingleUserCredentialsTest(unittest.TestCase):
    """NiFi ignores a single-user password shorter than 12 characters and
    generates random credentials instead. The old harness shipped an
    8-character one, so its authenticated profile never worked."""

    def test_single_user_password_is_long_enough(self):
        env_file = os.path.join(TESTS_DIR, "env", "nifi-singleuser.env")
        values = dict(
            line.split("=", 1)
            for line in open(env_file).read().splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        self.assertGreaterEqual(len(values["SINGLE_USER_CREDENTIALS_PASSWORD"]), 12)

    def test_proxy_host_has_no_unreplaced_placeholder(self):
        """'<URL_BASE>:9443' made NiFi answer 421 to every request."""
        env_file = os.path.join(TESTS_DIR, "env", "nifi-singleuser.env")
        content = open(env_file).read()
        self.assertIn("NIFI_WEB_PROXY_HOST=", content)
        self.assertNotIn("<", content.split("NIFI_WEB_PROXY_HOST=")[1].split("\n")[0])


class PushProfileTest(unittest.TestCase):
    """The push profile exercises the flow inside NiFi instead of the TA."""

    @classmethod
    def setUpClass(cls):
        cls.data = matrix.load()

    def push_profiles(self):
        return {n: p for n, p in self.data["profiles"].items()
                if p.get("collection") == "hec"}

    def test_there_is_a_push_profile(self):
        self.assertTrue(self.push_profiles(), "no profile covers the push path")

    def test_the_push_profile_disables_the_ta_input(self):
        """Both paths at once duplicates every event."""
        for name, profile in self.push_profiles().items():
            with self.subTest(profile=name):
                text = open(os.path.join(
                    TESTS_DIR, "provision", "splunk",
                    "inputs.conf.%s" % profile["nifi_auth"])).read()
                self.assertIn("disabled = 1", text)

    def test_the_push_profile_runs_nifi_unauthenticated(self):
        """The flow calls its own API with no credentials, so an
        authenticated NiFi rejects it."""
        for name, profile in self.push_profiles().items():
            with self.subTest(profile=name):
                self.assertIn("none", profile["nifi_auth"])

    def test_the_push_profile_is_in_the_release_matrix(self):
        for name in self.push_profiles():
            with self.subTest(profile=name):
                self.assertIn(name, self.data["ci"]["release"])

    def test_the_unsecured_2x_entrypoint_exists(self):
        """The image's start.sh cannot be told to skip HTTPS."""
        script = os.path.join(TESTS_DIR, "provision", "nifi", "start-unsecured.sh")
        self.assertTrue(os.path.isfile(script))
        self.assertTrue(os.access(script, os.X_OK), "not executable")


class ProvisioningTest(unittest.TestCase):
    """Every auth mode needs a TA input template that matches it.

    Without this, the harness seeded the unsecured input (plain HTTP on
    8080, auth_type=none) even for the single-user profile, so the TA polled
    a port nothing was listening on and no events ever arrived.
    """

    @classmethod
    def setUpClass(cls):
        cls.data = matrix.load()

    def auth_modes(self):
        return {p["nifi_auth"] for p in self.data["profiles"].values()}

    def test_each_auth_mode_has_an_input_template(self):
        for mode in self.auth_modes():
            with self.subTest(auth=mode):
                path = os.path.join(
                    TESTS_DIR, "provision", "splunk", "inputs.conf.%s" % mode
                )
                self.assertTrue(os.path.isfile(path), "missing %s" % path)

    def test_input_template_matches_its_auth_mode(self):
        expected = {
            "none": ("auth_type = none", "http://nifi:8080"),
            "singleuser": ("auth_type = basic", "https://nifi:8443"),
            # The push profile collects through the flow, so the TA's input
            # is present but disabled: running both duplicates every event.
            "none2x": ("auth_type = none", "disabled = 1"),
        }
        for mode in self.auth_modes():
            with self.subTest(auth=mode):
                content = open(
                    os.path.join(
                        TESTS_DIR, "provision", "splunk", "inputs.conf.%s" % mode
                    )
                ).read()
                for fragment in expected[mode]:
                    self.assertIn(fragment, content)

    def test_single_user_input_states_its_tls_decision(self):
        """TLS verification defaults to on, and the containers use self-signed
        certificates, so the harness has to opt out deliberately rather than
        fail on every request."""
        content = open(
            os.path.join(TESTS_DIR, "provision", "splunk", "inputs.conf.singleuser")
        ).read()
        self.assertIn("verify_tls = 0", content)

    def test_single_user_input_uses_the_profile_password(self):
        """The input and the NiFi container must agree on the credentials."""
        env_values = dict(
            line.split("=", 1)
            for line in open(
                os.path.join(TESTS_DIR, "env", "nifi-singleuser.env")
            ).read().splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        content = open(
            os.path.join(TESTS_DIR, "provision", "splunk", "inputs.conf.singleuser")
        ).read()
        self.assertIn(
            "username = %s" % env_values["SINGLE_USER_CREDENTIALS_USERNAME"], content
        )
        self.assertIn(
            "password = %s" % env_values["SINGLE_USER_CREDENTIALS_PASSWORD"], content
        )


class WorkflowMatrixTest(unittest.TestCase):
    """The workflows repeat the profile lists, so they can drift from
    matrix.yml. This keeps them honest."""

    WORKFLOWS = {
        "dev.yml": "pull_request",
        "testing.yml": "pull_request",
        "main.yml": "release",
    }

    @classmethod
    def setUpClass(cls):
        cls.data = matrix.load()
        cls.workflow_dir = os.path.join(
            os.path.dirname(TESTS_DIR), ".github", "workflows"
        )

    def workflow(self, name):
        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed")
        return yaml.safe_load(open(os.path.join(self.workflow_dir, name)))

    def test_integration_matrix_matches_matrix_yml(self):
        for name, stage in self.WORKFLOWS.items():
            with self.subTest(workflow=name):
                jobs = self.workflow(name)["jobs"]
                self.assertIn("integration", jobs, "%s has no integration job" % name)
                declared = jobs["integration"]["strategy"]["matrix"]["profile"]
                self.assertEqual(declared, self.data["ci"][stage])

    def test_release_does_not_publish_without_integration(self):
        jobs = self.workflow("main.yml")["jobs"]
        self.assertIn("integration", jobs["publish"]["needs"])

    def test_unit_tests_run_in_every_workflow(self):
        for name in self.WORKFLOWS:
            with self.subTest(workflow=name):
                steps = self.workflow(name)["jobs"]["unittest"]["steps"]
                commands = " ".join(str(step.get("run", "")) for step in steps)
                self.assertIn("unittest discover", commands)
                self.assertNotIn("TODO", commands)


if __name__ == "__main__":
    unittest.main()
