"""Mapped TCP ports are dropped. The host filter policy is not changed."""

import unittest

from opennhp_router.packetpath import PacketPathError, apply_filter, filter_commands


class FilterCommandTest(unittest.TestCase):
    def test_mapped_port_is_dropped_without_a_policy_change(self):
        commands = filter_commands([443])
        blob = "\n".join(" ".join(cmd) for cmd in commands)

        self.assertNotIn("-P INPUT DROP", blob)
        self.assertNotIn("-P FORWARD DROP", blob)
        self.assertNotIn("-F", blob)
        self.assertNotIn("REJECT", blob)
        self.assertNotIn("DNAT", blob)
        self.assertIn("hash:ip,port,ip", blob)
        self.assertIn("defaultset", blob)

        for cmd in commands:
            self.assertNotIn("-P", cmd)
            self.assertNotIn("-F", cmd)

        drops = [cmd for cmd in commands if "DROP" in cmd]
        self.assertTrue(drops)
        for cmd in drops:
            self.assertEqual(cmd[0], "iptables")
            self.assertIn("--dport", cmd)
            self.assertIn("443", cmd)
            self.assertIn("tcp", cmd)
            self.assertNotIn("FORWARD", cmd)

        accepts = [
            cmd for cmd in commands
            if "ACCEPT" in cmd and "defaultset" in cmd
        ]
        self.assertTrue(accepts)
        for cmd in accepts:
            self.assertIn("--dport", cmd)
            self.assertIn("443", cmd)
            self.assertIn("src,dst,dst", cmd)

        established = [cmd for cmd in commands if "ESTABLISHED" in cmd]
        self.assertTrue(established)
        self.assertIn("443", established[0])

    def test_commands_are_specific_to_each_mapped_port(self):
        commands = filter_commands([443, 8443])
        blob = "\n".join(" ".join(cmd) for cmd in commands)
        self.assertIn("--dport 443", blob)
        self.assertIn("--dport 8443", blob)
        for cmd in commands:
            if cmd[0] == "iptables":
                self.assertIn("--dport", cmd)
                self.assertNotIn("-P", cmd)

    def test_drop_follows_the_defaultset_accept_for_that_port(self):
        commands = filter_commands([443])
        indexed = list(enumerate(commands))
        accept = next(
            i for i, cmd in indexed
            if "ACCEPT" in cmd and "defaultset" in cmd and "443" in cmd
        )
        drop = next(i for i, cmd in indexed if "DROP" in cmd and "443" in cmd)
        established = next(i for i, cmd in indexed if "ESTABLISHED" in cmd)
        self.assertLess(established, accept)
        self.assertLess(accept, drop)

    def test_apply_failure_is_an_error(self):
        with self.assertRaises(PacketPathError):
            apply_filter([443], runner=lambda _cmd: 1)


if __name__ == "__main__":
    unittest.main()
