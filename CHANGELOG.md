# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

- rrb-report: evaluate.json, summary.md and a figure from one command; two-condition example.
- Sensitivity axis between condition pairs, with a shuffled null; reported for every measure and the reference row.
- spikes path: baseline firing rate reported as a reference row.
- excess.py: bin-free recovery measures t_half_excess and excess_per_trial.
- spikes path: inclusion is per measure; a measure with too few scored units is reported as not scored.
- rrb-evaluate --spikes --analysis: measures computed per half from spike times; spikes-path inclusion reported.
- spikes.py: per-half measures from spikes in the evaluator's halves format; min-dataset-7 pre-stimulus window requirement; analysis.json loader. Not yet wired into rrb-evaluate.
- Zenodo DOIs recorded: concept 10.5281/zenodo.24020731, v0.1.0 10.5281/zenodo.24020732.
- measures.py: PSTH recovery measures from spike times (t_peak, peak_rate, t_half_peak, t_return, residual, overshoot, baseline variance), pure functions; synthetic spike-train generator; not yet wired into rrb-evaluate.
- measures: bin edges never end in a sliver bin; overshoot is the pooled deficit after return.
- freeze --update: the Frozen: line is required only when a frozen item changed.

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
