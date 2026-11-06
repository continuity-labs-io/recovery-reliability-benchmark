"""Within-session reliability ceiling evaluator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from . import contract
from .contract import (
    SPEC_VERSION,
    ContractViolation,
    _validate_durations,
    file_sha256,
    read_spikes,
    read_tables,
    validate,
)
from .synthetic import make_tables

if TYPE_CHECKING:
    from .metadata import Condition, Preparation

logger = logging.getLogger(__name__)

# the SHOULD threshold of min-dataset-2; rho_at_20 is the ceiling a fully conforming session would show
REFERENCE_N_TRIALS = contract.MD2_SHOULD


def split_halves(
    responses: pd.DataFrame,
    measures: Sequence[str],
    conditions: Sequence[str],
    active_units: dict[str, set[str]] | None = None,
) -> pd.DataFrame:
    """Partition trials into odd and even halves by 1-based position within each (unit_id, condition) group.

    Within each ``(unit_id, condition)`` group, trials are sorted by ``trial_index``
    and assigned 1-based positions ``1, 2, 3, ...``; positions ``1, 3, 5, ...`` form
    the odd half and positions ``2, 4, 6, ...`` form the even half. Trials are ranked
    within each group rather than split by global ``trial_index`` parity because
    interleaved conditions or dropped trials can leave a group with only even or only
    odd global ``trial_index`` values. Groups where either half is empty are dropped.

    Args:
        responses: Trial-level response DataFrame containing ``unit_id``, ``condition``,
            ``trial_index``, and the measure columns.
        measures: Measure column names to average within each half.
        conditions: Condition labels to include in the partition.
        active_units: Optional mapping from condition label to the set of active
            ``unit_id`` values to retain in that condition.

    Returns:
        DataFrame indexed by ``(unit_id, condition)`` with columns ``f"{m}_odd"``
        and ``f"{m}_even"`` for each measure ``m``, plus ``n_odd`` and ``n_even``.
    """
    measure_list = list(measures)
    cond_set = set(conditions)
    sub = responses[responses["condition"].isin(cond_set)].copy()
    if sub.empty:
        empty_index = pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
        cols = [*(f"{m}_{h}" for m in measure_list for h in ("odd", "even")), "n_odd", "n_even"]
        return pd.DataFrame(columns=cols, index=empty_index)

    sub["unit_id"] = sub["unit_id"].astype(str)
    sub["condition"] = sub["condition"].astype(str)
    if active_units is not None:
        active_sets = {str(c): {str(u) for u in us} for c, us in active_units.items()}
        keep = [
            u in active_sets.get(c, set()) for u, c in zip(sub["unit_id"], sub["condition"], strict=False)
        ]
        sub = sub[keep]
        if sub.empty:
            empty_index = pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
            cols = [*(f"{m}_{h}" for m in measure_list for h in ("odd", "even")), "n_odd", "n_even"]
            return pd.DataFrame(columns=cols, index=empty_index)

    sub = sub.sort_values(["unit_id", "condition", "trial_index"], kind="mergesort")

    position = sub.groupby(["unit_id", "condition"], sort=False).cumcount() + 1
    half_odd = sub[position % 2 == 1]
    half_even = sub[position % 2 == 0]

    grp_odd = half_odd.groupby(["unit_id", "condition"], sort=True)
    grp_even = half_even.groupby(["unit_id", "condition"], sort=True)

    n_odd = grp_odd.size()
    n_even = grp_even.size()
    common_idx = n_odd.index.intersection(n_even.index)
    common_idx.names = ["unit_id", "condition"]

    means_odd = grp_odd[measure_list].mean().reindex(common_idx)
    means_even = grp_even[measure_list].mean().reindex(common_idx)

    out_cols: dict[str, Any] = {}
    for m in measure_list:
        out_cols[f"{m}_odd"] = means_odd[m].astype(float)
        out_cols[f"{m}_even"] = means_even[m].astype(float)
    out_cols["n_odd"] = n_odd.reindex(common_idx).astype(int)
    out_cols["n_even"] = n_even.reindex(common_idx).astype(int)

    return pd.DataFrame(out_cols, index=common_idx)


def reliability_ceiling(
    halves: pd.DataFrame,
    measure: str,
    center: bool = False,
    confidence: float = 0.95,
) -> dict[str, Any]:
    """Compute the split-half Pearson correlation, Spearman-Brown reliability ceiling, and Fisher-z interval.

    Args:
        halves: DataFrame of per-unit, per-condition odd and even half means as
            returned by ``split_halves``.
        measure: Measure name prefix to evaluate (reads ``f"{measure}_odd"`` and
            ``f"{measure}_even"``).
        center: If True, subtract each condition's mean over units within each
            half separately before correlating.
        confidence: Confidence level in ``(0, 1)`` for the two-sided Fisher-z
            interval (default ``0.95``).

    Returns:
        Dictionary with the following keys:
            r_half: Raw Pearson correlation between the odd and even half means (NaN if undefined).
            r_ci_low: Lower Fisher-z confidence bound on r_half, or None when n_eff < 4 or r_half is undefined.
            r_ci_high: Upper Fisher-z confidence bound on r_half, or None when n_eff < 4 or r_half is undefined.
            rho: Spearman-Brown corrected reliability ceiling 2r / (1 + r), floored at 0.0.
            rho_ci_low: Lower confidence bound on rho via Spearman-Brown on r_ci_low (floored at 0.0), or None.
            rho_ci_high: Upper confidence bound on rho via Spearman-Brown on r_ci_high (floored at 0.0), or None.
            n_eff: Effective sample size used for the Fisher-z interval (equal to n_units).
            n_trials_group: Median of n_odd + n_even across evaluated (unit_id, condition) pairs.
            rho_single_trial: Single-trial reliability obtained by inverting Spearman-Brown at n_trials_group.
            rho_at_20: Reliability projected to REFERENCE_N_TRIALS (20) trials via Spearman-Brown.
            n_pairs: Number of non-null (unit_id, condition) pairs correlated.
            n_units: Number of distinct units among the correlated pairs.
            n_conditions: Number of distinct conditions among the correlated pairs.
            r_undefined: True when fewer than 3 pairs are present or either half is constant.
            r_nonpositive: True when r_half is defined and r_half <= 0.
            odd_trials: True when any pair has n_odd != n_even.
            center: Boolean flag recording whether condition-centering was applied.

    Notes:
        The Fisher-z standard error uses ``n_eff = n_units`` rather than ``n_pairs``
        because pooled ``(unit_id, condition)`` pairs share physical units across
        conditions and are not independent observations; counting distinct units is
        the conservative choice.

        The ceiling ``rho`` is floored at ``0.0`` when ``r_half`` is undefined or
        non-positive because reliability is a variance ratio in ``[0, 1]`` and the
        Spearman-Brown formula ``2r / (1 + r)`` is not meaningful for ``r <= 0``
        (diverging as ``r`` approaches ``-1``). Ceilings from sessions with
        different trial counts are compared through ``rho_single_trial`` or
        ``rho_at_20``, not through ``rho``.
    """
    from scipy.stats import norm

    col_odd = f"{measure}_odd"
    col_even = f"{measure}_even"
    valid_mask = halves[col_odd].notna() & halves[col_even].notna()
    sub = halves.loc[valid_mask]

    x = sub[col_odd].astype(float)
    y = sub[col_even].astype(float)

    unit_level = "unit_id" if "unit_id" in sub.index.names else 0
    cond_level = "condition" if "condition" in sub.index.names else 1

    n_pairs = int(len(sub))
    n_units = int(sub.index.get_level_values(unit_level).nunique()) if n_pairs > 0 else 0
    n_conditions = int(sub.index.get_level_values(cond_level).nunique()) if n_pairs > 0 else 0
    if "n_odd" in sub.columns and "n_even" in sub.columns and n_pairs > 0:
        odd_trials = bool((sub["n_odd"] != sub["n_even"]).any())
        n_trials_group = float(np.median((sub["n_odd"] + sub["n_even"]).to_numpy(dtype=float)))
    else:
        odd_trials = False
        n_trials_group = 0.0

    if center and n_pairs > 0:
        x = x - x.groupby(level=cond_level).transform("mean")
        y = y - y.groupby(level=cond_level).transform("mean")

    xv = x.to_numpy(dtype=float)
    yv = y.to_numpy(dtype=float)
    if n_pairs < 3:
        logger.debug("Undefined r_half for measure '%s': fewer than 3 pairs (n_pairs=%d).", measure, n_pairs)
        r = float("nan")
    elif np.allclose(xv, xv[0], rtol=0.0, atol=1e-15):
        logger.debug("Undefined r_half for measure '%s': odd half is constant.", measure)
        r = float("nan")
    elif np.allclose(yv, yv[0], rtol=0.0, atol=1e-15):
        logger.debug("Undefined r_half for measure '%s': even half is constant.", measure)
        r = float("nan")
    else:
        dx = xv - xv.mean()
        dy = yv - yv.mean()
        denom = float(np.sqrt(np.dot(dx, dx) * np.dot(dy, dy)))
        if denom == 0.0:
            logger.debug("Undefined r_half for measure '%s': zero variance denominator.", measure)
            r = float("nan")
        else:
            r = float(np.clip(np.dot(dx, dy) / denom, -1.0, 1.0))

    r_undefined = bool(np.isnan(r))
    r_nonpositive = bool(not r_undefined and r <= 0.0)
    if r_nonpositive:
        logger.debug("Nonpositive r_half for measure '%s': r_half=%f.", measure, r)

    rho = float(2.0 * r / (1.0 + r)) if (not r_undefined and r > 0.0) else 0.0

    n_eff = n_units
    if n_eff < 4:
        logger.debug("CI not computed for measure '%s': n_eff=%d < 4.", measure, n_eff)
    if n_eff < 4 or r_undefined:
        r_ci_low: float | None = None
        r_ci_high: float | None = None
        rho_ci_low: float | None = None
        rho_ci_high: float | None = None
    else:
        z_crit = float(norm.ppf(0.5 + confidence / 2.0))
        with np.errstate(divide="ignore"):
            z = float(np.arctanh(r))
        se = 1.0 / float(np.sqrt(n_eff - 3))
        r_ci_low = float(np.tanh(z - z_crit * se))
        r_ci_high = float(np.tanh(z + z_crit * se))
        rho_ci_low = float(2.0 * r_ci_low / (1.0 + r_ci_low)) if r_ci_low > 0.0 else 0.0
        rho_ci_high = float(2.0 * r_ci_high / (1.0 + r_ci_high)) if r_ci_high > 0.0 else 0.0

    if rho == 0.0 or n_trials_group <= 0.0:
        rho_single_trial = 0.0
        rho_at_20 = 0.0
    else:
        denom_single = n_trials_group - (n_trials_group - 1.0) * rho
        rho_single_trial = float(rho / denom_single) if denom_single > 0.0 else 1.0
        ref_n = float(REFERENCE_N_TRIALS)
        rho_at_20 = float(ref_n * rho_single_trial / (1.0 + (ref_n - 1.0) * rho_single_trial))

    return {
        "r_half": r,
        "r_ci_low": r_ci_low,
        "r_ci_high": r_ci_high,
        "rho": rho,
        "rho_ci_low": rho_ci_low,
        "rho_ci_high": rho_ci_high,
        "n_eff": n_eff,
        "n_trials_group": n_trials_group,
        "rho_single_trial": rho_single_trial,
        "rho_at_20": rho_at_20,
        "n_pairs": n_pairs,
        "n_units": n_units,
        "n_conditions": n_conditions,
        "r_undefined": r_undefined,
        "r_nonpositive": r_nonpositive,
        "odd_trials": odd_trials,
        "center": bool(center),
    }


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

    observed = reliability_ceiling(halves, measure, center)["rho"]
    even_arrays = {col: halves[col].to_numpy(copy=True) for col in moved_cols}

    cond_level = "condition" if "condition" in halves.index.names else 1
    cond_vals = halves.index.get_level_values(cond_level)
    cond_groups = [np.flatnonzero(cond_vals == c) for c in cond_vals.unique()]

    perm_idx = np.empty(len(halves), dtype=int)
    rhos = np.empty(n_perm, dtype=float)
    rs = np.empty(n_perm, dtype=float)

    for i in range(n_perm):
        for grp in cond_groups:
            perm_idx[grp] = rng.permutation(grp)
        permuted = halves.copy()
        for col, arr in even_arrays.items():
            permuted[col] = arr[perm_idx]
        res = reliability_ceiling(permuted, measure, center)
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


def variance_components(
    responses: pd.DataFrame,
    measure: str,
    condition: str,
    active_units: Iterable[str] | dict[str, Iterable[str]] | None = None,
) -> dict[str, Any]:
    """Compute between-unit and within-unit variance components and moments reliability.

    A ceiling driven by between-unit heterogeneity shows up as large ``var_between``
    relative to ``var_within``; ``moments_reliability`` is the ANOVA-style estimate of
    the same quantity the split-half ceiling estimates, and the two should agree.

    Args:
        responses: Trial-level response DataFrame.
        measure: Measure column name to analyze.
        condition: Condition label to filter on.
        active_units: Optional iterable of active ``unit_id`` values (or mapping from
            condition label to active ``unit_id`` values).

    Returns:
        Dictionary with keys ``var_between``, ``var_within``, ``n_trials``, and
        ``moments_reliability``.
    """
    cond_mask = responses["condition"].astype(str) == str(condition)
    sub = responses.loc[cond_mask]
    if active_units is not None:
        if isinstance(active_units, dict):
            unit_set = {str(u) for u in active_units.get(str(condition), ())}
        else:
            unit_set = {str(u) for u in active_units}
        sub = sub.loc[sub["unit_id"].astype(str).isin(unit_set)]

    g = sub.groupby(sub["unit_id"].astype(str), sort=False)[measure]
    unit_means = g.mean()
    unit_vars = g.var(ddof=1)
    unit_counts = g.count()

    var_between = float(unit_means.var(ddof=1)) if len(unit_means) >= 2 else 0.0
    var_within = float(unit_vars.mean()) if len(unit_vars) >= 1 else 0.0
    n_trials = float(unit_counts.median()) if len(unit_counts) >= 1 else 0.0

    if var_between > 0.0 and n_trials > 0.0:
        moments_reliability: float | None = float(
            max(0.0, (var_between - var_within / n_trials) / var_between)
        )
    else:
        moments_reliability = None

    return {
        "var_between": var_between,
        "var_within": var_within,
        "n_trials": n_trials,
        "moments_reliability": moments_reliability,
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
    census_dict = census(val)
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

    pc = positive_control(reliability=injected_r, tolerance=tolerance, seed=seed)
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

        null = permutation_null(
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


def main(argv: list[str] | None = None) -> int:
    """Run the within-session reliability ceiling CLI.

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 1 on contract violation, 2 on input error,
        3 on positive-control failure).
    """
    from .metadata import load_conditions, load_preparation

    parser = argparse.ArgumentParser(
        description="Compute within-session reliability ceilings on conforming units and responses CSV tables."
    )
    parser.add_argument("units_csv", help="Path to units CSV file.")
    parser.add_argument("responses_csv", help="Path to responses CSV file.")
    parser.add_argument("--measures", required=True, help="Comma-separated measure column names.")
    parser.add_argument(
        "--post-stim-window-s", required=True, type=float, help="Post-stimulus window in seconds."
    )
    parser.add_argument(
        "--load-duration-s", type=float, default=0.0, help="Conditioning load duration in seconds."
    )
    parser.add_argument(
        "--n-perm", type=int, default=1000, help="Permutations for the label-permutation null."
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--preparation", default=None, help="Path to preparation.json metadata sidecar.")
    parser.add_argument("--conditions", default=None, help="Path to conditions.json metadata sidecar.")
    parser.add_argument("--spikes", default=None, help="Path to spikes.csv table.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]

    try:
        _validate_durations(args.post_stim_window_s, args.load_duration_s)
        units, responses = read_tables(args.units_csv, args.responses_csv)
        spikes = read_spikes(args.spikes) if args.spikes is not None else None
        for opt_path in (args.preparation, args.conditions):
            if opt_path is not None and not Path(opt_path).is_file():
                raise FileNotFoundError(opt_path)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inputs_meta: dict[str, Any] = {
        "units": {"path": args.units_csv, "sha256": file_sha256(args.units_csv)},
        "responses": {"path": args.responses_csv, "sha256": file_sha256(args.responses_csv)},
    }
    if args.preparation is not None:
        inputs_meta["preparation"] = {"path": args.preparation, "sha256": file_sha256(args.preparation)}
    if args.conditions is not None:
        inputs_meta["conditions"] = {"path": args.conditions, "sha256": file_sha256(args.conditions)}
    if args.spikes is not None:
        inputs_meta["spikes"] = {"path": args.spikes, "sha256": file_sha256(args.spikes)}

    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "n_perm": int(args.n_perm),
        "seed": int(args.seed),
    }

    try:
        preparation = load_preparation(args.preparation) if args.preparation is not None else None
        conditions = load_conditions(args.conditions) if args.conditions is not None else None
        result = run(
            units,
            responses,
            measures=measures,
            post_stim_window_s=args.post_stim_window_s,
            load_duration_s=args.load_duration_s,
            n_perm=args.n_perm,
            seed=args.seed,
            preparation=preparation,
            conditions=conditions,
            spikes=spikes,
        )
    except ContractViolation as exc:
        if args.as_json:
            doc = {
                "spec_version": SPEC_VERSION,
                "status": "violation",
                "inputs": inputs_meta,
                "arguments": arguments_meta,
                "violation": exc.to_dict(),
            }
            print(json.dumps(doc, indent=2, sort_keys=True))
        else:
            print(str(exc))
        return 1

    if result["status"] == "positive_control_failed":
        if args.as_json:
            doc = {
                "spec_version": SPEC_VERSION,
                "status": result["status"],
                "inputs": inputs_meta,
                "arguments": arguments_meta,
                "result": result,
            }
            print(json.dumps(doc, indent=2, sort_keys=True))
        else:
            print("positive_control_failed")
        return 3

    if args.as_json:
        doc = {
            "spec_version": SPEC_VERSION,
            "status": result["status"],
            "inputs": inputs_meta,
            "arguments": arguments_meta,
            "result": result,
        }
        print(json.dumps(doc, indent=2, sort_keys=True))
    else:
        print("census:")
        for key, value in result["census"].items():
            print(f"  {key}: {value}")
        decl = result["inclusion"]["declared"]
        for cond in result["census"]["evaluated_conditions"]:
            inc = result["inclusion"]["per_condition"][cond]
            print(
                f"{cond}: units included {inc['n_units_included']} of {inc['n_units_in_tables']} "
                f"(excluded by rule {inc['n_units_excluded_by_rule']}, rows missing {inc['n_rows_missing']}); "
                f"declared exclusions units {decl['units']} trials {decl['trials']}"
            )
        for m, m_res in result["measures"].items():
            h = m_res["headline"]
            kind = m_res["headline_kind"]
            null = m_res["null"]
            var = h["variance"]
            ci_str = (
                f"[{h['rho_ci_low']:.3f}, {h['rho_ci_high']:.3f}]"
                if h["rho_ci_low"] is not None and h["rho_ci_high"] is not None
                else "[None, None]"
            )
            print(
                f"{m}: rho={h['rho']:.3f} ci={ci_str} rho_at_20={h['rho_at_20']:.3f} "
                f"({kind}; r_half={h['r_half']:.3f}, n_units={h['n_units']}, n_pairs={h['n_pairs']}) "
                f"null_p95_rho={null['p95_rho']:.3f} "
                f"between={var['var_between']:.3g} within={var['var_within']:.3g}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
