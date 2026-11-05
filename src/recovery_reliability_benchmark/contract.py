"""Data contract reader and validator for the Recovery Reliability Benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from enum import Enum
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
    """Validate units and responses against SCHEMA and MD-1 through MD-6.

    Each measure must vary within at least one (unit_id, condition) group:
    a column constant within units but varying across them (an electrode
    position, an identifier) would score as perfectly reliable.

    For MD-6, every trial except the last in time must have at least
    ``post_stim_window_s`` seconds available before the next stimulus onset
    (after subtracting ``load_duration_s``). The last trial is not checked
    because the input tables do not record a recording-end timestamp.
    """
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

    null_trial_index = int(responses["trial_index"].isna().sum())
    if null_trial_index > 0:
        raise ContractViolation(
            Requirement.SCHEMA,
            f"{null_trial_index} responses rows have a null trial_index, requires 0.",
            found=null_trial_index,
            required=0,
        )

    g = responses.groupby(["unit_id", "condition"], sort=False, dropna=False)
    for measure in measures:
        nun = g[measure].nunique()
        cnt = g[measure].count()
        eligible = cnt >= 2
        if eligible.any() and (nun[eligible] <= 1).all():
            raise ContractViolation(
                Requirement.SCHEMA,
                f"measure '{measure}' is constant within every (unit_id, condition) group "
                "and carries no trial-to-trial information, requires variation in at least one group.",
            )

    if preparation is not None:
        units_prep_id = str(units["preparation_id"].iloc[0]) if len(units) > 0 else ""
        if str(preparation.preparation_id) != units_prep_id:
            raise ContractViolation(
                Requirement.SCHEMA,
                f"preparation.json preparation_id '{preparation.preparation_id}' does not match units ('{units_prep_id}').",
                found=preparation.preparation_id,
                required=units_prep_id,
            )

    if conditions is not None:
        for cond in responses["condition"].astype(str).unique():
            if cond not in conditions:
                raise ContractViolation(
                    Requirement.SCHEMA,
                    f"condition '{cond}' in responses has no entry in conditions.json.",
                    found=cond,
                )

    if spikes is not None:
        spikes = spikes.copy()
        for col in SPIKES_REQUIRED:
            if col not in spikes.columns:
                raise ContractViolation(Requirement.SCHEMA, f"spikes is missing required column '{col}'.")
        null_spike_time = int(spikes["spike_time_ns"].isna().sum())
        if null_spike_time > 0:
            raise ContractViolation(
                Requirement.SCHEMA,
                f"{null_spike_time} spikes rows have a null spike_time_ns, requires 0.",
                found=null_spike_time,
                required=0,
            )
        spikes["unit_id"] = spikes["unit_id"].astype(str)
        orphan_spikes = ~spikes["unit_id"].isin(set(units["unit_id"]))
        if orphan_spikes.any():
            bad_id = spikes.loc[orphan_spikes, "unit_id"].iloc[0]
            count = int((spikes["unit_id"] == bad_id).sum())
            raise ContractViolation(
                Requirement.SCHEMA,
                f"{count} spikes rows reference unit_id '{bad_id}', which is not in units.",
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

    responses["complete"] = responses[measures].notna().all(axis=1)
    g = responses.groupby(["condition", "unit_id"], sort=False)
    n_tr = g["trial_index"].nunique()
    all_complete = g["complete"].all()
    n_trials_cond = responses.groupby("condition")["trial_index"].nunique()
    responses = responses.drop(columns=["complete"])
    cond_trials_for_unit = n_tr.index.get_level_values("condition").map(n_trials_cond)
    unit_active = (n_tr == cond_trials_for_unit) & all_complete
    n_units_active_by_cond = unit_active.groupby(level="condition", sort=False).sum()
    conditions_info: dict[str, dict[str, Any]] = {
        str(cond): {
            "n_trials": int(n_trials_cond[cond]),
            "n_units_active": int(n_units_active_by_cond[cond]) if int(n_trials_cond[cond]) > 0 else 0,
        }
        for cond in responses["condition"].unique()
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

    null_stim = int(responses["stim_time_ns"].isna().sum())
    if null_stim > 0:
        raise ContractViolation(
            Requirement.MD4,
            f"{null_stim} responses rows have a null stim_time_ns, requires 0.",
            found=null_stim,
            required=0,
        )

    for trial_idx, trial_rows in responses.groupby("trial_index"):
        n_cond = int(trial_rows["condition"].nunique(dropna=False))
        if n_cond != 1:
            vals = ", ".join(f"'{v}'" for v in sorted(trial_rows["condition"].astype(str).unique()))
            raise ContractViolation(
                Requirement.MD4,
                f"trial_index {int(trial_idx)} has {n_cond} distinct condition values ({vals}), requires 1.",
                found=n_cond,
                required=1,
            )

    for trial_idx, trial_rows in responses.groupby("trial_index"):
        n_times = int(trial_rows["stim_time_ns"].nunique())
        if n_times != 1:
            raise ContractViolation(
                Requirement.MD4,
                f"trial_index {int(trial_idx)} has {n_times} distinct stim_time_ns values, requires 1.",
                found=n_times,
                required=1,
            )

    trials = (
        responses[["trial_index", "condition", "stim_time_ns"]]
        .drop_duplicates()
        .sort_values("trial_index")
        .reset_index(drop=True)
    )
    for cond, cond_trials in trials.groupby("condition", sort=False):
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

    pair_counts = responses.groupby(["unit_id", "trial_index"], sort=False).size()
    dup_pairs = pair_counts[pair_counts > 1]
    if not dup_pairs.empty:
        (bad_unit, bad_trial), count = dup_pairs.index[0], int(dup_pairs.iloc[0])
        raise ContractViolation(
            Requirement.MD5,
            f"{count} rows for trial {int(bad_trial)} on unit '{bad_unit}', requires 1.",
            found=count,
            required=1,
        )

    if post_stim_window_s < MD6_MUST:
        raise ContractViolation(
            Requirement.MD6,
            f"Post-stimulus window {post_stim_window_s:.1f} s, requires {MD6_MUST:.1f} s.",
            found=float(post_stim_window_s),
            required=MD6_MUST,
        )

    trials_by_time = trials.sort_values(["stim_time_ns", "trial_index"]).reset_index(drop=True)
    onsets = trials_by_time["stim_time_ns"].astype(int).to_list()
    trial_indices = trials_by_time["trial_index"].astype(int).to_list()
    gaps_s: list[float] = []
    for i in range(len(onsets) - 1):
        gap_s = (onsets[i + 1] - onsets[i]) / 1e9
        gaps_s.append(gap_s)
        available = gap_s - load_duration_s
        if available < post_stim_window_s:
            raise ContractViolation(
                Requirement.MD6,
                f"Trial {trial_indices[i]} has {available:.3f} s available before the next stimulus "
                f"(gap {gap_s:.3f} s minus load {load_duration_s:.3f} s), requires {post_stim_window_s:.3f} s.",
                found=float(available),
                required=float(post_stim_window_s),
            )
    min_inter_stimulus_s = float(min(gaps_s))

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
        "preparation": preparation.model_dump() if preparation is not None else None,
        "conditions": (
            {
                label: {
                    "fingerprint": cond.fingerprint,
                    "compound": cond.compound,
                    "dose": cond.dose,
                    "dose_unit": cond.dose_unit,
                    "vehicle": cond.vehicle,
                }
                for label, cond in conditions.items()
            }
            if conditions is not None
            else None
        ),
        "n_spikes": int(len(spikes)) if spikes is not None else None,
    }

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
        "best_condition": best_condition,
        "should_failed": should_failed,
        "conformance": conformance,
        "post_stim_window_s": float(post_stim_window_s),
        "load_duration_s": float(load_duration_s),
        "min_inter_stimulus_s": min_inter_stimulus_s,
        "metadata": metadata,
    }


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
    parser.add_argument("--post-stim-window-s", required=True, type=float, help="Post-stimulus window in seconds.")
    parser.add_argument("--load-duration-s", type=float, default=0.0, help="Conditioning load duration in seconds.")
    parser.add_argument("--extra-forbidden", default="", help="Comma-separated extra forbidden measure names.")
    parser.add_argument("--preparation", default=None, help="Path to preparation.json metadata sidecar.")
    parser.add_argument("--conditions", default=None, help="Path to conditions.json metadata sidecar.")
    parser.add_argument("--spikes", default=None, help="Path to spikes.csv table.")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Emit report as JSON.")
    args = parser.parse_args(argv)

    measures = [m.strip() for m in args.measures.split(",") if m.strip()]
    extra_forbidden = [m.strip() for m in args.extra_forbidden.split(",") if m.strip()]

    try:
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
            print(f"  {name}: n_trials={info['n_trials']} n_units_active={info['n_units_active']} should_failed={sf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

