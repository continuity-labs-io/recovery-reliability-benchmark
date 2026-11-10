"""Generate example CSV tables and metadata sidecars for the Recovery Reliability Benchmark."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from recovery_reliability_benchmark.measures import AnalysisParams
from recovery_reliability_benchmark.metadata import Condition, Preparation, write_analysis
from recovery_reliability_benchmark.protocol import Protocol
from recovery_reliability_benchmark.synthetic import (
    exponential_recovery,
    make_spike_trains,
    make_tables,
    make_two_condition_spike_trains,
)
from recovery_reliability_benchmark.writer import write_dataset

N_UNITS = 30  # MD3_SHOULD fully-conforming unit count
N_TRIALS = 20  # MD2_SHOULD fully-conforming trial count
TABLES_RELIABILITY = 0.8
POST_STIM_WINDOW_S = 2.0
TAU_MIN_S = 0.05
TAU_MAX_S = 0.5
BASELINE_MIN_HZ = 1.0
BASELINE_MAX_HZ = 20.0
# Stride coprime to N_UNITS=30 permutes baselines deterministically so baseline_hz
# varies across units (giving the reference row real signal) without tracking tau_s.
BASELINE_STRIDE = 7
PEAK_RATE_HZ = 100.0
INTER_STIMULUS_INTERVAL_S = 5.0
SLOWING_FACTOR = 1.5
EXAMPLE_SEED = 0


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    units, responses = make_tables(
        n_units=N_UNITS,
        n_trials=N_TRIALS,
        conditions=("baseline",),
        reliability=TABLES_RELIABILITY,
        seed=EXAMPLE_SEED,
    )
    units.to_csv(examples_dir / "units.csv", index=False)
    responses.to_csv(examples_dir / "responses.csv", index=False)

    preparation = Preparation(
        preparation_id="prep0",
        species="Rattus norvegicus",
        preparation_type="dissociated_culture",
        age_days=21,
        age_basis="DIV",
        line_or_donor_id="example",
        instrument="synthetic",
    )
    (examples_dir / "preparation.json").write_text(
        json.dumps(preparation.model_dump(exclude={"exclusions"}), indent=2) + "\n",
        encoding="utf-8",
    )

    conditions = {
        "baseline": Condition(
            protocol=Protocol.standard_hfs(),
            compound=None,
            dose=None,
            dose_unit=None,
            vehicle=None,
        ).model_dump()
    }
    (examples_dir / "conditions.json").write_text(
        json.dumps(conditions, indent=2) + "\n",
        encoding="utf-8",
    )

    analysis = AnalysisParams(post_stim_window_s=POST_STIM_WINDOW_S)
    write_analysis(analysis, examples_dir / "analysis.json")

    taus_s = np.geomspace(TAU_MIN_S, TAU_MAX_S, N_UNITS)
    baselines_hz = np.geomspace(BASELINE_MIN_HZ, BASELINE_MAX_HZ, N_UNITS)
    rate_fns = [
        exponential_recovery(
            baseline_hz=float(baselines_hz[(BASELINE_STRIDE * i) % N_UNITS]),
            peak_hz=PEAK_RATE_HZ,
            tau_s=float(tau_s),
        )
        for i, tau_s in enumerate(taus_s)
    ]
    trains, onsets_s = make_spike_trains(
        rate_fns,
        n_trials=N_TRIALS,
        params=analysis,
        isi_s=INTER_STIMULUS_INTERVAL_S,
        seed=EXAMPLE_SEED,
    )

    trials_df = pd.DataFrame(
        {
            "trial_index": list(range(len(onsets_s))),
            "stim_time_ns": [int(round(float(t) * 1e9)) for t in onsets_s],
            "condition": "baseline",
        }
    )
    trials_df.to_csv(examples_dir / "trials_responses.csv", index=False)

    spike_rows = [
        {"unit_id": str(uid), "spike_time_ns": int(round(float(t_s) * 1e9))}
        for uid, train in zip(units["unit_id"], trains, strict=True)
        for t_s in train
    ]
    spikes_df = pd.DataFrame(spike_rows, columns=["unit_id", "spike_time_ns"])
    spikes_df.to_csv(examples_dir / "spikes.csv", index=False)

    two_cond_dir = examples_dir / "two_conditions"
    rate_fns_slowed = [
        exponential_recovery(
            baseline_hz=float(baselines_hz[(BASELINE_STRIDE * i) % N_UNITS]),
            peak_hz=PEAK_RATE_HZ,
            tau_s=float(tau_s * SLOWING_FACTOR),
        )
        for i, tau_s in enumerate(taus_s)
    ]
    trains_two, onsets_two_s, n_first = make_two_condition_spike_trains(
        rate_fns,
        rate_fns_slowed,
        n_trials=N_TRIALS,
        params=analysis,
        isi_s=INTER_STIMULUS_INTERVAL_S,
        seed=EXAMPLE_SEED,
    )
    unit_ids = [f"u{i:02d}" for i in range(N_UNITS)]
    write_dataset(
        two_cond_dir,
        unit_ids=unit_ids,
        spike_times_s=dict(zip(unit_ids, trains_two, strict=True)),
        onsets_s=onsets_two_s,
        conditions=["control"] * n_first + ["slowed"] * (len(onsets_two_s) - n_first),
        analysis=analysis,
        condition_metadata={
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
                dose=SLOWING_FACTOR,
                dose_unit="x tau",
                vehicle=None,
            ),
        },
    )


if __name__ == "__main__":
    main()
