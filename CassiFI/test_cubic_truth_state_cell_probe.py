from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path

import pytest

import run_cubic_truth_state_cell_probe as probe
import verify_cubic_truth_state_cell_probe as verifier


def test_producer_and_independent_verifier_agree_on_small_fixture() -> None:
    formula = probe.prism_formula(6)
    produced = probe.evaluate_fixture(
        "hexagonal-prism",
        "planar-nullity-two-control",
        formula,
    )
    checked = verifier.verify_fixture(
        produced,
        verifier.fixture_specs()[0],
    )

    assert produced["census"]["basis_subsets_checked"] == 15
    assert produced["census"]["independent_ground_bases"] == 12
    assert produced["census"]["width_two_basis_count"] == 12
    assert produced["exclusive_pairs"] == []
    assert checked["census"] == produced["census"]


def test_identical_primal_support_is_rejected_as_a_truth_port() -> None:
    census = probe.enumerate_internal_width_two_bases(probe.SUPPORT_THREE_SAT)
    pairs = probe.exclusive_port_signatures(probe.SUPPORT_THREE_SAT, census)
    diagnostic = next(
        pair for pair in pairs if pair["ports"] == [7, 9]
    )

    assert diagnostic["signature_counts"] == {"01": 12, "10": 12}
    assert diagnostic["kernel_pair_rank"] == 2
    assert diagnostic["kernel_projectively_parallel"] is False
    assert diagnostic["primal_incidence_identical"] is True
    assert diagnostic["eligible_truth_state_pair"] is False
    assert diagnostic["rejection_reasons"] == ["identical_primal_incidence"]


def test_degree_preserving_switch_keeps_cubic_connected_formula() -> None:
    formula = probe.switch_compose(
        probe.prism_formula(6),
        probe.prism_formula(6),
        (1, 1),
        (1, 1),
    )

    assert len(formula) == 12
    assert probe.production.incidence_connected(formula)
    assert all(len(clause) == 3 for clause in formula)
    assert [
        sum(variable in clause for clause in formula)
        for variable in range(1, len(formula) + 1)
    ] == [3] * len(formula)


def test_independent_verifier_rejects_tampered_fixture_census() -> None:
    produced = probe.evaluate_fixture(
        "hexagonal-prism",
        "planar-nullity-two-control",
        probe.prism_formula(6),
    )
    tampered = copy.deepcopy(produced)
    tampered["census"]["independent_ground_bases"] += 1

    with pytest.raises(verifier.VerificationError, match="basis census mismatch"):
        verifier.verify_fixture(tampered, verifier.fixture_specs()[0])


def test_verifier_cli_honors_positional_receipt_path(tmp_path) -> None:
    receipt = tmp_path / "not-the-canonical-receipt.json"
    receipt.write_text("{}\n", encoding="utf-8")
    assert verifier.__file__ is not None
    verifier_path = Path(verifier.__file__).resolve()

    result = subprocess.run(
        [sys.executable, str(verifier_path), str(receipt)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "schema mismatch" in result.stderr
