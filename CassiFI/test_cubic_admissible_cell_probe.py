from __future__ import annotations
import copy

import json
import subprocess
import sys
from pathlib import Path

import pytest

import run_cubic_admissible_cell_probe as probe
import verify_cubic_admissible_cell_probe as verifier


def _synthetic_graph(
    vertices: list[list[int]],
    edges: list[list[int]],
    components: list[list[int]],
) -> dict[str, object]:
    adjacency = [[] for _ in vertices]
    for left, right in edges:
        adjacency[left].append(right)
        adjacency[right].append(left)
    return {
        "vertex_namespace": probe.VERTEX_NAMESPACE,
        "vertices": vertices,
        "vertex_count": len(vertices),
        "edge_count": len(edges),
        "edges": edges,
        "adjacency": adjacency,
        "component_count": len(components),
        "components": components,
        "connected": len(components) == 1,
        "isolated_vertices": [
            index for index, row in enumerate(adjacency) if not row
        ],
    }


def test_prism_exchange_graph_and_independent_reconstruction_agree() -> None:
    formula = probe.prism_formula(6)
    runtime_record = probe.evaluate_fixture(
        "hexagonal-prism",
        "planar-nullity-two-control",
        formula,
    )
    assert runtime_record["pair_screen_status"] == "exact"
    assert runtime_record["pair_certificate_status"] == "exact"
    assert runtime_record["census"]["status"] == "exact"
    assert runtime_record["candidate_pairs_attempted"] == runtime_record["candidate_pairs_total"]
    assert runtime_record["candidate_pairs_checked"] == runtime_record["candidate_pairs_total"]
    assert runtime_record["pair_certificate_work_attempted"] == runtime_record["pair_certificate_work_total"]
    assert runtime_record["pair_certificate_work_checked"] == runtime_record["pair_certificate_work_total"]
    producer_census = probe.enumerate_width_two_bases(formula)
    producer_graph = probe.build_basis_exchange_graph(
        producer_census["width_two_bases"], len(formula)
    )
    verifier_census = verifier.basis_census(verifier.prism_formula(6))
    verifier_graph = verifier.exchange_graph(
        verifier_census["width_two_bases"], len(formula)
    )

    assert producer_census == verifier_census
    assert producer_graph == verifier_graph
    assert producer_graph["vertex_count"] == 12
    assert producer_graph["edge_count"] == 36
    assert producer_graph["component_count"] == 1
    assert all(
        len(set(left).symmetric_difference(right)) == 2
        for left, right in producer_graph["edges"]
        for left, right in [(producer_graph["vertices"][left], producer_graph["vertices"][right])]
    )


def test_disconnected_truth_fibres_are_explicitly_rejected() -> None:
    graph = _synthetic_graph(
        [[1, 3], [2, 3], [1, 4], [2, 4]],
        [[0, 1], [2, 3]],
        [[0, 1], [2, 3]],
    )

    certificate = probe.analyze_pair_basis_family(graph, 4, (1, 2))

    assert certificate["exchange"]["full_graph_connected"] is False
    assert certificate["exchange"]["truth_fibres"]["01"]["component_count"] == 2
    assert certificate["exchange"]["truth_fibres"]["10"]["component_count"] == 2
    assert certificate["exchange"]["single_exchange_truth_flip"] is True


def test_alternate_pair_partition_is_recorded_up_to_orientation() -> None:
    graph = _synthetic_graph(
        [[1, 3], [2, 4]],
        [],
        [[0], [1]],
    )

    certificate = probe.analyze_pair_basis_family(graph, 4, (1, 2))

    assert certificate["exclusive_truth_states"] is True
    assert {
        tuple(row["ports"]) for row in certificate["alternate_pair_partitions"]
    } == {(1, 4), (2, 3), (3, 4)}
    matching = next(
        row
        for row in certificate["alternate_pair_partitions"]
        if row["ports"] == [3, 4]
    )
    assert matching["orientation"] == "same"
    assert matching["signature_counts"] == {
        "00": 0,
        "01": 1,
        "10": 1,
        "11": 0,
    }


def test_auxiliary_column_shadow_is_recorded() -> None:
    graph = _synthetic_graph(
        [[1, 3], [2, 4]],
        [],
        [[0], [1]],
    )

    certificate = probe.analyze_pair_basis_family(graph, 4, (1, 2))

    assert certificate["auxiliary_column_shadows"] == [
        {
            "column": 3,
            "matches": "left",
            "port": 1,
            "signature": "10",
        },
        {
            "column": 4,
            "matches": "right",
            "port": 2,
            "signature": "01",
        },
    ]

def test_duplicate_primal_columns_are_not_admissible_cells() -> None:
    formula = probe.SUPPORT_THREE_SAT
    census = probe.enumerate_width_two_bases(formula)
    graph = probe.build_basis_exchange_graph(
        census["width_two_bases"], len(formula)
    )

    certificate = probe.classify_admissible_pair(formula, graph, (7, 9))

    assert certificate["exclusive_truth_states"] is True
    assert certificate["primal_incidence_identical"] is True
    assert certificate["admissible"] is False
    assert "identical_primal_incidence" in certificate["rejection_reasons"]


def test_no_width_two_fixture_is_not_applicable() -> None:
    census = probe.enumerate_width_two_bases(probe.ALL_BASES_TERNARY_SAT)

    assert census["status"] == "not_applicable"
    assert census["reason"] == "no_width_two_bases"
    assert census["exact"] is True
    assert census["width_two_basis_count"] == 0


def test_pair_work_cap_is_inconclusive_not_a_negative() -> None:
    original_cap = probe.MAX_PAIR_CERTIFICATE_WORK
    probe.MAX_PAIR_CERTIFICATE_WORK = 0
    try:
        record = probe.evaluate_fixture(
            "hexagonal-prism",
            "planar-nullity-two-control",
            probe.prism_formula(6),
        )
    finally:
        probe.MAX_PAIR_CERTIFICATE_WORK = original_cap

    assert record["census"]["status"] == "exact"
    assert record["pair_certificate_status"] == "inconclusive"
    assert record["pair_screen_status"] == "inconclusive"
    assert record["candidate_pairs_total"] == 15
    assert record["candidate_pairs_attempted"] == 0
    assert record["candidate_pairs_checked"] == 0
    assert record["pair_certificate_work_total"] == 15 * 12
    assert record["pair_certificate_work_attempted"] == 0
    assert record["pair_certificate_work_checked"] == 0
    assert record["admissible_pairs"] == []

def test_verifier_rejects_exact_negative_after_pair_cap(tmp_path: Path) -> None:
    receipt = tmp_path / "capped-negative.json"
    receipt.write_text(
        json.dumps(
            {
                "schema": verifier.SCHEMA,
                "assessment": {
                    "result": "no_admissible_cell_in_frozen_fixtures"
                },
                "fixtures": [{"pair_certificate_status": "inconclusive"}],
                "compositions": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        verifier.VerificationError,
        match="exact negative claimed after an inconclusive pair certificate",
    ):
        verifier.verify(receipt)





def test_verifier_rejects_mutated_real_certificate_witness() -> None:
    produced = probe.evaluate_fixture(
        "hexagonal-prism",
        "planar-nullity-two-control",
        probe.prism_formula(6),
    )
    expected = verifier.fixture_record(
        "hexagonal-prism",
        "planar-nullity-two-control",
        verifier.prism_formula(6),
    )
    tampered = copy.deepcopy(produced)
    tampered["pair_classifications"][0]["exchange"]["cross_state_edge_count"] += 1

    with pytest.raises(verifier.VerificationError, match="fixture mismatch"):
        verifier.compare(tampered, expected, "fixture")
def test_verifier_rejects_tampered_definition_namespace(tmp_path: Path) -> None:
    receipt = {
        "schema": verifier.SCHEMA,
        "definition": {"port_namespace": "tampered"},
    }
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(receipt), encoding="utf-8")

    with pytest.raises(verifier.VerificationError, match="definition mismatch"):
        verifier.verify(path)


def test_verifier_cli_honors_positional_receipt_path(tmp_path: Path) -> None:
    receipt = tmp_path / "not-the-canonical-receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    verifier_path = verifier.__file__
    assert verifier_path is not None

    result = subprocess.run(
        [sys.executable, str(Path(verifier_path).resolve()), str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "schema mismatch" in result.stderr
