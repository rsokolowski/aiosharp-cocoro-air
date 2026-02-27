"""OAuth2/HMS authentication flow for Sharp COCORO Air EU."""

from __future__ import annotations

import logging
import secrets
import string
import urllib.parse

import aiohttp

from .exceptions import SharpAuthError, SharpConnectionError

_LOGGER = logging.getLogger(__name__)

AUTH_BASE = "https://auth-eu.global.sharp"
CLIENT_ID = "8c7f4378-5f26-4618-9854-483ad86bec0a"
REDIRECT_URI = "sharp-cocoroair-eu://authorize"
BROWSER_UA = (
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Mobile"
)

_MAX_REDIRECTS = 10
_CUSTOM_SCHEME = "sharp-cocoroair-eu://"


async def async_obtain_auth_code(email: str, password: str) -> tuple[str, str]:
    """Perform OAuth2 login and return (auth_code, nonce).

    Creates a temporary aiohttp session, navigates the OAuth login form,
    and captures the auth code from the custom-scheme redirect.
    """
    nonce = _generate_nonce()
    auth_params = urllib.parse.urlencode(
        {
            "scope": "openid profile email",
            "client_id": CLIENT_ID,
            "response_type": "code",
            "redirect_uri": REDIRECT_URI,
            "nonce": nonce,
            "ui_locales": "en",
            "prompt": "login",
        }
    )
    auth_url = f"{AUTH_BASE}/oxauth/restv1/authorize?{auth_params}"

    jar = aiohttp.CookieJar(unsafe=True)
    timeout = aiohttp.ClientTimeout(total=30)

    try:
        async with aiohttp.ClientSession(cookie_jar=jar, timeout=timeout) as session:
            # Step 1: GET authorize endpoint — collects cookies
            async with session.get(
                auth_url,
                headers={"User-Agent": BROWSER_UA},
                allow_redirects=True,
            ) as resp:
                await resp.read()

            # Step 2: POST login form
            form_data = {
                "loginForm": "loginForm",
                "javax.faces.ViewState": "stateless",
                "loginForm:username": email,
                "loginForm:password": password,
                "loginForm:loginButton": "",
            }
            redirect_url = await _follow_redirects_until_custom_scheme(
                session,
                f"{AUTH_BASE}/oxauth/login.htm",
                form_data,
                referer=auth_url,
            )
    except aiohttp.ClientError as err:
        raise SharpConnectionError(f"OAuth connection failed: {err}") from err

    if not redirect_url:
        raise SharpAuthError("OAuth login failed — invalid credentials")

    parsed = urllib.parse.urlparse(redirect_url)
    params = urllib.parse.parse_qs(parsed.query)
    auth_code = params.get("code", [None])[0]
    if not auth_code:
        raise SharpAuthError("No auth code in redirect URL")

    return auth_code, nonce


def _generate_nonce(length: int = 32) -> str:
    """Generate a cryptographically secure random alphanumeric nonce."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


async def _follow_redirects_until_custom_scheme(
    session: aiohttp.ClientSession,
    url: str,
    form_data: dict[str, str],
    referer: str,
) -> str | None:
    """POST form_data, then follow redirects until the custom scheme is hit.

    Returns the custom-scheme URL or None if no custom-scheme redirect found.
    """
    headers = {
        "User-Agent": BROWSER_UA,
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": referer,
    }

    current_url = url
    async with session.post(
        url,
        data=form_data,
        headers=headers,
        allow_redirects=False,
    ) as resp:
        location = resp.headers.get("Location", "")
        if location.startswith(_CUSTOM_SCHEME):
            return location
        # Resolve relative redirects against the current URL
        if location:
            location = urllib.parse.urljoin(current_url, location)

    # Follow redirect chain manually
    for _ in range(_MAX_REDIRECTS):
        if not location:
            return None

        current_url = location
        async with session.get(
            location,
            headers={"User-Agent": BROWSER_UA},
            allow_redirects=False,
        ) as resp:
            location = resp.headers.get("Location", "")
            if location.startswith(_CUSTOM_SCHEME):
                return location
            # Resolve relative redirects against the current URL
            if location:
                location = urllib.parse.urljoin(current_url, location)

    _LOGGER.warning("OAuth redirect limit reached (%d)", _MAX_REDIRECTS)
    return None
