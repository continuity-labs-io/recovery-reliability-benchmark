"""Axis-specific diagnostic note constants and pure row-note builder for reports."""

from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

NOTE_NO_VARIATION = "no variation across units"
NOTE_RELIABILITY_AT_CHANCE = "reliability at chance"
NOTE_SENSITIVITY_AT_CHANCE = "sensitivity at chance"
NOTE_DOES_NOT_BEAT_REFERENCE = "does not beat reference"
NOTES_SEPARATOR = "; "
EMPTY_NOTES = "—"


def row_notes(
    measure_entry: Mapping[str, Any],
    condition_pair: str | None = None,
    is_first_row: bool = True,
    measure: str | None = None,
) -> list[str]:
    """Return the ordered list of diagnostic notes for a table row or report line.

    Measure-level notes (reliability and censoring) appear on the measure's first
    row only; pair-level notes (sensitivity and reference comparison) appear on
    the row of their condition pair. Within a row, notes are ordered as:
    reliability note, ``sensitivity at chance``, ``does not beat reference``,
    then censoring.

    Args:
        measure_entry: Per-measure evaluation dictionary from ``run_with_inputs()``.
        condition_pair: Condition-pair key ``"<first>|<second>"`` for the row, or
            ``None`` for a one-condition row or measure-level line.
        is_first_row: Whether the row is the first row emitted for this measure.
        measure: Optional raw measure name used to look up ``<measure>_censored``
            in ``measure_entry["flags"]``.

    Returns:
        Ordered list of lowercase diagnostic note strings (empty when none apply).
    """
    flags = measure_entry.get("flags") or {}
    cens_note: str | None = None
    if is_first_row and measure:
        flag_key = f"{measure}_censored"
        items = [(c, int(cf.get(flag_key, 0))) for c, cf in flags.items() if int(cf.get(flag_key, 0)) > 0]
        if items:
            cens_note = (
                f"censored: {items[0][1]} units"
                if len(flags) == 1
                else "censored: " + ", ".join(f"{c} {cnt}" for c, cnt in items)
            )

    if measure_entry.get("status") == "not_scored":
        if not is_first_row:
            return []
        n_min = min(int(v["n_units_scored"]) for v in measure_entry["per_condition"].values())
        return [f"not scored ({n_min} units)", *([cens_note] if cens_note else [])]

    notes: list[str] = []
    if is_first_row:
        headline = measure_entry["headline"]
        null = measure_entry["null"]
        p95 = null.get("p95_rho")
        if headline.get("r_undefined"):
            notes.append(NOTE_NO_VARIATION)
        elif p95 is not None and not math.isnan(p95) and headline["rho"] <= p95:
            notes.append(NOTE_RELIABILITY_AT_CHANCE)

    if condition_pair is not None:
        pair_sens = (measure_entry.get("sensitivity") or {}).get(condition_pair)
        if pair_sens is not None:
            if pair_sens.get("above_null") is False:
                notes.append(NOTE_SENSITIVITY_AT_CHANCE)
            if pair_sens.get("beats_reference") is False:
                notes.append(NOTE_DOES_NOT_BEAT_REFERENCE)

    if cens_note is not None:
        notes.append(cens_note)
    return notes
