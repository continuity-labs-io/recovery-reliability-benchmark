"""Fixed-duration epoch table construction and monotone rate transforms."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pandas as pd

FloatArray = Sequence[float] | np.ndarray

TRANSFORM_MEASURES: tuple[str, ...] = (
    "firing_rate_hz",
    "log_firing_rate_hz",
    "sqrt_firing_rate_hz",
    "rank_firing_rate_hz",
)


def add_rate_transforms(responses: pd.DataFrame, epoch_s: float) -> pd.DataFrame:
    """Return a copy of ``responses`` with log, sqrt, and within-epoch rank firing-rate columns.

    Args:
        responses: Responses DataFrame containing ``trial_index`` and ``firing_rate_hz``.
        epoch_s: Positive fixed epoch duration in seconds.

    Returns:
        Copy of ``responses`` with ``log_firing_rate_hz``, ``sqrt_firing_rate_hz``, and
        ``rank_firing_rate_hz`` appended.

    Raises:
        ValueError: If ``epoch_s`` is not positive and finite.
    """
    epoch_f = float(epoch_s)
    if not math.isfinite(epoch_f) or epoch_f <= 0.0:
        raise ValueError(f"epoch_s must be positive and finite, got {epoch_s}.")
    # Intent: 1.0 / epoch_f (0.2 Hz for a 5.0 s epoch) is one spike in an epoch —
    # the smallest nonzero rate the recording can express, so it serves as the natural
    # floor for log10 rather than an arbitrary epsilon. Within-epoch rank (average ties)
    # discards magnitude and keeps only unit ordering, bounding how far any monotone
    # transform can move Pearson r.
    out = responses.copy()
    rate = out["firing_rate_hz"].astype(np.float64)
    out["log_firing_rate_hz"] = np.log10(rate + 1.0 / epoch_f)
    out["sqrt_firing_rate_hz"] = np.sqrt(rate)
    out["rank_firing_rate_hz"] = out.groupby("trial_index")["firing_rate_hz"].rank(method="average")
    return out


# Intent: An epoch with zero spikes records firing_rate_hz = 0.0 (never NaN) because zero
# spikes is a measurement, not a missing value (SPEC §15); every unit therefore has a
# complete epoch grid and none are filtered on activity.
def build_epoch_tables(
    unit_ids: Sequence[str],
    spike_times_s: Mapping[str, FloatArray],
    epoch_s: float,
    *,
    recording_id: str = "rec0",
    session_id: str = "sess0",
    preparation_id: str = "prep0",
    condition: str = "spontaneous",
    coords_um: Mapping[str, tuple[float, float]] | None = None,
    transforms: bool = False,
) -> dict[str, Any]:
    """Slice continuous spike timestamps into fixed-duration benchmark tables.

    Args:
        unit_ids: Ordered sequence of unique unit identifier strings.
        spike_times_s: Mapping from ``unit_id`` to a 1D array of spike timestamps in seconds.
        epoch_s: Positive fixed epoch duration in seconds standing in for trials.
        recording_id: Recording identifier written to ``units.csv``.
        session_id: Session identifier written to ``units.csv``.
        preparation_id: Preparation identifier written to ``units.csv``.
        condition: Condition label written to every row of ``responses.csv``.
        coords_um: Optional mapping from ``unit_id`` to ``(x_um, y_um)`` coordinates.
        transforms: When True, append log, sqrt, and within-epoch rank firing-rate columns.

    Returns:
        Dictionary with keys ``units``, ``responses``, ``spikes``, ``duration_s``, and ``n_epochs``.

    Raises:
        ValueError: If ``epoch_s`` is not positive and finite, or ``unit_ids`` has duplicates.
    """
    epoch_f = float(epoch_s)
    if not math.isfinite(epoch_f) or epoch_f <= 0.0:
        raise ValueError(f"epoch_s must be positive and finite, got {epoch_s}.")
    ids = [str(uid) for uid in unit_ids]
    if len(set(ids)) != len(ids):
        raise ValueError("unit_ids must not contain duplicates.")

    trains = [np.atleast_1d(np.asarray(spike_times_s.get(uid, ()), dtype=np.float64)) for uid in ids]
    duration_s = float(max((float(np.max(t)) for t in trains if t.size > 0), default=0.0))
    n_epochs = int(math.floor(duration_s / epoch_f))
    cutoff_s = n_epochs * epoch_f

    unit_rows: list[tuple[Any, ...]] = []
    response_rows: list[tuple[str, int, int, str, float]] = []
    spike_rows: list[tuple[str, int]] = []
    for uid, times_s in zip(ids, trains, strict=True):
        if coords_um is not None:
            x_um, y_um = coords_um[uid]
            unit_rows.append((uid, recording_id, session_id, preparation_id, float(x_um), float(y_um)))
        else:
            unit_rows.append((uid, recording_id, session_id, preparation_id))
        spike_rows.extend((uid, int(round(float(t) * 1e9))) for t in times_s)
        if n_epochs > 0:
            valid = times_s[(times_s >= 0.0) & (times_s < cutoff_s)]
            idx = np.floor(valid / epoch_f).astype(np.int64)
            counts = np.bincount(idx[(idx >= 0) & (idx < n_epochs)], minlength=n_epochs)[:n_epochs]
            for k in range(n_epochs):
                stim_ns = int(round(k * epoch_f * 1e9))
                response_rows.append((uid, k, stim_ns, condition, float(counts[k]) / epoch_f))

    u_cols = ["unit_id", "recording_id", "session_id", "preparation_id"]
    if coords_um is not None:
        u_cols.extend(["x_um", "y_um"])
    r_cols = ["unit_id", "trial_index", "stim_time_ns", "condition", "firing_rate_hz"]
    responses = pd.DataFrame(response_rows, columns=r_cols)
    if transforms:
        responses = add_rate_transforms(responses, epoch_f)
    return {
        "units": pd.DataFrame(unit_rows, columns=u_cols),
        "responses": responses,
        "spikes": pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"]),
        "duration_s": duration_s,
        "n_epochs": n_epochs,
    }
