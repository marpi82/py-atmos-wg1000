#!/usr/bin/env python3
"""Offline audit of Info entity names (no Home Assistant, no release needed).

Examples::

    uv run python scripts/audit_info_names.py
    uv run python scripts/audit_info_names.py --strict
    uv run python scripts/audit_info_names.py --langs

Exit code 1 when ``--strict`` and any smell is found.
"""

from __future__ import annotations

import argparse
import sys

from pyatmos_wg1000.protocol.info_naming_corpus import (
    MODE_CAPTIONS,
    ha_labels,
    mode_caption_corpus,
    panel_corpus,
    run_case,
)


def _print_case(case_id: str, device: str, caption: str, value: str, parts, smells: list[str]) -> None:
    status = "FAIL" if smells else "ok"
    print(f"[{status}] {case_id}")
    print(f"  caption={caption!r} value={value!r}")
    for label in ha_labels(device, parts):
        print(f"  → {label}")
    for part in parts:
        print(f"     name={part.name!r} kind={part.kind} raw={part.raw!r}")
    for smell in smells:
        print(f"  !! {smell}")
    print()


def main(argv: list[str] | None = None) -> int:
    """Run the naming corpus and print a readable report."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit 1 when any smell is found")
    parser.add_argument("--langs", action="store_true", help="Include mode captions for all gateway languages")
    parser.add_argument("--fail-only", action="store_true", help="Print only failing cases")
    args = parser.parse_args(argv)

    cases = list(panel_corpus())
    if args.langs:
        cases.extend(mode_caption_corpus())

    failed = 0
    for case in cases:
        parts, smells = run_case(case)
        if smells:
            failed += 1
        if args.fail_only and not smells:
            continue
        _print_case(case.id, case.device, case.caption, case.value, parts, smells)

    print(f"Mode captions known: {len(MODE_CAPTIONS)} ({', '.join(MODE_CAPTIONS)})")
    print(f"Cases: {len(cases)}, smells: {failed}")
    if args.strict and failed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
