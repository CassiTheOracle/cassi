from __future__ import annotations

from pathlib import Path

import pytest

from cassi_field_owner import FieldIntelligenceOwner
from run_general_intelligence_program import (
    DOMAINS,
    _actual,
    _case,
    _equal,
    _initialize_owner,
    _inventory_request,
    _knowledge_digest,
    _representation_request,
    _semantic,
    training_event,
)
from verify_general_intelligence_program import expected_for


def rows_for(seed: int, domain: str) -> list[dict]:
    return [
        {
            "payload": training_event(seed, 1, domain, slot)["payload"],
            "source_id": f"test:{domain}:{slot}",
        }
        for slot in range(4)
    ]


@pytest.mark.parametrize("domain", DOMAINS)
def test_evaluation_world_formula_is_independent_of_training_roots(domain: str) -> None:
    training_roots = {
        training_event(101, block, domain, slot)["split_root"]
        for block in range(1, 3)
        for slot in range(4)
    }
    for root in range(2):
        for decision in range(4):
            case = _case(101, domain, root, decision)
            row = {
                "domain": domain,
                "inputs": case["inputs"],
            }
            assert _equal(case["expected"], expected_for(row))
            assert case["root_id"] not in training_roots


def test_training_blocks_have_three_construction_and_one_selection_event() -> None:
    for domain in DOMAINS:
        rows = [training_event(101, 2, domain, slot) for slot in range(4)]
        assert [row["event_role"] for row in rows] == [
            "construction",
            "construction",
            "construction",
            "selection",
        ]
        assert len({row["split_root"] for row in rows}) == 4


def test_one_resident_field_learns_all_four_worlds_and_queries_without_learning(
    tmp_path: Path,
) -> None:
    owner_root = tmp_path / "owner"
    _initialize_owner(owner_root, "focused-program")
    with FieldIntelligenceOwner(owner_root) as owner:
        for domain in ("measurement", "temporal", "software"):
            rows = rows_for(101, domain)
            result, _ = _semantic(
                owner,
                f"focused:learn:{domain}",
                _representation_request(
                    domain,
                    rows[:3],
                    rows[3:],
                    [],
                    f"focused:learn:{domain}:semantic",
                ),
            )
            assert result["status"] == "supported"

        inventory_rows = rows_for(101, "inventory")
        inventory_result, _ = _semantic(
            owner,
            "focused:learn:inventory",
            _inventory_request(
                inventory_rows[:3],
                [],
                "focused:learn:inventory:semantic",
            ),
        )
        assert inventory_result["status"] == "supported"

        before = _knowledge_digest(owner)
        for domain in DOMAINS:
            case = _case(101, domain, 1, 2)
            result, _ = _semantic(
                owner,
                f"focused:query:{domain}",
                case["request"],
            )
            assert result["status"] == "supported"
            assert _equal(case["expected"], _actual(domain, result))
        assert _knowledge_digest(owner) == before

        task = owner.state.computers[0].inspect()["task"]
        target = task["current"]["Program"]["representation:measurement-relative"]
        revoked, _ = _semantic(
            owner,
            "focused:revoke:measurement",
            {
                "operation": "revoke",
                "operation_id": "focused:revoke:measurement:semantic",
                "reason": "focused causal regression",
                "target": target,
            },
        )
        assert revoked["status"] == "supported"
        case = _case(101, "measurement", 0, 0)
        after, _ = _semantic(owner, "focused:query:revoked", case["request"])
        assert after["status"] == "support-gap"
        assert _actual("measurement", after) is None
