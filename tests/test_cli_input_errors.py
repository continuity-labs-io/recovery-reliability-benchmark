"""Tests that CLI argument errors and undecodable integer columns exit 2 with one error line."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.cli import check_main, evaluate_main
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.spikes import halves_from_spikes
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_spike_trains, make_tables


@pytest.fixture(scope="module")
def spikes_fixture() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [exponential_recovery(5.0, 100.0, float(tau)) for tau in np.geomspace(0.05, 0.5, 12)]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=20, params=params, isi_s=5.0, seed=0)
    unit_ids = [f"u{i:02d}" for i in range(12)]
    units = pd.DataFrame(
        {"unit_id": unit_ids, "recording_id": "rec0", "session_id": "sess0", "preparation_id": "prep0"}
    )
    trials = pd.DataFrame(
        {
            "trial_index": pd.array(range(20), dtype="Int64"),
            "stim_time_ns": pd.array([int(round(float(t) * 1e9)) for t in onsets_s], dtype="Int64"),
            "condition": "baseline",
        }
    )
    spikes = pd.DataFrame(
        [
            (uid, int(round(float(t) * 1e9)))
            for uid, train in zip(unit_ids, trains, strict=True)
            for t in train
        ],
        columns=["unit_id", "spike_time_ns"],
    ).astype({"spike_time_ns": "Int64"})
    return units, trials, spikes, params


def _write_spikes_dataset(
    tmp_path: Path,
    units: pd.DataFrame,
    trials: pd.DataFrame,
    spikes: pd.DataFrame,
) -> tuple[Path, Path, Path, Path]:
    units_path = tmp_path / "units.csv"
    responses_path = tmp_path / "trials.csv"
    spikes_path = tmp_path / "spikes.csv"
    analysis_path = tmp_path / "analysis.json"
    units.to_csv(units_path, index=False)
    trials.to_csv(responses_path, index=False)
    spikes.to_csv(spikes_path, index=False)
    analysis_path.write_text('{"post_stim_window_s": 2.0}', encoding="utf-8")
    return units_path, responses_path, spikes_path, analysis_path


def _assert_single_error_line(captured: pytest.CaptureResult[str]) -> str:
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    assert captured.out == ""
    err_lines = captured.err.splitlines()
    assert len(err_lines) == 1
    assert err_lines[0].startswith("error: ")
    return err_lines[0]


def test_decimal_spike_time_ns_exits_2(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, _params = spikes_fixture
    bad_spikes = spikes.assign(spike_time_ns=spikes["spike_time_ns"].astype(float) / 1e9)
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, trials, bad_spikes
    )
    base = [
        str(units_path),
        str(responses_path),
        "--spikes",
        str(spikes_path),
        "--analysis",
        str(analysis_path),
    ]
    eval_flags = ["--measures", "t_half_excess", "--n-perm", "20"]
    for command, extra in (
        (check_main, []),
        (evaluate_main, eval_flags),
        (report_main, [*eval_flags, "--out", str(tmp_path / "report")]),
    ):
        assert command([*base, *extra]) == 2
        line = _assert_single_error_line(capsys.readouterr())
        assert str(spikes_path) in line
        assert line.endswith("spike_time_ns must be whole numbers in nanoseconds.")


def test_decimal_stim_time_ns_spikes_path_exits_2(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, _params = spikes_fixture
    bad_trials = trials.assign(stim_time_ns=trials["stim_time_ns"].astype(float) / 1e9 + 0.5)
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, bad_trials, spikes
    )
    base = [
        str(units_path),
        str(responses_path),
        "--spikes",
        str(spikes_path),
        "--analysis",
        str(analysis_path),
    ]
    eval_flags = ["--measures", "t_half_excess", "--n-perm", "20"]
    for command, extra in (
        (check_main, []),
        (evaluate_main, eval_flags),
        (report_main, [*eval_flags, "--out", str(tmp_path / "report")]),
    ):
        assert command([*base, *extra]) == 2
        line = _assert_single_error_line(capsys.readouterr())
        assert str(responses_path) in line
        assert line.endswith(
            "trial_index and stim_time_ns must be whole numbers (stim_time_ns in nanoseconds)."
        )


def test_decimal_stim_time_ns_tables_path_exits_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, responses = make_tables(n_units=12, n_trials=20, seed=0)
    bad_responses = responses.assign(stim_time_ns=responses["stim_time_ns"].astype(float) / 1e9 + 0.5)
    units_path = tmp_path / "units.csv"
    responses_path = tmp_path / "responses.csv"
    units.to_csv(units_path, index=False)
    bad_responses.to_csv(responses_path, index=False)
    args = [str(units_path), str(responses_path), "--measures", "tau", "--post-stim-window-s", "2.0"]
    for command in (check_main, evaluate_main):
        assert command(args) == 2
        line = _assert_single_error_line(capsys.readouterr())
        assert str(responses_path) in line
        assert line.endswith(
            "trial_index and stim_time_ns must be whole numbers (stim_time_ns in nanoseconds)."
        )


def test_decimal_trial_index_tables_path_exits_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, responses = make_tables(n_units=12, n_trials=20, seed=0)
    bad_responses = responses.assign(trial_index=responses["trial_index"].astype(float) + 0.5)
    units_path = tmp_path / "units.csv"
    responses_path = tmp_path / "responses.csv"
    units.to_csv(units_path, index=False)
    bad_responses.to_csv(responses_path, index=False)
    args = [str(units_path), str(responses_path), "--measures", "tau", "--post-stim-window-s", "2.0"]
    for command in (check_main, evaluate_main):
        assert command(args) == 2
        line = _assert_single_error_line(capsys.readouterr())
        assert str(responses_path) in line
        assert line.endswith(
            "trial_index and stim_time_ns must be whole numbers (stim_time_ns in nanoseconds)."
        )


def test_whole_float_trial_index_accepted_on_spikes_path(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, _params = spikes_fixture
    float_trials = trials.assign(trial_index=trials["trial_index"].astype(float))
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, float_trials, spikes
    )
    assert "0.0," in responses_path.read_text(encoding="utf-8")
    rc = check_main(
        [
            str(units_path),
            str(responses_path),
            "--spikes",
            str(spikes_path),
            "--analysis",
            str(analysis_path),
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("bad_n_perm", [0, -5])
def test_nonpositive_n_perm_cli_exits_2(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    bad_n_perm: int,
) -> None:
    units, trials, spikes, _params = spikes_fixture
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, trials, spikes
    )
    base = [
        str(units_path),
        str(responses_path),
        "--spikes",
        str(spikes_path),
        "--analysis",
        str(analysis_path),
        "--measures",
        "t_half_excess",
        "--n-perm",
        str(bad_n_perm),
    ]
    expected_line = f"error: n_perm must be >= 1, got {bad_n_perm}."
    assert evaluate_main(base) == 2
    assert _assert_single_error_line(capsys.readouterr()) == expected_line

    report_out = tmp_path / f"report_{bad_n_perm}"
    assert report_main([*base, "--out", str(report_out)]) == 2
    assert _assert_single_error_line(capsys.readouterr()) == expected_line
    assert not report_out.exists()


def test_run_nonpositive_n_perm_raises_value_error(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
) -> None:
    units_tables, responses_tables = make_tables(n_units=12, n_trials=20, seed=0)
    with pytest.raises(ValueError, match="n_perm must be >= 1, got 0"):
        run(units_tables, responses_tables, ["tau"], post_stim_window_s=2.0, n_perm=0)

    units_spikes, trials_spikes, spikes, params = spikes_fixture
    with pytest.raises(ValueError, match="n_perm must be >= 1, got 0"):
        run(units_spikes, trials_spikes, ["t_half_excess"], spikes=spikes, analysis=params, n_perm=0)


def test_unknown_spikes_measure_cli_exits_2(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, params = spikes_fixture
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, trials, spikes
    )
    with pytest.raises(ValueError) as halves_exc:
        halves_from_spikes(units, trials, spikes, params, ["nope"])
    expected_line = f"error: {halves_exc.value}"

    base = [
        str(units_path),
        str(responses_path),
        "--spikes",
        str(spikes_path),
        "--analysis",
        str(analysis_path),
        "--measures",
        "t_half_excess,nope",
        "--n-perm",
        "20",
    ]
    assert evaluate_main(base) == 2
    line_eval = _assert_single_error_line(capsys.readouterr())
    assert line_eval.startswith("error: Unknown measure 'nope'. Available measures: ")
    assert line_eval == expected_line

    report_out = tmp_path / "report_unknown_measure"
    assert report_main([*base, "--out", str(report_out)]) == 2
    line_report = _assert_single_error_line(capsys.readouterr())
    assert line_report.startswith("error: Unknown measure 'nope'. Available measures: ")
    assert line_report == expected_line
    assert not report_out.exists()


def test_argument_errors_precede_data_errors(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, params = spikes_fixture
    trials_no_condition = trials.drop(columns=["condition"])

    with pytest.raises(ValueError, match="Unknown measure 'nope'"):
        run(units, trials_no_condition, ["nope"], spikes=spikes, analysis=params, n_perm=20)

    with pytest.raises(ValueError, match="n_perm must be >= 1, got 0"):
        run(units, trials_no_condition, ["t_half_excess"], spikes=spikes, analysis=params, n_perm=0)

    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, trials_no_condition, spikes.assign(spike_time_ns=spikes["spike_time_ns"] / 1e9)
    )
    bad_args = [
        str(units_path),
        str(responses_path),
        "--spikes",
        str(spikes_path),
        "--analysis",
        str(analysis_path),
        "--measures",
        "nope",
        "--n-perm",
        "0",
    ]
    assert evaluate_main(bad_args) == 2
    assert _assert_single_error_line(capsys.readouterr()) == "error: n_perm must be >= 1, got 0."


def test_tables_path_unknown_measure_stays_schema_violation(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, responses = make_tables(n_units=12, n_trials=20, seed=0)
    units_path = tmp_path / "units.csv"
    responses_path = tmp_path / "responses.csv"
    units.to_csv(units_path, index=False)
    responses.to_csv(responses_path, index=False)
    rc = evaluate_main(
        [str(units_path), str(responses_path), "--measures", "nope", "--post-stim-window-s", "2.0"]
    )
    captured = capsys.readouterr()
    assert rc == 1
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    assert captured.out.startswith("SCHEMA failed.")


def test_empty_and_parser_error_files_keep_messages(
    spikes_fixture: tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, _params = spikes_fixture
    units_path, responses_path, spikes_path, analysis_path = _write_spikes_dataset(
        tmp_path, units, trials, spikes
    )
    spikes_path.write_text("", encoding="utf-8")
    rc_empty = check_main(
        [
            str(units_path),
            str(responses_path),
            "--spikes",
            str(spikes_path),
            "--analysis",
            str(analysis_path),
        ]
    )
    line_empty = _assert_single_error_line(capsys.readouterr())
    assert rc_empty == 2
    assert "whole numbers" not in line_empty

    responses_path.write_text('unit_id,trial_index\n"unclosed', encoding="utf-8")
    rc_parser = check_main(
        [str(units_path), str(responses_path), "--post-stim-window-s", "2.0", "--measures", "tau"]
    )
    captured_parser = capsys.readouterr()
    assert rc_parser == 2
    assert "Traceback" not in captured_parser.out
    assert "Traceback" not in captured_parser.err
    assert "whole numbers" not in captured_parser.err
