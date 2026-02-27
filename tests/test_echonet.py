"""Tests for ECHONET Lite property decoder."""

from __future__ import annotations

from aiosharp_cocoro_air.echonet import (
    CLEANING_MODES,
    OPERATION_MODES,
    decode_echonet_property,
)


def _build_hex(*tlvs: tuple[int, bytes], header: bytes = b"\x00" * 8) -> str:
    """Build an ECHONET hex string from (code, value) tuples."""
    buf = bytearray(header)
    for code, value in tlvs:
        buf.append(code)
        buf.append(len(value))
        buf.extend(value)
    return buf.hex()


class TestDecodeEchonetProperty:
    """Tests for decode_echonet_property."""

    def test_empty_string(self):
        assert decode_echonet_property("") == {}

    def test_short_string(self):
        assert decode_echonet_property("0102030405") == {}

    def test_none_input(self):
        assert decode_echonet_property(None) == {}

    def test_power_on(self):
        hex_str = _build_hex((0x80, b"\x30"))
        result = decode_echonet_property(hex_str)
        assert result["power"] == "on"

    def test_power_off(self):
        hex_str = _build_hex((0x80, b"\x31"))
        result = decode_echonet_property(hex_str)
        assert result["power"] == "off"

    def test_power_unknown(self):
        hex_str = _build_hex((0x80, b"\xff"))
        result = decode_echonet_property(hex_str)
        assert result["power"] == "0xFF"

    def test_power_watts(self):
        hex_str = _build_hex((0x84, b"\x00\x0a"))  # 10W
        result = decode_echonet_property(hex_str)
        assert result["power_watts"] == 10

    def test_energy_wh(self):
        hex_str = _build_hex((0x85, b"\x00\x00\x03\xe8"))  # 1000 Wh
        result = decode_echonet_property(hex_str)
        assert result["energy_wh"] == 1000

    def test_fault_active(self):
        hex_str = _build_hex((0x88, b"\x41"))
        result = decode_echonet_property(hex_str)
        assert result["fault"] is True

    def test_fault_inactive(self):
        hex_str = _build_hex((0x88, b"\x42"))
        result = decode_echonet_property(hex_str)
        assert result["fault"] is False

    def test_firmware(self):
        hex_str = _build_hex((0x8B, b"v1.23"))
        result = decode_echonet_property(hex_str)
        assert result["firmware"] == "v1.23"

    def test_airflow_auto(self):
        hex_str = _build_hex((0xA0, b"\x41"))
        result = decode_echonet_property(hex_str)
        assert result["airflow"] == "auto"

    def test_airflow_level(self):
        hex_str = _build_hex((0xA0, b"\x33"))  # level 3
        result = decode_echonet_property(hex_str)
        assert result["airflow"] == "level_3"

    def test_airflow_unknown(self):
        hex_str = _build_hex((0xA0, b"\x00"))
        result = decode_echonet_property(hex_str)
        assert result["airflow"] == "0x00"

    def test_cleaning_mode(self):
        hex_str = _build_hex((0xC0, b"\x43"))
        result = decode_echonet_property(hex_str)
        assert result["cleaning_mode"] == "Cleaning + Humidifying"

    def test_cleaning_mode_unknown(self):
        hex_str = _build_hex((0xC0, b"\xff"))
        result = decode_echonet_property(hex_str)
        assert result["cleaning_mode"] == "0xFF"

    def test_f1_temperature_humidity(self):
        # F1: 5 bytes minimum → temp at [3], humidity at [4]
        f1_data = bytes([0, 0, 0, 24, 55])  # 24°C, 55%
        hex_str = _build_hex((0xF1, f1_data))
        result = decode_echonet_property(hex_str)
        assert result["temperature_c"] == 24
        assert result["humidity_pct"] == 55

    def test_f1_negative_temperature(self):
        # Signed byte: -5 = 0xFB
        f1_data = bytes([0, 0, 0, 0xFB, 40])
        hex_str = _build_hex((0xF1, f1_data))
        result = decode_echonet_property(hex_str)
        assert result["temperature_c"] == -5

    def test_f1_extended_fields(self):
        # 38 bytes to get all extended fields
        f1_data = bytearray(38)
        f1_data[3] = 20  # temperature_c
        f1_data[4] = 50  # humidity_pct
        f1_data[15] = 0x01  # pci_sensor high
        f1_data[16] = 0x00  # pci_sensor low = 256
        f1_data[21] = 0x00  # filter_usage bytes 21-24
        f1_data[22] = 0x00
        f1_data[23] = 0x0B
        f1_data[24] = 0xB8  # filter_usage = 3000
        f1_data[29] = 0x00  # dust high
        f1_data[30] = 0x05  # dust = 5
        f1_data[31] = 0x00  # smell high
        f1_data[32] = 0x03  # smell = 3
        f1_data[35] = 0x00  # humidity_filter high
        f1_data[36] = 0x0A  # humidity_filter = 10
        f1_data[37] = 42  # light_sensor

        hex_str = _build_hex((0xF1, bytes(f1_data)))
        result = decode_echonet_property(hex_str)
        assert result["temperature_c"] == 20
        assert result["humidity_pct"] == 50
        assert result["pci_sensor"] == 256
        assert result["filter_usage"] == 3000
        assert result["dust"] == 5
        assert result["smell"] == 3
        assert result["humidity_filter"] == 10
        assert result["light_sensor"] == 42

    def test_f3_operation_mode(self):
        # F3: 5 bytes minimum → mode at [4]
        f3_data = bytes([0, 0, 0, 0, 0x10])  # Auto
        hex_str = _build_hex((0xF3, f3_data))
        result = decode_echonet_property(hex_str)
        assert result["operation_mode"] == "Auto"

    def test_f3_humidify_on(self):
        # F3: 16 bytes → humidify at [15]
        f3_data = bytearray(16)
        f3_data[4] = 0x15  # Medium
        f3_data[15] = 0xFF  # humidify on
        hex_str = _build_hex((0xF3, bytes(f3_data)))
        result = decode_echonet_property(hex_str)
        assert result["operation_mode"] == "Medium"
        assert result["humidify"] is True

    def test_f3_humidify_off(self):
        f3_data = bytearray(16)
        f3_data[4] = 0x14  # Silent
        f3_data[15] = 0x00  # humidify off
        hex_str = _build_hex((0xF3, bytes(f3_data)))
        result = decode_echonet_property(hex_str)
        assert result["humidify"] is False

    def test_multiple_properties(self):
        hex_str = _build_hex(
            (0x80, b"\x30"),  # power on
            (0x84, b"\x00\x05"),  # 5W
            (0x88, b"\x42"),  # no fault
        )
        result = decode_echonet_property(hex_str)
        assert result["power"] == "on"
        assert result["power_watts"] == 5
        assert result["fault"] is False

    def test_truncated_tlv(self):
        # TLV says length=5 but only 2 bytes follow → stops parsing
        header = b"\x00" * 8
        buf = bytearray(header)
        buf.append(0x80)  # code
        buf.append(5)  # length 5
        buf.extend(b"\x30\x31")  # only 2 bytes
        result = decode_echonet_property(buf.hex())
        assert result == {}

    def test_all_operation_modes(self):
        for byte_val, name in OPERATION_MODES.items():
            f3_data = bytes([0, 0, 0, 0, byte_val])
            hex_str = _build_hex((0xF3, f3_data))
            result = decode_echonet_property(hex_str)
            assert result["operation_mode"] == name

    def test_all_cleaning_modes(self):
        for byte_val, name in CLEANING_MODES.items():
            hex_str = _build_hex((0xC0, bytes([byte_val])))
            result = decode_echonet_property(hex_str)
            assert result["cleaning_mode"] == name
