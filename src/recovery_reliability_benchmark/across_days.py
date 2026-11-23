"""Across-day unit-matched comparison for two sessions of one preparation."""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from . import controls
from .analysis import AnalysisParams
from .contract import ContractViolation
from .evaluate import reliability_ceiling
from .frozen import frozen
from .inputs import EvaluationInputs, from_spikes
from .metadata import Condition, Preparation, load_conditions, load_preparation
from .spikes import MEASURE_KEYS
from .writer import read_dataset


@dataclass(frozen=True)
class DayInputs:
    """Loaded dataset tables, sidecars, and validated evaluation inputs for one day."""

    directory: Path
    units: pd.DataFrame
    trials: pd.DataFrame
    spikes: pd.DataFrame
    analysis: AnalysisParams
    preparation: Preparation | None
    conditions: dict[str, Condition] | None
    inputs: EvaluationInputs


def _validate_measure_name(measure: str) -> None:
    if not isinstance(measure, str) or measure not in MEASURE_KEYS:
        raise ValueError(f"Unknown measure '{measure}'. Available measures: {', '.join(MEASURE_KEYS)}.")


def load_day(directory: str | Path, measure: str) -> DayInputs:
    """Load and contract-check one spikes-path dataset directory for ``measure``.

    Args:
        directory: Path to the dataset folder written by ``writer.write_dataset``.
        measure: Spikes-path measure name to validate and compute per half.

    Returns:
        Populated ``DayInputs`` instance for the session.

    Raises:
        FileNotFoundError: If ``directory`` or any required dataset file is missing.
        ValueError: If ``measure`` is unknown or CSV integer columns cannot be decoded.
        ContractViolation: If the dataset fails any spikes-path contract requirement.
    """
    _validate_measure_name(measure)
    base = Path(directory)
    if not base.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {base}")

    try:
        units, trials, spikes, analysis = read_dataset(base)
    except (
        FileNotFoundError,
        ContractViolation,
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeError,
    ):
        raise
    except TypeError as exc:
        raise ValueError(
            f"{base}: trial_index, stim_time_ns, and spike_time_ns must be whole numbers."
        ) from exc

    prep_path, cond_path = base / "preparation.json", base / "conditions.json"
    preparation = load_preparation(prep_path) if prep_path.is_file() else None
    conditions = load_conditions(cond_path) if cond_path.is_file() else None
    eval_inputs = from_spikes(
        units, trials, [measure], spikes, analysis, preparation=preparation, conditions=conditions
    )
    return DayInputs(base, units, trials, spikes, analysis, preparation, conditions, eval_inputs)


@frozen("METHOD across-day comparison")
def _check_days_compatible(first: DayInputs, second: DayInputs) -> list[str]:
    """Verify that two validated days belong to the same preparation and analysis setup."""
    fp_first, fp_second = first.analysis.fingerprint(), second.analysis.fingerprint()
    if fp_first != fp_second:
        raise ValueError(f"analysis.json fingerprints differ between days: {fp_first} != {fp_second}.")

    prep_first = str(first.units["preparation_id"].iloc[0])
    prep_second = str(second.units["preparation_id"].iloc[0])
    if prep_first != prep_second:
        raise ValueError(f"preparation_id differs between days: '{prep_first}' != '{prep_second}'.")

    sess_first = str(first.units["session_id"].iloc[0])
    sess_second = str(second.units["session_id"].iloc[0])
    if sess_first == sess_second:
        raise ValueError(
            f"Both days share session_id '{sess_first}'; across-day comparison requires distinct sessions."
        )

    if first.conditions is not None and second.conditions is not None:
        for label in sorted(set(first.conditions) & set(second.conditions)):
            c_first, c_second = first.conditions[label].fingerprint, second.conditions[label].fingerprint
            if c_first != c_second:
                raise ValueError(
                    f"Condition '{label}' has different protocol fingerprints across days: {c_first} != {c_second}."
                )

    common = sorted(set(first.inputs.evaluated_conditions) & set(second.inputs.evaluated_conditions))
    if not common:
        raise ValueError(
            "No condition is in evaluated_conditions on both days "
            f"(first: {first.inputs.evaluated_conditions}, second: {second.inputs.evaluated_conditions})."
        )
    return common


@frozen("METHOD across-day comparison")
def across_day_frame(
    first_inputs: EvaluationInputs | DayInputs,
    second_inputs: EvaluationInputs | DayInputs,
    measure: str,
) -> pd.DataFrame:
    """Build the sorted ``(unit_id, condition)`` DataFrame of paired per-day unit values.

    Args:
        first_inputs: ``EvaluationInputs`` (or ``DayInputs``) for the first day.
        second_inputs: ``EvaluationInputs`` (or ``DayInputs``) for the second day.
        measure: Spikes-path measure name present in both days' halves and scored sets.

    Returns:
        DataFrame indexed by sorted ``(unit_id, condition)`` with columns
        ``"<measure>_odd"`` (first day) and ``"<measure>_even"`` (second day).

    Raises:
        ValueError: If ``measure`` is unknown or missing from spikes-path ``scored`` sets.
    """
    _validate_measure_name(measure)
    f_eval = first_inputs.inputs if isinstance(first_inputs, DayInputs) else first_inputs
    s_eval = second_inputs.inputs if isinstance(second_inputs, DayInputs) else second_inputs
    if f_eval.scored is None or s_eval.scored is None:
        raise ValueError("across_day_frame requires spikes-path EvaluationInputs with scored unit sets.")
    if measure not in f_eval.scored or measure not in s_eval.scored:
        raise ValueError(f"Measure '{measure}' is missing from scored unit sets.")

    common = sorted(set(f_eval.evaluated_conditions) & set(s_eval.evaluated_conditions))
    pairs = sorted(
        (str(u), str(c)) for c in common for u in (f_eval.scored[measure][c] & s_eval.scored[measure][c])
    )
    col_odd, col_even = f"{measure}_odd", f"{measure}_even"
    if not pairs:
        empty_idx = pd.MultiIndex.from_arrays([[], []], names=["unit_id", "condition"])
        return pd.DataFrame(
            {col_odd: pd.Series(dtype=float), col_even: pd.Series(dtype=float)}, index=empty_idx
        )

    idx = pd.MultiIndex.from_tuples(pairs, names=["unit_id", "condition"])
    f_sub, s_sub = f_eval.halves.loc[idx], s_eval.halves.loc[idx]
    first_day_vals = 0.5 * (f_sub[col_odd].astype(float) + f_sub[col_even].astype(float))
    second_day_vals = 0.5 * (s_sub[col_odd].astype(float) + s_sub[col_even].astype(float))

    # Store the first-day value in "<measure>_odd" and the second-day value in
    # "<measure>_even" so the frozen evaluate.reliability_ceiling and
    # controls.permutation_null functions can read the frame directly.
    return pd.DataFrame({col_odd: first_day_vals, col_even: second_day_vals}, index=idx)


@frozen("METHOD across-day comparison")
def across_day_comparison(
    first: str | Path | DayInputs,
    second: str | Path | DayInputs,
    measure: str = "t_half_excess",
    n_perm: int = controls.DEFAULT_N_PERM,
    seed: int = 42,
) -> dict[str, Any]:
    """Compare two spikes-path sessions of one preparation across matched units.

    Args:
        first: Path to the first-day dataset folder, or a pre-loaded ``DayInputs``.
        second: Path to the second-day dataset folder, or a pre-loaded ``DayInputs``.
        measure: Spikes-path measure name to compare (default ``"t_half_excess"``).
        n_perm: Number of stratified permutations for the null distribution.
        seed: Random seed initializing ``numpy.random.default_rng(seed)`` for the null.

    Returns:
        Dictionary of across-day correlation, interval, per-condition and pooled values,
        null summary, within-session reliabilities, fraction of within-session reliability,
        and dataset/unit counts.

    Raises:
        FileNotFoundError: If either dataset directory or a required file is missing.
        ContractViolation: If either day fails any spikes-path contract check.
        ValueError: If ``n_perm < 1``, ``measure`` is unknown, or the two days do not
            belong together.
    """
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1, got {n_perm}.")
    _validate_measure_name(measure)

    first_day = first if isinstance(first, DayInputs) else load_day(first, measure)
    second_day = second if isinstance(second, DayInputs) else load_day(second, measure)
    common = _check_days_compatible(first_day, second_day)

    frame = across_day_frame(first_day.inputs, second_day.inputs, measure)
    kind = "pooled_centered" if len(common) >= 2 else "per_condition"
    center = kind == "pooled_centered"

    cond_vals = frame.index.get_level_values("condition")
    per_condition: dict[str, dict[str, Any]] = {}
    for cond in common:
        cc = reliability_ceiling(frame.loc[cond_vals == cond], measure, center=False)
        per_condition[cond] = {"r_across_days": cc["r_half"], "n_units": cc["n_units"]}

    uncentered_ceil = reliability_ceiling(frame, measure, center=False)
    centered_ceil = reliability_ceiling(frame, measure, center=True)
    pooled = {"uncentered": uncentered_ceil["r_half"], "centered": centered_ceil["r_half"]}
    main_ceil = centered_ceil if center else uncentered_ceil
    r_across, r_undefined = float(main_ceil["r_half"]), bool(main_ceil["r_undefined"])

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message=r"^All-NaN slice encountered$", category=RuntimeWarning)
        raw_null = controls.permutation_null(
            frame, measure, center, n_perm=int(n_perm), rng=np.random.default_rng(seed)
        )

    p95_r = float(raw_null["p95_r"])
    above_null: bool | None = None if (r_undefined or math.isnan(p95_r)) else bool(r_across > p95_r)

    f_halves = first_day.inputs.halves.loc[frame.index]
    s_halves = second_day.inputs.halves.loc[frame.index]
    rho_first = float(reliability_ceiling(f_halves, measure, center=center)["rho"])
    rho_second = float(reliability_ceiling(s_halves, measure, center=center)["rho"])
    geo_mean = float(np.sqrt(rho_first * rho_second))
    fraction_of_ws = None if (r_undefined or geo_mean == 0.0) else float(r_across / geo_mean)

    first_units = set(first_day.units["unit_id"].astype(str))
    second_units = set(second_day.units["unit_id"].astype(str))
    return {
        "measure": measure,
        "kind": kind,
        "conditions": common,
        "preparation_id": str(first_day.units["preparation_id"].iloc[0]),
        "session_ids": {
            "first": str(first_day.units["session_id"].iloc[0]),
            "second": str(second_day.units["session_id"].iloc[0]),
        },
        "analysis_fingerprint": first_day.analysis.fingerprint(),
        "n_units_first": int(len(first_day.units)),
        "n_units_second": int(len(second_day.units)),
        "n_units_matched": int(len(first_units & second_units)),
        "n_units": int(main_ceil["n_units"]),
        "n_pairs": int(main_ceil["n_pairs"]),
        "r_across_days": r_across,
        "r_ci_low": main_ceil["r_ci_low"],
        "r_ci_high": main_ceil["r_ci_high"],
        "r_undefined": r_undefined,
        "per_condition": per_condition,
        "pooled": pooled,
        "null": {
            "n_perm": int(raw_null["n_perm"]),
            "p95_r": p95_r,
            "median_r": float(raw_null["median_r"]),
        },
        "above_null": above_null,
        "within_session": {"first": rho_first, "second": rho_second, "geometric_mean": geo_mean},
        "fraction_of_within_session": fraction_of_ws,
    }
