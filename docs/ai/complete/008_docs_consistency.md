Task: docs. Place the three documents and add a consistency test. No source changes.

1. Replace SPEC.md with the attached SPEC.md (copied verbatim).
2. Replace CONTRIBUTING.md with the contents of the contribution-terms document (doc 03) and METHOD.md with the ceiling-method document (doc 04). Append to the end of each: a blank line, "---", a blank line, and "This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS)." Do not edit their text otherwise.
3. README.md: insert the "What is being benchmarked" section (text supplied) between the opening sentence and "## Quickstart".
4. tests/test_docs.py, reading files relative to Path(__file__).resolve().parent.parent:
    - test_spec_lists_every_requirement: for every member of Requirement except SCHEMA, the string f"**{member.value} — " appears in SPEC.md, and "SCHEMA" appears at least once.
    - test_spec_version_matches_code: f"**Version {SPEC_VERSION}**" appears in SPEC.md.
    - test_spec_documents_example_message: the exact string "MD-6 failed. Post-stimulus window 0.4 s, requires 2.0 s." appears in SPEC.md, and validate() with post_stim_window_s=0.4 on make_tables() produces str(exc) equal to it.
    - test_spec_quickstart_matches_readme: the string "rrb-check units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0" appears in SPEC.md and "rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0" appears in README.md.
    - test_docs_carry_license_notice: SPEC.md, CONTRIBUTING.md, METHOD.md and README.md each contain "LICENSE-DOCS".

Run the full suite and make it pass.
