"""Manage the frozen-layer manifest and AST snapshots (--init, --check, --update)."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib
import json
import pkgutil
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

import recovery_reliability_benchmark  # noqa: E402
from recovery_reliability_benchmark.frozen import (  # noqa: E402
    FROZEN_CONSTANTS,
    FROZEN_FUNCTIONS,
    normalized_source,
)

FROZEN_DIR = ROOT / "frozen"
SNAP_DIR = FROZEN_DIR / "snapshots"
MANIFEST_PATH = FROZEN_DIR / "manifest.json"


def _resolve_constant(qualname: str) -> Any:
    mod_name, attr_name = qualname.rsplit(".", 1)
    return getattr(importlib.import_module(mod_name), attr_name)


def _compute_state() -> tuple[dict[str, Any], dict[str, str]]:
    for info in pkgutil.iter_modules(recovery_reliability_benchmark.__path__):
        importlib.import_module(f"recovery_reliability_benchmark.{info.name}")
    functions: dict[str, dict[str, str]] = {}
    sources: dict[str, str] = {}
    for qualname, fn in sorted(FROZEN_FUNCTIONS.items()):
        src = normalized_source(fn)
        sources[qualname] = src
        functions[qualname] = {
            "snapshot": f"frozen/snapshots/{qualname}.txt",
            "sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(),
        }
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    manifest: dict[str, Any] = {
        "version": str(pyproject["project"]["version"]),
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "functions": functions,
        "constants": {q: _resolve_constant(q) for q in sorted(FROZEN_CONSTANTS)},
    }
    return manifest, sources


def _write_state(manifest: dict[str, Any], sources: dict[str, str]) -> None:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    for qualname, src in sources.items():
        (ROOT / manifest["functions"][qualname]["snapshot"]).write_text(src, encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _compare_states(
    old_manifest: dict[str, Any], new_manifest: dict[str, Any], new_sources: dict[str, str]
) -> list[str]:
    diffs: list[str] = []
    old_fns, new_fns = old_manifest.get("functions", {}), new_manifest["functions"]
    for name in sorted(set(old_fns) | set(new_fns)):
        if name not in old_fns or name not in new_fns:
            diffs.append(f"Function {'added' if name in new_fns else 'removed'}: {name}")
            continue
        snap_path = ROOT / old_fns[name]["snapshot"]
        old_src = snap_path.read_text(encoding="utf-8") if snap_path.is_file() else ""
        if old_src != new_sources[name] or old_fns[name]["sha256"] != new_fns[name]["sha256"]:
            udiff = difflib.unified_diff(
                old_src.splitlines(keepends=True),
                new_sources[name].splitlines(keepends=True),
                fromfile=f"manifest:{name}",
                tofile=f"current:{name}",
            )
            diffs.append("".join(udiff).rstrip("\n"))
    old_consts, new_consts = old_manifest.get("constants", {}), new_manifest["constants"]
    for name in sorted(set(old_consts) | set(new_consts)):
        if old_consts.get(name) != new_consts.get(name):
            diffs.append(f"Constant {name}: {old_consts.get(name)!r} -> {new_consts.get(name)!r}")
    return diffs


def _has_changelog_frozen_line(version: str) -> bool:
    pattern = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s|-|$)")
    in_section = False
    for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if pattern.match(line):
            in_section = True
        elif in_section and line.startswith("## "):
            break
        elif in_section and line.strip().lstrip("-* ").startswith("Frozen:"):
            return True
    return False


def main(argv: list[str] | None = None) -> int:
    """Run the freeze CLI in --init, --check, or --update mode."""
    parser = argparse.ArgumentParser(description="Manage frozen-layer snapshots and manifest.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="Create initial manifest and snapshots.")
    group.add_argument("--check", action="store_true", help="Verify current code matches snapshots.")
    group.add_argument("--update", action="store_true", help="Update snapshots after a version bump.")
    args = parser.parse_args(argv)

    manifest, sources = _compute_state()
    if args.init:
        if MANIFEST_PATH.exists():
            print(f"error: {MANIFEST_PATH} already exists; refusing --init.", file=sys.stderr)
            return 1
        _write_state(manifest, sources)
        return 0
    if not MANIFEST_PATH.is_file():
        print(f"error: {MANIFEST_PATH} does not exist; run --init first.", file=sys.stderr)
        return 1
    old_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    diffs = _compare_states(old_manifest, manifest, sources)
    if args.check:
        if diffs:
            print("\n".join(diffs))
            return 1
        return 0
    if manifest["version"] == old_manifest.get("version"):
        print("error: pyproject.toml version matches manifest version; bump version first.", file=sys.stderr)
        return 1
    if not _has_changelog_frozen_line(manifest["version"]):
        print(f"error: CHANGELOG.md has no 'Frozen:' line under {manifest['version']}.", file=sys.stderr)
        return 1
    _write_state(manifest, sources)
    print("\n".join([f"Updated frozen manifest to {manifest['version']}.", *diffs]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
