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
from .text_report import print_check_human, print_evaluate_human


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
    w, d = float(args.post_stim_window_s), float(args.load_duration_s)
    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": w,
        "load_duration_s": d,
        "extra_forbidden": extra_forbidden,
    }

    try:
        prep = load_preparation(args.preparation) if args.preparation is not None else None
        conds = load_conditions(args.conditions) if args.conditions is not None else None
        if analysis is not None and spikes is not None:
            trials = spikes_mod.trial_table(responses)
            val_table = spikes_mod.per_trial_counts_table(units, trials, spikes, analysis)
            val_measures = ["spike_count"]
        else:
            trials, val_table, val_measures = None, responses, measures
        ef = set(extra_forbidden) if extra_forbidden else None
        result = validate(units, val_table, val_measures, w, d, ef, prep, conds, spikes)
        if analysis is not None and trials is not None:
            checks_spikes.check_pre_stimulus_window(trials, analysis, d)
            result["pre_stim_window_s"] = float(analysis.pre_stim_window_s)
            result["analysis_fingerprint"] = analysis.fingerprint()
    except ContractViolation as exc:
        _emit_report(
            "violation", inputs_meta, arguments_meta, violation=exc.to_dict()
        ) if args.as_json else print(str(exc))
        return 1

    _emit_report(
        result["conformance"], inputs_meta, arguments_meta, result=result
    ) if args.as_json else print_check_human(result)
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
    w, d = float(args.post_stim_window_s), float(args.load_duration_s)
    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": w,
        "load_duration_s": d,
        "n_perm": int(args.n_perm),
        "seed": int(args.seed),
    }

    try:
        prep = load_preparation(args.preparation) if args.preparation is not None else None
        conds = load_conditions(args.conditions) if args.conditions is not None else None
        pos = (units, responses, measures, w, d, args.n_perm)
        result = run(*pos, 0.85, 0.05, args.seed, prep, conds, spikes, analysis)
    except ContractViolation as exc:
        _emit_report(
            "violation", inputs_meta, arguments_meta, violation=exc.to_dict()
        ) if args.as_json else print(str(exc))
        return 1

    if result["status"] == "positive_control_failed":
        _emit_report(result["status"], inputs_meta, arguments_meta, result=result) if args.as_json else print(
            "positive_control_failed"
        )
        return 3
    _emit_report(
        result["status"], inputs_meta, arguments_meta, result=result
    ) if args.as_json else print_evaluate_human(result)
    return 0
