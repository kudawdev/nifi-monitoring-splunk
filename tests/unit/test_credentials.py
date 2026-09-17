"""Tests for credential handling in bin/nifi.py.

The input logged the full NiFi JWT at INFO level, which put a usable
credential into splunkd.log on every request, and __get_password returned
None without a word when no stored credential matched the username.
"""

import os
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response

TA_BIN = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "nifi_TA_monitoring", "bin",
)

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


class TokenStorageTest(NiFiScriptTestCase):
    """Defect B-14: the JWT used to be written to a .env inside the app.

    That file was lost on every reinstall, dotenv.find_dotenv() walked up from
    the working directory and could pick up an unrelated one under
    $SPLUNK_HOME, and -- the reason it blocks more than one instance --
    use_single_instance is false, so every input's process rewrote that same
    file non-atomically.
    """

    def stored(self, realm=None, username=None, password=None):
        entry = mock.MagicMock()
        entry.realm = realm
        entry.username = username
        entry.content.clear_password = password
        return entry

    def test_the_module_no_longer_writes_a_dotenv(self):
        """A source check: the file was created at import time, so nothing that
        exercises the class would notice its return."""
        source = open(
            os.path.join(TA_BIN, "nifi.py"), encoding="utf-8"
        ).read()
        self.assertNotIn("import dotenv", source)
        self.assertNotIn("set_key", source)
        self.assertNotIn("load_dotenv", source)

    def passwords(self, *entries):
        """storage_passwords is both iterable and has create/delete, which a
        plain list is not."""
        collection = mock.MagicMock()
        collection.__iter__ = lambda _self: iter(entries)
        return collection

    def test_the_token_is_stored_under_its_own_realm(self):
        service = mock.MagicMock()
        service.storage_passwords = self.passwords()

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            self.script._NiFiScript__write_token(
                mock.MagicMock(), "session-key", "prod", "NEW-TOKEN"
            )

        service.storage_passwords.create.assert_called_once_with(
            "NEW-TOKEN", "prod", self.script.token_realm
        )

    def test_the_stored_token_is_read_back(self):
        service = mock.MagicMock()
        service.storage_passwords = [
            self.stored(realm=self.script.token_realm, username="prod",
                        password="STORED-TOKEN"),
        ]

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            result = self.script._NiFiScript__read_token(
                mock.MagicMock(), "session-key", "prod"
            )

        self.assertEqual(result, "STORED-TOKEN")

    def test_another_inputs_token_is_not_returned(self):
        """The point of moving off the shared .env: one instance must not read
        or overwrite another's token."""
        service = mock.MagicMock()
        service.storage_passwords = [
            self.stored(realm=self.script.token_realm, username="staging",
                        password="STAGING-TOKEN"),
        ]

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            result = self.script._NiFiScript__read_token(
                mock.MagicMock(), "session-key", "prod"
            )

        self.assertIsNone(result)

    def test_the_token_is_read_once_per_process(self):
        """Without the cache this would be a storage/passwords round trip per
        endpoint per cycle, which is worse than the file it replaces."""
        service = mock.MagicMock()
        service.storage_passwords = [
            self.stored(realm=self.script.token_realm, username="prod",
                        password="STORED-TOKEN"),
        ]

        with mock.patch.object(self.nifi.client, "connect",
                               return_value=service) as connect:
            for _ in range(3):
                self.script._NiFiScript__read_token(
                    mock.MagicMock(), "session-key", "prod"
                )

        self.assertEqual(connect.call_count, 1)

    def test_a_token_entry_is_not_mistaken_for_the_credential(self):
        """Both live in storage/passwords. An input named like the NiFi user
        would otherwise hand the JWT back as the password."""
        self.use_real_get_password()
        service = mock.MagicMock()
        service.storage_passwords = [
            self.stored(realm=self.script.token_realm, username="admin",
                        password="A-JWT"),
            self.stored(realm=None, username="admin", password="the-password"),
        ]

        with mock.patch.object(self.nifi.client, "connect", return_value=service):
            result = self.script._NiFiScript__get_password(
                mock.MagicMock(), "session-key", "admin"
            )

        self.assertEqual(result, "the-password")
