"""Template for converting one recording session into benchmark files.

Read two things in a lab's format description before writing an adapter:
1. At least 2 s of recording after each stimulus (min-dataset-6).
2. At least 8 units (min-dataset-3).

By design, an adapter contains no analysis: it extracts unit IDs, spike timestamps,
stimulus onsets, and condition labels on the recording clock in seconds, and hands
them to ``writer.write_dataset``.
"""

from __future__ import annotations

import argparse
import shlex
from pathlib import Path

import numpy as np

from recovery_reliability_benchmark.measures import AnalysisParams
from recovery_reliability_benchmark.writer import write_dataset


def load_recording(
    path: Path,
) -> tuple[list[str], dict[str, np.ndarray], np.ndarray, list[str]]:
    """Return ``(unit_ids, spike_times_s, onsets_s, conditions)`` on the recording clock."""
    raise NotImplementedError(f"Fill in load_recording() for {path}.")


def main(argv: list[str] | None = None) -> int:
    """Convert a recording via ``load_recording`` and print next CLI commands."""
    parser = argparse.ArgumentParser(description="Convert a recording into benchmark files.")
    parser.add_argument("recording", type=Path, help="Path to the raw or sorted recording.")
    parser.add_argument("--out", type=Path, default=Path("dataset"), help="Output folder.")
    parser.add_argument("--post-stim-window-s", type=float, default=2.0, help="Window (s).")
    args = parser.parse_args(argv)

    unit_ids, spike_times_s, onsets_s, conditions = load_recording(args.recording)
    analysis = AnalysisParams(post_stim_window_s=args.post_stim_window_s)
    paths = write_dataset(args.out, unit_ids, spike_times_s, onsets_s, conditions, analysis)
    common = [
        str(paths["units"]),
        str(paths["trials"]),
        "--spikes",
        str(paths["spikes"]),
        "--analysis",
        str(paths["analysis"]),
    ]
    print(shlex.join(["rrb-check", *common]))
    report_args = ["--measures", "t_half_excess,excess_per_trial", "--out", str(args.out / "report")]
    print(shlex.join(["rrb-report", *common, *report_args]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
