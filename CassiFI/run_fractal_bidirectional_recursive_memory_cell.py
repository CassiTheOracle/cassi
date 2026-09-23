"""Measure the field-owned live LL-detail to L impulse transition."""
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
import run_fractal_parent_summary_application_exploration as parent_runner
from cassi_field_atlas import AtlasState
from cassi_field_owner import FieldIntelligenceError, FieldIntelligenceOwner

SCHEMA = "cassifi.fractal-bidirectional-recursive-memory-cell.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-bidirectional-recursive-memory-cell/exploration.json")
DETAIL_SIGNAL = (0.0, 1.0)
DETAIL_BUDGET = 5e-4
FEEDBACK_BUDGET = 5e-4
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
    return {"attempted": True, "accepted": True, "can_fail": False, "expected": expected, "error_type": None, "error": None}


def _relation(workspace: field.ResonantWorkspace) -> Mapping[str, Any]:
    relations = workspace.layout_transition[field.PARENT_REGISTER_METADATA_KEY]["relations"]
    return next(item for item in relations if item["parent_path"] == "L" and item["child_path"] == "LL")


def _route(origin: field.ResonantWorkspace, *, parent_enabled: bool, work_budget: float) -> tuple[dict[str, Any], field.ResonantWorkspace]:
    child_packet = field.analyze_helical_packet(origin, path="LL")
    relation = _relation(origin)
    parent_before = field.analyze_helical_packet(origin, path="L")
    successor, receipt = field.apply_live_child_detail_to_parent(
        origin,
        work_budget=work_budget,
        parent_enabled=parent_enabled,
        expected_child_source_state_sha256=origin.state_sha256,
        expected_child_packet_sha256=str(child_packet["packet_sha256"]),
        expected_relation_sha256=str(relation["relation_sha256"]),
    )
    parent_after = field.analyze_helical_packet(successor, path="L")
    return {
        "parent_enabled": parent_enabled,
        "initial_state_sha256": origin.state_sha256,
        "initial_page_sha256": _page(origin),
        "final_state_sha256": successor.state_sha256,
        "final_page_sha256": _page(successor),
        "child_packet_sha256": child_packet["packet_sha256"],
        "relation_sha256": relation["relation_sha256"],
        "parent_before_coefficients": np.asarray(parent_before["coefficients"], dtype=np.float64).tolist(),
        "parent_after_coefficients": np.asarray(parent_after["coefficients"], dtype=np.float64).tolist(),
        "parent_summary_delta_norm": _norm(parent_before["coefficients"][0], parent_after["coefficients"][0]),
        "child_register_preserved": field.read_parent_register(successor, "L")["values"] == field.read_parent_register(origin, "L")["values"],
        "application": receipt,
    }, successor


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    continuity = parent_runner.build_receipt()
    origin = field.initial_workspace(field.ResonantProfile())
    seeded, seed_receipt = field.apply_helical_packet_impulse(
        origin, path="LL", component="scale", flow_signal=(1.0, 0.0),
        work_budget=parent_runner.FIRST_BUDGET, evidence_tick=origin.evidence_tick,
        event_kind="reasoning-work",
    )
    captured, capture_receipt = field.write_parent_registers(
        seeded, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, freeze_receipt = field.freeze_parent(captured)
    frozen_read = field.read_frozen_parent(frozen)
    locked = _error(
        lambda: field.apply_live_child_detail_to_parent(
            frozen, work_budget=FEEDBACK_BUDGET,
            expected_child_source_state_sha256=frozen.state_sha256,
            expected_relation_sha256=frozen_read["relation_sha256"],
        ),
        "locked while a frozen parent is active",
    )
    released, release_receipt = field.release_frozen_parent(
        frozen, freeze_id=str(frozen_read["freeze_id"])
    )
    child_state, child_impulse = field.apply_helical_packet_impulse(
        released, path="LL", component="detail", flow_signal=DETAIL_SIGNAL,
        work_budget=DETAIL_BUDGET, evidence_tick=released.evidence_tick,
        event_kind="reasoning-work",
    )
    child_packet = field.analyze_helical_packet(child_state, path="LL")
    relation = _relation(child_state)
    on, on_state = _route(child_state, parent_enabled=True, work_budget=FEEDBACK_BUDGET)
    off, off_state = _route(child_state, parent_enabled=False, work_budget=FEEDBACK_BUDGET)
    noop, noop_state = _route(child_state, parent_enabled=True, work_budget=0.0)
    after_child_packet = field.analyze_helical_packet(on_state, path="LL")
    recomputed, recompute_receipt = field.recompute_parent_summary_from_child(
        on_state,
        expected_source_state_sha256=on_state.state_sha256,
        expected_relation_sha256=str(relation["relation_sha256"]),
        expected_child_packet_sha256=str(after_child_packet["packet_sha256"]),
    )
    live_parent = field.analyze_helical_packet(on_state, path="L")
    stored_parent = field.read_parent_register(recomputed, "L")
    tampered = copy.deepcopy(child_state.as_dict())
    tampered_transition = dict(tampered["layout_transition"])
    tampered_register = dict(tampered_transition[field.PARENT_REGISTER_METADATA_KEY])
    tampered_relations = [dict(item) for item in tampered_register["relations"]]
    tampered_relations[0]["relation_sha256"] = "0" * 64
    tampered_register["relations"] = tampered_relations
    tampered_transition[field.PARENT_REGISTER_METADATA_KEY] = tampered_register
    tampered["layout_transition"] = tampered_transition
    tampered_control = _error(
        lambda: field.ResonantWorkspace.from_dict(tampered), "relation digest mismatch"
    )
    stale_source = _error(
        lambda: field.apply_live_child_detail_to_parent(
            child_state, work_budget=FEEDBACK_BUDGET,
            expected_child_source_state_sha256="0" * 64,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256=str(relation["relation_sha256"]),
        ), "child detail source state digest is stale"
    )
    stale_packet = _error(
        lambda: field.apply_live_child_detail_to_parent(
            child_state, work_budget=FEEDBACK_BUDGET,
            expected_child_source_state_sha256=child_state.state_sha256,
            expected_child_packet_sha256="0" * 64,
            expected_relation_sha256=str(relation["relation_sha256"]),
        ), "child detail packet digest is stale"
    )
    stale_relation = _error(
        lambda: field.apply_live_child_detail_to_parent(
            child_state, work_budget=FEEDBACK_BUDGET,
            expected_child_source_state_sha256=child_state.state_sha256,
            expected_child_packet_sha256=str(child_packet["packet_sha256"]),
            expected_relation_sha256="0" * 64,
        ), "child detail relation digest is stale"
    )
    owner_receipt: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="cassifi-child-detail-owner-") as directory:
        owner = FieldIntelligenceOwner(Path(directory), initial_state=AtlasState(resonant_workspace=child_state))
        try:
            owner_packet = field.analyze_helical_packet(owner.state.resonant_workspace, path="LL")
            owner_relation = _relation(owner.state.resonant_workspace)
            owner_result = owner.apply_live_child_detail_to_parent(
                "owner:child-detail-to-parent", work_budget=FEEDBACK_BUDGET,
                expected_child_source_state_sha256=owner.state.resonant_workspace.state_sha256,
                expected_child_packet_sha256=str(owner_packet["packet_sha256"]),
                expected_relation_sha256=str(owner_relation["relation_sha256"]),
            )
            owner_manifest = owner.checkpoints.current_manifest_sha256
            reloaded = owner.checkpoints.load_version(owner_manifest)
            replay = owner.apply_live_child_detail_to_parent(
                "owner:child-detail-to-parent", work_budget=FEEDBACK_BUDGET,
                expected_child_source_state_sha256=child_state.state_sha256,
                expected_child_packet_sha256=str(owner_packet["packet_sha256"]),
                expected_relation_sha256=str(owner_relation["relation_sha256"]),
            )
            owner_receipt = {
                "result": owner_result,
                "reloaded_state_sha256": reloaded.state_sha256,
                "current_state_sha256": owner.state.state_sha256,
                "replay": replay,
                "replay_same_state": replay["live_child_detail_receipt"]["state_sha256"] == owner_result["live_child_detail_receipt"]["state_sha256"],
            }
        finally:
            owner.close()
    comparisons = [
        {"id": "parent_on_changes_parent_summary", "quantity": on["parent_summary_delta_norm"], "holds": on["parent_summary_delta_norm"] > MARGIN, "margin": MARGIN},
        {"id": "parent_off_is_silenced", "quantity": off["parent_summary_delta_norm"], "holds": off_state.state_sha256 == child_state.state_sha256, "margin": 0.0},
        {"id": "zero_work_is_identity", "quantity": float(noop_state.state_sha256 == child_state.state_sha256), "holds": noop_state.state_sha256 == child_state.state_sha256, "margin": 0.0},
        {"id": "child_register_preserved_until_explicit_recompute", "quantity": float(on["child_register_preserved"]), "holds": on["child_register_preserved"], "margin": 0.0},
        {"id": "recompute_matches_live_parent", "quantity": _norm(stored_parent["values"], live_parent["coefficients"][0]), "holds": _norm(stored_parent["values"], live_parent["coefficients"][0]) <= MARGIN, "margin": MARGIN},
        {"id": "impulse_work_balance", "quantity": abs(float(on["application"]["applied_work"]) - FEEDBACK_BUDGET), "holds": abs(float(on["application"]["applied_work"]) - FEEDBACK_BUDGET) <= float(on["application"]["energy_roundoff_allowance"]), "margin": float(on["application"]["energy_roundoff_allowance"])},
        {"id": "frozen_parent_lock_rejected", "quantity": float(locked["can_fail"]), "holds": locked["can_fail"], "margin": 0.0},
        {"id": "stale_source_rejected", "quantity": float(stale_source["can_fail"]), "holds": stale_source["can_fail"], "margin": 0.0},
        {"id": "stale_packet_rejected", "quantity": float(stale_packet["can_fail"]), "holds": stale_packet["can_fail"], "margin": 0.0},
        {"id": "stale_relation_rejected", "quantity": float(stale_relation["can_fail"]), "holds": stale_relation["can_fail"], "margin": 0.0},
        {"id": "tampered_relation_identity_rejected", "quantity": float(tampered_control["can_fail"]), "holds": tampered_control["can_fail"], "margin": 0.0},
        {"id": "owner_checkpoint_reload_replay", "quantity": float(owner_receipt["replay_same_state"] and owner_receipt["reloaded_state_sha256"] == owner_receipt["current_state_sha256"]), "holds": owner_receipt["replay_same_state"] and owner_receipt["reloaded_state_sha256"] == owner_receipt["current_state_sha256"], "margin": 0.0},
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "semantic_memory_claim": False,
            "parent_path": "L",
            "child_path": "LL",
            "restriction": "LL top Haar detail momentum channels [momentum-common,momentum-counterflow] -> native L scale flow signal",
            "feedback_budget": FEEDBACK_BUDGET,
            "detail_budget": DETAIL_BUDGET,
            "lr_isolation": "downward arm only; upward L support overlaps LR",
        },
        "continuity": {"parent_receipt_digest": continuity["content_digest"], "parent_verdict": continuity["verdict"]},
        "seed": seed_receipt,
        "capture": capture_receipt,
        "freeze": freeze_receipt,
        "release": release_receipt,
        "child_detail": {"impulse": child_impulse, "packet": child_packet},
        "arms": {"parent-on": on, "parent-off": off, "zero-work": {"application": noop}},
        "recompute": recompute_receipt,
        "controls": {"frozen_lock": locked, "stale_source": stale_source, "stale_packet": stale_packet, "stale_relation": stale_relation, "tampered_relation": tampered_control, "owner": owner_receipt},
        "comparisons": comparisons,
        "runtime_seconds": float(perf_counter() - started),
    }
    body["verdict"] = "PASS_FIELD_OWNED_LIVE_CHILD_DETAIL_TO_PARENT" if all(row["holds"] for row in comparisons) else "FAIL_LIVE_CHILD_DETAIL_TO_PARENT"
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
