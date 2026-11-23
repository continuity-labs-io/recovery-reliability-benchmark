"""Tests for across-day comparison (`across_days.py` and `rrb-across-days`)."""

from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.across_days import (
    across_day_comparison,
    across_day_frame,
    load_day,
)
from recovery_reliability_benchmark.across_days_cli import main as across_days_main
from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.contract import ContractViolation
from recovery_reliability_benchmark.controls import permutation_null
from recovery_reliability_benchmark.evaluate import reliability_ceiling
from recovery_reliability_benchmark.metadata import Condition, write_analysis
from recovery_reliability_benchmark.protocol import Protocol
from recovery_reliability_benchmark.spikes_path_checks import build_population
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
    make_two_condition_spike_trains,
)
from recovery_reliability_benchmark.writer import write_dataset

N_UNITS = 30
N_TRIALS = 40
ISI_S = 5.0
N_PERM = 200
UNIT_IDS = [f"u{i:02d}" for i in range(N_UNITS)]
ANALYSIS = AnalysisParams(post_stim_window_s=2.0)


def _strong_baselines_hz() -> np.ndarray:
    raw = np.geomspace(1.0, 20.0, N_UNITS)
    return np.asarray([float(raw[(7 * i) % N_UNITS]) for i in range(N_UNITS)], dtype=float)


def _write_one_cond_day(
    out_dir: Path,
    rate_fns: list[Any],
    *,
    seed: int,
    session_id: str,
    recording_id: str,
    preparation_id: str = "prep0",
    n_trials: int = N_TRIALS,
    condition: str = "baseline",
    unit_ids_for_trains: list[str] | None = None,
    condition_metadata: dict[str, Condition] | None = None,
) -> Path:
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=n_trials, params=ANALYSIS, isi_s=ISI_S, seed=seed)
    mapped_ids = unit_ids_for_trains if unit_ids_for_trains is not None else UNIT_IDS
    spike_times_s = dict(zip(mapped_ids, trains, strict=True))
    write_dataset(
        out_dir,
        UNIT_IDS,
        spike_times_s,
        onsets_s,
        [condition] * n_trials,
        ANALYSIS,
        recording_id=recording_id,
        session_id=session_id,
        preparation_id=preparation_id,
        condition_metadata=condition_metadata,
    )
    return out_dir


@pytest.fixture(scope="module")
def same_tissue_days(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    base = tmp_path_factory.mktemp("same_tissue")
    pop = build_population("strong")
    first_dir = _write_one_cond_day(
        base / "day_first", pop, seed=0, session_id="sess_first", recording_id="rec_first"
    )
    second_dir = _write_one_cond_day(
        base / "day_second", pop, seed=10_000, session_id="sess_second", recording_id="rec_second"
    )
    return first_dir, second_dir


@pytest.fixture(scope="module")
def known_change_days(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, float]:
    base = tmp_path_factory.mktemp("known_change")
    taus_first = np.geomspace(0.05, 0.5, N_UNITS)
    z = np.random.default_rng(901).normal(size=N_UNITS)
    taus_second = np.clip(taus_first * np.exp(0.6 * z), 0.03, 0.9)
    baselines = _strong_baselines_hz()

    fns_first = [
        exponential_recovery(float(baselines[i]), 100.0, float(taus_first[i])) for i in range(N_UNITS)
    ]
    fns_second = [
        exponential_recovery(float(baselines[i]), 100.0, float(taus_second[i])) for i in range(N_UNITS)
    ]
    first_dir = _write_one_cond_day(
        base / "day_first", fns_first, seed=1, session_id="sess_first", recording_id="rec_first"
    )
    second_dir = _write_one_cond_day(
        base / "day_second", fns_second, seed=10_001, session_id="sess_second", recording_id="rec_second"
    )
    true_r = float(np.corrcoef(taus_first, taus_second)[0, 1])
    return first_dir, second_dir, true_r


@pytest.fixture(scope="module")
def mismatched_second_day(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("mismatched")
    pop = build_population("strong")
    shifted_ids = [UNIT_IDS[(i + 15) % N_UNITS] for i in range(N_UNITS)]
    return _write_one_cond_day(
        base / "day_second_shifted",
        pop,
        seed=10_000,
        session_id="sess_second",
        recording_id="rec_second",
        unit_ids_for_trains=shifted_ids,
    )


@pytest.fixture(scope="module")
def two_load_days(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    base = tmp_path_factory.mktemp("two_loads")
    taus = np.geomspace(0.05, 0.5, N_UNITS)
    baselines = _strong_baselines_hz()
    fns_control = [exponential_recovery(float(baselines[i]), 100.0, float(taus[i])) for i in range(N_UNITS)]
    fns_slowed = [
        exponential_recovery(float(baselines[i]), 100.0, float(taus[i] * 1.5)) for i in range(N_UNITS)
    ]

    dirs: list[Path] = []
    for label, seed in (("first", 3), ("second", 10_003)):
        trains, onsets_s, n_first = make_two_condition_spike_trains(
            fns_control, fns_slowed, n_trials=N_TRIALS, params=ANALYSIS, isi_s=ISI_S, seed=seed
        )
        conds = ["control"] * n_first + ["slowed"] * (len(onsets_s) - n_first)
        spike_times_s = dict(zip(UNIT_IDS, trains, strict=True))
        out = base / f"day_{label}"
        write_dataset(
            out,
            UNIT_IDS,
            spike_times_s,
            onsets_s,
            conds,
            ANALYSIS,
            recording_id=f"rec_{label}",
            session_id=f"sess_{label}",
            preparation_id="prep0",
        )
        dirs.append(out)
    return dirs[0], dirs[1]


def _assert_approx_recursive(actual: Any, expected: Any, tol: float = 1e-9, path: str = "root") -> None:
    if expected is None or isinstance(expected, (str, bool)):
        assert actual == expected and type(actual) is type(expected), f"{path}: {actual!r} != {expected!r}"
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), f"{path}: {actual!r}"
        assert actual == pytest.approx(expected, rel=tol, abs=tol), f"{path}: {actual!r} != {expected!r}"
    elif isinstance(expected, int):
        assert actual == expected and not isinstance(actual, bool), f"{path}: {actual!r} != {expected!r}"
    elif isinstance(expected, dict):
        assert isinstance(actual, dict) and set(actual) == set(expected), f"{path}: keys differ"
        for k in expected:
            _assert_approx_recursive(actual[k], expected[k], tol=tol, path=f"{path}.{k}")
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{path}: len differs"
        for idx, (a_val, e_val) in enumerate(zip(actual, expected, strict=True)):
            _assert_approx_recursive(a_val, e_val, tol=tol, path=f"{path}[{idx}]")
    else:
        assert actual == expected


def test_same_tissue(same_tissue_days: tuple[Path, Path]) -> None:
    first_dir, second_dir = same_tissue_days
    res = across_day_comparison(first_dir, second_dir, n_perm=N_PERM)
    assert res["kind"] == "per_condition"
    assert res["r_across_days"] > 0.9
    assert 0.9 <= res["fraction_of_within_session"] <= 1.1
    assert res["above_null"] is True
    assert res["n_units"] >= 25


def test_known_change(known_change_days: tuple[Path, Path, float]) -> None:
    first_dir, second_dir, true_r = known_change_days
    res = across_day_comparison(first_dir, second_dir, n_perm=N_PERM)
    assert abs(res["fraction_of_within_session"] - true_r) <= 0.1
    assert res["above_null"] is True


def test_wrong_matching(same_tissue_days: tuple[Path, Path], mismatched_second_day: Path) -> None:
    first_dir, _ = same_tissue_days
    res = across_day_comparison(first_dir, mismatched_second_day, n_perm=N_PERM)
    assert res["r_across_days"] < 0.0
    assert res["above_null"] is False


def test_two_loads(two_load_days: tuple[Path, Path]) -> None:
    first_dir, second_dir = two_load_days
    res = across_day_comparison(first_dir, second_dir, n_perm=N_PERM)
    assert res["kind"] == "pooled_centered"
    assert res["conditions"] == ["control", "slowed"]
    assert res["r_across_days"] > 0.9
    assert "control" in res["per_condition"] and "slowed" in res["per_condition"]
    assert res["n_pairs"] >= res["n_units"]


def test_same_code_path(
    same_tissue_days: tuple[Path, Path],
    two_load_days: tuple[Path, Path],
) -> None:
    measure = "t_half_excess"
    seed = 77
    for (first_dir, second_dir), center in ((same_tissue_days, False), (two_load_days, True)):
        d_first = load_day(first_dir, measure)
        d_second = load_day(second_dir, measure)
        frame = across_day_frame(d_first.inputs, d_second.inputs, measure)
        res = across_day_comparison(first_dir, second_dir, measure=measure, n_perm=N_PERM, seed=seed)
        assert res["r_across_days"] == reliability_ceiling(frame, measure, center)["r_half"]
        expected_p95 = permutation_null(frame, measure, center, N_PERM, np.random.default_rng(seed))["p95_r"]
        assert res["null"]["p95_r"] == expected_p95


def test_guards(same_tissue_days: tuple[Path, Path], tmp_path: Path) -> None:
    first_dir, second_dir = same_tissue_days

    diff_analysis = tmp_path / "diff_analysis"
    shutil.copytree(second_dir, diff_analysis)
    write_analysis(AnalysisParams(post_stim_window_s=2.5), diff_analysis / "analysis.json")
    with pytest.raises(ValueError, match="fingerprint"):
        across_day_comparison(first_dir, diff_analysis, n_perm=N_PERM)

    diff_prep = tmp_path / "diff_prep"
    shutil.copytree(second_dir, diff_prep)
    units_df = pd.read_csv(diff_prep / "units.csv")
    units_df["preparation_id"] = "prep_other"
    units_df.to_csv(diff_prep / "units.csv", index=False)
    with pytest.raises(ValueError, match="preparation_id"):
        across_day_comparison(first_dir, diff_prep, n_perm=N_PERM)

    same_sess = tmp_path / "same_sess"
    shutil.copytree(second_dir, same_sess)
    units_df = pd.read_csv(same_sess / "units.csv")
    units_df["session_id"] = "sess_first"
    units_df.to_csv(same_sess / "units.csv", index=False)
    with pytest.raises(ValueError, match="session_id"):
        across_day_comparison(first_dir, same_sess, n_perm=N_PERM)

    cond_first = tmp_path / "cond_first"
    cond_second = tmp_path / "cond_second"
    shutil.copytree(first_dir, cond_first)
    shutil.copytree(second_dir, cond_second)
    c1 = {"baseline": Condition(protocol=Protocol.standard_hfs()).model_dump()}
    c2 = {"baseline": Condition(protocol=Protocol.theta_burst()).model_dump()}
    (cond_first / "conditions.json").write_text(json.dumps(c1), encoding="utf-8")
    (cond_second / "conditions.json").write_text(json.dumps(c2), encoding="utf-8")
    with pytest.raises(ValueError, match="fingerprint"):
        across_day_comparison(cond_first, cond_second, n_perm=N_PERM)

    no_common_cond = tmp_path / "no_common_cond"
    shutil.copytree(second_dir, no_common_cond)
    trials_df = pd.read_csv(no_common_cond / "trials_responses.csv")
    trials_df["condition"] = "other_condition"
    trials_df.to_csv(no_common_cond / "trials_responses.csv", index=False)
    with pytest.raises(ValueError, match="evaluated_conditions"):
        across_day_comparison(first_dir, no_common_cond, n_perm=N_PERM)


def test_day_contract_violation(
    same_tissue_days: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_dir, _ = same_tissue_days
    pop = build_population("strong")
    bad_second = _write_one_cond_day(
        tmp_path / "five_trials",
        pop,
        seed=10_000,
        session_id="sess_second",
        recording_id="rec_second",
        n_trials=5,
    )
    with pytest.raises(ContractViolation):
        load_day(bad_second, "t_half_excess")

    rc = across_days_main([str(first_dir), str(bad_second)])
    captured = capsys.readouterr()
    assert rc == 1
    assert captured.out.splitlines()[0].startswith("second day: ")

    rc_json = across_days_main([str(first_dir), str(bad_second), "--json"])
    doc = json.loads(capsys.readouterr().out)
    assert rc_json == 1
    assert doc["status"] == "violation"
    assert doc["day"] == "second"
    assert "violation" in doc


def test_invariance(two_load_days: tuple[Path, Path], tmp_path: Path) -> None:
    first_dir, second_dir = two_load_days
    baseline = across_day_comparison(first_dir, second_dir, n_perm=50, seed=9)

    rng = np.random.default_rng(321)
    shuf_first = tmp_path / "shuf_first"
    shutil.copytree(first_dir, shuf_first)
    for fname in ("units.csv", "trials_responses.csv", "spikes.csv"):
        df = pd.read_csv(shuf_first / fname)
        df.iloc[rng.permutation(len(df))].to_csv(shuf_first / fname, index=False)
    _assert_approx_recursive(across_day_comparison(shuf_first, second_dir, n_perm=50, seed=9), baseline)

    perm = rng.permutation(N_UNITS)
    unit_map = {UNIT_IDS[i]: f"rand_{perm[i]:02d}_{rng.integers(100, 999)}" for i in range(N_UNITS)}
    relab_first, relab_second = tmp_path / "relab_first", tmp_path / "relab_second"
    for src, dst in ((first_dir, relab_first), (second_dir, relab_second)):
        shutil.copytree(src, dst)
        for fname in ("units.csv", "spikes.csv"):
            df = pd.read_csv(dst / fname, dtype={"unit_id": str})
            df["unit_id"] = df["unit_id"].map(unit_map)
            df.to_csv(dst / fname, index=False)
    res_unit = across_day_comparison(relab_first, relab_second, n_perm=50, seed=9)
    for d in (res_unit_cmp := copy.deepcopy(res_unit), base_cmp := copy.deepcopy(baseline)):
        d.pop("null")
        d.pop("above_null")
    _assert_approx_recursive(res_unit_cmp, base_cmp)

    cond_map = {"control": "z_load", "slowed": "a_load"}
    inv_cond = {v: k for k, v in cond_map.items()}
    crel_first, crel_second = tmp_path / "crel_first", tmp_path / "crel_second"
    for src, dst in ((first_dir, crel_first), (second_dir, crel_second)):
        shutil.copytree(src, dst)
        t_df = pd.read_csv(dst / "trials_responses.csv")
        t_df["condition"] = t_df["condition"].map(cond_map)
        t_df.to_csv(dst / "trials_responses.csv", index=False)
    res_cond = across_day_comparison(crel_first, crel_second, n_perm=50, seed=9)
    res_cond_cmp = copy.deepcopy(res_cond)
    res_cond_cmp["conditions"] = sorted(inv_cond[c] for c in res_cond_cmp["conditions"])
    res_cond_cmp["per_condition"] = {inv_cond[c]: v for c, v in res_cond_cmp["per_condition"].items()}
    res_cond_cmp.pop("null")
    res_cond_cmp.pop("above_null")
    _assert_approx_recursive(res_cond_cmp, base_cmp)

    off_second = tmp_path / "off_second"
    shutil.copytree(second_dir, off_second)
    t_df = pd.read_csv(off_second / "trials_responses.csv")
    t_df["trial_index"] = t_df["trial_index"] + 500
    t_df.to_csv(off_second / "trials_responses.csv", index=False)
    _assert_approx_recursive(across_day_comparison(first_dir, off_second, n_perm=50, seed=9), baseline)

    swapped = across_day_comparison(second_dir, first_dir, n_perm=50, seed=9)
    for key in ("r_across_days", "r_ci_low", "r_ci_high", "fraction_of_within_session"):
        assert swapped[key] == pytest.approx(baseline[key], rel=1e-9, abs=1e-9)
    assert swapped["n_units"] == baseline["n_units"]
    assert swapped["n_pairs"] == baseline["n_pairs"]
    assert swapped["within_session"]["first"] == pytest.approx(baseline["within_session"]["second"])
    assert swapped["within_session"]["second"] == pytest.approx(baseline["within_session"]["first"])


def test_command(
    same_tissue_days: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_dir, second_dir = same_tissue_days
    rc = across_days_main([str(first_dir), str(second_dir), "--n-perm", "50"])
    plain_out = capsys.readouterr().out
    assert rc == 0
    assert "r_across_days" in plain_out

    rc_json = across_days_main([str(first_dir), str(second_dir), "--n-perm", "50", "--json"])
    json_raw = capsys.readouterr().out
    assert rc_json == 0
    assert "NaN" not in json_raw
    doc = json.loads(json_raw)
    assert set(doc) == {"spec_version", "package_version", "status", "inputs", "arguments", "result"}
    assert set(doc["inputs"]) == {"first", "second"}

    assert across_days_main([str(tmp_path / "missing_dir"), str(second_dir)]) == 2
    err_missing_first = capsys.readouterr().err
    assert err_missing_first.startswith("error: ")
    assert "first day" in err_missing_first
    assert "folder not found:" in err_missing_first

    assert across_days_main([str(first_dir), str(second_dir), "--n-perm", "0"]) == 2
    assert capsys.readouterr().err.startswith("error: ")

    assert across_days_main([str(first_dir), str(second_dir), "--measure", "unknown_measure"]) == 2
    assert capsys.readouterr().err.startswith("error: ")

    same_sess = tmp_path / "same_sess_cli"
    shutil.copytree(second_dir, same_sess)
    u_df = pd.read_csv(same_sess / "units.csv")
    u_df["session_id"] = "sess_first"
    u_df.to_csv(same_sess / "units.csv", index=False)
    assert across_days_main([str(first_dir), str(same_sess)]) == 2
    assert capsys.readouterr().err.startswith("error: ")

    disjoint_second = tmp_path / "disjoint_units_second"
    shutil.copytree(second_dir, disjoint_second)
    unit_map = {UNIT_IDS[i]: f"other_{i:02d}" for i in range(N_UNITS)}
    for fname in ("units.csv", "spikes.csv"):
        df = pd.read_csv(disjoint_second / fname, dtype={"unit_id": str})
        df["unit_id"] = df["unit_id"].map(unit_map)
        df.to_csv(disjoint_second / fname, index=False)
    with pytest.raises(
        ValueError,
        match=(
            r"^No unit_id appears on both days \(first: 30 units, second: 30 units\)\. "
            r"Units are matched by unit_id, so both days must come from one sort\.$"
        ),
    ):
        across_day_comparison(first_dir, disjoint_second, n_perm=20)
    assert across_days_main([str(first_dir), str(disjoint_second), "--n-perm", "20"]) == 2
    disjoint_err = capsys.readouterr().err
    assert disjoint_err.startswith("error: ")
    assert "No unit_id appears on both days" in disjoint_err


def test_two_matched_units_undefined_within_session(
    same_tissue_days: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_dir, second_dir = same_tissue_days
    two_matched = tmp_path / "two_matched_second"
    shutil.copytree(second_dir, two_matched)
    unit_map = {UNIT_IDS[i]: (UNIT_IDS[i] if i < 2 else f"other_{i:02d}") for i in range(N_UNITS)}
    for fname in ("units.csv", "spikes.csv"):
        df = pd.read_csv(two_matched / fname, dtype={"unit_id": str})
        df["unit_id"] = df["unit_id"].map(unit_map)
        df.to_csv(two_matched / fname, index=False)

    res = across_day_comparison(first_dir, two_matched, n_perm=20)
    assert res["n_units_matched"] == 2
    assert res["r_undefined"] is True
    assert res["within_session"] == {"first": None, "second": None, "geometric_mean": None}
    assert res["fraction_of_within_session"] is None

    assert across_days_main([str(first_dir), str(two_matched), "--n-perm", "20"]) == 0
    plain_out = capsys.readouterr().out
    assert "undefined" in plain_out
    ws_line = next(line for line in plain_out.splitlines() if line.startswith("within_session:"))
    assert "undefined" in ws_line

    assert across_days_main([str(first_dir), str(two_matched), "--n-perm", "20", "--json"]) == 0
    undef_raw = capsys.readouterr().out
    assert "NaN" not in undef_raw
    undef_doc = json.loads(undef_raw)
    assert undef_doc["result"]["r_undefined"] is True
    assert undef_doc["result"]["r_across_days"] is None
    assert undef_doc["result"]["above_null"] is None
    assert undef_doc["result"]["within_session"] == {
        "first": None,
        "second": None,
        "geometric_mean": None,
    }
    assert undef_doc["result"]["fraction_of_within_session"] is None


def test_command_day_and_file_error_messages(
    same_tissue_days: tuple[Path, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    first_dir, second_dir = same_tissue_days

    assert across_days_main([str(tmp_path / "no_such_first"), str(second_dir)]) == 2
    err_missing_folder = capsys.readouterr().err
    assert "first day" in err_missing_folder
    assert "folder not found:" in err_missing_folder

    no_analysis = tmp_path / "second_no_analysis"
    shutil.copytree(second_dir, no_analysis)
    (no_analysis / "analysis.json").unlink()
    assert across_days_main([str(first_dir), str(no_analysis)]) == 2
    err_no_analysis = capsys.readouterr().err
    assert "second day" in err_no_analysis
    assert "missing file:" in err_no_analysis
    assert "analysis.json" in err_no_analysis

    bad_spikes = tmp_path / "second_bad_spikes"
    shutil.copytree(second_dir, bad_spikes)
    (bad_spikes / "spikes.csv").write_text("unit_id,spike_time_ns\nu00,not_an_int\n", encoding="utf-8")
    assert across_days_main([str(first_dir), str(bad_spikes)]) == 2
    err_bad_spikes = capsys.readouterr().err
    assert "second day" in err_bad_spikes
    assert "spikes.csv" in err_bad_spikes

    bad_trials = tmp_path / "second_bad_trials"
    shutil.copytree(second_dir, bad_trials)
    (bad_trials / "trials_responses.csv").write_text(
        "trial_index,stim_time_ns,condition\n0,1.5,baseline\n", encoding="utf-8"
    )
    assert across_days_main([str(first_dir), str(bad_trials)]) == 2
    err_bad_trials = capsys.readouterr().err
    assert "second day" in err_bad_trials
    assert "trials_responses.csv" in err_bad_trials

    empty_units = tmp_path / "first_empty_units"
    shutil.copytree(first_dir, empty_units)
    (empty_units / "units.csv").write_text("", encoding="utf-8")
    assert across_days_main([str(empty_units), str(second_dir)]) == 2
    err_empty_units = capsys.readouterr().err
    assert "first day" in err_empty_units
    assert "units.csv" in err_empty_units
