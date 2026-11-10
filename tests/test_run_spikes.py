"""Tests for run.run on the spikes path and equivalence with the tables path."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.contract import ContractViolation, Requirement
from recovery_reliability_benchmark.measures import FLAG_KEYS, AnalysisParams
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.spikes import per_trial_counts_table
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
    make_tables,
)


def _build_spike_dataset(
    taus: Sequence[float],
    n_trials: int = 20,
    isi_s: float = 5.0,
    seed: int = 0,
    silent_units: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=float(tau)) for tau in taus]
    for _ in range(silent_units):
        rate_fns.append(exponential_recovery(baseline_hz=0.0, peak_hz=0.0, tau_s=0.2))

    n_units = len(rate_fns)
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=n_trials, params=params, isi_s=isi_s, seed=seed)
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
            "condition": "baseline",
        }
    )
    spike_rows = [
        {"unit_id": uid, "spike_time_ns": int(round(float(t_s) * 1e9))}
        for uid, train in zip(unit_ids, trains, strict=True)
        for t_s in train
    ]
    spikes = pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"])
    return units, trials, spikes, params


def test_spikes_path_matches_tables_for_counts() -> None:
    taus = np.geomspace(0.05, 0.5, 30)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=20, isi_s=5.0, seed=0)

    res_spikes = run(
        units,
        trials,
        measures=["spikes_per_trial"],
        spikes=spikes,
        analysis=params,
        n_perm=100,
    )

    counts_df = per_trial_counts_table(units, trials, spikes, params).rename(
        columns={"spike_count": "spikes_per_trial"}
    )
    res_tables = run(
        units,
        counts_df,
        measures=["spikes_per_trial"],
        post_stim_window_s=params.post_stim_window_s,
        load_duration_s=params.load_duration_s,
        n_perm=100,
    )

    h_spikes = res_spikes["measures"]["spikes_per_trial"]["headline"]
    h_tables = res_tables["measures"]["spikes_per_trial"]["headline"]
    assert h_spikes["rho"] == pytest.approx(h_tables["rho"], rel=0.0, abs=1e-9)
    assert h_spikes["n_units"] == h_tables["n_units"] == 30


def test_spikes_path_reports() -> None:
    taus = np.geomspace(0.05, 0.5, 30)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=20, isi_s=5.0, seed=0)

    res = run(
        units,
        trials,
        measures=["t_return", "peak_rate"],
        spikes=spikes,
        analysis=params,
        n_perm=50,
    )
    assert res["status"] == "ok"
    assert res["parameters"]["path"] == "spikes"
    assert res["parameters"]["analysis"] == params.to_dict()
    assert res["parameters"]["analysis_fingerprint"] == params.fingerprint()

    sp_inc = res["inclusion"]["spikes_path"]
    assert (
        sp_inc["rule"]
        == "A unit is scored in a condition when every requested measure is computed in both halves."
    )
    assert "baseline" in sp_inc["per_condition"]
    assert sp_inc["per_condition"]["baseline"] == {
        "n_units_in_tables": 30,
        "n_units_scored": 30,
        "n_units_excluded_by_rule": 0,
    }

    for m in ("t_return", "peak_rate"):
        m_res = res["measures"][m]
        assert m_res["headline"]["variance"] is None
        assert m_res["per_condition"]["baseline"]["variance"] is None
        assert "flags" in m_res
        assert "baseline" in m_res["flags"]
        assert set(m_res["flags"]["baseline"].keys()) == set(FLAG_KEYS)

    with pytest.raises(ValueError, match="analysis requires spikes"):
        run(units, trials, measures=["t_return"], analysis=params)

    with pytest.raises(ValueError, match=r"3\.0.*2\.0|2\.0.*3\.0"):
        run(
            units,
            trials,
            measures=["t_return"],
            post_stim_window_s=3.0,
            spikes=spikes,
            analysis=params,
        )

    with pytest.raises(ValueError, match=r"0\.5.*0\.0|0\.0.*0\.5"):
        run(
            units,
            trials,
            measures=["t_return"],
            load_duration_s=0.5,
            spikes=spikes,
            analysis=params,
        )


def test_t_return_reliability_bounds() -> None:
    taus_spread = np.geomspace(0.05, 0.5, 30)
    units_s, trials_s, spikes_s, params_s = _build_spike_dataset(taus_spread, n_trials=100, isi_s=5.0, seed=0)
    res_spread = run(
        units_s,
        trials_s,
        measures=["t_return"],
        spikes=spikes_s,
        analysis=params_s,
        n_perm=50,
    )
    rho_spread = res_spread["measures"]["t_return"]["headline"]["rho"]
    assert rho_spread > 0.9

    taus_identical = [0.2] * 30
    units_i, trials_i, spikes_i, params_i = _build_spike_dataset(
        taus_identical, n_trials=100, isi_s=5.0, seed=0
    )
    res_identical = run(
        units_i,
        trials_i,
        measures=["t_return"],
        spikes=spikes_i,
        analysis=params_i,
        n_perm=50,
    )
    rho_identical = res_identical["measures"]["t_return"]["headline"]["rho"]
    assert rho_identical < 0.3


def test_md7_from_run() -> None:
    taus = np.geomspace(0.05, 0.5, 10)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=10, isi_s=5.0, seed=0)
    trials_early = trials.copy()
    trials_early.loc[0, "stim_time_ns"] = int(0.5 * 1e9)

    with pytest.raises(ContractViolation) as exc_info:
        run(
            units,
            trials_early,
            measures=["t_return"],
            spikes=spikes,
            analysis=params,
            n_perm=20,
        )
    assert exc_info.value.requirement is Requirement.MD7


def test_md3_scored_from_run() -> None:
    taus = np.geomspace(0.05, 0.5, 6)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=10, isi_s=5.0, seed=0, silent_units=4)
    assert len(units) == 10

    with pytest.raises(ContractViolation) as exc_info:
        run(
            units,
            trials,
            measures=["t_return"],
            spikes=spikes,
            analysis=params,
            n_perm=20,
        )
    assert exc_info.value.requirement is Requirement.MD3
    assert "computed in both halves" in exc_info.value.message


def test_tables_path_unchanged() -> None:
    units, responses = make_tables(n_units=30, n_trials=20, reliability=0.8)
    res = run(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0)
    assert res["parameters"]["path"] == "responses"
    assert res["measures"]["tau"]["headline"]["rho"] == pytest.approx(0.8256281560268863, rel=0.0, abs=1e-15)
    assert res["measures"]["amplitude"]["headline"]["rho"] == pytest.approx(
        0.9044625066512956, rel=0.0, abs=1e-15
    )
