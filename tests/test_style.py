"""Style, layout, docstring, and glossary resolution tests."""

from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG_DIR = ROOT / "src" / "recovery_reliability_benchmark"

DOCSTRING_SKIP: set[str] = set()
AB_HALF_SKIP: set[str] = set()

PACKAGE_MODULES = (
    "contract",
    "checks",
    "evaluate",
    "controls",
    "inputs",
    "run",
    "cli",
    "text_report",
    "protocol",
    "metadata",
    "synthetic",
    "thresholds",
    "frozen",
    "analysis",
    "excess",
    "measures",
    "spikes",
    "checks_spikes",
)


def test_source_files_under_300_lines() -> None:
    offenders: list[str] = []
    for path in sorted(PKG_DIR.rglob("*.py")):
        n_lines = len(path.read_text(encoding="utf-8").splitlines())
        if n_lines > 300:
            offenders.append(f"{path.relative_to(ROOT)}: {n_lines} lines")
    assert not offenders, "Source files exceeding 300 lines:\n" + "\n".join(offenders)


def _returns_value(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if func.returns is not None:
        if isinstance(func.returns, ast.Constant) and func.returns.value is None:
            return False
        if isinstance(func.returns, ast.Name) and func.returns.id == "None":
            return False
        return True
    for child in ast.walk(func):
        if isinstance(child, ast.Return) and child.value is not None:
            return True
    return False


def test_public_functions_have_google_docstrings() -> None:
    offenders: list[str] = []
    for path in sorted(PKG_DIR.rglob("*.py")):
        module_name = path.stem
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                symbol = f"{module_name}.{node.name}"
                if symbol in DOCSTRING_SKIP:
                    continue
                doc = ast.get_docstring(node)
                if not doc or not doc.strip():
                    offenders.append(f"{symbol}: missing class docstring")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                symbol = f"{module_name}.{node.name}"
                if symbol in DOCSTRING_SKIP:
                    continue
                doc = ast.get_docstring(node)
                if not doc or not doc.strip():
                    offenders.append(f"{symbol}: missing function docstring")
                    continue
                params = [
                    a.arg
                    for a in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs)
                    if a.arg not in ("self", "cls")
                ]
                if node.args.vararg is not None:
                    params.append(node.args.vararg.arg)
                if node.args.kwarg is not None:
                    params.append(node.args.kwarg.arg)
                if params and "Args:" not in doc:
                    offenders.append(f"{symbol}: has parameters {params} but no 'Args:' section")
                if _returns_value(node) and "Returns:" not in doc:
                    offenders.append(f"{symbol}: returns a value but has no 'Returns:' section")
    assert not offenders, "Public docstring violations:\n" + "\n".join(offenders)


def test_glossary_symbols_resolve() -> None:
    glossary_text = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
    tokens = re.findall(r"`([^`]+)`", glossary_text)
    mod_alt = "|".join(PACKAGE_MODULES)
    symbol_re = re.compile(rf"^({mod_alt})(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")

    unresolved: list[str] = []
    checked = 0
    for raw_token in tokens:
        cleaned = re.sub(r"\(.*\)$", "", raw_token.strip())
        if cleaned.endswith((".py", ".csv", ".json")):
            continue
        if not symbol_re.match(cleaned):
            continue
        checked += 1
        mod_name, *attrs = cleaned.split(".")
        try:
            obj: object = importlib.import_module(f"recovery_reliability_benchmark.{mod_name}")
            for attr in attrs:
                obj = getattr(obj, attr)
        except (ImportError, AttributeError):
            unresolved.append(raw_token)
    assert checked > 0
    assert not unresolved, "Unresolved GLOSSARY.md code symbols:\n" + "\n".join(unresolved)


def test_no_ab_half_names() -> None:
    pattern = re.compile(r"_[AB]\b|\"n_[AB]\"|\"half [AB]\"|half [AB]")
    offenders: list[str] = []
    for folder in ("src", "tests"):
        for path in sorted((ROOT / folder).rglob("*")):
            if not path.is_file() or path.suffix != ".py":
                continue
            rel = str(path.relative_to(ROOT))
            if rel in AB_HALF_SKIP:
                continue
            text = path.read_text(encoding="utf-8")
            for lineno, line in enumerate(text.splitlines(), start=1):
                match = pattern.search(line)
                if match is not None:
                    offenders.append(f"{rel}:{lineno}: matched {match.group(0)!r} in {line.strip()!r}")
    assert not offenders, "Forbidden A/B half naming found:\n" + "\n".join(offenders)
