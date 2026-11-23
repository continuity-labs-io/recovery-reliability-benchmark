# Replication Plan and Pass Rule

**Plan version 2.** Published in release v0.3.0 of the Recovery Reliability Benchmark, before any site was registered and before any stimulated recording was made. Results are published whether the gates pass or fail.

Plan version 1 was published in release v0.2.1 and stays on record there. Changes in version 2, made 2026-11-23:

- Four settings were added to the site plan in section 5.
- One item was added to the reporting list in section 7.
- The across-day comparison is released and frozen in v0.3.0. Sections 1 and 3 name it, and section 3 says which correlation gate 3 uses when there are two loads.

No threshold, count rule or measure changed.

This is the plan for one study. It is not part of the benchmark. The benchmark reports a reliability number, its interval and its null for any dataset and sets no bar. This plan sets a bar for the first stimulated recordings, in advance, so the bar cannot move after the results are seen. Another group may set a different bar for a different use.

## 1. What is fixed

- **Code.** Recovery Reliability Benchmark v0.3.0, SPEC v1.1. The functions and constants that score R and S are unchanged from v0.2.0. Version 0.3.0 adds the across-day comparison that scores D. A change to frozen code before scoring means a new version of this plan.
- **Primary measure.** `t_half_excess`. `excess_per_trial` and the reference row `baseline_hz` are reported and are not part of the pass rule.
- **Recording.** One preparation, one continuous session, two loads as two conditions, 40 stimuli per condition (20 at minimum), stimulus onsets at least 4 s apart plus the load duration, and 1 s of recording before the first stimulus.
- **Preparation.** One culture on one chip. Preparations are what gets counted. Units on one chip are not independent samples.
- **Evaluable recording.** `rrb-check` passes and at least 15 units are scored for `t_half_excess`. Other recordings are listed as not evaluable, with the reason, and count as neither pass nor fail. At 15 units and 20 trials the simulated 95% interval of the estimate is [0.49, 0.95]; at 8 units and 20 trials it is [0.22, 0.97] (docs/thresholds.md, single-trial reliability 0.2, one condition).

## 2. Three results per recording

All three are for `t_half_excess`.

- **R, reliable within the session.** The positive control passes, the headline reliability is above the 95th percentile of its shuffled null, and the headline reliability is at least 0.70.
- **S, sensitive to load.** For the two loads, `above_null` is true and `beats_reference` is true.
- **D, repeats across days.** Defined in gate 3.

## 3. Gates

1. **First recording.** Pass: R and S. If R fails, record up to two more preparations. If none of the three passes R, stop and publish. If R passes and S fails, continue on reliability and report S as failed for this pair of loads.
2. **Across preparations.** Record 9 preparations. Count the R passes among the evaluable ones and apply the count rule. S is counted the same way and reported as a separate claim.
3. **Across days.** Each preparation is recorded again 1 to 7 days later with the same electrode configuration. Units are matched by sorting both sessions with one shared set of templates. D passes for a preparation when the correlation of `t_half_excess` between the two days, across matched units, is above the 95th percentile of a shuffled-unit null and is at least 0.50. Fewer than 15 matched, scored units means not evaluable. Apply the count rule.

Second-day recordings are made for every preparation without waiting for the gate 2 result, because cultures cannot wait.

The across-day comparison is computed by `rrb-across-days` (METHOD.md, Across-day comparison). It was released and frozen in v0.3.0, after it was checked on simulated pairs of sessions with known answers and before any second-day recording was made. With two loads, the correlation is the pooled, condition-centered one. In the command's output, D is `above_null` true with `r_across_days` at least 0.50, and a preparation with `n_units` below 15 is not evaluable.

## 4. Count rule

A gate passes when enough preparations pass that chance is an unlikely explanation: a two-sided exact binomial test of the pass count against one half gives p < 0.05.

| Evaluable preparations | Passes needed |
|---|---|
| 5 or fewer | No pass possible; report as inconclusive |
| 6 | 6 |
| 7 | 7 |
| 8 | 8 |
| 9 | 8 |

Recording stops at 9 preparations or on an end date set with the host lab, whichever comes first. No preparation is added or dropped after its score is seen.

## 5. Site plan, registered before the first session

These settings depend on the host lab and its instrument. They are added to this document, with a date, before the first session at that site is recorded. A change to any of them after the first session means a new version of this plan.

- The two loads: pulse and train settings, as written in `conditions.json`.
- The order of conditions: alternating blocks or fully interleaved.
- How the stimulation electrode is chosen. It comes from a separate screening run, not from the scored session.
- Whether the chip stays on the instrument between days, and the gap between sessions.
- Whether spike times and stimulus times are made public.
- The preparation type and the spacing between stimulus onsets.
- The pulse polarity. It comes from the screening run.
- The spike sorter, its version and settings, how stimulation artifact is removed before sorting, and how units are matched across days.
- The analysis parameters, as written in `analysis.json`, with the fingerprint. One artifact blank, `artifact_blank_s`, is used for both loads and both days. It is at least as long as the longest period after a stimulus in which the sorter loses spikes at the higher load, read from the screening run.

## 6. Where the thresholds come from

0.70 and 0.50 are conventions, not derived values. 0.70 is a conventional floor for acceptable reliability, commonly attributed to Nunnally (1978). 0.50 is the lower edge of the "moderate" band for agreement between repeated measurements in Koo and Li (2016); that band was defined for the intraclass correlation and is used here as a guide for an across-day correlation. The across-day bar is lower than the within-session bar because tissue changes over days. A different bar means a new version of this plan; this version stays on record.

## 7. Reported whatever the outcome

- Every recording made under this plan, including the ones that are not evaluable.
- Every per-preparation number with its interval and its null.
- The across-day correlation as a fraction of the within-session reliability (METHOD.md).
- Every deviation from this plan.
- The sensitivity result recomputed with the artifact blank doubled. A result that changes is reported as a possible effect of stimulation artifact.

## 8. Out of scope

- Whether recovery time tracks tissue health or age.
- Other labs, instruments or preparation types.
- Drug effects.
- The binned measures (`t_return`, `t_half_peak`, `peak_rate`, `t_peak`).

## 9. Already looked at before this plan

- Thirteen spontaneous recordings from Sharf et al. 2022, scored with v0.1.0 as a test of the machinery. No stimulation.
- Simulations (docs/spikes_path_checks.md, docs/thresholds.md, tests/test_across_days.py).
- No stimulated recording has been scored with `t_half_excess`.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](../LICENSE-DOCS).
