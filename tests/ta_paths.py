"""Where the add-on lives, now that part of it is generated.

Since the UCC migration the add-on has two forms and they are not
interchangeable:

* `TA_SOURCE` -- `nifi_TA_monitoring/package/`, what is versioned. Holds
  bin/, props.conf and transforms.conf, byte for byte what ships.
* `TA_BUILT` -- `output/nifi_TA_monitoring/`, what `ucc-gen build` produces
  and what Splunk actually installs. Holds everything in the source *plus*
  app.conf, inputs.conf, the spec, restmap.conf, default.meta and the whole
  UI, none of which exist until the build runs.

A check about a generated file has to read the built form, or it is checking
something nobody ships -- that is condition UI-3 of the plan. A check about
handwritten code can read either, and reads the source so that
`python3 -m unittest discover` still works with nothing installed.

`REQUIRE_BUILT_TA=1` turns a missing build from a skip into a failure. CI
sets it, because there the build always ran and a silent skip would mean the
generated half of the add-on is never checked at all.
"""

import os

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(TESTS_DIR)

TA_SOURCE = os.path.join(REPO, "nifi_TA_monitoring", "package")
TA_BUILT = os.path.join(REPO, "output", "nifi_TA_monitoring")
APP = os.path.join(REPO, "nifi_monitoring")

BUILD_HINT = (
    "the built add-on is not in output/. Run tests/build-ta.sh (or "
    "`ucc-gen build --source nifi_TA_monitoring/package "
    "--config nifi_TA_monitoring/globalConfig.json --output output`) first."
)


def built_available():
    return os.path.isdir(TA_BUILT)


def require_built():
    """Return None when the built add-on is usable, or a skip reason."""
    if built_available():
        return None
    if os.environ.get("REQUIRE_BUILT_TA") == "1":
        raise AssertionError(BUILD_HINT)
    return BUILD_HINT
