"""Offline checks for frames captured from a WG1000 and for value decoding."""

from __future__ import annotations

import hashlib

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.catalog import Device, Hod16, Id33, hod16_id
from pyatmos_wg1000.protocol.enums import Channel, CommandCode, FileOp, ParamAccess, ParamType
from pyatmos_wg1000.protocol.files import decode_file_chunk, encode_file_ack, encode_file_request
from pyatmos_wg1000.protocol.frame import decode_client_frame, decode_server_frame, encode_client_frame, encode_server_frame
from pyatmos_wg1000.protocol.login import encode_login, parse_login_result
from pyatmos_wg1000.protocol.params import (
    decode_acd_date,
    decode_acd_temperature,
    decode_acd_time,
    decode_packed_setpoints,
    decode_param_read,
    decode_param_write_result,
    encode_param_write,
)

# Server frames captured on the LAN gateway. They contain no credentials.
HELLO = bytes.fromhex("010f0001070000000000004ef4f0ad")
SKIN_LANG = bytes.fromhex("01210001190000000400005e00000001000000005c000000010800000001576bf8")
UNAVAILABLE = bytes.fromhex("011e00011600030004000000000011ff01000011ff15000011ff22ee4fdd")
LOGIN_OK = bytes.fromhex("011000010800010003000100c8f315b5")
# First gzip chunk header of PRM.js (file id assigned by the gateway, not the UI index).
PRM_CHUNK_HEADER = bytes.fromhex("010c000020a94900000000000002")


def test_captured_server_frames_round_trip() -> None:
    """Captured server frames decode and encode back to the same bytes."""
    for frame in (HELLO, SKIN_LANG, UNAVAILABLE, LOGIN_OK):
        decoded = decode_server_frame(frame)
        assert encode_server_frame(decoded.commands) == frame


def test_hello_reports_logged_out() -> None:
    """Hello before login is one byte, zero."""
    command = decode_server_frame(HELLO).commands[0]
    assert command.channel == Channel.WS
    assert command.code == CommandCode.HELLO
    assert command.payload == b"\x00"


def test_pre_login_language_and_hidden_regulator_values() -> None:
    """Skin and language are readable before login; HOD16 is not."""
    skin = decode_param_read(decode_server_frame(SKIN_LANG).commands[0].payload)
    assert [(row.register_id, row.kind, row.value) for row in skin] == [
        (Id33.USER1_SKIN, ParamType.READ_ONLY, 0),
        (Id33.USER1_LANG, ParamType.READ_ONLY, 8),
    ]
    hidden = decode_param_read(decode_server_frame(UNAVAILABLE).commands[0].payload)
    assert [row.register_id for row in hidden] == [
        hod16_id(Hod16.OBECNE),
        hod16_id(Hod16.AF),
        hod16_id(Hod16.O1_TEPLOTA),
    ]
    assert all(row.kind is ParamType.UNAVAILABLE and row.value is None for row in hidden)


def test_login_response_role_user() -> None:
    """A successful login captured on the gateway is role 1 and not locked out."""
    result = parse_login_result(decode_server_frame(LOGIN_OK).commands[0].payload)
    assert result.role == 1
    assert result.logged_in is True
    assert result.blocked is False


def test_login_payload_matches_ui_padding() -> None:
    """Username and password are NUL-padded before SHA-512, then sent with the digest."""
    payload = encode_login("user", "secret", stay=True)
    assert payload[0] == 0
    assert payload[1:33] == b"user".ljust(32, b"\x00")
    expected = hashlib.sha512(b"user".ljust(32, b"\x00") + b"secret".ljust(64, b"\x00")).digest()
    assert payload[33:97] == expected
    assert payload[-1] == 1
    assert len(payload) == 98


def test_client_frame_carries_session_id() -> None:
    """Client frames insert a 32-byte session id that server frames omit."""
    session = bytes(range(32))
    encoded = encode_client_frame(
        decode_server_frame(HELLO).commands,
        session,
    )
    decoded = decode_client_frame(encoded)
    assert decoded.session_id == session
    assert decoded.commands == decode_server_frame(HELLO).commands


def test_temperature_time_and_setpoints_from_live_words() -> None:
    """Words read after login decode to the temperatures and clock the UI would show."""
    assert decode_acd_temperature(0x8000138C) == 782 / 10 - 64
    assert decode_acd_temperature(0x800014CF) == 832 / 10 - 64
    assert decode_acd_temperature(0x80001E1A) == 1204 / 10 - 64
    assert decode_acd_temperature(0x80000000) is None
    clock = decode_acd_time(0x052E170F)
    assert (clock.hour, clock.minute, clock.weekday) == (15, 23, 5)
    date = decode_acd_date(0x07EA0919)
    assert (date.day, date.month, date.year) == (25, 9, 2026)
    pair = decode_packed_setpoints(0x1C801F00)
    assert pair.comfort_c == 1240 / 10 - 64
    assert pair.reduced_c == 1140 / 10 - 64


def test_file_chunk_header_and_ack() -> None:
    """The PRM.js chunk header uses the gateway file id and the gzip flag."""
    chunk = decode_file_chunk(PRM_CHUNK_HEADER)
    assert chunk.file_id == 12
    assert chunk.part_length == 8192
    assert chunk.file_length == 18857
    assert chunk.offset == 0
    assert chunk.gzip is True
    assert chunk.end is False
    assert encode_file_request("PRM.js") == bytes((FileOp.REQUEST, 6)) + b"PRM.js"
    assert encode_file_ack(12, 8192) == bytes((FileOp.ACK, 12, 0, 0, 0x20, 0, 0))


def test_param_write_codec_follows_ui_layout() -> None:
    """Write payloads use the Pages.js layout even though a live write was not captured."""
    payload = encode_param_write([(hod16_id(Hod16.O1_REZIM), 5)])
    assert payload[0] == ParamAccess.WRITE
    assert payload[1] == 1
    response = bytes((ParamAccess.WRITE, 1)) + (5).to_bytes(4, "little") + bytes((0x10,)) + (5).to_bytes(4, "little")
    result = decode_param_write_result(response)
    assert result[0].register_id == 5
    assert result[0].edit_accepted is True
    assert result[0].rejected is False


def test_bad_crc_is_rejected() -> None:
    """A flipped CRC byte does not decode."""
    broken = bytearray(HELLO)
    broken[-1] ^= 0xFF
    try:
        decode_server_frame(bytes(broken))
    except ProtocolError as exc:
        assert "CRC" in str(exc)
    else:
        raise AssertionError("expected ProtocolError")


def test_hod16_id_uses_first_acd_by_default() -> None:
    """The default device nibble matches PRM.js HOD16_ID."""
    assert hod16_id(Hod16.AF) == 0x11000001
    assert hod16_id(Hod16.AF, device=Device.AC16_2) == 0x21000001
    assert int(Id33.USER1_LANG) == 92
