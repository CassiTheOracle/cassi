"""Probe whether the public temporal APIs synthesize an unseen ordered composition.

Two singleton primitive sources (A and B) are admitted independently into one
memory.  The public task path then requests A followed by B on one participant.
The runner does *not* treat task syntax as a composition result: the verdict is
``SUPPORTED`` only if B is actually proposed after A and the task completes.
With the current public learner B is expected to be unresolved at A's
post-transition state, so the measured verdict is honestly ``UNSUPPORTED``.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_field_atlas import AtlasState, canonical_json_bytes
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput

SCHEMA = "cassifi.temporal-composition-probe.v1"
DEFAULT_OUTPUT = Path("_diag/temporal-composition-probe/receipt.json")
SEED = 20260917
MAX_RUNTIME_SECONDS = 60.0
CONTEXT = {"world": "temporal-composition-probe", "split": "primitive-train-ordered-composition-held-out"}
MEMORY_ID = "primitive-memory"
PARTICIPANT_ID = "agent"
SKILLS = ("left-skill", "right-skill")
ACTIONS = ("left-step", "right-step", "idle")
OBSERVATIONS = ("left-goal", "right-goal", "quiet", "wrong-goal")
TRAINING = (
    ("left-skill", "left-step", "left-goal"),
    ("right-skill", "right-step", "right-goal"),
)
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def canonical(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): strip_timing(item) for key, item in value.items() if str(key) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(item) for item in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(value)).encode("utf-8")).hexdigest()


def make_source(source_id: str, action: str, observation: str) -> SourceInput:
    steps = [{"action": action, "observation": observation}]
    return SourceInput(
        source_id=source_id,
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": steps}),
        media_type="application/json", codec="utf-8", observed_timestamp=source_id,
        scope="temporal-composition-probe", claim_category="controlled-world-observation",
        fidelity="exact-record", labels=("temporal-composition-probe", "train"),
    )


def _allowed_actions(*, allow_right: bool) -> list[dict[str, str]]:
    actions = [
        {"participant_id": PARTICIPANT_ID, "action": "left-step"},
        {"participant_id": PARTICIPANT_ID, "action": "idle"},
    ]
    if allow_right:
        actions.insert(1, {"participant_id": PARTICIPANT_ID, "action": "right-step"})
    return actions


def _setup(prefix: str) -> tuple[FieldIntelligenceOwner, Path, dict[str, Any]]:
    home = Path(tempfile.mkdtemp(prefix=prefix))
    owner = FieldIntelligenceOwner(
        home,
        limits=CapacityLimits(max_history_entries=2048),
        initial_state=AtlasState(resonant_workspace=None),
    )
    owner.configure_temporal(
        f"{prefix}:configure", memory_id=MEMORY_ID, action_ids=ACTIONS,
        observation_ids=OBSERVATIONS, max_states=8, context=CONTEXT,
    )
    learning: list[dict[str, Any]] = []
    condensed: list[dict[str, Any]] = []
    for index, (skill_id, action, observation) in enumerate(TRAINING):
        source = make_source(f"{prefix}:source:{index}:{skill_id}", action, observation)
        learned = owner.learn_temporal(
            f"{prefix}:learn:{index}", memory_id=MEMORY_ID, source=source, context=CONTEXT,
        )
        condensed_result = owner.condense_temporal_skill(
            f"{prefix}:condense:{index}", memory_id=MEMORY_ID, skill_id=skill_id,
            goal_observations=(observation,), forbidden_observations=("wrong-goal",),
        )
        learning.append({
            "skill_id": skill_id, "action": action, "observation": observation,
            "source": source.as_dict(), "source_content_sha256": hashlib.sha256(source.content).hexdigest(),
            "receipt": dict(learned["receipt"]),
        })
        condensed.append({"skill_id": skill_id, "receipt": dict(condensed_result["receipt"])})
    bound = owner.bind_temporal(
        f"{prefix}:bind", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, known_start=True,
    )
    return owner, home, {"learning": learning, "condensed": condensed, "binding": dict(bound["receipt"])}


def _task_steps() -> list[dict[str, str]]:
    return [
        {"memory_id": MEMORY_ID, "participant_id": PARTICIPANT_ID, "skill_id": "left-skill"},
        {"memory_id": MEMORY_ID, "participant_id": PARTICIPANT_ID, "skill_id": "right-skill"},
    ]


def _proposal(owner: FieldIntelligenceOwner, operation_id: str, task_id: str, *, allow_right: bool) -> dict[str, Any]:
    result = owner.propose_temporal_task(
        operation_id, task_id=task_id, allowed_actions=_allowed_actions(allow_right=allow_right),
    )
    return {"result": dict(result), "view": dict(owner.inspect_temporal_task(task_id))}


def _run_row(name: str, *, allow_right: bool) -> dict[str, Any]:
    owner, home, setup = _setup(f"tcomp-{name}-")
    try:
        task_id = f"{name}-task"
        composed = owner.compose_temporal_task(
            f"{name}:compose", task_id=task_id, steps=_task_steps(), context=CONTEXT,
        )
        first = _proposal(owner, f"{name}:propose:first", task_id, allow_right=True)
        first_receipt = first["result"]["receipt"]
        first_proposal = first_receipt["proposal"]
        first_ack = owner.acknowledge_temporal_task(
            f"{name}:ack:first", task_id=task_id, proposal_id=first_proposal["proposal_id"],
            participant_id=first_proposal["participant_id"], action=first_proposal["action"],
            observation="left-goal",
        )
        second = _proposal(owner, f"{name}:propose:second", task_id, allow_right=allow_right)
        second_receipt = second["result"]["receipt"]
        second_proposal = second_receipt.get("proposal")
        second_ack = None
        if second_receipt.get("status") == "proposed" and isinstance(second_proposal, Mapping):
            second_ack = dict(owner.acknowledge_temporal_task(
                f"{name}:ack:second", task_id=task_id, proposal_id=second_proposal["proposal_id"],
                participant_id=second_proposal["participant_id"], action=second_proposal["action"],
                observation="right-goal",
            ))
        final_view = dict(owner.inspect_temporal_task(task_id))
        return {
            "name": name, "task_id": task_id, "allow_right": allow_right, "training": setup,
            "composition": {"receipt": dict(composed["receipt"]), "steps": _task_steps()},
            "execution": {"first": first, "first_ack": dict(first_ack), "second": second,
                          "second_ack": second_ack, "final_view": final_view,
                          "selected_after_first": second_receipt.get("status") == "proposed" and second_receipt.get("action") == "right-step"},
            "status": final_view["status"],
        }
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def _contains_ordered(steps: Sequence[Mapping[str, str]], ordered: Sequence[Mapping[str, str]]) -> bool:
    if len(steps) < len(ordered):
        return False
    return any(list(steps[index:index + len(ordered)]) == list(ordered)
               for index in range(len(steps) - len(ordered) + 1))


def _provenance(row: Mapping[str, Any]) -> dict[str, Any]:
    sources = row["training"]["learning"]
    ordered = [
        {"action": "left-step", "observation": "left-goal"},
        {"action": "right-step", "observation": "right-goal"},
    ]
    source_steps = []
    for item in sources:
        raw = base64.b64decode(item["source"]["content_base64"], validate=True)
        payload = json.loads(raw.decode("utf-8"))
        source_steps.append({"source_id": item["source"]["source_id"], "steps": payload["steps"]})
    source_digests = [str(item["source_content_sha256"]) for item in sources]
    descriptor = {"task_id": row["task_id"], "ordered_skills": list(SKILLS), "ordered_actions": ordered}
    provenance_digest = hashlib.sha256(canonical({"source_digests": source_digests, "held_out": descriptor}).encode()).hexdigest()
    return {
        "training_source_content_sha256": source_digests,
        "training_source_steps": source_steps,
        "held_out_descriptor": descriptor,
        "held_out_descriptor_sha256": hashlib.sha256(canonical(descriptor).encode()).hexdigest(),
        "ordered_composition_absent_from_training": all(not _contains_ordered(item["steps"], ordered) for item in source_steps),
        "provenance_digest": provenance_digest,
        "digest_scope": "training source content digests plus held-out ordered descriptor; independent of receipt content digest",
    }


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    unsupported = _run_row("unseen-order-unsupported", allow_right=True)
    denied = _run_row("negative-denied-second", allow_right=False)
    provenance = _provenance(unsupported)
    unsupported_second = unsupported["execution"]["second"]["result"]["receipt"]
    denied_second = denied["execution"]["second"]["result"]["receipt"]
    evaluation = {
        "primitive_sources_are_separate": len(set(provenance["training_source_content_sha256"])) == 2,
        "held_out_composition_absent_from_training": provenance["ordered_composition_absent_from_training"],
        "first_primitive_selected": unsupported["execution"]["first"]["result"]["receipt"]["status"] == "proposed" and unsupported["execution"]["first"]["result"]["receipt"]["action"] == "left-step",
        "second_primitive_selected_after_first": unsupported["execution"]["selected_after_first"],
        "ordered_composition_supported": unsupported["status"] == "complete" and unsupported["execution"]["selected_after_first"],
        "ordered_composition_unresolved": unsupported_second["status"] == "unresolved" and unsupported_second.get("action") is None and unsupported["status"] != "complete",
        "negative_denied_second_abstains": denied_second["status"] == "unresolved" and denied_second.get("action") is None and denied["status"] != "complete",
    }
    verdict = "SUPPORTED" if evaluation["ordered_composition_supported"] else "UNSUPPORTED"
    body: dict[str, Any] = {
        "schema": SCHEMA, "status": "MEASURED", "verdict": verdict,
        "numeric_policy": {"dtype": "float64", "device": "cpu", "seed": SEED},
        "question": "Can public temporal task composition execute an ordered combination of separately learned primitive skills that no training source contains?",
        "scope": "Two singleton primitive sources in one temporal memory, one public ordered task, and a proposal-denial can-fail control; task syntax alone is not counted as composition support.",
        "public_path": ["configure_temporal", "learn_temporal", "condense_temporal_skill", "bind_temporal", "compose_temporal_task", "propose_temporal_task", "acknowledge_temporal_task"],
        "context": CONTEXT,
        "training_contract": "Each source contains exactly one primitive action/observation pair; the tested left-then-right ordered pair is absent from every source.",
        "provenance": provenance,
        "rows": [unsupported, denied],
        "summary": {"row_count": 2, "training_source_count": len(provenance["training_source_content_sha256"]), "unsupported_row_status": unsupported["status"], "negative_row_status": denied["status"]},
        "evaluation": evaluation,
        "controls": {"attempted": ["negative-denied-second"], "can_fail": evaluation["negative_denied_second_abstains"], "provenance_separation": evaluation["primitive_sources_are_separate"] and evaluation["held_out_composition_absent_from_training"]},
        "limitations": ["The public task API sequences existing skill bindings; it does not by itself synthesize a new skill policy at the destination state.", "A SUPPORTED verdict requires the second primitive to be selected after the first acknowledgment and the task to complete; the measured singleton-source arm is therefore UNSUPPORTED when B is unresolved."],
        "timing": {"runtime_seconds": float(time.perf_counter() - started)},
    }
    body["content_digest"] = content_digest(body)
    body["receipt_digest"] = body["content_digest"]
    body["self_check"] = {"performed": True, "content_digest_matches": content_digest(body) == body["content_digest"]}
    if time.perf_counter() - started > MAX_RUNTIME_SECONDS:
        raise TimeoutError("temporal composition probe exceeded runtime ceiling")
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": SCHEMA, "status": receipt["status"], "verdict": receipt["verdict"], "content_digest": receipt["content_digest"], "rows": len(receipt["rows"]), "runtime_seconds": receipt["timing"]["runtime_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
