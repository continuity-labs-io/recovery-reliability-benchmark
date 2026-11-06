"""Within-session reliability ceiling evaluator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from . import contract

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
    cols = [*(f"{m}_{h}" for m in measure_list for h in ("odd", "even")), "n_odd", "n_even"]
    sub = responses[responses["condition"].isin(set(conditions))].copy()
    if sub.empty:
        return pd.DataFrame(
            columns=cols, index=pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
        )

    sub["unit_id"] = sub["unit_id"].astype(str)
    sub["condition"] = sub["condition"].astype(str)
    if active_units is not None:
        active_sets = {str(c): {str(u) for u in us} for c, us in active_units.items()}
        keep = [
            u in active_sets.get(c, set()) for u, c in zip(sub["unit_id"], sub["condition"], strict=False)
        ]
        sub = sub[keep]
        if sub.empty:
            return pd.DataFrame(
                columns=cols, index=pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
            )

    sub = sub.sort_values(["unit_id", "condition", "trial_index"], kind="mergesort")
    position = sub.groupby(["unit_id", "condition"], sort=False).cumcount() + 1
    grp_odd = sub[position % 2 == 1].groupby(["unit_id", "condition"], sort=True)
    grp_even = sub[position % 2 == 0].groupby(["unit_id", "condition"], sort=True)

    n_odd, n_even = grp_odd.size(), grp_even.size()
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
        Dictionary with keys r_half, r_ci_low, r_ci_high, rho, rho_ci_low, rho_ci_high,
        n_eff, n_trials_group, rho_single_trial, rho_at_20, n_pairs, n_units, n_conditions,
        r_undefined, r_nonpositive, odd_trials, and center.

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

    col_odd, col_even = f"{measure}_odd", f"{measure}_even"
    sub = halves.loc[halves[col_odd].notna() & halves[col_even].notna()]
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

    xv, yv = x.to_numpy(dtype=float), y.to_numpy(dtype=float)
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
        dx, dy = xv - xv.mean(), yv - yv.mean()
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
        r_ci_low = r_ci_high = rho_ci_low = rho_ci_high = None
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
    sub = responses.loc[responses["condition"].astype(str) == str(condition)]
    if active_units is not None:
        raw_units = active_units.get(str(condition), ()) if isinstance(active_units, dict) else active_units
        sub = sub.loc[sub["unit_id"].astype(str).isin({str(u) for u in raw_units})]

    g = sub.groupby(sub["unit_id"].astype(str), sort=False)[measure]
    unit_means, unit_vars, unit_counts = g.mean(), g.var(ddof=1), g.count()

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


if __name__ == "__main__":
    from .cli import evaluate_main

    raise SystemExit(evaluate_main())
