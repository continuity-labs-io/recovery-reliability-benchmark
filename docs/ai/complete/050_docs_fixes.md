Setting the test expectations for conformance and contribution wording
Context Files

Existing files to read:

AGENTS.md
SPEC.md
GLOSSARY.md
METHOD.md
CONTRIBUTING.md
README.md
CHANGELOG.md
tests/test_docs.py
tests/test_style.py
tests/test_cli.py
src/recovery_reliability_benchmark/contract.py (read only)
src/recovery_reliability_benchmark/checks.py (read only)
src/recovery_reliability_benchmark/cli.py (read only)
New files to create:

None.

Prompt 050 - the specification states what the 0.2.0 checker requires.
Documentation and one documentation test. No change under src/.

1. OBJECTIVE AND OWNERSHIP

SPEC.md, written at 0.1.0, promises requirements that 0.2.0 does not enforce:
- Section 10: the sidecars preparation.json and conditions.json are "optional in SPEC v1.0 (benchmark
  v0.1.x) and required from SPEC v1.1 (benchmark v0.2.0)".
- Section 11: spikes.csv is "requested for every contribution at benchmark v0.1.x and required from
  v0.2.0".
The 0.2.0 checker reports fully_conforming (SPEC v1.1) for examples/units.csv and
examples/responses.csv with no sidecar and no spikes.csv, the README commands for a lab's own
recordings pass no sidecar, and the tables path has no spikes.csv at all. A specification that says
"required" while its reference checker passes without it cannot be tagged.

Decision already taken: reword the specification; do not change the checker. The sidecars and
spikes.csv are optional for conformance and required for a contribution to the atlas.

You own SPEC.md, GLOSSARY.md, METHOD.md, CONTRIBUTING.md and tests/test_docs.py for this change.
Find every sentence that carries the old promise and rewrite each so the documents agree with one
another and with the checker, instead of editing the two SPEC sentences in isolation.

2. INVARIANTS

- No file under src/, scripts/, examples/ or frozen/ changes. SPEC_VERSION stays "1.1": the new text
  describes what version 1.1 already does. Do not run freeze.py --amend.
- Section headings and numbering in SPEC.md are unchanged (other tests locate text by heading).
- The RFC keywords MUST and SHOULD keep their existing use in SPEC.md.

Two terms, used the same way in every document:
- Conformance is what rrb-check reports. It depends on SCHEMA and min-dataset-1 through
  min-dataset-6, plus min-dataset-7 on the spikes path, and on nothing else.
- A contribution is a dataset submitted for an atlas row. Its requirements are listed in
  CONTRIBUTING.md "What to send" and are checked when the dataset is submitted, not by rrb-check.

Required statements:
- Sidecars: optional for conformance at SPEC v1.0 and v1.1; required for a contribution, because an
  atlas row is keyed by protocol fingerprint, condition and preparation; validated under SCHEMA
  whenever they are provided.
- spikes.csv: required on the spikes path, where the benchmark computes the measures; not needed for
  conformance on the tables path. A contribution from a spike-recording modality must include
  spikes.csv. A modality without spikes (for example calcium imaging) contributes on the tables path.
  Validated under SCHEMA whenever it is provided.
- Benchmark-computed measures: statements of the form "from v0.2.0, measures are computed by the
  benchmark" become statements about the spikes path. The tables path still accepts per-trial numbers
  computed by the contributor, and for it row selection stays covered by declared exclusions.

SPEC.md section 10 opens with exactly this paragraph:
  These sidecars are optional for conformance: `rrb-check` reports a conformance level without them
  at SPEC v1.0 and v1.1. They are required for a contribution to the atlas (CONTRIBUTING.md, "What to
  send"), because an atlas row is keyed by protocol fingerprint, condition and preparation. When
  provided, they are validated under SCHEMA.

SPEC.md section 11 opens with exactly this sentence, followed by the existing sentence that lists
what the SCHEMA validation of spikes.csv covers:
  `spikes.csv` (`unit_id`, `spike_time_ns`; one row per spike; on the same clock as `stim_time_ns`)
  is required on the spikes path, where the benchmark computes the measures, and is not needed for
  conformance on the tables path. A contribution from a spike-recording modality must include it; a
  modality without spikes contributes on the tables path.

3. IMPLEMENTATION STEPS AND EDGE CASES

- SPEC.md: replace the two openings as specified. In the inclusion section, rewrite the sentence that
  begins "From v0.2.0, measures are computed by the benchmark from `spikes.csv`" so it speaks about
  the spikes path and says what remains true on the tables path. Leave the quoted
  SPIKES_INCLUSION_RULE text and the sentence about silent units as they are.
- GLOSSARY.md: the entries for `spikes.csv` and "Sidecar" restate the old promise ("required from
  v0.2.0", "Optional at v0.1.x ..."). Rewrite both to the required statements above. Every backticked
  code symbol must still resolve (tests/test_style.py).
- METHOD.md, table in "How this benchmark can be gamed": the mitigation that reads "benchmark computes
  measures from spikes from v0.2.0" becomes "benchmark computes measures from spikes on the spikes
  path". The attack names in the first column are pinned by a test and must not change.
- CONTRIBUTING.md "What to send": state in plain words that a contribution must include
  preparation.json and conditions.json, and spikes.csv when the recording modality produces spikes.
  Keep the section heading.
- README.md: no change expected. Edit only a sentence that has become false.
- tests/test_docs.py, one new test that ties the wording to the checker:
    a. SPEC.md contains the section 10 paragraph and the section 11 sentence above, compared after
       collapsing whitespace so line wrapping is free.
    b. None of SPEC.md, GLOSSARY.md, METHOD.md, CONTRIBUTING.md contains "required from".
    c. validate on make_tables(n_units=30, n_trials=20) with measures tau and amplitude,
       post_stim_window_s 2.0, no sidecar and no spikes, returns conformance "fully_conforming".
- CHANGELOG.md under 0.2.0, one line that does not start with "Frozen:": the sidecars and spikes.csv
  are optional for conformance and required for an atlas contribution; the 0.1.0 text said they
  would be required from 0.2.0, which the checker did not enforce.
- Out of scope, do not edit in this prompt: the phrase "in v0.1.x" in the inclusion rule
  (contract.INCLUSION_RULE and its copy in SPEC.md), the fate.csv sentence, the structure of the
  CHANGELOG 0.2.0 section, and CITATION.cff. They belong to the release prompt.
- Do not weaken or delete existing tests. If an existing documentation test fails because of a
  required edit, stop and report which assertion and which sentence conflict.

4. LOGGING AND NAMING

- No code under src/ changes, so no logging changes.
- Documentation prose is calm and plain: state what is required, by whom, and where it is checked.
  No emphasis by capitals other than the RFC keywords, no exclamation marks, no emojis.
- The new test has a descriptive lowercase name, for example
  test_spec_separates_conformance_from_contribution.

5. EXIT CONDITIONS

Run from the repository root and report the output of each:
  python scripts/freeze.py --check     exits 0 with no amend
  ruff check .                         no findings
  ruff format --check .                no files to reformat
  pytest tests/test_docs.py tests/test_style.py -q    all pass
  pytest -q                            all pass
  grep -rn "required from" --include="*.md" . | grep -v "docs/ai/" | grep -v "CHANGELOG.md"    prints nothing
  git status --short src scripts examples frozen    prints nothing
Report the suite count and the final text of SPEC.md sections 10 and 11 opening paragraphs.
