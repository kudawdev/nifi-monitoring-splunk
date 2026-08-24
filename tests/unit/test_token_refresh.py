"""Regression tests for the basic-auth token refresh in bin/nifi.py.

NiFi issues a JWT with a limited lifetime (8 hours on 2.11.0), so a
long-running input eventually gets a 401 and has to renew. The renewal path
built a new headers dict but never put it into the request arguments, so the
retry re-sent the expired token and the input stayed broken until the next
scheduled run.
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

        self.dotenv.set_key.assert_called_once()
        args = self.dotenv.set_key.call_args.args
        self.assertEqual(args[1], "prod")
        self.assertEqual(args[2], "NEW-TOKEN")

    def test_unauthenticated_mode_sends_no_authorization_header(self):
        self.http.get.side_effect = [response(200, "payload")]

        result = self.get_request("ignored", auth_type="none")

        self.assertEqual(result, "payload")
        headers = self.http.get.call_args_list[0].kwargs["headers"]
        self.assertNotIn("Authorization", headers)


if __name__ == "__main__":
    unittest.main()
