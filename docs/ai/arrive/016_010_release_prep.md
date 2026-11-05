Task: prepare the v0.1.0 release. No source changes.

1. CITATION.cff: cff-version 1.2.0; title "Recovery Reliability Benchmark"; authors McCall, Ryan J. (Continuity Labs); version 0.1.0; date-released today; repository-code URL; license Apache-2.0; abstract: the sharpened anchor claim (two sentences) plus "This repository holds the conformance specification, its reference checker, a stimulation-protocol schema, and the reliability-ceiling computation."
2. CHANGELOG.md: move everything under "## Unreleased" to "## [0.1.0] - <today>", grouped Added / Changed, and open a fresh empty Unreleased section. Add one line at the top of the 0.1.0 entry: "Scope of this release: conformance checking and reliability ceilings on per-trial measures, validated on synthetic data. Pilot reproduction and PSTH measures follow in 0.2.0."
3. pyproject.toml: confirm version = "0.1.0". README: add a "Citing" section pointing at CITATION.cff.
4. tests/test_docs.py: CITATION.cff exists, parses as YAML, version matches pyproject version; CHANGELOG contains "## [0.1.0]".
5. Print the exact commands to run after review, do not run them: git tag -a v0.1.0 -m "v0.1.0: conformance checker, protocol schema, reliability ceiling (synthetic validation)"; git push origin v0.1.0; gh release create v0.1.0 --title "v0.1.0" --notes-file <(sed -n '/## \[0.1.0\]/,/^## /p' CHANGELOG.md).

Run the full suite and make it pass.
