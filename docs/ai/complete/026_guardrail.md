Add a guardrail for the frozen layer. METHOD.md and SPEC.md define a procedure that
must not change in response to any dataset's result; the code implementing it is the
frozen layer. This task marks it, snapshots it, and makes any drift fail pytest unless
the change goes through a version-bump ceremony. Do not change the behavior of any
frozen function. No new dependencies. No file over 300 lines. Google docstrings.

1. New module src/recovery_reliability_benchmark/frozen.py (under 90 lines):
   - FROZEN_FUNCTIONS: dict[str, Callable] = {} keyed by f"{fn.__module__}.{fn.__qualname__}".
   - FROZEN_CONSTANTS: dict[str, str] = {} keyed by "module.NAME", value = reference string.
   - def frozen(reference: str): decorator; registers fn in FROZEN_FUNCTIONS, sets
     fn.__frozen_reference__ = reference, returns fn unchanged. No other runtime behavior.
   - def register(fn, reference: str): the same as the decorator in function form, for
     modules near the 300-line limit that already have a registry.
   - def freeze_constant(module_name: str, name: str, reference: str): registers a constant.
   - def normalized_source(fn) -> str: textwrap.dedent(inspect.getsource(fn)); ast.parse;
     take body[0]; if its first statement is a string-constant Expr (the docstring), drop
     it (use ast.Pass() if the body becomes empty); return ast.unparse(node) + "\n".
     Comments and docstrings therefore do not count as changes; logic does.

2. Mark the frozen layer.
   Functions, with the doc section as the reference string:
   - every check in checks.py: add at the bottom of checks.py one loop over CHECKS calling
     register(fn, "SPEC " + requirement.value), not per-function decorators (the file is
     at 298 lines)
   - contract.validate ("SPEC conformance levels")
   - evaluate.split_halves ("METHOD split"), evaluate.reliability_ceiling
     ("METHOD Spearman-Brown and interval"), evaluate.variance_components
     ("METHOD variance components")
   - the function that selects the headline (pooled-centered when two or more conditions).
     If that selection is inline in run.run, first extract it into a pure function
     evaluate.headline(...) with no behavior change and confirm existing tests pass, then
     mark it ("METHOD headline rule")
   - controls.permutation_null ("METHOD null"), controls.positive_control
     ("METHOD positive control"), controls.census if it affects any reported number
   - synthetic.make_tables ("METHOD positive control generator")
   - the protocol fingerprint function, wherever it lives ("SPEC conditions.json fingerprint");
     protocol.py is at 298 lines, so use register() there too if needed
   Constants, by value: every min-dataset MUST and SHOULD threshold, the positive-control
   parameters (units, trials, injected reliability, tolerance), the permutation count, the
   confidence level, and REFERENCE_N_TRIALS.
   If a name above does not exist as written, find the function that implements that
   section and mark that one. List the final set in your summary; do not guess silently.

3. Snapshots and manifest.
   - frozen/manifest.json: {"version": <pyproject version>, "python": "<major.minor>",
     "functions": {qualname: {"snapshot": path, "sha256": hex}}, "constants": {qualname: value}}.
   - frozen/snapshots/<module>.<qualname>.txt: the normalized source of each function.
   - scripts/freeze.py (under 150 lines) with three modes:
     --init: create manifest and snapshots; refuse if the manifest exists.
     --check: recompute and compare; exit 0 if identical, else exit 1 printing a unified
       diff per changed function and each changed constant.
     --update: refuse unless (a) the pyproject version differs from the manifest version
       and (b) CHANGELOG.md has a heading for the new version containing at least one line
       starting with "Frozen:". Then rewrite snapshots and manifest and print what changed.
   - Read .github/workflows/test.yml; run --init under the Python version CI uses (the
     highest, if a matrix). Record that version in the manifest.

4. tests/test_frozen.py. Import every module in the package first so registries fill.
   - test_registry_matches_manifest: registered function names == manifest function names.
   - test_snapshots_match: skip with a reason if the running major.minor differs from the
     manifest's; otherwise each normalized_source equals its snapshot. On failure include
     the unified diff and: "Frozen function <name> changed. If this is intended: bump the
     version in pyproject.toml, add a 'Frozen:' line under that version in CHANGELOG.md,
     run python scripts/freeze.py --update. See FROZEN.md."
   - test_constants_match: each registered constant equals its manifest value.
   - test_manifest_version_matches_package.
   - test_frozen_md_lists_every_name: every registered function and constant name appears
     in FROZEN.md inside backticks.

5. FROZEN.md at repo root, under 120 lines, CC BY 4.0 like the other docs:
   - Why: the reliability numbers are evidence only if the procedure was fixed before the
     data arrived. Nothing in this file's list changes in response to a dataset's result.
   - What is frozen: a table of every function and constant with its METHOD or SPEC
     reference, written from the registry.
   - What is not frozen: adapters, CLI, loaders, report generation, docs, synthetic
     condition offsets, new measure names.
   - How to change frozen code: minor version bump; CHANGELOG entry with "Frozen:" lines
     naming each function and the reason; python scripts/freeze.py --update; pytest.
     Results from different versions are never compared without saying so.
   - Optional hook: .githooks/pre-push running python scripts/freeze.py --check; enable
     with git config core.hooksPath .githooks. Add that hook file.

6. AGENTS.md at repo root, under 60 lines, for any coding agent reading this repo:
   one paragraph on what the repo is; the frozen rule (read FROZEN.md; never edit frozen
   functions, constants, snapshots or the manifest to make a test pass; if a task requires
   a frozen change, stop and report); never tune thresholds, split rules or measure
   definitions on a dataset's result; the code standards from CONTRIBUTING.md (300 lines
   per file, Google docstrings, names say what the number is, no A/B half naming,
   glossary-first); run pytest before reporting done.
   Add CLAUDE.md and GEMINI.md, each one line: "Read AGENTS.md first."

7. If the evaluate and report output does not already print the package version, add it.

8. CI: add a job named frozen-core to .github/workflows/test.yml that runs
   python scripts/freeze.py --check on the manifest's Python version.

9. GLOSSARY.md: add an entry "Frozen layer". CONTRIBUTING.md: one paragraph under code
   guidelines pointing to FROZEN.md.

10. Run python scripts/freeze.py --init, then pytest; everything passes including the five
    new tests. Then prove the guardrail: change one character of logic in
    evaluate.reliability_ceiling, run pytest, confirm test_snapshots_match fails with the
    diff and the message, revert, confirm pass. Paste both outputs in your summary.
