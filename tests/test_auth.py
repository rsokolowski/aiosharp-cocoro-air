"""Tests for OAuth2 authentication flow."""

from __future__ import annotations

import re

import aiohttp
import pytest
from aioresponses import aioresponses

from aiosharp_cocoro_air.auth import (
    _MAX_REDIRECTS,
    AUTH_BASE,
    REDIRECT_URI,
    async_obtain_auth_code,
)
from aiosharp_cocoro_air.exceptions import SharpAuthError, SharpConnectionError

# Use regex pattern for authorize URL since aioresponses double-encodes
# the redirect_uri query parameter (sharp-cocoroair-eu://)
AUTHORIZE_PATTERN = re.compile(
    r"^https://auth-eu\.global\.sharp/oxauth/restv1/authorize\?"
)
LOGIN_URL = f"{AUTH_BASE}/oxauth/login.htm"


class TestAsyncObtainAuthCode:
    """Tests for async_obtain_auth_code."""

    @pytest.mark.asyncio
    async def test_happy_path(self):
        """Successful login returns auth_code and nonce."""
        redirect_url = f"{REDIRECT_URI}?code=test-auth-code-123&state=ok"

        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, status=200, repeat=True)
            m.post(LOGIN_URL, status=302, headers={"Location": redirect_url})

            auth_code, nonce = await async_obtain_auth_code(
                "user@example.com", "password123"
            )

        assert auth_code == "test-auth-code-123"
        assert len(nonce) == 32

    @pytest.mark.asyncio
    async def test_redirect_chain(self):
        """Auth code captured after multiple redirects."""
        intermediate_url = f"{AUTH_BASE}/oxauth/intermediate"
        final_url = f"{REDIRECT_URI}?code=chained-code"

        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, status=200, repeat=True)
            m.post(
                LOGIN_URL,
                status=302,
                headers={"Location": intermediate_url},
            )
            m.get(
                intermediate_url,
                status=302,
                headers={"Location": final_url},
            )

            auth_code, _ = await async_obtain_auth_code("u@e.com", "pass")

        assert auth_code == "chained-code"

    @pytest.mark.asyncio
    async def test_bad_credentials_no_redirect(self):
        """When login returns 200 (no redirect), raise SharpAuthError."""
        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, status=200, repeat=True)
            m.post(LOGIN_URL, status=200)

            with pytest.raises(SharpAuthError, match="invalid credentials"):
                await async_obtain_auth_code("bad@example.com", "wrong")

    @pytest.mark.asyncio
    async def test_no_auth_code_in_redirect(self):
        """Custom-scheme redirect without code parameter raises error."""
        redirect_url = f"{REDIRECT_URI}?error=access_denied"

        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, status=200, repeat=True)
            m.post(LOGIN_URL, status=302, headers={"Location": redirect_url})

            with pytest.raises(SharpAuthError, match="No auth code"):
                await async_obtain_auth_code("u@e.com", "pass")

    @pytest.mark.asyncio
    async def test_connection_error(self):
        """Network error raises SharpConnectionError."""
        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, exception=aiohttp.ClientConnectionError())

            with pytest.raises(SharpConnectionError, match="OAuth connection"):
                await async_obtain_auth_code("u@e.com", "pass")

    @pytest.mark.asyncio
    async def test_redirect_loop_protection(self):
        """More than MAX_REDIRECTS without custom scheme returns None -> auth error."""
        loop_url = f"{AUTH_BASE}/oxauth/loop"

        with aioresponses() as m:
            m.get(AUTHORIZE_PATTERN, status=200, repeat=True)
            m.post(LOGIN_URL, status=302, headers={"Location": loop_url})
            for _ in range(_MAX_REDIRECTS + 1):
                m.get(loop_url, status=302, headers={"Location": loop_url})

            with pytest.raises(SharpAuthError, match="invalid credentials"):
                await async_obtain_auth_code("u@e.com", "pass")
