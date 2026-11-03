"""Data contract reader and validator for the Recovery Reliability Benchmark."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

SPEC_VERSION = "1.0"
UNITS_REQUIRED = ("unit_id", "recording_id", "session_id", "preparation_id")
RESPONSES_REQUIRED = ("unit_id", "trial_index", "stim_time_ns", "condition")
ID_COLUMNS = UNITS_REQUIRED
FORBIDDEN_MEASURES = frozenset(RESPONSES_REQUIRED)


class ContractViolation(Exception):
    """Raised when input tables violate a benchmark data contract requirement."""

    def __init__(self, requirement: str, message: str, found: Any = None, required: Any = None) -> None:
        super().__init__(f"{requirement} failed. {message}")
        self.requirement = requirement
        self.message = message
        self.found = found
        self.required = required

    def __str__(self) -> str:
        return f"{self.requirement} failed. {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
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
            raise ContractViolation("MD-0", f"units is missing required column '{col}'.")

    for col in RESPONSES_REQUIRED:
        if col not in responses.columns:
            raise ContractViolation("MD-0", f"responses is missing required column '{col}'.")

    if not measures:
        raise ContractViolation("MD-0", "measures must not be empty.")
    for measure in measures:
        if measure not in responses.columns:
            raise ContractViolation("MD-0", f"measure '{measure}' is not a column of responses.")

    forbidden = FORBIDDEN_MEASURES | (extra_forbidden or set())
    for measure in measures:
        if measure in forbidden:
            raise ContractViolation("MD-0", f"'{measure}' is not allowed as a measure.")

    for measure in measures:
        if not is_numeric_dtype(responses[measure]):
            raise ContractViolation("MD-0", f"measure '{measure}' is not numeric.")
        if responses[measure].isna().all():
            raise ContractViolation("MD-0", f"measure '{measure}' is entirely null.")

    for col in ID_COLUMNS:
        units[col] = units[col].astype(str)
    responses["unit_id"] = responses["unit_id"].astype(str)

    unit_counts = units["unit_id"].value_counts(sort=False)
    duplicates = unit_counts[unit_counts > 1]
    if not duplicates.empty:
        bad_id, count = duplicates.index[0], int(duplicates.iloc[0])
        raise ContractViolation(
            "MD-0", f"unit_id '{bad_id}' appears {count} times in units, requires 1.", found=count, required=1
        )

    orphan_mask = ~responses["unit_id"].isin(set(units["unit_id"]))
    if orphan_mask.any():
        bad_id = responses.loc[orphan_mask, "unit_id"].iloc[0]
        count = int((responses["unit_id"] == bad_id).sum())
        raise ContractViolation(
            "MD-0", f"{count} responses rows reference unit_id '{bad_id}', which is not in units.", found=count, required=0
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
