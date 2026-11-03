"""Documentation consistency tests for the Recovery Reliability Benchmark."""

from __future__ import annotations

from pathlib import Path

import pytest

from recovery_reliability_benchmark.contract import (
    SPEC_VERSION,
    ContractViolation,
    Requirement,
    validate,
)
from recovery_reliability_benchmark.synthetic import make_tables

ROOT = Path(__file__).resolve().parent.parent
MEASURES = ["tau", "amplitude"]


def test_spec_lists_every_requirement() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    for member in Requirement:
        if member is Requirement.SCHEMA:
            continue
        assert f"**{member.value} — " in spec_text
    assert "SCHEMA" in spec_text


def test_spec_version_matches_code() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert f"**Version {SPEC_VERSION}**" in spec_text


def test_spec_documents_example_message() -> None:
    expected = "MD-6 failed. Post-stimulus window 0.4 s, requires 2.0 s."
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert expected in spec_text

    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=0.4)
    assert str(exc_info.value) == expected


def test_spec_quickstart_matches_readme() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert (
        "rrb-check units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0"
        in spec_text
    )
    assert (
        "rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0"
        in readme_text
    )


def test_docs_carry_license_notice() -> None:
    for doc_name in ("SPEC.md", "CONTRIBUTING.md", "METHOD.md", "README.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8")
        assert "LICENSE-DOCS" in text, f"{doc_name} is missing LICENSE-DOCS reference"
