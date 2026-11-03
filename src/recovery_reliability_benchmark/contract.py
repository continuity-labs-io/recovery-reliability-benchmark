"""Data contract reader and validator for the Recovery Reliability Benchmark."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

SPEC_VERSION = "1.0"
UNITS_REQUIRED = ("unit_id", "recording_id", "session_id", "preparation_id")
RESPONSES_REQUIRED = ("unit_id", "trial_index", "stim_time_ns", "condition")
ID_COLUMNS = UNITS_REQUIRED
FORBIDDEN_MEASURES = frozenset(RESPONSES_REQUIRED)

MD2_MUST = 10
MD2_SHOULD = 20
MD3_MUST = 8
MD3_SHOULD = 15


class Requirement(str, Enum):
    """Minimum Dataset (MD) requirements from SPEC.md.

    A dataset must satisfy every MD requirement's MUST threshold to be
    "conforming" and every SHOULD threshold to be "fully_conforming".
    validate() checks them in numeric order and raises ContractViolation
    on the first failure.
    """

    SCHEMA = "SCHEMA"
    MD1 = "MD-1"
    MD2 = "MD-2"
    MD3 = "MD-3"
    MD4 = "MD-4"
    MD5 = "MD-5"
    MD6 = "MD-6"

    @property
    def description(self) -> str:
        return _REQUIREMENT_DESCRIPTIONS[self]


_REQUIREMENT_DESCRIPTIONS: dict[Requirement, str] = {
    Requirement.SCHEMA: "Input tables are well-formed: required columns present, measures numeric and allowed, unit_id unique, no responses rows for unknown units. A property of the CSV container, not of the dataset; not one of the six SPEC.md requirements.",
    Requirement.MD1: "Single session. Exactly one preparation_id, one session_id and one recording_id (a session is one continuous acquisition, so a second recording is a second session).",
    Requirement.MD2: "Repeated trials. At least 10 trials of at least one condition; SHOULD 20. Below 10 the two halves are too short for the correlation to be stable.",
    Requirement.MD3: "Multiple recording units. At least 8 units active in every trial of the evaluated condition; SHOULD 15. A unit is active in a trial when it has a row for it with every measure non-null.",
    Requirement.MD4: "Stimulus timestamps. Onset time of every stimulus on the same clock as the responses, non-null, strictly increasing within a condition, one timestamp and one condition per trial_index across units.",
    Requirement.MD5: "Trial-level resolution. Exactly one row per (unit_id, trial_index); rows are trials, not summary statistics.",
    Requirement.MD6: "Post-stimulus window. At least 2.0 s of recording after each stimulus onset: the declared post_stim_window_s is at least 2.0 s and fits before the next onset (minus load_duration_s).",
}


class ContractViolation(Exception):
    """Raised when input tables violate a benchmark data contract requirement."""

    def __init__(
        self,
        requirement: Requirement | str,
        message: str,
        found: Any = None,
        required: Any = None,
    ) -> None:
        req = Requirement(requirement)
        super().__init__(f"{req.value} failed. {message}")
        self.requirement: Requirement = req
        self.message = message
        self.found = found
        self.required = required

    def __str__(self) -> str:
        return f"{self.requirement.value} failed. {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement.value,
            "message": self.message,
            "found": self.found,
            "required": self.required,
        }


def read_tables(units_path: str | Path, responses_path: str | Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read units and responses CSV tables with contract-enforced column dtypes."""
    units = pd.read_csv(units_path, dtype=dict.fromkeys(ID_COLUMNS, str))
    responses = pd.read_csv(
        responses_path,
        dtype={"unit_id": str, "condition": str, "trial_index": "Int64", "stim_time_ns": "Int64"},
    )
    return units, responses


def validate(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: list[str],
    post_stim_window_s: float,
    load_duration_s: float = 0.0,
    extra_forbidden: set[str] | None = None,
) -> dict[str, Any]:
    """Validate units and responses (SCHEMA and MD-1..MD-3; MD-4..MD-6 are added in Step 3)."""
    units = units.copy()
    responses = responses.copy()

    for col in UNITS_REQUIRED:
        if col not in units.columns:
            raise ContractViolation(Requirement.SCHEMA, f"units is missing required column '{col}'.")

    for col in RESPONSES_REQUIRED:
        if col not in responses.columns:
            raise ContractViolation(Requirement.SCHEMA, f"responses is missing required column '{col}'.")

    if not measures:
        raise ContractViolation(Requirement.SCHEMA, "measures must not be empty.")
    for measure in measures:
        if measure not in responses.columns:
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is not a column of responses.")

    forbidden = FORBIDDEN_MEASURES | (extra_forbidden or set())
    for measure in measures:
        if measure in forbidden:
            raise ContractViolation(Requirement.SCHEMA, f"'{measure}' is not allowed as a measure.")

    for measure in measures:
        if not is_numeric_dtype(responses[measure]):
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is not numeric.")
        if responses[measure].isna().all():
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is entirely null.")

    for col in ID_COLUMNS:
        units[col] = units[col].astype(str)
    responses["unit_id"] = responses["unit_id"].astype(str)

    unit_counts = units["unit_id"].value_counts(sort=False)
    duplicates = unit_counts[unit_counts > 1]
    if not duplicates.empty:
        bad_id, count = duplicates.index[0], int(duplicates.iloc[0])
        raise ContractViolation(
            Requirement.SCHEMA,
            f"unit_id '{bad_id}' appears {count} times in units, requires 1.",
            found=count,
            required=1,
        )

    orphan_mask = ~responses["unit_id"].isin(set(units["unit_id"]))
    if orphan_mask.any():
        bad_id = responses.loc[orphan_mask, "unit_id"].iloc[0]
        count = int((responses["unit_id"] == bad_id).sum())
        raise ContractViolation(
            Requirement.SCHEMA,
            f"{count} responses rows reference unit_id '{bad_id}', which is not in units.",
            found=count,
            required=0,
        )

    for col in ("preparation_id", "session_id", "recording_id"):
        n_distinct = int(units[col].nunique())
        if n_distinct != 1:
            vals = ", ".join(f"'{v}'" for v in units[col].unique())
            raise ContractViolation(
                Requirement.MD1,
                f"{n_distinct} distinct {col} values ({vals}), requires exactly 1.",
                found=n_distinct,
                required=1,
            )

    conditions_info: dict[str, dict[str, int]] = {}
    for cond in responses["condition"].unique():
        cond_rows = responses[responses["condition"] == cond]
        n_trials_cond = int(cond_rows["trial_index"].nunique())
        n_active = 0
        if n_trials_cond > 0:
            for _, unit_rows in cond_rows.groupby("unit_id", sort=False):
                if (
                    int(unit_rows["trial_index"].nunique()) == n_trials_cond
                    and bool(unit_rows[measures].notna().all().all())
                ):
                    n_active += 1
        conditions_info[str(cond)] = {
            "n_trials": n_trials_cond,
            "n_units_active": n_active,
        }

    best_trial_cond = max(conditions_info, key=lambda c: conditions_info[c]["n_trials"])
    max_trials = conditions_info[best_trial_cond]["n_trials"]
    if max_trials < MD2_MUST:
        raise ContractViolation(
            Requirement.MD2,
            f"At most {max_trials} trials in any condition (condition '{best_trial_cond}'), requires {MD2_MUST}.",
            found=max_trials,
            required=MD2_MUST,
        )

    evaluable_conditions = [c for c, info in conditions_info.items() if info["n_trials"] >= MD2_MUST]
    best_eval_cond = max(evaluable_conditions, key=lambda c: conditions_info[c]["n_units_active"])
    max_active = conditions_info[best_eval_cond]["n_units_active"]
    if max_active < MD3_MUST:
        raise ContractViolation(
            Requirement.MD3,
            f"At most {max_active} units active in every trial of any condition with enough trials (condition '{best_eval_cond}'), requires {MD3_MUST}.",
            found=max_active,
            required=MD3_MUST,
        )

    evaluated_conditions = sorted(
        c for c, info in conditions_info.items() if info["n_trials"] >= MD2_MUST and info["n_units_active"] >= MD3_MUST
    )
    n_units_active = max(conditions_info[c]["n_units_active"] for c in evaluated_conditions)

    return {
        "spec_version": SPEC_VERSION,
        "n_preparations": int(units["preparation_id"].nunique()),
        "n_sessions": int(units["session_id"].nunique()),
        "n_recordings": int(units["recording_id"].nunique()),
        "n_units": int(len(units)),
        "n_units_active": int(n_units_active),
        "n_conditions": int(responses["condition"].nunique()),
        "n_trials": int(responses["trial_index"].nunique()),
        "trials_per_unit_condition": float(responses.groupby(["unit_id", "condition"]).size().median()),
        "conditions": conditions_info,
        "evaluated_conditions": evaluated_conditions,
    }
