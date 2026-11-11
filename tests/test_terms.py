"""License and terms document consistency tests."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_code_license_agrees() -> None:
    pyproject_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert 'license = "Apache-2.0"' in pyproject_text
    assert "Apache License" in license_text
    assert "Version 2.0" in license_text


def test_data_license_present() -> None:
    data_license = (ROOT / "DATA_LICENSE").read_text(encoding="utf-8")
    assert "CC0 1.0 Universal" in data_license


def test_contributing_data_section() -> None:
    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    heading = "## 5. Data license and use"
    assert heading in contributing_text

    section_after_5 = contributing_text.split(heading, maxsplit=1)[1]
    section_5 = section_after_5.split("\n## ", maxsplit=1)[0]
    assert "CC0" in section_5
    assert "DATA_LICENSE" in section_5


def test_terms_doc() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/terms.md" in readme_text

    terms_path = ROOT / "docs" / "terms.md"
    assert terms_path.is_file()
    terms_text = terms_path.read_text(encoding="utf-8")

    lead_phrases = (
        "**Maintainer.**",
        "**No special rights.**",
        "**Paid engagements.**",
        "**Governance.**",
    )
    for phrase in lead_phrases:
        assert phrase in terms_text


def test_changelog_mentions_cc0() -> None:
    changelog_path = ROOT / "CHANGELOG.md"
    assert changelog_path.is_file()
    changelog_text = changelog_path.read_text(encoding="utf-8")
    assert "CC0" in changelog_text
