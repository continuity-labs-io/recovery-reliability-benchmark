"""Manage the frozen-layer manifest and AST snapshots (--init, --check, --update, --amend)."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import importlib
import json
import pkgutil
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any

import recovery_reliability_benchmark

from .frozen import FROZEN_CONSTANTS, FROZEN_FUNCTIONS, normalized_source

ROOT = Path(__file__).resolve().parents[2]
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


def _write_state(
    manifest: dict[str, Any],
    sources: dict[str, str],
    manifest_path: Path = MANIFEST_PATH,
    root: Path = ROOT,
) -> None:
    for qualname, src in sources.items():
        snap_path = root / manifest["functions"][qualname]["snapshot"]
        snap_path.parent.mkdir(parents=True, exist_ok=True)
        snap_path.write_text(src, encoding="utf-8")
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    listed = {(root / entry["snapshot"]).resolve() for entry in manifest["functions"].values()}
    for snap_file in (root / "frozen" / "snapshots").glob("*.txt"):
        if snap_file.resolve() not in listed:
            snap_file.unlink()


def _compare_states(
    old_manifest: dict[str, Any],
    new_manifest: dict[str, Any],
    new_sources: dict[str, str],
    root: Path = ROOT,
) -> list[str]:
    diffs: list[str] = []
    old_fns, new_fns = old_manifest.get("functions", {}), new_manifest["functions"]
    for name in sorted(set(old_fns) | set(new_fns)):
        if name not in old_fns or name not in new_fns:
            diffs.append(f"Function {'added' if name in new_fns else 'removed'}: {name}")
            continue
        snap_path = root / old_fns[name]["snapshot"]
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


def _has_changelog_frozen_line(version: str, root: Path = ROOT) -> bool:
    pattern = re.compile(rf"^## \[?{re.escape(version)}\]?(?:\s|-|$)")
    in_section = False
    for line in (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if pattern.match(line):
            in_section = True
        elif in_section and line.startswith("## "):
            break
        elif in_section and line.strip().lstrip("-* ").startswith("Frozen:"):
            return True
    return False


def _git_tag_exists(version: str, root: Path = ROOT) -> bool:
    result = subprocess.run(
        ["git", "tag", "--list", f"v{version}"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def update_frozen(
    manifest: dict[str, Any],
    sources: dict[str, str],
    manifest_path: Path = MANIFEST_PATH,
    root: Path = ROOT,
    amend: bool = False,
    tag_exists: Callable[[str], bool] | None = None,
) -> int:
    """Update or amend frozen manifest and snapshots.

    Args:
        manifest: Newly computed manifest dictionary.
        sources: Mapping of qualified function names to normalized source strings.
        manifest_path: Path to the stored manifest JSON file.
        root: Repository root directory.
        amend: If True, re-snapshot in place while the version is not tagged.
        tag_exists: Callable checking whether ``v<version>`` exists in git tags.

    Returns:
        Exit status code (0 on success, 1 on error).
    """
    old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    version = str(manifest["version"])
    if amend:
        if version != old_manifest.get("version"):
            print(
                "error: --amend keeps the version, but pyproject.toml differs; use --update.",
                file=sys.stderr,
            )
            return 1
        check_tag = tag_exists if tag_exists is not None else lambda v: _git_tag_exists(v, root=root)
        try:
            is_tagged = check_tag(version)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"error: cannot check git tags ({exc}).", file=sys.stderr)
            return 1
        if is_tagged:
            print(f"error: v{version} is tagged; bump the version and use --update.", file=sys.stderr)
            return 1
    elif version == old_manifest.get("version"):
        print(
            "error: pyproject.toml version matches manifest version; "
            "bump version first (or use --amend while the version is not tagged).",
            file=sys.stderr,
        )
        return 1

    diffs = _compare_states(old_manifest, manifest, sources, root=root)
    if diffs and not _has_changelog_frozen_line(version, root=root):
        print(f"error: CHANGELOG.md has no 'Frozen:' line under {version}.", file=sys.stderr)
        return 1
    _write_state(manifest, sources, manifest_path=manifest_path, root=root)
    verb = "Amended" if amend else "Updated"
    print("\n".join([f"{verb} frozen manifest at {version}.", *diffs]))
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the freeze CLI in ``--init``, ``--check``, ``--update``, or ``--amend`` mode.

    Args:
        argv: Optional CLI argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Exit status code (0 on success, 1 on mismatch or error).
    """
    parser = argparse.ArgumentParser(description="Manage frozen-layer snapshots and manifest.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--init", action="store_true", help="Create initial manifest and snapshots.")
    group.add_argument("--check", action="store_true", help="Verify current code matches snapshots.")
    group.add_argument("--update", action="store_true", help="Update snapshots after a version bump.")
    group.add_argument(
        "--amend",
        action="store_true",
        help="Re-snapshot frozen items in place while the version is not tagged.",
    )
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
    if args.check:
        old_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        diffs = _compare_states(old_manifest, manifest, sources)
        if diffs:
            print("\n".join(diffs))
            return 1
        return 0
    return update_frozen(manifest, sources, amend=args.amend)


if __name__ == "__main__":
    raise SystemExit(main())
