from __future__ import annotations

import hashlib
import json
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from cassi_qi_bootstrap import canonical_hash
from cassi_grounded_language import make_grounded_action_command
from cassi_persistent_provider import PersistentFieldProvider, ProviderConfig
from cassi_qi_world import DeterministicQiWorld


_ROOT = Path(__file__).resolve().parent
_SEED = 20260831
_SESSION_ID = "grounded-counterflow-deliberation"
_SEMANTIC_KIND = "qi-world-state"
_PHI_CONFIG = _ROOT / "configs" / "cassi-phi-harmonic-language.json"
_CORPUS_CHECKPOINT = (
    _ROOT / "artifacts" / "cassi-phi-harmonic-language" / "field-state.pt"
)
_BRANCHES = {
    "north-west": (
        "action.gaze-left",
        "action.gaze-up",
        "action.gaze-left",
    ),
    "south-east": (
        "action.gaze-right",
        "action.gaze-down",
        "action.gaze-right",
    ),
}


def _world() -> DeterministicQiWorld:
    return DeterministicQiWorld(seed=_SEED, session_id=_SESSION_ID)


def _identity(world: DeterministicQiWorld) -> dict[str, Any]:
    record_id = f"{world.world_id}:{world.episode_id}:state"
    revision = world.state_sha256
    encoded = json.dumps(
        [
            "cassicore.mnemic.counterflow-address.v1",
            record_id,
            revision,
            0,
            0,
            _SEMANTIC_KIND,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "record_id": record_id,
        "address": hashlib.sha256(encoded).digest()[:16].hex(),
        "revision": revision,
        "start_byte": 0,
        "end_byte": 0,
        "semantic_kind": _SEMANTIC_KIND,
    }


def _history_free_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    body = {
        key: value
        for key, value in snapshot.items()
        if key != "snapshot_sha256"
    }
    body["tick_log"] = []
    return {
        **body,
        "snapshot_sha256": canonical_hash(body, "cassi.qi-world-snapshot.v1"),
    }


def _observe_fragments(
    name: str,
    actions: Sequence[str],
    *,
    field_state_sha256: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[int]]:
    holdout_world = _world()
    holdout_states = [_identity(holdout_world)]
    holdout_snapshots = [holdout_world.snapshot()]
    for action_id in actions:
        acknowledgment = holdout_world.step(
            make_grounded_action_command(
                holdout_world,
                action_id,
                field_state_sha256=field_state_sha256,
            )
        )
        if acknowledgment.status != "applied":
            raise RuntimeError(f"holdout action {action_id} was not applied")
        holdout_states.append(_identity(holdout_world))
        holdout_snapshots.append(holdout_world.snapshot())

    observations: list[dict[str, Any]] = []
    source_action_counts: list[int] = []
    for position, action_id in enumerate(actions):
        source_world = _world()
        source_world.restore(_history_free_snapshot(holdout_snapshots[position]))
        if source_world.snapshot()["tick_log"]:
            raise RuntimeError("training fragment source retained holdout action history")
        before = _identity(source_world)
        acknowledgment = source_world.step(
            make_grounded_action_command(
                source_world,
                action_id,
                field_state_sha256=field_state_sha256,
            )
        )
        if acknowledgment.status != "applied":
            raise RuntimeError(f"grounded fragment {action_id} was not applied")
        after = _identity(source_world)
        if (
            before["revision"] != holdout_states[position]["revision"]
            or after["revision"] != holdout_states[position + 1]["revision"]
        ):
            raise RuntimeError("isolated fragment does not match its held-out edge")
        source_action_count = len(source_world.snapshot()["tick_log"])
        if source_action_count != 1:
            raise RuntimeError("a training source contains more than one action")
        source_action_counts.append(source_action_count)
        event_id = hashlib.sha256(
            f"{name}:{position}:{before['revision']}:{action_id}:{after['revision']}".encode(
                "utf-8"
            )
        ).hexdigest()
        observations.append(
            {
                "id": event_id,
                "before": before,
                "after": after,
                "symbol": action_id,
                "outcome": "completed",
                "action": {
                    "id": action_id,
                    "kind": action_id,
                    "required_authority": 1.0,
                    "reversible": True,
                },
            }
        )
    return observations, holdout_states, source_action_counts


def _trajectory(start: dict[str, Any], goal: dict[str, Any]) -> list[dict[str, Any]]:
    unknown = {
        **start,
        "mask": [0.0, 0.0, 0.0, 0.0],
        "authority": 1.0,
        "required": False,
    }
    return [
        {
            **start,
            "mask": [1.0, 1.0, 1.0, 1.0],
            "authority": 1.0,
            "required": True,
        },
        dict(unknown),
        dict(unknown),
        {
            **goal,
            "mask": [1.0, 1.0, 1.0, 1.0],
            "authority": 1.0,
            "required": True,
        },
    ]


def _request(
    observations: Sequence[dict[str, Any]],
    start: dict[str, Any],
    goal: dict[str, Any],
) -> dict[str, Any]:
    return {
        "mode": "plan",
        "observations": list(observations),
        "trajectory": _trajectory(start, goal),
        "policy": {
            "eligible_observation_ids": [item["id"] for item in observations],
            "permitted_action_kinds": sorted(
                {str(item["action"]["kind"]) for item in observations}
            ),
            "authority": 1.0,
            "authorization_path": [
                "thalamus:grounded-deliberation",
                "owner:execute-separately",
            ],
        },
    }


def _execute(actions: Sequence[str], *, field_state_sha256: str) -> dict[str, Any]:
    world = _world()
    for action_id in actions:
        world.step(
            make_grounded_action_command(
                world,
                action_id,
                field_state_sha256=field_state_sha256,
            )
        )
    return _identity(world)


def _run(
    provider: PersistentFieldProvider,
    *,
    primary_field_sha256: str,
) -> dict[str, Any]:
    observations: list[dict[str, Any]] = []
    branch_states: dict[str, list[dict[str, Any]]] = {}
    branch_observation_ids: dict[str, list[str]] = {}
    source_action_counts: list[int] = []
    for name, actions in _BRANCHES.items():
        branch_observations, states, branch_source_counts = _observe_fragments(
            name,
            actions,
            field_state_sha256=primary_field_sha256,
        )
        source_action_counts.extend(branch_source_counts)
        observations.extend(branch_observations)
        branch_states[name] = states
        branch_observation_ids[name] = [
            str(observation["id"]) for observation in branch_observations
        ]
    observations.sort(key=lambda observation: str(observation["id"]))
    fragment_request_symbols = [
        str(observation["symbol"]) for observation in observations
    ]
    for target_actions in _BRANCHES.values():
        width = len(target_actions)
        if any(
            tuple(fragment_request_symbols[offset : offset + width])
            == tuple(target_actions)
            for offset in range(len(fragment_request_symbols) - width + 1)
        ):
            raise RuntimeError("a planning request contains an ordered target sequence")
    if not source_action_counts or max(source_action_counts) != 1:
        raise RuntimeError("training sources are not isolated one-edge fragments")

    starts = {states[0]["revision"] for states in branch_states.values()}
    if len(starts) != 1:
        raise RuntimeError("counterfactual branches must share one exact start state")
    start = next(iter(branch_states.values()))[0]

    commit_receipts: list[dict[str, Any]] = []
    last_commit_request: dict[str, Any] | None = None
    for observation in observations:
        before = observation["before"]
        after = observation["after"]
        last_commit_request = {
            "user": _SESSION_ID,
            "observation": observation,
            "acknowledgment": {
                "stream_id": f"grounded-fragment-{observation['id'][:12]}",
                "sequence": 1,
                "event_id": observation["id"],
                "status": observation["outcome"],
                "before_revision": before["revision"],
                "after_revision": after["revision"],
                "authorization_path": ["world:exact-fragment-execution-ack"],
            },
        }
        receipt = provider.commit_counterflow(last_commit_request)
        if (
            receipt["session_id"] != _SESSION_ID
            or receipt["state_sha256"] != primary_field_sha256
            or receipt["consolidated"] is not True
        ):
            raise RuntimeError("observed consequence did not enter the composite field")
        commit_receipts.append(receipt)

    if last_commit_request is None:
        raise RuntimeError("grounded deliberation produced no observations")
    checkpoint = Path(commit_receipts[-1]["checkpoint"])
    observed_checkpoint_bytes = checkpoint.read_bytes()
    counterflow_state_sha256 = commit_receipts[-1][
        "counterflow_state_out_sha256"
    ]
    duplicate = provider.commit_counterflow(last_commit_request)
    if duplicate["status"] != "duplicate" or duplicate["consolidated"] is not False:
        raise RuntimeError("observed consequence replay was not idempotent")
    if checkpoint.read_bytes() != observed_checkpoint_bytes:
        raise RuntimeError("duplicate consequence changed the composite checkpoint")

    results: dict[str, dict[str, Any]] = {}
    for name, expected_actions in _BRANCHES.items():
        began = time.perf_counter()
        receipt = provider.plan_counterflow(
            {
                "user": _SESSION_ID,
                **_request(observations, start, branch_states[name][-1]),
            }
        )
        elapsed_ms = (time.perf_counter() - began) * 1_000.0
        proposal = receipt.get("action_proposal")
        if receipt["status"] != "settled" or not isinstance(proposal, dict):
            raise RuntimeError(f"{name} did not settle an inert grounded plan")
        actions = tuple(proposal["action_ids"])
        if actions != expected_actions:
            raise RuntimeError(f"{name} settled {actions}, expected {expected_actions}")
        reached = _execute(
            actions,
            field_state_sha256=receipt["state_sha256"],
        )
        if reached["revision"] != branch_states[name][-1]["revision"]:
            raise RuntimeError(f"{name} proposal did not reach its exact world goal")
        if (
            receipt["session_id"] != _SESSION_ID
            or receipt["state_sha256"] != primary_field_sha256
            or receipt["primary_field_sha256"] != receipt["state_sha256"]
            or receipt["counterflow_state_sha256"] != counterflow_state_sha256
            or receipt["persistent_state"] is not False
            or not receipt["inference_memory_frozen"]
            or proposal["inert"] is not True
            or checkpoint.read_bytes() != observed_checkpoint_bytes
        ):
            raise RuntimeError("imagined deliberation changed a canonical field component")
        results[name] = {
            "actions": list(actions),
            "goal_revision": reached["revision"],
            "elapsed_ms": elapsed_ms,
            "counterflow_state_sha256": receipt["counterflow_state_sha256"],
            "plan": receipt["plan"],
            "symbolic": receipt["symbolic"],
            "inference_memory_frozen": receipt["inference_memory_frozen"],
            "inert": proposal["inert"],
        }

    names = tuple(_BRANCHES)
    first, second = (results[name] for name in names)
    if first["actions"] == second["actions"]:
        raise RuntimeError("changing the exact goal did not revise the settled trajectory")

    missing_fragment_id = branch_observation_ids[names[-1]][1]
    removed = [
        observation
        for observation in observations
        if observation["id"] != missing_fragment_id
    ]
    causal_receipt = provider.plan_counterflow(
        {
            "user": _SESSION_ID,
            **_request(removed, start, branch_states[names[-1]][-1]),
        }
    )
    if (
        causal_receipt["state_sha256"] != primary_field_sha256
        or causal_receipt["counterflow_state_sha256"] != counterflow_state_sha256
        or causal_receipt["status"] == "settled"
        and causal_receipt["action_proposal"] is not None
        or checkpoint.read_bytes() != observed_checkpoint_bytes
    ):
        raise RuntimeError("unobserved imagination changed or bypassed composite memory")

    return {
        "result": "NOVEL_COUNTERFLOW_COMPOSITION_OK",
        "adaptive_state": "versioned composite Phi and counterflow QiFieldState fields",
        "canonical_primary_field_sha256": primary_field_sha256,
        "canonical_counterflow_field_sha256": counterflow_state_sha256,
        "canonical_components_unchanged_by_planning": True,
        "observed_counterflow_state_persisted": True,
        "imagined_state_persisted": False,
        "observation_count": len(observations),
        "fragment_stream_count": len(observations),
        "maximum_source_episode_actions": max(source_action_counts),
        "source_episode_action_counts": source_action_counts,
        "holdout_generator_committed": False,
        "fragment_request_symbols": fragment_request_symbols,
        "complete_trajectory_observed": False,
        "fragment_commit_order": [
            str(observation["id"]) for observation in observations
        ],
        "duplicate_commit_status": duplicate["status"],
        "shared_start_revision": start["revision"],
        "goal_counterfactual_revised_all_actions": all(
            left != right
            for left, right in zip(
                first["actions"],
                second["actions"],
                strict=True,
            )
        ),
        "same_learned_field_for_both_goals": True,
        "novel_complete_sequences": {
            name: list(actions) for name, actions in _BRANCHES.items()
        },
        "branches": results,
        "removed_consequence": {
            "removed_fragment_id": missing_fragment_id,
            "status": causal_receipt["status"],
            "action_proposal": causal_receipt["action_proposal"],
        },
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="cassi-grounded-deliberation-") as state_dir:
        provider = PersistentFieldProvider(
            ProviderConfig(
                phi_config_path=_PHI_CONFIG,
                corpus_checkpoint_path=_CORPUS_CHECKPOINT,
                state_dir=Path(state_dir),
            )
        )
        provider.start()
        try:
            controller = provider.controller
            initial = provider.initial_state
            if controller is None or initial is None:
                raise RuntimeError("canonical field provider did not start")
            primary_field_sha256 = controller.state_sha256(initial)
            result = _run(
                provider,
                primary_field_sha256=primary_field_sha256,
            )
            if controller.state_sha256(initial) != primary_field_sha256:
                raise RuntimeError("grounded deliberation mutated the canonical field")
            result["canonical_checkpoint_sha256"] = provider.initial_checkpoint_sha256
        finally:
            provider.close()

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
