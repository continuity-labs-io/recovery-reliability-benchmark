# Recovery Reliability Benchmark

## Dataset Conformance Specification

**Version 1.0**
Status: normative
Reference implementation: `src/recovery_reliability_benchmark/contract.py`, run as `rrb-check`

The key words MUST, MUST NOT, SHOULD and MAY are to be interpreted as in RFC 2119.

---

## 1. What the benchmark asks

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported. If you know of a counterexample, open an issue. The claim is meant to be checked.

The benchmark asks whether they can be. The first question, which gates every other one, is whether a recovery measure is reliable enough to distinguish a preparation from a repeat of itself.

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

**Evaluated condition** — a condition that satisfies the MUST thresholds of MD-2 and MD-3. The computation in section 3 runs on evaluated conditions.

---

## 3. The computation this supports

Trials within one session are partitioned into two halves. The measure is computed independently on each half, giving two vectors indexed by recording unit. The two vectors are correlated across units and the result is corrected for length:

    rho_full = 2 * rho_half / (1 + rho_half)

Every requirement in section 4 follows from this procedure.

---

## 4. Requirements

| ID | Requirement | MUST | SHOULD |
|---|---|---|---|
| MD-1 | Preparations, sessions and recordings present | exactly 1 of each | |
| MD-2 | Trials per condition | ≥ 10 in at least one condition | ≥ 20 |
| MD-3 | Recording units active in every trial of an evaluated condition | ≥ 8 | ≥ 15 |
| MD-4 | Stimulus onset timestamps | present, one per trial across units, strictly increasing within a condition | |
| MD-5 | Rows per unit-trial pair | exactly 1 | |
| MD-6 | Post-stimulus window per trial | ≥ 2.0 s | |

**MD-1 — Single session.**
The dataset MUST contain exactly one session from exactly one preparation, in exactly one recording. Longitudinal data is out of scope for this computation. A second recording identifier is a second acquisition and therefore a second session.

**MD-2 — Repeated trials.**
At least one condition MUST contain 10 or more trials, and SHOULD contain 20 or more. A trial is counted once per distinct trial index. Below 10, the two halves are too short for the correlation to be stable.

**MD-3 — Multiple recording units.**
At least one condition that satisfies MD-2 MUST contain 8 or more units active in every one of its trials, and SHOULD contain 15 or more. A single unit cannot produce a correlation. A unit that is missing a trial, or carries a null measure in one, is not counted; section 12 says what a null is allowed to mean.

**MD-4 — Stimulus timestamps.**
The dataset MUST provide the onset time of every stimulus, on the same clock as the response data. Every unit on a preparation receives the same stimulus, so each trial MUST carry exactly one onset time and exactly one condition across all units. Onset times MUST be strictly increasing with trial index within a condition.

**MD-5 — Trial-level resolution.**
The dataset MUST provide per-trial data: exactly one row per unit and trial. One row per unit is a summary statistic, which cannot be partitioned into halves; two rows for the same unit and trial count one trial twice.

**MD-6 — Post-stimulus window.**
Each trial MUST carry at least 2.0 seconds of recording after stimulus onset. The submitter declares the analysis window. The declared window MUST be at least 2.0 s, and for every trial except the last it MUST fit before the next stimulus onset. The last trial has no following onset and is not checked. If the stimulus is a conditioning train of nonzero duration, the submitter MAY declare that duration; the window is then required after the train ends, which only tightens the check. This is the requirement that most often fails, because many stimulation protocols use short inter-stimulus intervals. A protocol truncating at 200 ms cannot resolve a seconds-scale return.

---

## 5. Conformance levels

Levels are evaluated per condition.

**Conforming.** All six MUST conditions hold for at least one condition. The dataset supports the computation.

**Fully conforming.** All MUST and all SHOULD conditions hold for at least one condition. Confidence intervals on the resulting estimate will be materially narrower.

The dataset's level is the level of its best condition. The reference implementation names that condition and lists the SHOULD thresholds it misses. A conforming dataset that is not fully conforming is still usable, and the shortfall is reported alongside the result rather than treated as disqualifying.

---

## 6. Not required

Multiple sessions. Conditioning bursts. A probe ladder. Any particular tissue type, species or cell source. Any particular instrument. Any particular modality: calcium imaging satisfies MD-1 through MD-6 as readily as an electrode array. Any aging-related metadata.

---

## 7. Optional, in order of value

| ID | Item | Why it matters |
|---|---|---|
| OD-1 | Multiple stimulus amplitudes | Permits direct evaluation of the dose-response curve and the titration rule, not only the ceiling |
| OD-2 | More than one session on the same preparation | Promotes the question from "is the measure capable" to "does it repeat" |
| OD-3 | Both stimulus polarities | Separates artifact from response |
| OD-4 | Preparation metadata: age, cell source, DIV, medium changes, handling | Medium changes are known to be material |
| OD-5 | Raw signal rather than detected events | Events cannot be un-thresholded; raw preserves every amplitude measure |

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

---

## 10. Size

A conforming dataset sent as events is on the order of megabytes: 10 trials across 20 units with 2 seconds of post-stimulus recording.

Raw voltage is not. At 20 kHz across 1,020 channels it is approximately 40 MB per second of recording, and a full raw session SHOULD be negotiated separately from the minimum dataset.

---

## 11. Checking conformance

Run the reference implementation against your data:

    rrb-check units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0

It checks SCHEMA, then MD-1 through MD-6 in order, raises on the first violation, and names the requirement ID, the value found, and the value required:

    MD-6 failed. Post-stimulus window 0.4 s, requires 2.0 s.

Exit status is 0 when the dataset conforms, 1 on a violation, and 2 when the input could not be read. With `--json` it prints a report containing the verdict, the counts behind it, the specification version, and the SHA-256 of both input files. The report is what a lab shares. No data leaves your machine to check conformance.

---

## 12. Nulls

A null measure value means the measure was not computed for that unit and trial, and the unit is not active in that trial. A null MUST NOT be used to mean that the preparation did not recover within the window; that is a result, not a missing value, and a measure definition in `METHOD.md` MUST state how it is encoded.

---

## 13. Scope of conformance

Conformance is necessary, not sufficient. A conforming dataset supports the computation. It does not guarantee that any measure computed from it clears any threshold, and it makes no claim about the tissue.

---

## 14. Versioning

Requirement IDs are stable across minor versions. Thresholds change only in a major version. The reference implementation reports the version it checked against, so a result citing "conformance to v1.0" means a fixed thing, which is the point of versioning it at all.

---

## 15. Contributing a dataset

Conformance is the entry point, not the commitment. Terms for contributing data, what contributors receive, and how authorship is handled are in [CONTRIBUTING.md](CONTRIBUTING.md).

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).
