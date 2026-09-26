"""Corpus and smell checks for Info entity naming (offline, no Home Assistant).

Run via ``scripts/audit_info_names.py`` or ``pytest tests/test_info_naming_corpus.py``.
"""

from __future__ import annotations

from dataclasses import dataclass

from pyatmos_wg1000.protocol.info_value import InfoValuePart, parse_info_row

# Single-token Info "mode" captions as shown on the WG1000 panel (gateway UI language).
# Extend when a live dump shows another spelling; keep entries space-free.
MODE_CAPTIONS: dict[str, str] = {
    "cs": "Režim",
    "da": "Drift",
    "de": "Betrieb",
    "en": "Mode",
    "es": "Modo",
    "et": "Režiim",
    "fr": "Mode",
    "hu": "Üzemmód",
    "it": "Modo",
    "pl": "Tryb",
    "pt": "Modo",
    "ro": "Mod",
    "ru": "Режим",
    "sl": "Način",
    "sv": "Läge",
}

# Bare / parenthetical regime values seen on panels (gateway language).
MODE_VALUES: dict[str, dict[str, str]] = {
    "pl": {
        "comfort": "Komfort",
        "standby": "Czuwanie",
        "auto_comfort": "Auto (Komfort)",
        "summer": "Lato",
    },
    "en": {
        "comfort": "Comfort",
        "standby": "Standby",
        "auto_comfort": "Auto (comfort)",
        "summer": "Summer",
    },
    "de": {
        "comfort": "Komfort",
        "standby": "Standby",
        "auto_comfort": "Auto (Komfort)",
        "summer": "Sommer",
    },
}


@dataclass(frozen=True)
class NamingCase:
    """One panel row to name."""

    id: str
    caption: str
    value: str
    text_a: str = ""
    text_b: str = ""
    device: str = "Device"
    expect_names: tuple[str, ...] | None = None
    expect_raws: tuple[str, ...] | None = None


def panel_corpus() -> tuple[NamingCase, ...]:
    """Real panel rows from PL live installs (extend as dumps arrive)."""
    return (
        NamingCase(
            id="mode-bare-comfort",
            device="Dom",
            caption="Dom",
            text_a="Tryb",
            value="Komfort",
            expect_names=("", "Tryb"),
            expect_raws=("Komfort", "Komfort"),
        ),
        NamingCase(
            id="mode-bare-standby",
            device="Poddasze",
            caption="Poddasze",
            text_a="Tryb",
            value="Standby",
            expect_names=("", "Tryb"),
            expect_raws=("Standby", "Standby"),
        ),
        NamingCase(
            id="mode-auto-comfort",
            device="CWU",
            caption="",
            text_a="Tryb",
            value="Auto (Komfort)",
            expect_names=("", "Tryb"),
            expect_raws=("Komfort", "Auto"),
        ),
        NamingCase(
            id="mode-auto-comfort-nospace",
            device="CWU",
            caption="",
            text_a="Tryb",
            value="Auto(comfort)",
            expect_names=("", "Tryb"),
            expect_raws=("comfort", "Auto"),
        ),
        NamingCase(
            id="pump-off-runtime",
            device="TUV",
            caption="Pompa obiegowa ZKP",
            value="OFF / 6 min",
            text_a="VA2",
            expect_names=("Pompa obiegowa ZKP", "Pompa obiegowa ZKP (2)"),
        ),
        NamingCase(
            id="cycle-button-allowed",
            device="TUV",
            caption="Przycisk cykli ZRF",
            value="25,4 °C / Dozwolone",
            text_a="VI5",
            expect_names=("Przycisk cykli ZRF", "Przycisk cykli ZRF (2)"),
            expect_raws=("25,4 °C", "Dozwolone"),
        ),
        NamingCase(
            id="outdoor-avg-summer",
            device="AF",
            caption="Średnia temp. zewnętrz.",
            value="18,9 °C / Tryb letni",
            expect_names=("Średnia temp. zewnętrz.", "Średnia temp. zewnętrz. (2)"),
        ),
        NamingCase(
            id="mixed-vf1",
            device="O1",
            caption="Mieszana temp. VF1 - aktualna / wymag.",
            value="35,0 °C / 40,0 °C",
            expect_names=("Mieszana temp. VF1 - aktualna", "Mieszana temp. VF1 - wymag."),
        ),
        NamingCase(
            id="valve-rla",
            device="O3",
            caption="Siłow. RLA3O / RLA3Z - pozycja / ruch",
            value="0 % / STOP",
            text_a="VA4",
            text_b="VA3",
            expect_names=("Siłow. RLA3O / RLA3Z - pozycja", "Siłow. RLA3O / RLA3Z - ruch"),
        ),
        NamingCase(
            id="af-min-max",
            device="AF",
            caption="Temp. zewnętrz. AF - min / maks",
            value="-5,0 °C / 12,0 °C",
            text_a="AF",
            expect_names=("Temp. zewnętrz. AF - min", "Temp. zewnętrz. AF - maks"),
        ),
    )


def mode_caption_corpus() -> tuple[NamingCase, ...]:
    """Mode rows for every known gateway UI language label (TextA path).

    Live Info puts OwnText circuit names in the caption and the catalog
    ``Tryb``/``Mode``/… string in TextA (regulator id 1281).
    """
    cases: list[NamingCase] = []
    for lang, label in MODE_CAPTIONS.items():
        values = MODE_VALUES.get(lang) or MODE_VALUES["en"]
        cases.append(
            NamingCase(
                id=f"mode-{lang}-bare",
                device=f"Circuit-{lang}",
                caption=f"Circuit-{lang}",
                text_a=label,
                value=values["comfort"],
                expect_names=("", label),
                expect_raws=(values["comfort"], values["comfort"]),
            )
        )
        cases.append(
            NamingCase(
                id=f"mode-{lang}-auto",
                device=f"TUV-{lang}",
                caption="",
                text_a=label,
                value=values["auto_comfort"],
                expect_names=("", label),
            )
        )
    return tuple(cases)


def ha_labels(device: str, parts: tuple[InfoValuePart, ...]) -> tuple[str, ...]:
    """Format parts the way the user reads them in HA (device or entity name + state)."""
    out: list[str] = []
    for part in parts:
        label = device if not part.name else part.name
        out.append(f"{label}: {part.raw}")
    return tuple(out)


def naming_smells(device: str, parts: tuple[InfoValuePart, ...]) -> list[str]:
    """Return human-readable problems with a named row."""
    smells: list[str] = []
    if not parts:
        return ["no parts"]
    names = tuple(part.name for part in parts)
    if len(parts) == 2 and names[0] == "" and names[1] == "":
        smells.append("both parts nameless (would show as two device titles)")
    mode_caption_names = frozenset(MODE_CAPTIONS.values())
    for part in parts:
        if part.name in {f"{caption} (1)" for caption in mode_caption_names} | {
            f"{caption} (2)" for caption in mode_caption_names
        }:
            smells.append(f"indexed mode name {part.name!r}")
        if part.name and part.name == part.raw and part.name not in mode_caption_names:
            smells.append(f"name equals state {part.name!r}")
    labels = ha_labels(device, parts)
    if len(labels) == 2 and labels[0] == labels[1]:
        smells.append(f"duplicate HA labels {labels[0]!r}")
    return smells


def run_case(case: NamingCase) -> tuple[tuple[InfoValuePart, ...], list[str]]:
    """Parse one case and return parts plus smell strings."""
    parts = parse_info_row(
        value=case.value,
        caption=case.caption,
        text_a=case.text_a,
        text_b=case.text_b,
    )
    smells = naming_smells(case.device, parts)
    if case.expect_names is not None:
        got = tuple(part.name for part in parts)
        if got != case.expect_names:
            smells.append(f"names {got!r} != expected {case.expect_names!r}")
    if case.expect_raws is not None:
        got = tuple(part.raw for part in parts)
        if got != case.expect_raws:
            smells.append(f"raws {got!r} != expected {case.expect_raws!r}")
    return parts, smells


__all__ = [
    "MODE_CAPTIONS",
    "MODE_VALUES",
    "NamingCase",
    "ha_labels",
    "mode_caption_corpus",
    "naming_smells",
    "panel_corpus",
    "run_case",
]
