"""Tests for bin-free excess-spike recovery measures."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.evaluate import reliability_ceiling
from recovery_reliability_benchmark.excess import excess_measures
from recovery_reliability_benchmark.measures import unit_measures
from recovery_reliability_benchmark.spikes import halves_from_spikes
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
)


def _build_spike_dataset(
    taus: Sequence[float],
    n_trials: int = 20,
    isi_s: float = 5.0,
    seed: int = 0,
    baseline_hz: float = 5.0,
    peak_hz: float = 100.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [
        exponential_recovery(baseline_hz=baseline_hz, peak_hz=peak_hz, tau_s=float(tau)) for tau in taus
    ]
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


def test_half_excess_matches_theory() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    taus = [0.05, 0.1, 0.2]
    rate_fns = [exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=tau) for tau in taus]
    trains, onsets = make_spike_trains(rate_fns, n_trials=400, params=params, isi_s=5.0, seed=5)
    for tau, train in zip(taus, trains, strict=True):
        values, flags = unit_measures(train, onsets, params)
        assert flags["no_excess"] is False
        assert values["t_half_excess"] == pytest.approx(
            params.artifact_blank_s + tau * math.log(2.0), rel=0.20
        )


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_half_excess_reliable_at_twenty_trials(seed: int) -> None:
    taus = np.geomspace(0.05, 0.5, 30)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=20, isi_s=5.0, seed=seed)
    halves, _flags = halves_from_spikes(units, trials, spikes, params, ["t_half_excess"])
    res = reliability_ceiling(halves, "t_half_excess")
    assert res["rho"] > 0.9


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_half_excess_blind_to_amplitude(seed: int) -> None:
    taus = [0.2] * 30
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=20, isi_s=5.0, seed=seed)
    halves, _flags = halves_from_spikes(units, trials, spikes, params, ["t_half_excess"])
    res = reliability_ceiling(halves, "t_half_excess")
    assert res["rho"] < 0.3


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_excess_per_trial_reliable(seed: int) -> None:
    taus = np.geomspace(0.05, 0.5, 30)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=20, isi_s=5.0, seed=seed)
    halves, _flags = halves_from_spikes(units, trials, spikes, params, ["excess_per_trial"])
    res = reliability_ceiling(halves, "excess_per_trial")
    assert res["rho"] > 0.95


def test_no_excess_flag() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=0.0, tau_s=0.1)
    trains, onsets = make_spike_trains([rate_fn], n_trials=20, params=params, isi_s=5.0, seed=0)
    values, flags = unit_measures(trains[0], onsets, params)
    assert math.isnan(values["t_half_excess"])
    assert flags["no_excess"] is True
    assert math.isfinite(values["excess_per_trial"])


def test_zero_baseline_ok() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=0.0, peak_hz=50.0, tau_s=0.1)
    trains, onsets = make_spike_trains([rate_fn], n_trials=20, params=params, isi_s=5.0, seed=0)
    values, flags = unit_measures(trains[0], onsets, params)
    assert math.isfinite(values["t_half_excess"])
    assert flags["no_excess"] is False


def test_bin_edges_do_not_matter() -> None:
    params_default = AnalysisParams(post_stim_window_s=2.0)
    linear_edges = tuple(float(x) for x in np.round(np.arange(0.1, 2.01, 0.1), 6))
    params_linear = AnalysisParams(post_stim_window_s=2.0, bin_edges_s=linear_edges)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=0.15)
    trains, onsets = make_spike_trains([rate_fn], n_trials=20, params=params_default, isi_s=5.0, seed=0)
    vals_default, _ = unit_measures(trains[0], onsets, params_default)
    vals_linear, _ = unit_measures(trains[0], onsets, params_linear)
    assert vals_default["t_half_excess"] == vals_linear["t_half_excess"]
    assert vals_default["excess_per_trial"] == vals_linear["excess_per_trial"]


def _latencies_with_counts(counts: Sequence[int]) -> list[np.ndarray]:
    return [np.linspace(0.1, 0.5, int(c)) for c in counts]


def test_gate_uses_trial_to_trial_spread() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)

    _values, flags = excess_measures(_latencies_with_counts([3, 3, 3, 3]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is False

    values, flags = excess_measures(_latencies_with_counts([4, 0, 4, 0]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is True
    assert math.isnan(values["t_half_excess"])
    assert values["excess_per_trial"] == 2.0

    values, flags = excess_measures(_latencies_with_counts([5, 4, 5, 4]), [1, 1, 1, 1], params)
    assert flags["no_excess"] is False
    assert values["excess_per_trial"] == pytest.approx(4.5 - 1.997)

    _values, flags = excess_measures(_latencies_with_counts([0, 0, 0, 0]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is True

    with pytest.raises(ValueError, match="pre_counts has 3 trials, latencies has 4"):
        excess_measures(_latencies_with_counts([1, 1, 1, 1]), [0, 0, 0], params)


@pytest.mark.parametrize("burst_max", [1, 5])
def test_gate_pass_rate_without_response(burst_max: int) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    onsets = 5.0 * (np.arange(10) + 1)
    rng = np.random.default_rng(7)
    n_units, n_pass = 1000, 0
    for _ in range(n_units):
        n_events = int(rng.poisson(5.0 * 56.0 * 2.0 / (1 + burst_max)))
        events = rng.uniform(0.0, 56.0, n_events)
        sizes = rng.integers(1, burst_max + 1, n_events)
        spikes = np.sort(np.repeat(events, sizes) + rng.uniform(0.0, 0.02, int(sizes.sum())))
        _values, flags = unit_measures(spikes, onsets, params)
        n_pass += not flags["no_excess"]
    assert n_pass / n_units < 0.08


def test_artifact_blank_drops_early_spikes() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=0.15)
    trains, onsets = make_spike_trains([rate_fn], n_trials=20, params=params, isi_s=5.0, seed=0)
    with_artifact = np.sort(np.concatenate([trains[0], onsets + 0.001]))

    clean, _ = unit_measures(trains[0], onsets, params)
    dirty, _ = unit_measures(with_artifact, onsets, params)
    for key in ("t_half_excess", "excess_per_trial", "spikes_per_trial", "peak_rate", "t_return"):
        assert dirty[key] == clean[key]

    no_blank = AnalysisParams(post_stim_window_s=2.0, artifact_blank_s=0.0)
    clean_no_blank, _ = unit_measures(trains[0], onsets, no_blank)
    dirty_no_blank, _ = unit_measures(with_artifact, onsets, no_blank)
    assert dirty_no_blank["spikes_per_trial"] == clean_no_blank["spikes_per_trial"] + 1.0
    assert dirty_no_blank["excess_per_trial"] == pytest.approx(clean_no_blank["excess_per_trial"] + 1.0)
    assert dirty_no_blank["t_half_excess"] < clean_no_blank["t_half_excess"]
