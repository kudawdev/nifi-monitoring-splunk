#!/usr/bin/env python3
"""Read matrix.yml and emit the .env for one profile.

    python3 matrix.py nifi2-current      # print the .env
    python3 matrix.py --ci pull_request  # print the profile names CI runs

PyYAML is used when available. The CI container's dependencies are not
guaranteed, so there is a fallback parser for the small subset of YAML this
file uses (two-space nesting, `key: value`, `- item` lists, and `>` folded
blocks for the descriptions).
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MATRIX = os.path.join(HERE, "matrix.yml")

# Host ports. Fixed rather than random so the URLs in README stay true and a
# developer can point a browser at a running stack.
PORTS = {
    "SPLUNK_WEB_PORT": "38000",
    "SPLUNK_MGMT_PORT": "38089",
    "SPLUNK_HEC_PORT": "38088",
    "NIFI_HTTP_PORT": "38080",
    "NIFI_HTTPS_PORT": "38443",
    "NIFI_B_HTTPS_PORT": "38444",
    "NIFI_B_HTTP_PORT": "38081",
}

SPLUNK_PASSWORD = "Password123"
SPLUNK_HEC_TOKEN = "00000000-0000-0000-0000-0000000000ab"


# PyYAML resolves these to booleans (YAML 1.1) and plain digits to ints, and
# the fallback parser has to agree: `forwarder: false` would otherwise come
# back as the non-empty -- and therefore truthy -- string "false", and
# `instances: 2` as a string where the caller expects a number. Floats are
# deliberately left alone, because matrix.yml quotes every version;
# test_matrix.ParserParityTest fails if that ever stops being true.
_TRUE = ("true", "True", "TRUE", "yes", "Yes", "YES", "on", "On", "ON")
_FALSE = ("false", "False", "FALSE", "no", "No", "NO", "off", "Off", "OFF")
_NULL = ("null", "Null", "NULL", "~")
_INT = re.compile(r"^[-+]?[0-9]+$")


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    if value in _NULL:
        return None
    if _INT.match(value):
        return int(value)
    return value


def _parse_minimal_yaml(text):
    """Parse the subset of YAML used by matrix.yml.

    Supports nested mappings by indentation, `- item` sequences and `>`
    folded scalars. Deliberately not a general YAML parser: it exists only so
    the harness does not depend on PyYAML being present in the CI container,
    and test_matrix.py asserts it agrees with PyYAML on the real file.
    """
    lines = []
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        lines.append((len(raw) - len(raw.lstrip()), stripped))

    position = [0]

    def parse_block(min_indent):
        _, first = lines[position[0]]
        if first.startswith("- "):
            items = []
            while position[0] < len(lines):
                indent, content = lines[position[0]]
                if indent < min_indent or not content.startswith("- "):
                    break
                items.append(_unquote(content[2:].strip()))
                position[0] += 1
            return items

        mapping = {}
        while position[0] < len(lines):
            indent, content = lines[position[0]]
            if indent < min_indent:
                break
            if ":" not in content:
                raise ValueError("cannot parse line: %r" % content)
            key, _, value = content.partition(":")
            key, value = key.strip(), value.strip()
            position[0] += 1

            if value in (">", "|", ">-", "|-"):
                folded = []
                while position[0] < len(lines) and lines[position[0]][0] > indent:
                    folded.append(lines[position[0]][1])
                    position[0] += 1
                joined = " ".join(folded)
                # `>` and `|` keep a trailing newline; the stripping forms
                # (`>-`, `|-`) do not. Match PyYAML so the parity test can
                # compare the two readers exactly.
                mapping[key] = joined if value.endswith("-") else joined + "\n"
            elif value == "":
                if position[0] < len(lines) and lines[position[0]][0] > indent:
                    mapping[key] = parse_block(lines[position[0]][0])
                else:
                    mapping[key] = None
            else:
                mapping[key] = _unquote(value)
        return mapping

    return parse_block(0) if lines else {}


def load():
    text = open(MATRIX).read()
    try:
        import yaml
        return yaml.safe_load(text)
    except ImportError:
        return _parse_minimal_yaml(text)


def env_for(profile_name):
    data = load()
    profiles = data["profiles"]
    if profile_name not in profiles:
        raise SystemExit(
            "unknown profile '%s'; known: %s"
            % (profile_name, ", ".join(sorted(profiles)))
        )
    profile = profiles[profile_name]
    auth = profile["nifi_auth"]
    instances = int(profile.get("instances", 1))

    compose_profiles = []
    forwarder = profile.get("forwarder")
    # A second forwarder wherever there is a second NiFi: the agent belongs on
    # the machine whose files it reads, so two NiFis mean two of them.
    second_nifi = instances > 1 or bool(profile.get("cluster"))
    if forwarder:
        compose_profiles.append("forwarder")
        if second_nifi:
            compose_profiles.append("forwarder2")
    if instances > 1:
        compose_profiles.append("multi")
    if profile.get("tls_verify"):
        compose_profiles.append("tlsverify")
    if profile.get("cluster"):
        compose_profiles.append("cluster")

    lines = [
        "# Generated by matrix.py from matrix.yml -- do not edit by hand.",
        "PROFILE=%s" % profile_name,
        "NIFI_VERSION=%s" % profile["nifi_version"],
        "SPLUNK_VERSION=%s" % profile["splunk_version"],
        "NIFI_AUTH=%s" % auth,
        "NIFI_ENV_FILE=./env/nifi-%s.env" % auth,
        # 'pull' (the TA's modular input) or 'hec' (the flow inside NiFi).
        "COLLECTION=%s" % profile.get("collection", "pull"),
        # Whether a Universal Forwarder ships NiFi's logs. Compose reads
        # COMPOSE_PROFILES from .env by itself, so run.sh needs no flag.
        "FORWARDER=%s" % ("1" if forwarder else "0"),
        "FORWARDER2=%s" % ("1" if forwarder and second_nifi else "0"),
        "UF_HOST=%s" % ("nifi"),
        # In a cluster both forwarders stamp the cluster as the host and say
        # which node in a `node` field (decision C-1); with two independent
        # instances the second one is its own host.
        "UF2_HOST=%s" % ("nifi" if profile.get("cluster") else "nifi-b"),
        "UF2_NODE=%s" % ("nifi-node2" if profile.get("cluster") else ""),
        "UF2_LOG_VOLUME=%s" % ("nifi_node2_logs" if profile.get("cluster") else "nifi_b_logs"),
        # How many independent NiFi instances the profile brings up. Anything
        # above one adds the `multi` compose profile and a second input.
        "INSTANCES=%s" % instances,
        # Whether the add-on verifies NiFi's certificate against the exported
        # bundle. Off means verify_tls = 0, which is what every profile did
        # before R-8.
        "TLS_VERIFY=%s" % ("1" if profile.get("tls_verify") else "0"),
        # Whether the NiFi under test is a cluster. Brings up ZooKeeper and a
        # second node of the SAME NiFi -- not a second instance.
        "CLUSTER=%s" % ("1" if profile.get("cluster") else "0"),
        "NIFI_CLUSTER_IS_NODE=%s" % ("true" if profile.get("cluster") else "false"),
        "NIFI_B_VERSION=%s" % profile.get("nifi_b_version", ""),
        # The second instance follows the first's auth mode: a push profile
        # needs both unsecured, because the flow calls its own API with no
        # credentials.
        "NIFI_B_ENV_FILE=./env/nifi-%s-b.env" % ("none2x" if auth == "none2x" else "singleuser"),
        "COMPOSE_PROFILES=%s" % ",".join(compose_profiles),
        # The unsecured 2.x profile cannot use the image's entrypoint.
        "NIFI_ENTRYPOINT=%s" % ("/opt/nifi/harness/start-unsecured.sh"
                                if auth == "none2x" else "../scripts/start.sh"),
        "SPLUNK_PASSWORD=%s" % SPLUNK_PASSWORD,
        "SPLUNK_HEC_TOKEN=%s" % SPLUNK_HEC_TOKEN,
    ]
    lines += ["%s=%s" % item for item in sorted(PORTS.items())]
    return "\n".join(lines) + "\n"


def topology(profile_name):
    """The long-lived containers a profile brings up, in start order.

    Derived from the same fields env_for() turns into COMPOSE_PROFILES, so the
    two cannot disagree about what runs. The transient seed containers are
    left out: they copy files and exit before splunkd is listening, and
    listing them alongside the machines suggests they are part of the
    environment.
    """
    profile = load()["profiles"][profile_name]
    instances = int(profile.get("instances", 1))
    clustered = bool(profile.get("cluster"))

    containers = ["splunk", "nifi"]
    if clustered:
        containers += ["nifi-node2", "zookeeper"]
    if instances > 1:
        containers.append("nifi-b")
    if profile.get("forwarder"):
        containers.append("forwarder")
        if instances > 1 or clustered:
            containers.append("forwarder2")
    return containers


def strategy(profile_name):
    """How data leaves NiFi in this profile: the axis matrix.yml calls
    `collection`, spelled the way section 8.4 of the plan names it."""
    profile = load()["profiles"][profile_name]
    if profile.get("collection") == "hec":
        return "push"
    return "pull"


def describe(profile_name):
    """Everything known about one profile, for `run.sh --list <name>`."""
    data = load()
    profile = data["profiles"][profile_name]
    env = dict(line.split("=", 1) for line in env_for(profile_name).splitlines()
               if "=" in line and not line.startswith("#"))
    instances = int(profile.get("instances", 1))
    clustered = bool(profile.get("cluster"))

    nifi = "%s, auth=%s" % (profile["nifi_version"], profile["nifi_auth"])
    if clustered:
        nifi += ", clustered (2 nodes)"
    elif instances > 1:
        nifi += ", %d independent instances" % instances

    how = ("the flow's InvokeHTTP and TailFile push to the HEC"
           if strategy(profile_name) == "push"
           else "the TA's modular input polls the REST API")
    if profile.get("forwarder"):
        how += "; a Universal Forwarder ships the log files"

    ci = [name for name, names in (data.get("ci") or {}).items()
          if profile_name in names]

    out = [profile_name, ""]
    for line in (profile.get("description") or "").split("\n"):
        if line.strip():
            out.append("  " + line.strip())
    out += [
        "",
        "  NiFi         %s" % nifi,
        "  Splunk       %s" % profile["splunk_version"],
        "  Strategy     %s -- %s" % (strategy(profile_name), how),
        "  Containers   %s" % ", ".join(topology(profile_name)),
        "               plus seed containers that copy files and exit",
        "  Ports        Splunk web %s, mgmt %s, HEC %s; NiFi %s / %s" % (
            env["SPLUNK_WEB_PORT"], env["SPLUNK_MGMT_PORT"],
            env["SPLUNK_HEC_PORT"], env["NIFI_HTTP_PORT"], env["NIFI_HTTPS_PORT"]),
        "  NiFi env     tests/%s" % env["NIFI_ENV_FILE"].lstrip("./"),
        "  CI           %s" % (", ".join(ci) if ci else "not run by CI"),
        "  TLS verify   %s" % ("on, against the exported bundle"
                               if profile.get("tls_verify") else "off"),
    ]
    return "\n".join(out) + "\n"


def main(argv):
    if len(argv) >= 2 and argv[0] == "--ci":
        for name in load()["ci"][argv[1]]:
            print(name)
        return 0
    if argv and argv[0] == "--describe":
        if len(argv) < 2:
            raise SystemExit("usage: matrix.py --describe <profile>")
        sys.stdout.write(describe(argv[1]))
        return 0
    if not argv:
        raise SystemExit("usage: matrix.py <profile> | --ci <pull_request|release>")
    sys.stdout.write(env_for(argv[0]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
