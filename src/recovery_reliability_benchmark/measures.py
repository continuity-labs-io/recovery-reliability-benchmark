"""PSTH-based neural recovery measures computed from spike times.

Pure functions on NumPy arrays in seconds. Where ``gate1.py`` fixes a detail (bin time at
bin center for ``t_peak``, ``t_half_peak``, and ``residual`` window; ``t_return`` as the
right edge of the last bin exceeding ``return_x_baseline * baseline``; ``residual`` as the
mean trailing rate divided by baseline; baseline from pooled pre-stimulus counts), it wins.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

FloatArray = Sequence[float] | np.ndarray
IntArray = Sequence[int] | np.ndarray
DEFAULT_BIN_EDGES_S: tuple[float, ...] = tuple(float(x) for x in np.round(np.geomspace(0.003, 10.0, 41), 6))
FLAG_KEYS: tuple[str, ...] = (
    "t_half_peak_censored",
    "t_return_censored",
    "no_response",
    "overshoot_undefined",
    "baseline_zero",
)


@dataclass(frozen=True)
class AnalysisParams:
    """Parameters governing PSTH construction and recovery-kinetics measures.

    Time zero for every latency is ``onset + load_duration_s``; spikes during the load are not latencies.
    """

    post_stim_window_s: float
    pre_stim_window_s: float = 1.0
    load_duration_s: float = 0.0
    bin_edges_s: tuple[float, ...] = DEFAULT_BIN_EDGES_S
    return_x_baseline: float = 1.5
    half_peak_frac: float = 0.5
    residual_s: float = 1.0

    def __post_init__(self) -> None:
        """Validate parameter ranges and coerce bin_edges_s to a tuple of floats."""
        edges = tuple(float(e) for e in self.bin_edges_s)
        object.__setattr__(self, "bin_edges_s", edges)
        if self.post_stim_window_s <= 0.0:
            raise ValueError(f"post_stim_window_s must be > 0, got {self.post_stim_window_s}.")
        if self.pre_stim_window_s <= 0.0:
            raise ValueError(f"pre_stim_window_s must be > 0, got {self.pre_stim_window_s}.")
        if self.load_duration_s < 0.0:
            raise ValueError(f"load_duration_s must be >= 0, got {self.load_duration_s}.")
        if (
            len(edges) < 2
            or edges[0] < 0.0
            or edges[0] >= self.post_stim_window_s
            or any(b <= a for a, b in zip(edges, edges[1:], strict=False))
        ):
            raise ValueError(f"bin_edges_s must be strictly increasing from >= 0, got {self.bin_edges_s}.")
        if not (0.0 < self.half_peak_frac < 1.0):
            raise ValueError(f"half_peak_frac must be in (0, 1), got {self.half_peak_frac}.")
        if self.return_x_baseline <= 1.0:
            raise ValueError(f"return_x_baseline must be > 1, got {self.return_x_baseline}.")
        if not (0.0 < self.residual_s <= self.post_stim_window_s):
            raise ValueError(f"residual_s must be in (0, post_stim_window_s], got {self.residual_s}.")

    def to_dict(self) -> dict[str, Any]:
        """Serialize parameters to a JSON-compatible dictionary."""
        return {**asdict(self), "bin_edges_s": list(self.bin_edges_s)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> AnalysisParams:
        """Construct an AnalysisParams instance from a dictionary."""
        kw = dict(d)
        if "bin_edges_s" in kw:
            kw["bin_edges_s"] = tuple(float(e) for e in kw["bin_edges_s"])
        return cls(**kw)

    def fingerprint(self) -> str:
        """Return the SHA-256 hex digest of ``json.dumps(to_dict(), sort_keys=True)``."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()

    def effective_edges(self) -> np.ndarray:
        """Return edges strictly inside ``post_stim_window_s`` followed by ``post_stim_window_s``."""
        inside = [e for e in self.bin_edges_s if e < self.post_stim_window_s]
        return np.asarray([*inside, float(self.post_stim_window_s)], dtype=float)


def trial_latencies(
    spike_times_s: FloatArray, onsets_s: FloatArray, params: AnalysisParams
) -> list[np.ndarray]:
    """Extract post-load spike latencies per trial in ``[0, post_stim_window_s)``.

    Time zero is ``onset + params.load_duration_s``; spikes during the load are excluded.
    Sorted inputs are not assumed.

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
        i0 = max(0, int(np.searchsorted(spikes, t0, side="left")) - 1)
        i1 = min(len(spikes), int(np.searchsorted(spikes, t0 + win, side="right")) + 1)
        rel = spikes[i0:i1] - t0
        out.append(rel[(rel >= 0.0) & (rel < win)])
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
    counts = np.empty(len(onsets), dtype=int)
    for idx, onset in enumerate(onsets):
        t_end, t_start = float(onset), float(onset) - params.pre_stim_window_s
        i0 = max(0, int(np.searchsorted(spikes, t_start, side="left")) - 1)
        i1 = min(len(spikes), int(np.searchsorted(spikes, t_end, side="right")) + 1)
        seg = spikes[i0:i1]
        counts[idx] = int(np.sum((seg >= t_start) & (seg < t_end)))
    return counts


def baseline_hz(pre_counts: IntArray, params: AnalysisParams) -> float:
    """Compute pooled pre-stimulus baseline firing rate in Hz (matching ``gate1.py``).

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
    """Compute PSTH firing rate in Hz per bin from per-trial bin counts.

    Mean over trials of ``counts`` divided by bin width, equal to pooled counts divided by
    ``(n_trials * width)`` (matching ``gate1.py``).

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

    Where ``gate1.py`` fixes a detail, it wins: bin time is the bin center for ``t_peak``,
    ``t_half_peak``, and the ``residual`` window filter; ``t_return`` is the right edge of
    the last bin with ``rate > return_x_baseline * baseline``; ``residual`` is the mean rate
    over bins with ``center >= post_stim_window_s - residual_s`` divided by ``baseline``.

    Args:
        rate_hz: 1D array of PSTH firing rates in Hz per bin.
        edges_s: 1D array of bin edges in seconds of length ``len(rate_hz) + 1``.
        baseline: Pre-stimulus baseline firing rate in Hz.
        params: Analysis parameters.

    Returns:
        Tuple of ``(values, flags)`` dictionaries.
    """
    rate, edges = np.asarray(rate_hz, dtype=float), np.asarray(edges_s, dtype=float)
    centers, right_edges = 0.5 * (edges[:-1] + edges[1:]), edges[1:]
    peak_idx = int(np.argmax(rate))
    t_peak, peak_rate, base = float(centers[peak_idx]), float(rate[peak_idx]), float(baseline)

    after_peak = np.flatnonzero(rate[peak_idx + 1 :] <= base + params.half_peak_frac * (peak_rate - base))
    t_half_peak_censored = len(after_peak) == 0
    t_half_peak = (
        float(params.post_stim_window_s)
        if t_half_peak_censored
        else float(centers[peak_idx + 1 + int(after_peak[0])])
    )

    nan = float("nan")
    if base == 0.0:
        t_return, residual, overshoot = nan, nan, nan
        t_return_censored, no_response, overshoot_undefined, baseline_zero = False, False, True, True
    else:
        baseline_zero = False
        exceed = np.flatnonzero(rate > params.return_x_baseline * base)
        no_response = len(exceed) == 0
        t_return_censored = not no_response and int(exceed[-1]) == len(rate) - 1
        if no_response:
            t_return = 0.0
        elif t_return_censored:
            t_return = float(params.post_stim_window_s)
        else:
            t_return = float(right_edges[int(exceed[-1])])
        res_mask = centers >= (params.post_stim_window_s - params.residual_s)
        residual = float(np.mean(rate[res_mask]) / base) if np.any(res_mask) else nan
        after_return = rate[centers > t_return]
        overshoot_undefined = t_return_censored or len(after_return) == 0
        overshoot = (
            nan if overshoot_undefined else float(max(0.0, (base - float(np.min(after_return))) / base))
        )

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
    """Run the full PSTH measure chain for one unit over one set of trials.

    Args:
        spike_times_s: 1D array-like of spike timestamps in seconds for one unit.
        onsets_s: 1D array-like of stimulus onset timestamps in seconds.
        params: Analysis parameters.

    Returns:
        Tuple of ``(values, flags)`` dictionaries for the unit, including ``baseline_hz``
        and ``baseline_variance_hz2`` in ``values``.
    """
    edges = params.effective_edges()
    pre = pre_counts(spike_times_s, onsets_s, params)
    base = baseline_hz(pre, params)
    rate = psth_rate(bin_counts(trial_latencies(spike_times_s, onsets_s, params), edges), edges)
    values, flags = recovery_measures(rate, edges, base, params)
    values["baseline_hz"] = base
    values["baseline_variance_hz2"] = baseline_variance_hz2(pre, params)
    return values, flags
