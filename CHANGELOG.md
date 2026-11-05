# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

### Added

- Scope: v0.x covers neural preparations only.
- Atlas framing: a dataset contributes rows keyed by (protocol fingerprint, condition, preparation).
- Optional sidecars preparation.json, conditions.json and spikes.csv are validated when provided; fate.csv is defined.
- Data license: contributed datasets are accepted under CC0 1.0 only (DATA_LICENSE, CONTRIBUTING.md §5); report-then-deposit sequence and withdrawal terms updated to match.
- docs/terms.md: maintainer position, paid-engagement derived-data clause, governance intent.
- Ceiling reports a Fisher-z interval (n_eff = units) and single-trial / 20-trial standardized reliabilities.
- docs/thresholds.md: simulated sampling distribution of the estimate at the MD-2/MD-3 thresholds; SPEC.md §4 and §5 cite it.
