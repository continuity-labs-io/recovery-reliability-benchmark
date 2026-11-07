"""Run v0.1.0 against the Sharf 2022 Dryad organoid spontaneous recordings (G0 machinery test)."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.io as sio

from recovery_reliability_benchmark import contract, evaluate

CHIP_TO_ORGANOID: dict[str, str] = {"2953": "L1", "2950": "L2", "2957": "L3", "2954": "L4", "5116": "L5", "5118": "L6"}  # fmt: skip
RECORDING_RELPATHS: tuple[str, ...] = (
    *(f"7month/kilosort2/{c}.mat" for c in (2950, 2953, 2954, 2957, 5116, 5118)),
    *(f"drug/kilosort2/control_{c}.mat" for c in (2950, 2953, 2954, 2957)),
    *(f"interval/kilosort2/4hr_{t}_{c}.mat" for t in (1200, 1600) for c in (2950, 2957)),
)
SUMMARY_COLUMNS: tuple[str, ...] = tuple(
    "organoid stem duration_s n_epochs units units_included conformance rho rho_ci_low "
    "rho_ci_high rho_at_20 null_p95_rho var_between var_within moments_reliability "
    "r_undefined r_nonpositive positive_control_passed check_exit evaluate_exit".split()
)
TRANSFORM_MEASURES: tuple[str, ...] = ("firing_rate_hz", "log_firing_rate_hz", "sqrt_firing_rate_hz", "rank_firing_rate_hz")  # fmt: skip
TRANSFORM_COLUMNS: tuple[str, ...] = (
    "organoid", "stem", "n_units", *(c for m in TRANSFORM_MEASURES for c in (f"{m}_rho", f"{m}_null_p95_rho")), "rho_max_minus_min"
)  # fmt: skip


def _cli_executable(name: str) -> str:
    candidate = Path(sys.executable).with_name(name)
    return str(candidate) if candidate.is_file() else name


# Intent: scipy.io.loadmat(..., squeeze_me=True) collapses a 1-spike train to a
# 0-D scalar and an empty train to shape (0,), so every spike_train is wrapped in
# np.atleast_1d. An epoch with zero spikes records firing_rate_hz = 0.0 (never NaN)
# because zero spikes is a measurement, not a missing value (SPEC §15); every unit
# therefore has a complete epoch grid and none are filtered on activity.
def build_recording_tables(
    raw_units: Sequence[Any] | np.ndarray, fs: float, epoch_s: float,
    stem: str = "recording", preparation_id: str = "L1", transforms: bool = False,
) -> dict[str, Any]:  # fmt: skip
    """Convert Kilosort2 unit structs into benchmark units, responses, and spikes tables.
    Args:
        raw_units: Sequence or array of unit objects with unit_id, spike_train, x_max, and y_max.
        fs: Sampling rate in Hz.
        epoch_s: Fixed epoch duration in seconds standing in for trials.
        stem: Recording stem used for recording_id and session_id.
        preparation_id: Organoid identifier (L1 through L6).
        transforms: When True, add log, sqrt, and within-epoch rank firing-rate columns.
    Returns:
        Dictionary with keys units, responses, spikes, duration_s, n_epochs, and unit_id_fallback.
    """
    units_list = list(np.atleast_1d(np.asarray(raw_units, dtype=object)))
    fs_f, epoch_f = float(fs), float(epoch_s)
    spike_trains = [np.atleast_1d(u.spike_train).astype(np.int64) for u in units_list]
    duration_s = float(max((int(st.max()) for st in spike_trains if st.size > 0), default=0)) / fs_f
    n_epochs = int(math.floor(duration_s / epoch_f))

    candidate_ids = [f"u{int(u.unit_id)}" for u in units_list]
    fallback = len(set(candidate_ids)) != len(candidate_ids)
    unit_ids = [f"u{idx}" for idx in range(len(units_list))] if fallback else candidate_ids

    unit_rows, response_rows, spike_rows, cutoff_s = [], [], [], n_epochs * epoch_f
    for uid, u, samples in zip(unit_ids, units_list, spike_trains, strict=True):
        unit_rows.append((uid, stem, stem, preparation_id, float(u.x_max), float(u.y_max)))
        spike_rows.extend((uid, int(round(int(s) / fs_f * 1e9))) for s in samples)
        if n_epochs > 0:
            times_s = samples.astype(np.float64) / fs_f
            valid = times_s[(times_s >= 0.0) & (times_s < cutoff_s)]
            idx = np.floor(valid / epoch_f).astype(np.int64)
            counts = np.bincount(idx[(idx >= 0) & (idx < n_epochs)], minlength=n_epochs)[:n_epochs]
            for k in range(n_epochs):
                response_rows.append((uid, k, int(round(k * epoch_f * 1e9)), "spontaneous", float(counts[k]) / epoch_f))  # fmt: skip

    u_cols = ["unit_id", "recording_id", "session_id", "preparation_id", "x_um", "y_um"]
    r_cols = ["unit_id", "trial_index", "stim_time_ns", "condition", "firing_rate_hz"]
    responses = pd.DataFrame(response_rows, columns=r_cols)
    if transforms:
        # Intent: 1.0 / epoch_f (0.2 Hz for a 5.0 s epoch) is one spike in an epoch —
        # the smallest nonzero rate the recording can express, so it serves as the natural
        # floor for log10 rather than an arbitrary epsilon. Within-epoch rank (average ties)
        # discards magnitude and keeps only unit ordering, bounding how far any monotone
        # transform can move Pearson r.
        rate = responses["firing_rate_hz"].astype(np.float64)
        responses["log_firing_rate_hz"], responses["sqrt_firing_rate_hz"] = np.log10(rate + 1.0 / epoch_f), np.sqrt(rate)  # fmt: skip
        responses["rank_firing_rate_hz"] = responses.groupby("trial_index")["firing_rate_hz"].rank(method="average")  # fmt: skip
    return {
        "units": pd.DataFrame(unit_rows, columns=u_cols), "responses": responses,
        "spikes": pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"]),
        "duration_s": duration_s, "n_epochs": n_epochs, "unit_id_fallback": fallback,
    }  # fmt: skip


def process_recording(
    mat_path: Path, out_dir: Path, epoch_s: float, min_epochs: int,
    n_perm: int, seed: int, transforms: bool = False,
) -> dict[str, Any]:  # fmt: skip
    """Write benchmark inputs for one recording, run CLI subprocesses, and collect summary fields.
    Args:
        mat_path: Path to the Kilosort2 .mat file.
        out_dir: Output root directory.
        epoch_s: Fixed epoch duration in seconds.
        min_epochs: Minimum required epoch count before skipping.
        n_perm: Number of permutations passed to rrb-evaluate.
        seed: Random seed passed to rrb-evaluate.
        transforms: When True, evaluate all four raw and transformed firing-rate measures together.
    Returns:
        Dictionary of summary and transform fields for summary.md, transforms.md, and g0.png.
    """
    stem, organoid = mat_path.stem, CHIP_TO_ORGANOID[mat_path.stem.split("_")[-1]]
    mat_data = sio.loadmat(mat_path, struct_as_record=False, squeeze_me=True)
    built = build_recording_tables(mat_data["units"], float(mat_data["fs"]), epoch_s, stem, organoid, transforms=transforms)  # fmt: skip
    duration_s, n_epochs, n_units = built["duration_s"], built["n_epochs"], int(len(built["units"]))
    fb_note = " (positional unit_id fallback)" if built["unit_id_fallback"] else ""

    row: dict[str, Any] = dict.fromkeys((*SUMMARY_COLUMNS, *TRANSFORM_COLUMNS), "—")
    row.update(organoid=organoid, stem=stem, duration_s=f"{duration_s:.2f}", n_epochs=n_epochs, units=n_units, n_units=n_units)  # fmt: skip
    if n_epochs < min_epochs:
        row["conformance"] = f"skipped: n_epochs={n_epochs} < min_epochs={min_epochs}{fb_note}"
        return row

    (rec_dir := out_dir / stem).mkdir(parents=True, exist_ok=True)
    units_csv, responses_csv, spikes_csv = (rec_dir / f for f in ("units.csv", "responses.csv", "spikes.csv"))
    prep_json, cond_json = rec_dir / "preparation.json", rec_dir / "conditions.json"
    for key, csv_path in (("units", units_csv), ("responses", responses_csv), ("spikes", spikes_csv)):
        built[key].to_csv(csv_path, index=False)
    prep_payload = {
        "preparation_id": organoid, "species": "Homo sapiens", "preparation_type": "organoid",
        "age_days": 210, "age_basis": "days_post_differentiation", "line_or_donor_id": "F12442.4",
        "instrument": "MaxOne", "raw_data_url": "https://doi.org/10.25349/D9031Z",
    }  # fmt: skip
    cond_payload = {"spontaneous": dict.fromkeys(("protocol", "compound", "dose", "dose_unit", "vehicle"))}
    prep_json.write_text(json.dumps(prep_payload, indent=2) + "\n", encoding="utf-8")
    cond_json.write_text(json.dumps(cond_payload, indent=2) + "\n", encoding="utf-8")

    measures_arg = ",".join(TRANSFORM_MEASURES) if transforms else "firing_rate_hz"
    cli_args = [
        str(units_csv), str(responses_csv), "--measures", measures_arg,
        "--post-stim-window-s", str(epoch_s), "--load-duration-s", "0",
        "--preparation", str(prep_json), "--conditions", str(cond_json),
        "--spikes", str(spikes_csv), "--json",
    ]  # fmt: skip
    check_proc = subprocess.run([_cli_executable("rrb-check"), *cli_args], capture_output=True, text=True)
    eval_cmd = [_cli_executable("rrb-evaluate"), *cli_args, "--n-perm", str(n_perm), "--seed", str(seed)]
    eval_proc = subprocess.run(eval_cmd, capture_output=True, text=True)
    (rec_dir / "check.json").write_text(check_proc.stdout, encoding="utf-8")
    (rec_dir / "evaluate.json").write_text(eval_proc.stdout, encoding="utf-8")
    row["check_exit"], row["evaluate_exit"] = check_proc.returncode, eval_proc.returncode

    check_doc = json.loads(check_proc.stdout) if check_proc.stdout.strip() else {}
    eval_doc = json.loads(eval_proc.stdout) if eval_proc.stdout.strip() else {}
    if check_proc.returncode != 0 or "result" not in check_doc:
        row["conformance"] = f"violation ({check_doc.get('violation', {}).get('requirement', 'error')}){fb_note}"  # fmt: skip
        return row

    c_res = check_doc["result"]
    row["units_included"] = row["n_units"] = c_res["inclusion"]["per_condition"]["spontaneous"]["n_units_included"]  # fmt: skip
    row["conformance"] = f"{c_res['conformance']}{fb_note}"
    if "result" in eval_doc and "measures" in eval_doc["result"]:
        e_res = eval_doc["result"]
        m_res = e_res["measures"]["firing_rate_hz"]
        h, var = m_res["headline"], m_res["headline"]["variance"]
        mr = var["moments_reliability"]
        ci_lo, ci_hi = (f"{h[k]:.2f}" if h[k] is not None else "None" for k in ("rho_ci_low", "rho_ci_high"))
        row.update(
            rho=f"{h['rho']:.3f}", rho_ci_low=ci_lo, rho_ci_high=ci_hi, rho_at_20=f"{h['rho_at_20']:.3f}",
            null_p95_rho=f"{m_res['null']['p95_rho']:.3f}", var_between=f"{var['var_between']:.4g}",
            var_within=f"{var['var_within']:.4g}", moments_reliability=f"{mr:.3f}" if mr is not None else "None",
            r_undefined=h["r_undefined"], r_nonpositive=h["r_nonpositive"],
            positive_control_passed=e_res["positive_control"]["passed"],
        )  # fmt: skip
        if transforms:
            rhos = [float(e_res["measures"][m]["headline"]["rho"]) for m in TRANSFORM_MEASURES]
            for m in TRANSFORM_MEASURES:
                mh, mnull = e_res["measures"][m]["headline"], e_res["measures"][m]["null"]
                row[f"{m}_rho"], row[f"{m}_null_p95_rho"] = f"{mh['rho']:.3f}", f"{mnull['p95_rho']:.3f}"
            row["rho_max_minus_min"] = f"{max(rhos) - min(rhos):.3f}"
    return row


def write_g0_plot(rows: Sequence[dict[str, Any]], out_dir: Path) -> Path:
    """Render odd-half vs even-half mean firing_rate_hz panels to {out}/g0.png.
    Args:
        rows: Per-recording summary rows produced by process_recording.
        out_dir: Output root directory containing per-recording subdirectories.
    Returns:
        Path to the written g0.png figure.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ncols, nrows = 4, int(math.ceil(len(rows) / 4))
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.8 * ncols, 4.0 * nrows), squeeze=False)
    flat_axes = axes.ravel()
    for idx, row in enumerate(rows):
        ax, stem, organoid = flat_axes[idx], str(row["stem"]), str(row["organoid"])
        if not (rec_dir := out_dir / stem).joinpath("responses.csv").is_file():
            ax.set_title(f"{organoid} {stem}: skipped", fontsize=8)
            ax.axis("off")
            continue
        _, responses = contract.read_tables(rec_dir / "units.csv", rec_dir / "responses.csv")
        check_doc = json.loads((rec_dir / "check.json").read_text(encoding="utf-8"))
        eval_doc = json.loads((rec_dir / "evaluate.json").read_text(encoding="utf-8"))
        active = {"spontaneous": set(check_doc["result"]["conditions"]["spontaneous"]["active_units"])} if "result" in check_doc else None  # fmt: skip
        halves = evaluate.split_halves(responses, ["firing_rate_hz"], ["spontaneous"], active_units=active)
        odd, even = halves["firing_rate_hz_odd"].to_numpy(float), halves["firing_rate_hz_even"].to_numpy(float)  # fmt: skip
        pos = (odd > 0.0) & (even > 0.0)
        if np.any(pos):
            ax.scatter(odd[pos], even[pos], s=18, alpha=0.75, edgecolors="none")
            lo_lim, hi_lim = float(min(odd[pos].min(), even[pos].min())) * 0.8, float(max(odd[pos].max(), even[pos].max())) * 1.25  # fmt: skip
            ax.plot([lo_lim, hi_lim], [lo_lim, hi_lim], "--", color="0.4", linewidth=1.0)
            ax.set(xlim=(lo_lim, hi_lim), ylim=(lo_lim, hi_lim), xscale="log", yscale="log")
        if "result" in eval_doc and "measures" in eval_doc["result"]:
            h = eval_doc["result"]["measures"]["firing_rate_hz"]["headline"]
            title = f"{organoid} {stem}: rho={h['rho']:.3f} [{h['rho_ci_low']:.2f}, {h['rho_ci_high']:.2f}], n_units={h['n_units']}, n_epochs={row['n_epochs']}"
        else:
            title = f"{organoid} {stem}: {row['conformance']}, n_units={row['units']}, n_epochs={row['n_epochs']}"  # fmt: skip
        ax.set_title(title, fontsize=8)
        ax.set(xlabel="Odd-half firing_rate_hz (Hz)", ylabel="Even-half firing_rate_hz (Hz)")
    for ax in flat_axes[len(rows) :]:
        ax.axis("off")
    fig.tight_layout()
    fig.savefig(out_png := out_dir / "g0.png", dpi=150)
    plt.close(fig)
    return out_png


def _write_markdown_table(rows: Sequence[dict[str, Any]], cols: Sequence[str], out_md: Path) -> Path:
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    lines.extend("| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows)
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_md


def write_summary_markdown(rows: Sequence[dict[str, Any]], out_dir: Path) -> Path:
    """Write the Markdown summary table across all recordings to {out}/summary.md.
    Args:
        rows: Per-recording summary rows produced by process_recording.
        out_dir: Output root directory.
    Returns:
        Path to the written summary.md file.
    """
    return _write_markdown_table(rows, SUMMARY_COLUMNS, out_dir / "summary.md")


def write_transforms_markdown(rows: Sequence[dict[str, Any]], out_dir: Path) -> Path:
    """Write the Markdown transform-sensitivity table across all recordings to {out}/transforms.md.
    Args:
        rows: Per-recording summary rows produced by process_recording(..., transforms=True).
        out_dir: Output root directory.
    Returns:
        Path to the written transforms.md file.
    """
    return _write_markdown_table(rows, TRANSFORM_COLUMNS, out_dir / "transforms.md")


def main(argv: list[str] | None = None) -> int:
    """Run the Sharf 2022 G0 machinery test across all spontaneous recordings.
    Args:
        argv: Optional CLI argument list (defaults to sys.argv[1:]).
    Returns:
        Exit code (0 on completion).
    """
    parser = argparse.ArgumentParser(description="Run v0.1.0 against Sharf 2022 spontaneous recordings.")
    parser.add_argument("--root", type=Path, default=Path("data/sharf2022/kilosort2"))
    parser.add_argument("--out", type=Path, default=Path("output/sharf2022"))
    parser.add_argument("--epoch-s", type=float, default=5.0)
    parser.add_argument("--min-epochs", type=int, default=20)
    parser.add_argument("--n-perm", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--transforms", action="store_true", help="Evaluate monotone measure transforms.")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rows = [
        process_recording(args.root / rel, args.out, args.epoch_s, args.min_epochs, args.n_perm, args.seed, transforms=args.transforms)
        for rel in RECORDING_RELPATHS
    ]  # fmt: skip
    write_summary_markdown(rows, args.out)
    write_g0_plot(rows, args.out)
    if args.transforms:
        write_transforms_markdown(rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
