from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import verify_cubic_order10_targeted_probe as verifier

ROOT = Path(__file__).resolve().parent
RECEIPT = ROOT / "_diag" / "cubic_order10_targeted_probe.json"


def test_targeted_order_ten_receipt_verifies_and_reports_full_denominators() -> None:
    result = verifier.verify(RECEIPT)
    assert result["status"] == "verified"
    assert result["exactly_profiled_candidate_count"] == 6230
    assert result["pair_profiled_candidate_count"] == 6230
    assert result["target_nullity_at_least_three_candidate_count"] == 12
    assert result["all_connected_exclusive_pair_count"] == 3474
    assert result["target_exclusive_pair_count"] == 36
    assert result["all_connected_nondegenerate_exclusive_pair_count"] == 0
    assert result["all_connected_exclusive_pairs_degenerate"] is True
    assert result["pair_case_count_consistent"] is True


def test_independent_verifier_rejects_summary_tampering(tmp_path: Path) -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(receipt)
    mutated["summary"]["all_connected_exclusive_pair_count"] += 1
    path = tmp_path / "mutated-summary.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")

    with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
        verifier.verify(path)


def test_independent_verifier_rejects_pair_record_tampering(tmp_path: Path) -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    mutated = copy.deepcopy(receipt)
    pair = next(
        candidate["exclusive_pairs"][0]
        for candidate in mutated["candidates"]
        if candidate["exclusive_pairs"]
    )
    pair["category"] = "eligible"
    path = tmp_path / "mutated-pair.json"
    path.write_text(json.dumps(mutated), encoding="utf-8")

    with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
        verifier.verify(path)
def test_independent_verifier_rejects_formula_provenance_binding_and_assessment_tampering(
    tmp_path: Path,
) -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    mutations = []

    formula_mutation = copy.deepcopy(receipt)
    formula_mutation["candidates"][0]["formula"][0][0] += 1
    mutations.append(formula_mutation)

    provenance_mutation = copy.deepcopy(receipt)
    provenance_mutation["candidates"][0]["provenance"][0]["edges"][0][0] += 1
    mutations.append(provenance_mutation)

    stream_mutation = copy.deepcopy(receipt)
    stream_mutation["generation"]["generation_stream_sha256"] = "0" * 64
    mutations.append(stream_mutation)

    source_mutation = copy.deepcopy(receipt)
    source_mutation["sources"]["lift_receipt_file_sha256"] = "0" * 64
    mutations.append(source_mutation)

    assessment_mutation = copy.deepcopy(receipt)
    assessment_mutation["assessment"]["result"] = "tampered"
    mutations.append(assessment_mutation)

    for index, mutation in enumerate(mutations):
        path = tmp_path / f"mutated-{index}.json"
        path.write_text(json.dumps(mutation), encoding="utf-8")
        with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
            verifier.verify(path)
