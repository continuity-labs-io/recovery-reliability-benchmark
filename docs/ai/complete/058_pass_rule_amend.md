Task: amend docs/pass_rule.md. Documentation only. Do not touch src/, frozen/, or any threshold.

1. In docs/pass_rule.md, directly under the "**Plan version 1.**" paragraph, add this paragraph:

**Amended 2026-11-23**, before any site was registered and before any stimulated recording was made. Four settings were added to the site plan in section 5 and one item to the reporting list in section 7. No gate, threshold or measure changed.

2. In "## 5. Site plan, registered before the first session", append these four bullets after the existing five, in this order:

- The preparation type and the spacing between stimulus onsets.
- The pulse polarity. It comes from the screening run.
- The spike sorter, its version and settings, how stimulation artifact is removed before sorting, and how units are matched across days.
- The analysis parameters, as written in `analysis.json`, with the fingerprint. One artifact blank, `artifact_blank_s`, is used for both loads and both days. It is at least as long as the longest period after a stimulus in which the sorter loses spikes at the higher load, read from the screening run.

3. In "## 7. Reported whatever the outcome", append this bullet:

- The sensitivity result recomputed with the artifact blank doubled. A result that changes is reported as a possible effect of stimulation artifact.

4. In CHANGELOG.md under "## Unreleased", add:

- docs/pass_rule.md amended before any site registration: the site plan also registers preparation type and stimulus spacing, pulse polarity, spike sorter and unit matching, and `analysis.json` with one artifact blank for both loads; sensitivity is also reported with the blank doubled. No gate, threshold or measure changed.

5. In tests/test_docs.py::test_pass_rule_doc, add assertions that the text contains "Amended 2026-11-23", "`analysis.json`", "`artifact_blank_s`" and "spike sorter", and that "artifact_blank_s" appears in the package sources. Keep every existing assertion.

Do not change any other wording in docs/pass_rule.md. Do not bump the version. Run ruff check ., ruff format --check ., and pytest. Report the result.
