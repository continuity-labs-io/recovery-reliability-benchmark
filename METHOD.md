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

Not a scalar. For one session and one condition, the measure is computed per recording unit, producing a **vector indexed by unit**. That vector is the measurement.

The correlation therefore runs **across units**, not across trials. Between-unit variance is the signal. If every unit returned the same value there would be nothing to correlate and the method would be undefined, which is also why section 4 matters.

---

## 3. Procedure

Input: a conforming dataset (MD-1 through MD-6), one or more measure columns, and the evaluated conditions identified by `validate()`.

**Step 1. Partition.** Within each `(unit_id, condition)` group in the evaluated conditions, sort trials by `trial_index` and rank them `k = 0, 1, 2, ...` within the group (not by global `trial_index` parity).

- `odd_even` (default, implemented in v1): even `k` go to half A, odd `k` go to half B.
- `random`: random partition, repeated `n_splits` times (not yet implemented in v1).

Groups where either half is empty are dropped.

**Step 2. Aggregate.** For each `(unit_id, condition)` group, take the mean of the measure over its half-A trials to give `x_A[u, c]`, and over its half-B trials to give `x_B[u, c]`, skipping nulls within each half and dropping pairs where either half-mean is `NaN`.

**Step 3. Per-condition and pooled estimates.** Two estimates are formed from the half-means:

- **Per-condition:** within each evaluated condition `c`, take the vector of pairs `(x_A[u, c], x_B[u, c])` across units `u`.
- **Pooled:** pool the pairs `(x_A[u, c], x_B[u, c])` across all evaluated conditions, both **uncentered** and **condition-centered**. Condition-centering subtracts each condition's mean over units from `x_A` and from `x_B`, within each half separately, before correlating.

**Step 4. Correlate and correct for length.** Compute Pearson `r` between the two halves (`NaN` if fewer than 3 pairs or if either half is constant) and apply the Spearman-Brown correction with `k = 2`:

    rho = 2r / (1 + r)

**Step 5. Confidence interval.** Apply the Fisher `z` transform to `r_half` using `n_eff = n_units` (not `n_pairs`: pooled pairs share units across conditions, so `n_units` is the conservative count):

    z = atanh(r)
    se = 1 / sqrt(n_eff - 3)
    r_lo = tanh(z - 1.96 * se),  r_hi = tanh(z + 1.96 * se)
    rho_ci_low  = 2 * r_lo / (1 + r_lo)  if r_lo > 0 else 0.0
    rho_ci_high = 2 * r_hi / (1 + r_hi)  if r_hi > 0 else 0.0

When `n_eff < 4` or `r` is `NaN`, both bounds are reported as `None`.

**Step 6. Trial-count standardization.** Let `n = n_trials_group` be the median over the frame's `(unit_id, condition)` groups of `n_A + n_B`. Invert Spearman-Brown to obtain the single-trial reliability `rho_1 = rho_single_trial` (`0.0` when `rho == 0`) and project it to a standard 20-trial session:

    rho_single_trial = rho / (n - (n - 1) * rho)
    rho_at_20 = 20 * rho_single_trial / (1 + 19 * rho_single_trial)

Ceilings from sessions with different trial counts are compared through `rho_single_trial` or `rho_at_20`, not through `rho`.

**Step 7. Headline rule.** When there are two or more evaluated conditions, the headline ceiling is the pooled condition-centered estimate (`pooled_centered`). When there is a single evaluated condition, the pooled and per-condition estimates coincide (Pearson correlation is shift-invariant) and the headline is the per-condition estimate of `validate()`'s `best_condition` (`per_condition`).

**Edge cases.** With an odd trial count one half carries one extra trial; record it (`odd_trials`). If `r <= 0` (or `NaN`) the Spearman-Brown correction is not meaningful and diverges as `r` approaches -1, so report the ceiling as `0.0` with the raw `r` alongside and a flag (`r_nonpositive`). A non-positive split-half correlation means there is no reliable between-unit variance to measure.

---

## 4. Condition-centering

Without centering, variance between conditions inflates the apparent reliability of the measure itself. A measure that only tracks which condition was delivered will produce a high uncentered ceiling while carrying no information about units.

In the per-condition estimate, centering subtracts one constant from every unit in that condition and cannot change the correlation, so centering is reported for the pooled estimate only. In the pooled estimate, `(unit_id, condition)` pairs share units across conditions, so `n_pairs` overstates the number of independent samples; the independence census counts distinct units alongside pairs.

Only the centered figure is comparable to a centered cross-session result. Both are reported so the gap is visible. On the fs369 pilot the uncentered ceiling was 0.779 and the centered ceiling 0.76, each the geometric mean of two sessions' within-session ceilings.

---

## 5. Controls

### 5.1 Synthetic positive control

Generate data from scratch with a known reliability and confirm the pipeline recovers it.

For a target full-length reliability `rho` across `n = 20` trials on `1000` units, draw per-unit true values `T ~ N(0, 1)` and per-trial errors `E ~ N(0, n(1 - rho) / rho)`:

    sigma^2 = n * (1 - rho) / rho

Run the synthetic data through the identical pipeline (`validate` -> `split_halves` -> `ceiling`) and require recovery within `0.05` (`|recovered - injected| <= tolerance`). The pilot's `gate1.py` used day-1 values plus noise instead; the two constructions agree in expectation.

**Pass:** `|recovered - injected| <= tolerance`, default `0.05`.
**Fail:** the pipeline has a defect and every other number in the run is void. This control is evaluated first for that reason.

### 5.2 Label-permutation null

Within each condition, permute the unit labels of half B (`*_B` and `n_B` rows) and recompute the headline ceiling through the same `ceiling()` function, rather than a separate routine, because a null that executes different code tests nothing.

**Pass:** median corrected correlation at or near zero, and the 95th percentile across permutations below the observed ceiling.
**Fail:** the observed ceiling is reachable by shuffled data and carries no information.

Default `n_perm` = 1000.

### 5.3 Independence accounting

Not a statistic. A census reporting counts at every level, in order: preparations, sessions, recordings, units, active units, conditions, evaluated conditions, trials, and median trials per unit-condition. The reported n is stated explicitly alongside what else could have been counted.

Most reported sample sizes in this literature count trials, which inflates apparent confidence by an order of magnitude or more.

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

## 8. What the number does not say

The ceiling states whether a measure can distinguish a preparation from a repeat of itself within one session. It says nothing about whether the measure repeats across days, responds to an intervention, or relates to any property of the tissue.

A high ceiling means the measure is worth testing further. A low ceiling means a cross-session result computed from that measure is uninterpretable, and that finding arrives before anything is built on top of it.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).

