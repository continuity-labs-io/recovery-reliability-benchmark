"""Tests for the MD-2/MD-3 threshold simulation script and SPEC.md numbers."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.thresholds import format_interval, main

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
