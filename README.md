# opennhp-router

A Docker deployment of OpenNHP. The gateway is an NHP-AC on the host network. It stays closed until an NHP-Server says open, then port-forwards to a backend. An unauthorized SYN to a mapped public port is dropped. The client is never given the backend address.

This is stock OpenNHP. It is not a new protocol.

## What you configure

One file, `router.toml`. Three settings:

- `window_seconds` — how long an open lasts.
- `[[identities]]` — public keys of clients that may knock. There is no registration path.
- `[[resources]]` — a name, and one or more forwards. `public_host` must be an address on this host, or a name that resolves to one. `public_port` is the TCP port the client uses. `backend_host` must be reachable from the host, not a compose service name. `backend_port` is where the gateway dials. A knock names one resource. Other resources stay closed.

Copy `router.example.toml`. Do not paste private keys or peer addresses.

## Run

```
docker compose -f docker/compose.yaml up --build
```

The relay is optional. A relay-profile start trusts the relay. A no-relay start does not wait for it:

```
OPENNHP_REQUIRE_RELAY=1 docker compose -f docker/compose.yaml --profile relay up --build
```

The agent is not part of that stack. The separate compose builds nhp-agentd from this repo and starts it:

```
docker compose -f docker/compose.agent.yaml up --build
```

To replace an image's key, set `OPENNHP_REGENERATE_KEY=1` for that start. A restart without it keeps the key.
