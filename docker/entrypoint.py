#!/usr/bin/env python3
"""Prepare one image: own key, rendered stock files, then the role process.

Private keys stay in this image's volume. Peers dial 127.0.0.1.
The ACK name is the public host. The AC open address is the local filter IP.
"""

import os
import sys
from pathlib import Path

from opennhp_router.keys import ensure_keypair, key_path, regenerate_requested
from opennhp_router.operator import load_operator_path
from opennhp_router.packetpath import (
    PacketPathError,
    addresses_document,
    apply_filter,
    check_forwards,
    host_local_ipv4s,
    load_addresses,
    resolve_forwards,
    system_resolver,
)
from opennhp_router.render import render


_REQUIRED_PEERS = {
    "gateway": ("server",),
    "server": ("gateway",),
    "relay": ("server",),
    "auth": (),
}


def required_peers(role: str, env=None) -> tuple:
    if role == "server":
        peers = ["gateway"]
        if _relay_required(env):
            peers.append("relay")
        return tuple(peers)
    if role not in _REQUIRED_PEERS:
        raise ValueError(f"unknown role {role}")
    return _REQUIRED_PEERS[role]


def _relay_required(env) -> bool:
    return str((env or {}).get("OPENNHP_REQUIRE_RELAY", "")).strip() == "1"


def _wait_files(role: str, env) -> tuple:
    files = [f"{name}/public" for name in required_peers(role, env)]
    if role == "server":
        files.append("gateway/addresses.toml")
    return tuple(files)


def wait_for_peers(peer_dir, names, timeout=None, interval=0.05) -> None:
    wait_for_files(
        peer_dir,
        [f"{name}/public" for name in names],
        timeout=timeout,
        interval=interval,
    )


def wait_for_files(root, relative, timeout=None, interval=0.05) -> None:
    import time

    pending = set(relative)
    deadline = None if timeout is None else time.monotonic() + float(timeout)
    while pending:
        for name in list(pending):
            path = Path(root) / name
            if path.is_file() and path.read_text().strip():
                pending.discard(name)
        if not pending:
            return
        if deadline is not None and time.monotonic() >= deadline:
            missing = ", ".join(sorted(pending))
            raise TimeoutError(f"missing peer files: {missing}")
        time.sleep(interval)


def prepare(
    role,
    operator_path,
    etc_dir,
    key_root,
    publish_dir,
    peer_dir,
    env,
    resolver=None,
    local_ips=None,
):
    config = load_operator_path(operator_path)
    pair = ensure_keypair(
        key_path(role, key_root),
        regenerate_requested(env),
        keygen=env.get("OPENNHP_KEYGEN"),
    )
    # Publish this image's public key before waiting, or two roles deadlock.
    _publish(publish_dir, pair.public)
    if role == "gateway":
        # Resolve and refuse bad forwards before any listener starts.
        forwards = [
            forward
            for resource in config.resources
            for forward in resource.forwards
        ]
        check_forwards(forwards)
        mapping = resolve_forwards(
            forwards,
            host_local_ipv4s() if local_ips is None else local_ips,
            resolver or system_resolver,
        )
        _publish_addresses(publish_dir, mapping)
    timeout = env.get("OPENNHP_PEER_TIMEOUT")
    wait_for_files(peer_dir, _wait_files(role, env), timeout=timeout)
    addresses = None
    if role == "server":
        text = (Path(peer_dir) / "gateway" / "addresses.toml").read_text()
        addresses = load_addresses(text)
    files = render(config, _peer_keys(role, pair, peer_dir), addresses)
    _write_role(role, etc_dir, files)
    return pair


def _publish(publish_dir, public: str) -> None:
    dest = Path(publish_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "public").write_text(public + "\n")
    os.chmod(dest / "public", 0o644)


def _publish_addresses(publish_dir, mapping: dict) -> None:
    dest = Path(publish_dir)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "addresses.toml").write_text(addresses_document(mapping))


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


def open_gateway(ports, apply, start_forwarder) -> int:
    """Apply the port filter, then start the forwarder. Filter failure stops."""
    try:
        apply(ports)
    except Exception:
        return 1
    start_forwarder()
    return 0


def agent_config_text(private: str) -> str:
    """Minimum etc/config.toml so nhp-agentd run stays up. No baked key."""
    return "\n".join([
        f'PrivateKeyBase64 = "{private}"',
        "DefaultCipherScheme = 0",
        "LogLevel = 2",
        "",
    ])


def start_agent(env, execv=None) -> int:
    """Generate a key, write the stock config, exec nhp-agentd run."""
    execv = execv or os.execv
    key_root = Path(env.get("OPENNHP_KEY_ROOT", "/var/lib/opennhp"))
    pair = ensure_keypair(
        key_root / "agent" / "keypair.toml",
        regenerate_requested(env),
        keygen=env.get("OPENNHP_KEYGEN"),
    )
    etc = Path(env.get("OPENNHP_ETC", "/opt/nhp-agent/etc"))
    etc.mkdir(parents=True, exist_ok=True)
    (etc / "config.toml").write_text(agent_config_text(pair.private))
    binary = env.get("OPENNHP_BIN", "/opt/nhp-agent/nhp-agentd")
    execv(binary, [binary, "run"])
    return 1


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


def _gateway_ports(operator_path):
    config = load_operator_path(operator_path)
    return [
        forward.public_port
        for resource in config.resources
        for forward in resource.forwards
    ]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    role = argv[0] if argv else os.environ.get("OPENNHP_ROLE", "")
    if "OPENNHP_KEYGEN" not in os.environ:
        os.environ["OPENNHP_KEYGEN"] = "/opt/opennhp-keygen"
    if role == "agent":
        return start_agent(os.environ)
    if role not in _ETC:
        print("usage: entrypoint.py <gateway|server|auth|relay|agent>", file=sys.stderr)
        return 2
    etc = Path(os.environ.get("OPENNHP_ETC", _ETC[role]))
    operator_path = os.environ.get("OPENNHP_OPERATOR", "/etc/opennhp/router.toml")
    try:
        prepare(
            role,
            operator_path=operator_path,
            etc_dir=etc,
            key_root=Path(os.environ.get("OPENNHP_KEY_ROOT", "/var/lib/opennhp")),
            publish_dir=Path(os.environ.get("OPENNHP_PUBLISH", f"/run/publish/{role}")),
            peer_dir=Path(os.environ.get("OPENNHP_PEERS", "/run/peers")),
            env=os.environ,
        )
    except PacketPathError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if role == "auth":
        from opennhp_router.authhttp import serve

        config = load_operator_path(operator_path)
        httpd, _port = serve(
            [item.pubkey for item in config.identities],
            host="127.0.0.1",
            port=8090,
        )
        httpd.serve_forever()
        return 0
    if role == "gateway":
        forwarder = os.environ.get("OPENNHP_FORWARDER", "/opt/forwarder.py")

        def start_forwarder():
            if os.path.isfile(forwarder):
                os.spawnv(
                    os.P_NOWAIT,
                    sys.executable,
                    [sys.executable, forwarder, str(etc / "forwards.toml")],
                )

        if open_gateway(_gateway_ports(operator_path), apply_filter, start_forwarder) != 0:
            print("filter rules failed; forwarder not started", file=sys.stderr)
            return 1
    binary = os.environ.get("OPENNHP_BIN", _BIN[role])
    os.execv(binary, [binary, "run"])
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
