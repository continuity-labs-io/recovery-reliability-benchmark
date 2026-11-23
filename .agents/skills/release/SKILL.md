---
name: release
description: >-
  Executes the Recovery Reliability Benchmark 5-step release workflow defined in AGENTS.md
  (pre-tag readiness, GitHub Actions CI gate, annotated git tag, GitHub Release + Zenodo
  Version DOI verification under Concept DOI 10.5281/zenodo.24020731, and post-tag DOI commit).
  Activate this skill whenever the user asks to cut, run, or publish a release (e.g. "release v0.2.1").
---

# Release Workflow (`vX.Y.Z`)

This skill automates the 5-step release checklist in [AGENTS.md](../../../AGENTS.md) using the deterministic helper [release_helper.py](./scripts/release_helper.py).

## Operating Rules

- **Single confirmation gate:** Run Steps 1 and 2 automatically, extract and display the exact commit SHA and release notes, and **ask the user once for confirmation** before creating/pushing the git tag and publishing the GitHub Release. Once confirmed, execute Steps 3, 4, and 5 straight through without pausing unless an error occurs.
- **Frozen-layer & Zenodo invariants:**
  - Never modify frozen functions, constants, or `frozen/snapshots/` unless explicitly instructed; `prepare` runs `python -m recovery_reliability_benchmark.frozen_manifest --update` and aborts if frozen items changed without a `Frozen:` bullet in `CHANGELOG.md`.
  - Keep top-level `doi:` in `CITATION.cff` pinned to Concept DOI `10.5281/zenodo.24020731`.
  - Never pre-reserve a draft DOI on Zenodo manually, and never assume `new_id - 1` belongs to this repository; always verify `conceptdoi == "10.5281/zenodo.24020731"` via `poll-zenodo`.

## Steps

### Step 1 — Pre-Tag Readiness

1. If `pyproject.toml` is not yet at `X.Y.Z`, prepare the version bump (supply `--scope "Scope of this release: ..."` summarized from `CHANGELOG.md` `## Unreleased` if not already written):
   ```bash
   .venv/bin/python .agents/skills/release/scripts/release_helper.py prepare --version X.Y.Z --scope "Scope of this release: ..."
   ```
   `prepare` reinstalls the package in editable mode so the installed version matches the new version. Commit (`Prepare release vX.Y.Z`) and push `main` (`git push origin main`).
2. If `pyproject.toml` is already committed at `X.Y.Z`, run pre-tag verification directly:
   ```bash
   .venv/bin/python .agents/skills/release/scripts/release_helper.py verify-pretag --version X.Y.Z
   ```

### Step 2 — CI Gate & Notes Preview

1. Verify that both the `test` matrix (Python 3.11, 3.12, 3.13) and `frozen-core` workflows succeeded on the exact `HEAD` commit SHA on `origin/main` (passing `--wait` if still running):
   ```bash
   .venv/bin/python .agents/skills/release/scripts/release_helper.py verify-ci --wait
   ```
2. Extract the annotated tag message and GitHub Release notes to temporary files (using `mktemp` or your conversation's scratch directory, never inside the repository root):
   ```bash
   TAG_NOTES="$(mktemp -t rrb_tag)"
   REL_NOTES="$(mktemp -t rrb_release)"
   .venv/bin/python .agents/skills/release/scripts/release_helper.py extract-notes \
     --version X.Y.Z \
     --tag-notes "$TAG_NOTES" \
     --release-notes "$REL_NOTES"
   ```
3. **Confirmation Gate:** Present the verified commit SHA, CI status, and extracted release notes to the user and ask for confirmation to tag and publish `vX.Y.Z`. Stop and wait for their reply.

### Step 3 — Annotated Tag (Auto-continue after confirmation)

Create and push the annotated tag on the verified SHA:

```bash
git tag -a vX.Y.Z -F "$TAG_NOTES" <verified_sha>
git push origin vX.Y.Z
```

### Step 4 — GitHub Release & Zenodo DOI Verification

1. Publish the GitHub Release from the pushed tag to trigger the Zenodo archive webhook:
   ```bash
   gh release create vX.Y.Z --verify-tag --title "vX.Y.Z" --notes-file "$REL_NOTES"
   ```
2. Poll Zenodo's public API until the new Version DOI for `vX.Y.Z` is minted and verified under Concept DOI `10.5281/zenodo.24020731`:
   ```bash
   .venv/bin/python .agents/skills/release/scripts/release_helper.py poll-zenodo --version X.Y.Z --timeout-s 300 --interval-s 10
   ```
   (If Zenodo takes longer than 5 minutes, schedule a wakeup timer via the `schedule` tool rather than shell `sleep`, and re-run `poll-zenodo`.)

### Step 5 — Post-Tag DOI Commit

1. Record the newly minted Version DOI across `CITATION.cff`, `CHANGELOG.md` (`## Unreleased`), `README.md` (`## Citing`), and `tests/test_docs.py::test_zenodo_doi_recorded`, and run full local verification (`ruff check`, `ruff format --check`, `frozen_manifest --check`, `pytest`):
   ```bash
   .venv/bin/python .agents/skills/release/scripts/release_helper.py record-doi --version X.Y.Z --doi <minted_doi>
   ```
2. Commit on `main` (`Record Zenodo vX.Y.Z DOI`), push to `origin/main`, and verify CI passes:
   ```bash
   git add CITATION.cff CHANGELOG.md README.md tests/test_docs.py
   git commit -m "Record Zenodo vX.Y.Z DOI"
   git push origin main
   .venv/bin/python .agents/skills/release/scripts/release_helper.py verify-ci --wait
   ```
3. Report the published GitHub Release URL, the verified Zenodo Version DOI (`https://doi.org/<minted_doi>`), and the post-tag commit SHA on `main`.
