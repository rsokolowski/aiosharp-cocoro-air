# aiosharp-cocoro-air — Async Python Client for Sharp COCORO Air EU

## What This Is

Standalone async Python library for the Sharp COCORO Air EU cloud API. Designed to be used by the Home Assistant core integration but has no HA dependencies.

## Architecture

### Module Layout
- `api.py` — Main `SharpCOCOROAir` client class (async context manager)
- `auth.py` — OAuth2 login flow + HMS authentication
- `echonet.py` — ECHONET Lite TLV property decoder
- `models.py` — Dataclasses for devices, properties, control commands
- `exceptions.py` — `SharpAuthError`, `SharpConnectionError`, `SharpApiError`

### Public API Target
```python
async with SharpCOCOROAir(email, password, session=aiohttp_session) as client:
    await client.authenticate()       # login + register terminal + pair boxes
    devices = await client.get_devices()
    await client.power_on(device)
    await client.set_mode(device, "auto")
    await client.set_humidify(device, True)
```

### Key Design Decisions
- **aiohttp, not httpx**: HA core uses aiohttp; keep dependency minimal
- **Accept optional `aiohttp.ClientSession`**: HA passes its shared session; standalone use creates one
- **No HA imports**: Pure Python + aiohttp only
- **Exceptions map to HA patterns**: `SharpAuthError` → `ConfigEntryAuthFailed`, `SharpConnectionError` → `UpdateFailed`

## Background

This library is a direct async rewrite of the sync `httpx`-based API client
from the Sharp COCORO Air HACS custom integration. The OAuth flow replaces
`urllib.request` with `aiohttp` — manually following redirects and stopping
when the `Location` header starts with the custom scheme
(`sharp-cocoroair-eu://authorize`).

## Conventions

- `ruff` for linting and formatting (config in pyproject.toml)
- `pytest` + `pytest-asyncio` + `aioresponses` for tests
- src layout: `src/aiosharp_cocoro_air/`
- Type hints on all public API methods
