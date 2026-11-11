"""Tests for rrb-report, summary.md generation, and the two-condition example."""

from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.contract import read_tables
from recovery_reliability_benchmark.metadata import load_conditions
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run, run_with_inputs
from recovery_reliability_benchmark.summary import build_summary
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_spike_trains
from recovery_reliability_benchmark.text_report import print_evaluate_human
from recovery_reliability_benchmark.writer import read_dataset, write_dataset

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


def test_two_conditions_build_summary_notes() -> None:
    units, trials, spikes, analysis = read_dataset(TWO_COND_DIR)
    conditions = load_conditions(TWO_COND_DIR / "conditions.json")
    result = run(
        units,
        trials,
        ["t_half_excess", "excess_per_trial", "t_return"],
        conditions=conditions,
        spikes=spikes,
        analysis=analysis,
        n_perm=200,
    )
    summary_lines = build_summary(result).splitlines()

    tr_row = next(line for line in summary_lines if line.startswith("| t_return |"))
    assert tr_row.endswith("| sensitivity at chance; censored: control 8, slowed 11 |")

    ref_row = next(line for line in summary_lines if line.startswith("| baseline_hz (reference) |"))
    assert ref_row.endswith("| sensitivity at chance |")

    the_row = next(line for line in summary_lines if line.startswith("| t_half_excess |"))
    the_cells = [c.strip() for c in the_row.strip("|").split("|")]
    assert the_cells[7] == "—"


def test_identical_recovery_across_units_flags_reliability_at_chance(tmp_path: Path) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [exponential_recovery(5.0, 100.0, 0.2) for _ in range(30)]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=20, params=params, isi_s=5.0, seed=0)
    unit_ids = [f"u{i:02d}" for i in range(30)]
    spike_times_s = dict(zip(unit_ids, trains, strict=True))
    ds_dir = tmp_path / "identical_units"
    write_dataset(ds_dir, unit_ids, spike_times_s, onsets_s, ["baseline"] * 20, params)
    units, trials, spikes, analysis = read_dataset(ds_dir)

    result = run(units, trials, ["t_half_excess"], spikes=spikes, analysis=analysis, n_perm=50, seed=0)
    summary_lines = build_summary(result).splitlines()
    the_row = next(line for line in summary_lines if line.startswith("| t_half_excess |"))
    the_cells = [c.strip() for c in the_row.strip("|").split("|")]
    assert "reliability at chance" in the_cells[7]

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluate_human(result)
    the_human_line = next(line for line in buf.getvalue().splitlines() if line.startswith("t_half_excess:"))
    assert "[reliability at chance]" in the_human_line


def _load_undefined_dataset_writer() -> Any:
    spec = importlib.util.spec_from_file_location(
        "test_strict_json",
        Path(__file__).with_name("test_strict_json.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.write_undefined_measure_dataset


def test_undefined_measure_summary_cells_and_notes(tmp_path: Path) -> None:
    write_undef = _load_undefined_dataset_writer()
    ds_dir = tmp_path / "undef_ds"
    write_undef(ds_dir)
    units, trials, spikes, analysis = read_dataset(ds_dir)

    result = run(
        units,
        trials,
        ["t_return", "t_half_excess"],
        spikes=spikes,
        analysis=analysis,
        n_perm=20,
    )
    summary_text = build_summary(result)
    tr_row = next(line for line in summary_text.splitlines() if line.startswith("| t_return |"))
    tr_cells = [c.strip() for c in tr_row.strip("|").split("|")]
    assert tr_cells[1] == "undefined"
    assert tr_cells[2] == "n/a"
    assert "no variation across units" in tr_cells[7]
    assert "censored: 12 units" in tr_cells[7]
    assert "reliability at chance" not in tr_cells[7]
    assert "t_return: reliability is undefined because every scored unit has the same value." in summary_text

    buf = io.StringIO()
    with redirect_stdout(buf):
        print_evaluate_human(result)
    tr_human_line = next(line for line in buf.getvalue().splitlines() if line.startswith("t_return:"))
    assert "[no variation across units]" in tr_human_line


def test_figure_note_above_four_measures(tmp_path: Path) -> None:
    six_out = tmp_path / "six_measures"
    rc_six = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(EXAMPLES_DIR / "trials_responses.csv"),
            "--spikes",
            str(EXAMPLES_DIR / "spikes.csv"),
            "--analysis",
            str(EXAMPLES_DIR / "analysis.json"),
            "--measures",
            "t_half_excess,excess_per_trial,t_return,t_half_peak,peak_rate,spikes_per_trial",
            "--n-perm",
            "20",
            "--out",
            str(six_out),
        ]
    )
    assert rc_six == 0
    six_summary = (six_out / "summary.md").read_text(encoding="utf-8")
    if importlib.util.find_spec("matplotlib") is not None:
        assert "Figure shows the first 4 of 6 measures." in six_summary

    two_out = tmp_path / "two_measures"
    rc_two = report_main(
        [
            str(EXAMPLES_DIR / "units.csv"),
            str(EXAMPLES_DIR / "trials_responses.csv"),
            "--spikes",
            str(EXAMPLES_DIR / "spikes.csv"),
            "--analysis",
            str(EXAMPLES_DIR / "analysis.json"),
            "--measures",
            "t_half_excess,excess_per_trial",
            "--n-perm",
            "20",
            "--out",
            str(two_out),
        ]
    )
    assert rc_two == 0
    two_summary = (two_out / "summary.md").read_text(encoding="utf-8")
    assert "Figure shows the first 4 of" not in two_summary


def test_positive_control_line_wording(two_conditions_report_dir: Path) -> None:
    summary_text = (two_conditions_report_dir / "summary.md").read_text(encoding="utf-8")
    assert "Positive control (split-half estimator on a synthetic table): passed (" in summary_text

    doc = json.loads((two_conditions_report_dir / "evaluate.json").read_text(encoding="utf-8"))
    doc["positive_control"]["passed"] = False
    doc["status"] = "positive_control_failed"
    failed_summary = build_summary(doc)
    assert "Positive control (split-half estimator on a synthetic table): failed (" in failed_summary
