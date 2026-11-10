"""Reference file writer and reader for the Recovery Reliability Benchmark."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import AnalysisParams
from .contract import read_spikes, read_tables
from .metadata import Condition, Preparation, load_analysis, write_analysis

FloatArray = Sequence[float] | np.ndarray


def _validate_times_1d(values: FloatArray, name: str) -> np.ndarray:
    """Convert ``values`` to a 1D float64 array and reject negative or non-finite entries."""
    arr = np.asarray(values, dtype=float)
    if arr.ndim != 1:
        raise ValueError(f"{name} must be a 1D array, got {arr.ndim}D.")
    if not np.all(np.isfinite(arr)):
        raise ValueError(f"{name} contains non-finite times.")
    if np.any(arr < 0.0):
        raise ValueError(f"{name} contains negative times.")
    return arr


def write_dataset(
    out_dir: str | Path,
    unit_ids: Sequence[str],
    spike_times_s: Mapping[str, FloatArray],
    onsets_s: FloatArray,
    conditions: Sequence[str],
    analysis: AnalysisParams,
    *,
    recording_id: str = "rec0",
    session_id: str = "sess0",
    preparation_id: str = "prep0",
    preparation: Preparation | None = None,
    condition_metadata: Mapping[str, Condition] | None = None,
) -> dict[str, Path]:
    """Write a spikes-path benchmark dataset directory in canonical layout.

    Writes ``units.csv``, ``trials_responses.csv`` (``trial_index`` ``0..n-1`` in onset
    order, ``stim_time_ns``, ``condition``), ``spikes.csv`` (units in ``unit_ids`` order,
    spike timestamps ascending), ``analysis.json``, and ``preparation.json`` and
    ``conditions.json`` when provided. Seconds are converted to integer nanoseconds via
    ``int(round(t * 1e9))``. Does not check contract conformance; run ``rrb-check`` on
    the written files.

    Args:
        out_dir: Destination directory path (created if absent).
        unit_ids: Ordered sequence of unique unit identifier strings.
        spike_times_s: Mapping from ``unit_id`` to a 1D array of spike timestamps in
            seconds on the recording clock. Units in ``unit_ids`` absent from
            ``spike_times_s`` are treated as having zero spikes.
        onsets_s: Strictly increasing 1D array of stimulus onset times in seconds.
        conditions: Sequence of condition labels, one per stimulus onset.
        analysis: ``AnalysisParams`` instance written to ``analysis.json``.
        recording_id: Recording identifier written to ``units.csv`` (default ``"rec0"``).
        session_id: Session identifier written to ``units.csv`` (default ``"sess0"``).
        preparation_id: Preparation identifier written to ``units.csv`` (default ``"prep0"``).
        preparation: Optional ``Preparation`` model written to ``preparation.json``.
        condition_metadata: Optional mapping from condition label to ``Condition`` model
            written to ``conditions.json``.

    Returns:
        Dictionary mapping ``"units"``, ``"trials"``, ``"spikes"``, ``"analysis"``, and
        (when provided) ``"preparation"`` and ``"conditions"`` to the written ``Path``s.

    Raises:
        ValueError: If ``unit_ids`` has duplicates, ``spike_times_s`` has a key missing
            from ``unit_ids``, ``onsets_s`` is not strictly increasing, ``len(conditions)
            != len(onsets_s)``, any timestamp is negative or non-finite, or
            ``condition_metadata`` keys differ from the set of ``conditions`` labels.
    """
    if isinstance(unit_ids, str):
        raise ValueError("unit_ids must be a sequence of unit ID strings, not a str.")
    if isinstance(conditions, str):
        raise ValueError("conditions must be a sequence of condition labels, not a str.")

    unit_list = [str(u) for u in unit_ids]
    seen_units: set[str] = set()
    duplicates: list[str] = []
    for uid in unit_list:
        if uid in seen_units and uid not in duplicates:
            duplicates.append(uid)
        seen_units.add(uid)
    if duplicates:
        raise ValueError(f"duplicate unit_ids: {duplicates}.")

    unknown_units = [str(k) for k in spike_times_s if str(k) not in seen_units]
    if unknown_units:
        raise ValueError(f"spike_times_s has unit_id keys missing from unit_ids: {unknown_units}.")
    spike_map = {str(k): v for k, v in spike_times_s.items()}

    onsets = _validate_times_1d(onsets_s, "onsets_s")
    cond_list = [str(c) for c in conditions]
    if len(cond_list) != len(onsets):
        raise ValueError(f"len(conditions) ({len(cond_list)}) != len(onsets_s) ({len(onsets)}).")
    if len(onsets) > 1 and not np.all(np.diff(onsets) > 0.0):
        raise ValueError("onsets_s must be strictly increasing.")

    stim_times_ns = [int(round(float(t) * 1e9)) for t in onsets]
    if any(b <= a for a, b in zip(stim_times_ns, stim_times_ns[1:], strict=False)):
        raise ValueError("onsets_s must be strictly increasing after nanosecond rounding.")

    if condition_metadata is not None:
        meta_keys = {str(k) for k in condition_metadata}
        cond_set = set(cond_list)
        if meta_keys != cond_set:
            raise ValueError(
                f"condition_metadata keys {sorted(meta_keys)} differ from condition labels {sorted(cond_set)}."
            )

    spike_unit_col: list[str] = []
    spike_time_col: list[int] = []
    for uid in unit_list:
        raw_train = spike_map.get(uid)
        if raw_train is None:
            continue
        arr = _validate_times_1d(raw_train, f"spike_times_s[{uid!r}]")
        if arr.size == 0:
            continue
        ns_times = sorted(int(round(float(t_s) * 1e9)) for t_s in arr)
        spike_unit_col.extend([uid] * len(ns_times))
        spike_time_col.extend(ns_times)

    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    n_units = len(unit_list)
    units_df = pd.DataFrame(
        {
            "unit_id": unit_list,
            "recording_id": [str(recording_id)] * n_units,
            "session_id": [str(session_id)] * n_units,
            "preparation_id": [str(preparation_id)] * n_units,
        },
        columns=["unit_id", "recording_id", "session_id", "preparation_id"],
    )
    units_path = out_path / "units.csv"
    units_df.to_csv(units_path, index=False)

    trials_df = pd.DataFrame(
        {
            "trial_index": list(range(len(stim_times_ns))),
            "stim_time_ns": stim_times_ns,
            "condition": cond_list,
        },
        columns=["trial_index", "stim_time_ns", "condition"],
    )
    trials_path = out_path / "trials_responses.csv"
    trials_df.to_csv(trials_path, index=False)

    if spike_time_col:
        spikes_df = pd.DataFrame(
            {"unit_id": spike_unit_col, "spike_time_ns": spike_time_col},
            columns=["unit_id", "spike_time_ns"],
        )
    else:
        spikes_df = pd.DataFrame(columns=["unit_id", "spike_time_ns"])
    spikes_path = out_path / "spikes.csv"
    spikes_df.to_csv(spikes_path, index=False)

    analysis_path = out_path / "analysis.json"
    write_analysis(analysis, analysis_path)

    paths: dict[str, Path] = {
        "units": units_path,
        "trials": trials_path,
        "spikes": spikes_path,
        "analysis": analysis_path,
    }

    if preparation is not None:
        prep_path = out_path / "preparation.json"
        prep_path.write_text(
            json.dumps(preparation.model_dump(), indent=2) + "\n",
            encoding="utf-8",
        )
        paths["preparation"] = prep_path

    if condition_metadata is not None:
        cond_path = out_path / "conditions.json"
        cond_payload = {str(k): v.model_dump() for k, v in condition_metadata.items()}
        cond_path.write_text(
            json.dumps(cond_payload, indent=2) + "\n",
            encoding="utf-8",
        )
        paths["conditions"] = cond_path

    return paths


def read_dataset(
    directory: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, AnalysisParams]:
    """Read ``(units, trials, spikes, analysis)`` from a dataset directory.

    Args:
        directory: Directory containing ``units.csv``, ``trials_responses.csv``,
            ``spikes.csv``, and ``analysis.json``.

    Returns:
        Tuple of ``(units, trials, spikes, analysis)`` loaded with contract dtypes and
        validated ``AnalysisParams``.

    Raises:
        FileNotFoundError: If any of the four required dataset files is missing.
        ContractViolation: If ``analysis.json`` fails schema validation.
    """
    base = Path(directory)
    analysis_path = base / "analysis.json"
    units, trials = read_tables(base / "units.csv", base / "trials_responses.csv")
    spikes = read_spikes(base / "spikes.csv")
    if not analysis_path.is_file():
        raise FileNotFoundError(analysis_path)
    analysis = load_analysis(analysis_path)
    return units, trials, spikes, analysis
