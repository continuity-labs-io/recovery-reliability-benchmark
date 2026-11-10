"""CLI tests for the Recovery Reliability Benchmark data contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from recovery_reliability_benchmark.cli import check_main as main
from recovery_reliability_benchmark.cli import evaluate_main
from recovery_reliability_benchmark.synthetic import make_tables
from recovery_reliability_benchmark.thresholds import main as thresholds_main


def _write_csvs(tmp_path: Path, **kwargs: object) -> tuple[Path, Path]:
    units, responses = make_tables(**kwargs)  # type: ignore[arg-type]
    units_csv = tmp_path / "units.csv"
    responses_csv = tmp_path / "responses.csv"
    units.to_csv(units_csv, index=False)
    responses.to_csv(responses_csv, index=False)
    return units_csv, responses_csv


def test_cli_conforming_exit_0(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path)
    rc = main(
        [str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "conforming (SPEC v1.1)"


def test_cli_fully_conforming(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_units=30, n_trials=20)
    rc = main(
        [str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "fully_conforming (SPEC v1.1)"


def test_cli_violation_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_trials=6)
    rc = main(
        [str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert (
        captured.out
        == "min-dataset-2 failed. At most 6 trials in any condition (condition 'A'), requires 10.\n"
    )


def test_cli_window_violation_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path)
    rc = main(
        [str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "0.4"]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == "min-dataset-6 failed. Post-stimulus window 0.4 s, requires 2.0 s.\n"


@pytest.mark.parametrize("bad_window", ["-0.1", "0", "nan"])
def test_cli_nonpositive_or_nan_window_exit_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], bad_window: str
) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path)
    for entry in (main, evaluate_main):
        rc = entry(
            [
                str(units_csv),
                str(responses_csv),
                "--measures",
                "tau,amplitude",
                "--post-stim-window-s",
                bad_window,
            ]
        )
        captured = capsys.readouterr()
        assert rc == 2
        assert "error: post_stim_window_s must be finite and > 0" in captured.err
        assert captured.out == ""


def test_cli_missing_file_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, responses_csv = _write_csvs(tmp_path)
    missing_units = tmp_path / "does_not_exist.csv"
    rc = main(
        [str(missing_units), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"]
    )
    captured = capsys.readouterr()
    assert rc == 2
    assert "error:" in captured.err
    assert captured.out == ""


def test_cli_json_pass(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_units=30, n_trials=20)
    rc = main(
        [
            str(units_csv),
            str(responses_csv),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    doc = json.loads(captured.out)
    assert doc["status"] == "fully_conforming"
    assert doc["spec_version"] == "1.1"
    assert doc["result"]["n_units"] == 30
    assert doc["inputs"]["units"]["sha256"] == hashlib.sha256(units_csv.read_bytes()).hexdigest()
    assert doc["arguments"]["measures"] == ["tau", "amplitude"]


def test_cli_json_violation(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_trials=6)
    rc = main(
        [
            str(units_csv),
            str(responses_csv),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 1
    doc = json.loads(captured.out)
    assert doc["status"] == "violation"
    assert doc["violation"]["requirement"] == "min-dataset-2"
    assert doc["violation"]["found"] == 6
    assert "result" not in doc


def test_examples_are_fully_conforming(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    rc = main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "responses.csv"),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "fully_conforming (SPEC v1.1)"


def test_module_invocation() -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "recovery_reliability_benchmark.contract",
            str(examples_dir / "units.csv"),
            str(examples_dir / "responses.csv"),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert proc.stdout.splitlines()[0] == "fully_conforming (SPEC v1.1)"


def test_help_flags() -> None:
    for entry in (main, evaluate_main, thresholds_main):
        with pytest.raises(SystemExit) as exc_info:
            entry(["--help"])
        assert exc_info.value.code == 0


def test_cli_evaluate_spikes_analysis_json(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    rc = evaluate_main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "trials_responses.csv"),
            "--spikes",
            str(examples_dir / "spikes.csv"),
            "--analysis",
            str(examples_dir / "analysis.json"),
            "--measures",
            "t_return,t_half_peak,peak_rate,spikes_per_trial",
            "--n-perm",
            "50",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    doc = json.loads(captured.out)
    assert doc["status"] == "ok"
    assert doc["result"]["parameters"]["path"] == "spikes"
    assert "analysis" in doc["inputs"]

    rc_human = evaluate_main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "trials_responses.csv"),
            "--spikes",
            str(examples_dir / "spikes.csv"),
            "--analysis",
            str(examples_dir / "analysis.json"),
            "--measures",
            "t_return,t_half_peak,peak_rate,spikes_per_trial",
            "--n-perm",
            "20",
        ]
    )
    captured_human = capsys.readouterr()
    assert rc_human == 0
    fp12 = doc["result"]["parameters"]["analysis_fingerprint"][:12]
    assert f"path: spikes, analysis {fp12}" in captured_human.out
    assert "units scored 30 of 30" in captured_human.out
    assert "reference (baseline_hz): rho=" in captured_human.out


def test_cli_analysis_requires_spikes_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    for entry in (evaluate_main, main):
        rc = entry(
            [
                str(examples_dir / "units.csv"),
                str(examples_dir / "trials_responses.csv"),
                "--analysis",
                str(examples_dir / "analysis.json"),
                "--measures",
                "t_return",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 2
        assert "--analysis requires --spikes" in captured.err


def test_cli_mismatched_post_stim_window_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    for entry in (evaluate_main, main):
        rc = entry(
            [
                str(examples_dir / "units.csv"),
                str(examples_dir / "trials_responses.csv"),
                "--spikes",
                str(examples_dir / "spikes.csv"),
                "--analysis",
                str(examples_dir / "analysis.json"),
                "--measures",
                "t_return",
                "--post-stim-window-s",
                "3.5",
            ]
        )
        captured = capsys.readouterr()
        assert rc == 2
        assert "3.5" in captured.err and "2.0" in captured.err


def test_cli_check_analysis_reports_pre_stim_window(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    rc = main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "trials_responses.csv"),
            "--spikes",
            str(examples_dir / "spikes.csv"),
            "--analysis",
            str(examples_dir / "analysis.json"),
            "--measures",
            "t_return,t_half_peak,peak_rate,spikes_per_trial",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "pre_stim_window_s: 1.0" in captured.out
    assert "analysis_fingerprint:" in captured.out

    rc_json = main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "trials_responses.csv"),
            "--spikes",
            str(examples_dir / "spikes.csv"),
            "--analysis",
            str(examples_dir / "analysis.json"),
            "--json",
        ]
    )
    captured_json = capsys.readouterr()
    assert rc_json == 0
    doc = json.loads(captured_json.out)
    assert doc["status"] == "fully_conforming"
    assert doc["result"]["pre_stim_window_s"] == 1.0
    assert "analysis_fingerprint" in doc["result"]


def test_cli_evaluate_two_condition_sensitivity_human(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    units_csv, responses_csv = _write_csvs(
        tmp_path,
        n_units=30,
        n_trials=20,
        conditions=("control", "slowed"),
        reliability=0.8,
        condition_offsets={"slowed": 3.0},
        seed=0,
    )
    rc = evaluate_main(
        [
            str(units_csv),
            str(responses_csv),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--n-perm",
            "50",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "sensitivity control|slowed:" in captured.out
