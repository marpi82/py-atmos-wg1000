"""Pytest wrapper around the Info naming corpus."""

from __future__ import annotations

import pytest

from pyatmos_wg1000.protocol.info_naming_corpus import (
    NamingCase,
    mode_caption_corpus,
    naming_smells,
    panel_corpus,
    run_case,
)
from pyatmos_wg1000.protocol.info_value import InfoValueKind, InfoValuePart


@pytest.mark.parametrize("case", panel_corpus(), ids=lambda c: c.id)
def test_panel_naming_corpus(case: NamingCase) -> None:
    """Live PL panel rows keep the expected HA-facing names."""
    _parts, smells = run_case(case)
    assert smells == [], smells


@pytest.mark.parametrize("case", mode_caption_corpus(), ids=lambda c: c.id)
def test_mode_captions_all_gateway_langs(case: NamingCase) -> None:
    """Every known gateway mode caption yields device + caption entities."""
    parts, smells = run_case(case)
    assert smells == [], smells
    assert parts[0].name == ""
    assert parts[1].name == case.caption


def _text(name: str, raw: str) -> InfoValuePart:
    return InfoValuePart(kind=InfoValueKind.TEXT, raw=raw, text=raw, name=name)


def test_naming_smells_detect_common_regressions() -> None:
    """Smell helpers flag empty rows, indexed Tryb, and name==state."""
    assert naming_smells("D", ()) == ["no parts"]
    assert "both parts nameless" in naming_smells("D", (_text("", "A"), _text("", "B")))[0]
    indexed = naming_smells("TUV", (_text("Tryb (1)", "Auto"), _text("Tryb (2)", "Komfort")))
    assert any("indexed mode name" in item for item in indexed)
    assert any("Dozwolone" in item for item in naming_smells("TUV", (_text("Dozwolone", "Dozwolone"),)))
    dup = naming_smells("D", (_text("", "X"), _text("", "X")))
    assert any("duplicate HA labels" in item for item in dup)


def test_run_case_reports_expectation_mismatches() -> None:
    """Wrong expect_names / expect_raws become smells instead of silent passes."""
    _parts, smells = run_case(
        NamingCase(
            id="mismatch",
            caption="Tryb",
            value="Komfort",
            expect_names=("nope",),
            expect_raws=("nope",),
        )
    )
    assert any(item.startswith("names ") for item in smells)
    assert any(item.startswith("raws ") for item in smells)
