Context Files

Existing files to read:

AGENTS.md
CHANGELOG.md
SPEC.md
README.md
src/recovery_reliability_benchmark/cli.py
src/recovery_reliability_benchmark/report.py
src/recovery_reliability_benchmark/inputs.py
src/recovery_reliability_benchmark/run.py
src/recovery_reliability_benchmark/spikes.py
src/recovery_reliability_benchmark/contract.py
src/recovery_reliability_benchmark/controls.py
src/recovery_reliability_benchmark/sensitivity.py
tests/test_cli.py
tests/test_report.py
tests/test_spikes.py
tests/test_spikes_inputs.py
tests/test_style.py

New file to create:

tests/test_cli_input_errors.py

Prompt 047 - command-line argument and file-read errors exit 2 with one line.
Apply after prompt 046.

1. OBJECTIVE AND OWNERSHIP

Three kinds of bad input still end in a Python traceback or a silent wrong run. Observed on the current
head:
- A timestamp or index column written with decimals (spike_time_ns in seconds, stim_time_ns in
  seconds, trial_index 0.5): rrb-check, rrb-evaluate and rrb-report crash at file read with
  "TypeError: cannot safely cast non-equivalent object to int64".
- --n-perm 0 runs to completion, exits 0 and reports NaN for the shuffled null; --n-perm -5 crashes
  rrb-evaluate with "ValueError: negative dimensions are not allowed".
- An unknown measure name on the spikes path crashes rrb-evaluate with ValueError, while rrb-report
  already exits 2 with "error: Unknown measure ...".

After this prompt each case exits 2 with a single "error: ..." line on stderr, from all three commands,
and the Python API raises ValueError for the two argument errors.

You own cli.py, the from_spikes function in inputs.py, and run_with_inputs in run.py. Fix the cause at
the boundary where it belongs (file reading in the CLI loader, argument validation at the top of the
API) instead of adding broad exception handlers around the evaluation.

2. INVARIANTS

- Open layer only. No frozen function or constant changes. Do not run freeze.py --amend. If
  freeze.py --check reports a difference, stop and report it.
- No reported number changes. examples/, the README example table and docs/spikes_path_checks.json
  stay byte-identical.
- Exit codes keep their meaning: 0 success, 1 contract violation, 2 input or argument error,
  3 positive-control failure. Error lines go to stderr in the existing form "error: <message>".
- Argument errors are reported before data errors: with a bad argument and a malformed dataset
  together, the argument error is the one reported.
- Contract violations from prompt 046 are unchanged, including their messages and exit code 1.
- Whole numbers written with a decimal point (trial_index 0.0, 1.0, 2.0) are still accepted.
- contract.py is at 299 lines of a 300-line limit: do not add lines to it.

File-read errors (CLI loader shared by the three commands):
- A failure to read responses into the contract column types becomes a ValueError whose message is
  "<responses path>: trial_index and stim_time_ns must be whole numbers (stim_time_ns in nanoseconds)."
- A failure to read spikes into the contract column types becomes a ValueError whose message is
  "<spikes path>: spike_time_ns must be whole numbers in nanoseconds."
- Convert only the type and value errors raised by those two read calls, each handled separately so
  the message names the right file. Missing files, empty files and parser errors keep their current
  handling and messages.

n_perm:
- run_with_inputs validates n_perm before anything else and raises
  ValueError("n_perm must be >= 1, got <value>.") for values below 1. run inherits this.
- rrb-evaluate and rrb-report exit 2 with "error: n_perm must be >= 1, got <value>." for 0 and for
  negative values. rrb-report writes no file and creates no output directory in that case.

Unknown measure on the spikes path:
- inputs.from_spikes checks every requested name against spikes.MEASURE_KEYS before it touches any
  table and raises ValueError with the same text spikes.halves_from_spikes produces
  ("Unknown measure '<name>'. Available measures: <comma-separated names>."). Build that text in one
  place so the two cannot drift; spikes.halves_from_spikes is frozen and must not change.
- rrb-evaluate treats a ValueError raised by run as an argument error: stderr "error: <message>",
  exit 2, matching what rrb-report already does.
- The tables path is unchanged: an unknown measure column there remains a SCHEMA violation, exit 1.

3. IMPLEMENTATION STEPS AND EDGE CASES

- Implement section 2. Keep every source file at or under 300 lines, Google-style docstrings with
  Args, Returns and Raises on public functions.
- New file tests/test_cli_input_errors.py. Build its well-formed dataset the same way
  tests/test_spikes_inputs.py does (12 units, 20 trials, isi 5 s, seed 0, post_stim_window_s 2.0),
  written to tmp_path with an analysis.json containing only post_stim_window_s 2.0. Cover:
    a. spikes.csv with spike_time_ns divided by 1e9 (decimals): each of rrb-check, rrb-evaluate and
       rrb-report returns 2; stderr is one line that starts with "error: ", contains the spikes file
       path and ends with "spike_time_ns must be whole numbers in nanoseconds."
    b. trial table with stim_time_ns divided by 1e9 plus 0.5 (decimals), spikes path: each command
       returns 2; stderr contains the trial table path and
       "trial_index and stim_time_ns must be whole numbers (stim_time_ns in nanoseconds)."
    c. the same fault as b on the tables path (make_tables output written to CSV, --measures tau
       --post-stim-window-s 2.0), for rrb-check and rrb-evaluate.
    d. trial_index offset by 0.5 on the tables path: returns 2 with the message from b.
    e. trial_index written as 0.0, 1.0, ... on the spikes path: rrb-check returns 0.
    f. --n-perm 0 and --n-perm -5: rrb-evaluate and rrb-report return 2 with
       "error: n_perm must be >= 1, got 0." and "error: n_perm must be >= 1, got -5."; the rrb-report
       output directory does not exist afterwards.
    g. run(..., n_perm=0) raises ValueError matching "n_perm must be >= 1, got 0", on the tables path
       and on the spikes path.
    h. --measures t_half_excess,nope on the spikes path: rrb-evaluate and rrb-report return 2 and
       stderr starts with "error: Unknown measure 'nope'. Available measures: ".
    i. ordering: run on the spikes path with measure "nope" and a trial table that lacks the condition
       column raises ValueError (not ContractViolation); the same tables with n_perm=0 and a valid
       measure raise the n_perm ValueError.
    j. none of the cases above prints a traceback: assert "Traceback" is absent from captured stdout
       and stderr.
- Do not weaken or delete existing tests. Existing tests that expect exit 2 or 1 keep passing
  unchanged, including the ValueError test on spikes.halves_from_spikes in tests/test_spikes.py.
- If an expectation above cannot be met as written, stop and report what you observed instead of
  changing the expectation.
- Docs: add one line to CHANGELOG.md under 0.2.0 (not a "Frozen:" line) stating that undecodable
  integer columns, a non-positive --n-perm and an unknown spikes-path measure exit 2 with a one-line
  error. Where SPEC.md or README.md describe exit codes, confirm they still read correctly and edit
  only a statement that has become false.

4. LOGGING AND NAMING

- No new print statements other than the existing "error: <message>" line on stderr, and no new
  logging. If a log line is warranted, use the module logger in the plain form
  logger.info("Step 1 - Read input tables.").
- Error messages are calm complete sentences that say what was found and what is required. No
  capitalized banners, exclamation marks or emojis in messages, comments, docstrings or test names.
- Names are practical and specific, for example responses_path, spikes_path, unknown_measures.

5. EXIT CONDITIONS

Run from the repository root and report the output of each:
  python scripts/freeze.py --check          exits 0 with no amend
  ruff check .                              no findings
  ruff format --check .                     no files to reformat
  pytest tests/test_cli_input_errors.py -q  all pass
  pytest -q                                 all pass (305 before this prompt, plus the new tests)
  git status --short examples README.md docs/spikes_path_checks.json frozen    prints nothing
Report the suite count and the number of new tests.
