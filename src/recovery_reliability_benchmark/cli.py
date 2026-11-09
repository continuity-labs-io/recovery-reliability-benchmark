"""Command-line interfaces for conformance checking and reliability evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from .contract import (
    SPEC_VERSION,
    ContractViolation,
    _validate_durations,
    read_spikes,
    read_tables,
    validate,
)
from .metadata import load_conditions, load_preparation
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
    parser.add_argument("--measures", required=True, help="Comma-separated measure column names.")
    parser.add_argument(
        "--post-stim-window-s", required=True, type=float, help="Post-stimulus window in seconds."
    )
    parser.add_argument(
        "--load-duration-s", type=float, default=0.0, help="Conditioning load duration in seconds."
    )
    parser.add_argument("--preparation", default=None, help="Path to preparation.json metadata sidecar.")
    parser.add_argument("--conditions", default=None, help="Path to conditions.json metadata sidecar.")
    parser.add_argument("--spikes", default=None, help="Path to spikes.csv table.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")


def _load_cli_inputs(
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame | None, dict[str, Any]]:
    _validate_durations(args.post_stim_window_s, args.load_duration_s)
    units, responses = read_tables(args.units_csv, args.responses_csv)
    spikes = read_spikes(args.spikes) if args.spikes is not None else None
    for opt_path in (args.preparation, args.conditions):
        if opt_path is not None and not Path(opt_path).is_file():
            raise FileNotFoundError(opt_path)

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
    return units, responses, spikes, inputs_meta


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
    }
    if violation is not None:
        doc["violation"] = violation
    if result is not None:
        doc["result"] = result
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


def check_main(argv: list[str] | None = None) -> int:
    """Run the contract validator CLI and print the conformance report.

    This report is what a lab shares; the data stays on their machine.

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 on conformance, 1 on contract violation, 2 on input error).
    """
    parser = argparse.ArgumentParser(
        description="Validate units and responses CSV tables against the benchmark data contract."
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--extra-forbidden", default="", help="Comma-separated extra forbidden measure names."
    )
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]
    extra_forbidden = [m.strip() for m in args.extra_forbidden.split(",") if m.strip()]

    try:
        units, responses, spikes, inputs_meta = _load_cli_inputs(args)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "extra_forbidden": extra_forbidden,
    }

    try:
        preparation = load_preparation(args.preparation) if args.preparation is not None else None
        conditions = load_conditions(args.conditions) if args.conditions is not None else None
        result = validate(
            units,
            responses,
            measures=measures,
            post_stim_window_s=args.post_stim_window_s,
            load_duration_s=args.load_duration_s,
            extra_forbidden=set(extra_forbidden) if extra_forbidden else None,
            preparation=preparation,
            conditions=conditions,
            spikes=spikes,
        )
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

        print(f"{result['conformance']} (SPEC v{result['spec_version']})")
        print(f"package_version: {__version__}")
        for key, value in result.items():
            if key == "conditions":
                continue
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
    parser = argparse.ArgumentParser(
        description="Compute within-session reliability ceilings on conforming units and responses CSV tables."
    )
    _add_common_arguments(parser)
    parser.add_argument(
        "--n-perm", type=int, default=1000, help="Permutations for the label-permutation null."
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]

    try:
        units, responses, spikes, inputs_meta = _load_cli_inputs(args)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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
            _emit_report("violation", inputs_meta, arguments_meta, violation=exc.to_dict())
        else:
            print(str(exc))
        return 1

    if result["status"] == "positive_control_failed":
        if args.as_json:
            _emit_report(result["status"], inputs_meta, arguments_meta, result=result)
        else:
            print("positive_control_failed")
        return 3

    if args.as_json:
        _emit_report(result["status"], inputs_meta, arguments_meta, result=result)
    else:
        print(f"package_version: {result['package_version']} (SPEC v{result['spec_version']})")
        print("census:")
        for key, value in result["census"].items():
            print(f"  {key}: {value}")
        _print_inclusion_lines(result["inclusion"], result["census"]["evaluated_conditions"])
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
