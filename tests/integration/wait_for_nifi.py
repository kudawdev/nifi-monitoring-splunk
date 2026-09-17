#!/usr/bin/env python3
"""Block until NiFi's REST API answers, then report what it is.

Run by run.sh after `docker compose up --wait`. The compose healthcheck only
proves the port is open; this also proves the API is usable and prints the
version, which makes a failing CI run readable.

Exits non-zero if NiFi does not become usable within the timeout.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TIMEOUT_SECONDS = int(os.environ.get("NIFI_WAIT_TIMEOUT", "300"))

# The container generates a self-signed certificate for a name that only
# resolves inside the compose network; this client only ever talks to that
# throwaway container.
_UNVERIFIED = ssl._create_unverified_context()


def env(name, default=None):
    path = os.path.join(TESTS_DIR, ".env")
    if os.path.isfile(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                if key == name:
                    return value
    return os.environ.get(name, default)


def base_url(port=None):
    if env("NIFI_AUTH") == "singleuser":
        return "https://localhost:%s/nifi-api" % (port or env("NIFI_HTTPS_PORT", "38443"))
    return "http://localhost:%s/nifi-api" % (port or env("NIFI_HTTP_PORT", "38080"))


def instance_urls():
    """Every NiFi the profile brings up.

    The multi-instance profile runs a second, independent node, and waiting
    only for the first would let the assertions start against a NiFi that is
    still booting -- which shows up as an empty index rather than as an error.
    """
    urls = [base_url()]
    if int(env("INSTANCES", "1")) > 1:
        # The second instance follows the first's scheme, so its port has to
        # as well: the push profiles run both NiFis on plain HTTP, and asking
        # for the HTTPS port there reaches a published port with nothing
        # behind it -- which shows up as a connection reset, not as a refusal.
        second = (env("NIFI_B_HTTPS_PORT", "38444")
                  if env("NIFI_AUTH") == "singleuser"
                  else env("NIFI_B_HTTP_PORT", "38081"))
        urls.append(base_url(second))
    return urls


def request(url, data=None, token=None, form=False, accept="application/json"):
    # /access/token answers text/plain (the raw JWT), so asking only for JSON
    # gets a 406 Not Acceptable from NiFi.
    headers = {"Accept": accept}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if data is not None:
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=_UNVERIFIED) as response:
        return response.read().decode()


def get_token(url=None):
    """Exercise the same login the TA uses, so a broken auth profile fails here."""
    return request(
        (url or base_url()) + "/access/token",
        data={
            "username": env("NIFI_USERNAME", "admin"),
            "password": env(
                "NIFI_PASSWORD", "ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB"
            ),
        },
        form=True,
        accept="*/*",
    ).strip()


def describe(token, url=None):
    """Report the NiFi version, from VERSION_INFO on 2.x or diagnostics on 1.x."""
    url = url or base_url()
    try:
        payload = json.loads(
            request(
                url + "/flow/metrics/json?includedRegistries=VERSION_INFO",
                token=token,
            )
        )
        sample = payload["samples"][0]
        labels = dict(zip(sample["labelNames"], sample["labelValues"]))
        return "NiFi %s on Java %s" % (
            labels.get("framework_version"),
            labels.get("java_version"),
        )
    except Exception:
        # VERSION_INFO returns 404 before NiFi 2.0; fall back to diagnostics.
        payload = json.loads(request(url + "/system-diagnostics", token=token))
        info = payload["systemDiagnostics"]["aggregateSnapshot"].get("versionInfo", {})
        return "NiFi %s on Java %s" % (
            info.get("niFiVersion", "?"),
            info.get("javaVersion", "?"),
        )


def wait_for_cluster(deadline):
    """Block until every node is CONNECTED, twice in a row.

    Not /flow/cluster/summary: its connectedNodeCount counts a node that is
    still joining, so the cluster reports 2 / 2 while it will still refuse to
    change the flow -- "Cluster is unable to service request to change flow:
    Node nifi:8080 is currently connecting", which is how the first clustered
    push run failed. /controller/cluster gives each node's real status.

    Twice in a row because the status flips through CONNECTED while a node is
    still settling; one reading is not evidence that it has stopped moving.
    """
    stable = 0
    while time.time() < deadline:
        try:
            nodes = json.loads(request(base_url() + "/controller/cluster"))["cluster"]["nodes"]
            states = [n.get("status") for n in nodes]
            if len(nodes) >= 2 and all(s == "CONNECTED" for s in states):
                stable += 1
                if stable >= 2:
                    print("    cluster: %d nodes CONNECTED" % len(nodes))
                    return True
            else:
                stable = 0
                print("    still forming: %s" % states)
        except Exception as error:  # noqa: BLE001 - keep polling while it forms
            stable = 0
            print("    still forming: %s" % error)
        time.sleep(5)
    return False


def main():
    deadline = time.time() + TIMEOUT_SECONDS
    last_error = None
    attempt = 0
    pending = list(instance_urls())
    while time.time() < deadline:
        attempt += 1
        try:
            for url in list(pending):
                token = get_token(url) if env("NIFI_AUTH") == "singleuser" else None
                print("    %s at %s" % (describe(token, url), url))
                pending.remove(url)
            if env("CLUSTER", "0") == "1" and not wait_for_cluster(deadline):
                print("the cluster did not form within the timeout", file=sys.stderr)
                return 1
            return 0
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                ValueError) as error:
            last_error = error
            if attempt == 1 or attempt % 6 == 0:
                print("    still waiting: %s: %s" % (type(error).__name__, error))
            time.sleep(5)
    print(
        "NiFi did not become usable within %ds: %s" % (TIMEOUT_SECONDS, last_error),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
