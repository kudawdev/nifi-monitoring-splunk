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


def base_url():
    if env("NIFI_AUTH") == "singleuser":
        return "https://localhost:%s/nifi-api" % env("NIFI_HTTPS_PORT", "38443")
    return "http://localhost:%s/nifi-api" % env("NIFI_HTTP_PORT", "38080")


def request(url, data=None, token=None, form=False):
    headers = {"Accept": "application/json"}
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


def get_token():
    """Exercise the same login the TA uses, so a broken auth profile fails here."""
    return request(
        base_url() + "/access/token",
        data={
            "username": env("NIFI_USERNAME", "admin"),
            "password": env(
                "NIFI_PASSWORD", "ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB"
            ),
        },
        form=True,
    ).strip()


def describe(token):
    """Report the NiFi version, from VERSION_INFO on 2.x or diagnostics on 1.x."""
    try:
        payload = json.loads(
            request(
                base_url() + "/flow/metrics/json?includedRegistries=VERSION_INFO",
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
        payload = json.loads(request(base_url() + "/system-diagnostics", token=token))
        info = payload["systemDiagnostics"]["aggregateSnapshot"].get("versionInfo", {})
        return "NiFi %s on Java %s" % (
            info.get("niFiVersion", "?"),
            info.get("javaVersion", "?"),
        )


def main():
    deadline = time.time() + TIMEOUT_SECONDS
    last_error = None
    while time.time() < deadline:
        try:
            token = get_token() if env("NIFI_AUTH") == "singleuser" else None
            print("    %s at %s" % (describe(token), base_url()))
            return 0
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, KeyError,
                ValueError) as error:
            last_error = error
            time.sleep(5)
    print(
        "NiFi did not become usable within %ds: %s" % (TIMEOUT_SECONDS, last_error),
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
