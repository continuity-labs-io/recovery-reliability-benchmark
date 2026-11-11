"""Spikes-path contract checks for pre-stimulus windows and scored units."""

from __future__ import annotations

from collections.abc import Mapping, Set

import pandas as pd

from . import checks, contract
from .contract import ContractViolation, Requirement, ValidationContext
from .frozen import frozen
from .measures import AnalysisParams

TRIALS_REQUIRED = ("trial_index", "stim_time_ns", "condition")


@frozen("SPEC SCHEMA")
def check_spikes_path_tables(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    spikes: pd.DataFrame,
    params: AnalysisParams,
) -> None:
    """Check the units, trial and spikes tables before any spike is counted.

    Required columns and nulls are checked here; the stimulus timeline is then checked by
    the tables-path functions ``check_stimulus_timeline`` (min-dataset-4) and
    ``check_post_stimulus_window`` (min-dataset-6), so one fault gives one message on
    both paths.

    Args:
        units: Recording-unit table.
        responses: Trial table with ``trial_index``, ``stim_time_ns`` and ``condition``.
        spikes: Spike table with ``unit_id`` and ``spike_time_ns``.
        params: Analysis parameters defining ``post_stim_window_s`` and ``load_duration_s``.

    Raises:
        ContractViolation: With ``Requirement.SCHEMA`` on a missing required column or a null
            ``trial_index``, ``condition`` or ``spike_time_ns``; with ``Requirement.MD4`` or
            ``Requirement.MD6`` from the timeline checks.
    """
    tables = (
        ("units", units, contract.UNITS_REQUIRED),
        ("responses", responses, TRIALS_REQUIRED),
        ("spikes", spikes, contract.SPIKES_REQUIRED),
    )
    for name, table, required in tables:
        for col in required:
            if col not in table.columns:
                raise ContractViolation(Requirement.SCHEMA, f"{name} is missing required column '{col}'.")
    for name, table, col in (
        ("responses", responses, "trial_index"),
        ("responses", responses, "condition"),
        ("spikes", spikes, "spike_time_ns"),
    ):
        n_null = int(table[col].isna().sum())
        if n_null > 0:
            msg = f"{n_null} {name} rows have a null {col}, requires 0."
            raise ContractViolation(Requirement.SCHEMA, msg, found=n_null, required=0)
    ctx = ValidationContext(
        units=units,
        responses=responses,
        measures=[],
        post_stim_window_s=float(params.post_stim_window_s),
        load_duration_s=float(params.load_duration_s),
        forbidden=frozenset(),
        preparation=None,
        conditions=None,
        spikes=None,
    )
    checks.check_stimulus_timeline(ctx)
    checks.check_post_stimulus_window(ctx)


@frozen("SPEC SCHEMA")
def check_spikes_in_windows(counts: pd.DataFrame, n_spikes: int) -> None:
    """Check that at least one spike falls inside a post-stimulus window.

    Args:
        counts: Per-unit, per-trial table from ``spikes.per_trial_counts_table``.
        n_spikes: Number of rows in the spikes table.

    Raises:
        ContractViolation: With ``Requirement.SCHEMA`` when every ``spike_count`` is zero, which
            is what a clock or unit mismatch between spikes and stimuli looks like.
    """
    if int(counts["spike_count"].sum()) == 0:
        msg = (
            f"0 of {n_spikes} spikes fall inside a post-stimulus window, requires at least 1. "
            "Check that spike_time_ns and stim_time_ns are integer nanoseconds on the same clock."
        )
        raise ContractViolation(Requirement.SCHEMA, msg, found=0, required=1)


@frozen("SPEC min-dataset-7")
def check_pre_stimulus_window(
    trials: pd.DataFrame,
    params: AnalysisParams,
    load_duration_s: float | None = None,
) -> None:
    """Check min-dataset-7: pre-stimulus window >= 1.0 s, fits before first onset and between trials.

    The pre-stimulus window must start at or after the end of the previous post-stimulus
    window, so consecutive stimulus onsets are at least ``load_duration_s +
    post_stim_window_s + pre_stim_window_s`` apart.

    Args:
        trials: Trial table DataFrame with ``trial_index`` and ``stim_time_ns`` columns.
        params: Analysis parameters defining ``pre_stim_window_s`` and ``post_stim_window_s``.
        load_duration_s: Conditioning train duration in seconds (defaults to ``params.load_duration_s``).

    Raises:
        ContractViolation: With ``Requirement.MD7`` if ``pre_stim_window_s < MD7_MUST``, does not
            fit before the first stimulus onset, or does not fit between the end of a previous
            post-stimulus window and the next onset.
    """
    pre_w = float(params.pre_stim_window_s)
    req_min = float(contract.MD7_MUST)
    if pre_w < req_min:
        msg = f"Pre-stimulus window {pre_w:.1f} s, requires {req_min:.1f} s."
        raise ContractViolation(Requirement.MD7, msg, found=pre_w, required=req_min)

    if trials.empty:
        return

    post_w = float(params.post_stim_window_s)
    load_s = float(params.load_duration_s if load_duration_s is None else load_duration_s)
    trials_by_time = trials.sort_values(["stim_time_ns", "trial_index"]).reset_index(drop=True)
    onsets_ns = [int(t) for t in trials_by_time["stim_time_ns"].tolist()]
    onsets_s = [t / 1e9 for t in onsets_ns]
    trial_indices = [int(i) for i in trials_by_time["trial_index"].tolist()]

    if onsets_s[0] < pre_w:
        msg = (
            f"Pre-stimulus window {pre_w:.1f} s does not fit before "
            f"trial {trial_indices[0]} at {onsets_s[0]:.3f} s, requires onset >= {pre_w:.1f} s."
        )
        raise ContractViolation(Requirement.MD7, msg, found=float(onsets_s[0]), required=pre_w)

    load_ns, post_ns, pre_ns = (int(round(x * 1e9)) for x in (load_s, post_w, pre_w))
    for i in range(1, len(onsets_ns)):
        gap_ns = onsets_ns[i] - onsets_ns[i - 1]
        available_ns = gap_ns - load_ns - post_ns
        if available_ns < pre_ns:
            available = available_ns / 1e9
            msg = (
                f"Trial {trial_indices[i]} has {available:.3f} s between the end of the previous "
                f"post-stimulus window and its onset (gap {gap_ns / 1e9:.3f} s minus load {load_s:.3f} s "
                f"minus post-stimulus window {post_w:.3f} s), requires {pre_w:.1f} s."
            )
            raise ContractViolation(Requirement.MD7, msg, found=float(available), required=pre_w)


@frozen("SPEC min-dataset-3")
def check_scored_units(
    scored: Mapping[str, Mapping[str, Set[str]]],
    measure: str,
    condition: str,
) -> None:
    """Check min-dataset-3 on the spikes path: at least ``MD3_MUST`` scored units for ``measure``.

    Args:
        scored: Mapping from measure name to per-condition sets of scored ``unit_id`` strings.
        measure: Measure name to verify.
        condition: Condition label to verify.

    Raises:
        ContractViolation: With ``Requirement.MD3`` when fewer than ``MD3_MUST`` units are scored.
    """
    n_scored = len(scored.get(measure, {}).get(condition, set()))
    if n_scored < contract.MD3_MUST:
        msg = (
            f"{n_scored} units with {measure} computed in both halves "
            f"for condition '{condition}', requires {contract.MD3_MUST}."
        )
        raise ContractViolation(Requirement.MD3, msg, found=n_scored, required=contract.MD3_MUST)
