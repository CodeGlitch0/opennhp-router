"""Public hosts must be local. Reserved ports and non-TCP forwards are refused."""

import unittest

from opennhp_router.operator import Forward
from opennhp_router.packetpath import (
    PacketPathError,
    check_forwards,
    resolve_forwards,
)


def _fwd(host, port, protocol="tcp"):
    return Forward(host, port, "backend.internal", 9, protocol)


class ResolveFailsClosedTest(unittest.TestCase):
    def test_name_resolves_to_a_local_address(self):
        mapping = resolve_forwards(
            [_fwd("gateway.example", 443)],
            local_ips={"198.51.100.8"},
            resolver=lambda host: ["198.51.100.8"],
        )
        self.assertEqual(mapping, {"gateway.example": "198.51.100.8"})

    def test_fails_closed_when_the_address_is_not_local(self):
        with self.assertRaises(PacketPathError):
            resolve_forwards(
                [_fwd("gateway.example", 443)],
                local_ips={"127.0.0.1"},
                resolver=lambda host: ["203.0.113.9"],
            )

    def test_ip_is_used_only_if_it_is_local(self):
        with self.assertRaises(PacketPathError):
            resolve_forwards(
                [_fwd("203.0.113.9", 443)],
                local_ips={"198.51.100.8"},
                resolver=lambda host: ["198.51.100.8"],
            )

    def test_literal_ip_does_not_call_the_resolver(self):
        def boom(_host):
            raise AssertionError("resolver must not be called for an IP")

        mapping = resolve_forwards(
            [_fwd("198.51.100.8", 443)],
            local_ips={"198.51.100.8"},
            resolver=boom,
        )
        self.assertEqual(mapping["198.51.100.8"], "198.51.100.8")

    def test_uses_the_local_address_when_a_name_has_several(self):
        mapping = resolve_forwards(
            [_fwd("gateway.example", 443)],
            local_ips={"198.51.100.8"},
            resolver=lambda host: ["8.8.8.8", "198.51.100.8"],
        )
        self.assertEqual(mapping["gateway.example"], "198.51.100.8")

    def test_resolver_error_fails_closed(self):
        def boom(_host):
            raise OSError("dns")

        with self.assertRaises(PacketPathError):
            resolve_forwards(
                [_fwd("gateway.example", 443)],
                local_ips={"198.51.100.8"},
                resolver=boom,
            )


class ForwardRefusalTest(unittest.TestCase):
    def test_reserved_ports_refused(self):
        for port in (62206, 8090, 8080):
            with self.assertRaises(PacketPathError):
                check_forwards([_fwd("198.51.100.8", port)])

    def test_non_tcp_refused(self):
        for protocol in ("udp", "any", "icmp", ""):
            with self.assertRaises(PacketPathError):
                check_forwards([_fwd("198.51.100.8", 443, protocol)])

    def test_tcp_on_an_unreserved_port_is_allowed(self):
        check_forwards([_fwd("198.51.100.8", 443, "TCP")])


if __name__ == "__main__":
    unittest.main()
