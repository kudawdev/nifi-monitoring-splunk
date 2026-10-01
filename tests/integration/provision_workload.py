#!/usr/bin/env python3
"""Give every harness NiFi something to monitor.

A NiFi with no flow leaves most of the dashboards with nothing to show:
no queues, no bulletins, no component history, every component count at
zero. Each panel then passes its test by returning nothing, which is the
failure the dashboard tests exist to catch (D-T). This builds a small,
deliberately unhealthy workload in each instance of the profile:

- traffic:     GenerateFlowFile -> ReplaceText -> UpdateAttribute (drained)
- backlog:     GenerateFlowFile -> a stopped consumer, with a low
               backpressure threshold, so a connection sits at its limit
- failure:     GenerateFlowFile -> InvokeHTTP at a closed port, which raises
               an ERROR bulletin on every run
- invalid:     a PutFile with no directory
- disabled:    an UpdateAttribute left disabled

Then it points the status-history settings at those components: on a pull
profile, by updating the TA input; on a push profile, provision_flow.py
reads the ids this writes to tests/.workload.json and puts them in the
flow's parameters.

Run by run.sh for every profile, after the instance lookup is loaded.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from support import env  # noqa: E402

OUT = os.path.join(TESTS_DIR, ".workload.json")
GROUP_NAME = "harness-workload"

# Throwaway containers with self-signed certificates for names that only
# resolve inside the compose network.
_UNVERIFIED = ssl._create_unverified_context()

STD = "org.apache.nifi.processors.standard."
ATTR = "org.apache.nifi.processors.attributes."


def env_file_value(path, name):
    full = os.path.join(TESTS_DIR, path)
    if not os.path.isfile(full):
        return None
    for line in open(full):
        line = line.strip()
        if line.startswith(name + "="):
            return line.split("=", 1)[1]
    return None


def instances():
    """(input name, base url, credentials or None) for each NiFi."""
    secured = env("NIFI_AUTH", "none") == "singleuser"
    out = []
    for suffix, name in (("", "nifi"), ("_B", "nifi-b")):
        if suffix and int(env("INSTANCES", "1")) < 2:
            continue
        if secured:
            port = env("NIFI%s_HTTPS_PORT" % suffix, "38444" if suffix else "38443")
            env_file = env("NIFI%s_ENV_FILE" % suffix)
            creds = (env_file_value(env_file, "SINGLE_USER_CREDENTIALS_USERNAME") or "admin",
                     env_file_value(env_file, "SINGLE_USER_CREDENTIALS_PASSWORD"))
            out.append((name, "https://localhost:%s/nifi-api" % port, creds))
        else:
            port = env("NIFI%s_HTTP_PORT" % suffix, "38081" if suffix else "38080")
            out.append((name, "http://localhost:%s/nifi-api" % port, None))
    return out


class NiFi(object):
    """The few REST calls this needs, with the cluster retries."""

    def __init__(self, base, creds):
        self.base = base
        self.token = None
        if creds:
            body = urllib.parse.urlencode({"username": creds[0], "password": creds[1]}).encode()
            request = urllib.request.Request(
                base + "/access/token", data=body, method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "*/*"})
            with urllib.request.urlopen(request, timeout=30, context=_UNVERIFIED) as response:
                self.token = response.read().decode().strip()

    def call(self, path, method="GET", body=None, attempts=30):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        for attempt in range(attempts):
            request = urllib.request.Request(self.base + path, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(request, timeout=60, context=_UNVERIFIED) as response:
                    raw = response.read().decode()
                return json.loads(raw) if raw else None
            except urllib.error.HTTPError as error:
                # A cluster answers 409 (node connecting) or 500 (replication)
                # while a node joins; nothing else is worth retrying.
                if error.code in (409, 500, 503) and attempt < attempts - 1:
                    time.sleep(5)
                    continue
                raise SystemExit("%s %s -> HTTP %s: %s" % (
                    method, path, error.code, error.read().decode()[:300]))

    def processor(self, group, name, kind, properties=None, x=0, y=0, period="1 sec",
                  terminate=None):
        created = self.call("/process-groups/%s/processors" % group, "POST", {
            "revision": {"version": 0},
            "component": {
                "name": name, "type": kind, "position": {"x": x, "y": y},
                "config": {"properties": properties or {}, "schedulingPeriod": period},
            },
        })
        if terminate is not None:
            current = self.call("/processors/%s" % created["id"])
            relationships = [r["name"] for r in current["component"]["relationships"]]
            names = relationships if terminate == "all" else [r for r in relationships if r in terminate]
            created = self.call("/processors/%s" % created["id"], "PUT", {
                "revision": current["revision"],
                "component": {"id": created["id"], "config": {"autoTerminatedRelationships": names}},
            })
        return created

    def connect(self, group, source, destination, relationships, objects=10000):
        return self.call("/process-groups/%s/connections" % group, "POST", {
            "revision": {"version": 0},
            "component": {
                "source": {"id": source["id"], "groupId": group, "type": "PROCESSOR"},
                "destination": {"id": destination["id"], "groupId": group, "type": "PROCESSOR"},
                "selectedRelationships": relationships,
                "backPressureObjectThreshold": objects,
            },
        })

    def set_state(self, processor, state):
        current = self.call("/processors/%s" % processor["id"])
        return self.call("/processors/%s/run-status" % processor["id"], "PUT", {
            "revision": current["revision"], "state": state})


def reuse(nifi, root, gid):
    """The ids of a workload an earlier run built (run.sh --keep, re-run)."""
    processors = nifi.call("/process-groups/%s/processors" % gid)["processors"]
    by_name = {p["component"]["name"]: p["id"] for p in processors}
    return {
        "root": root,
        "group": gid,
        "processors": [by_name[n] for n in ("traffic-source", "traffic-transform",
                                            "failure-invokehttp", "backlog-source")],
        "process_groups": [root, gid],
    }


def build(nifi):
    root = nifi.call("/flow/process-groups/root")["processGroupFlow"]["id"]
    existing = nifi.call("/process-groups/%s/process-groups" % root)["processGroups"]
    for group in existing:
        if group["component"]["name"] == GROUP_NAME:
            return reuse(nifi, root, group["id"])

    group = nifi.call("/process-groups/%s/process-groups" % root, "POST", {
        "revision": {"version": 0},
        "component": {"name": GROUP_NAME, "position": {"x": 0, "y": 600}},
    })
    gid = group["id"]

    # traffic: something is always moving
    source = nifi.processor(gid, "traffic-source", STD + "GenerateFlowFile",
                            {"File Size": "4 KB", "Batch Size": "20"}, 0, 0)
    transform = nifi.processor(gid, "traffic-transform", STD + "ReplaceText", {},
                               0, 200, terminate=["failure"])
    sink = nifi.processor(gid, "traffic-sink", ATTR + "UpdateAttribute", {},
                          0, 400, terminate="all")
    nifi.connect(gid, source, transform, ["success"])
    nifi.connect(gid, transform, sink, ["success"])

    # backlog: a connection pinned at its backpressure limit
    backlog_source = nifi.processor(gid, "backlog-source", STD + "GenerateFlowFile",
                                    {"File Size": "16 KB", "Batch Size": "5"}, 400, 0)
    stalled = nifi.processor(gid, "backlog-stalled-consumer", ATTR + "UpdateAttribute", {},
                             400, 200, terminate="all")
    nifi.connect(gid, backlog_source, stalled, ["success"], objects=500)

    # failure: an ERROR bulletin on every run
    failure_source = nifi.processor(gid, "failure-source", STD + "GenerateFlowFile",
                                    {"File Size": "1 B", "Batch Size": "1"}, 800, 0, period="10 sec")
    failing = nifi.processor(gid, "failure-invokehttp", STD + "InvokeHTTP",
                             {"HTTP URL": "http://127.0.0.1:1/unreachable", "HTTP Method": "GET"},
                             800, 200, terminate="all")
    nifi.connect(gid, failure_source, failing, ["success"])

    # invalid and disabled components, so those counts are not all zero
    nifi.processor(gid, "invalid-putfile", STD + "PutFile", {}, 1200, 0)
    disabled = nifi.processor(gid, "disabled-updateattribute", ATTR + "UpdateAttribute", {},
                              1200, 200, terminate="all")

    for processor in (source, transform, sink, backlog_source, failure_source, failing):
        nifi.set_state(processor, "RUNNING")
    nifi.set_state(disabled, "DISABLED")

    return {
        "root": root,
        "group": gid,
        "processors": [source["id"], transform["id"], failing["id"], backlog_source["id"]],
        "process_groups": [root, gid],
    }


def configure_ta_input(name, ids):
    """Point the TA input's status-history settings at the workload."""
    from support import connect  # needs the built add-on's splunklib
    service = connect(app="nifi_TA_monitoring", owner="nobody")
    path = "data/inputs/nifi/%s" % urllib.parse.quote(name, safe="")
    # The endpoint wants the input's required arguments on every update, so
    # read them back and send them with the change.
    current = json.loads(service.get(path, output_mode="json").body.read().decode())
    content = current["entry"][0]["content"]
    # Everything the input holds except what Splunk adds when it reads it back.
    added = ("disabled", "host_resolved", "python.required", "python.version")
    required = {k: ("1" if v else "0") if isinstance(v, bool) else v
                for k, v in content.items()
                if not k.startswith("eai:") and k not in added
                and v is not None and not isinstance(v, (dict, list))}
    service.post(path,
                 endpoint_processors_history=",".join(ids["processors"]),
                 endpoint_process_groups_history=",".join(ids["process_groups"]),
                 **required)


def main():
    written = {}
    for name, base, creds in instances():
        nifi = NiFi(base, creds)
        ids = build(nifi)
        written[name] = ids
        print("    %s: workload group %s, %d processors and %d groups with history"
              % (name, ids["group"], len(ids["processors"]), len(ids["process_groups"])))
        if env("COLLECTION", "pull") != "hec":
            configure_ta_input(name, ids)
            print("    %s: TA input now collects their status history" % name)
        if env("CLUSTER", "0") == "1":
            break   # a cluster replicates the flow; one node is the whole cluster
    with open(OUT, "w") as handle:
        json.dump(written, handle, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
