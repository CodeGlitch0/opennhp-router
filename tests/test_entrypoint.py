"""Shared entrypoint: one key path per image, render stock files, keep keys."""

import importlib.util
import stat
import tempfile
import unittest
from pathlib import Path

from opennhp_router.operator import load_operator_text


def _load_entrypoint():
    path = Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py"
    spec = importlib.util.spec_from_file_location("opennhp_entrypoint", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = _load_entrypoint().prepare


def _keygen_env(root: Path, private: str = "priv-role", public: str = "pub-role") -> dict:
    script = root / "keygen"
    root.mkdir(parents=True, exist_ok=True)
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{{\"privateKey\":\"{private}\",\"publicKey\":\"{public}\"}}'\n"
    )
    script.chmod(0o755)
    return {"OPENNHP_KEYGEN": str(script)}


def _seed_peer(peer_dir: Path, name: str, public: str = "peer-pub") -> None:
    dest = peer_dir / name
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "public").write_text(public + "\n")


def _seed_addresses(peer_dir: Path, mapping: dict) -> None:
    dest = peer_dir / "gateway"
    dest.mkdir(parents=True, exist_ok=True)
    lines = ["[addresses]"]
    for host, ip in mapping.items():
        lines.append(f'"{host}" = "{ip}"')
    (dest / "addresses.toml").write_text("\n".join(lines) + "\n")


OPERATOR = """
window_seconds = 25

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


class EntrypointPrepareTest(unittest.TestCase):
    def test_prepare_keeps_key_and_writes_role_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            etc = root / "etc"
            publish = root / "publish"
            peers = root / "peers"
            _seed_peer(peers, "server")
            env = _keygen_env(root)
            first = prepare(
                "gateway",
                operator_path=operator,
                etc_dir=etc,
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=peers,
                env=env,
                resolver=lambda _host: ["198.51.100.8"],
                local_ips={"198.51.100.8"},
            )
            key_file = root / "keys" / "gateway" / "keypair.toml"
            self.assertTrue(key_file.is_file())
            self.assertEqual(stat.S_IMODE(key_file.stat().st_mode), 0o600)
            self.assertFalse(stat.S_IMODE(key_file.stat().st_mode) & 0o077)
            again = prepare(
                "gateway",
                operator_path=operator,
                etc_dir=etc,
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=peers,
                env=env,
                resolver=lambda _host: ["198.51.100.8"],
                local_ips={"198.51.100.8"},
            )
            self.assertEqual(again.private, first.private)
            replaced = prepare(
                "gateway",
                operator_path=operator,
                etc_dir=etc,
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=peers,
                env={**env, "OPENNHP_REGENERATE_KEY": "1", "OPENNHP_KEYGEN": _keygen_env(root / "regen", "priv-new", "pub-new")["OPENNHP_KEYGEN"]},
                resolver=lambda _host: ["198.51.100.8"],
                local_ips={"198.51.100.8"},
            )
            self.assertNotEqual(replaced.private, first.private)
            forwards = (etc / "forwards.toml").read_text()
            self.assertIn("backend.internal", forwards)
            server_peer = (etc / "server.toml").read_text()
            self.assertIn('Host = "127.0.0.1"', server_peer)
            self.assertNotIn('Host = "server"', server_peer)
            self.assertNotIn("backend.internal", server_peer)
            config = load_operator_text(OPERATOR)
            self.assertEqual(config.window_seconds, 25)

    def test_three_roles_do_not_share_a_key_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            paths = []
            peers = root / "peers"
            _seed_peer(peers, "server")
            _seed_peer(peers, "gateway")
            _seed_addresses(peers, {"pub.example": "198.51.100.8"})
            env = _keygen_env(root)
            for role in ("gateway", "server", "auth"):
                prepare(
                    role,
                    operator_path=operator,
                    etc_dir=root / role / "etc",
                    key_root=root / "keys",
                    publish_dir=root / "publish" / role,
                    peer_dir=root / "peers",
                    env=env,
                    resolver=lambda _host: ["198.51.100.8"],
                    local_ips={"198.51.100.8"},
                )
                paths.append(root / "keys" / role / "keypair.toml")
            self.assertEqual(len(set(paths)), 3)
            for path in paths:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            resource = (root / "server" / "plugins" / "authclient" / "etc" / "resource.toml").read_text()
            self.assertIn('Addr.Ip = "198.51.100.8"', resource)
            self.assertNotIn('Addr.Ip = "pub.example"', resource)
            self.assertNotIn("backend.internal", resource)


class PeerWaitTest(unittest.TestCase):
    def test_server_renders_the_gateway_key_published_after_startup(self):
        import threading
        import time

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            publish = root / "publish"
            script = root / "keygen"
            script.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' '{\"privateKey\":\"priv-role\",\"publicKey\":\"pub-role\"}'\n"
            )
            script.chmod(0o755)

            def release():
                deadline = time.monotonic() + 1
                while not (publish / "public").is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                time.sleep(0.05)
                peer = root / "peers" / "gateway"
                peer.mkdir(parents=True)
                (peer / "public").write_text("gateway-pub\n")
                (peer / "addresses.toml").write_text(
                    '[addresses]\n"pub.example" = "198.51.100.8"\n'
                )

            threading.Thread(target=release, daemon=True).start()
            prepare(
                "server",
                operator_path=operator,
                etc_dir=root / "etc",
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=root / "peers",
                env={"OPENNHP_KEYGEN": str(script), "OPENNHP_PEER_TIMEOUT": "2"},
            )
            self.assertIn("gateway-pub", (root / "etc" / "ac.toml").read_text())
            resource = (root / "plugins" / "authclient" / "etc" / "resource.toml").read_text()
            self.assertIn('Addr.Ip = "198.51.100.8"', resource)
            self.assertNotIn("backend.internal", resource)

    def test_server_does_not_wait_for_relay(self):
        entry = _load_entrypoint()
        self.assertEqual(entry.required_peers("server"), ("gateway",))
        self.assertNotIn("relay", entry.required_peers("server"))
        self.assertEqual(
            entry.required_peers("server", {"OPENNHP_REQUIRE_RELAY": "1"}),
            ("gateway", "relay"),
        )
        self.assertEqual(entry.required_peers("gateway"), ("server",))
        self.assertEqual(entry.required_peers("relay"), ("server",))
        self.assertEqual(entry.required_peers("auth"), ())

    def test_server_blocks_on_relay_only_when_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            peers = root / "peers"
            _seed_peer(peers, "gateway")
            _seed_addresses(peers, {"pub.example": "198.51.100.8"})
            env = _keygen_env(root)
            env["OPENNHP_PEER_TIMEOUT"] = "0.3"
            prepare(
                "server",
                operator_path=operator,
                etc_dir=root / "etc",
                key_root=root / "keys",
                publish_dir=root / "publish",
                peer_dir=peers,
                env=env,
            )
            with self.assertRaises(TimeoutError):
                prepare(
                    "server",
                    operator_path=operator,
                    etc_dir=root / "wait",
                    key_root=root / "keys",
                    publish_dir=root / "publish",
                    peer_dir=peers,
                    env={**env, "OPENNHP_REQUIRE_RELAY": "1"},
                )

    def test_server_waits_for_the_address_file(self):
        import threading
        import time

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            publish = root / "publish"
            script = root / "keygen"
            script.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' '{\"privateKey\":\"priv-role\",\"publicKey\":\"pub-role\"}'\n"
            )
            script.chmod(0o755)
            released = {}

            def release():
                deadline = time.monotonic() + 1
                while not (publish / "public").is_file() and time.monotonic() < deadline:
                    time.sleep(0.01)
                peer = root / "peers" / "gateway"
                peer.mkdir(parents=True)
                (peer / "public").write_text("gateway-pub\n")
                time.sleep(0.2)
                released["at"] = time.monotonic()
                (peer / "addresses.toml").write_text(
                    '[addresses]\n"pub.example" = "198.51.100.8"\n'
                )

            threading.Thread(target=release, daemon=True).start()
            prepare(
                "server",
                operator_path=operator,
                etc_dir=root / "etc",
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=root / "peers",
                env={"OPENNHP_KEYGEN": str(script), "OPENNHP_PEER_TIMEOUT": "2"},
            )
            self.assertIn("at", released)
            resource = (root / "plugins" / "authclient" / "etc" / "resource.toml").read_text()
            self.assertIn('Addr.Ip = "198.51.100.8"', resource)

    def test_filter_failure_does_not_start_the_forwarder(self):
        entry = _load_entrypoint()
        self.assertTrue(hasattr(entry, "open_gateway"))
        started = []

        def fail(_ports):
            raise RuntimeError("iptables")

        rc = entry.open_gateway([443], apply=fail, start_forwarder=lambda: started.append(1))
        self.assertEqual(rc, 1)
        self.assertEqual(started, [])
        rc = entry.open_gateway([443], apply=lambda _ports: None, start_forwarder=lambda: started.append(1))
        self.assertEqual(rc, 0)
        self.assertEqual(started, [1])

    def test_auth_bind_is_loopback(self):
        text = (Path(__file__).resolve().parents[1] / "docker" / "entrypoint.py").read_text()
        self.assertIn('host="127.0.0.1"', text)
        self.assertIn("port=8090", text)

    def test_gateway_publishes_the_filter_address_before_waiting(self):
        from opennhp_router.packetpath import PacketPathError

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            publish = root / "publish"
            env = _keygen_env(root)
            env["OPENNHP_PEER_TIMEOUT"] = "0.2"
            with self.assertRaises(TimeoutError):
                prepare(
                    "gateway",
                    operator_path=operator,
                    etc_dir=root / "etc",
                    key_root=root / "keys",
                    publish_dir=publish,
                    peer_dir=root / "peers",
                    env=env,
                    resolver=lambda _host: ["198.51.100.8"],
                    local_ips={"198.51.100.8"},
                )
            text = (publish / "addresses.toml").read_text()
            self.assertIn("198.51.100.8", text)
            self.assertNotIn("backend.internal", text)
            self.assertTrue((publish / "public").is_file())

            with self.assertRaises(PacketPathError):
                prepare(
                    "gateway",
                    operator_path=operator,
                    etc_dir=root / "bad",
                    key_root=root / "keys",
                    publish_dir=root / "bad-publish",
                    peer_dir=root / "peers",
                    env=env,
                    resolver=lambda _host: ["203.0.113.9"],
                    local_ips={"127.0.0.1"},
                )
            self.assertFalse((root / "bad-publish" / "addresses.toml").exists())

    def test_gateway_refuses_reserved_port_and_non_tcp_before_a_listener(self):
        from opennhp_router.packetpath import PacketPathError

        reserved = OPERATOR.replace("public_port = 443", "public_port = 62206")
        udp = OPERATOR.replace('protocol = "tcp"', 'protocol = "udp"')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = _keygen_env(root)
            env["OPENNHP_PEER_TIMEOUT"] = "2"
            for text in (reserved, udp):
                operator = root / "router.toml"
                operator.write_text(text)
                publish = root / f"pub-{text[0]}"
                with self.assertRaises(PacketPathError):
                    prepare(
                        "gateway",
                        operator_path=operator,
                        etc_dir=root / "etc",
                        key_root=root / "keys",
                        publish_dir=publish,
                        peer_dir=root / "peers",
                        env=env,
                        resolver=lambda _host: ["198.51.100.8"],
                        local_ips={"198.51.100.8"},
                    )


if __name__ == "__main__":
    unittest.main()
