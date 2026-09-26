"""Independent verifier for the temporal/evidence action-selection receipt.

This module deliberately imports neither the runner nor CassiFI implementation
modules.  It checks the receipt's digest, reconstructs the selection,
permutation, abstention, consequence, and control predicates from rows, and
fires those predicates against mutated in-memory anchors.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "cassifi.temporal-evidence-action-selection.v1"
MINIMUM_MARGIN = 1e-12
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if str(key) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(item) for item in value]
    return value


def digest(receipt: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(receipt)).encode("utf-8")).hexdigest()


def _selected(row: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = row.get("selection", {}).get("selected")
    return value if isinstance(value, Mapping) else None


def _consequence_correct(row: Mapping[str, Any]) -> bool:
    consequence = row.get("consequence")
    if not isinstance(consequence, Mapping):
        return False
    transition = consequence.get("transition")
    receipt = transition.get("receipt") if isinstance(transition, Mapping) else None
    if not isinstance(receipt, Mapping):
        return False
    action = consequence.get("action_applied")
    observation = consequence.get("observation")
    expected = consequence.get("expected_goal_observation")
    return (
        consequence.get("selected_action") == action
        and observation == expected
        and bool(consequence.get("goal_progress"))
        and not bool(consequence.get("forbidden_outcome"))
        and bool(consequence.get("correct_first_transition"))
        and receipt.get("action") == action
        and receipt.get("observation") == observation
        and transition.get("action") == action
        and transition.get("observation") == observation
        and transition.get("before_state_sha256") != transition.get("after_state_sha256")
    )


def _selected_candidate(row: Mapping[str, Any]) -> bool:
    selection = row.get("selection")
    selected = _selected(row)
    candidates = selection.get("candidates", []) if isinstance(selection, Mapping) else []
    if selected is None or not isinstance(candidates, list):
        return False
    return any(
        isinstance(candidate, Mapping)
        and candidate.get("candidate_sha256") == selected.get("candidate_sha256")
        and candidate.get("skill_id") == selected.get("skill_id")
        and candidate.get("action") == selected.get("action")
        for candidate in candidates
    )


def predicates(receipt: Mapping[str, Any]) -> dict[str, bool]:
    rows = receipt.get("rows")
    if not isinstance(rows, list) or len(rows) != 6:
        return {"shape": False}
    by_name = {row.get("name"): row for row in rows if isinstance(row, Mapping)}
    supported = by_name.get("held-out-supported", {})
    reversed_row = by_name.get("held-out-supported-reversed", {})
    no_field = by_name.get("control-no-workspace", {})
    insufficient = by_name.get("control-insufficient-margin", {})
    forbidden = by_name.get("control-forbidden-operation", {})
    wrong = by_name.get("control-wrong-consequence", {})
    ssel, rsel = _selected(supported), _selected(reversed_row)
    s_margin = supported.get("selection", {}).get("selection_margin")
    minimum = supported.get("minimum_margin", MINIMUM_MARGIN)
    supported_selection = (
        supported.get("selection", {}).get("status") == "selected"
        and supported.get("selection", {}).get("reason") == "resonant-compatibility"
        and isinstance(s_margin, (int, float)) and float(s_margin) > float(minimum)
        and _selected_candidate(supported)
        and isinstance(supported.get("field_setup"), Mapping)
        and bool(supported["field_setup"].get("available"))
        and bool(supported.get("selection", {}).get("read_only"))
        and bool(supported.get("selection", {}).get("memory_unchanged"))
        and bool(supported.get("selection", {}).get("workspace_unchanged"))
    )
    permutation = (
        ssel is not None and rsel is not None
        and dict(ssel) == dict(rsel)
        and supported.get("selection", {}).get("candidate_set_sha256") == reversed_row.get("selection", {}).get("candidate_set_sha256")
        and supported.get("presentation_order_sha256") != reversed_row.get("presentation_order_sha256")
    )
    no_usable = (
        no_field.get("selection", {}).get("status") == "unresolved"
        and no_field.get("selection", {}).get("reason") == "resonant-workspace-unavailable"
        and _selected(no_field) is None and no_field.get("consequence") is None
        and no_field.get("field_setup", {}).get("available") is False
    )
    margin_abstain = (
        insufficient.get("selection", {}).get("status") == "unresolved"
        and insufficient.get("selection", {}).get("reason") == "insufficient-resonant-margin"
        and _selected(insufficient) is None
        and float(insufficient.get("minimum_margin", 0.0)) > MINIMUM_MARGIN
        and insufficient.get("consequence") is None
    )
    forbidden_abstain = (
        forbidden.get("selection", {}).get("status") == "unresolved"
        and forbidden.get("selection", {}).get("reason") in {"no-admissible-candidate", "resonant-workspace-unavailable"}
        and _selected(forbidden) is None and forbidden.get("consequence") is None
        and all(not bool(op.get("authorized")) or bool(op.get("represented_forbidden")) or not bool(op.get("feasible"))
                for op in forbidden.get("operations", []) if isinstance(op, Mapping))
    )
    wrong_consequence = wrong.get("consequence")
    wrong_failed = (
        isinstance(wrong_consequence, Mapping)
        and wrong_consequence.get("selected_action") != wrong_consequence.get("action_applied")
        and wrong_consequence.get("observation") != wrong_consequence.get("expected_goal_observation")
        and not bool(wrong_consequence.get("correct_first_transition"))
    )
    return {
        "shape": True,
        "field_supported_selection": bool(supported_selection),
        "held_out_consequence": bool(supported_selection and _consequence_correct(supported)),
        "presentation_order_invariant": bool(permutation),
        "no_workspace_abstains": bool(no_usable),
        "insufficient_margin_abstains": bool(margin_abstain),
        "forbidden_operation_abstains": bool(forbidden_abstain),
        "wrong_action_consequence_fails": bool(wrong_failed),
    }


def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    declared = str(receipt.get("content_digest", ""))
    actual = digest(receipt)
    checks = predicates(receipt)
    checks["schema"] = receipt.get("schema") == SCHEMA
    checks["digest"] = bool(declared) and declared == actual and receipt.get("receipt_digest") == declared
    checks["evaluation_matches"] = all(receipt.get("evaluation", {}).get(key) is value for key, value in checks.items() if key in receipt.get("evaluation", {}))
    mutated = copy.deepcopy(receipt)
    try:
        mutated["rows"][0]["selection"]["selected"]["action"] = "mutated-action"
    except (KeyError, IndexError, TypeError):
        pass
    checks["mutation_anchor_fires"] = not predicates(mutated).get("field_supported_selection", False)
    wrong_goal_mutated = copy.deepcopy(receipt)
    try:
        wrong_consequence = wrong_goal_mutated["rows"][5]["consequence"]
        wrong_consequence["expected_goal_observation"] = wrong_consequence["observation"]
    except (KeyError, IndexError, TypeError):
        pass
    checks["wrong_goal_anchor_fires"] = not predicates(wrong_goal_mutated).get("wrong_action_consequence_fails", False)
    checks["control_anchors_fire"] = all(checks.get(key, False) for key in ("no_workspace_abstains", "insufficient_margin_abstains", "forbidden_operation_abstains", "wrong_action_consequence_fails"))
    checks["status"] = receipt.get("status") == "MEASURED"
    checks["verified"] = all(bool(value) for key, value in checks.items() if key not in {"verified"})
    return {"status": "verified" if checks["verified"] else "failed", "content_digest": actual, "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, default=Path("_diag/temporal-evidence-action-selection/exploration.json"))
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = verify(receipt)
    print(json.dumps(result, sort_keys=True))
    if result["status"] != "verified":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
