"""Shared helpers for the integration assertions.

Talks to the running stack through Splunk's management API using the
splunklib already vendored in nifi_TA_monitoring/lib, so the harness needs
nothing installed.
"""

import json
import os
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(TESTS_DIR)
sys.path.insert(0, os.path.join(REPO, "nifi_TA_monitoring", "lib"))

import splunklib.client as client  # noqa: E402

# Deliberately not importing splunklib.results: the vendored copy needs the
# third-party `deprecation` package, which is not vendored alongside it (see
# the plan's defect B-24). Parsing the JSON output directly avoids it.


def env(name, default=None):
    """Read a value from the generated .env, falling back to the process env."""
    path = os.path.join(TESTS_DIR, ".env")
    if os.path.isfile(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key == name:
                    return value
    return os.environ.get(name, default)


def connect(app=None, owner=None):
    # verify=False is confined to this harness: the Splunk container generates
    # a self-signed certificate for a hostname that only exists inside the
    # compose network, and the endpoint is a throwaway container on localhost.
    # Production code must not do this -- see the plan's defect B-23 about the
    # TA disabling verification against real NiFi instances.
    kwargs = dict(
        host=env("SPLUNK_HOST", "localhost"),
        port=int(env("SPLUNK_MGMT_PORT", "38089")),
        username="admin",
        password=env("SPLUNK_PASSWORD", "Password123"),
        scheme="https",
        verify=False,
    )
    if app:
        kwargs["app"] = app
    if owner:
        kwargs["owner"] = owner
    return client.connect(**kwargs)


def search(service, query, earliest="-1h", timeout=180):
    """Run a search and return the rows as dicts.

    Deliberately not exec_mode="blocking": that blocks with no deadline, so a
    search that never finishes hangs the whole run. One did, for 16 hours.
    """
    job = service.jobs.create(
        query if query.lstrip().startswith("|") else "search " + query,
        earliest_time=earliest,
        latest_time="now",
        exec_mode="normal",
        adhoc_search_level="fast",
    )
    deadline = time.time() + timeout
    while not job.is_done():
        if time.time() > deadline:
            try:
                job.cancel()
            except Exception:  # noqa: BLE001 - cancelling is best effort
                pass
            raise TimeoutError("search did not finish in %ds: %s" % (timeout, query[:80]))
        time.sleep(1)
    payload = json.loads(job.results(output_mode="json").read().decode())
    return payload.get("results", [])


def wait_for_events(service, query, minimum=1, timeout=300, interval=10):
    """Poll a search until it returns at least `minimum` rows.

    The TA's input runs on an interval (60s by default), so the first events
    take a while to appear. Returns the rows, or [] if the timeout passes.
    """
    deadline = time.time() + timeout
    rows = []
    while time.time() < deadline:
        rows = search(service, query)
        if len(rows) >= minimum:
            return rows
        time.sleep(interval)
    return rows


class IntegrationTestCase(unittest.TestCase):
    """Base case that connects once and skips cleanly if the stack is down.

    `collection` declares which path a test class needs. A profile runs one
    path or the other -- never both, since that duplicates every event -- so a
    class that needs the TA has nothing to assert on a `hec` profile and says
    so instead of failing.
    """

    #: "pull", "hec", or None for a class that does not care.
    collection = None

    @classmethod
    def setUpClass(cls):
        try:
            cls.splunk = connect()
        except Exception as error:  # noqa: BLE001 - any failure means no stack
            raise unittest.SkipTest(
                "cannot reach Splunk management API: %s. "
                "Start the stack with ./run.sh" % error
            )
        cls.profile = env("PROFILE", "unknown")
        cls.nifi_version = env("NIFI_VERSION", "unknown")
        cls.profile_collection = env("COLLECTION", "pull")

    def setUp(self):
        if self.collection and self.collection != self.profile_collection:
            raise unittest.SkipTest(
                "this profile collects through the %s path, not %s"
                % (self.profile_collection, self.collection)
            )

    @property
    def nifi_major(self):
        return self.nifi_version.split(".")[0]
