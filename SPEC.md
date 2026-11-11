# Recovery Reliability Benchmark

## Dataset Conformance Specification

**Version 1.1**
Status: normative
Reference implementation: `src/recovery_reliability_benchmark/contract.py`, run as `rrb-check`

The keywords MUST, MUST NOT, SHOULD and MAY are to be interpreted as in [RFC 2119](https://www.ietf.org/rfc/rfc2119.txt).

---

## 0. Scope

Version 0.x of the benchmark covers neural preparations: dissociated cultures, organotypic slices, organoids and engineered neural tissue, on any recording modality. Other tissue types are a later major version.

---

## 1. What the benchmark asks

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported. If you know of a counterexample, open an issue. The claim is meant to be checked.

The benchmark asks whether they can be. The first question, which gates every other one, is whether a recovery measure is reliable enough to distinguish a preparation from a repeat of itself.

A conforming dataset contributes rows to a public atlas. A row is keyed by (protocol fingerprint, condition, preparation): the commanded load, the condition label with its pharmacology, and the specimen. Reliability is computed per row set, and rows accumulate across laboratories.

This document defines the smallest dataset from which that question can be answered.

---

## 2. Terms

**Preparation** — one physical specimen: a culture, well, construct or slice.

**Session** — one continuous acquisition from one preparation, with no intervening medium change, incubator opening or handling event.

**Recording** — one acquisition file. A session is one continuous acquisition, so a conforming dataset has exactly one recording.

**Recording unit** — one spatially distinct channel of measurement: an electrode, ROI, well or pixel group. The unit is the axis across which the reliability correlation is computed.

**Trial** — one stimulus delivery and the recorded response that follows it. Each trial has an integer index and a stimulus onset time.

**Condition** — a stimulus parameter set. Two trials share a condition only if every stimulus parameter is equal. A condition is identified by a label; the parameters behind the label can be described with `protocol.py` and identified by the protocol fingerprint.

**Measure** — a scalar computed per unit per trial from the post-stimulus response.

**Active** — a unit is active in a trial when the dataset has a row for that unit and trial with every measure non-null.

**Evaluated condition** — a condition that satisfies the MUST thresholds of the minimum dataset requirements `min-dataset-2` and `min-dataset-3` (section 4). The computation in section 3 runs on evaluated conditions.

---

## 3. The computation this supports

Trials within one session are partitioned into two halves. The measure is computed independently on each half, giving two vectors indexed by recording unit. The two vectors are correlated across units and the result is corrected for length:

    rho_full = 2 * rho_half / (1 + rho_half)

Every requirement in section 4 follows from this procedure.

---

## 4. Minimum Dataset Requirements

| ID | Requirement | MUST | SHOULD |
|---|---|---|---|
| min-dataset-1 | Preparations, sessions and recordings present | exactly 1 of each | |
| min-dataset-2 | Trials per condition | ≥ 10 in at least one condition | ≥ 20 |
| min-dataset-3 | Recording units active in every trial of an evaluated condition | ≥ 8 | ≥ 30 |
| min-dataset-4 | Stimulus onset timestamps | present, one per trial across units, strictly increasing within a condition | |
| min-dataset-5 | Rows per unit-trial pair | exactly 1 | |
| min-dataset-6 | Post-stimulus window per trial | ≥ 2.0 s | |
| min-dataset-7 | Pre-stimulus window per trial (spikes path) | ≥ 1.0 s | |

**min-dataset-1 — Single session.**
The dataset MUST contain exactly one session from exactly one preparation, in exactly one recording. Longitudinal data is out of scope for this computation. A second recording identifier is a second acquisition and therefore a second session.

**min-dataset-2 — Repeated trials.**
At least one condition MUST contain 10 or more trials, and SHOULD contain 20 or more. A trial is counted once per distinct trial index. Below 10, the two halves are too short for the correlation to be stable.

**min-dataset-3 — Multiple recording units.**
At least one condition that satisfies min-dataset-2 MUST contain 8 or more units active in every one of its trials, and SHOULD contain 30 or more. A single unit cannot produce a correlation. A unit that is missing a trial, or carries a null measure in one, is not counted; section 15 says what a null is allowed to mean.

The MUST thresholds define when the computation is possible. They do not make a single-dataset estimate precise. For a measure with single-trial reliability 0.2, the ceiling of a 10-trial session is 0.71 and of a 20-trial session 0.83. Simulated 95% intervals of the estimate (1,000 seeds, one condition): 8 units and 10 trials, [0.00, 0.95], and 7% of such runs report exactly 0 (19% when the single-trial reliability is 0.1); 15 units and 20 trials, [0.49, 0.95]; 30 units and 20 trials, [0.67, 0.92]. Pooling three conditions at 8 units and 10 trials gives [0.10, 0.90]. Every estimate is reported with its interval and converted to a single-trial reliability so sessions with different trial counts can be compared. Full table: docs/thresholds.md.

**min-dataset-4 — Stimulus timestamps.**
The dataset MUST provide the onset time of every stimulus, on the same clock as the response data. Every unit on a preparation receives the same stimulus, so each trial MUST carry exactly one onset time and exactly one condition across all units. Onset times MUST be strictly increasing with trial index within a condition.

**min-dataset-5 — Trial-level resolution.**
The dataset MUST provide per-trial data: exactly one row per unit and trial. One row per unit is a summary statistic, which cannot be partitioned into halves; two rows for the same unit and trial count one trial twice.

**min-dataset-6 — Post-stimulus window.**
Each trial MUST carry at least 2.0 seconds of recording after stimulus onset. The submitter declares the analysis window. The declared window MUST be at least 2.0 s, and for every trial except the last it MUST fit before the next stimulus onset. The last trial has no following onset and is not checked. If the stimulus is a conditioning train of nonzero duration, the submitter MAY declare that duration; the window is then required after the train ends, which only tightens the check. This is the requirement that most often fails, because many stimulation protocols use short inter-stimulus intervals. A protocol truncating at 200 ms cannot resolve a seconds-scale return.

**min-dataset-7 — Pre-stimulus window.**
Applies when measures are computed from spikes: the declared `pre_stim_window_s` is at least 1.0 s, fits before the first onset on the recording clock, and starts at or after the end of every previous trial's post-stimulus window (`load_duration_s + post_stim_window_s` after the previous onset). The baseline is read from `[onset - pre_stim_window_s, onset)` so it is clear of the preceding recovery window; with the defaults, stimulus onsets are at least 3.0 s apart plus the load duration.

---

## 5. Conformance levels

Levels are evaluated per condition.

**Conforming.** All six MUST conditions hold for at least one condition. The dataset supports the computation.

**Fully conforming.** All MUST and all SHOULD conditions hold for at least one condition. The simulated 95% interval of the estimate narrows from [0.00, 0.95] at the MUST thresholds to [0.67, 0.92] at the SHOULD thresholds (single-trial reliability 0.2); see docs/thresholds.md.

The dataset's level is the level of its best condition. The reference implementation names that condition and lists the SHOULD thresholds it misses. A conforming dataset that is not fully conforming is still usable, and the shortfall is reported alongside the result rather than treated as disqualifying.

---

## 6. Not required

Multiple sessions. Conditioning bursts. A probe ladder. Any particular neural preparation type, species or cell source. Any particular instrument. Any particular modality: calcium imaging satisfies min-dataset-1 through min-dataset-6 as readily as an electrode array. Any aging-related metadata.

---

## 7. Optional Dataset Requirements, in order of value

| ID | Item | Why it matters |
|---|---|---|
| optional-dataset-1 | Multiple stimulus amplitudes | Permits direct evaluation of the dose-response curve and the titration rule, not only the ceiling |
| optional-dataset-2 | More than one session on the same preparation | Promotes the question from "is the measure capable" to "does it repeat" |
| optional-dataset-3 | Both stimulus polarities | Separates artifact from response |
| optional-dataset-4 | Preparation metadata: age, cell source, DIV, medium changes, handling | Medium changes are known to be material |
| optional-dataset-5 | Raw signal rather than detected events | Events cannot be un-thresholded; raw preserves every amplitude measure |

---

## 8. Format

Any. HDF5, NWB, .mat, Axion AxIS, or CSV of event times with a separate stimulus timestamp file. Conformance is defined by content, not container.

The reference implementation accepts the two tables in section 9. Adapters from other containers produce those tables; they do not change what conformance means.

---

## 9. Reference tables

`units.csv`, one row per recording unit:

| column | type | required |
|---|---|---|
| `unit_id` | string | yes |
| `recording_id` | string | yes |
| `session_id` | string | yes |
| `preparation_id` | string | yes |
| `x_um`, `y_um` | float | no |

`responses.csv`, one row per unit and trial:

| column | type | required |
|---|---|---|
| `unit_id` | string | yes |
| `trial_index` | integer | yes |
| `stim_time_ns` | integer, stimulus onset in nanoseconds on the response clock | yes |
| `condition` | string | yes |
| one column per measure | float | yes |

The analysis window (`post_stim_window_s`) and, optionally, the conditioning train duration (`load_duration_s`) are declared when the check is run, not stored in the tables.

A measure MUST be a column of `responses.csv` other than the four required columns, MUST be numeric, MUST NOT be entirely null, and MUST vary within at least one unit-condition group. A column that is constant within every unit, such as an electrode position or an identifier, would score as perfectly reliable and is rejected.

Identifiers are compared as strings. A unit that appears in `responses.csv` MUST appear in `units.csv`.

These rules are checks on the container, reported under the name SCHEMA. They are not among the six requirements.

**Evaluating from spikes.** When `rrb-check`, `rrb-evaluate`, or `rrb-report` is invoked with `--spikes` and `--analysis`, `responses.csv` carries the trial columns (`trial_index`, `stim_time_ns`, `condition`), any measure columns in `responses.csv` are ignored, the benchmark computes the requested measures per half from `spikes.csv` under `analysis.json`, and `min-dataset-7` applies. The three tables are checked before any spike is counted: required columns and nulls under SCHEMA, then the stimulus timeline under `min-dataset-4` and `min-dataset-6`, with the same messages as the tables path. A dataset with no spike inside any post-stimulus window is rejected under SCHEMA, with a note to check that `spike_time_ns` and `stim_time_ns` are integer nanoseconds on the same clock.

**Reference writer.** `writer.write_dataset` (`src/recovery_reliability_benchmark/writer.py`) is the reference writer for the spikes-path file layout (`units.csv`, `trials_responses.csv`, `spikes.csv`, `analysis.json`, and optional `preparation.json` and `conditions.json`), converting seconds on the recording clock to integer nanoseconds with `int(round(t * 1e9))` and ordering `spikes.csv` by `unit_ids` with ascending timestamps.

---

## Measures computed by the benchmark

On the spikes path (`measures.py`, `excess.py`), the benchmark computes the following measures per unit on each half's pooled trials (with window `W = post_stim_window_s` and artifact blank `B = artifact_blank_s` measured from load end `onset + load_duration_s`, and baseline rate `b = baseline_hz` measured over `[onset - pre_stim_window_s, onset)`):

| name | one-line definition | status |
|---|---|---|
| `t_half_excess` | Smallest post-load time `t` at which cumulative excess spikes reach half of total window excess (`NaN` when excess fails `min_excess_z`) | Lead |
| `excess_per_trial` | Mean post-load spikes per trial above pre-stimulus baseline expectation over `[B, W)` | Lead |
| `baseline_hz` | Pooled pre-stimulus firing rate over `[onset - pre_stim_window_s, onset)`, always reported as a comparison row | Reference |
| `t_return` | Right edge of the last PSTH bin exceeding `return_x_baseline * b` (censored at `W`; `0.0` if none exceed; `NaN` if `b == 0`) | Secondary (histogram bin; needs many spikes per bin) |
| `t_half_peak` | Center of the first PSTH bin after the peak at or below `b + half_peak_frac * (peak_rate - b)` (censored at `W`; `NaN` when no spike falls in any bin) | Secondary (histogram bin; needs many spikes per bin) |
| `peak_rate` | Maximum PSTH bin firing rate in `[B, W)` | Secondary (histogram bin; needs many spikes per bin) |
| `t_peak` | Center of the PSTH bin attaining `peak_rate` (`NaN` when no spike falls in any bin) | Secondary (histogram bin; needs many spikes per bin) |
| `residual` | Mean PSTH rate over bins with center `>= W - residual_s`, divided by `b` (`NaN` if `b == 0`) | Secondary (histogram bins; needs many spikes per bin) |
| `overshoot` | Pooled relative firing-rate deficit below `b` over bins with center `> t_return` (`NaN` when `t_return` is censored, no bin follows, or `b == 0`) | Secondary (histogram bins; needs many spikes per bin) |
| `spikes_per_trial` | Mean post-load spike count per trial in `[B, W)` | Auxiliary (bin-free) |
| `baseline_variance_hz2` | Sample variance (`ddof=1`, in Hz²) across trials of per-trial pre-stimulus firing rate | Auxiliary (pre-stimulus) |

The secondary PSTH measures read single histogram bins (or trailing bin subsets) and need many spikes per bin before discretization noise subsides. The lead measure `t_half_excess` acts directly on the sorted post-load spike times across the `n` trials in the half:

    N(t) = spikes over all n trials with latency in [B, t]
    E(t) = N(t) - b * n * (t - B)
    t_half_excess = smallest t with E(t) >= E(W) / 2

Spikes in the first `B` seconds after the load (default 0.003 s) are not counted by any measure: stimulation artifact lands there. `bin_edges_s` must start at or after `B`. For an exponential recovery with time constant `tau`, `t_half_excess` estimates `B + tau * ln 2`.

The response gate uses one number per trial, `d_i = post_i - ((W - B) / pre_stim_window_s) * pre_i`: the spikes of trial `i` in `[B, W)` minus its pre-stimulus count scaled to the same duration, so `sum(d) = E(W)`. When `E(W) <= min_excess_z * sqrt(n) * sd(d)` (sample standard deviation over the `n` trials; when `sd(d)` is zero, `E(W) <= 0`), `t_half_excess` is `NaN` with flag `no_excess`. A unit is held to its own trial-to-trial spread, so bursting or drift between trials does not pass as a response.

---

## 10. Preparation and condition metadata

These sidecars are optional for conformance: `rrb-check` reports a conformance level without them at SPEC v1.0 and v1.1. They are required for a contribution to the atlas (CONTRIBUTING.md, "What to send"), because an atlas row is keyed by protocol fingerprint, condition and preparation. When provided, they are validated under SCHEMA.

`preparation.json`, describing the physical specimen and acquisition setup:

| field | type | required |
|---|---|---|
| `preparation_id` | string, must match `units.csv` | yes |
| `species` | string | yes |
| `preparation_type` | `dissociated_culture` \| `organotypic_slice` \| `organoid` \| `engineered_neural_tissue` | yes |
| `age_days` | number ≥ 0 | yes |
| `age_basis` | `DIV` \| `days_post_plating` \| `days_post_differentiation` | yes |
| `line_or_donor_id` | anonymized string | yes |
| `instrument` | string | yes |
| `raw_data_url` | string | no |
| `exclusions` | array of `{"kind": "unit" \| "trial", "id": string, "reason": string}` | no |

`conditions.json`, mapping each condition label to its commanded protocol and pharmacology:

```json
{
  "<condition label>": {
    "protocol": "<Protocol JSON from protocol.py, optional>",
    "compound": "string | null",
    "dose": "number | null",
    "dose_unit": "string | null",
    "vehicle": "string | null"
  }
}
```

Every condition present in `responses.csv` MUST have an entry in `conditions.json` when the file is provided. The atlas row's protocol fingerprint is computed from `"protocol"`.

`analysis.json` — Analysis parameters: the `AnalysisParams` fields; declared before the run; its fingerprint is printed in the report.

---

## Inclusion and exclusion

A unit is included in a condition if and only if it has a row for every trial of that condition with every measure non-null. All present trials are used; no trial is excluded by rule in v0.1.x.

Contributors MUST NOT exclude units or trials after seeing results. Any exclusion made before submission (dead electrodes, stimulation-artifact saturation, a dropped trial) MUST be declared in `preparation.json` under `exclusions`, one entry per unit or trial with a reason; the report prints the counts. An exclusion that names a unit or trial still present in the tables is a SCHEMA violation.

Every report prints: units in the tables, units included by rule, units excluded by rule, rows missing from the full grid, and contributor-declared exclusions.

On the spikes path, measures are computed by the benchmark from `spikes.csv` for every unit in `units.csv`, which removes per-trial row selection as a lever while unit-level selection remains covered by declaration; on the tables path, per-trial numbers are computed by the contributor and row selection stays covered by declared exclusions. On the spikes path: "A unit is scored for a measure in a condition when that measure is computed in both halves." A silent unit is not scored for a measure that needs a baseline, a response or a peak (`t_return`, `residual`, `overshoot`, `t_half_excess`, `t_peak`, `t_half_peak`).

---

## 11. Raw data

`spikes.csv` (`unit_id`, `spike_time_ns`; one row per spike; on the same clock as `stim_time_ns`) is required on the spikes path, where the benchmark computes the measures, and is not needed for conformance on the tables path. A contribution from a spike-recording modality must include it; a modality without spikes contributes on the tables path. When provided, `spikes.csv` is validated under SCHEMA (`unit_id` and `spike_time_ns` present, `spike_time_ns` non-null, and every `unit_id` present in `units.csv`).

Raw traces SHOULD be shared by persistent link (Zenodo or DANDI DOI) when available, recorded as `raw_data_url` in `preparation.json`.

---

## 12. Fate

`fate.csv` (optional) records later observations of the same preparation so that atlas rows can carry outcome labels:

| column | type | required |
|---|---|---|
| `preparation_id` | string | yes |
| `observed_at` | ISO 8601 date string | yes |
| `status` | string | yes |
| `measure` | string | yes |
| `value` | number | yes |

`fate.csv` is defined here and is not checked by the validator in benchmark v0.1.x.

---

## 13. Size

A conforming dataset sent as events is on the order of megabytes: 10 trials across 20 units with 2 seconds of post-stimulus recording.

Raw voltage is not. At 20 kHz across 1,020 channels it is approximately 40 MB per second of recording, and a full raw session SHOULD be negotiated separately from the minimum dataset.

---

## 14. Checking conformance

Run the reference implementation against your data:

    rrb-check units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0

It checks SCHEMA, then min-dataset-1 through min-dataset-6 in order, raises on the first violation, and names the requirement ID, the value found, and the value required:

    min-dataset-6 failed. Post-stimulus window 0.4 s, requires 2.0 s.

Exit status is 0 when the dataset conforms, 1 on a violation, and 2 when the input could not be read. With `--json` it prints a strict JSON report containing the verdict, the counts behind it, the specification version, and the SHA-256 of both input files (across `--json` and `evaluate.json`, undefined numbers are written as `null`, with `r_undefined` marking an undefined correlation; `rrb-report` clears `evaluate.json`, `summary.md`, and `halves.png` from its output folder at the start of each run). The report is what a lab shares. No data leaves your machine to check conformance.

---

## 15. Nulls

A null measure value means the measure was not computed for that unit and trial, and the unit is not active in that trial. A null MUST NOT be used to mean that the preparation did not recover within the window; that is a result, not a missing value, and a measure definition in `METHOD.md` MUST state how it is encoded.

---

## 16. Scope of conformance

Conformance is necessary, not sufficient. A conforming dataset supports the computation. It does not guarantee that any measure computed from it clears any threshold, and it makes no claim about the tissue.

---

## What conformance guarantees on the spikes path

The trial and unit thresholds (`min-dataset-2` and `min-dataset-3`) were set by simulation for per-trial scalar measures (`docs/thresholds.md`); on the spikes path, reliability also depends on how many spikes each unit contributes to each half. From `docs/spikes_path_checks.json` (`t_half_excess`) at 20 trials: strong responses reach 0.97 with 28 of 30 units scored; weak responses reach 0.69 with 16 of 30; sparse firing reaches 0.81 with 16 of 30; at 40 trials the last two reach 0.87 and 0.85. The confidence interval, the shuffled null, and the units-scored counts in the report are the guide; conformance does not promise a narrow interval.

---

## 17. Versioning

Requirement IDs are stable across minor versions. Thresholds change only in a major version. The reference implementation reports the version it checked against, so a result citing "conformance to v1.1" means a fixed thing, which is the point of versioning it at all.

SPEC versions (`1.1`) and benchmark package versions (`0.2.0`) are distinct.

**Version 1.1** (additions to 1.0): `min-dataset-7` (1.0 s pre-stimulus window before the first onset and starting at or after the end of every previous post-stimulus window) and the spikes path (`--spikes` and `--analysis` with `analysis.json`, benchmark-computed PSTH and bin-free recovery measures plus the `baseline_hz` reference measure, per-measure unit scoring under `SPIKES_INCLUSION_RULE`, and the reference dataset writer `writer.write_dataset`).

---

## 18. Contributing a dataset

Conformance is the entry point, not the commitment. Terms for contributing data, what contributors receive, and how authorship is handled are in [CONTRIBUTING.md](CONTRIBUTING.md).

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).
