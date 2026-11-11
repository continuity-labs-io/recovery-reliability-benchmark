"""Tests for rrb-report, summary.md generation, and the two-condition example."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from recovery_reliability_benchmark.contract import read_tables
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run, run_with_inputs

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
TWO_COND_DIR = EXAMPLES_DIR / "two_conditions"


def _run_two_conditions_report(out_dir: Path) -> int:
    return report_main(
        [
            str(TWO_COND_DIR / "units.csv"),
            str(TWO_COND_DIR / "trials_responses.csv"),
            "--spikes",
            str(TWO_COND_DIR / "spikes.csv"),
            "--analysis",
            str(TWO_COND_DIR / "analysis.json"),
            "--conditions",
            str(TWO_COND_DIR / "conditions.json"),
            "--measures",
            "t_half_excess,excess_per_trial,t_return",
            "--n-perm",
            "200",
            "--out",
            str(out_dir),
        ]
    )


@pytest.fixture(scope="module")
def two_conditions_report_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out_dir = tmp_path_factory.mktemp("two_conditions_report")
    rc = _run_two_conditions_report(out_dir)
    assert rc == 0
    return out_dir


def test_report_writes_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "report"
    rc = _run_two_conditions_report(out_dir)
    assert rc == 0
    assert (out_dir / "evaluate.json").is_file()
    assert (out_dir / "summary.md").is_file()
    if importlib.util.find_spec("matplotlib") is not None:
        assert (out_dir / "halves.png").is_file()
        assert (out_dir / "halves.png").stat().st_size > 0


def test_two_axis_numbers(two_conditions_report_dir: Path) -> None:
    doc = json.loads((two_conditions_report_dir / "evaluate.json").read_text(encoding="utf-8"))
    the = doc["measures"]["t_half_excess"]
    assert the["headline_kind"] == "pooled_centered"
    assert the["headline"]["rho"] > 0.95
    assert the["sensitivity"]["control|slowed"]["median_abs_z"] > 2.5

    ref = doc["reference"]
    assert ref["headline"]["rho"] > 0.95
    assert ref["sensitivity"]["control|slowed"]["median_abs_z"] < 1.0

    tr = doc["measures"]["t_return"]
    assert 0.5 < tr["headline"]["rho"] < 0.9


def test_summary_rows(two_conditions_report_dir: Path) -> None:
    summary_text = (two_conditions_report_dir / "summary.md").read_text(encoding="utf-8")
    lines = summary_text.splitlines()
    assert any(line.startswith("| t_half_excess |") for line in lines)
    assert any(line.startswith("| baseline_hz (reference) |") for line in lines)
    assert any(line.startswith("baseline_hz is the reference row") for line in lines)
    assert "protocol: control=" in summary_text
    assert "Between control and slowed the typical unit moved" in summary_text


def test_one_condition_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "one_cond"
    rc = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(EXAMPLES_DIR / "trials_responses.csv"),
            "--spikes",
            str(EXAMPLES_DIR / "spikes.csv"),
            "--analysis",
            str(EXAMPLES_DIR / "analysis.json"),
            "--conditions",
            str(EXAMPLES_DIR / "conditions.json"),
            "--measures",
            "t_half_excess,excess_per_trial",
            "--n-perm",
            "50",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    summary_text = (out_dir / "summary.md").read_text(encoding="utf-8")
    for prefix in ("| t_half_excess |", "| excess_per_trial |", "| baseline_hz (reference) |"):
        row = next(line for line in summary_text.splitlines() if line.startswith(prefix))
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert cells[5] == "n/a (one condition)"
        assert cells[6] == "n/a (one condition)"


def test_tables_path_report(tmp_path: Path) -> None:
    out_dir = tmp_path / "tables"
    rc = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(EXAMPLES_DIR / "responses.csv"),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--n-perm",
            "50",
            "--out",
            str(out_dir),
            "--title",
            "Tables Example Report",
        ]
    )
    assert rc == 0
    summary_text = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert summary_text.splitlines()[0] == "# Tables Example Report"
    assert "The reference row requires the spikes path." in summary_text
    assert "| baseline_hz (reference) |" not in summary_text


def test_violation_report(tmp_path: Path) -> None:
    trials = pd.read_csv(EXAMPLES_DIR / "trials_responses.csv")
    trials.loc[0, "stim_time_ns"] = int(0.5 * 1e9)
    bad_trials_csv = tmp_path / "bad_trials.csv"
    trials.to_csv(bad_trials_csv, index=False)

    out_dir = tmp_path / "violation_report"
    rc = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(bad_trials_csv),
            "--spikes",
            str(EXAMPLES_DIR / "spikes.csv"),
            "--analysis",
            str(EXAMPLES_DIR / "analysis.json"),
            "--measures",
            "t_return",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 1
    summary_path = out_dir / "summary.md"
    assert summary_path.is_file()
    summary_text = summary_path.read_text(encoding="utf-8")
    assert "min-dataset-7" in summary_text
    assert "0.5" in summary_text
    assert "1.0" in summary_text


def test_missing_matplotlib(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)

    out_dir = tmp_path / "no_mpl"
    rc = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(EXAMPLES_DIR / "responses.csv"),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--n-perm",
            "20",
            "--out",
            str(out_dir),
        ]
    )
    assert rc == 0
    summary_text = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "Figure skipped" in summary_text
    assert not (out_dir / "halves.png").exists()


def test_run_with_inputs_matches_run() -> None:
    units, responses = read_tables(EXAMPLES_DIR / "units.csv", EXAMPLES_DIR / "responses.csv")
    res_only = run(units, responses, ["tau", "amplitude"], post_stim_window_s=2.0, n_perm=20, seed=42)
    res_pair, inputs = run_with_inputs(
        units, responses, ["tau", "amplitude"], post_stim_window_s=2.0, n_perm=20, seed=42
    )
    assert res_pair == res_only
    assert inputs.path == "responses"
    assert len(inputs.halves) == 30


def _run_quick_spikes_report(
    out_dir: Path, *, spikes_path: Path | None = None, trials_path: Path | None = None
) -> int:
    return report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(trials_path or (EXAMPLES_DIR / "trials_responses.csv")),
            "--spikes",
            str(spikes_path or (EXAMPLES_DIR / "spikes.csv")),
            "--analysis",
            str(EXAMPLES_DIR / "analysis.json"),
            "--measures",
            "t_return",
            "--n-perm",
            "20",
            "--out",
            str(out_dir),
        ]
    )


def test_violation_clears_previous_report_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "shared_out"
    assert _run_quick_spikes_report(out_dir) == 0
    assert (out_dir / "evaluate.json").is_file()
    assert (out_dir / "summary.md").is_file()

    trials = pd.read_csv(EXAMPLES_DIR / "trials_responses.csv")
    trials.loc[0, "stim_time_ns"] = int(0.5 * 1e9)
    bad_trials_csv = tmp_path / "bad_trials.csv"
    trials.to_csv(bad_trials_csv, index=False)

    assert _run_quick_spikes_report(out_dir, trials_path=bad_trials_csv) == 1
    assert (out_dir / "summary.md").is_file()
    assert "min-dataset-7" in (out_dir / "summary.md").read_text(encoding="utf-8")
    assert not (out_dir / "evaluate.json").exists()
    assert not (out_dir / "halves.png").exists()


def test_input_error_clears_report_files_and_keeps_unrelated_file(tmp_path: Path) -> None:
    out_dir = tmp_path / "shared_out"
    out_dir.mkdir()
    keep_file = out_dir / "notes.txt"
    keep_file.write_text("unrelated file\n", encoding="utf-8")

    assert _run_quick_spikes_report(out_dir) == 0
    assert (out_dir / "evaluate.json").is_file()
    assert (out_dir / "summary.md").is_file()

    missing_spikes = tmp_path / "missing_spikes.csv"
    assert _run_quick_spikes_report(out_dir, spikes_path=missing_spikes) == 2
    assert not (out_dir / "evaluate.json").exists()
    assert not (out_dir / "summary.md").exists()
    assert not (out_dir / "halves.png").exists()
    assert out_dir.is_dir()
    assert keep_file.read_text(encoding="utf-8") == "unrelated file\n"


def test_input_error_does_not_create_missing_out_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "absent_report_dir"
    missing_spikes = tmp_path / "missing_spikes.csv"
    assert _run_quick_spikes_report(out_dir, spikes_path=missing_spikes) == 2
    assert not out_dir.exists()


def test_out_pointing_at_regular_file_exits_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    regular_file = tmp_path / "existing_file.txt"
    regular_file.write_text("do not touch\n", encoding="utf-8")
    capsys.readouterr()

    rc = _run_quick_spikes_report(regular_file)
    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert captured.err == f"error: --out {regular_file} is not a directory.\n"
    assert regular_file.is_file()
    assert regular_file.read_text(encoding="utf-8") == "do not touch\n"


def test_run_without_matplotlib_clears_previous_halves_figure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("matplotlib")
    out_dir = tmp_path / "mpl_toggle"
    assert _run_quick_spikes_report(out_dir) == 0
    assert (out_dir / "halves.png").is_file()

    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setitem(sys.modules, "matplotlib.pyplot", None)

    assert _run_quick_spikes_report(out_dir) == 0
    assert not (out_dir / "halves.png").exists()
    assert "Figure skipped" in (out_dir / "summary.md").read_text(encoding="utf-8")
