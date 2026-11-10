"""Command-line interfaces for conformance checking and reliability evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from . import checks_spikes
from . import spikes as spikes_mod
from .contract import SPEC_VERSION, ContractViolation, _validate_durations, read_spikes, read_tables, validate
from .measures import AnalysisParams
from .metadata import load_analysis, load_conditions, load_preparation
from .run import run


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's contents.

    Args:
        path: Path to the file to hash.

    Returns:
        Lowercase 64-character hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("units_csv", help="Path to units CSV file.")
    parser.add_argument("responses_csv", help="Path to responses CSV file.")
    parser.add_argument("--measures", default=None, help="Comma-separated measure column names.")
    parser.add_argument("--post-stim-window-s", default=None, type=float, help="Post-stimulus window (s).")
    parser.add_argument("--load-duration-s", default=None, type=float, help="Load duration (s).")
    parser.add_argument("--preparation", default=None, help="Path to preparation.json metadata sidecar.")
    parser.add_argument("--conditions", default=None, help="Path to conditions.json metadata sidecar.")
    parser.add_argument("--spikes", default=None, help="Path to spikes.csv table.")
    parser.add_argument("--analysis", default=None, help="Path to analysis.json parameters sidecar.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")


def _load_cli_inputs(
    args: argparse.Namespace, *, require_measures: bool = True
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, AnalysisParams | None, dict[str, Any]]:
    if args.analysis is not None and args.spikes is None:
        raise ValueError("--analysis requires --spikes")
    if (require_measures or args.analysis is None) and not args.measures:
        raise ValueError("--measures is required")
    for opt_path in (args.preparation, args.conditions, args.analysis):
        if opt_path is not None and not Path(opt_path).is_file():
            raise FileNotFoundError(opt_path)

    analysis = load_analysis(args.analysis) if args.analysis is not None else None
    if analysis is not None:
        w, d = args.post_stim_window_s, args.load_duration_s
        if w is not None and (_validate_durations(w, 0.0) or float(w) != float(analysis.post_stim_window_s)):
            raise ValueError(f"--post-stim-window-s ({w}) != {analysis.post_stim_window_s}")
        if d is not None and (_validate_durations(1.0, d) or float(d) != float(analysis.load_duration_s)):
            raise ValueError(f"--load-duration-s ({d}) != {analysis.load_duration_s}")
        args.post_stim_window_s = float(analysis.post_stim_window_s)
        args.load_duration_s = float(analysis.load_duration_s)
    else:
        if args.post_stim_window_s is None:
            raise ValueError("--post-stim-window-s is required")
        args.load_duration_s = 0.0 if args.load_duration_s is None else float(args.load_duration_s)
        _validate_durations(args.post_stim_window_s, args.load_duration_s)

    units, responses = read_tables(args.units_csv, args.responses_csv)
    spikes = read_spikes(args.spikes) if args.spikes is not None else None
    inputs_meta: dict[str, Any] = {
        "units": {"path": args.units_csv, "sha256": file_sha256(args.units_csv)},
        "responses": {"path": args.responses_csv, "sha256": file_sha256(args.responses_csv)},
        **{
            k: {"path": getattr(args, k), "sha256": file_sha256(getattr(args, k))}
            for k in ("preparation", "conditions", "spikes", "analysis")
            if getattr(args, k) is not None
        },
    }
    return units, responses, spikes, analysis, inputs_meta


def _emit_report(
    status: str,
    inputs_meta: dict[str, Any],
    arguments_meta: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
    violation: dict[str, Any] | None = None,
) -> None:
    from . import __version__

    doc: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "package_version": __version__,
        "status": status,
        "inputs": inputs_meta,
        "arguments": arguments_meta,
        **({"violation": violation} if violation is not None else {}),
        **({"result": result} if result is not None else {}),
    }
    print(json.dumps(doc, indent=2, sort_keys=True))


def _print_inclusion_lines(inclusion: dict[str, Any], evaluated_conditions: list[str]) -> None:
    decl = inclusion["declared"]
    for cond in evaluated_conditions:
        inc = inclusion["per_condition"][cond]
        print(
            f"{cond}: units included {inc['n_units_included']} of {inc['n_units_in_tables']} "
            f"(excluded by rule {inc['n_units_excluded_by_rule']}, rows missing {inc['n_rows_missing']}); "
            f"declared exclusions units {decl['units']} trials {decl['trials']}"
        )


def _print_evaluate_human(result: dict[str, Any]) -> None:
    print(f"package_version: {result['package_version']} (SPEC v{result['spec_version']})")
    params = result["parameters"]
    if params.get("path") == "spikes":
        print(f"path: spikes, analysis {params['analysis_fingerprint'][:12]}")
    print("census:")
    for key, value in result["census"].items():
        print(f"  {key}: {value}")
    eval_conds = result["census"]["evaluated_conditions"]
    _print_inclusion_lines(result["inclusion"], eval_conds)
    if "spikes_path" in result["inclusion"]:
        sp_inc = result["inclusion"]["spikes_path"]
        for m in result["measures"]:
            for cond in eval_conds:
                c_inc = sp_inc.get("per_measure", sp_inc)[m][cond]
                print(f"{cond} ({m}): units scored {c_inc['n_units_scored']} of {c_inc['n_units_in_tables']}")
    for m, m_res in result["measures"].items():
        if m_res.get("status") == "not_scored":
            print(f"{m}: not_scored")
            continue
        h, kind, null = m_res["headline"], m_res["headline_kind"], m_res["null"]
        var, lo, hi = h["variance"], h["rho_ci_low"], h["rho_ci_high"]
        ci_str = f"[{lo:.3f}, {hi:.3f}]" if lo is not None and hi is not None else "[None, None]"
        line = (
            f"{m}: rho={h['rho']:.3f} ci={ci_str} rho_at_20={h['rho_at_20']:.3f} "
            f"({kind}; r_half={h['r_half']:.3f}, n_units={h['n_units']}, n_pairs={h['n_pairs']}) "
            f"null_p95_rho={null['p95_rho']:.3f}"
        )
        if var is not None:
            line += f" between={var['var_between']:.3g} within={var['var_within']:.3g}"
        print(line)
        n_censored = sum(cf.get(f"{m}_censored", 0) for cf in m_res.get("flags", {}).values())
        if n_censored > 0:
            print(f"  {m} censored in {n_censored} units")


def check_main(argv: list[str] | None = None) -> int:
    """Run the contract validator CLI and print the conformance report.

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on conformance, 1 on contract violation, 2 on input error).
    """
    parser = argparse.ArgumentParser(description="Validate units and responses CSV tables.")
    _add_common_arguments(parser)
    parser.add_argument("--extra-forbidden", default="", help="Extra forbidden measure names.")
    args = parser.parse_args(argv)

    try:
        units, responses, spikes, analysis, inputs_meta = _load_cli_inputs(args, require_measures=False)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    measures = [m.strip() for m in (args.measures or "").split(",") if m.strip()]
    extra_forbidden = [m.strip() for m in args.extra_forbidden.split(",") if m.strip()]
    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "extra_forbidden": extra_forbidden,
    }

    try:
        prep = load_preparation(args.preparation) if args.preparation is not None else None
        conds = load_conditions(args.conditions) if args.conditions is not None else None
        if analysis is not None:
            assert spikes is not None
            trials = spikes_mod.trial_table(responses)
            val_table = spikes_mod.per_trial_counts_table(units, trials, spikes, analysis)
            val_measures = ["spike_count"]
        else:
            trials, val_table, val_measures = None, responses, measures
        ef = set(extra_forbidden) if extra_forbidden else None
        result = validate(
            units,
            val_table,
            val_measures,
            args.post_stim_window_s,
            args.load_duration_s,
            ef,
            prep,
            conds,
            spikes,
        )
        if analysis is not None and trials is not None:
            checks_spikes.check_pre_stimulus_window(trials, analysis, args.load_duration_s)
            result["pre_stim_window_s"] = float(analysis.pre_stim_window_s)
            result["analysis_fingerprint"] = analysis.fingerprint()
    except ContractViolation as exc:
        if args.as_json:
            _emit_report("violation", inputs_meta, arguments_meta, violation=exc.to_dict())
        else:
            print(str(exc))
        return 1

    if args.as_json:
        _emit_report(result["conformance"], inputs_meta, arguments_meta, result=result)
    else:
        from . import __version__

        print(f"{result['conformance']} (SPEC v{result['spec_version']})\npackage_version: {__version__}")
        for key, value in result.items():
            if key != "conditions":
                print(f"{key}: {value}")
        print("conditions:")
        for name, info in result["conditions"].items():
            sf = info["should_failed"] or "none"
            print(
                f"  {name}: n_trials={info['n_trials']} n_units_active={info['n_units_active']} should_failed={sf}"
            )
        _print_inclusion_lines(result["inclusion"], result["evaluated_conditions"])
    return 0


def evaluate_main(argv: list[str] | None = None) -> int:
    """Run the within-session reliability ceiling CLI.

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on success, 1 on contract violation, 2 on input error,
        3 on positive-control failure).
    """
    parser = argparse.ArgumentParser(description="Compute within-session reliability ceilings.")
    _add_common_arguments(parser)
    parser.add_argument("--n-perm", type=int, default=1000, help="Permutations for null.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args(argv)

    try:
        units, responses, spikes, analysis, inputs_meta = _load_cli_inputs(args, require_measures=True)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    measures = [m.strip() for m in (args.measures or "").split(",") if m.strip()]
    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "n_perm": int(args.n_perm),
        "seed": int(args.seed),
    }

    try:
        prep = load_preparation(args.preparation) if args.preparation is not None else None
        conds = load_conditions(args.conditions) if args.conditions is not None else None
        result = run(
            units,
            responses,
            measures,
            args.post_stim_window_s,
            args.load_duration_s,
            args.n_perm,
            seed=args.seed,
            preparation=prep,
            conditions=conds,
            spikes=spikes,
            analysis=analysis,
        )
    except ContractViolation as exc:
        if args.as_json:
            _emit_report("violation", inputs_meta, arguments_meta, violation=exc.to_dict())
        else:
            print(str(exc))
        return 1

    if result["status"] == "positive_control_failed":
        _emit_report(result["status"], inputs_meta, arguments_meta, result=result) if args.as_json else print(
            "positive_control_failed"
        )
        return 3
    _emit_report(
        result["status"], inputs_meta, arguments_meta, result=result
    ) if args.as_json else _print_evaluate_human(result)
    return 0
