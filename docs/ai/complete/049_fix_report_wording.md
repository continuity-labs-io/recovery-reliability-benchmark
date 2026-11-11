Context Files

Existing files to read:

AGENTS.md
CHANGELOG.md
README.md
SPEC.md
METHOD.md
GLOSSARY.md
src/recovery_reliability_benchmark/summary.py
src/recovery_reliability_benchmark/text_report.py
src/recovery_reliability_benchmark/report.py
src/recovery_reliability_benchmark/run.py
src/recovery_reliability_benchmark/inputs.py
src/recovery_reliability_benchmark/evaluate.py
src/recovery_reliability_benchmark/sensitivity.py
tests/test_report.py
tests/test_sensitivity.py
tests/test_docs.py
tests/test_cli.py
tests/test_strict_json.py
tests/test_style.py

New files to create:

src/recovery_reliability_benchmark/report_notes.py
tests/test_report_notes.py

Prompt 049 - report wording says which axis a note is about.
Apply after prompt 048.

1. OBJECTIVE AND OWNERSHIP

The Notes column and the text report use "at chance" for two different things. In a one-condition
report it means the reliability is no higher than its shuffled null. In a report with two or more
conditions it means the sensitivity is no higher than its shuffled null, and a reliability at chance
is not flagged at all. Four smaller wording faults sit beside it:
- A measure that is identical for every unit shows Reliability 0.000 with the note "at chance". Its
  correlation is undefined, not measured as zero.
- When baseline_hz is itself requested as a measure, its row carries "does not beat reference",
  because it is compared with itself.
- "Positive control: passed" reads as covering the whole run. It checks the split-half estimator on
  a synthetic table, on both paths.
- The figure shows only the first four requested measures and does not say so.

After this prompt every note names its axis, and the summary table and the text report take their
wording from one place.

You own summary.py, text_report.py, the figure note in report.py, the beats_reference assignment in
run.run_with_inputs, and the new report_notes.py. Replace the two separate note-building branches
with one rule instead of renaming strings in place.

2. INVARIANTS

- Open layer only. No frozen function or constant changes. Do not run freeze.py --amend. If
  freeze.py --check reports a difference, stop and report it.
- No reported number changes. Every numeric cell of every table, and every number in evaluate.json,
  is unchanged. The one JSON change is beats_reference for the reference measure (below).
- examples/ and docs/spikes_path_checks.json stay byte-identical.

One source of wording:
- report_notes.py holds the note texts as constants and one pure function that returns the ordered
  list of notes for a table row, given the measure entry, the condition pair for that row (or none),
  and whether the row is the measure's first row. summary.py and text_report.py both use it. No
  note text is written anywhere else.

Note texts and when each applies:
- "no variation across units": the headline has r_undefined true. Measure-level.
- "reliability at chance": r_undefined is false and the headline rho is less than or equal to the
  shuffled null p95_rho. Measure-level. Applies whatever the number of conditions.
- "sensitivity at chance": the pair's above_null is false. Pair-level.
- "does not beat reference": the pair's beats_reference is false. Pair-level.
- The censoring note keeps its current text. Measure-level.
- "no variation across units" and "reliability at chance" never appear together.
- Order within a row: reliability note, then sensitivity at chance, then does not beat reference,
  then censoring. Separator and the empty-notes dash are unchanged.
- Measure-level notes appear on the measure's first row only; pair-level notes appear on the row of
  their pair. A one-condition report has measure-level notes only.
- The bare phrase "at chance" no longer appears in any output.

Undefined reliability in the summary:
- The Reliability cell reads "undefined" (not 0.000) and the interval cell reads "n/a". Other cells
  are unchanged.
- The "How to read this" paragraph for that measure says the reliability is undefined because every
  scored unit has the same value, in place of the reliability sentence.

Text report:
- Sensitivity lines use "[sensitivity at chance]" and "[does not beat reference]".
- The measure line gains "[reliability at chance]" or "[no variation across units]" under the same
  rule as the table.

Reference measure:
- In run.run_with_inputs, beats_reference is None for the measure that is the reference measure
  (inputs.reference_measure) and unchanged for every other measure. It is written to JSON as null.
  The reference row itself still carries no beats_reference key.

Positive control line in summary.md:
- "Positive control (split-half estimator on a synthetic table): passed (...)" with the existing
  parenthesis of numbers unchanged; "failed" in the failing case.

Figure note:
- When more than four measures are requested, the figure line in summary.md is followed by
  "Figure shows the first 4 of <n> measures." With four or fewer, nothing is added.

3. IMPLEMENTATION STEPS AND EDGE CASES

- Implement section 2. Keep every source file at or under 300 lines (summary.py is at 291: moving the
  note logic out must leave it at or under the limit), Google-style docstrings with Args, Returns and
  Raises on public functions. Register the new module wherever tests/test_style.py enumerates the
  package modules.
- New file tests/test_report_notes.py, using hand-built measure entries (plain dictionaries with only
  the fields the function reads), so no simulation is needed:
    a. rho 0.20, p95_rho 0.35, one condition: ["reliability at chance"].
    b. rho 0.35, p95_rho 0.35: ["reliability at chance"] (equal counts as at chance).
    c. rho 0.90, p95_rho 0.35, one condition: [].
    d. r_undefined true, rho 0.0, p95_rho 0.0: ["no variation across units"] and not
       "reliability at chance".
    e. two conditions, rho 0.90, pair with above_null false and beats_reference true:
       ["sensitivity at chance"].
    f. pair with above_null false and beats_reference false:
       ["sensitivity at chance", "does not beat reference"] in that order.
    g. pair with beats_reference None: no reference note.
    h. rho below p95_rho with a pair at chance and a censoring count: reliability note first,
       censoring last, on the first row; on a second pair row only that pair's notes.
- Integration tests, added to the existing test files:
    i. examples/two_conditions through build_summary with measures
       t_half_excess,excess_per_trial,t_return: the t_return row ends with
       "| sensitivity at chance; censored: control 8, slowed 11 |", the baseline_hz (reference) row
       ends with "| sensitivity at chance |", and the t_half_excess row's Notes cell is the dash.
    j. Identical recovery in every unit (30 units, exponential_recovery baseline 5 Hz, peak 100 Hz,
       tau 0.2 for all, 20 trials, isi 5 s, seed 0, one condition, measure t_half_excess,
       n_perm 50): the t_half_excess row's notes contain "reliability at chance".
    k. The undefined-measure dataset defined in tests/test_strict_json.py, measures
       t_return,t_half_excess: the t_return row has Reliability "undefined", interval "n/a", and
       notes containing "no variation across units" and "censored: 12 units" and not
       "reliability at chance".
    l. Six requested measures on examples/ through rrb-report: summary.md contains
       "Figure shows the first 4 of 6 measures." when matplotlib is available; with two measures the
       sentence is absent.
    m. summary.md for any successful run contains
       "Positive control (split-half estimator on a synthetic table): passed".
- Update tests/test_sensitivity.py::test_run_reports_sensitivity to the new contract: for the
  requested baseline_hz measure beats_reference is None; the human text still contains
  "  sensitivity control|slowed: median|z|=3.27"; it does not contain "[does not beat reference]";
  its last line ends with "[sensitivity at chance]".
- README.md example table: only the Notes cells of two rows change. Expected rows:
    | t_return | 0.731 | [0.428, 0.874] | 0.357 | 30 | 1.00 | 1.07 | sensitivity at chance; censored: control 8, slowed 11 |
    | baseline_hz (reference) | 0.989 | [0.977, 0.995] | 0.350 | 30 | 0.59 | 1.13 | sensitivity at chance |
  If any other cell of the generated table differs from the README, stop and report it.
- Docs: update every sentence in README.md, SPEC.md, METHOD.md and GLOSSARY.md that explains the
  Notes column or quotes "at chance" or "Positive control: passed". Afterwards
  grep -rn "at chance" over *.md and *.py outside docs/ai/ shows only "reliability at chance" and
  "sensitivity at chance". One line in CHANGELOG.md under 0.2.0 (not a "Frozen:" line).
- Do not weaken or delete other existing tests. If an expectation above cannot be met as written,
  stop and report what you observed instead of changing the expectation.

4. LOGGING AND NAMING

- No new print statements and no new logging. If a log line is warranted, use the module logger in
  the plain form logger.info("Step 3 - Build summary table.").
- Note texts are lowercase plain phrases as specified. No capitalized banners, exclamation marks or
  emojis in notes, messages, comments, docstrings or test names.
- Names are practical and specific, for example NOTE_RELIABILITY_AT_CHANCE, NOTE_NO_VARIATION,
  row_notes.

5. EXIT CONDITIONS

Run from the repository root and report the output of each:
  python scripts/freeze.py --check       exits 0 with no amend
  ruff check .                           no findings
  ruff format --check .                  no files to reformat
  pytest tests/test_report_notes.py -q   all pass
  pytest tests/test_report.py tests/test_sensitivity.py tests/test_docs.py -q   all pass
  pytest -q                              all pass
  grep -rn "at chance" --include="*.md" --include="*.py" . | grep -v "docs/ai/" | grep -v "reliability at chance" | grep -v "sensitivity at chance"    prints nothing
  git status --short examples docs/spikes_path_checks.json frozen    prints nothing
Report the suite count, the number of new tests, and the six table lines of the regenerated README
example.
