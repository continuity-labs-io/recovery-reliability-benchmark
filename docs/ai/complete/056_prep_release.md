Prepare release v0.2.1. This is a documentation release: no file under src/ changes and no frozen function or constant changes. Do step 1 of "## Releasing" in AGENTS.md only. Do not push, tag or publish.

1. Set the version to 0.2.1 in pyproject.toml and CITATION.cff. Set date-released in CITATION.cff to today's date. Keep the top-level doi in CITATION.cff as the Concept DOI 10.5281/zenodo.24020731.

2. CHANGELOG.md: move everything under "## Unreleased" into a new "## [0.2.1] - <today's date>" section, and leave an empty "## Unreleased" above it. Start the new section with: "Scope of this release: documentation only. Adds the pre-registered replication plan and pass rule (docs/pass_rule.md). The frozen layer is unchanged from 0.2.0."

3. Run python -m recovery_reliability_benchmark.frozen_manifest --update. It must report no changed frozen items. If it reports any, stop and report them; do not add a "Frozen:" line.

4. README.md, "## Citing": the citation line must not pair v0.2.1 with the v0.2.0 Version DOI. Until the v0.2.1 Version DOI exists, make the line read:
   > McCall, R. J. (2026). Recovery Reliability Benchmark (v0.2.1). Continuity Labs. https://doi.org/10.5281/zenodo.24020731
   Keep the sentence that lists the v0.2.0 and v0.1.0 Version DOIs. Update tests/test_docs.py::test_zenodo_doi_recorded to match: the citation line contains "(v0.2.1)" and the Concept DOI, and the other DOI assertions stay as they are.

5. Run ruff check ., ruff format --check . and pytest. Report: the test count, the output of the frozen_manifest command, and the list of files changed.
