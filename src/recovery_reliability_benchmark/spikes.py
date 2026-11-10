"""Spike-train to split-half DataFrame conversion for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from .measures import FLAG_KEYS, AnalysisParams, trial_latencies, unit_measures

MEASURE_KEYS: tuple[str, ...] = (
    "t_peak",
    "peak_rate",
    "t_half_peak",
    "t_return",
    "residual",
    "overshoot",
    "baseline_hz",
    "baseline_variance_hz2",
    "spikes_per_trial",
)


def trial_table(responses: pd.DataFrame) -> pd.DataFrame:
    """Extract distinct ``(trial_index, stim_time_ns, condition)`` rows sorted by ``trial_index``.

    Args:
        responses: DataFrame containing ``trial_index``, ``stim_time_ns``, and ``condition`` columns.

    Returns:
        Deduplicated DataFrame with columns ``["trial_index", "stim_time_ns", "condition"]``
        sorted by ``trial_index``.

    Raises:
        ValueError: If any ``trial_index`` has more than one distinct ``stim_time_ns`` or ``condition``.
    """
    cols = ["trial_index", "stim_time_ns", "condition"]
    dedup = responses[cols].drop_duplicates()
    dup_mask = dedup["trial_index"].duplicated(keep=False)
    if dup_mask.any():
        bad_trial = dedup.loc[dup_mask, "trial_index"].iloc[0]
        raise ValueError(f"trial_index {bad_trial} has inconsistent stim_time_ns or condition across rows.")
    return dedup.sort_values("trial_index", kind="mergesort").reset_index(drop=True)


def split_trials(trials: pd.DataFrame, condition: str) -> tuple[np.ndarray, np.ndarray]:
    """Partition a condition's ``trial_index`` values into odd and even halves.

    Trials for ``condition`` are sorted by ``trial_index`` and assigned 1-based positions
    ``1, 2, 3, ...``; odd positions form the first returned array (odd half) and even
    positions form the second (even half). Uses the same rule as ``evaluate.split_halves``,
    enforced by test.

    Args:
        trials: Trial table DataFrame with ``trial_index`` and ``condition`` columns.
        condition: Condition label to filter on.

    Returns:
        Tuple of ``(odd_trial_indices, even_trial_indices)`` as 1D integer NumPy arrays.
    """
    sub = trials.loc[trials["condition"].astype(str) == str(condition), "trial_index"]
    sorted_idx = np.unique(sub.to_numpy(dtype=int))
    return sorted_idx[0::2], sorted_idx[1::2]


def spike_times_by_unit(
    spikes: pd.DataFrame,
    units: Iterable[str] | pd.DataFrame | None = None,
) -> dict[str, np.ndarray]:
    """Map each ``unit_id`` to a sorted 1D float64 array of spike times in seconds.

    Units in ``units`` with no rows in ``spikes`` map to an empty float64 array.

    Args:
        spikes: Spikes DataFrame with ``unit_id`` and ``spike_time_ns`` columns.
        units: Optional unit list (or ``units.csv`` DataFrame with ``unit_id`` column).

    Returns:
        Dictionary mapping ``unit_id`` string to sorted spike timestamps in seconds
        (``spike_time_ns / 1e9``).
    """
    if isinstance(units, pd.DataFrame):
        unit_ids = [str(u) for u in units["unit_id"]]
    elif units is not None:
        unit_ids = [str(u) for u in units]
    else:
        unit_ids = [str(u) for u in spikes["unit_id"].unique()]

    out: dict[str, np.ndarray] = {u: np.empty(0, dtype=float) for u in unit_ids}
    if not spikes.empty:
        for unit_id, grp in spikes.groupby(spikes["unit_id"].astype(str), sort=False):
            out[str(unit_id)] = np.sort(grp["spike_time_ns"].to_numpy(dtype=float) / 1e9)
    return out


def halves_from_spikes(
    units: pd.DataFrame | Iterable[str],
    trials: pd.DataFrame,
    spikes: pd.DataFrame,
    params: AnalysisParams,
    measures: Sequence[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Compute per-half PSTH measures and flags from spike timestamps across units and conditions.

    Args:
        units: Recording units DataFrame (with ``unit_id`` column) or iterable of ``unit_id`` strings.
        trials: Trial table DataFrame with ``trial_index``, ``stim_time_ns``, and ``condition``.
        spikes: Spike timestamps DataFrame with ``unit_id`` and ``spike_time_ns``.
        params: Analysis parameters governing PSTH bins and windows.
        measures: Sequence of measure names to extract from ``unit_measures``.

    Returns:
        Tuple of ``(halves, flags)`` DataFrames indexed by ``(unit_id, condition)``.
        ``halves`` has columns ``{m}_odd``, ``{m}_even`` for each requested measure plus
        ``n_odd`` and ``n_even`` with the same shape and dtypes as ``evaluate.split_halves``.
        ``flags`` has boolean columns ``{flag}_odd`` and ``{flag}_even`` for each flag.

    Raises:
        ValueError: If any requested measure is not in ``unit_measures``'s keys.
    """
    measure_list = list(measures)
    available = ", ".join(MEASURE_KEYS)
    for m in measure_list:
        if m not in MEASURE_KEYS:
            raise ValueError(f"Unknown measure '{m}'. Available measures: {available}.")

    clean_trials = trial_table(trials)
    unit_ids = (
        [str(u) for u in units["unit_id"]] if isinstance(units, pd.DataFrame) else [str(u) for u in units]
    )
    by_unit = spike_times_by_unit(spikes, unit_ids)
    onset_by_trial = dict(
        zip(
            clean_trials["trial_index"].to_numpy(dtype=int),
            clean_trials["stim_time_ns"].to_numpy(dtype=float) / 1e9,
            strict=False,
        )
    )
    conditions = [str(c) for c in clean_trials["condition"].unique()]

    half_cols = [*(f"{m}_{h}" for m in measure_list for h in ("odd", "even")), "n_odd", "n_even"]
    flag_cols = [f"{flag}_{h}" for flag in FLAG_KEYS for h in ("odd", "even")]

    cond_halves: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for cond in conditions:
        odd_idx, even_idx = split_trials(clean_trials, cond)
        if len(odd_idx) > 0 and len(even_idx) > 0:
            odd_onsets = np.asarray([onset_by_trial[int(t)] for t in odd_idx], dtype=float)
            even_onsets = np.asarray([onset_by_trial[int(t)] for t in even_idx], dtype=float)
            cond_halves[cond] = (odd_onsets, even_onsets)

    pairs = sorted((u, c) for u in unit_ids for c in cond_halves)
    if not pairs:
        empty_idx = pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
        return (
            pd.DataFrame(columns=half_cols, index=empty_idx),
            pd.DataFrame(columns=flag_cols, index=empty_idx, dtype=bool),
        )

    half_rows: list[dict[str, Any]] = []
    flag_rows: list[dict[str, bool]] = []
    for u, cond in pairs:
        odd_onsets, even_onsets = cond_halves[cond]
        u_spikes = by_unit[u]
        vals_odd, flags_odd = unit_measures(u_spikes, odd_onsets, params)
        vals_even, flags_even = unit_measures(u_spikes, even_onsets, params)

        h_row: dict[str, Any] = {}
        for m in measure_list:
            h_row[f"{m}_odd"] = float(vals_odd[m])
            h_row[f"{m}_even"] = float(vals_even[m])
        h_row["n_odd"] = int(len(odd_onsets))
        h_row["n_even"] = int(len(even_onsets))
        half_rows.append(h_row)

        f_row: dict[str, bool] = {}
        for flag in FLAG_KEYS:
            f_row[f"{flag}_odd"] = bool(flags_odd[flag])
            f_row[f"{flag}_even"] = bool(flags_even[flag])
        flag_rows.append(f_row)

    idx = pd.MultiIndex.from_tuples(pairs, names=["unit_id", "condition"])
    halves_df = pd.DataFrame(half_rows, index=idx, columns=half_cols)
    for m in measure_list:
        halves_df[f"{m}_odd"] = halves_df[f"{m}_odd"].astype(float)
        halves_df[f"{m}_even"] = halves_df[f"{m}_even"].astype(float)
    halves_df["n_odd"] = halves_df["n_odd"].astype(int)
    halves_df["n_even"] = halves_df["n_even"].astype(int)
    flags_df = pd.DataFrame(flag_rows, index=idx, columns=flag_cols).astype(bool)
    return halves_df, flags_df


def scored_units(halves: pd.DataFrame, measures: Sequence[str]) -> dict[str, dict[str, set[str]]]:
    """Return per-measure, per-condition sets of units with non-NaN values in both halves.

    Implements the inclusion rule on the spikes path: A unit is scored for a measure in a
    condition when that measure is computed in both halves; a silent unit has no baseline
    and is excluded.

    Args:
        halves: Halves DataFrame indexed by ``(unit_id, condition)``.
        measures: Sequence of measure names to score.

    Returns:
        Dictionary mapping each measure name to a dictionary mapping each condition label
        to the set of scored ``unit_id`` strings.
    """
    conditions = [str(c) for c in halves.index.get_level_values("condition").unique()]
    out: dict[str, dict[str, set[str]]] = {}
    for m in measures:
        m_str = str(m)
        valid = halves[[f"{m_str}_odd", f"{m_str}_even"]].notna().all(axis=1)
        per_cond: dict[str, set[str]] = {c: set() for c in conditions}
        for (unit_id, cond), is_valid in valid.items():
            if bool(is_valid):
                per_cond[str(cond)].add(str(unit_id))
        out[m_str] = per_cond
    return out


def per_trial_counts_table(
    units: pd.DataFrame | Iterable[str],
    trials: pd.DataFrame,
    spikes: pd.DataFrame,
    params: AnalysisParams,
) -> pd.DataFrame:
    """Build the per-unit, per-trial post-stimulus spike count table validated on the spikes path.

    Args:
        units: Recording units DataFrame (with ``unit_id`` column) or iterable of ``unit_id`` strings.
        trials: Trial table DataFrame with ``trial_index``, ``stim_time_ns``, and ``condition`` columns.
        spikes: Spike timestamps DataFrame with ``unit_id`` and ``spike_time_ns`` columns.
        params: Analysis parameters defining load duration and post-stimulus window.

    Returns:
        DataFrame with columns ``["unit_id", "trial_index", "stim_time_ns", "condition", "spike_count"]``,
        one row per unit and trial, with ``spike_count = len(latency array)`` as integer.
    """
    clean_trials = trial_table(trials)
    unit_ids = (
        [str(u) for u in units["unit_id"]] if isinstance(units, pd.DataFrame) else [str(u) for u in units]
    )
    by_unit = spike_times_by_unit(spikes, unit_ids)
    onsets_s = clean_trials["stim_time_ns"].to_numpy(dtype=float) / 1e9
    trial_indices = clean_trials["trial_index"].to_numpy(dtype=int)
    stim_times_ns = clean_trials["stim_time_ns"].to_numpy(dtype=int)
    conditions = clean_trials["condition"].astype(str).to_numpy()

    rows: list[dict[str, Any]] = []
    for uid in unit_ids:
        lats = trial_latencies(by_unit[uid], onsets_s, params)
        for ti, stim_ns, cond, lat in zip(trial_indices, stim_times_ns, conditions, lats, strict=False):
            rows.append(
                {
                    "unit_id": uid,
                    "trial_index": int(ti),
                    "stim_time_ns": int(stim_ns),
                    "condition": str(cond),
                    "spike_count": int(len(lat)),
                }
            )
    cols = ["unit_id", "trial_index", "stim_time_ns", "condition", "spike_count"]
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df["spike_count"] = df["spike_count"].astype(int)
    return df
