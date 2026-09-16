from __future__ import annotations

import json
from pathlib import Path

import pytest

from run_planar_cubic_obstruction_probe import run
from verify_planar_cubic_obstruction_probe import VerificationError, verify


def test_planar_cubic_screen_round_trips_through_independent_verifier(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "planar-cubic-obstruction.json"
    receipt = run(receipt_path)
    checked = verify(receipt_path)

    assert checked["result"] == "PASS"
    assert checked["verified_cases"] == 4
    assert checked["basis_subsets_checked"] == 4512
    assert receipt["summary"]["width_two_obstructions"] == 0
    assert receipt["summary"]["planar_vertex_3_connected_cases"] == 3


def test_planar_cubic_verifier_rejects_a_tampered_basis_census(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "planar-cubic-obstruction.json"
    run(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["cases"][0]["basis"]["column_bases_found"] += 1
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(VerificationError, match="basis census mismatch"):
        verify(receipt_path)
