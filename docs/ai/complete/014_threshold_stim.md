Task: justify the MD-2/MD-3 thresholds with a simulation, add confidence intervals and trial-count standardization to the ceiling, and write the numbers into SPEC.md. Thresholds themselves are not changed by this prompt.

1. evaluate.py additions to ceiling() (returned keys added; nothing removed):
   - Confidence interval: Fisher z on r_half with n_eff = n_units (not n_pairs: pooled pairs share units, so n_units is the conservative count). z = atanh(r), se = 1/sqrt(n_eff - 3), bounds z ± 1.96 se, back-transformed to r_lo, r_hi; rho_ci = (SB(r_lo) if r_lo > 0 else 0.0, SB(r_hi)). None if n_eff < 4 or r is NaN. Keys: rho_ci_low, rho_ci_high, n_eff.
   - Trial-count standardization: n_trials_group = median over the frame's groups of (n_A + n_B). rho_single_trial = rho / (n - (n-1) rho) with n = n_trials_group (0.0 when rho == 0); rho_at_20 = 20 rho1 / (1 + 19 rho1). Keys: n_trials_group, rho_single_trial, rho_at_20. Docstring: ceilings from sessions with different trial counts are compared through rho_single_trial or rho_at_20, not through rho.
   - Human CLI line gains "ci=[lo, hi]" and "rho_at_20=".

2. scripts/thresholds.py (runnable as python scripts/thresholds.py [--seeds 1000] [--out docs/thresholds] [--fast]):
   Grid: rho1 in (0.1, 0.2, 0.4); n_trials in (10, 20); n_units in (8, 15, 30); n_conditions in (1, 3). For n_conditions == 3 use conditions ("A","B","C") with condition_offsets {"A": 0.0, "B": 1.0, "C": 2.0}.
   Per cell, for seed in range(seeds): reliability = n_trials * rho1 / (1 + (n_trials - 1) * rho1); make_tables(n_units, n_trials, conditions, reliability=reliability, condition_offsets=..., seed=seed); halves = split_halves(responses, ["tau"], conditions); est = ceiling(halves, "tau", center=(n_conditions == 3)). Record est["rho"], est["rho_ci_low"], est["rho_ci_high"], est["r_nonpositive"].
   Do not call run() or validate() per seed (too slow); call validate() once per cell on seed 0 and record its conformance level.
   Per cell report: true_rho (the reliability passed in), median_rho_hat, p2_5, p97_5, width = p97_5 - p2_5, p_zero = fraction with r_nonpositive, ci_coverage = fraction of seeds whose [rho_ci_low, rho_ci_high] contains true_rho, conformance.
   --fast: seeds=50, for tests and CI.
   Outputs: docs/thresholds.md (one Markdown table, sorted by rho1, n_conditions, n_trials, n_units; a header paragraph stating the generator, the estimator, the seed count, and the command that produced it) and docs/thresholds.json (list of cell dicts plus "seeds" and "generated_by").
   Runtime target: a few minutes at 1000 seeds. If make_tables is the bottleneck, do not optimize it here; lower the default seeds and say so in the output header.

3. After running at 1000 seeds, edit the docs using numbers from docs/thresholds.json:
   - SPEC.md §4, after the MD-3 explanation, add a paragraph: "The MUST thresholds define when the computation is possible. They do not make a single-dataset estimate precise. For a measure with single-trial reliability 0.2, the ceiling of a 10-trial session is 0.71 and of a 20-trial session 0.83. Simulated 95% intervals of the estimate (1,000 seeds, one condition): 8 units and 10 trials, [L, U]; 15 units and 20 trials, [L, U]; 30 units and 20 trials, [L, U]. Pooling three conditions at 8 units and 10 trials gives [L, U]. Every estimate is reported with its interval and converted to a single-trial reliability so sessions with different trial counts can be compared. Full table: docs/thresholds.md."
   - SPEC.md §5: replace "Confidence intervals on the resulting estimate will be materially narrower." with "The simulated 95% interval of the estimate narrows from [L, U] at the MUST thresholds to [L, U] at the SHOULD thresholds (single-trial reliability 0.2); see docs/thresholds.md."
   - METHOD.md §3: add the confidence interval and the single-trial conversion as steps after Spearman-Brown, with the formulas.
   - CHANGELOG.md Unreleased: "Ceiling reports a Fisher-z interval (n_eff = units) and single-trial / 20-trial standardized reliabilities." and "docs/thresholds.md: simulated sampling distribution of the estimate at the MD-2/MD-3 thresholds; SPEC.md §4 and §5 cite it."

4. Tests
   tests/test_evaluate.py additions:
   - test_ci_contains_truth_at_scale: make_tables(n_units=2000, n_trials=20, reliability=0.8, seed=0); ceiling CI contains 0.8 and its width is below 0.05.
   - test_ci_coverage_small_n: over 200 seeds at n_units=15, n_trials=20, reliability=0.8, the fraction of CIs containing 0.8 is between 0.90 and 0.99.
   - test_single_trial_conversion: for a frame with n_A + n_B = 20 and rho = 0.8, rho_single_trial == approx(0.8 / (20 - 19 * 0.8)) and rho_at_20 == approx(0.8); with rho == 0.0 both are 0.0.
   tests/test_thresholds.py:
   - test_fast_grid_runs(tmp_path): import the script's main function, run with --fast and --out tmp_path/thresholds; the JSON has 36 cells, each with the keys above, and every cell's conformance is "conforming" or "fully_conforming".
   - test_spec_numbers_match_json: read docs/thresholds.json; format the four intervals named in SPEC.md §4 the same way the script formats them (two decimals, square brackets); assert each string appears in SPEC.md. Pins the spec text to the committed run.
   tests/test_docs.py: docs/thresholds.md exists and SPEC.md contains "docs/thresholds.md".

5. Commit docs/thresholds.md and docs/thresholds.json from the 1000-seed run. Report back the eight rows for rho1 = 0.2 at n_trials in (10, 20), n_units in (8, 15, 30), and n_conditions in (1, 3).
