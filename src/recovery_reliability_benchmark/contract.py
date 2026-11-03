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


class Requirement(str, Enum):
    """Minimum Dataset (MD) requirements from SPEC.md.

    A dataset must satisfy every MD requirement's MUST threshold to be
    "conforming" and every SHOULD threshold to be "fully_conforming".
    validate() checks them in numeric order and raises ContractViolation
    on the first failure.
    """

    MD0 = "MD-0"  # Schema: required columns present, measures numeric and allowed, ids unique, no orphan responses.
    MD1 = "MD-1"  # Identity: exactly one preparation_id, session_id, and recording_id across the joined tables.
    MD2 = "MD-2"  # Trials: at least 10 trials per (unit_id, condition); SHOULD 20.
    MD3 = "MD-3"  # Units: at least 8 units active (all measures non-null) in every trial of each condition; SHOULD 15.
    MD4 = "MD-4"  # Timeline: stim_time_ns non-null and strictly increasing with trial_index; one stim_time_ns and one condition per trial_index across units.
    MD5 = "MD-5"  # Uniqueness: exactly one row per (unit_id, trial_index).
    MD6 = "MD-6"  # Window: post_stim_window_s >= 2.0 and, for every load except the last, the gap to the next load minus load_duration_s is at least post_stim_window_s.

    @property
    def description(self) -> str:
        return _REQUIREMENT_DESCRIPTIONS[self]


_REQUIREMENT_DESCRIPTIONS: dict[Requirement, str] = {
    Requirement.MD0: "Schema: required columns present, measures numeric and allowed, ids unique, no orphan responses.",
    Requirement.MD1: "Identity: exactly one preparation_id, session_id, and recording_id across the joined tables.",
    Requirement.MD2: "Trials: at least 10 trials per (unit_id, condition); SHOULD 20.",
    Requirement.MD3: "Units: at least 8 units active (all measures non-null) in every trial of each condition; SHOULD 15.",
    Requirement.MD4: "Timeline: stim_time_ns non-null and strictly increasing with trial_index; one stim_time_ns and one condition per trial_index across units.",
    Requirement.MD5: "Uniqueness: exactly one row per (unit_id, trial_index).",
    Requirement.MD6: "Window: post_stim_window_s >= 2.0 and, for every load except the last, the gap to the next load minus load_duration_s is at least post_stim_window_s.",
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
    """Validate units and responses (day-one slice; MD-1..MD-6 are added in later steps)."""
    units = units.copy()
    responses = responses.copy()

    for col in UNITS_REQUIRED:
        if col not in units.columns:
            raise ContractViolation(Requirement.MD0, f"units is missing required column '{col}'.")

    for col in RESPONSES_REQUIRED:
        if col not in responses.columns:
            raise ContractViolation(Requirement.MD0, f"responses is missing required column '{col}'.")

    if not measures:
        raise ContractViolation(Requirement.MD0, "measures must not be empty.")
    for measure in measures:
        if measure not in responses.columns:
            raise ContractViolation(Requirement.MD0, f"measure '{measure}' is not a column of responses.")

    forbidden = FORBIDDEN_MEASURES | (extra_forbidden or set())
    for measure in measures:
        if measure in forbidden:
            raise ContractViolation(Requirement.MD0, f"'{measure}' is not allowed as a measure.")

    for measure in measures:
        if not is_numeric_dtype(responses[measure]):
            raise ContractViolation(Requirement.MD0, f"measure '{measure}' is not numeric.")
        if responses[measure].isna().all():
            raise ContractViolation(Requirement.MD0, f"measure '{measure}' is entirely null.")

    for col in ID_COLUMNS:
        units[col] = units[col].astype(str)
    responses["unit_id"] = responses["unit_id"].astype(str)

    unit_counts = units["unit_id"].value_counts(sort=False)
    duplicates = unit_counts[unit_counts > 1]
    if not duplicates.empty:
        bad_id, count = duplicates.index[0], int(duplicates.iloc[0])
        raise ContractViolation(
            Requirement.MD0, f"unit_id '{bad_id}' appears {count} times in units, requires 1.", found=count, required=1
        )

    orphan_mask = ~responses["unit_id"].isin(set(units["unit_id"]))
    if orphan_mask.any():
        bad_id = responses.loc[orphan_mask, "unit_id"].iloc[0]
        count = int((responses["unit_id"] == bad_id).sum())
        raise ContractViolation(
            Requirement.MD0,
            f"{count} responses rows reference unit_id '{bad_id}', which is not in units.",
            found=count,
            required=0,
        )

    return {
        "spec_version": SPEC_VERSION,
        "n_preparations": int(units["preparation_id"].nunique()),
        "n_sessions": int(units["session_id"].nunique()),
        "n_recordings": int(units["recording_id"].nunique()),
        "n_units": int(len(units)),
        "n_conditions": int(responses["condition"].nunique()),
        "n_trials": int(responses["trial_index"].nunique()),
        "trials_per_unit_condition": float(responses.groupby(["unit_id", "condition"]).size().median()),
    }
