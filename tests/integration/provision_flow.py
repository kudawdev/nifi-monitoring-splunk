#!/usr/bin/env python3
"""Install and start the monitoring flow inside the harness NiFi.

This is what the push path actually asks an operator to do: import the flow
definition, fill in the parameter context, and start it. Doing it from a
script means the profile tests the documented procedure rather than a
convenient shortcut.

Run by run.sh only for profiles whose collection path is `hec`.
"""

import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TESTS_DIR = os.path.dirname(HERE)
REPO = os.path.dirname(TESTS_DIR)

sys.path.insert(0, HERE)
from support import env  # noqa: E402

_UNVERIFIED = ssl._create_unverified_context()


#: Which NiFi the next call goes to. A push profile with two instances has to
#: install the flow in both -- there is no coordinator to replicate it, they
#: are unrelated NiFis that happen to send to the same HEC.
_PORT = None


def base_url():
    return "http://localhost:%s/nifi-api" % (_PORT or env("NIFI_HTTP_PORT", "38080"))


def instance_ports():
    ports = [env("NIFI_HTTP_PORT", "38080")]
    if int(env("INSTANCES", "1")) > 1:
        ports.append(env("NIFI_B_HTTP_PORT", "38081"))
    return ports


class _CallFailed(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


#: A cluster refuses to change its flow while any node is still joining, and
#: it goes back to joining while it inherits a flow that has just changed --
#: so this is not only a startup race. Every mutating call can land in that
#: window, which is why the retry lives here rather than around one of them.
#: Measured messages: HTTP 500 replicating the import to the other node, and
#: HTTP 409 "Cluster is unable to service request to change flow: Node
#: nifi:8080 is currently connecting".
CLUSTER_SETTLING = "currently connecting"
RETRIES = 12
RETRY_WAIT = 10


def call(path, body=None, method="GET", raw=None, content_type="application/json",
         raise_for_status=True):
    """Retries a request the cluster refuses while it is settling.

    Only that: any other 4xx -- a malformed flow, a bad parameter -- fails at
    once, and every attempt is printed even when a later one succeeds, so a
    real problem shows up in the log instead of being smoothed away.
    """
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            return _call_once(path, body, method, raw, content_type)
        except _CallFailed as error:
            last = error
            transient = error.status >= 500 or (
                error.status == 409 and CLUSTER_SETTLING in str(error))
            if not transient:
                if raise_for_status:
                    raise SystemExit(str(error))
                raise
            print("    attempt %d: cluster still settling, retrying" % attempt)
            time.sleep(RETRY_WAIT)
    if raise_for_status:
        raise SystemExit("gave up after %d attempts: %s" % (RETRIES, last))
    raise last


def _call_once(path, body=None, method="GET", raw=None, content_type="application/json"):
    headers = {"Accept": "application/json"}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw, content_type
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    request = urllib.request.Request(base_url() + path, data=data,
                                     headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=120, context=_UNVERIFIED) as response:
            text = response.read().decode()
    except urllib.error.HTTPError as error:
        # NiFi puts the reason in the body. Without it a 500 says nothing at
        # all, which is how the first clustered run of this script ended.
        detail = ""
        try:
            detail = error.read().decode()[:500]
        except Exception:  # noqa: BLE001 - best effort
            pass
        raise _CallFailed(error.code, "%s %s -> HTTP %s %s\n%s" % (
            method, path, error.code, error.reason, detail))
    return json.loads(text) if text else {}


GROUP_NAME = "NiFiMonitoring"


def imported_groups(root):
    """Every copy of the flow directly under root.

    NiFi does not refuse a second import of the same flow, it renames what
    collides -- so a duplicate announces itself as ports called "Copy of
    bulletin_report" rather than as an error.
    """
    flow = call("/flow/process-groups/%s" % root)["processGroupFlow"]["flow"]
    return [group for group in flow.get("processGroups", [])
            if GROUP_NAME in group["component"]["name"]]


def upload_flow(root, path):
    """Import the flow definition the way the UI's 'import from file' does.

    Deliberately not routed through call(). This POST is not idempotent, and
    on a cluster the coordinator can answer 500 because a node is still
    joining *after* the group has been created -- so the generic retry
    imported the flow again, once per attempt. Three attempts in one run left
    three copies of NiFiMonitoring under root, two stopped and one running,
    with ports named "Copy of Copy of bulletin_report". The events the
    dashboards need never arrived, because the copy that was running had its
    ports renamed out from under the connections.

    So: check whether the group landed before deciding the attempt failed.
    """
    boundary = "----nifiharness"
    with open(path, "rb") as handle:
        content = handle.read()

    parts = []
    for name, value in (("groupName", GROUP_NAME), ("positionX", "0"),
                        ("positionY", "0"), ("clientId", "harness"),
                        ("disconnectedNodeAcknowledged", "false")):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                  "filename=\"NiFiMonitoring.json\"\r\n"
                  "Content-Type: application/json\r\n\r\n" % boundary).encode())
    parts.append(content)
    parts.append(("\r\n--%s--\r\n" % boundary).encode())

    already = imported_groups(root)
    if already:
        raise SystemExit(
            "%d copies of %s already exist under root; this script expects a "
            "fresh NiFi" % (len(already), GROUP_NAME))

    payload = b"".join(parts)
    endpoint = "/process-groups/%s/process-groups/upload" % root
    content_type = "multipart/form-data; boundary=%s" % boundary

    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            return _call_once(endpoint, method="POST", raw=payload,
                              content_type=content_type)
        except _CallFailed as error:
            last = error
            transient = error.status >= 500 or (
                error.status == 409 and CLUSTER_SETTLING in str(error))
            if not transient:
                raise SystemExit(str(error))
            landed = imported_groups(root)
            if landed:
                print("    attempt %d answered HTTP %s but the group was "
                      "created; using it rather than importing again"
                      % (attempt, error.status))
                return landed[0]
            print("    attempt %d: cluster still settling, retrying" % attempt)
            time.sleep(RETRY_WAIT)
    raise SystemExit("gave up importing the flow after %d attempts: %s"
                     % (RETRIES, last))


def set_variables(group_id, values):
    """The 1.x way of doing what a parameter context does in 2.x.

    NiFi 1.x has no parameter context in this flow -- the variable registry is
    what the processors reference -- and 2.x removed the registry entirely.
    One flow artefact per line, one configuration mechanism per line: the same
    split the plan describes for the flow files themselves.
    """
    for name, value in values:
        group = call("/process-groups/%s" % group_id)
        request = call("/process-groups/%s/variable-registry/update-requests" % group_id,
                       method="POST", body={
                           "processGroupRevision": group["revision"],
                           "variableRegistry": {
                               "processGroupId": group_id,
                               "variables": [{"variable": {"name": name, "value": value}}],
                           },
                       })
        request_id = request["request"]["requestId"]
        for _ in range(60):
            time.sleep(1)
            state = call("/process-groups/%s/variable-registry/update-requests/%s"
                         % (group_id, request_id))
            if state["request"]["complete"]:
                failure = state["request"].get("failureReason")
                if failure:
                    raise SystemExit("variable %s failed: %s" % (name, failure))
                break
        else:
            raise SystemExit("variable %s did not apply" % name)


def set_parameters(context_id, values):
    """Fill in the parameter context, and wait for NiFi to apply it.

    Retried as a whole, not through call(): the update is asynchronous, so a
    cluster that is settling reports it inside a perfectly good HTTP 200 --
    failureReason "Cluster is unable to service request to change flow: Node
    nifi:8080 is currently connecting". An HTTP-level retry never sees it.
    """
    for attempt in range(1, RETRIES + 1):
        failure = _set_parameters_once(context_id, values)
        if failure is None:
            return
        if CLUSTER_SETTLING not in failure:
            raise SystemExit("parameter update failed: %s" % failure)
        print("    attempt %d: cluster still settling, retrying parameters" % attempt)
        time.sleep(RETRY_WAIT)
    raise SystemExit("the parameter update never completed: cluster kept settling")


def _set_parameters_once(context_id, values):
    """Returns None on success, or the failure reason NiFi reported."""
    context = call("/parameter-contexts/%s" % context_id)
    request = call("/parameter-contexts/%s/update-requests" % context_id, method="POST", body={
        "revision": context["revision"],
        "component": {
            "id": context_id,
            "name": context["component"]["name"],
            "parameters": [
                {"parameter": {"name": name, "sensitive": sensitive, "value": value}}
                for name, value, sensitive in values
            ],
        },
    })
    request_id = request["request"]["requestId"]
    for _ in range(60):
        time.sleep(2)
        state = call("/parameter-contexts/%s/update-requests/%s" % (context_id, request_id))
        if state["request"]["complete"]:
            return state["request"].get("failureReason")
    raise SystemExit("parameter update did not complete")


def processors_under(group_id):
    found = []
    stack = [group_id]
    while stack:
        flow = call("/flow/process-groups/%s" % stack.pop())["processGroupFlow"]["flow"]
        found.extend(flow.get("processors", []))
        stack.extend(child["id"] for child in flow.get("processGroups", []))
    return found


def port_states(group_id):
    """Every input and output port in the tree, with its state."""
    found = []
    stack = [group_id]
    while stack:
        flow = call("/flow/process-groups/%s" % stack.pop())["processGroupFlow"]["flow"]
        for kind in ("inputPorts", "outputPorts"):
            for port in flow.get(kind, []):
                found.append((port["component"]["name"], port["component"]["state"]))
        stack.extend(child["id"] for child in flow.get("processGroups", []))
    return found


def main():
    global _PORT
    ports = instance_ports()
    for index, port in enumerate(ports, 1):
        _PORT = port
        if len(ports) > 1:
            print("    instance %d of %d, on port %s" % (index, len(ports), port))
        provision_one()
    return 0


def provision_one():
    # One flow artefact per NiFi line: 2.x removed templates and the variable
    # registry, so the 1.x file is not merely older, it is configured through
    # a different mechanism.
    major = env("NIFI_VERSION", "2.11.0").split(".")[0]
    line = "nifi-1.x" if major == "1" else "nifi-2.x"
    flow_file = os.path.join(REPO, "flow_definition", line, "NiFiMonitoring.json")
    if not os.path.isfile(flow_file):
        raise SystemExit("missing %s" % flow_file)

    root = call("/flow/process-groups/root")["processGroupFlow"]["id"]
    group = upload_flow(root, flow_file)
    group_id = group["id"]
    print("    imported the %s flow as process group %s" % (line, group_id))

    copies = imported_groups(root)
    if len(copies) != 1:
        raise SystemExit(
            "%d copies of %s under root after one import: %s"
            % (len(copies), GROUP_NAME,
               ", ".join(c["component"]["name"] for c in copies)))

    if major == "1":
        set_variables(group_id, [
            ("splunk_hec", "http://splunk:8088"),
            ("splunk_hec_token", env("SPLUNK_HEC_TOKEN", "")),
            ("nifi_api_url", "http://localhost:8080/nifi-api"),
            ("nifi_path", "/opt/nifi/nifi-current/"),
            ("processors_list", ""),
            ("process_groups_list", ""),
        ])
        print("    variable registry filled in")
        finish(group_id)
        return

    context_id = call("/process-groups/%s" % group_id)["component"]["parameterContext"]["id"]
    # Inside the compose network Splunk answers on its service name, and the
    # flow reaches its own API over plain HTTP because this profile runs NiFi
    # unauthenticated -- which is what the push path requires.
    set_parameters(context_id, [
        ("splunk_hec", "http://splunk:8088", False),
        ("splunk_hec_token", env("SPLUNK_HEC_TOKEN", ""), True),
        # localhost only works on a single node. A clustered node binds to
        # its own name so the others can reach it, so nothing answers on the
        # loopback -- and the flow runs on whichever node is primary, which is
        # not knowable in advance. The service name resolves from any node,
        # and any node's API answers cluster-wide anyway.
        ("nifi_api_url",
         "http://nifi:8080/nifi-api" if env("CLUSTER", "0") == "1"
         else "http://localhost:8080/nifi-api", False),
        ("processors_list", "", False),
        ("process_groups_list", "", False),
    ])
    print("    parameter context filled in")
    finish(group_id)


def finish(group_id):
    processors = processors_under(group_id)
    invalid = [p for p in processors if p["component"]["validationStatus"] != "VALID"]
    print("    %d processors, %d valid" % (len(processors), len(processors) - len(invalid)))

    # The two GenerateFlowFile processors stay invalid while processors_list
    # and process_groups_list are empty, which is by design: this profile
    # exercises the API and log branches, which do not depend on them.
    for processor in invalid:
        print("      not started (%s): %s"
              % (processor["component"]["validationStatus"], processor["component"]["name"]))

    # Start the group, not the processors one by one. Input and output ports
    # and funnels carry their own state, and starting only processors leaves
    # the ports stopped: FlowFiles then pile up on an output port with nothing
    # draining it, no bulletin is raised, and Send2Splunk-HEC sits at zero
    # bytes while looking perfectly healthy.
    call("/flow/process-groups/%s" % group_id, method="PUT", body={
        "id": group_id, "state": "RUNNING", "disconnectedNodeAcknowledged": False})

    time.sleep(15)
    running = sum(1 for p in processors_under(group_id)
                  if p["component"]["state"] == "RUNNING")
    ports = port_states(group_id)
    print("    %d processors running, ports: %s"
          % (running, ", ".join("%s=%s" % item for item in sorted(ports))))

    # The symptom rather than the cause, kept because it is the thing anyone
    # actually sees: NiFi renames what collides instead of refusing, so a
    # second import shows up here as "Copy of bulletin_report" and nowhere
    # else. The connections still point at the original names, so the flow
    # looks healthy and sends nothing.
    renamed = sorted(name for name, _ in ports if name.startswith("Copy of"))
    if renamed:
        raise SystemExit(
            "NiFi renamed %d port(s), which means the flow was imported more "
            "than once: %s" % (len(renamed), ", ".join(renamed)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
