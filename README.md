# recovery-reliability-benchmark
[![test](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml/badge.svg)](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml)
[![DOI](https://zenodo.org/badge/1444426702.svg)](https://doi.org/10.5281/zenodo.24020731)

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

# threshold simulation across min-dataset-2/min-dataset-3 grid (writes output/thresholds.md and .json)
rrb-thresholds --fast --out output/thresholds
```

The first line of output is the conformance level (`conforming` or `fully_conforming`). The example data are synthetic with a true reliability of 0.8; the reported ceiling and its interval should bracket it. Passing `--json` produces a shareable report containing the verdict, counts, and SHA-256 digests of the inputs; no data leaves the machine. You can also run `python -m recovery_reliability_benchmark.contract` as the equivalent without the console script.

### From spikes

When the benchmark computes recovery measures directly from spike timestamps, pass the three tables (`units.csv`, `trials_responses.csv` carrying the trial columns, and `spikes.csv`) together with `analysis.json`:

```bash
# contract conformance check on the spikes path (includes min-dataset-7)
rrb-check examples/units.csv examples/trials_responses.csv \
--spikes examples/spikes.csv \
--analysis examples/analysis.json \
--measures t_half_excess,excess_per_trial,spikes_per_trial

# within-session reliability ceiling evaluator from spikes
rrb-evaluate examples/units.csv examples/trials_responses.csv \
--spikes examples/spikes.csv \
--analysis examples/analysis.json \
--measures t_half_excess,excess_per_trial,spikes_per_trial
```

Sample summary lines from `rrb-evaluate` on the spikes example (including the always-computed `baseline_hz` reference row):

```text
t_half_excess: rho=0.954 ci=[0.901, 0.979] rho_at_20=0.954 (per_condition; r_half=0.912, n_units=29, n_pairs=29) null_p95_rho=0.472
excess_per_trial: rho=0.978 ci=[0.953, 0.989] rho_at_20=0.978 (per_condition; r_half=0.956, n_units=30, n_pairs=30) null_p95_rho=0.467
spikes_per_trial: rho=0.993 ci=[0.985, 0.997] rho_at_20=0.993 (per_condition; r_half=0.986, n_units=30, n_pairs=30) null_p95_rho=0.456
reference (baseline_hz): rho=0.991 ci=[0.980, 0.996] n_units=30
```

## One command

`rrb-report` writes `evaluate.json`, `summary.md`, and `halves.png` (install with `pip install -e ".[report]"` for the figure) from one invocation:

```bash
rrb-report examples/two_conditions/units.csv examples/two_conditions/trials_responses.csv \
  --spikes examples/two_conditions/spikes.csv \
  --analysis examples/two_conditions/analysis.json \
  --conditions examples/two_conditions/conditions.json \
  --measures t_half_excess,excess_per_trial,t_return \
  --out report/two_conditions
```

Two-axis table from the generated `summary.md`:

| Measure | Reliability | 95% interval | Shuffled null p95 | Units | Sensitivity, median z | Sensitivity null p95 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| t_half_excess | 0.976 | [0.950, 0.989] | 0.384 | 30 | 3.08 | 1.05 | — |
| excess_per_trial | 0.987 | [0.972, 0.994] | 0.362 | 30 | 3.61 | 1.10 | — |
| t_return | 0.731 | [0.428, 0.874] | 0.357 | 30 | 1.00 | 1.07 | at chance; censored: control 8, slowed 11 |
| baseline_hz (reference) | 0.989 | [0.977, 0.995] | 0.350 | 30 | 0.59 | 1.13 | at chance |

## Repository layout

- `src/recovery_reliability_benchmark/contract.py` — Conformance checker for `units.csv`, `responses.csv`, and optional sidecars (`rrb-check`).
- `src/recovery_reliability_benchmark/protocol.py` — Stimulation-protocol hierarchy (`Pulse`, `Burst`, `Train`, `Protocol`) and SHA-256 fingerprinting.
- `src/recovery_reliability_benchmark/metadata.py` — Pydantic schemas and loaders for `preparation.json` and `conditions.json` sidecars.
- `src/recovery_reliability_benchmark/synthetic.py` — Synthetic dataset generator with configurable single-session reliability and condition offsets.
- `src/recovery_reliability_benchmark/evaluate.py` — Odd/even split-half reliability ceiling (`split_halves`, `reliability_ceiling`), Fisher-z interval, permutation null, and positive control (`rrb-evaluate`).
- `src/recovery_reliability_benchmark/report.py` — One-command report folder writer (`rrb-report`) producing `evaluate.json`, `summary.md` (`summary.py`), and `halves.png`.
- `src/recovery_reliability_benchmark/thresholds.py` — Monte Carlo simulation of the reliability ceiling across min-dataset-2/min-dataset-3 thresholds (`rrb-thresholds`).
- `examples/` — Conforming synthetic example tables (`units.csv`, `responses.csv`), metadata sidecars (`preparation.json`, `conditions.json`), and generator script.
- `scripts/` — CLI wrapper script (`scripts/thresholds.py`) for regenerating threshold simulation outputs.
- `docs/` — Maintainer terms (`docs/terms.md`) and generated threshold simulation tables (`docs/thresholds.md`, `docs/thresholds.json`).
- [SPEC.md](SPEC.md) — Normative dataset conformance specification (v1.0).
- [METHOD.md](METHOD.md) — Normative within-session reliability ceiling method and positive control specification.
- [GLOSSARY.md](GLOSSARY.md) — Plain-language definitions of experimental, computational, conformance, and protocol-schema terms.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Normative dataset contribution workflow, CC0 data licensing, and withdrawal terms.
- [docs/terms.md](docs/terms.md) — Normative maintainer position, paid-engagement derived-data clause, and archive governance.

## Citing

Every release is archived on Zenodo. Cite the version you used. The version DOI for v0.1.0 is [10.5281/zenodo.24020732](https://doi.org/10.5281/zenodo.24020732); [10.5281/zenodo.24020731](https://doi.org/10.5281/zenodo.24020731) always resolves to the latest release. Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button renders it.

> McCall, R. J. (2026). Recovery Reliability Benchmark (v0.1.0). Continuity Labs. https://doi.org/10.5281/zenodo.24020732

## Licensing

Copyright 2026 Continuity Labs / Ryan J. McCall.

Unless otherwise noted, all code, tests, and configuration in this repository (including `src/` and `tests/`) are licensed under the Apache License, Version 2.0; see [LICENSE](LICENSE). The specification and documentation files ([README.md](README.md), [SPEC.md](SPEC.md), [CONTRIBUTING.md](CONTRIBUTING.md), [METHOD.md](METHOD.md), [GLOSSARY.md](GLOSSARY.md), and [docs/terms.md](docs/terms.md)) are licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS). Contributed datasets are released under CC0 1.0; see DATA_LICENSE and CONTRIBUTING.md §5. Continuity Labs' position as maintainer is in docs/terms.md.
