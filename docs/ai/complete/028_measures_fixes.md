Task: close out 027_measures. Six fixes, no new features. Run the full suite after each item.

1. Remove the string "gate1" everywhere outside docs/ai/complete/. Known locations: measures.py (module
   docstring; baseline_hz, psth_rate and recovery_measures docstrings), GLOSSARY.md ("Electrode", "PSTH"),
   METHOD.md (positive-control paragraph). State each convention as the benchmark's rule, no attribution:
   - measures.py module docstring: "Pure functions on NumPy arrays in seconds. Conventions: bin time is the
     bin center for t_peak, t_half_peak and the residual window; t_return is the right edge of the last bin
     above return_x_baseline * baseline; residual is the pooled trailing rate divided by baseline; baseline
     is pooled pre-stimulus counts over the trial set."
   - GLOSSARY "Electrode": "The pilot analysis used electrodes as units."
   - GLOSSARY "PSTH": replace the `gate1.measures()` reference with `measures.psth_rate`.
   - METHOD: "The pilot analysis built its control from day-1 values plus noise; the two constructions
     agree in expectation."
   Add test_no_pilot_script_names to tests/test_style.py: "gate1" appears in no file under src/ or tests/
   (skipping __pycache__) and in no root-level .md file.

2. AnalysisParams.effective_edges, new rule: take the stored edges strictly below post_stim_window_s; if
   the gap from the last of them to the window end is less than half the width of the preceding bin, drop
   that last edge; then append the window end. Docstring: the rule, and the reason (a sliver bin has the
   fewest spikes and the noisiest rate, and it sits where t_return, residual and overshoot are read).
   to_dict() is unchanged, so PINNED_DEFAULT_FINGERPRINT_2S is unchanged; confirm. Add
   test_effective_edges_no_sliver: for the defaults at 2.0 s the last two edges are 1.612 (to three
   decimals) and 2.0, and the last bin is at least half as wide as the one before it.

3. recovery_measures, overshoot: replace the minimum over bins after t_return with the pooled rate over
   the interval after t_return: r_after = sum(rate_i * width_i) / sum(width_i) over bins with center >
   t_return; overshoot = max(0, (baseline - r_after) / baseline). Docstring reason: the minimum over bins
   is biased upward by whichever bin has the fewest spikes, so it grows with bin count and noise even when
   no dip exists; the pooled rate does not. Flags unchanged. Update GLOSSARY "Overshoot".

4. test_overshoot_detected: parametrize over seeds (70, 0). Keep baseline 5, tau 0.1, peak 50, 300
   trials; set dip_hz 5 and dip_s 1.0. With the dip: overshoot > 0.35. Without: overshoot < 0.1. Both
   seeds pass. If one does not, the measure or the edge rule is wrong: report it, do not change the seed.

5. scripts/freeze.py main(), --update branch: require the CHANGELOG "Frozen:" line only when diffs is
   non-empty. A version-only refresh (no diffs) needs only the version bump. Add
   test_update_version_only_refresh to tests/test_frozen.py: with the manifest's version string replaced
   by an older one in a temporary copy and no CHANGELOG change, the update logic succeeds; with a real
   source difference and no "Frozen:" line, it refuses. Factor the branch into a function so the test
   calls it directly rather than through a subprocess.

6. GLOSSARY.md: if an entry titled "Sensitivity." exists beside "Sensitivity axis.", delete
   "Sensitivity." The axis entry is the definition.

CHANGELOG Unreleased: "measures: bin edges never end in a sliver bin; overshoot is the pooled deficit
after return." "freeze --update: the Frozen: line is required only when a frozen item changed."
Report: the last two edges, overshoot for both seeds with and without the dip, and the suite count.
