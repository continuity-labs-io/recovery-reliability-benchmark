Task: record the minted v0.2.0 Zenodo version DOI (10.5281/zenodo.24143857) and document the release and Zenodo DOI rules in AGENTS.md. Docs and tests only; do not modify any source files or frozen items.

1. CITATION.cff
- Set top-level `doi: 10.5281/zenodo.24020731` (the permanent Concept DOI) so pre-tag archives on future releases never point at an older version's DOI.
- Under `identifiers:`, keep the Concept DOI (`10.5281/zenodo.24020731`) and the v0.1.0 Version DOI (`10.5281/zenodo.24020732`), and append:
  - type: doi
    value: 10.5281/zenodo.24143857
    description: Version DOI for v0.2.0.

2. README.md (`## Citing`)
- Update the prose so it states that the version DOI for v0.2.0 is `10.5281/zenodo.24143857` (and v0.1.0 is `10.5281/zenodo.24020732`), while `10.5281/zenodo.24020731` always resolves to the latest release.
- Update the citation blockquote to `(v0.2.0)` and `https://doi.org/10.5281/zenodo.24143857`.

3. CHANGELOG.md (`## Unreleased`)
- Under `## Unreleased`, add: `- Zenodo v0.2.0 DOI recorded (10.5281/zenodo.24143857); release checklist added to AGENTS.md.`

4. AGENTS.md
- Append a `## Releasing` section after `## Verification` documenting the five-step release sequence:
  1. Pre-tag readiness: ensure `pyproject.toml`, `CITATION.cff`, and `frozen/manifest.json` match the target version (`python -m recovery_reliability_benchmark.frozen_manifest --update` with `Frozen:` bullets in `CHANGELOG.md` when advancing from a tagged version), keep top-level `doi:` in `CITATION.cff` pinned to the Concept DOI (`10.5281/zenodo.24020731`), set the release date in `CHANGELOG.md` and `CITATION.cff`, and pass local verification.
  2. CI gate: push `main` and wait for both the `test` matrix and `frozen-core` GitHub Actions workflows to pass on the exact commit SHA to be tagged.
  3. Tag: create and push an annotated tag (`git tag -a vX.Y.Z -F <notes>` and `git push origin vX.Y.Z`). Do not manually pre-reserve a draft DOI on Zenodo while the GitHub webhook is active.
  4. GitHub Release & Zenodo ID check: publish the GitHub Release from tag `vX.Y.Z` to trigger Zenodo archiving. Note on Zenodo IDs: Zenodo only minted an `N - 1` Concept DOI (`24020731`) alongside the Version DOI (`24020732`) on the initial `v0.1.0` release; every subsequent release mints only one new Version DOI under the existing `10.5281/zenodo.24020731` Concept DOI (verify in the Zenodo sidebar that `24020731` remains the "Cite all versions" DOI—never assume `new_id - 1` belongs to this repository).
  5. Post-tag DOI commit: on `main` under `## Unreleased`, append the newly minted Version DOI to `identifiers:` in `CITATION.cff`, update `README.md` (`## Citing`) and `tests/test_docs.py::test_zenodo_doi_recorded`, and run full verification.

5. tests/test_docs.py
- Update `test_zenodo_doi_recorded()` to assert that `CITATION.cff` contains `doi: 10.5281/zenodo.24020731`, `10.5281/zenodo.24020732`, and `10.5281/zenodo.24143857`, that `README.md` contains `10.5281/zenodo.24020731` and `10.5281/zenodo.24143857`, and that `AGENTS.md` contains `## Releasing`.

6. Verification
- Run `ruff check .`, `ruff format --check .`, `pytest -q`, and `python -m recovery_reliability_benchmark.frozen_manifest --check`, and confirm all checks pass.
