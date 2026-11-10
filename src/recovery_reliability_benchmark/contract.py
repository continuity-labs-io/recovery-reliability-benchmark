"""Data contract reader and validator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd

from .frozen import freeze_constant, frozen

if TYPE_CHECKING:
    from .metadata import Condition, Preparation

SPEC_VERSION = "1.0"
UNITS_REQUIRED = ("unit_id", "recording_id", "session_id", "preparation_id")
RESPONSES_REQUIRED = ("unit_id", "trial_index", "stim_time_ns", "condition")
SPIKES_REQUIRED = ("unit_id", "spike_time_ns")
ID_COLUMNS = UNITS_REQUIRED
FORBIDDEN_MEASURES = frozenset(RESPONSES_REQUIRED)

MD2_MUST = 10
MD2_SHOULD = 20
MD3_MUST = 8
MD3_SHOULD = 30
MD6_MUST = 2.0
MD7_MUST = 1.0
for _const, _ref in (
    ("MD2_MUST", "SPEC min-dataset-2"),
    ("MD2_SHOULD", "SPEC min-dataset-2"),
    ("MD3_MUST", "SPEC min-dataset-3"),
    ("MD3_SHOULD", "SPEC min-dataset-3"),
    ("MD6_MUST", "SPEC min-dataset-6"),
):
    freeze_constant(__name__, _const, _ref)

CONFORMING = "conforming"
FULLY_CONFORMING = "fully_conforming"

INCLUSION_RULE = (
    "A unit is included in a condition if and only if it has a row for every trial of that condition "
    "with every measure non-null. All present trials are used; no trial is excluded by rule in v0.1.x."
)


class Requirement(StrEnum):
    """Minimum dataset (`min-dataset-*`) requirements from SPEC.md."""

    SCHEMA = "SCHEMA"
    MD1 = "min-dataset-1"
    MD2 = "min-dataset-2"
    MD3 = "min-dataset-3"
    MD4 = "min-dataset-4"
    MD5 = "min-dataset-5"
    MD6 = "min-dataset-6"
    MD7 = "min-dataset-7"

    @property
    def description(self) -> str:
        return _REQUIREMENT_DESCRIPTIONS[self]


_REQUIREMENT_DESCRIPTIONS: dict[Requirement, str] = {
    Requirement.SCHEMA: "Input tables are well-formed: required columns present, measures numeric and allowed, unit_id unique, no responses rows for unknown units. A property of the CSV container, not of the dataset; not one of the six SPEC.md requirements.",
    Requirement.MD1: "Single session. Exactly one preparation_id, one session_id and one recording_id (a session is one continuous acquisition, so a second recording is a second session).",
    Requirement.MD2: "Repeated trials. At least 10 trials of at least one condition; SHOULD 20. Below 10 the two halves are too short for the correlation to be stable.",
    Requirement.MD3: "Multiple recording units. At least 8 units active in every trial of the evaluated condition; SHOULD 30. A unit is active in a trial when it has a row for it with every measure non-null.",
    Requirement.MD4: "Stimulus timestamps. Onset time of every stimulus on the same clock as the responses, non-null, strictly increasing within a condition, one timestamp and one condition per trial_index across units.",
    Requirement.MD5: "Trial-level resolution. Exactly one row per (unit_id, trial_index); rows are trials, not summary statistics.",
    Requirement.MD6: "Post-stimulus window. At least 2.0 s of recording after each stimulus onset: the declared post_stim_window_s is at least 2.0 s and fits before the next onset (minus load_duration_s).",
    Requirement.MD7: "Pre-stimulus window. Applies when measures are computed from spikes: the declared pre_stim_window_s is at least 1.0 s, fits before the first onset on the recording clock, and fits between every previous load end and the next onset.",
}


class ContractViolation(Exception):
    """Raised when input tables violate a benchmark data contract requirement."""

    def __init__(
        self, requirement: Requirement | str, message: str, found: Any = None, required: Any = None
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
    """Read units and responses CSV tables with contract-enforced column dtypes.
    Args:
        units_path: Path to the units CSV file.
        responses_path: Path to the responses CSV file.
    Returns:
        Tuple of (units, responses) DataFrames with string IDs and Int64 trial/timestamp columns.
    """
    units = pd.read_csv(units_path, dtype=dict.fromkeys(ID_COLUMNS, str))
    resp_dtypes = {"unit_id": str, "condition": str, "trial_index": "Int64", "stim_time_ns": "Int64"}
    return units, pd.read_csv(responses_path, dtype=resp_dtypes)


def read_spikes(spikes_path: str | Path) -> pd.DataFrame:
    """Read spikes CSV table with contract-enforced column dtypes.
    Args:
        spikes_path: Path to the spikes CSV file.
    Returns:
        DataFrame with string unit_id and Int64 spike_time_ns columns.
    """
    return pd.read_csv(spikes_path, dtype={"unit_id": str, "spike_time_ns": "Int64"})


def _validate_durations(post_stim_window_s: float, load_duration_s: float) -> None:
    if not math.isfinite(post_stim_window_s) or post_stim_window_s <= 0.0:
        raise ValueError(f"post_stim_window_s must be finite and > 0, got {post_stim_window_s}.")
    if not math.isfinite(load_duration_s) or load_duration_s < 0.0:
        raise ValueError(f"load_duration_s must be finite and >= 0, got {load_duration_s}.")


@dataclass
class ValidationContext:
    """Working state passed through the ordered contract check registry."""

    units: pd.DataFrame
    responses: pd.DataFrame
    measures: list[str]
    post_stim_window_s: float
    load_duration_s: float
    forbidden: frozenset[str]
    preparation: Preparation | None
    conditions: dict[str, Condition] | None
    spikes: pd.DataFrame | None
    conditions_info: dict[str, dict[str, Any]] = field(default_factory=dict)
    trials: pd.DataFrame | None = None
    gaps_s: list[float] = field(default_factory=list)


@frozen("SPEC conformance levels")
def build_report(ctx: ValidationContext) -> dict[str, Any]:
    """Build the conformance report dictionary from a validated context.
    Args:
        ctx: Populated ValidationContext after all CHECKS have passed.
    Returns:
        Conformance report dictionary with SHOULD levels, best condition, inclusion counts, and metadata.
    """
    conditions_info = ctx.conditions_info
    evaluated_conditions = sorted(
        c
        for c, info in conditions_info.items()
        if info["n_trials"] >= MD2_MUST and info["n_units_active"] >= MD3_MUST
    )
    n_units_active = max(conditions_info[c]["n_units_active"] for c in evaluated_conditions)
    min_inter_stimulus_s = float(min(ctx.gaps_s))

    evaluated_set = set(evaluated_conditions)
    for cond, info in conditions_info.items():
        if cond in evaluated_set:
            failed: list[str] = []
            if info["n_trials"] < MD2_SHOULD:
                failed.append(Requirement.MD2.value)
            if info["n_units_active"] < MD3_SHOULD:
                failed.append(Requirement.MD3.value)
            info["should_failed"] = failed
        else:
            info["should_failed"] = None

    best_condition = min(
        evaluated_conditions,
        key=lambda c: (
            len(conditions_info[c]["should_failed"]),
            -conditions_info[c]["n_units_active"],
            -conditions_info[c]["n_trials"],
            c,
        ),
    )
    should_failed = list(conditions_info[best_condition]["should_failed"])
    conformance = FULLY_CONFORMING if not should_failed else CONFORMING

    cond_meta = (
        {
            label: {"fingerprint": cond.fingerprint, **cond.model_dump(exclude={"protocol"})}
            for label, cond in ctx.conditions.items()
        }
        if ctx.conditions is not None
        else None
    )
    metadata = {
        "preparation": ctx.preparation.model_dump() if ctx.preparation is not None else None,
        "conditions": cond_meta,
        "n_spikes": int(len(ctx.spikes)) if ctx.spikes is not None else None,
    }

    declared_exclusions = {
        "units": sum(1 for e in ctx.preparation.exclusions if e.kind == "unit") if ctx.preparation else 0,
        "trials": sum(1 for e in ctx.preparation.exclusions if e.kind == "trial") if ctx.preparation else 0,
    }
    inclusion = {
        "rule": INCLUSION_RULE,
        "per_condition": {
            cond: {
                "n_units_in_tables": info["n_units_in_tables"],
                "n_units_included": info["n_units_active"],
                "n_units_excluded_by_rule": info["n_units_excluded_by_rule"],
                "n_rows_missing": info["n_rows_missing"],
                "n_trials": info["n_trials"],
            }
            for cond, info in conditions_info.items()
        },
        "declared": declared_exclusions,
    }

    return {
        "spec_version": SPEC_VERSION,
        "n_preparations": int(ctx.units["preparation_id"].nunique()),
        "n_sessions": int(ctx.units["session_id"].nunique()),
        "n_recordings": int(ctx.units["recording_id"].nunique()),
        "n_units": int(len(ctx.units)),
        "n_units_active": int(n_units_active),
        "n_conditions": int(ctx.responses["condition"].nunique()),
        "n_trials": int(ctx.responses["trial_index"].nunique()),
        "trials_per_unit_condition": float(ctx.responses.groupby(["unit_id", "condition"]).size().median()),
        "conditions": conditions_info,
        "evaluated_conditions": evaluated_conditions,
        "best_condition": best_condition,
        "should_failed": should_failed,
        "conformance": conformance,
        "post_stim_window_s": float(ctx.post_stim_window_s),
        "load_duration_s": float(ctx.load_duration_s),
        "min_inter_stimulus_s": min_inter_stimulus_s,
        "inclusion": inclusion,
        "metadata": metadata,
    }


@frozen("SPEC conformance levels")
def validate(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    measures: list[str],
    post_stim_window_s: float,
    load_duration_s: float = 0.0,
    extra_forbidden: set[str] | None = None,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
    spikes: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Validate units and responses against SCHEMA and min-dataset-1 through min-dataset-6.
    Args:
        units: Recording-unit DataFrame (unit_id, recording_id, session_id, preparation_id).
        responses: Trial-level response DataFrame (unit_id, trial_index, stim_time_ns, condition, measures).
        measures: Measure column names to validate.
        post_stim_window_s: Declared post-stimulus analysis window in seconds.
        load_duration_s: Conditioning train duration in seconds (default 0.0).
        extra_forbidden: Additional column names disallowed as measures.
        preparation: Optional validated Preparation sidecar model.
        conditions: Optional mapping of condition labels to Condition sidecar models.
        spikes: Optional spike-timestamp DataFrame.
    Returns:
        Conformance report dictionary with counts, evaluated conditions, conformance level, and metadata.
    """
    from .checks import CHECKS

    _validate_durations(post_stim_window_s, load_duration_s)
    units_copy = units.assign(**{c: units[c].astype(str) for c in ID_COLUMNS if c in units.columns})
    ctx = ValidationContext(
        units=units_copy,
        responses=responses.copy(),
        measures=list(measures),
        post_stim_window_s=post_stim_window_s,
        load_duration_s=load_duration_s,
        forbidden=FORBIDDEN_MEASURES | frozenset(extra_forbidden or ()),
        preparation=preparation,
        conditions=conditions,
        spikes=spikes.copy() if spikes is not None else None,
    )
    for _, _, check_fn in CHECKS:
        check_fn(ctx)
    return build_report(ctx)


if __name__ == "__main__":
    from .cli import check_main

    raise SystemExit(check_main())
