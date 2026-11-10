Task: wire the spikes path into run.run and rrb-evaluate. Frozen functions unchanged; run.py and
cli.py are open layer. 300-line limit, Google docstrings, no A/B names, no version bump.

1. spikes.py: per_trial_counts_table(units, trials, spikes, params) -> DataFrame with columns
   unit_id, trial_index, stim_time_ns, condition, spike_count (int): one row per unit and trial,
   spike_count = len(latency array) from trial_latencies. This is the table the frozen contract
   validates on the spikes path.

2. run.run gains analysis: AnalysisParams | None = None. When analysis is not None (spikes required,
   else ValueError "analysis requires spikes"):
   - post_stim_window_s and load_duration_s come from analysis; if the caller also passed values that
     differ, raise ValueError naming both numbers.
   - trials = spikes.trial_table(responses); counts = spikes.per_trial_counts_table(...).
   - val = validate(units, counts, ["spike_count"], post_stim_window_s, load_duration_s, preparation,
     conditions, spikes). Unchanged frozen contract on the constructed table.
   - checks_spikes.check_pre_stimulus_window(trials, analysis, load_duration_s).
   - halves, flags = spikes.halves_from_spikes(units, trials restricted to val["evaluated_conditions"],
     spikes, analysis, measures); scored = spikes.scored_units(halves, measures);
     checks_spikes.check_scored_units(scored, c) for every evaluated condition; drop rows whose unit is
     not scored in its condition.
   - Then the existing per-measure loop on halves, unchanged, except variance is None for every
     measure and condition on this path (per-half measures have no per-trial values).
   - Result additions: parameters["path"] = "spikes" (tables path: "responses"),
     parameters["analysis"] = analysis.to_dict(), parameters["analysis_fingerprint"];
     inclusion["spikes_path"] = {"rule": "A unit is scored in a condition when every requested measure
     is computed in both halves.", "per_condition": {c: {"n_units_in_tables", "n_units_scored",
     "n_units_excluded_by_rule"}}}; per measure, "flags": {c: {flag: count of units with that flag set
     in either half}}.
   - Factor the shared per-measure loop into one private function used by both paths so the tables
     path's behavior is byte-identical (existing tests prove it).

3. cli.py: rrb-evaluate gains --analysis PATH (metadata.load_analysis). Requires --spikes, else exit 2
   with "--analysis requires --spikes". If --post-stim-window-s or --load-duration-s is also given and
   differs from analysis.json, exit 2 naming both. Human output adds a line "path: spikes, analysis
   <first 12 hex of fingerprint>", one line per evaluated condition "units scored <n> of <n_in_tables>",
   and per measure the censored counts when nonzero ("t_return censored in 3 units"). JSON output
   carries the result dict as is. rrb-check gains --analysis too: validates the counts table, runs
   min-dataset-7, and reports pre_stim_window_s and the analysis fingerprint in its result.

4. examples/: make_examples.py also writes examples/spikes.csv and examples/analysis.json from
   synthetic.make_spike_trains: 30 units, 20 trials, isi 5 s, baseline 5 Hz, peak 100 Hz, taus
   log-spaced 0.05 to 0.5 s, seed 0; responses.csv for this example is the trial table with no measure
   columns, written as examples/trials_responses.csv so the existing tables example is untouched.
   .github/workflows/test.yml adds: rrb-check and rrb-evaluate on the spikes example with --measures
   t_return,t_half_peak,peak_rate,spikes_per_trial.

5. Docs. README: a "From spikes" subsection with the two commands and the three files they need.
   SPEC: an "Evaluating from spikes" paragraph: responses.csv carries the trial columns, measure
   columns are ignored, the benchmark computes measures per half from spikes.csv under analysis.json,
   min-dataset-7 applies. METHOD §2: one paragraph on per-half measures and why (the spike-count
   argument). GLOSSARY "Spikes path" updated with the CLI flags. CHANGELOG Unreleased: "rrb-evaluate
   --spikes --analysis: measures computed per half from spike times; spikes-path inclusion reported."

6. Tests, tests/test_run_spikes.py:
   - test_spikes_path_matches_tables_for_counts: 30 units, 20 trials from make_spike_trains; run on
     the spikes path with measures ["spikes_per_trial"] versus run on the tables path with the
     per_trial_counts_table renamed to spikes_per_trial: identical headline rho to 1e-9 and identical
     n_units.
   - test_spikes_path_reports: parameters.path == "spikes", analysis_fingerprint ==
     AnalysisParams.fingerprint(), inclusion.spikes_path.per_condition present, flags present,
     variance is None.
   - test_t_return_reliability_bounds: taus log-spaced 0.05 to 0.5 across 30 units -> headline rho
     for t_return > 0.9; all taus 0.2 -> rho < 0.3.
   - test_md7_from_run: first onset at 0.5 s -> ContractViolation with requirement MD7.
   - test_md3_scored_from_run: 10 units, 4 silent -> ContractViolation MD3 whose message contains
     "computed in both halves".
   - test_tables_path_unchanged: run on make_tables(n_units=30, n_trials=20, reliability=0.8) gives
     the same headline rho as before this change (pin the value from the current main first).
   tests/test_cli.py: rrb-evaluate --spikes --analysis --json on the written example exits 0 with
   parameters.path == "spikes"; --analysis without --spikes exits 2; a mismatched --post-stim-window-s
   exits 2; rrb-check --analysis exits 0 and reports pre_stim_window_s.

Run the full suite and ruff. Report: the counts-equivalence rho from both paths, the t_return rho for
spread and identical taus, and the suite count.
