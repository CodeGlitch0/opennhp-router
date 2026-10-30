"""Cipher scheme 0 (Curve25519) in every rendered daemon config."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 15

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


class CipherSchemeTest(unittest.TestCase):
    def test_rendered_configs_use_curve25519_scheme_0(self):
        files = render(load_operator_text(OPERATOR))
        server = files["server/etc/config.toml"]
        gateway = files["gateway/etc/config.toml"]
        relay = files["relay/etc/config.toml"]
        self.assertIn("DefaultCipherScheme = 0", server)
        self.assertIn("DefaultCipherScheme = 0", gateway)
        self.assertIn("cipherScheme = 0", relay)
        for text in (server, gateway, relay):
            self.assertNotIn("DefaultCipherScheme = 1", text)
            self.assertNotIn("cipherScheme = 1", text)


if __name__ == "__main__":
    unittest.main()
