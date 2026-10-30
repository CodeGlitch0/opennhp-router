"""Key files: create, keep, regenerate. Three images, three paths. Scheme 0."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from opennhp_router.keys import ensure_keypair, key_path, regenerate_requested


def _keygen(root: Path, private: str, public: str) -> str:
    script = root / f"keygen-{private}"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' '{{\"privateKey\":\"{private}\",\"publicKey\":\"{public}\"}}'\n"
    )
    script.chmod(0o755)
    return str(script)


class KeyFileTest(unittest.TestCase):
    def test_first_start_writes_keypair_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keypair.toml"
            first = ensure_keypair(path, keygen=_keygen(Path(tmp), "priv-a", "pub-a"))
            self.assertTrue(path.is_file())
            mode = stat.S_IMODE(path.stat().st_mode)
            self.assertEqual(mode, 0o600)
            self.assertFalse(mode & 0o077)
            self.assertTrue(first.private)
            self.assertTrue(first.public)
            self.assertNotEqual(first.private, first.public)
            text = path.read_text()
            self.assertIn(first.private, text)
            self.assertIn(first.public, text)

    def test_restart_keeps_file_unless_regenerate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keypair.toml"
            root = Path(tmp)
            first = ensure_keypair(path, keygen=_keygen(root, "priv-a", "pub-a"))
            again = ensure_keypair(path, regenerate=False, keygen=_keygen(root, "priv-b", "pub-b"))
            self.assertEqual(again.private, first.private)
            self.assertFalse(regenerate_requested({}))
            self.assertFalse(regenerate_requested({"OPENNHP_REGENERATE_KEY": "0"}))
            replaced = ensure_keypair(
                path,
                regenerate=regenerate_requested({"OPENNHP_REGENERATE_KEY": "1"}),
                keygen=_keygen(root, "priv-b", "pub-b"),
            )
            self.assertNotEqual(replaced.private, first.private)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_three_images_use_three_paths(self):
        root = Path("/var/lib/opennhp")
        paths = [key_path(role, root) for role in ("gateway", "server", "auth")]
        self.assertEqual(len(set(paths)), 3)
        relay = key_path("relay", root)
        self.assertNotIn(relay, paths)
        for path in paths:
            self.assertIn(path.parent.name, ("gateway", "server", "auth"))


class KeygenCommandTest(unittest.TestCase):
    def test_new_key_comes_from_the_keygen_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "keygen"
            calls = root / "calls"
            script.write_text(
                "#!/bin/sh\n"
                f"echo \"$*\" >> {calls}\n"
                "printf '%s\\n' '{\"privateKey\":\"priv-from-keygen\",\"publicKey\":\"pub-from-keygen\"}'\n"
            )
            script.chmod(0o755)
            path = root / "keypair.toml"
            first = ensure_keypair(path, keygen=str(script))
            self.assertEqual(first.private, "priv-from-keygen")
            self.assertEqual(first.public, "pub-from-keygen")
            self.assertIn("keygen --curve --json", calls.read_text())
            again = ensure_keypair(path, keygen=str(script))
            self.assertEqual(again.private, first.private)
            self.assertEqual(calls.read_text().count("keygen --curve --json"), 1)
            source = Path(__file__).resolve().parents[1].joinpath("opennhp_router", "keys.py").read_text()
            self.assertNotIn("def _x25519", source)
            self.assertNotIn("2**255 - 19", source)


if __name__ == "__main__":
    unittest.main()
