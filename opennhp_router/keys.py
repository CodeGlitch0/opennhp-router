"""Key files produced by OpenNHP's own keygen.

Scheme 0 only: the command is `keygen --curve --json`. This module does not
implement a curve. Each image has its own path so the three required images
cannot share one private key. The private key file is mode 0600.
"""

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess

_ROLES = ("gateway", "server", "auth", "relay")


@dataclass(frozen=True)
class Keypair:
    private: str
    public: str


def key_path(role: str, root: Path | str = "/var/lib/opennhp") -> Path:
    if role not in _ROLES:
        raise ValueError(f"unknown role {role}")
    return Path(root) / role / "keypair.toml"


def regenerate_requested(env: dict) -> bool:
    return env.get("OPENNHP_REGENERATE_KEY") == "1"


def ensure_keypair(path: Path | str, regenerate: bool = False, keygen: str | None = None) -> Keypair:
    path = Path(path)
    if path.exists() and not regenerate:
        return _read_keypair(path)
    if not keygen:
        raise ValueError("keygen command is required to create a key")
    pair = _from_keygen(keygen)
    _write_secret(path, _format(pair))
    return pair


def _from_keygen(binary: str) -> Keypair:
    proc = subprocess.run(
        [binary, "keygen", "--curve", "--json"],
        check=True,
        capture_output=True,
        text=True,
    )
    data = json.loads(_json_line(proc.stdout))
    private = data.get("privateKey", "")
    public = data.get("publicKey", "")
    if not private or not public or private == public:
        raise ValueError("keygen returned an unusable pair")
    return Keypair(private, public)


def _json_line(text: str) -> str:
    for line in reversed(text.splitlines()):
        if line.startswith("{"):
            return line
    raise ValueError("keygen produced no JSON")


def _format(pair: Keypair) -> str:
    return (
        "scheme = 0\n"
        f'private = "{pair.private}"\n'
        f'public = "{pair.public}"\n'
    )


def _read_keypair(path: Path) -> Keypair:
    import tomllib
    data = tomllib.loads(path.read_text())
    return Keypair(data["private"], data["public"])


def _write_secret(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, text.encode("utf-8"))
    finally:
        os.close(fd)
    os.chmod(path, 0o600)
