"""Resolve public hosts onto this host, and build the port filter commands.

The resolver and the local-IP set are injected so tests do not need this
host to own a name or to have iptables privileges. Production passes the
host's addresses and the system resolver.
"""

from ipaddress import IPv4Address, AddressValueError
import socket
import tomllib

RESERVED_PORTS = frozenset({62206, 8090, 8080})


class PacketPathError(Exception):
    """A forward cannot be published, or a filter command failed."""


def check_forwards(forwards) -> None:
    """Refuse reserved public ports and anything that is not TCP."""
    for forward in forwards:
        protocol = _field(forward, "protocol").strip().lower()
        if protocol != "tcp":
            raise PacketPathError(f"protocol {protocol!r} is not tcp")
        port = int(_field(forward, "public_port"))
        if port in RESERVED_PORTS:
            raise PacketPathError(f"public_port {port} is reserved")


def resolve_forwards(forwards, local_ips, resolver) -> dict[str, str]:
    """Map each public host to a local IPv4. Fail closed otherwise.

    An IP is used only when it is in ``local_ips``. A name must resolve to
    one. The resolver is not called for an IP literal.
    """
    local = set(local_ips)
    mapping = {}
    for forward in forwards:
        host = _field(forward, "public_host").strip()
        if not host:
            raise PacketPathError("public_host is empty")
        if host in mapping:
            continue
        mapping[host] = _resolve_one(host, local, resolver)
    return mapping


def _resolve_one(host: str, local_ips: set[str], resolver) -> str:
    if _is_ipv4(host):
        if host not in local_ips:
            raise PacketPathError(f"{host} is not assigned on this host")
        return host
    try:
        found = list(resolver(host))
    except PacketPathError:
        raise
    except Exception as exc:
        raise PacketPathError(f"{host} did not resolve to a local address") from exc
    for ip in found:
        if ip in local_ips and _is_ipv4(ip):
            return ip
    raise PacketPathError(f"{host} does not resolve to an address on this host")


def _is_ipv4(value: str) -> bool:
    try:
        IPv4Address(value)
    except AddressValueError:
        return False
    return True


def filter_commands(ports) -> list[list[str]]:
    """Create defaultset, then per mapped TCP port: established, set, drop.

    No chain policy and no flush. An unauthorized SYN to a mapped port is
    dropped. Other host ports are left alone.
    """
    commands = [[
        "ipset", "-exist", "create", "defaultset",
        "hash:ip,port,ip", "counters", "maxelem", "1000000", "timeout", "120",
    ]]
    seen = []
    for port in ports:
        text = str(int(port))
        if text in seen:
            continue
        seen.append(text)
        commands.append([
            "iptables", "-A", "INPUT", "-p", "tcp", "--dport", text,
            "-m", "state", "--state", "ESTABLISHED", "-j", "ACCEPT",
        ])
        commands.append([
            "iptables", "-A", "INPUT", "-p", "tcp", "--dport", text,
            "-m", "set", "--match-set", "defaultset", "src,dst,dst",
            "-j", "ACCEPT",
        ])
        commands.append([
            "iptables", "-A", "INPUT", "-p", "tcp", "--dport", text, "-j", "DROP",
        ])
    return commands


def apply_filter(ports, runner=None) -> None:
    """Apply filter commands. A non-zero exit is an error.

    An existing identical iptables rule is left in place. A check that
    fails is not itself a failure; the following append is.
    """
    run = runner or _run
    for cmd in filter_commands(ports):
        if cmd[:2] == ["iptables", "-A"]:
            check = ["iptables", "-C", *cmd[2:]]
            if run(check) == 0:
                continue
        if run(cmd) != 0:
            raise PacketPathError("filter command failed: " + " ".join(cmd))


def addresses_document(mapping: dict[str, str]) -> str:
    """TOML the server reads as the filter address of each public host."""
    lines = [
        "# Local IPv4 the packet filter sees for each public host.",
        "# Not a backend address and not a DNS name.",
        "[addresses]",
    ]
    for host, ip in mapping.items():
        lines.append(f'{_quote(host)} = {_quote(ip)}')
    lines.append("")
    return "\n".join(lines)


def load_addresses(text: str) -> dict[str, str]:
    data = tomllib.loads(text)
    raw = data.get("addresses") or {}
    return {str(host): str(ip) for host, ip in raw.items()}


def host_local_ipv4s() -> set[str]:
    """IPv4 addresses assigned on this host. Always includes loopback."""
    ips = {"127.0.0.1"}
    try:
        import fcntl
        import struct
        from pathlib import Path

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            net = Path("/sys/class/net")
            if not net.is_dir():
                return ips
            for iface in net.iterdir():
                name = iface.name.encode()[:15]
                ifreq = struct.pack("16s16s", name, b"\x00" * 16)
                try:
                    result = fcntl.ioctl(sock.fileno(), 0x8915, ifreq)
                except OSError:
                    continue
                ips.add(socket.inet_ntoa(result[20:24]))
        finally:
            sock.close()
    except OSError:
        return ips
    return ips


def system_resolver(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET)
    except socket.gaierror as exc:
        raise PacketPathError(f"{host} did not resolve to an IPv4 address") from exc
    found = []
    for info in infos:
        ip = info[4][0]
        if ip not in found:
            found.append(ip)
    if not found:
        raise PacketPathError(f"{host} did not resolve to an IPv4 address")
    return found


def _run(cmd: list[str]) -> int:
    import subprocess

    completed = subprocess.run(cmd, check=False)
    return completed.returncode


def _field(forward, name: str):
    if isinstance(forward, dict):
        return forward[name]
    return getattr(forward, name)


def _quote(value: str) -> str:
    text = str(value)
    if any(ch in text for ch in '"\\\n\r'):
        raise PacketPathError(f"unsupported address {text!r}")
    return f'"{text}"'
