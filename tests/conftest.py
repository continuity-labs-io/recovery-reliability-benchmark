"""Shared pytest fixtures and conforming dataset factory for benchmark tests."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd
import pytest


def make_tables(
    n_units: int = 8,
    n_trials: int = 10,
    conditions: Sequence[str] = ("A",),
    isi_s: float = 5.0,
    measures: Sequence[str] = ("tau", "amplitude"),
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create a conforming (units, responses) dataset for contract tests."""
    rng = np.random.default_rng(seed)
    unit_ids = [f"u{i:02d}" for i in range(n_units)]
    units = pd.DataFrame(
        {
            "unit_id": unit_ids,
            "recording_id": "rec0",
            "session_id": "sess0",
            "preparation_id": "prep0",
            "x_um": rng.uniform(0.0, 100.0, size=n_units),
            "y_um": rng.uniform(0.0, 100.0, size=n_units),
        }
    )

    rows = []
    for unit_id in unit_ids:
        for ci, cond in enumerate(conditions):
            for t in range(n_trials):
                trial_index = ci * n_trials + t
                stim_time_ns = int(trial_index * isi_s * 1e9)
                rows.append(
                    {
                        "unit_id": unit_id,
                        "trial_index": trial_index,
                        "stim_time_ns": stim_time_ns,
                        "condition": cond,
                    }
                )
    responses = pd.DataFrame(rows)
    for measure in measures:
        responses[measure] = rng.uniform(0.1, 10.0, size=len(responses))

    return units, responses


@pytest.fixture
def tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a fresh conforming (units, responses) pair."""
    return make_tables()
