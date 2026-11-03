"""Tests for the Recovery Reliability Benchmark data contract (Step 1: MD-0 slice)."""

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
    assert exc_info.value.requirement == "MD-0"
    assert "preparation_id" in str(exc_info.value)


def test_md0_missing_responses_column() -> None:
    units, responses = make_tables()
    responses = responses.drop(columns=["condition"])
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "condition" in str(exc_info.value)


def test_md0_measure_not_a_column() -> None:
    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["missing"], post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "missing" in str(exc_info.value)


def test_md0_forbidden_measure() -> None:
    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["condition"], post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "condition" in str(exc_info.value)

    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau"], post_stim_window_s=2.0, extra_forbidden={"tau"})
    assert exc_info.value.requirement == "MD-0"
    assert "tau" in str(exc_info.value)


def test_md0_measure_not_numeric() -> None:
    units, responses = make_tables()
    responses["tau"] = "x"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "tau" in str(exc_info.value)


def test_md0_measure_all_null() -> None:
    units, responses = make_tables()
    responses["tau"] = float("nan")
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "tau" in str(exc_info.value)


def test_md0_duplicate_unit_id() -> None:
    units, responses = make_tables()
    units = pd.concat([units, units.iloc[[0]]], ignore_index=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
    assert "u00" in str(exc_info.value)


def test_md0_orphan_response() -> None:
    units, responses = make_tables()
    orphan = responses.iloc[[0]].copy()
    orphan["unit_id"] = "ghost"
    responses = pd.concat([responses, orphan], ignore_index=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert exc_info.value.requirement == "MD-0"
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

