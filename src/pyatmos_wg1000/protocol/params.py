"""Parameter read/write payloads and ACD value decoding."""

from __future__ import annotations

import math
import struct
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.protocol.enums import ParamAccess, ParamType

_U32 = 0xFFFFFFFF
_MAX_WRITE = 100


class ParamRecord(BaseModel):
    """One register in a parameter read response."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    register_id: int = Field(ge=0, le=_U32)
    kind: ParamType
    value: int | None = None
    minimum: int | None = None
    maximum: int | None = None


class WriteResult(BaseModel):
    """One register in a parameter write response.

    The layout comes from ``Pages.js`` (``GetMsg`` / ``RefreshPRM``). It has
    not been captured from a live write.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    register_id: int = Field(ge=0, le=_U32)
    status: int = Field(ge=0, le=0xFF)
    value: int = Field(ge=0, le=_U32)

    @property
    def rejected(self) -> bool:
        """Return whether the gateway refused the write (status bit 0)."""
        return bool(self.status & 0x01)

    @property
    def edit_accepted(self) -> bool:
        """Return whether the UI treats the edit as accepted (status bit 4)."""
        return bool(self.status & 0x10)


class SetpointPair(BaseModel):
    """Comfort and reduced setpoints packed in one 32-bit word."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    comfort_c: float
    reduced_c: float


class AcdTime(BaseModel):
    """Clock packed in ``HOD16.CAS``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hour: int = Field(ge=0, le=0xFF)
    minute: int = Field(ge=0, le=0xFF)
    weekday: int = Field(ge=0, le=7)


class AcdDate(BaseModel):
    """Calendar date packed in ``HOD16.DATUM``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    day: int = Field(ge=0, le=0xFF)
    month: int = Field(ge=0, le=0xFF)
    year: int = Field(ge=0, le=0xFFFF)


def encode_param_read(register_ids: Sequence[int]) -> bytes:
    """Encode a parameter read request.

    Args:
        register_ids: Register ids, each fitting in 32 bits.

    Returns:
        Payload starting with :attr:`ParamAccess.READ`.

    Raises:
        ProtocolError: The id list is empty or an id does not fit.
    """
    if not register_ids:
        raise ProtocolError("parameter read needs at least one register")
    body = bytearray((ParamAccess.READ,))
    for register_id in register_ids:
        body += _pack_u32(register_id)
    return bytes(body)


def encode_param_write(pairs: Sequence[tuple[int, int]]) -> bytes:
    """Encode a parameter write request.

    Args:
        pairs: ``(register_id, value)`` pairs. The UI allows at most 100.

    Returns:
        Payload starting with :attr:`ParamAccess.WRITE` and a count byte.

    Raises:
        ProtocolError: The list is empty, too long, or a value does not fit.
    """
    if not pairs or len(pairs) > _MAX_WRITE:
        raise ProtocolError(f"parameter write needs 1..{_MAX_WRITE} pairs, got {len(pairs)}")
    body = bytearray((ParamAccess.WRITE, len(pairs)))
    for register_id, value in pairs:
        body += _pack_u32(register_id)
        body += _pack_u32(value)
    return bytes(body)


def decode_param_read(payload: bytes) -> tuple[ParamRecord, ...]:
    """Decode a parameter read response payload.

    Args:
        payload: Command payload, including the leading access byte.

    Returns:
        One record per register. Hidden and unavailable records have no value.

    Raises:
        ProtocolError: The payload is not a read response or a record is truncated.
    """
    if not payload or payload[0] != ParamAccess.READ:
        raise ProtocolError("parameter payload is not a read response")
    records: list[ParamRecord] = []
    offset = 1
    while offset < len(payload):
        if offset + 5 > len(payload):
            raise ProtocolError("truncated parameter record")
        register_id = struct.unpack_from("<I", payload, offset)[0]
        offset += 4
        kind_byte = payload[offset]
        offset += 1
        try:
            kind = ParamType(kind_byte)
        except ValueError as exc:
            raise ProtocolError(f"unknown parameter type {kind_byte}") from exc
        value: int | None = None
        minimum: int | None = None
        maximum: int | None = None
        if kind in (ParamType.HIDDEN, ParamType.UNAVAILABLE):
            pass
        elif kind is ParamType.READ_ONLY:
            value, offset = _take_u32(payload, offset)
        elif kind is ParamType.EDITABLE:
            value, offset = _take_u32(payload, offset)
            minimum, offset = _take_u32(payload, offset)
            maximum, offset = _take_u32(payload, offset)
        records.append(ParamRecord(register_id=register_id, kind=kind, value=value, minimum=minimum, maximum=maximum))
    return tuple(records)


def decode_param_write_result(payload: bytes) -> tuple[WriteResult, ...]:
    """Decode a parameter write response payload.

    The record shape is taken from the gateway UI, not from a captured write.

    Args:
        payload: Command payload, including the leading access byte and count.

    Returns:
        One result per register named in the count byte.

    Raises:
        ProtocolError: The payload is not a write response or the count does not fit.
    """
    if len(payload) < 2 or payload[0] != ParamAccess.WRITE:
        raise ProtocolError("parameter payload is not a write response")
    count = payload[1]
    offset = 2
    results: list[WriteResult] = []
    for _ in range(count):
        if offset + 9 > len(payload):
            raise ProtocolError("truncated write result")
        register_id = struct.unpack_from("<I", payload, offset)[0]
        status = payload[offset + 4]
        value = struct.unpack_from("<I", payload, offset + 5)[0]
        offset += 9
        results.append(WriteResult(register_id=register_id, status=status, value=value))
    if offset != len(payload):
        raise ProtocolError("trailing bytes after write results")
    return tuple(results)


def decode_acd_temperature(word: int) -> float | None:
    """Decode an ACD temperature word to degrees Celsius.

    The UI treats the reading as present when bit 31 is set, bit 30 is clear,
    and the low 16 bits are non-zero. Those bits use
    ``round(raw * 10 / 64) / 10 - 64``, with JavaScript ``Math.round``.

    Args:
        word: Raw 32-bit register value.

    Returns:
        Degrees Celsius, or ``None`` when the reading is absent.
    """
    if (word & 0x80000000) == 0 or (word & 0x40000000) != 0 or (word & 0xFFFF) == 0:
        return None
    return _scaled_half(word & 0xFFFF)


def decode_acd_quantity(word: int) -> float | None:
    """Decode humidity the way the UI does.

    Same scale as temperature, but a zero low half is still a number
    (it becomes -64). The reading is absent when bit 31 is clear or bit 30 is set.

    Args:
        word: Raw 32-bit register value.

    Returns:
        The scaled quantity, or ``None`` when the reading is absent.
    """
    if (word & 0x80000000) == 0 or (word & 0x40000000) != 0:
        return None
    return _scaled_half(word & 0xFFFF)


def decode_acd_time(word: int) -> AcdTime:
    """Decode ``HOD16.CAS``.

    The UI prints ``hour:minute`` from the low two bytes and treats the
    top byte, masked with 7, as the weekday with Monday equal to 1.

    Args:
        word: Raw register value.

    Returns:
        Hour, minute, and the weekday code before the UI subtracts one.
    """
    return AcdTime(hour=word & 0xFF, minute=(word >> 8) & 0xFF, weekday=(word >> 24) & 0x07)


def decode_acd_date(word: int) -> AcdDate:
    """Decode ``HOD16.DATUM``.

    Args:
        word: Raw register value.

    Returns:
        Day, month, and full year from the low, middle, and high halves.
    """
    return AcdDate(day=word & 0xFF, month=(word >> 8) & 0xFF, year=(word >> 16) & 0xFFFF)


class CircuitGeneral(BaseModel):
    """Decoded ``O*_OBECNE`` word (``Hod16General`` in ``Pages.js``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    active: bool
    temp_type: int = Field(ge=0, le=0x07)
    humidity: bool


def decode_circuit_general(word: int) -> CircuitGeneral:
    """Decode an ``O*_OBECNE`` / ``TUV_OBECNE`` register word.

    Args:
        word: Raw register value.

    Returns:
        Active flag, temperature icon type, and humidity-present flag.
    """
    return CircuitGeneral(
        active=bool(word & 0x01),
        temp_type=(word >> 1) & 0x07,
        humidity=bool((word >> 4) & 0x01),
    )


def decode_packed_setpoints(word: int) -> SetpointPair:
    """Split a setpoint word into comfort and reduced temperatures.

    The setpoint widget stores comfort in the low 16 bits and the reduced
    setpoint in the high 16 bits, each scaled like a temperature half.
    Validity bits 30 and 31 are not consulted here.

    Args:
        word: Raw 32-bit setpoint word.

    Returns:
        Both halves in degrees Celsius.
    """
    return SetpointPair(comfort_c=_scaled_half(word & 0xFFFF), reduced_c=_scaled_half((word >> 16) & 0xFFFF))


def encode_packed_setpoints(comfort_c: float, reduced_c: float) -> int:
    """Pack comfort and reduced setpoints the way ``SendSetTemp`` does.

    Args:
        comfort_c: Comfort setpoint in degrees Celsius.
        reduced_c: Reduced (útlum) setpoint in degrees Celsius.

    Returns:
        32-bit word with comfort in the low half and reduced in the high half.
    """
    comfort = _encode_temp_half(comfort_c)
    reduced = _encode_temp_half(reduced_c)
    return (comfort | (reduced << 16)) & _U32


class CircuitRegime(BaseModel):
    """Decoded ``O*_REZIM`` word (``Hod16Regime`` in ``Pages.js``)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0, le=0x0F)
    week_prog: int = Field(ge=0, le=0x03)
    date_time: int = Field(ge=0, le=0xFFFF)

    @property
    def preset(self) -> str | None:
        """Return a simple preset name for permanent modes, else ``None``."""
        return _REGIME_PRESETS.get(self.index)


# Regime_menu indices in Pages.js (permanent / timed modes).
REGIME_HOLIDAY = 0
REGIME_ABSENCE = 1
REGIME_VISIT = 2
REGIME_AUTO = 3
REGIME_SUMMER = 4
REGIME_COMFORT = 5
REGIME_REDUCED = 6
REGIME_STANDBY = 7

_REGIME_PRESETS: dict[int, str] = {
    REGIME_HOLIDAY: "holiday",
    REGIME_ABSENCE: "absence",
    REGIME_VISIT: "visit",
    REGIME_AUTO: "auto",
    REGIME_SUMMER: "summer",
    REGIME_COMFORT: "comfort",
    REGIME_REDUCED: "reduced",
    REGIME_STANDBY: "standby",
}

_PRESET_TO_INDEX = {name: index for index, name in _REGIME_PRESETS.items()}


def decode_circuit_regime(word: int) -> CircuitRegime:
    """Decode an ``O*_REZIM`` register word.

    Args:
        word: Raw register value.

    Returns:
        Regime index, optional week program, and packed date/time payload.
    """
    return CircuitRegime(
        index=word & 0x0F,
        week_prog=(word >> 4) & 0x03,
        date_time=(word >> 6) & 0xFFFF,
    )


def encode_circuit_regime(
    index: int,
    *,
    week_prog: int = 0,
    date_time: int = 0,
) -> int:
    """Pack a regime write word the way the homepage menu does.

    Args:
        index: ``Regime_menu`` index (0..7 for known modes).
        week_prog: Weekly program A/B/C for auto/summer (0..2).
        date_time: End date (holiday) or end time (absence/visit).

    Returns:
        32-bit value for ``SetPrm([O*_REZIM], …)``.
    """
    if not 0 <= index <= 0x0F:
        raise ProtocolError(f"regime index out of range: {index}")
    if not 0 <= week_prog <= 0x03:
        raise ProtocolError(f"week prog out of range: {week_prog}")
    if not 0 <= date_time <= 0xFFFF:
        raise ProtocolError(f"regime date/time out of range: {date_time}")
    return ((date_time & 0xFFFF) << 6) | ((week_prog & 0x03) << 4) | (index & 0x0F)


def regime_preset_index(preset: str) -> int:
    """Map a simple preset name to a ``Regime_menu`` index.

    Args:
        preset: One of ``comfort``, ``reduced``, ``auto``, ``standby``, …

    Returns:
        Regime index.

    Raises:
        ProtocolError: Unknown preset name.
    """
    try:
        return _PRESET_TO_INDEX[preset]
    except KeyError as exc:
        raise ProtocolError(f"unknown regime preset: {preset!r}") from exc


def _scaled_half(raw: int) -> float:
    rounded = math.floor((raw * 10) / 64 + 0.5)
    return rounded / 10 - 64


def _encode_temp_half(celsius: float) -> int:
    return round((celsius + 64) * 64) & 0xFFFF


def _pack_u32(value: int) -> bytes:
    if not 0 <= value <= _U32:
        raise ProtocolError(f"value {value} does not fit in uint32")
    return struct.pack("<I", value)


def _take_u32(payload: bytes, offset: int) -> tuple[int, int]:
    if offset + 4 > len(payload):
        raise ProtocolError("truncated parameter value")
    return struct.unpack_from("<I", payload, offset)[0], offset + 4
