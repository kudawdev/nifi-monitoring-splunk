"""Regression tests for the basic-auth token refresh in bin/nifi.py.

NiFi issues a JWT with a limited lifetime (8 hours on 2.11.0), so a
long-running input eventually gets a 401 and has to renew. The renewal path
built a new headers dict but never put it into the request arguments, so the
retry re-sent the expired token and the input stayed broken until the next
scheduled run.

There are two ways to arrive without a usable token and they are not the
same. A cold start has nothing stored and knows it, so it logs in first
(TA-7). An expired token cannot be told apart from a good one until NiFi
refuses it, so that one is still reactive. Both paths are covered here.
"""

import unittest

from support import NiFiScriptTestCase, response


class TokenRefreshTest(NiFiScriptTestCase):

    def test_retry_after_401_uses_the_new_token(self):
        self.http.get.side_effect = [response(401), response(200, "payload")]
        self.http.post.return_value = response(200, "NEW-TOKEN")

        result = self.get_request("EXPIRED-TOKEN")

        self.assertEqual(
            self.sent_tokens(), ["Bearer EXPIRED-TOKEN", "Bearer NEW-TOKEN"]
        )
        self.assertEqual(result, "payload")

    def test_failed_renewal_does_not_retry_with_a_null_token(self):
        """A login that fails must abort, not retry with 'Bearer None'."""
        self.http.get.side_effect = [response(401)]
        self.http.post.return_value = response(401, "Unauthorized")

        result = self.get_request("EXPIRED-TOKEN")

        self.assertEqual(len(self.http.get.call_args_list), 1)
        self.assertIsNone(result)

    def test_renewal_exception_does_not_retry_with_a_null_token(self):
        self.http.get.side_effect = [response(401)]
        self.http.post.side_effect = OSError("connection refused")

        result = self.get_request("EXPIRED-TOKEN")

        self.assertEqual(len(self.http.get.call_args_list), 1)
        self.assertIsNone(result)

    def test_successful_request_does_not_hit_the_login_endpoint(self):
        self.http.get.side_effect = [response(200, "payload")]

        result = self.get_request("VALID-TOKEN")

        self.assertEqual(result, "payload")
        self.assertEqual(self.http.post.call_args_list, [])
        self.assertEqual(self.sent_tokens(), ["Bearer VALID-TOKEN"])

    def test_renewed_token_is_persisted(self):
        """The new token has to be written back, or every run pays a 401 first."""
        self.http.get.side_effect = [response(401), response(200, "payload")]
        self.http.post.return_value = response(200, "NEW-TOKEN")

        self.get_request("EXPIRED-TOKEN", input_name="prod")

        self.assertEqual(self.stored_tokens, ["NEW-TOKEN"])

    def test_cold_start_asks_for_a_token_instead_of_provoking_a_401(self):
        """TA-7. With nothing stored the input used to send the literal string
        "unknown" as the bearer and let NiFi refuse it, which cost one ERROR
        per enabled endpoint on every fresh install. It asks first now."""
        self.http.get.side_effect = [response(200, "payload")]
        self.http.post.return_value = response(200, "FIRST-TOKEN")

        result = self.get_request(None)

        self.assertEqual(result, "payload")
        self.assertEqual(self.sent_tokens(), ["Bearer FIRST-TOKEN"])
        self.assertEqual(len(self.http.get.call_args_list), 1)

    def test_cold_start_stores_the_token_it_fetched(self):
        """Or the next process pays for the same login all over again."""
        self.http.get.side_effect = [response(200, "payload")]
        self.http.post.return_value = response(200, "FIRST-TOKEN")

        self.get_request(None, input_name="prod")

        self.assertEqual(self.stored_tokens, ["FIRST-TOKEN"])

    def test_cold_start_with_a_failed_login_issues_no_request(self):
        """Bad credentials must not produce a 'Bearer None' call to NiFi."""
        self.http.post.return_value = response(401, "Unauthorized")

        result = self.get_request(None)

        self.assertIsNone(result)
        self.assertEqual(self.http.get.call_args_list, [])

    def test_an_expired_token_is_still_renewed_on_the_401(self):
        """The cold-start fetch must not replace the renewal path: a token
        that was valid and expired cannot be predicted, only reacted to."""
        self.http.get.side_effect = [response(401), response(200, "payload")]
        self.http.post.return_value = response(200, "NEW-TOKEN")

        result = self.get_request("EXPIRED-TOKEN")

        self.assertEqual(result, "payload")
        self.assertEqual(
            self.sent_tokens(), ["Bearer EXPIRED-TOKEN", "Bearer NEW-TOKEN"])

    def test_unauthenticated_mode_sends_no_authorization_header(self):
        self.http.get.side_effect = [response(200, "payload")]

        result = self.get_request("ignored", auth_type="none")

        self.assertEqual(result, "payload")
        headers = self.http.get.call_args_list[0].kwargs["headers"]
        self.assertNotIn("Authorization", headers)


if __name__ == "__main__":
    unittest.main()
