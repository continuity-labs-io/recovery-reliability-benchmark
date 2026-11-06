"""Tests for preparation and condition metadata sidecars."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from recovery_reliability_benchmark.contract import ContractViolation, Requirement
from recovery_reliability_benchmark.metadata import (
    Condition,
    Exclusion,
    Preparation,
    load_conditions,
    load_preparation,
)
from recovery_reliability_benchmark.protocol import Protocol


def test_preparation_round_trip(tmp_path: Path) -> None:
    prep = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
        raw_data_url="https://doi.org/10.5281/zenodo.0",
    )
    path = tmp_path / "preparation.json"
    path.write_text(prep.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_preparation(path)
    assert loaded == prep


def test_bad_preparation_type_rejected() -> None:
    with pytest.raises(ValidationError):
        Preparation(
            preparation_id="prep0",
            species="Rattus norvegicus",
            preparation_type="heart_slice",  # type: ignore[arg-type]
            age_days=21,
            age_basis="DIV",
            line_or_donor_id="example",
            instrument="synthetic",
        )


def test_condition_fingerprint() -> None:
    cond_no_proto = Condition(compound="TTX", dose=1.0, dose_unit="uM")
    assert cond_no_proto.fingerprint is None

    proto = Protocol.standard_hfs()
    cond_with_proto = Condition(protocol=proto)
    fp = cond_with_proto.fingerprint
    assert isinstance(fp, str)
    assert len(fp) == 64
    int(fp, 16)
    assert fp == proto.fingerprint()


def test_load_preparation_malformed_json_raises_contract_violation(tmp_path: Path) -> None:
    bad_path = tmp_path / "preparation.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ContractViolation) as exc_info:
        load_preparation(bad_path)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert "preparation.json" in str(exc_info.value)


def test_load_conditions_malformed_json_raises_contract_violation(tmp_path: Path) -> None:
    bad_path = tmp_path / "conditions.json"
    bad_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(ContractViolation) as exc_info:
        load_conditions(bad_path)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert "conditions.json" in str(exc_info.value)


def test_exclusion_round_trip(tmp_path: Path) -> None:
    excl = Exclusion(kind="unit", id="u99", reason="saturated")
    restored = Exclusion.model_validate_json(excl.model_dump_json())
    assert restored == excl

    prep = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
        exclusions=[
            excl,
            Exclusion(kind="trial", id="10", reason="artifact"),
        ],
    )
    path = tmp_path / "preparation.json"
    path.write_text(prep.model_dump_json(indent=2), encoding="utf-8")
    loaded = load_preparation(path)
    assert loaded == prep
    assert len(loaded.exclusions) == 2


def test_load_preparation_malformed_exclusion_raises_schema(tmp_path: Path) -> None:
    bad_path = tmp_path / "preparation.json"
    bad_path.write_text(
        '{"preparation_id":"prep0","species":"Rattus norvegicus",'
        '"preparation_type":"dissociated_culture","age_days":21,"age_basis":"DIV",'
        '"line_or_donor_id":"example","instrument":"synthetic",'
        '"exclusions":[{"kind":"unit","id":"u99","reason":""}]}',
        encoding="utf-8",
    )
    with pytest.raises(ContractViolation) as exc_info:
        load_preparation(bad_path)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert "exclusions" in str(exc_info.value)
