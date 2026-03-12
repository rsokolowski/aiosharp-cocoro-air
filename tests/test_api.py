"""Tests for the async API client."""

from __future__ import annotations

import urllib.parse
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest
from aioresponses import aioresponses

from aiosharp_cocoro_air.api import API_BASE, APP_SECRET, SharpCOCOROAir
from aiosharp_cocoro_air.exceptions import (
    SharpApiError,
    SharpAuthError,
    SharpConnectionError,
)
from aiosharp_cocoro_air.models import Device, DeviceProperties

from .conftest import BOX_INFO_RESPONSE

_BASE = API_BASE


def _url(path: str, **extra: str) -> str:
    """Build a full HMS API URL with appSecret and extra params (URL-encoded)."""
    params: dict[str, str] = {"appSecret": APP_SECRET}
    params.update(extra)
    return f"{_BASE}{path}?{urllib.parse.urlencode(params)}"


def _pairing_url(**params: str) -> str:
    """Build a pairing URL with URL-encoded parameters."""
    return f"{_BASE}setting/pairing/?{urllib.parse.urlencode(params)}"


class TestHmsRequest:
    """Tests for _hms_request error handling."""

    @pytest.mark.asyncio
    async def test_auth_error_401(self):
        with aioresponses() as m:
            m.get(_url("setting/test"), status=401, body="Unauthorized")

            async with SharpCOCOROAir("u@e.com", "p") as client:
                with pytest.raises(SharpAuthError, match="401"):
                    await client._hms_request("setting/test")

    @pytest.mark.asyncio
    async def test_auth_error_403(self):
        with aioresponses() as m:
            m.get(_url("setting/test"), status=403, body="Forbidden")

            async with SharpCOCOROAir("u@e.com", "p") as client:
                with pytest.raises(SharpAuthError, match="403"):
                    await client._hms_request("setting/test")

    @pytest.mark.asyncio
    async def test_api_error_500(self):
        with aioresponses() as m:
            m.get(_url("setting/test"), status=500, body="Internal Error")

            async with SharpCOCOROAir("u@e.com", "p") as client:
                with pytest.raises(SharpApiError, match="500"):
                    await client._hms_request("setting/test")

    @pytest.mark.asyncio
    async def test_connection_error(self):
        with aioresponses() as m:
            m.get(
                _url("setting/test"),
                exception=aiohttp.ClientConnectionError(),
            )

            async with SharpCOCOROAir("u@e.com", "p") as client:
                with pytest.raises(SharpConnectionError, match="Connection"):
                    await client._hms_request("setting/test")

    @pytest.mark.asyncio
    async def test_successful_get(self):
        with aioresponses() as m:
            m.get(
                _url("setting/test"),
                status=200,
                payload={"key": "value"},
            )

            async with SharpCOCOROAir("u@e.com", "p") as client:
                result = await client._hms_request("setting/test")

        assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_extra_params(self):
        url = _url("setting/userInfo", terminalAppId="tai-123")
        with aioresponses() as m:
            m.get(url, status=200, payload={"user": "info"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                result = await client._hms_request(
                    "setting/userInfo",
                    extra_params={"terminalAppId": "tai-123"},
                )

        assert result == {"user": "info"}


class TestAuthenticate:
    """Tests for the full authenticate() flow."""

    @pytest.mark.asyncio
    @patch("aiosharp_cocoro_air.api.async_obtain_auth_code")
    async def test_full_authenticate(self, mock_auth: AsyncMock):
        mock_auth.return_value = ("auth-code-xyz", "nonce-abc")

        terminal_url = (
            f"{_BASE}setting/terminal?"
            f"{urllib.parse.urlencode({'appSecret': APP_SECRET})}"
        )

        with aioresponses() as m:
            # Step 1: terminalAppId
            m.get(
                _url("setting/terminalAppId/"),
                payload={"terminalAppId": "tai-001"},
            )
            # Step 3: HMS login
            m.post(
                _url("setting/login/", serviceName="sharp-eu"),
                payload={"status": "ok"},
            )
            # Step 4: userInfo
            m.get(
                _url("setting/userInfo", terminalAppId="tai-001"),
                payload={"userId": "uid-001", "mailAddr": "u@e.com"},
            )
            # Step 5: register terminal
            m.post(terminal_url, payload={"status": "ok"})
            # Step 6: pair boxes — boxInfo returns empty
            m.get(
                _url("setting/boxInfo", mode="other"),
                payload={"box": []},
            )

            async with SharpCOCOROAir("u@e.com", "pass") as client:
                await client.authenticate()

            assert client._terminal_app_id == "tai-001"
            assert client.user_id == "uid-001"
            mock_auth.assert_awaited_once_with("u@e.com", "pass")


class TestGetDevices:
    """Tests for get_devices()."""

    @pytest.mark.asyncio
    async def test_get_devices_parses_response(self):
        with aioresponses() as m:
            m.get(
                _url("setting/boxInfo", mode="other"),
                payload=BOX_INFO_RESPONSE,
            )

            async with SharpCOCOROAir("u@e.com", "p") as client:
                devices = await client.get_devices()

        assert len(devices) == 1
        dev = devices[0]
        assert isinstance(dev, Device)
        assert dev.box_id == "box-001"
        assert dev.device_id == "dev-001"
        assert dev.name == "Living Room Purifier"
        assert dev.maker == "SHARP"
        assert dev.model == "KI-ND50"
        assert dev.echonet_node == "01"
        assert dev.echonet_object == "3A01"
        assert isinstance(dev.properties, DeviceProperties)
        assert dev.properties.power == "on"
        assert dev.properties.operation_mode == "Auto"
        assert dev.properties.humidify is True

    @pytest.mark.asyncio
    async def test_get_devices_empty(self):
        with aioresponses() as m:
            m.get(
                _url("setting/boxInfo", mode="other"),
                payload={"box": []},
            )

            async with SharpCOCOROAir("u@e.com", "p") as client:
                devices = await client.get_devices()

        assert devices == []


class TestControlCommands:
    """Tests for power_on, power_off, set_mode, set_humidify."""

    @pytest.mark.asyncio
    async def test_power_on(self, sample_device: Device):
        url = _url(
            "control/deviceControl",
            boxId="box-001",
            terminalAppId="tai-001",
        )
        with aioresponses() as m:
            m.post(url, payload={"status": "ok"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                client._terminal_app_id = "tai-001"
                await client.power_on(sample_device)

        assert len(m.requests) == 1

    @pytest.mark.asyncio
    async def test_power_off(self, sample_device: Device):
        url = _url(
            "control/deviceControl",
            boxId="box-001",
            terminalAppId="tai-001",
        )
        with aioresponses() as m:
            m.post(url, payload={"status": "ok"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                client._terminal_app_id = "tai-001"
                await client.power_off(sample_device)

        assert len(m.requests) == 1

    @pytest.mark.asyncio
    async def test_set_mode_auto(self, sample_device: Device):
        url = _url(
            "control/deviceControl",
            boxId="box-001",
            terminalAppId="tai-001",
        )
        with aioresponses() as m:
            m.post(url, payload={"status": "ok"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                client._terminal_app_id = "tai-001"
                await client.set_mode(sample_device, "auto")

        assert len(m.requests) == 1

    @pytest.mark.asyncio
    async def test_set_mode_invalid(self, sample_device: Device):
        async with SharpCOCOROAir("u@e.com", "p") as client:
            client._terminal_app_id = "tai-001"
            with pytest.raises(ValueError, match="Unknown mode"):
                await client.set_mode(sample_device, "turbo")

    @pytest.mark.asyncio
    async def test_set_humidify_on(self, sample_device: Device):
        url = _url(
            "control/deviceControl",
            boxId="box-001",
            terminalAppId="tai-001",
        )
        with aioresponses() as m:
            m.post(url, payload={"status": "ok"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                client._terminal_app_id = "tai-001"
                await client.set_humidify(sample_device, True)

        assert len(m.requests) == 1

    @pytest.mark.asyncio
    async def test_set_humidify_off(self, sample_device: Device):
        url = _url(
            "control/deviceControl",
            boxId="box-001",
            terminalAppId="tai-001",
        )
        with aioresponses() as m:
            m.post(url, payload={"status": "ok"})

            async with SharpCOCOROAir("u@e.com", "p") as client:
                client._terminal_app_id = "tai-001"
                await client.set_humidify(sample_device, False)

        assert len(m.requests) == 1

    @pytest.mark.asyncio
    async def test_unauthenticated_control_raises(self, sample_device: Device):
        """Calling control methods before authenticate() raises SharpAuthError."""
        async with SharpCOCOROAir("u@e.com", "p") as client:
            with pytest.raises(SharpAuthError, match="Not authenticated"):
                await client.power_on(sample_device)


class TestSessionManagement:
    """Tests for session ownership and lifecycle."""

    @pytest.mark.asyncio
    async def test_owned_session_closed(self):
        """When no session is passed, close() destroys the internal one."""
        client = SharpCOCOROAir("u@e.com", "p")
        assert client._owned_session is True
        session = client._ensure_session()
        assert session is not None
        assert not session.closed
        await client.close()
        assert session.closed

    @pytest.mark.asyncio
    async def test_external_session_not_closed(self):
        """When an external session is passed, close() is a no-op."""
        external = aiohttp.ClientSession()
        client = SharpCOCOROAir("u@e.com", "p", session=external)
        assert client._owned_session is False
        await client.close()
        assert not external.closed
        await external.close()

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """async with creates and closes the session."""
        async with SharpCOCOROAir("u@e.com", "p") as client:
            session = client._ensure_session()
            assert not session.closed
        assert session.closed


class TestPairBoxes:
    """Tests for box pairing during authenticate."""

    @pytest.mark.asyncio
    @patch("aiosharp_cocoro_air.api.async_obtain_auth_code")
    async def test_pair_cleans_stale_tais(self, mock_auth: AsyncMock):
        """Stale HA TAIs are cleaned up, phone app TAIs are kept."""
        mock_auth.return_value = ("code", "nonce")

        box_response = {
            "box": [
                {
                    "boxId": "box-001",
                    "terminalAppInfo": [
                        {
                            "terminalAppId": "tai-001",
                            "appName": "spremote_ha_eu:1:0.9.0",
                        },
                        {
                            "terminalAppId": "tai-phone",
                            "appName": "spremote_a_eu:1:2.0.0",
                        },
                        {"terminalAppId": "tai-orphan", "appName": None},
                    ],
                    "echonetData": [],
                }
            ]
        }

        terminal_url = (
            f"{_BASE}setting/terminal?"
            f"{urllib.parse.urlencode({'appSecret': APP_SECRET})}"
        )

        with aioresponses() as m:
            m.get(
                _url("setting/terminalAppId/"),
                payload={"terminalAppId": "tai-new"},
            )
            m.post(
                _url("setting/login/", serviceName="sharp-eu"),
                payload={},
            )
            m.get(
                _url("setting/userInfo", terminalAppId="tai-new"),
                payload={"userId": "uid-new", "mailAddr": "u@e.com"},
            )
            m.post(terminal_url, payload={})
            # boxInfo for pair_boxes
            m.get(
                _url("setting/boxInfo", mode="other"),
                payload=box_response,
            )
            # Unpair stale HA TAI (tai-001)
            m.put(
                _pairing_url(
                    appSecret=APP_SECRET,
                    terminalAppId="tai-001",
                    boxId="box-001",
                    houseFlag="true",
                ),
                payload={},
            )
            # Unpair orphan TAI
            m.put(
                _pairing_url(
                    appSecret=APP_SECRET,
                    terminalAppId="tai-orphan",
                    boxId="box-001",
                    houseFlag="true",
                ),
                payload={},
            )
            # Pair our TAI
            m.post(
                _pairing_url(
                    appSecret=APP_SECRET,
                    boxId="box-001",
                    houseFlag="true",
                ),
                payload={},
            )

            async with SharpCOCOROAir("u@e.com", "p") as client:
                await client.authenticate()

        # Verify: 2 PUTs (unpair stale + orphan) + 1 POST (pair ours)
        # Phone app TAI should NOT have been unpaired
        put_requests = [(k, v) for k, v in m.requests.items() if k[0] == "PUT"]
        assert len(put_requests) == 2
