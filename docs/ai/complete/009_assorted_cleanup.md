Task: cleanup pass across docs, package exports and two slow checks. No changes to validate() behavior; all existing tests must pass unchanged.

1. Titles and links
- METHOD.md and CONTRIBUTING.md: change the H1 "# Recovery Measurement Benchmark" to "# Recovery Reliability Benchmark".
- CONTRIBUTING.md §1: change the link target `01-dataset-conformance-spec.md` to `SPEC.md`.
- METHOD.md header: change "Reference implementation: `evaluate.py`" to "Reference implementation: `src/recovery_reliability_benchmark/evaluate.py` (planned; not yet in the repository)".

2. Anchor claim
The exact sentence pair, verbatim:
    Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported.
- README.md: insert it as its own paragraph directly after the opening one-sentence description, before "## What is being benchmarked".
- SPEC.md §1: replace the first sentence of the first paragraph (the one beginning "We have not found") with the sentence pair. Keep the counterexample invitation that follows it.

3. Package exports
- src/recovery_reliability_benchmark/__init__.py: export validate, ContractViolation, Requirement, read_tables, SPEC_VERSION from .contract and Pulse, Burst, Train, Protocol, default_pulse from .protocol; define __all__ with exactly those names plus "__version__".
- __version__: importlib.metadata.version("recovery-reliability-benchmark"), falling back to "0.0.0+unknown" on PackageNotFoundError.

4. Vectorize two checks in contract.py (same results, no Python loop over groups)
- Constant-measure SCHEMA check: g = responses.groupby(["unit_id", "condition"], sort=False, dropna=False); per measure, nun = g[measure].nunique() (dropna by default) and cnt = g[measure].count(); eligible = cnt >= 2; fail when eligible.any() and (nun[eligible] <= 1).all(). Same message as now.
- MD-3 active-unit counts: add a boolean column complete = responses[measures].notna().all(axis=1) on the working copy; g = responses.groupby(["condition", "unit_id"], sort=False); n_tr = g["trial_index"].nunique(); all_complete = g["complete"].all(); n_trials_cond = responses.groupby("condition")["trial_index"].nunique(); a unit is active when n_tr equals n_trials_cond for its condition and all_complete is True; n_units_active per condition is the sum. Drop the helper column before anything else uses the frame. Fill conditions_info from these series; keep every key and value identical to the current output.

5. Tests
- tests/test_docs.py, add:
    test_doc_titles: METHOD.md, CONTRIBUTING.md and SPEC.md each contain "# Recovery Reliability Benchmark" and none contains "Recovery Measurement Benchmark".
    test_contributing_links_spec: "SPEC.md" in CONTRIBUTING.md and "01-dataset-conformance-spec.md" not in it.
    test_anchor_claim_pinned: the exact sentence pair above appears in both README.md and SPEC.md.
- tests/test_package.py (new):
    test_exports: from recovery_reliability_benchmark import validate, ContractViolation, Requirement, read_tables, SPEC_VERSION, Pulse, Burst, Train, Protocol, default_pulse, __version__; __version__ is a non-empty str; set(__all__) equals the exported names.
- tests/test_contract.py, add:
    test_validate_at_scale: make_tables(n_units=1000, n_trials=100) validates with conformance == "fully_conforming", n_units_active == 1000, n_trials == 100. No timing assertion, but note in a comment that this took minutes before vectorization and should take seconds now.
    test_md3_vectorized_matches_original: make_tables(n_units=12, n_trials=10, conditions=("A","B")); drop one row for unit u00 in condition A and set tau to NaN for one row of u01 in condition B; result["conditions"]["A"]["n_units_active"] == 11 and result["conditions"]["B"]["n_units_active"] == 11.

Run the full suite and make it pass. Report the wall time of test_validate_at_scale.
