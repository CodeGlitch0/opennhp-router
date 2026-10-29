"""iptables-deny.sh drops unauthorized packets. No REJECT, no error page, no DNAT."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "docker" / "iptables-deny.sh"


class IptablesDenyTest(unittest.TestCase):
    def test_drops_input_and_forward_and_creates_defaultset(self):
        text = SCRIPT.read_text()
        self.assertIn("iptables -P INPUT DROP", text)
        self.assertIn("iptables -P FORWARD DROP", text)
        self.assertIn("defaultset", text)
        self.assertIn("ipset", text)
        self.assertNotIn("REJECT", text)
        self.assertNotIn("DNAT", text)
        self.assertNotIn("<html", text.lower())
        self.assertNotIn("error page", text.lower())


if __name__ == "__main__":
    unittest.main()
