"""Tests for the spikes-path simulation script and pinned numbers in docs/spikes_path_checks.json."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SIX_CASE_KEYS = (
    "strong_20",
    "strong_40",
    "weak_20",
    "weak_40",
    "sparse_20",
    "sparse_40",
)

FOUR_MEASURES = (
    "t_half_excess",
    "excess_per_trial",
    "baseline_hz",
    "t_return",
)

TOLERANCE = 0.005

EXPECTED_T_HALF_EXCESS: dict[str, tuple[float, float, float]] = {
    "strong_20": (0.968, 0.966, 28.1),
    "strong_40": (0.985, 0.985, 29.5),
    "weak_20": (0.696, 0.788, 16.1),
    "weak_40": (0.878, 0.880, 20.1),
    "sparse_20": (0.807, 0.824, 16.3),
    "sparse_40": (0.859, 0.854, 19.4),
}

EXPECTED_OTHER_MEASURES: dict[str, dict[str, tuple[float, float]]] = {
    "excess_per_trial": {
        "strong_20": (0.984, 0.984),
        "weak_20": (0.888, 0.867),
        "sparse_20": (0.964, 0.968),
    },
    "baseline_hz": {
        "strong_20": (0.990, 0.990),
        "sparse_20": (0.962, 0.966),
    },
    "t_return": {
        "strong_20": (0.687, 0.681),
        "weak_20": (0.528, 0.510),
        "sparse_20": (0.336, 0.341),
    },
}


def _load_spikes_path_checks():
    script_path = ROOT / "scripts" / "spikes_path_checks.py"
    spec = importlib.util.spec_from_file_location("spikes_path_checks", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_json_has_six_keys_and_matches_expected_values() -> None:
    json_path = ROOT / "docs" / "spikes_path_checks.json"
    md_path = ROOT / "docs" / "spikes_path_checks.md"
    assert json_path.is_file()
    assert md_path.is_file()

    doc = json.loads(json_path.read_text(encoding="utf-8"))
    assert set(doc.keys()) == set(SIX_CASE_KEYS)

    for case_key in SIX_CASE_KEYS:
        assert set(doc[case_key].keys()) == set(FOUR_MEASURES)
        for measure in FOUR_MEASURES:
            entry = doc[case_key][measure]
            assert set(entry.keys()) == {"split_half_corrected", "test_retest", "units_scored"}

    for case_key, (exp_sh, exp_tr, exp_us) in EXPECTED_T_HALF_EXCESS.items():
        actual = doc[case_key]["t_half_excess"]
        assert abs(actual["split_half_corrected"] - exp_sh) <= TOLERANCE, (
            f"t_half_excess {case_key} split_half_corrected: {actual['split_half_corrected']} vs {exp_sh}"
        )
        assert abs(actual["test_retest"] - exp_tr) <= TOLERANCE, (
            f"t_half_excess {case_key} test_retest: {actual['test_retest']} vs {exp_tr}"
        )
        assert abs(actual["units_scored"] - exp_us) <= TOLERANCE, (
            f"t_half_excess {case_key} units_scored: {actual['units_scored']} vs {exp_us}"
        )

    for measure, by_case in EXPECTED_OTHER_MEASURES.items():
        for case_key, (exp_sh, exp_tr) in by_case.items():
            actual = doc[case_key][measure]
            assert abs(actual["split_half_corrected"] - exp_sh) <= TOLERANCE, (
                f"{measure} {case_key} split_half_corrected: {actual['split_half_corrected']} vs {exp_sh}"
            )
            assert abs(actual["test_retest"] - exp_tr) <= TOLERANCE, (
                f"{measure} {case_key} test_retest: {actual['test_retest']} vs {exp_tr}"
            )


def test_smoke_single_session_strong_20_seed_0() -> None:
    mod = _load_spikes_path_checks()
    result = mod.simulate_seed("strong", n_trials=20, seed=0)
    assert set(result.keys()) == set(FOUR_MEASURES)
    for measure in FOUR_MEASURES:
        stats = result[measure]
        assert 0.0 <= stats["split_half_corrected"] <= 1.0
        assert not math.isnan(stats["test_retest"])
        assert -1.0 <= stats["test_retest"] <= 1.0
        assert 0.0 < stats["units_scored"] <= 30.0
