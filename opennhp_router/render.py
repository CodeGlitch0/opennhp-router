"""Render stock OpenNHP TOML from the operator file.

ACK address and AC open address are the same upstream field. Confirmed in
the pinned tree at endpoints/server/udpserver.go, handleNhpOpenResource:
info.Addr is appended into acDstIpMap (the destination NHP-AC opens) and
ackMsg.ResourceHost is info.DestHost(), which reads that same ResourceInfo
(Hostname, else Addr.Ip, plus Addr.Port when PortSuffix is set). Advertise
the public host and port there. Never the backend. The gateway forwarder
dials the backend from a separate table.
"""

from opennhp_router.operator import OperatorConfig

PLUGIN_RESOURCE = "server/plugins/authclient/etc/resource.toml"
FORWARD_TABLE = "gateway/etc/forwards.toml"
# Compose DNS name of the auth service. Not an operator setting.
AUTH_URL = "http://auth:8090/authorize"
ASP_ID = "authclient"
AC_ID = "gateway"
# Same far-future epoch the upstream samples use for peer ExpireTime.
PEER_EXPIRE = 1924991999
SERVER_LISTEN_PORT = 62206


def render(config: OperatorConfig, peer_keys=None) -> dict[str, str]:
    keys = peer_keys or {}
    files = {
        PLUGIN_RESOURCE: _plugin_resource(config),
        FORWARD_TABLE: _forward_table(config),
        "server/etc/config.toml": _server_config_toml(keys),
        "server/etc/agent.toml": _agent_toml(config),
        "server/etc/resource.toml": _server_resource_toml(),
        "server/etc/http.toml": _http_toml(),
        "gateway/etc/config.toml": _gateway_config_toml(config, keys),
    }
    files.update(_peer_files(keys))
    return files


def _priv(keys, role: str) -> str:
    role_keys = keys.get(role) or {}
    if isinstance(role_keys, str):
        return ""
    return role_keys.get("private", "")


def _server_resource_toml() -> str:
    return "\n".join([
        f'["{ASP_ID}"]',
        f'PluginPath = "{ASP_ID}/{ASP_ID}.so"',
        "",
    ])


def _http_toml() -> str:
    return "\n".join([
        "# Stock server HTTP login surface stays off. Auth is a separate process.",
        "EnableHttp = false",
        "EnableTLS = false",
        'HttpListenIp = "127.0.0.1"',
        "HttpListenPort = 0",
        "",
    ])


def _agent_toml(config: OperatorConfig) -> str:
    lines = ["# Installed client public keys only. There is no register route.", ""]
    for identity in config.identities:
        lines.append("[[Agents]]")
        lines.append(f'PubKeyBase64 = "{identity.pubkey}"')
        lines.append(f"ExpireTime = {PEER_EXPIRE}")
        lines.append("")
    return "\n".join(lines)


def _server_config_toml(keys) -> str:
    return "\n".join([
        'PrivateKeyBase64 = "%s"' % _priv(keys, "server"),
        "DefaultCipherScheme = 0",
        'ListenIp = "0.0.0.0"',
        f"ListenPort = {SERVER_LISTEN_PORT}",
        'Hostname = "server"',
        "LogLevel = 2",
        "DisableAgentValidation = false",
        "AllowPrivateRelaySource = false",
        "ForceOverload = false",
        "",
    ])


def _gateway_config_toml(config: OperatorConfig, keys) -> str:
    names = ", ".join(f'"{resource.name}"' for resource in config.resources)
    return "\n".join([
        'ACId = "gateway"',
        'PrivateKeyBase64 = "%s"' % _priv(keys, "gateway"),
        "DefaultCipherScheme = 0",
        "IpPassMode = 0",
        "FilterMode = 0",
        "LogLevel = 2",
        f'AuthServiceId = "{ASP_ID}"',
        f"ResourceIds = [{names}]",
        "",
    ])


def _pub(keys, role: str) -> str:
    role_keys = keys.get(role) or {}
    if isinstance(role_keys, str):
        return role_keys
    return role_keys.get("public", "")


def _peer_files(keys) -> dict[str, str]:
    """NHP peer tables. Hosts are compose DNS names, never operator addresses.

    auth is not an NHP UDP peer. The server plugin reaches it at AUTH_URL,
    whose host is the compose DNS name "auth".
    """
    server_pub = _pub(keys, "server")
    gateway_pub = _pub(keys, "gateway")
    relay_pub = _pub(keys, "relay")
    return {
        "gateway/etc/server.toml": _ac_server_toml(server_pub),
        "server/etc/ac.toml": _server_ac_toml(gateway_pub),
        "server/etc/relay.toml": _server_relay_toml(relay_pub),
        "relay/etc/config.toml": _relay_config_toml(server_pub, _priv(keys, "relay")),
    }


def _ac_server_toml(server_pub: str) -> str:
    return "\n".join([
        "# NHP-AC upstream server. Compose DNS name, not an operator address.",
        *_nhp_server_peer("server", server_pub),
    ])


def _server_ac_toml(gateway_pub: str) -> str:
    return "\n".join([
        "# NHP-Server AC peer. Compose DNS name gateway.",
        "# Auth HTTP is not an NHP peer; the plugin POSTs to",
        f"# {AUTH_URL} (compose DNS \"auth\").",
        "[[ACs]]",
        'Hostname = "gateway"',
        f'PubKeyBase64 = "{gateway_pub}"',
        f"ExpireTime = {PEER_EXPIRE}",
        "",
    ])


def _server_relay_toml(relay_pub: str) -> str:
    return "\n".join([
        "# Optional NHP-Relay peer. Compose DNS name relay.",
        "[[Relays]]",
        'Hostname = "relay"',
        f'PubKeyBase64 = "{relay_pub}"',
        f"ExpireTime = {PEER_EXPIRE}",
        "",
    ])


def _relay_config_toml(server_pub: str, private: str = "") -> str:
    return "\n".join([
        'listenIp = "0.0.0.0"',
        "listenPort = 8080",
        "enableTLS = false",
        "cipherScheme = 0",
        f'privateKeyBase64 = "{private}"',
        "keepaliveIntervalS = 20",
        "logLevel = 2",
        "",
        *_nhp_server_peer("server", server_pub),
    ])


def _nhp_server_peer(name: str, public: str) -> list[str]:
    return [
        "[[Servers]]",
        f'Name = "{name}"',
        f'PubKeyBase64 = "{public}"',
        f"ExpireTime = {PEER_EXPIRE}",
        "",
        "  [[Servers.Instances]]",
        f'  Host = "{name}"',
        f"  Port = {SERVER_LISTEN_PORT}",
        "  Weight = 1",
        "",
    ]


def _plugin_resource(config: OperatorConfig) -> str:
    lines = [
        "# Client-facing resource. Addr is the public host and port.",
        "# Backend addresses are not written here.",
        "# Open address source: endpoints/server/udpserver.go handleNhpOpenResource",
        "# uses info.Addr for the AC destination and DestHost() for the ACK.",
        "",
    ]
    for resource in config.resources:
        lines.append(f'["{resource.name}"]')
        lines.append(f"OpenTime = {config.window_seconds}")
        lines.append("SkipAuth = false")
        lines.append("")
        for forward in resource.forwards:
            sub = f"{forward.protocol}-{forward.public_port}"
            lines.append(f'["{resource.name}".Resources."{sub}"]')
            lines.append(f'ACId = "{AC_ID}"')
            lines.append(f'Hostname = "{forward.public_host}"')
            lines.append(f'Addr.Ip = "{forward.public_host}"')
            lines.append(f"Addr.Port = {forward.public_port}")
            lines.append(f'Addr.Protocol = "{forward.protocol}"')
            # DestHost includes the port so the client can connect.
            lines.append("PortSuffix = true")
            lines.append("MaskHost = false")
            lines.append("")
    return "\n".join(lines)


def _forward_table(config: OperatorConfig) -> str:
    """Gateway-only map. The client-facing resource file does not include this."""
    lines = [
        "# Gateway forward table. Not sent to the client.",
        "# public_port is dialed onward to backend_host:backend_port.",
        "",
    ]
    for resource in config.resources:
        for forward in resource.forwards:
            lines.append("[[forwards]]")
            lines.append(f'name = "{resource.name}"')
            lines.append(f"public_port = {forward.public_port}")
            lines.append(f'backend_host = "{forward.backend_host}"')
            lines.append(f"backend_port = {forward.backend_port}")
            lines.append(f'protocol = "{forward.protocol}"')
            lines.append("")
    return "\n".join(lines)
