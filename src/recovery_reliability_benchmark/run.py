"""End-to-end within-session reliability evaluation runner for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from . import controls
from .contract import SPEC_VERSION, validate
from .evaluate import reliability_ceiling, split_halves, variance_components

if TYPE_CHECKING:
    from .metadata import Condition, Preparation


def run(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: Sequence[str],
    post_stim_window_s: float,
    load_duration_s: float = 0.0,
    n_perm: int = 1000,
    injected_r: float = 0.85,
    tolerance: float = 0.05,
    seed: int = 42,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
    spikes: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Validate inputs, run the positive control, and compute within-session reliability ceilings.

    Args:
        units: Recording-unit table.
        responses: Trial-level response table.
        measures: Measure column names to evaluate.
        post_stim_window_s: Declared post-stimulus window in seconds.
        load_duration_s: Conditioning load duration in seconds.
        n_perm: Number of stratified permutations for the null distribution.
        injected_r: Target reliability for the synthetic positive control.
        tolerance: Pass tolerance for the synthetic positive control.
        seed: Random seed for the positive control and permutation null.
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.
        spikes: Optional spike-timestamp DataFrame.

    Returns:
        Dictionary containing status, versions, parameters, census, inclusion,
        metadata, positive_control, and (when the positive control passes) per-measure
        reliability ceilings and null distributions.
    """
    measure_list = list(measures)
    val = validate(
        units,
        responses,
        measures=measure_list,
        post_stim_window_s=post_stim_window_s,
        load_duration_s=load_duration_s,
        preparation=preparation,
        conditions=conditions,
        spikes=spikes,
    )
    census_dict = controls.census(val)
    parameters: dict[str, Any] = {
        "measures": measure_list,
        "post_stim_window_s": float(post_stim_window_s),
        "load_duration_s": float(load_duration_s),
        "n_perm": int(n_perm),
        "injected_r": float(injected_r),
        "tolerance": float(tolerance),
        "seed": int(seed),
        "split_mode": "odd_even",
    }

    pc = controls.positive_control(reliability=injected_r, tolerance=tolerance, seed=seed)
    if not pc["passed"]:
        return {
            "status": "positive_control_failed",
            "positive_control": pc,
            "census": census_dict,
            "inclusion": val["inclusion"],
            "parameters": parameters,
            "metadata": val["metadata"],
        }

    evaluated_conditions = val["evaluated_conditions"]
    best_condition = val["best_condition"]
    active_units = {c: set(val["conditions"][c]["active_units"]) for c in evaluated_conditions}
    halves = split_halves(responses, measure_list, evaluated_conditions, active_units=active_units)
    cond_level = halves.index.get_level_values("condition")

    measures_out: dict[str, Any] = {}
    for m in measure_list:
        per_cond: dict[str, Any] = {}
        for c in evaluated_conditions:
            cond_ceil = reliability_ceiling(halves[cond_level == c], m, False)
            cond_ceil["variance"] = variance_components(responses, m, c, active_units[c])
            per_cond[c] = cond_ceil
        pooled = {
            "uncentered": reliability_ceiling(halves, m, False),
            "centered": reliability_ceiling(halves, m, True),
        }
        if len(evaluated_conditions) >= 2:
            headline = {
                **pooled["centered"],
                "variance": per_cond[best_condition]["variance"],
            }
            headline_kind = "pooled_centered"
            headline_frame = halves
            headline_center = True
        else:
            headline = per_cond[best_condition]
            headline_kind = "per_condition"
            headline_frame = halves[cond_level == best_condition]
            headline_center = False

        null = controls.permutation_null(
            headline_frame,
            m,
            headline_center,
            n_perm=n_perm,
            rng=np.random.default_rng(seed),
        )
        measures_out[m] = {
            "headline": headline,
            "headline_kind": headline_kind,
            "per_condition": per_cond,
            "pooled": pooled,
            "null": null,
        }

    from . import __version__

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
