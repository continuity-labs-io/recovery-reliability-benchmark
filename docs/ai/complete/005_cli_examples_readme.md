Task: add the CLI, a console script, example CSVs, and a README quickstart. No changes to validate() logic.

1. Move the fixture factory into the package.
- Create src/recovery_reliability_benchmark/synthetic.py containing make_tables() exactly as it is in tests/conftest.py (same signature, same behavior, same docstring plus a line saying it produces a conforming dataset by construction).
- tests/conftest.py imports make_tables from recovery_reliability_benchmark.synthetic and keeps the `tables` fixture. Existing tests must not change.

2. CLI in src/recovery_reliability_benchmark/contract.py
- def file_sha256(path) -> str: hex digest of the file contents.
- def main(argv: list[str] | None = None) -> int, using argparse:
    positional: units_csv, responses_csv
    --measures            required, comma-separated
    --post-stim-window-s  required, float
    --load-duration-s     float, default 0.0
    --extra-forbidden     comma-separated, default empty
    --json                flag
- Behavior:
    a. read_tables(). On FileNotFoundError, ValueError, pandas.errors.ParserError, pandas.errors.EmptyDataError: print "error: <message>" to stderr and return 2.
    b. validate(). On ContractViolation: return 1. Otherwise return 0.
    c. Human output (default), on success: first line "<conformance> (SPEC v<spec_version>)", then one "key: value" line per top-level result key except "conditions", then "conditions:" followed by one indented line per condition formatted "<name>: n_trials=<n> n_units_active=<n> should_failed=<list or none>". On violation: print str(exc) as the only line. Both go to stdout.
    d. JSON output (--json), one JSON document to stdout:
       {"spec_version": SPEC_VERSION,
        "status": <result["conformance"]> on success or "violation" on failure,
        "inputs": {"units": {"path": <as given>, "sha256": ...}, "responses": {"path": ..., "sha256": ...}},
        "arguments": {"measures": [...], "post_stim_window_s": ..., "load_duration_s": ..., "extra_forbidden": [...]},
        "result": <validate() dict> on success, or
        "violation": <exc.to_dict()> on failure}
       Use indent=2 and sort_keys=True.
    e. Add at the bottom: if __name__ == "__main__": sys.exit(main())
- Docstring for main: this report is what a lab shares; the data stays on their machine.

3. pyproject.toml: add
    [project.scripts]
    rrb-check = "recovery_reliability_benchmark.contract:main"

4. examples/
- examples/make_examples.py: imports make_tables, calls make_tables(n_units=15, n_trials=20, seed=0), writes examples/units.csv and examples/responses.csv with index=False, paths resolved relative to the script's own directory. Runnable as `python examples/make_examples.py`.
- Run it and commit both CSVs.

5. README.md: add a "Quickstart" section above "Licensing":
    pip install -e .
    rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0
  State that the first line of output is the conformance level, that `--json` produces a shareable report containing the verdict, counts, and sha256 of the inputs, and that no data leaves the machine. Mention `python -m recovery_reliability_benchmark.contract` as the equivalent without the console script.

6. tests/test_cli.py (write CSVs into tmp_path with make_tables and call main([...]) directly; use capsys):
    - test_cli_conforming_exit_0: default make_tables; return 0; first stdout line == "conforming (SPEC v1.0)".
    - test_cli_fully_conforming: make_tables(n_units=15, n_trials=20); first line == "fully_conforming (SPEC v1.0)".
    - test_cli_violation_exit_1: make_tables(n_trials=6); return 1; stdout == "MD-2 failed. At most 6 trials in any condition (condition 'A'), requires 10.\n".
    - test_cli_window_violation_message: --post-stim-window-s 0.4; return 1; stdout == "MD-6 failed. Post-stimulus window 0.4 s, requires 2.0 s.\n".
    - test_cli_missing_file_exit_2: nonexistent units path; return 2; "error:" in stderr; stdout empty.
    - test_cli_json_pass: make_tables(n_units=15, n_trials=20) with --json; json.loads(stdout) has status == "fully_conforming", spec_version == "1.0", result["n_units"] == 15, inputs["units"]["sha256"] equal to hashlib.sha256 of the file bytes, arguments["measures"] == ["tau", "amplitude"].
    - test_cli_json_violation: make_tables(n_trials=6) with --json; return 1; status == "violation", violation["requirement"] == "MD-2", violation["found"] == 6, "result" not in the document.
    - test_examples_are_fully_conforming: run main on examples/units.csv and examples/responses.csv (paths built from Path(__file__).resolve().parent.parent / "examples"); return 0; first line == "fully_conforming (SPEC v1.0)".

Run the suite and make it pass. Then run the README quickstart command once and confirm it prints fully_conforming.
