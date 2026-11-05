"""Tests for the synthetic dataset generator."""

from __future__ import annotations

import hashlib

import pytest

from recovery_reliability_benchmark.contract import validate
from recovery_reliability_benchmark.synthetic import make_tables


def test_default_path_unchanged() -> None:
    units, responses = make_tables(n_units=15, n_trials=20, seed=0)
    units_sha = hashlib.sha256(units.to_csv(index=False).encode("utf-8")).hexdigest()
    responses_sha = hashlib.sha256(responses.to_csv(index=False).encode("utf-8")).hexdigest()
    assert units_sha == "976c588a995ee915fee0029d142143b849fe1b56bb519c4e6cc00cefaeccbc23"
    assert responses_sha == "b19b83abc1f078e2c1c9218db1e14bfd48c14abf630c2dc36a88991cba213c3a"


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
    units, responses = make_tables(n_units=30, n_trials=20, reliability=0.8)
    result = validate(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0)
    assert result["conformance"] == "fully_conforming"


def test_bad_arguments() -> None:
    with pytest.raises(ValueError):
        make_tables(reliability=1.0)
    with pytest.raises(ValueError):
        make_tables(reliability=0.0)
    with pytest.raises(ValueError):
        make_tables(conditions=("A",), condition_offsets={"Z": 1.0})
