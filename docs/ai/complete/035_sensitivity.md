Task: implement the sensitivity axis. One new module, sensitivity.py, plus wiring. No frozen changes.
Names below follow prompts 033 and 034; if the applied code differs, adapt and say so in the report.

Definition. For a measure and a pair of evaluated conditions (first, second), over the units whose odd
and even halves are non-null in both conditions:
  shift_u = (second_odd + second_even) / 2 - (first_odd + first_even) / 2
  noise_u = 0.5 * sqrt((first_odd - first_even)**2 + (second_odd - second_even)**2)
  z_u     = abs(shift_u) / max(noise_u, 1e-12)
Summaries: median_abs_z = median(z_u); frac_beyond_2 = mean(z_u > 2); median_shift = median(shift_u),
signed, in the measure's units; n_units.
Shuffled null: for each unit independently, deal its four half values at random into the four slots
and recompute the two summaries; n_perm times. Report the 95th percentile of each and the fraction of
shuffles with median_abs_z at or above the observed one.
Why the null: two halves per condition give each unit's noise two degrees of freedom, so about 18% of
units pass twice their noise by chance and the chance median is about 0.8.
This replaces the wording in METHOD and GLOSSARY. The one-condition variant is dropped: a pre-versus-
post contrast is not defined for a recovery time.

1. sensitivity.py:
   condition_sensitivity(halves, measure, first, second, n_perm, rng) -> dict with n_units,
     median_shift, median_abs_z, frac_beyond_2, null {n_perm, median_abs_z_p95, frac_beyond_2_p95,
     frac_perm_ge_observed}, above_null (median_abs_z > null.median_abs_z_p95). With zero qualifying
     units: n_units 0 and None for the rest.
   measure_sensitivity(halves, measure, evaluated_conditions, n_perm, seed) -> dict | None: None with
     fewer than two evaluated conditions; otherwise {"<first>|<second>": condition_sensitivity(...)}
     for every pair, labels in sorted order, shift = second minus first, a fresh
     np.random.default_rng(seed) per pair.

2. Wiring. Every scored measure entry and the reference entry gain "sensitivity", computed on the same
   halves that measure's reliability uses. For each pair a measure entry also gains "beats_reference":
   median_abs_z > the reference's median_abs_z for that pair; None on the tables path. The tables path
   gets sensitivity too.

3. text_report: one line per measure and pair, after that measure's reliability line:
   "  sensitivity control|slowed: median|z|=3.08 (null p95 1.07) beyond-2=0.71 (null p95 0.39)
   shift=+0.061 n_units=28", plus " [at chance]" when above_null is False and " [does not beat
   reference]" when beats_reference is False. The reference line gets the same.

4. synthetic.py: make_two_condition_spike_trains(rate_fns_first, rate_fns_second, n_trials, params,
   isi_s, seed) -> (trains, onsets_s, n_first), built exactly so:
     trains_1, onsets_1 = make_spike_trains(rate_fns_first, n_trials, params, isi_s, seed)
     trains_2, onsets_2 = make_spike_trains(rate_fns_second, n_trials, params, isi_s, seed + 1)
     offset = onsets_1[-1] + params.load_duration_s + params.post_stim_window_s + 1.0
     per unit: concatenate trains_1 with trains_2 + offset; onsets = onsets_1 then onsets_2 + offset.

5. tests/test_sensitivity.py. Bounds were measured with this exact recipe. Do not change seeds, trial
   counts or bounds; if a test fails, report the numbers.
   Dataset D(k, seed): 30 units; taus = np.geomspace(0.05, 0.5, 30); baseline of unit i =
   np.geomspace(1.0, 20.0, 30)[(7 * i) % 30]; peak 100; condition "control" uses taus, "slowed" uses
   taus * k; 20 trials each; isi 5 s; AnalysisParams(post_stim_window_s=2.0);
   make_two_condition_spike_trains with that seed; halves from spikes.halves_from_spikes.
   - test_detects_slowing, k = 1.5, seeds 0, 1, 2. t_half_excess: median_abs_z > 2.5 (measured 3.08,
     4.26, 3.33), frac_beyond_2 > 0.6 (0.71, 0.72, 0.73), median_shift > 0.04 (0.061, 0.061, 0.058),
     above_null True. baseline_hz: median_abs_z < 1.0 (0.59, 0.75, 0.67), frac_beyond_2 < 0.25.
   - test_chance_without_effect, k = 1.0, seeds 0, 1, 2. t_half_excess: median_abs_z < 1.0 (0.62,
     0.85, 0.70) and frac_beyond_2 < 0.2.
   - test_tables_path: make_tables(n_units=30, n_trials=20, conditions=("A", "B"), reliability=0.8,
     condition_offsets={"B": 3.0}), seeds 0, 1, 2, split_halves on tau: median_abs_z > 4.0 (5.42, 5.02,
     5.01), frac_beyond_2 > 0.9, 2.5 < median_shift < 3.5. With offset 0.0: median_abs_z < 1.0.
   - test_null_near_chance: on D(1.0, 0), null median_abs_z_p95 lies between 0.6 and 1.6.
   - test_one_condition_is_none.
   - test_zero_noise: hand-built halves; identical halves with a nonzero shift count as beyond 2;
     zero shift with zero noise gives z == 0; the output is finite and JSON-serializable.
   - test_run_reports_sensitivity: run on D(1.5, 0) with measures ["t_half_excess"]: the measure's
     sensitivity["control|slowed"].median_abs_z > 2.5 and beats_reference is True; the reference's
     median_abs_z < 1.0.
   - tests/test_cli.py: human output on a two-condition dataset contains "sensitivity control|slowed:".

6. Docs. METHOD: replace the sensitivity paragraph with the definition above; gaming table,
   stable-but-meaningless row, status "Implemented (v0.2.0)". GLOSSARY "Sensitivity axis": the
   definition, the null, the dropped one-condition variant. CONTRIBUTING "Submitting measures": the two
   marks. Add "sensitivity" to PACKAGE_MODULES. CHANGELOG Unreleased: "Sensitivity axis between
   condition pairs, with a shuffled null; reported for every measure and the reference row."

Run the full suite, ruff, scripts/freeze.py --check. Report: median_abs_z and frac_beyond_2 for
t_half_excess and baseline_hz on D(1.5, seeds 0, 1, 2), and the suite count.
