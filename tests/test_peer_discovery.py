"""Peer discovery uses compose DNS names, never operator-supplied addresses."""

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
    def test_peer_files_use_compose_dns_not_operator_addresses(self):
        files = render(load_operator_text(OPERATOR))
        blob = "\n".join(files[name] for name in PEER_FILES)
        for name in ("gateway", "server", "auth", "relay"):
            self.assertIn(f'"{name}"', blob)
        self.assertNotIn("203.0.113.10", blob)
        self.assertNotIn("10.9.8.7", blob)
        self.assertNotIn("pub.example", blob)


if __name__ == "__main__":
    unittest.main()
