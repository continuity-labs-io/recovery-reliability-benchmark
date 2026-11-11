"""Tests for writer.py, make_examples two_conditions byte-identity, and adapter_template.py."""

from __future__ import annotations

import shlex
from pathlib import Path

import numpy as np
import pytest

from adapters import adapter_template
from recovery_reliability_benchmark.cli import check_main
from recovery_reliability_benchmark.measures import AnalysisParams
from recovery_reliability_benchmark.metadata import Condition, Preparation, load_conditions, load_preparation
from recovery_reliability_benchmark.protocol import Protocol
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_two_condition_spike_trains
from recovery_reliability_benchmark.writer import read_dataset, write_dataset

ROOT = Path(__file__).resolve().parent.parent
TWO_COND_DIR = ROOT / "examples" / "two_conditions"
ADAPTER_TEMPLATE_PATH = ROOT / "adapters" / "adapter_template.py"


def _make_d_1_5_0() -> tuple[
    list[str],
    dict[str, np.ndarray],
    np.ndarray,
    list[str],
    AnalysisParams,
    Preparation,
    dict[str, Condition],
]:
    n_units = 30
    n_trials = 20
    slowing_factor = 1.5
    analysis = AnalysisParams(post_stim_window_s=2.0)
    taus_s = np.geomspace(0.05, 0.5, n_units)
    baselines_hz = np.geomspace(1.0, 20.0, n_units)
    rate_fns_control = [
        exponential_recovery(float(baselines_hz[(7 * i) % n_units]), 100.0, float(tau_s))
        for i, tau_s in enumerate(taus_s)
    ]
    rate_fns_slowed = [
        exponential_recovery(float(baselines_hz[(7 * i) % n_units]), 100.0, float(tau_s * slowing_factor))
        for i, tau_s in enumerate(taus_s)
    ]
    trains, onsets_s, n_first = make_two_condition_spike_trains(
        rate_fns_control,
        rate_fns_slowed,
        n_trials=n_trials,
        params=analysis,
        isi_s=5.0,
        seed=0,
    )
    unit_ids = [f"u{i:02d}" for i in range(n_units)]
    spike_times_s = dict(zip(unit_ids, trains, strict=True))
    conditions = ["control"] * n_first + ["slowed"] * (len(onsets_s) - n_first)
    preparation = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
    )
    condition_metadata = {
        "control": Condition(
            protocol=Protocol.standard_hfs(),
            compound=None,
            dose=None,
            dose_unit=None,
            vehicle=None,
        ),
        "slowed": Condition(
            protocol=Protocol.standard_hfs(),
            compound="synthetic slowing",
            dose=slowing_factor,
            dose_unit="x tau",
            vehicle=None,
        ),
    }
    return unit_ids, spike_times_s, onsets_s, conditions, analysis, preparation, condition_metadata


def _minimal_valid_inputs() -> tuple[
    list[str], dict[str, list[float]], list[float], list[str], AnalysisParams
]:
    return (
        ["u00", "u01"],
        {"u00": [0.5, 5.2], "u01": [1.1, 6.4]},
        [5.0, 10.0],
        ["control", "slowed"],
        AnalysisParams(post_stim_window_s=2.0),
    )


def test_round_trip_d_1_5_0(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis, preparation, condition_metadata = _make_d_1_5_0()
    ds_dir = tmp_path / "dataset"
    paths = write_dataset(
        ds_dir,
        unit_ids,
        spike_times_s,
        onsets_s,
        conditions,
        analysis,
        preparation=preparation,
        condition_metadata=condition_metadata,
    )
    assert set(paths) == {"units", "trials", "spikes", "analysis", "preparation", "conditions"}
    assert all(p.is_file() for p in paths.values())

    common_cli = [
        str(paths["units"]),
        str(paths["trials"]),
        "--spikes",
        str(paths["spikes"]),
        "--analysis",
        str(paths["analysis"]),
        "--preparation",
        str(paths["preparation"]),
        "--conditions",
        str(paths["conditions"]),
    ]
    assert check_main(common_cli) == 0

    report_dir = tmp_path / "report"
    rc = report_main(
        [
            *common_cli,
            "--measures",
            "t_half_excess,excess_per_trial",
            "--n-perm",
            "10",
            "--out",
            str(report_dir),
        ]
    )
    assert rc == 0
    assert (report_dir / "evaluate.json").is_file()
    assert (report_dir / "summary.md").is_file()

    units, trials, spikes, loaded_analysis = read_dataset(ds_dir)
    assert list(units["unit_id"]) == unit_ids
    assert (units["recording_id"] == "rec0").all()
    assert (units["session_id"] == "sess0").all()
    assert (units["preparation_id"] == "prep0").all()
    assert list(trials["trial_index"]) == list(range(len(onsets_s)))
    assert list(trials["stim_time_ns"]) == [int(round(float(t) * 1e9)) for t in onsets_s]
    assert list(trials["condition"]) == conditions
    assert loaded_analysis == analysis

    expected_unit_col = [uid for uid in unit_ids for _ in spike_times_s[uid]]
    expected_time_col = [int(round(float(t) * 1e9)) for uid in unit_ids for t in spike_times_s[uid]]
    assert list(spikes["unit_id"]) == expected_unit_col
    assert list(spikes["spike_time_ns"]) == expected_time_col

    assert load_preparation(paths["preparation"]) == preparation
    assert load_conditions(paths["conditions"]) == condition_metadata


def test_spikes_ordered_by_unit_ids_and_sorted_ascending(tmp_path: Path) -> None:
    _, _, onsets_s, conditions, analysis = _minimal_valid_inputs()
    unit_ids = ["u_second", "u_silent", "u_first"]
    spike_times_s = {
        "u_first": [0.9, 0.2],
        "u_second": [0.5, 0.1, 0.3],
    }
    write_dataset(tmp_path / "ordered", unit_ids, spike_times_s, onsets_s, conditions, analysis)
    _, _, spikes, _ = read_dataset(tmp_path / "ordered")
    assert list(spikes["unit_id"]) == ["u_second", "u_second", "u_second", "u_first", "u_first"]
    assert list(spikes["spike_time_ns"]) == [100_000_000, 300_000_000, 500_000_000, 200_000_000, 900_000_000]


def test_refuses_non_increasing_onsets(tmp_path: Path) -> None:
    unit_ids, spike_times_s, _, conditions, analysis = _minimal_valid_inputs()
    for bad_onsets in ([5.0, 5.0], [10.0, 5.0]):
        out = tmp_path / "bad_onsets"
        with pytest.raises(ValueError, match="onsets_s must be strictly increasing"):
            write_dataset(out, unit_ids, spike_times_s, bad_onsets, conditions, analysis)
        assert not out.exists()


def test_refuses_mismatched_conditions_length(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, _, analysis = _minimal_valid_inputs()
    out = tmp_path / "bad_conds"
    with pytest.raises(ValueError, match=r"len\(conditions\).*len\(onsets_s\)"):
        write_dataset(out, unit_ids, spike_times_s, onsets_s, ["control"], analysis)
    assert not out.exists()


def test_refuses_spike_key_missing_from_unit_ids(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis = _minimal_valid_inputs()
    out = tmp_path / "bad_spike_key"
    with pytest.raises(ValueError, match="missing from unit_ids"):
        write_dataset(out, unit_ids, {**spike_times_s, "u99": [1.0]}, onsets_s, conditions, analysis)
    assert not out.exists()


def test_refuses_duplicate_unit_ids(tmp_path: Path) -> None:
    _, spike_times_s, onsets_s, conditions, analysis = _minimal_valid_inputs()
    out = tmp_path / "dup_units"
    with pytest.raises(ValueError, match="duplicate unit_ids"):
        write_dataset(out, ["u00", "u00"], {"u00": spike_times_s["u00"]}, onsets_s, conditions, analysis)
    assert not out.exists()


def test_refuses_negative_times(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis = _minimal_valid_inputs()
    with pytest.raises(ValueError, match="negative times"):
        write_dataset(tmp_path / "neg_onset", unit_ids, spike_times_s, [-0.1, 5.0], conditions, analysis)
    with pytest.raises(ValueError, match="negative times"):
        write_dataset(
            tmp_path / "neg_spike", unit_ids, {"u00": [-0.01], "u01": [1.0]}, onsets_s, conditions, analysis
        )


def test_refuses_non_finite_times(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis = _minimal_valid_inputs()
    for bad_val in (float("nan"), float("inf")):
        with pytest.raises(ValueError, match="non-finite times"):
            write_dataset(
                tmp_path / "nonfinite_onset", unit_ids, spike_times_s, [5.0, bad_val], conditions, analysis
            )
        with pytest.raises(ValueError, match="non-finite times"):
            write_dataset(
                tmp_path / "nonfinite_spike",
                unit_ids,
                {"u00": [bad_val], "u01": [1.0]},
                onsets_s,
                conditions,
                analysis,
            )


def test_refuses_mismatched_condition_metadata_keys(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis = _minimal_valid_inputs()
    cond = Condition(protocol=Protocol.standard_hfs())
    with pytest.raises(ValueError, match="condition_metadata keys"):
        write_dataset(
            tmp_path / "missing_meta",
            unit_ids,
            spike_times_s,
            onsets_s,
            conditions,
            analysis,
            condition_metadata={"control": cond},
        )
    with pytest.raises(ValueError, match="condition_metadata keys"):
        write_dataset(
            tmp_path / "extra_meta",
            unit_ids,
            spike_times_s,
            onsets_s,
            conditions,
            analysis,
            condition_metadata={"control": cond, "slowed": cond, "extra": cond},
        )


def test_make_examples_two_conditions_byte_identical(tmp_path: Path) -> None:
    unit_ids, spike_times_s, onsets_s, conditions, analysis, _, condition_metadata = _make_d_1_5_0()
    gen_dir = tmp_path / "two_conditions"
    write_dataset(
        gen_dir,
        unit_ids=unit_ids,
        spike_times_s=spike_times_s,
        onsets_s=onsets_s,
        conditions=conditions,
        analysis=analysis,
        condition_metadata=condition_metadata,
    )
    committed_files = sorted(p.name for p in TWO_COND_DIR.iterdir() if p.is_file())
    generated_files = sorted(p.name for p in gen_dir.iterdir() if p.is_file())
    assert generated_files == committed_files

    for name in committed_files:
        committed_bytes = (TWO_COND_DIR / name).read_bytes()
        generated_bytes = (gen_dir / name).read_bytes()
        assert generated_bytes == committed_bytes, f"Byte mismatch in {name}"


def test_adapter_template(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    text = ADAPTER_TEMPLATE_PATH.read_text(encoding="utf-8")
    assert len(text.splitlines()) < 60
    assert adapter_template.__doc__ is not None
    assert "2 s" in adapter_template.__doc__
    assert "8 units" in adapter_template.__doc__
    assert "an adapter contains no analysis" in adapter_template.__doc__

    with pytest.raises(NotImplementedError):
        adapter_template.load_recording(tmp_path / "dummy.raw")

    unit_ids, spike_times_s, onsets_s, conditions, *_ = _make_d_1_5_0()
    monkeypatch.setattr(
        adapter_template, "load_recording", lambda _path: (unit_ids, spike_times_s, onsets_s, conditions)
    )
    out_dir = tmp_path / "adapted"
    rc = adapter_template.main([str(tmp_path / "session.raw"), "--out", str(out_dir)])
    assert rc == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("rrb-check ")
    assert lines[1].startswith("rrb-report ")
    assert check_main(shlex.split(lines[0])[1:]) == 0
