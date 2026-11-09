"""Frozen-layer registration and AST normalization for the Recovery Reliability Benchmark."""

from __future__ import annotations

import ast
import inspect
import textwrap
from collections.abc import Callable
from typing import Any

FROZEN_FUNCTIONS: dict[str, Callable[..., Any]] = {}
FROZEN_CONSTANTS: dict[str, str] = {}


def register(fn: Callable[..., Any], reference: str) -> Callable[..., Any]:
    """Register a callable in FROZEN_FUNCTIONS and attach its specification reference.

    Args:
        fn: Function or method implementing a frozen procedure step.
        reference: Section reference in METHOD.md or SPEC.md.

    Returns:
        The input callable ``fn`` unchanged, with ``__frozen_reference__`` set.
    """
    key = f"{fn.__module__}.{fn.__qualname__}"
    FROZEN_FUNCTIONS[key] = fn
    fn.__frozen_reference__ = reference  # type: ignore[attr-defined]
    return fn


def frozen(reference: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a decorator that registers a function in FROZEN_FUNCTIONS.

    Args:
        reference: Section reference in METHOD.md or SPEC.md.

    Returns:
        Decorator that registers ``fn`` and returns it unchanged.
    """

    def _decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        return register(fn, reference)

    return _decorator


def freeze_constant(module_name: str, name: str, reference: str) -> None:
    """Register a module-level constant in FROZEN_CONSTANTS.

    Args:
        module_name: Dotted module name (or short submodule name) defining the constant.
        name: Attribute name of the constant on the module.
        reference: Section reference in METHOD.md or SPEC.md.
    """
    pkg = "recovery_reliability_benchmark"
    full_mod = module_name if module_name.startswith(pkg) else f"{pkg}.{module_name}"
    FROZEN_CONSTANTS[f"{full_mod}.{name}"] = reference


def normalized_source(fn: Callable[..., Any]) -> str:
    """Return the AST-normalized source of ``fn`` with its docstring and comments removed.

    Args:
        fn: Callable whose source code is to be normalized.

    Returns:
        Normalized Python source string from ``ast.unparse`` with a trailing newline.
    """
    src = textwrap.dedent(inspect.getsource(fn))
    tree = ast.parse(src)
    node = tree.body[0]
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.unparse(node) + "\n"
