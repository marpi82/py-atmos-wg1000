"""Parse gateway Info display strings into typed parts.

The regulator sends preformatted UTF-8 (often ``a / b`` or ``a (b %)``).
This module splits those strings and classifies each half without Home
Assistant types. Language-invariant tokens (``ON``/``OFF``, ``OPEN``/
``STOP``/``CLOSE``) come from the gateway tables; localized modes stay text.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

# Gateway T16_2007/2008 and valve move tokens are identical across languages.
_BINARY_ON = frozenset({"on"})
_BINARY_OFF = frozenset({"off"})
_VALVE = {
    "open": "open",
    "stop": "stop",
    "close": "close",
}

_MISSING = re.compile(r"^-+$")
_NUMBER_UNIT = re.compile(
    r"^\s*"
    r"(?P<num>-?\d+(?:[.,]\d+)?)"
    r"(?:\s*(?P<unit>°C|%|h|min|x))?"
    r"\s*$",
    re.IGNORECASE,
)
_PAREN = re.compile(r"^(?P<outer>.+?)\s+\((?P<inner>[^)]+)\)\s*$")
_DATE = re.compile(r"^\d{1,2}\.\d{1,2}\.\d{4}$")


class InfoValueKind(StrEnum):
    """Classification of one Info value part."""

    NUMBER = "number"
    MISSING = "missing"
    BINARY = "binary"
    VALVE = "valve"
    TEXT = "text"


class InfoValuePart(BaseModel):
    """One half of an expanded Info display string."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: InfoValueKind
    raw: str = ""
    number: float | None = None
    unit_token: str | None = None
    binary_on: bool | None = None
    valve: Literal["open", "stop", "close"] | None = None
    text: str | None = None
    name: str = ""


def split_display(value: str) -> list[str]:
    """Split a display string into one or two halves.

    Args:
        value: Expanded Info value (after ``AC16_TEXT_INDEX`` expansion).

    Returns:
        One or two trimmed parts. ``S/N …`` is kept whole. Parenthetical
        humidity pairs become outer + inner.
    """
    text = value.strip()
    if not text:
        return [""]
    if text.upper().startswith("S/N"):
        return [text]
    if " / " in text:
        left, right = text.split(" / ", 1)
        return [left.strip(), right.strip()]
    match = _PAREN.match(text)
    if match is not None:
        return [match.group("outer").strip(), match.group("inner").strip()]
    return [text]


def parse_part(text: str, *, default_unit: str | None = None) -> InfoValuePart:
    """Classify one display half.

    Args:
        text: One half from :func:`split_display`.
        default_unit: Unit inherited from the sibling half (e.g. bare
            ``5,1`` next to ``26,1 °C``).

    Returns:
        A typed part. ``---`` (optionally with a unit) is ``missing``.
    """
    raw = text.strip()
    if not raw:
        return InfoValuePart(kind=InfoValueKind.MISSING, raw=raw)

    tokens = raw.split()
    if len(tokens) == 2 and _MISSING.match(tokens[0]) is not None:
        unit = _normalize_unit(tokens[1]) or default_unit
        return InfoValuePart(kind=InfoValueKind.MISSING, raw=raw, unit_token=unit)
    if _MISSING.match(raw) is not None:
        return InfoValuePart(kind=InfoValueKind.MISSING, raw=raw, unit_token=default_unit)

    key = raw.casefold()
    if key in _BINARY_ON:
        return InfoValuePart(kind=InfoValueKind.BINARY, raw=raw, binary_on=True)
    if key in _BINARY_OFF:
        return InfoValuePart(kind=InfoValueKind.BINARY, raw=raw, binary_on=False)
    valve = _VALVE.get(key)
    if valve is not None:
        return InfoValuePart(kind=InfoValueKind.VALVE, raw=raw, valve=valve)

    match = _NUMBER_UNIT.match(raw)
    if match is not None:
        number = _parse_number(match.group("num"))
        unit = _normalize_unit(match.group("unit")) or default_unit
        return InfoValuePart(kind=InfoValueKind.NUMBER, raw=raw, number=number, unit_token=unit)

    if _DATE.match(raw) is not None:
        return InfoValuePart(kind=InfoValueKind.TEXT, raw=raw, text=raw)

    return InfoValuePart(kind=InfoValueKind.TEXT, raw=raw, text=raw)


def parse_info_display(value: str) -> tuple[InfoValuePart, ...]:
    """Split and classify a full Info value string.

    Args:
        value: Expanded display string.

    Returns:
        One or two parts. When the left half is a bare number and the right
        carries a unit, the left inherits that unit.
    """
    halves = split_display(value)
    if len(halves) == 1:
        return (parse_part(halves[0]),)

    right = parse_part(halves[1])
    left = parse_part(halves[0], default_unit=right.unit_token)
    return (left, right)


def part_names(
    *,
    caption: str,
    text_a: str,
    text_b: str,
    n_parts: int,
) -> tuple[str, ...]:
    """Pick display names for parsed parts without language dictionaries.

    Args:
        caption: Resolved caption (often already contains `` / ``).
        text_a: Resolved TextA (sensor code or OwnText).
        text_b: Resolved TextB.
        n_parts: Number of value parts from :func:`parse_info_display`.

    Returns:
        One name per part.
    """
    if n_parts <= 0:
        return ()
    if n_parts == 1:
        return (_single_name(caption, text_a, text_b),)

    if " / " in caption:
        left, right = caption.split(" / ", 1)
        left, right = left.strip(), right.strip()
        if left and right:
            return (left, right)

    if text_a and text_b:
        return (text_a, text_b)

    base = caption or text_a or text_b or "Info"
    return (f"{base} (1)", f"{base} (2)")


def parse_info_row(
    *,
    value: str,
    caption: str = "",
    text_a: str = "",
    text_b: str = "",
) -> tuple[InfoValuePart, ...]:
    """Parse a value and attach names from caption / TextA / TextB.

    Args:
        value: Expanded Info value.
        caption: Resolved caption.
        text_a: Resolved TextA.
        text_b: Resolved TextB.

    Returns:
        Named parts ready for Home Assistant entity creation.
    """
    parts = parse_info_display(value)
    names = part_names(caption=caption, text_a=text_a, text_b=text_b, n_parts=len(parts))
    return tuple(part.model_copy(update={"name": names[i]}) for i, part in enumerate(parts))


def _single_name(caption: str, text_a: str, text_b: str) -> str:
    if caption:
        return caption
    if text_a and text_b:
        return f"{text_a} / {text_b}"
    return text_a or text_b or "Info"


def _parse_number(raw: str) -> float:
    return float(raw.replace(",", "."))


def _normalize_unit(raw: str | None) -> str | None:
    if raw is None:
        return None
    token = raw.strip()
    if token.casefold() == "°c":
        return "°C"
    lower = token.lower()
    if lower == "%":
        return "%"
    if lower == "h":
        return "h"
    if lower == "min":
        return "min"
    if lower == "x":
        return "x"
    return token


__all__ = [
    "InfoValueKind",
    "InfoValuePart",
    "parse_info_display",
    "parse_info_row",
    "parse_part",
    "part_names",
    "split_display",
]
