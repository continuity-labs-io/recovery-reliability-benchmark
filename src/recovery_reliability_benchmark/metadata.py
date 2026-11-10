"""Preparation and condition metadata sidecar schemas for the Recovery Reliability Benchmark."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from .contract import ContractViolation, Requirement
from .measures import AnalysisParams
from .protocol import Protocol

PreparationType = Literal[
    "dissociated_culture",
    "organotypic_slice",
    "organoid",
    "engineered_neural_tissue",
]
AgeBasis = Literal[
    "DIV",
    "days_post_plating",
    "days_post_differentiation",
]


class Exclusion(BaseModel):
    """Contributor-declared unit or trial exclusion in preparation.json."""

    model_config = ConfigDict(frozen=True)

    kind: Literal["unit", "trial"]
    id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class Preparation(BaseModel):
    """Preparation metadata sidecar (preparation.json)."""

    model_config = ConfigDict(frozen=True)

    preparation_id: str
    species: str
    preparation_type: PreparationType
    age_days: float = Field(ge=0)
    age_basis: AgeBasis
    line_or_donor_id: str
    instrument: str
    raw_data_url: str | None = None
    exclusions: list[Exclusion] = Field(default_factory=list)


class Condition(BaseModel):
    """Single condition metadata entry in conditions.json."""

    model_config = ConfigDict(frozen=True)

    protocol: Protocol | None = None
    compound: str | None = None
    dose: float | None = None
    dose_unit: str | None = None
    vehicle: str | None = None

    @property
    def fingerprint(self) -> str | None:
        """Return the protocol SHA-256 fingerprint, or None when no protocol is set."""
        return self.protocol.fingerprint() if self.protocol is not None else None


_CONDITIONS_ADAPTER: TypeAdapter[dict[str, Condition]] = TypeAdapter(dict[str, Condition])


def _first_error(exc: ValidationError | json.JSONDecodeError | ValueError) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(part) for part in first.get("loc", ()))
            msg = first.get("msg", str(exc))
            return f"{loc}: {msg}" if loc else str(msg)
    return str(exc)


def load_preparation(path: str | Path) -> Preparation:
    """Load and validate a preparation.json metadata sidecar.

    Args:
        path: Path to the preparation.json sidecar file.

    Returns:
        Validated Preparation model.

    Raises:
        ContractViolation: With Requirement.SCHEMA if the JSON is malformed or invalid.
    """
    raw = Path(path).read_text(encoding="utf-8")
    try:
        return Preparation.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        raise ContractViolation(
            Requirement.SCHEMA,
            f"preparation.json: {_first_error(exc)}",
        ) from exc


def load_conditions(path: str | Path) -> dict[str, Condition]:
    """Load and validate a conditions.json metadata sidecar.

    Args:
        path: Path to the conditions.json sidecar file.

    Returns:
        Dictionary mapping condition labels to validated Condition models.

    Raises:
        ContractViolation: With Requirement.SCHEMA if the JSON is malformed or invalid.
    """
    raw = Path(path).read_text(encoding="utf-8")
    try:
        return _CONDITIONS_ADAPTER.validate_json(raw)
    except (ValidationError, json.JSONDecodeError, ValueError) as exc:
        raise ContractViolation(
            Requirement.SCHEMA,
            f"conditions.json: {_first_error(exc)}",
        ) from exc


def load_analysis(path: str | Path) -> AnalysisParams:
    """Load and validate an analysis.json parameters sidecar.

    Args:
        path: Path to the analysis.json sidecar file.

    Returns:
        Validated AnalysisParams instance.

    Raises:
        ContractViolation: With Requirement.SCHEMA if the file is missing, malformed, or invalid.
    """
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("expected a JSON object.")
        return AnalysisParams.from_dict(data)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ContractViolation(
            Requirement.SCHEMA,
            f"analysis.json: {exc}",
        ) from exc


def write_analysis(params: AnalysisParams, path: str | Path) -> None:
    """Write an AnalysisParams instance to an analysis.json file as indented JSON.

    Args:
        params: AnalysisParams instance to serialize.
        path: Destination file path.
    """
    Path(path).write_text(json.dumps(params.to_dict(), indent=2) + "\n", encoding="utf-8")
