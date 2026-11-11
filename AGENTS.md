# Recovery Reliability Benchmark — Agent Instructions

This repository implements the Recovery Reliability Benchmark: a data contract (`SPEC.md`, `contract.py`, `checks.py`) and within-session split-half reliability ceiling evaluator (`METHOD.md`, `evaluate.py`, `controls.py`, `run.py`) testing whether neural recovery kinetics after a standardized conditioning load are reliable enough per recording unit to serve as a functional endpoint.

## Frozen-layer rule

Read `frozen/README.md` before modifying any code.

- Never edit frozen functions, frozen constants, `frozen/snapshots/`, or `frozen/manifest.json` to make a test pass.
- Never tune thresholds, split rules, inclusion rules, or measure definitions in response to a dataset's result.
- If a task requires changing a frozen function or constant, stop and report to the user unless the prompt explicitly instructs either a pre-tag amend (keep the version, add a `Frozen:` line under that version in `CHANGELOG.md`, and run `python -m recovery_reliability_benchmark.frozen_manifest --amend`, which refuses once `v<version>` is tagged) or a version bump with a `CHANGELOG.md` `Frozen:` entry and `python -m recovery_reliability_benchmark.frozen_manifest --update`.

## Code standards

- Top-level `scripts/` and `demos/` directories are banned (`tests/test_style.py`); format-conversion adapters live in `adapters/`.
- Every source file in `src/recovery_reliability_benchmark/` must stay at or under 300 lines; split by responsibility, not by arbitrary line count.
- Public functions and classes must have Google-style docstrings with `Args:`, `Returns:`, and `Raises:` sections where applicable.
- Names must state what the number is (`reliability_ceiling`, not `ceiling`; `odd`/`even` halves, never `A`/`B`).
- Keep `GLOSSARY.md` synchronized with code: every backticked code symbol in `GLOSSARY.md` must resolve (`tests/test_style.py`).
- `contract.py` and `checks.py` depend on `pandas` only; `scipy` is allowed from `evaluate.py` onward.
- Every reported number must remain invariant to row order, unit and condition relabeling, positive affine transforms of a measure, and index offsets (`tests/test_invariance.py`).

## Verification

Always run `ruff check .`, `ruff format --check .`, and `pytest` and confirm the entire test suite passes before reporting done.

## Releasing

1. Pre-tag readiness: ensure `pyproject.toml`, `CITATION.cff`, and `frozen/manifest.json` match the target version (`python -m recovery_reliability_benchmark.frozen_manifest --update` with `Frozen:` bullets in `CHANGELOG.md` when advancing from a tagged version), keep top-level `doi:` in `CITATION.cff` pinned to the Concept DOI (`10.5281/zenodo.24020731`), set the release date in `CHANGELOG.md` and `CITATION.cff`, and pass local verification.
2. CI gate: push `main` and wait for both the `test` matrix and `frozen-core` GitHub Actions workflows to pass on the exact commit SHA to be tagged.
3. Tag: create and push an annotated tag (`git tag -a vX.Y.Z -F <notes>` and `git push origin vX.Y.Z`). Do not manually pre-reserve a draft DOI on Zenodo while the GitHub webhook is active.
4. GitHub Release & Zenodo ID check: publish the GitHub Release from tag `vX.Y.Z` to trigger Zenodo archiving. Note on Zenodo IDs: Zenodo only minted an `N - 1` Concept DOI (`24020731`) alongside the Version DOI (`24020732`) on the initial `v0.1.0` release; every subsequent release mints only one new Version DOI under the existing `10.5281/zenodo.24020731` Concept DOI (verify in the Zenodo sidebar that `24020731` remains the "Cite all versions" DOI—never assume `new_id - 1` belongs to this repository).
5. Post-tag DOI commit: on `main` under `## Unreleased`, append the newly minted Version DOI to `identifiers:` in `CITATION.cff`, update `README.md` (`## Citing`) and `tests/test_docs.py::test_zenodo_doi_recorded`, and run full verification.
