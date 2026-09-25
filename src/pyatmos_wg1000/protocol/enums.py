"""Wire enumerations taken from the WG1000 web UI."""

from __future__ import annotations

from enum import IntEnum


class Channel(IntEnum):
    """Command channel (``WS_ID`` in the gateway UI)."""

    WS = 0
    PAGE_BODY = 1
    PAGE_NAV = 2
    PAGE_PARAM = 3
    PAGE_DATA = 4


class CommandCode(IntEnum):
    """Command code (``WS_CMD`` in the gateway UI)."""

    HELLO = 0
    CLOSE = 1
    FILE = 2
    LOGIN = 3
    PARAM = 4
    DATA = 5


class ParamAccess(IntEnum):
    """First byte of a parameter payload (``WS_PRM``)."""

    READ = 0
    WRITE = 1


class ParamType(IntEnum):
    """Per-register type byte in a parameter read response.

    ``UNAVAILABLE`` was observed on regulator registers before login.
    The stock UI does not decode it; the width is the same as ``HIDDEN``
    (no value bytes follow).
    """

    HIDDEN = 0
    READ_ONLY = 1
    EDITABLE = 2
    UNAVAILABLE = 0xFF


class LoginAction(IntEnum):
    """First byte of a login payload (``WS_LOGIN``)."""

    LOGIN = 0
    LOGOUT = 1
    EDIT = 2


class LoginRole(IntEnum):
    """Session role reported by Hello and by a successful login (``LOGIN``)."""

    LOGGED_OUT = 0
    USER = 1
    TECHNICIAN = 2


class FileOp(IntEnum):
    """File-transfer operation (``WS_FILE``)."""

    REQUEST = 0
    GET = 1
    ACK = 2


class DataKind(IntEnum):
    """Page-data payload kind (``WS_DATA``)."""

    OWN_TEXT = 0
    SCHEDULE = 1
    CRC = 2
    INFO = 3
