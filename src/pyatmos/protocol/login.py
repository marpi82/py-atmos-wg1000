"""Login payload used by the WG1000 web UI.

The byte layout is taken from ``Pages.js``. This module does not contact a gateway.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field

from pyatmos.errors import ProtocolError
from pyatmos.protocol.enums import LoginAction, LoginRole

_USER_FIELD = 32
_PASSWORD_FIELD = 64


class LoginResult(BaseModel):
    """Login command response, as the UI interprets the first two payload bytes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: int = Field(ge=0, le=0xFF)
    blocked: bool
    retry_after_s: int | None = None

    @property
    def logged_in(self) -> bool:
        """Return whether the role is above logged-out."""
        return self.role > LoginRole.LOGGED_OUT


def encode_login(username: str, password: str, *, stay: bool = False, edit: bool = False) -> bytes:
    """Encode a login (or password-edit) payload.

    The UI pads the username to 32 characters and the password to 64 with NUL,
    then SHA-512s the UTF-8 encoding of that concatenation. ASCII credentials
    therefore hash 96 bytes. The payload is the action, the padded username,
    the digest, and the stay-logged-in flag.

    Args:
        username: Account name. At most 32 bytes once encoded as UTF-8.
        password: Password. At most 64 bytes once encoded as UTF-8.
        stay: Ask the gateway to keep the session after the socket closes.
        edit: Send the password-change action instead of login.

    Returns:
        Login-command payload.

    Raises:
        ProtocolError: A field does not fit in its padded width.
    """
    user = _padded(username, _USER_FIELD, "username")
    secret = _padded(password, _PASSWORD_FIELD, "password")
    digest = hashlib.sha512(user + secret).digest()
    action = LoginAction.EDIT if edit else LoginAction.LOGIN
    return bytes((action,)) + user + digest + bytes((1 if stay else 0,))


def parse_login_result(payload: bytes) -> LoginResult:
    """Interpret a login response the way ``Pages.js`` does.

    Args:
        payload: Login-command payload.

    Returns:
        Role, and the lockout fields when the UI would show them.

    Raises:
        ProtocolError: The payload is shorter than two bytes.
    """
    if len(payload) < 2:
        raise ProtocolError("login response needs two bytes")
    role = payload[0]
    status = payload[1]
    if role > LoginRole.LOGGED_OUT or status == 0xFF:
        return LoginResult(role=role, blocked=False, retry_after_s=None)
    return LoginResult(role=role, blocked=bool(status & 0x01), retry_after_s=status >> 1)


def _padded(text: str, width: int, label: str) -> bytes:
    raw = text.encode("utf-8")
    if len(raw) > width:
        raise ProtocolError(f"{label} is longer than {width} bytes")
    return raw.ljust(width, b"\x00")
