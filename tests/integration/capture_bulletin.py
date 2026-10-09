#!/usr/bin/env python3
"""Provoke a real bulletin and capture the board's payload.

The field mapping in nifi_TA_monitoring/default/props.conf was written from
NiFi's BulletinDTO definitions, not from a captured event. A NiFi with no
flow never produces a bulletin, so the integration profiles can only check
that the polling runs, not that the mapping is right.

This builds the smallest flow that fails on purpose -- GenerateFlowFile
feeding an InvokeHTTP pointed at a closed port -- waits for the bulletin,
and writes the board response to docs/plans/samples/. Run it by hand
against a NiFi you do not mind dirtying:

    python3 capture_bulletin.py https://localhost:19443/nifi-api

It is not part of run.sh: it mutates the flow, which the assertions should
not do.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT_DIR = os.path.join(REPO, "docs", "plans", "samples")

USERNAME = os.environ.get("NIFI_USERNAME", "admin")
PASSWORD = os.environ.get("NIFI_PASSWORD", "ctsBtRBKHRAx69EqUghvvgEvjnaLjFEB")

# Throwaway container with a self-signed certificate for a name that only
# resolves locally; this script talks to nothing else.
_UNVERIFIED = ssl._create_unverified_context()


def call(url, method="GET", body=None, token=None, accept="application/json"):
    headers = {"Accept": accept}
    if token:
        headers["Authorization"] = "Bearer " + token
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=30, context=_UNVERIFIED) as response:
        raw = response.read().decode()
    return json.loads(raw) if raw and accept == "application/json" else raw


def login(base):
    body = urllib.parse.urlencode({"username": USERNAME, "password": PASSWORD}).encode()
    request = urllib.request.Request(
        base + "/access/token",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "*/*",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30, context=_UNVERIFIED) as response:
        return response.read().decode().strip()


def create_processor(base, token, root, name, kind, properties, position_x):
    return call(
        "%s/process-groups/%s/processors" % (base, root),
        method="POST",
        token=token,
        body={
            "revision": {"version": 0},
            "component": {
                "name": name,
                "type": kind,
                "position": {"x": position_x, "y": 100.0},
                "config": {
                    "properties": properties,
                    "schedulingPeriod": "1 sec",
                    "autoTerminatedRelationships": [],
                },
            },
        },
    )


def main(argv):
    base = (argv[0] if argv else "https://localhost:19443/nifi-api").rstrip("/")
    token = login(base)
    root = call(base + "/flow/process-groups/root", token=token)["processGroupFlow"]["id"]
    print("root process group: %s" % root)

    generate = create_processor(
        base, token, root, "capture-source",
        "org.apache.nifi.processors.standard.GenerateFlowFile",
        {"File Size": "1 B", "Batch Size": "1"}, 200.0,
    )
    # A closed port makes InvokeHTTP fail every run, which is what emits the
    # ERROR bulletin we are after.
    invoke = create_processor(
        base, token, root, "capture-failure",
        "org.apache.nifi.processors.standard.InvokeHTTP",
        {"HTTP URL": "http://127.0.0.1:1/unreachable", "HTTP Method": "GET"}, 500.0,
    )
    print("created %s and %s" % (generate["component"]["name"], invoke["component"]["name"]))

    call(
        "%s/process-groups/%s/connections" % (base, root),
        method="POST", token=token,
        body={
            "revision": {"version": 0},
            "component": {
                "source": {"id": generate["id"], "groupId": root, "type": "PROCESSOR"},
                "destination": {"id": invoke["id"], "groupId": root, "type": "PROCESSOR"},
                "selectedRelationships": ["success"],
            },
        },
    )

    # Terminate InvokeHTTP's outputs so it is valid enough to run.
    current = call("%s/processors/%s" % (base, invoke["id"]), token=token)
    relationships = [r["name"] for r in current["component"]["relationships"]]
    call(
        "%s/processors/%s" % (base, invoke["id"]),
        method="PUT", token=token,
        body={
            "revision": current["revision"],
            "component": {
                "id": invoke["id"],
                "config": {"autoTerminatedRelationships": relationships},
            },
        },
    )

    for processor_id in (generate["id"], invoke["id"]):
        state = call("%s/processors/%s" % (base, processor_id), token=token)
        call(
            "%s/processors/%s/run-status" % (base, processor_id),
            method="PUT", token=token,
            body={"revision": state["revision"], "state": "RUNNING"},
        )
    print("both processors running; waiting for a bulletin")

    board = None
    for _ in range(30):
        time.sleep(5)
        board = call(base + "/flow/bulletin-board?limit=100", token=token)
        if board.get("bulletinBoard", {}).get("bulletins"):
            break

    bulletins = board.get("bulletinBoard", {}).get("bulletins") or []
    if not bulletins:
        print("no bulletin appeared within 150s", file=sys.stderr)
        return 1

    version = call(base + "/system-diagnostics", token=token)
    version = version["systemDiagnostics"]["aggregateSnapshot"]["versionInfo"]["niFiVersion"]
    out = os.path.join(OUT_DIR, "nifi%s-bulletin-board.json" % ".".join(version.split(".")[:2]))
    with open(out, "w") as handle:
        json.dump(board, handle, indent=2)

    print("captured %d bulletin(s) from NiFi %s -> %s" % (len(bulletins), version, out))
    first = bulletins[0]
    print("entry keys:    %s" % sorted(first))
    print("bulletin keys: %s" % sorted(first.get("bulletin", {})))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
