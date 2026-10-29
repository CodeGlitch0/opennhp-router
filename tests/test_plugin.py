"""Auth plugin exports Init and AuthWithNHP and asks the auth service."""

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "authclient" / "main.go"


class AuthClientPluginTest(unittest.TestCase):
    def test_exports_only_init_and_auth_with_nhp(self):
        text = PLUGIN.read_text()
        exported = re.findall(r"^func ([A-Z][A-Za-z0-9]*)\(", text, re.M)
        self.assertEqual(exported, ["Init", "AuthWithNHP"])

    def test_signatures_match_upstream_loader(self):
        text = PLUGIN.read_text()
        self.assertIn("func Init(in *plugins.PluginParamsIn) error", text)
        self.assertIn(
            "func AuthWithNHP(req *common.NhpAuthRequest, helper *plugins.NhpServerPluginHelper)",
            text,
        )
        self.assertIn("*common.ServerKnockAckMsg", text)
        self.assertIn("http://auth:8090/authorize", text)
        self.assertIn("http.Post", text)
        self.assertIn('"pubkey"', text)
        self.assertIn("req.PublicKey", text)
        self.assertIn("AuthWithNhpCallbackFunc", text)
        self.assertNotIn("NHP_KNK", text)
        self.assertNotIn("NHP_ACK", text)
        self.assertNotIn("/register", text)


if __name__ == "__main__":
    unittest.main()
