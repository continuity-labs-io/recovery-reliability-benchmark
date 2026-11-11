"""Deterministic spike-train simulation checking split-half ceiling against test-retest."""

from __future__ import annotations

import argparse
import json
import math
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .measures import AnalysisParams, unit_measures
from .synthetic import exponential_recovery, make_spike_trains

ROOT = Path(__file__).resolve().parents[2]
POPULATIONS: tuple[str, ...] = ("strong", "weak", "sparse")
N_TRIALS_GRID: tuple[int, ...] = (20, 40)
N_UNITS: int = 30
N_SEEDS: int = 40
RETEST_SEED_OFFSET: int = 10_000
ISI_S: float = 5.0
POST_STIM_WINDOW_S: float = 2.0
MEASURES: tuple[str, ...] = (
    "t_half_excess",
    "excess_per_trial",
    "baseline_hz",
    "t_return",
)

OUT_JSON = ROOT / "docs" / "spikes_path_checks.json"
OUT_MD = ROOT / "docs" / "spikes_path_checks.md"


def build_population(population: str) -> list[Callable[[np.ndarray], np.ndarray]]:
    """Construct the 30 per-unit exponential recovery rate functions for a named population.

    Args:
        population: One of ``"strong"``, ``"weak"``, or ``"sparse"``.

    Returns:
        List of 30 ``rate_fn(latency_s) -> rate_hz`` callables.

    Raises:
        ValueError: If ``population`` is not a recognized population name.
    """
    taus = np.geomspace(0.05, 0.5, N_UNITS)
    if population in ("strong", "weak"):
        baselines = np.geomspace(1.0, 20.0, N_UNITS)
        peak_hz = 100.0 if population == "strong" else 30.0
        return [
            exponential_recovery(
                baseline_hz=float(baselines[(7 * i) % N_UNITS]),
                peak_hz=peak_hz,
                tau_s=float(taus[i]),
            )
            for i in range(N_UNITS)
        ]
    if population == "sparse":
        baselines = np.geomspace(0.2, 5.0, N_UNITS)
        peaks = np.geomspace(5.0, 50.0, N_UNITS)
        return [
            exponential_recovery(
                baseline_hz=float(baselines[(7 * i) % N_UNITS]),
                peak_hz=float(peaks[(11 * i) % N_UNITS]),
                tau_s=float(taus[i]),
            )
            for i in range(N_UNITS)
        ]
    raise ValueError(f"Unknown population '{population}'. Expected one of {POPULATIONS}.")


def pearson_r(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation across paired 1D arrays.

    Args:
        x: First 1D float array of paired values.
        y: Second 1D float array of paired values.

    Returns:
        Pearson correlation coefficient in ``[-1, 1]``, or ``NaN`` if fewer than two
        observations or zero variance in either array.
    """
    if len(x) < 2:
        return float("nan")
    dx = x - np.mean(x)
    dy = y - np.mean(y)
    denom = float(np.sqrt(np.dot(dx, dx) * np.dot(dy, dy)))
    if denom == 0.0:
        return float("nan")
    return float(np.clip(np.dot(dx, dy) / denom, -1.0, 1.0))


def simulate_seed(
    population: str,
    n_trials: int,
    seed: int,
    rate_fns: list[Callable[[np.ndarray], np.ndarray]] | None = None,
) -> dict[str, dict[str, float]]:
    """Simulate one paired test-retest session and compute split-half and retest statistics.

    Args:
        population: Population name (``"strong"``, ``"weak"``, or ``"sparse"``).
        n_trials: Number of stimulus trials per session.
        seed: Base random seed for the first session; second session uses ``10_000 + seed``.
        rate_fns: Optional pre-built rate functions for ``population``.

    Returns:
        Mapping from each measure in ``MEASURES`` to a dictionary with keys
        ``split_half_corrected``, ``test_retest``, ``r_half``, and ``units_scored``.
    """
    fns = rate_fns if rate_fns is not None else build_population(population)
    params = AnalysisParams(post_stim_window_s=POST_STIM_WINDOW_S)

    trains_first, onsets_first = make_spike_trains(fns, n_trials, params, ISI_S, seed=seed)
    trains_second, onsets_second = make_spike_trains(
        fns, n_trials, params, ISI_S, seed=RETEST_SEED_OFFSET + seed
    )
    odd_onsets = onsets_first[0::2]
    even_onsets = onsets_first[1::2]

    full_first: dict[str, np.ndarray] = {m: np.empty(N_UNITS, dtype=float) for m in MEASURES}
    full_second: dict[str, np.ndarray] = {m: np.empty(N_UNITS, dtype=float) for m in MEASURES}
    odd_vals: dict[str, np.ndarray] = {m: np.empty(N_UNITS, dtype=float) for m in MEASURES}
    even_vals: dict[str, np.ndarray] = {m: np.empty(N_UNITS, dtype=float) for m in MEASURES}

    for u in range(N_UNITS):
        vals_first, _ = unit_measures(trains_first[u], onsets_first, params)
        vals_second, _ = unit_measures(trains_second[u], onsets_second, params)
        vals_odd, _ = unit_measures(trains_first[u], odd_onsets, params)
        vals_even, _ = unit_measures(trains_first[u], even_onsets, params)
        for m in MEASURES:
            full_first[m][u] = float(vals_first[m])
            full_second[m][u] = float(vals_second[m])
            odd_vals[m][u] = float(vals_odd[m])
            even_vals[m][u] = float(vals_even[m])

    out: dict[str, dict[str, float]] = {}
    for m in MEASURES:
        valid_full = ~np.isnan(full_first[m]) & ~np.isnan(full_second[m])
        test_retest = pearson_r(full_first[m][valid_full], full_second[m][valid_full])

        valid_half = ~np.isnan(odd_vals[m]) & ~np.isnan(even_vals[m])
        units_scored = float(np.sum(valid_half))
        r_half = pearson_r(odd_vals[m][valid_half], even_vals[m][valid_half])
        split_half_corrected = (
            float(2.0 * r_half / (1.0 + r_half)) if (not math.isnan(r_half) and r_half > 0.0) else 0.0
        )
        out[m] = {
            "split_half_corrected": split_half_corrected,
            "test_retest": test_retest,
            "r_half": r_half,
            "units_scored": units_scored,
        }
    return out


def run_all_checks() -> dict[str, dict[str, dict[str, float]]]:
    """Run all six ``<population>_<n_trials>`` regimes across ``N_SEEDS`` seeds.

    Returns:
        Nested dictionary ``results[case_key][measure]`` with rounded mean statistics
        ``split_half_corrected`` (3 decimals), ``test_retest`` (3 decimals), and
        ``units_scored`` (1 decimal).
    """
    results: dict[str, dict[str, dict[str, float]]] = {}
    for population in POPULATIONS:
        rate_fns = build_population(population)
        for n_trials in N_TRIALS_GRID:
            case_key = f"{population}_{n_trials}"
            per_seed = [
                simulate_seed(population, n_trials, seed=seed, rate_fns=rate_fns) for seed in range(N_SEEDS)
            ]
            case_summary: dict[str, dict[str, float]] = {}
            for m in MEASURES:
                sh = float(np.mean([s[m]["split_half_corrected"] for s in per_seed]))
                tr = float(np.mean([s[m]["test_retest"] for s in per_seed]))
                us = float(np.mean([s[m]["units_scored"] for s in per_seed]))
                case_summary[m] = {
                    "split_half_corrected": round(sh, 3),
                    "test_retest": round(tr, 3),
                    "units_scored": round(us, 1),
                }
            results[case_key] = case_summary
    return results


def render_markdown(results: dict[str, dict[str, dict[str, float]]]) -> str:
    """Render the simulation recipe and per-measure summary tables as Markdown.

    Args:
        results: Nested dictionary produced by ``run_all_checks``.

    Returns:
        Markdown document string.
    """
    case_keys = [f"{pop}_{n}" for pop in POPULATIONS for n in N_TRIALS_GRID]
    lines: list[str] = [
        "# Spikes-Path Simulation Checks",
        "",
        (
            "Comparison of the within-session Spearman-Brown split-half reliability ceiling "
            "on pooled spike-train measures against two-session test-retest correlation across "
            "three synthetic 30-unit inhomogeneous Poisson populations (`i = 0..29`, recovery "
            "time constants `taus = np.geomspace(0.05, 0.5, 30)` s via "
            "`recovery_reliability_benchmark.synthetic.exponential_recovery` and `make_spike_trains`):"
        ),
        "",
        "- **strong**: baseline `np.geomspace(1.0, 20.0, 30)[(7 * i) % 30]` Hz, peak `100` Hz.",
        "- **weak**: same baselines as `strong`, peak `30` Hz.",
        (
            "- **sparse**: baseline `np.geomspace(0.2, 5.0, 30)[(7 * i) % 30]` Hz, "
            "peak `np.geomspace(5.0, 50.0, 30)[(11 * i) % 30]` Hz."
        ),
        "",
        (
            f"For each population, trial count `n_trials` in `(20, 40)`, and `seed` in `0..{N_SEEDS - 1}` "
            f"({N_SEEDS} seeds), with `AnalysisParams(post_stim_window_s=2.0)` and inter-stimulus "
            "interval `5.0` s: two independent sessions of the same units are simulated with `seed` "
            "and `10_000 + seed`. `unit_measures` is evaluated over all trial onsets of each session "
            "(`test_retest` = Pearson `r` across units non-NaN in both sessions) and over the first "
            "session's odd (`onsets[0::2]`) and even (`onsets[1::2]`) trial onsets (`r_half` = Pearson `r` "
            "across units non-NaN in both halves; `split_half_corrected = 2 * r_half / (1 + r_half)` "
            "if `r_half > 0` else `0`; `units_scored` = count of units non-NaN in both halves). "
            "Tables report the mean across the 40 seeds, generated by "
            "`python -m recovery_reliability_benchmark.spikes_path_checks`."
        ),
    ]

    for m in MEASURES:
        lines.extend(
            [
                "",
                f"## `{m}`",
                "",
                "| case | split_half_corrected | test_retest | units_scored |",
                "|---|---:|---:|---:|",
            ]
        )
        for case_key in case_keys:
            cell = results[case_key][m]
            lines.append(
                f"| {case_key} | {cell['split_half_corrected']:.3f} "
                f"| {cell['test_retest']:.3f} | {cell['units_scored']:.1f} |"
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


def main(argv: list[str] | None = None) -> int:
    """Run the deterministic spikes-path simulation and write JSON and Markdown outputs.

    Args:
        argv: Optional CLI argument list (must be empty; no arguments are accepted).

    Returns:
        Exit status code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        description="Run deterministic spikes-path simulation checks and write docs outputs."
    )
    parser.parse_args(argv)

    t0 = time.perf_counter()
    results = run_all_checks()
    elapsed_s = time.perf_counter() - t0

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    OUT_MD.write_text(render_markdown(results), encoding="utf-8")
    print(f"Wrote {OUT_JSON.relative_to(ROOT)} and {OUT_MD.relative_to(ROOT)} in {elapsed_s:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
