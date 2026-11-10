Task: one writer for the benchmark's files, so every adapter and example produces the same layout.
New module writer.py. No frozen changes.

1. writer.py:
   write_dataset(out_dir, unit_ids, spike_times_s, onsets_s, conditions, analysis, *,
                 recording_id="rec0", session_id="sess0", preparation_id="prep0",
                 preparation=None, condition_metadata=None) -> dict[str, Path]
   - unit_ids: sequence of str. spike_times_s: mapping unit_id -> 1D array of spike times in seconds
     on the recording clock. onsets_s: 1D array of stimulus onsets in seconds. conditions: one label
     per onset. analysis: AnalysisParams. preparation: Preparation or None. condition_metadata:
     dict[str, Condition] or None.
   - Writes units.csv, trials_responses.csv (trial_index 0..n-1 in onset order, stim_time_ns,
     condition), spikes.csv (units in unit_ids order, times ascending), analysis.json, and
     preparation.json and conditions.json when given. Seconds become nanoseconds with
     int(round(t * 1e9)).
   - Raises ValueError naming the problem for: onsets not strictly increasing; len(conditions) !=
     len(onsets_s); a key of spike_times_s missing from unit_ids; duplicate unit ids; negative or
     non-finite times; condition_metadata keys that differ from the set of condition labels.
   - Does not check the contract; that is rrb-check's job.
   read_dataset(directory) -> tuple[units, trials, spikes, analysis].

2. examples/make_examples.py builds examples/two_conditions/ through write_dataset. The files stay
   byte-identical; if a byte differs, report the difference instead of accepting it. Other examples
   are untouched.

3. scripts/adapter_template.py, under 60 lines: one function to fill in,
   load_recording(path) -> (unit_ids, spike_times_s, onsets_s, conditions), and a main that calls
   write_dataset and prints the rrb-check and rrb-report commands to run next. Module docstring: the
   two things to read in a lab's format description before writing an adapter (at least 2 s of
   recording after each stimulus; at least 8 units), and "an adapter contains no analysis".

4. tests/test_writer.py: round trip on D(1.5, 0) (write into tmp_path; rrb-check exits 0; rrb-report
   exits 0; read_dataset returns what was written); one test per refusal; make_examples output for
   two_conditions is byte-identical to the committed files.

5. Docs: SPEC's file section names write_dataset as the reference writer. CONTRIBUTING gains "Writing
   an adapter". GLOSSARY: "Adapter", "Reference writer (`writer.write_dataset`)". PACKAGE_MODULES +=
   "writer". CHANGELOG Unreleased.

Run the full suite, ruff, scripts/freeze.py --check. Report the byte comparison and the suite count.
