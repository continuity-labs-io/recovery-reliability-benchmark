Task: restructure run.py and cli.py with no behavior change. run.run is a 200-line function with a
12-parameter helper at 297 lines; cli.py is at 299. Pure moves: no output changes, no frozen changes,
no test logic changes.

0. Before touching code, save these six outputs with the current code:
   rrb-evaluate examples/units.csv examples/responses.csv --measures tau,amplitude \
     --post-stim-window-s 2.0 --n-perm 200            (once with --json, once without)
   rrb-evaluate examples/units.csv examples/trials_responses.csv --spikes examples/spikes.csv \
     --analysis examples/analysis.json \
     --measures t_half_excess,excess_per_trial,spikes_per_trial,t_return,overshoot --n-perm 200
                                                       (once with --json, once without)
   rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude \
     --post-stim-window-s 2.0 --json
   rrb-check examples/units.csv examples/trials_responses.csv --spikes examples/spikes.csv \
     --analysis examples/analysis.json --json

1. New module inputs.py:
   @dataclass(frozen=True) class EvaluationInputs with fields
     path ("responses" or "spikes"), val (the validate() result), halves, evaluated_conditions,
     best_condition, post_stim_window_s, load_duration_s,
     responses and active_units (tables path, else None),
     scored (measure -> condition -> unit ids), not_scored (frozenset of measure names),
     scored_counts (measure -> condition -> counts), flags_by_condition (spikes path, else None/empty).
   from_responses(...) -> EvaluationInputs: the current tables branch of run.run.
   from_spikes(...) -> EvaluationInputs: the current spikes branch, including the consistency
     ValueErrors, min-dataset-7, per-measure scoring, the rule that MD3 is raised only when no
     requested measure is scored, inclusion["spikes_path"], and the flag counts.
   SPIKES_INCLUSION_RULE moves here.

2. run.py keeps two functions:
   evaluate_measure(inputs, measure, n_perm, seed) -> dict: one measure, either the not_scored entry
     or the full entry. Replaces _evaluate_measures.
   run(...): same signature and docstring. Build inputs, census, parameters, positive control,
     evaluate each measure, assemble. No assert statements.
   Targets: run.py under 180 lines, inputs.py under 220.

3. New module text_report.py: the functions that format the check and evaluate results as
   human-readable lines move out of cli.py unchanged. cli.py keeps argument parsing, file loading and
   exit codes. Target: cli.py under 220 lines.

4. Add "inputs" and "text_report" to PACKAGE_MODULES in tests/test_style.py. Tests change only where
   they imported a moved name.

5. Regenerate the six outputs and compare with the saved ones: all byte-identical. Run the full
   suite, ruff, and scripts/freeze.py --check.

Report: the six comparison results, the line counts of run.py, inputs.py, cli.py and text_report.py,
and the suite count.
