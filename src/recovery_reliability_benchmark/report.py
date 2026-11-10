"""One-command report folder writer and CLI entry point (`rrb-report`)."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .cli import _add_common_arguments, _emit_report, _load_cli_inputs
from .contract import ContractViolation
from .inputs import EvaluationInputs
from .metadata import load_conditions, load_preparation
from .run import run_with_inputs
from .summary import DEFAULT_TITLE, build_summary, build_violation_summary


def _write_halves_figure(
    result: dict[str, Any],
    inputs: EvaluationInputs,
    halves_path: Path,
) -> bool:
    """Render odd-half versus even-half scatter panels; return False if matplotlib is missing."""
    try:
        import matplotlib

        if "matplotlib.pyplot" not in sys.modules:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    if result.get("status") != "ok":
        return True

    measures = list(result["parameters"]["measures"])[:4]
    n_panels = max(len(measures), 1)
    fig, axes = plt.subplots(1, n_panels, figsize=(4.6 * n_panels, 4.2), squeeze=False)

    for idx, measure in enumerate(measures):
        ax = axes[0, idx]
        m_res = result["measures"][measure]
        if m_res.get("status") == "not_scored":
            ax.set_title(f"{measure}: not scored", fontsize=9)
            ax.axis("off")
            continue

        if inputs.scored is not None and measure in inputs.scored:
            scored_m = inputs.scored[measure]
            m_halves = inputs.halves.loc[[str(u) in scored_m[str(c)] for u, c in inputs.halves.index]]
        else:
            m_halves = inputs.halves

        col_odd, col_even = f"{measure}_odd", f"{measure}_even"
        valid = m_halves.loc[m_halves[col_odd].notna() & m_halves[col_even].notna()]
        cond_vals = valid.index.get_level_values("condition").astype(str)
        all_vals: list[np.ndarray] = []
        for cond in inputs.evaluated_conditions:
            sub = valid.loc[cond_vals == str(cond)]
            if sub.empty:
                continue
            odd = sub[col_odd].to_numpy(dtype=float)
            even = sub[col_even].to_numpy(dtype=float)
            ax.scatter(odd, even, label=str(cond), s=24, alpha=0.8)
            all_vals.extend([odd, even])

        if all_vals:
            stacked = np.concatenate(all_vals)
            lo_v, hi_v = float(np.min(stacked)), float(np.max(stacked))
            pad = 0.05 * (hi_v - lo_v) if hi_v > lo_v else 0.5
            lim = (lo_v - pad, hi_v + pad)
            ax.plot(lim, lim, "--", color="0.4", linewidth=1.0)
            ax.set_xlim(lim)
            ax.set_ylim(lim)
            if len(inputs.evaluated_conditions) > 1:
                ax.legend(frameon=False, fontsize=8)

        h = m_res["headline"]
        lo_s = f"{h['rho_ci_low']:.3f}" if h["rho_ci_low"] is not None else "n/a"
        hi_s = f"{h['rho_ci_high']:.3f}" if h["rho_ci_high"] is not None else "n/a"
        ax.set_title(f"{measure}: rho={h['rho']:.3f} [{lo_s}, {hi_s}], n_units={h['n_units']}", fontsize=9)
        ax.set_xlabel(f"{measure} (odd half)")
        ax.set_ylabel(f"{measure} (even half)")

    fig.tight_layout()
    fig.savefig(halves_path, dpi=150)
    plt.close(fig)
    return True


def write_report(
    result: dict[str, Any],
    inputs: EvaluationInputs,
    out_dir: str | Path,
    title: str | None = None,
    command: str = "",
) -> dict[str, Path]:
    """Write ``evaluate.json``, ``summary.md``, and ``halves.png`` into ``out_dir``.

    Args:
        result: Evaluation result dictionary returned by ``run_with_inputs()``.
        inputs: Prepared ``EvaluationInputs`` carrying the split-half DataFrame and inclusion sets.
        out_dir: Destination folder for report artifacts (created if absent).
        title: Report title heading (defaults to ``DEFAULT_TITLE`` when ``None`` or empty).
        command: Command-line invocation string recorded in ``summary.md``.

    Returns:
        Dictionary mapping ``"evaluate"``, ``"summary"``, and (when ``matplotlib`` is
        installed and ``result["status"] == "ok"``) ``"halves"`` to written ``Path`` objects.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    eval_path = out_path / "evaluate.json"
    eval_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    halves_path = out_path / "halves.png"
    has_mpl = _write_halves_figure(result, inputs, halves_path)
    if not has_mpl:
        figure_note: str | None = "Figure skipped: matplotlib not installed"
    elif halves_path.is_file():
        figure_note = "![Split-half scatter](halves.png)"
    else:
        figure_note = None

    summary_path = out_path / "summary.md"
    summary_path.write_text(
        build_summary(result, title=title, command=command, figure_note=figure_note),
        encoding="utf-8",
    )

    paths: dict[str, Path] = {"evaluate": eval_path, "summary": summary_path}
    if halves_path.is_file():
        paths["halves"] = halves_path
    return paths


def main(argv: list[str] | None = None) -> int:
    """Run the one-command report generator CLI (`rrb-report`).

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 1 on contract violation, 2 on input error,
        3 on positive-control failure).
    """
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    command = shlex.join(["rrb-report", *raw_argv])

    parser = argparse.ArgumentParser(
        description="Generate evaluate.json, summary.md, and halves.png from benchmark inputs."
    )
    _add_common_arguments(parser)
    parser.add_argument("--n-perm", type=int, default=1000, help="Permutations for null.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--out", default="report", metavar="DIR", help="Output report directory.")
    parser.add_argument("--title", default=None, help="Report title heading.")
    args = parser.parse_args(argv)
    title = args.title if args.title else DEFAULT_TITLE

    inputs_meta: dict[str, Any] = {}
    arguments_meta: dict[str, Any] = {}
    try:
        units, responses, spikes, analysis, inputs_meta = _load_cli_inputs(args, require_measures=True)
        measures = [m.strip() for m in (args.measures or "").split(",") if m.strip()]
        w, d = float(args.post_stim_window_s), float(args.load_duration_s)
        arguments_meta = {
            "measures": measures,
            "post_stim_window_s": w,
            "load_duration_s": d,
            "n_perm": int(args.n_perm),
            "seed": int(args.seed),
            "out": str(args.out),
            "title": title,
        }
        prep = load_preparation(args.preparation) if args.preparation is not None else None
        conds = load_conditions(args.conditions) if args.conditions is not None else None
        result, eval_inputs = run_with_inputs(
            units,
            responses,
            measures,
            w,
            d,
            args.n_perm,
            0.85,
            0.05,
            args.seed,
            prep,
            conds,
            spikes,
            analysis,
        )
    except ContractViolation as exc:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "summary.md").write_text(
            build_violation_summary(exc, title=title, command=command),
            encoding="utf-8",
        )
        if args.as_json:
            _emit_report("violation", inputs_meta, arguments_meta, violation=exc.to_dict())
        else:
            print(str(exc))
        return 1
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    paths = write_report(result, eval_inputs, args.out, title=title, command=command)
    if result["status"] == "positive_control_failed":
        if args.as_json:
            _emit_report(result["status"], inputs_meta, arguments_meta, result=result)
        else:
            print("positive_control_failed")
        return 3
    if args.as_json:
        _emit_report(result["status"], inputs_meta, arguments_meta, result=result)
    else:
        print(str(paths["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
