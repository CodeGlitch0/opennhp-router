# opennhp-router

A Docker deployment of OpenNHP. The gateway is an NHP-AC. It stays closed until an NHP-Server says open, then port-forwards to a backend. The client is never given the backend address.

This is stock OpenNHP. It is not a new protocol.

## What you configure

One file, `router.toml`. Three settings:

- `window_seconds` — how long an open lasts.
- `[[identities]]` — public keys of clients that may knock. There is no registration path.
- `[[resources]]` — a name, and one or more forwards. `public_host` and `public_port` are what the client uses. `backend_host` and `backend_port` are where the gateway dials. A knock names one resource. Other resources stay closed.

Copy `router.example.toml`. Do not paste private keys or peer addresses.

## Run

```
docker compose -f docker/compose.yaml up --build
```

The relay is optional:

```
docker compose -f docker/compose.yaml --profile relay up --build
```

The agent is not part of that stack. Start it on its own:

```
docker compose -f docker/compose.agent.yaml up
```

To replace an image's key, set `OPENNHP_REGENERATE_KEY=1` for that start. A restart without it keeps the key.
