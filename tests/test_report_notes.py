"""Unit tests for axis-specific diagnostic notes in report_notes.py."""

from __future__ import annotations

from recovery_reliability_benchmark.report_notes import (
    NOTE_DOES_NOT_BEAT_REFERENCE,
    NOTE_NO_VARIATION,
    NOTE_RELIABILITY_AT_CHANCE,
    NOTE_SENSITIVITY_AT_CHANCE,
    row_notes,
)


def test_reliability_below_null_one_condition() -> None:
    entry = {
        "headline": {"rho": 0.20, "r_undefined": False},
        "null": {"p95_rho": 0.35},
    }
    assert row_notes(entry) == [NOTE_RELIABILITY_AT_CHANCE]
    assert row_notes(entry) == ["reliability at chance"]


def test_reliability_equal_to_null_counts_as_at_chance() -> None:
    entry = {
        "headline": {"rho": 0.35, "r_undefined": False},
        "null": {"p95_rho": 0.35},
    }
    assert row_notes(entry) == ["reliability at chance"]


def test_reliability_above_null_one_condition_has_no_notes() -> None:
    entry = {
        "headline": {"rho": 0.90, "r_undefined": False},
        "null": {"p95_rho": 0.35},
    }
    assert row_notes(entry) == []


def test_undefined_reliability_reports_no_variation_only() -> None:
    entry = {
        "headline": {"rho": 0.0, "r_undefined": True},
        "null": {"p95_rho": 0.0},
    }
    notes = row_notes(entry)
    assert notes == [NOTE_NO_VARIATION]
    assert notes == ["no variation across units"]
    assert "reliability at chance" not in notes


def test_two_conditions_pair_sensitivity_at_chance() -> None:
    entry = {
        "headline": {"rho": 0.90, "r_undefined": False},
        "null": {"p95_rho": 0.35},
        "sensitivity": {
            "control|slowed": {"above_null": False, "beats_reference": True},
        },
    }
    assert row_notes(entry, "control|slowed") == [NOTE_SENSITIVITY_AT_CHANCE]
    assert row_notes(entry, "control|slowed") == ["sensitivity at chance"]


def test_pair_sensitivity_at_chance_and_below_reference_order() -> None:
    entry = {
        "headline": {"rho": 0.90, "r_undefined": False},
        "null": {"p95_rho": 0.35},
        "sensitivity": {
            "control|slowed": {"above_null": False, "beats_reference": False},
        },
    }
    assert row_notes(entry, "control|slowed") == [
        NOTE_SENSITIVITY_AT_CHANCE,
        NOTE_DOES_NOT_BEAT_REFERENCE,
    ]
    assert row_notes(entry, "control|slowed") == [
        "sensitivity at chance",
        "does not beat reference",
    ]


def test_pair_beats_reference_none_omits_reference_note() -> None:
    entry = {
        "headline": {"rho": 0.90, "r_undefined": False},
        "null": {"p95_rho": 0.35},
        "sensitivity": {
            "control|slowed": {"above_null": True, "beats_reference": None},
        },
    }
    assert row_notes(entry, "control|slowed") == []


def test_first_and_second_pair_rows_note_order_and_scoping() -> None:
    entry = {
        "headline": {"rho": 0.20, "r_undefined": False},
        "null": {"p95_rho": 0.35},
        "sensitivity": {
            "control|slowed": {"above_null": False, "beats_reference": False},
            "control|treated": {"above_null": False, "beats_reference": True},
        },
        "flags": {
            "control": {"t_return_censored": 4},
            "slowed": {"t_return_censored": 7},
            "treated": {"t_return_censored": 0},
        },
    }
    first = row_notes(entry, "control|slowed", is_first_row=True, measure="t_return")
    assert first == [
        "reliability at chance",
        "sensitivity at chance",
        "does not beat reference",
        "censored: control 4, slowed 7",
    ]
    assert first[0] == "reliability at chance"
    assert first[-1] == "censored: control 4, slowed 7"

    second = row_notes(entry, "control|treated", is_first_row=False, measure="t_return")
    assert second == ["sensitivity at chance"]
