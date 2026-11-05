"""Documentation consistency tests for the Recovery Reliability Benchmark."""

from __future__ import annotations

import tomllib
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
    expected = "min-dataset-6 failed. Post-stimulus window 0.4 s, requires 2.0 s."
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert expected in spec_text

    units, responses = make_tables()
    with pytest.raises(ContractViolation) as exc_info:
        validate(units, responses, MEASURES, post_stim_window_s=0.4)
    assert str(exc_info.value) == expected


def test_spec_quickstart_matches_readme() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    readme_normalized = " ".join(readme_text.replace("\\\n", " ").split())
    assert "rrb-check units.csv responses.csv --measures tau,amplitude --post-stim-window-s 2.0" in spec_text
    assert (
        "rrb-check examples/units.csv examples/responses.csv --measures tau,amplitude --post-stim-window-s 2.0"
        in readme_normalized
    )


def test_docs_carry_license_notice() -> None:
    for doc_name in ("SPEC.md", "CONTRIBUTING.md", "METHOD.md", "README.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8")
        assert "LICENSE-DOCS" in text, f"{doc_name} is missing LICENSE-DOCS reference"


def test_doc_titles() -> None:
    for doc_name in ("METHOD.md", "CONTRIBUTING.md", "SPEC.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8")
        assert "# Recovery Reliability Benchmark" in text
        assert "Recovery Measurement Benchmark" not in text


def test_contributing_links_spec() -> None:
    text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "SPEC.md" in text
    assert "01-dataset-conformance-spec.md" not in text


def test_anchor_claim_pinned() -> None:
    anchor_claim = (
        "Recovery kinetics after a conditioning load are an established mechanistic "
        "measurement in synaptic and cardiac physiology. They are not used as an "
        "endpoint in pharmacology screening or tissue release testing, and their "
        "per-unit reliability has not been reported."
    )
    for doc_name in ("README.md", "SPEC.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8")
        assert anchor_claim in text


def test_method_reference_implementation() -> None:
    text = (ROOT / "METHOD.md").read_text(encoding="utf-8")
    assert "Reference implementation: `src/recovery_reliability_benchmark/evaluate.py`" in text
    assert "(planned; not yet in the repository)" not in text


def test_scope_atlas_and_sidecar_docs() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    for phrase in (
        "## 0. Scope",
        "Preparation and condition metadata",
        "Raw data",
        "Fate",
    ):
        assert phrase in spec_text

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "protocol fingerprint, condition, preparation" in readme_text

    changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Scope" in changelog_text


def test_thresholds_doc_referenced_in_spec() -> None:
    assert (ROOT / "docs" / "thresholds.md").is_file()
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "docs/thresholds.md" in spec_text


def test_citation_cff() -> None:
    cff_path = ROOT / "CITATION.cff"
    assert cff_path.is_file()
    cff_text = cff_path.read_text(encoding="utf-8")
    pyproject_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pyproject_version = pyproject_data["project"]["version"]

    try:
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        assert "version: 0.1.0" in cff_text
        cff_version = next(
            line.split(":", 1)[1].strip().strip('"').strip("'")
            for line in cff_text.splitlines()
            if line.startswith("version:")
        )
    else:
        parsed = yaml.safe_load(cff_text)
        assert isinstance(parsed, dict)
        cff_version = str(parsed["version"])

    assert cff_version == pyproject_version


def test_release_docs_sections() -> None:
    changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0]" in changelog_text

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Status" in readme_text
    assert "## Repository layout" in readme_text
    assert "CITATION.cff" in readme_text
