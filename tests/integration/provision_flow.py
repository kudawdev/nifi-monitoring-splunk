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


def base_url():
    return "http://localhost:%s/nifi-api" % env("NIFI_HTTP_PORT", "38080")


def call(path, body=None, method="GET", raw=None, content_type="application/json"):
    headers = {"Accept": "application/json"}
    data = None
    if raw is not None:
        data, headers["Content-Type"] = raw, content_type
    elif body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    request = urllib.request.Request(base_url() + path, data=data,
                                     headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=120, context=_UNVERIFIED) as response:
        text = response.read().decode()
    return json.loads(text) if text else {}


def upload_flow(root, path):
    """Import the flow definition the way the UI's 'import from file' does."""
    boundary = "----nifiharness"
    with open(path, "rb") as handle:
        content = handle.read()

    parts = []
    for name, value in (("groupName", "NiFiMonitoring"), ("positionX", "0"),
                        ("positionY", "0"), ("clientId", "harness"),
                        ("disconnectedNodeAcknowledged", "false")):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                      % (boundary, name, value)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                  "filename=\"NiFiMonitoring.json\"\r\n"
                  "Content-Type: application/json\r\n\r\n" % boundary).encode())
    parts.append(content)
    parts.append(("\r\n--%s--\r\n" % boundary).encode())

    return call("/process-groups/%s/process-groups/upload" % root, method="POST",
                raw=b"".join(parts),
                content_type="multipart/form-data; boundary=%s" % boundary)


def set_parameters(context_id, values):
    """Fill in the parameter context, and wait for NiFi to apply it."""
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
            failure = state["request"].get("failureReason")
            if failure:
                raise SystemExit("parameter update failed: %s" % failure)
            return
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
    flow_file = os.path.join(REPO, "flow_definition", "nifi-2.x", "NiFiMonitoring.json")
    if not os.path.isfile(flow_file):
        raise SystemExit("missing %s" % flow_file)

    root = call("/flow/process-groups/root")["processGroupFlow"]["id"]
    group = upload_flow(root, flow_file)
    group_id = group["id"]
    print("    imported the flow as process group %s" % group_id)

    context_id = call("/process-groups/%s" % group_id)["component"]["parameterContext"]["id"]
    # Inside the compose network Splunk answers on its service name, and the
    # flow reaches its own API over plain HTTP because this profile runs NiFi
    # unauthenticated -- which is what the push path requires.
    set_parameters(context_id, [
        ("splunk_hec", "http://splunk:8088", False),
        ("splunk_hec_token", env("SPLUNK_HEC_TOKEN", ""), True),
        ("nifi_api_url", "http://localhost:8080/nifi-api", False),
        ("processors_list", "", False),
        ("process_groups_list", "", False),
    ])
    print("    parameter context filled in")

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
    return 0


if __name__ == "__main__":
    sys.exit(main())
