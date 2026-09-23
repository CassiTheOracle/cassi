"""Measure field-owned frozen L parent application into later LL evolution."""
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
from cassi_field_atlas import AtlasState
from cassi_field_owner import FieldIntelligenceError, FieldIntelligenceOwner

SCHEMA = "cassifi.fractal-parent-summary-application-exploration.v1"
DEFAULT_OUTPUT = Path("_diag/fractal-parent-summary-application/exploration.json")
BASE_SIGNAL = (0.0, 1.0)
FIRST_SIGNAL = (1.0, 0.0)
FIRST_BUDGET = 1e-3
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

def _error(call: Any, expected: str) -> dict[str, Any]:
    expected_error_type = field.ResonantNumericalError.__name__
    try:
        call()
    except Exception as exc:
        error_type = type(exc).__name__
        error = str(exc)
        error_type_matches = error_type == expected_error_type
        error_message_matches = expected in error
        return {
            "attempted": True,
            "accepted": False,
            "can_fail": error_type_matches and error_message_matches,
            "expected": expected,
            "error_type": error_type,
            "error": error,
            "error_type_matches": error_type_matches,
            "error_message_matches": error_message_matches,
        }
    return {
        "attempted": True,
        "accepted": True,
        "can_fail": False,
        "expected": expected,
        "error_type": None,
        "error": None,
        "error_type_matches": False,
        "error_message_matches": False,
    }

def _arm(origin: field.ResonantWorkspace, *, parent_enabled: bool) -> tuple[dict[str, Any], field.ResonantWorkspace]:
    before = field.read_frozen_parent(origin)
    sibling_before = field.analyze_helical_packet(origin, path="LR")
    post, receipt = field.apply_frozen_parent_to_child(
        origin,
        freeze_id=str(before["freeze_id"]),
        base_flow_signal=BASE_SIGNAL,
        work_budget=CHILD_BUDGET,
        parent_enabled=parent_enabled,
        expected_parent_summary_sha256=str(before["summary_sha256"]),
        expected_parent_source_state_sha256=str(before["source_state_sha256"]),
        expected_relation_sha256=str(before["relation_sha256"]),
        expected_child_source_state_sha256=origin.state_sha256,
    )
    sibling_after = field.analyze_helical_packet(post, path="LR")
    after = field.read_frozen_parent(post)
    row = {
        "parent_enabled": parent_enabled,
        "initial_state_sha256": origin.state_sha256,
        "initial_page_sha256": _page(origin),
        "final_state_sha256": post.state_sha256,
        "final_page_sha256": _page(post),
        "before_parent": before,
        "after_parent": after,
        "sibling_path": "LR",
        "sibling_before_coefficients": np.asarray(sibling_before["coefficients"], dtype=np.float64).reshape(-1).tolist(),
        "sibling_after_coefficients": np.asarray(sibling_after["coefficients"], dtype=np.float64).reshape(-1).tolist(),
        "sibling_delta_norm": _norm(sibling_before["coefficients"], sibling_after["coefficients"]),
        "application": receipt,
    }
    return row, post


def build_receipt() -> dict[str, Any]:
    started = perf_counter()
    origin = field.initial_workspace(field.ResonantProfile())
    first, first_impulse = field.apply_helical_packet_impulse(
        origin, path="LL", component="scale", flow_signal=FIRST_SIGNAL,
        work_budget=FIRST_BUDGET, evidence_tick=origin.evidence_tick,
        event_kind="reasoning-work",
    )
    captured, capture = field.write_parent_registers(
        first, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, freeze = field.freeze_parent(captured)
    frozen_read = field.read_frozen_parent(frozen)
    source_off, source_off_receipt = field.advance_workspace(
        frozen, ticks=SOURCE_OFF_TICKS, demand=0.0, source_enabled=False
    )
    on, on_final = _arm(source_off, parent_enabled=True)
    off, off_final = _arm(source_off, parent_enabled=False)
    noop, noop_receipt = field.apply_frozen_parent_to_child(
        source_off,
        freeze_id=str(frozen_read["freeze_id"]), base_flow_signal=BASE_SIGNAL,
        work_budget=0.0, parent_enabled=True,
        expected_parent_summary_sha256=str(frozen_read["summary_sha256"]),
        expected_parent_source_state_sha256=str(frozen_read["source_state_sha256"]),
        expected_relation_sha256=str(frozen_read["relation_sha256"]),
        expected_child_source_state_sha256=source_off.state_sha256,
    )
    stale_parent = _error(
        lambda: field.apply_frozen_parent_to_child(
            source_off, freeze_id=str(frozen_read["freeze_id"]),
            base_flow_signal=BASE_SIGNAL, work_budget=CHILD_BUDGET,
            expected_parent_source_state_sha256="0" * 64,
        ),
        "frozen parent source digest",
    )
    locked_recompute = _error(
        lambda: field.recompute_parent_summary_from_child(source_off),
        "parent recompute is locked",
    )
    tampered = copy.deepcopy(frozen.as_dict())
    tampered_transition = dict(tampered["layout_transition"])
    tampered_descriptor = dict(tampered_transition["frozen_parent"])
    tampered_descriptor["freeze_id"] = "0" * 64
    tampered_transition["frozen_parent"] = tampered_descriptor
    tampered["layout_transition"] = tampered_transition
    tampered_control = _error(
        lambda: field.ResonantWorkspace.from_dict(tampered),
        "frozen parent identity digest mismatch",
    )
    owner_receipt: dict[str, Any]
    with tempfile.TemporaryDirectory(prefix="cassifi-frozen-parent-owner-") as directory:
        owner = FieldIntelligenceOwner(
            Path(directory),
            initial_state=AtlasState(resonant_workspace=frozen),
        )
        try:
            owner_read = owner.read_frozen_parent()
            owner_freeze = owner.freeze_parent("owner:freeze")
            owner_advance = owner.advance("owner:source-off", source_enabled=False)
            owner_apply = owner.apply_frozen_parent_to_child(
                "owner:apply",
                freeze_id=str(owner_read["freeze_id"]),
                base_flow_signal=BASE_SIGNAL,
                work_budget=CHILD_BUDGET,
            )
            owner_receipt = {
                "read": owner_read,
                "freeze": owner_freeze,
                "advance": owner_advance,
                "apply": owner_apply,
                "read_state": owner.state.state_sha256,
            }
        finally:
            owner.close()
    comparisons = [
        {
            "id": "parent_on_changes_child_relative_to_parent_off",
            "quantity": float(on["application"]["impulse"]["applied_work"]),
            "child_state_distinct": on_final.state_sha256 != off_final.state_sha256,
            "holds": on_final.state_sha256 != off_final.state_sha256,
            "margin": MARGIN,
        },
        {
            "id": "frozen_parent_values_survive_parent_on",
            "quantity": _norm(on["before_parent"]["values"], on["after_parent"]["values"]),
            "holds": _norm(on["before_parent"]["values"], on["after_parent"]["values"]) <= MARGIN,
            "margin": MARGIN,
        },
        {
            "id": "frozen_parent_values_survive_parent_off",
            "quantity": _norm(off["before_parent"]["values"], off["after_parent"]["values"]),
            "holds": _norm(off["before_parent"]["values"], off["after_parent"]["values"]) <= MARGIN,
            "margin": MARGIN,
        },
        {
            "id": "zero_work_is_identity",
            "quantity": float(noop.state_sha256 == source_off.state_sha256),
            "holds": noop.state_sha256 == source_off.state_sha256,
            "margin": 0.0,
        },
        {
            "id": "source_off_has_zero_heartbeat_work",
            "quantity": float(source_off_receipt["positive_heartbeat_work"]),
            "holds": not source_off_receipt["source_enabled"] and source_off_receipt["positive_heartbeat_work"] == 0.0,
            "margin": 0.0,
        },
        {
            "id": "sibling_LR_isolation",
            "quantity": max(on["sibling_delta_norm"], off["sibling_delta_norm"]),
            "holds": max(on["sibling_delta_norm"], off["sibling_delta_norm"]) <= MARGIN,
            "margin": MARGIN,
        },
        {
            "id": "stale_parent_rejected",
            "quantity": float(stale_parent["can_fail"]),
            "holds": stale_parent["can_fail"],
            "margin": 0.0,
        },
        {
            "id": "live_recompute_locked",
            "quantity": float(locked_recompute["can_fail"]),
            "holds": locked_recompute["can_fail"],
            "margin": 0.0,
        },
        {
            "id": "tampered_provenance_rejected",
            "quantity": float(tampered_control["can_fail"]),
            "holds": tampered_control["can_fail"],
            "margin": 0.0,
        },
    ]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "declared": {
            "field_only": True,
            "semantic_memory_claim": False,
            "hierarchy_claim": False,
            "parent_path": "L",
            "child_path": "LL",
            "prolongation": "native L level-zero momentum common/counterflow values[2:4] as LL flow_signal",
            "coupling_gain": field.FROZEN_PARENT_COUPLING_GAIN,
            "arm_matrix": ["parent-on", "parent-off", "zero-work-noop"],
        },
        "capture": capture,
        "freeze": freeze,
        "frozen_parent": frozen_read,
        "first_impulse": first_impulse,
        "source_off": source_off_receipt,
        "arms": {"parent-on": on, "parent-off": off},
        "zero_work": {"receipt": noop_receipt, "state_unchanged": noop.state_sha256 == source_off.state_sha256},
        "controls": {
            "stale_parent": stale_parent,
            "locked_recompute": locked_recompute,
            "tampered_provenance": tampered_control,
            "owner": owner_receipt,
        },
        "comparisons": comparisons,
        "runtime_seconds": float(perf_counter() - started),
    }
    body["verdict"] = "PASS_FIELD_OWNED_FROZEN_PARENT_APPLICATION" if all(row["holds"] for row in comparisons) else "FAIL_FROZEN_PARENT_APPLICATION"
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
