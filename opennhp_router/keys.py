"""Curve25519 key files. Stand-in for `<daemon> keygen --curve`.

Scheme 0 only. Each image has its own path so the three required images
cannot share one private key. The private key file is mode 0600.
"""

from dataclasses import dataclass
import os
from pathlib import Path

_P = 2**255 - 19
_A24 = 121665
_BASE = bytes([9]) + bytes(31)
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


def x25519_public(scalar: bytes) -> bytes:
    return _x25519(scalar, _BASE)


def ensure_keypair(path: Path | str, regenerate: bool = False) -> Keypair:
    path = Path(path)
    if path.exists() and not regenerate:
        return _read_keypair(path)
    private = os.urandom(32)
    public = x25519_public(private)
    pair = Keypair(_b64(private), _b64(public))
    _write_secret(path, _format(pair))
    return pair


def _x25519(scalar: bytes, u_bytes: bytes) -> bytes:
    k = _decode_scalar(scalar)
    x1 = _decode_u(u_bytes)
    x2, z2 = 1, 0
    x3, z3 = x1, 1
    swap = 0
    for t in range(254, -1, -1):
        kt = (k >> t) & 1
        swap ^= kt
        if swap:
            x2, x3 = x3, x2
            z2, z3 = z3, z2
        swap = kt
        a = (x2 + z2) % _P
        aa = (a * a) % _P
        b = (x2 - z2) % _P
        bb = (b * b) % _P
        e = (aa - bb) % _P
        c = (x3 + z3) % _P
        d = (x3 - z3) % _P
        da = (d * a) % _P
        cb = (c * b) % _P
        x3 = pow(da + cb, 2, _P)
        z3 = (x1 * pow(da - cb, 2, _P)) % _P
        x2 = (aa * bb) % _P
        z2 = (e * (aa + _A24 * e)) % _P
    if swap:
        x2, x3 = x3, x2
        z2, z3 = z3, z2
    out = (x2 * pow(z2, _P - 2, _P)) % _P
    return out.to_bytes(32, "little")


def _decode_scalar(k: bytes) -> int:
    e = bytearray(k[:32])
    e[0] &= 248
    e[31] &= 127
    e[31] |= 64
    return int.from_bytes(e, "little")


def _decode_u(u: bytes) -> int:
    t = bytearray(u[:32])
    t[31] &= 127
    return int.from_bytes(t, "little")


def _b64(raw: bytes) -> str:
    import base64
    return base64.standard_b64encode(raw).decode("ascii")


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
