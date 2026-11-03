"""Shared pytest fixtures and conforming dataset factory for benchmark tests."""

from __future__ import annotations

import pandas as pd
import pytest

from recovery_reliability_benchmark.synthetic import make_tables


@pytest.fixture
def tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return a fresh conforming (units, responses) pair."""
    return make_tables()

