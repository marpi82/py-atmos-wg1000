"""Language catalog: column selection and the two gateway tables."""

from __future__ import annotations

import json

import pytest

from pyatmos_wg1000.errors import ProtocolError
from pyatmos_wg1000.i18n import LanguageCatalog

_COLUMNS = ["ID", "CES", "ENG", "POL"]
_UI = json.dumps(
    {
        "columns": _COLUMNS,
        "data": [
            ["TXT_LANG", "Čeština", "English", "Polski"],
            ["TXT_FLAG", "cz", "gb", "pl"],
            ["TXT2_LOGIN_BTN", "Přihlásit se", "Log in", "Zaloguj"],
            ["TXT_BLANK", "z ces", "from eng", None],
        ],
    }
).encode()
_REG = json.dumps(
    {
        "columns": _COLUMNS,
        "data": [[90, "Okruh", "Circuit", "Obieg"]],
    }
).encode()


def _catalog(language: str | int = "ENG") -> LanguageCatalog:
    return LanguageCatalog.from_bytes(_UI, _REG, language=language)


def test_languages_follow_the_table_columns() -> None:
    """Each language column is listed with its native name and gateway index."""
    codes = [(item.code, item.gateway_index, item.name) for item in _catalog().languages()]
    assert codes == [("CES", 0, "Čeština"), ("ENG", 1, "English"), ("POL", 2, "Polski")]


def test_gateway_index_skips_the_id_column() -> None:
    """USER1_LANG 2 selects POL, the third language, because column 0 is the id."""
    catalog = _catalog(2)
    assert catalog.language.code == "POL"
    assert catalog.text("TXT2_LOGIN_BTN") == "Zaloguj"
    assert catalog.text("T16_90") == "Obieg"


def test_code_selection_and_english_fallback() -> None:
    """A column code selects that language, and a blank cell falls back to English."""
    catalog = _catalog("pol")
    assert catalog.select("CES").code == "CES"
    assert catalog.text("TXT_BLANK") == "z ces"
    catalog.select("POL")
    assert catalog.text("TXT_BLANK") == "from eng"
    assert catalog.text("MISSING") is None


def test_unknown_language_is_rejected() -> None:
    """A code or index outside the table does not silently pick a column."""
    with pytest.raises(ProtocolError):
        _catalog("FRA")
    with pytest.raises(ProtocolError):
        _catalog(9)
