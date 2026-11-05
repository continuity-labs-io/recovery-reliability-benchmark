DECISION: MD3_SHOULD = 30   (if keeping 15, skip section 1 and use n_units=15 in section 3)

1. Threshold change (only if MD3_SHOULD = 30)
- contract.py: MD3_SHOULD = 30; Requirement.MD3 description "SHOULD 30".
- SPEC.md: §4 table row MD-3 SHOULD "≥ 30"; MD-3 text "SHOULD contain 30 or more"; §5 sentence becomes "narrows from [0.00, 0.95] at the MUST thresholds to [0.67, 0.92] at the SHOULD thresholds (single-trial reliability 0.2)". Keep the 15-unit interval in the §4 paragraph as an intermediate point. Add to the §4 paragraph, after the 8-unit interval: "and 7% of such runs report exactly 0 (19% when the single-trial reliability is 0.1)".
- tests/test_thresholds.py::test_spec_numbers_match_json: pin the §5 sentence to the (rho1=0.2, n_conditions=1, n_trials=20, n_units=30) cell and the p_zero figures to the (0.2, 1, 10, 8) and (0.1, 1, 10, 8) cells.
- Tests that used 15 units as fully conforming move to 30: test_fully_conforming, test_should_partial (n_units=30, n_trials=10 -> should_failed == ["MD-2"]), test_best_condition_tiebreak (n_units=30; drop A's units u08..u29 so A keeps 8 active and B keeps 30; expectations unchanged in form), test_cli_fully_conforming, test_cli_json_pass, and any evaluate/metadata test that asserts "fully_conforming" at 15.
- CHANGELOG Unreleased: "MD-3 SHOULD raised from 15 to 30 units before the v1.0 spec is tagged, on the basis of docs/thresholds.md."

2. Test fix
- tests/test_evaluate.py::test_ci_contains_truth_at_scale: revert the measure to "tau" and replace the containment assertion with: abs(est["rho"] - 0.8) < 0.03 and (rho_ci_high - rho_ci_low) < 0.05. Add a comment: a single 95% interval misses 5% of the time, so containment is tested by coverage over seeds (test_ci_coverage_small_n), not on one draw.

3. Examples with signal
- Before touching examples/, compute sha256 of the current examples/units.csv and examples/responses.csv and hardcode both digests in tests/test_synthetic.py::test_default_path_unchanged, which asserts that make_tables(n_units=15, n_trials=20, seed=0) serialized with to_csv(index=False) reproduces those digests. Delete test_default_matches_committed_examples.
- examples/make_examples.py: make_tables(n_units=30 (or 15), n_trials=20, reliability=0.8, seed=0); keep writing preparation.json and conditions.json. Regenerate and commit.
- tests/test_cli.py::test_examples_are_fully_conforming stays; add tests/test_evaluate.py::test_examples_headline: run() on the examples with n_perm=50 gives headline rho within 0.15 of 0.8, rho_ci_low > 0.5, status "ok".
- README quickstart: add the rrb-evaluate line and one sentence: "The example data are synthetic with a true reliability of 0.8; the reported ceiling and its interval should bracket it."
- .github/workflows/test.yml: keep the existing asserts.

Run the full suite and make it pass.
