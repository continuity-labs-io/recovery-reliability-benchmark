"""Tests for the MD-2/MD-3 threshold simulation script and SPEC.md numbers."""

from __future__ import annotations

import json
from pathlib import Path

from recovery_reliability_benchmark.thresholds import format_interval, main

ROOT = Path(__file__).resolve().parent.parent

REQUIRED_CELL_KEYS = {
    "rho1",
    "n_conditions",
    "n_trials",
    "n_units",
    "true_rho",
    "median_rho_hat",
    "p2_5",
    "p97_5",
    "width",
    "p_zero",
    "ci_coverage",
    "conformance",
}


def test_fast_grid_runs(tmp_path: Path) -> None:
    out_stem = tmp_path / "thresholds"
    rc = main(["--fast", "--out", str(out_stem)])
    assert rc == 0

    out_json = tmp_path / "thresholds.json"
    out_md = tmp_path / "thresholds.md"
    assert out_json.is_file()
    assert out_md.is_file()

    md_text = out_md.read_text(encoding="utf-8")
    assert (
        "The simulation assumes Gaussian unit effects and independent trial errors with no "
        "drift and no unit dropout, so intervals on real data are at least this wide."
        in md_text
    )
    assert (
        "For the pooled estimate the interval uses n_eff = units and is conservative; "
        "observed coverage is 0.99 or higher."
        in md_text
    )

    doc = json.loads(out_json.read_text(encoding="utf-8"))
    assert doc["seeds"] == 50
    assert "generated_by" in doc
    cells = doc["cells"]
    assert len(cells) == 36
    for cell in cells:
        assert REQUIRED_CELL_KEYS.issubset(cell.keys())
        assert cell["conformance"] in ("conforming", "fully_conforming")


def test_spec_numbers_match_json() -> None:
    doc = json.loads((ROOT / "docs" / "thresholds.json").read_text(encoding="utf-8"))
    spec_text = (ROOT / "SPEC.md").read_text(encoding="utf-8")

    by_key = {
        (c["rho1"], c["n_conditions"], c["n_trials"], c["n_units"]): c
        for c in doc["cells"]
    }

    four_cells = [
        (0.2, 1, 10, 8),
        (0.2, 1, 20, 15),
        (0.2, 1, 20, 30),
        (0.2, 3, 10, 8),
    ]
    for key in four_cells:
        cell = by_key[key]
        interval_str = format_interval(cell["p2_5"], cell["p97_5"])
        assert interval_str in spec_text

    must_cell = by_key[(0.2, 1, 10, 8)]
    should_cell = by_key[(0.2, 1, 20, 30)]
    must_interval = format_interval(must_cell["p2_5"], must_cell["p97_5"])
    should_interval = format_interval(should_cell["p2_5"], should_cell["p97_5"])
    assert (
        f"narrows from {must_interval} at the MUST thresholds to {should_interval} "
        "at the SHOULD thresholds (single-trial reliability 0.2)"
        in spec_text
    )

    p_zero_02 = f"{must_cell['p_zero']:.0%}"
    p_zero_01 = f"{by_key[(0.1, 1, 10, 8)]['p_zero']:.0%}"
    assert (
        f"and {p_zero_02} of such runs report exactly 0 "
        f"({p_zero_01} when the single-trial reliability is 0.1)"
        in spec_text
    )
