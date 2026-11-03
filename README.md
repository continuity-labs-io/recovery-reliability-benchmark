# recovery-reliability-benchmark
[![test](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml/badge.svg)](https://github.com/continuity-labs-io/recovery-reliability-benchmark/actions/workflows/test.yml)

A public benchmark testing whether recovery kinetics after a standardized conditioning load are reliable enough to serve as a functional endpoint.

## Quickstart

```bash
pip install -e .
rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0
```

The first line of output is the conformance level (`conforming` or `fully_conforming`). Passing `--json` produces a shareable report containing the verdict, counts, and SHA-256 digests of the inputs; no data leaves the machine. You can also run `python -m recovery_reliability_benchmark.contract` as the equivalent without the console script.

## Licensing

Copyright 2026 Continuity Labs / Ryan J. McCall.

Unless otherwise noted, all code, tests, and configuration in this repository (including `src/` and `tests/`) are licensed under the Apache License, Version 2.0; see [LICENSE](LICENSE). The specification and documentation files ([README.md](README.md), [SPEC.md](SPEC.md), [CONTRIBUTING.md](CONTRIBUTING.md), and [METHOD.md](METHOD.md)) are licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).
