Context Files

Existing files to read:

AGENTS.md
CHANGELOG.md
CITATION.cff
README.md
SPEC.md
GLOSSARY.md
pyproject.toml
src/recovery_reliability_benchmark/contract.py
src/recovery_reliability_benchmark/frozen_manifest.py (read only)
tests/test_docs.py
tests/test_style.py
tests/test_frozen.py (read only)
tests/test_contract.py

New files to create:

None.

Prompt 051 - release metadata and wording for 0.2.0.
Documentation, one string constant and one test. No behavior changes.

1. OBJECTIVE AND OWNERSHIP

The files that the 0.2.0 archive will carry still describe 0.1.0 in six places:
- CITATION.cff pairs version 0.2.0 with the version DOI of the v0.1.0 archive.
- The README citation blockquote cites v0.1.0.
- The 0.2.0 section of CHANGELOG.md has no scope statement, says two modules are "not yet wired into
  rrb-evaluate", and names scripts/adapter_template.py, which now lives in adapters/.
- The inclusion rule text, printed in every report and evaluate.json, ends "in v0.1.x".
- The fate.csv sentence in SPEC.md says "in benchmark v0.1.x".
- Two GLOSSARY.md entries name v0.1 (the inclusion rule and the odd/even split).

You own exactly these passages: the 0.2.0 section of CHANGELOG.md, CITATION.cff, the "Citing" section
of README.md, the two SPEC.md sentences and two GLOSSARY.md entries named below, the INCLUSION_RULE
string in contract.py, and test_zenodo_doi_recorded in tests/test_docs.py. Make them agree with one
another. If you find another statement in these files that this release makes false, report it in
your final message instead of editing it. No new features, checks, files or sections.

2. INVARIANTS

- No frozen function or constant changes. INCLUSION_RULE is not in the frozen manifest; only its text
  changes, and contract.py keeps its line count. Do not run the amend or update modes. If the
  frozen-manifest check reports a difference, stop and report it.
- No reported number changes. examples/, frozen/, docs/spikes_path_checks.json and the README example
  table stay byte-identical.
- Version stays 0.2.0 in pyproject.toml and CITATION.cff. SPEC_VERSION stays "1.1".
- CHANGELOG.md: every bullet that starts with "Frozen:" under 0.2.0 stays byte-identical and in its
  current order (there are 15). The "## Unreleased" heading stays above the section, empty. The
  0.1.0 section is released history and is not edited.
- Do not invent a version DOI for 0.2.0. It does not exist until the release is archived; a later
  prompt records it.
- One release date, in ISO form, equal to the day this prompt is applied (2026-11-11 if applied
  today), used in both the CHANGELOG 0.2.0 heading and CITATION.cff date-released.

3. IMPLEMENTATION STEPS AND EDGE CASES

CITATION.cff
- The top-level field becomes "doi: 10.5281/zenodo.24020731" (the concept DOI, which resolves to the
  latest release).
- The identifiers list is unchanged: the concept DOI entry and the "Version DOI for v0.1.0" entry
  both stay.
- date-released becomes the release date. Nothing else changes.

README.md, section "Citing"
- The paragraph becomes:
  Every release is archived on Zenodo. Cite the version you used.
  [10.5281/zenodo.24020731](https://doi.org/10.5281/zenodo.24020731) always resolves to the latest
  release, and its Zenodo record lists the DOI of each version (v0.1.0:
  [10.5281/zenodo.24020732](https://doi.org/10.5281/zenodo.24020732)). Citation metadata is in
  [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button renders it.
- The blockquote becomes:
  > McCall, R. J. (2026). Recovery Reliability Benchmark (v0.2.0). Continuity Labs. https://doi.org/10.5281/zenodo.24020731
- The badge line at the top of the README is unchanged.

tests/test_docs.py, test_zenodo_doi_recorded
- CITATION.cff: the line that begins with "doi:" at column 0 is exactly
  "doi: 10.5281/zenodo.24020731"; the text still contains "value: 10.5281/zenodo.24020732" and
  "Version DOI for v0.1.0".
- README.md: the two existing assertions stay (badge and concept DOI). Add: the line that starts with
  "> McCall" contains "(v<version>)" with the version read from pyproject.toml, contains
  "https://doi.org/10.5281/zenodo.24020731", and does not contain "10.5281/zenodo.24020732".

Inclusion rule
- contract.INCLUSION_RULE: the final sentence becomes
  "All present trials are used; no trial is excluded by rule." The first sentence is unchanged.
- SPEC.md "Inclusion and exclusion": the copy of the rule changes the same way, so the existing
  assertion that INCLUSION_RULE appears in SPEC.md keeps passing.
- GLOSSARY.md entry "Inclusion rule (`INCLUSION_RULE`)": remove "in v0.1.x" from the same sentence.
- Tests that compare against the constant by name need no change. A test that hardcodes the old
  sentence is updated to the new sentence.

Other wording
- SPEC.md: "`fate.csv` is defined here and is not checked by the validator in benchmark v0.1.x."
  becomes "`fate.csv` is defined here and is not checked by the validator."
- GLOSSARY.md entry "Odd/even split (`odd_even`)": "The only split mode in v0.1.0; `random` is
  planned." becomes "The only split mode implemented; `random` is planned."
- Every backticked code symbol in GLOSSARY.md must still resolve (tests/test_style.py).

CHANGELOG.md, section 0.2.0 only
- Heading: "## [0.2.0] - <release date>".
- Directly under the heading, before the bullets, add this paragraph:
  Scope of this release: the spikes path. From spike times and stimulus times the benchmark computes
  the recovery measures itself with frozen definitions, reports reliability and sensitivity beside a
  baseline firing rate reference row, and writes a report folder from one command. Validated on
  simulated spike trains with known answers; no real stimulation recording has been scored yet.
  Pilot reproduction, announced for 0.2.0 in the 0.1.0 notes, is not part of this release.
- Add one bullet at the top of the list, not starting with "Frozen:": release metadata and wording:
  CITATION.cff cites the concept DOI, the README citation names the current version, and the
  inclusion rule text, the fate.csv sentence and two glossary entries no longer name v0.1.
- Correct three existing bullets and change nothing else in them:
    the writer.py bullet: "scripts/adapter_template.py" becomes "adapters/adapter_template.py";
    the spikes.py bullet: delete its last sentence, "Not yet wired into rrb-evaluate.";
    the measures.py bullet: delete "; not yet wired into rrb-evaluate".
- Leave every other bullet as it is, including the Zenodo bullet and all 15 "Frozen:" bullets.

4. LOGGING AND NAMING

- No logging and no print statements change. The only source edit is the text of one string constant.
- Prose is calm and plain: say what the release contains and what it does not. No emphasis by
  capitals other than the RFC keywords already in SPEC.md, no exclamation marks, no emojis.
- No renames. The test keeps the name test_zenodo_doi_recorded.

5. EXIT CONDITIONS

Run from the repository root and report the output of each:
  python -m recovery_reliability_benchmark.frozen_manifest --check     exits 0, no amend
  ruff check .                                                         no findings
  ruff format --check .                                                no files to reformat
  pytest tests/test_docs.py tests/test_style.py tests/test_frozen.py tests/test_contract.py -q   all pass
  pytest -q                                                            all pass
  grep -rn "v0\.1\.x" --include="*.md" --include="*.py" . | grep -v "docs/ai/"       prints nothing
  grep -n -i "not yet wired" CHANGELOG.md                              prints nothing
  grep -n "scripts/adapter_template" CHANGELOG.md                      prints nothing
  grep -c "^- Frozen:" CHANGELOG.md                                    prints 15
  git diff CHANGELOG.md | grep -E "^[-+]- Frozen:"                     prints nothing
  grep -n "^doi:\|^date-released:" CITATION.cff                        concept DOI and the release date
  grep -n "^## \[0.2.0\]" CHANGELOG.md                                 the same release date
  git status --short frozen examples docs/spikes_path_checks.json pyproject.toml     prints nothing
Report the suite count, the release date used, the final README "Citing" section, and any statement
you found but did not edit under the rule in section 1.
