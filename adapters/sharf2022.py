"""Adapter converting Sharf et al. (2022) Kilosort2 .mat recordings into benchmark tables.

Contains no analysis: extracts unit identifiers, electrode coordinates, and spike timestamps
from Kilosort2 MATLAB structs, slices spontaneous recordings into fixed-duration epochs via
``recovery_reliability_benchmark.epochs.build_epoch_tables``, writes canonical dataset files
plus ``preparation.json`` and ``conditions.json``, and prints the next ``rrb-check`` and
``rrb-report`` CLI commands.
"""

from __future__ import annotations

import argparse
import json
import shlex
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io as sio

from recovery_reliability_benchmark.epochs import TRANSFORM_MEASURES, build_epoch_tables

CHIP_TO_ORGANOID: dict[str, str] = {
    "2953": "L1",
    "2950": "L2",
    "2957": "L3",
    "2954": "L4",
    "5116": "L5",
    "5118": "L6",
}
RECORDING_RELPATHS: tuple[str, ...] = (
    *(f"7month/kilosort2/{c}.mat" for c in (2950, 2953, 2954, 2957, 5116, 5118)),
    *(f"drug/kilosort2/control_{c}.mat" for c in (2950, 2953, 2954, 2957)),
    *(f"interval/kilosort2/4hr_{t}_{c}.mat" for t in (1200, 1600) for c in (2950, 2957)),
)
RAW_DATA_URL = "https://doi.org/10.25349/D9031Z"


# Intent: scipy.io.loadmat(..., squeeze_me=True) collapses a 1-spike train to a
# 0-D scalar and an empty train to shape (0,), so every spike_train is wrapped in
# np.atleast_1d before converting integer sample indices to seconds.
def build_recording_tables(
    raw_units: Sequence[Any] | np.ndarray,
    fs: float,
    epoch_s: float,
    stem: str = "recording",
    preparation_id: str = "L1",
    transforms: bool = False,
) -> dict[str, Any]:
    """Convert Kilosort2 unit structs into benchmark units, responses, and spikes tables.

    Args:
        raw_units: Sequence or array of unit objects with ``unit_id``, ``spike_train``,
            ``x_max``, and ``y_max``.
        fs: Sampling rate in Hz.
        epoch_s: Fixed epoch duration in seconds standing in for trials.
        stem: Recording stem used for ``recording_id`` and ``session_id``.
        preparation_id: Organoid identifier (``L1`` through ``L6``).
        transforms: When True, add log, sqrt, and within-epoch rank firing-rate columns.

    Returns:
        Dictionary with keys ``units``, ``responses``, ``spikes``, ``duration_s``,
        ``n_epochs``, and ``unit_id_fallback``.
    """
    units_list = list(np.atleast_1d(np.asarray(raw_units, dtype=object)))
    fs_f = float(fs)
    candidate_ids = [f"u{int(u.unit_id)}" for u in units_list]
    fallback = len(set(candidate_ids)) != len(candidate_ids)
    unit_ids = [f"u{idx}" for idx in range(len(units_list))] if fallback else candidate_ids

    spike_times_s: dict[str, np.ndarray] = {}
    coords_um: dict[str, tuple[float, float]] = {}
    for uid, u in zip(unit_ids, units_list, strict=True):
        samples = np.atleast_1d(u.spike_train).astype(np.int64)
        spike_times_s[uid] = samples.astype(np.float64) / fs_f
        coords_um[uid] = (float(u.x_max), float(u.y_max))

    built = build_epoch_tables(
        unit_ids=unit_ids,
        spike_times_s=spike_times_s,
        epoch_s=epoch_s,
        recording_id=stem,
        session_id=stem,
        preparation_id=preparation_id,
        condition="spontaneous",
        coords_um=coords_um,
        transforms=transforms,
    )
    built["unit_id_fallback"] = fallback
    return built


def convert_recording(
    mat_path: Path,
    out_dir: Path,
    epoch_s: float = 5.0,
    min_epochs: int = 20,
    *,
    transforms: bool = False,
) -> dict[str, Any]:
    """Convert one Sharf 2022 ``.mat`` file into a canonical dataset folder under ``out_dir``.

    Args:
        mat_path: Path to the Kilosort2 ``.mat`` file.
        out_dir: Output root directory; writes into ``out_dir / mat_path.stem``.
        epoch_s: Fixed epoch duration in seconds.
        min_epochs: Minimum required epoch count before skipping conversion.
        transforms: When True, include monotone rate-transform columns in ``responses.csv``.

    Returns:
        Dictionary describing the converted recording, written paths, and next CLI commands
        (or ``skipped=True`` with ``reason`` when ``n_epochs < min_epochs``).
    """
    stem = mat_path.stem
    organoid = CHIP_TO_ORGANOID.get(stem.split("_")[-1], "prep0")
    mat_data = sio.loadmat(mat_path, struct_as_record=False, squeeze_me=True)
    built = build_recording_tables(
        mat_data["units"],
        float(mat_data["fs"]),
        epoch_s,
        stem=stem,
        preparation_id=organoid,
        transforms=transforms,
    )
    n_epochs = int(built["n_epochs"])
    fb_note = " (positional unit_id fallback)" if built["unit_id_fallback"] else ""
    if n_epochs < min_epochs:
        return {
            "stem": stem,
            "organoid": organoid,
            "duration_s": built["duration_s"],
            "n_epochs": n_epochs,
            "skipped": True,
            "reason": f"n_epochs={n_epochs} < min_epochs={min_epochs}{fb_note}",
        }

    rec_dir = out_dir / stem
    rec_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "units": rec_dir / "units.csv",
        "responses": rec_dir / "responses.csv",
        "spikes": rec_dir / "spikes.csv",
        "preparation": rec_dir / "preparation.json",
        "conditions": rec_dir / "conditions.json",
    }
    for key in ("units", "responses", "spikes"):
        built[key].to_csv(paths[key], index=False)

    prep_payload = {
        "preparation_id": organoid,
        "species": "Homo sapiens",
        "preparation_type": "organoid",
        "age_days": 210,
        "age_basis": "days_post_differentiation",
        "line_or_donor_id": "F12442.4",
        "instrument": "MaxOne",
        "raw_data_url": RAW_DATA_URL,
    }
    cond_payload = {"spontaneous": dict.fromkeys(("protocol", "compound", "dose", "dose_unit", "vehicle"))}
    paths["preparation"].write_text(json.dumps(prep_payload, indent=2) + "\n", encoding="utf-8")
    paths["conditions"].write_text(json.dumps(cond_payload, indent=2) + "\n", encoding="utf-8")

    measures_arg = ",".join(TRANSFORM_MEASURES) if transforms else "firing_rate_hz"
    common = [
        str(paths["units"]),
        str(paths["responses"]),
        "--measures",
        measures_arg,
        "--post-stim-window-s",
        str(epoch_s),
        "--load-duration-s",
        "0",
        "--preparation",
        str(paths["preparation"]),
        "--conditions",
        str(paths["conditions"]),
        "--spikes",
        str(paths["spikes"]),
    ]
    return {
        "stem": stem,
        "organoid": organoid,
        "duration_s": built["duration_s"],
        "n_epochs": n_epochs,
        "skipped": False,
        "paths": paths,
        "check_cmd": shlex.join(["rrb-check", *common]),
        "report_cmd": shlex.join(["rrb-report", *common, "--out", str(rec_dir / "report")]),
    }


def main(argv: list[str] | None = None) -> int:
    """Convert Sharf 2022 Kilosort2 recordings into benchmark folders and print CLI commands."""
    parser = argparse.ArgumentParser(description="Convert Sharf 2022 .mat recordings into benchmark tables.")
    parser.add_argument("--recording", type=Path, default=None, help="Single .mat recording to convert.")
    parser.add_argument("--root", type=Path, default=Path("data/sharf2022/kilosort2"), help="Dataset root.")
    parser.add_argument("--out", type=Path, default=Path("output/sharf2022"), help="Output directory.")
    parser.add_argument("--epoch-s", type=float, default=5.0, help="Fixed epoch duration (s).")
    parser.add_argument("--min-epochs", type=int, default=20, help="Minimum epochs required.")
    parser.add_argument("--transforms", action="store_true", help="Include monotone rate transforms.")
    args = parser.parse_args(argv)

    targets = [args.recording] if args.recording is not None else [args.root / r for r in RECORDING_RELPATHS]
    args.out.mkdir(parents=True, exist_ok=True)
    for mat_path in targets:
        info = convert_recording(
            mat_path, args.out, epoch_s=args.epoch_s, min_epochs=args.min_epochs, transforms=args.transforms
        )
        if info["skipped"]:
            print(f"# skipped {info['stem']} ({info['organoid']}): {info['reason']}")
        else:
            print(info["check_cmd"])
            print(info["report_cmd"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
