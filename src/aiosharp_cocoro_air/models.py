"""Data models for Sharp COCORO Air devices and properties."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DeviceProperties:
    """Decoded ECHONET Lite sensor/state values for a Sharp device."""

    power: str | None = None
    power_watts: int | None = None
    energy_wh: int | None = None
    fault: bool | None = None
    firmware: str | None = None
    airflow: str | None = None
    cleaning_mode: str | None = None
    temperature_c: int | None = None
    humidity_pct: int | None = None
    pci_sensor: int | None = None
    filter_usage: int | None = None
    dust: int | None = None
    smell: int | None = None
    humidity_filter: int | None = None
    light_sensor: int | None = None
    operation_mode: str | None = None
    humidify: bool | None = None


@dataclass(frozen=True)
class Device:
    """A Sharp air purifier device registered in the COCORO Air cloud."""

    box_id: str
    device_id: str
    name: str
    echonet_node: str
    echonet_object: str
    maker: str | None = None
    model: str | None = None
    updated_at: str | None = None
    properties: DeviceProperties = field(default_factory=DeviceProperties)
