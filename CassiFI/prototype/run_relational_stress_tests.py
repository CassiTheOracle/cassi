from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
import statistics
from typing import Any, Callable

import torch

from cassi_relational_basis import (
    RelationAtoms,
    RelationalBasisConfig,
    RelationalBasisController,
    relational_basis_value,
)
from run_learned_relational_basis import (
    _bind_self,
    HOLDOUT_SEQUENCES,
    INVERSE_ACTIONS,
    _atoms,
    _clone,
    _relative_residual,
    _selection_evidence,
    _step,
    _training_state,
    _world,
)


_EXPERIMENTAL_BASIS_NAMES = (
    "target_minus_self",
    "distance_bearing",
    "boundary_context",
)
_NOISE_AMPLITUDES = (0.0, 0.002, 0.01, 0.015, 0.02, 0.025, 0.03, 0.06)


def _trained_fixture() -> tuple[RelationalBasisController, Any, int]:
    controller = RelationalBasisController(
        RelationalBasisConfig(
            slot_count=4,
            merge_residual=0.02,
            separate_residual=0.05,
            action_residual_tolerance=0.04,
        )
    )
    state, _, _ = _training_state(controller)
    state, _ = _selection_evidence(controller, state)
    selection = controller.select_basis(state)
    if selection.status != "selected" or selection.basis_id != 0:
        raise RuntimeError("stress fixture did not select target-minus-self")
    return controller, state, selection.basis_id


def _field_value(
    atoms: RelationAtoms,
    self_index: int,
    slot: int,
) -> torch.Tensor:
    _ = slot
    return relational_basis_value(0, atoms, self_index=self_index)


def _planned_execution(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    world: Any,
    *,
    self_id: str,
    sequence: tuple[int, int, int],
    value: Callable[[RelationAtoms, int, int], torch.Tensor] = _field_value,
    eligible_actions: tuple[int, ...] = (0, 1, 2, 3),
    intermediate_constraint_slots: tuple[int, ...] = (1, 2),
) -> dict[str, Any]:
    source_snapshot = world.snapshot()
    generator = _clone(world)
    before, self_index = _atoms(generator, self_id=self_id)
    values = [value(before, self_index, 0)]
    for slot, action_id in enumerate(sequence, start=1):
        _step(generator, action_id)
        current, _ = _atoms(generator, self_id=self_id)
        values.append(value(current, self_index, slot))
    goal_revision = generator.state_sha256
    constraints = (
        {
            slot: (values[slot], (1.0, 1.0, 1.0, 1.0))
            for slot in intermediate_constraint_slots
        }
        or None
    )

    _, trace = controller.run_until_closed(
        controller.start_thought(
            state,
            values[0],
            values[-1],
            active_slots=4,
            constraints=constraints,
            eligible_basins=tuple(
                controller.basin_id(basis_id, action_id)
                for action_id in eligible_actions
            ),
        )
    )
    final = trace[-1]
    selected_actions = tuple(
        basin_id - basis_id * controller.config.action_count
        for basin_id in final.winning_basins
    )
    exact_revision = False
    if final.status == "settled":
        execution = _clone(world)
        execution.restore(source_snapshot)
        for action_id in selected_actions:
            _step(execution, action_id)
        exact_revision = execution.state_sha256 == goal_revision
    return {
        "status": final.status,
        "selected_actions": selected_actions,
        "expected_actions": sequence,
        "exact_revision": exact_revision,
        "constraint_residual": final.constraint_residual,
        "intermediate_constraint_slots": intermediate_constraint_slots,
    }


def _outcome_summary(outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "count": len(outcomes),
        "settled": sum(item["status"] == "settled" for item in outcomes),
        "exact_revisions": sum(item["exact_revision"] for item in outcomes),
        "false_settlements": sum(
            item["status"] == "settled" and not item["exact_revision"]
            for item in outcomes
        ),
        "action_sequences_exact": sum(
            item["selected_actions"] == item["expected_actions"] for item in outcomes
        ),
        "constraint_residual_max": max(
            item["constraint_residual"] for item in outcomes
        ),
    }


def _moving_target_results(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
) -> dict[str, Any]:
    velocities = (
        (0.009, -0.006),
        (-0.012, 0.008),
        (0.018, 0.0),
        (0.0, -0.018),
    )
    constrained = []
    one_constraint = []
    endpoint_only = []
    stationary_endpoint_control = []
    for sample_id in range(24):
        self_position = (
            -0.34 + 0.08 * (sample_id % 8),
            -0.28 + 0.07 * ((sample_id // 4) % 6),
        )
        world = _world(
            seed=2000 + sample_id,
            world_id=f"world.relation-moving.{sample_id}",
            episode_id=f"episode.relation-moving.{sample_id}",
            self_position=self_position,
            target_position=(self_position[0] + 0.28, self_position[1] + 0.22),
            target_id=f"moving-target-{sample_id}",
            target_velocity=velocities[sample_id % len(velocities)],
        )
        arguments = {
            "self_id": f"moving-self-{sample_id}",
            "sequence": HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)],
        }
        constrained.append(
            _planned_execution(
                controller,
                state,
                basis_id,
                world,
                **arguments,
            )
        )
        one_constraint.append(
            _planned_execution(
                controller,
                state,
                basis_id,
                world,
                intermediate_constraint_slots=(1,),
                **arguments,
            )
        )
        endpoint_only.append(
            _planned_execution(
                controller,
                state,
                basis_id,
                world,
                intermediate_constraint_slots=(),
                **arguments,
            )
        )
        stationary = _world(
            seed=2100 + sample_id,
            world_id=f"world.relation-stationary-endpoint.{sample_id}",
            episode_id=f"episode.relation-stationary-endpoint.{sample_id}",
            self_position=self_position,
            target_position=(self_position[0] + 0.28, self_position[1] + 0.22),
            target_id=f"stationary-endpoint-target-{sample_id}",
        )
        stationary_endpoint_control.append(
            _planned_execution(
                controller,
                state,
                basis_id,
                stationary,
                self_id=f"stationary-endpoint-self-{sample_id}",
                sequence=HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)],
                intermediate_constraint_slots=(),
            )
        )
    return {
        "with_two_intermediate_constraints": _outcome_summary(constrained),
        "with_one_intermediate_constraint": _outcome_summary(one_constraint),
        "endpoint_only": _outcome_summary(endpoint_only),
        "stationary_endpoint_control": _outcome_summary(
            stationary_endpoint_control
        ),
        "velocity_max": max(math.hypot(*velocity) for velocity in velocities),
    }


def _signed_noise(key: str) -> float:
    digest = hashlib.sha256(key.encode()).digest()
    return int.from_bytes(digest[:8], "big") / float((1 << 64) - 1) * 2.0 - 1.0


def _noisy_value(
    atoms: RelationAtoms,
    self_index: int,
    slot: int,
    *,
    amplitude: float,
    sample_id: int,
) -> torch.Tensor:
    self_entity = atoms.entities[self_index]
    target = atoms.entities[1 - self_index]
    prefix = f"{sample_id}:{slot}"
    self_x = self_entity.x + amplitude * _signed_noise(f"{prefix}:self:x")
    self_y = self_entity.y + amplitude * _signed_noise(f"{prefix}:self:y")
    target_x = target.x + amplitude * _signed_noise(f"{prefix}:target:x")
    target_y = target.y + amplitude * _signed_noise(f"{prefix}:target:y")
    x, y = target_x - self_x, target_y - self_y
    return torch.tensor((x, y, 1.0, x * y), dtype=torch.complex128)


def _noise_results(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
) -> list[dict[str, Any]]:
    results = []
    for amplitude in _NOISE_AMPLITUDES:
        outcomes = []
        for sample_id in range(16):
            self_position = (
                -0.32 + 0.08 * (sample_id % 8),
                -0.26 + 0.08 * (sample_id // 4),
            )
            world = _world(
                seed=3000 + sample_id,
                world_id=f"world.relation-noise.{sample_id}",
                episode_id=f"episode.relation-noise.{sample_id}",
                self_position=self_position,
                target_position=(self_position[0] + 0.30, self_position[1] + 0.24),
                target_id=f"noise-target-{sample_id}",
            )
            outcomes.append(
                _planned_execution(
                    controller,
                    state,
                    basis_id,
                    world,
                    self_id=f"noise-self-{sample_id}",
                    sequence=HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)],
                    value=lambda atoms, self_index, slot, amplitude=amplitude, sample_id=sample_id: _noisy_value(
                        atoms,
                        self_index,
                        slot,
                        amplitude=amplitude,
                        sample_id=sample_id,
                    ),
                )
            )
        results.append(
            {
                "amplitude": amplitude,
                "count": len(outcomes),
                "settled": sum(item["status"] == "settled" for item in outcomes),
                "exact_revisions": sum(item["exact_revision"] for item in outcomes),
                "action_sequences_exact": sum(
                    item["selected_actions"] == item["expected_actions"]
                    for item in outcomes
                ),
                "constraint_residual_median": statistics.median(
                    item["constraint_residual"] for item in outcomes
                ),
                "constraint_residual_max": max(
                    item["constraint_residual"] for item in outcomes
                ),
            }
        )
    return results


def _candidate_object_scores(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    world: Any,
    *,
    self_id: str,
) -> tuple[float, ...]:
    sequence = (1, 2, 0, 3)
    before_values = []
    for target_index in range(world.object_count):
        atoms, self_index = _atoms(
            world,
            self_id=self_id,
            target_index=target_index,
        )
        before_values.append(
            relational_basis_value(basis_id, atoms, self_index=self_index)
        )
    transitioned = _clone(world)
    for action_id in sequence:
        _step(transitioned, action_id)
    scores = []
    for target_index, before in enumerate(before_values):
        predicted = before
        for action_id in sequence:
            predicted = controller.operator(state, basis_id, action_id) @ predicted
        after, self_index = _atoms(
            transitioned,
            self_id=self_id,
            target_index=target_index,
        )
        observed = relational_basis_value(basis_id, after, self_index=self_index)
        scores.append(_relative_residual(predicted, observed))
    return tuple(scores)


def _distractor_results(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
) -> dict[str, Any]:
    diagnostic_selected = 0
    diagnostic_margins = []
    for sample_id in range(24):
        world = _world(
            seed=4000 + sample_id,
            world_id=f"world.relation-distractor.{sample_id}",
            episode_id=f"episode.relation-distractor.{sample_id}",
            self_position=(-0.20 + 0.02 * (sample_id % 4), -0.18),
            target_position=(0.22, 0.20),
            target_id=f"relevant-target-{sample_id}",
            distractors=(
                (f"distractor-a-{sample_id}", (-0.40, 0.32), (0.018, 0.0)),
                (f"distractor-b-{sample_id}", (0.42, -0.30), (0.0, -0.018)),
                (f"distractor-c-{sample_id}", (-0.32, -0.38), (0.013, 0.013)),
            ),
        )
        scores = _candidate_object_scores(
            controller,
            state,
            basis_id,
            world,
            self_id=f"distractor-self-{sample_id}",
        )
        eligible = [
            index
            for index, score in enumerate(scores)
            if score <= controller.config.action_residual_tolerance
        ]
        diagnostic_selected += eligible == [0]
        ordered = sorted(scores)
        diagnostic_margins.append(ordered[1] - ordered[0])

    indistinguishable_abstentions = 0
    indistinguishable_correct = 0
    indistinguishable_false_confidence = 0
    indistinguishable_eligible_counts = []
    for sample_id in range(16):
        world = _world(
            seed=5000 + sample_id,
            world_id=f"world.relation-indistinguishable.{sample_id}",
            episode_id=f"episode.relation-indistinguishable.{sample_id}",
            self_position=(-0.16, -0.14),
            target_position=(0.24, 0.18),
            target_id=f"indistinguishable-object-0-{sample_id}",
            distractors=(
                (f"indistinguishable-object-1-{sample_id}", (-0.38, 0.30), (0.0, 0.0)),
                (f"indistinguishable-object-2-{sample_id}", (0.40, -0.28), (0.0, 0.0)),
            ),
        )
        scores = _candidate_object_scores(
            controller,
            state,
            basis_id,
            world,
            self_id=f"indistinguishable-self-{sample_id}",
        )
        eligible = [
            index
            for index, score in enumerate(scores)
            if score <= controller.config.action_residual_tolerance
        ]
        indistinguishable_eligible_counts.append(len(eligible))
        hidden_relevant_index = sample_id % 3
        if len(eligible) != 1:
            indistinguishable_abstentions += 1
        elif eligible[0] == hidden_relevant_index:
            indistinguishable_correct += 1
        else:
            indistinguishable_false_confidence += 1

    return {
        "diagnostic_count": 24,
        "diagnostic_target_selections": diagnostic_selected,
        "diagnostic_margin_min": min(diagnostic_margins),
        "indistinguishable_count": 16,
        "indistinguishable_correct": indistinguishable_correct,
        "indistinguishable_false_confidence": indistinguishable_false_confidence,
        "indistinguishable_abstentions": indistinguishable_abstentions,
        "indistinguishable_eligible_min": min(indistinguishable_eligible_counts),
        "indistinguishable_eligible_max": max(indistinguishable_eligible_counts),
        "hidden_relevance_observable": False,
    }


def _passive_role_scores(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    atoms: RelationAtoms,
) -> tuple[float, float]:
    scores = []
    for self_index in (0, 1):
        value = relational_basis_value(basis_id, atoms, self_index=self_index)
        residuals = []
        for action_id, inverse_id in INVERSE_ACTIONS.items():
            cycled = controller.operator(state, basis_id, inverse_id) @ (
                controller.operator(state, basis_id, action_id) @ value
            )
            residuals.append(_relative_residual(cycled, value))
        scores.append(max(residuals))
    return scores[0], scores[1]


def _passive_role_results(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
) -> dict[str, Any]:
    relative_positions = (
        (0.42, 0.30),
        (-0.42, 0.30),
        (-0.42, -0.30),
        (0.42, -0.30),
    )
    passive_correct = 0
    passive_wrong = 0
    passive_abstentions = 0
    interventional_correct = 0
    maximum_cycle_residual = 0.0
    minimum_passive_margin = math.inf
    quadrant_results = {
        name: {
            "count": 0,
            "passive_correct": 0,
            "passive_wrong": 0,
            "passive_abstentions": 0,
            "interventional_correct": 0,
        }
        for name in ("northeast", "northwest", "southwest", "southeast")
    }
    for sample_id in range(32):
        self_position = (
            -0.08 + 0.02 * (sample_id % 8),
            -0.06 + 0.02 * ((sample_id // 4) % 4),
        )
        relative = relative_positions[sample_id % len(relative_positions)]
        quadrant_name = tuple(quadrant_results)[
            sample_id % len(relative_positions)
        ]
        quadrant_results[quadrant_name]["count"] += 1
        world = _world(
            seed=6000 + sample_id,
            world_id=f"world.relation-passive.{sample_id}",
            episode_id=f"episode.relation-passive.{sample_id}",
            self_position=self_position,
            target_position=(
                self_position[0] + relative[0],
                self_position[1] + relative[1],
            ),
            target_id=f"passive-entity-b-{sample_id}",
        )
        permuted = bool(sample_id % 2)
        atoms, true_self_index = _atoms(
            world,
            self_id=f"passive-entity-a-{sample_id}",
            permuted=permuted,
        )
        scores = _passive_role_scores(controller, state, basis_id, atoms)
        maximum_cycle_residual = max(maximum_cycle_residual, *scores)
        eligible = [
            index
            for index, score in enumerate(scores)
            if score <= controller.config.action_residual_tolerance
        ]
        if len(eligible) != 1:
            passive_abstentions += 1
            quadrant_results[quadrant_name]["passive_abstentions"] += 1
        else:
            minimum_passive_margin = min(
                minimum_passive_margin,
                abs(scores[0] - scores[1]),
            )
            if eligible[0] == true_self_index:
                passive_correct += 1
                quadrant_results[quadrant_name]["passive_correct"] += 1
            else:
                passive_wrong += 1
                quadrant_results[quadrant_name]["passive_wrong"] += 1

        action_id = 1 if sample_id % 2 == 0 else 2
        transitioned = _clone(world)
        _step(transitioned, action_id)
        after, _ = _atoms(
            transitioned,
            self_id=f"passive-entity-a-{sample_id}",
            permuted=permuted,
        )
        bound_self, _, _ = _bind_self(
            controller,
            state,
            basis_id,
            action_id,
            atoms,
            after,
        )
        interventional_correct += bound_self == true_self_index
        quadrant_results[quadrant_name]["interventional_correct"] += (
            bound_self == true_self_index
        )
    return {
        "count": 32,
        "balanced_relative_quadrants": 4,
        "passive_correct": passive_correct,
        "passive_wrong": passive_wrong,
        "passive_abstentions": passive_abstentions,
        "passive_margin_min": (
            None if math.isinf(minimum_passive_margin) else minimum_passive_margin
        ),
        "interventional_correct": interventional_correct,
        "maximum_inverse_cycle_residual": maximum_cycle_residual,
        "by_quadrant": quadrant_results,
    }


def _experimental_value(
    name: str,
    atoms: RelationAtoms,
    self_index: int,
) -> torch.Tensor:
    self_entity = atoms.entities[self_index]
    target = atoms.entities[1 - self_index]
    x, y = target.x - self_entity.x, target.y - self_entity.y
    if name == "target_minus_self":
        values = (x, y, 1.0, x * y)
    elif name == "distance_bearing":
        distance = math.hypot(x, y)
        inverse = 0.0 if distance == 0.0 else 1.0 / distance
        values = (distance, x * inverse, y * inverse, 1.0)
    elif name == "boundary_context":
        values = (x, y, 1.0, complex(self_entity.x, self_entity.y))
    else:
        raise RuntimeError(f"unknown experimental basis: {name}")
    return torch.tensor(values, dtype=torch.complex128)


def _candidate_training_position(
    action_id: int,
    sample_id: int,
) -> tuple[tuple[float, float], tuple[float, float]]:
    if sample_id < 4:
        self_position = (
            -0.30 + 0.18 * (sample_id % 2),
            -0.24 + 0.18 * (sample_id // 2),
        )
        return self_position, (self_position[0] + 0.28, self_position[1] + 0.22)
    offset = 0.94 + 0.015 * (sample_id - 4)
    transverse = -0.24 + 0.16 * (sample_id - 4)
    if action_id == 0:
        self_position = (-offset, transverse)
    elif action_id == 1:
        self_position = (offset, transverse)
    elif action_id == 2:
        self_position = (transverse, offset)
    else:
        self_position = (transverse, -offset)
    return self_position, (0.18, 0.16)


def _deposit_experimental_candidate(
    controller: RelationalBasisController,
    state: Any,
    basis_id: int,
    name: str,
) -> tuple[Any, dict[str, Any]]:
    for action_id in range(controller.config.action_count):
        before_values = []
        after_values = []
        for sample_id in range(8):
            self_position, target_position = _candidate_training_position(
                action_id,
                sample_id,
            )
            world = _world(
                seed=7000 + action_id * 10 + sample_id,
                world_id=f"world.candidate-train.{action_id}.{sample_id}",
                episode_id=f"episode.candidate-train.{action_id}.{sample_id}",
                self_position=self_position,
                target_position=target_position,
                target_id=f"candidate-train-target-{action_id}-{sample_id}",
            )
            before, self_index = _atoms(
                world,
                self_id=f"candidate-train-self-{action_id}-{sample_id}",
            )
            _step(world, action_id)
            after, _ = _atoms(
                world,
                self_id=f"candidate-train-self-{action_id}-{sample_id}",
            )
            before_values.append(_experimental_value(name, before, self_index))
            after_values.append(_experimental_value(name, after, self_index))
        state, _ = controller.observe_grouped_transitions(
            state,
            basis_id,
            action_id,
            torch.stack(before_values),
            torch.stack(after_values),
        )

    transitions = []
    compositions = []
    invariance_pairs = []
    collision_values = []
    for sample_id in range(8):
        self_position = (-0.38 + 0.08 * sample_id, -0.26 + 0.03 * (sample_id % 4))
        target_position = (self_position[0] + 0.30, self_position[1] + 0.24)
        source = _world(
            seed=7200 + sample_id,
            world_id=f"world.candidate-select.{sample_id}",
            episode_id=f"episode.candidate-select.{sample_id}",
            self_position=self_position,
            target_position=target_position,
            target_id=f"candidate-select-target-{sample_id}",
        )
        before, self_index = _atoms(
            source,
            self_id=f"candidate-select-self-{sample_id}",
        )
        collision_values.append(_experimental_value(name, before, self_index))
        for action_id in range(controller.config.action_count):
            transitioned = _clone(source)
            _step(transitioned, action_id)
            after, _ = _atoms(
                transitioned,
                self_id=f"candidate-select-self-{sample_id}",
            )
            transitions.append(
                (
                    action_id,
                    _experimental_value(name, before, self_index),
                    _experimental_value(name, after, self_index),
                )
            )
        sequence = HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)]
        composed = _clone(source)
        for action_id in sequence:
            _step(composed, action_id)
        after, _ = _atoms(
            composed,
            self_id=f"candidate-select-self-{sample_id}",
        )
        compositions.append(
            (
                sequence,
                _experimental_value(name, before, self_index),
                _experimental_value(name, after, self_index),
            )
        )
        shifted = _world(
            seed=7300 + sample_id,
            world_id=f"world.candidate-shift.{sample_id}",
            episode_id=f"episode.candidate-shift.{sample_id}",
            self_position=(self_position[0] + 0.16, self_position[1] - 0.10),
            target_position=(target_position[0] + 0.16, target_position[1] - 0.10),
            target_id=f"candidate-shift-target-{sample_id}",
        )
        shifted_atoms, shifted_self = _atoms(
            shifted,
            self_id=f"candidate-shift-self-{sample_id}",
        )
        invariance_pairs.append(
            (
                _experimental_value(name, before, self_index),
                _experimental_value(name, shifted_atoms, shifted_self),
            )
        )

    boundary_transitions = []
    for sample_id in range(12):
        action_id = sample_id % 4
        offset = 0.945 + 0.01 * (sample_id // 4)
        transverse = -0.28 + 0.07 * sample_id
        if action_id == 0:
            self_position = (-offset, transverse)
        elif action_id == 1:
            self_position = (offset, transverse)
        elif action_id == 2:
            self_position = (transverse, offset)
        else:
            self_position = (transverse, -offset)
        world = _world(
            seed=7400 + sample_id,
            world_id=f"world.candidate-boundary.{sample_id}",
            episode_id=f"episode.candidate-boundary.{sample_id}",
            self_position=self_position,
            target_position=(0.20, 0.18),
            target_id=f"candidate-boundary-target-{sample_id}",
        )
        before, self_index = _atoms(
            world,
            self_id=f"candidate-boundary-self-{sample_id}",
        )
        _step(world, action_id)
        after, _ = _atoms(
            world,
            self_id=f"candidate-boundary-self-{sample_id}",
        )
        boundary_transitions.append(
            (
                action_id,
                _experimental_value(name, before, self_index),
                _experimental_value(name, after, self_index),
            )
        )

    state, evidence = controller.observe_basis_evidence(
        state,
        basis_id,
        transitions=transitions,
        inverse_actions=INVERSE_ACTIONS,
        compositions=compositions,
        invariance_pairs=invariance_pairs,
        collision_values=collision_values,
        boundary_transitions=boundary_transitions,
    )
    return state, {
        **asdict(evidence),
        "basis_name": name,
        "field_owned": True,
    }


def _experimental_candidate_results() -> dict[str, Any]:
    controller = RelationalBasisController(
        RelationalBasisConfig(
            slot_count=4,
            merge_residual=0.02,
            separate_residual=0.25,
            action_residual_tolerance=0.08,
            boundary_weight=1.0,
            max_basis_score=8.0,
        )
    )
    state = controller.initial_state(dtype=torch.float64)
    evidence = []
    for basis_id, name in enumerate(_EXPERIMENTAL_BASIS_NAMES):
        state, item = _deposit_experimental_candidate(
            controller,
            state,
            basis_id,
            name,
        )
        evidence.append(item)
    selection = controller.select_basis(state)
    if selection.status != "selected" or selection.basis_id is None:
        raise RuntimeError("expanded field did not select an experimental basis")

    boundary_composition = {}
    for basis_id, name in enumerate(_EXPERIMENTAL_BASIS_NAMES):
        outcomes = []
        for sample_id in range(12):
            sequence = HOLDOUT_SEQUENCES[sample_id % len(HOLDOUT_SEQUENCES)]
            first_action = sequence[0]
            transverse = -0.30 + 0.05 * sample_id
            if first_action == 0:
                self_position = (-0.97, transverse)
            elif first_action == 1:
                self_position = (0.97, transverse)
            elif first_action == 2:
                self_position = (transverse, 0.97)
            else:
                self_position = (transverse, -0.97)
            world = _world(
                seed=7600 + basis_id * 20 + sample_id,
                world_id=f"world.candidate-plan.{basis_id}.{sample_id}",
                episode_id=f"episode.candidate-plan.{basis_id}.{sample_id}",
                self_position=self_position,
                target_position=(0.18, 0.16),
                target_id=f"candidate-plan-target-{basis_id}-{sample_id}",
            )
            outcomes.append(
                _planned_execution(
                    controller,
                    state,
                    basis_id,
                    world,
                    self_id=f"candidate-plan-self-{basis_id}-{sample_id}",
                    sequence=sequence,
                    value=lambda atoms, self_index, _slot, name=name: _experimental_value(
                        name,
                        atoms,
                        self_index,
                    ),
                )
            )
        boundary_composition[name] = _outcome_summary(outcomes)

    checkpoint = controller.dump_state_bytes(state)
    restored = controller.load_state_bytes(checkpoint)
    return {
        "candidate_count": len(_EXPERIMENTAL_BASIS_NAMES),
        "training_includes_boundary_examples": True,
        "evidence": evidence,
        "selected_basis": _EXPERIMENTAL_BASIS_NAMES[selection.basis_id],
        "selection_margin": selection.margin,
        "boundary_composition": boundary_composition,
        "checkpoint_restart_exact": (
            controller.dump_state_bytes(restored) == checkpoint
        ),
        "field_owned": True,
    }


def run_relational_stress_tests() -> dict[str, Any]:
    controller, state, basis_id = _trained_fixture()
    checkpoint = controller.dump_state_bytes(state)
    restored = controller.load_state_bytes(checkpoint)
    field_sha256 = controller.select_basis(restored).field_sha256

    moving = _moving_target_results(controller, restored, basis_id)
    noise = _noise_results(controller, restored, basis_id)
    distractors = _distractor_results(controller, restored, basis_id)
    passive_roles = _passive_role_results(controller, restored, basis_id)
    experimental_candidates = _experimental_candidate_results()

    ablation_world = _world(
        seed=8000,
        world_id="world.relation-stress-ablation",
        episode_id="episode.relation-stress-ablation",
        self_position=(-0.20, -0.18),
        target_position=(0.18, 0.20),
        target_id="stress-ablation-target",
        target_velocity=(0.006, -0.004),
    )
    required_action = 2
    ablated = controller.clear_basin(
        restored,
        controller.basin_id(basis_id, required_action),
    )
    ablation = _planned_execution(
        controller,
        ablated,
        basis_id,
        ablation_world,
        self_id="stress-ablation-self",
        sequence=HOLDOUT_SEQUENCES[0],
        eligible_actions=(0, 1, 3),
    )
    if ablation["exact_revision"]:
        raise RuntimeError("stress operator ablation retained the exact trajectory")
    if controller.select_basis(restored).field_sha256 != field_sha256:
        raise RuntimeError("stress inference mutated the selected relational field")

    return {
        "result": "RELATIONAL_STRESS_TESTS_OK",
        "claim": "defined relational stress testing",
        "selected_basis": "target_minus_self",
        "moving_targets": moving,
        "coordinate_noise": noise,
        "distractors": distractors,
        "passive_roles": passive_roles,
        "experimental_candidates": experimental_candidates,
        "operator_ablation": ablation,
        "checkpoint_restart_exact": controller.dump_state_bytes(restored) == checkpoint,
        "field_memory_frozen": True,
        "teacher_or_model_calls": 0,
        "provider_integration": False,
    }


def main() -> int:
    result = run_relational_stress_tests()
    print(json.dumps(result, indent=2, sort_keys=True))
    print("RELATIONAL_STRESS_TESTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
