Task: no measure counts spikes in the first 3 ms after the load. This changes frozen items
(AnalysisParams.to_dict and fingerprint through the new field, DEFAULT_ANALYSIS_FINGERPRINT_2S,
measures.trial_latencies, excess.excess_measures). That is intended: record it under 0.2.0 and amend (step 8).

Why: the binned measures start at 3 ms (first bin edge 0.003 s), but t_half_excess, excess_per_trial and
spikes_per_trial count from 0 ms, so stimulation artifact that a spike sorter reports as spikes lands in
the two lead measures. One artifact spike per trial at 1 ms adds exactly 1.0 to excess_per_trial today.

1. analysis.AnalysisParams: new last field `artifact_blank_s: float = 0.003`. In __post_init__, after the
   min_excess_z check:

```python
if not (0.0 <= self.artifact_blank_s < self.post_stim_window_s):
    raise ValueError(f"artifact_blank_s must be in [0, post_stim_window_s), got {self.artifact_blank_s}.")
if edges[0] < self.artifact_blank_s:
    raise ValueError(
        f"bin_edges_s must start at or after artifact_blank_s ({self.artifact_blank_s}), got {edges[0]}."
    )
```

   Class docstring: spikes in the first artifact_blank_s seconds after the load end are not counted.

2. measures.trial_latencies: latencies are kept in [artifact_blank_s, post_stim_window_s), still measured
   from t0 = onset + load_duration_s. The one changed line:
     i0, i1 = np.searchsorted(spikes, [t0 + params.artifact_blank_s, t0 + win], side="left")
   Update its docstring and the unit_measures docstring from [0, post_stim_window_s) to
   [artifact_blank_s, post_stim_window_s).

3. excess.py: replace excess_measures with this, unchanged. The counted duration is
   post_stim_window_s - artifact_blank_s, and the running excess subtracts the blank.

```python
@frozen("SPEC measures computed by the benchmark")
def excess_measures(
    latencies: Sequence[np.ndarray],
    pre_counts: Sequence[int] | np.ndarray,
    params: AnalysisParams,
) -> tuple[dict[str, float], dict[str, bool]]:
    """Compute bin-free excess-spike recovery measures from per-trial latency arrays.

    Spikes are counted over ``[artifact_blank_s, post_stim_window_s)``, a duration of
    ``counted_s = post_stim_window_s - artifact_blank_s``. For an exponential recovery with
    time constant ``tau`` and a window much longer than ``tau``, ``t_half_excess`` estimates
    ``artifact_blank_s + tau * ln 2``. The response gate works on one number per trial,
    ``d_i = post_i - (counted_s / pre_stim_window_s) * pre_i``:
    ``t_half_excess`` is computed only when ``sum(d) > min_excess_z * sqrt(n) * sd(d)``
    (``sd`` with ``ddof=1``), so a unit that fires in bursts or drifts between trials
    is held to its own trial-to-trial spread.

    Args:
        latencies: Sequence of per-trial 1D latency arrays in ``[artifact_blank_s, post_stim_window_s)``
            from ``trial_latencies`` for one unit and one set of trials.
        pre_counts: Per-trial pre-stimulus spike counts from ``pre_counts`` for the same trials.
        params: Analysis parameters defining the two windows and ``min_excess_z``.

    Returns:
        Tuple of ``(values, flags)`` dictionaries with ``t_half_excess`` and
        ``excess_per_trial`` in ``values`` and ``no_excess`` in ``flags``.

    Raises:
        ValueError: If ``pre_counts`` and ``latencies`` differ in length.
    """
    n = len(latencies)
    nan = float("nan")
    if n == 0:
        return {"t_half_excess": nan, "excess_per_trial": nan}, {"no_excess": True}
    pre = np.asarray(pre_counts, dtype=float)
    if len(pre) != n:
        raise ValueError(f"pre_counts has {len(pre)} trials, latencies has {n}.")

    pooled = (
        np.sort(np.concatenate([np.asarray(lat, dtype=float) for lat in latencies]))
        if any(len(lat) > 0 for lat in latencies)
        else np.empty(0, dtype=float)
    )
    n_spikes = len(pooled)
    blank = float(params.artifact_blank_s)
    counted_s = float(params.post_stim_window_s) - blank
    base = float(np.sum(pre) / (n * params.pre_stim_window_s))
    excess_total = float(n_spikes - base * n * counted_s)
    excess_per_trial = float(excess_total / n)

    post = np.asarray([len(lat) for lat in latencies], dtype=float)
    per_trial = post - (counted_s / params.pre_stim_window_s) * pre
    spread = float(np.std(per_trial, ddof=1)) if n >= 2 else 0.0
    if n < 2:
        responds = False
    elif spread > 0.0:
        responds = excess_total > params.min_excess_z * math.sqrt(n) * spread
    else:
        responds = excess_total > 0.0

    if responds:
        k = np.arange(1, n_spikes + 1, dtype=float)
        cum_k = k - base * n * (pooled - blank)
        first_idx = int(np.flatnonzero(cum_k >= 0.5 * excess_total)[0])
        t_half_excess = float(pooled[first_idx])
    else:
        t_half_excess = nan

    values = {
        "t_half_excess": t_half_excess,
        "excess_per_trial": excess_per_trial,
    }
    flags = {
        "no_excess": not responds,
    }
    return values, flags
```

4. Tests. Do not change seeds, trial counts or bounds; if a value differs, stop and report it.
   - tests/test_measures.py: PINNED_DEFAULT_FINGERPRINT_2S =
     "95ba4e054c0ab9813b16f2629a9e6d679afe71691aea711b0f635ccd8106e9f0". If your fingerprint differs, the
     field name or default differs from step 1: stop and report. Append to test_params_validation:

```python
with pytest.raises(ValueError, match="artifact_blank_s"):
    AnalysisParams(post_stim_window_s=2.0, artifact_blank_s=-0.001)
with pytest.raises(ValueError, match="artifact_blank_s"):
    AnalysisParams(post_stim_window_s=2.0, artifact_blank_s=2.0)
with pytest.raises(ValueError, match="bin_edges_s must start at or after artifact_blank_s"):
    AnalysisParams(post_stim_window_s=2.0, bin_edges_s=(0.0, 0.1, 1.0))
assert AnalysisParams(post_stim_window_s=2.0).artifact_blank_s == 0.003
assert (
    AnalysisParams(post_stim_window_s=2.0, artifact_blank_s=0.0, bin_edges_s=(0.0, 0.1, 1.0)).bin_edges_s[0]
    == 0.0
)
```

   - tests/test_excess.py:
     - test_half_excess_matches_theory expects
       pytest.approx(params.artifact_blank_s + tau * math.log(2.0), rel=0.20).
     - test_bin_edges_do_not_matter: linear edges become np.arange(0.1, 2.01, 0.1).
     - test_gate_uses_trial_to_trial_spread, third case: excess_per_trial == pytest.approx(4.5 - 1.997).
     - append unchanged:

```python
def test_artifact_blank_drops_early_spikes() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    rate_fn = exponential_recovery(baseline_hz=5.0, peak_hz=100.0, tau_s=0.15)
    trains, onsets = make_spike_trains([rate_fn], n_trials=20, params=params, isi_s=5.0, seed=0)
    with_artifact = np.sort(np.concatenate([trains[0], onsets + 0.001]))

    clean, _ = unit_measures(trains[0], onsets, params)
    dirty, _ = unit_measures(with_artifact, onsets, params)
    for key in ("t_half_excess", "excess_per_trial", "spikes_per_trial", "peak_rate", "t_return"):
        assert dirty[key] == clean[key]

    no_blank = AnalysisParams(post_stim_window_s=2.0, artifact_blank_s=0.0)
    clean_no_blank, _ = unit_measures(trains[0], onsets, no_blank)
    dirty_no_blank, _ = unit_measures(with_artifact, onsets, no_blank)
    assert dirty_no_blank["spikes_per_trial"] == clean_no_blank["spikes_per_trial"] + 1.0
    assert dirty_no_blank["excess_per_trial"] == pytest.approx(clean_no_blank["excess_per_trial"] + 1.0)
    assert dirty_no_blank["t_half_excess"] < clean_no_blank["t_half_excess"]
```

   - tests/test_spikes.py::test_spikes_per_trial_matches_tables_path, seed None: the hand-made spikes go
     at int(onset_ns) + 500_000 * (2 * idx + 1), which is 0.5, 1.5, 2.5, 3.5, 4.5 ms after onset for the
     five units, and the two u00 assertions become:

```python
        assert params.artifact_blank_s == 0.003
        for unit_id, expected in (("u00", 0.0), ("u02", 0.0), ("u03", 1.0), ("u04", 1.0)):
            assert float(halves_spikes.loc[(unit_id, "baseline"), "spikes_per_trial_odd"]) == expected
            assert float(halves_spikes.loc[(unit_id, "baseline"), "spikes_per_trial_even"]) == expected
```

   - tests/test_sensitivity.py::test_run_reports_sensitivity: the pinned line starts
     "  sensitivity control|slowed: median|z|=3.27".
   - tests/test_run_spikes.py::test_reference_row_on_example: n_units stays 28.

5. Run `python examples/make_examples.py`. Only examples/analysis.json and
   examples/two_conditions/analysis.json change (one new line, "artifact_blank_s": 0.003).

6. Run `python scripts/spikes_path_checks.py`. In tests/test_spikes_path_checks.py:
     EXPECTED_T_HALF_EXCESS:
       "strong_20": (0.967, 0.965, 27.8),
       "strong_40": (0.984, 0.984, 29.4),
       "weak_20": (0.685, 0.782, 15.9),
       "weak_40": (0.871, 0.875, 19.9),
       "sparse_20": (0.807, 0.822, 16.1),
       "sparse_40": (0.848, 0.838, 19.2),
     EXPECTED_OTHER_MEASURES["excess_per_trial"]["sparse_20"]: (0.965, 0.968). Nothing else in that
     dictionary changes.

7. Docs:
   - README.md example table, first two rows:
     | t_half_excess | 0.975 | [0.946, 0.988] | 0.371 | 29 | 3.27 | 1.09 | — |
     | excess_per_trial | 0.987 | [0.972, 0.994] | 0.363 | 30 | 3.88 | 1.10 | — |
     The t_return and baseline_hz rows do not change.
   - SPEC.md "Measures computed by the benchmark":
     - the opening sentence also defines "artifact blank `B = artifact_blank_s`";
     - excess_per_trial, peak_rate and spikes_per_trial rows say `[B, W)` instead of `[0, W)`;
     - the formula block becomes
           N(t) = spikes over all n trials with latency in [B, t]
           E(t) = N(t) - b * n * (t - B)
           t_half_excess = smallest t with E(t) >= E(W) / 2
       followed by: "Spikes in the first `B` seconds after the load (default 0.003 s) are not counted by
       any measure: stimulation artifact lands there. `bin_edges_s` must start at or after `B`. For an
       exponential recovery with time constant `tau`, `t_half_excess` estimates `B + tau * ln 2`."
     - the response gate sentence uses `d_i = post_i - ((W - B) / pre_stim_window_s) * pre_i` and "the
       spikes of trial `i` in `[B, W)`".
   - SPEC.md "What conformance guarantees on the spikes path": "strong responses reach 0.97 with 28 of 30
     units scored; weak responses reach 0.69 with 16 of 30; sparse firing reaches 0.81 with 16 of 30; at
     40 trials the last two reach 0.87 and 0.85."
   - METHOD.md "Split-half on pooled measures": "`t_half_excess` reads 0.09 low (0.69 against 0.78 at 20
     trials)". In tests/test_docs.py::test_spikes_path_checks_numbers_match_docs compute the gap from the
     two printed values so the sentence adds up:
       weak_gap = round(w20["test_retest"], 2) - round(w20["split_half_corrected"], 2)
   - GLOSSARY.md: new entry "Artifact blank (`artifact_blank_s`)"; "Excess spikes", "`t_half_excess`"
     (running count `k - baseline * n * (pooled[k - 1] - artifact_blank_s)`, estimates
     `artifact_blank_s + tau * ln 2`, gate ratio `(post_stim_window_s - artifact_blank_s) /
     pre_stim_window_s`), "`excess_per_trial`" and "Spikes per trial" say
     `[artifact_blank_s, post_stim_window_s)`; "Analysis parameters" lists `artifact_blank_s`.
   - frozen/README.md: the DEFAULT_ANALYSIS_FINGERPRINT_2S row shows the new value.
   - `grep -rn "2fe0111e" --include="*.md" --include="*.py" --include="*.json" .` returns nothing
     outside docs/ai/.

8. CHANGELOG.md under 0.2.0: "Frozen: AnalysisParams gains artifact_blank_s (default 0.003 s);
   trial_latencies keeps latencies in [artifact_blank_s, post_stim_window_s); excess_measures counts over
   post_stim_window_s - artifact_blank_s; DEFAULT_ANALYSIS_FINGERPRINT_2S changes with the new field."
   Then run `python scripts/freeze.py --amend`.

Every number above was produced by running this exact code on the repo after prompt 043.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass (279 tests). Report: the suite count, the fingerprint, the six t_half_excess rows of
docs/spikes_path_checks.json, and the output of the grep in step 7.
