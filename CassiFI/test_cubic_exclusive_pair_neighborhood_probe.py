from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

import run_cubic_exclusive_pair_neighborhood_probe as producer
import verify_cubic_exclusive_pair_neighborhood_probe as verifier

@pytest.fixture(scope="module")
def full_produced_receipt() -> dict[str, Any]:
    return producer.build_receipt()


@pytest.fixture(scope="module")
def full_independently_rebuilt_receipt() -> dict[str, Any]:
    return verifier.expected_receipt()


def _population_counts(
    formula: verifier.Formula,
    specs: list[verifier.Switch],
) -> tuple[int, int, int]:
    base_digest = verifier.formula_digest(formula)
    neighbors: set[str] = set()
    base_equivalent = 0
    for spec in specs:
        switched = verifier.apply_spec(formula, spec)
        digest = verifier.formula_digest(switched)
        if digest == base_digest:
            base_equivalent += 1
        else:
            neighbors.add(digest)
    duplicate_nonbase = len(specs) - base_equivalent - len(neighbors)
    return base_equivalent, duplicate_nonbase, len(neighbors)


def test_frozen_seeds_and_complete_switch_populations_are_pinned() -> None:
    expected = {
        "rank-two-identical-support": (434, 10, 32, 392),
        "distinct-support-parallel": (426, 6, 48, 372),
    }

    for producer_seed, verifier_seed in zip(
        producer.SEED_SPECS,
        verifier.SEED_SPECS,
    ):
        producer_name, producer_formula, producer_ports = producer_seed
        verifier_name, verifier_formula, verifier_ports = verifier_seed
        assert producer_name == verifier_name
        assert producer_ports == verifier_ports
        assert producer.formula_digest(producer_formula) == (
            verifier.formula_digest(verifier_formula)
        )
        producer_specs = producer.switch_source.switch_specs(producer_formula)
        verifier_specs = verifier.switch_specs(verifier_formula)
        assert producer_specs == verifier_specs
        base_count, duplicate_count, neighbor_count = _population_counts(
            verifier_formula,
            verifier_specs,
        )
        assert (
            len(verifier_specs),
            base_count,
            duplicate_count,
            neighbor_count,
        ) == expected[verifier_name]


def test_runner_and_verifier_agree_on_real_seed_baselines() -> None:
    expected_reasons = {
        "rank-two-identical-support": [
            ["identical_primal_incidence"],
        ],
        "distinct-support-parallel": [
            ["projectively_parallel_kernel_columns"],
            ["projectively_parallel_kernel_columns"],
        ],
    }

    for producer_seed, verifier_seed in zip(
        producer.SEED_SPECS,
        verifier.SEED_SPECS,
    ):
        name, producer_formula, producer_ports = producer_seed
        _, verifier_formula, verifier_ports = verifier_seed
        produced = producer._baseline_record(
            producer_formula,
            producer_ports,
        )
        rebuilt = verifier.baseline_record(
            verifier_formula,
            verifier_ports,
        )
        assert produced == rebuilt
        assert [pair["rejection_reasons"] for pair in produced["pairs"]] == (
            expected_reasons[name]
        )
        assert all(pair["exclusive"] for pair in produced["pairs"])
        assert not any(pair["eligible"] for pair in produced["pairs"])


@pytest.mark.parametrize(
    (("seed_index", "spec")),
    [
        (0, (5, 10, 3, 11)),
        (1, (6, 10, 5, 11)),
    ],
)
def test_runner_and_verifier_agree_on_real_switched_neighbors(
    seed_index: int,
    spec: verifier.Switch,
) -> None:
    _, producer_formula, producer_ports = producer.SEED_SPECS[seed_index]
    _, verifier_formula, verifier_ports = verifier.SEED_SPECS[seed_index]
    produced_formula = producer.switch_source.apply_spec(
        producer_formula,
        spec,
    )
    rebuilt_formula = verifier.apply_spec(verifier_formula, spec)
    assert produced_formula == rebuilt_formula

    produced = producer._neighbor_record(
        produced_formula,
        spec,
        1,
        producer_ports,
    )
    rebuilt = verifier.neighbor_record(
        rebuilt_formula,
        spec,
        1,
        verifier_ports,
    )
    assert produced == rebuilt
    assert any(
        pair["status"] == "exact" and pair["exclusive"]
        for pair in produced["pairs"]
    )


def test_real_no_width_two_neighbor_is_explicitly_not_applicable() -> None:
    spec: verifier.Switch = (4, 10, 2, 8)
    _, producer_formula, producer_ports = producer.SEED_SPECS[1]
    _, verifier_formula, verifier_ports = verifier.SEED_SPECS[1]
    produced_formula = producer.switch_source.apply_spec(
        producer_formula,
        spec,
    )
    rebuilt_formula = verifier.apply_spec(verifier_formula, spec)

    produced = producer._neighbor_record(
        produced_formula,
        spec,
        1,
        producer_ports,
    )
    rebuilt = verifier.neighbor_record(
        rebuilt_formula,
        spec,
        1,
        verifier_ports,
    )
    assert produced == rebuilt
    assert produced["census"]["status"] == "not_applicable"
    assert produced["census"]["reason"] == "no_width_two_bases"
    assert [pair["status"] for pair in produced["pairs"]] == [
        "not_applicable",
        "not_applicable",
    ]


def test_verifier_rejects_mutated_real_pair_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, formula, ports = verifier.SEED_SPECS[0]
    expected = {
        "schema": verifier.SCHEMA,
        "baseline": verifier.baseline_record(formula, ports),
    }
    tampered = copy.deepcopy(expected)
    tampered["baseline"]["pairs"][0]["eligible"] = True
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(tampered), encoding="utf-8")
    monkeypatch.setattr(verifier, "expected_receipt", lambda: expected)

    with pytest.raises(verifier.VerificationError, match="receipt mismatch"):
        verifier.verify(path)


def test_full_independent_reconstruction_matches_every_neighbor(
    full_produced_receipt: dict[str, Any],
    full_independently_rebuilt_receipt: dict[str, Any],
) -> None:
    assert full_produced_receipt == full_independently_rebuilt_receipt


def test_full_summary_and_accounting(
    full_produced_receipt: dict[str, Any],
) -> None:
    summary = full_produced_receipt["summary"]
    assert summary == {
        "switch_specs": 860,
        "base_equivalent_specs": 16,
        "duplicate_nonbase_specs": 80,
        "distinct_neighbors": 764,
        "connected_neighbors": 764,
        "disconnected_neighbors": 0,
        "exact_censuses": 764,
        "inconclusive_censuses": 0,
        "width_two_neighbors": 754,
        "no_width_two_neighbors": 10,
        "designated_pair_cases": 1136,
        "pair_cases_checked": 1116,
        "pair_cases_not_applicable": 20,
        "pair_cases_inconclusive": 0,
        "exclusive_pairs": 236,
        "eligible_pairs": 0,
        "admissible_pairs": 0,
        "seed_formulas": 2,
        "designated_pairs": 3,
        "switch_accounting_complete": True,
        "pair_accounting_complete": True,
    }
    assert 860 == 16 + 80 + 764
    assert 1136 == 1116 + 20
    assert full_produced_receipt["assessment"]["result"] == (
        "finite_distance_one_search_null"
    )
    assert full_produced_receipt["assessment"][
        "exclusive_pair_degeneracy_conjecture"
    ] == "not established"


def test_every_exclusive_neighbor_retains_its_seed_degeneracy(
    full_produced_receipt: dict[str, Any],
) -> None:
    seeds = {
        seed["name"]: seed for seed in full_produced_receipt["seeds"]
    }
    identical = seeds["rank-two-identical-support"]
    parallel = seeds["distinct-support-parallel"]
    assert identical["counts"]["exclusive_pairs"] == 128
    assert identical["exclusive_rejection_combinations"] == {
        "identical_primal_incidence": 128
    }
    assert parallel["counts"]["exclusive_pairs"] == 108
    assert parallel["exclusive_rejection_combinations"] == {
        "projectively_parallel_kernel_columns": 108
    }

    for seed in full_produced_receipt["seeds"]:
        for neighbor in seed["neighbors"]:
            for pair in neighbor["pairs"]:
                if pair["status"] != "exact" or not pair["exclusive"]:
                    continue
                assert pair["eligible"] is False
                assert pair["admissible"] is False
                if seed["name"] == "rank-two-identical-support":
                    assert pair["kernel_pair_rank"] == 2
                    assert pair["kernel_projectively_parallel"] is False
                    assert pair["primal_incidence_identical"] is True
                else:
                    assert pair["kernel_projectively_parallel"] is True
                    assert pair["primal_incidence_identical"] is False


def test_every_neighbor_replays_from_its_representative_switch(
    full_produced_receipt: dict[str, Any],
) -> None:
    verifier_seeds = {
        name: formula for name, formula, _ in verifier.SEED_SPECS
    }
    for seed in full_produced_receipt["seeds"]:
        formula = verifier_seeds[seed["name"]]
        for neighbor in seed["neighbors"]:
            switched = verifier.apply_spec(
                formula,
                tuple(neighbor["representative_switch"]),
            )
            assert verifier.formula_digest(switched) == (
                neighbor["formula_sha256"]
            )
            assert neighbor["switch_multiplicity"] >= 1


def test_verifier_cli_honors_explicit_full_receipt_path(
    tmp_path: Path,
    full_produced_receipt: dict[str, Any],
) -> None:
    receipt_path = tmp_path / "neighborhood.json"
    receipt_path.write_text(
        json.dumps(full_produced_receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    verifier_path = verifier.__file__
    assert verifier_path is not None

    result = subprocess.run(
        [sys.executable, str(Path(verifier_path).resolve()), str(receipt_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert '"status": "verified"' in result.stdout
    assert '"distinct_neighbors": 764' in result.stdout
    assert '"eligible_pairs": 0' in result.stdout
