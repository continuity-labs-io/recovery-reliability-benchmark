"""Strict JSON serialization replacing non-finite floats with ``null``."""

from __future__ import annotations

import json
from typing import Any

import numpy as np


def _replace_non_finite(value: Any) -> Any:
    """Recursively replace non-finite float values with ``None`` in containers."""
    if isinstance(value, dict):
        return {key: _replace_non_finite(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_replace_non_finite(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_replace_non_finite(item) for item in value)
    if isinstance(value, bool):
        return value
    if isinstance(value, (float, np.floating)):
        if not np.isfinite(value):
            return None
        return value if isinstance(value, float) else float(value)
    return value


def dumps_strict(
    value: Any,
    *,
    indent: int | str | None = None,
    sort_keys: bool = False,
) -> str:
    """Serialize a result structure to RFC 8259 strict JSON text.

    Replaces every non-finite floating-point value (``NaN``, ``Infinity``, and
    ``-Infinity``, including NumPy floating scalars) with ``None`` (serialized as
    JSON ``null``) at any nesting depth inside dictionaries, lists, and tuples,
    without mutating ``value`` in memory. Calls ``json.dumps`` with
    ``allow_nan=False`` so any non-finite value that escapes conversion raises
    ``ValueError`` instead of emitting invalid JSON tokens.

    Args:
        value: JSON-serializable Python value (nested dicts, lists, tuples, and scalars).
        indent: Indentation width or string passed through to ``json.dumps``.
        sort_keys: Whether dictionary keys are sorted in the serialized output.

    Returns:
        Strict JSON string containing no ``NaN`` or ``Infinity`` constants.

    Raises:
        TypeError: If ``value`` contains an object of a non-JSON-serializable type,
            or if ``sort_keys=True`` encounters mutually incomparable dictionary keys.
        ValueError: If a non-finite float escapes conversion (for example as a dict key).
    """
    cleaned = _replace_non_finite(value)
    return json.dumps(cleaned, allow_nan=False, indent=indent, sort_keys=sort_keys)
