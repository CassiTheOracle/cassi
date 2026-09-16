"""Focused transition regressions for packet-aware reasoning episodes.

Each test drives one transition contract of the work loop: dispatch and
return consumption, root budgeting, certified readouts, dependency-local
correction, and reuse of completed subproblems.
"""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from cassi_field_atlas import FieldIntelligenceError
from cassi_field_cognition import (
    PACKET_BOUND_SCHEMA,
    PACKET_READOUT_SCHEMA,
    semantic_cognition_kernel,
    semantic_cognition_state,
)
from cassi_field_program import semantic_program_payload

HASH = "a" * 64
ALLOCATION = {
    "branch_count": 64,
    "evidence_reads": 1_000_000,
    "frontier_size": 64,
    "model_calls": 64,
    "refinement_depth": 8,
    "storage_words": 4_000_000,
    "work": 4_096,
}


def step(state: Mapping[str, Any], **request: Any):
    transition = semantic_cognition_kernel(state, request, 4096)
    assert transition.status == "done", transition.status
    return transition.state, transition.output


def surfaced(state: Mapping[str, Any]):
    state, _ = step(
        state,
        operation="observe",
        operation_id="observe-premise",
        delivery_id="delivery:premise",
        event_id="event:premise",
        observations=[
            {
                "binding_id": "binding:premise",
                "subject": "world",
                "attribute": "rate",
                "value": 2.0,
            }
        ],
    )
    return state


def premise_ref(version: int = 1) -> dict[str, Any]:
    return {
        "content_version": version,
        "id": "binding:premise",
        "kind": "Binding",
    }


def adapter_item(
    item_id: str = "item-a",
    *,
    reservation: Mapping[str, int] | None = None,
    request_value: float = 7.0,
) -> dict[str, Any]:
    invocation: dict[str, Any] = {
        "adapter": "model.echo",
        "arguments": {},
        "request": {"value": request_value},
    }
    if reservation is not None:
        invocation["reservation"] = dict(reservation)
    return {
        "dependencies": [],
        "item_id": item_id,
        "kind": "model-native",
        "priority": 1,
        "invocation": invocation,
    }


def readout_item(
    item_id: str,
    coefficients: list[float],
    weights: list[float],
    inspected: list[int],
    *,
    threshold: float | None,
    tolerance: float | None,
    norm_upper: float,
    comparison: str | None = None,
) -> dict[str, Any]:
    return {
        "dependencies": [],
        "item_id": item_id,
        "kind": "readout",
        "priority": 1,
        "readout": {
            "bias": 0.0,
            "bound_provider": {
                "arithmetic_epsilon": 1e-12,
                "codec_sha256": HASH,
                "construction_work": 2,
                "omitted_indices": sorted(
                    set(range(len(coefficients))) - set(inspected)
                ),
                "readout_sha256": HASH,
                "schema": PACKET_BOUND_SCHEMA,
                "source_state_sha256": HASH,
                "x_norm_upper": norm_upper,
            },
            "codec_sha256": HASH,
            "comparison": comparison,
            "inspected_indices": list(inspected),
            "output_units": "count",
            "readout_sha256": HASH,
            "scaled_coefficients": list(coefficients),
            "scaled_weights": list(weights),
            "schema": PACKET_READOUT_SCHEMA,
            "source_state_sha256": HASH,
            "threshold": threshold,
            "tolerance": tolerance,
        },
    }


def begin(
    state,
    episode_id: str,
    items,
    *,
    allocation=None,
    dependencies=(),
    selection=None,
):
    program: dict[str, Any] = {"work_items": list(items)}
    if selection is not None:
        program["selection"] = dict(selection)
    return step(
        state,
        operation="begin-reasoning",
        operation_id=f"begin-{episode_id}",
        episode_id=episode_id,
        question=f"question for {episode_id}",
        allocation=dict(ALLOCATION if allocation is None else allocation),
        dependencies=list(dependencies),
        program=program,
    )


def episode_record(state: Mapping[str, Any], episode_id: str) -> dict[str, Any]:
    return state["records"][f"obligation:reasoning:{episode_id}"][-1]


def test_adapter_dispatch_consumes_one_bounded_return() -> None:
    state = surfaced(semantic_cognition_state())
    state, began = begin(state, "episode-a", [adapter_item()])
    assert began["status"] == "waiting"
    invitation = began["invocation"]
    assert invitation["adapter"] == "model.echo"
    assert invitation["call_id"] == "reasoning:episode-a:item-a:1"

    with pytest.raises(FieldIntelligenceError, match="return identity"):
        step(
            state,
            operation="advance-reasoning",
            operation_id="advance-corrupt",
            episode_id="episode-a",
            expected_return={
                "call_id": invitation["call_id"],
                "request_sha256": "b" * 64,
                "status": "halted",
            },
        )

    state, consumed = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-consume",
        episode_id="episode-a",
        expected_return={
            "call_id": invitation["call_id"],
            "request_sha256": invitation["request_sha256"],
            "result": {"accepted": True, "value": 7.0},
            "status": "halted",
        },
    )
    assert consumed["status"] == "supported"
    assert consumed["phase"] == "terminal"
    assert [
        row["call_id"] for row in consumed["consumed_returns"]
    ] == [invitation["call_id"]]
    recorded = episode_record(state, "episode-a")
    assert recorded["payload"]["resources"]["charged"]["work"] > 0
    assert recorded["payload"]["resources"]["charged"]["storage_words"] > 0

    state, finished = step(
        state,
        operation="finish-reasoning",
        operation_id="finish-episode-a",
        episode_id="episode-a",
    )
    assert finished["status"] == "supported"
    assert finished["result"]["accepted"] is True
    assert finished["result"]["value"] == 7.0


def test_enforced_allocation_refuses_a_reservation_that_does_not_fit() -> None:
    state = surfaced(semantic_cognition_state())
    oversized = {
        "branch_count": 0,
        "evidence_reads": 16,
        "frontier_size": 2,
        "model_calls": 0,
        "refinement_depth": 0,
        "storage_words": 64,
        "work": 32,
    }
    state, began = begin(
        state,
        "episode-budget",
        [adapter_item(reservation=oversized)],
        allocation={
            "branch_count": 0,
            "evidence_reads": 4,
            "frontier_size": 1,
            "model_calls": 0,
            "refinement_depth": 0,
            "storage_words": 16,
            "work": 8,
        },
    )
    assert began["invocation"] is None
    assert began["phase"] == "terminal"
    assert began["limitation"] == {
        "kind": "resource-exhausted",
        "remaining_items": ["item-a"],
    }
    assert [
        (row["item_id"], row["status"]) for row in began["work_items"]
    ] == [("item-a", "limited")]

    state, finished = step(
        state,
        operation="finish-reasoning",
        operation_id="finish-episode-budget",
        episode_id="episode-budget",
    )
    assert finished["status"] == "resource-exhausted"
    assert finished["result"]["status"] == "resource-exhausted"


def test_readout_decides_within_its_bound_and_refuses_an_uncertified_norm() -> None:
    state = surfaced(semantic_cognition_state())
    decisive = readout_item(
        "item-decisive",
        [10.0, 0.0],
        [1.0, 1.0],
        [0],
        threshold=5.0,
        tolerance=None,
        norm_upper=0.0,
        comparison="gt",
    )
    state, _began = begin(state, "episode-decisive", [decisive])
    state, advanced = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-decisive",
        episode_id="episode-decisive",
    )
    assert advanced["status"] == "supported"
    result = episode_record(state, "episode-decisive")["payload"]["results"][
        "item-decisive"
    ]
    assert result["status"] == "exact"
    assert result["decision"] is True
    assert result["interval"]["lower"] > 5.0

    unresolved = readout_item(
        "item-unresolved",
        [1.0, 3.0],
        [1.0, 1.0],
        [0],
        threshold=2.0,
        tolerance=None,
        norm_upper=3.0,
        comparison="gt",
    )
    other = surfaced(semantic_cognition_state())
    other, _began = begin(other, "episode-unresolved", [unresolved])
    other, advanced = step(
        other,
        operation="advance-reasoning",
        operation_id="advance-unresolved",
        episode_id="episode-unresolved",
    )
    assert advanced["status"] == "non-identifiable"
    pending = episode_record(other, "episode-unresolved")["payload"]["results"][
        "item-unresolved"
    ]
    assert pending["status"] == "unresolved"
    assert pending["decision"] is None
    assert pending["reason"] == "refinement-required"

    corrupted = readout_item(
        "item-corrupted",
        [1.0, 30.0],
        [1.0, 1.0],
        [0],
        threshold=2.0,
        tolerance=None,
        norm_upper=3.0,
        comparison="gt",
    )
    third = surfaced(semantic_cognition_state())
    with pytest.raises(
        FieldIntelligenceError, match="certified enclosure"
    ):
        begin(third, "episode-corrupted", [corrupted])


def test_correction_blocks_stale_reads_and_resumes_after_bounded_repair() -> None:
    narrow = dict(ALLOCATION)
    narrow.update(
        {"frontier_size": 4, "model_calls": 4, "work": 4, "storage_words": 64}
    )
    state = surfaced(semantic_cognition_state(bounds={"max_work": 4}))
    state, _began = begin(
        state,
        "episode-correction",
        [adapter_item()],
        allocation=narrow,
        dependencies=[premise_ref()],
    )
    state, corrected = step(
        state,
        operation="correct",
        operation_id="correct-premise",
        correction_id="premise-rate",
        target=premise_ref(),
        replacement={"value": 5.0},
    )
    assert corrected["status"] == "supported"
    assert state["invalidation"]["active"] is True
    assert [
        row["id"] for row in state["invalidation"]["frontier"]
    ] == ["obligation:reasoning:episode-correction"]

    with pytest.raises(
        FieldIntelligenceError, match="unfinished invalidation barrier"
    ):
        step(
            state,
            operation="advance-reasoning",
            operation_id="advance-blocked",
            episode_id="episode-correction",
        )

    quanta = 0
    while state["invalidation"]["active"]:
        state, progress = step(
            state,
            operation="advance-invalidation",
            operation_id=f"advance-invalidation-{quanta}",
            quanta=1,
        )
        quanta += 1
        assert quanta <= 64
    assert progress["status"] == "supported"
    assert progress["pending_records"] == 0

    state, resumed = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-resumed",
        episode_id="episode-correction",
    )
    assert resumed["status"] == "waiting"
    assert resumed["phase"] == "reserved"
    assert resumed["invocation"]["call_id"].endswith(":item-a:2")
    recorded = episode_record(state, "episode-correction")
    assert recorded["payload"]["dependencies"] == [
        {"content_version": 2, "id": "binding:premise", "kind": "Binding"}
    ]
    assert recorded["payload"]["repairs"] == [
        {
            "current": recorded["payload"]["dependencies"][0],
            "prior": premise_ref(),
            "slot": "dependencies",
        }
    ]
    assert recorded["payload"]["releases"] == [
        {
            "call_id": "reasoning:episode-correction:item-a:1",
            "item_id": "item-a",
            "reason": "dependency-repaired",
        }
    ]
    assert recorded["payload"]["resources"]["reserved"]["work"] <= 4


def test_repeated_subproblem_reuses_completed_work_without_redispatch() -> None:
    state = surfaced(semantic_cognition_state())
    state, began = begin(
        state,
        "episode-reuse",
        [adapter_item("item-a"), adapter_item("item-b")],
    )
    invitation = began["invocation"]
    assert invitation["call_id"] == "reasoning:episode-reuse:item-a:1"
    state, _consumed = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-reuse-consume",
        episode_id="episode-reuse",
        expected_return={
            "call_id": invitation["call_id"],
            "request_sha256": invitation["request_sha256"],
            "result": {"accepted": True, "value": 7.0},
            "status": "halted",
        },
    )
    state, added = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-reuse-second",
        episode_id="episode-reuse",
    )
    assert added["phase"] == "terminal"
    assert added["invocation"] is None
    recorded = episode_record(state, "episode-reuse")["payload"]
    assert [
        (row["item_id"], row["status"]) for row in recorded["work_items"]
    ] == [("item-a", "completed"), ("item-b", "reused")]
    assert recorded["shared_work"] == [
        {
            "consumer": "item-b",
            "producer": "item-a",
            "reuse_key": recorded["work_items"][1]["reuse_key"],
        }
    ]
    assert recorded["resources"]["charged"]["storage_words"] == recorded[
        "results"
    ]["item-a"]["resources"]["storage_words"]
    state, finished = step(
        state,
        operation="finish-reasoning",
        operation_id="finish-episode-reuse",
        episode_id="episode-reuse",
    )
    assert finished["status"] == "supported"
    assert [row["item_id"] for row in finished["result"]["work_items"]] == [
        "item-a",
        "item-b",
    ]


def test_readout_reuse_shares_one_certified_result_between_items() -> None:
    state = surfaced(semantic_cognition_state())
    first = readout_item(
        "item-first",
        [10.0, 0.0],
        [1.0, 1.0],
        [0],
        threshold=5.0,
        tolerance=None,
        norm_upper=0.0,
        comparison="gt",
    )
    second = readout_item(
        "item-second",
        [10.0, 0.0],
        [1.0, 1.0],
        [0],
        threshold=5.0,
        tolerance=None,
        norm_upper=0.0,
        comparison="gt",
    )
    state, began = begin(state, "episode-shared", [first, second])
    assert began["invocation"] is None
    for index in range(4):
        state, advanced = step(
            state,
            operation="advance-reasoning",
            operation_id=f"advance-shared-{index}",
            episode_id="episode-shared",
        )
        if advanced["phase"] == "terminal":
            break
    assert advanced["phase"] == "terminal"
    assert advanced["status"] == "supported"
    recorded = episode_record(state, "episode-shared")["payload"]
    assert recorded["shared_work"] == [
        {
            "consumer": "item-second",
            "producer": "item-first",
            "reuse_key": recorded["work_items"][0]["reuse_key"],
        }
    ]
    assert [
        (row["item_id"], row["status"]) for row in recorded["work_items"]
    ] == [("item-first", "completed"), ("item-second", "reused")]
    assert recorded["resources"]["charged"]["evidence_reads"] == 2
    state, finished = step(
        state,
        operation="finish-reasoning",
        operation_id="finish-episode-shared",
        episode_id="episode-shared",
    )
    assert finished["status"] == "supported"

def test_branch_item_keeps_incompatible_hypotheses_distinct() -> None:
    state = surfaced(semantic_cognition_state())
    state, _began = begin(
        state,
        "episode-branch",
        [
            {
                "branch": {
                    "hypotheses": [
                        {
                            "assumptions": {"support": "left"},
                            "conclusion": "left carries the load",
                            "hypothesis_id": "left-load",
                        },
                        {
                            "assumptions": {"support": "right"},
                            "conclusion": "right carries the load",
                            "hypothesis_id": "right-load",
                        },
                    ],
                    "parent_rule": "conditional",
                },
                "dependencies": [],
                "item_id": "item-branch",
                "kind": "branch",
                "priority": 1,
            }
        ],
    )
    state, advanced = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-branch",
        episode_id="episode-branch",
    )
    assert advanced["status"] == "alternatives"
    result = episode_record(state, "episode-branch")["payload"]["results"][
        "item-branch"
    ]
    assert result["status"] == "alternatives"
    assert [row["hypothesis_id"] for row in result["alternatives"]] == [
        "left-load",
        "right-load",
    ]
    alternatives = {
        row["id"]: row
        for history in state["records"].values()
        for row in history
        if row["kind"] == "Value"
        and row["payload"].get("purpose") == "reasoning-alternative"
    }
    assert sorted(
        row["payload"]["hypothesis_id"] for row in alternatives.values()
    ) == ["left-load", "right-load"]
    assert len(
        {row["payload"]["conclusion"] for row in alternatives.values()}
    ) == 2
    assert {
        row["epistemic_kind"] for row in alternatives.values()
    } == {"hypothetical"}
    assert all(
        row["status"] == "active" for row in alternatives.values()
    )
    state, finished = step(
        state,
        operation="finish-reasoning",
        operation_id="finish-episode-branch",
        episode_id="episode-branch",
    )
    assert finished["status"] == "alternatives"

def selector_program(terms: Mapping[str, float]) -> dict[str, Any]:
    return semantic_program_payload(
        program_kind="affine",
        body={
            "outputs": {
                "priority": {
                    "action_terms": {},
                    "bias": 0.0,
                    "error": 0.0,
                    "terms": dict(terms),
                }
            }
        },
        max_work=8,
    )


def test_acquired_selector_program_orders_the_frontier() -> None:
    state = surfaced(semantic_cognition_state())
    state, registered = step(
        state,
        operation="register",
        operation_id="register-selector",
        record_id="program:reasoning-selector",
        kind="Program",
        payload={
            "program": selector_program(
                {"base_priority": 1.0, "support_count": 1_000.0}
            ),
            "program_role": "reasoning",
        },
    )
    selector = registered["record"]
    lead = dict(adapter_item("item-lead"))
    lead.update({"priority": 5, "support_paths": ["L"]})
    wide = dict(adapter_item("item-wide"))
    wide.update({"priority": 1, "support_paths": ["L", "R"]})
    state, began = begin(
        state,
        "episode-acquired",
        [lead, wide],
        selection={"method": "acquired", "selector": selector},
    )
    recorded = episode_record(state, "episode-acquired")
    scheduler = recorded["payload"]["scheduler"]
    assert scheduler["method"] == "acquired"
    first = scheduler["snapshots"][0]
    assert first["selected"] == "item-wide"
    assert {
        row["item_id"]: row["score"] for row in first["eligible"]
    } == {"item-lead": 1010, "item-wide": 2002}
    details = first["selected_score_details"]
    assert details["base_priority"] == 1
    assert details["cue"]["kind"] == "acquired-selector"
    assert details["cue"]["program"]["id"] == "program:reasoning-selector"
    assert details["cue"]["value"] == 2001
    assert began["invocation"]["call_id"] == (
        "reasoning:episode-acquired:item-wide:1"
    )
    state, advanced = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-episode-acquired",
        episode_id="episode-acquired",
        expected_return={
            "call_id": began["invocation"]["call_id"],
            "request_sha256": began["invocation"]["request_sha256"],
            "result": {"accepted": True, "value": 1.0},
            "status": "halted",
        },
    )
    second = episode_record(state, "episode-acquired")["payload"][
        "scheduler"
    ]["snapshots"][1]
    assert second["selected"] == "item-lead"
    assert second["selected_score_details"]["cue"] == {
        "kind": "acquired-selector",
        "program": {
            "content_version": 1,
            "id": "program:reasoning-selector",
            "kind": "Program",
        },
        "value": 1005,
    }
    assert [
        row["item_id"]
        for row in episode_record(state, "episode-acquired")["payload"][
            "work_items"
        ]
    ] == ["item-lead", "item-wide"]
    state, fractional = step(
        state,
        operation="register",
        operation_id="register-fractional-selector",
        record_id="program:fractional-selector",
        kind="Program",
        payload={
            "program": selector_program({"base_priority": 0.5}),
            "program_role": "reasoning",
        },
    )
    state, structural = step(
        state,
        operation="register",
        operation_id="register-structural-selector",
        record_id="program:structural-selector",
        kind="Program",
        payload={
            "program": selector_program(
                {"activation": 1.0, "has_support": 1_000.0}
            ),
            "program_role": "reasoning",
        },
    )
    state, structural_began = begin(
        state,
        "episode-structural",
        [dict(wide)],
        selection={"method": "acquired", "selector": structural["record"]},
    )
    structural_first = episode_record(state, "episode-structural")["payload"][
        "scheduler"
    ]["snapshots"][0]
    assert structural_first["selected_score_details"]["cue"] == {
        "kind": "acquired-selector",
        "program": {
            "content_version": 1,
            "id": "program:structural-selector",
            "kind": "Program",
        },
        "value": 1000,
    }
    assert structural_began["invocation"]["call_id"] == (
        "reasoning:episode-structural:item-wide:1"
    )
    with pytest.raises(
        FieldIntelligenceError, match="acquired scheduling priority"
    ):
        begin(
            state,
            "episode-fractional",
            [adapter_item("item-fractional")],
            selection={
                "method": "acquired",
                "selector": fractional["record"],
            },
        )


def test_acquired_selector_program_refuses_an_unresolvable_score() -> None:
    state = surfaced(semantic_cognition_state())
    state, registered = step(
        state,
        operation="register",
        operation_id="register-unresolvable-selector",
        record_id="program:unresolvable-selector",
        kind="Program",
        payload={
            "program": selector_program({"unavailable_feature": 1.0}),
            "program_role": "reasoning",
        },
    )
    with pytest.raises(
        FieldIntelligenceError,
        match="acquired scheduler did not return supported values",
    ):
        begin(
            state,
            "episode-unresolvable",
            [adapter_item("item-a")],
            selection={
                "method": "acquired",
                "selector": registered["record"],
            },
        )

def test_undeclared_reservation_holds_only_the_remaining_allowance() -> None:
    state = surfaced(semantic_cognition_state())
    first = adapter_item("item-first")
    second = adapter_item("item-second", request_value=8.0)
    state, began = begin(
        state,
        "episode-remaining",
        [first, second],
        allocation={
            "branch_count": 0,
            "evidence_reads": 0,
            "frontier_size": 2,
            "model_calls": 2,
            "refinement_depth": 0,
            "storage_words": 512,
            "work": 8,
        },
    )
    assert began["invocation"]["call_id"] == "reasoning:episode-remaining:item-first:1"
    reserved = episode_record(state, "episode-remaining")["payload"]["resources"]
    assert reserved["reserved"] == {
        "branch_count": 0,
        "evidence_reads": 0,
        "frontier_size": 2,
        "model_calls": 2,
        "refinement_depth": 0,
        "storage_words": 512,
        "work": 8,
    }
    state, advanced = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-episode-remaining-first",
        episode_id="episode-remaining",
        expected_return={
            "call_id": began["invocation"]["call_id"],
            "request_sha256": began["invocation"]["request_sha256"],
            "result": {"accepted": True, "value": 3.0},
            "status": "halted",
        },
    )
    assert advanced["status"] == "waiting"
    assert advanced["invocation"]["call_id"] == (
        "reasoning:episode-remaining:item-second:2"
    )
    state, finished = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-episode-remaining-second",
        episode_id="episode-remaining",
        expected_return={
            "call_id": advanced["invocation"]["call_id"],
            "request_sha256": advanced["invocation"]["request_sha256"],
            "result": {"accepted": True, "value": 4.0},
            "status": "halted",
        },
    )
    assert finished["status"] == "supported"
    resources = episode_record(state, "episode-remaining")["payload"]["resources"]
    assert resources["reserved"] == {
        "branch_count": 0,
        "evidence_reads": 0,
        "frontier_size": 0,
        "model_calls": 0,
        "refinement_depth": 0,
        "storage_words": 0,
        "work": 0,
    }
    assert all(
        int(resources["charged"][name]) <= int(resources["limits"][name])
        for name in resources["limits"]
    )


SOURCE_REVISION = "c" * 64


def bound_readout_item(
    item_id: str,
    *,
    dependencies: list[str],
    binding: Mapping[str, Any],
) -> dict[str, Any]:
    item = readout_item(
        item_id,
        [3.0],
        [1.0],
        [0],
        threshold=2.0,
        tolerance=None,
        norm_upper=10.0,
        comparison="gt",
    )
    item["dependencies"] = list(dependencies)
    item["source_binding"] = dict(binding)
    return item


def admitted_source_input(span: list[int] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "input_id": "input:source",
        "payload": {"excerpt": "the declared premise"},
        "source_revision_id": SOURCE_REVISION,
    }
    if span is not None:
        row["span"] = list(span)
    return row


def test_work_item_source_binding_records_the_span_it_reads() -> None:
    """A dispatched item carries the source span it cites, once admitted."""

    state = surfaced(semantic_cognition_state())
    binding = {"source_revision_id": SOURCE_REVISION, "span": [0, 40]}
    state, began = begin(
        state,
        "episode-bound",
        [
            adapter_item("item-a"),
            bound_readout_item("item-b", dependencies=["item-a"], binding=binding),
        ],
    )
    invitation = began["invocation"]
    state, admitted = step(
        state,
        operation="admit-reasoning-input",
        operation_id="admit-bound-input",
        episode_id="episode-bound",
        inputs=[admitted_source_input([0, 64])],
    )
    assert admitted["admitted"][0]["source_binding"] == {
        "source_revision_id": SOURCE_REVISION,
        "span": [0, 64],
    }

    state, _advanced = step(
        state,
        operation="advance-reasoning",
        operation_id="advance-bound",
        episode_id="episode-bound",
        expected_return={
            "call_id": invitation["call_id"],
            "request_sha256": invitation["request_sha256"],
            "result": {"accepted": True, "value": 7.0},
            "status": "halted",
        },
    )
    rows = episode_record(state, "episode-bound")["payload"]["scheduler"]["snapshots"]
    dispatched = [row for row in rows if row["selected"] == "item-b"]
    assert dispatched, [row["selected"] for row in rows]
    assert dispatched[-1]["selected_source_binding"] == binding
    assert dispatched[-1]["selected_support"] == {"resolved": [], "unresolved": []}


def test_work_item_source_binding_refuses_an_unadmitted_source() -> None:
    state = surfaced(semantic_cognition_state())
    with pytest.raises(FieldIntelligenceError, match="did not admit"):
        begin(
            state,
            "episode-unadmitted",
            [
                bound_readout_item(
                    "item-a",
                    dependencies=[],
                    binding={"source_revision_id": SOURCE_REVISION, "span": [0, 40]},
                )
            ],
        )


def test_work_item_source_binding_refuses_a_span_outside_its_admission() -> None:
    state = surfaced(semantic_cognition_state())
    state, began = begin(
        state,
        "episode-outside",
        [
            adapter_item("item-a"),
            bound_readout_item(
                "item-b",
                dependencies=["item-a"],
                binding={"source_revision_id": SOURCE_REVISION, "span": [0, 40]},
            ),
        ],
    )
    invitation = began["invocation"]
    state, _admitted = step(
        state,
        operation="admit-reasoning-input",
        operation_id="admit-narrow-input",
        episode_id="episode-outside",
        inputs=[admitted_source_input([0, 10])],
    )
    with pytest.raises(FieldIntelligenceError, match="cites a span the episode did not admit"):
        step(
            state,
            operation="advance-reasoning",
            operation_id="advance-outside",
            episode_id="episode-outside",
            expected_return={
                "call_id": invitation["call_id"],
                "request_sha256": invitation["request_sha256"],
                "result": {"accepted": True, "value": 7.0},
                "status": "halted",
            },
        )


@pytest.mark.parametrize(
    "binding, message",
    [
        ({"source_revision_id": "short", "span": [0, 4]}, "identity"),
        ({"source_revision_id": "c" * 64, "span": [4, 2]}, "span"),
        ({"source_revision_id": "c" * 64, "span": "0..4"}, "span"),
        ({"source_revision_id": "c" * 64, "extra": 1}, "invalid"),
    ],
)
def test_work_item_source_binding_rejects_malformed_declarations(
    binding: Mapping[str, Any], message: str
) -> None:
    state = surfaced(semantic_cognition_state())
    with pytest.raises(FieldIntelligenceError, match=f"source binding.*{message}"):
        begin(
            state,
            "episode-malformed",
            [bound_readout_item("item-a", dependencies=[], binding=binding)],
        )


def test_spanless_admission_does_not_authorize_a_span() -> None:
    """An admitted revision without a span authorizes identity use only."""

    state = surfaced(semantic_cognition_state())
    state, began = begin(
        state,
        "episode-spanless",
        [
            adapter_item("item-a"),
            bound_readout_item(
                "item-b",
                dependencies=["item-a"],
                binding={"source_revision_id": SOURCE_REVISION, "span": [0, 10]},
            ),
        ],
    )
    invitation = began["invocation"]
    state, admitted = step(
        state,
        operation="admit-reasoning-input",
        operation_id="admit-spanless-input",
        episode_id="episode-spanless",
        inputs=[admitted_source_input(None)],
    )
    assert admitted["admitted"][0]["source_binding"] == {
        "source_revision_id": SOURCE_REVISION,
        "span": None,
    }
    with pytest.raises(FieldIntelligenceError, match="cites a span the episode did not admit"):
        step(
            state,
            operation="advance-reasoning",
            operation_id="advance-spanless",
            episode_id="episode-spanless",
            expected_return={
                "call_id": invitation["call_id"],
                "request_sha256": invitation["request_sha256"],
                "result": {"accepted": True, "value": 7.0},
                "status": "halted",
            },
        )


def test_admitted_input_span_requires_an_identity() -> None:
    state = surfaced(semantic_cognition_state())
    state, _began = begin(state, "episode-input", [adapter_item()])
    with pytest.raises(FieldIntelligenceError, match="source binding identity"):
        step(
            state,
            operation="admit-reasoning-input",
            operation_id="admit-malformed-input",
            episode_id="episode-input",
            inputs=[{"input_id": "input:source", "payload": {}, "span": [0, 4]}],
        )
