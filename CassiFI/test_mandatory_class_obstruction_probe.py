"""Fast controls for the mandatory-class obstruction probe."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_mandatory_class_obstruction_probe as probe
import verify_mandatory_class_obstruction_probe as verifier


def _case(name: str) -> dict[str, Any]:
    for spec in probe.build_specs():
        if spec[0] != name:
            continue
        _, kind, source, nullity, expected, q, family = spec
        if kind != "rational":
            raise AssertionError("test helper expects a rational case")
        return probe.analyze_classes(
            name,
            source,
            nullity,
            expected,
            kind=kind,
            q=q,
            family=family,
        )
    raise AssertionError(f"missing case {name}")


def test_general_position_has_minimal_mandatory_obstruction() -> None:
    record = _case("rational-general-position-k3")

    assert record["mandatory"] == {
        "classes": [1, 2, 3, 4],
        "count": 4,
        "rank": 3,
        "rejects": True,
        "cardinality_witness": [1, 2, 3, 4],
    }
    local = record["local_obstruction"]
    assert local["status"] == "exact"
    assert local["reason"] == "minimum_uncoverable_subset"
    assert local["basis_index_space"] == "original_columns"
    assert local["target_index_space"] == "projective_classes"
    assert local["obstruction_defined"] is True
    assert local["basis_subsets_total"] == 4
    assert local["basis_subsets_checked"] == 4
    assert local["independent_bases"] == 4
    assert local["minimum_size"] == 4
    assert local["witness_subset"] == [1, 2, 3, 4]
    assert local["subset_sizes_checked"] == [1, 2, 3, 4]
    assert record["production"]["reason"] == "mandatory_class_obstruction"
def test_long_line_prefilter_rejects_negative_family_and_preserves_positive() -> None:
    negative = _case("moment_negative-q3")
    positive = _case("path_positive-q3")

    assert negative["mandatory"]["rejects"] is True
    assert negative["production"]["reason"] == "mandatory_class_obstruction"
    assert negative["production"]["residual_subsets_checked"] == 0
    assert positive["mandatory"]["rejects"] is False
    assert positive["production"]["status"] == "width_two"
    assert positive["local_obstruction"]["status"] == "not_applicable"
    assert positive["local_obstruction"]["minimum_size"] is None


def test_cap_is_inconclusive_not_negative() -> None:
    classes = probe.growing_residual(3, "moment_negative")
    geometry = probe.production._projective_geometry(classes)
    result = probe.exact_local_obstruction(
        geometry,
        5,
        applicable=True,
        basis_cap=0,
    )
    assert result["status"] == "inconclusive"
    assert result["reason"] == "basis_enum_cap"
    assert result["minimum_size"] is None


def test_original_column_census_preserves_projective_duplicates() -> None:
    vectors = (
        (probe.Fraction(1), probe.Fraction(0), probe.Fraction(0)),
        (probe.Fraction(1), probe.Fraction(0), probe.Fraction(0)),
        (probe.Fraction(0), probe.Fraction(1), probe.Fraction(0)),
        (probe.Fraction(0), probe.Fraction(0), probe.Fraction(1)),
        (probe.Fraction(1), probe.Fraction(1), probe.Fraction(1)),
    )
    geometry = probe.production._projective_geometry(vectors)
    result = probe.exact_local_obstruction(
        geometry,
        3,
        applicable=True,
        basis_cap=100,
    )
    assert geometry["class_columns"] == [[1, 2], [3], [4], [5]]
    assert result["basis_subsets_total"] == 10
    assert result["basis_subsets_checked"] == 10
    assert result["independent_bases"] == 7
    assert result["minimum_size"] is not None


def test_independent_verifier_rejects_tampered_mandatory_witness(tmp_path: Path) -> None:
    receipt_path = tmp_path / "mandatory-obstruction.json"
    receipt = probe.build_receipt()
    receipt["cases"][0]["mandatory"]["classes"] = [999]
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(verifier.VerificationError, match="mandatory obstruction"):
        verifier.verify(receipt_path)
