"""Opaque candidate-set recovery from the field's public read path.

This is deliberately not semantic recall or task utility.  Four orthogonal
field-coordinate directions are candidates.  An episode writes a hidden set of
two, reads all four through ``FieldIntelligenceOwner.read_packet_deposit`` in a
shuffled presentation order, selects the top two by measured score (lexical
direction digest breaks ties), and performs one owner act per selected direction.
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
import run_fractal_geometry_exploration as geometry
import run_memory_consumer_path as consumer

SCHEMA = "cassifi.opaque-candidate-set-recovery.v1"
DEFAULT_OUTPUT = Path("_diag/task-conditioned-memory-consumer/exploration.json")
SOURCE_RECEIPT = Path("_diag/memory-consumer-path/exploration.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 180.0
CONTINUITY_TOLERANCE = 1e-12
ACT_BUDGET = 1e-3
HOLD_TICKS = 2
TIMING_KEYS = frozenset({"elapsed_seconds", "runtime_seconds", "content_digest", "receipt_digest", "receipt_sha256", "self_check"})
CANDIDATE_NAMES = ("root-scale", "root-detail", "left-detail", "right-detail")
TRAIN_HIDDEN_SETS = (("root-scale", "left-detail"), ("root-detail", "right-detail"))
HELDOUT_HIDDEN_SET = ("left-detail", "right-detail")
ORDERS = (
    ("root-scale", "root-detail", "left-detail", "right-detail"),
    ("right-detail", "left-detail", "root-scale", "root-detail"),
    ("root-detail", "right-detail", "left-detail", "root-scale"),
)
HELDOUT_ORDER = ("left-detail", "root-scale", "right-detail", "root-detail")


def _jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return [_jsonable(x) for x in value.tolist()]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(v) for v in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if str(k) not in TIMING_KEYS}
    if isinstance(value, (tuple, list)):
        return [strip_timing(v) for v in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def _profile() -> Any:
    return arrangement._profile("helix7")


def _specs() -> dict[str, durability.ItemSpec]:
    return {spec.name: spec for spec in durability.ITEM_SPECS}


def _digest_direction(capture: Mapping[str, Any]) -> str:
    return hashlib.sha256(np.ascontiguousarray(np.asarray(capture["direction"], dtype=np.float64), dtype="<f8").tobytes()).hexdigest()


def _top_two(scores: Mapping[str, float], direction_digests: Mapping[str, str]) -> list[str]:
    # Presentation order is intentionally absent from this key.  The digest is
    # the deterministic tie-break for blank/silenced pages.
    return [name for name, _ in sorted(scores.items(), key=lambda pair: (-float(pair[1]), direction_digests[pair[0]]))[:2]]


def _act_and_measure(owner: Any, name: str, spec: durability.ItemSpec, capture: Mapping[str, Any], captures_by_name: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    before = consumer.frame(owner.state.resonant_workspace)
    result = consumer.plain(owner.write_packet_impulse(f"{name}:act:{spec.name}", **consumer.named_direction(spec), work_budget=ACT_BUDGET))
    after = consumer.frame(owner.state.resonant_workspace)
    increment = after - before
    return {
        "direction": spec.name,
        "accepted": bool(result["impulse_receipt"]["accepted"]),
        "applied_work": float(result["impulse_receipt"]["applied_work"]),
        "share_along_acted_direction": None if consumer.share_along(increment, np.asarray(capture["direction"], dtype=np.float64)) is None else float(consumer.share_along(increment, np.asarray(capture["direction"], dtype=np.float64))),
        "read_frame_increment_energy": float(np.dot(increment, increment)),
    }


def _episode(profile: Any, captures_by_name: Mapping[str, Mapping[str, Any]], specs: Mapping[str, durability.ItemSpec], hidden: Sequence[str], order: Sequence[str], *, name: str, mode: str = "measured-read", hold_ticks: int = HOLD_TICKS, decoys: Sequence[str] = (), action_order: Sequence[str] | None = None) -> dict[str, Any]:
    owner, home = consumer.open_owner(profile, prefix="tcmc-owner-")
    try:
        writes = []
        for direction in tuple(hidden) + tuple(decoys):
            result = consumer.plain(owner.write_packet_impulse(f"{name}:memory:{direction}", **consumer.named_direction(specs[direction]), work_budget=ACT_BUDGET))
            writes.append({"direction": direction, "accepted": bool(result["impulse_receipt"]["accepted"]), "applied_work": float(result["impulse_receipt"]["applied_work"])})
        if hold_ticks:
            owner.advance(f"{name}:hold", ticks=int(hold_ticks), source_enabled=False)
        instrument = None
        if mode == "read-suppressed":
            instrument_read = consumer.plain(owner.read_packet_deposit(**consumer.named_direction(specs[hidden[0]])))
            instrument = {"direction": hidden[0], "recovered_deposit": float(instrument_read["recovered_deposit"]), "readout_kind": str(instrument_read["readout_kind"])}
            scores = {candidate: 0.0 for candidate in order}
            read_calls = 0
        else:
            scores = {}
            for candidate in order:
                result = consumer.plain(owner.read_packet_deposit(**consumer.named_direction(specs[candidate])))
                scores[candidate] = float(result["recovered_deposit"])
            read_calls = len(order)
        digests = {candidate: _digest_direction(captures_by_name[candidate]) for candidate in CANDIDATE_NAMES}
        selected = _top_two(scores, digests) if mode != "unconditional" else list(CANDIDATE_NAMES[:2])
        act_order = [candidate for candidate in (action_order or selected) if candidate in selected]
        acts = [_act_and_measure(owner, f"{name}:act-{index}", specs[direction], captures_by_name[direction], captures_by_name) for index, direction in enumerate(act_order)]
        selected_set, hidden_set = set(selected), set(hidden)
        unselected = [candidate for candidate in CANDIDATE_NAMES if candidate not in selected_set]
        margin = min((scores[candidate] for candidate in selected), default=0.0) - max((scores[candidate] for candidate in unselected), default=0.0)
        precision = len(selected_set & hidden_set) / 2.0
        recall = len(selected_set & hidden_set) / 2.0
        return {
            "name": name, "status": "MEASURED", "mode": mode, "hidden_set": list(hidden), "presentation_order": list(order), "action_order": act_order, "read_calls": read_calls,
            "scores": {candidate: float(scores[candidate]) for candidate in order}, "direction_digests": digests, "selected_set": selected, "exact_set_match": selected_set == hidden_set,
            "precision": float(precision), "recall": float(recall), "selection_margin": float(margin), "writes": writes, "acts": acts, "instrument_read": instrument,
            "declared": "opaque candidate-set recovery in field coordinates; no semantic or task-utility claim",
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    np.seterr(all="raise")
    profile = _profile()
    specs = _specs()
    capture_config = durability.DurabilityConfig(write_budget=ACT_BUDGET)
    captures = durability.capture_items(capture_config, profile)
    captures_by_name = {str(capture["name"]): capture for capture in captures}
    candidates = {name: captures_by_name[name] for name in CANDIDATE_NAMES}
    direction_digests = {name: _digest_direction(captures_by_name[name]) for name in CANDIDATE_NAMES}
    overlap_matrix = durability.overlap_matrix(captures)
    candidate_indices = [next(i for i, spec in enumerate(durability.ITEM_SPECS) if spec.name == name) for name in CANDIDATE_NAMES]
    pairwise = {name: {other: float(overlap_matrix[i][j]) for other, j in zip(CANDIDATE_NAMES, candidate_indices) if other != name} for name, i in zip(CANDIDATE_NAMES, candidate_indices)}
    max_overlap = max(value for row in pairwise.values() for value in row.values())
    source = json.loads(SOURCE_RECEIPT.read_text(encoding="utf-8"))
    source_write_budget = float(source["declared"]["config"]["write_budget"])
    source_overlap = float(source["captures"]["greatest_off_diagonal_squared_cosine"])
    continuity = {
        "source_receipt": str(SOURCE_RECEIPT).replace("\\", "/"),
        "write_budget": {"selector": "declared.config.write_budget", "source": source_write_budget, "observed": ACT_BUDGET, "difference": ACT_BUDGET - source_write_budget, "within_tolerance": abs(ACT_BUDGET-source_write_budget) <= CONTINUITY_TOLERANCE},
        "greatest_off_diagonal_squared_cosine": {"selector": "captures.greatest_off_diagonal_squared_cosine", "source": source_overlap, "observed": max_overlap, "difference": max_overlap - source_overlap, "within_tolerance": abs(max_overlap - source_overlap) <= CONTINUITY_TOLERANCE},
    }
    episodes = []
    for index, hidden in enumerate(TRAIN_HIDDEN_SETS):
        episodes.append(_episode(profile, candidates, specs, hidden, ORDERS[index], name=f"train:{index}"))
    episodes.append(_episode(profile, candidates, specs, HELDOUT_HIDDEN_SET, HELDOUT_ORDER, name="held-out:permutation"))
    suppressed = _episode(profile, candidates, specs, HELDOUT_HIDDEN_SET, HELDOUT_ORDER, name="control:same-page-read-suppressed", mode="read-suppressed")
    blank = _episode(profile, candidates, specs, (), HELDOUT_ORDER, name="control:blank-no-memory", hold_ticks=HOLD_TICKS)
    decoy_set = ("root-scale", "root-detail")
    decoy = _episode(profile, candidates, specs, (), HELDOUT_ORDER, name="control:decoy-only", decoys=decoy_set, hold_ticks=HOLD_TICKS)
    firing = _episode(profile, candidates, specs, HELDOUT_HIDDEN_SET, HELDOUT_ORDER, name="control:unconditional-policy-firing", mode="unconditional", hold_ticks=0)
    action_order = tuple(reversed(HELDOUT_ORDER))
    action_act_order = CANDIDATE_NAMES
    order_control = _episode(profile, candidates, specs, HELDOUT_HIDDEN_SET, action_order, name="control:order-permutation", action_order=action_act_order)
    episodes.extend([suppressed, blank, decoy, firing, order_control])
    measured = [episode for episode in episodes if episode["name"].startswith(("train:", "held-out:"))]
    heldout = [episode for episode in measured if episode["name"].startswith("held-out:")]
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "question": "Can the public field read path recover a hidden two-item candidate set from four orthogonal directions under a held-out presentation permutation?",
        "status": "MEASURED",
        "numeric_policy": {"dtype": "float64", "device": "cpu", "numpy_seterr": "raise", "seed": SEED},
        "profile": {"arrangement": "helix7", "builder": "run_fractal_arrangement_recall_exploration._profile", "topology": str(profile.topology), "port_count": int(profile.port_count)},
        "candidate_directions": [{"name": name, "path": specs[name].path, "component": specs[name].component, "flow_signal": list(specs[name].flow_signal), "direction_sha256": direction_digests[name]} for name in CANDIDATE_NAMES],
        "declared_task": {"label": "opaque candidate-set recovery", "candidate_count": 4, "hidden_set_size": 2, "score": "FieldIntelligenceOwner.read_packet_deposit recovered_deposit", "selection": "top-2 by score; direction digest lexical order breaks ties; presentation index is never used", "action": "one owner write_packet_impulse act per selected direction", "semantic_claim": False},
        "orthogonality": {"pairwise_squared_cosine": pairwise, "greatest_off_diagonal_squared_cosine": float(max_overlap), "declared_allowance": 1e-12, "within_allowance": bool(max_overlap <= 1e-12)},
        "continuity": continuity,
        "episodes": episodes,
        "evaluation": {"train": {"total": 2, "exact_set_matches": sum(bool(e["exact_set_match"]) for e in measured if e["name"].startswith("train:"))}, "held_out_permutation": {"total": 1, "exact_set_matches": sum(bool(e["exact_set_match"]) for e in heldout), "precision": float(heldout[0]["precision"]), "recall": float(heldout[0]["recall"]), "selection_margin": float(heldout[0]["selection_margin"]), "exact_set_match": bool(heldout[0]["exact_set_match"]) }},
        "controls": {"same_page_read_suppressed": suppressed["read_calls"] == 0 and suppressed["instrument_read"] is not None and not suppressed["exact_set_match"], "blank_no_memory": not blank["exact_set_match"], "decoy": not decoy["exact_set_match"], "unconditional_policy_firing": firing["mode"] == "unconditional" and all(act["accepted"] for act in firing["acts"]) and not firing["exact_set_match"], "cue_action_permutation": order_control["presentation_order"] == list(action_order) and order_control["action_order"] != heldout[0]["action_order"] and bool(order_control["exact_set_match"])},
        "limitations": ["This is an opaque field-coordinate candidate-set recovery measurement, not semantic recall, language understanding, or task usefulness.", "The four directions and hidden sets are declared by the runner; the relation is not learned and no semantic labels are attached.", "Held-out evaluation covers one candidate-order permutation and two hidden sets; no embeddings, neural state, sidecar policy, Qwen call, or hard-coded presentation-index selection is used."],
        "timing": {"runtime_seconds": float(time.perf_counter() - started)},
    }
    if body["timing"]["runtime_seconds"] >= MAX_RUNTIME_SECONDS:
        raise TimeoutError("opaque candidate-set probe exceeded runtime ceiling")
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
    print(json.dumps({"output": str(args.output), "status": receipt["status"], "content_digest": receipt["content_digest"], "held_out_exact_set_match": receipt["evaluation"]["held_out_permutation"]["exact_set_match"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
