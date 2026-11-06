Task: make unit inclusion a pre-registered rule applied identically by validate() and evaluate(), report inclusion counts and contributor-declared exclusions, and add variance components next to each ceiling.

1. contract.py
- In the per-condition info, add "active_units": sorted list of unit_ids active in that condition, and "n_units_in_tables": len(units). Add "n_rows_missing": the number of (unit, trial) cells of the full grid (all units × that condition's distinct trial_index values) with no row. Add "n_units_excluded_by_rule": n_units_in_tables - n_units_active.
- Return dict adds "inclusion": {
    "rule": "A unit is included in a condition if and only if it has a row for every trial of that condition with every measure non-null. All present trials are used; no trial is excluded by rule in v0.1.x.",
    "per_condition": {c: {"n_units_in_tables", "n_units_included", "n_units_excluded_by_rule", "n_rows_missing", "n_trials"}},
    "declared": {"units": int, "trials": int} from preparation.exclusions (zeros when no sidecar) }.

2. metadata.py
- Preparation gains exclusions: list[Exclusion] = [] where class Exclusion(BaseModel, frozen): kind: Literal["unit", "trial"]; id: str; reason: str (min_length 1).
- validate(): under SCHEMA, an excluded unit id that is present in units.csv, or an excluded trial id that is present as a trial_index in responses, is a contradiction: "exclusions lists unit 'X' as excluded but it is present in units." Same for trials.

3. evaluate.py
- split_halves(responses, measures, conditions, active_units: dict[str, set[str]] | None = None): when given, keep only rows whose (unit_id, condition) is in the active set for that condition. run() passes val["conditions"][c]["active_units"] for every evaluated condition. positive_control passes them too (all units are active there; this keeps one code path).
- New function variance_components(responses, measure, condition, active_units) -> dict: over included units, unit_mean = mean over trials; var_between = variance of unit means (ddof=1); var_within = mean over units of the per-unit trial variance (ddof=1); n_trials = median trials per unit; moments_reliability = max(0, (var_between - var_within / n_trials) / var_between) if var_between > 0 else None. Docstring: a ceiling driven by between-unit heterogeneity shows up as large var_between relative to var_within; moments_reliability is the ANOVA-style estimate of the same quantity the split-half ceiling estimates, and the two should agree.
- run(): per measure, per evaluated condition, add "variance": variance_components(...). Add "inclusion": val["inclusion"] to the result, and the census gains "units_in_tables", "units_included" (max over evaluated conditions), "units_excluded_by_rule", "rows_missing", "declared_exclusions".
- Human CLI: after the census, print one line per evaluated condition: "<cond>: units included <n> of <n_in_tables> (excluded by rule <n>, rows missing <n>); declared exclusions units <n> trials <n>". Per measure line gains "between=<var_between:.3g> within=<var_within:.3g>" for the headline condition (for pooled headlines, the best condition's values).
- rrb-check human output prints the same inclusion lines.

4. Tests
- tests/test_contract.py: test_inclusion_counts: make_tables(n_units=12, n_trials=10); drop one row for u00; result["inclusion"]["per_condition"]["A"] == {"n_units_in_tables": 12, "n_units_included": 11, "n_units_excluded_by_rule": 1, "n_rows_missing": 1, "n_trials": 10}; "u00" not in conditions["A"]["active_units"].
- tests/test_metadata.py: Exclusion round-trip; Preparation with exclusions; load_preparation on a malformed exclusion raises SCHEMA.
- tests/test_contract.py: test_declared_exclusion_contradiction: preparation with exclusions=[{"kind":"unit","id":"u00","reason":"saturated"}] while u00 is in units -> SCHEMA, "u00" in message; with id "u99" -> passes and inclusion["declared"]["units"] == 1.
- tests/test_evaluate.py:
    test_inactive_unit_not_in_halves: same dropped-row table; run(n_perm=20); "u00" not in the unit level of the halves used (expose via result["measures"]["tau"]["per_condition"]["A"]["n_units"] == 11) and result["inclusion"]["per_condition"]["A"]["n_units_excluded_by_rule"] == 1.
    test_variance_components_match_generator: make_tables(n_units=2000, n_trials=20, reliability=0.8, seed=0); variance_components on tau: var_within within 5% of 5.0, var_between within 5% of 1.25, moments_reliability within 0.03 of 0.8, and within 0.03 of the split-half rho from ceiling().
    test_cli_prints_inclusion(tmp_path): human output contains "units included".
- Update any test that asserted exact census keys.

Run the full suite and ruff; make both pass.
