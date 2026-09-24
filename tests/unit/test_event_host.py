"""The host an input's events carry.

The form says the input's name is "used as the host value unless one is set
below". Nothing did that: with no host in the stanza splunkd hands the input
its placeholder, "$decideOnStartup", and the add-on wrote that literal into
every event. An input created from the form without a Host then matched no
row of the instance lookup and appeared on no dashboard.
"""

import unittest

from support import NiFiScriptTestCase


class EventHostTest(NiFiScriptTestCase):

    def host(self, configured):
        return self.nifi.NiFiScript._event_host(configured, "prod_nifi")

    def test_no_host_means_the_input_name(self):
        for configured in (None, "", "   "):
            with self.subTest(configured=configured):
                self.assertEqual(self.host(configured), "prod_nifi")

    def test_splunkds_placeholder_is_not_a_host(self):
        self.assertEqual(self.host("$decideOnStartup"), "prod_nifi")

    def test_a_configured_host_wins(self):
        self.assertEqual(self.host("nifi-cluster-a"), "nifi-cluster-a")


if __name__ == "__main__":
    unittest.main()
