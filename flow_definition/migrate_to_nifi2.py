#!/usr/bin/env python3
"""Rewrite the NiFi 1.x monitoring flow for NiFi 2.x.

    python3 migrate_to_nifi2.py nifi-1.x/NiFiMonitoring.json nifi-2.x/NiFiMonitoring.json

The transformation is a script rather than a hand edit because the flow
definition is 6000+ lines of generated JSON: a script is reviewable, and it
can be re-run if the 1.x flow changes.

What it changes, and why each one is needed -- every item below was
established by importing the 1.x flow into a real NiFi 2.11.0 and reading
back the validation state, not from the migration guide:

1. GetHTTP was removed in 2.0. Three of them become InvokeHTTP with the
   2.x property names.

2. JoltTransformJSON was *relocated*: org.apache.nifi.processors.standard
   -> org.apache.nifi.processors.jolt, and its bundle from
   nifi-standard-nar to nifi-jolt-nar. The processor still exists, which is
   why a "does this file still exist" check misses it, but a flow naming the
   old type imports as INVALID.

3. The Variable Registry is gone. This is the dangerous one: the six
   variables simply vanish, no component reports an error, and a processor
   like Send2Splunk-HEC imports as VALID holding `${splunk_hec}` -- a
   reference that now resolves to nothing. It fails at runtime with no
   warning at import time. They become a Parameter Context, and every
   `${var}` reference becomes `#{var}`.

What it deliberately does not change: InvokeHTTP's property names. NiFi 2.x
migrates those itself on import (Remote URL -> HTTP URL, with the value
intact), verified against 2.11.0.
"""

import json
import re
import sys
from collections import OrderedDict

PARAMETER_CONTEXT_NAME = "NiFi Monitoring"

# Processors whose type moved between NARs. The processor is still there; only
# its coordinates changed, so the flow has to name the new ones.
RELOCATED = {
    "org.apache.nifi.processors.standard.JoltTransformJSON": {
        "type": "org.apache.nifi.processors.jolt.JoltTransformJSON",
        "bundle": {"group": "org.apache.nifi", "artifact": "nifi-jolt-nar"},
        # The relocated processor also renamed its properties, so moving the
        # type alone leaves it invalid.
        "properties": {
            "jolt-spec": "Jolt Specification",
            "jolt-transform": "Jolt Transform",
            "pretty_print": "Pretty Print",
            "jolt-custom-class": "Custom Transformation Class Name",
            "jolt-custom-modules": "Custom Module Directory",
            "Transform Cache Size": "Transform Cache Size",
        },
    },
}

# GetHTTP property -> InvokeHTTP (2.x) property. Anything not listed is
# dropped, either because it has no equivalent or because the 2.x default is
# the right one.
GETHTTP_TO_INVOKEHTTP = {
    "URL": "HTTP URL",
    "Connection Timeout": "Connection Timeout",
    "Data Timeout": "Socket Read Timeout",
    "User Agent": "Request User-Agent",
    "Follow Redirects": "Response Redirects Enabled",
}

INVOKEHTTP_TYPE = "org.apache.nifi.processors.standard.InvokeHTTP"


def walk_groups(group):
    """Yield every process group in the tree, outermost first."""
    yield group
    for child in group.get("processGroups") or []:
        yield from walk_groups(child.get("flowContents", child))


def convert_gethttp(processor, report):
    config = processor.setdefault("properties", processor.get("config", {}).get("properties", {}))
    source = dict(config)

    converted = {}
    for old, new in GETHTTP_TO_INVOKEHTTP.items():
        value = source.get(old)
        if value in (None, ""):
            continue
        # InvokeHTTP's allowable values are 'True'/'False'; GetHTTP wrote
        # lowercase, which 2.x rejects as outside the allowed set.
        if str(value).lower() in ("true", "false"):
            value = str(value).capitalize()
        converted[new] = value
    converted["HTTP Method"] = "GET"
    # GetHTTP produced a FlowFile named by its Filename property; InvokeHTTP
    # names the response FlowFile by strategy instead.
    converted["Response FlowFile Naming Strategy"] = "RANDOM"

    processor["type"] = INVOKEHTTP_TYPE
    processor["bundle"] = {"group": "org.apache.nifi", "artifact": "nifi-standard-nar"}
    if "properties" in processor:
        processor["properties"] = converted
    if "config" in processor and isinstance(processor["config"], dict):
        processor["config"]["properties"] = converted

    # GetHTTP had one 'success' relationship; InvokeHTTP has five, and the
    # ones the flow does not route have to be auto-terminated or the
    # processor is invalid.
    terminate = ["Original", "Failure", "Retry", "No Retry"]
    for holder in (processor, processor.get("config")):
        if isinstance(holder, dict) and "autoTerminatedRelationships" in holder:
            existing = holder.get("autoTerminatedRelationships") or []
            holder["autoTerminatedRelationships"] = sorted(set(existing) | set(terminate))

    report.append("GetHTTP -> InvokeHTTP: %s" % processor.get("name"))
    return processor.get("identifier")


def relocate(processor, report):
    move = RELOCATED.get(processor.get("type"))
    if not move:
        return
    report.append("relocated %s: %s -> %s"
                  % (processor.get("name"), processor["type"], move["type"]))
    processor["type"] = move["type"]
    processor["bundle"] = dict(move["bundle"], version=processor.get("bundle", {}).get("version", ""))

    renames = move.get("properties") or {}
    if not renames:
        return
    for holder in (processor, processor.get("config")):
        if not isinstance(holder, dict) or "properties" not in holder:
            continue
        old = holder["properties"] or {}
        holder["properties"] = {
            renames.get(key, key): value
            for key, value in old.items()
            if key in renames or key not in ("Transform Cache Size",)
        }


def mark_sensitive_headers(root, report, sensitive_names):
    """Declare dynamic properties that hold a credential as sensitive.

    A non-sensitive property cannot reference a sensitive parameter -- NiFi
    rejects it outright. InvokeHTTP's dynamic properties become request
    headers, so the Authorization header carrying the HEC token has to be
    declared sensitive for the reference to be legal, and that also keeps the
    value out of an exported flow definition.
    """
    for group in walk_groups(root):
        for processor in group.get("processors") or []:
            props = (processor.get("properties")
                     or processor.get("config", {}).get("properties", {}) or {})
            for name, value in props.items():
                if not isinstance(value, str):
                    continue
                if not any("#{%s}" % s in value for s in sensitive_names):
                    continue
                descriptors = processor.setdefault("propertyDescriptors", {})
                if name in descriptors and descriptors[name].get("sensitive"):
                    continue
                descriptors[name] = {
                    "name": name, "displayName": name,
                    "identifiesControllerService": False,
                    "sensitive": True, "dynamic": True,
                }
                report.append("declared %r on %s as a sensitive dynamic property"
                              % (name, processor.get("name")))


def variables_to_parameters(root, report):
    """Turn the root group's variables into a Parameter Context."""
    variables = root.get("variables") or {}
    if not variables:
        return None, set()

    # Anything that looks like a credential is marked sensitive, so NiFi does
    # not write it into an exported flow definition. That is also what keeps a
    # token from being committed again.
    sensitive = re.compile(r"token|password|secret|credential", re.I)

    # NiFi shows a parameter's description in the UI, so this is where an
    # operator finds out what to put in each box. Defaults point at the local
    # test stack from tests/, which is a working example rather than a
    # placeholder to decode.
    DESCRIPTIONS = {
        "splunk_hec": "Splunk HEC endpoint, e.g. http://splunk:8088 "
                      "(the hostname the test compose uses).",
        "splunk_hec_token": "HEC token from Splunk. Sensitive: NiFi keeps it out "
                            "of an exported flow.",
        "nifi_api_url": "This NiFi's REST API, e.g. http://localhost:8080/nifi-api",
        "nifi_path": "NiFi's install directory, used to tail its logs. The "
                     "official container uses /opt/nifi/nifi-current/",
        "processors_list": "REQUIRED. Ids of the processors to monitor, one per "
                           "line. Empty by design, so no installation ships "
                           "another one's component ids.",
        "process_groups_list": "REQUIRED. Ids of the process groups to monitor, "
                               "one per line. Empty by design.",
    }

    parameters = []
    for name in sorted(variables):
        entry = {"name": name, "description": DESCRIPTIONS.get(name, ""),
                 "sensitive": bool(sensitive.search(name)), "provided": False}
        if not entry["sensitive"]:
            entry["value"] = variables[name]
        parameters.append(entry)

    report.append("variables -> parameter context %r (%d parameters, %d sensitive)"
                  % (PARAMETER_CONTEXT_NAME, len(parameters),
                     sum(1 for p in parameters if p["sensitive"])))
    return {
        PARAMETER_CONTEXT_NAME: {
            "name": PARAMETER_CONTEXT_NAME,
            "parameters": parameters,
            "inheritedParameterContexts": [],
            "description": "Settings for the NiFi Monitoring flow. Replaces the "
                           "variables the 1.x flow used; the Variable Registry "
                           "was removed in NiFi 2.0.",
            "componentType": "PARAMETER_CONTEXT",
        }
    }, set(variables)


def rewrite_references(node, names, report, seen):
    """Rewrite ${var} to #{var} for every migrated variable, everywhere."""
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = rewrite_references(value, names, report, seen)
        return node
    if isinstance(node, list):
        return [rewrite_references(item, names, report, seen) for item in node]
    if isinstance(node, str):
        result = node
        for name in names:
            token = "${%s}" % name
            if token in result:
                result = result.replace(token, "#{%s}" % name)
                seen.add(name)
        return result
    return node


def main(argv):
    if len(argv) != 2:
        raise SystemExit(__doc__.strip().splitlines()[2].strip())

    source, destination = argv
    with open(source) as handle:
        flow = json.load(handle, object_pairs_hook=OrderedDict)

    report = []
    root = flow["flowContents"]

    contexts, variable_names = variables_to_parameters(root, report)
    if contexts:
        flow["parameterContexts"] = contexts
        # A child process group does not inherit the parent's parameter
        # context: without its own, every parameter reference inside it is
        # invalid. Verified on 2.11.0 -- setting it only on the root left the
        # processors in every subgroup broken.
        for group in walk_groups(root):
            group["parameterContextName"] = PARAMETER_CONTEXT_NAME
            group.pop("variables", None)

    converted_ids = set()
    for group in walk_groups(root):
        for processor in group.get("processors") or []:
            if processor.get("type", "").endswith(".GetHTTP"):
                identifier = convert_gethttp(processor, report)
                if identifier:
                    converted_ids.add(identifier)
            relocate(processor, report)

    # GetHTTP emitted 'success'; InvokeHTTP emits 'Response'. A connection
    # still naming the old relationship leaves the processor invalid.
    for group in walk_groups(root):
        for connection in group.get("connections") or []:
            source = (connection.get("source") or {}).get("id")
            if source in converted_ids:
                names = connection.get("selectedRelationships") or []
                if "success" in names:
                    connection["selectedRelationships"] = [
                        "Response" if n == "success" else n for n in names
                    ]
                    report.append("connection out of %s: success -> Response"
                                  % (connection.get("source") or {}).get("name", source))

    sensitive_names = set()
    if contexts:
        sensitive_names = {
            p["name"] for p in contexts[PARAMETER_CONTEXT_NAME]["parameters"]
            if p.get("sensitive")
        }

    rewritten = set()
    if variable_names:
        flow["flowContents"] = rewrite_references(root, variable_names, report, rewritten)
        report.append("rewrote ${...} -> #{...} for: %s" % ", ".join(sorted(rewritten)))
        unused = variable_names - rewritten
        if unused:
            report.append("NOTE: no reference found for: %s" % ", ".join(sorted(unused)))

    if sensitive_names:
        mark_sensitive_headers(flow["flowContents"], report, sensitive_names)

    with open(destination, "w") as handle:
        json.dump(flow, handle, indent=2)
        handle.write("\n")

    print("wrote %s" % destination)
    for line in report:
        print("  " + line)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
