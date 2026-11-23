Task: freeze the across-day comparison ahead of release 0.3.0 and make the pass rule name it. Do not bump the version. Do not edit frozen/manifest.json or frozen/snapshots/. Do not commit or push. The release skill runs next, and its prepare step bumps the version and updates the manifest.

This is the version-bump path in AGENTS.md: new frozen functions, a "Frozen:" line in the changelog, then frozen_manifest --update, which the release skill runs.

1. src/recovery_reliability_benchmark/across_days.py: register _check_days_compatible, across_day_frame and across_day_comparison with @frozen("METHOD across-day comparison"). Add the import it needs. Change nothing else in the file.

2. frozen/README.md:
- In the table in section 2, add three rows above the first existing row, each with kind "function" and reference "METHOD across-day comparison":
  `recovery_reliability_benchmark.across_days._check_days_compatible`
  `recovery_reliability_benchmark.across_days.across_day_comparison`
  `recovery_reliability_benchmark.across_days.across_day_frame`
- In section 3, add `across_days.load_day` to the input orchestration list and `across_days_cli.py` to the runner and CLI list.

3. CHANGELOG.md, under "## Unreleased":
- In the across-day entry, replace "Not yet in the frozen layer; no real second-day recording has been scored." with "No real second-day recording has been scored."
- Replace the entry that starts "docs/pass_rule.md amended before any site registration" with these two entries:

- docs/pass_rule.md is now plan version 2, published before any site was registered: the site plan also registers preparation type and stimulus spacing, pulse polarity, spike sorter and unit matching, and `analysis.json` with one artifact blank for both loads; sensitivity is also reported with the blank doubled; gate 3 is scored by `rrb-across-days`, with the pooled, condition-centered correlation when there are two loads. No threshold, count rule or measure changed. Plan version 1 stays on record in v0.2.1.
- Frozen: across_days.py (`across_day_frame`, `across_day_comparison`, `_check_days_compatible`) joined the frozen layer at 0.3.0. No existing frozen function or constant changed.

4. docs/pass_rule.md. Use this wording exactly.

Replace the paragraph that starts "**Plan version 1.**" and the paragraph that starts "**Amended 2026-11-23**" with:

**Plan version 2.** Published in release v0.3.0 of the Recovery Reliability Benchmark, before any site was registered and before any stimulated recording was made. Results are published whether the gates pass or fail.

Plan version 1 was published in release v0.2.1 and stays on record there. Changes in version 2, made 2026-11-23:

- Four settings were added to the site plan in section 5.
- One item was added to the reporting list in section 7.
- The across-day comparison is released and frozen in v0.3.0. Sections 1 and 3 name it, and section 3 says which correlation gate 3 uses when there are two loads.

No threshold, count rule or measure changed.

Replace the "**Code.**" bullet in section 1 with:

- **Code.** Recovery Reliability Benchmark v0.3.0, SPEC v1.1. The functions and constants that score R and S are unchanged from v0.2.0. Version 0.3.0 adds the across-day comparison that scores D. A change to frozen code before scoring means a new version of this plan.

In section 3, replace the paragraph that starts "Release v0.2.1 does not compute the across-day comparison." with:

The across-day comparison is computed by `rrb-across-days` (METHOD.md, Across-day comparison). It was released and frozen in v0.3.0, after it was checked on simulated pairs of sessions with known answers and before any second-day recording was made. With two loads, the correlation is the pooled, condition-centered one. In the command's output, D is `above_null` true with `r_across_days` at least 0.50, and a preparation with `n_units` below 15 is not evaluable.

In section 9, replace the Simulations bullet with:

- Simulations (docs/spikes_path_checks.md, docs/thresholds.md, tests/test_across_days.py).

5. tests/test_docs.py:
- test_pass_rule_doc: replace the phrase "Amended 2026-11-23" with "Plan version 2", add the phrase "`rrb-across-days`", and add "r_across_days" to the field-name loop. Keep every other assertion.
- test_across_days_docs: assert that "rrb-across-days" appears anywhere in CHANGELOG.md, not only above the first version heading. The release moves that entry under a version heading.

6. Finish. Run ruff check ., ruff format --check ., and pytest. Exactly these four tests must fail, because the manifest is not updated yet:
tests/test_frozen.py::test_registry_matches_manifest
tests/test_frozen.py::test_snapshots_match
tests/test_frozen.py::test_update_version_only_refresh
tests/test_frozen.py::test_frozen_module_cli_check
Every other test must pass. Report the result and stop.
