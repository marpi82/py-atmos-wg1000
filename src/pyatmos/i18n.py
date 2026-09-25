"""Language tables downloaded from the gateway.

This is the heavy, config-time catalog. Runtime acquisition
(:class:`pyatmos.feed.AtmosFeed`) does not use it.

``Lang.json`` holds UI strings keyed by text id. ``texty_brana.json`` holds
regulator strings keyed by number. Both tables share the same language
columns. The gateway stores ``USER1_LANG`` as a zero-based language index.
The UI adds one, because column 0 is the row id (``SetLang`` in ``Pages.js``).
Missing or blank cells fall back to English (``LangDef`` in the UI).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from pyatmos.errors import ProtocolError
from pyatmos.protocol.catalog import Id33
from pyatmos.protocol.enums import Channel

if TYPE_CHECKING:
    from pyatmos.client import AtmosClient

_UI_FILE = "Lang.json"
_REGULATOR_FILE = "texty_brana.json"
_FALLBACK = "ENG"
_ID_COLUMN = "ID"
_NAME_ROW = "TXT_LANG"
_FLAG_ROW = "TXT_FLAG"
_REGULATOR_PREFIXES = ("T16_", "T160", "T161", "T162", "T163")
_Row = tuple[str | None, ...]


class Language(BaseModel):
    """One column of the gateway language tables."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    name: str
    flag: str
    column: int = Field(ge=1)
    gateway_index: int = Field(ge=0)


class LanguageCatalog:
    """Translations for one selected language, with an English fallback.

    Args:
        ui_rows: UI table keyed by string id. Each value is the full row,
            including the id in column 0.
        regulator_rows: Regulator table keyed by numeric id.
        columns: Column names. Index 0 is ``ID``.
        language: Column code (``POL``) or the gateway's ``USER1_LANG`` index.
        fallback: Column used when the selected cell is empty. The UI uses ``ENG``.
    """

    def __init__(
        self,
        ui_rows: Mapping[str, _Row],
        regulator_rows: Mapping[int, _Row],
        columns: tuple[str, ...],
        *,
        language: str | int = _FALLBACK,
        fallback: str = _FALLBACK,
    ) -> None:
        """Index the tables and select the starting language."""
        if not columns or columns[0] != _ID_COLUMN:
            raise ProtocolError("language table must start with an ID column")
        self._ui = dict(ui_rows)
        self._regulator = dict(regulator_rows)
        self._columns = columns
        self._fallback_column = _column_for_code(columns, fallback)
        self._language = self._resolve(language)

    @classmethod
    def from_bytes(
        cls,
        ui: bytes,
        regulator: bytes,
        *,
        language: str | int = _FALLBACK,
        fallback: str = _FALLBACK,
    ) -> LanguageCatalog:
        """Build a catalog from the two JSON files the gateway sends.

        Args:
            ui: ``Lang.json`` bytes. UTF-8, optionally with a BOM.
            regulator: ``texty_brana.json`` bytes.
            language: Column code or ``USER1_LANG`` index.
            fallback: Column code used for empty cells.

        Returns:
            A catalog with ``language`` selected.
        """
        ui_columns, ui_rows, _ignored = _parse_table(ui, numeric_keys=False)
        reg_columns, _ignored_rows, reg_rows = _parse_table(regulator, numeric_keys=True)
        if ui_columns != reg_columns:
            raise ProtocolError("UI and regulator language tables use different columns")
        return cls(ui_rows, reg_rows, ui_columns, language=language, fallback=fallback)

    @classmethod
    async def fetch(cls, client: AtmosClient, *, language: str | int | None = None) -> LanguageCatalog:
        """Download both language files and select a language.

        When ``language`` is omitted, Hello is sent and the gateway's
        ``USER1_LANG`` register is read. That register is available before
        login, but only after Hello. The value is the column index.

        Args:
            client: Connected client. Login is not required for the files.
            language: Column code, gateway index, or ``None`` to follow the gateway.

        Returns:
            The downloaded catalog.
        """
        ui = await client.download_file(_UI_FILE)
        regulator = await client.download_file(_REGULATOR_FILE)
        selected = language
        if selected is None:
            # Parameter reads are answered only after Hello.
            await client.hello()
            records = await client.read_registers([Id33.USER1_LANG], channel=Channel.WS)
            selected = records[0].value if records and records[0].value is not None else _FALLBACK
        return cls.from_bytes(ui, regulator, language=selected)

    @property
    def language(self) -> Language:
        """The column currently used for :meth:`text`."""
        return self._language

    def languages(self) -> tuple[Language, ...]:
        """Return every language column, in table order.

        Names and flags come from the ``TXT_LANG`` and ``TXT_FLAG`` rows.
        """
        names = self._ui.get(_NAME_ROW)
        flags = self._ui.get(_FLAG_ROW)
        found: list[Language] = []
        for column, code in enumerate(self._columns):
            if column == 0:
                continue
            found.append(
                Language(
                    code=code,
                    name=_cell(names, column) or code,
                    flag=_cell(flags, column),
                    column=column,
                    gateway_index=column - 1,
                )
            )
        return tuple(found)

    def select(self, language: str | int) -> Language:
        """Switch the active language.

        Args:
            language: Column code such as ``POL``, or the gateway index
                (``8`` selects the ninth column because column 0 is the id).

        Returns:
            The language now in effect.
        """
        self._language = self._resolve(language)
        return self._language

    def text(self, key: str) -> str | None:
        """Translate one UI or regulator key.

        Regulator keys use the UI prefixes ``T16_``, ``T160``, ``T161``,
        ``T162``, and ``T163``. The number after the four-character prefix is
        the row id in ``texty_brana.json``. Other keys are looked up in
        ``Lang.json``.

        The catalog does not apply the panel's custom circuit names. Those
        are live device strings, not rows in the file.

        Args:
            key: Text id, for example ``TXT2_LOGIN_BTN`` or ``T16_90``.

        Returns:
            The translated string, or ``None`` when the key is absent.
            An empty cell falls back to English.
        """
        regulator_id = _regulator_id(key)
        row = self._regulator.get(regulator_id) if regulator_id is not None else self._ui.get(key)
        if row is None:
            return None
        selected = _cell(row, self._language.column)
        if selected:
            return selected
        fallback = _cell(row, self._fallback_column)
        return fallback or None

    def _resolve(self, language: str | int) -> Language:
        if isinstance(language, int) or _digits(language):
            column = int(language) + 1
            if not 0 < column < len(self._columns):
                raise ProtocolError(f"language index {language} is outside the table")
        else:
            column = _column_for_code(self._columns, str(language))
        known = {item.column: item for item in self.languages()}
        return known[column]


def _parse_table(
    raw: bytes,
    *,
    numeric_keys: bool,
) -> tuple[tuple[str, ...], dict[str, _Row], dict[int, _Row]]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("language file is not JSON") from exc
    if not isinstance(payload, dict):
        raise ProtocolError("language file must be an object")
    columns_raw = payload.get("columns")
    data = payload.get("data")
    if not isinstance(columns_raw, list) or not isinstance(data, list):
        raise ProtocolError("language file needs columns and data")
    columns = tuple(str(column) for column in columns_raw)
    ui_rows: dict[str, _Row] = {}
    reg_rows: dict[int, _Row] = {}
    width = len(columns)
    for item in data:
        if not isinstance(item, list) or not item:
            continue
        padded = tuple(_as_cell(cell) for cell in item[:width])
        if len(padded) < width:
            padded = padded + (None,) * (width - len(padded))
        key = item[0]
        if numeric_keys and isinstance(key, int):
            reg_rows[key] = padded
        elif isinstance(key, str):
            ui_rows[key] = padded
    return columns, ui_rows, reg_rows


def _as_cell(cell: object) -> str | None:
    if cell is None:
        return None
    if isinstance(cell, str):
        return cell
    return str(cell)


def _cell(row: _Row | None, column: int) -> str:
    if row is None or column >= len(row):
        return ""
    value = row[column]
    if value is None:
        return ""
    stripped = value.strip()
    return "" if stripped == "" else stripped


def _column_for_code(columns: tuple[str, ...], code: str) -> int:
    wanted = code.strip().upper()
    for index, name in enumerate(columns):
        if name.upper() == wanted:
            return index
    raise ProtocolError(f"language {code} is not in the table")


def _digits(language: str | int) -> bool:
    return isinstance(language, str) and language.strip().lstrip("-").isdigit()


def _regulator_id(key: str) -> int | None:
    if len(key) <= 4 or not key.startswith(_REGULATOR_PREFIXES):
        return None
    number = key[4:]
    if not number.isdigit():
        return None
    return int(number)
