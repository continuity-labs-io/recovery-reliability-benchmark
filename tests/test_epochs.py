"""Unit tests for epochs.py and adapters/sharf2022.py."""

from __future__ import annotations

import shlex
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import scipy.io as sio

from adapters import sharf2022
from recovery_reliability_benchmark.cli import check_main
from recovery_reliability_benchmark.epochs import TRANSFORM_MEASURES, build_epoch_tables
from recovery_reliability_benchmark.report import main as report_main


def _hand_built_units() -> list[SimpleNamespace]:
    # 3 units spanning 17.0 s (max sample = 340000 at fs=20000):
    # - u10: 2 spikes in epoch 0, 0 in epoch 1, 3 in epoch 2, plus 1 spike at 17 s (dropped)
    # - u20: single spike stored as a 0-D scalar (as squeeze_me=True produces) in epoch 1 (6 s)
    # - u30: empty spike train (shape (0,)) across all epochs
    return [
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


def test_build_recording_tables_hand_built_units() -> None:
    fs = 20000.0
    epoch_s = 5.0

    built = sharf2022.build_recording_tables(
        raw_units=_hand_built_units(),
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
    assert list(responses.columns) == [
        "unit_id",
        "trial_index",
        "stim_time_ns",
        "condition",
        "firing_rate_hz",
    ]


def test_build_recording_tables_transforms() -> None:
    fs = 20000.0
    raw_units = _hand_built_units()

    for epoch_s in (5.0, 2.5):
        built = sharf2022.build_recording_tables(
            raw_units=raw_units,
            fs=fs,
            epoch_s=epoch_s,
            stem="2950",
            preparation_id="L2",
            transforms=True,
        )
        responses = built["responses"]
        assert list(responses.columns) == [
            "unit_id",
            "trial_index",
            "stim_time_ns",
            "condition",
            *TRANSFORM_MEASURES,
        ]
        rate = responses["firing_rate_hz"].to_numpy(dtype=float)
        np.testing.assert_allclose(responses["log_firing_rate_hz"], np.log10(rate + 1.0 / epoch_s))
        np.testing.assert_allclose(responses["sqrt_firing_rate_hz"], np.sqrt(rate))

    built_5s = sharf2022.build_recording_tables(
        raw_units=raw_units, fs=fs, epoch_s=5.0, stem="2950", preparation_id="L2", transforms=True
    )
    resp_5s = built_5s["responses"]
    ranks_by_epoch = {
        int(k): grp.sort_values("unit_id")["rank_firing_rate_hz"].to_list()
        for k, grp in resp_5s.groupby("trial_index")
    }
    assert ranks_by_epoch == {
        0: [3.0, 1.5, 1.5],
        1: [1.5, 3.0, 1.5],
        2: [3.0, 1.5, 1.5],
    }


def test_build_epoch_tables_validation() -> None:
    with pytest.raises(ValueError, match="epoch_s"):
        build_epoch_tables(["u0"], {"u0": [1.0]}, epoch_s=0.0)
    with pytest.raises(ValueError, match="duplicates"):
        build_epoch_tables(["u0", "u0"], {"u0": [1.0]}, epoch_s=2.0)


def test_sharf2022_adapter_end_to_end_with_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    rng = np.random.default_rng(0)
    fs = 1000.0
    unit_dtype = [("unit_id", "O"), ("spike_train", "O"), ("x_max", "O"), ("y_max", "O")]
    units_arr = np.empty(10, dtype=unit_dtype)
    for idx in range(10):
        rate_hz = 1.0 + idx * 2.0
        isis = rng.exponential(1.0 / rate_hz, size=int(rate_hz * 60))
        times_s = np.cumsum(isis)
        times_s = times_s[times_s <= 55.0]
        if idx == 9:
            times_s = np.append(times_s, 52.0)
        units_arr[idx] = (idx, (times_s * fs).astype(np.int64), float(idx * 10), float(idx * 20))

    mat_path = tmp_path / "2950.mat"
    sio.savemat(mat_path, {"units": units_arr, "fs": fs})

    out_dir = tmp_path / "adapted"
    rc = sharf2022.main(
        [
            "--recording",
            str(mat_path),
            "--out",
            str(out_dir),
            "--epoch-s",
            "5.0",
            "--min-epochs",
            "10",
            "--transforms",
        ]
    )
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("rrb-check ")
    assert lines[1].startswith("rrb-report ")
    assert check_main(shlex.split(lines[0])[1:]) == 0
    assert report_main([*shlex.split(lines[1])[1:], "--n-perm", "10"]) == 0
    assert (out_dir / "2950" / "report" / "evaluate.json").is_file()
    assert (out_dir / "2950" / "report" / "summary.md").is_file()
