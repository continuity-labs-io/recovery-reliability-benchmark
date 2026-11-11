Task: min-dataset-7 requires the pre-stimulus window to be clear of the previous trial's post-stimulus
window. This changes one frozen function. That is intended: record it under 0.2.0 and amend (step 6).
Requires prompt 041.

Why: check_pre_stimulus_window only requires the pre-stimulus window to fit after the previous load end, so
the 1 s baseline window may sit inside the previous trial's 2 s recovery window. Measured at 2.0 s spacing
on synthetic units: the slowest units' baseline reads 15.0 Hz against a true 13.2 and 3.0 against 1.2, and
t_half_excess for slow units reads 16% short. At 3.0 s spacing the baseline matches and t_half_excess
reads within 2%.

1. checks_spikes.check_pre_stimulus_window. The two existing checks before the loop are unchanged. Replace
   the loop over consecutive trials with this, where post_w = float(params.post_stim_window_s) and
   onsets_ns is the list of int stim_time_ns in time order (onsets_s = [t / 1e9 for t in onsets_ns]):

```python
    load_ns, post_ns, pre_ns = (int(round(x * 1e9)) for x in (load_s, post_w, pre_w))
    for i in range(1, len(onsets_ns)):
        gap_ns = onsets_ns[i] - onsets_ns[i - 1]
        available_ns = gap_ns - load_ns - post_ns
        if available_ns < pre_ns:
            available = available_ns / 1e9
            msg = (
                f"Trial {trial_indices[i]} has {available:.3f} s between the end of the previous "
                f"post-stimulus window and its onset (gap {gap_ns / 1e9:.3f} s minus load {load_s:.3f} s "
                f"minus post-stimulus window {post_w:.3f} s), requires {pre_w:.1f} s."
            )
            raise ContractViolation(Requirement.MD7, msg, found=float(available), required=pre_w)
```

   Gaps are compared in integer nanoseconds so that a gap exactly equal to the requirement is accepted
   whatever the clock origin. Update the docstring: the pre-stimulus window must start at or after the end
   of the previous post-stimulus window, so onsets are at least load_duration_s + post_stim_window_s +
   pre_stim_window_s apart.
2. contract.py, Requirement.MD7 description: replace "and fits between every previous load end and the
   next onset" with "and fits between the end of every previous post-stimulus window and the next onset".
   Same line count; contract.py is at 299 lines.
3. tests/test_spikes.py::test_pre_window_violations, tight-gap case: trial 7 onset becomes
   prev_onset_s + 1.0 + 2.0 + 0.8, and the expected message is
   "Trial 7 has 0.800 s between the end of the previous post-stimulus window and its onset (gap 3.800 s
   minus load 1.000 s minus post-stimulus window 2.000 s), requires 1.0 s." (one line), with
   found == pytest.approx(0.8) and required == 1.0. Then add this test unchanged:

```python
@pytest.mark.parametrize(
    "first_onset_ns", [1_000_000_000, 1_100_000_000, 4_700_000_001, 1_762_800_000_123_456_789]
)
def test_pre_window_spacing_boundary(first_onset_ns: int) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)

    def trials_spaced(gap_ns: int) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "trial_index": list(range(10)),
                "stim_time_ns": [first_onset_ns + k * gap_ns for k in range(10)],
                "condition": "baseline",
            }
        )

    check_pre_stimulus_window(trials_spaced(3_000_000_000), params)
    with pytest.raises(ContractViolation) as exc_info:
        check_pre_stimulus_window(trials_spaced(2_999_999_999), params)
    assert exc_info.value.requirement is Requirement.MD7
    assert (
        "Trial 1 has 1.000 s between the end of the previous post-stimulus window" in exc_info.value.message
    )
    assert "(gap 3.000 s minus load 0.000 s minus post-stimulus window 2.000 s)" in exc_info.value.message

    params_loaded = AnalysisParams(post_stim_window_s=2.0, load_duration_s=0.3)
    check_pre_stimulus_window(trials_spaced(3_300_000_000), params_loaded)
    with pytest.raises(ContractViolation):
        check_pre_stimulus_window(trials_spaced(3_299_999_999), params_loaded)
```

4. tests/test_run_spikes.py: add this test unchanged after test_md7_from_run:

```python
@pytest.mark.parametrize(("isi_s", "accepted"), [(2.0, False), (2.5, False), (2.9, False), (3.0, True)])
def test_md7_spacing_from_run(isi_s: float, accepted: bool) -> None:
    taus = np.geomspace(0.05, 0.5, 10)
    units, trials, spikes, params = _build_spike_dataset(taus, n_trials=10, isi_s=isi_s, seed=0)
    if accepted:
        res = run(units, trials, measures=["t_half_excess"], spikes=spikes, analysis=params, n_perm=20)
        assert res["status"] == "ok"
        return
    with pytest.raises(ContractViolation) as exc_info:
        run(units, trials, measures=["t_half_excess"], spikes=spikes, analysis=params, n_perm=20)
    assert exc_info.value.requirement is Requirement.MD7
    assert exc_info.value.found == pytest.approx(isi_s - 2.0)
    assert exc_info.value.required == 1.0
```

5. Docs. Every place that states the rule says the same thing:
   - SPEC.md min-dataset-7: the pre-stimulus window must start at or after the end of the previous
     trial's post-stimulus window; with the defaults, stimulus onsets are at least 3.0 s apart plus the
     load duration.
   - README.md "Run it on your recordings": after the "1.0 s of quiet before each stimulus" requirement
     add "so stimulus onsets must be at least 3.0 s apart, plus the load duration". In
     tests/test_docs.py::test_readme_example_table_matches_two_conditions assert
     f"at least {MD6_MUST + MD7_MUST:.1f} s apart" in recordings_section.
   - CONTRIBUTING.md "Protocol advice" and GLOSSARY.md where the pre-stimulus window is described.
   - scripts/adapter_template.py docstring: add a third item, "3. At least 3 s between stimulus onsets,
     plus the load duration (min-dataset-7)." and change "Read two things" to "Read three things". The
     file stays under 60 lines.
   - `grep -rn "previous load end" --include="*.md" --include="*.py" .` returns nothing outside
     docs/ai/.
6. CHANGELOG.md under 0.2.0: "Frozen: check_pre_stimulus_window requires the pre-stimulus window to start
   after the previous trial's post-stimulus window (onsets at least load + post + pre apart)." Then run
   `python scripts/freeze.py --amend`.

Do not change seeds, trial counts or expected values in the tests above. If one fails, report the numbers.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass. No example, README table or docs/spikes_path_checks number changes, because every example uses 5 s
spacing. Report: the suite count and the output of the grep in step 5.
