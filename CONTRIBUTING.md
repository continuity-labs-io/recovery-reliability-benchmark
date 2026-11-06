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

**You receive this whether or not you then choose to deposit.** If the report tells you something you would rather not publish, you keep it and we stop there.

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

**Each laboratory chooses independently whether its dataset is attributed by name.** Authorship records that you contributed. It does not record which row of the results table is yours unless you say so. The public archive entry carries the attribution you choose, your laboratory's name or an anonymized identifier; the paper's results table uses anonymized identifiers either way.

A low ceiling on your dataset is a finding about a measure, not an assessment of your laboratory. It will not be written up as one. If you believe a draft does so, say it and it gets changed before submission.

---

## 5. Data license and use

Contributed datasets are released under CC0 1.0 Universal; see DATA_LICENSE. Contributions are accepted only under CC0. Datasets offered under any other terms, including non-commercial or no-derivatives conditions, are not accepted. By contributing, you confirm that you hold the rights needed to deposit the data and that the data were collected under the ethics approvals applicable to your institution. Citation of the dataset and of the benchmark is requested as a norm; it is not a condition of the license. The data may be used by anyone for any purpose, including training models and building commercial products. Continuity Labs' own position as maintainer is stated in docs/terms.md.

---

## 6. Data handling

You send the dataset for analysis; the report is delivered within two weeks; the dataset is deposited in the public archive under CC0 when you confirm after reading the report. Until deposit the data are held for analysis only, shared with no third party, and deleted on request. Only deposited datasets are part of the benchmark and the publication.

---

## 7. Publication

The benchmark is submitted once there are **at least five conforming datasets from at least three independent laboratories.** Fewer than that is a case study, not a benchmark.

Every contributor sees the full draft and has thirty days to comment before submission.

**Both outcomes are published.** If recovery measures prove unreliable across every dataset tested, that result goes out in full, with the protocol, the code and the data handling described identically. Negative results in assay development are rarely reported, which is why the same unproductive designs are rebuilt independently across groups.

---

## 8. Withdrawal

You may withdraw at any point before deposit, for any reason; the data are deleted and you keep the report. After deposit, CC0 is irrevocable: the record can be delisted from the archive and your authorship removed before journal submission, but copies already made under CC0 remain licensed.

After publication, withdrawal is not possible, which is why the thirty-day review window exists.

---

## Submitting measures

A submitted measure is a named function from the raw inputs (spike times, stimulus times, declared parameters) to one value per unit per trial or per half; it is scored on the fixed public datasets with splits chosen by the benchmark, never by the submitter; it is reported on both axes, reliability and sensitivity, with its interval and inclusion counts, next to the baseline-firing-rate reference row; a measure that does not beat the reference on sensitivity is listed and marked. The leaderboard does not exist yet; this is the rule it will follow.

---

## Code guidelines

- Source files stay under 300 lines; split by responsibility, not by line count.
- Public functions carry Google-style docstrings with `Args`, `Returns` and `Raises` where applicable.
- Validation lives in `checks.py` as an ordered registry; a new requirement is a new entry, not a new branch in `validate()`.
- Anything algorithmically non-obvious carries a comment stating intent before the code (`permutation_null` is the example).
- Names say what the number is: `reliability_ceiling`, not `ceiling`; odd/even halves, not A/B.
- The checker (`contract.py`, `checks.py`) depends on pandas only; scipy is allowed from `evaluate.py` onward.
- Every backticked code symbol in `GLOSSARY.md` must resolve; `tests/test_style.py` enforces all of the above.

---

## 9. Starting

Run the conformance check locally. If it passes, get in touch. If it fails, the error names the requirement and the shortfall, and that information is useful to you regardless of whether you contribute.

Ryan J. McCall, Continuity Labs.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).

