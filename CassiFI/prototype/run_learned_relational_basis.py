from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import statistics
import struct
import time
from typing import Any

import torch

from cassi_grounded_language import make_grounded_action_command
from cassi_qi_bootstrap import canonical_hash
from cassi_qi_world import DeterministicQiWorld
from cassi_relational_basis import (
    RELATIONAL_BASIS_NAMES,
    RelationAtoms,
    RelationEntity,
    RelationalBasisConfig,
    RelationalBasisController,
    relational_basis_value,
)


ACTIONS = (
    "action.gaze-left",
    "action.gaze-right",
    "action.gaze-up",
    "action.gaze-down",
)
ACTION_INDEX = {action_id: index for index, action_id in enumerate(ACTIONS)}
INVERSE_ACTIONS = {0: 1, 1: 0, 2: 3, 3: 2}
SELECTION_COMPOSITION = (0, 2, 1)
HOLDOUT_SEQUENCES = (
    (1, 2, 1),
    (0, 3, 0),
    (2, 1, 2),
    (3, 0, 3),
)
COMMAND_FIELD_SHA256 = hashlib.sha256(
    b"cassi.field-selected-relational-basis.v1"
).hexdigest()


def _f64(value: float) -> str:
    return f"f64:{struct.pack('>d', value).hex()}"


def _f64_value(value: Any) -> float:
    if not isinstance(value, str) or not value.startswith("f64:"):
        raise RuntimeError("world value is not canonical f64")
    return struct.unpack(">d", bytes.fromhex(value[4:]))[0]


def _world(
    *,
    seed: int,
    world_id: str,
    episode_id: str,
    self_position: tuple[float, float],
    target_position: tuple[float, float],
    target_id: str,
    target_velocity: tuple[float, float] = (0.0, 0.0),
    distractors: tuple[
        tuple[str, tuple[float, float], tuple[float, float]], ...
    ] = (),
) -> DeterministicQiWorld:
    world = DeterministicQiWorld(
        seed=seed,
        world_id=world_id,
        episode_id=episode_id,
        object_count=1 + len(distractors),
        occlusion=False,
    )
    snapshot = deepcopy(world.snapshot())
    state = snapshot["state"]
    state["agent"] = [
        _f64(self_position[0]),
        _f64(self_position[1]),
        _f64(0.0),
        _f64(0.0),
    ]
    object_specs = (
        (target_id, target_position, target_velocity),
        *distractors,
    )
    for target, (object_id, position, velocity) in zip(
        state["objects"],
        object_specs,
        strict=True,
    ):
        target.update(
            {
                "object_id": object_id,
                "x": _f64(position[0]),
                "y": _f64(position[1]),
                "vx": _f64(velocity[0]),
                "vy": _f64(velocity[1]),
                "phase": _f64(0.0),
            }
        )
    state["last_action_id"] = None
    state["last_values"] = []
    snapshot["tick_log"] = []
    body = {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    snapshot["snapshot_sha256"] = canonical_hash(
        body,
        "cassi.qi-world-snapshot.v1",
    )
    world.restore(snapshot)
    return world


def _step(world: DeterministicQiWorld, action_index: int) -> None:
    acknowledgment = world.step(
        make_grounded_action_command(
            world,
            ACTIONS[action_index],
            field_state_sha256=COMMAND_FIELD_SHA256,
        )
    )
    if acknowledgment.status != "applied":
        raise RuntimeError(f"{ACTIONS[action_index]} was not applied")


def _clone(world: DeterministicQiWorld) -> DeterministicQiWorld:
    duplicate = DeterministicQiWorld(
        seed=world.seed,
        world_id=world.world_id,
        episode_id=world.episode_id,
        object_count=world.object_count,
        occlusion=False,
    )
    duplicate.restore(world.snapshot())
    return duplicate


def _atoms(
    world: DeterministicQiWorld,
    *,
    self_id: str,
    permuted: bool = False,
    target_index: int = 0,
) -> tuple[RelationAtoms, int]:
    snapshot = world.snapshot()
    state = snapshot["state"]
    self_entity = RelationEntity(
        self_id,
        _f64_value(state["agent"][0]),
        _f64_value(state["agent"][1]),
    )
    target = state["objects"][target_index]
    target_entity = RelationEntity(
        target["object_id"],
        _f64_value(target["x"]),
        _f64_value(target["y"]),
    )
    boundary = max(abs(self_entity.x), abs(self_entity.y)) > 0.92
    entities = (target_entity, self_entity) if permuted else (self_entity, target_entity)
    return (
        RelationAtoms(
            world_id=world.world_id,
            episode_id=world.episode_id,
            state_sha256=world.state_sha256,
            regime="boundary" if boundary else "interior",
            entities=entities,
        ),
        1 if permuted else 0,
    )


def _relative_residual(predicted: torch.Tensor, observed: torch.Tensor) -> float:
    denominator = max(
        float(torch.linalg.vector_norm(observed).item()),
        1.0e-12,
    )
    return float(torch.linalg.vector_norm(predicted - observed).item()) / denominator


def _training_state(
    controller: RelationalBasisController,
) -> tuple[Any, int, set[tuple[str, str]]]:
    state = controller.initial_state(dtype=torch.float64)
    self_positions = ((-0.30, -0.20), (0.10, -0.20), (-0.30, 0.20), (0.10, 0.20))
    relative_positions = ((0.20, 0.10), (0.40, 0.10), (0.20, 0.30), (0.40, 0.30))
    examples: dict[tuple[int, int], tuple[list[torch.Tensor], list[torch.Tensor]]] = {
        (basis_id, action_id): ([], [])
        for basis_id in range(controller.config.basis_count)
        for action_id in range(controller.config.action_count)
    }
    identities: set[tuple[str, str]] = set()
    execution_count = 0
    for action_id in range(controller.config.action_count):
        for sample_id, (self_position, relative) in enumerate(
            zip(self_positions, relative_positions, strict=True)
        ):
            world_id = f"world.relation-train.{action_id}.{sample_id}"
            episode_id = f"episode.relation-train.{action_id}.{sample_id}"
            identities.add((world_id, episode_id))
            target_position = (
                self_position[0] + relative[0],
                self_position[1] + relative[1],
            )
            world = _world(
                seed=100 + action_id * 10 + sample_id,
                world_id=world_id,
                episode_id=episode_id,
                self_position=self_position,
                target_position=target_position,
                target_id=f"training-target-{action_id}-{sample_id}",
            )
            before, self_index = _atoms(
                world,
                self_id=f"training-self-{action_id}-{sample_id}",
            )
            _step(world, action_id)
            after, _ = _atoms(
                world,
                self_id=f"training-self-{action_id}-{sample_id}",
            )
            if len(world.snapshot()["tick_log"]) != 1:
                raise RuntimeError("training source was not a one-action execution")
            for basis_id in range(controller.config.basis_count):
                before_values, after_values = examples[(basis_id, action_id)]
                before_values.append(
                    relational_basis_value(basis_id, before, self_index=self_index)
                )
                after_values.append(
                    relational_basis_value(basis_id, after, self_index=self_index)
                )
            execution_count += 1

    for basis_id in range(controller.config.basis_count):
        for action_id in range(controller.config.action_count):
            before_values, after_values = examples[(basis_id, action_id)]
            state, receipt = controller.observe_grouped_transitions(
                state,
                basis_id,
                action_id,
                torch.stack(before_values),
                torch.stack(after_values),
            )
            if receipt.basin_id != controller.basin_id(basis_id, action_id):
                raise RuntimeError("grouped operator entered the wrong field basin")
    return state, execution_count, identities


def _selection_evidence(
    controller: RelationalBasisController,
    state: Any,
) -> tuple[Any, set[tuple[str, str]]]:
    transitions: dict[int, list[tuple[int, torch.Tensor, torch.Tensor]]] = {
        basis_id: [] for basis_id in range(controller.config.basis_count)
    }
    compositions: dict[int, list[tuple[tuple[int, ...], torch.Tensor, torch.Tensor]]] = {
        basis_id: [] for basis_id in range(controller.config.basis_count)
    }
    invariance: dict[int, list[tuple[torch.Tensor, torch.Tensor]]] = {
        basis_id: [] for basis_id in range(controller.config.basis_count)
    }
    collision: dict[int, list[torch.Tensor]] = {
        basis_id: [] for basis_id in range(controller.config.basis_count)
    }
    identities: set[tuple[str, str]] = set()

    for sample_id in range(8):
        self_position = (-0.42 + 0.08 * sample_id, -0.28 + 0.04 * (sample_id % 4))
        relative = (0.22 + 0.03 * (sample_id % 3), 0.18 + 0.02 * (sample_id % 2))
        target_position = (
            self_position[0] + relative[0],
            self_position[1] + relative[1],
        )
        world_id = f"world.relation-select.{sample_id}"
        episode_id = f"episode.relation-select.{sample_id}"
        identities.add((world_id, episode_id))
        source = _world(
            seed=300 + sample_id,
            world_id=world_id,
            episode_id=episode_id,
            self_position=self_position,
            target_position=target_position,
            target_id=f"selection-target-{sample_id}",
        )
        before, self_index = _atoms(
            source,
            self_id=f"selection-self-{sample_id}",
        )
        for basis_id in range(controller.config.basis_count):
            collision[basis_id].append(
                relational_basis_value(basis_id, before, self_index=self_index)
            )
        for action_id in range(controller.config.action_count):
            transitioned = _clone(source)
            _step(transitioned, action_id)
            after, _ = _atoms(
                transitioned,
                self_id=f"selection-self-{sample_id}",
            )
            for basis_id in range(controller.config.basis_count):
                transitions[basis_id].append(
                    (
                        action_id,
                        relational_basis_value(basis_id, before, self_index=self_index),
                        relational_basis_value(basis_id, after, self_index=self_index),
                    )
                )

        composed = _clone(source)
        for action_id in SELECTION_COMPOSITION:
            _step(composed, action_id)
        composed_atoms, _ = _atoms(
            composed,
            self_id=f"selection-self-{sample_id}",
        )
        for basis_id in range(controller.config.basis_count):
            compositions[basis_id].append(
                (
                    SELECTION_COMPOSITION,
                    relational_basis_value(basis_id, before, self_index=self_index),
                    relational_basis_value(
                        basis_id,
                        composed_atoms,
                        self_index=self_index,
                    ),
                )
            )

        shift = (0.18, -0.12)
        shifted = _world(
            seed=400 + sample_id,
            world_id=f"world.relation-shifted.{sample_id}",
            episode_id=f"episode.relation-shifted.{sample_id}",
            self_position=(self_position[0] + shift[0], self_position[1] + shift[1]),
            target_position=(target_position[0] + shift[0], target_position[1] + shift[1]),
            target_id=f"renamed-target-{sample_id}",
        )
        shifted_atoms, shifted_self_index = _atoms(
            shifted,
            self_id=f"renamed-self-{sample_id}",
        )
        for basis_id in range(controller.config.basis_count):
            invariance[basis_id].append(
                (
                    relational_basis_value(basis_id, before, self_index=self_index),
                    relational_basis_value(
                        basis_id,
                        shifted_atoms,
                        self_index=shifted_self_index,
                    ),
                )
            )

    boundary_transitions: dict[int, list[tuple[int, torch.Tensor, torch.Tensor]]] = {
        basis_id: [] for basis_id in range(controller.config.basis_count)
    }
    boundary_specs = (
        ((0.995, 0.0), (0.4, 0.3), 1),
        ((-0.995, 0.0), (-0.4, 0.3), 0),
        ((0.0, 0.995), (0.3, 0.4), 2),
        ((0.0, -0.995), (0.3, -0.4), 3),
    )
    for sample_id, (self_position, target_position, action_id) in enumerate(boundary_specs):
        world = _world(
            seed=500 + sample_id,
            world_id=f"world.relation-boundary.{sample_id}",
            episode_id=f"episode.relation-boundary.{sample_id}",
            self_position=self_position,
            target_position=target_position,
            target_id=f"boundary-target-{sample_id}",
        )
        before, self_index = _atoms(world, self_id=f"boundary-self-{sample_id}")
        _step(world, action_id)
        after, _ = _atoms(world, self_id=f"boundary-self-{sample_id}")
        for basis_id in range(controller.config.basis_count):
            boundary_transitions[basis_id].append(
                (
                    action_id,
                    relational_basis_value(basis_id, before, self_index=self_index),
                    relational_basis_value(basis_id, after, self_index=self_index),
                )
            )

    for basis_id in range(controller.config.basis_count):
        state, _ = controller.observe_basis_evidence(
            state,
            basis_id,
            transitions=transitions[basis_id],
            inverse_actions=INVERSE_ACTIONS,
            compositions=compositions[basis_id],
            invariance_pairs=invariance[basis_id],
            collision_values=collision[basis_id],
            boundary_transitions=boundary_transitions[basis_id],
        )
    return state, identities


def _bind_self(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    action_id: int,
    before: RelationAtoms,
    after: RelationAtoms,
) -> tuple[int, tuple[float, float], float]:
    operator = controller.operator(state, basis_id, action_id)
    residuals = []
    for self_index in (0, 1):
        before_value = relational_basis_value(basis_id, before, self_index=self_index)
        after_value = relational_basis_value(basis_id, after, self_index=self_index)
        residuals.append(_relative_residual(operator @ before_value, after_value))
    order = sorted(range(2), key=lambda index: (residuals[index], index))
    margin = residuals[order[1]] - residuals[order[0]]
    if margin <= controller.config.margin_floor:
        raise RuntimeError("interventional role binding was ambiguous")
    return order[0], (residuals[0], residuals[1]), margin


def _plan_holdouts(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    training_identities: set[tuple[str, str]],
) -> dict[str, Any]:
    planning_ms = []
    iterations = []
    constraint_residuals = []
    role_margins = []
    revisions = []
    successes = 0
    permutation_count = 0
    for sample_id in range(32):
        sequence = HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)]
        self_position = (
            -0.36 + 0.06 * (sample_id % 8),
            -0.30 + 0.06 * ((sample_id // 4) % 8),
        )
        target_position = (
            self_position[0] + 0.28 - 0.02 * (sample_id % 3),
            self_position[1] + 0.24 - 0.02 * (sample_id % 2),
        )
        world_id = f"world.relation-holdout.{sample_id}"
        episode_id = f"episode.relation-holdout.{sample_id}"
        if (world_id, episode_id) in training_identities:
            raise RuntimeError("holdout identity overlaps training")
        source = _world(
            seed=700 + sample_id,
            world_id=world_id,
            episode_id=episode_id,
            self_position=self_position,
            target_position=target_position,
            target_id=f"holdout-target-renamed-{sample_id}",
        )
        source_snapshot = source.snapshot()
        permuted = bool(sample_id % 2)
        permutation_count += int(permuted)
        before, true_self_index = _atoms(
            source,
            self_id=f"holdout-self-renamed-{sample_id}",
            permuted=permuted,
        )
        calibration_action = 1 if sample_id % 2 == 0 else 2
        calibration = _clone(source)
        _step(calibration, calibration_action)
        calibration_after, _ = _atoms(
            calibration,
            self_id=f"holdout-self-renamed-{sample_id}",
            permuted=permuted,
        )
        bound_self_index, _, role_margin = _bind_self(
            controller,
            state,
            basis_id,
            calibration_action,
            before,
            calibration_after,
        )
        if bound_self_index != true_self_index:
            raise RuntimeError("field operator bound the wrong interventional self role")
        role_margins.append(role_margin)

        generator = _clone(source)
        values = [
            relational_basis_value(
                basis_id,
                before,
                self_index=bound_self_index,
            )
        ]
        for action_id in sequence:
            _step(generator, action_id)
            atoms, _ = _atoms(
                generator,
                self_id=f"holdout-self-renamed-{sample_id}",
                permuted=permuted,
            )
            values.append(
                relational_basis_value(
                    basis_id,
                    atoms,
                    self_index=bound_self_index,
                )
            )
        goal_revision = generator.state_sha256

        active = controller.start_thought(
            state,
            values[0],
            values[-1],
            active_slots=4,
            constraints={
                1: (values[1], (1.0, 1.0, 1.0, 1.0)),
                2: (values[2], (1.0, 1.0, 1.0, 1.0)),
            },
            eligible_basins=tuple(
                controller.basin_id(basis_id, action_id)
                for action_id in range(controller.config.action_count)
            ),
        )
        started = time.perf_counter()
        _, trace = controller.run_until_closed(active)
        planning_ms.append((time.perf_counter() - started) * 1000.0)
        final = trace[-1]
        selected_actions = tuple(
            basin_id - basis_id * controller.config.action_count
            for basin_id in final.winning_basins
        )
        if final.status != "settled" or selected_actions != sequence:
            raise RuntimeError(
                f"holdout {sample_id} produced {selected_actions} with {final.status}"
            )

        execution = _world(
            seed=700 + sample_id,
            world_id=world_id,
            episode_id=episode_id,
            self_position=self_position,
            target_position=target_position,
            target_id=f"holdout-target-renamed-{sample_id}",
        )
        execution.restore(source_snapshot)
        for action_id in selected_actions:
            _step(execution, action_id)
        if execution.state_sha256 != goal_revision:
            raise RuntimeError("relational holdout missed its exact world revision")
        successes += 1
        iterations.append(len(trace))
        constraint_residuals.append(final.constraint_residual)
        revisions.append(goal_revision)

    return {
        "count": 32,
        "successes": successes,
        "permuted_entity_orders": permutation_count,
        "renamed_identities": 32,
        "role_binding_successes": successes,
        "role_margin_min": min(role_margins),
        "planning_ms_total": sum(planning_ms),
        "planning_ms_median": statistics.median(planning_ms),
        "planning_ms_max": max(planning_ms),
        "iterations_min": min(iterations),
        "iterations_max": max(iterations),
        "constraint_residual_max": max(constraint_residuals),
        "first_exact_revision": revisions[0],
        "last_exact_revision": revisions[-1],
    }


def run_field_selected_relational_basis() -> dict[str, Any]:
    controller = RelationalBasisController(
        RelationalBasisConfig(
            slot_count=4,
            merge_residual=0.02,
            separate_residual=0.05,
            action_residual_tolerance=0.04,
        )
    )
    started = time.perf_counter()
    state, training_executions, training_identities = _training_state(controller)
    training_ms = (time.perf_counter() - started) * 1000.0

    selection_started = time.perf_counter()
    state, selection_identities = _selection_evidence(controller, state)
    selection_ms = (time.perf_counter() - selection_started) * 1000.0
    if training_identities & selection_identities:
        raise RuntimeError("basis selection identities overlap operator training")
    selection = controller.select_basis(state)
    if selection.status != "selected" or selection.basis_id != 0:
        raise RuntimeError(
            f"field selected {selection.basis_name} with {selection.status}"
        )

    checkpoint = controller.dump_state_bytes(state)
    restored = controller.load_state_bytes(checkpoint)
    reloaded_selection = controller.select_basis(restored)
    if reloaded_selection != selection:
        raise RuntimeError("field-selected basis did not survive exact checkpoint reload")
    frozen_sha256 = selection.field_sha256

    holdouts = _plan_holdouts(
        controller,
        restored,
        selection.basis_id,
        training_identities | selection_identities,
    )
    if controller._tensor_sha256(restored.field) != frozen_sha256:
        raise RuntimeError("held-out inference mutated relational field memory")

    evidence_ablated = controller.clear_basis_evidence(restored, selection.basis_id)
    ablated_selection = controller.select_basis(evidence_ablated)
    if ablated_selection.status != "no_eligible_basis":
        raise RuntimeError("clearing selected field evidence did not force abstention")

    required_basin = controller.basin_id(selection.basis_id, 2)
    operator_ablated = controller.clear_basin(restored, required_basin)
    ablation_source = _world(
        seed=999,
        world_id="world.relation-ablation",
        episode_id="episode.relation-ablation",
        self_position=(-0.2, -0.2),
        target_position=(0.2, 0.2),
        target_id="ablation-target",
    )
    ablation_atoms, self_index = _atoms(
        ablation_source,
        self_id="ablation-self",
    )
    ablation_values = [
        relational_basis_value(selection.basis_id, ablation_atoms, self_index=self_index)
    ]
    for action_id in HOLDOUT_SEQUENCES[0]:
        _step(ablation_source, action_id)
        atoms, _ = _atoms(ablation_source, self_id="ablation-self")
        ablation_values.append(
            relational_basis_value(selection.basis_id, atoms, self_index=self_index)
        )
    _, ablation_trace = controller.run_until_closed(
        controller.start_thought(
            operator_ablated,
            ablation_values[0],
            ablation_values[-1],
            active_slots=4,
            constraints={
                1: (ablation_values[1], (1.0, 1.0, 1.0, 1.0)),
                2: (ablation_values[2], (1.0, 1.0, 1.0, 1.0)),
            },
            eligible_basins=tuple(
                controller.basin_id(selection.basis_id, action_id)
                for action_id in range(controller.config.action_count)
                if action_id != 2
            ),
        )
    )
    if ablation_trace[-1].status == "settled":
        raise RuntimeError("required operator ablation did not force exhaustion")

    relation_payload = RelationAtoms.from_payload(
        _atoms(
            _world(
                seed=1001,
                world_id="world.relation-schema",
                episode_id="episode.relation-schema",
                self_position=(0.0, 0.0),
                target_position=(0.2, 0.2),
                target_id="schema-target",
            ),
            self_id="schema-self",
        )[0].payload()
    )
    boundary_residual = selection.evidence[selection.basis_id].boundary
    boundary_supported = (
        boundary_residual <= controller.config.action_residual_tolerance
    )
    if boundary_supported:
        raise RuntimeError("interior field basis unexpectedly covered boundary clamping")


    return {
        "result": "FIELD_SELECTED_RELATIONAL_BASIS_OK",
        "claim": "field-selected relational basis discovery",
        "candidate_library": list(RELATIONAL_BASIS_NAMES),
        "selected_basis": selection.basis_name,
        "selection_margin": selection.margin,
        "selection_evidence": [asdict(item) for item in selection.evidence],
        "selection_evidence_field_owned": True,
        "caller_supplied_verdicts": False,
        "training_executions": training_executions,
        "training_identity_count": len(training_identities),
        "selection_identity_count": len(selection_identities),
        "training_ms": training_ms,
        "selection_ms": selection_ms,
        "holdouts": holdouts,
        "checkpoint_restart_exact": controller.dump_state_bytes(restored) == checkpoint,
        "field_memory_frozen_during_inference": True,
        "evidence_ablation_status": ablated_selection.status,
        "operator_ablation_status": ablation_trace[-1].status,
        "boundary_case_count": 4,
        "boundary_mean_residual": boundary_residual,
        "boundary_supported": boundary_supported,
        "relation_atom_schema": relation_payload.payload()["schema"],
        "relation_atom_payload_sha256": relation_payload.payload()["payload_sha256"],
        "live_provider_fallback": False,
        "teacher_or_model_calls": 0,
    }


def main() -> int:
    result = run_field_selected_relational_basis()
    print(json.dumps(result, indent=2, sort_keys=True))
    print("FIELD_SELECTED_RELATIONAL_BASIS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
