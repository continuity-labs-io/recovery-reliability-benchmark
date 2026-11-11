"""Tests for the between-condition sensitivity axis and its shuffled null."""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd

from recovery_reliability_benchmark.evaluate import split_halves
from recovery_reliability_benchmark.measures import AnalysisParams
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.sensitivity import condition_sensitivity, measure_sensitivity
from recovery_reliability_benchmark.spikes import halves_from_spikes
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_tables,
    make_two_condition_spike_trains,
)
from recovery_reliability_benchmark.text_report import print_evaluate_human


def _make_dataset(
    k: float,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    n_units = 30
    taus = np.geomspace(0.05, 0.5, n_units)
    baselines = np.geomspace(1.0, 20.0, n_units)
    params = AnalysisParams(post_stim_window_s=2.0)

    rate_fns_first = [
        exponential_recovery(float(baselines[(7 * i) % n_units]), 100.0, float(taus[i]))
        for i in range(n_units)
    ]
    rate_fns_second = [
        exponential_recovery(float(baselines[(7 * i) % n_units]), 100.0, float(taus[i] * k))
        for i in range(n_units)
    ]

    trains, onsets_s, n_first = make_two_condition_spike_trains(
        rate_fns_first,
        rate_fns_second,
        n_trials=20,
        params=params,
        isi_s=5.0,
        seed=seed,
    )
    unit_ids = [f"u{i:02d}" for i in range(n_units)]
    units = pd.DataFrame(
        {
            "unit_id": unit_ids,
            "recording_id": "rec0",
            "session_id": "sess0",
            "preparation_id": "prep0",
        }
    )
    trials = pd.DataFrame(
        {
            "trial_index": list(range(len(onsets_s))),
            "stim_time_ns": [int(round(float(t) * 1e9)) for t in onsets_s],
            "condition": ["control"] * n_first + ["slowed"] * (len(onsets_s) - n_first),
        }
    )
    spike_rows = [
        {"unit_id": uid, "spike_time_ns": int(round(float(t_s) * 1e9))}
        for uid, train in zip(unit_ids, trains, strict=True)
        for t_s in train
    ]
    spikes = pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"])
    return units, trials, spikes, params


def _assert_finite_numbers(obj: Any) -> None:
    if isinstance(obj, float):
        assert math.isfinite(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _assert_finite_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            _assert_finite_numbers(item)


def test_detects_slowing() -> None:
    for seed in (0, 1):
        units, trials, spikes, params = _make_dataset(1.5, seed)
        halves, _ = halves_from_spikes(units, trials, spikes, params, ["t_half_excess", "baseline_hz"])

        sens_the = measure_sensitivity(halves, "t_half_excess", ["control", "slowed"], n_perm=200, seed=seed)
        assert sens_the is not None
        pair_the = sens_the["control|slowed"]
        assert pair_the["median_abs_z"] > 2.5
        assert pair_the["frac_beyond_2"] > 0.6
        assert pair_the["median_shift"] > 0.04
        assert pair_the["above_null"] is True

        sens_base = measure_sensitivity(halves, "baseline_hz", ["control", "slowed"], n_perm=200, seed=seed)
        assert sens_base is not None
        pair_base = sens_base["control|slowed"]
        assert pair_base["median_abs_z"] < 1.0
        assert pair_base["frac_beyond_2"] < 0.25


def test_chance_without_effect() -> None:
    for seed in (0, 1):
        units, trials, spikes, params = _make_dataset(1.0, seed)
        halves, _ = halves_from_spikes(units, trials, spikes, params, ["t_half_excess"])

        sens = measure_sensitivity(halves, "t_half_excess", ["control", "slowed"], n_perm=200, seed=seed)
        assert sens is not None
        pair = sens["control|slowed"]
        assert pair["median_abs_z"] < 1.0
        assert pair["frac_beyond_2"] < 0.2


def test_tables_path() -> None:
    for seed in (0, 1):
        units, responses = make_tables(
            n_units=30,
            n_trials=20,
            conditions=("A", "B"),
            reliability=0.8,
            condition_offsets={"B": 3.0},
            seed=seed,
        )
        halves = split_halves(responses, ["tau"], ["A", "B"])
        sens = measure_sensitivity(halves, "tau", ["A", "B"], n_perm=200, seed=seed)
        assert sens is not None
        pair = sens["A|B"]
        assert pair["median_abs_z"] > 4.0
        assert pair["frac_beyond_2"] > 0.9
        assert 2.5 < pair["median_shift"] < 3.5

        _, responses_zero = make_tables(
            n_units=30,
            n_trials=20,
            conditions=("A", "B"),
            reliability=0.8,
            condition_offsets={"B": 0.0},
            seed=seed,
        )
        halves_zero = split_halves(responses_zero, ["tau"], ["A", "B"])
        sens_zero = measure_sensitivity(halves_zero, "tau", ["A", "B"], n_perm=200, seed=seed)
        assert sens_zero is not None
        assert sens_zero["A|B"]["median_abs_z"] < 1.0

    units_run, resp_run = make_tables(
        n_units=30,
        n_trials=20,
        conditions=("A", "B"),
        reliability=0.8,
        condition_offsets={"B": 3.0},
        seed=0,
    )
    res_run = run(units_run, resp_run, ["tau"], post_stim_window_s=2.0, n_perm=50, seed=0)
    assert res_run["measures"]["tau"]["sensitivity"]["A|B"]["beats_reference"] is None


def test_null_near_chance() -> None:
    units, trials, spikes, params = _make_dataset(1.0, 0)
    halves, _ = halves_from_spikes(units, trials, spikes, params, ["t_half_excess"])
    sens = measure_sensitivity(halves, "t_half_excess", ["control", "slowed"], n_perm=300, seed=0)
    assert sens is not None
    p95 = sens["control|slowed"]["null"]["median_abs_z_p95"]
    assert 0.6 <= p95 <= 1.6


def test_one_condition_is_none() -> None:
    units, responses = make_tables(n_units=15, n_trials=20, conditions=("A",), reliability=0.8, seed=0)
    halves = split_halves(responses, ["tau"], ["A"])
    assert measure_sensitivity(halves, "tau", ["A"], n_perm=100, seed=0) is None
    assert measure_sensitivity(halves, "tau", [], n_perm=100, seed=0) is None

    res = run(units, responses, ["tau"], post_stim_window_s=2.0, n_perm=20, seed=0)
    assert res["measures"]["tau"]["sensitivity"] is None

    empty_sens = condition_sensitivity(halves, "tau", "A", "B", n_perm=50, rng=np.random.default_rng(0))
    assert empty_sens == {
        "n_units": 0,
        "median_shift": None,
        "median_abs_z": None,
        "frac_beyond_2": None,
        "null": None,
        "above_null": None,
    }


def test_zero_noise() -> None:
    unit_ids = [f"u{i:02d}" for i in range(6)]
    idx = pd.MultiIndex.from_tuples(
        [(u, c) for u in unit_ids for c in ("control", "slowed")],
        names=["unit_id", "condition"],
    )

    shifted_rows = []
    zero_rows = []
    for i, _ in enumerate(unit_ids):
        base = float(i + 1)
        shifted_rows.append({"tau_odd": base, "tau_even": base})
        shifted_rows.append({"tau_odd": base + 0.5, "tau_even": base + 0.5})
        zero_rows.append({"tau_odd": base, "tau_even": base})
        zero_rows.append({"tau_odd": base, "tau_even": base})

    halves_shifted = pd.DataFrame(shifted_rows, index=idx)
    out_shifted = condition_sensitivity(
        halves_shifted, "tau", "control", "slowed", n_perm=200, rng=np.random.default_rng(0)
    )
    assert out_shifted["n_units"] == 6
    assert out_shifted["frac_beyond_2"] == 1.0
    assert out_shifted["median_abs_z"] > 2.0
    _assert_finite_numbers(out_shifted)
    assert json.loads(json.dumps(out_shifted, allow_nan=False))["n_units"] == 6

    halves_zero = pd.DataFrame(zero_rows, index=idx)
    out_zero = condition_sensitivity(
        halves_zero, "tau", "control", "slowed", n_perm=200, rng=np.random.default_rng(0)
    )
    assert out_zero["n_units"] == 6
    assert out_zero["median_abs_z"] == 0.0
    assert out_zero["frac_beyond_2"] == 0.0
    assert out_zero["median_shift"] == 0.0
    _assert_finite_numbers(out_zero)
    assert json.loads(json.dumps(out_zero, allow_nan=False))["median_abs_z"] == 0.0


def test_run_reports_sensitivity() -> None:
    units, trials, spikes, params = _make_dataset(1.5, 0)
    res_both = run(
        units,
        trials,
        measures=["t_half_excess", "baseline_hz"],
        spikes=spikes,
        analysis=params,
        n_perm=50,
        seed=0,
    )
    m_sens = res_both["measures"]["t_half_excess"]["sensitivity"]["control|slowed"]
    assert m_sens["median_abs_z"] > 2.5
    assert m_sens["beats_reference"] is True

    ref_sens = res_both["reference"]["sensitivity"]["control|slowed"]
    assert ref_sens["median_abs_z"] < 1.0
    assert "beats_reference" not in ref_sens
    assert res_both["measures"]["baseline_hz"]["sensitivity"]["control|slowed"]["beats_reference"] is None

    import io
    from contextlib import redirect_stdout

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluate_human(res_both)
    human_text = buf.getvalue()
    assert "  sensitivity control|slowed: median|z|=3.27" in human_text
    assert "[does not beat reference]" not in human_text
    assert human_text.strip().splitlines()[-1].endswith("[sensitivity at chance]")
