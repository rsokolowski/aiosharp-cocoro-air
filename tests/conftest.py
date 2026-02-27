"""Shared fixtures for aiosharp-cocoro-air tests."""

from __future__ import annotations

import pytest

from aiosharp_cocoro_air import Device, DeviceProperties


@pytest.fixture
def sample_device() -> Device:
    """A sample device for control command tests."""
    return Device(
        box_id="box-001",
        device_id="dev-001",
        name="Living Room Purifier",
        echonet_node="01",
        echonet_object="3A01",
        maker="SHARP",
        model="KI-ND50",
        properties=DeviceProperties(power="on", temperature_c=22, humidity_pct=45),
    )


# Minimal ECHONET hex with power=on (0x30), temp=22
# Header (8 bytes) + TLV properties
ECHONET_HEX_POWER_ON = (
    "0000000000000000"  # 8-byte header
    "80"
    "01"
    "30"  # 0x80: power=ON
    "84"
    "02"
    "0007"  # 0x84: 7W
    "85"
    "04"
    "00000064"  # 0x85: 100 Wh
    "88"
    "01"
    "42"  # 0x88: no fault
    "A0"
    "01"
    "41"  # 0xA0: airflow=auto
    "C0"
    "01"
    "41"  # 0xC0: Cleaning
    # 0xF1: 38 bytes (indices 0-37)
    "F1"
    "26"
    "0000001600"  # [0-4]: temp=22(0x16), humidity=0
    "00000000000000000000"  # [5-14]: zeros
    "00C8"  # [15-16]: pci_sensor=200
    "00000000"  # [17-20]: zeros
    "00000BB8"  # [21-24]: filter_usage=3000
    "00000000"  # [25-28]: zeros
    "0000"  # [29-30]: dust=0
    "0000"  # [31-32]: smell=0
    "0000"  # [33-34]: zeros
    "0000"  # [35-36]: humidity_filter=0
    "32"  # [37]: light_sensor=50
    # 0xF3: 16 bytes (indices 0-15)
    "F3"
    "10"
    "0000000010"  # [0-4]: mode=Auto(0x10) at index 4
    "00000000000000000000"  # [5-14]: zeros
    "FF"  # [15]: humidify=True
)

# Response payload for boxInfo — used in test_api.py
BOX_INFO_RESPONSE = {
    "box": [
        {
            "boxId": "box-001",
            "terminalAppInfo": [],
            "echonetData": [
                {
                    "deviceId": "dev-001",
                    "echonetNode": "01",
                    "echonetObject": "3A01",
                    "maker": "SHARP",
                    "model": "KI-ND50",
                    "propertyUpdatedAt": "2024-01-15T10:00:00Z",
                    "labelData": {"name": "Living Room Purifier"},
                    "echonetProperty": ECHONET_HEX_POWER_ON,
                }
            ],
        }
    ]
}
