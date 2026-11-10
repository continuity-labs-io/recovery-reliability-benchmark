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
)


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    units, responses = make_tables(
        n_units=30,
        n_trials=20,
        conditions=("baseline",),
        reliability=0.8,
        seed=0,
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
        json.dumps(preparation.model_dump(), indent=2) + "\n",
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

    analysis = AnalysisParams(post_stim_window_s=2.0)
    write_analysis(analysis, examples_dir / "analysis.json")

    taus = np.geomspace(0.05, 0.5, 30)
    rate_fns = [exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=float(tau)) for tau in taus]
    trains, onsets_s = make_spike_trains(rate_fns, n_trials=20, params=analysis, isi_s=5.0, seed=0)

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


if __name__ == "__main__":
    main()
