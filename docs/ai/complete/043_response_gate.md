Task: the response gate for t_half_excess is computed per trial. This changes two frozen functions
(excess.excess_measures, measures.unit_measures). That is intended: record it under 0.2.0 and amend (step 7).

Why: the gate compares total excess spikes with sqrt(N), which treats the baseline as known and the unit
as Poisson. Measured on 1000 simulated units with no response at all (5 Hz, 10 trials): the gate passes
13.3% of Poisson units and 29.8% of units that fire in bursts. The version below passes 3.9% and 5.3%.
Only t_half_excess changes; every other measure is bit-identical.

1. excess.py: replace excess_measures with this, unchanged:

```python
@frozen("SPEC measures computed by the benchmark")
def excess_measures(
    latencies: Sequence[np.ndarray],
    pre_counts: Sequence[int] | np.ndarray,
    params: AnalysisParams,
) -> tuple[dict[str, float], dict[str, bool]]:
    """Compute bin-free excess-spike recovery measures from per-trial latency arrays.

    For an exponential recovery with time constant ``tau`` and a window much longer than
    ``tau``, ``t_half_excess`` estimates ``tau * ln 2``. The response gate works on one
    number per trial, ``d_i = post_i - (post_stim_window_s / pre_stim_window_s) * pre_i``:
    ``t_half_excess`` is computed only when ``sum(d) > min_excess_z * sqrt(n) * sd(d)``
    (``sd`` with ``ddof=1``), so a unit that fires in bursts or drifts between trials
    is held to its own trial-to-trial spread.

    Args:
        latencies: Sequence of per-trial 1D latency arrays in ``[0, post_stim_window_s)``
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
    win = float(params.post_stim_window_s)
    base = float(np.sum(pre) / (n * params.pre_stim_window_s))
    excess_total = float(n_spikes - base * n * win)
    excess_per_trial = float(excess_total / n)

    post = np.asarray([len(lat) for lat in latencies], dtype=float)
    per_trial = post - (win / params.pre_stim_window_s) * pre
    spread = float(np.std(per_trial, ddof=1)) if n >= 2 else 0.0
    if n < 2:
        responds = False
    elif spread > 0.0:
        responds = excess_total > params.min_excess_z * math.sqrt(n) * spread
    else:
        responds = excess_total > 0.0

    if responds:
        k = np.arange(1, n_spikes + 1, dtype=float)
        cum_k = k - base * n * pooled
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

2. measures.unit_measures: the call becomes excess_measures(lats, pre, params). Same change in
   tests/test_measures.py::test_unit_measures_matches_pieces.

3. tests/test_excess.py: add `from recovery_reliability_benchmark.excess import excess_measures` and
   append these tests unchanged. Existing tests in this file stay as they are.

```python
def _latencies_with_counts(counts: Sequence[int]) -> list[np.ndarray]:
    return [np.linspace(0.1, 0.5, int(c)) for c in counts]


def test_gate_uses_trial_to_trial_spread() -> None:
    params = AnalysisParams(post_stim_window_s=2.0)

    _values, flags = excess_measures(_latencies_with_counts([3, 3, 3, 3]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is False

    values, flags = excess_measures(_latencies_with_counts([4, 0, 4, 0]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is True
    assert math.isnan(values["t_half_excess"])
    assert values["excess_per_trial"] == 2.0

    values, flags = excess_measures(_latencies_with_counts([5, 4, 5, 4]), [1, 1, 1, 1], params)
    assert flags["no_excess"] is False
    assert values["excess_per_trial"] == 2.5

    _values, flags = excess_measures(_latencies_with_counts([0, 0, 0, 0]), [0, 0, 0, 0], params)
    assert flags["no_excess"] is True

    with pytest.raises(ValueError, match="pre_counts has 3 trials, latencies has 4"):
        excess_measures(_latencies_with_counts([1, 1, 1, 1]), [0, 0, 0], params)


@pytest.mark.parametrize("burst_max", [1, 5])
def test_gate_pass_rate_without_response(burst_max: int) -> None:
    params = AnalysisParams(post_stim_window_s=2.0)
    onsets = 5.0 * (np.arange(10) + 1)
    rng = np.random.default_rng(7)
    n_units, n_pass = 1000, 0
    for _ in range(n_units):
        n_events = int(rng.poisson(5.0 * 56.0 * 2.0 / (1 + burst_max)))
        events = rng.uniform(0.0, 56.0, n_events)
        sizes = rng.integers(1, burst_max + 1, n_events)
        spikes = np.sort(np.repeat(events, sizes) + rng.uniform(0.0, 0.02, int(sizes.sum())))
        _values, flags = unit_measures(spikes, onsets, params)
        n_pass += not flags["no_excess"]
    assert n_pass / n_units < 0.08
```

4. Run `python scripts/spikes_path_checks.py`. Only the t_half_excess rows of docs/spikes_path_checks.json
   change. In tests/test_spikes_path_checks.py, EXPECTED_T_HALF_EXCESS becomes:
     "strong_20": (0.968, 0.966, 28.1),
     "strong_40": (0.985, 0.985, 29.5),
     "weak_20": (0.696, 0.788, 16.1),
     "weak_40": (0.878, 0.880, 20.1),
     "sparse_20": (0.807, 0.824, 16.3),
     "sparse_40": (0.859, 0.854, 19.4),
   EXPECTED_OTHER_MEASURES does not change.

5. Other pinned values:
   - tests/test_run_spikes.py::test_reference_row_on_example: t_half_excess n_units is 28 (was 29).
   - README.md example table, first row becomes
     | t_half_excess | 0.976 | [0.948, 0.989] | 0.364 | 29 | 3.08 | 1.05 | — |
     The other three rows do not change.
   - tests/test_docs.py::test_spikes_path_checks_numbers_match_docs: weak_40 and sparse_40 no longer round
     to the same value. Delete the equality assertion and replace the "at 40 trials" assertion and the
     expected_spec_decimals set with:

```python
    assert (
        f"at 40 trials the last two reach {w40['split_half_corrected']:.2f} "
        f"and {sp40['split_half_corrected']:.2f}"
    ) in spec_section

    expected_spec_decimals = {
        f"{s20['split_half_corrected']:.2f}",
        f"{w20['split_half_corrected']:.2f}",
        f"{sp20['split_half_corrected']:.2f}",
        f"{w40['split_half_corrected']:.2f}",
        f"{sp40['split_half_corrected']:.2f}",
    }
    assert set(re.findall(r"\b\d+\.\d+\b", spec_section)) == expected_spec_decimals
```

6. Docs:
   - SPEC.md, replace the sentence that starts "When `E(W) <= min_excess_z * sqrt(max(N(W), 1))`" with:
     The response gate uses one number per trial, `d_i = post_i - (W / pre_stim_window_s) * pre_i`: the
     spikes of trial `i` in `[0, W)` minus its pre-stimulus count scaled to the same duration, so
     `sum(d) = E(W)`. When `E(W) <= min_excess_z * sqrt(n) * sd(d)` (sample standard deviation over the
     `n` trials; when `sd(d)` is zero, `E(W) <= 0`), `t_half_excess` is `NaN` with flag `no_excess`. A
     unit is held to its own trial-to-trial spread, so bursting or drift between trials does not pass as
     a response.
   - SPEC.md "What conformance guarantees on the spikes path": "strong responses reach 0.97 with 28 of 30
     units scored; weak responses reach 0.70 with 16 of 30; sparse firing reaches 0.81 with 16 of 30; at
     40 trials the last two reach 0.88 and 0.86."
   - METHOD.md "Split-half on pooled measures": "`t_half_excess` reads 0.09 low (0.70 against 0.79 at 20
     trials)". The rest of that sentence does not change.
   - GLOSSARY.md `t_half_excess`: the last condition becomes "`NaN` with flag `no_excess` when
     `excess_total <= min_excess_z * sqrt(n) * sd(d)`, where `d_i = post_i - (post_stim_window_s /
     pre_stim_window_s) * pre_i` is one number per trial (response gate)."
   - `grep -rn "sqrt(max" --include="*.md" --include="*.py" .` returns nothing outside docs/ai/.

7. CHANGELOG.md under 0.2.0: "Frozen: excess_measures takes per-trial pre-stimulus counts and gates
   t_half_excess on the trial-to-trial spread of per-trial excess (sum(d) > min_excess_z * sqrt(n) *
   sd(d)) instead of sqrt(N); unit_measures passes the counts." Then run
   `python scripts/freeze.py --amend`.

Do not change seeds, trial counts, bounds or expected values. Every number above was produced by running
this exact code. If one differs, stop and report the number you got.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass (278 tests). Report: the suite count, the six t_half_excess rows of docs/spikes_path_checks.json, and
the output of the grep in step 6.
