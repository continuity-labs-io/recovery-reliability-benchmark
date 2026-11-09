# Recovery Reliability Benchmark

## Frozen Layer

### 1. Why

The reliability numbers reported by this benchmark are evidence only if the procedure was fixed before the data arrived. Nothing in this file's list changes in response to a dataset's result.

### 2. What is frozen

Every function and constant below is registered in `recovery_reliability_benchmark.frozen` and snapshotted under `frozen/`.

| Name | Kind | Reference |
|---|---|---|
| `recovery_reliability_benchmark.checks.check_active_units` | function | SPEC min-dataset-3 |
| `recovery_reliability_benchmark.checks.check_identifiers` | function | SPEC SCHEMA |
| `recovery_reliability_benchmark.checks.check_measures_allowed_and_numeric` | function | SPEC SCHEMA |
| `recovery_reliability_benchmark.checks.check_measures_vary_within_groups` | function | SPEC SCHEMA |
| `recovery_reliability_benchmark.checks.check_one_row_per_unit_trial` | function | SPEC min-dataset-5 |
| `recovery_reliability_benchmark.checks.check_post_stimulus_window` | function | SPEC min-dataset-6 |
| `recovery_reliability_benchmark.checks.check_required_columns` | function | SPEC SCHEMA |
| `recovery_reliability_benchmark.checks.check_sidecars` | function | SPEC SCHEMA |
| `recovery_reliability_benchmark.checks.check_single_session` | function | SPEC min-dataset-1 |
| `recovery_reliability_benchmark.checks.check_stimulus_timeline` | function | SPEC min-dataset-4 |
| `recovery_reliability_benchmark.checks.check_trials_per_condition` | function | SPEC min-dataset-2 |
| `recovery_reliability_benchmark.contract.build_report` | function | SPEC conformance levels |
| `recovery_reliability_benchmark.contract.validate` | function | SPEC conformance levels |
| `recovery_reliability_benchmark.controls.census` | function | METHOD independence accounting |
| `recovery_reliability_benchmark.controls.permutation_null` | function | METHOD null |
| `recovery_reliability_benchmark.controls.positive_control` | function | METHOD positive control |
| `recovery_reliability_benchmark.evaluate.headline` | function | METHOD headline rule |
| `recovery_reliability_benchmark.evaluate.reliability_ceiling` | function | METHOD Spearman-Brown and interval |
| `recovery_reliability_benchmark.evaluate.split_halves` | function | METHOD split |
| `recovery_reliability_benchmark.evaluate.variance_components` | function | METHOD variance components |
| `recovery_reliability_benchmark.protocol.Protocol.fingerprint` | function | SPEC conditions.json fingerprint |
| `recovery_reliability_benchmark.synthetic.make_tables` | function | METHOD positive control generator |
| `recovery_reliability_benchmark.contract.MD2_MUST` | constant (`10`) | SPEC min-dataset-2 |
| `recovery_reliability_benchmark.contract.MD2_SHOULD` | constant (`20`) | SPEC min-dataset-2 |
| `recovery_reliability_benchmark.contract.MD3_MUST` | constant (`8`) | SPEC min-dataset-3 |
| `recovery_reliability_benchmark.contract.MD3_SHOULD` | constant (`30`) | SPEC min-dataset-3 |
| `recovery_reliability_benchmark.contract.MD6_MUST` | constant (`2.0`) | SPEC min-dataset-6 |
| `recovery_reliability_benchmark.controls.DEFAULT_N_PERM` | constant (`1000`) | METHOD null |
| `recovery_reliability_benchmark.controls.POSITIVE_CONTROL_RELIABILITY` | constant (`0.85`) | METHOD positive control |
| `recovery_reliability_benchmark.controls.POSITIVE_CONTROL_TOLERANCE` | constant (`0.05`) | METHOD positive control |
| `recovery_reliability_benchmark.controls.POSITIVE_CONTROL_TRIALS` | constant (`20`) | METHOD positive control |
| `recovery_reliability_benchmark.controls.POSITIVE_CONTROL_UNITS` | constant (`1000`) | METHOD positive control |
| `recovery_reliability_benchmark.evaluate.DEFAULT_CONFIDENCE` | constant (`0.95`) | METHOD Spearman-Brown and interval |
| `recovery_reliability_benchmark.evaluate.REFERENCE_N_TRIALS` | constant (`20`) | METHOD trial-count standardization |

### 3. What is not frozen

Adapters, CLI (`cli.py`), loaders (`read_tables`, `read_spikes`, `metadata.py`), report generation (`scripts/`), documentation, synthetic condition offsets, and new measure names live in the open layer and may evolve without a frozen-layer update.

### 4. How to change frozen code

1. Bump the minor version in `pyproject.toml` (and `CITATION.cff`).
2. Add a heading for the new version in `CHANGELOG.md` containing at least one line starting with `Frozen:` naming each changed function or constant and the reason.
3. Run `python scripts/freeze.py --update`.
4. Run `pytest` and confirm all tests pass.

Results computed under different versions of the frozen layer are never compared without explicitly stating the versions.

### 5. Optional pre-push hook

`.githooks/pre-push` runs `python scripts/freeze.py --check`. Enable it locally with:

```sh
git config core.hooksPath .githooks
```

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).
