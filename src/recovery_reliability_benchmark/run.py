"""End-to-end within-session reliability evaluation runner for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from . import checks_spikes, controls
from . import spikes as spikes_mod
from .contract import SPEC_VERSION, ContractViolation, validate
from .evaluate import headline, reliability_ceiling, split_halves, variance_components
from .measures import FLAG_KEYS, AnalysisParams

if TYPE_CHECKING:
    from .metadata import Condition, Preparation

SPIKES_INCLUSION_RULE = (
    "A unit is scored for a measure in a condition when that measure is computed in both halves."
)


def _evaluate_measures(
    halves: pd.DataFrame,
    measure_list: list[str],
    evaluated_conditions: list[str],
    best_condition: str,
    n_perm: int,
    seed: int,
    responses: pd.DataFrame | None = None,
    active_units: dict[str, set[str]] | None = None,
    flags_by_condition: dict[str, dict[str, int]] | None = None,
    scored: dict[str, dict[str, set[str]]] | None = None,
    not_scored_measures: set[str] | None = None,
    per_measure_inc: dict[str, dict[str, dict[str, int]]] | None = None,
) -> dict[str, Any]:
    measures_out: dict[str, Any] = {}
    for m in measure_list:
        if not_scored_measures is not None and m in not_scored_measures:
            assert per_measure_inc is not None
            m_entry: dict[str, Any] = {
                "status": "not_scored",
                "per_condition": {c: dict(per_measure_inc[m][c]) for c in evaluated_conditions},
                "counts": {c: dict(per_measure_inc[m][c]) for c in evaluated_conditions},
            }
            if flags_by_condition is not None:
                m_entry["flags"] = {c: dict(flags_by_condition[c]) for c in evaluated_conditions}
            measures_out[m] = m_entry
            continue

        if scored is not None:
            keep = [str(u) in scored[m][str(c)] for u, c in halves.index]
            m_halves = halves.loc[keep]
        else:
            m_halves = halves
        cond_level = m_halves.index.get_level_values("condition")
        per_cond: dict[str, Any] = {}
        for c in evaluated_conditions:
            cond_ceil = reliability_ceiling(m_halves[cond_level == c], m, False)
            if responses is not None and active_units is not None:
                cond_ceil["variance"] = variance_components(responses, m, c, active_units[c])
            else:
                cond_ceil["variance"] = None
            per_cond[c] = cond_ceil
        pooled = {
            "uncentered": reliability_ceiling(m_halves, m, False),
            "centered": reliability_ceiling(m_halves, m, True),
        }
        headline_val, headline_kind = headline(evaluated_conditions, best_condition, per_cond, pooled)
        headline_frame = (
            m_halves if headline_kind == "pooled_centered" else m_halves[cond_level == best_condition]
        )
        headline_center = headline_kind == "pooled_centered"

        null = controls.permutation_null(
            headline_frame,
            m,
            headline_center,
            n_perm=n_perm,
            rng=np.random.default_rng(seed),
        )
        m_entry = {
            "headline": headline_val,
            "headline_kind": headline_kind,
            "per_condition": per_cond,
            "pooled": pooled,
            "null": null,
        }
        if flags_by_condition is not None:
            m_entry["flags"] = {c: dict(flags_by_condition[c]) for c in evaluated_conditions}
        measures_out[m] = m_entry
    return measures_out


def run(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: Sequence[str],
    post_stim_window_s: float | None = None,
    load_duration_s: float | None = None,
    n_perm: int = 1000,
    injected_r: float = 0.85,
    tolerance: float = 0.05,
    seed: int = 42,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
    spikes: pd.DataFrame | None = None,
    analysis: AnalysisParams | None = None,
) -> dict[str, Any]:
    """Validate inputs, run the positive control, and compute within-session reliability ceilings.

    Args:
        units: Recording-unit table.
        responses: Trial-level response table (or trial timeline table on the spikes path).
        measures: Measure names to evaluate.
        post_stim_window_s: Declared post-stimulus window in seconds (optional when ``analysis`` is set).
        load_duration_s: Conditioning load duration in seconds (optional when ``analysis`` is set).
        n_perm: Number of stratified permutations for the null distribution.
        injected_r: Target reliability for the synthetic positive control.
        tolerance: Pass tolerance for the synthetic positive control.
        seed: Random seed for the positive control and permutation null.
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.
        spikes: Optional spike-timestamp DataFrame (required when ``analysis`` is provided).
        analysis: Optional ``AnalysisParams`` enabling the spikes evaluation path.

    Returns:
        Dictionary containing status, versions, parameters, census, inclusion,
        metadata, positive_control, and (when the positive control passes) per-measure
        reliability ceilings and null distributions.

    Raises:
        ValueError: If ``analysis`` is provided without ``spikes``, if ``post_stim_window_s`` or
            ``load_duration_s`` disagrees with ``analysis``, or if ``post_stim_window_s`` is
            omitted on the tables path.
    """
    measure_list = list(measures)
    if analysis is not None:
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
        post_w = float(analysis.post_stim_window_s)
        load_s = float(analysis.load_duration_s)
        trials = spikes_mod.trial_table(responses)
        counts = spikes_mod.per_trial_counts_table(units, trials, spikes, analysis)
        val = validate(
            units,
            counts,
            measures=["spike_count"],
            post_stim_window_s=post_w,
            load_duration_s=load_s,
            preparation=preparation,
            conditions=conditions,
            spikes=spikes,
        )
        checks_spikes.check_pre_stimulus_window(trials, analysis, load_s)
        evaluated_conditions = val["evaluated_conditions"]
        eval_trials = trials[trials["condition"].astype(str).isin(set(evaluated_conditions))]
        halves, flags = spikes_mod.halves_from_spikes(units, eval_trials, spikes, analysis, measure_list)
        scored: dict[str, dict[str, set[str]]] | None = spikes_mod.scored_units(halves, measure_list)
        assert scored is not None
        not_scored_measures: set[str] | None = set()
        first_md3_violation: ContractViolation | None = None
        for m in measure_list:
            try:
                for c in evaluated_conditions:
                    checks_spikes.check_scored_units(scored, m, c)
            except ContractViolation as exc:
                not_scored_measures.add(m)
                if first_md3_violation is None:
                    first_md3_violation = exc
        if measure_list and len(not_scored_measures) == len(measure_list):
            assert first_md3_violation is not None
            raise first_md3_violation
        n_units_in_tables = int(len(units))
        per_measure_inc: dict[str, dict[str, dict[str, int]]] | None = {
            m: {
                c: {
                    "n_units_in_tables": n_units_in_tables,
                    "n_units_scored": len(scored[m][c]),
                    "n_units_excluded_by_rule": n_units_in_tables - len(scored[m][c]),
                }
                for c in evaluated_conditions
            }
            for m in measure_list
        }
        val["inclusion"]["spikes_path"] = {
            "rule": SPIKES_INCLUSION_RULE,
            "per_measure": per_measure_inc,
            **per_measure_inc,
        }
        flags_cond = flags.index.get_level_values("condition")
        flags_by_condition: dict[str, dict[str, int]] | None = {
            c: {
                flag: int(
                    (
                        flags.loc[flags_cond == c, f"{flag}_odd"] | flags.loc[flags_cond == c, f"{flag}_even"]
                    ).sum()
                )
                for flag in FLAG_KEYS
            }
            for c in evaluated_conditions
        }
        active_units: dict[str, set[str]] | None = None
        var_responses: pd.DataFrame | None = None
    else:
        if post_stim_window_s is None:
            raise ValueError("post_stim_window_s is required when analysis is None.")
        post_w = float(post_stim_window_s)
        load_s = 0.0 if load_duration_s is None else float(load_duration_s)
        val = validate(
            units,
            responses,
            measures=measure_list,
            post_stim_window_s=post_w,
            load_duration_s=load_s,
            preparation=preparation,
            conditions=conditions,
            spikes=spikes,
        )
        evaluated_conditions = val["evaluated_conditions"]
        active_units = {c: set(val["conditions"][c]["active_units"]) for c in evaluated_conditions}
        halves = split_halves(responses, measure_list, evaluated_conditions, active_units=active_units)
        flags_by_condition = None
        var_responses = responses
        scored = None
        not_scored_measures = None
        per_measure_inc = None

    census_dict = controls.census(val)
    parameters: dict[str, Any] = {
        "measures": measure_list,
        "post_stim_window_s": post_w,
        "load_duration_s": load_s,
        "n_perm": int(n_perm),
        "injected_r": float(injected_r),
        "tolerance": float(tolerance),
        "seed": int(seed),
        "split_mode": "odd_even",
        "path": "spikes" if analysis is not None else "responses",
    }
    if analysis is not None:
        parameters["analysis"] = analysis.to_dict()
        parameters["analysis_fingerprint"] = analysis.fingerprint()

    from . import __version__

    pc = controls.positive_control(reliability=injected_r, tolerance=tolerance, seed=seed)
    if not pc["passed"]:
        return {
            "status": "positive_control_failed",
            "spec_version": SPEC_VERSION,
            "package_version": __version__,
            "positive_control": pc,
            "census": census_dict,
            "inclusion": val["inclusion"],
            "parameters": parameters,
            "metadata": val["metadata"],
        }

    measures_out = _evaluate_measures(
        halves=halves,
        measure_list=measure_list,
        evaluated_conditions=evaluated_conditions,
        best_condition=val["best_condition"],
        n_perm=n_perm,
        seed=seed,
        responses=var_responses,
        active_units=active_units,
        flags_by_condition=flags_by_condition,
        scored=scored,
        not_scored_measures=not_scored_measures,
        per_measure_inc=per_measure_inc,
    )

    return {
        "status": "ok",
        "spec_version": SPEC_VERSION,
        "package_version": __version__,
        "parameters": parameters,
        "census": census_dict,
        "inclusion": val["inclusion"],
        "metadata": val["metadata"],
        "positive_control": pc,
        "measures": measures_out,
    }
