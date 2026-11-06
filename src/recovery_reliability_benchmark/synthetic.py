"""Synthetic conforming dataset factory for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


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
