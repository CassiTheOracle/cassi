"""Independent verifier for the cue-conditioned field-action receipt.

This module intentionally imports neither the runner nor CassiFI field
implementation.  It rebuilds selection and protocol decisions from receipt
rows and checks the receipt's declared digest rule.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

DEFAULT_RECEIPT = Path("_diag/cue-conditioned-field-action/exploration.json")
SCHEMA = "cassifi.cue-conditioned-field-action.v1"
CUES = ("root-scale", "root-detail", "left-detail", "right-detail")
SCORE_FLOOR = 1e-12
MARGIN_FLOOR = 1e-12
MAPPING = {"root-scale": "left-detail", "root-detail": "right-detail", "left-detail": "root-scale", "right-detail": "root-detail"}


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_keys(value: Any, keys: set[str]) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_keys(item, keys) for key, item in value.items() if str(key) not in keys}
    if isinstance(value, list):
        return [strip_keys(item, keys) for item in value]
    return value


def digest(receipt: Mapping[str, Any]) -> str:
    rule = receipt.get("digest_rule", {})
    keys = {str(key) for key in rule.get("strip_keys", [])}
    body = strip_keys(receipt, keys)
    return hashlib.sha256(canonical(body).encode("utf-8")).hexdigest()


def select(scores: Mapping[str, Any], digests: Mapping[str, Any]) -> list[str]:
    ranked = [name for name, _ in sorted(scores.items(), key=lambda pair: (-float(pair[1]), str(digests[pair[0]])))]
    candidate = ranked[:2]
    selected_min = min((float(scores[name]) for name in candidate), default=0.0)
    unselected_max = max((float(scores[name]) for name in ranked[2:]), default=0.0)
    margin = selected_min - unselected_max
    return candidate if len(candidate) == 2 and selected_min >= SCORE_FLOOR and margin > MARGIN_FLOOR else []

def _row(rows: list[Mapping[str, Any]], name: str) -> Mapping[str, Any]:
    matches = [row for row in rows if row.get("name") == name]
    if len(matches) != 1:
        raise AssertionError(f"expected one episode named {name!r}")
    return matches[0]


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def verify(receipt: Mapping[str, Any]) -> dict[str, Any]:
    checks = 0
    _check(receipt.get("schema") == SCHEMA, "schema mismatch"); checks += 1
    _check(receipt.get("status") == "MEASURED", "receipt is not measured"); checks += 1
    rule = receipt.get("digest_rule")
    _check(isinstance(rule, Mapping), "digest rule missing"); checks += 1
    _check(set(rule.get("strip_keys", [])) == {"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"}, "strip rule mismatch"); checks += 1
    actual_digest = digest(receipt)
    _check(actual_digest == str(receipt.get("content_digest", "")), "content digest mismatch"); checks += 1
    _check(receipt.get("receipt_digest") == receipt.get("content_digest"), "receipt digest alias mismatch"); checks += 1
    _check(receipt.get("self_check", {}).get("content_digest_matches") is True, "runner self-check failed"); checks += 1
    protocol = receipt.get("protocol", {})
    _check(protocol.get("cue_to_action") == MAPPING, "coordinate protocol mapping mismatch"); checks += 1
    direction_rows = receipt.get("cue_directions", [])
    _check([row.get("name") for row in direction_rows] == list(CUES), "cue direction order mismatch"); checks += 1
    _check(len({row.get("direction_sha256") for row in direction_rows}) == len(CUES), "cue direction digests are not distinct"); checks += 1
    continuity = receipt.get("continuity", {})
    _check(continuity.get("write_budget", {}).get("within_tolerance") is True, "write budget continuity failed"); checks += 1
    _check(continuity.get("greatest_off_diagonal_squared_cosine", {}).get("within_tolerance") is True, "overlap continuity failed"); checks += 1
    _check(continuity.get("source_selectors") == ["continuity.write_budget.observed", "orthogonality.greatest_off_diagonal_squared_cosine"], "source selectors missing"); checks += 1
    rows = receipt.get("episodes", [])
    _check(isinstance(rows, list) and len(rows) == 8, "episode census mismatch"); checks += 1
    digests = {str(row["name"]): str(row["direction_sha256"]) for row in direction_rows}
    controls = receipt["controls"]
    margin_floor = float(controls["selection_margin_floor"])
    score_floor = float(controls["score_floor"])
    _check(score_floor == SCORE_FLOOR, "score floor mismatch"); checks += 1
    _check(margin_floor == MARGIN_FLOOR, "margin floor mismatch"); checks += 1
    share_floor = float(controls["action_share_floor"])
    measured_names = ["train:0", "train:1", "held-out:combination"]
    for name in measured_names:
        row = _row(rows, name)
        scores = row.get("scores", {})
        _check(set(scores) == set(CUES), f"{name}: scores do not cover cues"); checks += 1
        ranked = [cue for cue, _ in sorted(scores.items(), key=lambda pair: (-float(pair[1]), digests[pair[0]]))]
        candidate = ranked[:2]
        selected_min = min((float(scores[cue]) for cue in candidate), default=0.0)
        unselected_max = max((float(scores[cue]) for cue in ranked[2:]), default=0.0)
        candidate_margin = selected_min - unselected_max
        expected_selected = select(scores, digests)
        _check(row.get("selected_cues") == expected_selected, f"{name}: gated selection formula mismatch"); checks += 1
        _check(row.get("selected_scores_clear_gates") is True, f"{name}: score/margin gates not declared clear"); checks += 1
        _check(row.get("abstained") is False and row.get("action_count") == 2, f"{name}: measured row abstained or action count mismatch"); checks += 1
        _check(set(row.get("selected_cues", [])) == set(row.get("hidden_cues", [])), f"{name}: hidden set not recovered"); checks += 1
        _check(abs(float(row.get("selection_margin")) - candidate_margin) <= 1e-15, f"{name}: selection margin mismatch"); checks += 1
        _check(float(row.get("selection_margin")) > margin_floor and selected_min >= score_floor, f"{name}: selection gates absent"); checks += 1
        expected_actions = [MAPPING[cue] for cue in expected_selected]
        _check(row.get("expected_actions") == expected_actions, f"{name}: expected action rows mismatch"); checks += 1
        _check(row.get("action_sequence_match") is True, f"{name}: action sequence did not match"); checks += 1
        _check(len(row.get("acts", [])) == 2, f"{name}: action count mismatch"); checks += 1
        for act in row["acts"]:
            cue = str(act.get("cue"))
            _check(act.get("target_action") == MAPPING.get(cue), f"{name}: target action mismatch"); checks += 1
            _check(act.get("action_direction") == MAPPING.get(cue), f"{name}: acted direction mismatch"); checks += 1
            _check(act.get("accepted") is True, f"{name}: owner action was not accepted"); checks += 1
            _check(float(act.get("share_along_action_direction")) >= share_floor, f"{name}: action direction share below floor"); checks += 1

    heldout = _row(rows, "held-out:combination")
    blank = _row(rows, "control:blank-no-memory")
    suppressed = _row(rows, "control:cue-read-suppressed")
    wrong = _row(rows, "control:wrong-cue-action-mapping")
    unconditional = _row(rows, "control:unconditional-fixed-action")
    permuted = _row(rows, "control:action-order-permutation")
    _check(blank.get("writes") == [] and blank.get("read_calls") == 4, "blank control did not attempt blank reads"); checks += 1
    _check(blank.get("abstained") is True and blank.get("action_count") == 0 and blank.get("selected_cues") == [] and blank.get("selected_actions") == [] and blank.get("action_order") == [] and blank.get("acts") == [], "blank control did not abstain without owner action"); checks += 1
    _check(blank.get("selected_cues") != heldout.get("selected_cues"), "blank control did not fire"); checks += 1
    _check(suppressed.get("read_calls") == 0 and suppressed.get("suppressed_probe") is not None, "suppressed control did not prove read suppression"); checks += 1
    _check(suppressed.get("abstained") is True and suppressed.get("action_count") == 0 and suppressed.get("selected_cues") == [] and suppressed.get("selected_actions") == [] and suppressed.get("action_order") == [] and suppressed.get("acts") == [], "suppressed control did not abstain without owner action"); checks += 1
    _check(suppressed.get("selected_cues") != heldout.get("selected_cues"), "suppressed control did not fire"); checks += 1
    _check(wrong.get("exact_cue_set_match") is True and wrong.get("action_sequence_match") is False and wrong.get("abstained") is False and wrong.get("action_count") == 2, "wrong mapping control did not fire"); checks += 1
    _check(all(act.get("action_direction") != MAPPING.get(str(act.get("cue"))) for act in wrong.get("acts", [])), "wrong mapping action rows did not all diverge"); checks += 1
    _check(unconditional.get("mode") == "unconditional", "unconditional mode missing"); checks += 1
    _check(unconditional.get("selected_cues") == list(CUES[:2]), "unconditional fixed pair changed"); checks += 1
    _check(unconditional.get("selected_cues") != select(unconditional.get("scores", {}), digests), "unconditional selection was score-derived"); checks += 1
    _check(unconditional.get("exact_cue_set_match") is False and unconditional.get("action_count") == 2 and all(act.get("accepted") is True for act in unconditional.get("acts", [])), "unconditional control did not fire"); checks += 1
    _check(permuted.get("selected_cues") == heldout.get("selected_cues"), "order control changed selection"); checks += 1
    _check(permuted.get("action_order") != heldout.get("action_order") and permuted.get("action_sequence_match") is False, "action-order control did not fire"); checks += 1
    derived_firing = {
        "blank_selection_changed": blank.get("selected_cues") != heldout.get("selected_cues"),
        "blank_abstained_without_action": blank.get("abstained") is True and blank.get("action_count") == 0,
        "suppressed_selection_changed": suppressed.get("selected_cues") != heldout.get("selected_cues"),
        "suppressed_abstained_without_action": suppressed.get("abstained") is True and suppressed.get("action_count") == 0,
        "wrong_action_changed": wrong.get("action_sequence_match") is False,
        "unconditional_selection_changed": unconditional.get("selected_cues") != heldout.get("selected_cues"),
        "order_changed_without_selection_change": permuted.get("selected_cues") == heldout.get("selected_cues") and permuted.get("action_order") != heldout.get("action_order"),
    }
    controls = receipt.get("controls", {})
    _check(controls.get("firing") == derived_firing, "firing control block is not row-derived"); checks += 1
    expected_controls = ("blank_no_memory", "cue_read_suppressed", "wrong_cue_action_mapping", "unconditional_fixed_action", "action_order_permutation")
    _check(set(controls.get("attempted", [])) == set(expected_controls), "control census mismatch"); checks += 1
    for key in expected_controls:
        _check(controls.get(key) is True, f"declared control {key} failed"); checks += 1
    for key in derived_firing:
        _check(controls.get("firing", {}).get(key) is True, f"firing control {key} failed"); checks += 1

    positive_scores = {"a": 3.0, "b": 2.0, "c": 0.0, "d": 0.0}
    positive_digests = {"a": "a", "b": "b", "c": "c", "d": "d"}
    negative_scores = {key: 0.0 for key in positive_scores}
    positive_selected = select(positive_scores, positive_digests)
    negative_selected = select(negative_scores, positive_digests)
    positive = positive_selected == ["a", "b"]
    negative = negative_selected == []
    _check(positive, "positive synthetic anchor failed"); checks += 1
    _check(negative, "negative synthetic anchor failed"); checks += 1
    return {"status": "VERIFIED", "schema": SCHEMA, "content_digest_matches": True, "content_digest": actual_digest, "checks": checks, "positive_anchor": positive, "negative_anchor": negative}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    try:
        result = verify(json.loads(args.receipt.read_text(encoding="utf-8")))
    except (AssertionError, KeyError, TypeError, ValueError) as exc:
        result = {"status": "REJECTED", "schema": SCHEMA, "error": str(exc)}
        print(json.dumps(result, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
