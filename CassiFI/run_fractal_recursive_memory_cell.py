"""Measure one closed field-owned L/LL recurrence over two child writes.

The primary observable is the later LL child itself: a full loop and a
feedback-off loop start from the same source-off state and differ only in
whether the updated L parent flow is coupled into LL_{t+2}.  This is a
field-level causal wiring probe, not a semantic-memory or task-utility claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
import run_fractal_bidirectional_recursive_memory_cell as bidirectional_runner
import run_fractal_parent_summary_application_exploration as parent_runner
from cassi_field_atlas import AtlasState
from cassi_field_owner import FieldIntelligenceOwner

SCHEMA = "cassifi.fractal-recursive-memory-cell.v2"
DEFAULT_OUTPUT = Path("_diag/fractal-recursive-memory-cell/exploration.json")
SEED_FLOW = (1.0, 0.0)
BASE_FLOW = (0.0, 1.0)
SEED_BUDGET = 1e-3
CHILD_BUDGET = 5e-4
SOURCE_OFF_TICKS = 1
MARGIN = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    if isinstance(value, (np.integer, np.floating, np.bool_)):
        return value.item()
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [_strip_timing(v) for v in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_timing(value)).encode()).hexdigest()


def _norm(left: Any, right: Any) -> float:
    return float(np.linalg.norm(np.asarray(left, dtype=np.float64) - np.asarray(right, dtype=np.float64)))


def _page(workspace: field.ResonantWorkspace) -> str:
    return hashlib.sha256(workspace.page_bytes).hexdigest()


def _relation(workspace: field.ResonantWorkspace) -> Mapping[str, Any]:
    metadata = workspace.layout_transition[field.PARENT_REGISTER_METADATA_KEY]
    return next(item for item in metadata["relations"] if item["parent_path"] == "L" and item["child_path"] == "LL")


def _error(call: Any, expected: str) -> dict[str, Any]:
    try:
        call()
    except Exception as exc:
        error_type = type(exc).__name__
        error = str(exc)
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": error_type == field.ResonantNumericalError.__name__ and expected in error,
            "expected": expected,
            "error_type": error_type,
            "error": error,
        }
    return {
        "attempted": True,
        "accepted": True,
        "can_fail": False,
        "expected": expected,
        "error_type": None,
        "error": None,
    }


def _loop(
    origin: field.ResonantWorkspace,
    *,
    first_parent_enabled: bool,
    upward_enabled: bool,
    second_parent_enabled: bool,
    second_work_budget: float,
) -> tuple[dict[str, Any], field.ResonantWorkspace, field.ResonantWorkspace]:
    """Run the strict L/LL route with an active upward child-detail impulse."""
    frozen_before = field.read_frozen_parent(origin)
    relation_before = _relation(origin)
    first_child, first_receipt = field.apply_frozen_parent_to_child(
        origin,
        freeze_id=str(frozen_before["freeze_id"]),
        base_flow_signal=BASE_FLOW,
        component="detail",
        work_budget=CHILD_BUDGET,
        parent_enabled=first_parent_enabled,
        expected_parent_summary_sha256=str(frozen_before["summary_sha256"]),
        expected_parent_source_state_sha256=str(frozen_before["source_state_sha256"]),
        expected_relation_sha256=str(frozen_before["relation_sha256"]),
        expected_child_source_state_sha256=origin.state_sha256,
    )
    released, release_receipt = field.release_frozen_parent(
        first_child, freeze_id=str(frozen_before["freeze_id"])
    )
    child_packet = field.analyze_helical_packet(released, path="LL")
    if upward_enabled:
        upward_parent, upward_receipt = field.apply_live_child_detail_to_parent(
            released,
            work_budget=CHILD_BUDGET,
            parent_enabled=True,
            expected_child_source_state_sha256=released.state_sha256,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256=str(relation_before["relation_sha256"]),
        )
    else:
        upward_parent = released
        upward_receipt = {
            "schema": "cassifi.live-child-detail-to-parent.v1",
            "attempted": False,
            "accepted": False,
            "parent_enabled": False,
            "reason": "feedback-off control omits active upward impulse",
            "child_source_state_sha256": released.state_sha256,
            "child_packet_sha256": child_packet["packet_sha256"],
            "relation_sha256": relation_before["relation_sha256"],
            "applied_work": 0.0,
            "balance_defect": 0.0,
        }
    parent_register_before_materialize = field.read_parent_register(upward_parent, "L")
    parent_register_at_child = field.read_parent_register(released, "L")
    parent_register_preserved_before_materialize = (
        parent_register_before_materialize["values"] == parent_register_at_child["values"]
        and parent_register_before_materialize["summary_sha256"] == parent_register_at_child["summary_sha256"]
    )
    # The live impulse changes L's field coordinates but intentionally does not
    # rewrite its canonical register.  Explicitly materialize that updated
    # parent before refreezing; this is not the upward route itself.
    parent_updated, materialize_receipt = field.recompute_parent_summary_from_child(
        upward_parent,
        expected_source_state_sha256=upward_parent.state_sha256,
        expected_relation_sha256=str(relation_before["relation_sha256"]),
        expected_child_packet_sha256=str(
            field.analyze_helical_packet(upward_parent, path="LL")["packet_sha256"]
        ),
    )
    updated_parent = field.read_parent_register(parent_updated, "L")
    frozen_after, freeze_receipt = field.freeze_parent(
        parent_updated,
        expected_state_sha256=parent_updated.state_sha256,
        expected_relation_sha256=str(materialize_receipt["relation_sha256"]),
    )
    sibling_before = field.analyze_helical_packet(frozen_after, path="LR")
    later_child, later_receipt = field.apply_frozen_parent_to_child(
        frozen_after,
        freeze_id=str(freeze_receipt["freeze_id"]),
        base_flow_signal=BASE_FLOW,
        work_budget=second_work_budget,
        parent_enabled=second_parent_enabled,
        component="detail",
        expected_parent_source_state_sha256=str(freeze_receipt["source_state_sha256"]),
        expected_relation_sha256=str(freeze_receipt["relation_sha256"]),
        expected_child_source_state_sha256=frozen_after.state_sha256,
    )
    sibling_after = field.analyze_helical_packet(later_child, path="LR")
    later_packet_before = field.analyze_helical_packet(frozen_after, path="LL")
    later_packet_after = field.analyze_helical_packet(later_child, path="LL")
    row = {
        "first_parent_enabled": first_parent_enabled,
        "upward_enabled": upward_enabled,
        "second_parent_enabled": second_parent_enabled,
        "second_work_budget": second_work_budget,
        "initial_state_sha256": origin.state_sha256,
        "first_child_state_sha256": first_child.state_sha256,
        "parent_register_at_child": parent_register_at_child,
        "parent_register_before_materialize": parent_register_before_materialize,
        "parent_register_preserved_before_materialize": parent_register_preserved_before_materialize,
        "parent_register_after_materialize": updated_parent,
        "parent_updated_state_sha256": parent_updated.state_sha256,
        "later_child_initial_state_sha256": frozen_after.state_sha256,
        "later_child_final_state_sha256": later_child.state_sha256,
        "initial_page_sha256": _page(origin),
        "later_child_final_page_sha256": _page(later_child),
        "updated_parent_values": updated_parent["values"],
        "relation_before_sha256": relation_before["relation_sha256"],
        "relation_after_sha256": freeze_receipt["relation_sha256"],
        "first_application": first_receipt,
        "release": release_receipt,
        "upward_application": upward_receipt,
        "materialize_parent": materialize_receipt,
        "freeze_after_materialize": freeze_receipt,
        "later_application": later_receipt,
        "later_child_packet_before_coefficients": np.asarray(later_packet_before["coefficients"], dtype=np.float64).tolist(),
        "later_child_packet_after_coefficients": np.asarray(later_packet_after["coefficients"], dtype=np.float64).tolist(),
        "later_child_flow_signal": later_receipt["effective_flow_signal"],
        "sibling_path": "LR",
        "sibling_delta_norm": _norm(sibling_before["coefficients"], sibling_after["coefficients"]),
        "later_child_self_delta_norm": _norm(later_packet_before["coefficients"], later_packet_after["coefficients"]),
    }
    return row, later_child, parent_updated


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    # Import and execute the prior verified builder as a continuity check.  No
    # result from it is used as hidden state; only two cited first-hop numbers
    # are compared against this runner's independently executed first hop.
    parent_continuity = parent_runner.build_receipt()
    bidirectional_continuity = bidirectional_runner.build_receipt()
    origin = field.initial_workspace(field.ResonantProfile())

    seeded_scale, seed_scale_receipt = field.apply_helical_packet_impulse(
        origin,
        path="LL",
        component="scale",
        flow_signal=SEED_FLOW,
        work_budget=SEED_BUDGET,
        evidence_tick=origin.evidence_tick,
        event_kind="reasoning-work",
    )
    seeded, seed_detail_receipt = field.apply_helical_packet_impulse(
        seeded_scale,
        path="LL",
        component="detail",
        flow_signal=SEED_FLOW,
        work_budget=SEED_BUDGET,
        evidence_tick=seeded_scale.evidence_tick,
        event_kind="reasoning-work",
    )
    seed_receipt = {"scale": seed_scale_receipt, "detail": seed_detail_receipt}
    captured, capture_receipt = field.write_parent_registers(
        seeded, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, freeze_receipt = field.freeze_parent(captured)
    frozen_read = field.read_frozen_parent(frozen)
    source_off, source_off_receipt = field.advance_workspace(
        frozen, ticks=SOURCE_OFF_TICKS, demand=0.0, source_enabled=False
    )
    full, full_final, full_parent_updated = _loop(
        source_off, first_parent_enabled=True, upward_enabled=True,
        second_parent_enabled=True, second_work_budget=CHILD_BUDGET,
    )
    feedback_off, feedback_final, _ = _loop(
        source_off, first_parent_enabled=True, upward_enabled=False,
        second_parent_enabled=False, second_work_budget=CHILD_BUDGET,
    )
    parent_off, parent_off_final, _ = _loop(
        source_off, first_parent_enabled=False, upward_enabled=False,
        second_parent_enabled=False, second_work_budget=CHILD_BUDGET,
    )
    zero_work, zero_final, _ = _loop(
        source_off, first_parent_enabled=True, upward_enabled=True,
        second_parent_enabled=True, second_work_budget=0.0,
    )

    first_on_delta = float(full["first_application"]["impulse"]["applied_work"])
    first_off_delta = float(parent_off["first_application"]["impulse"]["applied_work"])
    continuity = {
        "parent_runner_schema": parent_continuity["schema"],
        "parent_receipt_digest": parent_continuity["content_digest"],
        "parent_verdict": parent_continuity["verdict"],
        "bidirectional_runner_schema": bidirectional_continuity["schema"],
        "bidirectional_receipt_digest": bidirectional_continuity["content_digest"],
        "cited_numbers": {
            "parent_on_applied_work": parent_continuity["arms"]["parent-on"]["application"]["impulse"]["applied_work"],
            "parent_off_applied_work": parent_continuity["arms"]["parent-off"]["application"]["impulse"]["applied_work"],
        },
        "reproduced_numbers": {
            "parent_on_first_applied_work": first_on_delta,
            "parent_off_first_applied_work": first_off_delta,
        },
        "allowance": MARGIN,
        "holds": abs(first_on_delta - float(parent_continuity["arms"]["parent-on"]["application"]["impulse"]["applied_work"])) <= MARGIN
        and abs(first_off_delta - float(parent_continuity["arms"]["parent-off"]["application"]["impulse"]["applied_work"])) <= MARGIN,
    }

    # Provenance controls: each stale/tampered input is attempted against a
    # real transition, never a synthetic predicate.
    released_source, source_release_control = field.release_frozen_parent(
        source_off, freeze_id=str(frozen_read["freeze_id"])
    )
    relation_now = _relation(released_source)
    child_packet = field.analyze_helical_packet(released_source, path="LL")
    stale_source = _error(
        lambda: field.recompute_parent_summary_from_child(
            released_source,
            expected_source_state_sha256="0" * 64,
            expected_relation_sha256=str(relation_now["relation_sha256"]),
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
        ),
        "parent recompute source state digest is stale",
    )
    stale_upward_source = _error(
        lambda: field.apply_live_child_detail_to_parent(
            released_source,
            work_budget=CHILD_BUDGET,
            expected_child_source_state_sha256="0" * 64,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256=str(relation_now["relation_sha256"]),
        ),
        "child detail source state digest is stale",
    )
    stale_upward_packet = _error(
        lambda: field.apply_live_child_detail_to_parent(
            released_source,
            work_budget=CHILD_BUDGET,
            expected_child_source_state_sha256=released_source.state_sha256,
            expected_child_packet_sha256="0" * 64,
            expected_relation_sha256=str(relation_now["relation_sha256"]),
        ),
        "child detail packet digest is stale",
    )
    stale_upward_relation = _error(
        lambda: field.apply_live_child_detail_to_parent(
            released_source,
            work_budget=CHILD_BUDGET,
            expected_child_source_state_sha256=released_source.state_sha256,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256="0" * 64,
        ),
        "child detail relation digest is stale",
    )
    stale_parent = _error(
        lambda: field.apply_frozen_parent_to_child(
            source_off,
            freeze_id=str(frozen_read["freeze_id"]),
            base_flow_signal=BASE_FLOW,
            work_budget=CHILD_BUDGET,
            expected_parent_summary_sha256="0" * 64,
            expected_parent_source_state_sha256=str(frozen_read["source_state_sha256"]),
            expected_relation_sha256=str(frozen_read["relation_sha256"]),
            expected_child_source_state_sha256=source_off.state_sha256,
        ),
        "frozen parent summary digest is stale",
    )
    tampered = copy.deepcopy(source_off.as_dict())
    tampered_map = dict(tampered["layout_transition"][field.PARENT_REGISTER_METADATA_KEY])
    tampered_relations = [dict(item) for item in tampered_map["relations"]]
    tampered_relations[0]["relation_sha256"] = "0" * 64
    tampered_map["relations"] = tampered_relations
    tampered["layout_transition"][field.PARENT_REGISTER_METADATA_KEY] = tampered_map
    tampered_control = _error(
        lambda: field.ResonantWorkspace.from_dict(tampered),
        "parent register relation digest mismatch",
    )

    owner_receipt: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="cassifi-recursive-cell-owner-") as directory:
        owner = FieldIntelligenceOwner(Path(directory), initial_state=AtlasState(resonant_workspace=full_parent_updated))
        try:
            owner_freeze_result = owner.freeze_parent("owner:later-freeze")
            owner_freeze = owner_freeze_result["frozen_parent_receipt"]
            owner_manifest = owner.checkpoints.current_manifest_sha256
            owner_result = owner.apply_frozen_parent_to_child(
                "owner:later-child",
                freeze_id=str(owner_freeze["freeze_id"]),
                base_flow_signal=BASE_FLOW,
                work_budget=CHILD_BUDGET,
                parent_enabled=True,
                expected_parent_summary_sha256=str(owner_freeze["summary_sha256"]),
                expected_parent_source_state_sha256=str(owner_freeze["source_state_sha256"]),
            )
            reloaded_state = owner.checkpoints.load_version(owner_manifest)
            reloaded_owner = FieldIntelligenceOwner(
                Path(directory) / "reloaded",
                initial_state=reloaded_state,
            )
            try:
                replay = reloaded_owner.apply_frozen_parent_to_child(
                    "owner:later-child",
                    freeze_id=str(owner_freeze["freeze_id"]),
                    base_flow_signal=BASE_FLOW,
                    work_budget=CHILD_BUDGET,
                    parent_enabled=True,
                    expected_parent_summary_sha256=str(owner_freeze["summary_sha256"]),
                    expected_parent_source_state_sha256=str(owner_freeze["source_state_sha256"]),
                    expected_relation_sha256=str(owner_freeze["relation_sha256"]),
                )
            finally:
                reloaded_owner.close()
            owner_receipt = {
                "freeze": owner_freeze,
                "manifest_before_apply": owner_manifest,
                "result": owner_result,
                "reloaded_state_sha256": reloaded_state.state_sha256,
                "current_state_sha256": owner.state.state_sha256,
                "replay": replay,
                "replay_same_state": replay["frozen_parent_application_receipt"]["state_sha256"] == owner_result["frozen_parent_application_receipt"]["state_sha256"],
            }
        finally:
            owner.close()

    later_state_divergence = _norm(full_final._field, feedback_final._field)
    later_flow_divergence = _norm(full["later_child_flow_signal"], feedback_off["later_child_flow_signal"])
    later_packet_divergence = _norm(full["later_child_packet_after_coefficients"], feedback_off["later_child_packet_after_coefficients"])
    all_impulses = {
        name: {
            "first_applied_work": row["first_application"]["impulse"]["applied_work"],
            "first_balance_defect": row["first_application"]["impulse"]["balance_defect"],
            "upward_applied_work": row["upward_application"]["applied_work"],
            "upward_balance_defect": row["upward_application"]["balance_defect"],
            "later_applied_work": row["later_application"]["impulse"]["applied_work"],
            "later_balance_defect": row["later_application"]["impulse"]["balance_defect"],
            "later_requested_work": row["later_application"]["impulse"]["requested_work"],
        }
        for name, row in {"full-loop": full, "feedback-off": feedback_off, "parent-off": parent_off, "zero-work": zero_work}.items()
    }
    comparisons = [
        {"id": "later_child_field_state_diverges_full_loop_vs_feedback_off", "quantity": later_state_divergence, "holds": later_state_divergence > MARGIN, "margin": MARGIN},
        {"id": "later_child_flow_diverges_full_loop_vs_feedback_off", "quantity": later_flow_divergence, "holds": later_flow_divergence > MARGIN, "margin": MARGIN},
        {"id": "later_child_packet_diverges_full_loop_vs_feedback_off", "quantity": later_packet_divergence, "holds": later_packet_divergence > MARGIN, "margin": MARGIN},
        {"id": "active_upward_child_detail_impulse_reaches_parent", "quantity": float(full["upward_application"]["accepted"]), "holds": full["upward_enabled"] and full["upward_application"]["accepted"] and full["upward_application"]["applied_work"] > MARGIN, "margin": MARGIN},
        {"id": "register_preserved_before_explicit_materialization", "quantity": float(full["parent_register_preserved_before_materialize"]), "holds": full["parent_register_preserved_before_materialize"], "margin": 0.0},
        {"id": "feedback_off_omits_active_upward_impulse", "quantity": float(not feedback_off["upward_application"]["attempted"]), "holds": feedback_off["upward_application"]["attempted"] is False and feedback_off["upward_application"]["applied_work"] == 0.0, "margin": 0.0},
        {"id": "feedback_off_disables_only_later_parent_coupling", "quantity": float(not feedback_off["second_parent_enabled"] and feedback_off["first_parent_enabled"]), "holds": feedback_off["first_parent_enabled"] and not feedback_off["second_parent_enabled"], "margin": 0.0},
        {"id": "matched_parent_off_silences_both_parent_couplings", "quantity": float(not parent_off["first_parent_enabled"] and not parent_off["second_parent_enabled"]), "holds": not parent_off["first_parent_enabled"] and not parent_off["second_parent_enabled"], "margin": 0.0},
        {"id": "zero_work_later_child_is_identity", "quantity": float(zero_final.state_sha256 == zero_work["later_child_initial_state_sha256"]), "holds": zero_final.state_sha256 == zero_work["later_child_initial_state_sha256"], "margin": 0.0},
        {"id": "source_off_has_zero_positive_heartbeat_work", "quantity": float(source_off_receipt["positive_heartbeat_work"]), "holds": source_off_receipt["source_enabled"] is False and source_off_receipt["positive_heartbeat_work"] == 0.0, "margin": 0.0},
        {"id": "sibling_LR_isolation", "quantity": max(full["sibling_delta_norm"], feedback_off["sibling_delta_norm"], parent_off["sibling_delta_norm"], zero_work["sibling_delta_norm"]), "holds": max(full["sibling_delta_norm"], feedback_off["sibling_delta_norm"], parent_off["sibling_delta_norm"], zero_work["sibling_delta_norm"]) <= MARGIN, "margin": MARGIN},
        {"id": "all_impulse_balance_defects_bounded", "quantity": max(abs(float(v["first_balance_defect"])) for v in all_impulses.values()) if all_impulses else 0.0, "holds": all(abs(float(v[key])) <= MARGIN for v in all_impulses.values() for key in ("first_balance_defect", "upward_balance_defect", "later_balance_defect")), "margin": MARGIN},
        {"id": "stale_recompute_rejected", "quantity": float(stale_source["can_fail"]), "holds": stale_source["can_fail"], "margin": 0.0},
        {"id": "stale_upward_source_rejected", "quantity": float(stale_upward_source["can_fail"]), "holds": stale_upward_source["can_fail"], "margin": 0.0},
        {"id": "stale_upward_packet_rejected", "quantity": float(stale_upward_packet["can_fail"]), "holds": stale_upward_packet["can_fail"], "margin": 0.0},
        {"id": "stale_upward_relation_rejected", "quantity": float(stale_upward_relation["can_fail"]), "holds": stale_upward_relation["can_fail"], "margin": 0.0},
        {"id": "stale_parent_rejected", "quantity": float(stale_parent["can_fail"]), "holds": stale_parent["can_fail"], "margin": 0.0},
        {"id": "tampered_relation_rejected", "quantity": float(tampered_control["can_fail"]), "holds": tampered_control["can_fail"], "margin": 0.0},
        {"id": "owner_checkpoint_reload_replay", "quantity": float(owner_receipt["replay_same_state"]), "holds": owner_receipt["replay_same_state"], "margin": 0.0},
        {"id": "continuity_matches_prior_receipts", "quantity": float(continuity["holds"]), "holds": continuity["holds"], "margin": MARGIN},
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "semantic_memory_claim": False,
            "task_utility_claim": False,
            "recurrence": "L_t -> LL_{t+1} (detail); active LL_{t+1} detail -> L_{t+1}; L_{t+1} -> LL_{t+2} (detail)",
            "downward_component": "LL:detail for both frozen parent applications",
            "upward_route": "apply_live_child_detail_to_parent with expected child source/packet/relation digests",
            "materialization": "recompute_parent_summary_from_child occurs only after the active upward impulse and preserves the pre-materialization register distinction",
            "primary_observable": "later-child LL field-state, packet-state, and effective-flow divergence between full-loop and feedback-off arms",
            "parent_off_control": "both parent couplings disabled, with matched source-off predecessor",
            "source_off_ticks": SOURCE_OFF_TICKS,
            "arithmetic": "deterministic CPU float64",
            "sibling_path": "LR",
            "limitation": "proves only field-level recurrent causal wiring; not semantic retrieval, embeddings, semantic memory, or task utility",
        },
        "seed": seed_receipt,
        "capture": capture_receipt,
        "freeze": freeze_receipt,
        "source_off": source_off_receipt,
        "arms": {"full-loop": full, "feedback-off": feedback_off, "parent-off": parent_off, "zero-work": zero_work},
        "later_child_contrast": {
            "full_loop_final_state_sha256": full_final.state_sha256,
            "feedback_off_final_state_sha256": feedback_final.state_sha256,
            "field_state_delta_norm": later_state_divergence,
            "effective_flow_delta_norm": later_flow_divergence,
            "packet_delta_norm": later_packet_divergence,
            "full_loop_later_flow": full["later_child_flow_signal"],
            "feedback_off_later_flow": feedback_off["later_child_flow_signal"],
        },
        "work_balance": all_impulses,
        "controls": {"source_release": source_release_control, "stale_recompute": stale_source, "stale_upward_source": stale_upward_source, "stale_upward_packet": stale_upward_packet, "stale_upward_relation": stale_upward_relation, "stale_parent": stale_parent, "tampered_relation": tampered_control, "owner": owner_receipt},
        "continuity": continuity,
        "comparisons": comparisons,
        "runtime_seconds": float(perf_counter() - started),
    }
    body["verdict"] = "PASS_FIELD_OWNED_CLOSED_TWO_CYCLE_ACTIVE_UPWARD_RECURRENCE" if all(row["holds"] for row in comparisons) else "FAIL_CLOSED_TWO_CYCLE_ACTIVE_UPWARD_RECURRENCE"
    body["content_digest"] = content_digest(body)
    body["receipt_sha256"] = body["content_digest"]
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    digest = content_digest(receipt)
    return {"content_digest_matches": digest == receipt.get("content_digest"), "digest": digest}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "verdict": receipt["verdict"], "content_digest": receipt["content_digest"]}, sort_keys=True))
    return 0 if receipt["verdict"].startswith("PASS_") else 1


if __name__ == "__main__":
    raise SystemExit(main())
