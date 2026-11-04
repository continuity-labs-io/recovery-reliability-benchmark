Read it. Two findings before the prompt, then the prompt.

**Centering, settled.** gate1 does not compute the per-condition ceiling METHOD.md §3 describes. It builds an electrodes × blocks matrix per half, flattens it, and correlates across all (electrode, block) pairs pooled. The uncentered number includes between-block variance; `centered_r` subtracts each block's mean over electrodes within each half and correlates the residuals. That is where 0.779 vs 0.76 comes from, and it's the right design for a dataset with a dose sweep: with 8 to 19 units per condition, a per-condition correlation is too noisy to use alone, and pooling across conditions stabilizes it. So `evaluate.py` reports both: per-condition (where centering is a no-op) and pooled (uncentered and centered), with pooled-centered as the headline when there are two or more evaluated conditions. With one condition the three numbers coincide. Also: 0.779 is the geometric mean over two days of the within-session ceilings, so the single-session reproduction target is `ceiling_by_day`, not 0.779.

**A bigger one for later.** gate1's measures (`t_return`, `t_half_peak`, `residual`) are computed from the PSTH of all trials in a half pooled together, not per trial and then averaged. A per-trial `t_return` from two seconds of one electrode's spikes doesn't exist. `responses.csv` as a per-trial scalar table covers measures that *can* be averaged (counts, first-spike latency), which is enough for the evaluate engine, but reproducing the pilot requires the per-trial rows to carry binned counts and the measure to be a function of the half's mean bin vector. That fits the existing contract (still one row per unit and trial) and lands in item 8. So the pilot reproduction moves after `measures.py`; today's gates are synthetic.

## evaluate.py prompt

```
Task: create src/recovery_reliability_benchmark/evaluate.py (within-session reliability ceiling), an rrb-evaluate CLI, tests, and METHOD.md edits so the document matches the code. Add "numpy>=1.24" to pyproject dependencies explicitly.

Design (matches the Stable Basin gate1.py that produced the pilot numbers):
- The measure for a (unit, condition) group is computed on each half of that group's trials. Two estimates:
  per-condition: vector over units within one condition; Pearson across units; Spearman-Brown.
  pooled: vector over (unit, condition) pairs across all evaluated conditions; reported uncentered and condition-centered. Centering subtracts each condition's mean over units, within each half separately, before correlating.
  With one evaluated condition the pooled and per-condition numbers coincide (Pearson is shift-invariant). Headline = pooled centered when there are 2+ evaluated conditions, else per-condition of validate()'s best_condition.

Functions:

split_halves(responses, measures, conditions) -> pd.DataFrame
  Rows whose condition is in `conditions`. Within each (unit_id, condition) group sort by trial_index and rank k = 0, 1, 2, ...; even k -> half A, odd k -> half B. Return a frame indexed by (unit_id, condition) with columns f"{m}_A", f"{m}_B" (mean of the half's rows, skipna) and n_A, n_B. Drop groups where either half is empty. Rank within the group, not global trial_index parity.

ceiling(halves, measure, center: bool) -> dict
  x = halves[f"{measure}_A"], y = halves[f"{measure}_B"], drop pairs where either is NaN.
  If center: subtract the per-condition mean of x from x and of y from y (groupby level "condition", transform "mean").
  r = Pearson(x, y); NaN if fewer than 3 pairs or either side is constant.
  rho = 2r/(1+r) if r > 0 else 0.0.
  Return dict(r_half, rho, n_pairs, n_units, n_conditions, r_nonpositive=bool(not r > 0), odd_trials=bool((n_A != n_B).any()), center).

permutation_null(halves, measure, center, n_perm, rng) -> dict
  n_perm times: within each condition, permute which unit's B values sit on which row (shuffle the *_B and n_B columns among that condition's rows), then call ceiling() on the permuted frame. Same code path, no separate implementation. Return dict(median_rho, p95_rho, median_r, p95_r, frac_rho_ge_observed, n_perm), observed being ceiling(halves, measure, center)["rho"].

positive_control(reliability=0.85, n_units=1000, n_trials=20, seed=42, tolerance=0.05) -> dict
  make_tables(n_units, n_trials, reliability=reliability, seed=seed) -> validate -> split_halves -> ceiling(center=False) on "tau". Return dict(injected, recovered, passed=abs(recovered - injected) <= tolerance, n_units, n_trials, tolerance). Fixed size on purpose: it tests the pipeline, not the dataset, so it uses enough units for 0.05 to mean something.

census(validate_result) -> dict
  preparations, sessions, recordings, units, units_active, conditions, evaluated_conditions, trials, trials_per_unit_condition, in that order, from validate()'s return.

run(units, responses, measures, post_stim_window_s, load_duration_s=0.0, n_perm=1000, injected_r=0.85, tolerance=0.05, seed=42) -> dict
  1. validate(); let ContractViolation propagate.
  2. positive_control(injected_r, tolerance=tolerance, seed=seed). If it fails, return dict(status="positive_control_failed", positive_control, census, parameters) and compute nothing else.
  3. halves = split_halves(responses, measures, evaluated_conditions).
  4. Per measure: per_condition = {c: ceiling(rows of condition c, m, False)}; pooled = {"uncentered": ceiling(halves, m, False), "centered": ceiling(halves, m, True)}; headline per the rule above, with headline_kind "pooled_centered" or "per_condition"; null = permutation_null on the headline's frame and center flag, rng = np.random.default_rng(seed).
  5. Return dict(status="ok", spec_version, package_version (from __version__), parameters (all arguments plus "split_mode": "odd_even"), census, positive_control, measures={m: {"headline", "headline_kind", "per_condition", "pooled", "null"}}).

CLI main(argv): rrb-evaluate units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0 [--load-duration-s] [--n-perm] [--seed] [--json]. Exit 0 on status ok; 1 on ContractViolation (print str(exc)); 2 on unreadable input ("error: ..." to stderr); 3 on positive_control_failed. Human output: a census block, then one line per measure: "<measure>: rho=<headline rho:.3f> (<headline_kind>; r_half=<r:.3f>, n_units=<n>, n_pairs=<n>) null_p95_rho=<p95:.3f>". --json: same report shape as rrb-check (spec_version, status, inputs with sha256, arguments, result). Reuse read_tables and file_sha256 from contract.py. Add rrb-evaluate under [project.scripts].

METHOD.md edits:
- Header: "Reference implementation: `src/recovery_reliability_benchmark/evaluate.py`" (drop "planned"); update any test_docs assertion that depended on the old wording.
- §3 Procedure: replace steps 1-6 with the design above: partition by rank within (unit, condition); per-condition and pooled estimates; centering defined on the pooled estimate, within each half; headline rule; v1 implements odd_even only and `random` is not yet implemented (say so in §7 too).
- §4: add that in the per-condition estimate centering subtracts one constant from every unit and cannot change the correlation, so it is reported for the pooled estimate only; that pooled pairs share units across conditions, so n_pairs overstates independent samples and the census counts units; and that the pilot figures 0.779 / 0.76 are geometric means of two sessions' within-session ceilings.
- §5.1: the positive control generates data from scratch with T ~ N(0,1) and E ~ N(0, n(1-rho)/rho) at 1000 units × 20 trials and requires recovery within 0.05; the pilot's gate1.py used day-1 values plus noise instead, and the two constructions agree in expectation.
- §5.2: the null permutes unit labels of half B within each condition and recomputes the headline through the same function.

tests/test_evaluate.py:
- test_split_ranks_within_group: make_tables(n_units=8, n_trials=5, conditions=("A","B")); for (u00, B): half A has trial_index {5,7,9}, half B {6,8}; n_A=3, n_B=2. (Requires exposing which trials went where, or assert via means of trial_index: add a hidden option or compute from a measure column equal to trial_index. Simplest: add responses["ti"] = responses["trial_index"].astype(float) and pass measures=["ti"]; ti_A == 7.0, ti_B == 7.0 is ambiguous, so instead set ti = trial_index**2: ti_A == (25+49+81)/3, ti_B == (36+64)/2.)
- test_odd_trials_flag: n_trials=11 -> odd_trials True; n_trials=10 -> False.
- test_positive_control_large: positive_control(reliability=0.8, n_units=2000, n_trials=10, seed=0)["recovered"] within 0.02 of 0.8.
- test_positive_control_default_passes: positive_control()["passed"] is True.
- test_single_condition_estimates_agree: make_tables(n_units=15, n_trials=20, reliability=0.8); run(n_perm=20); for tau: pooled centered rho == pooled uncentered rho == per_condition["A"]["rho"] (approx); headline_kind == "per_condition".
- test_centering_removes_condition_offsets: make_tables(n_units=200, n_trials=20, conditions=("A","B","C"), reliability=0.8, condition_offsets={"A":0.0,"B":3.0,"C":6.0}, seed=3); run(n_perm=50); pooled uncentered rho > 0.93; pooled centered rho within 0.05 of 0.8; headline_kind == "pooled_centered". (Expected half-r: uncentered 7/7.5, centered 1/1.5.)
- test_nonpositive_r_reports_zero: hand-built halves frame, one condition, 10 units, tau_B = -tau_A: rho == 0.0, r_nonpositive True, r_half == approx(-1.0).
- test_null_below_observed: make_tables(n_units=40, n_trials=20, reliability=0.85, seed=4); run(n_perm=300); abs(null median_rho) <= 0.1 and null p95_rho < headline rho.
- test_census_matches_validate.
- test_run_positive_control_failure_path: monkeypatch evaluate.positive_control to return passed=False; run() returns status "positive_control_failed" and has no "measures" key.
- test_cli_evaluate_json(tmp_path): make_tables(n_units=15, n_trials=20, reliability=0.8) CSVs; main([..., "--n-perm", "50", "--json"]) returns 0; status "ok"; result["measures"]["tau"]["headline"]["rho"] within 0.15 of 0.8; both sha256 present.
- test_cli_evaluate_violation(tmp_path): n_trials=6 -> exit 1, stdout starts with "MD-2 failed."

CI: in .github/workflows/test.yml, after the rrb-check lines, run rrb-evaluate on examples/ with --n-perm 100 --json > evaluate.json and assert status == "ok" with a python -c line.

Run the full suite and make it pass. Report the headline rho for examples/ (expected near 0, possibly r_nonpositive, because the example measures are uniform noise with no unit effect; regenerating the examples with an injected reliability is a separate later step).
```

Gate: `pytest -q`, expect 102 passed, CI green with the new step. Then item 5 (threshold simulation), which is a short script on top of this.
