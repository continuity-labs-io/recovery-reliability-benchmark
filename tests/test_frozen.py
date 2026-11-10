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
                f"Frozen function {name} changed. If this is intended: bump the "
                "version in pyproject.toml, add a 'Frozen:' line under that version in CHANGELOG.md, "
                f"run python scripts/freeze.py --update. See FROZEN.md.\n{diff}",
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
    frozen_md = (ROOT / "FROZEN.md").read_text(encoding="utf-8")
    for name in (*sorted(FROZEN_FUNCTIONS), *sorted(FROZEN_CONSTANTS)):
        assert f"`{name}`" in frozen_md, f"{name} is missing inside backticks in FROZEN.md"


def test_update_version_only_refresh(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("freeze_script", ROOT / "scripts" / "freeze.py")
    assert spec is not None and spec.loader is not None
    freeze = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(freeze)

    shutil.copytree(ROOT / "frozen", tmp_path / "frozen")
    shutil.copy2(ROOT / "CHANGELOG.md", tmp_path / "CHANGELOG.md")
    tmp_manifest = tmp_path / "frozen" / "manifest.json"

    old_data = json.loads(tmp_manifest.read_text(encoding="utf-8"))
    old_data["version"] = "0.0.1"
    tmp_manifest.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")

    manifest, sources = freeze._compute_state()
    assert freeze.update_frozen(manifest, sources, manifest_path=tmp_manifest, root=tmp_path) == 0
    assert json.loads(tmp_manifest.read_text(encoding="utf-8"))["version"] == manifest["version"]

    old_data["version"] = "0.0.1"
    tmp_manifest.write_text(json.dumps(old_data, indent=2) + "\n", encoding="utf-8")
    first_fn = sorted(sources)[0]
    modified_sources = {**sources, first_fn: sources[first_fn] + "    pass\n"}
    assert freeze.update_frozen(manifest, modified_sources, manifest_path=tmp_manifest, root=tmp_path) == 1
