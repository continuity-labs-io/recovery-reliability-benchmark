"""Tests that malformed spikes-path tables give contract violations, never tracebacks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.cli import check_main, evaluate_main
from recovery_reliability_benchmark.contract import ContractViolation, Requirement, validate
from recovery_reliability_benchmark.inputs import validate_spikes_path
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_spike_trains, make_tables

Tables = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]


def _good_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
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
            "condition": "A",
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


def _drop(table: str, column: str) -> Callable[[Tables], Tables]:
    def mutate(tables: Tables) -> Tables:
        frames = dict(zip(("units", "trials", "spikes"), tables, strict=True))
        frames[table] = frames[table].drop(columns=[column])
        return frames["units"], frames["trials"], frames["spikes"]

    return mutate


def _null(table: str, column: str) -> Callable[[Tables], Tables]:
    def mutate(tables: Tables) -> Tables:
        frames = dict(zip(("units", "trials", "spikes"), tables, strict=True))
        frame = frames[table].copy()
        frame[column] = frame[column].astype(object)
        frame.loc[3, column] = None
        frames[table] = frame
        return frames["units"], frames["trials"], frames["spikes"]

    return mutate


def _duplicate_trial_index(tables: Tables) -> Tables:
    units, trials, spikes = tables
    trials = trials.copy()
    trials.loc[1, "trial_index"] = 0
    return units, trials, spikes


def _spikes_on_another_clock(tables: Tables) -> Tables:
    units, trials, spikes = tables
    return units, trials, spikes.assign(spike_time_ns=spikes["spike_time_ns"] + 10**12)


def _stim_times_in_seconds(tables: Tables) -> Tables:
    units, trials, spikes = tables
    return units, trials.assign(stim_time_ns=trials["stim_time_ns"] // 10**9), spikes


CASES: list[tuple[str, Callable[[Tables], Tables], Requirement, str]] = [
    (
        "units_missing_unit_id",
        _drop("units", "unit_id"),
        Requirement.SCHEMA,
        "units is missing required column 'unit_id'.",
    ),
    (
        "trials_missing_condition",
        _drop("trials", "condition"),
        Requirement.SCHEMA,
        "responses is missing required column 'condition'.",
    ),
    (
        "trials_missing_stim_time",
        _drop("trials", "stim_time_ns"),
        Requirement.SCHEMA,
        "responses is missing required column 'stim_time_ns'.",
    ),
    (
        "spikes_missing_spike_time",
        _drop("spikes", "spike_time_ns"),
        Requirement.SCHEMA,
        "spikes is missing required column 'spike_time_ns'.",
    ),
    (
        "null_trial_index",
        _null("trials", "trial_index"),
        Requirement.SCHEMA,
        "1 responses rows have a null trial_index, requires 0.",
    ),
    (
        "null_condition",
        _null("trials", "condition"),
        Requirement.SCHEMA,
        "1 responses rows have a null condition, requires 0.",
    ),
    (
        "null_stim_time",
        _null("trials", "stim_time_ns"),
        Requirement.MD4,
        "1 responses rows have a null stim_time_ns, requires 0.",
    ),
    (
        "null_spike_time",
        _null("spikes", "spike_time_ns"),
        Requirement.SCHEMA,
        "1 spikes rows have a null spike_time_ns, requires 0.",
    ),
    (
        "duplicate_trial_index",
        _duplicate_trial_index,
        Requirement.MD4,
        "trial_index 0 has 2 distinct stim_time_ns values, requires 1.",
    ),
    (
        "spikes_on_another_clock",
        _spikes_on_another_clock,
        Requirement.SCHEMA,
        "0 of 10892 spikes fall inside a post-stimulus window, requires at least 1. "
        "Check that spike_time_ns and stim_time_ns are integer nanoseconds on the same clock.",
    ),
    (
        "stim_times_in_seconds",
        _stim_times_in_seconds,
        Requirement.MD6,
        "Trial 0 has 0.000 s available before the next stimulus (gap 0.000 s minus load 0.000 s), requires 2.000 s.",
    ),
]


def test_good_tables_pass() -> None:
    units, trials, spikes, params = _good_tables()
    report, trial_table = validate_spikes_path(units, trials, spikes, params)
    assert report["conformance"] == "conforming"
    assert len(trial_table) == 20


@pytest.mark.parametrize(
    ("mutate", "requirement", "message"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_malformed_tables_raise_violations(
    mutate: Callable[[Tables], Tables], requirement: Requirement, message: str
) -> None:
    units, trials, spikes, params = _good_tables()
    bad_units, bad_trials, bad_spikes = mutate((units, trials, spikes))
    with pytest.raises(ContractViolation) as exc_info:
        validate_spikes_path(bad_units, bad_trials, bad_spikes, params)
    assert exc_info.value.requirement is requirement
    assert exc_info.value.message == message
    with pytest.raises(ContractViolation) as run_info:
        run(bad_units, bad_trials, ["t_half_excess"], spikes=bad_spikes, analysis=params, n_perm=20)
    assert str(run_info.value) == str(exc_info.value)


@pytest.mark.parametrize(
    ("mutate", "requirement", "message"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_malformed_files_exit_1_from_every_command(
    mutate: Callable[[Tables], Tables],
    requirement: Requirement,
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, params = _good_tables()
    bad_units, bad_trials, bad_spikes = mutate((units, trials, spikes))
    bad_units.to_csv(tmp_path / "units.csv", index=False)
    bad_trials.to_csv(tmp_path / "trials.csv", index=False)
    bad_spikes.to_csv(tmp_path / "spikes.csv", index=False)
    (tmp_path / "analysis.json").write_text('{"post_stim_window_s": 2.0}', encoding="utf-8")
    base = [
        str(tmp_path / "units.csv"),
        str(tmp_path / "trials.csv"),
        "--spikes",
        str(tmp_path / "spikes.csv"),
        "--analysis",
        str(tmp_path / "analysis.json"),
    ]
    expected = f"{requirement.value} failed. {message}"
    measures = ["--measures", "t_half_excess", "--n-perm", "20"]
    for command, extra in (
        (check_main, []),
        (evaluate_main, measures),
        (report_main, [*measures, "--out", str(tmp_path / "report")]),
    ):
        assert command([*base, *extra]) == 1
        assert capsys.readouterr().out.strip() == expected


def test_null_condition_on_tables_path() -> None:
    units, responses = make_tables(n_units=12, n_trials=20, reliability=0.8, seed=1)
    responses["condition"] = responses["condition"].astype(object)
    responses.loc[5, "condition"] = None
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau"], post_stim_window_s=2.0)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert exc_info.value.message == "1 responses rows have a null condition, requires 0."
