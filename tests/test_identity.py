"""Identity allow/deny. Installed client public keys only. No registration."""

import unittest

from opennhp_router.identity import decision


class IdentityDecisionTest(unittest.TestCase):
    def test_installed_pubkey_is_allowed(self):
        installed = ["client-pubkey-a", "client-pubkey-b"]
        self.assertEqual(decision("client-pubkey-a", installed), "allow")

    def test_unknown_pubkey_is_denied(self):
        installed = ["client-pubkey-a"]
        self.assertEqual(decision("not-installed", installed), "deny")

    def test_empty_pubkey_is_denied(self):
        self.assertEqual(decision("", ["client-pubkey-a"]), "deny")


if __name__ == "__main__":
    unittest.main()
