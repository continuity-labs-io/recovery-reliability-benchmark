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
    baseline: float,
    params: AnalysisParams,
) -> tuple[dict[str, float], dict[str, bool]]:
    """Compute bin-free excess-spike recovery measures from per-trial latency arrays.

    For an exponential recovery with time constant ``tau`` and a window much longer than
    ``tau``, ``t_half_excess`` estimates ``tau * ln 2``.

    Args:
        latencies: Sequence of per-trial 1D latency arrays in ``[0, post_stim_window_s)``
            from ``trial_latencies`` for one unit and one set of trials.
        baseline: Pooled pre-stimulus baseline firing rate in Hz.
        params: Analysis parameters defining ``post_stim_window_s`` and ``min_excess_z``.

    Returns:
        Tuple of ``(values, flags)`` dictionaries with ``t_half_excess`` and
        ``excess_per_trial`` in ``values`` and ``no_excess`` in ``flags``.
    """
    n = len(latencies)
    nan = float("nan")
    if n == 0:
        return {"t_half_excess": nan, "excess_per_trial": nan}, {"no_excess": True}

    pooled = (
        np.sort(np.concatenate([np.asarray(lat, dtype=float) for lat in latencies]))
        if any(len(lat) > 0 for lat in latencies)
        else np.empty(0, dtype=float)
    )
    n_spikes = len(pooled)
    win = float(params.post_stim_window_s)
    base = float(baseline)

    excess_total = float(n_spikes - base * n * win)
    excess_per_trial = float(excess_total / n)

    if math.isnan(base) or excess_total <= params.min_excess_z * math.sqrt(max(n_spikes, 1)):
        t_half_excess = nan
        no_excess = True
    else:
        k = np.arange(1, n_spikes + 1, dtype=float)
        cum_k = k - base * n * pooled
        first_idx = int(np.flatnonzero(cum_k >= 0.5 * excess_total)[0])
        t_half_excess = float(pooled[first_idx])
        no_excess = False

    values = {
        "t_half_excess": t_half_excess,
        "excess_per_trial": excess_per_trial,
    }
    flags = {
        "no_excess": no_excess,
    }
    return values, flags
