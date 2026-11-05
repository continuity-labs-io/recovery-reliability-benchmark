"""CLI tests for the Recovery Reliability Benchmark data contract."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from recovery_reliability_benchmark.contract import main
from recovery_reliability_benchmark.evaluate import main as evaluate_main
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
    rc = main([str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "conforming (SPEC v1.0)"


def test_cli_fully_conforming(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_units=30, n_trials=20)
    rc = main([str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"])
    captured = capsys.readouterr()
    assert rc == 0
    assert captured.out.splitlines()[0] == "fully_conforming (SPEC v1.0)"


def test_cli_violation_exit_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path, n_trials=6)
    rc = main([str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == "MD-2 failed. At most 6 trials in any condition (condition 'A'), requires 10.\n"


def test_cli_window_violation_message(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    units_csv, responses_csv = _write_csvs(tmp_path)
    rc = main([str(units_csv), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "0.4"])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out == "MD-6 failed. Post-stimulus window 0.4 s, requires 2.0 s.\n"


def test_cli_missing_file_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, responses_csv = _write_csvs(tmp_path)
    missing_units = tmp_path / "does_not_exist.csv"
    rc = main([str(missing_units), str(responses_csv), "--measures", "tau,amplitude", "--post-stim-window-s", "2.0"])
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
    assert doc["spec_version"] == "1.0"
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
    assert doc["violation"]["requirement"] == "MD-2"
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
    assert captured.out.splitlines()[0] == "fully_conforming (SPEC v1.0)"


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
    assert proc.stdout.splitlines()[0] == "fully_conforming (SPEC v1.0)"


def test_help_flags() -> None:
    for entry in (main, evaluate_main, thresholds_main):
        with pytest.raises(SystemExit) as exc_info:
            entry(["--help"])
        assert exc_info.value.code == 0

