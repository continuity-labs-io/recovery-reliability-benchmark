Context Files

Existing files to read:

AGENTS.md
CHANGELOG.md
SPEC.md
README.md
src/recovery_reliability_benchmark/cli.py
src/recovery_reliability_benchmark/report.py
src/recovery_reliability_benchmark/run.py
src/recovery_reliability_benchmark/summary.py
src/recovery_reliability_benchmark/text_report.py
src/recovery_reliability_benchmark/controls.py
src/recovery_reliability_benchmark/evaluate.py
tests/test_cli.py
tests/test_report.py
tests/test_cli_input_errors.py
tests/test_style.py

New files to create:

src/recovery_reliability_benchmark/strict_json.py
tests/test_strict_json.py

Prompt 048 - valid JSON for undefined values, and a report folder that never holds stale files.
Apply after prompt 047.

1. OBJECTIVE AND OWNERSHIP

Two defects in what the commands write.

A. Invalid JSON. When a measure is identical for every unit, its split-half correlation is undefined.
   Observed on the current head with 12 slowly recovering units (t_return censored at the window end
   for every unit): rrb-evaluate --json and the evaluate.json written by rrb-report contain six NaN
   tokens (r_half in the headline, per-condition and both pooled entries; median_r and p95_r in the
   null), and numpy prints "RuntimeWarning: All-NaN slice encountered" on stderr. NaN is not JSON;
   strict parsers reject the file. Python's own json.load accepts it, which is why CI did not notice.

B. Stale report files. By inspection of report.main: after a contract violation it writes only
   summary.md and leaves evaluate.json and halves.png from an earlier successful run in the same
   --out folder; after an input error it writes nothing and leaves all three. A reader of the folder
   then gets results that do not belong to the last command.

You own cli.py, report.py, the evaluate_measure function in run.py, and the new strict_json.py. Put
JSON writing behind one function and make the report folder's contents a stated invariant, instead of
patching individual call sites.

2. INVARIANTS

- Open layer only. No frozen function or constant changes: evaluate.reliability_ceiling and
  controls.permutation_null keep returning float NaN for undefined values. Do not run
  freeze.py --amend. If freeze.py --check reports a difference, stop and report it.
- No reported number changes. examples/, the README example table and docs/spikes_path_checks.json
  stay byte-identical. For a dataset with no undefined value, the JSON output is byte-identical to
  what it is today.
- The dictionary returned by run and run_with_inputs is unchanged in memory. Conversion happens only
  where JSON text is produced.

Strict JSON:
- One public function in strict_json.py turns a result object into JSON text. It replaces every
  non-finite float (NaN, positive and negative infinity, including numpy float scalars) with null,
  at any nesting depth inside dicts, lists and tuples, and serializes with NaN output disabled so a
  non-finite value that escapes conversion raises instead of being written. Finite numbers, integers,
  booleans, strings, None and all keys pass through unchanged. It accepts the indent and sort_keys
  options the current call sites use.
- Every JSON document a command prints or writes for the user goes through it: the --json output of
  rrb-check, rrb-evaluate and rrb-report, and evaluate.json.
- Reading rule for consumers: an undefined number is null; r_undefined true marks an undefined
  correlation; rho stays 0.0 in that case, as today.
- The human-readable text output is unchanged.

No warnings on stderr:
- The "All-NaN slice encountered" RuntimeWarning raised inside the frozen permutation null is
  silenced at its call site in run.evaluate_measure, with a filter limited to that message and that
  call. Do not silence warnings globally and do not touch controls.py.

Report folder (rrb-report --out DIR):
- After any rrb-report invocation, each of evaluate.json, summary.md and halves.png in DIR either
  belongs to that invocation or is absent.
- Achieve this by removing those three files, if present, before inputs are loaded. Remove only
  those three names. Never remove other files or the directory.
- Success (exit 0) and positive-control failure (exit 3): evaluate.json and summary.md are written;
  halves.png is written only when matplotlib is available and the status is ok.
- Contract violation (exit 1): DIR holds summary.md with the violation and neither evaluate.json nor
  halves.png.
- Input or argument error (exit 2): nothing is written, a DIR that did not exist is not created, and
  a DIR that existed no longer holds any of the three files.
- If --out names an existing path that is not a directory: exit 2 with
  "error: --out <path> is not a directory." and nothing removed or written.

3. IMPLEMENTATION STEPS AND EDGE CASES

- Implement section 2. Keep every source file at or under 300 lines, Google-style docstrings with
  Args, Returns and Raises on public functions. Register the new module wherever tests/test_style.py
  enumerates the package modules.
- New file tests/test_strict_json.py:
    a. Unit tests of the function: NaN, inf and -inf become null at the top level, inside nested
       dicts, inside lists and tuples, and as numpy float scalars; finite floats, ints, bools,
       strings and None are unchanged; the output parses with a strict parser.
    b. A strict parser for the tests is json.loads with a parse_constant callback that raises.
    c. Undefined-measure dataset: 12 units, exponential_recovery with baseline 5 Hz, peak 100 Hz and
       tau np.geomspace(4.0, 8.0, 12); make_spike_trains with 20 trials, isi 5 s, seed 0;
       AnalysisParams(post_stim_window_s=2.0); written with writer.write_dataset; measures
       t_return,t_half_excess; --n-perm 20.
    d. rrb-evaluate --json on c, with RuntimeWarning turned into an error for the duration of the
       call: exit 0; stdout parses strictly; the text contains no "NaN" and no "Infinity"; for
       t_return the headline has r_half null, r_undefined true and rho 0.0, and the null has
       median_r null and p95_r null.
    e. rrb-report on c under the same warning rule: exit 0 and evaluate.json parses strictly with
       the same four facts.
    f. rrb-check --json on the same files parses strictly.
    g. On examples/two_conditions the rrb-evaluate --json output is byte-identical to
       json.dumps(document, indent=2, sort_keys=True) of the same document.
- Additions to tests/test_report.py, each using one --out folder across two invocations:
    h. Good run, then a run whose trial table violates min-dataset-7 (first onset at 0.5 s): exit 1;
       summary.md contains "min-dataset-7"; evaluate.json and halves.png are absent.
    i. Good run, then a run with a missing spikes file: exit 2; none of the three files is present;
       an unrelated file placed in the folder beforehand is still there.
    j. Missing input with an --out folder that does not exist: exit 2 and the folder still does not
       exist.
    k. --out pointing at an existing regular file: exit 2 with the message from section 2, and the
       file is unchanged.
    l. Good run with matplotlib available, then a good run with matplotlib made unavailable (reuse
       the technique in test_missing_matplotlib): halves.png is absent and summary.md says the figure
       was skipped.
- Do not weaken or delete existing tests. If an expectation above cannot be met as written, or a
  RuntimeWarning other than "All-NaN slice encountered" appears in d or e, stop and report what you
  observed instead of changing the expectation.
- Docs: where SPEC.md or README.md describe the JSON output or the report folder, add that undefined
  numbers are written as null with r_undefined marking an undefined correlation, and that the report
  folder is cleared of its three files at the start of each run. One line in CHANGELOG.md under
  0.2.0 (not a "Frozen:" line).

4. LOGGING AND NAMING

- No new print statements other than the existing result and "error: <message>" lines, and no new
  logging. If a log line is warranted, use the module logger in the plain form
  logger.info("Step 1 - Clear previous report files.").
- Messages are calm complete sentences. No capitalized banners, exclamation marks or emojis in
  messages, comments, docstrings or test names.
- Names are practical and specific, for example REPORT_FILE_NAMES, clear_report_files,
  replace_non_finite.

5. EXIT CONDITIONS

Run from the repository root and report the output of each:
  python scripts/freeze.py --check     exits 0 with no amend
  ruff check .                         no findings
  ruff format --check .                no files to reformat
  pytest tests/test_strict_json.py -q  all pass
  pytest tests/test_report.py -q       all pass
  pytest -q                            all pass
  git status --short examples README.md docs/spikes_path_checks.json frozen    prints nothing
  (README.md may appear only if the docs step edited it)
Report the suite count and the number of new tests.
