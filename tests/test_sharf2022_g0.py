"""Unit tests for the Sharf 2022 G0 epoching and table conversion script."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parent.parent


def _load_sharf2022_g0():
    script_path = ROOT / "scripts" / "sharf2022_g0.py"
    spec = importlib.util.spec_from_file_location("sharf2022_g0", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_recording_tables_hand_built_units() -> None:
    sharf = _load_sharf2022_g0()
    fs = 20000.0
    epoch_s = 5.0

    # 3 units spanning 17.0 s (max sample = 340000 at fs=20000):
    # - u10: 2 spikes in epoch 0, 0 in epoch 1, 3 in epoch 2, plus 1 spike at 17 s (dropped)
    # - u20: single spike stored as a 0-D scalar (as squeeze_me=True produces) in epoch 1 (6 s)
    # - u30: empty spike train (shape (0,)) across all epochs
    raw_units = [
        SimpleNamespace(
            unit_id=10,
            spike_train=np.array([10000, 50000, 200000, 240000, 299999, 340000], dtype=np.int64),
            x_max=100.0,
            y_max=200.0,
        ),
        SimpleNamespace(
            unit_id=20,
            spike_train=np.array(120000, dtype=np.int64),
            x_max=110.0,
            y_max=210.0,
        ),
        SimpleNamespace(
            unit_id=30,
            spike_train=np.array([], dtype=np.int64),
            x_max=120.0,
            y_max=220.0,
        ),
    ]

    built = sharf.build_recording_tables(
        raw_units=raw_units,
        fs=fs,
        epoch_s=epoch_s,
        stem="2950",
        preparation_id="L2",
    )

    assert built["duration_s"] == 17.0
    assert built["n_epochs"] == 3
    assert built["unit_id_fallback"] is False

    responses = built["responses"]
    assert len(responses) == 9
    assert not responses["firing_rate_hz"].isna().any()

    counts_by_unit = {
        uid: [int(round(r * epoch_s)) for r in grp.sort_values("trial_index")["firing_rate_hz"]]
        for uid, grp in responses.groupby("unit_id", sort=False)
    }
    assert counts_by_unit == {
        "u10": [2, 0, 3],
        "u20": [0, 1, 0],
        "u30": [0, 0, 0],
    }

    rates_by_unit = {
        uid: grp.sort_values("trial_index")["firing_rate_hz"].to_list()
        for uid, grp in responses.groupby("unit_id", sort=False)
    }
    assert rates_by_unit["u10"] == [0.4, 0.0, 0.6]
    assert rates_by_unit["u20"] == [0.0, 0.2, 0.0]
    assert rates_by_unit["u30"] == [0.0, 0.0, 0.0]

    stim_times = responses.sort_values("trial_index")["stim_time_ns"].unique().tolist()
    assert stim_times == [0, 5_000_000_000, 10_000_000_000]
    assert all(t % 5_000_000_000 == 0 for t in responses["stim_time_ns"])
