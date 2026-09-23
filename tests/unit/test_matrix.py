"""Tests for tests/matrix.py.

matrix.py has two YAML readers: PyYAML when installed, and a minimal
fallback for the subset matrix.yml uses, because the CI container's
dependencies are not guaranteed. If those two disagree, run.sh silently
brings up a different environment than the one the profile names, so the
parity test matters more than either parser on its own.
"""

import os
import re
import sys
import unittest

TESTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import matrix  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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


class ExecutableBitTest(unittest.TestCase):
    """The scripts CI runs have to arrive executable from a fresh checkout.

    This repository has core.fileMode = false, so chmod on a working copy
    changes nothing that git records: a script can be 755 on the machine that
    wrote it and 644 for everyone who clones it. `./run.sh` is how all three
    workflows start the integration matrix and start-unsecured.sh is a
    container entrypoint, so a missing bit is not cosmetic -- it is a
    permission denied on a fresh clone, which is exactly what CI does and a
    developer never sees.
    """

    #: Executed directly rather than handed to an interpreter.
    SCRIPTS = [
        "run.sh",
        "provision/nifi/start-unsecured.sh",
        "provision/seed-splunk-etc.sh",
        "provision/seed-uf-etc.sh",
    ]

    def recorded_mode(self, relative):
        import subprocess
        try:
            out = subprocess.check_output(
                ["git", "ls-files", "-s", relative],
                cwd=TESTS_DIR, stderr=subprocess.DEVNULL).decode()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        if not out.strip():
            self.fail("%s is not tracked" % relative)
        return out.split()[0]

    def test_the_scripts_ci_runs_are_executable(self):
        for relative in self.SCRIPTS:
            with self.subTest(script=relative):
                self.assertEqual(
                    self.recorded_mode(relative), "100755",
                    "%s is not executable in the index; chmod alone does not "
                    "fix it with core.fileMode = false -- use "
                    "`git update-index --chmod=+x`" % relative,
                )


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

    def cluster_profiles(self):
        return {n: p for n, p in self.data["profiles"].items() if p.get("cluster")}

    def test_there_is_a_cluster_profile(self):
        """Section 11.3: cluster is a supported topology, so it needs a profile
        rather than a paragraph saying it is out of scope."""
        self.assertTrue(self.cluster_profiles(), "no profile runs a NiFi cluster")

    def test_a_cluster_profile_collects_through_each_strategy(self):
        """Cluster is an architecture, not a strategy: it has to be covered by
        both. The pull one proves the add-on reads a cluster; the push one
        proves the flow does not run on every node at once."""
        collections = {p.get("collection", "pull")
                       for p in self.cluster_profiles().values()}
        self.assertIn("pull", collections)
        self.assertIn("hec", collections)

    def test_the_cluster_profile_is_in_the_release_matrix(self):
        for name in self.cluster_profiles():
            with self.subTest(profile=name):
                self.assertIn(name, self.data["ci"]["release"])

    def test_the_cluster_env_reaches_compose(self):
        for name in self.cluster_profiles():
            with self.subTest(profile=name):
                env = matrix.env_for(name)
                self.assertIn("CLUSTER=1", env)
                self.assertIn("NIFI_CLUSTER_IS_NODE=true", env)
                self.assertIn("cluster", env)
        for name, profile in self.data["profiles"].items():
            if not profile.get("cluster"):
                with self.subTest(profile=name):
                    self.assertIn("CLUSTER=0", matrix.env_for(name))
                    self.assertIn("NIFI_CLUSTER_IS_NODE=false", matrix.env_for(name))

    def test_the_cluster_input_does_not_ask_for_cluster_data(self):
        """Detection is the add-on's job: an operator should not have to know
        their NiFi is clustered to get per-node data."""
        text = open(os.path.join(
            TESTS_DIR, "provision", "splunk", "inputs.conf.cluster")).read()
        self.assertNotIn("cluster_nodes", text)
        self.assertNotIn("node_diagnostics", text)
        self.assertNotIn("disabled = 1", text)

    def tls_profiles(self):
        return {n: p for n, p in self.data["profiles"].items()
                if p.get("tls_verify")}

    def test_a_profile_verifies_the_certificate(self):
        """2.0.0 made verification the default; without a profile for it the
        only covered path is the one operators are told not to use."""
        self.assertTrue(
            self.tls_profiles(),
            "no profile runs with verify_tls = 1 (defect R-8)")

    def test_the_tls_profile_is_authenticated(self):
        """There is no certificate to verify against a plain-HTTP NiFi."""
        for name, profile in self.tls_profiles().items():
            with self.subTest(profile=name):
                self.assertEqual(profile["nifi_auth"], "singleuser")

    def test_the_tls_env_reaches_compose(self):
        for name in self.tls_profiles():
            with self.subTest(profile=name):
                env = matrix.env_for(name)
                self.assertIn("TLS_VERIFY=1", env)
                self.assertIn("tlsverify", env)
        for name, profile in self.data["profiles"].items():
            if not profile.get("tls_verify"):
                with self.subTest(profile=name):
                    self.assertIn("TLS_VERIFY=0", matrix.env_for(name))

    def multi_profiles(self):
        return {n: p for n, p in self.data["profiles"].items()
                if int(p.get("instances", 1)) > 1}

    def test_there_is_a_multi_instance_profile(self):
        """The app's premise is centralising several NiFi instances; without a
        profile for it that claim has no coverage at all."""
        self.assertTrue(
            self.multi_profiles(),
            "no profile brings up more than one NiFi instance")

    def test_the_multi_instance_pull_profile_mixes_versions(self):
        """Only the pull one. There the point is that version autodetection is
        per input rather than per installation, which two identical NiFis
        would not prove; the push one is about two flows reaching one HEC, and
        the versions are beside that."""
        for name, profile in self.multi_profiles().items():
            if profile.get("collection", "pull") == "hec":
                continue
            with self.subTest(profile=name):
                self.assertIn("nifi_b_version", profile)
                self.assertNotEqual(
                    profile["nifi_b_version"], profile["nifi_version"])

    def test_the_multi_instance_profile_is_in_the_release_matrix(self):
        for name in self.multi_profiles():
            with self.subTest(profile=name):
                self.assertIn(name, self.data["ci"]["release"])

    def test_the_multi_instance_env_reaches_compose(self):
        for name in self.multi_profiles():
            with self.subTest(profile=name):
                env = matrix.env_for(name)
                # A profile can carry several compose profiles now, so match
                # the entry rather than the whole line.
                line = [l for l in env.splitlines() if l.startswith("COMPOSE_PROFILES=")][0]
                self.assertIn("multi", line.split("=", 1)[1].split(","))
                self.assertIn("INSTANCES=2", env)
                self.assertIn("NIFI_B_VERSION=", env)
        for name, profile in self.data["profiles"].items():
            if int(profile.get("instances", 1)) == 1:
                with self.subTest(profile=name):
                    self.assertIn("INSTANCES=1", matrix.env_for(name))

    def test_the_second_instance_has_its_own_input_and_lookup_row(self):
        extra = open(os.path.join(
            TESTS_DIR, "provision", "splunk", "inputs.conf.multi")).read()
        self.assertIn("[nifi://nifi-b]", extra)
        self.assertIn("host = nifi-b", extra)
        # In its own file, not appended to instance.csv: the overview panel
        # lists every configured instance and reports one that sends nothing
        # as Down, so a stray row is a phantom instance on every other profile.
        lookup = open(os.path.join(
            TESTS_DIR, "provision", "splunk", "instance-multi.csv")).read()
        self.assertIn("nifi-b", lookup)
        base = open(os.path.join(
            TESTS_DIR, "provision", "splunk", "instance.csv")).read()
        self.assertNotIn("nifi-b", base)

    def forwarder_profiles(self):
        return {n: p for n, p in self.data["profiles"].items()
                if p.get("forwarder")}

    def test_there_is_a_pull_plus_forwarder_profile(self):
        """The two recommended strategies are push (the flow, which tails the
        logs itself) and pull + forwarder. Each must be covered whole: the
        pull profiles alone only exercise the API half."""
        self.assertTrue(
            self.forwarder_profiles(),
            "no profile ships NiFi's logs, so the pull strategy is only "
            "half covered")

    def test_the_forwarder_profile_collects_through_the_pull_path(self):
        """A push profile already carries logs through the flow's TailFile
        branch; adding a forwarder there would duplicate them."""
        for name, profile in self.forwarder_profiles().items():
            with self.subTest(profile=name):
                self.assertNotEqual(profile.get("collection", "pull"), "hec")

    def test_the_forwarder_profile_is_in_the_release_matrix(self):
        for name in self.forwarder_profiles():
            with self.subTest(profile=name):
                self.assertIn(name, self.data["ci"]["release"])

    def test_the_forwarder_env_reaches_compose(self):
        """Compose reads COMPOSE_PROFILES from .env by itself; if matrix.py
        stopped writing it the forwarder would silently never start and the
        log assertions would skip instead of fail."""
        for name in self.forwarder_profiles():
            with self.subTest(profile=name):
                env = matrix.env_for(name)
                self.assertIn("COMPOSE_PROFILES=forwarder", env)
                self.assertIn("FORWARDER=1", env)
        for name, profile in self.data["profiles"].items():
            if not profile.get("forwarder"):
                with self.subTest(profile=name):
                    self.assertIn("FORWARDER=0", matrix.env_for(name))

    def test_the_push_profile_disables_the_ta_input(self):
        """Both paths at once duplicates every event.

        Asserted against the seed rather than the templates: which auth mode a
        profile uses and who collects are unrelated, and baking the disable
        into one auth template only held while push meant exactly one profile.
        """
        seed = open(os.path.join(
            TESTS_DIR, "provision", "seed-splunk-etc.sh")).read()
        self.assertIn('COLLECTION:-pull}" = "hec"', seed)
        self.assertIn("disabled = 1", seed)
        # And the rule has to be written in a form busybox's sed honours: the
        # substitution form fails there silently, which is a push profile
        # quietly collecting through both paths.
        self.assertNotIn("0,/^\\[nifi", seed)

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

    def test_the_makefile_gate_matches_the_workflows(self):
        """`make validate` exists so a person runs what CI runs.

        The warning ceiling is the one number the two share, and a Makefile
        that allowed more than the workflow would pass locally and fail on the
        release -- which is the drift the facade is there to remove, arriving
        by the facade itself.
        """
        makefile = open(os.path.join(REPO, "Makefile")).read()
        local = re.search(r"^MAX_WARNING \?= (\d+)", makefile, re.M)
        self.assertIsNotNone(local, "the Makefile declares no MAX_WARNING")
        for name in self.WORKFLOWS:
            with self.subTest(workflow=name):
                self.assertEqual(
                    str(self.workflow(name)["env"]["MAX_WARNING"]),
                    local.group(1))

    def test_the_makefile_packages_what_the_workflow_packages(self):
        """The TA ships from output/ and the app from the tree. Packaging the
        TA from the tree would produce an add-on with no app.conf and no UI,
        and slim would not complain (UI-3)."""
        makefile = open(os.path.join(REPO, "Makefile")).read()
        self.assertIn("slim package output/$(TA)", makefile)
        self.assertIn("slim package $(APP)", makefile)
        self.assertNotIn("slim package $(TA)", makefile)


if __name__ == "__main__":
    unittest.main()


class TopologyTest(unittest.TestCase):
    """`run.sh --list` claims what a profile starts; compose decides it.

    The list is derived from matrix.yml rather than from docker-compose.yml so
    that `--list` needs no Docker -- which is the point of a listing you run
    before anything else. That leaves the two free to drift, so this compares
    them: every long-lived service compose would start for a profile has to be
    in the list, and nothing else.

    The seed containers are excluded on purpose. They copy files and exit
    before splunkd is listening, and naming them next to the machines suggests
    they are part of the environment rather than of its setup.
    """

    COMPOSE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docker-compose.yml")

    @classmethod
    def setUpClass(cls):
        try:
            import yaml
        except ImportError:  # pragma: no cover - depends on the host
            raise unittest.SkipTest("PyYAML is not installed")
        with open(cls.COMPOSE) as handle:
            cls.services = yaml.safe_load(handle)["services"]

    def compose_would_start(self, profile_name):
        enabled = set(
            dict(line.split("=", 1) for line in
                 matrix.env_for(profile_name).splitlines()
                 if "=" in line and not line.startswith("#"))
            ["COMPOSE_PROFILES"].split(",")) - {""}
        started = set()
        for name, service in self.services.items():
            if name.startswith("provision"):
                continue          # seeds, not machines
            needed = set(service.get("profiles") or [])
            if not needed or needed & enabled:
                started.add(name)
        return started

    def test_the_listed_containers_are_the_ones_compose_starts(self):
        for name in matrix.load()["profiles"]:
            with self.subTest(profile=name):
                self.assertEqual(
                    set(matrix.topology(name)), self.compose_would_start(name))

    def test_every_profile_can_be_described(self):
        """--list <profile> reads fields that a new profile might not set."""
        for name in matrix.load()["profiles"]:
            with self.subTest(profile=name):
                text = matrix.describe(name)
                self.assertIn("Containers", text)
                self.assertIn("Strategy", text)
                self.assertTrue(
                    text.splitlines()[2].strip(),
                    "profile %s has no description in matrix.yml" % name)
