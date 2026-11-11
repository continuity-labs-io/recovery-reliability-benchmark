# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## Unreleased

## [0.2.0] - 2026-11-10

- Specification and contribution wording (`SPEC.md`, `GLOSSARY.md`, `METHOD.md`, `CONTRIBUTING.md`): the sidecars (`preparation.json`, `conditions.json`) and `spikes.csv` are optional for conformance and required for an atlas contribution (with `spikes.csv` required on the spikes path and for spike-recording modalities); the 0.1.0 text said they would be required from 0.2.0, which the checker did not enforce.
- Axis-specific report wording (`report_notes.py`, `summary.py`, `text_report.py`, `report.py`, `run.py`): diagnostic notes come from `report_notes.row_notes` (`no variation across units`, `reliability at chance`, `sensitivity at chance`, `does not beat reference`), undefined reliability renders as `undefined` (`n/a` interval) in `summary.md`, `beats_reference` is `null` when `baseline_hz` is requested as a measure, the positive-control line states `(split-half estimator on a synthetic table)`, and `summary.md` notes when `halves.png` shows the first 4 of more than 4 measures.
- Strict JSON output and report-folder cleanup: `--json` and `evaluate.json` write non-finite floats as `null` (`allow_nan=False`, with `r_undefined` marking undefined correlations), the all-`NaN` slice warning in the undefined-correlation permutation null is silenced at the call site, and `rrb-report` clears previous `evaluate.json`, `summary.md`, and `halves.png` files at the start of each run.
- CLI and API input validation: undecodable integer columns in responses or spikes CSVs, a non-positive `--n-perm`, and an unknown spikes-path measure exit 2 with a one-line error on stderr (`ValueError` in the Python API).
- Frozen: check_identifiers rejects a null condition under SCHEMA (it crashed before).
- Frozen: new checks_spikes.check_spikes_path_tables and checks_spikes.check_spikes_in_windows run before spikes are counted, so a missing column, a null, an inconsistent trial or a clock mismatch gives a contract violation instead of a traceback; check_scored_units takes one argument order.
- Frozen: recovery_measures returns NaN for t_peak and t_half_peak when no spike falls in any bin (peak_rate stays 0.0), so a silent unit is not scored for a peak time.
- Frozen: AnalysisParams gains artifact_blank_s (default 0.003 s); trial_latencies keeps latencies in [artifact_blank_s, post_stim_window_s); excess_measures counts over post_stim_window_s - artifact_blank_s; DEFAULT_ANALYSIS_FINGERPRINT_2S changes with the new field.
- Frozen: excess_measures takes per-trial pre-stimulus counts and gates t_half_excess on the trial-to-trial spread of per-trial excess (sum(d) > min_excess_z * sqrt(n) * sd(d)) instead of sqrt(N); unit_measures passes the counts.
- Frozen: check_pre_stimulus_window requires the pre-stimulus window to start after the previous trial's post-stimulus window (onsets at least load + post + pre apart).
- Frozen: SPEC_VERSION 1.0 -> 1.1
- Frozen: analysis.py (`AnalysisParams.to_dict`, `AnalysisParams.fingerprint`, `AnalysisParams.effective_edges`, `DEFAULT_ANALYSIS_FINGERPRINT_2S`) joined the frozen layer at 0.2.0.
- Frozen: measures.py (`trial_latencies`, `pre_counts`, `baseline_hz`, `baseline_variance_hz2`, `bin_counts`, `psth_rate`, `recovery_measures`, `unit_measures`) joined the frozen layer at 0.2.0.
- Frozen: excess.py (`excess_measures`) joined the frozen layer at 0.2.0.
- Frozen: spikes.py (`trial_table`, `split_trials`, `halves_from_spikes`, `scored_units`, `per_trial_counts_table`) joined the frozen layer at 0.2.0.
- Frozen: checks_spikes.py (`check_pre_stimulus_window`, `check_scored_units`) joined the frozen layer at 0.2.0.
- Frozen: sensitivity.py (`_shift_and_z`, `condition_sensitivity`, `measure_sensitivity`, `NOISE_FLOOR`) joined the frozen layer at 0.2.0.
- Frozen: contract.py (`MD7_MUST`, `SPEC_VERSION`) joined the frozen layer at 0.2.0.
- Frozen: inputs.py (`SPIKES_REFERENCE_MEASURE`, `SPIKES_INCLUSION_RULE`) joined the frozen layer at 0.2.0.
- Docs for the spikes path: measures table, what conformance guarantees, split-half on pooled measures.
- writer.py: reference dataset writer (write_dataset, read_dataset) and scripts/adapter_template.py.
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
