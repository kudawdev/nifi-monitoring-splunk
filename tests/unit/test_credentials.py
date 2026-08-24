"""Tests for credential handling in bin/nifi.py.

The input logged the full NiFi JWT at INFO level, which put a usable
credential into splunkd.log on every request, and __get_password returned
None without a word when no stored credential matched the username.
"""

import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response

JWT = (
    "eyJraWQiOiJhYjAyM2RhNC1hNTA5LTRjYTAtYTc2ZSJ9."
    "eyJzdWIiOiJhZG1pbiIsImV4cCI6MTc4NzYxMDExNn0.c3ViLXNpZ25hdHVyZQ"
)


class RedactTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.redact = staticmethod(
            load_nifi_module()[0].NiFiScript._NiFiScript__redact
        )

    def test_long_secret_keeps_only_the_last_four_characters(self):
        redacted = self.redact(JWT)
        self.assertNotIn(JWT, redacted)
        self.assertIn(JWT[-4:], redacted)
        self.assertIn(str(len(JWT)), redacted)

    def test_short_secret_is_not_revealed_at_all(self):
        for secret in ("abc", "shortsecret", "a" * 15):
            redacted = self.redact(secret)
            self.assertNotIn(secret, redacted)
            self.assertIn("redacted", redacted)

    def test_missing_secret_is_reported_as_none(self):
        self.assertEqual(self.redact(None), "<none>")
        self.assertEqual(self.redact(""), "<none>")


class TokenLoggingTest(NiFiScriptTestCase):

    def logged_messages(self):
        return [
            str(call.args[2])
            for call in self.event_writer.log.call_args_list
            if len(call.args) > 2
        ] + [
            str(call.args[-1])
            for call in self.nifi.EventWriter.log.call_args_list
            if call.args
        ]

    def test_token_is_never_written_to_the_log_in_full(self):
        self.http.get.side_effect = [response(200, "payload")]

        with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()) as writer:
            writer.INFO = "INFO"
            writer.ERROR = "ERROR"
            writer.DEBUG = "DEBUG"
            self.get_request(JWT)
            logged = " | ".join(
                str(arg) for call in writer.log.call_args_list for arg in call.args
            )

        self.assertNotIn(JWT, logged)
        self.assertIn(JWT[-4:], logged)  # the tail is kept, for debugging


class GetPasswordTest(NiFiScriptTestCase):

    def setUp(self):
        super().setUp()
        self.use_real_get_password()

    def test_missing_stored_credential_is_logged_as_an_error(self):
        """Returning None silently left 'Bearer None' as the only symptom."""
        stored = mock.MagicMock()
        stored.username = "someone-else"
        service = mock.MagicMock()
        service.storage_passwords = [stored]

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            with mock.patch.object(self.nifi, "EventWriter", mock.MagicMock()) as writer:
                writer.INFO = "INFO"
                writer.ERROR = "ERROR"
                result = self.script._NiFiScript__get_password(
                    mock.MagicMock(), "session-key", "admin"
                )
                levels = [call.args[1] for call in writer.log.call_args_list]
                messages = " ".join(
                    str(arg) for call in writer.log.call_args_list for arg in call.args
                )

        self.assertIsNone(result)
        self.assertIn("ERROR", levels)
        self.assertIn("No stored credential", messages)

    def test_matching_credential_is_returned(self):
        stored = mock.MagicMock()
        stored.username = "admin"
        stored.content.clear_password = "secret"
        service = mock.MagicMock()
        service.storage_passwords = [stored]

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            result = self.script._NiFiScript__get_password(
                mock.MagicMock(), "session-key", "admin"
            )

        self.assertEqual(result, "secret")


class UnauthenticatedModeTest(NiFiScriptTestCase):
    """auth_type=none must not touch storage/passwords at all.

    __get_request used to read the stored password before branching on
    auth_type, so an unsecured input made one pointless storage/passwords
    call per endpoint per cycle -- and once __get_password started logging a
    missing credential, that turned into an ERROR per request for a
    credential that mode never stores. The mocked unit tests could not see
    this; the integration run against NiFi 1.23.2 surfaced it as six errors
    against two indexed events.
    """

    def test_no_credential_lookup_when_auth_is_none(self):
        self.http.get.side_effect = [response(200, "payload")]
        lookup = mock.patch.object(
            self.nifi.NiFiScript, "_NiFiScript__get_password", return_value="pw"
        )
        self._stop_password_patcher()
        spy = lookup.start()
        self.addCleanup(lookup.stop)

        result = self.get_request("ignored", auth_type="none")

        self.assertEqual(result, "payload")
        spy.assert_not_called()

    def test_credential_is_looked_up_when_auth_is_basic(self):
        self.http.get.side_effect = [response(200, "payload")]
        lookup = mock.patch.object(
            self.nifi.NiFiScript, "_NiFiScript__get_password", return_value="pw"
        )
        self._stop_password_patcher()
        spy = lookup.start()
        self.addCleanup(lookup.stop)

        self.get_request("TOKEN", auth_type="basic")

        spy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
