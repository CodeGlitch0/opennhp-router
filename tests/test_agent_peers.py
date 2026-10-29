"""Installed client public keys are the only agent peers. No extra identities."""

import unittest

from opennhp_router.operator import load_operator_text
from opennhp_router.render import render


OPERATOR = """
window_seconds = 15

[[identities]]
pubkey = "client-pubkey-a"

[[identities]]
pubkey = "client-pubkey-b"

[[resources]]
name = "app"

[[resources.forwards]]
public_host = "pub.example"
public_port = 443
backend_host = "backend.internal"
backend_port = 8080
protocol = "tcp"
"""


class AgentPeerTest(unittest.TestCase):
    def test_agent_toml_lists_only_installed_pubkeys(self):
        files = render(load_operator_text(OPERATOR))
        agents = files["server/etc/agent.toml"]
        self.assertIn('PubKeyBase64 = "client-pubkey-a"', agents)
        self.assertIn('PubKeyBase64 = "client-pubkey-b"', agents)
        self.assertNotIn("not-installed", agents)
        self.assertEqual(agents.count("[[Agents]]"), 2)


if __name__ == "__main__":
    unittest.main()
