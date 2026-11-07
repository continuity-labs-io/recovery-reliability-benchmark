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

CHIP_TO_ORGANOID: dict[str, str] = {
    "2953": "L1", "2950": "L2", "2957": "L3", "2954": "L4", "5116": "L5", "5118": "L6"
}  # fmt: skip

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


def _cli_executable(name: str) -> str:
    candidate = Path(sys.executable).with_name(name)
    return str(candidate) if candidate.is_file() else name


# Intent: scipy.io.loadmat(..., squeeze_me=True) collapses a 1-spike train to a
# 0-D scalar and an empty train to shape (0,), so every spike_train is wrapped in
# np.atleast_1d. An epoch with zero spikes records firing_rate_hz = 0.0 (never NaN)
# because zero spikes is a measurement, not a missing value (SPEC §15); every unit
# therefore has a complete epoch grid and none are filtered on activity.
def build_recording_tables(
    raw_units: Sequence[Any] | np.ndarray,
    fs: float,
    epoch_s: float,
    stem: str = "recording",
    preparation_id: str = "L1",
) -> dict[str, Any]:
    """Convert Kilosort2 unit structs into benchmark units, responses, and spikes tables.
    Args:
        raw_units: Sequence or array of unit objects with unit_id, spike_train, x_max, and y_max.
        fs: Sampling rate in Hz.
        epoch_s: Fixed epoch duration in seconds standing in for trials.
        stem: Recording stem used for recording_id and session_id.
        preparation_id: Organoid identifier (L1 through L6).
    Returns:
        Dictionary with keys units, responses, spikes, duration_s, n_epochs, and unit_id_fallback.
    """
    units_list = list(np.atleast_1d(np.asarray(raw_units, dtype=object)))
    fs_f, epoch_f = float(fs), float(epoch_s)
    spike_trains = [np.atleast_1d(u.spike_train).astype(np.int64) for u in units_list]
    max_sample = max((int(st.max()) for st in spike_trains if st.size > 0), default=0)
    duration_s = float(max_sample) / fs_f
    n_epochs = int(math.floor(duration_s / epoch_f))

    candidate_ids = [f"u{int(u.unit_id)}" for u in units_list]
    fallback = len(set(candidate_ids)) != len(candidate_ids)
    unit_ids = [f"u{idx}" for idx in range(len(units_list))] if fallback else candidate_ids

    unit_rows: list[tuple[Any, ...]] = []
    response_rows: list[tuple[Any, ...]] = []
    spike_rows: list[tuple[str, int]] = []
    cutoff_s = n_epochs * epoch_f

    for uid, u, samples in zip(unit_ids, units_list, spike_trains, strict=True):
        unit_rows.append((uid, stem, stem, preparation_id, float(u.x_max), float(u.y_max)))
        spike_rows.extend((uid, int(round(int(s) / fs_f * 1e9))) for s in samples)
        if n_epochs > 0:
            times_s = samples.astype(np.float64) / fs_f
            valid = times_s[(times_s >= 0.0) & (times_s < cutoff_s)]
            idx = np.floor(valid / epoch_f).astype(np.int64)
            counts = np.bincount(idx[(idx >= 0) & (idx < n_epochs)], minlength=n_epochs)[:n_epochs]
            for k in range(n_epochs):
                stim_ns = int(round(k * epoch_f * 1e9))
                response_rows.append((uid, k, stim_ns, "spontaneous", float(counts[k]) / epoch_f))

    u_cols = ["unit_id", "recording_id", "session_id", "preparation_id", "x_um", "y_um"]
    r_cols = ["unit_id", "trial_index", "stim_time_ns", "condition", "firing_rate_hz"]
    return {
        "units": pd.DataFrame(unit_rows, columns=u_cols),
        "responses": pd.DataFrame(response_rows, columns=r_cols),
        "spikes": pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"]),
        "duration_s": duration_s,
        "n_epochs": n_epochs,
        "unit_id_fallback": fallback,
    }


def process_recording(
    mat_path: Path, out_dir: Path, epoch_s: float, min_epochs: int, n_perm: int, seed: int
) -> dict[str, Any]:
    """Write benchmark inputs for one recording, run CLI subprocesses, and collect summary fields.
    Args:
        mat_path: Path to the Kilosort2 .mat file.
        out_dir: Output root directory.
        epoch_s: Fixed epoch duration in seconds.
        min_epochs: Minimum required epoch count before skipping.
        n_perm: Number of permutations passed to rrb-evaluate.
        seed: Random seed passed to rrb-evaluate.
    Returns:
        Dictionary of summary fields for summary.md and g0.png.
    """
    stem = mat_path.stem
    organoid = CHIP_TO_ORGANOID[stem.split("_")[-1]]
    mat_data = sio.loadmat(mat_path, struct_as_record=False, squeeze_me=True)
    built = build_recording_tables(mat_data["units"], float(mat_data["fs"]), epoch_s, stem, organoid)
    duration_s, n_epochs, n_units = built["duration_s"], built["n_epochs"], int(len(built["units"]))
    fb_note = " (positional unit_id fallback)" if built["unit_id_fallback"] else ""

    row: dict[str, Any] = dict.fromkeys(SUMMARY_COLUMNS, "—")
    row.update(organoid=organoid, stem=stem, duration_s=f"{duration_s:.2f}", n_epochs=n_epochs, units=n_units)
    if n_epochs < min_epochs:
        row["conformance"] = f"skipped: n_epochs={n_epochs} < min_epochs={min_epochs}{fb_note}"
        return row

    rec_dir = out_dir / stem
    rec_dir.mkdir(parents=True, exist_ok=True)
    units_csv, responses_csv = rec_dir / "units.csv", rec_dir / "responses.csv"
    spikes_csv, prep_json, cond_json = (
        rec_dir / "spikes.csv", rec_dir / "preparation.json", rec_dir / "conditions.json"
    )  # fmt: skip
    built["units"].to_csv(units_csv, index=False)
    built["responses"].to_csv(responses_csv, index=False)
    built["spikes"].to_csv(spikes_csv, index=False)
    prep_payload = {
        "preparation_id": organoid, "species": "Homo sapiens", "preparation_type": "organoid",
        "age_days": 210, "age_basis": "days_post_differentiation", "line_or_donor_id": "F12442.4",
        "instrument": "MaxOne", "raw_data_url": "https://doi.org/10.25349/D9031Z",
    }  # fmt: skip
    cond_payload = {"spontaneous": dict.fromkeys(("protocol", "compound", "dose", "dose_unit", "vehicle"))}
    prep_json.write_text(json.dumps(prep_payload, indent=2) + "\n", encoding="utf-8")
    cond_json.write_text(json.dumps(cond_payload, indent=2) + "\n", encoding="utf-8")

    cli_args = [
        str(units_csv), str(responses_csv), "--measures", "firing_rate_hz",
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
        req = check_doc.get("violation", {}).get("requirement", "error")
        row["conformance"] = f"violation ({req}){fb_note}"
        return row

    c_res = check_doc["result"]
    row["units_included"] = c_res["inclusion"]["per_condition"]["spontaneous"]["n_units_included"]
    row["conformance"] = f"{c_res['conformance']}{fb_note}"
    if "result" in eval_doc and "measures" in eval_doc["result"]:
        e_res = eval_doc["result"]
        m_res = e_res["measures"]["firing_rate_hz"]
        h, var = m_res["headline"], m_res["headline"]["variance"]
        mr = var["moments_reliability"]
        row.update(
            rho=f"{h['rho']:.3f}",
            rho_ci_low=f"{h['rho_ci_low']:.2f}" if h["rho_ci_low"] is not None else "None",
            rho_ci_high=f"{h['rho_ci_high']:.2f}" if h["rho_ci_high"] is not None else "None",
            rho_at_20=f"{h['rho_at_20']:.3f}",
            null_p95_rho=f"{m_res['null']['p95_rho']:.3f}",
            var_between=f"{var['var_between']:.4g}",
            var_within=f"{var['var_within']:.4g}",
            moments_reliability=f"{mr:.3f}" if mr is not None else "None",
            r_undefined=h["r_undefined"],
            r_nonpositive=h["r_nonpositive"],
            positive_control_passed=e_res["positive_control"]["passed"],
        )
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
        ax = flat_axes[idx]
        stem, organoid = str(row["stem"]), str(row["organoid"])
        rec_dir = out_dir / stem
        if not (rec_dir / "responses.csv").is_file():
            ax.set_title(f"{organoid} {stem}: skipped", fontsize=8)
            ax.axis("off")
            continue
        _, responses = contract.read_tables(rec_dir / "units.csv", rec_dir / "responses.csv")
        check_doc = json.loads((rec_dir / "check.json").read_text(encoding="utf-8"))
        eval_doc = json.loads((rec_dir / "evaluate.json").read_text(encoding="utf-8"))
        active = (
            {"spontaneous": set(check_doc["result"]["conditions"]["spontaneous"]["active_units"])}
            if "result" in check_doc
            else None
        )
        halves = evaluate.split_halves(responses, ["firing_rate_hz"], ["spontaneous"], active_units=active)
        odd = halves["firing_rate_hz_odd"].to_numpy(dtype=float)
        even = halves["firing_rate_hz_even"].to_numpy(dtype=float)
        pos = (odd > 0.0) & (even > 0.0)
        if np.any(pos):
            ax.scatter(odd[pos], even[pos], s=18, alpha=0.75, edgecolors="none")
            lo_lim = float(min(odd[pos].min(), even[pos].min())) * 0.8
            hi_lim = float(max(odd[pos].max(), even[pos].max())) * 1.25
            ax.plot([lo_lim, hi_lim], [lo_lim, hi_lim], "--", color="0.4", linewidth=1.0)
            ax.set(xlim=(lo_lim, hi_lim), ylim=(lo_lim, hi_lim), xscale="log", yscale="log")
        if "result" in eval_doc and "measures" in eval_doc["result"]:
            h = eval_doc["result"]["measures"]["firing_rate_hz"]["headline"]
            title = f"{organoid} {stem}: rho={h['rho']:.3f} [{h['rho_ci_low']:.2f}, {h['rho_ci_high']:.2f}], n_units={h['n_units']}, n_epochs={row['n_epochs']}"
        else:
            conf, u_cnt, ep_cnt = row["conformance"], row["units"], row["n_epochs"]
            title = f"{organoid} {stem}: {conf}, n_units={u_cnt}, n_epochs={ep_cnt}"
        ax.set_title(title, fontsize=8)
        ax.set_xlabel("Odd-half firing_rate_hz (Hz)", fontsize=8)
        ax.set_ylabel("Even-half firing_rate_hz (Hz)", fontsize=8)
    for idx in range(len(rows), len(flat_axes)):
        flat_axes[idx].axis("off")
    fig.tight_layout()
    out_png = out_dir / "g0.png"
    fig.savefig(out_png, dpi=150)
    plt.close(fig)
    return out_png


def write_summary_markdown(rows: Sequence[dict[str, Any]], out_dir: Path) -> Path:
    """Write the Markdown summary table across all recordings to {out}/summary.md.
    Args:
        rows: Per-recording summary rows produced by process_recording.
        out_dir: Output root directory.
    Returns:
        Path to the written summary.md file.
    """
    header = "| " + " | ".join(SUMMARY_COLUMNS) + " |"
    divider = "| " + " | ".join("---" for _ in SUMMARY_COLUMNS) + " |"
    body = ["| " + " | ".join(str(row[col]) for col in SUMMARY_COLUMNS) + " |" for row in rows]
    out_md = out_dir / "summary.md"
    out_md.write_text("\n".join([header, divider, *body]) + "\n", encoding="utf-8")
    return out_md


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
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    rows = [
        process_recording(args.root / rel, args.out, args.epoch_s, args.min_epochs, args.n_perm, args.seed)
        for rel in RECORDING_RELPATHS
    ]
    write_summary_markdown(rows, args.out)
    write_g0_plot(rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
