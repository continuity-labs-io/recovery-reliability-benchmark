Task: review fixes to src/recovery_reliability_benchmark/evaluate.py. Behavior changes are limited to naming, the undefined-r flag, and the source of the z critical value. Add scipy>=1.10 to dependencies.

1. Rename ceiling -> reliability_ceiling everywhere: definition, imports, __init__ exports and __all__, thresholds.py, tests, METHOD.md, GLOSSARY.md, README layout line, docstrings. No alias left behind.

2. Expel A/B. Halves are "odd" and "even" by 1-based position within each (unit_id, condition) group after sorting by trial_index: positions 1, 3, 5, ... are the odd half; 2, 4, 6, ... the even half. Columns become f"{measure}_odd", f"{measure}_even", n_odd, n_even. Update split_halves, reliability_ceiling, permutation_null, variance_components, thresholds.py, all tests, METHOD.md §3 and GLOSSARY.md ("Half means"). Docstring of split_halves states the position rule in one sentence and says why rank within group rather than global trial_index parity.

3. reliability_ceiling:
   - Add r_undefined: True when fewer than 3 pairs or either half is constant; r_nonpositive stays True only for a defined r <= 0. rho is 0.0 in both cases; the two flags tell them apart.
   - confidence: float = 0.95 parameter. Critical value z_crit = scipy.stats.norm.ppf(0.5 + confidence / 2). Expose r_ci_low, r_ci_high (bounds on r) alongside rho_ci_low, rho_ci_high.
   - rho_at_20 is derived: REFERENCE_N_TRIALS = contract.MD2_SHOULD, with a comment "the SHOULD threshold of min-dataset-2; rho_at_20 is the ceiling a fully conforming session would show". Key stays rho_at_20; a test asserts REFERENCE_N_TRIALS == 20 so a future threshold change forces renaming the key.
   - logging: module logger = logging.getLogger(__name__); logger.debug on each branch: undefined r (with the reason), nonpositive r, CI not computed (n_eff < 4). No handlers configured in the library.
   - Google-style docstring: one-paragraph summary, Args (every parameter), Returns (every key of the dict, one line each), Notes (why n_eff = units; why rho is floored at 0).

4. permutation_null, rewrite for intent:
   - Module-level comment block above the function stating the algorithm: within each condition, draw a random permutation of that condition's rows and move the even-half columns (every f"{m}_even" for m in measures, plus n_even) along it, leaving the odd half in place; recompute reliability_ceiling on the permuted frame with the same center flag; repeat n_perm times. Pairings never cross conditions. This is a stratified pairing permutation, the same null scipy.stats.permutation_test(permutation_type="pairings") computes for a single stratum.
   - Build the moved-column list from the measure names present (columns ending in "_even" derived by stripping the suffix), not from an endswith match on arbitrary columns; assert the list is non-empty.
   - Add a `seed`-free signature: rng is required and must be a numpy Generator (raise TypeError otherwise).
   - Google-style docstring.

5. Tests (tests/test_evaluate.py):
   - test_fisher_interval_matches_scipy: 40 units, one condition, reliability 0.8; r_ci_low/r_ci_high equal scipy.stats.pearsonr(odd, even).confidence_interval(0.95) to 1e-9 (n_eff == n_pairs in this case).
   - test_pooled_interval_uses_units_not_pairs: 3 conditions, 30 units; n_eff == 30 while n_pairs == 90, and the interval is wider than pearsonr's on the 90 pairs.
   - test_null_matches_scipy_pairings_single_condition: 40 units, one condition, reliability 0.5, n_perm 2000, seed fixed; our median_r and p95_r within 0.03 of the 50th and 95th percentiles of scipy.stats.permutation_test((odd, even), lambda a, b: np.corrcoef(a, b)[0, 1], permutation_type="pairings", n_resamples=2000, random_state=0).null_distribution.
   - test_null_never_mixes_conditions: 2 conditions with condition_offsets {"A": 0, "B": 100}; monkeypatch reliability_ceiling to capture each permuted frame; in every permuted frame the sorted even-half values within each condition equal the originals.
   - test_r_undefined_flags: two pairs -> r_undefined True, r_nonpositive False, rho 0.0; a constant odd half -> same; a negative correlation -> r_undefined False, r_nonpositive True.
   - test_reference_trials_is_should_threshold: REFERENCE_N_TRIALS == MD2_SHOULD == 20.
   - test_contract_imports_only_pandas: subprocess python -c "import recovery_reliability_benchmark.contract, sys; assert 'scipy' not in sys.modules".
   - Update every test and doc string that referenced A/B or ceiling.

Run the full suite and ruff; make both pass.
