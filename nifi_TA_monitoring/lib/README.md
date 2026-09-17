# Vendored libraries

Third-party code the add-on ships so it does not depend on what a particular
Splunk release happens to bundle. `bin/nifi.py` puts this directory on
`sys.path` at import time.

## splunklib

The Splunk SDK for Python, 2.1.1.

**`results.py` is deliberately removed** (defect B-24). Upstream, that module
imports `deprecation`, a third-party package that the SDK does not vendor
alongside it, so `import splunklib.results` raised `ModuleNotFoundError` —
a trap for whoever next needed to read search results. Vendoring `deprecation`
would have meant vendoring `packaging` too, for a module nothing in this
add-on imports.

Nothing else in the SDK imports it: the references in `client.py` are all
docstring examples. A unit test asserts the package still imports cleanly and
that the module stays out.

If a future change does need to read search results, vendor `deprecation` and
`packaging` and restore `results.py` from upstream rather than patching it.
