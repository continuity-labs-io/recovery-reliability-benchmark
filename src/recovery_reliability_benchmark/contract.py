"""Data contract reader and validator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from pandas.api.types import is_numeric_dtype

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

CONFORMING = "conforming"
FULLY_CONFORMING = "fully_conforming"

INCLUSION_RULE = (
    "A unit is included in a condition if and only if it has a row for every trial of that condition "
    "with every measure non-null. All present trials are used; no trial is excluded by rule in v0.1.x."
)


class Requirement(StrEnum):
    """Minimum dataset (`min-dataset-*`) requirements from SPEC.md.

    A dataset must satisfy every minimum dataset requirement's MUST threshold to be
    "conforming" and every SHOULD threshold to be "fully_conforming".
    validate() checks them in numeric order and raises ContractViolation
    on the first failure.
    """

    SCHEMA = "SCHEMA"
    MD1 = "min-dataset-1"
    MD2 = "min-dataset-2"
    MD3 = "min-dataset-3"
    MD4 = "min-dataset-4"
    MD5 = "min-dataset-5"
    MD6 = "min-dataset-6"

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


def read_spikes(spikes_path: str | Path) -> pd.DataFrame:
    """Read spikes CSV table with contract-enforced column dtypes."""
    return pd.read_csv(spikes_path, dtype={"unit_id": str, "spike_time_ns": "Int64"})


def _validate_durations(post_stim_window_s: float, load_duration_s: float) -> None:
    if not math.isfinite(post_stim_window_s) or post_stim_window_s <= 0.0:
        raise ValueError(f"post_stim_window_s must be finite and > 0, got {post_stim_window_s}.")
    if not math.isfinite(load_duration_s) or load_duration_s < 0.0:
        raise ValueError(f"load_duration_s must be finite and >= 0, got {load_duration_s}.")


@dataclass
class ValidationContext:
    """Working state passed through the ordered contract check registry."""

    units: pd.DataFrame            # working copy, ids cast to str
    responses: pd.DataFrame        # working copy
    measures: list[str]
    post_stim_window_s: float
    load_duration_s: float
    forbidden: frozenset[str]
    preparation: Preparation | None
    conditions: dict[str, Condition] | None
    spikes: pd.DataFrame | None
    # derived, filled by checks in order:
    conditions_info: dict[str, dict[str, Any]] = field(default_factory=dict)
    trials: pd.DataFrame | None = None     # distinct (trial_index, condition, stim_time_ns), sorted
    gaps_s: list[float] = field(default_factory=list)


def check_required_columns(ctx: ValidationContext) -> None:
    """Check that units and responses contain all required columns (SPEC §9); fills nothing on ctx.

    Args:
        ctx: Validation context with working copies of units and responses.

    Raises:
        ContractViolation: With Requirement.SCHEMA if a required column is missing.
    """
    for col in UNITS_REQUIRED:
        if col not in ctx.units.columns:
            raise ContractViolation(Requirement.SCHEMA, f"units is missing required column '{col}'.")
    for col in RESPONSES_REQUIRED:
        if col not in ctx.responses.columns:
            raise ContractViolation(Requirement.SCHEMA, f"responses is missing required column '{col}'.")


def check_measures_allowed_and_numeric(ctx: ValidationContext) -> None:
    """Check that measures are non-empty, present, allowed, numeric, and not all-null (SPEC §9); fills nothing on ctx.

    Args:
        ctx: Validation context with responses, measures, and forbidden column set.

    Raises:
        ContractViolation: With Requirement.SCHEMA if any measure is missing, forbidden, non-numeric, or all-null.
    """
    if not ctx.measures:
        raise ContractViolation(Requirement.SCHEMA, "measures must not be empty.")
    for measure in ctx.measures:
        if measure not in ctx.responses.columns:
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is not a column of responses.")
    for measure in ctx.measures:
        if measure in ctx.forbidden:
            raise ContractViolation(Requirement.SCHEMA, f"'{measure}' is not allowed as a measure.")
    for measure in ctx.measures:
        if not is_numeric_dtype(ctx.responses[measure]):
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is not numeric.")
        if ctx.responses[measure].isna().all():
            raise ContractViolation(Requirement.SCHEMA, f"measure '{measure}' is entirely null.")


def check_identifiers(ctx: ValidationContext) -> None:
    """Check unique unit_id, no orphan response rows, and non-null trial_index (SPEC §9); casts ID columns on ctx.

    Args:
        ctx: Validation context with units and responses tables.

    Raises:
        ContractViolation: With Requirement.SCHEMA on duplicate unit_id, orphan response unit_id, or null trial_index.
    """
    for col in ID_COLUMNS:
        ctx.units[col] = ctx.units[col].astype(str)
    ctx.responses["unit_id"] = ctx.responses["unit_id"].astype(str)

    unit_counts = ctx.units["unit_id"].value_counts(sort=False)
    duplicates = unit_counts[unit_counts > 1]
    if not duplicates.empty:
        bad_id, count = duplicates.index[0], int(duplicates.iloc[0])
        raise ContractViolation(
            Requirement.SCHEMA,
            f"unit_id '{bad_id}' appears {count} times in units, requires 1.",
            found=count,
            required=1,
        )

    orphan_mask = ~ctx.responses["unit_id"].isin(set(ctx.units["unit_id"]))
    if orphan_mask.any():
        bad_id = ctx.responses.loc[orphan_mask, "unit_id"].iloc[0]
        count = int((ctx.responses["unit_id"] == bad_id).sum())
        raise ContractViolation(
            Requirement.SCHEMA,
            f"{count} responses rows reference unit_id '{bad_id}', which is not in units.",
            found=count,
            required=0,
        )

    null_trial_index = int(ctx.responses["trial_index"].isna().sum())
    if null_trial_index > 0:
        raise ContractViolation(
            Requirement.SCHEMA,
            f"{null_trial_index} responses rows have a null trial_index, requires 0.",
            found=null_trial_index,
            required=0,
        )


def check_measures_vary_within_groups(ctx: ValidationContext) -> None:
    """Check that each measure varies within at least one (unit_id, condition) group (SPEC §9); fills nothing on ctx.

    Args:
        ctx: Validation context with responses and measures.

    Raises:
        ContractViolation: With Requirement.SCHEMA if a measure is constant within every (unit_id, condition) group.
    """
    g = ctx.responses.groupby(["unit_id", "condition"], sort=False, dropna=False)
    for measure in ctx.measures:
        nun = g[measure].nunique()
        cnt = g[measure].count()
        eligible = cnt >= 2
        if eligible.any() and (nun[eligible] <= 1).all():
            raise ContractViolation(
                Requirement.SCHEMA,
                f"measure '{measure}' is constant within every (unit_id, condition) group "
                "and carries no trial-to-trial information, requires variation in at least one group.",
            )


def check_sidecars(ctx: ValidationContext) -> None:
    """Check preparation, exclusions, conditions, and spikes sidecars (SPEC §10, §11); casts spikes.unit_id on ctx.

    Args:
        ctx: Validation context with units, responses, preparation, conditions, and spikes.

    Raises:
        ContractViolation: With Requirement.SCHEMA on sidecar mismatch, exclusion contradiction, or invalid spikes.
    """
    if ctx.preparation is not None:
        units_prep_ids = set(ctx.units["preparation_id"].astype(str))
        if str(ctx.preparation.preparation_id) not in units_prep_ids:
            units_prep_id = str(ctx.units["preparation_id"].iloc[0]) if len(ctx.units) > 0 else ""
            raise ContractViolation(
                Requirement.SCHEMA,
                f"preparation.json preparation_id '{ctx.preparation.preparation_id}' does not match units ('{units_prep_id}').",
                found=ctx.preparation.preparation_id,
                required=units_prep_id,
            )
        present_units = set(ctx.units["unit_id"])
        present_trials = set(ctx.responses["trial_index"].astype(str))
        for excl in ctx.preparation.exclusions:
            if excl.kind == "unit" and excl.id in present_units:
                raise ContractViolation(
                    Requirement.SCHEMA,
                    f"exclusions lists unit '{excl.id}' as excluded but it is present in units.",
                    found=excl.id,
                )
            if excl.kind == "trial" and excl.id in present_trials:
                raise ContractViolation(
                    Requirement.SCHEMA,
                    f"exclusions lists trial '{excl.id}' as excluded but it is present in responses.",
                    found=excl.id,
                )

    if ctx.conditions is not None:
        for cond in ctx.responses["condition"].astype(str).unique():
            if cond not in ctx.conditions:
                raise ContractViolation(
                    Requirement.SCHEMA,
                    f"condition '{cond}' in responses has no entry in conditions.json.",
                    found=cond,
                )

    if ctx.spikes is not None:
        for col in SPIKES_REQUIRED:
            if col not in ctx.spikes.columns:
                raise ContractViolation(Requirement.SCHEMA, f"spikes is missing required column '{col}'.")
        null_spike_time = int(ctx.spikes["spike_time_ns"].isna().sum())
        if null_spike_time > 0:
            raise ContractViolation(
                Requirement.SCHEMA,
                f"{null_spike_time} spikes rows have a null spike_time_ns, requires 0.",
                found=null_spike_time,
                required=0,
            )
        ctx.spikes["unit_id"] = ctx.spikes["unit_id"].astype(str)
        orphan_spikes = ~ctx.spikes["unit_id"].isin(set(ctx.units["unit_id"]))
        if orphan_spikes.any():
            bad_id = ctx.spikes.loc[orphan_spikes, "unit_id"].iloc[0]
            count = int((ctx.spikes["unit_id"] == bad_id).sum())
            raise ContractViolation(
                Requirement.SCHEMA,
                f"{count} spikes rows reference unit_id '{bad_id}', which is not in units.",
                found=count,
                required=0,
            )


def check_single_session(ctx: ValidationContext) -> None:
    """Check min-dataset-1: single preparation_id, session_id, and recording_id (SPEC §4); fills nothing on ctx.

    Args:
        ctx: Validation context with units table.

    Raises:
        ContractViolation: With Requirement.MD1 if any hierarchy column has != 1 distinct value.
    """
    for col in ("preparation_id", "session_id", "recording_id"):
        n_distinct = int(ctx.units[col].nunique())
        if n_distinct != 1:
            vals = ", ".join(f"'{v}'" for v in ctx.units[col].unique())
            raise ContractViolation(
                Requirement.MD1,
                f"{n_distinct} distinct {col} values ({vals}), requires exactly 1.",
                found=n_distinct,
                required=1,
            )


def check_trials_per_condition(ctx: ValidationContext) -> None:
    """Check min-dataset-2: at least MD2_MUST trials in some condition (SPEC §4); fills ctx.conditions_info.

    Args:
        ctx: Validation context with units, responses, and measures.

    Raises:
        ContractViolation: With Requirement.MD2 if no condition has at least MD2_MUST trials.
    """
    n_units_in_tables = int(len(ctx.units))
    complete = ctx.responses[ctx.measures].notna().all(axis=1)
    g = ctx.responses.assign(complete=complete).groupby(["condition", "unit_id"], sort=False)
    n_tr = g["trial_index"].nunique()
    all_complete = g["complete"].all()
    n_trials_cond = ctx.responses.groupby("condition")["trial_index"].nunique()
    cond_trials_for_unit = n_tr.index.get_level_values("condition").map(n_trials_cond)
    unit_active = (n_tr == cond_trials_for_unit) & all_complete

    ctx.conditions_info = {}
    for cond in ctx.responses["condition"].unique():
        cond_str = str(cond)
        n_trials_c = int(n_trials_cond[cond])
        if n_trials_c > 0 and cond in unit_active.index:
            cond_active = unit_active.loc[cond]
            active_unit_list = sorted(str(u) for u in cond_active.index[cond_active])
            present_cells = int(n_tr.loc[cond].sum())
        else:
            active_unit_list = []
            present_cells = 0
        n_active_c = len(active_unit_list)
        ctx.conditions_info[cond_str] = {
            "n_trials": n_trials_c,
            "n_units_active": n_active_c,
            "active_units": active_unit_list,
            "n_units_in_tables": n_units_in_tables,
            "n_units_excluded_by_rule": n_units_in_tables - n_active_c,
            "n_rows_missing": n_units_in_tables * n_trials_c - present_cells,
        }

    best_trial_cond = max(ctx.conditions_info, key=lambda c: ctx.conditions_info[c]["n_trials"])
    max_trials = ctx.conditions_info[best_trial_cond]["n_trials"]
    if max_trials < MD2_MUST:
        raise ContractViolation(
            Requirement.MD2,
            f"At most {max_trials} trials in any condition (condition '{best_trial_cond}'), requires {MD2_MUST}.",
            found=max_trials,
            required=MD2_MUST,
        )


def check_active_units(ctx: ValidationContext) -> None:
    """Check min-dataset-3: at least MD3_MUST active units in an evaluable condition (SPEC §4); fills nothing on ctx.

    Args:
        ctx: Validation context with conditions_info populated by check_trials_per_condition.

    Raises:
        ContractViolation: With Requirement.MD3 if no condition with >= MD2_MUST trials has >= MD3_MUST active units.
    """
    if not ctx.conditions_info:
        check_trials_per_condition(ctx)
    evaluable_conditions = [c for c, info in ctx.conditions_info.items() if info["n_trials"] >= MD2_MUST]
    best_eval_cond = max(evaluable_conditions, key=lambda c: ctx.conditions_info[c]["n_units_active"])
    max_active = ctx.conditions_info[best_eval_cond]["n_units_active"]
    if max_active < MD3_MUST:
        raise ContractViolation(
            Requirement.MD3,
            f"At most {max_active} units active in every trial of any condition with enough trials (condition '{best_eval_cond}'), requires {MD3_MUST}.",
            found=max_active,
            required=MD3_MUST,
        )


def check_stimulus_timeline(ctx: ValidationContext) -> None:
    """Check min-dataset-4: non-null, consistent, strictly increasing stim_time_ns (SPEC §4); fills ctx.trials.

    Args:
        ctx: Validation context with responses table.

    Raises:
        ContractViolation: With Requirement.MD4 on null, inconsistent, or non-increasing stimulus timestamps.
    """
    null_stim = int(ctx.responses["stim_time_ns"].isna().sum())
    if null_stim > 0:
        raise ContractViolation(
            Requirement.MD4,
            f"{null_stim} responses rows have a null stim_time_ns, requires 0.",
            found=null_stim,
            required=0,
        )

    for trial_idx, trial_rows in ctx.responses.groupby("trial_index"):
        n_cond = int(trial_rows["condition"].nunique(dropna=False))
        if n_cond != 1:
            vals = ", ".join(f"'{v}'" for v in sorted(trial_rows["condition"].astype(str).unique()))
            raise ContractViolation(
                Requirement.MD4,
                f"trial_index {int(trial_idx)} has {n_cond} distinct condition values ({vals}), requires 1.",
                found=n_cond,
                required=1,
            )

    for trial_idx, trial_rows in ctx.responses.groupby("trial_index"):
        n_times = int(trial_rows["stim_time_ns"].nunique())
        if n_times != 1:
            raise ContractViolation(
                Requirement.MD4,
                f"trial_index {int(trial_idx)} has {n_times} distinct stim_time_ns values, requires 1.",
                found=n_times,
                required=1,
            )

    ctx.trials = (
        ctx.responses[["trial_index", "condition", "stim_time_ns"]]
        .drop_duplicates()
        .sort_values("trial_index")
        .reset_index(drop=True)
    )
    for cond, cond_trials in ctx.trials.groupby("condition", sort=False):
        prev_trial: int | None = None
        prev_time: int | None = None
        for row in cond_trials.itertuples(index=False):
            curr_trial = int(row.trial_index)
            curr_time = int(row.stim_time_ns)
            if prev_time is not None and curr_time <= prev_time:
                raise ContractViolation(
                    Requirement.MD4,
                    f"stim_time_ns is not strictly increasing within condition '{cond}': "
                    f"trial {curr_trial} at {curr_time} ns does not exceed trial {prev_trial} at {prev_time} ns.",
                    found=curr_time,
                    required=prev_time,
                )
            prev_trial = curr_trial
            prev_time = curr_time


def check_one_row_per_unit_trial(ctx: ValidationContext) -> None:
    """Check min-dataset-5: at most one row per (unit_id, trial_index) pair (SPEC §4); fills nothing on ctx.

    Args:
        ctx: Validation context with responses table.

    Raises:
        ContractViolation: With Requirement.MD5 if any (unit_id, trial_index) pair appears more than once.
    """
    pair_counts = ctx.responses.groupby(["unit_id", "trial_index"], sort=False).size()
    dup_pairs = pair_counts[pair_counts > 1]
    if not dup_pairs.empty:
        (bad_unit, bad_trial), count = dup_pairs.index[0], int(dup_pairs.iloc[0])
        raise ContractViolation(
            Requirement.MD5,
            f"{count} rows for trial {int(bad_trial)} on unit '{bad_unit}', requires 1.",
            found=count,
            required=1,
        )


def check_post_stimulus_window(ctx: ValidationContext) -> None:
    """Check min-dataset-6: post-stimulus window >= 2.0 s and fits before next onset (SPEC §4); fills ctx.gaps_s.

    Args:
        ctx: Validation context with post_stim_window_s, load_duration_s, and trials.

    Raises:
        ContractViolation: With Requirement.MD6 if post_stim_window_s < MD6_MUST or exceeds available inter-trial time.
    """
    if ctx.post_stim_window_s < MD6_MUST:
        raise ContractViolation(
            Requirement.MD6,
            f"Post-stimulus window {ctx.post_stim_window_s:.1f} s, requires {MD6_MUST:.1f} s.",
            found=float(ctx.post_stim_window_s),
            required=MD6_MUST,
        )

    if ctx.trials is None:
        check_stimulus_timeline(ctx)
    assert ctx.trials is not None
    trials_by_time = ctx.trials.sort_values(["stim_time_ns", "trial_index"]).reset_index(drop=True)
    onsets = trials_by_time["stim_time_ns"].astype(int).to_list()
    trial_indices = trials_by_time["trial_index"].astype(int).to_list()
    ctx.gaps_s = []
    for i in range(len(onsets) - 1):
        gap_s = (onsets[i + 1] - onsets[i]) / 1e9
        ctx.gaps_s.append(gap_s)
        available = gap_s - ctx.load_duration_s
        if available < ctx.post_stim_window_s:
            raise ContractViolation(
                Requirement.MD6,
                f"Trial {trial_indices[i]} has {available:.3f} s available before the next stimulus "
                f"(gap {gap_s:.3f} s minus load {ctx.load_duration_s:.3f} s), requires {ctx.post_stim_window_s:.3f} s.",
                found=float(available),
                required=float(ctx.post_stim_window_s),
            )


CHECKS: tuple[tuple[Requirement, str, Callable[[ValidationContext], None]], ...] = (
    (Requirement.SCHEMA, "required_columns", check_required_columns),
    (Requirement.SCHEMA, "measures_allowed_and_numeric", check_measures_allowed_and_numeric),
    (Requirement.SCHEMA, "identifiers", check_identifiers),
    (Requirement.SCHEMA, "measures_vary_within_groups", check_measures_vary_within_groups),
    (Requirement.SCHEMA, "sidecars", check_sidecars),
    (Requirement.MD1, "single_session", check_single_session),
    (Requirement.MD2, "trials_per_condition", check_trials_per_condition),
    (Requirement.MD3, "active_units", check_active_units),
    (Requirement.MD4, "stimulus_timeline", check_stimulus_timeline),
    (Requirement.MD5, "one_row_per_unit_trial", check_one_row_per_unit_trial),
    (Requirement.MD6, "post_stimulus_window", check_post_stimulus_window),
)


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

    metadata = {
        "preparation": ctx.preparation.model_dump() if ctx.preparation is not None else None,
        "conditions": (
            {
                label: {
                    "fingerprint": cond.fingerprint,
                    "compound": cond.compound,
                    "dose": cond.dose,
                    "dose_unit": cond.dose_unit,
                    "vehicle": cond.vehicle,
                }
                for label, cond in ctx.conditions.items()
            }
            if ctx.conditions is not None
            else None
        ),
        "n_spikes": int(len(ctx.spikes)) if ctx.spikes is not None else None,
    }

    declared_exclusions = {
        "units": sum(1 for e in ctx.preparation.exclusions if e.kind == "unit") if ctx.preparation is not None else 0,
        "trials": sum(1 for e in ctx.preparation.exclusions if e.kind == "trial")
        if ctx.preparation is not None
        else 0,
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


def validate(
    units: pd.DataFrame, responses: pd.DataFrame, measures: list[str], post_stim_window_s: float,
    load_duration_s: float = 0.0, extra_forbidden: set[str] | None = None,
    preparation: Preparation | None = None, conditions: dict[str, Condition] | None = None,
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
        Conformance report dict with keys: spec_version, n_preparations, n_sessions, n_recordings,
        n_units, n_units_active, n_conditions, n_trials, trials_per_unit_condition, conditions,
        evaluated_conditions, best_condition, should_failed, conformance, post_stim_window_s,
        load_duration_s, min_inter_stimulus_s, inclusion, metadata.
    """
    _validate_durations(post_stim_window_s, load_duration_s)
    units_copy = units.assign(**{c: units[c].astype(str) for c in ID_COLUMNS if c in units.columns})
    ctx = ValidationContext(
        units=units_copy, responses=responses.copy(), measures=list(measures),
        post_stim_window_s=post_stim_window_s, load_duration_s=load_duration_s,
        forbidden=FORBIDDEN_MEASURES | frozenset(extra_forbidden or ()),
        preparation=preparation, conditions=conditions,
        spikes=spikes.copy() if spikes is not None else None,
    )
    for _, _, check_fn in CHECKS:
        check_fn(ctx)
    return build_report(ctx)


def file_sha256(path: str | Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    """Run the contract validator CLI and print the conformance report.

    This report is what a lab shares; the data stays on their machine.
    """
    from .metadata import load_conditions, load_preparation

    parser = argparse.ArgumentParser(
        description="Validate units and responses CSV tables against the benchmark data contract."
    )
    parser.add_argument("units_csv", help="Path to units CSV file.")
    parser.add_argument("responses_csv", help="Path to responses CSV file.")
    parser.add_argument("--measures", required=True, help="Comma-separated measure column names.")
    parser.add_argument(
        "--post-stim-window-s", required=True, type=float, help="Post-stimulus window in seconds."
    )
    parser.add_argument(
        "--load-duration-s", type=float, default=0.0, help="Conditioning load duration in seconds."
    )
    parser.add_argument(
        "--extra-forbidden", default="", help="Comma-separated extra forbidden measure names."
    )
    parser.add_argument("--preparation", default=None, help="Path to preparation.json metadata sidecar.")
    parser.add_argument("--conditions", default=None, help="Path to conditions.json metadata sidecar.")
    parser.add_argument("--spikes", default=None, help="Path to spikes.csv table.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]
    extra_forbidden = [m.strip() for m in args.extra_forbidden.split(",") if m.strip()]

    try:
        _validate_durations(args.post_stim_window_s, args.load_duration_s)
        units, responses = read_tables(args.units_csv, args.responses_csv)
        spikes = read_spikes(args.spikes) if args.spikes is not None else None
        for opt_path in (args.preparation, args.conditions):
            if opt_path is not None and not Path(opt_path).is_file():
                raise FileNotFoundError(opt_path)
    except (FileNotFoundError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    inputs_meta: dict[str, Any] = {
        "units": {"path": args.units_csv, "sha256": file_sha256(args.units_csv)},
        "responses": {"path": args.responses_csv, "sha256": file_sha256(args.responses_csv)},
    }
    if args.preparation is not None:
        inputs_meta["preparation"] = {"path": args.preparation, "sha256": file_sha256(args.preparation)}
    if args.conditions is not None:
        inputs_meta["conditions"] = {"path": args.conditions, "sha256": file_sha256(args.conditions)}
    if args.spikes is not None:
        inputs_meta["spikes"] = {"path": args.spikes, "sha256": file_sha256(args.spikes)}

    arguments_meta = {
        "measures": measures,
        "post_stim_window_s": float(args.post_stim_window_s),
        "load_duration_s": float(args.load_duration_s),
        "extra_forbidden": extra_forbidden,
    }

    try:
        preparation = load_preparation(args.preparation) if args.preparation is not None else None
        conditions = load_conditions(args.conditions) if args.conditions is not None else None
        result = validate(
            units,
            responses,
            measures=measures,
            post_stim_window_s=args.post_stim_window_s,
            load_duration_s=args.load_duration_s,
            extra_forbidden=set(extra_forbidden) if extra_forbidden else None,
            preparation=preparation,
            conditions=conditions,
            spikes=spikes,
        )
    except ContractViolation as exc:
        if args.as_json:
            doc = {
                "spec_version": SPEC_VERSION,
                "status": "violation",
                "inputs": inputs_meta,
                "arguments": arguments_meta,
                "violation": exc.to_dict(),
            }
            print(json.dumps(doc, indent=2, sort_keys=True))
        else:
            print(str(exc))
        return 1

    if args.as_json:
        doc = {
            "spec_version": SPEC_VERSION,
            "status": result["conformance"],
            "inputs": inputs_meta,
            "arguments": arguments_meta,
            "result": result,
        }
        print(json.dumps(doc, indent=2, sort_keys=True))
    else:
        print(f"{result['conformance']} (SPEC v{result['spec_version']})")
        for key, value in result.items():
            if key == "conditions":
                continue
            print(f"{key}: {value}")
        print("conditions:")
        for name, info in result["conditions"].items():
            sf = info["should_failed"] or "none"
            print(
                f"  {name}: n_trials={info['n_trials']} n_units_active={info['n_units_active']} should_failed={sf}"
            )
        decl = result["inclusion"]["declared"]
        for cond in result["evaluated_conditions"]:
            inc = result["inclusion"]["per_condition"][cond]
            print(
                f"{cond}: units included {inc['n_units_included']} of {inc['n_units_in_tables']} "
                f"(excluded by rule {inc['n_units_excluded_by_rule']}, rows missing {inc['n_rows_missing']}); "
                f"declared exclusions units {decl['units']} trials {decl['trials']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
