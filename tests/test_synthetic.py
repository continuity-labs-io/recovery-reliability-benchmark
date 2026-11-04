"""Tests for the synthetic dataset generator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from recovery_reliability_benchmark.contract import read_tables, validate
from recovery_reliability_benchmark.synthetic import make_tables

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_default_matches_committed_examples() -> None:
    units, responses = make_tables(n_units=15, n_trials=20, seed=0)
    expected_units, expected_responses = read_tables(
        EXAMPLES_DIR / "units.csv",
        EXAMPLES_DIR / "responses.csv",
    )
    for df in (responses, expected_responses):
        df["trial_index"] = df["trial_index"].astype("int64")
        df["stim_time_ns"] = df["stim_time_ns"].astype("int64")

    pd.testing.assert_frame_equal(units, expected_units, check_dtype=False)
    pd.testing.assert_frame_equal(responses, expected_responses, check_dtype=False)


def test_true_columns_present() -> None:
    units_rel, _ = make_tables(reliability=0.8)
    assert "tau_true" in units_rel.columns
    assert "amplitude_true" in units_rel.columns

    units_default, _ = make_tables()
    assert "tau_true" not in units_default.columns
    assert "amplitude_true" not in units_default.columns


def test_variance_ratio_matches_reliability() -> None:
    for rho in (0.3, 0.8, 0.95):
        units, responses = make_tables(n_units=20000, n_trials=10, reliability=rho, seed=1)
        unit_means = responses.groupby("unit_id", sort=False)["tau"].mean()
        aligned = units.set_index("unit_id")["tau_true"].loc[unit_means.index]
        ratio = float(aligned.var(ddof=1) / unit_means.var(ddof=1))
        assert abs(ratio - rho) < 0.02


def test_condition_offsets_shift_means() -> None:
    _, responses = make_tables(
        n_units=200,
        n_trials=20,
        conditions=("A", "B"),
        reliability=0.8,
        condition_offsets={"B": 5.0},
        seed=2,
    )
    mean_a = float(responses.loc[responses["condition"] == "A", "tau"].mean())
    mean_b = float(responses.loc[responses["condition"] == "B", "tau"].mean())
    assert abs((mean_b - mean_a) - 5.0) < 0.3


def test_reliability_dataset_conforms() -> None:
    units, responses = make_tables(n_units=15, n_trials=20, reliability=0.8)
    result = validate(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0)
    assert result["conformance"] == "fully_conforming"


def test_bad_arguments() -> None:
    with pytest.raises(ValueError):
        make_tables(reliability=1.0)
    with pytest.raises(ValueError):
        make_tables(reliability=0.0)
    with pytest.raises(ValueError):
        make_tables(conditions=("A",), condition_offsets={"Z": 1.0})
