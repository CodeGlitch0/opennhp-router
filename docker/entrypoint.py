#!/usr/bin/env python3
"""Prepare one image: own key, rendered stock files, then the role process.

Private keys stay in this image's volume. Peer files use compose DNS names.
The client-facing resource address is the public host and port, never the backend.
"""

import os
import sys
from pathlib import Path

from opennhp_router.keys import ensure_keypair, key_path, regenerate_requested
from opennhp_router.operator import load_operator_path
from opennhp_router.render import render


_REQUIRED_PEERS = {
    "gateway": ("server",),
    "server": ("gateway",),
    "relay": ("server",),
    "auth": (),
}


def required_peers(role: str) -> tuple:
    if role not in _REQUIRED_PEERS:
        raise ValueError(f"unknown role {role}")
    return _REQUIRED_PEERS[role]


def wait_for_peers(peer_dir, names, timeout=None, interval=0.05) -> None:
    import time

    pending = set(names)
    deadline = None if timeout is None else time.monotonic() + float(timeout)
    while pending:
        for name in list(pending):
            pub = Path(peer_dir) / name / "public"
            if pub.is_file() and pub.read_text().strip():
                pending.discard(name)
        if not pending:
            return
        if deadline is not None and time.monotonic() >= deadline:
            missing = ", ".join(sorted(pending))
            raise TimeoutError(f"missing peer public keys: {missing}")
        time.sleep(interval)


def prepare(
    role,
    operator_path,
    etc_dir,
    key_root,
    publish_dir,
    peer_dir,
    env,
):
    config = load_operator_path(operator_path)
    pair = ensure_keypair(
        key_path(role, key_root),
        regenerate_requested(env),
        keygen=env.get("OPENNHP_KEYGEN"),
    )
    _publish(publish_dir, pair.public)
    timeout = env.get("OPENNHP_PEER_TIMEOUT")
    wait_for_peers(peer_dir, required_peers(role), timeout=timeout)
    files = render(config, _peer_keys(role, pair, peer_dir))
    _write_role(role, etc_dir, files)
    return pair


def _publish(publish_dir, public: str) -> None:
    dest = Path(publish_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "public").write_text(public + "\n")
    os.chmod(dest / "public", 0o644)


def _peer_keys(role, pair, peer_dir) -> dict:
    keys = {role: {"private": pair.private, "public": pair.public}}
    root = Path(peer_dir)
    if not root.is_dir():
        return keys
    for child in root.iterdir():
        pub = child / "public"
        if child.is_dir() and pub.is_file():
            keys[child.name] = {"public": pub.read_text().strip()}
    return keys


def _write_role(role, etc_dir, files) -> None:
    etc_dir = Path(etc_dir)
    prefix = role + "/"
    for name, text in files.items():
        if not name.startswith(prefix):
            continue
        rel = name[len(prefix):]
        if rel.startswith("etc/"):
            dest = etc_dir / rel[len("etc/"):]
        else:
            dest = etc_dir.parent / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)


_ETC = {
    "gateway": "/opt/nhp-ac/etc",
    "server": "/opt/nhp-server/etc",
    "relay": "/opt/nhp-relay/etc",
    "auth": "/var/lib/opennhp/auth",
}
_BIN = {
    "gateway": "/opt/nhp-ac/nhp-acd",
    "server": "/opt/nhp-server/nhp-serverd",
    "relay": "/opt/nhp-relay/nhp-relayd",
}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    role = argv[0] if argv else os.environ.get("OPENNHP_ROLE", "")
    if role not in _ETC:
        print("usage: entrypoint.py <gateway|server|auth|relay>", file=sys.stderr)
        return 2
    if "OPENNHP_KEYGEN" not in os.environ:
        os.environ["OPENNHP_KEYGEN"] = "/opt/opennhp-keygen"
    etc = Path(os.environ.get("OPENNHP_ETC", _ETC[role]))
    prepare(
        role,
        operator_path=os.environ.get("OPENNHP_OPERATOR", "/etc/opennhp/router.toml"),
        etc_dir=etc,
        key_root=Path(os.environ.get("OPENNHP_KEY_ROOT", "/var/lib/opennhp")),
        publish_dir=Path(os.environ.get("OPENNHP_PUBLISH", f"/run/publish/{role}")),
        peer_dir=Path(os.environ.get("OPENNHP_PEERS", "/run/peers")),
        env=os.environ,
    )
    if role == "auth":
        from opennhp_router.authhttp import serve
        from opennhp_router.operator import load_operator_path

        config = load_operator_path(os.environ.get("OPENNHP_OPERATOR", "/etc/opennhp/router.toml"))
        httpd, _port = serve([item.pubkey for item in config.identities])
        httpd.serve_forever()
        return 0
    if role == "gateway":
        deny = os.environ.get("OPENNHP_IPTABLES", "/iptables-deny.sh")
        if os.path.isfile(deny) and os.access(deny, os.X_OK):
            os.spawnv(os.P_WAIT, deny, [deny])
        forwarder = os.environ.get("OPENNHP_FORWARDER", "/opt/forwarder.py")
        if os.path.isfile(forwarder):
            os.spawnv(os.P_NOWAIT, sys.executable, [sys.executable, forwarder, str(etc / "forwards.toml")])
    binary = os.environ.get("OPENNHP_BIN", _BIN[role])
    os.execv(binary, [binary, "run"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
