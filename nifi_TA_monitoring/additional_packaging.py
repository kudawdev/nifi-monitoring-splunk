"""Post-build touch-ups ucc-gen has no hook for.

Two of them, both about `default/inputs.conf`:

1. ucc-gen owns that file -- it writes the [nifi] stanza with every default
   declared in globalConfig.json -- and a file of ours in package/default/
   would replace it rather than merge, so the defaults would vanish and an
   input that omitted verify_tls would stop verifying. The file monitors have
   to be appended after the fact instead. They are in appended/inputs.conf.

2. Splunk reads two keys for the interpreter and they are read by different
   audiences. `python.version` is what Splunk 8.2-9.1 understands, and
   ucc-gen writes it. `python.required` is the newer one AppInspect checks,
   it only accepts "3.9" or "3.13" -- "python3" is rejected outright -- and
   ucc-gen does not write it at all. Without it the precert gate fails.

The same second point applies to restmap.conf, where ucc-gen declares three
python REST handlers and gives none of them `python.required`. AppInspect
reports that as a future_failure today, and slim warns about it now.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON_REQUIRED = "3.13"


def _built_app(ta_name):
    """Where ucc-gen left the built add-on.

    It hands us only the name, so the output directory has to be guessed. The
    default is `output/`, which is what this repo and ucc-gen both use.
    """
    for candidate in (os.path.join("output", ta_name), ta_name):
        if os.path.isdir(candidate):
            return candidate
    raise RuntimeError(
        "cannot find the built add-on for %r; looked in output/ and ./" % ta_name)


def _add_python_required(path, stanza_prefix):
    """Put python.required under every stanza whose name starts with prefix."""
    with open(path) as handle:
        lines = handle.read().rstrip("\n").split("\n")

    out, touched = [], 0
    for line in lines:
        out.append(line)
        if line.strip().startswith(stanza_prefix) and line.strip().endswith("]"):
            out.append("python.required = %s" % PYTHON_REQUIRED)
            touched += 1

    with open(path, "w") as handle:
        handle.write("\n".join(out) + "\n")
    return touched


def additional_packaging(ta_name):
    built = _built_app(ta_name)

    restmap = os.path.join(built, "default", "restmap.conf")
    if os.path.isfile(restmap):
        handlers = _add_python_required(restmap, "[admin_external:")
        print("additional_packaging: python.required on %d REST handlers" % handlers)

    inputs_conf = os.path.join(built, "default", "inputs.conf")
    with open(inputs_conf) as handle:
        generated = handle.read()

    if "[nifi]" not in generated:
        raise RuntimeError(
            "ucc-gen did not generate the [nifi] stanza; appending the "
            "monitors to this file would ship an add-on with no input "
            "defaults at all")

    lines = []
    for line in generated.rstrip("\n").split("\n"):
        lines.append(line)
        if line.strip() == "[nifi]":
            lines.append("python.required = %s" % PYTHON_REQUIRED)

    with open(os.path.join(HERE, "appended", "inputs.conf")) as handle:
        appended = handle.read()

    with open(inputs_conf, "w") as handle:
        handle.write("\n".join(lines) + "\n\n" + appended.lstrip("\n"))

    print("additional_packaging: added python.required and the file monitors")
