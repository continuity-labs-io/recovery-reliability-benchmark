Task: record the Zenodo DOIs for v0.1.0. Docs and one test only; no source changes. Commit as "docs: Zenodo DOI for v0.1.0".

1. README.md: directly under the existing test badge line, add exactly:
   [![DOI](https://zenodo.org/badge/1444426702.svg)](https://doi.org/10.5281/zenodo.24020731)

2. README.md: replace the "## Citing" section with:

   ## Citing

   Every release is archived on Zenodo. Cite the version you used. The version DOI for v0.1.0 is [10.5281/zenodo.24020732](https://doi.org/10.5281/zenodo.24020732); [10.5281/zenodo.24020731](https://doi.org/10.5281/zenodo.24020731) always resolves to the latest release. Citation metadata is in [CITATION.cff](CITATION.cff); GitHub's "Cite this repository" button renders it.

   > McCall, R. J. (2026). Recovery Reliability Benchmark (v0.1.0). Continuity Labs. https://doi.org/10.5281/zenodo.24020732

3. CITATION.cff: after the `version:` line add
   doi: 10.5281/zenodo.24020732
   identifiers:
     - type: doi
       value: 10.5281/zenodo.24020731
       description: Concept DOI; resolves to the latest release.
     - type: doi
       value: 10.5281/zenodo.24020732
       description: Version DOI for v0.1.0.
   Validate with `cffconvert --validate` (pip install cffconvert if needed).

4. tests/test_docs.py: add test_zenodo_doi_recorded: CITATION.cff contains "doi: 10.5281/zenodo.24020732"; README.md contains "zenodo.org/badge/1444426702.svg" and "10.5281/zenodo.24020731".

5. CHANGELOG.md Unreleased: "Zenodo DOIs recorded: concept 10.5281/zenodo.24020731, v0.1.0 10.5281/zenodo.24020732."

Run the suite; make it pass.
