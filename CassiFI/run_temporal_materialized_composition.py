"""Opt-in field-owned state-conditioned temporal composition probe.

The frozen temporal-composition probe remains the unsupported baseline. This
probe explicitly reads a derived proposal, then commits one observed B outcome
through the owner. Only the commit writes canonical TemporalField planes.
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
from typing import Any, Mapping

from cassi_field_atlas import AtlasState, canonical_json_bytes
from cassi_field_owner import CapacityLimits, FieldIntelligenceOwner, SourceInput

SCHEMA = "cassifi.temporal-materialized-composition.v1"
DEFAULT_OUTPUT = Path("_diag/temporal-materialized-composition/receipt.json")
CONTEXT = {"world": "temporal-composition-probe", "split": "primitive-train-ordered-composition-held-out"}
MEMORY_ID = "primitive-memory"
PARTICIPANT_ID = "agent"
ACTIONS = ("left-step", "right-step", "idle")
OBSERVATIONS = ("left-goal", "right-goal", "quiet", "wrong-goal")
TRAINING = (("left-step", "left-goal"), ("right-step", "right-goal"))
TIMING_KEYS = frozenset({"runtime_seconds", "elapsed_seconds", "content_digest", "receipt_digest", "self_check"})


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def canonical(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def strip_timing(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(k): strip_timing(v) for k, v in value.items() if str(k) not in TIMING_KEYS}
    if isinstance(value, list):
        return [strip_timing(v) for v in value]
    return value


def content_digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical(strip_timing(value)).encode()).hexdigest()


def source(source_id: str, action: str, observation: str) -> SourceInput:
    return SourceInput(
        source_id=source_id,
        content=canonical_json_bytes({"schema": "cassifi.temporal-episode.v1", "steps": [{"action": action, "observation": observation}]}),
        media_type="application/json", codec="utf-8", observed_timestamp=source_id,
        scope="temporal-materialized-composition", claim_category="controlled-world-observation",
        fidelity="exact-record", labels=("temporal-materialized-composition", "train"),
    )


def setup(prefix: str) -> tuple[FieldIntelligenceOwner, Path, dict[str, Any]]:
    home = Path(tempfile.mkdtemp(prefix=prefix))
    owner = FieldIntelligenceOwner(home, limits=CapacityLimits(max_history_entries=2048), initial_state=AtlasState(resonant_workspace=None))
    owner.configure_temporal(f"{prefix}:configure", memory_id=MEMORY_ID, action_ids=ACTIONS, observation_ids=OBSERVATIONS, max_states=8, context=CONTEXT)
    learned, condensed = [], []
    for index, (action, observation) in enumerate(TRAINING):
        item = source(f"{prefix}:source:{index}", action, observation)
        result = owner.learn_temporal(f"{prefix}:learn:{index}", memory_id=MEMORY_ID, source=item, context=CONTEXT)
        skill = "left-skill" if action == "left-step" else "right-skill"
        condensed_result = owner.condense_temporal_skill(f"{prefix}:condense:{index}", memory_id=MEMORY_ID, skill_id=skill, goal_observations=(observation,), forbidden_observations=("wrong-goal",))
        learned.append({"action": action, "observation": observation, "source": item.as_dict(), "source_content_sha256": hashlib.sha256(item.content).hexdigest(), "receipt": dict(result["receipt"])})
        condensed.append({"skill_id": skill, "receipt": dict(condensed_result["receipt"])})
    bound = owner.bind_temporal(f"{prefix}:bind", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, known_start=True)
    return owner, home, {"learning": learned, "condensed": condensed, "binding": dict(bound["receipt"])}


def run_row(name: str, *, observation: str = "right-goal", action: str = "right-step") -> dict[str, Any]:
    owner, home, setup_receipts = setup(f"tmat-{name}-")
    try:
        before = dict(owner.inspect_temporal(MEMORY_ID, action=action, participant_id=PARTICIPANT_ID))
        left = dict(owner.advance_temporal(f"{name}:left", memory_id=MEMORY_ID, participant_id=PARTICIPANT_ID, action="left-step", observation="left-goal")["receipt"])
        proposal = dict(owner.synthesize_temporal_transition(memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID))
        precommit = owner.inspect_temporal(MEMORY_ID, action=action, participant_id=PARTICIPANT_ID)
        prior_state = owner.state.state_sha256
        commit = owner.materialize_temporal_transition(
            f"{name}:materialize", memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID,
            action=action, observation=observation, hypothesis_sha256=proposal["hypothesis_sha256"], expected_state_sha256=prior_state,
        )
        receipt = dict(commit["receipt"])
        replay_denied = None
        try:
            owner.materialize_temporal_transition(
                f"{name}:materialize", memory_id=MEMORY_ID, skill_id="right-skill", participant_id=PARTICIPANT_ID,
                action=action, observation="quiet", hypothesis_sha256=proposal["hypothesis_sha256"],
                expected_state_sha256=prior_state,
            )
        except Exception as exc:
            replay_denied = type(exc).__name__ + ": " + str(exc)
        after = dict(owner.inspect_temporal(MEMORY_ID, action=action, participant_id=PARTICIPANT_ID))
        return {"name": name, "training": setup_receipts, "before": before, "left": left, "proposal": proposal, "precommit": precommit, "materialization": receipt, "replay_denied": replay_denied, "after": after, "status": "SUPPORTED"}
    finally:
        owner.close()
        shutil.rmtree(home, ignore_errors=True)


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    success = run_row("supported")
    denied = None
    try:
        denied = run_row("mismatch", observation="right-goal", action="idle")
    except Exception as exc:
        denied = {"status": "DENIED", "error": type(exc).__name__ + ": " + str(exc)}
    body = {"schema": SCHEMA, "status": "MEASURED", "verdict": success["status"], "rows": [success, denied], "summary": {"held_out_training_edge": True, "proposal_is_derived_only": success["proposal"]["canonical_support"] is False, "field_digest_changed": success["materialization"]["previous_state_sha256"] != success["materialization"]["state_sha256"], "successful_materialization": success["materialization"]["supported"] is True, "mismatch_denied": denied.get("status") == "DENIED"}, "timing": {"runtime_seconds": time.perf_counter() - started}}
    body["content_digest"] = content_digest(body)
    body["receipt_digest"] = hashlib.sha256(canonical(strip_timing(body)).encode()).hexdigest()
    body["self_check"] = body["content_digest"] == content_digest(body)
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    receipt = build_receipt()
    if receipt["timing"]["runtime_seconds"] > 90:
        raise TimeoutError("materialized composition probe exceeded runtime ceiling")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema": receipt["schema"], "status": receipt["status"], "verdict": receipt["verdict"], "content_digest": receipt["content_digest"], "runtime_seconds": receipt["timing"]["runtime_seconds"]}, sort_keys=True))


if __name__ == "__main__":
    main()
