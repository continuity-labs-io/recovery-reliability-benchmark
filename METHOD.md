# Recovery Reliability Benchmark

## The within-session reliability ceiling: method

**Version 1.0**
Reference implementation: `src/recovery_reliability_benchmark/evaluate.py`

---

## 1. What is being estimated

For a measure X decomposed into a true value T and measurement error E, with E of mean zero and uncorrelated with T:

    X = T + E
    Var(X) = Var(T) + Var(E)

Reliability is the fraction of observed variance that is true variance:

    rho = Var(T) / Var(X)

It lies in [0, 1]. This quantity is the ceiling, and the name comes from the attenuation theorem. For two measures whose true values correlate at rho_T:

    rho_XY = rho_T * sqrt(rho_XX * rho_YY)

Applying the same measure twice makes rho_XX = rho_YY = rho, and since rho_T <= 1:

    rho_XY <= rho

No observed correlation between two applications of a measure can exceed that measure's own reliability. A cross-session correlation below the ceiling is a statement about the preparation. A cross-session correlation at the ceiling is a statement about the instrument.

---

## 2. What "the measure" is

For one session and one condition, the measure is computed per recording unit, producing a **vector indexed by unit**. That vector is the measurement.

The correlation therefore runs **across units**, not across trials. Between-unit variance is the signal. If every unit returned the same value there would be nothing to correlate and the method would be undefined, which is also why section 4 matters.

When measures are computed from spike times (`--spikes` and `--analysis`), the trials of each half are pooled first and each recovery measure (`t_peak`, `peak_rate`, `t_half_peak`, `t_return`, `residual`, `overshoot`, `t_half_excess`, `excess_per_trial`, `baseline_hz`, `baseline_variance_hz2`, `spikes_per_trial`) is computed once per half rather than once per trial and averaged. One trial of a 2 Hz unit holds about four spikes in a two-second post-stimulus window, so a return-to-baseline time estimated from four spikes is dominated by discretization noise; pooling ten trials in a half yields roughly forty spikes and a well-defined recovery summary while still ending in one number per unit per half for the split-half correlation.

**Binned and bin-free measures.** The PSTH measures (`peak_rate`, `t_peak`, `t_half_peak`, `t_return`) read single time bins; with 10 trials per half the early log-spaced bins hold about one spike, so `peak_rate`, `t_peak`, and `t_half_peak` are set by chance and `t_return` moves with the bin choice. The bin-free measures (`t_half_excess` and `excess_per_trial` in `excess.py`, alongside `spikes_per_trial`) act directly on the sorted running post-stimulus spike count relative to baseline and do not depend on `bin_edges_s`.

---

## 3. Procedure

Input: a conforming dataset (min-dataset-1 through min-dataset-6), one or more measure columns, and the evaluated conditions identified by `validate()`.

**Step 1. Partition.** Within each `(unit_id, condition)` group in the evaluated conditions, sort trials by `trial_index` and assign 1-based positions `1, 2, 3, ...` within the group (not by global `trial_index` parity, which can leave one half empty when conditions are interleaved or trials are excluded).

- `odd_even` (default, implemented in v1): positions `1, 3, 5, ...` go to the odd half, positions `2, 4, 6, ...` go to the even half.
- `random`: random partition, repeated `n_splits` times (not yet implemented in v1).

Groups where either half is empty are dropped.

**Step 2. Aggregate.** For each `(unit_id, condition)` group, take the mean of the measure over its odd-half trials to give `x_odd[u, c]` (`{measure}_odd`, count `n_odd`), and over its even-half trials to give `x_even[u, c]` (`{measure}_even`, count `n_even`), skipping nulls within each half and dropping pairs where either half-mean is `NaN`.

**Step 3. Per-condition and pooled estimates.** Two estimates are formed from the half-means:

- **Per-condition:** within each evaluated condition `c`, take the vector of pairs `(x_odd[u, c], x_even[u, c])` across units `u`.
- **Pooled:** pool the pairs `(x_odd[u, c], x_even[u, c])` across all evaluated conditions, both **uncentered** and **condition-centered**. Condition-centering subtracts each condition's mean over units from `x_odd` and from `x_even`, within each half separately, before correlating.

**Step 4. Correlate and correct for length.** Compute Pearson `r` between the two halves (`NaN` if fewer than 3 pairs or if either half is constant) and apply the Spearman-Brown correction with `k = 2`:

    rho = 2r / (1 + r)

**Step 5. Confidence interval.** Apply the Fisher `z` transform to `r_half` using `n_eff = n_units` (not `n_pairs`: pooled pairs share units across conditions, so `n_units` is the conservative count) and critical value `z_crit = scipy.stats.norm.ppf(0.5 + confidence / 2)` (`confidence = 0.95` by default):

    z = atanh(r)
    se = 1 / sqrt(n_eff - 3)
    r_ci_low  = tanh(z - z_crit * se),  r_ci_high = tanh(z + z_crit * se)
    rho_ci_low  = 2 * r_ci_low / (1 + r_ci_low)   if r_ci_low > 0 else 0.0
    rho_ci_high = 2 * r_ci_high / (1 + r_ci_high) if r_ci_high > 0 else 0.0

When `n_eff < 4` or `r` is `NaN`, all four bounds are reported as `None`.

**Variance components.** The report shows between-unit variance, within-unit (trial) variance and the moments estimate next to the split-half ceiling. A ceiling driven by between-unit heterogeneity shows up as large var_between relative to var_within; moments_reliability is the ANOVA-style estimate of the same quantity the split-half ceiling estimates, and the two should agree.

**Step 6. Trial-count standardization.** Let `n = n_trials_group` be the median over the frame's `(unit_id, condition)` groups of `n_odd + n_even`. Invert Spearman-Brown to obtain the single-trial reliability `rho_1 = rho_single_trial` (`0.0` when `rho == 0`) and project it to a standard 20-trial session (`REFERENCE_N_TRIALS = MD2_SHOULD = 20`):

    rho_single_trial = rho / (n - (n - 1) * rho)
    rho_at_20 = 20 * rho_single_trial / (1 + 19 * rho_single_trial)

Ceilings from sessions with different trial counts are compared through `rho_single_trial` or `rho_at_20`, not through `rho`.

**Step 7. Headline rule.** When there are two or more evaluated conditions, the headline ceiling is the pooled condition-centered estimate (`pooled_centered`). When there is a single evaluated condition, the pooled and per-condition estimates coincide (Pearson correlation is shift-invariant) and the headline is the per-condition estimate of `validate()`'s `best_condition` (`per_condition`).

**Edge cases.** With an odd trial count one half carries one extra trial; record it (`odd_trials`). When fewer than 3 pairs are available or either half is constant, `r` is `NaN` (`r_undefined = True`, `r_nonpositive = False`). When `r` is defined and `r <= 0`, the Spearman-Brown correction is not meaningful and diverges as `r` approaches -1 (`r_undefined = False`, `r_nonpositive = True`). In JSON both cases record the ceiling `rho` as `0.0` with the raw `r_half` alongside (`null` when undefined) and the two flags distinguishing undefined from non-positive correlation; `summary.md` renders `r_undefined` as `undefined` (interval `n/a`, note `no variation across units`). A non-positive split-half correlation means there is no reliable between-unit variance to measure.

---

## Split-half on pooled measures

On the spikes path (`spikes.py`), each half's measure is computed once from that half's pooled trials rather than averaged over per-trial estimates, and the Spearman-Brown correction (`2r / (1 + r)`) is applied to the odd-versus-even correlation across units just as on the tables path. Checked against the test-retest correlation between two independent sessions of the same units (`docs/spikes_path_checks.json`): within 0.01 for strong responses on every measure; for weak responses `t_half_excess` reads 0.09 low (0.69 against 0.78 at 20 trials), so the correction errs low for the lead measure; other measures stay within about 0.02.

---

## 4. Condition-centering

Without centering, variance between conditions inflates the apparent reliability of the measure itself. A measure that only tracks which condition was delivered will produce a high uncentered ceiling while carrying no information about units.

In the per-condition estimate, centering subtracts one constant from every unit in that condition and cannot change the correlation, so centering is reported for the pooled estimate only. In the pooled estimate, `(unit_id, condition)` pairs share units across conditions, so `n_pairs` overstates the number of independent samples; the independence census counts distinct units alongside pairs.

Only the centered figure is comparable to a centered cross-session result. Both are reported so the gap is visible. On the [FinalSpark](https://finalspark.com/) (`fs369`) pilot the uncentered ceiling was 0.779 and the centered ceiling 0.76, each the geometric mean of two sessions' within-session ceilings.

---

## 5. Controls

### 5.1 Synthetic positive control

Generate data from scratch with a known reliability and confirm the pipeline recovers it.

For a target full-length reliability `rho` across `n = 20` trials on `1000` units, draw per-unit true values `T ~ N(0, 1)` and per-trial errors `E ~ N(0, n(1 - rho) / rho)`:

    sigma^2 = n * (1 - rho) / rho

Run the synthetic data through the identical pipeline (`validate` -> `split_halves` -> `reliability_ceiling`) and require recovery within `0.05` (`|recovered - injected| <= tolerance`). The pilot analysis built its control from day-1 values plus noise; the two constructions agree in expectation.

**Pass:** `|recovered - injected| <= tolerance`, default `0.05`.
**Fail:** the pipeline has a defect and every other number in the run is void. This control is evaluated first for that reason.

### 5.2 Label-permutation null

Within each condition, permute the unit labels of the even half (`*_even` and `n_even` columns) and recompute the headline ceiling through the same `reliability_ceiling()` function, rather than a separate routine, because a null that executes different code tests nothing.

**Pass:** median corrected correlation at or near zero, and the 95th percentile across permutations below the observed ceiling.
**Fail:** the observed ceiling is reachable by shuffled data and carries no information.

Default `n_perm` = 1000.

### 5.3 Independence accounting

This is a census that reports counts at every level, in order: 
- preparations
- sessions
- recordings
- units
- active units
- conditions
- evaluated conditions
- trials
- median trials per unit-condition

The reported n is stated explicitly alongside what else could have been counted.

---

## 6. Assumptions, and where they fail here

**Parallel halves.** Both halves are assumed to measure the same quantity with equal reliability. This fails under within-session drift. Odd/even partitioning is strictly balanced across the session and is therefore more robust to monotonic drift than random partitioning, which is balanced only in expectation. This is why `odd_even` is the default.

**Error uncorrelated with true value.** Fails if noisier units systematically carry different measure values. Untested in any dataset analyzed so far, and currently an open item.

**Exchangeable units.** Classical test theory assumes units are independent samples. Nineteen electrodes in a single culture are emphatically not. The independence census reports this; the method does not correct for it. This is a limitation of the estimate, not of the implementation, and any reported confidence interval should be read with it in mind.

---

## 7. Parameters

| Parameter | Default | Effect |
|---|---|---|
| `split_mode` | `odd_even` | Partition rule. v1 implements `odd_even` only (`random` is not yet implemented). |
| `n_splits` | 100 | Repetitions under `random` (not yet implemented in v1). Ignored under `odd_even`. |
| `center` | both | Centered and uncentered both reported on the pooled estimate. |
| `n_perm` | 1000 | Permutations for the null. |
| `injected_r` | 0.85 | Target reliability for the positive control. |
| `tolerance` | 0.05 | Pass band for the positive control. |
| `seed` | 42 | Reported with every result. |

Every result carries the parameter set and the code version tag, so that two laboratories reporting a ceiling of 0.8 mean the same thing.

---

## How this benchmark can be gamed

Arc's Virtual Cell Challenge used a scale-sensitive perturbation discrimination score and was climbed by inflating the variance of random predictions; the split-half correlation is scale-invariant, so that attack fails, and the table lists its neighbors.

| Attack | Effect on the score | Countermeasure | Status |
|---|---|---|---|
| Variance inflation | None: Pearson r is invariant to scaling and shifting a measure | Scale-invariant score | Not applicable |
| Unit selection (drop low-variance units, keep heterogeneous ones) | Raises between-unit variance, raises the ceiling | Pre-registered inclusion rule; inclusion counts and declared exclusions in every report; variance components printed next to the ceiling | Implemented (v0.1.0) |
| Trial exclusion after seeing results | Removes noisy trials, raises the ceiling | No trial exclusion by rule; missing rows make a unit inactive; declared exclusions required; benchmark computes measures from spikes from v0.2.0 | Implemented (counts); tightened in v0.2.0 |
| Stable-but-meaningless measures (baseline firing rate) | Wins a reliability-only ranking while saying nothing about recovery | Sensitivity axis reported next to reliability, never combined; baseline firing rate as a reference row every submitted measure is compared with | Implemented (v0.2.0) |
| Submitter-chosen data or splits | Cherry-picked datasets or favorable halves | Submitted measures are scored on fixed public datasets with splits chosen by the benchmark | Documented (CONTRIBUTING.md); leaderboard planned |
| Something we have not thought of | Unknown | Adversarial review requested: open an issue titled "gaming:" with the attack and, if possible, a synthetic dataset that demonstrates it | Open |

For a measure and each sorted pair `(first, second)` of evaluated conditions (`sensitivity.py`), over the units whose odd and even halves are non-null in both conditions:

    shift_u = (second_odd + second_even) / 2 - (first_odd + first_even) / 2
    noise_u = 0.5 * sqrt((first_odd - first_even)**2 + (second_odd - second_even)**2)
    z_u     = abs(shift_u) / max(noise_u, 1e-12)

Summarized as `median_abs_z = median(z_u)`, `frac_beyond_2 = mean(z_u > 2)`, `median_shift = median(shift_u)` (signed, in the measure's units), and `n_units`. Under the shuffled null, for each unit independently its four half values are dealt at random into the four slots and `median_abs_z` and `frac_beyond_2` are recomputed `n_perm` times, reporting the 95th percentile of each and the fraction of shuffles with `median_abs_z` at or above the observed value (`above_null` is `median_abs_z > null.median_abs_z_p95`): two halves per condition give each unit's noise two degrees of freedom, so about 18% of units pass twice their noise by chance and the chance median is about 0.8. With fewer than two evaluated conditions, sensitivity is `None`; a pre-versus-post contrast is not defined for a recovery time. Reported beside reliability for every measure and the reference row (`beats_reference` is `null` when `baseline_hz` is itself requested as a measure), never merged into one score.

---

## 8. What the number does not say

The ceiling states whether a measure can distinguish a preparation from a repeat of itself within one session. It says nothing about whether the measure repeats across days, responds to an intervention, or relates to any property of the tissue.

A high ceiling means the measure is worth testing further. A low ceiling means a cross-session result computed from that measure is uninterpretable, and that finding arrives before anything is built on top of it.

On the spikes path, a low ceiling can come from too few spikes per unit rather than from the tissue. Sensitivity's per-unit noise estimate has two degrees of freedom, which is why every sensitivity value is printed beside its shuffled null.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).

