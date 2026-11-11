"""Bin-free neural recovery measures computed on the running post-stimulus spike count."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from .analysis import AnalysisParams
from .frozen import frozen


@frozen("SPEC measures computed by the benchmark")
def excess_measures(
    latencies: Sequence[np.ndarray],
    pre_counts: Sequence[int] | np.ndarray,
    params: AnalysisParams,
) -> tuple[dict[str, float], dict[str, bool]]:
    """Compute bin-free excess-spike recovery measures from per-trial latency arrays.

    Spikes are counted over ``[artifact_blank_s, post_stim_window_s)``, a duration of
    ``counted_s = post_stim_window_s - artifact_blank_s``. For an exponential recovery with
    time constant ``tau`` and a window much longer than ``tau``, ``t_half_excess`` estimates
    ``artifact_blank_s + tau * ln 2``. The response gate works on one number per trial,
    ``d_i = post_i - (counted_s / pre_stim_window_s) * pre_i``:
    ``t_half_excess`` is computed only when ``sum(d) > min_excess_z * sqrt(n) * sd(d)``
    (``sd`` with ``ddof=1``), so a unit that fires in bursts or drifts between trials
    is held to its own trial-to-trial spread.

    Args:
        latencies: Sequence of per-trial 1D latency arrays in ``[artifact_blank_s, post_stim_window_s)``
            from ``trial_latencies`` for one unit and one set of trials.
        pre_counts: Per-trial pre-stimulus spike counts from ``pre_counts`` for the same trials.
        params: Analysis parameters defining the two windows and ``min_excess_z``.

    Returns:
        Tuple of ``(values, flags)`` dictionaries with ``t_half_excess`` and
        ``excess_per_trial`` in ``values`` and ``no_excess`` in ``flags``.

    Raises:
        ValueError: If ``pre_counts`` and ``latencies`` differ in length.
    """
    n = len(latencies)
    nan = float("nan")
    if n == 0:
        return {"t_half_excess": nan, "excess_per_trial": nan}, {"no_excess": True}
    pre = np.asarray(pre_counts, dtype=float)
    if len(pre) != n:
        raise ValueError(f"pre_counts has {len(pre)} trials, latencies has {n}.")

    pooled = (
        np.sort(np.concatenate([np.asarray(lat, dtype=float) for lat in latencies]))
        if any(len(lat) > 0 for lat in latencies)
        else np.empty(0, dtype=float)
    )
    n_spikes = len(pooled)
    blank = float(params.artifact_blank_s)
    counted_s = float(params.post_stim_window_s) - blank
    base = float(np.sum(pre) / (n * params.pre_stim_window_s))
    excess_total = float(n_spikes - base * n * counted_s)
    excess_per_trial = float(excess_total / n)

    post = np.asarray([len(lat) for lat in latencies], dtype=float)
    per_trial = post - (counted_s / params.pre_stim_window_s) * pre
    spread = float(np.std(per_trial, ddof=1)) if n >= 2 else 0.0
    if n < 2:
        responds = False
    elif spread > 0.0:
        responds = excess_total > params.min_excess_z * math.sqrt(n) * spread
    else:
        responds = excess_total > 0.0

    if responds:
        k = np.arange(1, n_spikes + 1, dtype=float)
        cum_k = k - base * n * (pooled - blank)
        first_idx = int(np.flatnonzero(cum_k >= 0.5 * excess_total)[0])
        t_half_excess = float(pooled[first_idx])
    else:
        t_half_excess = nan

    values = {
        "t_half_excess": t_half_excess,
        "excess_per_trial": excess_per_trial,
    }
    flags = {
        "no_excess": not responds,
    }
    return values, flags
