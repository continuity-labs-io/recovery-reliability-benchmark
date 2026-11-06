"""Ordered contract check functions and registry for the Recovery Reliability Benchmark."""

from __future__ import annotations

from collections.abc import Callable

from pandas.api.types import is_numeric_dtype

from . import contract
from .contract import ContractViolation, Requirement, ValidationContext


def check_required_columns(ctx: ValidationContext) -> None:
    """Check that units and responses contain all required columns (SPEC §9); fills nothing on ctx.
    Args:
        ctx: Validation context with working copies of units and responses.
    Raises:
        ContractViolation: With Requirement.SCHEMA if a required column is missing.
    """
    for col in contract.UNITS_REQUIRED:
        if col not in ctx.units.columns:
            raise ContractViolation(Requirement.SCHEMA, f"units is missing required column '{col}'.")
    for col in contract.RESPONSES_REQUIRED:
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
    for col in contract.ID_COLUMNS:
        ctx.units[col] = ctx.units[col].astype(str)
    ctx.responses["unit_id"] = ctx.responses["unit_id"].astype(str)
    unit_counts = ctx.units["unit_id"].value_counts(sort=False)
    duplicates = unit_counts[unit_counts > 1]
    if not duplicates.empty:
        bad_id, count = duplicates.index[0], int(duplicates.iloc[0])
        msg = f"unit_id '{bad_id}' appears {count} times in units, requires 1."
        raise ContractViolation(Requirement.SCHEMA, msg, found=count, required=1)
    orphan_mask = ~ctx.responses["unit_id"].isin(set(ctx.units["unit_id"]))
    if orphan_mask.any():
        bad_id = ctx.responses.loc[orphan_mask, "unit_id"].iloc[0]
        count = int((ctx.responses["unit_id"] == bad_id).sum())
        msg = f"{count} responses rows reference unit_id '{bad_id}', which is not in units."
        raise ContractViolation(Requirement.SCHEMA, msg, found=count, required=0)
    null_trial_index = int(ctx.responses["trial_index"].isna().sum())
    if null_trial_index > 0:
        msg = f"{null_trial_index} responses rows have a null trial_index, requires 0."
        raise ContractViolation(Requirement.SCHEMA, msg, found=null_trial_index, required=0)


def check_measures_vary_within_groups(ctx: ValidationContext) -> None:
    """Check that each measure varies within at least one (unit_id, condition) group (SPEC §9); fills nothing on ctx.
    Args:
        ctx: Validation context with responses and measures.
    Raises:
        ContractViolation: With Requirement.SCHEMA if a measure is constant within every (unit_id, condition) group.
    """
    g = ctx.responses.groupby(["unit_id", "condition"], sort=False, dropna=False)
    for measure in ctx.measures:
        nun, cnt = g[measure].nunique(), g[measure].count()
        eligible = cnt >= 2
        if eligible.any() and (nun[eligible] <= 1).all():
            msg = f"measure '{measure}' is constant within every (unit_id, condition) group and carries no trial-to-trial information, requires variation in at least one group."
            raise ContractViolation(Requirement.SCHEMA, msg)


def check_sidecars(ctx: ValidationContext) -> None:
    """Check preparation, exclusions, conditions, and spikes sidecars (SPEC §10, §11); casts spikes.unit_id on ctx.
    Args:
        ctx: Validation context with units, responses, preparation, conditions, and spikes.
    Raises:
        ContractViolation: With Requirement.SCHEMA on sidecar mismatch, exclusion contradiction, or invalid spikes.
    """
    if ctx.preparation is not None:
        prep_id = ctx.preparation.preparation_id
        if str(prep_id) not in set(ctx.units["preparation_id"].astype(str)):
            u_prep = str(ctx.units["preparation_id"].iloc[0]) if len(ctx.units) > 0 else ""
            msg = f"preparation.json preparation_id '{prep_id}' does not match units ('{u_prep}')."
            raise ContractViolation(Requirement.SCHEMA, msg, found=prep_id, required=u_prep)
        present_units = set(ctx.units["unit_id"])
        present_trials = set(ctx.responses["trial_index"].astype(str))
        for excl in ctx.preparation.exclusions:
            if excl.kind == "unit" and excl.id in present_units:
                msg = f"exclusions lists unit '{excl.id}' as excluded but it is present in units."
                raise ContractViolation(Requirement.SCHEMA, msg, found=excl.id)
            if excl.kind == "trial" and excl.id in present_trials:
                msg = f"exclusions lists trial '{excl.id}' as excluded but it is present in responses."
                raise ContractViolation(Requirement.SCHEMA, msg, found=excl.id)
    if ctx.conditions is not None:
        for cond in ctx.responses["condition"].astype(str).unique():
            if cond not in ctx.conditions:
                msg = f"condition '{cond}' in responses has no entry in conditions.json."
                raise ContractViolation(Requirement.SCHEMA, msg, found=cond)
    if ctx.spikes is not None:
        for col in contract.SPIKES_REQUIRED:
            if col not in ctx.spikes.columns:
                raise ContractViolation(Requirement.SCHEMA, f"spikes is missing required column '{col}'.")
        null_spike_time = int(ctx.spikes["spike_time_ns"].isna().sum())
        if null_spike_time > 0:
            msg = f"{null_spike_time} spikes rows have a null spike_time_ns, requires 0."
            raise ContractViolation(Requirement.SCHEMA, msg, found=null_spike_time, required=0)
        ctx.spikes["unit_id"] = ctx.spikes["unit_id"].astype(str)
        orphan_spikes = ~ctx.spikes["unit_id"].isin(set(ctx.units["unit_id"]))
        if orphan_spikes.any():
            bad_id = ctx.spikes.loc[orphan_spikes, "unit_id"].iloc[0]
            count = int((ctx.spikes["unit_id"] == bad_id).sum())
            msg = f"{count} spikes rows reference unit_id '{bad_id}', which is not in units."
            raise ContractViolation(Requirement.SCHEMA, msg, found=count, required=0)


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
            msg = f"{n_distinct} distinct {col} values ({vals}), requires exactly 1."
            raise ContractViolation(Requirement.MD1, msg, found=n_distinct, required=1)


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
    n_tr, all_complete = g["trial_index"].nunique(), g["complete"].all()
    n_trials_cond = ctx.responses.groupby("condition")["trial_index"].nunique()
    unit_active = (n_tr == n_tr.index.get_level_values("condition").map(n_trials_cond)) & all_complete
    ctx.conditions_info = {}
    for cond in ctx.responses["condition"].unique():
        n_trials_c = int(n_trials_cond[cond])
        cond_active = unit_active.loc[cond] if (n_trials_c > 0 and cond in unit_active.index) else None
        active_units = (
            sorted(str(u) for u in cond_active.index[cond_active]) if cond_active is not None else []
        )
        present_cells = int(n_tr.loc[cond].sum()) if cond_active is not None else 0
        n_active_c = len(active_units)
        ctx.conditions_info[str(cond)] = {
            "n_trials": n_trials_c,
            "n_units_active": n_active_c,
            "active_units": active_units,
            "n_units_in_tables": n_units_in_tables,
            "n_units_excluded_by_rule": n_units_in_tables - n_active_c,
            "n_rows_missing": n_units_in_tables * n_trials_c - present_cells,
        }
    best_trial_cond = max(ctx.conditions_info, key=lambda c: ctx.conditions_info[c]["n_trials"])
    max_trials = ctx.conditions_info[best_trial_cond]["n_trials"]
    if max_trials < contract.MD2_MUST:
        msg = f"At most {max_trials} trials in any condition (condition '{best_trial_cond}'), requires {contract.MD2_MUST}."
        raise ContractViolation(Requirement.MD2, msg, found=max_trials, required=contract.MD2_MUST)


def check_active_units(ctx: ValidationContext) -> None:
    """Check min-dataset-3: at least MD3_MUST active units in an evaluable condition (SPEC §4); fills nothing on ctx.
    Args:
        ctx: Validation context with conditions_info populated by check_trials_per_condition.
    Raises:
        ContractViolation: With Requirement.MD3 if no condition with >= MD2_MUST trials has >= MD3_MUST active units.
    """
    if not ctx.conditions_info:
        check_trials_per_condition(ctx)
    eval_conds = [c for c, info in ctx.conditions_info.items() if info["n_trials"] >= contract.MD2_MUST]
    best_eval_cond = max(eval_conds, key=lambda c: ctx.conditions_info[c]["n_units_active"])
    max_active = ctx.conditions_info[best_eval_cond]["n_units_active"]
    if max_active < contract.MD3_MUST:
        msg = f"At most {max_active} units active in every trial of any condition with enough trials (condition '{best_eval_cond}'), requires {contract.MD3_MUST}."
        raise ContractViolation(Requirement.MD3, msg, found=max_active, required=contract.MD3_MUST)


def check_stimulus_timeline(ctx: ValidationContext) -> None:
    """Check min-dataset-4: non-null, consistent, strictly increasing stim_time_ns (SPEC §4); fills ctx.trials.
    Args:
        ctx: Validation context with responses table.
    Raises:
        ContractViolation: With Requirement.MD4 on null, inconsistent, or non-increasing stimulus timestamps.
    """
    null_stim = int(ctx.responses["stim_time_ns"].isna().sum())
    if null_stim > 0:
        msg = f"{null_stim} responses rows have a null stim_time_ns, requires 0."
        raise ContractViolation(Requirement.MD4, msg, found=null_stim, required=0)
    for trial_idx, trial_rows in ctx.responses.groupby("trial_index"):
        n_cond = int(trial_rows["condition"].nunique(dropna=False))
        if n_cond != 1:
            vals = ", ".join(f"'{v}'" for v in sorted(trial_rows["condition"].astype(str).unique()))
            msg = f"trial_index {int(trial_idx)} has {n_cond} distinct condition values ({vals}), requires 1."
            raise ContractViolation(Requirement.MD4, msg, found=n_cond, required=1)
    for trial_idx, trial_rows in ctx.responses.groupby("trial_index"):
        n_times = int(trial_rows["stim_time_ns"].nunique())
        if n_times != 1:
            msg = f"trial_index {int(trial_idx)} has {n_times} distinct stim_time_ns values, requires 1."
            raise ContractViolation(Requirement.MD4, msg, found=n_times, required=1)
    cols = ["trial_index", "condition", "stim_time_ns"]
    ctx.trials = ctx.responses[cols].drop_duplicates().sort_values("trial_index").reset_index(drop=True)
    for cond, cond_trials in ctx.trials.groupby("condition", sort=False):
        prev_trial: int | None = None
        prev_time: int | None = None
        for row in cond_trials.itertuples(index=False):
            curr_trial, curr_time = int(row.trial_index), int(row.stim_time_ns)
            if prev_time is not None and curr_time <= prev_time:
                msg = f"stim_time_ns is not strictly increasing within condition '{cond}': trial {curr_trial} at {curr_time} ns does not exceed trial {prev_trial} at {prev_time} ns."
                raise ContractViolation(Requirement.MD4, msg, found=curr_time, required=prev_time)
            prev_trial, prev_time = curr_trial, curr_time


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
        msg = f"{count} rows for trial {int(bad_trial)} on unit '{bad_unit}', requires 1."
        raise ContractViolation(Requirement.MD5, msg, found=count, required=1)


def check_post_stimulus_window(ctx: ValidationContext) -> None:
    """Check min-dataset-6: post-stimulus window >= 2.0 s and fits before next onset (SPEC §4); fills ctx.gaps_s.
    Args:
        ctx: Validation context with post_stim_window_s, load_duration_s, and trials.
    Raises:
        ContractViolation: With Requirement.MD6 if post_stim_window_s < MD6_MUST or exceeds available inter-trial time.
    """
    if ctx.post_stim_window_s < contract.MD6_MUST:
        req_min = contract.MD6_MUST
        msg = f"Post-stimulus window {ctx.post_stim_window_s:.1f} s, requires {req_min:.1f} s."
        raise ContractViolation(Requirement.MD6, msg, found=float(ctx.post_stim_window_s), required=req_min)
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
            req_w = float(ctx.post_stim_window_s)
            msg = f"Trial {trial_indices[i]} has {available:.3f} s available before the next stimulus (gap {gap_s:.3f} s minus load {ctx.load_duration_s:.3f} s), requires {req_w:.3f} s."
            raise ContractViolation(Requirement.MD6, msg, found=float(available), required=req_w)


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
