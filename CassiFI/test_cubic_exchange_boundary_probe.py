from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import run_cubic_exchange_boundary_probe as producer
import verify_cubic_exchange_boundary_probe as verifier


def _zero_left_port_relation_coefficient(receipt: dict[str, Any]) -> None:
    record = receipt["fixtures"][0]["boundary_records"][0]
    edge = record["boundary_edges"][0]
    edge["kernel_relation"][str(record["ports"][0])] = "0"


def test_canonical_receipt_verifies_with_independent_reconstruction(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "boundary.json"
    receipt_path.write_text(
        json.dumps(producer.build_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    result = verifier.verify(receipt_path)

    assert result == {
        "status": "verified",
        "schema": verifier.SCHEMA,
        "candidate_pairs_checked": 192,
        "not_applicable_candidate_pairs": 171,
        "exclusive_pairs": 5,
        "boundary_edges": 54,
    }


def test_every_boundary_edge_is_the_oriented_port_swap() -> None:
    receipt = producer.build_receipt()
    records = [
        record
        for fixture in receipt["fixtures"]
        for record in fixture["boundary_records"]
    ]

    for record in records:
        ports = tuple(record["ports"])
        for edge in record["boundary_edges"]:
            assert edge["from_state"] == "01"
            assert edge["to_state"] == "10"
            assert edge["removed_column"] == ports[1]
            assert edge["added_column"] == ports[0]
            assert edge["removed_column"] in edge["from_basis"]
            assert edge["removed_column"] not in edge["to_basis"]
            assert edge["added_column"] not in edge["from_basis"]
            assert edge["added_column"] in edge["to_basis"]
            assert edge["symmetric_difference"] == list(ports)
            assert edge["port_relation_coefficients_nonzero"]

    edges = [edge for record in records for edge in record["boundary_edges"]]

    assert len(records) == receipt["summary"]["exclusive_pairs"] == 5
    assert receipt["summary"]["source_fixtures"] == 6
    assert receipt["summary"]["applicable_fixtures"] == 4
    assert receipt["summary"]["not_applicable_fixtures"] == 2
    assert receipt["summary"]["candidate_pairs_total"] == 363
    assert receipt["summary"]["candidate_pairs_attempted"] == 192
    assert receipt["summary"]["candidate_pairs_checked"] == 192
    assert receipt["summary"]["not_applicable_candidate_pairs"] == 171
    assert receipt["summary"]["candidate_pair_scan_complete"] is True
    assert len(edges) == receipt["summary"]["boundary_edges"] == 54
    assert all(record["boundary_port_swap_identity"] for record in records)
    assert all(record["boundary_relation_identity"] for record in records)


def test_independent_expected_receipt_has_no_runner_import_dependency() -> None:
    expected = verifier.expected_receipt()
    produced = producer.build_receipt()

    assert expected == produced
    assert expected["assessment"]["global_admissible_cell_theorem"] == "not established"
    assert expected["summary"]["all_boundary_port_swaps"] is True
    assert expected["summary"]["all_boundary_relations_nonzero"] is True


@pytest.mark.parametrize(
    "mutation",
    [
        lambda receipt: receipt["fixtures"][0]["boundary_records"][0]["boundary_edges"][0].update(
            {"added_column": 999}
        ),
        lambda receipt: receipt["summary"].update({"boundary_edges": 55}),
        _zero_left_port_relation_coefficient,
    ],
)
def test_verifier_rejects_real_witness_or_summary_mutation(
    tmp_path: Path,
    mutation,
) -> None:
    tampered = copy.deepcopy(producer.build_receipt())
    mutation(tampered)
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")

    with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
        verifier.verify(path)


def test_verifier_cli_honors_explicit_receipt_path(tmp_path: Path) -> None:
    receipt = tmp_path / "boundary.json"
    receipt.write_text(
        json.dumps(producer.build_receipt(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verifier_path = verifier.__file__
    assert verifier_path is not None

    result = subprocess.run(
        [sys.executable, str(Path(verifier_path).resolve()), str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert '"status": "verified"' in result.stdout
    assert '"boundary_edges": 54' in result.stdout
