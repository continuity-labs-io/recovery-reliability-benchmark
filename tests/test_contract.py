"""Tests for the Recovery Reliability Benchmark data contract."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pandas.api.types import is_integer_dtype

from tests.conftest import make_tables
from recovery_reliability_benchmark.contract import (
    SPEC_VERSION,
    ContractViolation,
    Requirement,
    read_tables,
    validate,
)

MEASURES = ["tau", "amplitude"]


def test_conforming_returns_counts() -> None:
    units, responses = make_tables()
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["n_units"] == 8
    assert result["n_trials"] == 10
    assert result["n_conditions"] == 1
    assert result["n_recordings"] == 1
    assert result["trials_per_unit_condition"] == 10.0
    assert result["spec_version"] == SPEC_VERSION


def test_validate_does_not_mutate_inputs() -> None:
    units, responses = make_tables()
    units["unit_id"] = list(range(8))
    responses["unit_id"] = responses["unit_id"].str[1:].astype(int)
    validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert is_integer_dtype(units["unit_id"])
    assert is_integer_dtype(responses["unit_id"])


def test_md0_missing_units_column() -> None:
    units, responses = make_tables()
    units = units.drop(columns=["preparation_id"])
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "preparation_id" in str(exc_info.value)


def test_md0_missing_responses_column() -> None:
    units, responses = make_tables()
    responses = responses.drop(columns=["condition"])
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "condition" in str(exc_info.value)


def test_md0_measure_not_a_column() -> None:
    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["missing"], post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "missing" in str(exc_info.value)


def test_md0_forbidden_measure() -> None:
    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["condition"], post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "condition" in str(exc_info.value)

    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau"], post_stim_window_s=2.0, extra_forbidden={"tau"})
    assert exc_info.value.requirement == "SCHEMA"
    assert "tau" in str(exc_info.value)


def test_md0_measure_not_numeric() -> None:
    units, responses = make_tables()
    responses["tau"] = "x"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "tau" in str(exc_info.value)


def test_md0_measure_all_null() -> None:
    units, responses = make_tables()
    responses["tau"] = float("nan")
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "tau" in str(exc_info.value)


def test_md0_duplicate_unit_id() -> None:
    units, responses = make_tables()
    units = pd.concat([units, units.iloc[[0]]], ignore_index=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "u00" in str(exc_info.value)


def test_md0_orphan_response() -> None:
    units, responses = make_tables()
    orphan = responses.iloc[[0]].copy()
    orphan["unit_id"] = "ghost"
    responses = pd.concat([responses, orphan], ignore_index=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "SCHEMA"
    assert "ghost" in str(exc_info.value)


def test_read_tables_dtypes(tmp_path: Path) -> None:
    units_csv = tmp_path / "units.csv"
    responses_csv = tmp_path / "responses.csv"
    units_csv.write_text(
        "unit_id,recording_id,session_id,preparation_id\n17,rec0,sess0,prep0\n",
        encoding="utf-8",
    )
    responses_csv.write_text(
        "unit_id,trial_index,stim_time_ns,condition,tau\n17,0,0,A,1.5\n17,1,,A,1.6\n",
        encoding="utf-8",
    )
    units, responses = read_tables(units_csv, responses_csv)
    assert units["unit_id"].dtype in (object, "str")
    assert units["unit_id"].tolist() == ["17"]
    assert responses["unit_id"].dtype in (object, "str")
    assert responses["unit_id"].tolist() == ["17", "17"]
    assert responses["stim_time_ns"].dtype == "Int64"
    assert int(responses["stim_time_ns"].isna().sum()) == 1
    assert responses["trial_index"].dtype == "Int64"


def test_contract_violation_str_and_dict() -> None:
    exc = ContractViolation(
        "MD-2",
        "6 trials for condition 'A' on unit 'ch17', requires 10.",
        found=6,
        required=10,
    )
    assert str(exc) == "MD-2 failed. 6 trials for condition 'A' on unit 'ch17', requires 10."
    assert exc.to_dict() == {
        "requirement": "MD-2",
        "message": "6 trials for condition 'A' on unit 'ch17', requires 10.",
        "found": 6,
        "required": 10,
    }


def test_requirement_enum() -> None:
    assert len(Requirement) == 7
    assert Requirement("MD-3") is Requirement.MD3
    assert Requirement.MD3 == "MD-3"
    for member in Requirement:
        assert isinstance(member.description, str)
        assert len(member.description) > 0


def test_contract_violation_accepts_string_or_enum() -> None:
    for exc in (ContractViolation("MD-2", "m"), ContractViolation(Requirement.MD2, "m")):
        assert exc.requirement is Requirement.MD2
        assert exc.to_dict()["requirement"] == "MD-2"


def test_md1_two_preparations() -> None:
    units, responses = make_tables()
    units.loc[units.index[-1], "preparation_id"] = "prep1"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD1
    assert "preparation_id" in str(exc)
    assert exc.found == 2
    assert exc.required == 1


def test_md1_two_sessions() -> None:
    units, responses = make_tables()
    units.loc[units.index[-1], "session_id"] = "sess1"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD1
    assert "session_id" in str(exc)
    assert exc.found == 2
    assert exc.required == 1


def test_md1_two_recordings() -> None:
    units, responses = make_tables()
    units.loc[units.index[-1], "recording_id"] = "rec1"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD1
    assert "recording_id" in str(exc)
    assert exc.found == 2
    assert exc.required == 1


def test_md2_too_few_trials() -> None:
    units, responses = make_tables(n_trials=6)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD2
    assert exc.found == 6
    assert exc.required == 10


def test_md2_passes_if_any_condition_has_enough() -> None:
    units, responses = make_tables(n_trials=10, conditions=("A", "B"))
    responses = responses[~((responses["condition"] == "B") & (responses["trial_index"] >= 15))].reset_index(drop=True)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conditions"]["B"]["n_trials"] == 5
    assert result["evaluated_conditions"] == ["A"]


def test_md3_too_few_units() -> None:
    units, responses = make_tables(n_units=5)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD3
    assert exc.found == 5
    assert exc.required == 8


def test_md3_missing_row_makes_unit_inactive() -> None:
    units, responses = make_tables()
    u00_first = responses.index[responses["unit_id"] == "u00"][0]
    responses = responses.drop(index=u00_first).reset_index(drop=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD3
    assert exc.found == 7
    assert exc.required == 8


def test_md3_null_measure_makes_unit_inactive() -> None:
    units, responses = make_tables()
    u00_first = responses.index[responses["unit_id"] == "u00"][0]
    responses.loc[u00_first, "tau"] = float("nan")
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD3
    assert exc.found == 7
    assert exc.required == 8


def test_md3_counts_in_result() -> None:
    units, responses = make_tables(n_units=12)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["n_units_active"] == 12
    assert result["conditions"]["A"]["n_units_active"] == 12


