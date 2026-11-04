# Recovery Reliability Benchmark

## The within-session reliability ceiling: method

**Version 1.0**
Reference implementation: `src/recovery_reliability_benchmark/evaluate.py` (planned; not yet in the repository)

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

Input: a conforming dataset (MD-1 through MD-6), one measure column, one condition.

**Step 1. Condition-centering.** For each condition, subtract the mean of the measure over all unit-trial pairs in that condition. Run with and without; report both.

**Step 2. Partition.** Within each unit-condition group, split trials into halves A and B.

- `odd_even` (default): even trial indices to A, odd to B.
- `random`: random partition, repeated `n_splits` times.

**Step 3. Aggregate.** For each unit u, take the mean of the measure over its half-A trials to give x_A[u], and over its half-B trials to give x_B[u].

**Step 4. Correlate.** Pearson r between x_A and x_B across units.

**Step 5. Correct for length.** Spearman-Brown with k = 2:

    rho = 2r / (1 + r)

**Step 6.** Under `random`, repeat steps 2 to 5 `n_splits` times and report median with interquartile range.

**Edge cases.** With an odd trial count one half carries one extra trial; record it. If r <= 0 the Spearman-Brown correction is not meaningful and diverges as r approaches -1, so report the ceiling as 0.0 with the raw r alongside and a flag. A non-positive split-half correlation means there is no reliable between-unit variance to measure.

---

## 4. Condition-centering

Without centering, variance between conditions inflates the apparent reliability of the measure itself. A measure that only tracks which condition was delivered will produce a high uncentered ceiling while carrying no information about units.

Only the centered figure is comparable to a centered cross-session result. Both are reported so the gap is visible. On the fs369 pilot the uncentered ceiling was 0.779 and the centered ceiling 0.76.

---

## 5. Controls

### 5.1 Synthetic positive control

Generate data with a known reliability and confirm the pipeline recovers it.

For a target full-length reliability rho across n trials, draw per-unit true values T from N(0, 1) and per-trial errors from N(0, sigma squared) with:

    sigma^2 = n * (1 - rho) / rho

Run the synthetic data through the identical path: contract validation, centering, partition, correlation, correction.

**Pass:** |recovered - injected| <= tolerance, default 0.05.
**Fail:** the pipeline has a defect and every other number in the run is void. This control is evaluated first for that reason.

### 5.2 Label-permutation null

Permute unit identity within each condition and rerun the identical code path. This is a flag on the same function rather than a separate routine, because a null that executes different code tests nothing.

**Pass:** median corrected correlation at or near zero, and the 95th percentile across permutations below the observed ceiling.
**Fail:** the observed ceiling is reachable by shuffled data and carries no information.

Default `n_perm` = 1000.

### 5.3 Independence accounting

Not a statistic. A census reporting counts at every level, in order: preparations, sessions, units, conditions, trials. The reported n is stated explicitly alongside what else could have been counted.

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
| `split_mode` | `odd_even` | Partition rule. `random` available. |
| `n_splits` | 100 | Repetitions under `random`. Ignored under `odd_even`. |
| `center` | both | Centered and uncentered both reported. |
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

