Task: on the spikes path, a malformed table gives a contract violation with exit code 1, never a
Python traceback, and a clock mismatch gets a message a lab can act on. This changes frozen items
(checks.check_identifiers, checks_spikes.check_scored_units, two new frozen functions). That is intended:
record it under 0.2.0 and amend (step 7).

Why: on the spikes path the code reads the tables before the contract has checked them. Measured on the
current head: a missing column in any of the three tables, an empty stim_time_ns or trial_index, or a
repeated trial_index crashes rrb-check, rrb-evaluate and rrb-report with KeyError or ValueError. An empty
condition cell is silently accepted on the spikes path and crashes the tables path with KeyError. Spikes
on a different clock give "measure 'spike_count' is constant within every (unit_id, condition) group".

1. checks.check_identifiers: the null trial_index check becomes this loop (checks.py stays at 299 lines):

```python
    for col in ("trial_index", "condition"):
        n_null = int(ctx.responses[col].isna().sum())
        if n_null > 0:
            msg = f"{n_null} responses rows have a null {col}, requires 0."
            raise ContractViolation(Requirement.SCHEMA, msg, found=n_null, required=0)
```

   Docstring: also rejects a null condition.

2. checks_spikes.py: imports become
     from . import checks, contract
     from .contract import ContractViolation, Requirement, ValidationContext
   Add before check_pre_stimulus_window, unchanged:

```python
TRIALS_REQUIRED = ("trial_index", "stim_time_ns", "condition")


@frozen("SPEC SCHEMA")
def check_spikes_path_tables(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    spikes: pd.DataFrame,
    params: AnalysisParams,
) -> None:
    """Check the units, trial and spikes tables before any spike is counted.

    Required columns and nulls are checked here; the stimulus timeline is then checked by
    the tables-path functions ``check_stimulus_timeline`` (min-dataset-4) and
    ``check_post_stimulus_window`` (min-dataset-6), so one fault gives one message on
    both paths.

    Args:
        units: Recording-unit table.
        responses: Trial table with ``trial_index``, ``stim_time_ns`` and ``condition``.
        spikes: Spike table with ``unit_id`` and ``spike_time_ns``.
        params: Analysis parameters defining ``post_stim_window_s`` and ``load_duration_s``.

    Raises:
        ContractViolation: With ``Requirement.SCHEMA`` on a missing required column or a null
            ``trial_index``, ``condition`` or ``spike_time_ns``; with ``Requirement.MD4`` or
            ``Requirement.MD6`` from the timeline checks.
    """
    tables = (
        ("units", units, contract.UNITS_REQUIRED),
        ("responses", responses, TRIALS_REQUIRED),
        ("spikes", spikes, contract.SPIKES_REQUIRED),
    )
    for name, table, required in tables:
        for col in required:
            if col not in table.columns:
                raise ContractViolation(Requirement.SCHEMA, f"{name} is missing required column '{col}'.")
    for name, table, col in (
        ("responses", responses, "trial_index"),
        ("responses", responses, "condition"),
        ("spikes", spikes, "spike_time_ns"),
    ):
        n_null = int(table[col].isna().sum())
        if n_null > 0:
            msg = f"{n_null} {name} rows have a null {col}, requires 0."
            raise ContractViolation(Requirement.SCHEMA, msg, found=n_null, required=0)
    ctx = ValidationContext(
        units=units,
        responses=responses,
        measures=[],
        post_stim_window_s=float(params.post_stim_window_s),
        load_duration_s=float(params.load_duration_s),
        forbidden=frozenset(),
        preparation=None,
        conditions=None,
        spikes=None,
    )
    checks.check_stimulus_timeline(ctx)
    checks.check_post_stimulus_window(ctx)


@frozen("SPEC SCHEMA")
def check_spikes_in_windows(counts: pd.DataFrame, n_spikes: int) -> None:
    """Check that at least one spike falls inside a post-stimulus window.

    Args:
        counts: Per-unit, per-trial table from ``spikes.per_trial_counts_table``.
        n_spikes: Number of rows in the spikes table.

    Raises:
        ContractViolation: With ``Requirement.SCHEMA`` when every ``spike_count`` is zero, which
            is what a clock or unit mismatch between spikes and stimuli looks like.
    """
    if int(counts["spike_count"].sum()) == 0:
        msg = (
            f"0 of {n_spikes} spikes fall inside a post-stimulus window, requires at least 1. "
            "Check that spike_time_ns and stim_time_ns are integer nanoseconds on the same clock."
        )
        raise ContractViolation(Requirement.SCHEMA, msg, found=0, required=1)
```

   The timeline is checked by the same two functions the tables path uses, so one fault gives one message
   on both paths.

3. checks_spikes.check_scored_units loses its argument-swapping branch and becomes, unchanged:

```python
@frozen("SPEC min-dataset-3")
def check_scored_units(
    scored: Mapping[str, Mapping[str, Set[str]]],
    measure: str,
    condition: str,
) -> None:
    """Check min-dataset-3 on the spikes path: at least ``MD3_MUST`` scored units for ``measure``.

    Args:
        scored: Mapping from measure name to per-condition sets of scored ``unit_id`` strings.
        measure: Measure name to verify.
        condition: Condition label to verify.

    Raises:
        ContractViolation: With ``Requirement.MD3`` when fewer than ``MD3_MUST`` units are scored.
    """
    n_scored = len(scored.get(measure, {}).get(condition, set()))
    if n_scored < contract.MD3_MUST:
        msg = (
            f"{n_scored} units with {measure} computed in both halves "
            f"for condition '{condition}', requires {contract.MD3_MUST}."
        )
        raise ContractViolation(Requirement.MD3, msg, found=n_scored, required=contract.MD3_MUST)
```

4. inputs.py: add before from_spikes, unchanged:

```python
def validate_spikes_path(
    units: pd.DataFrame,
    responses: pd.DataFrame,
    spikes: pd.DataFrame,
    analysis: AnalysisParams,
    extra_forbidden: set[str] | None = None,
    preparation: Preparation | None = None,
    conditions: dict[str, Condition] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Run every contract check of the spikes path, in order.

    Args:
        units: Recording-unit table.
        responses: Trial table carrying ``trial_index``, ``stim_time_ns``, and ``condition``.
        spikes: Spike-timestamp DataFrame.
        analysis: ``AnalysisParams`` defining the load duration and the two windows.
        extra_forbidden: Additional column names disallowed as measures.
        preparation: Optional validated ``Preparation`` metadata model.
        conditions: Optional mapping of condition labels to ``Condition`` metadata models.

    Returns:
        Tuple ``(report, trials)`` of the conformance report from ``validate`` on the per-trial
        spike count table and the deduplicated trial table.

    Raises:
        ContractViolation: On the first failed requirement.
    """
    checks_spikes.check_spikes_path_tables(units, responses, spikes, analysis)
    trials = spikes_mod.trial_table(responses)
    counts = spikes_mod.per_trial_counts_table(units, trials, spikes, analysis)
    checks_spikes.check_spikes_in_windows(counts, int(len(spikes)))
    post_w, load_s = float(analysis.post_stim_window_s), float(analysis.load_duration_s)
    report = validate(
        units, counts, ["spike_count"], post_w, load_s, extra_forbidden, preparation, conditions, spikes
    )
    checks_spikes.check_pre_stimulus_window(trials, analysis, load_s)
    return report, trials
```

   In from_spikes, the block from `trials = spikes_mod.trial_table(responses)` through
   `checks_spikes.check_pre_stimulus_window(trials, analysis, load_s)` is replaced by

```python
    val, trials = validate_spikes_path(
        units, responses, spikes, analysis, preparation=preparation, conditions=conditions
    )
```

5. cli.check_main uses the same entry point. Import validate_spikes_path from .inputs, drop the imports
   of checks_spikes and spikes_mod, and replace the body of the try block after prep and conds with

```python
        ef = set(extra_forbidden) if extra_forbidden else None
        if analysis is not None and spikes is not None:
            result, _trials = validate_spikes_path(units, responses, spikes, analysis, ef, prep, conds)
            result["pre_stim_window_s"] = float(analysis.pre_stim_window_s)
            result["analysis_fingerprint"] = analysis.fingerprint()
        else:
            result = validate(units, responses, measures, w, d, ef, prep, conds, spikes)
```

6. New file tests/test_spikes_inputs.py, unchanged:

```python
"""Tests that malformed spikes-path tables give contract violations, never tracebacks."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from recovery_reliability_benchmark.analysis import AnalysisParams
from recovery_reliability_benchmark.cli import check_main, evaluate_main
from recovery_reliability_benchmark.contract import ContractViolation, Requirement, validate
from recovery_reliability_benchmark.inputs import validate_spikes_path
from recovery_reliability_benchmark.report import main as report_main
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.synthetic import exponential_recovery, make_spike_trains, make_tables

Tables = tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]


def _good_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fns = [exponential_recovery(5.0, 100.0, float(tau)) for tau in np.geomspace(0.05, 0.5, 12)]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=20, params=params, isi_s=5.0, seed=0)
    unit_ids = [f"u{i:02d}" for i in range(12)]
    units = pd.DataFrame(
        {"unit_id": unit_ids, "recording_id": "rec0", "session_id": "sess0", "preparation_id": "prep0"}
    )
    trials = pd.DataFrame(
        {
            "trial_index": pd.array(range(20), dtype="Int64"),
            "stim_time_ns": pd.array([int(round(float(t) * 1e9)) for t in onsets_s], dtype="Int64"),
            "condition": "A",
        }
    )
    spikes = pd.DataFrame(
        [
            (uid, int(round(float(t) * 1e9)))
            for uid, train in zip(unit_ids, trains, strict=True)
            for t in train
        ],
        columns=["unit_id", "spike_time_ns"],
    ).astype({"spike_time_ns": "Int64"})
    return units, trials, spikes, params


def _drop(table: str, column: str) -> Callable[[Tables], Tables]:
    def mutate(tables: Tables) -> Tables:
        frames = dict(zip(("units", "trials", "spikes"), tables, strict=True))
        frames[table] = frames[table].drop(columns=[column])
        return frames["units"], frames["trials"], frames["spikes"]

    return mutate


def _null(table: str, column: str) -> Callable[[Tables], Tables]:
    def mutate(tables: Tables) -> Tables:
        frames = dict(zip(("units", "trials", "spikes"), tables, strict=True))
        frame = frames[table].copy()
        frame[column] = frame[column].astype(object)
        frame.loc[3, column] = None
        frames[table] = frame
        return frames["units"], frames["trials"], frames["spikes"]

    return mutate


def _duplicate_trial_index(tables: Tables) -> Tables:
    units, trials, spikes = tables
    trials = trials.copy()
    trials.loc[1, "trial_index"] = 0
    return units, trials, spikes


def _spikes_on_another_clock(tables: Tables) -> Tables:
    units, trials, spikes = tables
    return units, trials, spikes.assign(spike_time_ns=spikes["spike_time_ns"] + 10**12)


def _stim_times_in_seconds(tables: Tables) -> Tables:
    units, trials, spikes = tables
    return units, trials.assign(stim_time_ns=trials["stim_time_ns"] // 10**9), spikes


CASES: list[tuple[str, Callable[[Tables], Tables], Requirement, str]] = [
    (
        "units_missing_unit_id",
        _drop("units", "unit_id"),
        Requirement.SCHEMA,
        "units is missing required column 'unit_id'.",
    ),
    (
        "trials_missing_condition",
        _drop("trials", "condition"),
        Requirement.SCHEMA,
        "responses is missing required column 'condition'.",
    ),
    (
        "trials_missing_stim_time",
        _drop("trials", "stim_time_ns"),
        Requirement.SCHEMA,
        "responses is missing required column 'stim_time_ns'.",
    ),
    (
        "spikes_missing_spike_time",
        _drop("spikes", "spike_time_ns"),
        Requirement.SCHEMA,
        "spikes is missing required column 'spike_time_ns'.",
    ),
    (
        "null_trial_index",
        _null("trials", "trial_index"),
        Requirement.SCHEMA,
        "1 responses rows have a null trial_index, requires 0.",
    ),
    (
        "null_condition",
        _null("trials", "condition"),
        Requirement.SCHEMA,
        "1 responses rows have a null condition, requires 0.",
    ),
    (
        "null_stim_time",
        _null("trials", "stim_time_ns"),
        Requirement.MD4,
        "1 responses rows have a null stim_time_ns, requires 0.",
    ),
    (
        "null_spike_time",
        _null("spikes", "spike_time_ns"),
        Requirement.SCHEMA,
        "1 spikes rows have a null spike_time_ns, requires 0.",
    ),
    (
        "duplicate_trial_index",
        _duplicate_trial_index,
        Requirement.MD4,
        "trial_index 0 has 2 distinct stim_time_ns values, requires 1.",
    ),
    (
        "spikes_on_another_clock",
        _spikes_on_another_clock,
        Requirement.SCHEMA,
        "0 of 10892 spikes fall inside a post-stimulus window, requires at least 1. "
        "Check that spike_time_ns and stim_time_ns are integer nanoseconds on the same clock.",
    ),
    (
        "stim_times_in_seconds",
        _stim_times_in_seconds,
        Requirement.MD6,
        "Trial 0 has 0.000 s available before the next stimulus (gap 0.000 s minus load 0.000 s), requires 2.000 s.",
    ),
]


def test_good_tables_pass() -> None:
    units, trials, spikes, params = _good_tables()
    report, trial_table = validate_spikes_path(units, trials, spikes, params)
    assert report["conformance"] == "conforming"
    assert len(trial_table) == 20


@pytest.mark.parametrize(
    ("mutate", "requirement", "message"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_malformed_tables_raise_violations(
    mutate: Callable[[Tables], Tables], requirement: Requirement, message: str
) -> None:
    units, trials, spikes, params = _good_tables()
    bad_units, bad_trials, bad_spikes = mutate((units, trials, spikes))
    with pytest.raises(ContractViolation) as exc_info:
        validate_spikes_path(bad_units, bad_trials, bad_spikes, params)
    assert exc_info.value.requirement is requirement
    assert exc_info.value.message == message
    with pytest.raises(ContractViolation) as run_info:
        run(bad_units, bad_trials, ["t_half_excess"], spikes=bad_spikes, analysis=params, n_perm=20)
    assert str(run_info.value) == str(exc_info.value)


@pytest.mark.parametrize(
    ("mutate", "requirement", "message"), [c[1:] for c in CASES], ids=[c[0] for c in CASES]
)
def test_malformed_files_exit_1_from_every_command(
    mutate: Callable[[Tables], Tables],
    requirement: Requirement,
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    units, trials, spikes, params = _good_tables()
    bad_units, bad_trials, bad_spikes = mutate((units, trials, spikes))
    bad_units.to_csv(tmp_path / "units.csv", index=False)
    bad_trials.to_csv(tmp_path / "trials.csv", index=False)
    bad_spikes.to_csv(tmp_path / "spikes.csv", index=False)
    (tmp_path / "analysis.json").write_text('{"post_stim_window_s": 2.0}', encoding="utf-8")
    base = [
        str(tmp_path / "units.csv"),
        str(tmp_path / "trials.csv"),
        "--spikes",
        str(tmp_path / "spikes.csv"),
        "--analysis",
        str(tmp_path / "analysis.json"),
    ]
    expected = f"{requirement.value} failed. {message}"
    measures = ["--measures", "t_half_excess", "--n-perm", "20"]
    for command, extra in (
        (check_main, []),
        (evaluate_main, measures),
        (report_main, [*measures, "--out", str(tmp_path / "report")]),
    ):
        assert command([*base, *extra]) == 1
        assert capsys.readouterr().out.strip() == expected


def test_null_condition_on_tables_path() -> None:
    units, responses = make_tables(n_units=12, n_trials=20, reliability=0.8, seed=1)
    responses["condition"] = responses["condition"].astype(object)
    responses.loc[5, "condition"] = None
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, ["tau"], post_stim_window_s=2.0)
    assert exc_info.value.requirement is Requirement.SCHEMA
    assert exc_info.value.message == "1 responses rows have a null condition, requires 0."
```

   Existing tests stay as they are, including test_trial_table_rejects_inconsistent_trial.

7. Docs and freeze:
   - SPEC.md "Evaluating from spikes", append: "The three tables are checked before any spike is counted:
     required columns and nulls under SCHEMA, then the stimulus timeline under `min-dataset-4` and
     `min-dataset-6`, with the same messages as the tables path. A dataset with no spike inside any
     post-stimulus window is rejected under SCHEMA, with a note to check that `spike_time_ns` and
     `stim_time_ns` are integer nanoseconds on the same clock."
   - frozen/README.md: add rows for `recovery_reliability_benchmark.checks_spikes.check_spikes_in_windows`
     and `recovery_reliability_benchmark.checks_spikes.check_spikes_path_tables` (function, SPEC SCHEMA).
   - CHANGELOG.md under 0.2.0:
     "Frozen: check_identifiers rejects a null condition under SCHEMA (it crashed before)."
     "Frozen: new checks_spikes.check_spikes_path_tables and checks_spikes.check_spikes_in_windows run
     before spikes are counted, so a missing column, a null, an inconsistent trial or a clock mismatch
     gives a contract violation instead of a traceback; check_scored_units takes one argument order."
   - Run `python scripts/freeze.py --amend`.

No score changes: no example, README table or docs/spikes_path_checks number moves. Do not change the
expected messages or the spike count 10892 in the tests; if one differs, stop and report it.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass (305 tests); the frozen manifest lists 46 functions. Report: the suite count and the function count.
