"""The gateway forward table is not the client-facing address."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 30

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

[[resources.forwards]]
public_host = "pub.example"
public_port = 8443
backend_host = "other.internal"
backend_port = 9443
protocol = "tcp"
"""


class ForwardTableTest(unittest.TestCase):
    def test_forward_table_maps_public_port_to_backend(self):
        files = render(
            load_operator_text(OPERATOR),
            addresses={"pub.example": "198.51.100.8"},
        )
        table = files["gateway/etc/forwards.toml"]
        client = files["server/plugins/authclient/etc/resource.toml"]

        self.assertIn("public_port = 443", table)
        self.assertIn('backend_host = "backend.internal"', table)
        self.assertIn("backend_port = 8080", table)
        self.assertIn("public_port = 8443", table)
        self.assertIn('backend_host = "other.internal"', table)
        self.assertNotIn("backend.internal", client)
        self.assertNotIn("other.internal", client)
        self.assertNotIn("9443", client)
        self.assertIn('Addr.Ip = "198.51.100.8"', client)
        self.assertNotIn('Addr.Ip = "backend.internal"', client)
        self.assertNotIn('Addr.Ip = "other.internal"', client)


if __name__ == "__main__":
    unittest.main()
