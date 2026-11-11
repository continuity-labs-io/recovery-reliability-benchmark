# Recovery Reliability Benchmark — Agent Instructions

This repository implements the Recovery Reliability Benchmark: a data contract (`SPEC.md`, `contract.py`, `checks.py`) and within-session split-half reliability ceiling evaluator (`METHOD.md`, `evaluate.py`, `controls.py`, `run.py`) testing whether neural recovery kinetics after a standardized conditioning load are reliable enough per recording unit to serve as a functional endpoint.

## Frozen-layer rule

Read `frozen/README.md` before modifying any code.

- Never edit frozen functions, frozen constants, `frozen/snapshots/`, or `frozen/manifest.json` to make a test pass.
- Never tune thresholds, split rules, inclusion rules, or measure definitions in response to a dataset's result.
- If a task requires changing a frozen function or constant, stop and report to the user unless the prompt explicitly instructs either a pre-tag amend (keep the version, add a `Frozen:` line under that version in `CHANGELOG.md`, and run `python scripts/freeze.py --amend`, which refuses once `v<version>` is tagged) or a version bump with a `CHANGELOG.md` `Frozen:` entry and `python scripts/freeze.py --update`.

## Code standards

- Every source file in `src/recovery_reliability_benchmark/` must stay at or under 300 lines; split by responsibility, not by arbitrary line count.
- Public functions and classes must have Google-style docstrings with `Args:`, `Returns:`, and `Raises:` sections where applicable.
- Names must state what the number is (`reliability_ceiling`, not `ceiling`; `odd`/`even` halves, never `A`/`B`).
- Keep `GLOSSARY.md` synchronized with code: every backticked code symbol in `GLOSSARY.md` must resolve (`tests/test_style.py`).
- `contract.py` and `checks.py` depend on `pandas` only; `scipy` is allowed from `evaluate.py` onward.
- Every reported number must remain invariant to row order, unit and condition relabeling, positive affine transforms of a measure, and index offsets (`tests/test_invariance.py`).

## Verification

Always run `ruff check .`, `ruff format --check .`, and `pytest` and confirm the entire test suite passes before reporting done.
