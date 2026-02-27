"""Exceptions for the Sharp COCORO Air API client."""


class SharpAuthError(Exception):
    """Authentication failed."""


class SharpConnectionError(Exception):
    """Network/connection error."""


class SharpApiError(Exception):
    """General API error."""
