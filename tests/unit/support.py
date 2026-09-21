"""Test harness for the TA's modular input.

bin/nifi.py is a Splunk modular input: importing it pulls in `requests`,
`urllib3` and `splunklib.client`, none of which is available (or wanted) in a
unit test, so the imports are stubbed before the module is loaded.

The JWT used to live in a .env file, which is why this harness once stubbed
`dotenv` and drove the token through os.environ. It now lives in
storage/passwords (defect B-14), so the token is injected by setting the
script's cache instead.

Uses only the standard library so the suite runs anywhere, including inside
the kudaw/appinspect container used by CI.
"""

import os
import sys
import unittest
import unittest.mock as mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from ta_paths import TA_BUILT, TA_SOURCE, built_available, require_built  # noqa: E402

# bin/ and lib/ come from different places now. bin/nifi.py is handwritten and
# versioned under package/; lib/ only exists once ucc-gen has installed the
# requirements into output/. Importing the source file against the built lib
# is deliberate: it is the combination that ships, and it keeps the suite
# runnable from a clean checkout for everything that does not need lib/.
TA_DIR = TA_SOURCE


def load_nifi_module():
    """Import nifi_TA_monitoring/bin/nifi.py with its runtime deps stubbed.

    Returns (module, stubs) where stubs holds the mock for `requests` so tests
    can drive and inspect it.
    """
    # splunklib is no longer versioned: ucc-gen installs it into the built
    # add-on's lib/. Without a build there is nothing to import against, and
    # the failure would otherwise arrive as thirty ImportErrors from
    # setUpClass rather than as one sentence saying to run the build.
    reason = require_built()
    if reason:
        raise unittest.SkipTest(reason)

    for path in (os.path.join(TA_BUILT, "lib"), os.path.join(TA_DIR, "bin")):
        if path not in sys.path:
            sys.path.insert(0, path)

    stub_requests = mock.MagicMock()
    stub_urllib3 = mock.MagicMock()
    stub_urllib3.exceptions.InsecureRequestWarning = Warning
    stubs = {
        "requests": stub_requests,
        "urllib3": stub_urllib3,
        "splunklib.client": mock.MagicMock(),
        # ucc-gen generates this into the built add-on's bin/. It rewrites
        # sys.path for the real runtime; here sys.path is already whatever the
        # test needs, and importing it would undo that.
        "import_declare_test": mock.MagicMock(),
    }
    with mock.patch.dict(sys.modules, stubs):
        if "nifi" in sys.modules:
            del sys.modules["nifi"]
        import nifi

    return nifi, {"requests": stub_requests}


def response(status_code, text="body"):
    """A minimal stand-in for a requests.Response."""
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.reason = "reason"
    resp.elapsed.total_seconds.return_value = 0.1
    return resp


class NiFiScriptTestCase(unittest.TestCase):
    """Base case: a NiFiScript with the network and Splunk calls stubbed."""

    @classmethod
    def setUpClass(cls):
        cls.nifi, cls.stubs = load_nifi_module()

    def setUp(self):
        self.http = self.stubs["requests"]
        self.http.reset_mock(return_value=True, side_effect=True)
        self.script = self.nifi.NiFiScript()
        self.event_writer = mock.MagicMock()
        self._password_patcher = mock.patch.object(
            self.nifi.NiFiScript, "_NiFiScript__get_password", return_value="pw"
        )
        self._password_patcher.start()
        self.addCleanup(self._stop_password_patcher)

    def _stop_password_patcher(self):
        if self._password_patcher is not None:
            self._password_patcher.stop()
            self._password_patcher = None

    def use_real_get_password(self):
        """Un-stub __get_password, for tests that exercise it directly."""
        self._stop_password_patcher()

    def get_request(self, stored_token, input_name="instance", auth_type="basic"):
        """Call the private __get_request with `stored_token` already stored.

        The token now comes from storage/passwords rather than a .env, so it is
        seeded through the process cache and the write is captured instead of
        hitting Splunk.
        """
        self.script.token_cache = stored_token
        self.stored_tokens = []
        with mock.patch.object(
            self.nifi.NiFiScript, "_NiFiScript__write_token",
            side_effect=lambda ew, key, name, token: (
                self.stored_tokens.append(token),
                setattr(self.script, "token_cache", token),
            ),
        ):
            return self.script._NiFiScript__get_request(
                self.event_writer,
                "http://nifi:8080/nifi-api",
                "/flow/status",
                auth_type,
                "user",
                input_name,
                "session-key",
            )

    def sent_tokens(self):
        """The bearer token of every GET the code issued, in order."""
        return [
            call.kwargs["headers"]["Authorization"]
            for call in self.http.get.call_args_list
        ]
