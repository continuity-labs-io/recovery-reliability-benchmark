"""Tests for strict JSON output and undefined-correlation handling."""

from __future__ import annotations

import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.cli import check_main, evaluate_main
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.strict_json import dumps_strict
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_spike_trains
from recovery_reliability_benchmark.writer import read_dataset, write_dataset

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
TWO_COND_DIR = EXAMPLES_DIR / "two_conditions"
UNDEFINED_MEASURES = "t_return,t_half_excess"


def parse_strict_json(text: str) -> Any:
    """Parse JSON text while rejecting non-standard NaN and Infinity constants."""

    def _reject_constant(token: str) -> Any:
        raise ValueError(f"Non-standard JSON constant: {token}")

    return json.loads(text, parse_constant=_reject_constant)


def write_undefined_measure_dataset(out_dir: Path) -> dict[str, Path]:
    """Write the 12-unit slowly recovering dataset where t_return is censored for every unit."""
    params = AnalysisParams(post_stim_window_s=2.0)
    taus = np.geomspace(4.0, 8.0, 12)
    rate_fns = [exponential_recovery(5.0, 100.0, float(tau)) for tau in taus]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=20, params=params, isi_s=5.0, seed=0)
    unit_ids = [f"u{i:02d}" for i in range(12)]
    spike_times_s = dict(zip(unit_ids, trains, strict=True))
    return write_dataset(out_dir, unit_ids, spike_times_s, onsets_s, ["baseline"] * 20, params)


@pytest.fixture(scope="module")
def undefined_dataset_paths(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    out_dir = tmp_path_factory.mktemp("undefined_measure_dataset")
    return write_undefined_measure_dataset(out_dir)


def test_strict_parser_rejects_non_finite_tokens() -> None:
    for bad_token in ("NaN", "Infinity", "-Infinity", '{"x": NaN}'):
        with pytest.raises(ValueError, match="Non-standard JSON constant"):
            parse_strict_json(bad_token)


@pytest.mark.parametrize(
    "bad_float",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        np.float64("nan"),
        np.float64("inf"),
        np.float64("-inf"),
        np.float32("nan"),
        np.float32("inf"),
        np.float32("-inf"),
        np.float16("nan"),
    ],
)
def test_dumps_strict_top_level_non_finite_becomes_null(bad_float: Any) -> None:
    encoded = dumps_strict(bad_float)
    assert encoded == "null"
    assert parse_strict_json(encoded) is None


def test_dumps_strict_nested_containers_and_preserved_types() -> None:
    payload: dict[str, Any] = {
        "nan_val": float("nan"),
        "pos_inf": float("inf"),
        "neg_inf": float("-inf"),
        "nested_dict": {
            "np_nan64": np.float64("nan"),
            "np_inf32": np.float32("inf"),
            "np_ninf32": np.float32("-inf"),
            "finite_np64": np.float64(1.25),
            "finite_np32": np.float32(2.5),
        },
        "list_items": [float("nan"), 3.5, (float("inf"), float("-inf"), np.float64("nan"), "ok")],
        "tuple_items": (0.0, -4.25, 7, -3, True, False, "text", "NaN", "Infinity", None),
    }
    encoded = dumps_strict(payload, indent=2, sort_keys=True)
    parsed = parse_strict_json(encoded)

    assert parsed == {
        "nan_val": None,
        "pos_inf": None,
        "neg_inf": None,
        "nested_dict": {
            "np_nan64": None,
            "np_inf32": None,
            "np_ninf32": None,
            "finite_np64": 1.25,
            "finite_np32": 2.5,
        },
        "list_items": [None, 3.5, [None, None, None, "ok"]],
        "tuple_items": [0.0, -4.25, 7, -3, True, False, "text", "NaN", "Infinity", None],
    }
    assert type(parsed["tuple_items"][2]) is int
    assert type(parsed["tuple_items"][4]) is bool
    assert type(parsed["tuple_items"][5]) is bool
    assert math.isnan(payload["nan_val"])
    assert math.isnan(float(payload["nested_dict"]["np_nan64"]))


def test_dumps_strict_raises_if_non_finite_escapes_conversion(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValueError):
        dumps_strict({float("nan"): 1})

    monkeypatch.setattr(
        "recovery_reliability_benchmark.strict_json._replace_non_finite",
        lambda x: x,
    )
    with pytest.raises(ValueError):
        dumps_strict({"escaped": float("nan")})


def _assert_undefined_t_return(measure_entry: dict[str, Any]) -> None:
    headline = measure_entry["headline"]
    assert headline["r_half"] is None
    assert headline["r_undefined"] is True
    assert headline["rho"] == 0.0

    null = measure_entry["null"]
    assert null["median_r"] is None
    assert null["p95_r"] is None

    for cond_entry in measure_entry["per_condition"].values():
        assert cond_entry["r_half"] is None
    assert measure_entry["pooled"]["uncentered"]["r_half"] is None
    assert measure_entry["pooled"]["centered"]["r_half"] is None


def test_evaluate_json_undefined_measure_strict_and_warning_free(
    undefined_dataset_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        str(undefined_dataset_paths["units"]),
        str(undefined_dataset_paths["trials"]),
        "--spikes",
        str(undefined_dataset_paths["spikes"]),
        "--analysis",
        str(undefined_dataset_paths["analysis"]),
        "--measures",
        UNDEFINED_MEASURES,
        "--n-perm",
        "20",
        "--json",
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        rc = evaluate_main(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""
    assert "NaN" not in captured.out
    assert "Infinity" not in captured.out

    doc = parse_strict_json(captured.out)
    _assert_undefined_t_return(doc["result"]["measures"]["t_return"])

    units, trials, spikes, analysis = read_dataset(undefined_dataset_paths["units"].parent)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        mem_result = run(
            units,
            trials,
            ["t_return", "t_half_excess"],
            spikes=spikes,
            analysis=analysis,
            n_perm=20,
        )
    assert math.isnan(mem_result["measures"]["t_return"]["headline"]["r_half"])
    assert math.isnan(mem_result["measures"]["t_return"]["null"]["median_r"])
    assert math.isnan(mem_result["measures"]["t_return"]["null"]["p95_r"])


def test_report_undefined_measure_strict_and_warning_free(
    undefined_dataset_paths: dict[str, Path],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    out_dir = tmp_path / "report_undefined"
    args = [
        str(undefined_dataset_paths["units"]),
        str(undefined_dataset_paths["trials"]),
        "--spikes",
        str(undefined_dataset_paths["spikes"]),
        "--analysis",
        str(undefined_dataset_paths["analysis"]),
        "--measures",
        UNDEFINED_MEASURES,
        "--n-perm",
        "20",
        "--out",
        str(out_dir),
    ]
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        rc = report_main(args)

    captured = capsys.readouterr()
    assert rc == 0
    assert captured.err == ""

    raw_eval = (out_dir / "evaluate.json").read_text(encoding="utf-8")
    assert "NaN" not in raw_eval
    assert "Infinity" not in raw_eval
    eval_doc = parse_strict_json(raw_eval)
    _assert_undefined_t_return(eval_doc["measures"]["t_return"])

    out_dir_json = tmp_path / "report_undefined_json"
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        rc_json = report_main([*args[:-1], str(out_dir_json), "--json"])
    captured_json = capsys.readouterr()
    assert rc_json == 0
    assert "NaN" not in captured_json.out
    assert "Infinity" not in captured_json.out
    cli_doc = parse_strict_json(captured_json.out)
    _assert_undefined_t_return(cli_doc["result"]["measures"]["t_return"])


def test_check_json_undefined_dataset_parses_strictly(
    undefined_dataset_paths: dict[str, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = check_main(
        [
            str(undefined_dataset_paths["units"]),
            str(undefined_dataset_paths["trials"]),
            "--spikes",
            str(undefined_dataset_paths["spikes"]),
            "--analysis",
            str(undefined_dataset_paths["analysis"]),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    assert "NaN" not in captured.out
    assert "Infinity" not in captured.out
    doc = parse_strict_json(captured.out)
    assert doc["status"] == "conforming"


def test_two_conditions_evaluate_json_byte_identical_to_stdlib(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = evaluate_main(
        [
            str(TWO_COND_DIR / "units.csv"),
            str(TWO_COND_DIR / "trials_responses.csv"),
            "--spikes",
            str(TWO_COND_DIR / "spikes.csv"),
            "--analysis",
            str(TWO_COND_DIR / "analysis.json"),
            "--conditions",
            str(TWO_COND_DIR / "conditions.json"),
            "--measures",
            "t_half_excess,excess_per_trial,t_return",
            "--n-perm",
            "50",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert rc == 0
    document = parse_strict_json(captured.out)
    assert captured.out == json.dumps(document, indent=2, sort_keys=True) + "\n"
