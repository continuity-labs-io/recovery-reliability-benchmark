# recovery-reliability-benchmark
[![test](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml/badge.svg)](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml)
[![DOI](https://zenodo.org/badge/1444426702.svg)](https://doi.org/10.5281/zenodo.24020731)

A public benchmark testing whether recovery kinetics after a standardized conditioning load are reliable enough to serve as a functional endpoint. The computation is fixed while every laboratory brings its own recordings, and conforming datasets contribute rows keyed by (protocol fingerprint, condition, preparation) to a public atlas.

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported.

## Run the example

```bash
pip install -e ".[report]"

rrb-report examples/two_conditions/units.csv examples/two_conditions/trials_responses.csv \
  --spikes examples/two_conditions/spikes.csv \
  --analysis examples/two_conditions/analysis.json \
  --conditions examples/two_conditions/conditions.json \
  --measures t_half_excess,excess_per_trial,t_return \
  --out report/two_conditions
```

`rrb-report` writes `evaluate.json`, `summary.md`, and `halves.png` into `report/two_conditions/`. Two-axis table from `summary.md`:

| Measure | Reliability | 95% interval | Shuffled null p95 | Units | Sensitivity, median z | Sensitivity null p95 | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| t_half_excess | 0.975 | [0.946, 0.988] | 0.371 | 29 | 3.27 | 1.09 | — |
| excess_per_trial | 0.987 | [0.972, 0.994] | 0.363 | 30 | 3.88 | 1.10 | — |
| t_return | 0.731 | [0.428, 0.874] | 0.357 | 30 | 1.00 | 1.07 | at chance; censored: control 8, slowed 11 |
| baseline_hz (reference) | 0.989 | [0.977, 0.995] | 0.350 | 30 | 0.59 | 1.13 | at chance |

The `Reliability` column is the within-session split-half ceiling across units: how reproducibly the measure orders units from one half of the session's trials to the other, alongside its 95% interval and shuffled-unit null. The `Sensitivity, median z` column is how many multiples of its own split-half noise the typical unit shifts between `control` and `slowed`, alongside a shuffled-condition null. The reference row is baseline firing rate (`baseline_hz`), the most repeatable number in the report, and it does not move when recovery slows.

## Run it on your recordings

A laboratory provides three things on a shared recording clock: spike times per unit, stimulus onset times, and a condition label per stimulus. Copy [`scripts/adapter_template.py`](scripts/adapter_template.py) and fill in `load_recording(path)` to extract those arrays and pass them to `writer.write_dataset`, which writes `units.csv`, `trials_responses.csv`, `spikes.csv`, and `analysis.json`.

The protocol asks for at least 2.0 s of recording after each stimulus (`min-dataset-6`), at least 1.0 s of quiet before each stimulus (`min-dataset-7`, so stimulus onsets must be at least 3.0 s apart, plus the load duration), 20 trials per condition recommended (10 minimum, `min-dataset-2`), and 30 units recommended (8 minimum, `min-dataset-3`). Check conformance first, then generate the report:

```bash
rrb-check dataset/units.csv dataset/trials_responses.csv \
  --spikes dataset/spikes.csv \
  --analysis dataset/analysis.json

rrb-report dataset/units.csv dataset/trials_responses.csv \
  --spikes dataset/spikes.csv \
  --analysis dataset/analysis.json \
  --measures t_half_excess,excess_per_trial \
  --out dataset/report
```

Nothing leaves your machine.

## If you only have per-trial numbers

When spike timestamps are unavailable and you already have scalar per-trial measure columns in `responses.csv`, run the tables path directly on `units.csv` and `responses.csv` (without the `baseline_hz` reference row, which requires spikes):

```bash
rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0
rrb-report examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0 --out report/tables
```

## What the report does not say

Reliability is not validity: a high within-session ceiling shows that a measure reproduces unit differences across halves of one session, not that it repeats across days or tracks a mechanism. Nothing here measures age or tissue health. Conformance checks that a dataset supports the computation rather than grading the recording, so a conforming dataset can still score low.

## Documentation

- [SPEC.md](SPEC.md) — Normative dataset conformance specification, reference file layout, and benchmark measures.
- [METHOD.md](METHOD.md) — Within-session split-half reliability ceiling, between-condition sensitivity, and controls.
- [GLOSSARY.md](GLOSSARY.md) — Plain-language definitions of experimental, computational, conformance, and protocol terms.
- [FROZEN](frozen/README.md) — Frozen-layer manifest, AST snapshots, and change governance.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Dataset contribution workflow, adapter guide, CC0 data licensing, and withdrawal terms.
- [docs/terms.md](docs/terms.md) — Maintainer position, paid-engagement derived-data clause, and archive governance.

## Citing

Every release is archived on Zenodo. Cite the version you used. The version DOI for v0.1.0 is [10.5281/zenodo.24020732](https://doi.org/10.5281/zenodo.24020732); [10.5281/zenodo.24020731](https://doi.org/10.5281/zenodo.24020731) always resolves to the latest release. Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button renders it.

> McCall, R. J. (2026). Recovery Reliability Benchmark (v0.1.0). Continuity Labs. https://doi.org/10.5281/zenodo.24020732

## Licensing

Copyright 2026 Continuity Labs / Ryan J. McCall.

Unless otherwise noted, all code, tests, and configuration in this repository (including `src/` and `tests/`) are licensed under the Apache License, Version 2.0; see [LICENSE](LICENSE). The specification and documentation files ([README.md](README.md), [SPEC.md](SPEC.md), [CONTRIBUTING.md](CONTRIBUTING.md), [METHOD.md](METHOD.md), [GLOSSARY.md](GLOSSARY.md), [frozen/README.md](frozen/README.md), and [docs/terms.md](docs/terms.md)) are licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS). Contributed datasets are released under CC0 1.0; see DATA_LICENSE and CONTRIBUTING.md §5. Continuity Labs' position as maintainer is in docs/terms.md.
