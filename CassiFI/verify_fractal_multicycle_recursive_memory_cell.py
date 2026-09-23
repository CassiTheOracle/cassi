"""Independent verifier for the bounded multicycle recurrence receipt.

This module deliberately imports neither the runner nor CassiFI implementation
modules.  It treats the JSON receipt as the artifact, rebuilds all published
norms/ratios from receipt rows, and checks the control/verdict logic.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.fractal-multicycle-recursive-memory-cell.v1"
DEFAULT_RECEIPT = Path("_diag/fractal-multicycle-recursive-memory-cell/exploration.json")
MARGIN = 1e-12
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_sha256"})


def _strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _strip_timing(v) for k, v in value.items() if k not in TIMING_KEYS}
    if isinstance(value, list):
        return [_strip_timing(v) for v in value]
    return value


def _canonical(value: Any) -> str:
    return json.dumps(_strip_timing(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _norm(left: Any, right: Any) -> float:
    a = [float(x) for x in left]
    b = [float(x) for x in right]
    if len(a) != len(b):
        raise ValueError("norm operands have different lengths")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _nested_norm(left: Any, right: Any) -> float:
    if isinstance(left, list) and left and isinstance(left[0], list):
        return math.sqrt(sum((_nested_norm(x, y) ** 2 for x, y in zip(left, right))))
    return _norm(left, right)


def _close(actual: float, expected: float, allowance: float = 1e-12) -> bool:
    return math.isfinite(actual) and math.isfinite(expected) and abs(actual - expected) <= allowance * max(1.0, abs(actual), abs(expected))


def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if receipt.get("schema") != SCHEMA:
        errors.append("schema mismatch")
    digest = content_digest(receipt)
    if digest != receipt.get("content_digest") or receipt.get("receipt_sha256") != receipt.get("content_digest"):
        errors.append("content digest mismatch")
    arms = receipt.get("arms", {})
    try:
        full = arms["feedback-on"]
        off = arms["feedback-off"]
        parent_off = arms["parent-off"]
        zero = arms["zero-work"]
        for name, arm in (("feedback-on", full), ("feedback-off", off), ("parent-off", parent_off), ("zero-work", zero)):
            if len(arm["cycles"]) != 3:
                errors.append(f"{name} does not contain exactly three bounded children")
            if len(arm["child_packet_coefficients"]) != 3:
                errors.append(f"{name} packet row count mismatch")
        if not (full["upward_enabled"] and off["upward_enabled"] is False and full["parent_enabled"] and off["parent_enabled"]):
            errors.append("matched arm mode is not [on,on] versus [off,off] with parent enabled")
        for arm in (full, off):
            for row in arm["cycles"]:
                if row["downward"]["component"] != "detail" or row["downward"]["child_path"] != "LL":
                    errors.append(f"{arm['name']} downward route is not LL detail")
    except (KeyError, TypeError):
        errors.append("arm map is incomplete")
        return {"status": "failed", "errors": errors, "digest": digest}

    contrast = receipt.get("later_child_contrast", {})
    packet_delta = _nested_norm(full["final_packet_coefficients"], off["final_packet_coefficients"])
    flow_delta = _norm(full["final_flow_signal"], off["final_flow_signal"])
    field_delta = _nested_norm(full["final_field_vector"], off["final_field_vector"])
    off_packet_norm = _nested_norm(off["final_packet_coefficients"], [[0.0] * len(off["final_packet_coefficients"][0])] * len(off["final_packet_coefficients"]))
    persistence = packet_delta / max(off_packet_norm, MARGIN)
    selectivity = max(
        float(row["sibling_delta_norm"])
        for arm in (full, off, parent_off, zero)
        for row in arm["cycles"]
    )
    expected_aggregates = {
        "field_state_delta_norm": field_delta,
        "effective_flow_delta_norm": flow_delta,
        "packet_delta_norm": packet_delta,
        "persistence_ratio": persistence,
        "selectivity_ratio": selectivity,
    }
    for key, value in expected_aggregates.items():
        if not _close(float(contrast.get(key, float("nan"))), value):
            errors.append(f"aggregate drift: {key}")

    if full["child_state_sha256s"][0] != off["child_state_sha256s"][0]:
        errors.append("matched arms diverge before prior upward feedback")
    if full["child_state_sha256s"][2] == off["child_state_sha256s"][2]:
        errors.append("terminal child does not carry arm divergence")
    if not (field_delta > MARGIN and flow_delta > MARGIN and packet_delta > MARGIN):
        errors.append("primary later-child observable is below margin")
    if not (persistence > MARGIN and selectivity <= MARGIN):
        errors.append("persistence/selectivity predicate failed")

    for arm in (full, off, parent_off):
        for row in arm["cycles"]:
            if row["downward_target_packet_delta_norm"] <= MARGIN or row["downward_target_field_state_delta_norm"] <= MARGIN:
                errors.append(f"nonzero downward LL target did not move in {arm['name']}")
    for row in zero["cycles"]:
        if row["downward_target_packet_delta_norm"] != 0.0 or row["downward_target_field_state_delta_norm"] != 0.0:
            errors.append("zero-work downward target is not identity")

    for arm in (full, off, parent_off, zero):
        for row in arm["cycles"][:-1]:
            if not row["parent_register_preserved_before_materialize"]:
                errors.append(f"register was not preserved before materialization in {arm['name']}")
            if row["downward_target_packet_delta_norm"] <= MARGIN and arm is not zero:
                errors.append(f"nonzero downward LL target did not move in {arm['name']}")
            if row["downward_target_field_state_delta_norm"] <= MARGIN and arm is not zero:
                errors.append(f"nonzero downward field did not move in {arm['name']}")
            if arm is zero and (row["downward_target_packet_delta_norm"] != 0.0 or row["downward_target_field_state_delta_norm"] != 0.0):
                errors.append("zero-work downward target is not identity")
            if row["cycle"] < 3:
                upward = row["upward"]
                if arm is full:
                    if not upward.get("accepted") or not upward.get("parent_enabled"):
                        errors.append("feedback-on upward hop was not accepted")
                    if upward.get("child_source_state_sha256") != row["release"].get("state_sha256"):
                        errors.append("upward source digest is not the released child")
                    if upward.get("child_packet_sha256") != row["child_packet_sha256"]:
                        errors.append("upward packet digest is not the released child packet")
                    if upward.get("relation_sha256") != row["downward"].get("relation_sha256"):
                        errors.append("upward relation digest is stale")
                if arm is off and (upward.get("attempted") or upward.get("applied_work") != 0.0):
                    errors.append("feedback-off arm attempted an upward hop")
            if not row["release"].get("released"):
                errors.append(f"missing release in {arm['name']}")
            if row["materialize"].get("schema") != "cassifi.parent-child-summary-recompute.v1":
                errors.append(f"missing explicit materialization in {arm['name']}")
            if not row["freeze_after"].get("accepted"):
                errors.append(f"missing refreeze in {arm['name']}")

    for arm in (full, off, parent_off, zero):
        if not arm["cycles"][-1]["release"].get("released"):
            errors.append(f"terminal child was not released in {arm['name']}")
    comparisons = receipt.get("comparisons", [])
    required_ids = {
        "later_child_field_state_diverges",
        "later_child_flow_diverges",
        "later_child_packet_diverges",
        "feedback_persists_to_late_child",
        "feedback_is_selective_to_LL",
        "all_feedback_on_off_downward_LL_targets_diverge",
        "all_zero_work_downward_targets_are_identity",
        "all_nonterminal_registers_preserved_before_materialize",
        "zero_work_is_identity",
        "standalone_upward_zero_work_is_identity",
        "immutable_workspace_roundtrip",
        "source_off_has_zero_positive_heartbeat",
        "stale_source_rejected",
        "stale_packet_rejected",
        "stale_relation_rejected",
        "frozen_parent_lock_rejected",
        "mutated_persistence_selectivity_fails",
        "prior_receipt_continuity",
    }
    if {row.get("id") for row in comparisons} != required_ids or not all(bool(row.get("holds")) for row in comparisons):
        errors.append("published comparison table is not fully passing")
    controls = receipt.get("controls", {})
    for key in (
        "zero_work_identity", "zero_work_downward_target", "standalone_upward_zero_work",
        "source_off_heartbeat", "sibling_isolation", "immutable_roundtrip",
        "stale_source", "stale_packet", "stale_relation", "frozen_parent_lock",
        "persistence_selectivity_mutation",
    ):
        if not controls.get(key, {}).get("can_fail"):
            errors.append(f"control cannot fail: {key}")
    mutation = controls.get("persistence_selectivity_mutation", {})
    observed = mutation.get("observed", {})
    mutated = mutation.get("mutated", {})
    observed_holds = float(observed.get("persistence_ratio", 0.0)) > MARGIN and float(observed.get("selectivity_ratio", float("inf"))) <= MARGIN
    mutated_holds = float(mutated.get("persistence_ratio", 0.0)) > MARGIN and float(mutated.get("selectivity_ratio", float("inf"))) <= MARGIN
    if not observed_holds or mutated_holds or not mutation.get("mutated_holds") is False:
        errors.append("persistence/selectivity mutation did not fire")

    continuity = receipt.get("continuity", {})
    cited = continuity.get("cited_numbers", {})
    reproduced = continuity.get("reproduced_numbers", {})
    for cited_key, reproduced_key in (("prior_full_first_applied_work", "current_full_first_applied_work"), ("prior_parent_off_first_applied_work", "current_parent_off_first_applied_work")):
        if not _close(float(cited.get(cited_key, float("nan"))), float(reproduced.get(reproduced_key, float("nan")))):
            errors.append(f"continuity mismatch: {cited_key}")

    verdict = receipt.get("verdict", "")
    if not verdict.startswith("PASS_"):
        errors.append("receipt verdict is not PASS")
    status = "verified" if not errors else "failed"
    return {"status": status, "errors": errors, "digest": digest, "verdict": verdict, "recomputed": expected_aggregates}


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args(argv)
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
