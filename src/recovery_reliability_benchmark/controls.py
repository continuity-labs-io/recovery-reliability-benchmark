"""Null distribution, synthetic positive control, and independence census for the benchmark."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from . import evaluate
from .contract import validate
from .evaluate import reliability_ceiling, split_halves
from .synthetic import make_tables


# Algorithm: within each condition, draw a random permutation of that
# condition's rows and move the even-half columns (every f"{m}_even" for m in
# measures, plus n_even) along it, leaving the odd half in place; recompute
# reliability_ceiling on the permuted frame with the same center flag; repeat
# n_perm times. Pairings never cross conditions. This is a stratified pairing
# permutation, the same null scipy.stats.permutation_test(permutation_type="pairings")
# computes for a single stratum.
def permutation_null(
    halves: pd.DataFrame,
    measure: str,
    center: bool,
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Compute the stratified pairing-permutation null distribution by shuffling the even half within conditions.

    Args:
        halves: DataFrame of odd and even half means indexed by ``(unit_id, condition)``.
        measure: Measure name to pass to ``reliability_ceiling``.
        center: Whether to condition-center within each half when calling ``reliability_ceiling``.
        n_perm: Number of stratified permutations to draw.
        rng: NumPy random ``Generator`` used to draw row permutations within each condition.

    Returns:
        Dictionary with keys ``median_rho``, ``p95_rho``, ``median_r``, ``p95_r``,
        ``frac_rho_ge_observed``, and ``n_perm``.

    Raises:
        TypeError: If ``rng`` is not a ``numpy.random.Generator``.
    """
    if not isinstance(rng, np.random.Generator):
        raise TypeError(f"rng must be a numpy.random.Generator, got {type(rng).__name__}.")

    present_measures = [
        col.removesuffix("_even") for col in halves.columns if col.endswith("_even") and col != "n_even"
    ]
    moved_cols = [f"{m}_even" for m in present_measures]
    if "n_even" in halves.columns:
        moved_cols.append("n_even")
    assert len(present_measures) > 0 and len(moved_cols) > 0, (
        "halves must contain at least one '<measure>_even' column."
    )

    observed = evaluate.reliability_ceiling(halves, measure, center)["rho"]
    even_arrays = {col: halves[col].to_numpy(copy=True) for col in moved_cols}

    cond_level = "condition" if "condition" in halves.index.names else 1
    cond_vals = halves.index.get_level_values(cond_level)
    cond_groups = [np.flatnonzero(cond_vals == c) for c in cond_vals.unique()]

    perm_idx = np.empty(len(halves), dtype=int)
    rhos = np.empty(n_perm, dtype=float)
    rs = np.empty(n_perm, dtype=float)
    permuted = halves.copy()

    for i in range(n_perm):
        for grp in cond_groups:
            perm_idx[grp] = rng.permutation(grp)
        for col, arr in even_arrays.items():
            permuted[col] = arr[perm_idx]
        res = evaluate.reliability_ceiling(permuted, measure, center)
        rhos[i] = res["rho"]
        rs[i] = res["r_half"]

    return {
        "median_rho": float(np.nanmedian(rhos)),
        "p95_rho": float(np.nanpercentile(rhos, 95)),
        "median_r": float(np.nanmedian(rs)),
        "p95_r": float(np.nanpercentile(rs, 95)),
        "frac_rho_ge_observed": float(np.mean(rhos >= observed)),
        "n_perm": int(n_perm),
    }


def positive_control(
    reliability: float = 0.85,
    n_units: int = 1000,
    n_trials: int = 20,
    seed: int = 42,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Run the synthetic positive control through validate, split_halves, and reliability_ceiling.

    Args:
        reliability: Target full-length reliability injected into the synthetic dataset.
        n_units: Number of synthetic units to generate.
        n_trials: Number of synthetic trials per unit.
        seed: Random seed for synthetic dataset generation.
        tolerance: Maximum allowed absolute difference between recovered and injected reliability.

    Returns:
        Dictionary with keys ``injected``, ``recovered``, ``passed``, ``n_units``,
        ``n_trials``, and ``tolerance``.
    """
    units, responses = make_tables(
        n_units=n_units,
        n_trials=n_trials,
        reliability=reliability,
        seed=seed,
    )
    val = validate(units, responses, measures=["tau"], post_stim_window_s=2.0)
    active_units = {c: set(val["conditions"][c]["active_units"]) for c in val["evaluated_conditions"]}
    halves = split_halves(
        responses,
        measures=["tau"],
        conditions=val["evaluated_conditions"],
        active_units=active_units,
    )
    ceil = reliability_ceiling(halves, "tau", center=False)
    injected = float(reliability)
    recovered = float(ceil["rho"])
    return {
        "injected": injected,
        "recovered": recovered,
        "passed": bool(abs(recovered - injected) <= tolerance),
        "n_units": int(n_units),
        "n_trials": int(n_trials),
        "tolerance": float(tolerance),
    }


def census(validate_result: dict[str, Any]) -> dict[str, Any]:
    """Extract the independence-accounting census from validate()'s return dict.

    Args:
        validate_result: Dictionary returned by ``contract.validate``.

    Returns:
        Dictionary of hierarchy, inclusion, condition, and trial counts.
    """
    evaluated_conditions = list(validate_result["evaluated_conditions"])
    inc = validate_result["inclusion"]
    units_in_tables = int(validate_result["n_units"])
    units_included = int(max(inc["per_condition"][c]["n_units_included"] for c in evaluated_conditions))
    return {
        "preparations": int(validate_result["n_preparations"]),
        "sessions": int(validate_result["n_sessions"]),
        "recordings": int(validate_result["n_recordings"]),
        "units": int(validate_result["n_units"]),
        "units_active": int(validate_result["n_units_active"]),
        "units_in_tables": units_in_tables,
        "units_included": units_included,
        "units_excluded_by_rule": units_in_tables - units_included,
        "rows_missing": int(sum(inc["per_condition"][c]["n_rows_missing"] for c in evaluated_conditions)),
        "declared_exclusions": dict(inc["declared"]),
        "conditions": int(validate_result["n_conditions"]),
        "evaluated_conditions": evaluated_conditions,
        "trials": int(validate_result["n_trials"]),
        "trials_per_unit_condition": float(validate_result["trials_per_unit_condition"]),
    }
