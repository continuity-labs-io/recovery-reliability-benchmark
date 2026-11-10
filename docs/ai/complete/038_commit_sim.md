Task: commit the simulation that backs two statements the docs are about to make, and pin its numbers.
New script; no package changes; no frozen changes.

1. scripts/spikes_path_checks.py, deterministic, no arguments.
   Populations of 30 units, i = 0..29, taus = np.geomspace(0.05, 0.5, 30):
     strong: baseline np.geomspace(1.0, 20.0, 30)[(7 * i) % 30], peak 100 Hz
     weak:   same baselines, peak 30 Hz
     sparse: baseline np.geomspace(0.2, 5.0, 30)[(7 * i) % 30],
             peak np.geomspace(5.0, 50.0, 30)[(11 * i) % 30]
   For each population, n_trials in (20, 40) and seed in range(40), with
   AnalysisParams(post_stim_window_s=2.0), isi 5 s, rate functions from exponential_recovery:
     session A = make_spike_trains(..., seed=seed); session B = make_spike_trains(..., seed=10_000 + seed)
     full_A, full_B = unit_measures over all onsets of each session
     odd, even = unit_measures over session A's onsets[0::2] and onsets[1::2]
     per measure in (t_half_excess, excess_per_trial, baseline_hz, t_return):
       test_retest = Pearson r across units between full_A and full_B (units non-NaN in both)
       r_half = Pearson r across units between odd and even (units non-NaN in both)
       split_half_corrected = 2 r / (1 + r) if r > 0 else 0
       units_scored = number of units non-NaN in both halves
   Writes docs/spikes_path_checks.json: per "<population>_<n_trials>" and measure, the mean over the
   40 seeds of split_half_corrected and test_retest (3 decimals) and units_scored (1 decimal). Writes
   docs/spikes_path_checks.md: the same as tables, plus the recipe in words.

2. Expected values, measured with this recipe. If any differs by more than 0.005, stop and report;
   adjust nothing.
   t_half_excess (split_half_corrected / test_retest / units_scored):
     strong_20 0.968 / 0.965 / 29.3      strong_40 0.985 / 0.985 / 29.8
     weak_20   0.678 / 0.728 / 20.9      weak_40   0.811 / 0.863 / 24.5
     sparse_20 0.734 / 0.737 / 19.8      sparse_40 0.811 / 0.793 / 22.8
   excess_per_trial: strong_20 0.984 / 0.984; weak_20 0.888 / 0.867; sparse_20 0.964 / 0.968
   baseline_hz:      strong_20 0.990 / 0.990; sparse_20 0.962 / 0.966
   t_return:         strong_20 0.687 / 0.681; weak_20 0.528 / 0.510; sparse_20 0.336 / 0.341

3. tests/test_spikes_path_checks.py: the JSON has the six keys; the values in item 2 match it to
   0.005; a smoke test runs one session (strong, 20 trials, seed 0) and gets four measures. The full
   script is not run in CI.

Run the script, the suite and ruff. Report the t_half_excess values for all six cases and the runtime.
