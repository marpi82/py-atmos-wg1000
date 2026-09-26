"""Pytest wrapper around the Info naming corpus."""

from __future__ import annotations

import pytest

from pyatmos_wg1000.protocol.info_naming_corpus import mode_caption_corpus, panel_corpus, run_case


@pytest.mark.parametrize("case", panel_corpus(), ids=lambda c: c.id)
def test_panel_naming_corpus(case) -> None:
    """Live PL panel rows keep the expected HA-facing names."""
    _parts, smells = run_case(case)
    assert smells == [], smells


@pytest.mark.parametrize("case", mode_caption_corpus(), ids=lambda c: c.id)
def test_mode_captions_all_gateway_langs(case) -> None:
    """Every known gateway mode caption yields device + caption entities."""
    parts, smells = run_case(case)
    assert smells == [], smells
    assert parts[0].name == ""
    assert parts[1].name == case.caption
