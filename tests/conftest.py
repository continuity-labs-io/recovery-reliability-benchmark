"""Shared pytest fixtures and conforming dataset factory for benchmark tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

import recovery_reliability_benchmark.report as report_mod
from recovery_reliability_benchmark.synthetic import make_tables


def _fast_write_halves_figure(
    result: dict[str, Any],
    _inputs: object,
    halves_path: Path,
) -> bool:
    if "matplotlib" in sys.modules and sys.modules["matplotlib"] is None:
        return False
    if importlib.util.find_spec("matplotlib") is None:
        return False
    if result.get("status") == "ok":
        halves_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    return True


@pytest.fixture(autouse=True)
def stub_halves_figure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid importing matplotlib and rasterizing PNGs during unit tests."""
    monkeypatch.setattr(report_mod, "_write_halves_figure", _fast_write_halves_figure)


@pytest.fixture
def tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a fresh conforming (units, responses) pair."""
    return make_tables()
