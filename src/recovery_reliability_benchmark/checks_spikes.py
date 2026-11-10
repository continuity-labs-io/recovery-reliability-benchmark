"""Spikes-path contract checks for pre-stimulus windows and scored units."""

from __future__ import annotations

from collections.abc import Mapping, Set

import pandas as pd

from . import contract
from .contract import ContractViolation, Requirement
from .measures import AnalysisParams


def check_pre_stimulus_window(
    trials: pd.DataFrame,
    params: AnalysisParams,
    load_duration_s: float | None = None,
) -> None:
    """Check min-dataset-7: pre-stimulus window >= 1.0 s, fits before first onset and between trials.

    Args:
        trials: Trial table DataFrame with ``trial_index`` and ``stim_time_ns`` columns.
        params: Analysis parameters defining ``pre_stim_window_s``.
        load_duration_s: Conditioning train duration in seconds (defaults to ``params.load_duration_s``).

    Raises:
        ContractViolation: With ``Requirement.MD7`` if ``pre_stim_window_s < MD7_MUST``, does not
            fit before the first stimulus onset, or does not fit between a previous load end and
            the next onset.
    """
    pre_w = float(params.pre_stim_window_s)
    req_min = float(contract.MD7_MUST)
    if pre_w < req_min:
        msg = f"Pre-stimulus window {pre_w:.1f} s, requires {req_min:.1f} s."
        raise ContractViolation(Requirement.MD7, msg, found=pre_w, required=req_min)

    if trials.empty:
        return

    load_s = float(params.load_duration_s if load_duration_s is None else load_duration_s)
    trials_by_time = trials.sort_values(["stim_time_ns", "trial_index"]).reset_index(drop=True)
    onsets_s = [int(t) / 1e9 for t in trials_by_time["stim_time_ns"].tolist()]
    trial_indices = [int(i) for i in trials_by_time["trial_index"].tolist()]

    if onsets_s[0] < pre_w:
        msg = (
            f"Pre-stimulus window {pre_w:.1f} s does not fit before "
            f"trial {trial_indices[0]} at {onsets_s[0]:.3f} s, requires onset >= {pre_w:.1f} s."
        )
        raise ContractViolation(Requirement.MD7, msg, found=float(onsets_s[0]), required=pre_w)

    for i in range(1, len(onsets_s)):
        available = onsets_s[i] - (onsets_s[i - 1] + load_s)
        if available < pre_w:
            msg = (
                f"Trial {trial_indices[i]} has {available:.3f} s between the previous load end "
                f"and its onset, requires {pre_w:.1f} s."
            )
            raise ContractViolation(Requirement.MD7, msg, found=float(available), required=pre_w)


def check_scored_units(scored: Mapping[str, Set[str]], condition: str) -> None:
    """Check min-dataset-3 on the spikes path: at least ``MD3_MUST`` scored units in ``condition``.

    Args:
        scored: Mapping from condition label to set of scored ``unit_id`` strings.
        condition: Condition label to verify.

    Raises:
        ContractViolation: With ``Requirement.MD3`` when fewer than ``MD3_MUST`` units are scored.
    """
    n_scored = len(scored.get(condition, set()))
    if n_scored < contract.MD3_MUST:
        msg = (
            f"{n_scored} units with every measure computed in both halves "
            f"for condition '{condition}', requires {contract.MD3_MUST}."
        )
        raise ContractViolation(Requirement.MD3, msg, found=n_scored, required=contract.MD3_MUST)
