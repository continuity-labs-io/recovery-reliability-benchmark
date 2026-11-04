Task: extend make_tables() in src/recovery_reliability_benchmark/synthetic.py so it can generate data with a known reliability, for the positive control in METHOD.md §5.1. The default path must stay byte-identical: when reliability is None, draw exactly what is drawn today, in the same order, so examples/*.csv regenerate unchanged.

1. New keyword arguments (append after seed, defaults preserve current behavior):
    reliability: float | None = None
    condition_offsets: dict[str, float] | None = None

2. Behavior when reliability is set (require 0 < reliability < 1, else ValueError; reliability == 1 would make every measure constant within units and fail the SCHEMA check):
    For each measure m independently:
        T_m[u] ~ N(0, 1) per unit
        E_m[u, t] ~ N(0, sigma^2) per row, with sigma^2 = n_trials * (1 - reliability) / reliability
        measure[u, t] = T_m[u] + offset[condition(t)] + E_m[u, t]
    offset comes from condition_offsets (missing conditions get 0.0). Raise ValueError if condition_offsets names a condition that is not in `conditions`.
    Add a column f"{m}_true" to units holding T_m[u], so tests and the positive control can see the truth.
    Draw order: after the existing x_um / y_um draws, per measure draw T then E. Do not touch the default path's draws.

3. Docstring: state the formula and this derivation, so nobody "fixes" it later:
    The per-unit mean over n trials has variance 1 + sigma^2/n, so its reliability is 1 / (1 + sigma^2/n) = rho.
    A split into two halves of n/2 trials gives half-means with correlation 1 / (1 + 2 sigma^2/n); Spearman-Brown on that
    correlation, 2r/(1+r), returns 1 / (1 + sigma^2/n) = rho. So the split-half estimate recovers `reliability` in expectation.

4. tests/test_synthetic.py (new):
    - test_default_matches_committed_examples: make_tables(n_units=15, n_trials=20, seed=0) equals examples/units.csv and examples/responses.csv read with read_tables (compare with pd.testing.assert_frame_equal, check_dtype=False, after casting trial_index and stim_time_ns to int64 on both sides). This pins the default path.
    - test_true_columns_present: make_tables(reliability=0.8) returns units with columns tau_true and amplitude_true; make_tables() does not.
    - test_variance_ratio_matches_reliability: for rho in (0.3, 0.8, 0.95): make_tables(n_units=20000, n_trials=10, reliability=rho, seed=1); per-unit mean M of tau from responses aligned to units["tau_true"] by unit_id; abs(var(T)/var(M) - rho) < 0.02. (At 20,000 units the standard error of that ratio is about 0.005.)
    - test_condition_offsets_shift_means: make_tables(n_units=200, n_trials=20, conditions=("A","B"), reliability=0.8, condition_offsets={"B": 5.0}, seed=2); mean(tau | B) - mean(tau | A) within 0.3 of 5.0.
    - test_reliability_dataset_conforms: make_tables(n_units=15, n_trials=20, reliability=0.8) validates with conformance == "fully_conforming".
    - test_bad_arguments: reliability=1.0 raises ValueError; reliability=0.0 raises ValueError; condition_offsets={"Z": 1.0} with conditions=("A",) raises ValueError.

Run the full suite and make it pass.
