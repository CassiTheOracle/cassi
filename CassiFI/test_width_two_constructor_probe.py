from __future__ import annotations

import json
from pathlib import Path

import pytest

from run_width_two_constructor_probe import run
from verify_width_two_constructor_probe import (
    VerificationError,
    verify,
    verify_candidate_basis,
)


COUNTEREXAMPLE_DIGEST = (
    "c26d0346c837aa4af28c0f4e687eff573ee441abbc3d340a3e7785e714bac37e"
)


def test_greedy_constructor_is_falsified_by_exact_basis_census(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "width-two-constructor.json"
    receipt = run(receipt_path)
    checked = verify(receipt_path)

    counterexample = receipt["counterexamples"][0]
    assert checked["result"] == "PASS"
    assert receipt["hypothesis"]["status"] == "falsified"
    assert receipt["summary"]["corpus_cases"] == 811
    assert receipt["summary"]["basis_subsets_checked"] == 7452
    assert receipt["summary"]["counterexamples"] == 1
    assert counterexample["formula_sha256"] == COUNTEREXAMPLE_DIGEST
    assert counterexample["exact_width"] == 2
    assert counterexample["greedy"]["width"] == 3
    assert counterexample["exact_free_basis"]


def test_candidate_verifier_fails_closed_on_missing_or_invalid_basis() -> None:
    formula = (
        (1, 2, 3),
        (1, 2, 4),
        (1, 3, 4),
        (2, 3, 4),
    )

    missing = verify_candidate_basis(formula, None)
    invalid = verify_candidate_basis(formula, [1])

    assert missing == {
        "valid": False,
        "reason": "no_basis",
        "basis": None,
        "rank": 0,
        "nullity": 0,
        "support_profile": None,
        "maximum_support": None,
    }
    assert invalid["valid"] is False
    assert invalid["reason"] == "basis_rank_or_size"


def test_constructor_verifier_rejects_tampered_operation_audit(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "width-two-constructor.json"
    run(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["cases"][0]["greedy"]["candidate_generation"]["rank_checks"] += 1
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(VerificationError, match="greedy constructor result"):
        verify(receipt_path)


def test_constructor_verifier_rejects_tampered_greedy_width(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "width-two-constructor.json"
    run(receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["cases"][0]["greedy"]["width"] = 99
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(VerificationError, match="greedy constructor result"):
        verify(receipt_path)
