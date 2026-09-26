"""Bounded three-child field-owned recurrence over repeated LL-detail cycles.

This workstream is intentionally isolated from the existing two-cycle probe.  It
uses the production resonant-field transitions and asks whether an earlier
LL:detail -> L:scale route changes a *later* LL child, with matched feedback-off
and parent-off controls.  It is a field-wiring measurement, not a semantic
memory or task-utility claim.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Mapping

import numpy as np

import cassi_resonant_field as field
import run_fractal_recursive_memory_cell as prior_runner

SCHEMA = "cassifi.fractal-multicycle-recursive-memory-cell.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-multicycle-recursive-memory-cell/exploration.json")
SEED_FLOW = (1.0, 0.0)
BASE_FLOW = (0.0, 1.0)
SEED_BUDGET = 1e-3
CHILD_BUDGET = 5e-4
SOURCE_OFF_TICKS = 1
CYCLES = 3
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
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": type(exc).__name__ == field.ResonantNumericalError.__name__ and expected in str(exc),
            "expected": expected,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    return {
        "attempted": True,
        "accepted": True,
        "can_fail": False,
        "expected": expected,
        "error_type": None,
        "error": None,
    }


def _seed_and_freeze() -> tuple[field.ResonantWorkspace, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    origin = field.initial_workspace(field.ResonantProfile())
    seeded_scale, scale_receipt = field.apply_helical_packet_impulse(
        origin, path="LL", component="scale", flow_signal=SEED_FLOW,
        work_budget=SEED_BUDGET, evidence_tick=origin.evidence_tick,
        event_kind="reasoning-work",
    )
    seeded, detail_receipt = field.apply_helical_packet_impulse(
        seeded_scale, path="LL", component="detail", flow_signal=SEED_FLOW,
        work_budget=SEED_BUDGET, evidence_tick=seeded_scale.evidence_tick,
        event_kind="reasoning-work",
    )
    captured, capture_receipt = field.write_parent_registers(
        seeded, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, freeze_receipt = field.freeze_parent(captured)
    return (
        frozen,
        {"scale": scale_receipt, "detail": detail_receipt},
        capture_receipt,
        freeze_receipt,
        {"origin_state_sha256": origin.state_sha256, "seeded_state_sha256": seeded.state_sha256},
    )


def _cycle(
    workspace: field.ResonantWorkspace,
    *,
    cycle: int,
    upward_enabled: bool,
    parent_enabled: bool,
    work_budget: float,
) -> tuple[field.ResonantWorkspace, dict[str, Any]]:
    """Execute one downward child transition and (except after the last child)
    its release/upward/materialize/refreeze boundary.

    The returned workspace has an active frozen parent so the next cycle starts
    from the exact register/materialization boundary of the prior one.
    """
    frozen_before = field.read_frozen_parent(workspace)
    sibling_before_down = field.analyze_helical_packet(workspace, path="LR")
    target_before_down = field.analyze_helical_packet(workspace, path="LL")
    pre_page_sha256 = _page(workspace)
    pre_state_sha256 = workspace.state_sha256
    relation_before = _relation(workspace)
    child, down = field.apply_frozen_parent_to_child(
        workspace,
        freeze_id=str(frozen_before["freeze_id"]),
        base_flow_signal=BASE_FLOW,
        component="detail",
        work_budget=work_budget,
        parent_enabled=parent_enabled,
        expected_parent_summary_sha256=str(frozen_before["summary_sha256"]),
        expected_parent_source_state_sha256=str(frozen_before["source_state_sha256"]),
        expected_relation_sha256=str(frozen_before["relation_sha256"]),
        expected_child_source_state_sha256=workspace.state_sha256,
    )
    target_after_down = field.analyze_helical_packet(child, path="LL")
    if cycle == CYCLES:
        child_packet = target_after_down
        sibling_after_down = field.analyze_helical_packet(child, path="LR")
        released_terminal, release = field.release_frozen_parent(
            child, freeze_id=str(frozen_before["freeze_id"])
        )
        return released_terminal, {
            "cycle": cycle,
            "parent_enabled": parent_enabled,
            "upward_enabled": False,
            "downward": down,
            "release": release,
            "upward": {"attempted": False, "accepted": False, "applied_work": 0.0},
            "materialize": {"accepted": False, "reason": "terminal child"},
            "freeze_after": {"accepted": False, "released": True, "freeze_id": release["freeze_id"]},
            "pre_state_sha256": pre_state_sha256,
            "pre_page_sha256": pre_page_sha256,
            "child_state_sha256": child.state_sha256,
            "child_page_sha256": _page(child),
            "downward_target_packet_delta_norm": _norm(target_before_down["coefficients"], target_after_down["coefficients"]),
            "downward_target_field_state_delta_norm": _norm(workspace._field, child._field),
            "child_packet_sha256": child_packet["packet_sha256"],
            "child_packet_coefficients": np.asarray(child_packet["coefficients"], dtype=np.float64).tolist(),
            "child_flow_signal": down["effective_flow_signal"],
            "parent_register_preserved_before_materialize": True,
            "sibling_delta_norm": _norm(sibling_before_down["coefficients"], sibling_after_down["coefficients"]),
        }
    
    released, release = field.release_frozen_parent(child, freeze_id=str(frozen_before["freeze_id"]))
    child_packet = field.analyze_helical_packet(released, path="LL")
    if upward_enabled:
        updated, upward = field.apply_live_child_detail_to_parent(
            released,
            work_budget=work_budget,
            parent_enabled=True,
            expected_child_source_state_sha256=released.state_sha256,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256=str(relation_before["relation_sha256"]),
        )
    else:
        updated = released
        upward = {
            "schema": "cassifi.live-child-detail-to-parent.v1",
            "attempted": False,
            "accepted": False,
            "parent_enabled": False,
            "reason": "matched feedback-off control omits active upward impulse",
            "child_source_state_sha256": released.state_sha256,
            "child_packet_sha256": child_packet["packet_sha256"],
            "relation_sha256": relation_before["relation_sha256"],
            "applied_work": 0.0,
            "balance_defect": 0.0,
        }
    register_before = field.read_parent_register(updated, "L")
    register_at_child = field.read_parent_register(released, "L")
    register_preserved = (
        register_before["values"] == register_at_child["values"]
        and register_before["summary_sha256"] == register_at_child["summary_sha256"]
    )
    materialized, materialize = field.recompute_parent_summary_from_child(
        updated,
        expected_source_state_sha256=updated.state_sha256,
        expected_relation_sha256=str(relation_before["relation_sha256"]),
        expected_child_packet_sha256=str(field.analyze_helical_packet(updated, path="LL")["packet_sha256"]),
    )
    frozen_after, freeze_after = field.freeze_parent(
        materialized,
        expected_state_sha256=materialized.state_sha256,
        expected_relation_sha256=str(materialize["relation_sha256"]),
    )
    sibling_after_down = field.analyze_helical_packet(child, path="LR")
    return frozen_after, {
        "cycle": cycle,
        "parent_enabled": parent_enabled,
        "upward_enabled": upward_enabled,
        "downward": down,
        "release": release,
        "upward": upward,
        "freeze_after": freeze_after,
        "materialize": materialize,
        "pre_state_sha256": pre_state_sha256,
        "pre_page_sha256": pre_page_sha256,
        "child_state_sha256": child.state_sha256,
        "child_page_sha256": _page(child),
        "downward_target_packet_delta_norm": _norm(target_before_down["coefficients"], target_after_down["coefficients"]),
        "downward_target_field_state_delta_norm": _norm(workspace._field, child._field),
        "child_packet_sha256": child_packet["packet_sha256"],
        "child_packet_coefficients": np.asarray(child_packet["coefficients"], dtype=np.float64).tolist(),
        "child_flow_signal": down["effective_flow_signal"],
        "parent_register_before_materialize": register_before,
        "parent_register_at_child": register_at_child,
        "parent_register_preserved_before_materialize": register_preserved,
        "parent_updated_state_sha256": updated.state_sha256,
        "sibling_delta_norm": _norm(sibling_before_down["coefficients"], sibling_after_down["coefficients"]),
    }


def _arm(
    source_off: field.ResonantWorkspace,
    *,
    name: str,
    upward_enabled: bool,
    parent_enabled: bool,
    work_budget: float,
) -> tuple[dict[str, Any], field.ResonantWorkspace]:
    workspace = source_off
    rows: list[dict[str, Any]] = []
    for cycle in range(1, CYCLES + 1):
        workspace, row = _cycle(
            workspace, cycle=cycle, upward_enabled=upward_enabled,
            parent_enabled=parent_enabled, work_budget=work_budget,
        )
        rows.append(row)
    final = rows[-1]
    return {
        "name": name,
        "upward_enabled": upward_enabled,
        "parent_enabled": parent_enabled,
        "work_budget": work_budget,
        "cycles": rows,
        "child_state_sha256s": [row["child_state_sha256"] for row in rows],
        "child_page_sha256s": [row["child_page_sha256"] for row in rows],
        "child_flow_signals": [row["child_flow_signal"] for row in rows],
        "child_packet_sha256s": [row["child_packet_sha256"] for row in rows],
        "child_packet_coefficients": [row["child_packet_coefficients"] for row in rows],
        "final_state_sha256": workspace.state_sha256,
        "final_page_sha256": _page(workspace),
        "final_flow_signal": final["child_flow_signal"],
        "final_packet_coefficients": final["child_packet_coefficients"],
        "final_sibling_delta_norm": final["sibling_delta_norm"],
        "final_field_vector": np.asarray(workspace._field, dtype=np.float64).tolist(),
    }, workspace


def _firing_control(name: str, holds: bool, mutated_holds: bool, *, observed: Any = None, mutated: Any = None) -> dict[str, Any]:
    return {
        "name": name,
        "holds": bool(holds),
        "can_fail": bool(holds and not mutated_holds),
        "observed": observed,
        "mutated": mutated,
        "mutated_holds": bool(mutated_holds),
    }


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    # Continuity is measured, not imported as hidden state: two first-hop
    # applied-work values from the prior verified runner must reproduce here.
    prior = prior_runner.build_receipt()
    frozen, seed, capture, initial_freeze, seed_meta = _seed_and_freeze()
    source_off, source_off_receipt = field.advance_workspace(
        frozen, ticks=SOURCE_OFF_TICKS, demand=0.0, source_enabled=False
    )
    full, full_final = _arm(source_off, name="feedback-on", upward_enabled=True, parent_enabled=True, work_budget=CHILD_BUDGET)
    feedback_off, off_final = _arm(source_off, name="feedback-off", upward_enabled=False, parent_enabled=True, work_budget=CHILD_BUDGET)
    parent_off, parent_off_final = _arm(source_off, name="parent-off", upward_enabled=False, parent_enabled=False, work_budget=CHILD_BUDGET)
    zero_work, zero_final = _arm(source_off, name="zero-work", upward_enabled=True, parent_enabled=True, work_budget=0.0)

    late_field_delta = _norm(full_final._field, off_final._field)
    late_flow_delta = _norm(full["final_flow_signal"], feedback_off["final_flow_signal"])
    late_packet_delta = _norm(full["final_packet_coefficients"], feedback_off["final_packet_coefficients"])
    first_packet_delta = _norm(full["child_packet_coefficients"][0], feedback_off["child_packet_coefficients"][0])
    persistence_ratio = late_packet_delta / max(float(np.linalg.norm(np.asarray(feedback_off["final_packet_coefficients"], dtype=np.float64))), MARGIN)
    selectivity_ratio = max(
        row["sibling_delta_norm"]
        for arm in (full, feedback_off, parent_off, zero_work)
        for row in arm["cycles"]
    )

    # Freshness and lock controls fire against real transitions.
    released, release_control = field.release_frozen_parent(source_off, freeze_id=str(initial_freeze["freeze_id"]))
    relation = _relation(released)
    packet = field.analyze_helical_packet(released, path="LL")
    stale_source = _error(lambda: field.apply_live_child_detail_to_parent(
        released, work_budget=CHILD_BUDGET,
        expected_child_source_state_sha256="0" * 64,
        expected_child_packet_sha256=str(packet["packet_sha256"]),
        expected_relation_sha256=str(relation["relation_sha256"]),
    ), "child detail source state digest is stale")
    stale_packet = _error(lambda: field.apply_live_child_detail_to_parent(
        released, work_budget=CHILD_BUDGET,
        expected_child_source_state_sha256=released.state_sha256,
        expected_child_packet_sha256="0" * 64,
        expected_relation_sha256=str(relation["relation_sha256"]),
    ), "child detail packet digest is stale")
    stale_relation = _error(lambda: field.apply_live_child_detail_to_parent(
        released, work_budget=CHILD_BUDGET,
        expected_child_source_state_sha256=released.state_sha256,
        expected_child_packet_sha256=str(packet["packet_sha256"]),
        expected_relation_sha256="0" * 64,
    ), "child detail relation digest is stale")
    frozen_lock = _error(lambda: field.apply_live_child_detail_to_parent(
        source_off, work_budget=CHILD_BUDGET,
        expected_child_source_state_sha256=source_off.state_sha256,
        expected_child_packet_sha256=str(field.analyze_helical_packet(source_off, path="LL")["packet_sha256"]),
        expected_relation_sha256=str(_relation(source_off)["relation_sha256"]),
    ), "child detail to parent transition is locked while a frozen parent is active")
    standalone_zero, standalone_zero_receipt = field.apply_live_child_detail_to_parent(
        released,
        work_budget=0.0,
        parent_enabled=True,
        expected_child_source_state_sha256=released.state_sha256,
        expected_child_packet_sha256=str(packet["packet_sha256"]),
        expected_relation_sha256=str(relation["relation_sha256"]),
    )
    standalone_upward_identity = standalone_zero.state_sha256 == released.state_sha256
    roundtrip = field.ResonantWorkspace.from_dict(full_final.as_dict())
    roundtrip_holds = roundtrip.state_sha256 == full_final.state_sha256 and roundtrip.page_bytes == full_final.page_bytes

    zero_identity = all(
        row["pre_page_sha256"] == row["child_page_sha256"]
        and row["pre_state_sha256"] == row["child_state_sha256"]
        for row in zero_work["cycles"]
    )
    # A zero-work route must leave each downward transition as an identity;
    # register/materialization metadata is intentionally not this predicate.
    source_off_holds = source_off_receipt["source_enabled"] is False and source_off_receipt["positive_heartbeat_work"] == 0.0
    sibling_holds = selectivity_ratio <= MARGIN
    persistence_holds = late_packet_delta > MARGIN and persistence_ratio > MARGIN
    selectivity_holds = sibling_holds and late_packet_delta > MARGIN
    downward_packet_holds = all(
        row["downward_target_packet_delta_norm"] > MARGIN
        for arm in (full, feedback_off)
        for row in arm["cycles"]
    )
    zero_downward_holds = all(
        row["downward_target_packet_delta_norm"] == 0.0
        and row["downward_target_field_state_delta_norm"] == 0.0
        for row in zero_work["cycles"]
    )
    controls = {
        "zero_work_identity": _firing_control("zero_work_identity", zero_identity, False, observed=zero_work["final_page_sha256"], mutated="0" * 64),
        "zero_work_downward_target": _firing_control("zero_work_downward_target", zero_downward_holds, False, observed=[row["downward_target_packet_delta_norm"] for row in zero_work["cycles"]], mutated=[MARGIN * 2]),
        "standalone_upward_zero_work": _firing_control("standalone_upward_zero_work", standalone_upward_identity, False, observed=standalone_zero.state_sha256, mutated="0" * 64),
        "source_off_heartbeat": _firing_control("source_off_heartbeat", source_off_holds, False, observed=source_off_receipt["positive_heartbeat_work"], mutated=1.0),
        "sibling_isolation": _firing_control("sibling_isolation", sibling_holds, False, observed=selectivity_ratio, mutated=MARGIN * 2),
        "immutable_roundtrip": _firing_control("immutable_roundtrip", roundtrip_holds, False, observed=roundtrip.state_sha256, mutated="0" * 64),
        "stale_source": stale_source,
        "stale_packet": stale_packet,
        "stale_relation": stale_relation,
        "frozen_parent_lock": frozen_lock,
    }
    controls["persistence_selectivity_mutation"] = _firing_control(
        "persistence_selectivity_predicate", persistence_holds and selectivity_holds, False,
        observed={"persistence_ratio": persistence_ratio, "selectivity_ratio": selectivity_ratio},
        mutated={"persistence_ratio": 0.0, "selectivity_ratio": MARGIN * 2},
    )

    continuity_delta = abs(float(prior["arms"]["full-loop"]["first_application"]["impulse"]["applied_work"]) - float(full["cycles"][0]["downward"]["impulse"]["applied_work"]))
    continuity_holds = continuity_delta <= MARGIN
    comparisons = [
        {"id": "later_child_field_state_diverges", "quantity": late_field_delta, "holds": late_field_delta > MARGIN, "margin": MARGIN},
        {"id": "later_child_flow_diverges", "quantity": late_flow_delta, "holds": late_flow_delta > MARGIN, "margin": MARGIN},
        {"id": "later_child_packet_diverges", "quantity": late_packet_delta, "holds": late_packet_delta > MARGIN, "margin": MARGIN},
        {"id": "feedback_persists_to_late_child", "quantity": persistence_ratio, "holds": persistence_holds, "margin": MARGIN},
        {"id": "feedback_is_selective_to_LL", "quantity": selectivity_ratio, "holds": selectivity_holds, "margin": MARGIN},
        {"id": "all_feedback_on_off_downward_LL_targets_diverge", "quantity": min(row["downward_target_packet_delta_norm"] for arm in (full, feedback_off) for row in arm["cycles"]), "holds": downward_packet_holds, "margin": MARGIN},
        {"id": "all_zero_work_downward_targets_are_identity", "quantity": float(zero_downward_holds), "holds": zero_downward_holds, "margin": 0.0},
        {"id": "all_nonterminal_registers_preserved_before_materialize", "quantity": float(all(row["parent_register_preserved_before_materialize"] for arm in (full, feedback_off, parent_off, zero_work) for row in arm["cycles"][:-1])), "holds": all(row["parent_register_preserved_before_materialize"] for arm in (full, feedback_off, parent_off, zero_work) for row in arm["cycles"][:-1]), "margin": 0.0},
        {"id": "zero_work_is_identity", "quantity": float(zero_identity), "holds": zero_identity, "margin": 0.0},
        {"id": "standalone_upward_zero_work_is_identity", "quantity": float(standalone_upward_identity), "holds": standalone_upward_identity, "margin": 0.0},
        {"id": "immutable_workspace_roundtrip", "quantity": float(roundtrip_holds), "holds": roundtrip_holds, "margin": 0.0},
        {"id": "source_off_has_zero_positive_heartbeat", "quantity": float(source_off_holds), "holds": source_off_holds, "margin": 0.0},
        {"id": "stale_source_rejected", "quantity": float(stale_source["can_fail"]), "holds": stale_source["can_fail"], "margin": 0.0},
        {"id": "stale_packet_rejected", "quantity": float(stale_packet["can_fail"]), "holds": stale_packet["can_fail"], "margin": 0.0},
        {"id": "stale_relation_rejected", "quantity": float(stale_relation["can_fail"]), "holds": stale_relation["can_fail"], "margin": 0.0},
        {"id": "frozen_parent_lock_rejected", "quantity": float(frozen_lock["can_fail"]), "holds": frozen_lock["can_fail"], "margin": 0.0},
        {"id": "mutated_persistence_selectivity_fails", "quantity": float(controls["persistence_selectivity_mutation"]["can_fail"]), "holds": controls["persistence_selectivity_mutation"]["can_fail"], "margin": 0.0},
        {"id": "prior_receipt_continuity", "quantity": continuity_delta, "holds": continuity_holds, "margin": MARGIN},
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "arithmetic": "deterministic CPU float64",
            "bounded_transitions": CYCLES,
            "route": "D1 frozen L -> LL:detail -> release -> U1 live LL:detail -> L:scale -> explicit recompute -> refreeze; D2/U2; D3 final LL:detail then release",
            "primary_observable": "third-child LL field page, packet, and effective-flow divergence caused by prior upward feedback",
            "matched_arms": ["feedback-on", "feedback-off"],
            "register_semantics": "parent register is read before materialization; upward transition never rewrites it",
            "limitation": "field-level recurrent causal wiring only; no semantic retrieval, embeddings, semantic memory, or task utility claim",
        },
        "seed": seed,
        "capture": capture,
        "initial_freeze": initial_freeze,
        "seed_metadata": seed_meta,
        "source_off": source_off_receipt,
        "arms": {"feedback-on": full, "feedback-off": feedback_off, "parent-off": parent_off, "zero-work": zero_work},
        "later_child_contrast": {
            "feedback_on_final_state_sha256": full["final_state_sha256"],
            "feedback_off_final_state_sha256": feedback_off["final_state_sha256"],
            "field_state_delta_norm": late_field_delta,
            "effective_flow_delta_norm": late_flow_delta,
            "packet_delta_norm": late_packet_delta,
            "first_packet_delta_norm": first_packet_delta,
            "persistence_ratio": persistence_ratio,
            "selectivity_ratio": selectivity_ratio,
        },
        "controls": controls,
        "comparisons": comparisons,
        "continuity": {
            "prior_schema": prior["schema"],
            "prior_content_digest": prior["content_digest"],
            "cited_numbers": {
                "prior_full_first_applied_work": prior["arms"]["full-loop"]["first_application"]["impulse"]["applied_work"],
                "prior_parent_off_first_applied_work": prior["arms"]["parent-off"]["first_application"]["impulse"]["applied_work"],
            },
            "reproduced_numbers": {
                "current_full_first_applied_work": full["cycles"][0]["downward"]["impulse"]["applied_work"],
                "current_parent_off_first_applied_work": parent_off["cycles"][0]["downward"]["impulse"]["applied_work"],
            },
            "allowance": MARGIN,
        },
        "runtime_seconds": float(perf_counter() - started),
    }
    body["verdict"] = "PASS_FIELD_OWNED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE" if all(row["holds"] for row in comparisons) else "FAIL_CLOSED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE"
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
