Task: a half with no spikes has no peak time. This changes one frozen function
(measures.recovery_measures). That is intended: record it under 0.2.0 and amend (step 5).
Apply after prompt 044.

Why: for a unit with no spike in the histogram, np.argmax returns bin 0, so t_peak is the center of the
first bin and t_half_peak the center of the second, in both halves. Identical made-up values in both
halves raise the reliability of the measure. Measured with 20 responding units (taus
np.geomspace(0.05, 0.5, 20), 20 trials, seed 0): adding 10 silent units moves t_peak reliability from
0.000 to 0.244 and t_half_peak from 0.289 to 0.451, with 30 units scored instead of 20.

1. measures.recovery_measures: after t_half_peak is computed and `nan = float("nan")` is defined, add

```python
    if peak_rate == 0.0:
        t_peak, t_half_peak, t_half_peak_censored = nan, nan, False
```

   peak_rate stays 0.0 and nothing else in the function changes. Docstring: when no spike falls in any
   bin, peak_rate is 0.0 and t_peak and t_half_peak are NaN.

2. tests/test_measures.py: append unchanged:

```python
def test_empty_histogram_has_no_peak_time() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    onsets = 5.0 * (np.arange(10) + 1)

    values, flags = unit_measures(np.empty(0, dtype=float), onsets, params)
    assert values["peak_rate"] == 0.0
    assert math.isnan(values["t_peak"])
    assert math.isnan(values["t_half_peak"])
    assert flags["t_half_peak_censored"] is False

    only_before_onsets = onsets - 0.5
    values, flags = unit_measures(only_before_onsets, onsets, params)
    assert values["baseline_hz"] == 1.0
    assert values["peak_rate"] == 0.0
    assert math.isnan(values["t_peak"])
    assert math.isnan(values["t_half_peak"])
    assert values["t_return"] == 0.0

    one_spike = np.asarray([onsets[3] + 0.2])
    values, _flags = unit_measures(one_spike, onsets, params)
    assert values["peak_rate"] > 0.0
    assert not math.isnan(values["t_peak"])
    assert not math.isnan(values["t_half_peak"])
```

3. tests/test_run_spikes.py: add unchanged before test_md3_scored_from_run:

```python
def test_silent_units_do_not_change_peak_time_reliability() -> None:
    taus = np.geomspace(0.05, 0.5, 20)
    results = {}
    for silent_units in (0, 10):
        units, trials, spikes, params = _build_spike_dataset(
            taus, n_trials=20, isi_s=5.0, seed=0, silent_units=silent_units
        )
        results[silent_units] = run(
            units, trials, measures=["t_peak", "t_half_peak"], spikes=spikes, analysis=params, n_perm=20
        )
    for measure in ("t_peak", "t_half_peak"):
        alone = results[0]["measures"][measure]["headline"]
        with_silent = results[10]["measures"][measure]["headline"]
        assert alone["n_units"] == with_silent["n_units"] == 20
        assert alone["rho"] == with_silent["rho"]
```

   tests/test_spikes.py: test_scored_units_excludes_silent_unit becomes:

```python
def test_scored_units_excludes_silent_unit() -> None:
    units, trials, spikes, _trains, _onsets_s, params = _build_five_unit_fixture()
    silent_row = pd.DataFrame(
        {
            "unit_id": ["u_silent"],
            "recording_id": ["rec0"],
            "session_id": ["sess0"],
            "preparation_id": ["prep0"],
        }
    )
    units_with_silent = pd.concat([units, silent_row], ignore_index=True)
    measures = ["t_return", "peak_rate", "t_peak", "t_half_peak"]
    halves, _flags = halves_from_spikes(units_with_silent, trials, spikes, params, measures)

    scored = scored_units(halves, measures)
    assert "u_silent" not in scored["t_return"]["baseline"]
    assert len(scored["t_return"]["baseline"]) == 5

    assert "u_silent" in scored["peak_rate"]["baseline"]
    assert len(scored["peak_rate"]["baseline"]) == 6

    for measure in ("t_peak", "t_half_peak"):
        assert "u_silent" not in scored[measure]["baseline"]
        assert len(scored[measure]["baseline"]) == 5
```

4. Docs:
   - SPEC.md measures table: the t_peak row adds "(`NaN` when no spike falls in any bin)"; the
     t_half_peak row reads "(censored at `W`; `NaN` when no spike falls in any bin)".
   - SPEC.md: replace the sentence "A silent unit has no baseline and is excluded." with
     "A silent unit is not scored for a measure that needs a baseline, a response or a peak (`t_return`,
     `residual`, `overshoot`, `t_half_excess`, `t_peak`, `t_half_peak`)."
   - GLOSSARY.md "Scored unit": the parenthesis that lists what yields NaN adds "a half with no spike in
     any bin yields `NaN` on `t_peak` and `t_half_peak`, while its `peak_rate` is `0.0`".

5. CHANGELOG.md under 0.2.0: "Frozen: recovery_measures returns NaN for t_peak and t_half_peak when no
   spike falls in any bin (peak_rate stays 0.0), so a silent unit is not scored for a peak time." Then
   run `python scripts/freeze.py --amend`.

Do not change seeds, trial counts or expected values. If a test fails, stop and report the numbers.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass (281 tests). No example, README table or docs/spikes_path_checks number changes, because no example
has a silent unit. Report: the suite count.
