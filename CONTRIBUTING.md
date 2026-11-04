# Recovery Reliability Benchmark

## Contribution terms

A contributing laboratory supplies one conforming dataset already on disk. It receives a reliability analysis of that dataset, authorship on the benchmark publication, and the option to walk away at any point before submission.

No new experiments. No instrument purchase. No obligation created by checking conformance.

This is a statement of how the benchmark operates, not a legal agreement. If your institution requires a formal data transfer agreement, that is handled separately and will not change anything below.

---

## 1. What you provide

**One conforming dataset.** Six requirements, verifiable on your own machine before anything is shared. See the [conformance specification](SPEC.md).

**Minimal metadata.** Species or cell source, age or days in vitro, instrument, recording modality, and the stimulus protocol as actually run. Not as planned.

**One contact** who can answer questions about how the recording was made.

That is the whole ask. If a dataset does not conform, there is nothing to discuss and no further time is spent.

---

## 2. What you get back

**A written reliability report on your own data**, within two weeks of receipt. Within-session ceiling for each measure, synthetic positive control, label-permutation null, condition-centered and uncentered figures, and an explicit independence accounting stating what was treated as one sample.

**You receive this whether or not your dataset ends up in the publication, and whether or not you choose to continue.** If the report tells you something you would rather not publish, you keep it and we stop there.

**Authorship** on the benchmark publication, under the terms in section 3.

**The analysis code**, which is public from the outset and carries a version tag, so you can rerun any result yourself.

---

## 3. Authorship

Each contributing laboratory nominates up to two authors. The laboratory decides who they are.

**Author order after the first author is by date of conforming dataset received.** Earliest first. This is objective, it is stated before anyone joins, and it means nobody negotiates position.

The first author is whoever performs the analysis. There is no honorary authorship and no author added for providing funding or facilities alone.

A laboratory that withdraws its dataset is removed from the author list.

---

## 4. How results are reported

This section exists because it is the part that decides whether contributing is safe.

**Results are reported per measure and per preparation type, not per laboratory.** In the main text, datasets carry anonymized identifiers: Dataset A, Dataset B. The results table says what a given measure achieved on a given class of preparation.

**Each laboratory chooses independently whether its dataset is attributed by name.** Authorship records that you contributed. It does not record which row of the results table is yours unless you say so.

A low ceiling on your dataset is a finding about a measure, not an assessment of your laboratory. It will not be written up as one. If you believe a draft does so, say it and it gets changed before submission.

---

## 5. Data handling

Data is analyzed and retained only for the duration of the benchmark, then deleted on request.

**You decide whether your underlying data is deposited publicly.** Public deposit is encouraged and is not required. A dataset that stays private contributes its derived statistics to the benchmark and nothing else.

Nothing is shared with any third party. Nothing is used for any purpose other than the analysis described here.

---

## 6. Publication

The benchmark is submitted once there are **at least five conforming datasets from at least three independent laboratories.** Fewer than that is a case study, not a benchmark.

Every contributor sees the full draft and has thirty days to comment before submission.

**Both outcomes are published.** If recovery measures prove unreliable across every dataset tested, that result goes out in full, with the protocol, the code and the data handling described identically. Negative results in assay development are rarely reported, which is why the same unproductive designs are rebuilt independently across groups.

---

## 7. Withdrawal

You may withdraw your dataset at any point before journal submission, for any reason or none. Your data is deleted, your authorship is removed, and you keep your reliability report.

After publication, withdrawal is not possible, which is why the thirty-day review window exists.

---

## 8. Starting

Run the conformance check locally. If it passes, get in touch. If it fails, the error names the requirement and the shortfall, and that information is useful to you regardless of whether you contribute.

Ryan J. McCall, Continuity Labs.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).

