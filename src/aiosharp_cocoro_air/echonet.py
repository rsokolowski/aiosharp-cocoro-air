"""ECHONET Lite property decoder for Sharp device data."""

from __future__ import annotations

OPERATION_MODES: dict[int, str] = {
    0x10: "Auto",
    0x11: "Night",
    0x13: "Pollen",
    0x14: "Silent",
    0x15: "Medium",
    0x16: "High",
    0x20: "AI Auto",
    0x40: "Realize",
}

CLEANING_MODES: dict[int, str] = {
    0x41: "Cleaning",
    0x42: "Humidifying",
    0x43: "Cleaning + Humidifying",
    0x44: "Off",
}


def decode_echonet_property(hex_string: str) -> dict[str, str | int | bool]:
    """Decode ECHONET Lite property hex from the Sharp cloud API.

    Parses TLV-encoded property blobs returned in ``echonetProperty`` fields.
    Returns a flat dict of decoded sensor/state values.
    """
    if not hex_string or len(hex_string) < 16:
        return {}

    data = bytes.fromhex(hex_string)

    # Parse TLV properties starting at byte 8 (after header)
    raw_props: dict[int, bytes] = {}
    i = 8
    while i + 1 < len(data):
        code = data[i]
        length = data[i + 1]
        if i + 2 + length > len(data):
            break
        raw_props[code] = data[i + 2 : i + 2 + length]
        i += 2 + length

    result: dict[str, str | int | bool] = {}

    # 0x80: Power status
    if 0x80 in raw_props:
        v = raw_props[0x80][0]
        result["power"] = "on" if v == 0x30 else "off" if v == 0x31 else f"0x{v:02X}"

    # 0x84: Instantaneous power consumption (W)
    if 0x84 in raw_props:
        result["power_watts"] = int.from_bytes(raw_props[0x84], "big")

    # 0x85: Cumulative energy (Wh)
    if 0x85 in raw_props:
        result["energy_wh"] = int.from_bytes(raw_props[0x85], "big")

    # 0x88: Fault status
    if 0x88 in raw_props:
        v = raw_props[0x88][0]
        result["fault"] = v == 0x41

    # 0x8B: Firmware version (ASCII)
    if 0x8B in raw_props:
        result["firmware"] = raw_props[0x8B].decode("ascii", errors="replace")

    # 0xA0: Air flow rate
    if 0xA0 in raw_props:
        v = raw_props[0xA0][0]
        result["airflow"] = (
            "auto"
            if v == 0x41
            else f"level_{v - 0x30}"
            if 0x31 <= v <= 0x38
            else f"0x{v:02X}"
        )

    # 0xC0: Cleaning mode
    if 0xC0 in raw_props:
        v = raw_props[0xC0][0]
        result["cleaning_mode"] = CLEANING_MODES.get(v, f"0x{v:02X}")

    # 0xF1: State detail (Sharp proprietary - 40 bytes)
    if 0xF1 in raw_props:
        f1 = raw_props[0xF1]
        if len(f1) >= 5:
            result["temperature_c"] = int.from_bytes(bytes([f1[3]]), "big", signed=True)
            result["humidity_pct"] = f1[4]
        if len(f1) >= 38:
            result["pci_sensor"] = (f1[15] << 8) | f1[16]
            result["filter_usage"] = (
                (f1[21] << 24) | (f1[22] << 16) | (f1[23] << 8) | f1[24]
            )
            result["dust"] = (f1[29] << 8) | f1[30]
            result["smell"] = (f1[31] << 8) | f1[32]
            result["humidity_filter"] = (f1[35] << 8) | f1[36]
            result["light_sensor"] = f1[37]

    # 0xF3: Operation mode (Sharp proprietary - 27 bytes)
    if 0xF3 in raw_props:
        f3 = raw_props[0xF3]
        if len(f3) >= 5:
            result["operation_mode"] = OPERATION_MODES.get(f3[4], f"0x{f3[4]:02X}")
        if len(f3) >= 16:
            result["humidify"] = f3[15] == 0xFF

    return result
