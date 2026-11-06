"""Recovery Reliability Benchmark package."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .contract import (
    SPEC_VERSION,
    ContractViolation,
    Requirement,
    read_tables,
    validate,
)
from .evaluate import (
    reliability_ceiling,
    split_halves,
)
from .metadata import (
    Condition,
    Preparation,
)
from .protocol import (
    Burst,
    Protocol,
    Pulse,
    Train,
    default_pulse,
)
from .run import run

try:
    __version__ = version("recovery-reliability-benchmark")
except PackageNotFoundError:
    __version__ = "0.0.0+unknown"

__all__ = [
    "SPEC_VERSION",
    "Burst",
    "Condition",
    "ContractViolation",
    "Preparation",
    "Protocol",
    "Pulse",
    "Requirement",
    "Train",
    "__version__",
    "default_pulse",
    "read_tables",
    "reliability_ceiling",
    "run",
    "split_halves",
    "validate",
]
