Task: bring every source file under 300 lines, write the repo's code guidelines down, and tie the glossary to the code. No behavior changes.

1. Layout (move code, do not rewrite it):
   - contract.py keeps: constants, Requirement, ContractViolation, read_tables, read_spikes, ValidationContext, validate, build_report. checks.py gets the check functions and CHECKS (contract imports it lazily inside validate to avoid a cycle, or checks imports the types from a new _types.py; pick whichever keeps both files acyclic and say which).
   - evaluate.py keeps: split_halves, reliability_ceiling, variance_components. controls.py gets permutation_null, positive_control, census. run.py gets run. cli.py gets both CLIs as check_main and evaluate_main plus the shared report-writing helpers; pyproject scripts point at cli; contract.py and evaluate.py keep a two-line __main__ that calls the cli function so python -m still works.
   - __init__.py re-exports the same public names from their new homes; test_package.py unchanged except for one added assertion that nothing is exported twice.

2. tests/test_style.py:
   - test_source_files_under_300_lines: every .py under src/recovery_reliability_benchmark has at most 300 lines (physical lines). Print the offenders with counts on failure.
   - test_public_functions_have_google_docstrings: every public function and class in the package has a docstring; functions with parameters have an "Args:" section; functions that return a value have a "Returns:" section. Use ast; allow a per-symbol skip list that starts empty.
   - test_glossary_symbols_resolve: for every backticked token in GLOSSARY.md that looks like a dotted code path inside the package (module.name or module.Class.method, where module is one of contract, checks, evaluate, controls, run, cli, protocol, metadata, synthetic, thresholds), import the module and assert the attribute exists. Print the unresolved ones.
   - test_no_ab_half_names: no identifier or string matching _A\b, _B\b, "n_A", "n_B", "half A", "half B" appears under src/ or tests/ (grep by regex over file text; allow a skip list that starts empty).

3. CONTRIBUTING.md, new section "## Code guidelines" (short):
   - Source files stay under 300 lines; split by responsibility, not by line count.
   - Public functions carry Google-style docstrings with Args, Returns and Raises where applicable.
   - Validation lives in checks.py as an ordered registry; a new requirement is a new entry, not a new branch in validate().
   - Anything algorithmically non-obvious carries a comment stating intent before the code (permutation_null is the example).
   - Names say what the number is: reliability_ceiling, not ceiling; odd/even halves, not A/B.
   - The checker (contract.py, checks.py) depends on pandas only; scipy is allowed from evaluate.py onward.
   - Every backticked code symbol in GLOSSARY.md must resolve; tests/test_style.py enforces all of the above.

4. GLOSSARY.md: update symbol references to the new module paths (evaluate.reliability_ceiling, controls.permutation_null, controls.positive_control, run.run, checks.CHECKS); add entries "Check registry" and "Validation context".

5. CHANGELOG Unreleased: "Modules split under a 300-line rule: checks.py, controls.py, run.py, cli.py; ceiling renamed reliability_ceiling; halves named odd/even; Fisher interval and permutation null pinned to SciPy in tests; code guidelines in CONTRIBUTING.md."

Run the full suite and ruff; make both pass. Report the line count of every file under src/.
