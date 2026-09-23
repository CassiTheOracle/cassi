"""Measure a cue-conditioned action through field-owner read/write methods.

The cue is a declared direction in the canonical packet coordinate system.  A
fresh owner writes one or two cues, the field-owner ``read_packet_deposit``
method selects them from measured scores, and the owner writes the declared
action for each selected cue.  Existing harness capture instrumentation supplies
the coordinate directions; this is a bounded controller measurement, not a
semantic or language task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

import run_fractal_arrangement_recall_exploration as arrangement
import run_fractal_durability_exploration as durability
import run_memory_consumer_path as consumer

SCHEMA = "cassifi.cue-conditioned-field-action.v1"
DEFAULT_OUTPUT = Path("_diag/cue-conditioned-field-action/exploration.json")
SOURCE_RECEIPT = Path("_diag/task-conditioned-memory-consumer/exploration.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 180.0
CONTINUITY_TOLERANCE = 1e-12
ACT_BUDGET = 1e-3
HOLD_TICKS = 2
SELECTION_MARGIN_FLOOR = 1e-12
SCORE_FLOOR = 1e-12
ACTION_SHARE_FLOOR = 1.0 - 1e-12
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})
CUE_NAMES = ("root-scale", "root-detail", "left-detail", "right-detail")
# This is a fixed coordinate protocol, not learned adaptive state or a sidecar
TRAIN_CUE_SETS = (("root-scale", "left-detail"), ("root-detail", "right-detail"))
# policy.  Training rows exercise two pairs; held-out rows exercise the other
# two pairs in a combination and a new presentation order.
CUE_TO_ACTION = {
    "root-scale": "left-detail",
    "root-detail": "right-detail",
    "left-detail": "root-scale",
    "right-detail": "root-detail",
}
TRAIN_PAIRS = (("root-scale", "left-detail"), ("root-detail", "right-detail"))
HELD_OUT_PAIRS = (("left-detail", "root-scale"), ("right-detail", "root-detail"))
HELD_OUT_CUES = tuple(cue for cue, _ in HELD_OUT_PAIRS)
PRESENTATION_ORDERS = (
    ("root-scale", "left-detail", "root-detail", "right-detail"),
    ("right-detail", "root-scale", "root-detail", "left-detail"),
)
HELD_OUT_ORDER = ("right-detail", "root-scale", "left-detail", "root-detail")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(item) for item in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if str(key) not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def _profile() -> Any:
    return arrangement._profile("helix7")


def _specs() -> dict[str, durability.ItemSpec]:
    return {spec.name: spec for spec in durability.ITEM_SPECS}


def _direction_digest(capture: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        np.ascontiguousarray(np.asarray(capture["direction"], dtype=np.float64), dtype="<f8").tobytes()
    ).hexdigest()


def _select(scores: Mapping[str, float], digests: Mapping[str, str]) -> tuple[list[str], float, float, bool]:
    ranked = [name for name, _ in sorted(scores.items(), key=lambda pair: (-float(pair[1]), digests[pair[0]]))]
    candidate = ranked[:2]
    selected_min = min((float(scores[name]) for name in candidate), default=0.0)
    unselected_max = max((float(scores[name]) for name in ranked[2:]), default=0.0)
    margin = selected_min - unselected_max
    gates_clear = len(candidate) == 2 and selected_min >= SCORE_FLOOR and margin > SELECTION_MARGIN_FLOOR
    return (candidate if gates_clear else []), selected_min, margin, gates_clear


def _act(owner: Any, cue: str, action: str, specs: Mapping[str, durability.ItemSpec], captures: Mapping[str, Mapping[str, Any]], episode: str, index: int) -> dict[str, Any]:
    before = consumer.frame(owner.state.resonant_workspace)
    result = consumer.plain(owner.write_packet_impulse(f"{episode}:action:{index}:{cue}", **consumer.named_direction(specs[action]), work_budget=ACT_BUDGET))
    after = consumer.frame(owner.state.resonant_workspace)
    increment = after - before
    direction = np.asarray(captures[action]["direction"], dtype=np.float64)
    share = consumer.share_along(increment, direction)
    return {
        "cue": cue,
        "target_action": CUE_TO_ACTION[cue],
        "action_direction": action,
        "accepted": bool(result["impulse_receipt"]["accepted"]),
        "applied_work": float(result["impulse_receipt"]["applied_work"]),
        "share_along_action_direction": None if share is None else float(share),
        "owner_write_delta_energy": float(np.dot(increment, increment)),
    }


def _episode(
    profile: Any,
    specs: Mapping[str, durability.ItemSpec],
    captures: Mapping[str, Mapping[str, Any]],
    hidden: Sequence[str],
    presentation_order: Sequence[str],
    *,
    name: str,
    mode: str = "measured-read",
    action_order: Sequence[str] | None = None,
    mapping: Mapping[str, str] = CUE_TO_ACTION,
) -> dict[str, Any]:
    owner, home = consumer.open_owner(profile, prefix="ccfa-owner-")
    try:
        writes: list[dict[str, Any]] = []
        for cue in hidden:
            result = consumer.plain(owner.write_packet_impulse(f"{name}:cue:{cue}", **consumer.named_direction(specs[cue]), work_budget=ACT_BUDGET))
            writes.append({"cue": cue, "accepted": bool(result["impulse_receipt"]["accepted"]), "applied_work": float(result["impulse_receipt"]["applied_work"])})
        if mode == "read-suppressed":
            probe = consumer.plain(owner.read_packet_deposit(**consumer.named_direction(specs[hidden[0]]))) if hidden else None
            scores = {cue: 0.0 for cue in CUE_NAMES}
            read_calls = 0
            suppressed_probe = None if probe is None else {"recovered_deposit": float(probe["recovered_deposit"]), "readout_kind": str(probe["readout_kind"])}
        else:
            scores = {}
            read_calls = 0
            suppressed_probe = None
            for cue in CUE_NAMES:
                result = consumer.plain(owner.read_packet_deposit(**consumer.named_direction(specs[cue])))
                scores[cue] = float(result["recovered_deposit"])
                read_calls += 1
        digests = {cue: _direction_digest(captures[cue]) for cue in CUE_NAMES}
        if mode == "unconditional":
            selected = list(CUE_NAMES[:2])
            candidate_min = min(float(scores[cue]) for cue in selected)
            candidate_margin = candidate_min - max((float(scores[cue]) for cue in CUE_NAMES[2:]), default=0.0)
            gates_clear = False
        else:
            selected, candidate_min, candidate_margin, gates_clear = _select(scores, digests)
        selected_actions = [mapping[cue] for cue in selected]
        actual_action_order = list(action_order or selected) if selected else []
        acts = [_act(owner, cue, mapping[cue], specs, captures, name, index) for index, cue in enumerate(actual_action_order)]
        hidden_set = set(hidden)
        selected_set = set(selected)
        expected_actions = [CUE_TO_ACTION[cue] for cue in selected]
        actual_actions = [row["action_direction"] for row in acts]
        return {
            "name": name,
            "status": "MEASURED",
            "mode": mode,
            "hidden_cues": list(hidden),
            "presentation_order": list(presentation_order),
            "action_order": actual_action_order,
            "read_calls": read_calls,
            "scores": {cue: float(scores[cue]) for cue in presentation_order},
            "direction_digests": digests,
            "selected_cues": selected,
            "selected_actions": selected_actions,
            "expected_actions": expected_actions,
            "exact_cue_set_match": selected_set == hidden_set,
            "action_sequence_match": actual_actions == expected_actions,
            "selection_margin": float(candidate_margin),
            "selection_margin_floor": SELECTION_MARGIN_FLOOR,
            "score_floor": SCORE_FLOOR,
            "selected_scores_clear_gates": bool(gates_clear),
            "abstained": not bool(selected),
            "action_count": len(acts),
            "writes": writes,
            "acts": acts,
            "suppressed_probe": suppressed_probe,
            "declared": "synthetic cue-conditioned controller in field coordinates; no semantic or task-utility claim",
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    np.seterr(all="raise")
    profile = _profile()
    specs = _specs()
    captures_list = durability.capture_items(durability.DurabilityConfig(write_budget=ACT_BUDGET), profile)
    captures = {str(row["name"]): row for row in captures_list}
    digests = {cue: _direction_digest(captures[cue]) for cue in CUE_NAMES}
    overlap = durability.overlap_matrix(captures_list)
    indices = [next(index for index, spec in enumerate(durability.ITEM_SPECS) if spec.name == cue) for cue in CUE_NAMES]
    pairwise = {cue: {other: float(overlap[i][j]) for other, j in zip(CUE_NAMES, indices) if other != cue} for cue, i in zip(CUE_NAMES, indices)}
    greatest_overlap = max((value for row in pairwise.values() for value in row.values()), default=0.0)
    source = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    source_budget = float(source["continuity"]["write_budget"]["observed"])
    source_overlap = float(source["orthogonality"]["greatest_off_diagonal_squared_cosine"])
    continuity = {
        "source_receipt": str(SOURCE_RECEIPT).replace("\\", "/"),
        "source_selectors": ["continuity.write_budget.observed", "orthogonality.greatest_off_diagonal_squared_cosine"],
        "write_budget": {"source": source_budget, "observed": ACT_BUDGET, "difference": ACT_BUDGET - source_budget, "within_tolerance": abs(ACT_BUDGET - source_budget) <= CONTINUITY_TOLERANCE},
        "greatest_off_diagonal_squared_cosine": {"source": source_overlap, "observed": greatest_overlap, "difference": greatest_overlap - source_overlap, "within_tolerance": abs(greatest_overlap - source_overlap) <= CONTINUITY_TOLERANCE},
    }
    training_episodes = [
        _episode(profile, specs, captures, cue_set, PRESENTATION_ORDERS[index], name=f"train:{index}")
        for index, cue_set in enumerate(TRAIN_CUE_SETS)
    ]
    heldout = _episode(profile, specs, captures, HELD_OUT_CUES, HELD_OUT_ORDER, name="held-out:combination")
    blank = _episode(profile, specs, captures, (), HELD_OUT_ORDER, name="control:blank-no-memory")
    suppressed = _episode(profile, specs, captures, HELD_OUT_CUES, HELD_OUT_ORDER, name="control:cue-read-suppressed", mode="read-suppressed")
    wrong_mapping = dict(CUE_TO_ACTION)
    wrong_mapping["left-detail"], wrong_mapping["right-detail"] = wrong_mapping["right-detail"], wrong_mapping["left-detail"]
    wrong = _episode(profile, specs, captures, HELD_OUT_CUES, HELD_OUT_ORDER, name="control:wrong-cue-action-mapping", mapping=wrong_mapping)
    unconditional = _episode(profile, specs, captures, HELD_OUT_CUES, HELD_OUT_ORDER, name="control:unconditional-fixed-action", mode="unconditional")
    permuted = _episode(profile, specs, captures, HELD_OUT_CUES, tuple(reversed(HELD_OUT_ORDER)), name="control:action-order-permutation", action_order=HELD_OUT_CUES)
    episodes = [*training_episodes, heldout, blank, suppressed, wrong, unconditional, permuted]
    measured = episodes[:3]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": "Can a declared field-coordinate cue read through field-owner read/write methods select the paired field-coordinate action on training pairs and a held-out combination?",
        "status": "MEASURED",
        "numeric_policy": {"dtype": "float64", "device": "cpu", "numpy_seterr": "raise", "seed": SEED},
        "profile": {"arrangement": "helix7", "builder": "run_fractal_arrangement_recall_exploration._profile", "topology": str(profile.topology), "port_count": int(profile.port_count)},
        "cue_directions": [{"name": cue, "path": specs[cue].path, "component": specs[cue].component, "flow_signal": list(specs[cue].flow_signal), "direction_sha256": digests[cue]} for cue in CUE_NAMES],
        "protocol": {"cue_to_action": dict(CUE_TO_ACTION), "selection": "rank by recovered_deposit, then direction digest lexical order; measured-read selects exactly two only when both selected scores are at least score_floor and selection margin is greater than selection_margin_floor; otherwise it abstains; presentation index is never used", "action": "one owner write_packet_impulse per selected cue, using the fixed declared coordinate protocol; abstention performs no owner action", "adaptive_state": "the live resonant field only", "semantic_claim": False},
        "training_pairs": [{"cue": cue, "action": action} for cue, action in TRAIN_PAIRS],
        "held_out_pairs": [{"cue": cue, "action": action} for cue, action in HELD_OUT_PAIRS],
        "continuity": continuity,
        "orthogonality": {"pairwise_squared_cosine": pairwise, "greatest_off_diagonal_squared_cosine": float(greatest_overlap), "declared_allowance": 1e-12, "within_allowance": bool(greatest_overlap <= 1e-12)},
        "episodes": episodes,
        "evaluation": {"training": {"total": 2, "exact_cue_set_matches": sum(bool(row["exact_cue_set_match"]) for row in measured[:2]), "action_sequence_matches": sum(bool(row["action_sequence_match"]) for row in measured[:2])}, "held_out_combination": {"exact_cue_set_match": bool(heldout["exact_cue_set_match"]), "action_sequence_match": bool(heldout["action_sequence_match"]), "selection_margin": float(heldout["selection_margin"]), "selected_cues": list(heldout["selected_cues"]), "selected_actions": list(heldout["selected_actions"])}},
        "controls": {
            "attempted": ["blank_no_memory", "cue_read_suppressed", "wrong_cue_action_mapping", "unconditional_fixed_action", "action_order_permutation"],
            "selection_margin_floor": SELECTION_MARGIN_FLOOR,
            "score_floor": SCORE_FLOOR,
            "action_share_floor": ACTION_SHARE_FLOOR,
            "wrong_cue_action_mapping": wrong["exact_cue_set_match"] and not wrong["action_sequence_match"],
            "unconditional_fixed_action": unconditional["mode"] == "unconditional" and not unconditional["exact_cue_set_match"],
            "action_order_permutation": permuted["exact_cue_set_match"] and permuted["selected_cues"] == heldout["selected_cues"] and permuted["action_order"] != heldout["action_order"] and permuted["action_sequence_match"] is False,
            "blank_no_memory": blank["abstained"] and blank["action_count"] == 0 and blank["selected_cues"] == [] and blank["selected_actions"] == [] and blank["action_order"] == [] and blank["acts"] == [],
            "cue_read_suppressed": suppressed["read_calls"] == 0 and suppressed["suppressed_probe"] is not None and suppressed["abstained"] and suppressed["action_count"] == 0 and suppressed["selected_cues"] == [] and suppressed["selected_actions"] == [] and suppressed["action_order"] == [] and suppressed["acts"] == [],
            "firing": {"blank_selection_changed": blank["selected_cues"] != heldout["selected_cues"], "blank_abstained_without_action": blank["abstained"] and blank["action_count"] == 0, "suppressed_selection_changed": suppressed["selected_cues"] != heldout["selected_cues"], "suppressed_abstained_without_action": suppressed["abstained"] and suppressed["action_count"] == 0, "wrong_action_changed": wrong["action_sequence_match"] is False, "unconditional_selection_changed": unconditional["selected_cues"] != heldout["selected_cues"], "order_changed_without_selection_change": permuted["selected_cues"] == heldout["selected_cues"] and permuted["action_order"] != heldout["action_order"]},
        },
        "source_receipt_selectors": {"receipt": str(SOURCE_RECEIPT).replace("\\", "/"), "selectors": continuity["source_selectors"]},
        "digest_rule": {"algorithm": "sha256", "canonical_json": "sorted keys, compact separators, allow_nan=False", "strip_keys": sorted(TIMING_KEYS)},
        "limitations": ["The cue and action are synthetic declared directions in one field coordinate frame; no semantic cue, language understanding, or task utility is claimed.", "The cue-to-action relation is a fixed protocol exercised by training pairs, not learned weights or a persistent policy sidecar.", "The held-out result is one two-cue combination and one presentation permutation on one profile and budget; broader generalization is unmeasured.", "The runner imports private helper builders and existing harness capture instrumentation (arrangement._profile, durability.capture_items, and consumer.frame); the scope is therefore this repository's field-owner read/write methods plus that instrumentation, not a clean public-API-only isolation."],
        "timing": {"runtime_seconds": float(time.perf_counter() - started)},
    }
    if time.perf_counter() - started > MAX_RUNTIME_SECONDS:
        raise TimeoutError("cue-conditioned field action exceeded runtime ceiling")
    body["content_digest"] = content_digest(body)
    body["receipt_digest"] = body["content_digest"]
    body["self_check"] = {"performed": True, "content_digest_matches": content_digest(body) == body["content_digest"]}
    return body


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    actual = content_digest(receipt)
    return {"content_digest_matches": actual == str(receipt.get("content_digest", "")), "digest": actual, "status": receipt.get("status"), "episode_count": len(receipt.get("episodes", []))}


def write_receipt(path: Path) -> dict[str, Any]:
    receipt = build_receipt()
    if not verify_receipt(receipt)["content_digest_matches"]:
        raise ValueError("receipt digest self-check failed")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_jsonable(receipt), sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = write_receipt(args.output)
    print(json.dumps({"output": str(args.output), "status": receipt["status"], "content_digest": receipt["content_digest"], "held_out_combination": receipt["evaluation"]["held_out_combination"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
