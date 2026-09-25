"""Library exceptions."""

from __future__ import annotations


class AtmosError(Exception):
    """Base error for py-atmos-wg1000."""


class ProtocolError(AtmosError):
    """A frame or payload does not match the WG1000 protocol."""


class NotConnectedError(AtmosError):
    """A request was made before the WebSocket was open."""
