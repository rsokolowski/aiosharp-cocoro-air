# aiosharp-cocoro-air

Async Python client for the Sharp COCORO Air EU cloud API.

Designed as a standalone library for use by the [Home Assistant](https://www.home-assistant.io/) core integration, but has no HA dependencies — pure Python + aiohttp.

## Installation

```bash
pip install aiosharp-cocoro-air
```

## Usage

```python
import aiohttp
from aiosharp_cocoro_air import SharpCOCOROAir

async with SharpCOCOROAir(email, password) as client:
    await client.authenticate()
    devices = await client.get_devices()

    for device in devices:
        print(device.name, device.properties.temperature_c)

    await client.power_on(devices[0])
    await client.set_mode(devices[0], "auto")
    await client.set_humidify(devices[0], True)
```

When used inside Home Assistant, pass the shared session:

```python
async with SharpCOCOROAir(email, password, session=hass_session) as client:
    ...
```

## Supported Devices

Sharp air purifiers sold in Europe that use the Sharp COCORO Air EU cloud (the same backend as the official **Sharp Life AIR EU** mobile app).

> **Note:** This library has only been tested with the **Sharp KI-N52** air purifier. It should work with other Sharp COCORO Air EU devices, but this is unconfirmed. If you have a different model, please open an issue with your results.

## API

### `SharpCOCOROAir(email, password, session=None)`

- `authenticate()` — Full login sequence (OAuth + terminal registration + box pairing)
- `get_devices()` — Returns `list[Device]` with decoded sensor data
- `power_on(device)` / `power_off(device)` — Power control
- `set_mode(device, mode)` — Set operation mode (`auto`, `night`, `pollen`, `silent`, `medium`, `high`, `ai_auto`, `realize`)
- `set_humidify(device, on)` — Toggle humidification

### Models

- **`Device`** — device identity, ECHONET addresses, and decoded properties
- **`DeviceProperties`** — temperature, humidity, power, dust, smell, PCI sensor, filter usage, operation mode, etc.

### Exceptions

- `SharpAuthError` — authentication failed (bad credentials or expired session)
- `SharpConnectionError` — network/connection error
- `SharpApiError` — non-auth API error (4xx/5xx)

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
ruff check src/ tests/
```

## License

MIT
