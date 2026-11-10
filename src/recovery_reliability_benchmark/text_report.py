"""Human-readable text report formatting for conformance checks and reliability evaluations."""

from __future__ import annotations

from typing import Any


def print_inclusion_lines(inclusion: dict[str, Any], evaluated_conditions: list[str]) -> None:
    """Print per-condition unit inclusion and declared exclusion summary lines.

    Args:
        inclusion: Inclusion summary dictionary from the conformance or evaluation report.
        evaluated_conditions: List of evaluated condition labels.
    """
    decl = inclusion["declared"]
    for cond in evaluated_conditions:
        inc = inclusion["per_condition"][cond]
        print(
            f"{cond}: units included {inc['n_units_included']} of {inc['n_units_in_tables']} "
            f"(excluded by rule {inc['n_units_excluded_by_rule']}, rows missing {inc['n_rows_missing']}); "
            f"declared exclusions units {decl['units']} trials {decl['trials']}"
        )


def print_check_human(result: dict[str, Any]) -> None:
    """Print a conformance check result as human-readable lines.

    Args:
        result: Conformance report dictionary returned by ``validate()``.
    """
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
    print_inclusion_lines(result["inclusion"], result["evaluated_conditions"])


def print_evaluate_human(result: dict[str, Any]) -> None:
    """Print an evaluation report as human-readable lines.

    Args:
        result: Evaluation report dictionary returned by ``run()``.
    """
    print(f"package_version: {result['package_version']} (SPEC v{result['spec_version']})")
    params = result["parameters"]
    if params.get("path") == "spikes":
        print(f"path: spikes, analysis {params['analysis_fingerprint'][:12]}")
    print("census:")
    for key, value in result["census"].items():
        print(f"  {key}: {value}")
    eval_conds = result["census"]["evaluated_conditions"]
    print_inclusion_lines(result["inclusion"], eval_conds)
    if "spikes_path" in result["inclusion"]:
        sp_inc = result["inclusion"]["spikes_path"]["per_measure"]
        for m in result["measures"]:
            for cond in eval_conds:
                c_inc = sp_inc[m][cond]
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
    ref = result.get("reference")
    if ref is not None:
        ref_m = ref["measure"]
        if ref.get("status") == "not_scored":
            print(f"reference ({ref_m}): not_scored")
        else:
            h = ref["headline"]
            lo, hi = h["rho_ci_low"], h["rho_ci_high"]
            ci_str = f"[{lo:.3f}, {hi:.3f}]" if lo is not None and hi is not None else "[None, None]"
            print(f"reference ({ref_m}): rho={h['rho']:.3f} ci={ci_str} n_units={h['n_units']}")
