"""Measure field-native temporal/evidence action selection and one bounded consequence."""
from __future__ import annotations

import argparse
from dataclasses import replace
import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import AtlasState, canonical_json_bytes
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput

SCHEMA = "cassifi.temporal-evidence-action-selection.v1"
DEFAULT_OUTPUT = Path("_diag/temporal-evidence-action-selection/exploration.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 180.0
MINIMUM_MARGIN = 1e-12
MEMORY_ID = "evidence-actions"
CONTEXT = {"world": "bounded-two-goal", "split": "temporal-evidence-action-selection"}
ACTION_IDS = ("left-step", "right-step", "right-confirm", "idle")
OBSERVATION_IDS = ("left-goal", "right-stage", "right-goal", "quiet", "wrong-goal")
SKILL_IDS = ("left-skill", "right-skill")
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if str(key) not in TIMING_KEYS}
    if isinstance(value, (list, tuple)):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(strip_timing(value)).encode("utf-8")).hexdigest()


def make_source(source_id: str, steps: Sequence[Mapping[str, str]], timestamp: str) -> SourceInput:
    return SourceInput(
        source_id=source_id,
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": list(steps)}),
        media_type="application/json", codec="utf-8", observed_timestamp=timestamp,
        scope="temporal-evidence-action-selection", claim_category="controlled-world-observation",
        fidelity="exact-record", labels=("temporal-evidence-action-selection", "train"),
    )


def operation_rows() -> list[dict[str, Any]]:
    # Fixed protocol is limited to independently safe world operations; it is
    # not a cue-to-action mapping and does not select the measured action.
    return [
        {"action": "left-step", "authorized": True, "feasible": True, "represented_forbidden": False},
        {"action": "right-step", "authorized": True, "feasible": True, "represented_forbidden": False},
    ]
def operation_rows_for(order: Sequence[str]) -> list[dict[str, Any]]:
    # Present operations in the same permutation as skills; selection itself
    # remains entirely inside the owner.
    rows = operation_rows()
    return rows if tuple(order) == SKILL_IDS else list(reversed(rows))


def forbidden_operation_rows() -> list[dict[str, Any]]:
    return [{**row, "authorized": False} for row in operation_rows()]




def world_step(position: str, action: str) -> tuple[str, str]:
    if action == "left-step" and position == "start":
        return "left", "left-goal"
    if action == "right-step" and position == "start":
        return "right", "right-goal"
    return position, "wrong-goal"


def _setup(prefix: str) -> tuple[FieldIntelligenceOwner, Path, dict[str, Any]]:
    home = Path(tempfile.mkdtemp(prefix=prefix))
    owner = FieldIntelligenceOwner(home, limits=CapacityLimits(max_history_entries=2048),
                                   initial_state=AtlasState(resonant_workspace=None))
    owner.configure_temporal(f"{prefix}:configure", memory_id=MEMORY_ID, action_ids=ACTION_IDS,
                             observation_ids=OBSERVATION_IDS, max_states=16, context=CONTEXT)
    episodes = {
        "left": [{"action": "left-step", "observation": "left-goal"}],
        "right": [{"action": "right-step", "observation": "right-stage"},
                  {"action": "right-confirm", "observation": "right-goal"}],
    }
    learning: list[Mapping[str, Any]] = []
    for side in ("left", "right"):
        source = make_source(f"{prefix}:episode:{side}", episodes[side], f"{prefix}:{side}")
        result = owner.learn_temporal(f"{prefix}:learn:{side}", memory_id=MEMORY_ID, source=source, context=CONTEXT)
        learning.append({"side": side, "source": source.as_dict(), "receipt": dict(result["receipt"])})
    condensed: list[Mapping[str, Any]] = []
    for side, skill in zip(("left", "right"), SKILL_IDS, strict=True):
        result = owner.condense_temporal_skill(f"{prefix}:condense:{side}", memory_id=MEMORY_ID,
                                               skill_id=skill, goal_observations=(f"{side}-goal",),
                                               forbidden_observations=("wrong-goal",))
        condensed.append({"side": side, "skill_id": skill, "receipt": dict(result["receipt"])})
    return owner, home, {"learning": learning, "condensed": condensed, "episodes": episodes}


def _field_observation(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    workspace = owner.state.resonant_workspace
    return {"available": workspace is not None,
            "state_sha256": None if workspace is None else workspace.state_sha256,
            "field_ticks": None if workspace is None else workspace.field_ticks,
            "evidence_tick": None if workspace is None else workspace.evidence_tick,
            "resonance": dict(owner.inspect_resonance())}


def _field_signal(owner: FieldIntelligenceOwner, skill_id: str) -> list[float]:
    result = owner.inspect_temporal(MEMORY_ID, skill_id=skill_id)
    return [float(value) for value in result["skill_pool_signal"]["pool_signal"]]


def _select(owner: FieldIntelligenceOwner, skill_order: Sequence[str],
            operations: Sequence[Mapping[str, Any]], minimum_margin: float = MINIMUM_MARGIN) -> Mapping[str, Any]:
    before = owner.state.encode_bundle()
    result = owner.select_temporal_action(MEMORY_ID, skill_ids=tuple(skill_order),
                                           operations=operations, minimum_margin=minimum_margin)
    if owner.state.encode_bundle() != before:
        raise RuntimeError("temporal selection was not read-only")
    return dict(result)


def _transition(owner: FieldIntelligenceOwner, action: str, *, prefix: str, observation: str) -> Mapping[str, Any]:
    before_state = owner.state.state_sha256
    result = owner.advance_temporal(f"{prefix}:advance", memory_id=MEMORY_ID, participant_id="agent",
                                    action=action, observation=observation)
    return {"action": action, "observation": observation, "before_state_sha256": before_state,
            "receipt": dict(result["receipt"]), "after_state_sha256": owner.state.state_sha256}


def _arm(name: str, *, permutation: Sequence[str] | None = None,
         consequence_mode: str | None = None,
         operations: Sequence[Mapping[str, Any]] | None = None,
         minimum_margin: float = MINIMUM_MARGIN) -> dict[str, Any]:
    # Fixed provenance labels make independent permutation arms comparable;
    # each still uses a fresh isolated owner and checkpoint home.
    owner, home, setup = _setup("tea-shared-")
    try:
        binding = owner.bind_temporal(f"{name}:bind", memory_id=MEMORY_ID, participant_id="agent", known_start=True)
        setup = {**setup, "binding": dict(binding["receipt"])}
        order = tuple(permutation or SKILL_IDS)
        field = _field_observation(owner)
        field["skill_pool_signals"] = {skill: _field_signal(owner, skill) for skill in SKILL_IDS}
        presented_operations = list(operations or operation_rows_for(order))
        selected = _select(owner, order, presented_operations, minimum_margin)
        consequence = None
        if consequence_mode is not None and selected["status"] == "selected":
            selected_action = selected["selected"]["action"]
            candidate = next(
                candidate for candidate in selected["candidates"]
                if candidate["candidate_sha256"] == selected["selected"]["candidate_sha256"]
            )
            expected_goal = candidate["goal_observations"][0]
            action = selected_action
            if consequence_mode == "wrong":
                action = "right-step" if selected_action == "left-step" else "left-step"
            position, observed = world_step("start", action)
            transition = _transition(owner, action, prefix=name, observation=observed)
            consequence = {"position": position, "observation": observed,
                           "expected_goal_observation": expected_goal,
                           "selected_action": selected_action, "action_applied": action,
                           "goal_progress": position != "start",
                           "correct_first_transition": position in {"left", "right"} and
                           action == selected_action and observed == expected_goal and observed != "wrong-goal",
                           "forbidden_outcome": observed == "wrong-goal", "transition": transition}
        return {"name": name, "skill_order": list(order), "operations": presented_operations,
                "minimum_margin": minimum_margin,
                "presentation_order_sha256": hashlib.sha256(canonical_json(list(order)).encode("utf-8")).hexdigest(),
                "selection": selected, "field_setup": field, "consequence": consequence, "setup": setup}
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)
def _no_workspace_arm() -> dict[str, Any]:
    source_owner, source_home, setup = _setup("tea-no-workspace-source-")
    try:
        learned_state = source_owner.state
        home = Path(tempfile.mkdtemp(prefix="tea-no-workspace-lesion-"))
        shutil.copytree(source_home / "evidence", home / "evidence")
    finally:
        source_owner.close()
        shutil.rmtree(source_home, ignore_errors=True)
    owner = FieldIntelligenceOwner(
        home,
        limits=CapacityLimits(max_history_entries=2048),
        initial_state=replace(learned_state, resonant_workspace=None),
    )
    try:
        binding = owner.bind_temporal("control-no-workspace:bind", memory_id=MEMORY_ID,
                                      participant_id="agent", known_start=True)
        field = _field_observation(owner)
        selected = _select(owner, SKILL_IDS, operation_rows())
        return {"name": "control-no-workspace", "skill_order": list(SKILL_IDS),
                "operations": operation_rows(), "minimum_margin": MINIMUM_MARGIN,
                "presentation_order_sha256": hashlib.sha256(canonical_json(list(SKILL_IDS)).encode("utf-8")).hexdigest(),
                "selection": selected, "field_setup": field, "consequence": None,
                "setup": {**setup, "binding": dict(binding["receipt"]),
                          "lesion": "dataclasses.replace(learned AtlasState, resonant_workspace=None)"}}
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)




def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    rows = [
        _arm("held-out-supported", permutation=("right-skill", "left-skill"), consequence_mode="selected"),
        _arm("held-out-supported-reversed", permutation=("left-skill", "right-skill"), consequence_mode="selected"),
        _no_workspace_arm(),
        _arm("control-insufficient-margin", minimum_margin=1.0),
        _arm("control-forbidden-operation", operations=forbidden_operation_rows()),
        _arm("control-wrong-consequence", permutation=("right-skill", "left-skill"), consequence_mode="wrong"),
    ]
    supported, reversed_row, no_field, insufficient, forbidden, wrong = rows
    body: dict[str, Any] = {
        "schema": SCHEMA, "status": "MEASURED", "numeric_policy": {"dtype": "float64", "device": "cpu", "seed": SEED},
        "question": "Can live resonant compatibility of condensed temporal/evidence skills select an action with a positive margin and produce one correct bounded temporal consequence?",
        "scope": "field-native temporal/evidence action selection and one bounded consequence; no language or world generality",
        "temporal_configuration": {"memory_id": MEMORY_ID, "context": CONTEXT, "action_ids": list(ACTION_IDS),
                                   "observation_ids": list(OBSERVATION_IDS), "skill_ids": list(SKILL_IDS),
                                   "canonical_episode_schema": "cassifi.temporal-episode.v1"},
        "protocol": {
            "selection": "FieldIntelligenceOwner.select_temporal_action over condensed skill candidates and declared safe operations; selection is read-only and selected only when resonant compatibility margin > minimum_margin.",
            "minimum_margin": MINIMUM_MARGIN,
            "field_support": "The measured arm uses only public configure_temporal, learn_temporal, condense_temporal_skill, and select_temporal_action; the selector reads the live workspace produced by temporal learning.",
            "consequence": "The selected action is applied to a deterministic start-state world and admitted through FieldIntelligenceOwner.advance_temporal.",
            "abstention": "No selected action and no advance_temporal when the resonant workspace is unavailable (isolated AtlasState lesion), when the field has no admissible operation, or when the margin is insufficient.",
            "measured_controller": "No fixed cue-to-action table; action identity comes from learned SourceInput temporal episodes and condensed skill candidates.",
        },
        "held_out": {"kind": "presentation-permutation", "declared": True,
                     "orders": [list(supported["skill_order"]), list(reversed_row["skill_order"])],
                     "selection_must_be_order_invariant": True},
        "rows": rows,
        "evaluation": {
            "field_supported_selection": supported["selection"]["status"] == "selected" and supported["selection"]["reason"] == "resonant-compatibility",
            "held_out_consequence": bool(supported["consequence"] and supported["consequence"]["correct_first_transition"]),
            "presentation_order_invariant": reversed_row["selection"]["selected"] == supported["selection"]["selected"],
            "no_workspace_abstains": no_field["selection"]["status"] == "unresolved" and no_field["selection"]["reason"] == "resonant-workspace-unavailable" and no_field["field_setup"]["available"] is False and no_field["consequence"] is None,
            "insufficient_margin_abstains": insufficient["selection"]["status"] == "unresolved" and insufficient["selection"]["reason"] == "insufficient-resonant-margin" and insufficient["consequence"] is None,
            "forbidden_operation_abstains": forbidden["selection"]["status"] == "unresolved" and forbidden["consequence"] is None,
            "wrong_action_consequence_fails": bool(wrong["consequence"] and not wrong["consequence"]["correct_first_transition"]),
        },
        "controls": {
            "attempted": ["control-no-workspace", "control-insufficient-margin", "control-forbidden-operation", "control-wrong-consequence"],
            "no_workspace": {"fired": no_field["selection"]["status"] == "unresolved" and no_field["selection"]["reason"] == "resonant-workspace-unavailable", "abstained_without_transition": no_field["consequence"] is None, "field_available": no_field["field_setup"]["available"]},
            "insufficient_margin": {"fired": insufficient["selection"]["status"] == "unresolved", "threshold": insufficient["minimum_margin"]},
            "forbidden_operation": {"fired": forbidden["selection"]["status"] == "unresolved" and forbidden["selection"]["selected"] is None},
            "wrong_consequence": {"fired": bool(wrong["consequence"] and not wrong["consequence"]["correct_first_transition"])},
            "presentation_permutation": {"fired": reversed_row["selection"]["selected"] == supported["selection"]["selected"] and reversed_row["selection"]["candidate_set_sha256"] == supported["selection"]["candidate_set_sha256"] and reversed_row["presentation_order_sha256"] != supported["presentation_order_sha256"]},
            "read_only": {"all_rows": all(row["selection"]["read_only"] and row["selection"]["memory_unchanged"] and row["selection"]["workspace_unchanged"] for row in rows)},
        },
        "limitations": ["One two-action temporal memory and one deterministic start-state consequence are measured; this does not establish language understanding, broad planning, or general world utility.",
                        "The measured arm uses public owner temporal/evidence APIs. The no-workspace control uses an isolated public owner initialized from the learned AtlasState with resonant_workspace removed; it does not contaminate measured arms.",
                        "The held-out claim is presentation permutation invariance over the same condensed skills, not an independent task distribution."],
        "timing": {"runtime_seconds": float(time.perf_counter() - started)},
    }
    if time.perf_counter() - started > MAX_RUNTIME_SECONDS:
        raise TimeoutError("temporal evidence action selection exceeded runtime ceiling")
    body["content_digest"] = content_digest(body)
    body["receipt_digest"] = body["content_digest"]
    body["self_check"] = {"performed": True, "content_digest_matches": content_digest(body) == body["content_digest"]}
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "status": receipt["status"], "content_digest": receipt["content_digest"],
                      "rows": len(receipt["rows"]), "runtime_seconds": receipt["timing"]["runtime_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
