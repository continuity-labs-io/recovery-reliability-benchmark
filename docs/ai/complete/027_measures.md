Task: create src/recovery_reliability_benchmark/measures.py, the PSTH recovery measures computed from spike
times, plus the synthetic spike-train generator and ordering tests. Pure functions on numpy arrays in seconds;
no file I/O, no pandas, no CLI, no change to any existing function. gate1.py (the pilot analysis) is attached:
where it fixes a detail the definitions below leave open (bin time = edge or center; last-exceed rule; residual
window; baseline source), gate1.py wins and the docstring says so; where it is silent, the defaults below apply.

1. AnalysisParams, a frozen dataclass:
   post_stim_window_s: float (required); pre_stim_window_s: float = 1.0; load_duration_s: float = 0.0;
   bin_edges_s: tuple[float, ...] = 41 edges log-spaced from 0.003 to 10.0 (np.geomspace, rounded to 6
   decimals); return_x_baseline: float = 1.5; half_peak_frac: float = 0.5; residual_s: float = 1.0.
   Methods: to_dict(), from_dict(d), fingerprint() = sha256 hex of json.dumps(to_dict(), sort_keys=True),
   effective_edges() = the edges strictly inside post_stim_window_s followed by post_stim_window_s itself, so
   the last bin ends at the window end and every width is positive. Validation in __post_init__: windows > 0,
   load_duration_s >= 0, edges strictly increasing and starting at 0 or above, 0 < half_peak_frac < 1,
   return_x_baseline > 1, 0 < residual_s <= post_stim_window_s. ValueError with the value named.
   Time zero for every latency is onset + load_duration_s; spikes during the load are not latencies.

2. Functions, each with Google docstrings (Args, Returns):
   - trial_latencies(spike_times_s, onsets_s, params) -> list[np.ndarray]: per onset, spike times minus
     (onset + load_duration_s), kept when 0 <= latency < post_stim_window_s. Sorted inputs not assumed.
   - pre_counts(spike_times_s, onsets_s, params) -> np.ndarray[int]: per onset, spikes with
     onset - pre_stim_window_s <= t < onset.
   - baseline_hz(pre_counts, params) -> float: sum(pre_counts) / (n_trials * pre_stim_window_s).
   - baseline_variance_hz2(pre_counts, params) -> float: variance (ddof=1) across trials of
     pre_counts / pre_stim_window_s; NaN when fewer than 2 trials.
   - bin_counts(latencies, edges_s) -> np.ndarray shape (n_trials, n_bins).
   - psth_rate(counts, edges_s) -> np.ndarray: mean over trials of counts, divided by bin width, Hz per bin.
     Equal to pooled counts / (n_trials * width); say so in the docstring.
   - recovery_measures(rate_hz, edges_s, baseline, params) -> tuple[dict[str, float], dict[str, bool]].
     Bin time = bin center unless gate1.py says otherwise. Values:
       t_peak: time of the bin with the maximum rate (first on ties). peak_rate: that maximum.
       t_half_peak: time of the first bin after the peak bin with rate <= baseline + half_peak_frac *
         (peak_rate - baseline); if none, post_stim_window_s and flag t_half_peak_censored.
       t_return: right edge of the last bin with rate > return_x_baseline * baseline; if that is the last bin,
         post_stim_window_s and flag t_return_censored; if no bin exceeds, 0.0 and flag no_response.
       residual: mean rate over the bins whose center >= post_stim_window_s - residual_s, divided by baseline.
       overshoot: (baseline - min rate over bins after t_return) / baseline, floored at 0.0; NaN with flag
         overshoot_undefined when t_return is censored or no bin follows it.
     When baseline == 0.0: t_return, residual and overshoot are NaN and flag baseline_zero is True; t_peak,
     peak_rate and t_half_peak are still computed (half-peak threshold then = half_peak_frac * peak_rate).
     NaN means not computed (SPEC "Nulls"); censoring never produces NaN.
     Flags dict always has every key: t_half_peak_censored, t_return_censored, no_response,
     overshoot_undefined, baseline_zero.
   - unit_measures(spike_times_s, onsets_s, params) -> tuple[dict, dict]: the whole chain for one unit over
     one set of trials (the half, later): pre_counts -> baseline_hz -> latencies -> bin_counts -> psth_rate ->
     recovery_measures; adds baseline_hz and baseline_variance_hz2 to the values dict.

3. Generator, in synthetic.py (make_tables stays byte-identical):
   - exponential_recovery(baseline_hz, peak_hz, tau_s, dip_hz=0.0, dip_s=0.0) -> Callable[[np.ndarray],
     np.ndarray]: rate(t) = baseline + peak * exp(-t / tau) for t >= 0, minus dip_hz for
     3 * tau <= t < 3 * tau + dip_s, floored at 0.
   - make_spike_trains(rate_fns, n_trials, params, isi_s, seed) -> tuple[list[np.ndarray], np.ndarray]:
     onsets at isi_s * (k + 1) for k in range(n_trials) (so the first pre-window exists); for each unit,
     an inhomogeneous Poisson train on a 1 ms grid over [0, onsets[-1] + post_stim_window_s + 1]: rate =
     the unit's rate_fn(latency) inside each post-stimulus window (latency from onset + load_duration_s),
     the unit's baseline (rate_fn evaluated at t -> inf, i.e. rate_fn(np.array([1e9]))) elsewhere; counts
     ~ Poisson(rate * dt), spike times uniform within the step; sorted float seconds. numpy default_rng(seed).

4. tests/test_measures.py, seeds fixed, each test under 2 s:
   - test_effective_edges_end_at_window: for post_stim_window_s=2.0 the last edge == 2.0, widths > 0, first
     edge == 0.003.
   - test_params_roundtrip_and_fingerprint: from_dict(to_dict()) == params; the default fingerprint for
     post_stim_window_s=2.0 pinned as a literal in the test (compute once, paste it).
   - test_params_validation: five bad inputs, each raises ValueError naming the field.
   - test_psth_constant_rate: rate_fn constant 10 Hz, 300 trials: overall mean of psth_rate within 5% of 10.
   - test_baseline_matches_generator: baseline 5 Hz, 200 trials: baseline_hz within 10% of 5.0;
     baseline_variance_hz2 within 30% of 5.0 / pre_stim_window_s (Poisson: variance of a 1 s count rate
     equals the rate).
   - test_t_return_orders_with_tau: four units, taus 0.05, 0.1, 0.2, 0.4, baseline 5, peak 100, 200 trials:
     t_return and t_half_peak strictly increasing in tau; no flags set.
   - test_peak_rate_orders_with_amplitude: peaks 20, 50, 100 at tau 0.1: peak_rate strictly increasing.
   - test_censoring_is_not_null: tau 5.0, peak 100, window 2.0: t_return == 2.0, t_return_censored True,
     no NaN among t_return, t_peak, peak_rate.
   - test_no_response: peak 0 at baseline 5: t_return == 0.0, no_response True.
   - test_zero_baseline_gives_null: rate_fn with baseline 0 and peak 50: baseline_hz == 0.0, t_return and
     residual and overshoot NaN, baseline_zero True, peak_rate > 0.
   - test_overshoot_detected: dip_hz 5 (to zero) for dip_s 0.5 at baseline 5, tau 0.1, 300 trials:
     overshoot > 0.5; the same unit without dip: overshoot < 0.25.
   - test_unit_measures_matches_pieces: unit_measures equals the hand-chained calls on one unit.

5. Housekeeping: add "measures" to PACKAGE_MODULES in tests/test_style.py. GLOSSARY.md: update
   "PSTH-based measure" to name `measures.recovery_measures` and the censoring and zero-baseline rules; update
   "Baseline" to say the pre-stimulus window is `measures.AnalysisParams.pre_stim_window_s`, 1.0 s default;
   add "Analysis parameters (`measures.AnalysisParams`)", "Baseline variance (`baseline_variance_hz2`)",
   "Overshoot", "Time zero (load end)". CHANGELOG.md Unreleased: "measures.py: PSTH recovery measures from
   spike times (t_peak, peak_rate, t_half_peak, t_return, residual, overshoot, baseline variance), pure
   functions; synthetic spike-train generator; not yet wired into rrb-evaluate." No SPEC, METHOD, FROZEN or
   version changes in this step.

6. Limits: no file over 300 lines; if measures.py would exceed it, move AnalysisParams and the binning
   functions (effective edges, trial_latencies, pre_counts, bin_counts, psth_rate) to psth.py and add "psth" to
   PACKAGE_MODULES. Google docstrings on every public function and class. No names matching the A/B pattern.
   Ruff clean. Run the full suite; everything passes, including test_frozen.

Report: the final function list per file with line counts, the pinned fingerprint, and every place where
gate1.py overrode a default.
