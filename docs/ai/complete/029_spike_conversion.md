Task: add the module that turns spikes into the halves frame the evaluator already consumes, plus
analysis.json loading and the pre-stimulus window requirement. No change to any frozen function, no
CLI or run.py changes (next prompt), no version bump. One new module per concern. 300-line limit,
Google docstrings, no A/B names.

1. measures.py: unit_measures adds values["spikes_per_trial"] = mean over trials of the spike count in
   the post-stimulus window (sum of bin_counts per trial, averaged). Never NaN when there is at least
   one trial.

2. metadata.py: load_analysis(path) -> AnalysisParams. Reads JSON, builds AnalysisParams.from_dict;
   a missing file, malformed JSON, unknown key or ValueError from AnalysisParams raises
   ContractViolation(Requirement.SCHEMA, ...) in the style of load_preparation. write_analysis(params,
   path) writes to_dict() as indented JSON.

3. New module spikes.py, pure functions, DataFrames in and out:
   - trial_table(responses) -> DataFrame: distinct (trial_index, stim_time_ns, condition) rows sorted
     by trial_index. A trial_index with more than one onset or condition raises ValueError naming it.
   - split_trials(trials, condition) -> tuple[np.ndarray, np.ndarray]: trial_index values of the odd
     and even halves, 1-based position within the condition after sorting by trial_index, odd positions
     first. Docstring: the same rule as evaluate.split_halves, enforced by test.
   - spike_times_by_unit(spikes) -> dict[str, np.ndarray]: unit_id -> sorted float seconds
     (spike_time_ns / 1e9). Units in units.csv with no spikes map to an empty array; the caller passes
     the unit list.
   - halves_from_spikes(units, trials, spikes, params, measures) -> tuple[DataFrame, DataFrame]:
     for every condition in trials and every unit in units, onsets_s = stim_time_ns / 1e9 for each
     half from split_trials; unit_measures on each half; first frame indexed (unit_id, condition) with
     columns {m}_odd, {m}_even for each requested measure plus n_odd, n_even (trial counts), same
     shape and dtypes as evaluate.split_halves output; second frame, same index, one boolean column
     per flag and half ({flag}_odd, {flag}_even). A requested measure not in unit_measures' keys
     raises ValueError listing the available names.
   - scored_units(halves, measures) -> dict[str, set[str]]: per condition, the units whose
     {m}_odd and {m}_even are non-NaN for every requested measure. Docstring: this is the inclusion
     rule on the spikes path, "a unit is scored in a condition when every requested measure is
     computed in both halves"; a silent unit has no baseline and is excluded.

4. New module checks_spikes.py:
   - contract.py gains Requirement.MD7 = "min-dataset-7" with description "Pre-stimulus window.
     Applies when measures are computed from spikes: the declared pre_stim_window_s is at least 1.0 s,
     fits before the first onset on the recording clock, and fits between every previous load end and
     the next onset." and the constant MD7_MUST = 1.0. Not registered as frozen in this prompt.
   - check_pre_stimulus_window(trials, params, load_duration_s) -> None: raises
     ContractViolation(Requirement.MD7, ...) with found and required in the existing message style:
     "Pre-stimulus window 0.5 s, requires 1.0 s."; "Pre-stimulus window 1.0 s does not fit before
     trial 0 at 0.500 s, requires onset >= 1.0 s."; "Trial 7 has 0.800 s between the previous load end
     and its onset, requires 1.0 s."
   - check_scored_units(scored, condition) -> None: raises ContractViolation(Requirement.MD3, ...)
     when len(scored[condition]) < contract.MD3_MUST: "6 units with every measure computed in both
     halves for condition 'A', requires 8." Uses the existing constant; no new threshold.

5. SPEC.md: a "min-dataset-7" subsection after min-dataset-6 with the description text above and one
   sentence on why (the baseline is read from the pre-stimulus window, and with the 2 s post-stimulus
   requirement a 1 s pre-window always fits except before the first trial). Add analysis.json to the
   file list: "Analysis parameters: the AnalysisParams fields; declared before the run; its fingerprint
   is printed in the report." Add the spikes-path inclusion sentence to "Inclusion and exclusion".
   GLOSSARY: entries for `spikes.trial_table`, `spikes.split_trials`, `spikes.halves_from_spikes`,
   `spikes.scored_units` (one entry "Spikes path"), "Scored unit", "min-dataset-7", `spikes_per_trial`,
   `analysis.json`. tests/test_style.py PACKAGE_MODULES += "spikes", "checks_spikes".
   CHANGELOG Unreleased: "spikes.py: per-half measures from spikes in the evaluator's halves format;
   min-dataset-7 pre-stimulus window requirement; analysis.json loader. Not yet wired into
   rrb-evaluate."

6. tests/test_spikes.py:
   - test_split_trials_matches_split_halves: make_tables(n_units=3, n_trials=11, conditions=("A","B"))
     with a measure column equal to trial_index; for each condition, split_halves' {m}_odd equals the
     mean of split_trials' odd indices and likewise even, for every unit.
   - test_trial_table_rejects_inconsistent_trial: two onsets for one trial_index -> ValueError naming
     the trial_index.
   - test_halves_shape: make_spike_trains for 5 units, 10 trials, one condition; trials built from
     the onsets; halves has 5 rows, columns t_return_odd, t_return_even, n_odd == 5, n_even == 5,
     index names ["unit_id", "condition"].
   - test_spikes_per_trial_matches_tables_path: same trains; build a responses table with per-trial
     spike counts using measures.trial_latencies; split_halves on it versus halves_from_spikes with
     measures ["spikes_per_trial"]: the odd and even columns are equal to 1e-12.
   - test_scored_units_excludes_silent_unit: add a unit with no spikes; with measures ["t_return"] it
     is excluded, with ["peak_rate"] it is included.
   - test_pre_window_violations: pre 0.5 -> MD7 with found 0.5, required 1.0; first onset 0.5 s with
     pre 1.0 -> MD7 naming trial 0; a trial with 0.8 s between previous load end and onset -> MD7
     naming that trial; onsets every 5 s with load 1.0 -> passes.
   - test_check_scored_units_md3: five scored units -> ContractViolation with requirement MD3 and
     "requires 8" in the message.
   - test_load_analysis(tmp_path): write_analysis then load_analysis round-trips; malformed JSON ->
     SCHEMA; unknown key -> SCHEMA.
   - test_docs: SPEC contains "min-dataset-7"; GLOSSARY contains "Scored unit".

Run the full suite and ruff. Report: line counts of the new modules, and the split-equivalence and
spikes-per-trial test results.
