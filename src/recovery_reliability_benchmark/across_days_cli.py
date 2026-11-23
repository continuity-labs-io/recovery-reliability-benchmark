"""Command-line interface for across-day comparison (`rrb-across-days`)."""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from . import controls
from .across_days import _validate_measure_name, across_day_comparison, load_day
from .cli import file_sha256
from .contract import SPEC_VERSION, ContractViolation
from .strict_json import dumps_strict

_REQUIRED_DAY_FILES: tuple[tuple[str, str], ...] = (
    ("units", "units.csv"),
    ("trials", "trials_responses.csv"),
    ("spikes", "spikes.csv"),
    ("analysis", "analysis.json"),
)
_OPTIONAL_DAY_FILES: tuple[tuple[str, str], ...] = (
    ("preparation", "preparation.json"),
    ("conditions", "conditions.json"),
)


def _inspect_day_files(directory: str | Path) -> dict[str, dict[str, str]]:
    """Verify required files exist in ``directory`` and hash all dataset files present."""
    base = Path(directory)
    if not base.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {base}")
    meta: dict[str, dict[str, str]] = {}
    for key, filename in _REQUIRED_DAY_FILES:
        fpath = base / filename
        if not fpath.is_file():
            raise FileNotFoundError(fpath)
        meta[key] = {"path": str(fpath), "sha256": file_sha256(fpath)}
    for key, filename in _OPTIONAL_DAY_FILES:
        fpath = base / filename
        if fpath.is_file():
            meta[key] = {"path": str(fpath), "sha256": file_sha256(fpath)}
    return meta


def _emit_across_days_json(
    status: str,
    inputs_meta: dict[str, Any],
    arguments_meta: dict[str, Any],
    *,
    result: dict[str, Any] | None = None,
    violation: dict[str, Any] | None = None,
    day: str | None = None,
) -> None:
    """Serialize and print the strict JSON envelope for ``rrb-across-days``."""
    from . import __version__

    doc: dict[str, Any] = {
        "spec_version": SPEC_VERSION,
        "package_version": __version__,
        "status": status,
        "inputs": inputs_meta,
        "arguments": arguments_meta,
        **({"day": day} if day is not None else {}),
        **({"violation": violation} if violation is not None else {}),
        **({"result": result} if result is not None else {}),
    }
    print(dumps_strict(doc, indent=2, sort_keys=True))


def _print_across_days_human(result: dict[str, Any]) -> None:
    """Print an across-day comparison dictionary as human-readable lines."""
    from . import __version__

    print(f"package_version: {__version__} (SPEC v{SPEC_VERSION})")
    sids = result["session_ids"]
    print(
        f"preparation: {result['preparation_id']} (sessions: first={sids['first']}, second={sids['second']})"
    )
    print(f"path: spikes, analysis {result['analysis_fingerprint'][:12]}")
    conds_str = ", ".join(result["conditions"])
    print(f"kind: {result['kind']} (conditions: {conds_str})")
    print(
        f"units: first={result['n_units_first']} second={result['n_units_second']} "
        f"matched={result['n_units_matched']}"
    )

    r_str = "undefined" if result["r_undefined"] else f"{result['r_across_days']:.3f}"
    lo, hi = result["r_ci_low"], result["r_ci_high"]
    ci_str = f"[{lo:.3f}, {hi:.3f}]" if lo is not None and hi is not None else "[None, None]"
    p95 = result["null"]["p95_r"]
    p95_str = f"{p95:.3f}" if (p95 is not None and math.isfinite(p95)) else "None"
    print(
        f"{result['measure']}: r_across_days={r_str} ci={ci_str} "
        f"({result['kind']}; n_units={result['n_units']}, n_pairs={result['n_pairs']}) "
        f"null_p95_r={p95_str} above_null={result['above_null']}"
    )

    ws = result["within_session"]
    frac = result["fraction_of_within_session"]
    frac_str = f"{frac:.3f}" if frac is not None else "None"
    print(
        f"within_session: first={ws['first']:.3f} second={ws['second']:.3f} "
        f"geometric_mean={ws['geometric_mean']:.3f} fraction_of_within_session={frac_str}"
    )


def main(argv: list[str] | None = None) -> int:
    """Run the across-day comparison CLI (`rrb-across-days`).

    Args:
        argv: Optional list of CLI argument strings (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code (0 when the comparison was computed, 1 on contract violation
        in either day, 2 on input or compatibility error).
    """
    parser = argparse.ArgumentParser(
        description="Compare two spikes-path sessions of one preparation across matched units."
    )
    parser.add_argument("first_dir", metavar="FIRST_DIR", help="First-day dataset folder.")
    parser.add_argument("second_dir", metavar="SECOND_DIR", help="Second-day dataset folder.")
    parser.add_argument("--measure", default="t_half_excess", help="Measure name to compare.")
    parser.add_argument("--n-perm", type=int, default=controls.DEFAULT_N_PERM, help="Permutations for null.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")
    args = parser.parse_args(argv)

    try:
        if args.n_perm < 1:
            raise ValueError(f"n_perm must be >= 1, got {args.n_perm}.")
        _validate_measure_name(args.measure)
        first_meta = _inspect_day_files(args.first_dir)
        second_meta = _inspect_day_files(args.second_dir)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inputs_meta = {"first": first_meta, "second": second_meta}
    arguments_meta = {
        "first_dir": str(args.first_dir),
        "second_dir": str(args.second_dir),
        "measure": str(args.measure),
        "n_perm": int(args.n_perm),
        "seed": int(args.seed),
    }

    loaded: dict[str, Any] = {}
    for label, directory in (("first", args.first_dir), ("second", args.second_dir)):
        try:
            loaded[label] = load_day(directory, args.measure)
        except ContractViolation as exc:
            if args.as_json:
                _emit_across_days_json(
                    "violation", inputs_meta, arguments_meta, violation=exc.to_dict(), day=label
                )
            else:
                print(f"{label} day: {exc}")
            return 1
        except (
            FileNotFoundError,
            OSError,
            ValueError,
            pd.errors.ParserError,
            pd.errors.EmptyDataError,
            UnicodeError,
        ) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

    try:
        result = across_day_comparison(
            loaded["first"],
            loaded["second"],
            measure=args.measure,
            n_perm=args.n_perm,
            seed=args.seed,
        )
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.as_json:
        _emit_across_days_json("ok", inputs_meta, arguments_meta, result=result)
    else:
        _print_across_days_human(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
