Task: add invariance tests, fix four small things, fold the changelog, prepare the tag. No behavior changes except where noted.

1. tests/test_invariance.py. Fixture: make_tables(n_units=30, n_trials=20, conditions=("A","B","C"), reliability=0.8, condition_offsets={"A":0,"B":1,"C":2}, seed=7). Baseline = run(units, responses, ["tau","amplitude"], 2.0, n_perm=200, seed=1). Helper strip(result) drops package_version and compares the rest with pytest.approx recursively (floats to 1e-9, None/str/bool exact).
   - test_invariant_to_row_order: shuffle responses rows and units rows (seeded) -> identical result.
   - test_invariant_to_unit_relabeling: map every unit_id to a new random string consistently in units and responses -> identical numbers (compare after re-mapping the active_units lists and per-unit keys back).
   - test_invariant_to_condition_relabeling: rename conditions A,B,C -> X,Y,Z consistently -> identical numbers after re-mapping keys; best_condition maps accordingly.
   - test_invariant_to_affine_measure_transform: tau -> 3.7 * tau - 12.5 -> identical rho, r_half, CI, rho_single_trial, null, moments_reliability; var_between and var_within scale by 3.7**2 (assert that explicitly); headline_kind unchanged.
   - test_invariant_to_trial_index_offset: add 1000 to every trial_index and stim_time_ns -> identical result.
   - test_variance_inflation_does_not_move_score: multiply tau by 100 for the even-positioned trials only is NOT an invariance (it changes the data); instead assert that scaling the whole measure by 100 leaves rho and the null unchanged (the Arc-style attack has no lever here). Reference METHOD.md's gaming table in the docstring.
   Mark the module in CONTRIBUTING.md code guidelines: "Every reported number must be invariant to row order, unit and condition relabeling, affine transforms of a measure, and index offsets; tests/test_invariance.py enforces this."

2. Small fixes:
   - controls.permutation_null: create `permuted = halves.copy()` once before the loop; inside the loop only assign the moved columns.
   - checks.check_active_units and checks.check_post_stimulus_window: replace the fallback calls to earlier checks with `raise RuntimeError("<name> requires <prerequisite> to have run; CHECKS order guarantees this")` when the context is unfilled. Add a test that calls check_active_units on a fresh context and expects RuntimeError.
   - checks.check_trials_per_condition: compare with explicit arrays: `n_tr.to_numpy() == n_tr.index.get_level_values("condition").map(n_trials_cond).to_numpy()`.
   - checks.check_stimulus_timeline: replace the two per-trial loops with groupby("trial_index").nunique() on condition and stim_time_ns, raising on the first offending trial_index; same messages.

3. CHANGELOG.md: move everything under Unreleased into the [0.1.0] section (grouped Added/Changed), set its date to today, leave Unreleased empty. The release is the state after this prompt.

4. Run the suite, ruff and the style test. Print the tag commands; do not run them.
