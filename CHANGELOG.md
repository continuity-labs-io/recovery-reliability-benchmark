# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

- Zenodo DOIs recorded: concept 10.5281/zenodo.24020731, v0.1.0 10.5281/zenodo.24020732.
- measures.py: PSTH recovery measures from spike times (t_peak, peak_rate, t_half_peak, t_return, residual, overshoot, baseline variance), pure functions; synthetic spike-train generator; not yet wired into rrb-evaluate.

## [0.1.0] - 2026-11-06

Scope of this release: conformance checking and reliability ceilings on per-trial measures, validated on synthetic data. Pilot reproduction and PSTH measures follow in 0.2.0.

### Added

- Scope: v0.x covers neural preparations only.
- Atlas framing: a dataset contributes rows keyed by (protocol fingerprint, condition, preparation).
- Optional sidecars preparation.json, conditions.json and spikes.csv are validated when provided; fate.csv is defined.
- Data license: contributed datasets are accepted under CC0 1.0 only (DATA_LICENSE, CONTRIBUTING.md §5); report-then-deposit sequence and withdrawal terms updated to match.
- docs/terms.md: maintainer position, paid-engagement derived-data clause, governance intent.
- Ceiling reports a Fisher-z interval (n_eff = units) and single-trial / 20-trial standardized reliabilities.
- docs/thresholds.md: simulated sampling distribution of the estimate at the min-dataset-2/min-dataset-3 thresholds; SPEC.md §4 and §5 cite it.
- GLOSSARY.md added.
- Inclusion rule made explicit and applied identically by rrb-check and rrb-evaluate; inclusion counts and contributor-declared exclusions reported.
- Variance components reported next to each ceiling.
- METHOD.md: 'How this benchmark can be gamed' section; CONTRIBUTING.md: measure-submission rule.

### Changed

- min-dataset-3 SHOULD raised from 15 to 30 units before the v1.0 spec is tagged, on the basis of docs/thresholds.md.
- Optional dataset items renamed OD-N to optional-dataset-N to match min-dataset-N.
- Modules split under a 300-line rule: checks.py, controls.py, run.py, cli.py; ceiling renamed reliability_ceiling; halves named odd/even; Fisher interval and permutation null pinned to SciPy in tests; code guidelines in CONTRIBUTING.md.
