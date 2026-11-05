# recovery-reliability-benchmark
[![test](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml/badge.svg)](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml)

## Status

v0.1.0: conformance checking and reliability ceilings on per-trial measures, validated on synthetic data. Reproduction of the pilot dataset and PSTH-based recovery measures follow in v0.2.0.

A public benchmark testing whether recovery kinetics after a standardized conditioning load are reliable enough to serve as a functional endpoint.

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported.

## What is being benchmarked

A benchmark normally holds the data fixed and varies the method. This one is the other way around: the computation is fixed and every lab brings different data, which makes it closer to an inter-laboratory ring trial than to an ImageNet-style benchmark.

What gets scored is the measures. A recovery measure (a time constant, an amplitude, a fraction recovered) receives a reliability ceiling on each contributed dataset, and the output is which measures hold up and where. The contributed datasets are the test set. [SPEC.md](SPEC.md) defines what makes a dataset admissible to that test set, the same way ImageNet defines what counts as a labeled image; without it, a result on one dataset and a result on another are not comparable.

Today the repository checks admissibility (`rrb-check`) and describes the conditioning load ([protocol.py](src/recovery_reliability_benchmark/protocol.py)). The ceiling computation ([METHOD.md](METHOD.md)) and the ability to submit a new measure and have it scored against the corpus come next.

A conforming dataset contributes rows to a public atlas. A row is keyed by (protocol fingerprint, condition, preparation): the commanded load, the condition label with its pharmacology, and the specimen. Reliability is computed per row set, and rows accumulate across laboratories. Contributed datasets are released into the public domain under CC0; see [CONTRIBUTING.md](CONTRIBUTING.md).

## Quickstart

```bash
# With uv:
uv sync && source .venv/bin/activate

# Or with standard Python venv:
python3 -m venv .venv && source .venv/bin/activate && pip install -e .

# minimal contract conformance check
rrb-check examples/units.csv examples/responses.csv \
--measures tau,amplitude \
--post-stim-window-s 2.0

# contract conformance check with sidecars
rrb-check examples/units.csv examples/responses.csv \
--measures tau,amplitude \
--post-stim-window-s 2.0 \
--preparation examples/preparation.json \
--conditions examples/conditions.json

# within-session reliability ceiling evaluator
rrb-evaluate examples/units.csv examples/responses.csv \
--measures tau,amplitude \
--post-stim-window-s 2.0

# threshold simulation across MD-2/MD-3 grid (writes output/thresholds.md and .json)
rrb-thresholds --fast --out output/thresholds
```

The first line of output is the conformance level (`conforming` or `fully_conforming`). The example data are synthetic with a true reliability of 0.8; the reported ceiling and its interval should bracket it. Passing `--json` produces a shareable report containing the verdict, counts, and SHA-256 digests of the inputs; no data leaves the machine. You can also run `python -m recovery_reliability_benchmark.contract` as the equivalent without the console script.

## Repository layout

- `src/recovery_reliability_benchmark/contract.py` — Conformance checker for `units.csv`, `responses.csv`, and optional sidecars (`rrb-check`).
- `src/recovery_reliability_benchmark/protocol.py` — Stimulation-protocol hierarchy (`Pulse`, `Burst`, `Train`, `Protocol`) and SHA-256 fingerprinting.
- `src/recovery_reliability_benchmark/metadata.py` — Pydantic schemas and loaders for `preparation.json` and `conditions.json` sidecars.
- `src/recovery_reliability_benchmark/synthetic.py` — Synthetic dataset generator with configurable single-session reliability and condition offsets.
- `src/recovery_reliability_benchmark/evaluate.py` — Odd/even split-half reliability ceiling, Fisher-z interval, permutation null, and positive control (`rrb-evaluate`).
- `src/recovery_reliability_benchmark/thresholds.py` — Monte Carlo simulation of the reliability ceiling across MD-2/MD-3 thresholds (`rrb-thresholds`).
- `examples/` — Conforming synthetic example tables (`units.csv`, `responses.csv`), metadata sidecars (`preparation.json`, `conditions.json`), and generator script.
- `scripts/` — CLI wrapper script (`scripts/thresholds.py`) for regenerating threshold simulation outputs.
- `docs/` — Maintainer terms (`docs/terms.md`) and generated threshold simulation tables (`docs/thresholds.md`, `docs/thresholds.json`).
- [SPEC.md](SPEC.md) — Normative dataset conformance specification (v1.0).
- [METHOD.md](METHOD.md) — Normative within-session reliability ceiling method and positive control specification.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Normative dataset contribution workflow, CC0 data licensing, and withdrawal terms.
- [docs/terms.md](docs/terms.md) — Normative maintainer position, paid-engagement derived-data clause, and archive governance.

## Citing

If you use this benchmark, please cite it using the metadata in [CITATION.cff](CITATION.cff).

## Licensing

Copyright 2026 Continuity Labs / Ryan J. McCall.

Unless otherwise noted, all code, tests, and configuration in this repository (including `src/` and `tests/`) are licensed under the Apache License, Version 2.0; see [LICENSE](LICENSE). The specification and documentation files ([README.md](README.md), [SPEC.md](SPEC.md), [CONTRIBUTING.md](CONTRIBUTING.md), [METHOD.md](METHOD.md), and [docs/terms.md](docs/terms.md)) are licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS). Contributed datasets are released under CC0 1.0; see DATA_LICENSE and CONTRIBUTING.md §5. Continuity Labs' position as maintainer is in docs/terms.md.
