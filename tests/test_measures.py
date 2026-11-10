"""Unit and ordering tests for PSTH recovery measures and synthetic spike trains."""

from __future__ import annotations

import math

import numpy as np
import pytest

from recovery_reliability_benchmark.analysis import DEFAULT_ANALYSIS_FINGERPRINT_2S
from recovery_reliability_benchmark.excess import excess_measures
from recovery_reliability_benchmark.measures import (
    AnalysisParams,
    baseline_hz,
    baseline_variance_hz2,
    bin_counts,
    pre_counts,
    psth_rate,
    recovery_measures,
    trial_latencies,
    unit_measures,
)
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
)

PINNED_DEFAULT_FINGERPRINT_2S = "2fe0111e220a4963da320333b9d23b2addb5a716d070c8b6395066e0f5b1c02a"


def test_effective_edges_end_at_window() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    edges = params.effective_edges()
    assert edges[0] == 0.003
    assert edges[-1] == 2.0
    assert np.all(np.diff(edges) > 0.0)


def test_effective_edges_no_sliver() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    edges = params.effective_edges()
    assert round(float(edges[-2]), 3) == 1.612
    assert float(edges[-1]) == 2.0
    widths = np.diff(edges)
    assert float(widths[-1]) >= 0.5 * float(widths[-2])


def test_params_roundtrip_and_fingerprint() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    assert AnalysisParams.from_dict(params.to_dict()) == params
    assert params.fingerprint() == PINNED_DEFAULT_FINGERPRINT_2S == DEFAULT_ANALYSIS_FINGERPRINT_2S


def test_params_validation() -> None:
    with pytest.raises(ValueError, match="post_stim_window_s"):
        AnalysisParams(post_stim_window_s=0.0)
    with pytest.raises(ValueError, match="pre_stim_window_s"):
        AnalysisParams(post_stim_window_s=2.0, pre_stim_window_s=-1.0)
    with pytest.raises(ValueError, match="load_duration_s"):
        AnalysisParams(post_stim_window_s=2.0, load_duration_s=-0.5)
    with pytest.raises(ValueError, match="bin_edges_s"):
        AnalysisParams(post_stim_window_s=2.0, bin_edges_s=(0.01, 0.005, 1.0))
    with pytest.raises(ValueError, match="half_peak_frac"):
        AnalysisParams(post_stim_window_s=2.0, half_peak_frac=1.0)
    with pytest.raises(ValueError, match="return_x_baseline"):
        AnalysisParams(post_stim_window_s=2.0, return_x_baseline=1.0)
    with pytest.raises(ValueError, match="residual_s"):
        AnalysisParams(post_stim_window_s=2.0, residual_s=2.5)
    with pytest.raises(ValueError, match="min_excess_z"):
        AnalysisParams(post_stim_window_s=2.0, min_excess_z=0.0)


def test_psth_constant_rate() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=10.0, peak_hz=0.0, tau_s=0.1)
    trains, onsets = make_spike_trains([rate_fn], n_trials=300, params=params, isi_s=4.0, seed=10)
    edges = params.effective_edges()
    counts = bin_counts(trial_latencies(trains[0], onsets, params), edges)
    rate = psth_rate(counts, edges)
    assert float(np.mean(rate)) == pytest.approx(10.0, rel=0.05)


def test_baseline_matches_generator() -> None:
    params = AnalysisParams(post_stim_window_s=2.0, pre_stim_window_s=1.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=20.0, tau_s=0.1)
    trains, onsets = make_spike_trains([rate_fn], n_trials=200, params=params, isi_s=4.0, seed=20)
    pre = pre_counts(trains[0], onsets, params)
    base = baseline_hz(pre, params)
    base_var = baseline_variance_hz2(pre, params)
    assert base == pytest.approx(5.0, rel=0.10)
    assert base_var == pytest.approx(5.0 / params.pre_stim_window_s, rel=0.30)


def test_t_return_orders_with_tau() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    taus = [0.05, 0.1, 0.2, 0.4]
    rate_fns = [exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=tau) for tau in taus]
    trains, onsets = make_spike_trains(rate_fns, n_trials=200, params=params, isi_s=4.0, seed=30)

    t_returns: list[float] = []
    t_half_peaks: list[float] = []
    for train in trains:
        values, flags = unit_measures(train, onsets, params)
        t_returns.append(values["t_return"])
        t_half_peaks.append(values["t_half_peak"])
        assert not any(flags.values()), f"Expected no flags set, got {flags}"

    assert all(a < b for a, b in zip(t_returns, t_returns[1:], strict=False))
    assert all(a < b for a, b in zip(t_half_peaks, t_half_peaks[1:], strict=False))


def test_peak_rate_orders_with_amplitude() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    peaks = [20.0, 50.0, 100.0]
    rate_fns = [exponential_recovery(baseline_hz=5.0, peak_hz=p, tau_s=0.1) for p in peaks]
    trains, onsets = make_spike_trains(rate_fns, n_trials=200, params=params, isi_s=4.0, seed=40)

    peak_rates = [unit_measures(train, onsets, params)[0]["peak_rate"] for train in trains]
    assert all(a < b for a, b in zip(peak_rates, peak_rates[1:], strict=False))


def test_censoring_is_not_null() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=5.0)
    trains, onsets = make_spike_trains([rate_fn], n_trials=200, params=params, isi_s=4.0, seed=50)
    values, flags = unit_measures(trains[0], onsets, params)
    assert values["t_return"] == 2.0
    assert flags["t_return_censored"] is True
    assert not math.isnan(values["t_return"])
    assert not math.isnan(values["t_peak"])
    assert not math.isnan(values["peak_rate"])


def test_no_response() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    edges = params.effective_edges()
    centers = 0.5 * (edges[:-1] + edges[1:])
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=0.0, tau_s=0.1)
    values, flags = recovery_measures(rate_fn(centers), edges, baseline=5.0, params=params)
    assert values["t_return"] == 0.0
    assert flags["no_response"] is True


def test_zero_baseline_gives_null() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=0.0, peak_hz=50.0, tau_s=0.1)
    trains, onsets = make_spike_trains([rate_fn], n_trials=100, params=params, isi_s=4.0, seed=60)
    values, flags = unit_measures(trains[0], onsets, params)
    assert values["baseline_hz"] == 0.0
    assert math.isnan(values["t_return"])
    assert math.isnan(values["residual"])
    assert math.isnan(values["overshoot"])
    assert flags["baseline_zero"] is True
    assert values["peak_rate"] > 0.0


@pytest.mark.parametrize("seed", [70, 0])
def test_overshoot_detected(seed: int) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    fn_dip = exponential_recovery(baseline_hz=5.0, peak_hz=50.0, tau_s=0.1, dip_hz=5.0, dip_s=1.0)
    fn_no_dip = exponential_recovery(baseline_hz=5.0, peak_hz=50.0, tau_s=0.1, dip_hz=0.0, dip_s=0.0)
    trains, onsets = make_spike_trains([fn_dip, fn_no_dip], n_trials=300, params=params, isi_s=4.0, seed=seed)
    vals_dip, _ = unit_measures(trains[0], onsets, params)
    vals_no_dip, _ = unit_measures(trains[1], onsets, params)
    assert vals_dip["overshoot"] > 0.35
    assert vals_no_dip["overshoot"] < 0.1


def test_unit_measures_matches_pieces() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=80.0, tau_s=0.15)
    trains, onsets = make_spike_trains([rate_fn], n_trials=100, params=params, isi_s=4.0, seed=80)
    spikes = trains[0]

    edges = params.effective_edges()
    pre = pre_counts(spikes, onsets, params)
    base = baseline_hz(pre, params)
    base_var = baseline_variance_hz2(pre, params)
    lats = trial_latencies(spikes, onsets, params)
    counts = bin_counts(lats, edges)
    rate = psth_rate(counts, edges)
    expected_values, expected_flags = recovery_measures(rate, edges, base, params)
    ex_values, ex_flags = excess_measures(lats, base, params)
    expected_values.update(ex_values)
    expected_flags.update(ex_flags)
    expected_values["baseline_hz"] = base
    expected_values["baseline_variance_hz2"] = base_var
    expected_values["spikes_per_trial"] = float(np.mean([len(lat) for lat in lats]))

    actual_values, actual_flags = unit_measures(spikes, onsets, params)
    assert actual_flags == expected_flags
    assert actual_values == expected_values
