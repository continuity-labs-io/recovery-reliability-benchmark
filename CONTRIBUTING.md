# Recovery Reliability Benchmark

## Contribution terms

A contributing laboratory supplies one conforming dataset already on disk. It receives a reliability analysis of that dataset, authorship on the benchmark publication, and the option to walk away at any point before submission.

No new experiments. No instrument purchase. No obligation created by checking conformance.

This is a statement of how the benchmark operates, not a legal agreement. If your institution requires a formal data transfer agreement, that is handled separately and will not change anything below.

---

## 1. What to send

A contribution is a conforming dataset submitted for an atlas row. Conformance is checked locally by `rrb-check` without requiring metadata sidecars or (on the tables path) `spikes.csv`; a contribution must include `preparation.json` and `conditions.json`, and must include `spikes.csv` when the recording modality produces spikes. These contribution requirements are checked when the dataset is submitted, and `rrb-check` validates `preparation.json`, `conditions.json`, and `spikes.csv` under `SCHEMA` whenever they are provided.

**One conforming dataset.** When the recording modality produces spikes, send the spikes-path dataset directory written by `writer.write_dataset` (via an adapter built from `adapters/adapter_template.py`): `units.csv`, `trials_responses.csv`, `spikes.csv`, and `analysis.json`, checked locally with `rrb-check` and previewed with `rrb-report` before anything is shared (`min-dataset-1` through `min-dataset-7`; see [SPEC.md](SPEC.md)). A modality without spikes (for example calcium imaging) contributes on the tables path with pre-computed per-trial measure tables (`units.csv` and `responses.csv`, `min-dataset-1` through `min-dataset-6`).

**Metadata sidecars (`preparation.json` and `conditions.json`).** Required for every contribution because an atlas row is keyed by protocol fingerprint, condition, and preparation: species, preparation type, age or days in vitro, anonymized line or donor identifier, instrument, any pre-submission unit or trial exclusions, and the stimulus protocol as actually run (not as planned) with any compound, dose, and vehicle.

**One contact** who can answer questions about how the recording was made.

That is the whole ask. If a dataset does not conform, there is nothing to discuss and no further time is spent.

---

## Protocol advice

- **2.0 s after and 1.0 s before each stimulus.** Record at least 2.0 s after every conditioning load ends (`min-dataset-6`) and leave at least 1.0 s of quiet before every stimulus onset (`min-dataset-7`), starting at or after the end of the previous trial's post-stimulus window (so stimulus onsets are at least 3.0 s apart plus the load duration) and including before the first stimulus on the recording clock.
- **20 or more trials per condition.** Ten trials is the admission floor (`min-dataset-2`); 20 or more trials per condition are recommended, and weak or sparse firing benefits from 40.
- **The same load on every trial.** Deliver the identical conditioning load on every trial within a condition. When multiple stimulation loads or compounds are run in the same session, give each regime its own condition label.
- **The protocol recorded in `conditions.json`.** Encode the commanded `Protocol` (`protocol.py`) as actually delivered in `conditions.json`, alongside any compound, dose, and vehicle, so each condition carries a reproducible protocol fingerprint.

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

A submitted measure is a named function from the raw inputs (spike times, stimulus times, declared parameters) to one value per unit per trial or per half; it is scored on the fixed public datasets with splits chosen by the benchmark, never by the submitter; it is reported on both axes, reliability and sensitivity, with its interval and inclusion counts, next to the baseline-firing-rate reference row; a measure whose headline `rho` does not exceed the 95th percentile of its shuffled null is marked `[reliability at chance]` (`[no variation across units]` when `r_undefined` is `True`), and on each condition pair a measure whose `median_abs_z` does not exceed the 95th percentile of its shuffled null (`above_null` is `False`) is marked `[sensitivity at chance]`, while a measure that does not beat the reference on sensitivity (`beats_reference` is `False`) is listed and marked `[does not beat reference]`. The leaderboard does not exist yet; this is the rule it will follow.

---

## Writing an adapter

Before writing an adapter for a laboratory's recording format, check three things in the format description: at least 2.0 s of recording after each stimulus (`min-dataset-6`), at least 8 units (`min-dataset-3`), and at least 3.0 s between stimulus onsets, plus the load duration (`min-dataset-7`). Copy `adapters/adapter_template.py` and implement `load_recording(path)` returning `(unit_ids, spike_times_s, onsets_s, conditions)` in seconds on the recording clock. An adapter contains no analysis: it extracts identifiers, spike timestamps, stimulus onsets, and condition labels and hands them to `writer.write_dataset`, which writes `units.csv`, `trials_responses.csv`, `spikes.csv`, and `analysis.json` (plus `preparation.json` and `conditions.json` when passed), then prints the `rrb-check` and `rrb-report` commands to run locally.

---

## Code guidelines

- Source files stay under 300 lines; split by responsibility, not by line count.
- Public functions carry Google-style docstrings with `Args`, `Returns` and `Raises` where applicable.
- Validation lives in `checks.py` as an ordered registry; a new requirement is a new entry, not a new branch in `validate()`.
- Anything algorithmically non-obvious carries a comment stating intent before the code (`permutation_null` is the example).
- Names say what the number is: `reliability_ceiling`, not `ceiling`; odd/even halves, not A/B.
- The checker (`contract.py`, `checks.py`) depends on pandas only; scipy is allowed from `evaluate.py` onward.
- Every backticked code symbol in `GLOSSARY.md` must resolve; `tests/test_style.py` enforces all of the above.
- Every reported number must be invariant to row order, unit and condition relabeling, affine transforms of a measure, and index offsets; `tests/test_invariance.py` enforces this.

The functions and constants implementing `METHOD.md` and `SPEC.md` form the frozen layer (`frozen.py`, `frozen/manifest.json`, `frozen/snapshots/`). They do not change in response to any dataset's result; any intentional modification requires a minor version bump in `pyproject.toml`, a `Frozen:` line under that version in `CHANGELOG.md`, and `python -m recovery_reliability_benchmark.frozen_manifest --update`. See [frozen/README.md](frozen/README.md).

---

## 9. Starting

Run the conformance check locally. If it passes, get in touch. If it fails, the error names the requirement and the shortfall, and that information is useful to you regardless of whether you contribute.

Ryan J. McCall, Continuity Labs.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).

