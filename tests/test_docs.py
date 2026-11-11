"""Documentation consistency tests for the Recovery Reliability Benchmark."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from recovery_reliability_benchmark.contract import (
    INCLUSION_RULE,
    MD2_MUST,
    MD2_SHOULD,
    MD3_MUST,
    MD3_SHOULD,
    MD6_MUST,
    MD7_MUST,
    SPEC_VERSION,
    ContractViolation,
    Requirement,
    validate,
)
from recovery_reliability_benchmark.metadata import load_conditions
from recovery_reliability_benchmark.run import run
from recovery_reliability_benchmark.spikes import MEASURE_KEYS
from recovery_reliability_benchmark.summary import build_summary
from recovery_reliability_benchmark.synthetic import make_tables
from recovery_reliability_benchmark.writer import read_dataset

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
    for doc_name in ("SPEC.md", "CONTRIBUTING.md", "METHOD.md", "README.md", "GLOSSARY.md"):
        text = (ROOT / doc_name).read_text(encoding="utf-8")
        assert "LICENSE-DOCS" in text, f"{doc_name} is missing LICENSE-DOCS reference"


def test_glossary_structure() -> None:
    glossary_path = ROOT / "GLOSSARY.md"
    assert glossary_path.is_file()
    text = glossary_path.read_text(encoding="utf-8")
    assert "LICENSE-DOCS" in text
    for heading in (
        "## 1. The experiment",
        "## 3. The computation",
        "## 4. Conformance",
        "## 5. The protocol schema",
    ):
        assert heading in text


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
        assert f"version: {pyproject_version}" in cff_text
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


def _section_text(markdown: str, heading: str) -> str:
    after = markdown.split(heading, maxsplit=1)[1]
    return after.split("\n## ", maxsplit=1)[0]


def test_release_docs_sections() -> None:
    changelog_text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.1.0]" in changelog_text

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    ordered_headings = (
        "## Run the example",
        "## Run it on your recordings",
        "## If you only have per-trial numbers",
        "## What the report does not say",
        "## Documentation",
    )
    positions = [readme_text.index(h) for h in ordered_headings]
    assert positions == sorted(positions)
    assert "CITATION.cff" in readme_text


def test_inclusion_gaming_and_submission_docs() -> None:
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "## Inclusion and exclusion" in spec_text
    assert INCLUSION_RULE in spec_text

    method_text = (ROOT / "METHOD.md").read_text(encoding="utf-8")
    assert "## How this benchmark can be gamed" in method_text
    for attack in (
        "Variance inflation",
        "Unit selection (drop low-variance units, keep heterogeneous ones)",
        "Trial exclusion after seeing results",
        "Stable-but-meaningless measures (baseline firing rate)",
        "Submitter-chosen data or splits",
        "Something we have not thought of",
    ):
        assert attack in method_text

    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "## Submitting measures" in contributing_text

    glossary_text = (ROOT / "GLOSSARY.md").read_text(encoding="utf-8")
    assert "Sensitivity axis" in glossary_text


def test_zenodo_doi_recorded() -> None:
    cff_text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "doi: 10.5281/zenodo.24020732" in cff_text

    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "zenodo.org/badge/1444426702.svg" in readme_text
    assert "10.5281/zenodo.24020731" in readme_text


def test_v020_spikes_docs_sections() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    for phrase in (
        "rrb-report",
        "examples/two_conditions",
        "Nothing leaves your machine",
        "adapter_template",
        "SPEC.md",
        "METHOD.md",
        "GLOSSARY.md",
        "frozen/README.md",
        "CONTRIBUTING.md",
    ):
        assert phrase in readme_text

    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")
    assert "## Measures computed by the benchmark" in spec_text
    assert "## What conformance guarantees on the spikes path" in spec_text
    measures_section = _section_text(spec_text, "## Measures computed by the benchmark")
    for key in MEASURE_KEYS:
        assert f"`{key}`" in measures_section

    method_text = (ROOT / "METHOD.md").read_text(encoding="utf-8")
    assert "## Split-half on pooled measures" in method_text

    contributing_text = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "## 1. What to send" in contributing_text
    assert "## Protocol advice" in contributing_text


def test_spikes_path_checks_numbers_match_docs() -> None:
    doc = json.loads((ROOT / "docs" / "spikes_path_checks.json").read_text(encoding="utf-8"))
    spec_section = _section_text(
        (ROOT / "SPEC.md").read_text(encoding="utf-8"),
        "## What conformance guarantees on the spikes path",
    )
    method_section = _section_text(
        (ROOT / "METHOD.md").read_text(encoding="utf-8"),
        "## Split-half on pooled measures",
    )

    s20 = doc["strong_20"]["t_half_excess"]
    w20 = doc["weak_20"]["t_half_excess"]
    sp20 = doc["sparse_20"]["t_half_excess"]
    w40 = doc["weak_40"]["t_half_excess"]
    sp40 = doc["sparse_40"]["t_half_excess"]

    assert (
        f"strong responses reach {s20['split_half_corrected']:.2f} "
        f"with {round(s20['units_scored'])} of 30 units scored"
    ) in spec_section
    assert (
        f"weak responses reach {w20['split_half_corrected']:.2f} with {round(w20['units_scored'])} of 30"
    ) in spec_section
    assert (
        f"sparse firing reaches {sp20['split_half_corrected']:.2f} with {round(sp20['units_scored'])} of 30"
    ) in spec_section
    assert (
        f"at 40 trials the last two reach {w40['split_half_corrected']:.2f} "
        f"and {sp40['split_half_corrected']:.2f}"
    ) in spec_section

    expected_spec_decimals = {
        f"{s20['split_half_corrected']:.2f}",
        f"{w20['split_half_corrected']:.2f}",
        f"{sp20['split_half_corrected']:.2f}",
        f"{w40['split_half_corrected']:.2f}",
        f"{sp40['split_half_corrected']:.2f}",
    }
    assert set(re.findall(r"\b\d+\.\d+\b", spec_section)) == expected_spec_decimals

    max_strong_diff = max(
        abs(entry["split_half_corrected"] - entry["test_retest"])
        for case_key in ("strong_20", "strong_40")
        for entry in doc[case_key].values()
    )
    weak_gap = w20["test_retest"] - w20["split_half_corrected"]
    max_other_diff = max(
        abs(doc[case_key][m]["split_half_corrected"] - doc[case_key][m]["test_retest"])
        for case_key in doc
        for m in ("excess_per_trial", "baseline_hz", "t_return")
    )

    assert f"within {max_strong_diff:.2f} for strong responses on every measure" in method_section
    assert (
        f"reads {weak_gap:.2f} low "
        f"({w20['split_half_corrected']:.2f} against {w20['test_retest']:.2f} at 20 trials)"
    ) in method_section
    assert f"within about {max_other_diff:.2f}" in method_section

    expected_method_decimals = {
        f"{max_strong_diff:.2f}",
        f"{weak_gap:.2f}",
        f"{w20['split_half_corrected']:.2f}",
        f"{w20['test_retest']:.2f}",
        f"{max_other_diff:.2f}",
    }
    assert set(re.findall(r"\b\d+\.\d+\b", method_section)) == expected_method_decimals


def test_readme_example_table_matches_two_conditions() -> None:
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8")
    two_cond_dir = ROOT / "examples" / "two_conditions"
    units, trials, spikes, analysis = read_dataset(two_cond_dir)
    conditions = load_conditions(two_cond_dir / "conditions.json")
    result = run(
        units,
        trials,
        ["t_half_excess", "excess_per_trial", "t_return"],
        conditions=conditions,
        spikes=spikes,
        analysis=analysis,
    )
    summary_md = build_summary(result)
    table_lines = [line for line in summary_md.splitlines() if line.startswith("| ")]
    assert len(table_lines) == 6
    assert "\n".join(table_lines) in readme_text

    recordings_section = _section_text(readme_text, "## Run it on your recordings")
    assert f"{MD6_MUST:.1f} s of recording after each stimulus" in recordings_section
    assert f"{MD7_MUST:.1f} s of quiet before each stimulus" in recordings_section
    assert f"at least {MD6_MUST + MD7_MUST:.1f} s apart" in recordings_section
    assert f"{MD2_SHOULD} trials per condition recommended ({MD2_MUST} minimum" in recordings_section
    assert f"{MD3_SHOULD} units recommended ({MD3_MUST} minimum" in recordings_section
