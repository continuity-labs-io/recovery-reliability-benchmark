"""Invariance tests for every reported number in the Recovery Reliability Benchmark."""

from __future__ import annotations

import copy
from typing import Any

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.synthetic import make_tables


def strip(result: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of ``result`` without ``package_version``."""
    out = copy.deepcopy(result)
    out.pop("package_version", None)
    return out


def _assert_approx_recursive(actual: Any, expected: Any, tol: float = 1e-9, path: str = "root") -> None:
    if expected is None or isinstance(expected, (str, bool)):
        assert actual == expected and type(actual) is type(expected), (
            f"Mismatch at {path}: {actual!r} != {expected!r}"
        )
    elif isinstance(expected, float):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), (
            f"Type mismatch at {path}: {actual!r} vs {expected!r}"
        )
        assert actual == pytest.approx(expected, rel=tol, abs=tol), (
            f"Float mismatch at {path}: {actual!r} != {expected!r}"
        )
    elif isinstance(expected, int):
        assert actual == expected and not isinstance(actual, bool), (
            f"Int mismatch at {path}: {actual!r} != {expected!r}"
        )
    elif isinstance(expected, dict):
        assert isinstance(actual, dict), f"Expected dict at {path}, got {type(actual).__name__}"
        assert set(actual.keys()) == set(expected.keys()), (
            f"Key mismatch at {path}: {set(actual.keys())} != {set(expected.keys())}"
        )
        for k in expected:
            _assert_approx_recursive(actual[k], expected[k], tol=tol, path=f"{path}.{k}")
    elif isinstance(expected, (list, tuple)):
        assert isinstance(actual, (list, tuple)) and len(actual) == len(expected), (
            f"Sequence mismatch at {path}: {actual!r} vs {expected!r}"
        )
        for idx, (a_item, e_item) in enumerate(zip(actual, expected, strict=True)):
            _assert_approx_recursive(a_item, e_item, tol=tol, path=f"{path}[{idx}]")
    else:
        assert actual == expected, f"Mismatch at {path}: {actual!r} != {expected!r}"


def compare_results(res_a: dict[str, Any], res_b: dict[str, Any], tol: float = 1e-9) -> None:
    """Compare two run() results stripped of package_version recursively."""
    _assert_approx_recursive(strip(res_a), strip(res_b), tol=tol)


@pytest.fixture(scope="module")
def baseline_fixture() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    units, responses = make_tables(
        n_units=30,
        n_trials=20,
        conditions=("A", "B", "C"),
        reliability=0.8,
        condition_offsets={"A": 0, "B": 1, "C": 2},
        seed=7,
    )
    baseline = run(units, responses, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)
    return units, responses, baseline


def test_invariant_to_row_order(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    units, responses, baseline = baseline_fixture
    rng = np.random.default_rng(123)
    units_shuffled = units.iloc[rng.permutation(len(units))].reset_index(drop=True)
    responses_shuffled = responses.iloc[rng.permutation(len(responses))].reset_index(drop=True)

    res = run(units_shuffled, responses_shuffled, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)
    compare_results(res, baseline)


def test_invariant_to_unit_relabeling(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    units, responses, baseline = baseline_fixture
    rng = np.random.default_rng(456)
    orig_ids = list(units["unit_id"])
    perm = rng.permutation(len(orig_ids))
    # Map every unit_id to a new random string consistently (preserving sort order so
    # permutation_null draws identical row permutations per unit).
    sorted_random_labels = sorted(
        f"unit_{rng.integers(100_000, 999_999)}_{i:03d}" for i in range(len(orig_ids))
    )
    fwd_map = dict(zip(sorted(orig_ids), sorted_random_labels, strict=True))
    inv_map = {v: k for k, v in fwd_map.items()}

    units_relabeled = units.copy()
    units_relabeled["unit_id"] = units_relabeled["unit_id"].map(fwd_map)
    responses_relabeled = responses.copy()
    responses_relabeled["unit_id"] = responses_relabeled["unit_id"].map(fwd_map)

    from recovery_reliability_benchmark.contract import validate

    val_base = validate(units, responses, ["tau", "amplitude"], 2.0)
    val_relabeled = validate(units_relabeled, responses_relabeled, ["tau", "amplitude"], 2.0)
    for c in ("A", "B", "C"):
        remapped_active = sorted(inv_map[u] for u in val_relabeled["conditions"][c]["active_units"])
        assert remapped_active == val_base["conditions"][c]["active_units"]

    res = run(units_relabeled, responses_relabeled, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)
    compare_results(res, baseline)

    # Also test a completely arbitrary permutation of random unit label strings:
    arb_labels = [f"rand_{p:02d}_{rng.integers(1000, 9999)}" for p in perm]
    arb_map = dict(zip(orig_ids, arb_labels, strict=True))
    inv_arb_map = {v: k for k, v in arb_map.items()}
    units_arb = units.copy()
    units_arb["unit_id"] = units_arb["unit_id"].map(arb_map)
    responses_arb = responses.copy()
    responses_arb["unit_id"] = responses_arb["unit_id"].map(arb_map)

    val_arb = validate(units_arb, responses_arb, ["tau", "amplitude"], 2.0)
    for c in ("A", "B", "C"):
        remapped_arb_active = sorted(inv_arb_map[u] for u in val_arb["conditions"][c]["active_units"])
        assert remapped_arb_active == val_base["conditions"][c]["active_units"]

    res_arb = run(units_arb, responses_arb, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)
    res_arb_check = copy.deepcopy(res_arb)
    base_check = copy.deepcopy(baseline)
    for m in ("tau", "amplitude"):
        res_arb_check["measures"][m].pop("null")
        base_check["measures"][m].pop("null")
        for pair_sens in res_arb_check["measures"][m]["sensitivity"].values():
            pair_sens.pop("null")
            pair_sens.pop("above_null")
        for pair_sens in base_check["measures"][m]["sensitivity"].values():
            pair_sens.pop("null")
            pair_sens.pop("above_null")
    compare_results(res_arb_check, base_check)


def test_invariant_to_condition_relabeling(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    units, responses, baseline = baseline_fixture
    cond_map = {"A": "X", "B": "Y", "C": "Z"}
    inv_map = {v: k for k, v in cond_map.items()}

    responses_relabeled = responses.copy()
    responses_relabeled["condition"] = responses_relabeled["condition"].map(cond_map)

    res = run(units, responses_relabeled, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)

    remapped = copy.deepcopy(res)
    remapped["census"]["evaluated_conditions"] = [
        inv_map[c] for c in remapped["census"]["evaluated_conditions"]
    ]
    remapped["inclusion"]["per_condition"] = {
        inv_map[c]: v for c, v in remapped["inclusion"]["per_condition"].items()
    }
    for m in ("tau", "amplitude"):
        remapped["measures"][m]["per_condition"] = {
            inv_map[c]: v for c, v in remapped["measures"][m]["per_condition"].items()
        }
        remapped["measures"][m]["sensitivity"] = {
            f"{inv_map[k.split('|')[0]]}|{inv_map[k.split('|')[1]]}": v
            for k, v in remapped["measures"][m]["sensitivity"].items()
        }

    compare_results(remapped, baseline)

    from recovery_reliability_benchmark.contract import validate

    val_base = validate(units, responses, ["tau", "amplitude"], 2.0)
    val_relabeled = validate(units, responses_relabeled, ["tau", "amplitude"], 2.0)
    assert val_relabeled["best_condition"] == cond_map[val_base["best_condition"]]


def test_invariant_to_affine_measure_transform(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    units, responses, baseline = baseline_fixture
    scale = 3.7
    shift = -12.5
    responses_aff = responses.copy()
    responses_aff["tau"] = scale * responses_aff["tau"] + shift

    res = run(units, responses_aff, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)

    tau_base = baseline["measures"]["tau"]
    tau_aff = res["measures"]["tau"]

    assert tau_aff["headline_kind"] == tau_base["headline_kind"]
    _assert_approx_recursive(tau_aff["null"], tau_base["null"])

    for scope_aff, scope_base in (
        (tau_aff["headline"], tau_base["headline"]),
        (tau_aff["pooled"]["uncentered"], tau_base["pooled"]["uncentered"]),
        (tau_aff["pooled"]["centered"], tau_base["pooled"]["centered"]),
        *((tau_aff["per_condition"][c], tau_base["per_condition"][c]) for c in ("A", "B", "C")),
    ):
        for key in (
            "rho",
            "r_half",
            "r_ci_low",
            "r_ci_high",
            "rho_ci_low",
            "rho_ci_high",
            "rho_single_trial",
            "rho_at_20",
        ):
            assert scope_aff[key] == pytest.approx(scope_base[key], rel=1e-9, abs=1e-9)

    for var_aff, var_base in (
        (tau_aff["headline"]["variance"], tau_base["headline"]["variance"]),
        *(
            (tau_aff["per_condition"][c]["variance"], tau_base["per_condition"][c]["variance"])
            for c in ("A", "B", "C")
        ),
    ):
        assert var_aff["var_between"] == pytest.approx(
            var_base["var_between"] * (scale**2), rel=1e-9, abs=1e-9
        )
        assert var_aff["var_within"] == pytest.approx(var_base["var_within"] * (scale**2), rel=1e-9, abs=1e-9)
        assert var_aff["moments_reliability"] == pytest.approx(
            var_base["moments_reliability"], rel=1e-9, abs=1e-9
        )

    for pair in ("A|B", "A|C", "B|C"):
        s_aff = tau_aff["sensitivity"][pair]
        s_base = tau_base["sensitivity"][pair]
        assert s_aff["n_units"] == s_base["n_units"]
        assert s_aff["median_abs_z"] == pytest.approx(s_base["median_abs_z"], rel=1e-9, abs=1e-9)
        assert s_aff["frac_beyond_2"] == pytest.approx(s_base["frac_beyond_2"], rel=1e-9, abs=1e-9)
        assert s_aff["median_shift"] == pytest.approx(s_base["median_shift"] * scale, rel=1e-9, abs=1e-9)
        assert s_aff["above_null"] == s_base["above_null"]
        _assert_approx_recursive(s_aff["null"], s_base["null"])


def test_invariant_to_trial_index_offset(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    units, responses, baseline = baseline_fixture
    responses_offset = responses.copy()
    responses_offset["trial_index"] = responses_offset["trial_index"] + 1000
    responses_offset["stim_time_ns"] = responses_offset["stim_time_ns"] + 1000

    res = run(units, responses_offset, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)
    compare_results(res, baseline)


def test_variance_inflation_does_not_move_score(
    baseline_fixture: tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]],
) -> None:
    """Confirm that global variance inflation does not move rho or the permutation null.

    See METHOD.md ('How this benchmark can be gamed' table, 'Variance inflation' row):
    multiplying a measure by 100 for only the even-positioned trials is NOT an invariance
    because it changes the relative scale of the two halves (modifying the data), whereas
    scaling the whole measure by 100 leaves Pearson r, Spearman-Brown rho, and the
    permutation null unchanged, giving the Arc-style variance-inflation attack no lever.
    """
    units, responses, baseline = baseline_fixture
    responses_scaled = responses.copy()
    responses_scaled["tau"] = 100.0 * responses_scaled["tau"]

    res = run(units, responses_scaled, ["tau", "amplitude"], 2.0, n_perm=200, seed=1)

    tau_base = baseline["measures"]["tau"]
    tau_scaled = res["measures"]["tau"]

    assert tau_scaled["headline"]["rho"] == pytest.approx(tau_base["headline"]["rho"], rel=1e-9, abs=1e-9)
    for c in ("A", "B", "C"):
        assert tau_scaled["per_condition"][c]["rho"] == pytest.approx(
            tau_base["per_condition"][c]["rho"], rel=1e-9, abs=1e-9
        )
    _assert_approx_recursive(tau_scaled["null"], tau_base["null"])
