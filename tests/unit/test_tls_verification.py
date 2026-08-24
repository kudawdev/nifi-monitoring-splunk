"""Tests for TLS verification in bin/nifi.py.

Every request used to pass verify=False, with urllib3's warning silenced at
import time. Against a NiFi served over HTTPS that accepts any certificate,
so anyone able to intercept the connection can read the username, the
password and the bearer token. NiFi 2.x serves HTTPS by default, so this is
the common case rather than the exception.

Verification is now on unless the input turns it off.
"""

import os
import tempfile
import unittest
import unittest.mock as mock

from support import NiFiScriptTestCase, load_nifi_module, response


class TlsVerifyResolutionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def resolve(self, **item):
        return self.nifi.NiFiScript()._tls_verify(item)

    def test_verification_is_on_when_the_input_says_nothing(self):
        """An input saved before this option existed must still verify."""
        self.assertIs(self.resolve(), True)

    def test_verification_is_on_when_explicitly_enabled(self):
        for value in ("1", "true", "True", "yes", "on"):
            with self.subTest(value=value):
                self.assertIs(self.resolve(verify_tls=value), True)

    def test_verification_is_off_when_explicitly_disabled(self):
        for value in ("0", "false", "False", "no", "off"):
            with self.subTest(value=value):
                self.assertIs(self.resolve(verify_tls=value), False)

    def test_a_ca_bundle_is_passed_through_as_the_verify_value(self):
        self.assertEqual(
            self.resolve(ca_bundle="/opt/certs/nifi-ca.pem"),
            "/opt/certs/nifi-ca.pem",
        )

    def test_an_empty_ca_bundle_falls_back_to_the_system_store(self):
        self.assertIs(self.resolve(ca_bundle="   "), True)

    def test_disabling_verification_wins_over_a_ca_bundle(self):
        self.assertIs(
            self.resolve(verify_tls="0", ca_bundle="/opt/certs/nifi-ca.pem"), False
        )


class RequestsReceiveTheVerifyValueTest(NiFiScriptTestCase):

    def test_requests_verify_defaults_to_true(self):
        self.http.get.side_effect = [response(200, "payload")]
        self.get_request("TOKEN", auth_type="none")
        self.assertIs(self.http.get.call_args_list[0].kwargs["verify"], True)

    def test_requests_verify_follows_the_resolved_value(self):
        self.script.tls_verify = "/opt/certs/nifi-ca.pem"
        self.http.get.side_effect = [response(200, "payload")]
        self.get_request("TOKEN", auth_type="basic")
        self.assertEqual(
            self.http.get.call_args_list[0].kwargs["verify"], "/opt/certs/nifi-ca.pem"
        )

    def test_the_token_request_also_verifies(self):
        self.http.get.side_effect = [response(401), response(200, "payload")]
        self.http.post.return_value = response(200, "NEW-TOKEN")
        self.get_request("EXPIRED")
        self.assertIs(self.http.post.call_args_list[0].kwargs["verify"], True)


class WarningsAreNotSilencedGloballyTest(unittest.TestCase):

    def test_module_import_does_not_disable_urllib3_warnings(self):
        """Silencing the warning at import time hid it even for inputs that
        never asked to skip verification."""
        source = open(
            os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "nifi_TA_monitoring",
                "bin",
                "nifi.py",
            )
        ).read()
        module_body = source.split("class NiFiScript", 1)[0]
        self.assertNotIn("disable_warnings", module_body)
        # but it must still be silenced somewhere, for the opted-in case
        self.assertIn("disable_warnings", source)


class CaBundleValidationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def validate(self, **params):
        base = {"api_url": "http://nifi:8080/nifi-api/", "auth_type": "none"}
        base.update(params)
        definition = mock.MagicMock()
        definition.parameters = base
        return self.nifi.NiFiScript().validate_input(definition)

    def test_a_missing_ca_bundle_is_rejected(self):
        with self.assertRaises(ValueError) as caught:
            self.validate(ca_bundle="/does/not/exist.pem")
        self.assertIn("CA bundle not found", str(caught.exception))

    def test_an_existing_ca_bundle_is_accepted(self):
        with tempfile.NamedTemporaryFile(suffix=".pem") as bundle:
            self.validate(ca_bundle=bundle.name)

    def test_a_ca_bundle_with_verification_off_is_rejected(self):
        """Asking to trust a bundle while skipping verification is incoherent
        and almost certainly a mistake."""
        with tempfile.NamedTemporaryFile(suffix=".pem") as bundle:
            with self.assertRaises(ValueError) as caught:
                self.validate(ca_bundle=bundle.name, verify_tls="0")
            self.assertIn("verification is disabled", str(caught.exception))


class TlsHintTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.hint = staticmethod(load_nifi_module()[0].NiFiScript._NiFiScript__tls_hint)

    def test_a_certificate_error_explains_the_two_ways_out(self):
        hint = self.hint("SSLError: certificate verify failed: self signed certificate")
        self.assertIn("CA bundle", hint)
        self.assertIn("Verify TLS certificate", hint)

    def test_an_unrelated_error_adds_nothing(self):
        self.assertEqual(self.hint("Connection refused"), "")


if __name__ == "__main__":
    unittest.main()
