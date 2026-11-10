"""Between-condition per-unit sensitivity axis and shuffled null for the benchmark."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from .controls import DEFAULT_N_PERM
from .frozen import freeze_constant, frozen

NOISE_FLOOR = 1e-12
freeze_constant(__name__, "NOISE_FLOOR", "METHOD sensitivity")


@frozen("METHOD sensitivity")
def _shift_and_z(slots: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Compute signed condition shifts and standardized |z| from (..., 4) half-value arrays."""
    shift = 0.5 * (slots[..., 2] + slots[..., 3]) - 0.5 * (slots[..., 0] + slots[..., 1])
    noise = 0.5 * np.sqrt((slots[..., 0] - slots[..., 1]) ** 2 + (slots[..., 2] - slots[..., 3]) ** 2)
    z = np.abs(shift) / np.maximum(noise, NOISE_FLOOR)
    return shift, z


# Two halves per condition give each unit's noise estimate two degrees of freedom,
# so under no condition effect about 18% of units exceed z = 2 by chance and the
# chance median |z| is about 0.8. Dealing each unit's four half values independently
# at random into (first_odd, first_even, second_odd, second_even) destroys condition
# assignment while keeping every unit's own level and spread intact.
@frozen("METHOD sensitivity")
def condition_sensitivity(
    halves: pd.DataFrame,
    measure: str,
    first: str,
    second: str,
    n_perm: int = DEFAULT_N_PERM,
    rng: np.random.Generator | None = None,
) -> dict[str, Any]:
    """Compute per-unit sensitivity and its shuffled null between two conditions.

    Over units whose odd and even halves are non-null in both ``first`` and ``second``:
    ``shift_u = (second_odd + second_even) / 2 - (first_odd + first_even) / 2``,
    ``noise_u = 0.5 * sqrt((first_odd - first_even)**2 + (second_odd - second_even)**2)``,
    and ``z_u = abs(shift_u) / max(noise_u, 1e-12)``.

    Args:
        halves: Split-half DataFrame indexed by ``(unit_id, condition)`` with
            ``{measure}_odd`` and ``{measure}_even`` columns.
        measure: Measure name prefix to evaluate.
        first: Reference (first) condition label; ``shift_u`` is ``second`` minus ``first``.
        second: Comparison (second) condition label.
        n_perm: Number of independent per-unit 4-slot shuffles for the null distribution.
        rng: Optional NumPy random ``Generator`` (defaults to ``np.random.default_rng(0)``).

    Returns:
        Dictionary with keys ``n_units``, ``median_shift``, ``median_abs_z``,
        ``frac_beyond_2``, ``null`` (``n_perm``, ``median_abs_z_p95``, ``frac_beyond_2_p95``,
        ``frac_perm_ge_observed``), and ``above_null``. With zero qualifying units,
        ``n_units`` is ``0`` and all other values are ``None``.

    Raises:
        TypeError: If ``rng`` is provided and is not a ``numpy.random.Generator``.
        ValueError: If ``n_perm < 1``.
    """
    if rng is None:
        rng = np.random.default_rng(0)
    elif not isinstance(rng, np.random.Generator):
        raise TypeError(f"rng must be a numpy.random.Generator, got {type(rng).__name__}.")
    if n_perm < 1:
        raise ValueError(f"n_perm must be >= 1, got {n_perm}.")

    col_odd, col_even = f"{measure}_odd", f"{measure}_even"
    valid = halves.loc[halves[col_odd].notna() & halves[col_even].notna(), [col_odd, col_even]]

    unit_level = "unit_id" if "unit_id" in valid.index.names else 0
    cond_level = "condition" if "condition" in valid.index.names else 1
    u_vals = valid.index.get_level_values(unit_level).astype(str)
    c_vals = valid.index.get_level_values(cond_level).astype(str)

    mask_first = c_vals == str(first)
    mask_second = c_vals == str(second)
    first_df = valid.loc[mask_first].set_axis(u_vals[mask_first], axis=0)
    second_df = valid.loc[mask_second].set_axis(u_vals[mask_second], axis=0)

    common_units = sorted(set(first_df.index) & set(second_df.index))
    n_units = len(common_units)
    if n_units == 0:
        return {
            "n_units": 0,
            "median_shift": None,
            "median_abs_z": None,
            "frac_beyond_2": None,
            "null": None,
            "above_null": None,
        }

    f_aligned = first_df.loc[common_units]
    s_aligned = second_df.loc[common_units]
    slots = np.column_stack(
        [
            f_aligned[col_odd].to_numpy(dtype=float),
            f_aligned[col_even].to_numpy(dtype=float),
            s_aligned[col_odd].to_numpy(dtype=float),
            s_aligned[col_even].to_numpy(dtype=float),
        ]
    )

    shift_u, z_u = _shift_and_z(slots)
    median_shift = float(np.median(shift_u))
    median_abs_z = float(np.median(z_u))
    frac_beyond_2 = float(np.mean(z_u > 2.0))

    shuffled = rng.permuted(np.broadcast_to(slots, (int(n_perm), n_units, 4)), axis=2)
    _, perm_z = _shift_and_z(shuffled)
    perm_median_abs_z = np.median(perm_z, axis=1)
    perm_frac_beyond_2 = np.mean(perm_z > 2.0, axis=1)

    median_abs_z_p95 = float(np.percentile(perm_median_abs_z, 95))
    frac_beyond_2_p95 = float(np.percentile(perm_frac_beyond_2, 95))
    frac_perm_ge_observed = float(np.mean(perm_median_abs_z >= median_abs_z))

    return {
        "n_units": int(n_units),
        "median_shift": median_shift,
        "median_abs_z": median_abs_z,
        "frac_beyond_2": frac_beyond_2,
        "null": {
            "n_perm": int(n_perm),
            "median_abs_z_p95": median_abs_z_p95,
            "frac_beyond_2_p95": frac_beyond_2_p95,
            "frac_perm_ge_observed": frac_perm_ge_observed,
        },
        "above_null": bool(median_abs_z > median_abs_z_p95),
    }


@frozen("METHOD sensitivity")
def measure_sensitivity(
    halves: pd.DataFrame,
    measure: str,
    evaluated_conditions: Sequence[str],
    n_perm: int = DEFAULT_N_PERM,
    seed: int = 42,
) -> dict[str, dict[str, Any]] | None:
    """Compute pairwise condition sensitivity across all sorted pairs of evaluated conditions.

    Args:
        halves: Split-half DataFrame indexed by ``(unit_id, condition)``.
        measure: Measure name prefix to evaluate.
        evaluated_conditions: Sequence of evaluated condition labels.
        n_perm: Number of shuffles per condition pair for the null distribution.
        seed: Random seed initializing a fresh ``np.random.default_rng(seed)`` per pair.

    Returns:
        ``None`` when fewer than two conditions are evaluated; otherwise a dictionary
        mapping ``"<first>|<second>"`` (labels in sorted order, shift = second minus first)
        to ``condition_sensitivity`` dicts.
    """
    conds = sorted({str(c) for c in evaluated_conditions})
    if len(conds) < 2:
        return None
    out: dict[str, dict[str, Any]] = {}
    for idx, first in enumerate(conds):
        for second in conds[idx + 1 :]:
            out[f"{first}|{second}"] = condition_sensitivity(
                halves,
                measure,
                first,
                second,
                n_perm=n_perm,
                rng=np.random.default_rng(seed),
            )
    return out
