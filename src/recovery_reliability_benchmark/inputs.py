"""Input preparation for the tables and spikes evaluation paths."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pandas as pd

from . import checks_spikes
from . import spikes as spikes_mod
from .contract import ContractViolation, validate
from .evaluate import split_halves
from .frozen import freeze_constant
from .measures import FLAG_KEYS, AnalysisParams

if TYPE_CHECKING:
    from .metadata import Condition, Preparation

SPIKES_INCLUSION_RULE = (
    "A unit is scored for a measure in a condition when that measure is computed in both halves."
)
SPIKES_REFERENCE_MEASURE = "baseline_hz"
freeze_constant(__name__, "SPIKES_INCLUSION_RULE", "SPEC inclusion and exclusion")
freeze_constant(__name__, "SPIKES_REFERENCE_MEASURE", "SPEC measures computed by the benchmark")


@dataclass(frozen=True)
class EvaluationInputs:
    """Validated inputs and split-half tables ready for per-measure reliability evaluation."""

    path: str
    val: dict[str, Any]
    halves: pd.DataFrame
    evaluated_conditions: list[str]
    best_condition: str
    post_stim_window_s: float
    load_duration_s: float
    reference_measure: str | None = None
    responses: pd.DataFrame | None = None
    active_units: dict[str, set[str]] | None = None
    scored: dict[str, dict[str, set[str]]] | None = None
    not_scored: frozenset[str] = frozenset()
    scored_counts: dict[str, dict[str, dict[str, int]]] | None = None
    flags_by_condition: dict[str, dict[str, int]] | None = None


def from_responses(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: Sequence[str],
    post_stim_window_s: float | None = None,
    load_duration_s: float | None = None,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
    spikes: pd.DataFrame | None = None,
) -> EvaluationInputs:
    """Validate and split a trial-level responses table into ``EvaluationInputs``.

    Args:
        units: Recording-unit table.
        responses: Trial-level response table.
        measures: Measure names to evaluate.
        post_stim_window_s: Declared post-stimulus window in seconds.
        load_duration_s: Conditioning load duration in seconds.
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.
        spikes: Optional spike-timestamp DataFrame.

    Returns:
        Populated ``EvaluationInputs`` for the ``"responses"`` path.

    Raises:
        ValueError: If ``post_stim_window_s`` is ``None``.
    """
    if post_stim_window_s is None:
        raise ValueError("post_stim_window_s is required when analysis is None.")
    measure_list = list(measures)
    post_w = float(post_stim_window_s)
    load_s = 0.0 if load_duration_s is None else float(load_duration_s)
    val = validate(
        units,
        responses,
        measure_list,
        post_w,
        load_s,
        preparation=preparation,
        conditions=conditions,
        spikes=spikes,
    )
    evaluated_conditions = val["evaluated_conditions"]
    active_units = {c: set(val["conditions"][c]["active_units"]) for c in evaluated_conditions}
    halves = split_halves(responses, measure_list, evaluated_conditions, active_units=active_units)
    return EvaluationInputs(
        path="responses",
        val=val,
        halves=halves,
        evaluated_conditions=evaluated_conditions,
        best_condition=val["best_condition"],
        post_stim_window_s=post_w,
        load_duration_s=load_s,
        reference_measure=None,
        responses=responses,
        active_units=active_units,
    )


def validate_spikes_path(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    spikes: pd.DataFrame,
    analysis: AnalysisParams,
    extra_forbidden: set[str] | None = None,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Run every contract check of the spikes path, in order.

    Args:
        units: Recording-unit table.
        responses: Trial table carrying ``trial_index``, ``stim_time_ns``, and ``condition``.
        spikes: Spike-timestamp DataFrame.
        analysis: ``AnalysisParams`` defining the load duration and the two windows.
        extra_forbidden: Additional column names disallowed as measures.
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.

    Returns:
        Tuple ``(report, trials)`` of the conformance report from ``validate`` on the per-trial
        spike count table and the deduplicated trial table.

    Raises:
        ContractViolation: On the first failed requirement.
    """
    checks_spikes.check_spikes_path_tables(units, responses, spikes, analysis)
    trials = spikes_mod.trial_table(responses)
    counts = spikes_mod.per_trial_counts_table(units, trials, spikes, analysis)
    checks_spikes.check_spikes_in_windows(counts, int(len(spikes)))
    post_w, load_s = float(analysis.post_stim_window_s), float(analysis.load_duration_s)
    report = validate(
        units, counts, ["spike_count"], post_w, load_s, extra_forbidden, preparation, conditions, spikes
    )
    checks_spikes.check_pre_stimulus_window(trials, analysis, load_s)
    return report, trials


def from_spikes(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: Sequence[str],
    spikes: pd.DataFrame | None,
    analysis: AnalysisParams,
    post_stim_window_s: float | None = None,
    load_duration_s: float | None = None,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
) -> EvaluationInputs:
    """Validate and convert spike timestamps into ``EvaluationInputs``.

    Args:
        units: Recording-unit table.
        responses: Trial timeline table carrying ``trial_index``, ``stim_time_ns``, and ``condition``.
        measures: Measure names to evaluate.
        spikes: Spike-timestamp DataFrame.
        analysis: ``AnalysisParams`` governing spike-derived recovery measures.
        post_stim_window_s: Optional post-stimulus window in seconds (must match ``analysis`` if set).
        load_duration_s: Optional load duration in seconds (must match ``analysis`` if set).
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.

    Returns:
        Populated ``EvaluationInputs`` for the ``"spikes"`` path.

    Raises:
        ValueError: If ``spikes`` is ``None`` or if ``post_stim_window_s`` / ``load_duration_s``
            disagrees with ``analysis``.
        ContractViolation: If ``min-dataset-7`` fails or if no requested measure meets ``min-dataset-3``.
    """
    if spikes is None:
        raise ValueError("analysis requires spikes")
    if post_stim_window_s is not None and float(post_stim_window_s) != float(analysis.post_stim_window_s):
        raise ValueError(
            f"post_stim_window_s ({post_stim_window_s}) differs from "
            f"analysis.post_stim_window_s ({analysis.post_stim_window_s})."
        )
    if load_duration_s is not None and float(load_duration_s) != float(analysis.load_duration_s):
        raise ValueError(
            f"load_duration_s ({load_duration_s}) differs from "
            f"analysis.load_duration_s ({analysis.load_duration_s})."
        )
    measure_list = list(measures)
    requested_set = set(measure_list)
    all_measures = list(dict.fromkeys([*measure_list, SPIKES_REFERENCE_MEASURE]))
    post_w = float(analysis.post_stim_window_s)
    load_s = float(analysis.load_duration_s)
    val, trials = validate_spikes_path(
        units, responses, spikes, analysis, preparation=preparation, conditions=conditions
    )
    evaluated_conditions = val["evaluated_conditions"]
    eval_trials = trials[trials["condition"].astype(str).isin(set(evaluated_conditions))]
    halves, flags = spikes_mod.halves_from_spikes(units, eval_trials, spikes, analysis, all_measures)
    scored = spikes_mod.scored_units(halves, all_measures)
    not_scored_set: set[str] = set()
    first_md3_violation: ContractViolation | None = None
    for m in all_measures:
        try:
            for c in evaluated_conditions:
                checks_spikes.check_scored_units(scored, m, c)
        except ContractViolation as exc:
            not_scored_set.add(m)
            if m in requested_set and first_md3_violation is None:
                first_md3_violation = exc
    if first_md3_violation is not None and requested_set <= not_scored_set:
        raise first_md3_violation
    n_units_in_tables = int(len(units))
    scored_counts: dict[str, dict[str, dict[str, int]]] = {
        m: {
            c: {
                "n_units_in_tables": n_units_in_tables,
                "n_units_scored": len(scored[m][c]),
                "n_units_excluded_by_rule": n_units_in_tables - len(scored[m][c]),
            }
            for c in evaluated_conditions
        }
        for m in all_measures
    }
    val["inclusion"]["spikes_path"] = {
        "rule": SPIKES_INCLUSION_RULE,
        "per_measure": scored_counts,
    }
    flags_cond = flags.index.get_level_values("condition")
    flags_by_condition: dict[str, dict[str, int]] = {
        c: {
            flag: int(
                (flags.loc[flags_cond == c, f"{flag}_odd"] | flags.loc[flags_cond == c, f"{flag}_even"]).sum()
            )
            for flag in FLAG_KEYS
        }
        for c in evaluated_conditions
    }
    return EvaluationInputs(
        path="spikes",
        val=val,
        halves=halves,
        evaluated_conditions=evaluated_conditions,
        best_condition=val["best_condition"],
        post_stim_window_s=post_w,
        load_duration_s=load_s,
        reference_measure=SPIKES_REFERENCE_MEASURE,
        scored=scored,
        not_scored=frozenset(not_scored_set),
        scored_counts=scored_counts,
        flags_by_condition=flags_by_condition,
    )
