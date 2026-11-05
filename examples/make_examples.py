"""Generate example CSV tables and metadata sidecars for the Recovery Reliability Benchmark."""

from __future__ import annotations

import json
from pathlib import Path

from recovery_reliability_benchmark.metadata import Condition, Preparation
from recovery_reliability_benchmark.protocol import Protocol
from recovery_reliability_benchmark.synthetic import make_tables


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


if __name__ == "__main__":
    main()
