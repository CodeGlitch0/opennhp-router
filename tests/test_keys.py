"""Key files: create, keep, regenerate. Three images, three paths. Scheme 0."""

import os
import stat
import tempfile
import unittest
from pathlib import Path

from opennhp_router.keys import ensure_keypair, key_path, regenerate_requested


class KeyFileTest(unittest.TestCase):
    def test_first_start_writes_keypair_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "keypair.toml"
            first = ensure_keypair(path)
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
            first = ensure_keypair(path)
            again = ensure_keypair(path, regenerate=False)
            self.assertEqual(again.private, first.private)
            self.assertFalse(regenerate_requested({}))
            self.assertFalse(regenerate_requested({"OPENNHP_REGENERATE_KEY": "0"}))
            replaced = ensure_keypair(path, regenerate=regenerate_requested({"OPENNHP_REGENERATE_KEY": "1"}))
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


class Curve25519VectorTest(unittest.TestCase):
    def test_base_point_matches_rfc7748(self):
        from opennhp_router.keys import x25519_public

        scalar = bytes.fromhex(
            "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a"
        )
        public = x25519_public(scalar)
        self.assertEqual(
            public.hex(),
            "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a",
        )


if __name__ == "__main__":
    unittest.main()
