"""Client-facing resource address is the public host and port, never the backend."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 90

[[identities]]
pubkey = "client-pubkey-a"

[[resources]]
name = "app"

[[resources.forwards]]
public_host = "pub.example"
public_port = 443
backend_host = "backend.internal"
backend_port = 8080
protocol = "tcp"
"""


class PluginResourceAddressTest(unittest.TestCase):
    def test_advertises_public_host_and_port_not_backend(self):
        config = load_operator_text(OPERATOR)
        files = render(config)
        resource = files["server/plugins/authclient/etc/resource.toml"]

        self.assertIn('ACId = "gateway"', resource)
        self.assertIn("OpenTime = 90", resource)
        self.assertIn('Hostname = "pub.example"', resource)
        self.assertIn('Addr.Ip = "pub.example"', resource)
        self.assertIn("Addr.Port = 443", resource)
        self.assertNotIn("backend.internal", resource)
        self.assertNotIn("8080", resource)


if __name__ == "__main__":
    unittest.main()
