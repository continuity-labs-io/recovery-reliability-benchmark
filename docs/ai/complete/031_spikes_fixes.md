Task: two corrections to the spikes path. No frozen function changes, no version bump.

1. Inclusion per measure. Today scored_units requires every requested measure to be non-null in both
   halves, so requesting overshoot removes units from every other measure, and a measure's ceiling
   depends on what else was requested.
   - spikes.scored_units(halves, measures) -> dict[str, dict[str, set[str]]]: measure -> condition ->
     units with that measure non-NaN in both halves.
   - run: for each measure, restrict halves to that measure's scored units before the per-condition
     and pooled ceilings, the headline and the permutation null.
   - checks_spikes.check_scored_units works per measure and names it: "6 units with t_return computed
     in both halves for condition 'A', requires 8." A measure below the threshold is reported with
     status "not_scored" and its counts, and the other measures proceed; run raises the MD3
     ContractViolation only when no requested measure reaches the threshold.
   - Rule text everywhere (docstring, inclusion.spikes_path.rule, SPEC, GLOSSARY "Scored unit"):
     "A unit is scored for a measure in a condition when that measure is computed in both halves."
   - inclusion.spikes_path becomes per measure: {measure: {condition: {n_units_in_tables,
     n_units_scored, n_units_excluded_by_rule}}}. Human output prints "units scored" per measure.
   - Tests: on the example, t_return requested alone and requested with overshoot gives the identical
     headline rho with n_units == 30; overshoot's n_units == 27. A dataset where overshoot has 6
     scored units and t_return has 30 returns status "not_scored" for overshoot and a ceiling for
     t_return.

2. tests/test_run_spikes.py test_t_return_reliability_bounds was moved from 20 to 100 trials to meet a
   0.9 bound. The bound was wrong, not the trial count. Replace it with:
   - test_t_return_at_twenty_trials: 30 units, taus log-spaced 0.05 to 0.5, 20 trials, seeds 0, 1, 2.
     Assert t_half_peak's headline rho exceeds t_return's on at least two of the three seeds.
     Docstring: at 20 trials the last-exceedance rule is dominated by late Poisson fluctuations; this
     is a property of the measure, recorded here, not tuned away.
   - test_t_return_converges_with_trials: same units at 20, 50 and 100 trials, seed 0: rho at 100
     exceeds rho at 20, and rho at 100 > 0.9.
   - Keep the identical-taus assertion (rho < 0.3) at 20 trials.
   Do not change trial counts, seeds or bounds to make these pass. If one fails, report the numbers.

3. examples/make_examples.py: the spikes example's condition label "baseline" reads as the baseline
   firing rate. Use the label the tables example uses. Regenerate the three spikes example files.

CHANGELOG Unreleased: "spikes path: inclusion is per measure; a measure with too few scored units is
reported as not scored." Report: t_return and t_half_peak rho for seeds 0, 1, 2 at 20 trials; t_return
rho at 20, 50, 100; the suite count.
