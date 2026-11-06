"""Tests for the Recovery Reliability Benchmark data contract."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from pandas.api.types import is_integer_dtype

from recovery_reliability_benchmark.checks import CHECKS
from recovery_reliability_benchmark.cli import check_main as main
from recovery_reliability_benchmark.contract import (
    CONFORMING,
    FORBIDDEN_MEASURES,
    FULLY_CONFORMING,
    SPEC_VERSION,
    ContractViolation,
    Requirement,
    ValidationContext,
    read_tables,
    validate,
)
from recovery_reliability_benchmark.metadata import Condition, Exclusion, Preparation
from recovery_reliability_benchmark.protocol import Protocol
from tests.conftest import make_tables

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
        "min-dataset-2",
        "6 trials for condition 'A' on unit 'ch17', requires 10.",
        found=6,
        required=10,
    )
    assert str(exc) == "min-dataset-2 failed. 6 trials for condition 'A' on unit 'ch17', requires 10."
    assert exc.to_dict() == {
        "requirement": "min-dataset-2",
        "message": "6 trials for condition 'A' on unit 'ch17', requires 10.",
        "found": 6,
        "required": 10,
    }


def test_requirement_enum() -> None:
    assert len(Requirement) == 7
    assert Requirement("min-dataset-3") is Requirement.MD3
    assert Requirement.MD3 == "min-dataset-3"
    for member in Requirement:
        assert isinstance(member.description, str)
        assert len(member.description) > 0


def test_contract_violation_accepts_string_or_enum() -> None:
    for exc in (ContractViolation("min-dataset-2", "m"), ContractViolation(Requirement.MD2, "m")):
        assert exc.requirement is Requirement.MD2
        assert exc.to_dict()["requirement"] == "min-dataset-2"


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
    responses = responses[~((responses["condition"] == "B") & (responses["trial_index"] >= 15))].reset_index(
        drop=True
    )
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


def test_schema_null_trial_index() -> None:
    units, responses = make_tables()
    responses["trial_index"] = responses["trial_index"].astype("Int64")
    responses.loc[0, "trial_index"] = pd.NA
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert "trial_index" in str(exc)
    assert exc.found == 1
    assert exc.required == 0


def test_md4_null_stim_time() -> None:
    units, responses = make_tables()
    responses["stim_time_ns"] = responses["stim_time_ns"].astype("Int64")
    responses.loc[0, "stim_time_ns"] = pd.NA
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD4
    assert "null" in str(exc)
    assert exc.found == 1
    assert exc.required == 0


def test_md4_not_increasing() -> None:
    units, responses = make_tables()
    t4_val = int(responses.loc[responses["trial_index"] == 4, "stim_time_ns"].iloc[0])
    responses.loc[responses["trial_index"] == 5, "stim_time_ns"] = t4_val
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD4
    assert "strictly increasing" in str(exc)
    assert exc.found == t4_val
    assert exc.required == t4_val


def test_md4_inconsistent_stim_time_across_units() -> None:
    units, responses = make_tables()
    mask = (responses["unit_id"] == "u00") & (responses["trial_index"] == 3)
    responses.loc[mask, "stim_time_ns"] = responses.loc[mask, "stim_time_ns"] + 1
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD4
    assert "trial_index 3" in str(exc)
    assert exc.found == 2
    assert exc.required == 1


def test_md4_inconsistent_condition_across_units() -> None:
    units, responses = make_tables(n_units=9, conditions=("A", "B"))
    mask = (responses["unit_id"] == "u00") & (responses["trial_index"] == 3)
    responses.loc[mask, "condition"] = "B"
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD4
    assert "trial_index 3" in str(exc)
    assert exc.found == 2
    assert exc.required == 1


def test_md5_duplicate_row() -> None:
    units, responses = make_tables()
    dup = responses[(responses["unit_id"] == "u00") & (responses["trial_index"] == 7)].copy()
    responses = pd.concat([responses, dup], ignore_index=True)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD5
    assert exc.found == 2
    assert exc.required == 1
    assert "u00" in str(exc)


def test_md6_window_below_minimum() -> None:
    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=0.4)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD6
    assert str(exc) == "min-dataset-6 failed. Post-stimulus window 0.4 s, requires 2.0 s."
    assert exc.found == 0.4
    assert exc.required == 2.0


@pytest.mark.parametrize("bad_window", [-0.1, 0.0, float("nan"), float("inf")])
def test_invalid_post_stim_window_rejected(bad_window: float) -> None:
    units, responses = make_tables()
    with pytest.raises(ValueError, match="post_stim_window_s"):
        validate(units, responses, MEASURES, post_stim_window_s=bad_window)


@pytest.mark.parametrize("bad_load", [-0.1, float("nan"), float("inf")])
def test_invalid_load_duration_rejected(bad_load: float) -> None:
    units, responses = make_tables()
    with pytest.raises(ValueError, match="load_duration_s"):
        validate(units, responses, MEASURES, post_stim_window_s=2.0, load_duration_s=bad_load)


def test_md6_isi_too_short() -> None:
    units, responses = make_tables(isi_s=1.5)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD6
    assert exc.found == 1.5
    assert "Trial 0" in str(exc)


def test_md6_load_duration_tightens() -> None:
    units, responses = make_tables(isi_s=3.0)
    validate(units, responses, MEASURES, post_stim_window_s=2.0, load_duration_s=0.0)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, load_duration_s=1.5)
    exc = exc_info.value
    assert exc.requirement is Requirement.MD6
    assert exc.found == 1.5


def test_result_reports_isi() -> None:
    units, responses = make_tables()
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["min_inter_stimulus_s"] == 5.0
    assert result["post_stim_window_s"] == 2.0
    assert result["load_duration_s"] == 0.0


def test_conforming_level() -> None:
    units, responses = make_tables()
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conformance"] == CONFORMING
    assert result["conformance"] == "conforming"
    assert result["should_failed"] == ["min-dataset-2", "min-dataset-3"]
    assert result["best_condition"] == "A"


def test_fully_conforming() -> None:
    units, responses = make_tables(n_units=30, n_trials=20)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conformance"] == FULLY_CONFORMING
    assert result["conformance"] == "fully_conforming"
    assert result["should_failed"] == []
    assert result["conditions"]["A"]["should_failed"] == []


def test_should_partial() -> None:
    units, responses = make_tables(n_units=30, n_trials=10)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conformance"] == "conforming"
    assert result["should_failed"] == ["min-dataset-2"]


def test_best_condition_skips_unevaluated() -> None:
    units, responses = make_tables(n_units=30, n_trials=20, conditions=("A", "B"))
    responses = responses[~((responses["condition"] == "B") & (responses["trial_index"] >= 25))].reset_index(
        drop=True
    )
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conformance"] == "fully_conforming"
    assert result["best_condition"] == "A"
    assert result["conditions"]["B"]["should_failed"] is None


def test_best_condition_tiebreak() -> None:
    units, responses = make_tables(n_units=30, n_trials=10, conditions=("A", "B"))
    dropped_units = {f"u{i:02d}" for i in range(8, 30)}
    responses = responses[
        ~((responses["condition"] == "A") & (responses["unit_id"].isin(dropped_units)))
    ].reset_index(drop=True)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conditions"]["A"]["should_failed"] == ["min-dataset-2", "min-dataset-3"]
    assert result["conditions"]["B"]["should_failed"] == ["min-dataset-2"]
    assert result["best_condition"] == "B"
    assert result["should_failed"] == ["min-dataset-2"]
    assert result["conformance"] == "conforming"


def test_schema_constant_measure_per_unit() -> None:
    units, responses = make_tables()
    unit_map = {u: float(i + 1) for i, u in enumerate(units["unit_id"])}
    responses["pos"] = responses["unit_id"].map(unit_map)
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau", "pos"], post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert "pos" in str(exc)


def test_schema_constant_measure_everywhere() -> None:
    units, responses = make_tables()
    responses["bias"] = 1.0
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau", "bias"], post_stim_window_s=2.0)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert "bias" in str(exc)


def test_validate_at_scale() -> None:
    # Took minutes before vectorization of constant-measure and min-dataset-3 checks; should take seconds now.
    units, responses = make_tables(n_units=1000, n_trials=100)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conformance"] == "fully_conforming"
    assert result["n_units_active"] == 1000
    assert result["n_trials"] == 100


def test_md3_vectorized_matches_original() -> None:
    units, responses = make_tables(n_units=12, n_trials=10, conditions=("A", "B"))
    drop_idx = responses.index[(responses["unit_id"] == "u00") & (responses["condition"] == "A")][0]
    responses = responses.drop(index=drop_idx).reset_index(drop=True)
    nan_idx = responses.index[(responses["unit_id"] == "u01") & (responses["condition"] == "B")][0]
    responses.loc[nan_idx, "tau"] = float("nan")

    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["conditions"]["A"]["n_units_active"] == 11
    assert result["conditions"]["B"]["n_units_active"] == 11


def test_preparation_id_mismatch() -> None:
    units, responses = make_tables()
    prep = Preparation(
        preparation_id="other_prep",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
    )
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, preparation=prep)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert exc.message == "preparation.json preparation_id 'other_prep' does not match units ('prep0')."


def test_condition_missing_from_sidecar() -> None:
    units, responses = make_tables(conditions=("A", "B"))
    conds = {"A": Condition()}
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, conditions=conds)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert exc.message == "condition 'B' in responses has no entry in conditions.json."


def test_spikes_orphan_unit() -> None:
    units, responses = make_tables()
    spikes = pd.DataFrame({"unit_id": ["u00", "ghost"], "spike_time_ns": [100, 200]})
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, spikes=spikes)
    exc = exc_info.value
    assert exc.requirement is Requirement.SCHEMA
    assert "ghost" in str(exc)


def test_sidecars_absent_unchanged() -> None:
    units, responses = make_tables()
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    expected_keys = {
        "spec_version",
        "n_preparations",
        "n_sessions",
        "n_recordings",
        "n_units",
        "n_units_active",
        "n_conditions",
        "n_trials",
        "trials_per_unit_condition",
        "conditions",
        "evaluated_conditions",
        "best_condition",
        "should_failed",
        "conformance",
        "post_stim_window_s",
        "load_duration_s",
        "min_inter_stimulus_s",
        "inclusion",
        "metadata",
    }
    assert set(result.keys()) == expected_keys
    assert result["metadata"] == {
        "preparation": None,
        "conditions": None,
        "n_spikes": None,
    }


def test_inclusion_counts() -> None:
    units, responses = make_tables(n_units=12, n_trials=10)
    drop_idx = responses.index[responses["unit_id"] == "u00"][0]
    responses = responses.drop(index=drop_idx).reset_index(drop=True)
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0)
    assert result["inclusion"]["per_condition"]["A"] == {
        "n_units_in_tables": 12,
        "n_units_included": 11,
        "n_units_excluded_by_rule": 1,
        "n_rows_missing": 1,
        "n_trials": 10,
    }
    assert "u00" not in result["conditions"]["A"]["active_units"]


def test_declared_exclusion_contradiction() -> None:
    units, responses = make_tables()
    prep_bad = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
        exclusions=[Exclusion(kind="unit", id="u00", reason="saturated")],
    )
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, preparation=prep_bad)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert "u00" in str(exc_info.value)

    prep_bad_trial = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
        exclusions=[Exclusion(kind="trial", id="0", reason="artifact")],
    )
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, preparation=prep_bad_trial)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert "0" in str(exc_info.value)

    prep_ok = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
        exclusions=[Exclusion(kind="unit", id="u99", reason="saturated")],
    )
    result = validate(units, responses, MEASURES, post_stim_window_s=2.0, preparation=prep_ok)
    assert result["inclusion"]["declared"]["units"] == 1
    assert result["inclusion"]["declared"]["trials"] == 0


def test_examples_with_sidecars(capsys: pytest.CaptureFixture[str]) -> None:
    examples_dir = Path(__file__).resolve().parent.parent / "examples"
    rc = main(
        [
            str(examples_dir / "units.csv"),
            str(examples_dir / "responses.csv"),
            "--measures",
            "tau,amplitude",
            "--post-stim-window-s",
            "2.0",
            "--preparation",
            str(examples_dir / "preparation.json"),
            "--conditions",
            str(examples_dir / "conditions.json"),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    doc = json.loads(captured.out)
    metadata = doc["result"]["metadata"]
    assert metadata["conditions"]["baseline"]["fingerprint"] == Protocol.standard_hfs().fingerprint()


def test_checks_registry() -> None:
    assert len(CHECKS) == 11
    reqs = [req for req, _, _ in CHECKS]
    assert reqs == [
        Requirement.SCHEMA,
        Requirement.SCHEMA,
        Requirement.SCHEMA,
        Requirement.SCHEMA,
        Requirement.SCHEMA,
        Requirement.MD1,
        Requirement.MD2,
        Requirement.MD3,
        Requirement.MD4,
        Requirement.MD5,
        Requirement.MD6,
    ]
    names = [name for _, name, _ in CHECKS]
    assert len(names) == len(set(names))
    for _, _, fn in CHECKS:
        assert callable(fn)
        assert isinstance(fn.__doc__, str) and len(fn.__doc__.strip()) > 0


def test_each_check_raises_its_own_requirement() -> None:
    units_md1, responses_md1 = make_tables()
    units_md1.loc[units_md1.index[-1], "preparation_id"] = "prep1"

    units_md2, responses_md2 = make_tables(n_trials=6)

    units_md3, responses_md3 = make_tables(n_units=5)

    units_md4, responses_md4 = make_tables()
    responses_md4["stim_time_ns"] = responses_md4["stim_time_ns"].astype("Int64")
    responses_md4.loc[0, "stim_time_ns"] = pd.NA

    units_md5, responses_md5 = make_tables()
    dup = responses_md5[(responses_md5["unit_id"] == "u00") & (responses_md5["trial_index"] == 7)].copy()
    responses_md5 = pd.concat([responses_md5, dup], ignore_index=True)

    units_md6, responses_md6 = make_tables(isi_s=1.5)

    violating_fixtures: dict[Requirement, tuple[pd.DataFrame, pd.DataFrame]] = {
        Requirement.MD1: (units_md1, responses_md1),
        Requirement.MD2: (units_md2, responses_md2),
        Requirement.MD3: (units_md3, responses_md3),
        Requirement.MD4: (units_md4, responses_md4),
        Requirement.MD5: (units_md5, responses_md5),
        Requirement.MD6: (units_md6, responses_md6),
    }

    for req, _name, fn in CHECKS:
        if req is Requirement.SCHEMA:
            continue
        units, responses = violating_fixtures[req]
        ctx = ValidationContext(
            units=units.copy(),
            responses=responses.copy(),
            measures=list(MEASURES),
            post_stim_window_s=2.0,
            load_duration_s=0.0,
            forbidden=FORBIDDEN_MEASURES,
            preparation=None,
            conditions=None,
            spikes=None,
        )
        with pytest.raises(ContractViolation) as exc_info:
            fn(ctx)
        assert exc_info.value.requirement is req


def test_two_preparations_with_matching_sidecar_reports_md1() -> None:
    units, responses = make_tables()
    units.loc[units.index[-1], "preparation_id"] = "prep1"
    prep = Preparation(
        preparation_id="prep1",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
    )
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=2.0, preparation=prep)
    assert exc_info.value.requirement is Requirement.MD1
