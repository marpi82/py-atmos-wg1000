"""Offline checks for PAGE_DATA Info and OwnText codecs."""

from __future__ import annotations

from pathlib import Path

import pytest

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.data import (
    AC16_OWN_TEXT_OFFSET,
    AC16_TEXT_INDEX,
    InfoItem,
    InfoRowType,
    assemble_info_chunks,
    decode_info_chunk,
    decode_own_text,
    encode_data_request,
    expand_info_value_with,
    resolve_text_id,
)
from pyatmos_wg1000.protocol.enums import DataKind

_FIXTURES = Path(__file__).parent / "fixtures"


def _fixture_bytes(name: str) -> bytes:
    return bytes.fromhex((_FIXTURES / name).read_text().strip())


def test_encode_data_request_matches_ui_layout() -> None:
    """Info start request is kind, ac16, then little-endian req."""
    assert encode_data_request(DataKind.INFO, 0, 1) == bytes.fromhex("030001000000")
    assert encode_data_request(DataKind.OWN_TEXT, 0, 0) == bytes.fromhex("000000000000")


def test_live_info_fixture_decodes_to_known_groups() -> None:
    """Captured Info PAGE_DATA payload yields the live group set."""
    chunk = decode_info_chunk(_fixture_bytes("info_page_data.hex"))
    assert chunk.ac16 == 0
    assert chunk.first_row == 0
    assert chunk.last is True
    assert chunk.row_count == 76
    assert len(chunk.items) == 76
    dump = assemble_info_chunks([chunk])
    assert dump.ac16 == 0
    titles = [item for item in dump.items if item.is_title]
    assert [item.skupina for item in titles] == [1, 2, 4, 5, 8, 9, 10, 11, 12, 13, 14, 20, 22]
    assert titles[0].text_a == 1011  # Temperatury
    by_group = {item.skupina: item for item in titles}
    assert by_group[12].text_a == AC16_OWN_TEXT_OFFSET  # Dom via OwnText[0]
    assert by_group[13].text_a == AC16_OWN_TEXT_OFFSET + 1  # Poddasze
    assert any(item.typ == InfoRowType.SHORT for item in dump.items)
    assert all(not item.is_alarm for item in dump.items)


def test_live_own_text_fixture_has_circuit_names() -> None:
    """Captured OwnText slots include Dom and Poddasze."""
    names = decode_own_text(_fixture_bytes("own_text_data.hex"))
    assert names[0] == "Dom"
    assert names[1] == "Poddasze"
    assert names[2] == "Ochrona powrotu"
    assert len(names) == 39


def test_expand_text_index_escape() -> None:
    """0xFF + u16 LE is replaced with the looked-up regulator string."""
    raw = bytes([AC16_TEXT_INDEX, 0xD7, 0x07, 0x00])  # index 2007
    assert expand_info_value_with(lambda i: {2007: "OFF"}.get(i, ""), raw) == "OFF"
    mixed = b"20,3 \xc2\xb0C / " + bytes([AC16_TEXT_INDEX, 0x8F, 0x03, 0x00])
    assert expand_info_value_with(lambda i: {911: "Tryb letni"}.get(i, ""), mixed) == "20,3 °C / Tryb letni"


def test_resolve_text_id_own_empty_and_catalog() -> None:
    """OwnText slots, empty id, and catalog keys resolve like the UI."""

    class _Catalog:
        def text(self, key: str) -> str | None:
            return {"T16_1011": "Temperatury"}.get(key)

    catalog = _Catalog()
    own = ("Dom", "Poddasze")
    assert resolve_text_id(1011, catalog, own) == "Temperatury"
    assert resolve_text_id(AC16_OWN_TEXT_OFFSET, catalog, own) == "Dom"
    assert resolve_text_id(AC16_OWN_TEXT_OFFSET + 1, catalog, own) == "Poddasze"
    from pyatmos_wg1000.protocol.data import AC16_EMPTY_TEXT_ID

    assert resolve_text_id(AC16_EMPTY_TEXT_ID, catalog, own) == ""


def test_assemble_rejects_gap_incomplete_and_count_mismatch() -> None:
    """Assembler requires contiguous rows, a last flag, and the declared row count."""
    item = InfoItem(typ=0, vzhled=0, skupina=1, text_a=1, text_b=0, caption=0, value=b"\x00")
    from pyatmos_wg1000.protocol.data import InfoChunk

    first = InfoChunk(ac16=0, row_count=2, first_row=0, last=False, items=(item,))
    with pytest.raises(ProtocolError, match="incomplete"):
        assemble_info_chunks([first])
    gap = InfoChunk(ac16=0, row_count=2, first_row=2, last=True, items=(item,))
    with pytest.raises(ProtocolError, match="expected 1"):
        assemble_info_chunks([first, gap])
    short = InfoChunk(ac16=0, row_count=2, first_row=0, last=True, items=(item,))
    with pytest.raises(ProtocolError, match="expected 2"):
        assemble_info_chunks([short])
