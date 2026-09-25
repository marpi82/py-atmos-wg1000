"""UI bundle download over the same WebSocket."""

from __future__ import annotations

import struct

from pydantic import BaseModel, ConfigDict, Field

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.enums import FileOp


class FileChunk(BaseModel):
    """One slice of a file sent by the gateway."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_id: int = Field(ge=0, le=0xFFFF)
    part_length: int = Field(ge=0, le=0xFFFF)
    file_length: int = Field(ge=0, le=0xFFFFFFFF)
    offset: int = Field(ge=0, le=0xFFFFFFFF)
    end: bool
    gzip: bool
    error: bool
    data: bytes


def encode_file_request(name: str) -> bytes:
    """Encode a request for one UI file by name.

    Args:
        name: File name as the UI requests it, for example ``PRM.js``.

    Returns:
        File-command payload.

    Raises:
        ProtocolError: The name is empty or is not ASCII.
    """
    try:
        raw = name.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ProtocolError("file name must be ASCII") from exc
    if not raw or len(raw) > 0xFF:
        raise ProtocolError("file name length must be 1..255")
    return bytes((FileOp.REQUEST, len(raw))) + raw


def encode_file_ack(file_id: int, offset: int) -> bytes:
    """Encode the acknowledgement that asks for the next chunk.

    Args:
        file_id: Id from the previous chunk, not the UI file index.
        offset: Number of bytes received so far.

    Returns:
        File-command payload.

    Raises:
        ProtocolError: An argument does not fit in its field.
    """
    if not 0 <= file_id <= 0xFFFF or not 0 <= offset <= 0xFFFFFFFF:
        raise ProtocolError("file acknowledgement field out of range")
    return bytes((FileOp.ACK,)) + struct.pack("<HI", file_id, offset)


def decode_file_chunk(payload: bytes) -> FileChunk:
    """Decode a file-data payload (operation ``GET``).

    Args:
        payload: File-command payload, including the operation byte.

    Returns:
        Chunk metadata and the bytes that follow the header.

    Raises:
        ProtocolError: The payload is not a GET chunk or the header is short.
    """
    header = 1 + 2 + 2 + 4 + 4 + 1
    if len(payload) < header or payload[0] != FileOp.GET:
        raise ProtocolError("file payload is not a GET chunk")
    file_id, part_length = struct.unpack_from("<HH", payload, 1)
    file_length, offset = struct.unpack_from("<II", payload, 5)
    flags = payload[13]
    return FileChunk(
        file_id=file_id,
        part_length=part_length,
        file_length=file_length,
        offset=offset,
        end=bool(flags & 0x01),
        gzip=bool(flags & 0x02),
        error=bool(flags & 0x04),
        data=payload[header:],
    )
