"""PSTH-based neural recovery measures computed from spike times.

Pure functions on NumPy arrays in seconds. Conventions: bin time is the bin center for
t_peak, t_half_peak and the residual window; t_return is the right edge of the last bin
above return_x_baseline * baseline; residual is the pooled trailing rate divided by
baseline; baseline is pooled pre-stimulus counts over the trial set.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from .analysis import DEFAULT_BIN_EDGES_S, FLAG_KEYS, AnalysisParams
from .excess import excess_measures

__all__ = [
    "DEFAULT_BIN_EDGES_S",
    "FLAG_KEYS",
    "AnalysisParams",
    "FloatArray",
    "IntArray",
    "baseline_hz",
    "baseline_variance_hz2",
    "bin_counts",
    "pre_counts",
    "psth_rate",
    "recovery_measures",
    "trial_latencies",
    "unit_measures",
]

FloatArray = Sequence[float] | np.ndarray
IntArray = Sequence[int] | np.ndarray


def trial_latencies(
    spike_times_s: FloatArray, onsets_s: FloatArray, params: AnalysisParams
) -> list[np.ndarray]:
    """Extract post-load spike latencies per trial in ``[0, post_stim_window_s)`` (t0 = onset + load_duration_s).

    Args:
        spike_times_s: 1D array-like of spike timestamps in seconds.
        onsets_s: 1D array-like of stimulus onset timestamps in seconds.
        params: Analysis parameters defining load duration and post-stimulus window.

    Returns:
        List of 1D float64 arrays of latencies in ``[0, post_stim_window_s)``, one per onset.
    """
    spikes, win = np.sort(np.asarray(spike_times_s, dtype=float)), params.post_stim_window_s
    out: list[np.ndarray] = []
    for onset in np.asarray(onsets_s, dtype=float):
        t0 = float(onset) + params.load_duration_s
        i0, i1 = np.searchsorted(spikes, [t0, t0 + win], side="left")
        out.append(spikes[int(i0) : int(i1)] - t0)
    return out


def pre_counts(spike_times_s: FloatArray, onsets_s: FloatArray, params: AnalysisParams) -> np.ndarray:
    """Count spikes per trial in ``[onset - pre_stim_window_s, onset)``.

    Args:
        spike_times_s: 1D array-like of spike timestamps in seconds.
        onsets_s: 1D array-like of stimulus onset timestamps in seconds.
        params: Analysis parameters defining ``pre_stim_window_s``.

    Returns:
        1D integer array of pre-stimulus spike counts, one per onset.
    """
    spikes, onsets = np.sort(np.asarray(spike_times_s, dtype=float)), np.asarray(onsets_s, dtype=float)
    i0 = np.searchsorted(spikes, onsets - params.pre_stim_window_s, side="left")
    i1 = np.searchsorted(spikes, onsets, side="left")
    return np.asarray(i1 - i0, dtype=int)


def baseline_hz(pre_counts: IntArray, params: AnalysisParams) -> float:
    """Compute pooled pre-stimulus baseline firing rate in Hz.

    Args:
        pre_counts: Per-trial spike counts in the pre-stimulus window.
        params: Analysis parameters defining ``pre_stim_window_s``.

    Returns:
        Pooled baseline firing rate ``sum(pre_counts) / (n_trials * pre_stim_window_s)`` in Hz.
    """
    arr = np.asarray(pre_counts, dtype=float)
    return float("nan") if len(arr) == 0 else float(np.sum(arr) / (len(arr) * params.pre_stim_window_s))


def baseline_variance_hz2(pre_counts: IntArray, params: AnalysisParams) -> float:
    """Compute sample variance (``ddof=1``) across trials of pre-stimulus rate in Hz^2.

    Args:
        pre_counts: Per-trial spike counts in the pre-stimulus window.
        params: Analysis parameters defining ``pre_stim_window_s``.

    Returns:
        Sample variance of ``pre_counts / pre_stim_window_s`` across trials, or ``NaN`` if < 2 trials.
    """
    arr = np.asarray(pre_counts, dtype=float)
    return float("nan") if len(arr) < 2 else float(np.var(arr / params.pre_stim_window_s, ddof=1))


def bin_counts(latencies: Sequence[np.ndarray], edges_s: FloatArray) -> np.ndarray:
    """Histogram per-trial latencies into PSTH bins.

    Args:
        latencies: Sequence of per-trial 1D latency arrays in seconds.
        edges_s: Increasing 1D array of bin edges in seconds of length ``n_bins + 1``.

    Returns:
        Integer array of shape ``(n_trials, n_bins)`` with spike counts per trial and bin.
    """
    edges = np.asarray(edges_s, dtype=float)
    out = np.zeros((len(latencies), len(edges) - 1), dtype=int)
    for i, trial_lat in enumerate(latencies):
        out[i], _ = np.histogram(np.asarray(trial_lat, dtype=float), bins=edges)
    return out


def psth_rate(counts: np.ndarray, edges_s: FloatArray) -> np.ndarray:
    """Compute PSTH firing rate in Hz per bin (pooled counts divided by ``n_trials * width``).

    Args:
        counts: 2D array of shape ``(n_trials, n_bins)`` containing spike counts.
        edges_s: 1D array of bin edges in seconds of length ``n_bins + 1``.

    Returns:
        1D float64 array of firing rates in Hz of length ``n_bins``.
    """
    widths = np.diff(np.asarray(edges_s, dtype=float))
    return np.asarray(np.mean(np.asarray(counts, dtype=float), axis=0) / widths, dtype=float)


def recovery_measures(
    rate_hz: FloatArray, edges_s: FloatArray, baseline: float, params: AnalysisParams
) -> tuple[dict[str, float], dict[str, bool]]:
    """Compute PSTH recovery measures and censoring/status flags.

    Bin time is the bin center for ``t_peak``, ``t_half_peak``, and the ``residual`` window
    filter; ``t_return`` is the right edge of the last bin with
    ``rate > return_x_baseline * baseline``; ``residual`` is the mean rate over bins with
    ``center >= post_stim_window_s - residual_s`` divided by ``baseline``. ``overshoot`` uses
    the pooled rate ``sum(rate_i * width_i) / sum(width_i)`` over bins with
    ``center > t_return``: the minimum over bins is biased upward by whichever bin has the
    fewest spikes, so it grows with bin count and noise even when no dip exists; the pooled
    rate does not.

    Args:
        rate_hz: 1D array of PSTH firing rates in Hz per bin.
        edges_s: 1D array of bin edges in seconds of length ``len(rate_hz) + 1``.
        baseline: Pre-stimulus baseline firing rate in Hz.
        params: Analysis parameters.

    Returns:
        Tuple of ``(values, flags)`` dictionaries.
    """
    rate, edges = np.asarray(rate_hz, dtype=float), np.asarray(edges_s, dtype=float)
    centers, right_edges, win = 0.5 * (edges[:-1] + edges[1:]), edges[1:], float(params.post_stim_window_s)
    peak_idx = int(np.argmax(rate))
    t_peak, peak_rate, base = float(centers[peak_idx]), float(rate[peak_idx]), float(baseline)

    after_peak = np.flatnonzero(rate[peak_idx + 1 :] <= base + params.half_peak_frac * (peak_rate - base))
    t_half_peak_censored = len(after_peak) == 0
    t_half_peak = win if t_half_peak_censored else float(centers[peak_idx + 1 + int(after_peak[0])])

    nan = float("nan")
    if base == 0.0:
        t_return, residual, overshoot = nan, nan, nan
        t_return_censored, no_response, overshoot_undefined, baseline_zero = False, False, True, True
    else:
        baseline_zero = False
        exceed = np.flatnonzero(rate > params.return_x_baseline * base)
        no_response = len(exceed) == 0
        t_return_censored = not no_response and int(exceed[-1]) == len(rate) - 1
        t_return = 0.0 if no_response else (win if t_return_censored else float(right_edges[int(exceed[-1])]))
        res_mask = centers >= (win - params.residual_s)
        residual = float(np.mean(rate[res_mask]) / base) if np.any(res_mask) else nan
        after_mask = centers > t_return
        overshoot_undefined = t_return_censored or not bool(np.any(after_mask))
        if overshoot_undefined:
            overshoot = nan
        else:
            widths = np.diff(edges)[after_mask]
            r_after = float(np.sum(rate[after_mask] * widths) / np.sum(widths))
            overshoot = float(max(0.0, (base - r_after) / base))

    values = {
        "t_peak": t_peak,
        "peak_rate": peak_rate,
        "t_half_peak": t_half_peak,
        "t_return": t_return,
        "residual": residual,
        "overshoot": overshoot,
    }
    flags = {
        "t_half_peak_censored": t_half_peak_censored,
        "t_return_censored": t_return_censored,
        "no_response": no_response,
        "overshoot_undefined": overshoot_undefined,
        "baseline_zero": baseline_zero,
    }
    return values, flags


def unit_measures(
    spike_times_s: FloatArray, onsets_s: FloatArray, params: AnalysisParams
) -> tuple[dict[str, float], dict[str, bool]]:
    """Run the full PSTH and bin-free measure chain for one unit over one set of trials.

    ``spikes_per_trial`` is the mean over trials of ``len(latencies)`` from
    ``trial_latencies``, so every spike in ``[0, post_stim_window_s)`` counts, not
    only those inside the bin edges.

    Args:
        spike_times_s: 1D array-like of spike timestamps in seconds for one unit.
        onsets_s: 1D array-like of stimulus onset timestamps in seconds.
        params: Analysis parameters.

    Returns:
        Tuple of ``(values, flags)`` dictionaries for the unit, including ``t_half_excess``,
        ``excess_per_trial``, ``baseline_hz``, ``baseline_variance_hz2``, and
        ``spikes_per_trial`` in ``values`` and ``no_excess`` in ``flags``.
    """
    edges = params.effective_edges()
    pre = pre_counts(spike_times_s, onsets_s, params)
    base = baseline_hz(pre, params)
    lats = trial_latencies(spike_times_s, onsets_s, params)
    rate = psth_rate(bin_counts(lats, edges), edges)
    values, flags = recovery_measures(rate, edges, base, params)
    ex_values, ex_flags = excess_measures(lats, base, params)
    values.update(ex_values)
    flags.update(ex_flags)
    values["baseline_hz"] = base
    values["baseline_variance_hz2"] = baseline_variance_hz2(pre, params)
    values["spikes_per_trial"] = (
        float("nan") if len(lats) == 0 else float(np.mean([len(lat) for lat in lats]))
    )
    return values, flags
