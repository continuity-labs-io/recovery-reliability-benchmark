"""Tests for top-level package exports of recovery_reliability_benchmark."""

from __future__ import annotations

import recovery_reliability_benchmark
from recovery_reliability_benchmark import (
    SPEC_VERSION,
    Burst,
    Condition,
    ContractViolation,
    Preparation,
    Protocol,
    Pulse,
    Requirement,
    Train,
    __all__,
    __version__,
    default_pulse,
    read_tables,
    reliability_ceiling,
    run,
    split_halves,
    validate,
)


def test_exports() -> None:
    exported = {
        "validate": validate,
        "ContractViolation": ContractViolation,
        "Requirement": Requirement,
        "read_tables": read_tables,
        "SPEC_VERSION": SPEC_VERSION,
        "Pulse": Pulse,
        "Burst": Burst,
        "Train": Train,
        "Protocol": Protocol,
        "default_pulse": default_pulse,
        "split_halves": split_halves,
        "reliability_ceiling": reliability_ceiling,
        "run": run,
        "Preparation": Preparation,
        "Condition": Condition,
        "__version__": __version__,
    }
    assert isinstance(__version__, str) and len(__version__) > 0
    assert set(__all__) == set(exported.keys())
    assert set(recovery_reliability_benchmark.__all__) == set(exported.keys())
