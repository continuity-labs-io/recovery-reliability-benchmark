"""Spikes-path contract checks for pre-stimulus windows and scored units."""

from __future__ import annotations

from collections.abc import Mapping, Set

import pandas as pd

from . import contract
from .contract import ContractViolation, Requirement
from .frozen import frozen
from .measures import AnalysisParams


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
    scored: Mapping[str, Mapping[str, Set[str]]] | Mapping[str, Set[str]],
    measure: str,
    condition: str,
) -> None:
    """Check min-dataset-3 on the spikes path: at least ``MD3_MUST`` scored units for ``measure``.

    Args:
        scored: Mapping from measure name to per-condition sets of scored ``unit_id`` strings
            (or a per-condition mapping for a single measure).
        measure: Measure name to verify.
        condition: Condition label to verify.

    Raises:
        ContractViolation: With ``Requirement.MD3`` when fewer than ``MD3_MUST`` units are scored.
    """
    first_val = next(iter(scored.values()), None)
    if isinstance(first_val, Mapping):
        nested: Mapping[str, Mapping[str, Set[str]]] = scored  # type: ignore[assignment]
        if measure not in nested and condition in nested:
            measure, condition = condition, measure
        cond_map: Mapping[str, Set[str]] = nested.get(measure, {})
    else:
        flat: Mapping[str, Set[str]] = scored  # type: ignore[assignment]
        if condition not in flat and measure in flat:
            measure, condition = condition, measure
        cond_map = flat

    n_scored = len(cond_map.get(condition, set()))
    if n_scored < contract.MD3_MUST:
        msg = (
            f"{n_scored} units with {measure} computed in both halves "
            f"for condition '{condition}', requires {contract.MD3_MUST}."
        )
        raise ContractViolation(Requirement.MD3, msg, found=n_scored, required=contract.MD3_MUST)
