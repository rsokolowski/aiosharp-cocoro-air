"""Async API client for Sharp COCORO Air EU cloud.

Constants ``APP_SECRET`` and ``API_BASE`` are extracted from the Sharp Life
AIR EU APK (``jp.co.sharp.hms.smartlink.eu``).  If Sharp rotates them a
new library release will be needed.
"""

from __future__ import annotations

import json
import logging
import urllib.parse
from typing import Any

import aiohttp

from .auth import async_obtain_auth_code
from .echonet import decode_echonet_property
from .exceptions import SharpApiError, SharpAuthError, SharpConnectionError
from .models import Device, DeviceProperties

_LOGGER = logging.getLogger(__name__)

# Extracted from APK — see module docstring
APP_SECRET = "pngtfljRoYsJE9NW7opn1t2cXA5MtZDKbwon368hs80="
API_BASE = "https://eu-hms.cloudlabs.sharp.co.jp/hems/pfApi/ta/"
USER_AGENT = (
    "smartlink_v200a_eu Mozilla/5.0 (Linux; Android 14) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Mobile"
)
HA_APP_NAME = "spremote_ha_eu:1:1.0.0"


class SharpCOCOROAir:
    """Async client for the Sharp COCORO Air EU cloud API."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._terminal_app_id: str | None = None

        if session is not None:
            self._session = session
            self._owned_session = False
        else:
            self._session = None  # created lazily in _ensure_session
            self._owned_session = True

    def _ensure_session(self) -> aiohttp.ClientSession:
        """Return the HTTP session, creating one if we own it."""
        if self._session is None:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json; charset=utf-8",
                    "Accept": "application/json",
                },
            )
        return self._session

    async def _hms_request(
        self,
        path: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Make a request to the HMS API."""
        params: dict[str, str] = {"appSecret": APP_SECRET}
        if extra_params:
            params.update(extra_params)
        url = f"{API_BASE}{path}?{urllib.parse.urlencode(params)}"

        session = self._ensure_session()
        try:
            cm = session.get(url) if method == "GET" else session.post(url, json=body)
            async with cm as resp:
                if resp.status in (401, 403):
                    text = await resp.text()
                    raise SharpAuthError(
                        f"Auth error {resp.status} on {path}: {text[:200]}"
                    )
                if resp.status >= 400:
                    text = await resp.text()
                    raise SharpApiError(
                        f"API error {resp.status} on {path}: {text[:200]}"
                    )
                text = await resp.text()
                return json.loads(text) if text else {}
        except aiohttp.ClientError as err:
            raise SharpConnectionError(f"Connection failed: {err}") from err

    async def authenticate(self) -> None:
        """Perform the complete authentication sequence.

        Obtains a terminal app ID, runs the OAuth login flow, registers
        the terminal, and pairs all boxes.
        """
        # Step 1: Get terminalAppId
        data = await self._hms_request("setting/terminalAppId/")
        self._terminal_app_id = data["terminalAppId"]

        # Step 2: OAuth login → auth code + nonce
        auth_code, nonce = await async_obtain_auth_code(self._email, self._password)

        # Step 3: HMS login with auth code + nonce
        body = {
            "terminalAppId": self._terminal_app_id,
            "tempAccToken": auth_code,
            "password": nonce,
        }
        await self._hms_request(
            "setting/login/",
            method="POST",
            body=body,
            extra_params={"serviceName": "sharp-eu"},
        )

        # Step 4: Get user info
        await self._hms_request(
            "setting/userInfo",
            extra_params={"terminalAppId": self._terminal_app_id},
        )

        # Step 5: Register terminal
        await self._register_terminal()

        # Step 6: Pair boxes
        await self._pair_boxes()

    async def _register_terminal(self) -> None:
        """Register terminal info with the server.

        Required before control/ POST endpoints will work.
        """
        body = {
            "name": "HomeAssistant",
            "os": "Android",
            "osVersion": "14",
            "pushId": "",
            "appName": HA_APP_NAME,
        }
        qs = urllib.parse.urlencode({"appSecret": APP_SECRET})
        url = f"{API_BASE}setting/terminal?{qs}"

        session = self._ensure_session()
        try:
            async with await session.post(url, json=body) as resp:
                if resp.status in (401, 403):
                    raise SharpAuthError(
                        f"Terminal registration auth error: {resp.status}"
                    )
                if resp.status != 200:
                    text = await resp.text()
                    raise SharpApiError(
                        f"Terminal registration failed: {resp.status} {text[:200]}"
                    )
        except aiohttp.ClientError as err:
            raise SharpConnectionError(f"Terminal registration failed: {err}") from err

    async def _get_boxes(self) -> dict[str, Any]:
        """List all registered devices (boxes) with full ECHONET data."""
        return await self._hms_request(
            "setting/boxInfo", extra_params={"mode": "other"}
        )

    async def _pair_boxes(self) -> None:
        """Pair our terminalAppId with all boxes.

        Cleans up stale TAIs to stay within the 5-TAI limit.
        """
        session = self._ensure_session()
        boxes = await self._get_boxes()

        for box in boxes.get("box", []):
            box_id = box["boxId"]

            # Clean up stale TAIs
            for tai in box.get("terminalAppInfo", []):
                if tai["terminalAppId"] == self._terminal_app_id:
                    continue  # keep our own
                app_name = tai.get("appName")
                if app_name is not None and not app_name.startswith("spremote_ha_eu"):
                    continue  # keep phone app and other real entries
                unpair_params = urllib.parse.urlencode(
                    {
                        "appSecret": APP_SECRET,
                        "terminalAppId": tai["terminalAppId"],
                        "boxId": box_id,
                        "houseFlag": "true",
                    }
                )
                url = f"{API_BASE}setting/pairing/?{unpair_params}"
                try:
                    async with await session.put(url) as resp:
                        pass  # just fire the request
                except aiohttp.ClientError:
                    _LOGGER.warning("Failed to unpair TAI %s", tai["terminalAppId"])

            # Pair our TAI
            pair_params = urllib.parse.urlencode(
                {
                    "appSecret": APP_SECRET,
                    "boxId": box_id,
                    "houseFlag": "true",
                }
            )
            url = f"{API_BASE}setting/pairing/?{pair_params}"
            try:
                async with await session.post(url, data=b"") as resp:
                    if resp.status not in (200, 201):
                        text = await resp.text()
                        _LOGGER.warning(
                            "Pairing box %s: %s %s",
                            box_id,
                            resp.status,
                            text[:100],
                        )
            except aiohttp.ClientError as err:
                _LOGGER.warning("Failed to pair box %s: %s", box_id, err)

    async def get_devices(self) -> list[Device]:
        """Get parsed device list with decoded sensor data."""
        boxes = await self._get_boxes()
        devices: list[Device] = []
        for box in boxes.get("box", []):
            box_id = box.get("boxId")
            for edev in box.get("echonetData", []):
                label = edev.get("labelData", {})
                props_dict = decode_echonet_property(edev.get("echonetProperty", ""))
                devices.append(
                    Device(
                        box_id=box_id,
                        device_id=edev.get("deviceId"),
                        name=label.get("name", "Sharp Air Purifier"),
                        maker=edev.get("maker"),
                        model=edev.get("model"),
                        echonet_node=edev.get("echonetNode"),
                        echonet_object=edev.get("echonetObject"),
                        updated_at=edev.get("propertyUpdatedAt"),
                        properties=DeviceProperties(**props_dict),
                    )
                )
        return devices

    async def _send_device_control(
        self, device: Device, status_list: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Send a control command to a device."""
        if self._terminal_app_id is None:
            raise SharpAuthError("Not authenticated — call authenticate() first")
        body = {
            "controlList": [
                {
                    "deviceId": device.device_id,
                    "echonetNode": device.echonet_node,
                    "echonetObject": device.echonet_object,
                    "status": status_list,
                }
            ]
        }
        return await self._hms_request(
            "control/deviceControl",
            method="POST",
            body=body,
            extra_params={
                "boxId": device.box_id,
                "terminalAppId": self._terminal_app_id,
            },
        )

    async def power_on(self, device: Device) -> None:
        """Turn device on."""
        await self._send_device_control(
            device,
            [
                {
                    "statusCode": "80",
                    "valueType": "valueSingle",
                    "valueSingle": {"code": "30"},
                },
                {
                    "statusCode": "F3",
                    "valueType": "valueBinary",
                    "valueBinary": {
                        "code": "00030000000000000000000000FF00000000000000000000000000"
                    },
                },
            ],
        )

    async def power_off(self, device: Device) -> None:
        """Turn device off."""
        await self._send_device_control(
            device,
            [
                {
                    "statusCode": "80",
                    "valueType": "valueSingle",
                    "valueSingle": {"code": "31"},
                },
                {
                    "statusCode": "F3",
                    "valueType": "valueBinary",
                    "valueBinary": {
                        "code": "000300000000000000000000000000000000000000000000000000"
                    },
                },
            ],
        )

    async def set_mode(self, device: Device, mode: str) -> None:
        """Set operation mode."""
        mode_codes = {
            "auto": "010100001000000000000000000000000000000000000000000000",
            "night": "010100001100000000000000000000000000000000000000000000",
            "pollen": "010100001300000000000000000000000000000000000000000000",
            "silent": "010100001400000000000000000000000000000000000000000000",
            "medium": "010100001500000000000000000000000000000000000000000000",
            "high": "010100001600000000000000000000000000000000000000000000",
            "ai_auto": "010100002000000000000000000000000000000000000000000000",
            "realize": "010100004000000000000000000000000000000000000000000000",
        }
        code = mode_codes.get(mode)
        if not code:
            raise ValueError(f"Unknown mode '{mode}'. Valid: {', '.join(mode_codes)}")
        await self._send_device_control(
            device,
            [
                {
                    "statusCode": "F3",
                    "valueType": "valueBinary",
                    "valueBinary": {"code": code},
                },
            ],
        )

    async def set_humidify(self, device: Device, on: bool) -> None:
        """Turn humidification on or off."""
        code = (
            "000900000000000000000000000000FF0000000000000000000000"
            if on
            else "000900000000000000000000000000000000000000000000000000"
        )
        await self._send_device_control(
            device,
            [
                {
                    "statusCode": "F3",
                    "valueType": "valueBinary",
                    "valueBinary": {"code": code},
                },
            ],
        )

    async def close(self) -> None:
        """Close the HTTP session if we own it."""
        if self._owned_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> SharpCOCOROAir:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
