"""Markdown summary builder for the Recovery Reliability Benchmark report command."""

from __future__ import annotations

import json
import math
from typing import Any

from . import contract
from .contract import ContractViolation, Requirement
from .report_notes import EMPTY_NOTES, NOTES_SEPARATOR, row_notes

DEFAULT_TITLE = "Recovery Reliability Benchmark Report"


def _conformance_line(result: dict[str, Any]) -> str:
    eval_conds: list[str] = list(result["census"]["evaluated_conditions"])
    per_cond = result["inclusion"]["per_condition"]
    should_by_cond: dict[str, list[str]] = {}
    for cond in eval_conds:
        info = per_cond[cond]
        failed = ([Requirement.MD2.value] if info["n_trials"] < contract.MD2_SHOULD else []) + (
            [Requirement.MD3.value] if info["n_units_included"] < contract.MD3_SHOULD else []
        )
        should_by_cond[cond] = failed

    best = min(
        eval_conds,
        key=lambda c: (
            len(should_by_cond[c]),
            -per_cond[c]["n_units_included"],
            -per_cond[c]["n_trials"],
            c,
        ),
    )
    missed = should_by_cond[best]
    level = contract.FULLY_CONFORMING if not missed else contract.CONFORMING
    census = result["census"]
    cond_word = "condition" if len(eval_conds) == 1 else "conditions"
    missed_part = f"; missed SHOULD: {', '.join(missed)}" if missed else ""
    return (
        f"Conformance: `{level}` (SPEC v{result['spec_version']}{missed_part}; "
        f"{len(eval_conds)} evaluated {cond_word}, {census['trials']} trials, {census['units']} units)."
    )


def _positive_control_line(pc: dict[str, Any]) -> str:
    verdict = "passed" if pc["passed"] else "failed"
    return (
        f"Positive control (split-half estimator on a synthetic table): {verdict} "
        f"(injected {pc['injected']:.2f}, recovered {pc['recovered']:.3f}, "
        f"tolerance ±{pc['tolerance']:.2f}, {pc['n_units']} units × {pc['n_trials']} trials)."
    )


def _measure_table_rows(
    label: str, raw_measure: str, m_entry: dict[str, Any], n_conditions: int
) -> list[str]:
    if m_entry.get("status") == "not_scored":
        n_min = min(int(v["n_units_scored"]) for v in m_entry["per_condition"].values())
        sens_cell = "n/a (one condition)" if n_conditions < 2 else "—"
        notes = row_notes(m_entry, None, is_first_row=True, measure=raw_measure)
        return [
            f"| {label} | — | — | — | {n_min} | {sens_cell} | {sens_cell} | {NOTES_SEPARATOR.join(notes)} |"
        ]

    h, null = m_entry["headline"], m_entry["null"]
    r_undef = bool(h.get("r_undefined"))
    rho_cell = "undefined" if r_undef else f"{h['rho']:.3f}"
    units_cell = str(h["n_units"])
    lo, hi, p95 = h["rho_ci_low"], h["rho_ci_high"], null["p95_rho"]
    ci_cell = f"[{lo:.3f}, {hi:.3f}]" if (not r_undef and lo is not None and hi is not None) else "n/a"
    null_cell = f"{p95:.3f}" if p95 is not None and not math.isnan(p95) else "n/a"

    sens = m_entry.get("sensitivity")
    pair_items: list[tuple[str | None, dict[str, Any] | None]] = (
        [(None, None)] if not sens else list(sens.items())
    )
    multi_pair = len(pair_items) > 1
    rows: list[str] = []
    for idx, (pair, pair_sens) in enumerate(pair_items):
        if pair_sens is None:
            z_cell = z_null_cell = "n/a (one condition)"
        else:
            z_val, s_null = pair_sens["median_abs_z"], pair_sens["null"]
            if z_val is None or s_null is None:
                z_cell, z_null_cell = (f"{pair}: n/a" if multi_pair else "n/a"), "n/a"
            else:
                z_cell = f"{pair}: {z_val:.2f}" if multi_pair else f"{z_val:.2f}"
                z_null_cell = f"{s_null['median_abs_z_p95']:.2f}"
        notes = row_notes(m_entry, pair, is_first_row=(idx == 0), measure=raw_measure)
        notes_str = NOTES_SEPARATOR.join(notes) if notes else EMPTY_NOTES
        rows.append(
            f"| {label} | {rho_cell} | {ci_cell} | {null_cell} | {units_cell} | "
            f"{z_cell} | {z_null_cell} | {notes_str} |"
        )
    return rows


def _how_to_read_lines(result: dict[str, Any], requested_measures: list[str]) -> list[str]:
    paragraphs: list[str] = []
    for m in requested_measures:
        m_entry = result["measures"][m]
        if m_entry.get("status") == "not_scored":
            n_min = min(int(v["n_units_scored"]) for v in m_entry["per_condition"].values())
            paragraphs.append(f"{m}: not scored ({n_min} units).")
            continue
        h, null = m_entry["headline"], m_entry["null"]
        if h.get("r_undefined"):
            parts = [f"{m}: reliability is undefined because every scored unit has the same value."]
        else:
            lo, hi, p95 = h["rho_ci_low"], h["rho_ci_high"], null["p95_rho"]
            lo_s = f"{lo:.3f}" if lo is not None else "n/a"
            hi_s = f"{hi:.3f}" if hi is not None else "n/a"
            p95_s = f"{p95:.3f}" if p95 is not None and not math.isnan(p95) else "n/a"
            parts = [f"{m}: reliability {h['rho']:.3f} (interval {lo_s} to {hi_s}; shuffled null {p95_s})."]
        for pair, pair_sens in (m_entry.get("sensitivity") or {}).items():
            first, second = pair.split("|", 1)
            z_val, s_null = pair_sens["median_abs_z"], pair_sens["null"]
            if z_val is not None and s_null is not None:
                parts.append(
                    f"Between {first} and {second} the typical unit moved {z_val:.2f} times its own noise "
                    f"(chance about {s_null['median_abs_z_p95']:.2f}); "
                    f"median shift {pair_sens['median_shift']:+.3g}."
                )
        paragraphs.append(" ".join(parts))

    ref = result.get("reference")
    if ref is not None:
        if ref.get("status") == "not_scored":
            ref_rho, ref_z = "not scored", "n/a"
        else:
            ref_h = ref["headline"]
            ref_rho = "undefined" if ref_h.get("r_undefined") else f"{ref_h['rho']:.3f}"
            ref_sens = ref.get("sensitivity")
            if ref_sens is None:
                ref_z = "n/a (one condition)"
            elif len(ref_sens) == 1:
                ps = next(iter(ref_sens.values()))
                ref_z = f"{ps['median_abs_z']:.2f}" if ps["median_abs_z"] is not None else "n/a"
            else:
                ref_z = ", ".join(
                    f"{p} {ps['median_abs_z']:.2f}" if ps["median_abs_z"] is not None else f"{p} n/a"
                    for p, ps in ref_sens.items()
                )
        paragraphs.append(
            f"baseline_hz is the reference row: reliability {ref_rho}, sensitivity {ref_z}. "
            "A measure worth using should match the reference on reliability and exceed it on sensitivity."
        )
    return paragraphs


def _inclusion_block(result: dict[str, Any], requested: list[str], eval_conds: list[str]) -> str:
    inc = result["inclusion"]
    items: list[str] = []
    if "spikes_path" in inc:
        sp_inc = inc["spikes_path"]["per_measure"]
        entries: list[tuple[str, str]] = [(m, m) for m in requested]
        ref = result.get("reference")
        if ref is not None and str(ref["measure"]) not in requested:
            rm = str(ref["measure"])
            entries.append((f"{rm} (reference)", rm))
        for label, key in entries:
            per_c = ", ".join(
                f"{c} {sp_inc[key][c]['n_units_scored']} of {sp_inc[key][c]['n_units_in_tables']} units scored"
                for c in eval_conds
            )
            items.append(f"- `{label}`: {per_c}")
    else:
        pc_inc = inc["per_condition"]
        for m in requested:
            per_c = ", ".join(
                f"{c} {pc_inc[c]['n_units_included']} of {pc_inc[c]['n_units_in_tables']} units scored"
                for c in eval_conds
            )
            items.append(f"- `{m}`: {per_c}")
    return "## Inclusion\n\n" + "\n".join(items)


def build_summary(
    result: dict[str, Any],
    title: str | None = None,
    command: str = "",
    *,
    figure_note: str | None = None,
) -> str:
    """Build the Markdown summary document from an evaluation result dictionary.

    Args:
        result: Evaluation result dictionary returned by ``run()`` or ``run_with_inputs()``.
        title: Report title heading (defaults to ``DEFAULT_TITLE`` when ``None`` or empty).
        command: Command-line invocation string recorded in the header.
        figure_note: Optional Markdown line describing or embedding the split-half figure
            (for example ``"Figure skipped: matplotlib not installed"``).

    Returns:
        Formatted Markdown report string ending with a trailing newline.
    """
    resolved_title = title if title else DEFAULT_TITLE
    params = result["parameters"]
    meta_parts = [
        f"package {result['package_version']}",
        f"SPEC v{result['spec_version']}",
        f"path: {params['path']}",
    ]
    if "analysis_fingerprint" in params:
        meta_parts.append(f"analysis: {params['analysis_fingerprint'][:12]}")
    cond_meta = (result.get("metadata") or {}).get("conditions")
    if cond_meta:
        proto = ", ".join(
            f"{c}={info['fingerprint'][:12] if info.get('fingerprint') else 'none'}"
            for c, info in cond_meta.items()
        )
        meta_parts.append(f"protocol: {proto}")

    blocks: list[str] = [f"# {resolved_title}", " | ".join(meta_parts)]
    if command:
        blocks.append(f"Command: `{command}`")
    blocks.append(_conformance_line(result))
    blocks.append(_positive_control_line(result["positive_control"]))

    requested = list(params["measures"])
    eval_conds = list(result["census"]["evaluated_conditions"])
    if result.get("status") == "ok":
        table_lines = [
            "| Measure | Reliability | 95% interval | Shuffled null p95 | Units | "
            "Sensitivity, median z | Sensitivity null p95 | Notes |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for m in requested:
            table_lines.extend(_measure_table_rows(m, m, result["measures"][m], len(eval_conds)))
        ref = result.get("reference")
        if ref is not None:
            ref_m = str(ref["measure"])
            table_lines.extend(_measure_table_rows(f"{ref_m} (reference)", ref_m, ref, len(eval_conds)))
        blocks.append("\n".join(table_lines))
        if ref is None:
            blocks.append("The reference row requires the spikes path.")

    if figure_note is not None:
        blocks.append(figure_note)
    blocks.append(_inclusion_block(result, requested, eval_conds))
    if result.get("status") == "ok":
        blocks.append("## How to read this\n\n" + "\n\n".join(_how_to_read_lines(result, requested)))
    blocks.append(f"## Parameters\n\n```json\n{json.dumps(params, indent=2, sort_keys=True)}\n```")
    return "\n\n".join(blocks) + "\n"


def build_violation_summary(
    exc: ContractViolation,
    title: str | None = None,
    command: str = "",
) -> str:
    """Build a Markdown summary document recording a contract violation.

    Args:
        exc: Raised ``ContractViolation`` instance.
        title: Report title heading (defaults to ``DEFAULT_TITLE`` when ``None`` or empty).
        command: Command-line invocation string recorded in the header.

    Returns:
        Formatted Markdown violation summary string ending with a trailing newline.
    """
    from . import __version__

    resolved_title = title if title else DEFAULT_TITLE
    blocks = [
        f"# {resolved_title}",
        f"package {__version__} | SPEC v{contract.SPEC_VERSION} | status: violation",
        *([f"Command: `{command}`"] if command else []),
        "## Contract violation\n\n"
        f"- Requirement: `{exc.requirement.value}`\n"
        f"- Message: {exc.message}\n"
        f"- Found: `{exc.found}`\n"
        f"- Required: `{exc.required}`",
    ]
    return "\n\n".join(blocks) + "\n"
