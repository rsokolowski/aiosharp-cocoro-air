"""Tests for data models."""

from __future__ import annotations

import pytest

from aiosharp_cocoro_air.echonet import decode_echonet_property
from aiosharp_cocoro_air.models import Device, DeviceProperties


class TestDeviceProperties:
    """Tests for DeviceProperties dataclass."""

    def test_defaults_are_none(self):
        props = DeviceProperties()
        assert props.power is None
        assert props.temperature_c is None
        assert props.humidify is None

    def test_construct_with_kwargs(self):
        props = DeviceProperties(power="on", temperature_c=22, humidity_pct=45)
        assert props.power == "on"
        assert props.temperature_c == 22
        assert props.humidity_pct == 45

    def test_frozen(self):
        props = DeviceProperties(power="on")
        with pytest.raises(AttributeError):
            props.power = "off"  # type: ignore[misc]

    def test_splat_from_decoder(self):
        """DeviceProperties(**decoded_dict) should work directly."""
        decoded = {
            "power": "on",
            "power_watts": 7,
            "fault": False,
            "temperature_c": 22,
            "humidity_pct": 45,
        }
        props = DeviceProperties(**decoded)
        assert props.power == "on"
        assert props.power_watts == 7
        assert props.fault is False
        assert props.temperature_c == 22
        assert props.humidity_pct == 45
        # Unset fields remain None
        assert props.firmware is None
        assert props.humidify is None


class TestDevice:
    """Tests for Device dataclass."""

    def test_required_fields(self):
        dev = Device(
            box_id="box-1",
            device_id="dev-1",
            name="Purifier",
            echonet_node="01",
            echonet_object="3A01",
        )
        assert dev.box_id == "box-1"
        assert dev.name == "Purifier"
        assert dev.maker is None
        assert dev.properties == DeviceProperties()

    def test_with_properties(self):
        props = DeviceProperties(power="off", temperature_c=18)
        dev = Device(
            box_id="box-1",
            device_id="dev-1",
            name="Purifier",
            echonet_node="01",
            echonet_object="3A01",
            properties=props,
        )
        assert dev.properties.power == "off"
        assert dev.properties.temperature_c == 18

    def test_frozen(self):
        dev = Device(
            box_id="box-1",
            device_id="dev-1",
            name="Purifier",
            echonet_node="01",
            echonet_object="3A01",
        )
        with pytest.raises(AttributeError):
            dev.name = "Other"  # type: ignore[misc]

    def test_all_optional_fields(self):
        dev = Device(
            box_id="box-1",
            device_id="dev-1",
            name="Purifier",
            echonet_node="01",
            echonet_object="3A01",
            maker="SHARP",
            model="KI-ND50",
            updated_at="2024-01-15T10:00:00Z",
        )
        assert dev.maker == "SHARP"
        assert dev.model == "KI-ND50"
        assert dev.updated_at == "2024-01-15T10:00:00Z"

    def test_integration_with_decoder(self):
        """Full round-trip: hex → decode → DeviceProperties → Device."""
        # Build a minimal ECHONET hex with power=on
        header = b"\x00" * 8
        buf = bytearray(header)
        buf.extend(b"\x80\x01\x30")  # power on
        decoded = decode_echonet_property(buf.hex())
        props = DeviceProperties(**decoded)
        dev = Device(
            box_id="box-1",
            device_id="dev-1",
            name="Test",
            echonet_node="01",
            echonet_object="3A01",
            properties=props,
        )
        assert dev.properties.power == "on"
