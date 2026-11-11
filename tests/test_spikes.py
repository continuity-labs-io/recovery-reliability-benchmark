"""Tests for spike-train to split-half conversion, analysis sidecar loading, and min-dataset-7."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.checks_spikes import (
    check_pre_stimulus_window,
    check_scored_units,
)
from recovery_reliability_benchmark.contract import ContractViolation, Requirement
from recovery_reliability_benchmark.evaluate import split_halves
from recovery_reliability_benchmark.measures import (
    AnalysisParams,
    trial_latencies,
)
from recovery_reliability_benchmark.metadata import load_analysis, write_analysis
from recovery_reliability_benchmark.spikes import (
    halves_from_spikes,
    scored_units,
    spike_times_by_unit,
    split_trials,
    trial_table,
)
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
    make_tables,
)

ROOT = Path(__file__).resolve().parent.parent


def _build_five_unit_fixture(
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[np.ndarray], np.ndarray, AnalysisParams]:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [
        exponential_recovery(baseline_hz=5.0, peak_hz=15.0 + 5.0 * i, tau_s=0.15 + 0.03 * i) for i in range(5)
    ]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=10, params=params, isi_s=4.0, seed=seed)
    unit_ids = [f"u{i:02d}" for i in range(5)]
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
            "stim_time_ns": [int(round(t * 1e9)) for t in onsets_s],
            "condition": "baseline",
        }
    )
    spike_rows = [
        {"unit_id": uid, "spike_time_ns": int(round(float(t_s) * 1e9))}
        for uid, train in zip(unit_ids, trains, strict=False)
        for t_s in train
    ]
    spikes = pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"])
    return units, trials, spikes, trains, onsets_s, params


def test_split_trials_matches_split_halves() -> None:
    _units, responses = make_tables(n_units=3, n_trials=11, conditions=("A", "B"))
    responses["idx_measure"] = responses["trial_index"].astype(float)
    halves = split_halves(responses, ["idx_measure"], ["A", "B"])
    trials = trial_table(responses)

    for cond in ("A", "B"):
        odd_idx, even_idx = split_trials(trials, cond)
        expected_odd = float(np.mean(odd_idx))
        expected_even = float(np.mean(even_idx))
        cond_rows = halves.xs(cond, level="condition")
        assert len(cond_rows) == 3
        np.testing.assert_allclose(
            cond_rows["idx_measure_odd"].to_numpy(), expected_odd, rtol=0.0, atol=1e-12
        )
        np.testing.assert_allclose(
            cond_rows["idx_measure_even"].to_numpy(), expected_even, rtol=0.0, atol=1e-12
        )


def test_trial_table_rejects_inconsistent_trial() -> None:
    _units, responses = make_tables(n_units=3, n_trials=10)
    mask = (responses["unit_id"] == "u00") & (responses["trial_index"] == 4)
    responses.loc[mask, "stim_time_ns"] = responses.loc[mask, "stim_time_ns"] + 100
    with pytest.raises(ValueError, match="4"):
        trial_table(responses)


def test_halves_shape() -> None:
    units, trials, spikes, _trains, _onsets_s, params = _build_five_unit_fixture()
    halves, flags = halves_from_spikes(units, trials, spikes, params, ["t_return"])
    assert len(halves) == 5
    assert list(halves.columns) == ["t_return_odd", "t_return_even", "n_odd", "n_even"]
    assert (halves["n_odd"] == 5).all()
    assert (halves["n_even"] == 5).all()
    assert list(halves.index.names) == ["unit_id", "condition"]
    assert list(flags.index.names) == ["unit_id", "condition"]
    assert len(flags) == 5

    with pytest.raises(ValueError, match="Available measures"):
        halves_from_spikes(units, trials, spikes, params, ["not_a_measure"])


@pytest.mark.parametrize("seed", [0, 1, 2, None])
def test_spikes_per_trial_matches_tables_path(seed: int | None) -> None:
    units, trials, spikes, _trains, _onsets_s, params = _build_five_unit_fixture(
        seed=0 if seed is None else seed
    )
    if seed is None:
        spikes = pd.DataFrame(
            [
                {"unit_id": uid, "spike_time_ns": int(onset_ns) + 500_000 * (2 * idx + 1)}
                for idx, uid in enumerate(units["unit_id"])
                for onset_ns in trials["stim_time_ns"]
            ]
        )

    by_unit = spike_times_by_unit(spikes, units)
    onsets_from_trials = trials["stim_time_ns"].to_numpy(dtype=float) / 1e9

    rows = []
    for uid in units["unit_id"]:
        lats = trial_latencies(by_unit[str(uid)], onsets_from_trials, params)
        per_trial_counts = [len(lat) for lat in lats]
        for ti, onset_ns, cond, cnt in zip(
            trials["trial_index"],
            trials["stim_time_ns"],
            trials["condition"],
            per_trial_counts,
            strict=False,
        ):
            rows.append(
                {
                    "unit_id": str(uid),
                    "trial_index": int(ti),
                    "stim_time_ns": int(onset_ns),
                    "condition": str(cond),
                    "spikes_per_trial": float(cnt),
                }
            )
    responses = pd.DataFrame(rows)
    halves_tables = split_halves(responses, ["spikes_per_trial"], ["baseline"])
    halves_spikes, _flags = halves_from_spikes(units, trials, spikes, params, ["spikes_per_trial"])

    if seed is None:
        assert params.artifact_blank_s == 0.003
        for unit_id, expected in (("u00", 0.0), ("u02", 0.0), ("u03", 1.0), ("u04", 1.0)):
            assert float(halves_spikes.loc[(unit_id, "baseline"), "spikes_per_trial_odd"]) == expected
            assert float(halves_spikes.loc[(unit_id, "baseline"), "spikes_per_trial_even"]) == expected

    np.testing.assert_allclose(
        halves_spikes["spikes_per_trial_odd"].to_numpy(),
        halves_tables["spikes_per_trial_odd"].to_numpy(),
        rtol=0.0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        halves_spikes["spikes_per_trial_even"].to_numpy(),
        halves_tables["spikes_per_trial_even"].to_numpy(),
        rtol=0.0,
        atol=1e-12,
    )


def test_scored_units_excludes_silent_unit() -> None:
    units, trials, spikes, _trains, _onsets_s, params = _build_five_unit_fixture()
    silent_row = pd.DataFrame(
        {
            "unit_id": ["u_silent"],
            "recording_id": ["rec0"],
            "session_id": ["sess0"],
            "preparation_id": ["prep0"],
        }
    )
    units_with_silent = pd.concat([units, silent_row], ignore_index=True)
    measures = ["t_return", "peak_rate", "t_peak", "t_half_peak"]
    halves, _flags = halves_from_spikes(units_with_silent, trials, spikes, params, measures)

    scored = scored_units(halves, measures)
    assert "u_silent" not in scored["t_return"]["baseline"]
    assert len(scored["t_return"]["baseline"]) == 5

    assert "u_silent" in scored["peak_rate"]["baseline"]
    assert len(scored["peak_rate"]["baseline"]) == 6

    for measure in ("t_peak", "t_half_peak"):
        assert "u_silent" not in scored[measure]["baseline"]
        assert len(scored[measure]["baseline"]) == 5


def test_pre_window_violations() -> None:
    trials_ok = pd.DataFrame(
        {
            "trial_index": list(range(10)),
            "stim_time_ns": [int((k + 1) * 5 * 1e9) for k in range(10)],
            "condition": "baseline",
        }
    )

    params_short = AnalysisParams(post_stim_window_s=2.0, pre_stim_window_s=0.5)
    with pytest.raises(ContractViolation) as exc_info:
        check_pre_stimulus_window(trials_ok, params_short, load_duration_s=0.0)
    assert exc_info.value.requirement is Requirement.MD7
    assert exc_info.value.found == 0.5
    assert exc_info.value.required == 1.0
    assert exc_info.value.message == "Pre-stimulus window 0.5 s, requires 1.0 s."

    trials_early_first = trials_ok.copy()
    trials_early_first.loc[0, "stim_time_ns"] = int(0.5 * 1e9)
    params_1s = AnalysisParams(post_stim_window_s=2.0, pre_stim_window_s=1.0)
    with pytest.raises(ContractViolation) as exc_info:
        check_pre_stimulus_window(trials_early_first, params_1s, load_duration_s=0.0)
    assert exc_info.value.requirement is Requirement.MD7
    assert "trial 0" in exc_info.value.message
    assert (
        exc_info.value.message
        == "Pre-stimulus window 1.0 s does not fit before trial 0 at 0.500 s, requires onset >= 1.0 s."
    )

    trials_tight_gap = trials_ok.copy()
    prev_onset_s = trials_tight_gap.loc[6, "stim_time_ns"] / 1e9
    trials_tight_gap.loc[7, "stim_time_ns"] = int(round((prev_onset_s + 1.0 + 2.0 + 0.8) * 1e9))
    with pytest.raises(ContractViolation) as exc_info:
        check_pre_stimulus_window(trials_tight_gap, params_1s, load_duration_s=1.0)
    assert exc_info.value.requirement is Requirement.MD7
    assert "Trial 7" in exc_info.value.message
    assert exc_info.value.found == pytest.approx(0.8)
    assert exc_info.value.required == 1.0
    assert (
        exc_info.value.message
        == "Trial 7 has 0.800 s between the end of the previous post-stimulus window and its onset (gap 3.800 s minus load 1.000 s minus post-stimulus window 2.000 s), requires 1.0 s."
    )

    check_pre_stimulus_window(trials_ok, params_1s, load_duration_s=1.0)


@pytest.mark.parametrize(
    "first_onset_ns", [1_000_000_000, 1_100_000_000, 4_700_000_001, 1_762_800_000_123_456_789]
)
def test_pre_window_spacing_boundary(first_onset_ns: int) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)

    def trials_spaced(gap_ns: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "trial_index": list(range(10)),
                "stim_time_ns": [first_onset_ns + k * gap_ns for k in range(10)],
                "condition": "baseline",
            }
        )

    check_pre_stimulus_window(trials_spaced(3_000_000_000), params)
    with pytest.raises(ContractViolation) as exc_info:
        check_pre_stimulus_window(trials_spaced(2_999_999_999), params)
    assert exc_info.value.requirement is Requirement.MD7
    assert (
        "Trial 1 has 1.000 s between the end of the previous post-stimulus window" in exc_info.value.message
    )
    assert "(gap 3.000 s minus load 0.000 s minus post-stimulus window 2.000 s)" in exc_info.value.message

    params_loaded = AnalysisParams(post_stim_window_s=2.0, load_duration_s=0.3)
    check_pre_stimulus_window(trials_spaced(3_300_000_000), params_loaded)
    with pytest.raises(ContractViolation):
        check_pre_stimulus_window(trials_spaced(3_299_999_999), params_loaded)


def test_check_scored_units_md3() -> None:
    scored = {"t_return": {"A": {f"u{i:02d}" for i in range(6)}}}
    with pytest.raises(ContractViolation) as exc_info:
        check_scored_units(scored, "t_return", "A")
    assert exc_info.value.requirement is Requirement.MD3
    assert (
        exc_info.value.message
        == "6 units with t_return computed in both halves for condition 'A', requires 8."
    )
    assert exc_info.value.found == 6
    assert exc_info.value.required == 8


def test_load_analysis(tmp_path: Path) -> None:
    params = AnalysisParams(post_stim_window_s=2.5, pre_stim_window_s=1.2, load_duration_s=0.5)
    path = tmp_path / "analysis.json"
    write_analysis(params, path)
    loaded = load_analysis(path)
    assert loaded == params

    missing_path = tmp_path / "missing_analysis.json"
    with pytest.raises(ContractViolation) as exc_info:
        load_analysis(missing_path)
    assert exc_info.value.requirement is Requirement.SCHEMA

    bad_json_path = tmp_path / "bad_json.json"
    bad_json_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ContractViolation) as exc_info:
        load_analysis(bad_json_path)
    assert exc_info.value.requirement is Requirement.SCHEMA

    unknown_key_path = tmp_path / "unknown_key.json"
    unknown_key_path.write_text('{"post_stim_window_s": 2.0, "unknown_field": 123}', encoding="utf-8")
    with pytest.raises(ContractViolation) as exc_info:
        load_analysis(unknown_key_path)
    assert exc_info.value.requirement is Requirement.SCHEMA

    invalid_val_path = tmp_path / "invalid_val.json"
    invalid_val_path.write_text('{"post_stim_window_s": -1.0}', encoding="utf-8")
    with pytest.raises(ContractViolation) as exc_info:
        load_analysis(invalid_val_path)
    assert exc_info.value.requirement is Requirement.SCHEMA


def test_docs() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    glossary_text = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
    assert "min-dataset-7" in spec_text
    assert "Scored unit" in glossary_text
