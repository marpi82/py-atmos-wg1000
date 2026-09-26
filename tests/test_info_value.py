"""Offline checks for Info display-string parsing."""

from __future__ import annotations

from pathlib import Path

from pyatmos_wg1000.protocol.data import (
    assemble_info_chunks,
    decode_info_chunk,
    expand_info_value_with,
)
from pyatmos_wg1000.protocol.info_value import (
    InfoValueKind,
    InfoValuePart,
    _refine_mixed_dual_names,
    parse_info_display,
    parse_info_row,
    parse_part,
    part_names,
    split_display,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def test_split_slash_and_paren_and_sn() -> None:
    """Slash and parenthetical pairs split; S/N stays whole."""
    assert split_display("25,0 °C / 20,9 °C") == ["25,0 °C", "20,9 °C"]
    assert split_display("19,7 °C (65,9 %)") == ["19,7 °C", "65,9 %"]
    assert split_display("S/N 7101") == ["S/N 7101"]
    assert split_display("25,9 °C") == ["25,9 °C"]
    assert split_display("   ") == [""]
    assert split_display("") == [""]


def test_parse_missing_and_number_units() -> None:
    """Missing dashes and locale decimals classify correctly."""
    missing = parse_part("--- °C")
    assert missing.kind is InfoValueKind.MISSING
    assert missing.unit_token == "°C"
    assert missing.number is None

    bare_missing = parse_part("---")
    assert bare_missing.kind is InfoValueKind.MISSING
    assert bare_missing.unit_token is None

    empty = parse_part("  ")
    assert empty.kind is InfoValueKind.MISSING

    temp = parse_part("25,9 °C")
    assert temp.kind is InfoValueKind.NUMBER
    assert temp.number == 25.9
    assert temp.unit_token == "°C"

    bare = parse_part("5,1", default_unit="°C")
    assert bare.kind is InfoValueKind.NUMBER
    assert bare.number == 5.1
    assert bare.unit_token == "°C"

    hours = parse_part("11 h")
    assert hours.unit_token == "h"
    mins = parse_part("15 min")
    assert mins.unit_token == "min"
    count = parse_part("16 x")
    assert count.unit_token == "x"
    weird = parse_part("--- kPa")
    assert weird.kind is InfoValueKind.MISSING
    assert weird.unit_token == "kPa"


def test_parse_binary_and_valve() -> None:
    """Language-invariant ON/OFF and valve tokens."""
    assert parse_part("ON").kind is InfoValueKind.BINARY
    assert parse_part("ON").binary_on is True
    assert parse_part("OFF").binary_on is False
    assert parse_part("STOP").valve == "stop"
    assert parse_part("OPEN").valve == "open"
    assert parse_part("CLOSE").valve == "close"


def test_unit_inheritance_across_slash() -> None:
    """Bare left number inherits the right half unit."""
    parts = parse_info_display("5,1 / 26,1 °C")
    assert len(parts) == 2
    left, right = parts[0], parts[1]
    assert left.number == 5.1
    assert left.unit_token == "°C"
    assert right.number == 26.1
    assert right.unit_token == "°C"

    missing_pair = parse_info_display("--- / 26,1 °C")
    assert missing_pair[0].kind is InfoValueKind.MISSING
    assert missing_pair[0].unit_token == "°C"


def test_part_names_from_caption_and_codes() -> None:
    """Names prefer caption slash, then text_a/text_b."""
    assert part_names(caption="current / avg", text_a="AF", text_b="", n_parts=2) == ("current", "avg")
    assert part_names(caption="Servo", text_a="MK1A", text_b="MK1B", n_parts=2) == ("MK1A", "MK1B")
    assert part_names(caption="AF", text_a="AF", text_b="", n_parts=1) == ("AF",)
    assert part_names(caption="", text_a="", text_b="", n_parts=0) == ()
    assert part_names(caption="OnlyLeft / ", text_a="A", text_b="B", n_parts=2) == ("A", "B")
    assert part_names(caption="Pair", text_a="", text_b="", n_parts=2) == ("Pair (1)", "Pair (2)")
    assert part_names(caption="", text_a="AF", text_b="WF", n_parts=1) == ("AF / WF",)
    assert part_names(caption="", text_a="", text_b="", n_parts=1) == ("Info",)


def test_part_names_qualify_short_requirement_half() -> None:
    """Bare ``wymag.`` is kept under the left caption so HA stays readable."""
    left, right = part_names(
        caption="Wymagana temp. pokoj. / wymag.",
        text_a="",
        text_b="",
        n_parts=2,
    )
    assert left == "Wymagana temp. pokoj."
    assert right == "Wymagana temp. pokoj. (wymag.)"
    # Stem contained in the left half (no trailing period) is also qualified.
    assert (
        part_names(
            caption="Wymagana temp. / wymag",
            text_a="",
            text_b="",
            n_parts=2,
        )[1]
        == "Wymagana temp. (wymag)"
    )


def test_part_names_dashed_valve_caption() -> None:
    """Dashed captions keep the full head; TextA/TextB terminal codes are ignored."""
    assert part_names(
        caption="Siłow. RLA3O / RLA3Z - pozycja / ruch",
        text_a="VA4",
        text_b="VA3",
        n_parts=2,
    ) == ("Siłow. RLA3O / RLA3Z - pozycja", "Siłow. RLA3O / RLA3Z - ruch")
    assert part_names(
        caption="Mieszana temp. VF1 - aktualna / wymag.",
        text_a="",
        text_b="",
        n_parts=2,
    ) == ("Mieszana temp. VF1 - aktualna", "Mieszana temp. VF1 - wymag.")
    assert part_names(
        caption="Temp. zewnętrz. AF - min / maks",
        text_a="AF",
        text_b="",
        n_parts=2,
    ) == ("Temp. zewnętrz. AF - min", "Temp. zewnętrz. AF - maks")
    assert part_names(
        caption="Servo - pozycja / ruch",
        text_a="",
        text_b="",
        n_parts=2,
    ) == ("Servo - pozycja", "Servo - ruch")
    # Dash without a dual role in the tail falls through.
    assert part_names(
        caption="Room - sensor",
        text_a="A",
        text_b="B",
        n_parts=2,
    ) == ("A", "B")
    # Empty role after the slash is rejected.
    assert part_names(
        caption="Head - left / ",
        text_a="",
        text_b="",
        n_parts=2,
    ) == ("Head - left /  (1)", "Head - left /  (2)")


def test_named_row_parse() -> None:
    """parse_info_row attaches names to parts."""
    parts = parse_info_row(
        value="0 % / STOP",
        caption="position / move",
        text_a="MK1A",
        text_b="MK1B",
    )
    assert len(parts) == 2
    assert parts[0].name == "position"
    assert parts[0].kind is InfoValueKind.NUMBER
    assert parts[0].unit_token == "%"
    assert parts[1].name == "move"
    assert parts[1].valve == "stop"
    single = parse_info_row(value="25,9 °C", caption="Temp. zewnętrz. AF")
    assert len(single) == 1
    assert single[0].name == "Temp. zewnętrz. AF"


def test_mixed_dual_row_uses_caption_and_text_token() -> None:
    """Number + text without a dual caption becomes caption + raw text."""
    parts = parse_info_row(
        value="18,9 °C / Tryb letni",
        caption="Średnia temp. zewnętrz.",
    )
    assert parts[0].name == "Średnia temp. zewnętrz."
    assert parts[0].kind is InfoValueKind.NUMBER
    assert parts[1].name == "Tryb letni"
    assert parts[1].kind is InfoValueKind.TEXT


def test_auto_comfort_paren_names_caption_and_effect() -> None:
    """Mode pairs keep caption on the selection and the inner token on the effect."""
    assert split_display("Auto(comfort)") == ["Auto", "comfort"]
    parts = parse_info_row(value="Auto(comfort)", caption="Tryb")
    assert parts[0].name == "Tryb"
    assert parts[0].raw == "Auto"
    assert parts[1].name == "comfort"
    assert parts[1].raw == "comfort"
    spaced = parse_info_row(value="Auto (Komfort)", caption="Tryb")
    assert spaced[0].name == "Tryb"
    assert spaced[0].raw == "Auto"
    assert spaced[1].name == "Komfort"
    assert spaced[1].raw == "Komfort"


def test_bare_mode_expands_to_selection_and_effect() -> None:
    """Bare regime values under a short caption become two identical mode parts."""
    parts = parse_info_row(value="Standby", caption="Tryb")
    assert len(parts) == 2
    assert parts[0].name == "Tryb"
    assert parts[0].raw == "Standby"
    assert parts[1].name == "Standby"
    assert parts[1].raw == "Standby"
    comfort = parse_info_row(value="Komfort", caption="Tryb")
    assert comfort[0].name == "Tryb"
    assert comfort[1].name == "Komfort"


def test_binary_plus_number_keeps_caption_names() -> None:
    """``OFF / 6 min`` must not name the binary entity ``OFF``."""
    parts = parse_info_row(
        value="OFF / 6 min",
        caption="Pompa obiegowa ZKP",
        text_a="VA2",
    )
    assert parts[0].name == "Pompa obiegowa ZKP"
    assert parts[0].kind is InfoValueKind.BINARY
    assert parts[1].name == "Pompa obiegowa ZKP (2)"
    assert parts[1].kind is InfoValueKind.NUMBER


def test_mixed_dual_keeps_indexed_names_for_two_numbers() -> None:
    """Two numeric halves keep ``Caption (1)/(2)`` when the caption is singular."""
    parts = parse_info_row(value="18,9 °C / 20,0 °C", caption="Pair")
    assert parts[0].name == "Pair (1)"
    assert parts[1].name == "Pair (2)"


def test_mixed_dual_text_then_number() -> None:
    """Text on the left keeps its raw token; the number side uses the caption."""
    parts = parse_info_row(value="Tryb letni / 18,9 °C", caption="Outdoor")
    assert parts[0].name == "Tryb letni"
    assert parts[1].name == "Outdoor"


def test_refine_mixed_dual_names_guards() -> None:
    """Defensive length and empty-raw edges stay stable."""
    empty = ()
    assert _refine_mixed_dual_names("X", ("a",), empty) == ("a",)
    num = InfoValuePart(kind=InfoValueKind.NUMBER, raw="1", number=1.0)
    text = InfoValuePart(kind=InfoValueKind.TEXT, raw="", text="")
    assert _refine_mixed_dual_names("", ("Info (1)", "Info (2)"), (num, text)) == ("Info", "Info")
    assert _refine_mixed_dual_names("M", ("M (1)", "M (2)"), (text, text)) == ("M", "M")
    # Non-mode dual text with an existing slash caption keeps those names.
    assert _refine_mixed_dual_names(
        "left / right",
        ("left", "right"),
        (
            InfoValuePart(kind=InfoValueKind.TEXT, raw="A", text="A"),
            InfoValuePart(kind=InfoValueKind.TEXT, raw="B", text="B"),
        ),
    ) == ("left", "right")


def test_mode_caption_helpers_skip_non_mode_rows() -> None:
    """Dashed / multi-word captions and non-text values stay single-part."""
    assert parse_info_row(value="Standby", caption="Room mode")[0].name == "Room mode"
    assert len(parse_info_row(value="Standby", caption="A / B")) == 1
    assert len(parse_info_row(value="OFF", caption="Tryb")) == 1
    assert len(parse_info_row(value="   ", caption="Tryb")) == 1


def test_binary_text_and_swapped_binary_number_names() -> None:
    """Binary+text and number+binary keep the panel caption on the switch side."""
    broken = parse_info_row(value="OFF / nie działa", caption="Pompa")
    assert broken[0].name == "Pompa"
    assert broken[1].name == "Pompa (2)"
    swapped = parse_info_row(value="6 min / OFF", caption="Pompa")
    assert swapped[0].name == "Pompa (1)"
    assert swapped[1].name == "Pompa"
    text_off = parse_info_row(value="alarm / OFF", caption="Status")
    assert text_off[0].name == "Status (1)"
    assert text_off[1].name == "Status"


def test_date_and_text_parts() -> None:
    """Dates and free text stay as text parts."""
    assert parse_part("28.08.2026").kind is InfoValueKind.TEXT
    assert parse_part("Tryb letni").kind is InfoValueKind.TEXT


def test_live_fixture_dual_rows_parse() -> None:
    """Every dual value in the live Info hex expands into two typed parts."""
    raw = bytes.fromhex((_FIXTURES / "info_page_data.hex").read_text().strip())
    dump = assemble_info_chunks([decode_info_chunk(raw)])
    dual = 0
    for item in dump.items:
        if item.is_title:
            continue
        value = expand_info_value_with(lambda i: f"T{i}", item.value)
        if value.upper().startswith("S/N"):
            continue
        parts = parse_info_display(value)
        if " / " in value or ("(" in value and ")" in value):
            assert len(parts) == 2, value
            dual += 1
        else:
            assert len(parts) == 1, value
    assert dual >= 18
