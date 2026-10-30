"""Image and compose boundaries. Gateway is NHP-AC, server is not auth, no agent in the default stack."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKER = ROOT / "docker"


def _copy_lines(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("COPY"):
            lines.append(stripped)
    return lines


def _stage(text, name):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith("FROM ") and line.rstrip().endswith(f"AS {name}"):
            start = i
            break
    if start is None:
        return ""
    block = [lines[start]]
    for line in lines[start + 1:]:
        if line.startswith("FROM "):
            break
        block.append(line)
    return "\n".join(block)


class DockerfileBoundaryTest(unittest.TestCase):
    def test_one_clone_and_one_pin(self):
        text = (DOCKER / "Dockerfile").read_text()
        self.assertEqual(text.count("git clone"), 1)
        self.assertEqual(text.count("0115f5ff"), 1)
        self.assertIn("opennhp-keygen", text)

    def test_gateway_stage_does_not_copy_server_or_auth_code(self):
        text = _stage((DOCKER / "Dockerfile").read_text(), "gateway")
        copies = "\n".join(_copy_lines(text)).lower()
        self.assertNotIn("plugins/authclient", copies)
        self.assertNotIn("authclient", copies)
        self.assertNotIn("nhp-server", copies)
        self.assertIn("nhp-ac", text)
        self.assertNotIn("nhp-serverd", text)

    def test_server_stage_is_not_the_auth_service(self):
        dockerfile = (DOCKER / "Dockerfile").read_text()
        server = _stage(dockerfile, "server")
        auth = _stage(dockerfile, "auth")
        self.assertNotEqual(server, auth)
        self.assertIn("nhp-server", server)
        self.assertIn("authclient", server)
        self.assertNotIn("nhp-server", auth)
        self.assertIn("8090", auth)
        self.assertNotIn("8090", server)

    def test_relay_stage_uses_the_shared_pin(self):
        text = _stage((DOCKER / "Dockerfile").read_text(), "relay")
        self.assertIn("nhp-relay", text)
        self.assertNotIn("git clone", text)


class ComposeBoundaryTest(unittest.TestCase):
    def test_default_stack_has_no_agent_and_relay_is_optional(self):
        text = (DOCKER / "compose.yaml").read_text()
        self.assertNotIn("compose.agent.yaml", text)
        self.assertNotIn("opennhp-agent", text)
        services = _service_names(text)
        self.assertIn("gateway", services)
        self.assertIn("server", services)
        self.assertIn("auth", services)
        self.assertNotIn("agent", services)
        self.assertIn("relay", services)
        self.assertIn("relay", _service_block(text, "relay"))
        relay_block = _service_block(text, "relay")
        self.assertIn("profiles:", relay_block)
        self.assertIn("relay", relay_block)
        for name in ("gateway", "server", "auth"):
            block = _service_block(text, name)
            self.assertNotIn("profiles:", block)
            self.assertNotIn("relay", _depends_on(block))

    def test_agent_compose_is_separate(self):
        text = (DOCKER / "compose.agent.yaml").read_text()
        self.assertIn("agent:", text)
        self.assertIn("image: opennhp-agent", text)
        self.assertIn("upstream agent", text.lower())


def _service_names(text):
    names = []
    in_services = False
    for line in text.splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if in_services and line and not line.startswith(" ") and not line.startswith("#"):
            break
        if in_services and line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            names.append(line.strip()[:-1])
    return names


def _service_block(text, name):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.startswith(f"  {name}:"):
            start = i + 1
            break
    if start is None:
        return ""
    block = []
    for line in lines[start:]:
        if line.startswith("  ") and not line.startswith("   ") and line.rstrip().endswith(":"):
            break
        block.append(line)
    return "\n".join(block)


def _depends_on(block):
    lines = block.splitlines()
    collecting = False
    names = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("depends_on:"):
            collecting = True
            continue
        if collecting:
            if stripped.startswith("- "):
                names.append(stripped[2:].split(":")[0])
                continue
            if stripped and not stripped.startswith("#"):
                break
    return names


if __name__ == "__main__":
    unittest.main()
