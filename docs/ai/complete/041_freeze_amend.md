Task: let frozen code be re-snapshotted before a version is tagged. Tooling only; no frozen function or
constant changes in this prompt.

Why: pyproject.toml and frozen/manifest.json both say 0.2.0, and v0.2.0 is not tagged. `freeze.py --update`
refuses when the version is unchanged, so a defect found before the tag cannot be fixed.

1. scripts/freeze.py: add `--amend` to the mutually exclusive group.
   update_frozen(manifest, sources, manifest_path=MANIFEST_PATH, root=ROOT, amend=False, tag_exists=None) -> int
   - tag_exists is a callable version -> bool. Default: run `git tag --list v<version>` in root and
     return whether the output is non-empty.
   - amend=True:
     - manifest version != stored manifest version: print
       "error: --amend keeps the version, but pyproject.toml differs; use --update." and return 1.
     - git cannot be run (OSError or CalledProcessError): print "error: cannot check git tags (<exc>)." and
       return 1.
     - the tag exists: print "error: v<version> is tagged; bump the version and use --update." and return 1.
   - amend=False keeps today's rule. Its message becomes "error: pyproject.toml version matches manifest
     version; bump version first (or use --amend while the version is not tagged)."
   - Both modes still require the CHANGELOG `Frozen:` line under the version when a frozen item changed.
   - Success prints "Amended frozen manifest at <version>." or "Updated frozen manifest at <version>.",
     then the diffs.
2. _write_state: after writing, delete every frozen/snapshots/*.txt that the manifest does not list.
3. tests/test_frozen.py: in test_snapshots_match, the failure text names both routes: `--amend` while the
   version is not tagged, version bump plus `--update` once it is. Append these tests unchanged:

```python
def _load_freeze_script() -> Any:
    spec = importlib.util.spec_from_file_location("freeze_script", ROOT / "scripts" / "freeze.py")
    assert spec is not None and spec.loader is not None
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)
    return freeze


def test_snapshot_folder_matches_manifest() -> None:
    manifest = _load_manifest()
    on_disk = {p.name for p in (ROOT / "frozen" / "snapshots").glob("*.txt")}
    assert on_disk == {Path(entry["snapshot"]).name for entry in manifest["functions"].values()}


def test_amend_before_tag(tmp_path: Path) -> None:
    freeze = _load_freeze_script()
    shutil.copytree(ROOT / "frozen", tmp_path / "frozen")
    tmp_manifest = tmp_path / "frozen" / "manifest.json"
    stale = tmp_path / "frozen" / "snapshots" / "recovery_reliability_benchmark.removed.function.txt"
    stale.write_text("def function():\n    pass\n", encoding="utf-8")
    manifest, sources = freeze._compute_state()
    version = manifest["version"]
    first_fn = sorted(sources)[0]
    changed = {**sources, first_fn: sources[first_fn] + "    pass\n"}
    changelog = tmp_path / "CHANGELOG.md"

    def amend(tagged: bool) -> int:
        return freeze.update_frozen(
            manifest,
            changed,
            manifest_path=tmp_manifest,
            root=tmp_path,
            amend=True,
            tag_exists=lambda _v: tagged,
        )

    changelog.write_text(f"# Changelog\n\n## [{version}]\n\n- Docs update.\n", encoding="utf-8")
    assert amend(tagged=False) == 1
    changelog.write_text(f"# Changelog\n\n## [{version}]\n\n- Frozen: example change.\n", encoding="utf-8")
    assert amend(tagged=True) == 1
    assert stale.is_file()
    assert amend(tagged=False) == 0
    assert not stale.exists()
    snapshot = tmp_path / "frozen" / "snapshots" / f"{first_fn}.txt"
    assert snapshot.read_text(encoding="utf-8") == changed[first_fn]

    old_data = json.loads(tmp_manifest.read_text(encoding="utf-8"))
    old_data["version"] = "0.0.1"
    tmp_manifest.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")
    assert amend(tagged=False) == 1
```

4. frozen/README.md "How to change frozen code" and AGENTS.md frozen-layer rule: add the pre-tag route
   (keep the version, add the `Frozen:` line under that version in CHANGELOG.md, run
   `python scripts/freeze.py --amend`; it refuses once v<version> is tagged).
5. Run `python scripts/freeze.py --amend` once. It must print "Amended frozen manifest at 0.2.0." with no
   diffs. If it prints diffs or removes snapshot files, list them in the report.

Gate: `python scripts/freeze.py --check` exits 0; ruff check, ruff format --check and the full pytest suite
pass. Report: the suite count and anything step 5 printed beyond the first line.
