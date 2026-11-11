"""Guardrail tests for the frozen layer of the Recovery Reliability Benchmark."""

from __future__ import annotations

import difflib
import hashlib
import importlib
import importlib.util
import json
import pkgutil
import shutil
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

import recovery_reliability_benchmark
from recovery_reliability_benchmark.frozen import (
    FROZEN_CONSTANTS,
    FROZEN_FUNCTIONS,
    normalized_source,
)

for _info in pkgutil.iter_modules(recovery_reliability_benchmark.__path__):
    importlib.import_module(f"recovery_reliability_benchmark.{_info.name}")

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "frozen" / "manifest.json"


def _load_manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _resolve_constant(qualname: str) -> Any:
    mod_name, attr_name = qualname.rsplit(".", 1)
    return getattr(importlib.import_module(mod_name), attr_name)


def test_registry_matches_manifest() -> None:
    manifest = _load_manifest()
    assert set(FROZEN_FUNCTIONS.keys()) == set(manifest["functions"].keys())


def test_snapshots_match() -> None:
    manifest = _load_manifest()
    running_py = f"{sys.version_info.major}.{sys.version_info.minor}"
    manifest_py = manifest["python"]
    if running_py != manifest_py:
        pytest.skip(f"Running Python {running_py} differs from manifest Python {manifest_py}.")

    for name, fn in sorted(FROZEN_FUNCTIONS.items()):
        entry = manifest["functions"][name]
        snap_path = ROOT / entry["snapshot"]
        expected = snap_path.read_text(encoding="utf-8")
        actual = normalized_source(fn)
        actual_sha = hashlib.sha256(actual.encode("utf-8")).hexdigest()
        if actual != expected or actual_sha != entry["sha256"]:
            diff = "".join(
                difflib.unified_diff(
                    expected.splitlines(keepends=True),
                    actual.splitlines(keepends=True),
                    fromfile=f"snapshot:{name}",
                    tofile=f"current:{name}",
                )
            )
            pytest.fail(
                f"Frozen function {name} changed. If this is intended: add a 'Frozen:' line under "
                "the version in CHANGELOG.md and run python scripts/freeze.py --amend while the "
                "version is not tagged, or bump the version in pyproject.toml and run "
                f"python scripts/freeze.py --update once it is. See frozen/README.md.\n{diff}",
                pytrace=False,
            )


def test_constants_match() -> None:
    manifest = _load_manifest()
    assert set(FROZEN_CONSTANTS.keys()) == set(manifest["constants"].keys())
    for name in sorted(FROZEN_CONSTANTS):
        assert _resolve_constant(name) == manifest["constants"][name], f"Frozen constant {name} changed."


def test_manifest_version_matches_package() -> None:
    manifest = _load_manifest()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_version = str(pyproject["project"]["version"])
    assert manifest["version"] == pyproject_version == recovery_reliability_benchmark.__version__


def test_frozen_md_lists_every_name() -> None:
    frozen_md = (ROOT / "frozen" / "README.md").read_text(encoding="utf-8")
    for name in (*sorted(FROZEN_FUNCTIONS), *sorted(FROZEN_CONSTANTS)):
        assert f"`{name}`" in frozen_md, f"{name} is missing inside backticks in frozen/README.md"


def test_update_version_only_refresh(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("freeze_script", ROOT / "scripts" / "freeze.py")
    assert spec is not None and spec.loader is not None
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)

    shutil.copytree(ROOT / "frozen", tmp_path / "frozen")
    tmp_manifest = tmp_path / "frozen" / "manifest.json"

    old_data = json.loads(tmp_manifest.read_text(encoding="utf-8"))
    old_data["version"] = "0.0.1"
    tmp_manifest.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")

    manifest, sources = freeze._compute_state()
    (tmp_path / "CHANGELOG.md").write_text(
        f"# Changelog\n\n## [{manifest['version']}]\n\n- Docs update.\n",
        encoding="utf-8",
    )
    assert freeze.update_frozen(manifest, sources, manifest_path=tmp_manifest, root=tmp_path) == 0
    assert json.loads(tmp_manifest.read_text(encoding="utf-8"))["version"] == manifest["version"]

    old_data["version"] = "0.0.1"
    tmp_manifest.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")
    first_fn = sorted(sources)[0]
    modified_sources = {**sources, first_fn: sources[first_fn] + "    pass\n"}
    assert freeze.update_frozen(manifest, modified_sources, manifest_path=tmp_manifest, root=tmp_path) == 1


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
