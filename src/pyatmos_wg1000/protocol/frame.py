"""WG1000 WebSocket frame codec.

Client frames carry a 32-byte session id. Server frames do not.
Both end with the CRC from :mod:`pyatmos_wg1000.protocol.crc`.
"""

from __future__ import annotations

import struct
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.crc import frame_crc, frame_crc_ok

PROTOCOL_VERSION = 1
SESSION_ID_LENGTH = 32
_LENGTH_SIZE = 2
_CRC_SIZE = 4
_COMMAND_HEADER = 6
_MAX_COMMANDS = 255


class Command(BaseModel):
    """One command inside a frame."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    channel: int = Field(ge=0, le=0xFFFF)
    code: int = Field(ge=0, le=0xFFFF)
    payload: bytes = b""


class Frame(BaseModel):
    """A decoded WebSocket binary frame."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int
    session_id: bytes | None = None
    commands: tuple[Command, ...]


def encode_command(channel: int, code: int, payload: bytes = b"") -> bytes:
    """Encode one command, including its length prefix.

    Args:
        channel: ``WS_ID`` channel.
        code: ``WS_CMD`` code.
        payload: Command body. May be empty.

    Returns:
        Little-endian command bytes. The length counts itself.
    """
    body = struct.pack("<HH", channel, code) + payload
    return struct.pack("<H", _COMMAND_HEADER + len(payload)) + body


def encode_client_frame(commands: Sequence[Command], session_id: bytes) -> bytes:
    """Encode a frame sent to the gateway.

    Args:
        commands: One or more commands. The UI usually sends one.
        session_id: 32-byte session id chosen by the client.

    Returns:
        A complete client frame, including CRC.

    Raises:
        ProtocolError: The session id or command list has the wrong size.
    """
    if len(session_id) != SESSION_ID_LENGTH:
        raise ProtocolError(f"session id must be {SESSION_ID_LENGTH} bytes, got {len(session_id)}")
    return _encode_frame(commands, session_id)


def encode_server_frame(commands: Sequence[Command]) -> bytes:
    """Encode a frame as the gateway sends it (no session id).

    Args:
        commands: Commands to place in the frame.

    Returns:
        A complete server frame, including CRC.

    Raises:
        ProtocolError: ``commands`` is empty or longer than 255 entries.
    """
    return _encode_frame(commands, None)


def decode_client_frame(data: bytes) -> Frame:
    """Decode a frame that includes a session id.

    Args:
        data: Complete client frame.

    Returns:
        The decoded frame. ``session_id`` is 32 bytes.

    Raises:
        ProtocolError: The frame is truncated, has a bad CRC, or an unknown version.
    """
    return _decode_frame(data, has_session=True)


def decode_server_frame(data: bytes) -> Frame:
    """Decode a frame received from the gateway.

    Args:
        data: Complete server frame.

    Returns:
        The decoded frame. ``session_id`` is ``None``.

    Raises:
        ProtocolError: The frame is truncated, has a bad CRC, or an unknown version.
    """
    return _decode_frame(data, has_session=False)


def _encode_frame(commands: Sequence[Command], session_id: bytes | None) -> bytes:
    if not commands or len(commands) > _MAX_COMMANDS:
        raise ProtocolError(f"a frame must contain 1..{_MAX_COMMANDS} commands, got {len(commands)}")
    buf = bytearray()
    buf.append(PROTOCOL_VERSION)
    buf += b"\x00\x00"
    if session_id is not None:
        buf += session_id
    buf.append(len(commands))
    for command in commands:
        buf += encode_command(command.channel, command.code, command.payload)
    total = len(buf) + _CRC_SIZE
    buf[1] = total & 0xFF
    buf[2] = (total >> 8) & 0xFF
    payload = bytes(buf)
    return payload + struct.pack("<I", frame_crc(payload))


def _decode_frame(data: bytes, *, has_session: bool) -> Frame:
    header = 1 + _LENGTH_SIZE + (SESSION_ID_LENGTH if has_session else 0) + 1
    minimum = header + _COMMAND_HEADER + _CRC_SIZE
    if len(data) < minimum:
        raise ProtocolError(f"frame is shorter than the minimum {minimum} bytes")
    if not frame_crc_ok(data):
        raise ProtocolError("frame CRC does not match")
    version = data[0]
    if version != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version {version}")
    declared = struct.unpack_from("<H", data, 1)[0]
    if declared != len(data):
        raise ProtocolError(f"frame length field is {declared}, buffer is {len(data)}")
    offset = 1 + _LENGTH_SIZE
    session_id: bytes | None = None
    if has_session:
        session_id = data[offset : offset + SESSION_ID_LENGTH]
        offset += SESSION_ID_LENGTH
    count = data[offset]
    offset += 1
    command_bytes = data[offset : len(data) - _CRC_SIZE]
    commands = tuple(_parse_commands(command_bytes))
    if len(commands) != count:
        raise ProtocolError(f"frame announces {count} commands but contained {len(commands)}")
    return Frame(version=version, session_id=session_id, commands=commands)


def _parse_commands(data: bytes) -> list[Command]:
    commands: list[Command] = []
    offset = 0
    while offset < len(data):
        if offset + _COMMAND_HEADER > len(data):
            raise ProtocolError("truncated command header")
        length = struct.unpack_from("<H", data, offset)[0]
        if length < _COMMAND_HEADER or offset + length > len(data):
            raise ProtocolError(f"command length {length} does not fit")
        channel, code = struct.unpack_from("<HH", data, offset + 2)
        payload = data[offset + _COMMAND_HEADER : offset + length]
        commands.append(Command(channel=channel, code=code, payload=payload))
        offset += length
    return commands
