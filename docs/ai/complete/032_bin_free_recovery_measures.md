Task: add two bin-free recovery measures. No frozen changes, no version bump.

Why: the binned measures read single PSTH bins. With 10 trials per half the early bins hold about one
spike, so peak_rate, t_peak and t_half_peak are set by chance, and t_return moves between 0.5 and 0.0
with the bin choice. Measures built on the running spike count have no bins.

1. Mechanical move to stay under 300 lines: AnalysisParams, DEFAULT_BIN_EDGES_S and FLAG_KEYS move to a
   new module analysis.py and are re-exported from measures.py, so existing imports and glossary
   references keep working. Add "analysis" and "excess" to PACKAGE_MODULES in tests/test_style.py.

2. AnalysisParams gains min_excess_z: float = 2.0, validated > 0. to_dict changes, so re-pin
   PINNED_DEFAULT_FINGERPRINT_2S and regenerate examples/analysis.json.

3. New module excess.py:
   excess_measures(latencies, baseline, params) -> tuple[dict[str, float], dict[str, bool]]
   - latencies: the per-trial arrays from trial_latencies for one unit and one set of trials.
     n = number of trials; pooled = all latencies sorted; N = len(pooled); W = post_stim_window_s.
   - excess_total = N - baseline * n * W.
   - excess_per_trial = excess_total / n. Never NaN for n >= 1; may be negative.
   - If excess_total <= min_excess_z * sqrt(max(N, 1)): t_half_excess = NaN and flag no_excess = True.
     The response is not distinguishable from baseline, so there is no recovery to time.
   - Otherwise, with cum_k = k - baseline * n * pooled[k-1] for k = 1..N, t_half_excess is the latency
     of the first spike k with cum_k >= 0.5 * excess_total.
   - A zero baseline needs no special case.
   Docstring: for an exponential recovery with time constant tau and a window much longer than tau,
   t_half_excess estimates tau * ln 2.

4. measures.unit_measures merges the excess values and flags into its outputs. FLAG_KEYS gains
   "no_excess". spikes.MEASURE_KEYS gains "t_half_excess" and "excess_per_trial".

5. tests/test_excess.py. Every bound below was measured by running this exact definition on these
   exact settings (baseline 5 Hz, peak 100 Hz, isi 5 s, AnalysisParams(post_stim_window_s=2.0),
   make_spike_trains). Do not change seeds, trial counts or bounds. If a test fails, report the numbers.
   - test_half_excess_matches_theory: taus 0.05, 0.1, 0.2, 400 trials, seed 5: t_half_excess within
     20% of tau * ln 2 for each.
   - test_half_excess_reliable_at_twenty_trials: 30 units, taus np.geomspace(0.05, 0.5, 30), 20 trials,
     seeds 0, 1, 2: split-half rho through halves_from_spikes and reliability_ceiling > 0.9 on each
     seed (measured 0.976, 0.981, 0.957).
   - test_half_excess_blind_to_amplitude: all taus 0.2, same settings, seeds 0, 1, 2: rho < 0.3 on
     each (measured 0.0, 0.0, 0.052).
   - test_excess_per_trial_reliable: the spread-tau data, seeds 0, 1, 2: rho > 0.95.
   - test_no_excess_flag: peak 0: t_half_excess is NaN, no_excess is True, excess_per_trial is finite.
   - test_zero_baseline_ok: baseline 0, peak 50: t_half_excess is finite and no_excess is False.
   - test_bin_edges_do_not_matter: t_half_excess is exactly equal under the default edges and under
     linear 100 ms edges.

6. Docs: GLOSSARY entries "Excess spikes", "`t_half_excess`", "`excess_per_trial`", "Bin-free measure";
   in "PSTH-based measure" add: "reads single bins, so it needs many spikes per bin; on the synthetic
   example at 20 trials peak_rate, t_peak and t_half_peak score near zero." README "From spikes" and
   the CI workflow use --measures t_half_excess,excess_per_trial,spikes_per_trial. METHOD: one short
   paragraph "Binned and bin-free measures". CHANGELOG Unreleased: "excess.py: bin-free recovery
   measures t_half_excess and excess_per_trial."

Run the full suite and ruff. Report: the three t_half_excess rhos at 20 trials, the three
identical-tau rhos, the new fingerprint, and the suite count.
