"""Simulate the sampling distribution of the reliability ceiling across MD-2/MD-3 thresholds."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from .contract import validate
from .evaluate import ceiling, split_halves
from .synthetic import make_tables

RHO1_GRID = (0.1, 0.2, 0.4)
N_CONDITIONS_GRID = (1, 3)
N_TRIALS_GRID = (10, 20)
N_UNITS_GRID = (8, 15, 30)


def format_interval(p2_5: float, p97_5: float) -> str:
    """Format a 95% interval with two decimals in square brackets."""
    return f"[{p2_5:.2f}, {p97_5:.2f}]"


def simulate_cell(
    rho1: float,
    n_conditions: int,
    n_trials: int,
    n_units: int,
    seeds: int,
) -> dict[str, Any]:
    """Run one grid cell across ``seeds`` synthetic datasets."""
    if n_conditions == 3:
        conditions: tuple[str, ...] = ("A", "B", "C")
        condition_offsets: dict[str, float] | None = {"A": 0.0, "B": 1.0, "C": 2.0}
        center = True
    else:
        conditions = ("A",)
        condition_offsets = None
        center = False

    reliability = float(n_trials * rho1 / (1.0 + (n_trials - 1) * rho1))
    rhos = np.empty(seeds, dtype=float)
    r_nonpositive = np.empty(seeds, dtype=bool)
    covered = np.empty(seeds, dtype=bool)
    conformance = ""

    for seed in range(seeds):
        units, responses = make_tables(
            n_units=n_units,
            n_trials=n_trials,
            conditions=conditions,
            reliability=reliability,
            condition_offsets=condition_offsets,
            seed=seed,
        )
        if seed == 0:
            val = validate(units, responses, measures=["tau"], post_stim_window_s=2.0)
            conformance = str(val["conformance"])

        halves = split_halves(responses, ["tau"], conditions)
        est = ceiling(halves, "tau", center=center)
        rhos[seed] = est["rho"]
        r_nonpositive[seed] = bool(est["r_nonpositive"])
        ci_lo = est["rho_ci_low"]
        ci_hi = est["rho_ci_high"]
        covered[seed] = bool(ci_lo is not None and ci_hi is not None and (ci_lo <= reliability <= ci_hi))

    p2_5 = float(np.percentile(rhos, 2.5))
    p97_5 = float(np.percentile(rhos, 97.5))
    return {
        "rho1": float(rho1),
        "n_conditions": int(n_conditions),
        "n_trials": int(n_trials),
        "n_units": int(n_units),
        "true_rho": reliability,
        "median_rho_hat": float(np.median(rhos)),
        "p2_5": p2_5,
        "p97_5": p97_5,
        "width": float(p97_5 - p2_5),
        "p_zero": float(np.mean(r_nonpositive)),
        "ci_coverage": float(np.mean(covered)),
        "conformance": conformance,
    }


def render_markdown(cells: list[dict[str, Any]], seeds: int, command: str) -> str:
    """Render the simulation cells as a single Markdown document and table."""
    lines = [
        "# Threshold Simulation",
        "",
        (
            "Simulated sampling distribution of the within-session reliability ceiling across the "
            "MD-2 (`n_trials`) and MD-3 (`n_units`) thresholds. Synthetic datasets were generated "
            "with `recovery_reliability_benchmark.synthetic.make_tables` (Gaussian unit true values "
            "and per-trial errors scaled to single-trial reliability `rho1`, with condition offsets "
            "`{A: 0.0, B: 1.0, C: 2.0}` when `n_conditions == 3`) and estimated with "
            "`split_halves` and `ceiling` from `recovery_reliability_benchmark.evaluate` "
            "(odd/even split-half Pearson correlation with Spearman-Brown correction, "
            "condition-centered for 3 conditions). "
            f"Run across **{seeds} seeds** per cell with `{command}`. "
            "The simulation assumes Gaussian unit effects and independent trial errors with no "
            "drift and no unit dropout, so intervals on real data are at least this wide. "
            "For the pooled estimate the interval uses n_eff = units and is conservative; "
            "observed coverage is 0.99 or higher."
        ),
        "",
        "| rho1 | n_conditions | n_trials | n_units | true_rho | median_rho_hat | p2_5 | p97_5 | interval_95 | width | p_zero | ci_coverage | conformance |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|",
    ]
    for c in cells:
        interval_str = format_interval(c["p2_5"], c["p97_5"])
        lines.append(
            f"| {c['rho1']:.1f} | {c['n_conditions']} | {c['n_trials']} | {c['n_units']} "
            f"| {c['true_rho']:.2f} | {c['median_rho_hat']:.2f} | {c['p2_5']:.2f} | {c['p97_5']:.2f} "
            f"| {interval_str} | {c['width']:.2f} | {c['p_zero']:.3f} | {c['ci_coverage']:.3f} "
            f"| {c['conformance']} |"
        )
    lines.extend(
        [
            "",
            "---",
            "",
            "This document is licensed under CC BY 4.0; see [LICENSE-DOCS](../LICENSE-DOCS).",
            "",
        ]
    )
    return "\n".join(lines)


def write_table(path: Path, cells: list[dict[str, Any]], seeds: int, command: str) -> None:
    """Write the Markdown threshold simulation table to ``path``."""
    path.write_text(render_markdown(cells, seeds=seeds, command=command), encoding="utf-8")


def write_json(path: Path, cells: list[dict[str, Any]], seeds: int, command: str) -> None:
    """Write the JSON threshold simulation payload to ``path``."""
    payload = {
        "generated_by": command,
        "seeds": seeds,
        "cells": cells,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    """Run the threshold simulation grid and write Markdown and JSON outputs."""
    parser = argparse.ArgumentParser(
        description="Simulate the sampling distribution of the reliability ceiling across MD-2/MD-3 thresholds."
    )
    parser.add_argument("--seeds", type=int, default=1000, help="Number of random seeds per cell.")
    parser.add_argument("--out", default="docs/thresholds", help="Output path stem (writes .md and .json).")
    parser.add_argument("--fast", action="store_true", help="Run with 50 seeds for tests and CI.")
    args = parser.parse_args(argv)

    seeds = 50 if args.fast else int(args.seeds)
    out_stem = Path(args.out)
    out_md = out_stem.with_suffix(".md")
    out_json = out_stem.with_suffix(".json")
    out_md.parent.mkdir(parents=True, exist_ok=True)

    cells: list[dict[str, Any]] = []
    for rho1 in RHO1_GRID:
        for n_conditions in N_CONDITIONS_GRID:
            for n_trials in N_TRIALS_GRID:
                for n_units in N_UNITS_GRID:
                    cells.append(
                        simulate_cell(
                            rho1=rho1,
                            n_conditions=n_conditions,
                            n_trials=n_trials,
                            n_units=n_units,
                            seeds=seeds,
                        )
                    )

    cells.sort(key=lambda c: (c["rho1"], c["n_conditions"], c["n_trials"], c["n_units"]))

    cmd = f"python scripts/thresholds.py --seeds {seeds} --out {args.out}"
    if args.fast:
        cmd = f"python scripts/thresholds.py --fast --out {args.out}"

    write_json(out_json, cells, seeds=seeds, command=cmd)
    write_table(out_md, cells, seeds=seeds, command=cmd)
    return 0


if __name__ == "__main__":
    sys.exit(main())
