Task: prepare release 0.2.0. Register the new frozen items, bump versions, run the ceremony. No logic
changes.

1. Register as frozen, with decorators or register(), every file staying under 300 lines:
   - analysis.py: AnalysisParams.to_dict, AnalysisParams.fingerprint, AnalysisParams.effective_edges
     ("SPEC analysis parameters"). New module constant DEFAULT_ANALYSIS_FINGERPRINT_2S =
     AnalysisParams(post_stim_window_s=2.0).fingerprint(), registered with freeze_constant, so any
     change to a default or to the bin edges changes a frozen value.
   - measures.py: trial_latencies, pre_counts, baseline_hz, baseline_variance_hz2, bin_counts,
     psth_rate, recovery_measures, unit_measures ("SPEC measures computed by the benchmark").
   - excess.py: excess_measures (same reference).
   - spikes.py: trial_table, split_trials, halves_from_spikes, scored_units, per_trial_counts_table
     ("METHOD split-half on pooled measures").
   - checks_spikes.py: check_pre_stimulus_window ("SPEC min-dataset-7"), check_scored_units
     ("SPEC min-dataset-3").
   - sensitivity.py: _shift_and_z, condition_sensitivity, measure_sensitivity ("METHOD sensitivity");
     constant NOISE_FLOOR.
   - contract.py: constants MD7_MUST ("SPEC min-dataset-7") and SPEC_VERSION ("SPEC version").
   - inputs.py: constants SPIKES_REFERENCE_MEASURE and SPIKES_INCLUSION_RULE.
   Not frozen: inputs.from_spikes, inputs.from_responses, run.py, cli.py, text_report.py, summary.py,
   report.py, writer.py, metadata.py, the spike-train generators.

2. SPEC_VERSION becomes "1.1": min-dataset-7 and the spikes path are additions to the spec. SPEC.md
   states its version and lists what 1.1 added. Update tests and docs that print "SPEC v1.0".

3. Version 0.2.0 in pyproject.toml and CITATION.cff, date-released today. CHANGELOG: Unreleased
   becomes [0.2.0] with today's date; under it one "Frozen:" line per group in item 1 saying it joined
   the frozen layer at 0.2.0, and "Frozen: SPEC_VERSION 1.0 -> 1.1". The fingerprint pinned in the
   tests equals DEFAULT_ANALYSIS_FINGERPRINT_2S.

4. FROZEN.md: every new name in the table with its reference; "what is not frozen" updated.

5. Run python scripts/freeze.py --update, then the full suite, ruff and scripts/freeze.py --check.
   Then prove the guardrail on a new item: change one character of logic in excess.excess_measures,
   confirm test_snapshots_match fails with the diff, revert, confirm green.

6. Regenerate the README example table if the version or SPEC string appears in it.

Report: the count of frozen functions and constants before and after, the --update output, the
guardrail proof, and the suite count. Do not create the tag.
