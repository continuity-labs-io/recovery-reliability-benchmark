"""Within-session reliability ceiling evaluator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from . import __version__
from .contract import (
    SPEC_VERSION,
    ContractViolation,
    file_sha256,
    read_tables,
    validate,
)
from .synthetic import make_tables


def split_halves(
    responses: pd.DataFrame,
    measures: Sequence[str],
    conditions: Sequence[str],
) -> pd.DataFrame:
    """Partition trials into odd/even halves ranked within each (unit_id, condition) group.

    Within each ``(unit_id, condition)`` group, trials are sorted by ``trial_index``
    and assigned rank ``k = 0, 1, 2, ...``; even ``k`` go to half A and odd ``k``
    go to half B. Groups where either half is empty are dropped.
    """
    measure_list = list(measures)
    cond_set = set(conditions)
    sub = responses[responses["condition"].isin(cond_set)].copy()
    if sub.empty:
        empty_index = pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
        cols = [*(f"{m}_{h}" for m in measure_list for h in ("A", "B")), "n_A", "n_B"]
        return pd.DataFrame(columns=cols, index=empty_index)

    sub["unit_id"] = sub["unit_id"].astype(str)
    sub["condition"] = sub["condition"].astype(str)
    sub = sub.sort_values(["unit_id", "condition", "trial_index"], kind="mergesort")

    rank = sub.groupby(["unit_id", "condition"], sort=False).cumcount()
    half_a = sub[rank % 2 == 0]
    half_b = sub[rank % 2 == 1]

    grp_a = half_a.groupby(["unit_id", "condition"], sort=True)
    grp_b = half_b.groupby(["unit_id", "condition"], sort=True)

    n_a = grp_a.size()
    n_b = grp_b.size()
    common_idx = n_a.index.intersection(n_b.index)
    common_idx.names = ["unit_id", "condition"]

    means_a = grp_a[measure_list].mean().reindex(common_idx)
    means_b = grp_b[measure_list].mean().reindex(common_idx)

    out_cols: dict[str, Any] = {}
    for m in measure_list:
        out_cols[f"{m}_A"] = means_a[m].astype(float)
        out_cols[f"{m}_B"] = means_b[m].astype(float)
    out_cols["n_A"] = n_a.reindex(common_idx).astype(int)
    out_cols["n_B"] = n_b.reindex(common_idx).astype(int)

    return pd.DataFrame(out_cols, index=common_idx)


def ceiling(
    halves: pd.DataFrame,
    measure: str,
    center: bool = False,
) -> dict[str, Any]:
    """Compute the split-half Pearson correlation and Spearman-Brown reliability ceiling."""
    col_a = f"{measure}_A"
    col_b = f"{measure}_B"
    valid_mask = halves[col_a].notna() & halves[col_b].notna()
    sub = halves.loc[valid_mask]

    x = sub[col_a].astype(float)
    y = sub[col_b].astype(float)

    unit_level = "unit_id" if "unit_id" in sub.index.names else 0
    cond_level = "condition" if "condition" in sub.index.names else 1

    n_pairs = int(len(sub))
    n_units = int(sub.index.get_level_values(unit_level).nunique()) if n_pairs > 0 else 0
    n_conditions = int(sub.index.get_level_values(cond_level).nunique()) if n_pairs > 0 else 0
    if "n_A" in sub.columns and "n_B" in sub.columns and n_pairs > 0:
        odd_trials = bool((sub["n_A"] != sub["n_B"]).any())
    else:
        odd_trials = False

    if center and n_pairs > 0:
        x = x - x.groupby(level=cond_level).transform("mean")
        y = y - y.groupby(level=cond_level).transform("mean")

    xv = x.to_numpy(dtype=float)
    yv = y.to_numpy(dtype=float)
    if (
        n_pairs < 3
        or np.allclose(xv, xv[0], rtol=0.0, atol=1e-15)
        or np.allclose(yv, yv[0], rtol=0.0, atol=1e-15)
    ):
        r = float("nan")
    else:
        dx = xv - xv.mean()
        dy = yv - yv.mean()
        denom = float(np.sqrt(np.dot(dx, dx) * np.dot(dy, dy)))
        if denom == 0.0:
            r = float("nan")
        else:
            r = float(np.clip(np.dot(dx, dy) / denom, -1.0, 1.0))

    rho = float(2.0 * r / (1.0 + r)) if r > 0 else 0.0
    return {
        "r_half": r,
        "rho": rho,
        "n_pairs": n_pairs,
        "n_units": n_units,
        "n_conditions": n_conditions,
        "r_nonpositive": bool(not r > 0),
        "odd_trials": odd_trials,
        "center": bool(center),
    }


def permutation_null(
    halves: pd.DataFrame,
    measure: str,
    center: bool,
    n_perm: int,
    rng: np.random.Generator,
) -> dict[str, Any]:
    """Compute the label-permutation null distribution by shuffling half B within conditions."""
    if not isinstance(rng, np.random.Generator):
        rng = np.random.default_rng(rng)

    observed = ceiling(halves, measure, center)["rho"]
    b_cols = [c for c in halves.columns if c.endswith("_B")]
    b_arrays = {col: halves[col].to_numpy(copy=True) for col in b_cols}

    cond_level = "condition" if "condition" in halves.index.names else 1
    cond_vals = halves.index.get_level_values(cond_level)
    cond_groups = [np.flatnonzero(cond_vals == c) for c in cond_vals.unique()]

    permuted = halves.copy()
    perm_idx = np.empty(len(halves), dtype=int)
    rhos = np.empty(n_perm, dtype=float)
    rs = np.empty(n_perm, dtype=float)

    for i in range(n_perm):
        for grp in cond_groups:
            perm_idx[grp] = rng.permutation(grp)
        for col, arr in b_arrays.items():
            permuted[col] = arr[perm_idx]
        res = ceiling(permuted, measure, center)
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
    """Run the synthetic positive control through validate, split_halves, and ceiling."""
    units, responses = make_tables(
        n_units=n_units,
        n_trials=n_trials,
        reliability=reliability,
        seed=seed,
    )
    val = validate(units, responses, measures=["tau"], post_stim_window_s=2.0)
    halves = split_halves(responses, measures=["tau"], conditions=val["evaluated_conditions"])
    ceil = ceiling(halves, "tau", center=False)
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
    """Extract the independence-accounting census from validate()'s return dict."""
    return {
        "preparations": int(validate_result["n_preparations"]),
        "sessions": int(validate_result["n_sessions"]),
        "recordings": int(validate_result["n_recordings"]),
        "units": int(validate_result["n_units"]),
        "units_active": int(validate_result["n_units_active"]),
        "conditions": int(validate_result["n_conditions"]),
        "evaluated_conditions": list(validate_result["evaluated_conditions"]),
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
) -> dict[str, Any]:
    """Validate inputs, run the positive control, and compute within-session ceilings."""
    measure_list = list(measures)
    val = validate(
        units,
        responses,
        measures=measure_list,
        post_stim_window_s=post_stim_window_s,
        load_duration_s=load_duration_s,
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
            "parameters": parameters,
        }

    evaluated_conditions = val["evaluated_conditions"]
    best_condition = val["best_condition"]
    halves = split_halves(responses, measure_list, evaluated_conditions)
    cond_level = halves.index.get_level_values("condition")

    measures_out: dict[str, Any] = {}
    for m in measure_list:
        per_cond = {
            c: ceiling(halves[cond_level == c], m, False)
            for c in evaluated_conditions
        }
        pooled = {
            "uncentered": ceiling(halves, m, False),
            "centered": ceiling(halves, m, True),
        }
        if len(evaluated_conditions) >= 2:
            headline = pooled["centered"]
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

    return {
        "status": "ok",
        "spec_version": SPEC_VERSION,
        "package_version": __version__,
        "parameters": parameters,
        "census": census_dict,
        "positive_control": pc,
        "measures": measures_out,
    }


def main(argv: list[str] | None = None) -> int:
    """Run the within-session reliability ceiling CLI."""
    parser = argparse.ArgumentParser(
        description="Compute within-session reliability ceilings on conforming units and responses CSV tables."
    )
    parser.add_argument("units_csv", help="Path to units CSV file.")
    parser.add_argument("responses_csv", help="Path to responses CSV file.")
    parser.add_argument("--measures", required=True, help="Comma-separated measure column names.")
    parser.add_argument("--post-stim-window-s", required=True, type=float, help="Post-stimulus window in seconds.")
    parser.add_argument("--load-duration-s", type=float, default=0.0, help="Conditioning load duration in seconds.")
    parser.add_argument("--n-perm", type=int, default=1000, help="Permutations for the label-permutation null.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]

    try:
        units, responses = read_tables(args.units_csv, args.responses_csv)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inputs_meta = {
        "units": {"path": args.units_csv, "sha256": file_sha256(args.units_csv)},
        "responses": {"path": args.responses_csv, "sha256": file_sha256(args.responses_csv)},
    }
    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "n_perm": int(args.n_perm),
        "seed": int(args.seed),
    }

    try:
        result = run(
            units,
            responses,
            measures=measures,
            post_stim_window_s=args.post_stim_window_s,
            load_duration_s=args.load_duration_s,
            n_perm=args.n_perm,
            seed=args.seed,
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
        for m, m_res in result["measures"].items():
            h = m_res["headline"]
            kind = m_res["headline_kind"]
            null = m_res["null"]
            print(
                f"{m}: rho={h['rho']:.3f} "
                f"({kind}; r_half={h['r_half']:.3f}, n_units={h['n_units']}, n_pairs={h['n_pairs']}) "
                f"null_p95_rho={null['p95_rho']:.3f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
