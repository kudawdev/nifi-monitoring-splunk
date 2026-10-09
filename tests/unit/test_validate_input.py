"""Tests for validate_input in bin/nifi.py.

The scheme declares use_external_validation = True, so Splunk calls this
method before saving an input. It used to be a stub:

    a = 1
    b = 2
    if a >= b:
        raise ValueError("a >= b")

1 >= 2 is never true, so nothing was ever validated and a bad URL or a
mistyped component id was accepted and only failed later, as an HTTP error
buried in splunkd.log.
"""

import unittest
import unittest.mock as mock

from support import load_nifi_module

VALID_UUID = "c45766f3-018e-1000-d4c4-8bc3e0de9c9e"
OTHER_UUID = "c4574f03-018e-1000-c4c6-bf343a1a92ea"


def definition(**params):
    """A stand-in for Splunk's ValidationDefinition."""
    base = {"api_url": "http://nifi:8080/nifi-api/", "auth_type": "none"}
    base.update(params)
    stub = mock.MagicMock()
    stub.parameters = base
    return stub


class ValidateInputTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.nifi, _ = load_nifi_module()

    def setUp(self):
        self.script = self.nifi.NiFiScript()

    def assertRejected(self, expected_message, **params):
        with self.assertRaises(ValueError) as caught:
            self.script.validate_input(definition(**params))
        self.assertIn(expected_message, str(caught.exception))

    # --- accepted configurations -------------------------------------------

    def test_accepts_minimal_unauthenticated_input(self):
        self.script.validate_input(definition())

    def test_accepts_basic_auth_with_credentials(self):
        self.script.validate_input(
            definition(auth_type="basic", username="admin", password="secret")
        )

    def test_accepts_https_url(self):
        self.script.validate_input(definition(api_url="https://nifi:8443/nifi-api/"))

    def test_accepts_component_ids_separated_by_comma_or_newline(self):
        self.script.validate_input(
            definition(
                endpoint_processors_history="{},{}".format(VALID_UUID, OTHER_UUID),
                endpoint_process_groups_history="{}\n{}\n".format(VALID_UUID, OTHER_UUID),
            )
        )

    def test_accepts_a_cron_expression_as_interval(self):
        """Splunk allows cron in the interval field; it must not be rejected."""
        self.script.validate_input(definition(interval="*/5 * * * *"))

    # --- rejected configurations -------------------------------------------

    def test_rejects_missing_url(self):
        self.assertRejected("API URL is required", api_url="")

    def test_rejects_whitespace_only_url(self):
        self.assertRejected("API URL is required", api_url="   ")

    def test_rejects_url_without_scheme(self):
        self.assertRejected("must start with http", api_url="nifi:8080/nifi-api")

    def test_rejects_unknown_auth_type(self):
        self.assertRejected("Auth type must be", auth_type="kerberos")

    def test_rejects_basic_auth_without_username(self):
        self.assertRejected(
            "Username is required", auth_type="basic", username="", password="secret"
        )

    def test_rejects_basic_auth_without_password(self):
        self.assertRejected(
            "Password is required", auth_type="basic", username="admin", password=""
        )

    def test_rejects_zero_interval(self):
        self.assertRejected("greater than 0", interval="0")

    def test_rejects_malformed_processor_id(self):
        self.assertRejected(
            "Invalid processor id", endpoint_processors_history="not-a-uuid"
        )

    def test_rejects_truncated_processor_id(self):
        self.assertRejected(
            "Invalid processor id", endpoint_processors_history=VALID_UUID[:-4]
        )

    def test_rejects_malformed_process_group_id(self):
        self.assertRejected(
            "Invalid process group id",
            endpoint_process_groups_history="{},oops".format(VALID_UUID),
        )


class SplitIdsTest(unittest.TestCase):
    """_split_ids replaced two copies of the same inline lambda chain."""

    @classmethod
    def setUpClass(cls):
        cls.split = staticmethod(load_nifi_module()[0].NiFiScript._split_ids)

    def test_splits_on_commas_and_newlines(self):
        self.assertEqual(self.split("a,b\nc"), ["a", "b", "c"])

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(self.split(" a , b \n c "), ["a", "b", "c"])

    def test_drops_empty_entries(self):
        self.assertEqual(self.split("a,,b,\n\n,c,"), ["a", "b", "c"])

    def test_empty_input_yields_no_ids(self):
        self.assertEqual(self.split(""), [])
        self.assertEqual(self.split("\n,  ,\n"), [])


if __name__ == "__main__":
    unittest.main()
