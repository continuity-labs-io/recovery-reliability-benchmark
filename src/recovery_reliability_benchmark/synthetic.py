"""Synthetic conforming dataset factory for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from .frozen import frozen

if TYPE_CHECKING:
    from .measures import AnalysisParams


@frozen("METHOD positive control generator")
def make_tables(
    n_units: int = 8,
    n_trials: int = 10,
    conditions: Sequence[str] = ("A",),
    isi_s: float = 5.0,
    measures: Sequence[str] = ("tau", "amplitude"),
    seed: int = 0,
    reliability: float | None = None,
    condition_offsets: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a conforming (units, responses) dataset for contract tests.

    Produces a conforming dataset by construction. When ``reliability`` is ``None``
    (default), each measure column is drawn uniformly on ``[0.1, 10.0)``.

    When ``reliability`` is set (``0 < reliability < 1``), each measure ``m`` is
    generated independently from:

        T_m[u] ~ N(0, 1) per unit
        E_m[u, t] ~ N(0, sigma^2) per row, with sigma^2 = n_trials * (1 - reliability) / reliability
        measure[u, t] = T_m[u] + offset[condition(t)] + E_m[u, t]

    The per-unit mean over n trials has variance 1 + sigma^2/n, so its reliability is 1 / (1 + sigma^2/n) = rho.
    A split into two halves of n/2 trials gives half-means with correlation 1 / (1 + 2 sigma^2/n); Spearman-Brown on that
    correlation, 2r/(1+r), returns 1 / (1 + sigma^2/n) = rho. So the split-half estimate recovers `reliability` in expectation.

    Args:
        n_units: Number of recording units to generate.
        n_trials: Number of trials per unit per condition.
        conditions: Sequence of condition labels to generate.
        isi_s: Inter-stimulus interval in seconds between consecutive trials.
        measures: Sequence of measure column names to populate.
        seed: Random seed for reproducible generation.
        reliability: Optional target full-length reliability in (0, 1).
        condition_offsets: Optional mapping of condition labels to additive mean shifts.

    Returns:
        Tuple of (units, responses) DataFrames conforming to the benchmark contract.

    Raises:
        ValueError: If reliability is not in (0, 1) or condition_offsets has unknown conditions.
    """
    if reliability is not None and not (0.0 < reliability < 1.0):
        raise ValueError(f"reliability must satisfy 0 < reliability < 1, got {reliability}.")
    if condition_offsets is not None:
        unknown = set(condition_offsets) - set(conditions)
        if unknown:
            raise ValueError(f"condition_offsets contains unknown conditions: {sorted(unknown)}.")

    rng = np.random.default_rng(seed)
    unit_ids = [f"u{i:02d}" for i in range(n_units)]
    units = pd.DataFrame(
        {
            "unit_id": unit_ids,
            "recording_id": "rec0",
            "session_id": "sess0",
            "preparation_id": "prep0",
            "x_um": rng.uniform(0.0, 100.0, size=n_units),
            "y_um": rng.uniform(0.0, 100.0, size=n_units),
        }
    )

    rows = []
    for unit_id in unit_ids:
        for ci, cond in enumerate(conditions):
            for t in range(n_trials):
                trial_index = ci * n_trials + t
                stim_time_ns = int(trial_index * isi_s * 1e9)
                rows.append(
                    {
                        "unit_id": unit_id,
                        "trial_index": trial_index,
                        "stim_time_ns": stim_time_ns,
                        "condition": cond,
                    }
                )
    responses = pd.DataFrame(rows)
    if reliability is None:
        for measure in measures:
            responses[measure] = rng.uniform(0.1, 10.0, size=len(responses))
    else:
        sigma = float(np.sqrt(n_trials * (1.0 - reliability) / reliability))
        offsets = condition_offsets or {}
        cond_offsets_per_unit = np.repeat([float(offsets.get(c, 0.0)) for c in conditions], n_trials)
        trial_offsets = np.tile(cond_offsets_per_unit, n_units)
        rows_per_unit = len(conditions) * n_trials
        for measure in measures:
            t_true = rng.normal(0.0, 1.0, size=n_units)
            err = rng.normal(0.0, sigma, size=len(responses))
            units[f"{measure}_true"] = t_true
            responses[measure] = np.repeat(t_true, rows_per_unit) + trial_offsets + err

    return units, responses


def exponential_recovery(
    baseline_hz: float,
    peak_hz: float,
    tau_s: float,
    dip_hz: float = 0.0,
    dip_s: float = 0.0,
) -> Callable[[np.ndarray], np.ndarray]:
    """Build a synthetic post-stimulus firing-rate curve ``rate(t_s)`` in Hz.

    Evaluates ``baseline_hz + peak_hz * exp(-t / tau_s)`` for ``t >= 0``, subtracts
    ``dip_hz`` on ``3 * tau_s <= t < 3 * tau_s + dip_s``, and floors at ``0.0``.

    Args:
        baseline_hz: Asymptotic resting firing rate in Hz.
        peak_hz: Peak elevation above baseline at ``t = 0`` in Hz.
        tau_s: Exponential recovery time constant in seconds.
        dip_hz: Downward dip amplitude in Hz subtracted during the dip window.
        dip_s: Duration of the post-recovery dip window in seconds starting at ``3 * tau_s``.

    Returns:
        Callable mapping a 1D array of latencies ``t_s`` (seconds) to firing rates (Hz).
    """

    def _rate(t_s: np.ndarray) -> np.ndarray:
        t = np.asarray(t_s, dtype=float)
        rate = np.where(t >= 0.0, baseline_hz + peak_hz * np.exp(-np.maximum(t, 0.0) / tau_s), baseline_hz)
        if dip_hz != 0.0 and dip_s > 0.0:
            in_dip = (t >= 3.0 * tau_s) & (t < 3.0 * tau_s + dip_s)
            rate = np.where(in_dip, rate - dip_hz, rate)
        return np.maximum(rate, 0.0)

    return _rate


def make_spike_trains(
    rate_fns: Sequence[Callable[[np.ndarray], np.ndarray]],
    n_trials: int,
    params: AnalysisParams,
    isi_s: float,
    seed: int,
) -> tuple[list[np.ndarray], np.ndarray]:
    """Generate inhomogeneous Poisson spike trains on a 1 ms grid for multiple units.

    Stimulus onsets are placed at ``isi_s * (k + 1)`` for ``k in range(n_trials)``.
    Within each post-stimulus window ``[onset + load_duration_s, onset + load_duration_s +
    post_stim_window_s)``, the unit's rate is ``rate_fn(latency)``; elsewhere it equals
    ``rate_fn(np.array([1e9]))``.

    Args:
        rate_fns: Sequence of per-unit rate functions ``rate_fn(latency_s) -> rate_hz``.
        n_trials: Number of stimulus trials to simulate.
        params: Analysis parameters defining load duration and post-stimulus window.
        isi_s: Inter-stimulus interval in seconds between consecutive trial onsets.
        seed: Random seed passed to ``numpy.random.default_rng``.

    Returns:
        Tuple of ``(spike_trains, onsets_s)`` where ``spike_trains`` is a list of sorted
        1D float64 spike-timestamp arrays (one per unit) and ``onsets_s`` is the 1D
        float64 array of trial onset times in seconds.
    """
    rng = np.random.default_rng(seed)
    dt = 0.001
    onsets = np.asarray([isi_s * (k + 1) for k in range(n_trials)], dtype=float)
    t_end = float(onsets[-1]) + params.load_duration_s + params.post_stim_window_s + 1.0
    n_steps = int(np.round(t_end / dt))
    grid_t = np.arange(n_steps, dtype=float) * dt

    win_slices: list[tuple[int, int, np.ndarray]] = []
    for onset in onsets:
        t0 = float(onset) + params.load_duration_s
        i0 = int(np.searchsorted(grid_t, t0, side="left"))
        i1 = int(np.searchsorted(grid_t, t0 + params.post_stim_window_s, side="left"))
        win_slices.append((i0, i1, grid_t[i0:i1] - t0))

    trains: list[np.ndarray] = []
    for rate_fn in rate_fns:
        base_rate = float(np.asarray(rate_fn(np.array([1e9], dtype=float)), dtype=float)[0])
        rate = np.full(n_steps, base_rate, dtype=float)
        for i0, i1, lat in win_slices:
            rate[i0:i1] = rate_fn(lat)
        counts = rng.poisson(np.maximum(rate, 0.0) * dt)
        nonzero = np.flatnonzero(counts)
        step_idx = np.repeat(nonzero, counts[nonzero])
        spikes = np.sort(grid_t[step_idx] + rng.uniform(0.0, dt, size=len(step_idx)))
        trains.append(np.asarray(spikes, dtype=float))

    return trains, onsets
