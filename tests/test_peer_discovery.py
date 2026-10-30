"""Peers dial 127.0.0.1. Operator addresses are not peer addresses."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 45

[[identities]]
pubkey = "client-pubkey-a"

[[resources]]
name = "app"

[[resources.forwards]]
public_host = "203.0.113.10"
public_port = 443
backend_host = "10.9.8.7"
backend_port = 8080
protocol = "tcp"
"""

PEER_FILES = (
    "gateway/etc/server.toml",
    "server/etc/ac.toml",
    "server/etc/relay.toml",
    "relay/etc/config.toml",
)


class PeerDiscoveryTest(unittest.TestCase):
    def test_peer_dial_host_is_loopback_not_an_operator_address(self):
        files = render(load_operator_text(OPERATOR))
        blob = "\n".join(files[name] for name in PEER_FILES)
        self.assertIn('Host = "127.0.0.1"', files["gateway/etc/server.toml"])
        self.assertIn('Host = "127.0.0.1"', files["relay/etc/config.toml"])
        self.assertNotIn('Host = "server"', blob)
        self.assertNotIn('Host = "gateway"', blob)
        self.assertNotIn('Host = "auth"', blob)
        self.assertNotIn('Host = "relay"', blob)
        self.assertIn("62206", blob)
        self.assertNotIn("203.0.113.10", blob)
        self.assertNotIn("10.9.8.7", blob)
        self.assertNotIn("pub.example", blob)


if __name__ == "__main__":
    unittest.main()
