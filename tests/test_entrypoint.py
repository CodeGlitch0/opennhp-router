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
            first = prepare(
                "gateway",
                operator_path=operator,
                etc_dir=etc,
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=peers,
                env={},
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
                env={},
            )
            self.assertEqual(again.private, first.private)
            replaced = prepare(
                "gateway",
                operator_path=operator,
                etc_dir=etc,
                key_root=root / "keys",
                publish_dir=publish,
                peer_dir=peers,
                env={"OPENNHP_REGENERATE_KEY": "1"},
            )
            self.assertNotEqual(replaced.private, first.private)
            forwards = (etc / "forwards.toml").read_text()
            self.assertIn("backend.internal", forwards)
            server_peer = (etc / "server.toml").read_text()
            self.assertIn('Host = "server"', server_peer)
            self.assertNotIn("backend.internal", server_peer)
            config = load_operator_text(OPERATOR)
            self.assertEqual(config.window_seconds, 25)

    def test_three_roles_do_not_share_a_key_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            operator = root / "router.toml"
            operator.write_text(OPERATOR)
            paths = []
            for role in ("gateway", "server", "auth"):
                prepare(
                    role,
                    operator_path=operator,
                    etc_dir=root / role / "etc",
                    key_root=root / "keys",
                    publish_dir=root / "publish" / role,
                    peer_dir=root / "peers",
                    env={},
                )
                paths.append(root / "keys" / role / "keypair.toml")
            self.assertEqual(len(set(paths)), 3)
            for path in paths:
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            resource = (root / "server" / "plugins" / "authclient" / "etc" / "resource.toml").read_text()
            self.assertIn('Addr.Ip = "pub.example"', resource)
            self.assertNotIn("backend.internal", resource)


if __name__ == "__main__":
    unittest.main()
