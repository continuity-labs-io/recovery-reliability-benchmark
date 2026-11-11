"""End-to-end within-session reliability evaluation runner for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from . import controls
from .contract import SPEC_VERSION
from .evaluate import headline, reliability_ceiling, variance_components
from .inputs import EvaluationInputs, from_responses, from_spikes
from .measures import AnalysisParams
from .sensitivity import measure_sensitivity

if TYPE_CHECKING:
    from .metadata import Condition, Preparation


def evaluate_measure(inputs: EvaluationInputs, measure: str, n_perm: int, seed: int) -> dict[str, Any]:
    """Compute reliability ceilings and permutation null for a single measure.

    Args:
        inputs: Prepared ``EvaluationInputs`` from the responses or spikes path.
        measure: Name of the measure to evaluate.
        n_perm: Number of stratified permutations for the null distribution.
        seed: Random seed for the permutation null.

    Returns:
        Dictionary containing the measure's evaluation result (either a ``not_scored``
        entry with per-condition unit counts or the full headline, per-condition,
        pooled, and null dictionary, plus optional per-condition flags).
    """
    evaluated_conditions = inputs.evaluated_conditions
    flags = (
        {"flags": {c: dict(inputs.flags_by_condition[c]) for c in evaluated_conditions}}
        if inputs.flags_by_condition is not None
        else {}
    )
    if measure in inputs.not_scored and inputs.scored_counts is not None:
        counts_m = inputs.scored_counts[measure]
        return {
            "status": "not_scored",
            "per_condition": {c: dict(counts_m[c]) for c in evaluated_conditions},
            "counts": {c: dict(counts_m[c]) for c in evaluated_conditions},
            **flags,
        }

    if inputs.scored is not None:
        scored_m = inputs.scored[measure]
        m_halves = inputs.halves.loc[[str(u) in scored_m[str(c)] for u, c in inputs.halves.index]]
    else:
        m_halves = inputs.halves

    cond_level = m_halves.index.get_level_values("condition")
    per_cond: dict[str, Any] = {}
    for c in evaluated_conditions:
        cond_ceil = reliability_ceiling(m_halves[cond_level == c], measure, False)
        cond_ceil["variance"] = (
            variance_components(inputs.responses, measure, c, inputs.active_units[c])
            if inputs.responses is not None and inputs.active_units is not None
            else None
        )
        per_cond[c] = cond_ceil

    pooled = {
        "uncentered": reliability_ceiling(m_halves, measure, False),
        "centered": reliability_ceiling(m_halves, measure, True),
    }
    headline_val, headline_kind = headline(evaluated_conditions, inputs.best_condition, per_cond, pooled)
    headline_center = headline_kind == "pooled_centered"
    headline_frame = m_halves if headline_center else m_halves[cond_level == inputs.best_condition]
    null = controls.permutation_null(
        headline_frame, measure, headline_center, n_perm=n_perm, rng=np.random.default_rng(seed)
    )
    sens = measure_sensitivity(m_halves, measure, evaluated_conditions, n_perm=n_perm, seed=seed)
    return {
        "headline": headline_val,
        "headline_kind": headline_kind,
        "per_condition": per_cond,
        "pooled": pooled,
        "null": null,
        "sensitivity": sens,
        **flags,
    }


def run_with_inputs(
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
) -> tuple[dict[str, Any], EvaluationInputs]:
    """Validate inputs, run the positive control, and return ``(result, inputs)``.

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
        Tuple ``(result, inputs)`` of the evaluation result dictionary and the prepared
        ``EvaluationInputs`` carrying the split-half DataFrame and inclusion sets.

    Raises:
        ValueError: If ``n_perm < 1``, if ``analysis`` is provided without ``spikes``, if
            ``post_stim_window_s`` or ``load_duration_s`` disagrees with ``analysis``, if
            any spikes-path measure is unknown, or if ``post_stim_window_s`` is omitted on
            the tables path.
    """
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1, got {n_perm}.")
    measure_list = list(measures)
    w, d = post_stim_window_s, load_duration_s
    if analysis is not None:
        inputs = from_spikes(units, responses, measure_list, spikes, analysis, w, d, preparation, conditions)
    else:
        inputs = from_responses(units, responses, measure_list, w, d, preparation, conditions, spikes)

    census_dict = controls.census(inputs.val)
    parameters: dict[str, Any] = {
        "measures": measure_list,
        "post_stim_window_s": inputs.post_stim_window_s,
        "load_duration_s": inputs.load_duration_s,
        "n_perm": int(n_perm),
        "injected_r": float(injected_r),
        "tolerance": float(tolerance),
        "seed": int(seed),
        "split_mode": "odd_even",
        "path": inputs.path,
    }
    if analysis is not None:
        parameters["analysis"] = analysis.to_dict()
        parameters["analysis_fingerprint"] = analysis.fingerprint()

    from . import __version__

    pc = controls.positive_control(reliability=injected_r, tolerance=tolerance, seed=seed)
    base = {
        "spec_version": SPEC_VERSION,
        "package_version": __version__,
        "parameters": parameters,
        "census": census_dict,
        "inclusion": inputs.val["inclusion"],
        "metadata": inputs.val["metadata"],
        "positive_control": pc,
    }
    if not pc["passed"]:
        return {"status": "positive_control_failed", **base}, inputs

    measures_out = {m: evaluate_measure(inputs, m, n_perm=n_perm, seed=seed) for m in measure_list}
    ref_m = inputs.reference_measure
    reference = (
        {"measure": ref_m, **evaluate_measure(inputs, ref_m, n_perm=n_perm, seed=seed)}
        if ref_m is not None
        else None
    )
    ref_sens = reference.get("sensitivity") if reference is not None else None
    for m_entry in measures_out.values():
        m_sens = m_entry.get("sensitivity")
        if m_sens is not None:
            for pair, pair_sens in m_sens.items():
                m_z = pair_sens["median_abs_z"]
                ref_z = ref_sens[pair]["median_abs_z"] if ref_sens is not None and pair in ref_sens else None
                pair_sens["beats_reference"] = (
                    bool(m_z > ref_z) if m_z is not None and ref_z is not None else None
                )
    return {"status": "ok", **base, "measures": measures_out, "reference": reference}, inputs


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
        ValueError: If ``n_perm < 1``, if ``analysis`` is provided without ``spikes``, if
            ``post_stim_window_s`` or ``load_duration_s`` disagrees with ``analysis``, if
            any spikes-path measure is unknown, or if ``post_stim_window_s`` is omitted on
            the tables path.
    """
    return run_with_inputs(
        units=units,
        responses=responses,
        measures=measures,
        post_stim_window_s=post_stim_window_s,
        load_duration_s=load_duration_s,
        n_perm=n_perm,
        injected_r=injected_r,
        tolerance=tolerance,
        seed=seed,
        preparation=preparation,
        conditions=conditions,
        spikes=spikes,
        analysis=analysis,
    )[0]
