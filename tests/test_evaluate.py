"""Tests for the within-session reliability ceiling evaluator."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import recovery_reliability_benchmark.evaluate as evaluate
from recovery_reliability_benchmark.contract import read_tables, validate
from recovery_reliability_benchmark.evaluate import (
    ceiling,
    census,
    main,
    positive_control,
    run,
    split_halves,
)
from recovery_reliability_benchmark.synthetic import make_tables


def test_split_ranks_within_group() -> None:
    _, responses = make_tables(n_units=8, n_trials=5, conditions=("A", "B"))
    responses["ti"] = (responses["trial_index"].astype(float)) ** 2
    halves = split_halves(responses, ["ti"], ["A", "B"])
    row = halves.loc[("u00", "B")]
    assert row["n_A"] == 3
    assert row["n_B"] == 2
    assert row["ti_A"] == pytest.approx((25.0 + 49.0 + 81.0) / 3.0)
    assert row["ti_B"] == pytest.approx((36.0 + 64.0) / 2.0)


def test_odd_trials_flag() -> None:
    _, resp_odd = make_tables(n_units=8, n_trials=11)
    halves_odd = split_halves(resp_odd, ["tau"], ["A"])
    assert ceiling(halves_odd, "tau", center=False)["odd_trials"] is True

    _, resp_even = make_tables(n_units=8, n_trials=10)
    halves_even = split_halves(resp_even, ["tau"], ["A"])
    assert ceiling(halves_even, "tau", center=False)["odd_trials"] is False


def test_positive_control_large() -> None:
    pc = positive_control(reliability=0.8, n_units=2000, n_trials=10, seed=0)
    assert abs(pc["recovered"] - 0.8) <= 0.02


def test_positive_control_default_passes() -> None:
    assert positive_control()["passed"] is True


def test_single_condition_estimates_agree() -> None:
    units, responses = make_tables(n_units=15, n_trials=20, reliability=0.8)
    res = run(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0, n_perm=20)
    tau = res["measures"]["tau"]
    assert tau["headline_kind"] == "per_condition"
    assert tau["pooled"]["centered"]["rho"] == pytest.approx(tau["pooled"]["uncentered"]["rho"])
    assert tau["pooled"]["uncentered"]["rho"] == pytest.approx(tau["per_condition"]["A"]["rho"])
    assert tau["headline"]["rho"] == pytest.approx(tau["per_condition"]["A"]["rho"])


def test_centering_removes_condition_offsets() -> None:
    units, responses = make_tables(
        n_units=200,
        n_trials=20,
        conditions=("A", "B", "C"),
        reliability=0.8,
        condition_offsets={"A": 0.0, "B": 3.0, "C": 6.0},
        seed=3,
    )
    res = run(units, responses, ["tau"], post_stim_window_s=2.0, n_perm=50)
    tau = res["measures"]["tau"]
    assert tau["headline_kind"] == "pooled_centered"
    assert tau["pooled"]["uncentered"]["rho"] > 0.93
    assert abs(tau["pooled"]["centered"]["rho"] - 0.8) <= 0.05
    assert tau["headline"]["rho"] == pytest.approx(tau["pooled"]["centered"]["rho"])


def test_nonpositive_r_reports_zero() -> None:
    idx = pd.MultiIndex.from_arrays(
        [[f"u{i:02d}" for i in range(10)], ["A"] * 10],
        names=["unit_id", "condition"],
    )
    tau_a = np.arange(1.0, 11.0)
    halves = pd.DataFrame(
        {
            "tau_A": tau_a,
            "tau_B": -tau_a,
            "n_A": 5,
            "n_B": 5,
        },
        index=idx,
    )
    c = ceiling(halves, "tau", center=False)
    assert c["rho"] == 0.0
    assert c["r_nonpositive"] is True
    assert c["r_half"] == pytest.approx(-1.0)


def test_null_below_observed() -> None:
    units, responses = make_tables(n_units=40, n_trials=20, reliability=0.85, seed=4)
    res = run(units, responses, ["tau"], post_stim_window_s=2.0, n_perm=300)
    tau = res["measures"]["tau"]
    assert abs(tau["null"]["median_rho"]) <= 0.1
    assert tau["null"]["p95_rho"] < tau["headline"]["rho"]


def test_census_matches_validate() -> None:
    units, responses = make_tables(n_units=12, n_trials=14, conditions=("A", "B"))
    val = validate(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0)
    c = census(val)
    assert list(c.keys()) == [
        "preparations",
        "sessions",
        "recordings",
        "units",
        "units_active",
        "conditions",
        "evaluated_conditions",
        "trials",
        "trials_per_unit_condition",
    ]
    assert c["preparations"] == val["n_preparations"]
    assert c["sessions"] == val["n_sessions"]
    assert c["recordings"] == val["n_recordings"]
    assert c["units"] == val["n_units"]
    assert c["units_active"] == val["n_units_active"]
    assert c["conditions"] == val["n_conditions"]
    assert c["evaluated_conditions"] == val["evaluated_conditions"]
    assert c["trials"] == val["n_trials"]
    assert c["trials_per_unit_condition"] == val["trials_per_unit_condition"]


def test_run_positive_control_failure_path(monkeypatch: pytest.MonkeyPatch) -> None:
    def _failed_pc(*args: object, **kwargs: object) -> dict[str, object]:
        return {
            "injected": 0.85,
            "recovered": 0.10,
            "passed": False,
            "n_units": 1000,
            "n_trials": 20,
            "tolerance": 0.05,
        }

    monkeypatch.setattr(evaluate, "positive_control", _failed_pc)
    units, responses = make_tables(n_units=15, n_trials=20, reliability=0.8)
    res = run(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0)
    assert res["status"] == "positive_control_failed"
    assert "measures" not in res
    assert res["positive_control"]["passed"] is False


def test_cli_evaluate_json(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units, responses = make_tables(n_units=15, n_trials=20, reliability=0.8, seed=2)
    units_csv = tmp_path / "units.csv"
    responses_csv = tmp_path / "responses.csv"
    units.to_csv(units_csv, index=False)
    responses.to_csv(responses_csv, index=False)

    rc = main(
        [
            str(units_csv),
            str(responses_csv),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--n-perm",
            "50",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    doc = json.loads(captured.out)
    assert doc["status"] == "ok"
    assert abs(doc["result"]["measures"]["tau"]["headline"]["rho"] - 0.8) <= 0.15
    assert doc["inputs"]["units"]["sha256"] == hashlib.sha256(units_csv.read_bytes()).hexdigest()
    assert doc["inputs"]["responses"]["sha256"] == hashlib.sha256(responses_csv.read_bytes()).hexdigest()


def test_cli_evaluate_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units, responses = make_tables(n_trials=6)
    units_csv = tmp_path / "units.csv"
    responses_csv = tmp_path / "responses.csv"
    units.to_csv(units_csv, index=False)
    responses.to_csv(responses_csv, index=False)

    rc = main(
        [
            str(units_csv),
            str(responses_csv),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out.startswith("MD-2 failed.")


def test_ci_contains_truth_at_scale() -> None:
    # A single 95% interval misses 5% of the time, so containment is tested by
    # coverage over seeds (test_ci_coverage_small_n), not on one draw.
    _, responses = make_tables(n_units=2000, n_trials=20, reliability=0.8, seed=0)
    halves = split_halves(responses, ["tau"], ["A"])
    est = ceiling(halves, "tau", center=False)
    assert est["rho_ci_low"] is not None
    assert est["rho_ci_high"] is not None
    assert abs(est["rho"] - 0.8) < 0.03
    assert (est["rho_ci_high"] - est["rho_ci_low"]) < 0.05


def test_examples_headline() -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    units, responses = read_tables(examples_dir / "units.csv", examples_dir / "responses.csv")
    res = run(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0, n_perm=50)
    assert res["status"] == "ok"
    for measure in ("tau", "amplitude"):
        headline = res["measures"][measure]["headline"]
        assert abs(headline["rho"] - 0.8) <= 0.15
        assert headline["rho_ci_low"] > 0.5


def test_ci_coverage_small_n() -> None:
    covered = 0
    n_seeds = 200
    for seed in range(n_seeds):
        _, responses = make_tables(n_units=15, n_trials=20, reliability=0.8, seed=seed)
        halves = split_halves(responses, ["tau"], ["A"])
        est = ceiling(halves, "tau", center=False)
        if est["rho_ci_low"] <= 0.8 <= est["rho_ci_high"]:
            covered += 1
    coverage = covered / n_seeds
    assert 0.90 <= coverage <= 0.99


def test_single_trial_conversion() -> None:
    idx = pd.MultiIndex.from_arrays(
        [[f"u{i:02d}" for i in range(4)], ["A"] * 4],
        names=["unit_id", "condition"],
    )
    u = np.array([1.0, -1.0, 1.0, -1.0])
    v = np.array([1.0, 1.0, -1.0, -1.0])
    r_target = 0.8 / (2.0 - 0.8)
    halves = pd.DataFrame(
        {
            "tau_A": u,
            "tau_B": r_target * u + np.sqrt(1.0 - r_target**2) * v,
            "n_A": 10,
            "n_B": 10,
        },
        index=idx,
    )
    est = ceiling(halves, "tau", center=False)
    assert est["rho"] == pytest.approx(0.8)
    assert est["n_trials_group"] == pytest.approx(20.0)
    assert est["rho_single_trial"] == pytest.approx(0.8 / (20.0 - 19.0 * 0.8))
    assert est["rho_at_20"] == pytest.approx(0.8)

    halves_zero = halves.copy()
    halves_zero["tau_B"] = -u
    est_zero = ceiling(halves_zero, "tau", center=False)
    assert est_zero["rho"] == 0.0
    assert est_zero["rho_single_trial"] == 0.0
    assert est_zero["rho_at_20"] == 0.0

