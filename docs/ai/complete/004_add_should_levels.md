Task: add SHOULD levels and the conformance verdict to validate() in src/recovery_reliability_benchmark/contract.py, plus one SCHEMA check on measures. No CLI yet (step 5).

1. SCHEMA check j (append after the trial_index null check): a measure must vary within at least one (unit_id, condition) group. Compute, per measure, nunique(dropna=True) over each (unit_id, condition) group that has at least 2 non-null rows; if no such group exists, skip the check for that measure; if every such group has nunique <= 1, fail.
    Message: "measure 'pos' is constant within every (unit_id, condition) group and carries no trial-to-trial information, requires variation in at least one group."
    Rationale for the docstring: a column constant within units but varying across them (an electrode position, an identifier) would score as perfectly reliable.

2. SHOULD levels, computed after all MUST checks pass (no exceptions raised for SHOULD):
    - Module constants CONFORMING = "conforming", FULLY_CONFORMING = "fully_conforming".
    - For every evaluated condition c: should_failed(c) = [id for id in ("MD-2", "MD-3") that fail], where MD-2 SHOULD fails when n_trials < MD2_SHOULD and MD-3 SHOULD fails when n_units_active < MD3_SHOULD. Store it as conditions[c]["should_failed"]. For conditions that are not evaluated, conditions[c]["should_failed"] = None.
    - best_condition = the evaluated condition with the fewest should_failed; ties broken by larger n_units_active, then larger n_trials, then condition name ascending.
    - conformance = FULLY_CONFORMING if best_condition has an empty should_failed, else CONFORMING.
    - Return dict adds: best_condition, should_failed (the best condition's list), conformance.

3. tests/test_contract.py, each from make_tables() with MEASURES and post_stim_window_s=2.0 unless noted:
    - test_conforming_level: default fixture; result["conformance"] == "conforming", result["should_failed"] == ["MD-2", "MD-3"], result["best_condition"] == "A".
    - test_fully_conforming: make_tables(n_units=15, n_trials=20); "fully_conforming", should_failed == [], conditions["A"]["should_failed"] == [].
    - test_should_partial: make_tables(n_units=15, n_trials=10); "conforming", should_failed == ["MD-2"].
    - test_best_condition_skips_unevaluated: make_tables(n_units=15, n_trials=20, conditions=("A", "B")); drop responses rows where condition == "B" and trial_index >= 25 (B keeps 5 trials, not evaluated); "fully_conforming", best_condition == "A", conditions["B"]["should_failed"] is None.
    - test_best_condition_tiebreak: make_tables(n_units=15, n_trials=10, conditions=("A", "B")); drop responses rows where condition == "A" and unit_id in {"u08", ..., "u14"} (A keeps 8 active units, B keeps 15); conditions["A"]["should_failed"] == ["MD-2", "MD-3"], conditions["B"]["should_failed"] == ["MD-2"], best_condition == "B", should_failed == ["MD-2"], conformance == "conforming".
    - test_schema_constant_measure_per_unit: add responses["pos"] = responses["unit_id"] mapped to a distinct float per unit (varies across units, constant within each); measures=["tau", "pos"]; exc.requirement is Requirement.SCHEMA and "pos" in str(exc).
    - test_schema_constant_measure_everywhere: responses["bias"] = 1.0; measures=["tau", "bias"]; SCHEMA, "bias" in str(exc).

Run the suite and make it pass.

