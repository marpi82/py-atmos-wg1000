"""PAGE_DATA payloads: Info page rows and OwnText custom names.

The stock UI polls ``DataKind.INFO`` for the Info page and ``DataKind.OWN_TEXT``
for panel-custom circuit names. Value blobs may embed ``AC16_TEXT_INDEX``
escapes that expand to regulator strings via :class:`~pyatmos_wg1000.i18n.LanguageCatalog`.
"""

from __future__ import annotations

import struct
from collections.abc import Callable, Sequence
from enum import IntEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.enums import DataKind


class TextLookup(Protocol):
    """Minimal catalog surface for Info caption and value expansion."""

    def text(self, key: str) -> str | None:
        """Translate one UI or regulator key."""


# Magic byte before a little-endian u16 regulator text index in Info values.
AC16_TEXT_INDEX = 0xFF
# Regulator string ids at or above this are OwnText slot indices (``Pages.js``).
AC16_OWN_TEXT_OFFSET = 0x8000
# UI ``EMPTY`` id — blank label, not a missing translation.
AC16_EMPTY_TEXT_ID = 1614

_U32 = 0xFFFFFFFF


class InfoRowType(IntEnum):
    """Info row kind (``AC16_INFO_TYP`` in the gateway UI)."""

    TITLE = 0
    LONG = 1
    SHORT = 2
    ALARM = 3


class InfoItem(BaseModel):
    """One row from an Info page dump, before caption/value expansion."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    typ: int = Field(ge=0, le=0xFF)
    vzhled: int = Field(ge=0, le=0xFF)
    skupina: int = Field(ge=0, le=0xFF)
    text_a: int = Field(ge=0, le=0xFFFF)
    text_b: int = Field(ge=0, le=0xFFFF)
    caption: int = Field(ge=0, le=0xFFFF)
    value: bytes

    @property
    def row_type(self) -> InfoRowType | int:
        """Return a known :class:`InfoRowType`, or the raw byte when unknown."""
        try:
            return InfoRowType(self.typ)
        except ValueError:
            return self.typ

    @property
    def is_title(self) -> bool:
        """Return whether this row is a group heading."""
        return self.typ == InfoRowType.TITLE

    @property
    def is_alarm(self) -> bool:
        """Return whether this row is an alarm entry."""
        return self.typ == InfoRowType.ALARM


class InfoChunk(BaseModel):
    """One PAGE_DATA Info response chunk (may be a partial dump)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ac16: int = Field(ge=0, le=0xFF)
    row_count: int = Field(ge=0, le=0xFFFF)
    first_row: int = Field(ge=0, le=0xFFFF)
    last: bool
    items: tuple[InfoItem, ...]


class InfoDump(BaseModel):
    """A fully assembled Info dump for one AC16."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ac16: int = Field(ge=0, le=0xFF)
    items: tuple[InfoItem, ...]


def encode_data_request(kind: DataKind | int, ac16: int, req: int) -> bytes:
    """Build a PAGE_DATA request payload.

    Args:
        kind: ``DataKind`` value (Info, OwnText, …).
        ac16: Controller index (``0`` is the first AC16).
        req: For Info, ``1`` starts a dump and ``0`` continues. OwnText uses ``0``.

    Returns:
        Six bytes: kind, ac16, then ``req`` as little-endian u32.
    """
    if not 0 <= int(kind) <= 0xFF:
        raise ProtocolError(f"data kind out of range: {kind!r}")
    if not 0 <= ac16 <= 0xFF:
        raise ProtocolError(f"ac16 out of range: {ac16}")
    if not 0 <= req <= _U32:
        raise ProtocolError(f"data req out of range: {req}")
    return bytes((int(kind) & 0xFF, ac16 & 0xFF)) + struct.pack("<I", req)


def decode_own_text(payload: bytes) -> tuple[str, ...]:
    """Decode an OwnText PAGE_DATA response into NUL-separated UTF-8 strings.

    Args:
        payload: Full command payload including kind and ac16, or the body only
            (NUL-separated strings). When the first byte is ``DataKind.OWN_TEXT``
            and the length is at least 2, kind and ac16 are stripped.

    Returns:
        The custom-name slots in order. Trailing empty fragments from a final
        NUL are dropped.
    """
    body = _strip_data_header(payload, DataKind.OWN_TEXT)
    parts = body.split(b"\x00")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return tuple(part.decode("utf-8", errors="replace") for part in parts)


def decode_info_chunk(payload: bytes) -> InfoChunk:
    """Decode one Info PAGE_DATA response chunk.

    Args:
        payload: Full command payload (kind + ac16 + body).

    Returns:
        The decoded chunk metadata and items.

    Raises:
        ProtocolError: Kind is not Info, or the body is truncated.
    """
    if len(payload) < 2:
        raise ProtocolError("info payload is shorter than kind and ac16")
    kind = payload[0]
    ac16 = payload[1]
    if kind != DataKind.INFO:
        raise ProtocolError(f"expected DataKind.INFO, got {kind}")
    body = payload[2:]
    if len(body) < 5:
        raise ProtocolError("info body is shorter than the chunk header")
    row_count = body[0] | (body[1] << 8)
    first_row = body[2] | (body[3] << 8)
    last = body[4] != 0
    items = _decode_info_items(body[5:])
    return InfoChunk(ac16=ac16, row_count=row_count, first_row=first_row, last=last, items=items)


def assemble_info_chunks(chunks: Sequence[InfoChunk]) -> InfoDump:
    """Merge ordered Info chunks into one dump.

    Args:
        chunks: Chunks for a single AC16, in wire order. The first chunk must
            start at row 0; each later chunk must continue the row index.

    Returns:
        The assembled dump.

    Raises:
        ProtocolError: Chunks are empty, span AC16s, or leave a gap.
    """
    if not chunks:
        raise ProtocolError("info dump has no chunks")
    ac16 = chunks[0].ac16
    items: list[InfoItem] = []
    expected_row = 0
    for chunk in chunks:
        if chunk.ac16 != ac16:
            raise ProtocolError(f"info chunk ac16 {chunk.ac16} does not match {ac16}")
        if chunk.first_row != expected_row:
            raise ProtocolError(f"info chunk starts at row {chunk.first_row}, expected {expected_row}")
        items.extend(chunk.items)
        expected_row += len(chunk.items)
    if not chunks[-1].last:
        raise ProtocolError("info dump is incomplete (last flag unset)")
    return InfoDump(ac16=ac16, items=tuple(items))


def expand_info_value(raw: bytes, catalog: TextLookup) -> str:
    """Expand ``AC16_TEXT_INDEX`` escapes in an Info value blob.

    Args:
        raw: Value bytes from :attr:`InfoItem.value` (may include a trailing NUL).
        catalog: Language tables used to resolve embedded ``T16_<n>`` ids.

    Returns:
        UTF-8 text after expanding index escapes. Unknown ids become empty.
    """

    def _lookup(index: int) -> str:
        text = catalog.text(f"T16_{index}")
        return text if text is not None else ""

    return expand_info_value_with(_lookup, raw)


def expand_info_value_with(lookup: Callable[[int], str], raw: bytes) -> str:
    """Expand Info value escapes with a custom text lookup.

    Args:
        lookup: Maps a regulator text index to a string.
        raw: Value bytes (trailing NULs are ignored).

    Returns:
        Expanded UTF-8 text.
    """
    data = raw.rstrip(b"\x00")
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == AC16_TEXT_INDEX and i + 2 < len(data):
            index = data[i + 1] | (data[i + 2] << 8)
            i += 3
            out.extend(lookup(index).encode("utf-8"))
        else:
            out.append(data[i])
            i += 1
    return out.decode("utf-8", errors="replace")


def resolve_text_id(
    text_id: int,
    catalog: TextLookup,
    own_text: Sequence[str] = (),
) -> str:
    """Resolve a caption / TextA / TextB id the way the Info UI does.

    Args:
        text_id: Regulator string id, OwnText slot (``>= 0x8000``), or empty id.
        catalog: Language tables for ``T16_*`` keys.
        own_text: Custom names from :func:`decode_own_text`.

    Returns:
        The display string. Empty id and missing translations yield ``""``.
    """
    if text_id == AC16_EMPTY_TEXT_ID:
        return ""
    if text_id >= AC16_OWN_TEXT_OFFSET:
        slot = text_id - AC16_OWN_TEXT_OFFSET
        if 0 <= slot < len(own_text):
            return own_text[slot]
        return ""
    text = catalog.text(f"T16_{text_id}")
    return text if text is not None else ""


def _strip_data_header(payload: bytes, expected: DataKind) -> bytes:
    if len(payload) >= 2 and payload[0] == int(expected):
        return payload[2:]
    return payload


def _decode_info_items(data: bytes) -> tuple[InfoItem, ...]:
    remaining = bytearray(data)
    items: list[InfoItem] = []
    while len(remaining) >= 11:
        typ = remaining[0]
        vzhled = remaining[1]
        skupina = remaining[2]
        text_a = remaining[3] | (remaining[4] << 8)
        text_b = remaining[5] | (remaining[6] << 8)
        caption = remaining[7] | (remaining[8] << 8)
        length = remaining[9] + 1
        if len(remaining) < 10 + length:
            raise ProtocolError(f"info item needs {length} value bytes, have {len(remaining) - 10}")
        value = bytes(remaining[10 : 10 + length])
        del remaining[: 10 + length]
        items.append(
            InfoItem(
                typ=typ,
                vzhled=vzhled,
                skupina=skupina,
                text_a=text_a,
                text_b=text_b,
                caption=caption,
                value=value,
            )
        )
    if remaining:
        raise ProtocolError(f"info body has {len(remaining)} trailing bytes")
    return tuple(items)
