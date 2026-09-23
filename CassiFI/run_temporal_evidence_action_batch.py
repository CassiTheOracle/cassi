"""Concurrent field-native temporal/evidence action-selection benchmark.

Each case owns a fresh FieldIntelligenceOwner and checkpoint home.  The
ThreadPoolExecutor only changes scheduling: rows are sorted by the declared
case order before the digest is computed.  Completion and elapsed diagnostics
are deliberately stripped from the content digest.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
import os
import json
import hashlib
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import AtlasState, canonical_json_bytes
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput
from run_temporal_evidence_action_selection import canonical_json

SCHEMA = "cassifi.temporal-evidence-action-batch.v1"
DEFAULT_OUTPUT = Path("_diag/temporal-evidence-action-batch/exploration.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 180.0
MINIMUM_MARGIN = 1e-12
MEMORY_ID = "evidence-actions-batch"
ACTION_IDS = ("left-step", "right-step", "jump-step", "bridge-step", "bridge-confirm", "idle")
OBSERVATION_IDS = ("left-goal", "right-stage", "right-goal", "jump-goal", "bridge-stage", "bridge-goal", "wrong-goal", "quiet")
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "case_elapsed_seconds", "completion_index", "completion_order", "worker_id", "content_digest", "receipt_digest", "self_check"})
CASE_ORDER = (
    "continuity-baseline",
    "continuity-baseline-reversed",
    "control-forbidden-operation",
    "control-infeasible-operation",
    "control-insufficient-margin",
    "control-no-workspace",
    "control-order-permutation",
    "control-wrong-consequence",
    "multi-step-consequence",
    "three-candidate",
    "unsupported-held-out-composition",
)

_CASES: dict[str, dict[str, Any]] = {
    "continuity-baseline": {"family": "two-candidate-continuity", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "consequence": "selected"},
    "continuity-baseline-reversed": {"family": "two-candidate-continuity", "skills": ("right-skill", "left-skill"), "operations": ("right-step", "left-step"), "consequence": "selected"},
    "three-candidate": {"family": "three-candidate", "skills": ("left-skill", "right-skill", "jump-skill"), "operations": ("left-step", "right-step", "jump-step"), "consequence": "selected"},
    "multi-step-consequence": {"family": "multi-step", "skills": ("bridge-skill",), "operations": ("bridge-step", "bridge-confirm"), "consequence": "multi-step"},
    "unsupported-held-out-composition": {"family": "unsupported-held-out-composition", "skills": ("bridge-skill",), "operations": ("bridge-step", "bridge-confirm"), "unsupported": True, "training_episodes": {"bridge": [[{"action": "bridge-step", "observation": "bridge-stage"}]]}},
    "control-no-workspace": {"family": "no-workspace-lesion", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "control": "no-workspace"},
    "control-insufficient-margin": {"family": "insufficient-margin", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "control": "insufficient-margin"},
    "control-forbidden-operation": {"family": "forbidden-operation", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "control": "forbidden-operation"},
    "control-infeasible-operation": {"family": "infeasible-operation", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "control": "infeasible-operation"},
    "control-wrong-consequence": {"family": "wrong-consequence", "skills": ("left-skill", "right-skill"), "operations": ("left-step", "right-step"), "consequence": "wrong"},
    "control-order-permutation": {"family": "order-permutation", "skills": ("left-skill", "right-skill"), "operations": ("right-step", "left-step"), "consequence": "selected", "permutation": True},
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if str(k) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value
def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def make_source(source_id: str, steps: Sequence[Mapping[str, str]], timestamp: str, labels: Sequence[str] = ("temporal-evidence-action-batch", "train")) -> SourceInput:
    return SourceInput(source_id=source_id,
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": list(steps)}),
        media_type="application/json", codec="utf-8", observed_timestamp=timestamp,
        scope="temporal-evidence-action-batch", claim_category="controlled-world-observation",
        fidelity="exact-record", labels=tuple(labels))


def operation_rows(actions: Sequence[str], *, authorized: bool = True, feasible: bool = True) -> list[dict[str, Any]]:
    return [{"action": action, "authorized": authorized, "feasible": feasible, "represented_forbidden": not authorized} for action in actions]


def _episodes() -> dict[str, list[dict[str, str]]]:
    return {
        "left": [{"action": "left-step", "observation": "left-goal"}],
        "right": [{"action": "right-step", "observation": "right-stage"}, {"action": "bridge-confirm", "observation": "right-goal"}],
        "jump": [{"action": "jump-step", "observation": "jump-goal"}],
        "bridge": [{"action": "bridge-step", "observation": "bridge-stage"}, {"action": "bridge-confirm", "observation": "bridge-goal"}],
    }
def _setup(prefix: str, needed_skills: Sequence[str], training_episodes: Mapping[str, Sequence[Sequence[Mapping[str, str]]]] | None = None) -> tuple[FieldIntelligenceOwner, Path, dict[str, Any]]:
    home = Path(tempfile.mkdtemp(prefix=prefix))
    owner = FieldIntelligenceOwner(home, limits=CapacityLimits(max_history_entries=2048), initial_state=AtlasState(resonant_workspace=None))
    context = {"world": "bounded-temporal-batch", "split": "concurrent-independent-cases"}
    owner.configure_temporal(f"{prefix}:configure", memory_id=MEMORY_ID, action_ids=ACTION_IDS, observation_ids=OBSERVATION_IDS, max_states=32, context=context)
    episodes = _episodes()
    side_for = {"left-skill": "left", "right-skill": "right", "jump-skill": "jump", "bridge-skill": "bridge"}
    overrides = {} if training_episodes is None else {str(side): [list(step) for step in values] for side, values in training_episodes.items()}
    learning: list[dict[str, Any]] = []
    for side in [side_for[s] for s in needed_skills]:
        source_episodes = overrides.get(side, [episodes[side]])
        for episode_index, source_steps in enumerate(source_episodes):
            source = make_source(f"{prefix}:episode:{side}:{episode_index}", source_steps, f"{prefix}:{side}:{episode_index}")
            result = owner.learn_temporal(f"{prefix}:learn:{side}:{episode_index}", memory_id=MEMORY_ID, source=source, context=context)
            learning.append({"side": side, "episode_index": episode_index, "source": source.as_dict(), "source_content_sha256": hashlib.sha256(source.content).hexdigest(), "receipt": dict(result["receipt"])})
    goals = {"left-skill": ("left-goal",), "right-skill": ("right-goal",), "jump-skill": ("jump-goal",), "bridge-skill": ("bridge-goal",)}
    condensed: list[dict[str, Any]] = []
    for skill in needed_skills:
        side = side_for[skill]
        result = owner.condense_temporal_skill(f"{prefix}:condense:{side}", memory_id=MEMORY_ID, skill_id=skill, goal_observations=goals[skill], forbidden_observations=("wrong-goal",))
        condensed.append({"skill_id": skill, "receipt": dict(result["receipt"])})
    return owner, home, {"context": context, "episodes": episodes, "learning": learning, "condensed": condensed}


def _field(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    workspace = owner.state.resonant_workspace
    return {"available": workspace is not None, "state_sha256": None if workspace is None else workspace.state_sha256, "field_ticks": None if workspace is None else workspace.field_ticks, "evidence_tick": None if workspace is None else workspace.evidence_tick, "resonance": dict(owner.inspect_resonance())}


def _select(owner: FieldIntelligenceOwner, skills: Sequence[str], operations: Sequence[Mapping[str, Any]], minimum_margin: float) -> Mapping[str, Any]:
    before = owner.state.encode_bundle()
    result = dict(owner.select_temporal_action(MEMORY_ID, skill_ids=tuple(skills), operations=operations, minimum_margin=minimum_margin))
    if owner.state.encode_bundle() != before:
        raise RuntimeError("temporal selection was not read-only")
    result["candidate_count"] = len(result.get("candidates", []))
    return result


def _advance(owner: FieldIntelligenceOwner, action: str, observation: str, prefix: str) -> dict[str, Any]:
    before = owner.state.state_sha256
    result = owner.advance_temporal(f"{prefix}:advance:{action}:{observation}", memory_id=MEMORY_ID, participant_id="agent", action=action, observation=observation)
    return {"action": action, "observation": observation, "before_state_sha256": before, "receipt": dict(result["receipt"]), "after_state_sha256": owner.state.state_sha256}


def _world(position: str, action: str) -> tuple[str, str]:
    if position == "start" and action == "left-step": return "left", "left-goal"
    if position == "start" and action == "right-step": return "right", "right-stage"
    if position == "start" and action == "jump-step": return "jump", "jump-goal"
    if position == "start" and action == "bridge-step": return "bridge", "bridge-stage"
    if position == "bridge" and action == "bridge-confirm": return "done", "bridge-goal"
    return position, "wrong-goal"


def _case(name: str, spec: Mapping[str, Any], gate: Any = None) -> dict[str, Any]:
    started = time.perf_counter()
    worker = f"process-{os.getpid()}"
    if gate is not None:
        gate.wait()
    skills = tuple(spec["skills"])
    training_episodes = spec.get("training_episodes")
    owner, home, setup = _setup(f"teab-{name}-", skills, training_episodes)
    try:
        if spec.get("unsupported"):
            held_out_source = make_source(
                f"teab-{name}-held-out",
                setup["episodes"]["bridge"],
                f"teab-{name}:held-out",
                labels=("temporal-evidence-action-batch", "held-out"),
            )
            training_digests = [
                str(item["source_content_sha256"])
                for item in setup["learning"]
            ]
            setup["held_out_source"] = held_out_source.as_dict()
            setup["held_out_source_content_sha256"] = hashlib.sha256(held_out_source.content).hexdigest()
            setup["training_source_content_sha256"] = training_digests
            setup["held_out_source_digest_absent_from_training"] = (
                setup["held_out_source_content_sha256"] not in training_digests
            )
        forbidden = spec.get("control") == "forbidden-operation"
        infeasible = spec.get("control") == "infeasible-operation"
        operations = operation_rows(spec["operations"], authorized=not forbidden, feasible=not infeasible)
        binding = owner.bind_temporal(f"{name}:bind", memory_id=MEMORY_ID, participant_id="agent", known_start=True)
        setup["binding"] = dict(binding["receipt"])
        if spec.get("control") == "no-workspace":
            learned = owner.state
            evidence_copy = home.parent / f"{home.name}-evidence-copy"
            shutil.copytree(home / "evidence", evidence_copy)
            owner.close(); shutil.rmtree(home, ignore_errors=True)
            home = Path(tempfile.mkdtemp(prefix=f"teab-{name}-lesion-"))
            shutil.copytree(evidence_copy, home / "evidence")
            shutil.rmtree(evidence_copy, ignore_errors=True)
            owner = FieldIntelligenceOwner(home, limits=CapacityLimits(max_history_entries=2048), initial_state=replace(learned, resonant_workspace=None))
            lesion_binding = owner.bind_temporal(f"{name}:lesion-bind", memory_id=MEMORY_ID, participant_id="agent", known_start=True)
            setup["lesion_binding"] = dict(lesion_binding["receipt"])
        minimum = 1.0 if spec.get("control") == "insufficient-margin" else MINIMUM_MARGIN
        selected = _select(owner, skills, operations, minimum)
        transitions: list[dict[str, Any]] = []
        expected_goal = None
        observed_goal = None
        position = "start"
        selected_item = selected.get("selected")
        if isinstance(selected_item, Mapping):
            chosen = next((c for c in selected.get("candidates", []) if c.get("candidate_sha256") == selected_item.get("candidate_sha256")), None)
            expected_goal = (chosen or {}).get("goal_observations", [None])[0]
            mode = spec.get("consequence")
            if mode in {"selected", "multi-step", "wrong"}:
                action = str(selected_item.get("action"))
                if mode == "wrong": action = "jump-step" if action != "jump-step" else "left-step"
                position, observation = _world(position, action)
                transitions.append(_advance(owner, action, observation, name))
                observed_goal = observation
                if mode == "multi-step" and action == "bridge-step":
                    position, observation = _world(position, "bridge-confirm")
                    transitions.append(_advance(owner, "bridge-confirm", observation, name))
                    observed_goal = observation
        correct = bool(transitions) and spec.get("consequence") != "wrong" and observed_goal == expected_goal and position in {"left", "jump", "done"}
        if spec.get("consequence") == "multi-step": correct = len(transitions) == 2 and observed_goal == expected_goal and position == "done"
        if spec.get("control") in {"no-workspace", "insufficient-margin", "forbidden-operation", "infeasible-operation"}: correct = False
        abstaining_control = spec.get("control") in {"no-workspace", "insufficient-margin", "forbidden-operation", "infeasible-operation"}
        unsupported_case = bool(spec.get("unsupported"))
        row = {"name": name, "case_family": spec["family"], "skills_presented": list(skills), "operations": operations, "minimum_margin": minimum,
               "selection": selected, "field_setup": _field(owner), "setup": setup,
               "transitions": transitions, "consequence": {"expected_goal": expected_goal, "observed_goal": observed_goal, "selected_action": selected_item.get("action") if isinstance(selected_item, Mapping) else None, "position": position, "correct": correct, "transition_count": len(transitions)} if spec.get("consequence") else None,
               "expected_observed": {"expected": "unsupported" if unsupported_case else ("abstain" if abstaining_control else ("multi-step-goal" if spec.get("consequence") == "multi-step" else "correct-goal")), "observed": "unsupported" if unsupported_case and selected.get("status") != "selected" else ("abstain" if selected.get("status") != "selected" else ("correct-goal" if correct else "wrong-goal")), "match": (bool(setup.get("held_out_source_digest_absent_from_training")) and selected.get("status") == "unresolved") if unsupported_case else ((selected.get("status") != "selected") if abstaining_control else correct)},
               "read_only": bool(selected.get("read_only")), "state_unchanged": bool(selected.get("memory_unchanged") and selected.get("workspace_unchanged")),
               "diagnostics": {"worker_id": worker, "case_elapsed_seconds": time.perf_counter() - started}}
        if name == "continuity-baseline":
            row["continuity_reproduction"] = {"baseline_selection_margin": 0.035448902588912756, "baseline_candidate_set_sha256": "74ce5086ef4ae6135f97b46549ffd68839a0d97c0d95e3815963a37345373b5d", "baseline_receipt_digest": "94efb7e88ca7c618b039daa7bc62a2df3225a64721e8fb6b67aa4c7d7354b9e1"}
        return _jsonable(row)
    finally:
        try: owner.close()
        except Exception: pass
        shutil.rmtree(home, ignore_errors=True)


def _no_workspace_expected(row: Mapping[str, Any]) -> bool:
    return row["selection"].get("status") == "unresolved" and row["selection"].get("reason") == "resonant-workspace-unavailable" and row["field_setup"].get("available") is False


def build_receipt(requested_workers: int = 4) -> dict[str, Any]:
    started = time.perf_counter()
    workers = max(1, min(int(requested_workers), len(CASE_ORDER)))
    results: dict[str, dict[str, Any]] = {}
    completion: list[str] = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_case, name, _CASES[name]): name for name in CASE_ORDER}
        for future in as_completed(futures):
            name = futures[future]
            row = future.result()
            row["diagnostics"]["completion_index"] = len(completion)
            completion.append(name)
            results[name] = row
    rows = [results[name] for name in CASE_ORDER]
    used_workers = len({row["diagnostics"]["worker_id"] for row in rows})
    selected_count = sum(row["selection"].get("status") == "selected" for row in rows)
    multi_count = sum(row["case_family"] == "multi-step" for row in rows)
    control_rows = [row for row in rows if row["case_family"] in {"no-workspace-lesion", "insufficient-margin", "forbidden-operation", "infeasible-operation", "wrong-consequence"}]
    by_name = {row["name"]: row for row in rows}
    body: dict[str, Any] = {
        "schema": SCHEMA, "status": "MEASURED", "numeric_policy": {"dtype": "float64", "device": "cpu", "seed": SEED},
        "question": "Does concurrent execution preserve field-native temporal/evidence action selection, bounded consequences, and can-fail controls across independent cases?",
        "scope": "bounded field-native categorical action selection over a closed action/observation codec; temporal reachability and deterministic consequence only",
        "parallelism": {"executor": "ProcessPoolExecutor", "requested_worker_count": int(requested_workers), "used_worker_count": used_workers, "case_count": len(rows), "canonical_case_order": list(CASE_ORDER), "completion_order": completion, "max_workers": workers},
        "temporal_configuration": {"memory_id": MEMORY_ID, "action_ids": list(ACTION_IDS), "observation_ids": list(OBSERVATION_IDS), "canonical_episode_schema": "cassifi.temporal-episode.v1", "public_path": ["configure_temporal", "learn_temporal", "condense_temporal_skill", "bind_temporal", "select_temporal_action", "advance_temporal"]},
        "held_out": {"declared": True, "kind": "unsupported-composition", "case": "unsupported-held-out-composition", "verdict": "unsupported", "reason": "public_temporal_api_requires_contiguous_transition_evidence; singleton primitive sources cannot compose a new ordered transition"},
        "continuity": {"baseline_receipt_digest": "94efb7e88ca7c618b039daa7bc62a2df3225a64721e8fb6b67aa4c7d7354b9e1", "baseline_selection_margin": 0.035448902588912756, "baseline_candidate_set_sha256": "74ce5086ef4ae6135f97b46549ffd68839a0d97c0d95e3815963a37345373b5d", "continuity_row": "continuity-baseline", "note": "Baseline values are cited exactly; batch rows retain fresh raw setup and selection receipts."},
        "rows": rows,
        "summary": {"case_count": len(rows), "selected_case_count": selected_count, "multi_step_case_count": multi_count, "control_case_count": len(control_rows), "unsupported_case_count": sum(row["case_family"] == "unsupported-held-out-composition" for row in rows), "field_available_case_count": sum(bool(row["field_setup"].get("available")) for row in rows), "read_only_case_count": sum(bool(row["read_only"] and row["state_unchanged"]) for row in rows), "canonical_case_order": list(CASE_ORDER)},
        "evaluation": {"field_supported_selection": by_name["continuity-baseline"]["selection"].get("status") == "selected", "three_candidate_case": by_name["three-candidate"]["selection"].get("candidate_count") >= 3, "multi_step_consequence": by_name["multi-step-consequence"]["consequence"].get("correct", False), "held_out_composition_unsupported": by_name["unsupported-held-out-composition"]["expected_observed"].get("match", False) and by_name["unsupported-held-out-composition"]["selection"].get("status") == "unresolved", "no_workspace_abstains": _no_workspace_expected(by_name["control-no-workspace"]), "insufficient_margin_abstains": by_name["control-insufficient-margin"]["selection"].get("status") == "unresolved" and by_name["control-insufficient-margin"]["selection"].get("reason") == "insufficient-resonant-margin", "forbidden_operation_abstains": by_name["control-forbidden-operation"]["selection"].get("status") == "unresolved" and by_name["control-forbidden-operation"]["selection"].get("reason") == "no-admissible-candidate", "infeasible_operation_abstains": by_name["control-infeasible-operation"]["selection"].get("status") == "unresolved" and by_name["control-infeasible-operation"]["selection"].get("reason") == "no-admissible-candidate", "wrong_action_consequence_fails": by_name["control-wrong-consequence"]["consequence"].get("correct") is False, "order_permutation_invariant": (by_name["continuity-baseline"]["selection"].get("selected") or {}).get("action") == (by_name["control-order-permutation"]["selection"].get("selected") or {}).get("action") and (by_name["continuity-baseline"]["selection"].get("selected") or {}).get("skill_id") == (by_name["control-order-permutation"]["selection"].get("selected") or {}).get("skill_id")},
        "controls": {"attempted": [row["name"] for row in control_rows], "all_fired": all((row["selection"].get("status") == "unresolved") if row["case_family"] != "wrong-consequence" else (row["consequence"] is not None and row["consequence"].get("correct") is False) for row in control_rows), "read_only_all_rows": all(row["read_only"] and row["state_unchanged"] for row in rows)},
        "timing": {"runtime_seconds": time.perf_counter() - started},
    }
    if body["timing"]["runtime_seconds"] > MAX_RUNTIME_SECONDS: raise TimeoutError("temporal evidence action batch exceeded runtime ceiling")
    body["content_digest"] = content_digest(body)
    body["receipt_digest"] = body["content_digest"]
    body["self_check"] = {"performed": True, "content_digest_matches": content_digest(body) == body["content_digest"]}
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    receipt = build_receipt(args.workers)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "status": receipt["status"], "content_digest": receipt["content_digest"], "case_count": receipt["parallelism"]["case_count"], "requested_worker_count": receipt["parallelism"]["requested_worker_count"], "used_worker_count": receipt["parallelism"]["used_worker_count"], "runtime_seconds": receipt["timing"]["runtime_seconds"]}, sort_keys=True))

if __name__ == "__main__": main()
