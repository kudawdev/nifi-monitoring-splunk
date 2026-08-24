"""Test harness for the TA's modular input.

bin/nifi.py is a Splunk modular input: importing it pulls in `requests`,
`urllib3`, `dotenv` and `splunklib.client`, and its module body touches the
filesystem looking for a .env file. None of that is available (or wanted) in a
unit test, so the imports are stubbed before the module is loaded.

Uses only the standard library so the suite runs anywhere, including inside
the kudaw/appinspect container used by CI.
"""

import os
import sys
import unittest
import unittest.mock as mock

TA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "nifi_TA_monitoring")
)


def load_nifi_module():
    """Import nifi_TA_monitoring/bin/nifi.py with its runtime deps stubbed.

    Returns (module, stubs) where stubs holds the mocks for `requests` and
    `dotenv` so tests can drive and inspect them.
    """
    for path in (os.path.join(TA_DIR, "lib"), os.path.join(TA_DIR, "bin")):
        if path not in sys.path:
            sys.path.insert(0, path)

    stub_requests = mock.MagicMock()
    stub_urllib3 = mock.MagicMock()
    stub_urllib3.exceptions.InsecureRequestWarning = Warning
    stub_dotenv = mock.MagicMock()
    # keep the module body from creating a .env inside the app directory
    stub_dotenv.find_dotenv.return_value = "/tmp/nifi-ta-unittest.env"

    stubs = {
        "requests": stub_requests,
        "urllib3": stub_urllib3,
        "dotenv": stub_dotenv,
        "splunklib.client": mock.MagicMock(),
    }
    with mock.patch.dict(sys.modules, stubs):
        if "nifi" in sys.modules:
            del sys.modules["nifi"]
        import nifi

    return nifi, {"requests": stub_requests, "dotenv": stub_dotenv}


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
        self.dotenv = self.stubs["dotenv"]
        self.http.reset_mock(return_value=True, side_effect=True)
        self.dotenv.reset_mock()
        self.script = self.nifi.NiFiScript()
        self.event_writer = mock.MagicMock()
        patcher = mock.patch.object(
            self.nifi.NiFiScript, "_NiFiScript__get_password", return_value="pw"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def get_request(self, stored_token, input_name="instance", auth_type="basic"):
        """Call the private __get_request with `stored_token` as cached token."""
        with mock.patch.dict("os.environ", {input_name: stored_token}, clear=False):
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
