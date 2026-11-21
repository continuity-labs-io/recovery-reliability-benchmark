Narrow the anchor claim to the tissue level. This is a wording change in four documents and one test. Do not change anything under src/, frozen/, adapters/ or examples/. Do not change the package version or the SPEC version.

The new anchor claim, to be used word for word everywhere:

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology, and ion-channel pharmacology measures recovery from inactivation in cell lines engineered to express one channel. At the tissue level they are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported.

The old anchor claim it replaces:

Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported.

1. README.md: replace the old claim with the new one (the standalone paragraph under the first description paragraph).

2. SPEC.md, "## 1. What the benchmark asks": replace the old claim with the new one. Keep the two sentences that follow it ("If you know of a counterexample, open an issue. The claim is meant to be checked.").

3. GLOSSARY.md, the "**Anchor claim.**" entry: replace the quoted old claim with the new one. Keep the trailing "README; SPEC §1."

4. CITATION.cff, the abstract: replace the old claim with the new one, re-wrapped to the existing line width. Keep the sentence that starts "This repository holds". Keep the YAML valid.

5. tests/test_docs.py::test_anchor_claim_pinned: update the pinned string to the new claim. Extend the test so it also asserts the new claim appears in GLOSSARY.md, and that the old sentence "They are not used as an endpoint in pharmacology screening" appears in none of README.md, SPEC.md, GLOSSARY.md or CITATION.cff. For CITATION.cff, compare after collapsing whitespace, since the abstract is wrapped.

6. CHANGELOG.md, under "## Unreleased", add:
   - Anchor claim narrowed to the tissue level (README, SPEC §1, GLOSSARY, CITATION.cff). Ion-channel pharmacology measures recovery from inactivation on automated patch clamp in recombinant cell lines (Lukacs et al. 2021, doi:10.3389/fphar.2021.738260), and FDA's recommended voltage protocols for cardiac ion channels include one for the kinetics of hERG block (2018, https://www.fda.gov/media/129686/download).

7. Run ruff check ., ruff format --check . and pytest. Report the test count, any failure, and the output of a repo-wide search for "not used as an endpoint", which should show only the new sentence that begins "At the tissue level".
