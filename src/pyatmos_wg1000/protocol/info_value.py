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
_PAREN = re.compile(r"^(?P<outer>.+?)\s*\((?P<inner>[^)]+)\)\s*$")
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

    Notes:
        Dashed captions keep the full head on both entities
        (``Siłow. RLA3O / RLA3Z - pozycja`` / ``… - ruch``). Terminal codes in
        TextA/TextB are not used when the caption already encodes the panel label.
    """
    if n_parts <= 0:
        return ()
    if n_parts == 1:
        return (_single_name(caption, text_a, text_b),)

    dashed = _names_from_dashed_caption(caption)
    if dashed is not None:
        return dashed

    if caption.count(" / ") == 1:
        left, right = caption.split(" / ", 1)
        left, right = left.strip(), right.strip()
        if left and right:
            return (left, _qualify_short_half(left, right))

    if text_a and text_b:
        return (text_a, text_b)

    base = caption or text_a or text_b or "Info"
    return (f"{base} (1)", f"{base} (2)")


def _names_from_dashed_caption(caption: str) -> tuple[str, str] | None:
    """Parse ``Head - roleA / roleB`` into ``Head - roleA`` / ``Head - roleB``."""
    if " - " not in caption:
        return None
    head, tail = caption.split(" - ", 1)
    head = head.strip()
    if not head or " / " not in tail:
        return None
    role_left, role_right = (part.strip() for part in tail.split(" / ", 1))
    if not role_left or not role_right:
        return None
    return (f"{head} - {role_left}", f"{head} - {role_right}")


def _qualify_short_half(left: str, right: str) -> str:
    """Avoid orphan abbreviations like bare ``wymag.`` as an entity name.

    Full role words (``move``, ``avg``) stay as-is. Trailing ``.`` marks an
    ATMOS abbreviation; a stem contained in the left half is treated the same.
    """
    bare = right.rstrip(".").casefold()
    abbreviated = right.endswith(".") or (len(right) < 10 and bare in left.casefold() and bare != left.casefold())
    if abbreviated:
        return f"{left} ({right})"
    return right


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

    Notes:
        Mode rows with a single-token caption (e.g. ``Tryb``) always yield two
        parts: selection keeps the caption name, effective mode uses the inner
        token (or the bare value when there is no parenthesis).
    """
    parts = parse_info_display(value)
    parts = _expand_bare_mode_pair(caption, parts)
    names = part_names(caption=caption, text_a=text_a, text_b=text_b, n_parts=len(parts))
    if len(parts) == 2:
        names = _refine_mixed_dual_names(caption, names, parts)
    return tuple(part.model_copy(update={"name": names[i]}) for i, part in enumerate(parts))


def _is_mode_caption(caption: str) -> bool:
    """Return True for short regime captions like ``Tryb`` / ``Mode``."""
    text = caption.strip()
    if not text or " / " in text or " - " in text:
        return False
    return " " not in text


def _expand_bare_mode_pair(
    caption: str,
    parts: tuple[InfoValuePart, ...],
) -> tuple[InfoValuePart, ...]:
    """Duplicate a bare regime value into selection + effective parts."""
    if len(parts) != 1 or not _is_mode_caption(caption):
        return parts
    only = parts[0]
    if only.kind is not InfoValueKind.TEXT or not only.raw:
        return parts
    return (only, only.model_copy())


def _refine_mixed_dual_names(
    caption: str,
    names: tuple[str, ...],
    parts: tuple[InfoValuePart, ...],
) -> tuple[str, ...]:
    """Improve fallback ``Caption (1)/(2)`` names for mixed or mode pairs."""
    if len(parts) != 2 or len(names) != 2:
        return names
    base = caption.strip() or "Info"
    indexed = names == (f"{base} (1)", f"{base} (2)")
    numeric = {InfoValueKind.NUMBER, InfoValueKind.MISSING}
    left, right = parts[0], parts[1]

    # ``Auto (Komfort)`` / bare ``Standby`` duplicated: selection=caption, effect=token.
    if left.kind is InfoValueKind.TEXT and right.kind is InfoValueKind.TEXT:
        if indexed or _is_mode_caption(caption):
            effect = right.raw or left.raw or base
            return (base, effect)
        return names

    if not indexed:
        return names
    if left.kind in numeric and right.kind in numeric:
        return names
    # Binary/valve halves keep the panel caption (never ``OFF`` as the entity name).
    if left.kind in (InfoValueKind.BINARY, InfoValueKind.VALVE) and right.kind in numeric:
        return (base, f"{base} (2)")
    if right.kind in (InfoValueKind.BINARY, InfoValueKind.VALVE) and left.kind in numeric:
        return (f"{base} (1)", base)
    if left.kind in (InfoValueKind.BINARY, InfoValueKind.VALVE) and right.kind not in numeric:
        return (base, f"{base} (2)")
    if right.kind in (InfoValueKind.BINARY, InfoValueKind.VALVE) and left.kind not in numeric:
        return (f"{base} (1)", base)
    # Number + status text (e.g. ``18,9 °C / Tryb letni``).
    left_name = base if left.kind in numeric else (left.raw or base)
    right_name = base if right.kind in numeric else (right.raw or base)
    return (left_name, right_name)


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
