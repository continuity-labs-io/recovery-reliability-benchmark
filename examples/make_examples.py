"""Generate example CSV tables for the Recovery Reliability Benchmark."""

from __future__ import annotations

from pathlib import Path

from recovery_reliability_benchmark.synthetic import make_tables


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    units, responses = make_tables(n_units=15, n_trials=20, seed=0)
    units.to_csv(examples_dir / "units.csv", index=False)
    responses.to_csv(examples_dir / "responses.csv", index=False)


if __name__ == "__main__":
    main()
