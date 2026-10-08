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

With SHOWCASE=1 (run.sh --showcase) it builds a healthy flow instead, for
the documentation's screenshots: two process groups with steady traffic, a
queue that fills and drains, and a WARN bulletin every few minutes -- no
invalid components and no errors, so every instance reads Healthy.

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
STALE_REVISION = "is not the most up-to-date revision"


class StaleRevision(Exception):
    """NiFi refused a PUT whose revision another node has moved past."""


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
                message = error.read().decode()
                # A stale revision cannot succeed by resending the same body:
                # the caller has to read the component again.
                if error.code == 409 and STALE_REVISION in message:
                    raise StaleRevision(message)
                # A cluster answers 409 (node connecting) or 500 (replication)
                # while a node joins; nothing else is worth retrying.
                if error.code in (409, 500, 503) and attempt < attempts - 1:
                    time.sleep(5)
                    continue
                raise SystemExit("%s %s -> HTTP %s: %s" % (
                    method, path, error.code, message[:300]))

    def update(self, processor, path, body_from):
        """PUT a body built from the processor's current revision.

        On a cluster the revision read from one node can be behind the one
        another node holds while a change replicates, and NiFi answers 409
        "is not the most up-to-date revision". Re-reading is the only retry
        that can succeed.
        """
        for attempt in range(10):
            current = self.call("/processors/%s" % processor["id"])
            try:
                return self.call(path, "PUT", body_from(current))
            except StaleRevision as error:
                if attempt == 9:
                    raise SystemExit("PUT %s -> HTTP 409: %s" % (path, str(error)[:300]))
                time.sleep(3)

    def processor(self, group, name, kind, properties=None, x=0, y=0, period="1 sec",
                  terminate=None, run_duration=0):
        config = {"properties": properties or {}, "schedulingPeriod": period}
        if run_duration:
            config["runDurationMillis"] = run_duration
        created = self.call("/process-groups/%s/processors" % group, "POST", {
            "revision": {"version": 0},
            "component": {
                "name": name, "type": kind, "position": {"x": x, "y": y},
                "config": config,
            },
        })
        if terminate is not None:
            current = self.call("/processors/%s" % created["id"])
            relationships = [r["name"] for r in current["component"]["relationships"]]
            names = relationships if terminate == "all" else [r for r in relationships if r in terminate]
            created = self.update(created, "/processors/%s" % created["id"], lambda fresh: {
                "revision": fresh["revision"],
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

    def set_properties(self, processor, by_display_name):
        """Set properties by display name: their keys differ between NiFi lines.

        LogMessage's level is `log-level` on 1.x and `Log Level` on 2.x; a key
        the processor does not know is kept and makes it invalid.
        """
        current = self.call("/processors/%s" % processor["id"])
        descriptors = current["component"]["config"]["descriptors"]
        # Case-insensitive: 1.x says "Log message" where 2.x says "Log Message".
        keys = {d["displayName"].lower(): key for key, d in descriptors.items()
                if not d.get("dynamic")}
        properties = {}
        for names, value in by_display_name.items():
            # A tuple is alternatives: InvokeHTTP's URL is "Remote URL" on
            # older 1.x and "HTTP URL" since.
            names = names if isinstance(names, tuple) else (names,)
            key = next(keys[n.lower()] for n in names if n.lower() in keys)
            properties[key] = value
        return self.update(processor, "/processors/%s" % processor["id"], lambda fresh: {
            "revision": fresh["revision"],
            "component": {"id": processor["id"], "config": {"properties": properties}},
        })

    def set_state(self, processor, state):
        return self.update(processor, "/processors/%s/run-status" % processor["id"], lambda fresh: {
            "revision": fresh["revision"], "state": state})


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


SHOWCASE_GROUPS = ("Orders ingest", "Telemetry enrichment")
#: Where "Receive orders" listens, inside each NiFi container.
SHOWCASE_PORT = 9411


def build_showcase(nifi):
    """A healthy flow that looks like work, for the documentation's screenshots."""
    root = nifi.call("/flow/process-groups/root")["processGroupFlow"]["id"]
    existing = {g["component"]["name"]: g["id"] for g in
                nifi.call("/process-groups/%s/process-groups" % root)["processGroups"]}
    if all(name in existing for name in SHOWCASE_GROUPS):
        groups = [existing[name] for name in SHOWCASE_GROUPS]
        processors = []
        for gid in groups:
            processors += [p["id"] for p in
                           nifi.call("/process-groups/%s/processors" % gid)["processors"]]
        return {"root": root, "group": groups[0], "processors": processors,
                "process_groups": [root] + groups}

    def group(name, y):
        return nifi.call("/process-groups/%s/process-groups" % root, "POST", {
            "revision": {"version": 0},
            "component": {"name": name, "position": {"x": 0, "y": y}},
        })["id"]

    # Orders arrive over HTTP and leave over HTTP, so the throughput charts
    # have data received from and sent to outside the flow, not only written.
    orders = group(SHOWCASE_GROUPS[0], 0)
    receive = nifi.processor(orders, "Receive orders", STD + "ListenHTTP", {}, 400, 0,
                             period="0 sec")
    nifi.set_properties(receive, {"Listening Port": str(SHOWCASE_PORT)})
    normalize = nifi.processor(orders, "Normalize JSON", STD + "ReplaceText", {},
                               400, 200, terminate=["failure"])
    # Runs every 10 s and drains what queued meanwhile: a queue that fills and
    # empties, well under its backpressure threshold.
    tag = nifi.processor(orders, "Tag region", ATTR + "UpdateAttribute", {},
                         400, 400, period="10 sec", terminate="all", run_duration=2000)
    nifi.connect(orders, receive, normalize, ["success"])
    nifi.connect(orders, normalize, tag, ["success"], objects=250)
    feed = nifi.processor(orders, "Partner feed", STD + "GenerateFlowFile",
                          {"File Size": "2 KB", "Batch Size": "10"}, 0, 0)
    post = nifi.processor(orders, "Post to gateway", STD + "InvokeHTTP", {}, 0, 200,
                          period="0 sec", terminate="all")
    nifi.set_properties(post, {"HTTP Method": "POST",
                               ("HTTP URL", "Remote URL"):
                                   "http://localhost:%d/contentListener" % SHOWCASE_PORT})
    nifi.connect(orders, feed, post, ["success"])

    telemetry = group(SHOWCASE_GROUPS[1], 300)
    collect = nifi.processor(telemetry, "Collect metrics", STD + "GenerateFlowFile",
                             {"File Size": "8 KB", "Batch Size": "5"}, 0, 0)
    enrich = nifi.processor(telemetry, "Enrich with host", ATTR + "UpdateAttribute", {},
                            0, 400)
    route = nifi.processor(telemetry, "Route by type", STD + "RouteOnAttribute", {},
                           0, 600, terminate="all")
    # On 1.x, a deprecated processor, so the Logs view's deprecations panel has
    # the kind of entry it exists for. HashContent is gone from 2.x.
    # Ask for that one type: listing every type takes over a minute on 2.x.
    hash_content = nifi.call("/flow/processor-types?type=" + STD + "HashContent")
    fingerprint = None
    if hash_content["processorTypes"]:
        # One FlowFile per run, so it runs back to back: on a 1 s schedule it
        # falls behind the 5 a second it is fed and its queue never stops growing.
        fingerprint = nifi.processor(telemetry, "Fingerprint payload", STD + "HashContent", {},
                                     0, 200, period="0 sec", terminate=["failure"])
        nifi.connect(telemetry, collect, fingerprint, ["success"])
        nifi.connect(telemetry, fingerprint, enrich, ["success"])
    else:
        nifi.connect(telemetry, collect, enrich, ["success"])
    nifi.connect(telemetry, enrich, route, ["success"])
    # A WARN bulletin now and then, so the bulletin panels are not empty.
    probe = nifi.processor(telemetry, "Latency probe", STD + "GenerateFlowFile",
                           {"File Size": "1 B", "Batch Size": "1"}, 400, 0, period="5 min")
    warn = nifi.processor(telemetry, "Report slow upstream", STD + "LogMessage", {},
                          400, 200, terminate="all")
    nifi.set_properties(warn, {"Log Level": "warn",
                               "Log Message": "Upstream latency above 2 s; batch retried"})
    nifi.connect(telemetry, probe, warn, ["success"])

    # The listener first: a POST before it is up fails, and that is an ERROR
    # bulletin on a fleet that is supposed to read Healthy.
    nifi.set_state(receive, "RUNNING")
    time.sleep(5)
    running = [receive, normalize, tag, feed, post, collect, enrich, route, probe, warn]
    if fingerprint:
        running.insert(6, fingerprint)
    for processor in running[1:]:
        nifi.set_state(processor, "RUNNING")
    return {
        "root": root,
        "group": orders,
        "processors": [p["id"] for p in running],
        "process_groups": [root, orders, telemetry],
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
        ids = build_showcase(nifi) if env("SHOWCASE", "0") == "1" else build(nifi)
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
