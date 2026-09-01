from __future__ import annotations

from dataclasses import asdict, replace
from fractions import Fraction
import hashlib
import json
import random
import struct
from tempfile import TemporaryDirectory
from typing import Any, Literal, Sequence

import torch

from cassi_counterflow_runtime import DerivedCounterflowRuntime
from cassi_generative_abstraction import (
    AbstractionProgram,
    GenerativeAbstractionConfig,
    GenerativeAbstractionController,
    ObservableEntityFrame,
    ProgramContext,
    ProgramCorpus,
    ProgramSequence,
    ProgramToken,
    ProgramTransition,
    evaluate_program,
    generate_candidate_programs,
    program_interval_radius,
    observation_from_relation_atoms,
)
from cassi_qi_field import QiFieldError
from cassi_relational_basis import RelationAtoms, RelationEntity
from cassi_universal_data import (
    Atom,
    BoundaryIdentity,
    BoundaryPacket,
    CODEC_AUDIO,
    CODEC_CODE,
    CODEC_JSON,
    CODEC_OPAQUE,
    CODEC_RASTER,
    CODEC_TENSOR,
    CODEC_TEXT,
    Collection,
    Event,
    MnemicObservationReference,
    ObservationNode,
    ObservationView,
    QiIngressJournal,
    Tensor,
    SourceLocation,
    ThalamusAdmission,
    adapt,
)
from run_learned_relational_basis import _atoms, _clone, _step, _world


_INTERIOR_CASES = (
    ((-0.62, -0.48), (0.24, 0.31)),
    ((-0.54, 0.44), (0.28, -0.21)),
    ((0.46, -0.56), (-0.32, 0.27)),
    ((0.58, 0.38), (-0.18, -0.43)),
    ((-0.34, -0.12), (0.52, 0.55)),
    ((-0.26, 0.61), (0.44, 0.03)),
    ((0.38, -0.18), (-0.47, 0.58)),
    ((0.31, 0.52), (-0.55, -0.08)),
)
_EVALUATION_CASES = (
    ((-0.49, -0.37), (0.37, 0.29)),
    ((-0.41, 0.36), (0.39, -0.33)),
    ((0.43, -0.42), (-0.39, 0.34)),
    ((0.51, 0.33), (-0.35, -0.39)),
)
_SEQUENCES = (
    (1, 2, 0),
    (0, 3, 1),
    (2, 1, 3),
    (3, 0, 2),
    (1, 1, 2),
    (0, 0, 3),
    (2, 2, 1),
    (3, 3, 0),
)


def _relative_residual(predicted: torch.Tensor, observed: torch.Tensor) -> float:
    denominator = max(1.0, float(torch.linalg.vector_norm(observed).item()))
    return float(torch.linalg.vector_norm(predicted - observed).item()) / denominator


def _context(
    world: Any,
    *,
    self_id: str,
    previous: RelationAtoms | None = None,
    permuted: bool = False,
    target_index: int = 0,
    sensor_precision: float = 0.0,
) -> ProgramContext:
    atoms, self_index = _atoms(
        world,
        self_id=self_id,
        permuted=permuted,
        target_index=target_index,
    )
    current_view = observation_from_relation_atoms(atoms)
    return ProgramContext(
        current_view=current_view,
        previous_view=observation_from_relation_atoms(atoms if previous is None else previous),
        sensor_precision=sensor_precision,
        role_a_index=self_index,
        regime=atoms.regime,
    )


def _transition(
    *,
    seed: int,
    label: str,
    self_position: tuple[float, float],
    target_position: tuple[float, float],
    action_id: int,
    regime: Literal["interior", "boundary", "temporal"],
    target_velocity: tuple[float, float] = (0.0, 0.0),
    warmup_action: int = 0,
    permuted: bool = False,
) -> ProgramTransition:
    self_id = f"self-{label}"
    world = _world(
        seed=seed,
        world_id=f"world-{label}",
        episode_id=f"episode-{label}",
        self_position=self_position,
        target_position=target_position,
        target_id=f"object-{label}",
        target_velocity=target_velocity,
    )
    initial, _ = _atoms(world, self_id=self_id, permuted=permuted)
    if regime == "temporal":
        _step(world, warmup_action)
        before = _context(
            world,
            self_id=self_id,
            previous=initial,
            permuted=permuted,
        )
    else:
        before = _context(world, self_id=self_id, permuted=permuted)
    _step(world, action_id)
    after = _context(
        world,
        self_id=self_id,
        previous=before.current,
        permuted=permuted,
    )
    return ProgramTransition(action_id, before, after, regime)


def _sequence(
    *,
    seed: int,
    label: str,
    self_position: tuple[float, float],
    target_position: tuple[float, float],
    actions: tuple[int, ...],
    regime: Literal["interior", "boundary", "temporal"],
    target_velocity: tuple[float, float] = (0.0, 0.0),
    warmup_action: int = 0,
    permuted: bool = False,
) -> ProgramSequence:
    self_id = f"self-{label}"
    world = _world(
        seed=seed,
        world_id=f"world-{label}",
        episode_id=f"episode-{label}",
        self_position=self_position,
        target_position=target_position,
        target_id=f"object-{label}",
        target_velocity=target_velocity,
    )
    initial, _ = _atoms(world, self_id=self_id, permuted=permuted)
    if regime == "temporal":
        _step(world, warmup_action)
        first = _context(
            world,
            self_id=self_id,
            previous=initial,
            permuted=permuted,
        )
    else:
        first = _context(world, self_id=self_id, permuted=permuted)
    contexts = [first]
    for action_id in actions:
        previous = contexts[-1].current
        _step(world, action_id)
        contexts.append(
            _context(
                world,
                self_id=self_id,
                previous=previous,
                permuted=permuted,
            )
        )
    return ProgramSequence(actions, tuple(contexts), regime)


def _boundary_position(action_id: int, tangent: float) -> tuple[float, float]:
    return (
        (-0.98, tangent),
        (0.98, tangent),
        (tangent, 0.98),
        (tangent, -0.98),
    )[action_id]


def _build_corpus() -> ProgramCorpus:
    training: list[ProgramTransition] = []
    evaluation: list[ProgramTransition] = []
    for action_id in range(4):
        for case_id, (self_position, target_position) in enumerate(_INTERIOR_CASES):
            training.append(
                _transition(
                    seed=1000 + 100 * action_id + case_id,
                    label=f"train-interior-{action_id}-{case_id}",
                    self_position=self_position,
                    target_position=target_position,
                    action_id=action_id,
                    regime="interior",
                    permuted=(action_id + case_id) % 2 == 1,
                )
            )
        for case_id, tangent in enumerate((-0.43, 0.37)):
            training.append(
                _transition(
                    seed=2000 + 100 * action_id + case_id,
                    label=f"train-boundary-{action_id}-{case_id}",
                    self_position=_boundary_position(action_id, tangent),
                    target_position=((0.21, -0.17), (-0.29, 0.26))[case_id],
                    action_id=action_id,
                    regime="boundary",
                    permuted=case_id == 1,
                )
            )
        for case_id in range(4):
            self_position, target_position = _INTERIOR_CASES[(2 * action_id + case_id) % len(_INTERIOR_CASES)]
            training.append(
                _transition(
                    seed=3000 + 100 * action_id + case_id,
                    label=f"train-temporal-{action_id}-{case_id}",
                    self_position=self_position,
                    target_position=target_position,
                    action_id=action_id,
                    regime="temporal",
                    target_velocity=(0.012, -0.006),
                    warmup_action=case_id,
                    permuted=(action_id + case_id) % 2 == 0,
                )
            )

        for case_id, (self_position, target_position) in enumerate(_EVALUATION_CASES):
            evaluation.append(
                _transition(
                    seed=4000 + 100 * action_id + case_id,
                    label=f"eval-interior-{action_id}-{case_id}",
                    self_position=self_position,
                    target_position=target_position,
                    action_id=action_id,
                    regime="interior",
                    permuted=(action_id + case_id) % 2 == 0,
                )
            )
        for case_id, tangent in enumerate((-0.31, 0.49)):
            evaluation.append(
                _transition(
                    seed=5000 + 100 * action_id + case_id,
                    label=f"eval-boundary-{action_id}-{case_id}",
                    self_position=_boundary_position(action_id, tangent),
                    target_position=((-0.18, 0.22), (0.31, -0.24))[case_id],
                    action_id=action_id,
                    regime="boundary",
                    permuted=case_id == 0,
                )
            )
        for case_id in range(4):
            self_position, target_position = _EVALUATION_CASES[(action_id + case_id) % len(_EVALUATION_CASES)]
            evaluation.append(
                _transition(
                    seed=6000 + 100 * action_id + case_id,
                    label=f"eval-temporal-{action_id}-{case_id}",
                    self_position=self_position,
                    target_position=target_position,
                    action_id=action_id,
                    regime="temporal",
                    target_velocity=(0.012, -0.006),
                    warmup_action=case_id,
                    permuted=(action_id + case_id) % 2 == 1,
                )
            )

    sequences: list[ProgramSequence] = []
    for sequence_id, actions in enumerate(_SEQUENCES):
        self_position, target_position = _INTERIOR_CASES[sequence_id]
        sequences.append(
            _sequence(
                seed=7000 + sequence_id,
                label=f"sequence-interior-{sequence_id}",
                self_position=self_position,
                target_position=target_position,
                actions=actions,
                regime="interior",
                permuted=sequence_id % 2 == 1,
            )
        )
        edge = sequence_id % 4
        boundary_actions = (edge, actions[1], edge)
        sequences.append(
            _sequence(
                seed=8000 + sequence_id,
                label=f"sequence-boundary-{sequence_id}",
                self_position=_boundary_position(edge, (-0.42, 0.36)[sequence_id % 2]),
                target_position=((0.23, 0.19), (-0.27, -0.22))[sequence_id % 2],
                actions=boundary_actions,
                regime="boundary",
                permuted=sequence_id % 2 == 0,
            )
        )
        sequences.append(
            _sequence(
                seed=9000 + sequence_id,
                label=f"sequence-temporal-{sequence_id}",
                self_position=self_position,
                target_position=target_position,
                actions=actions,
                regime="temporal",
                target_velocity=(0.012, -0.006),
                warmup_action=sequence_id % 4,
                permuted=sequence_id % 2 == 0,
            )
        )

    invariance_pairs = []
    relation_cases = (
        ((-0.52, -0.41), (0.18, 0.27), (0.24, -0.16)),
        ((-0.47, 0.36), (0.25, -0.31), (0.19, 0.21)),
        ((0.44, -0.39), (-0.26, 0.32), (-0.17, 0.18)),
        ((0.49, 0.34), (-0.21, -0.28), (-0.23, -0.19)),
    )
    for pair_id, (self_position, target_position, shift) in enumerate(relation_cases):
        shifted_self = (self_position[0] + shift[0], self_position[1] + shift[1])
        shifted_target = (target_position[0] + shift[0], target_position[1] + shift[1])
        left_world = _world(
            seed=10000 + pair_id,
            world_id=f"invariance-left-{pair_id}",
            episode_id=f"invariance-left-{pair_id}",
            self_position=self_position,
            target_position=target_position,
            target_id=f"left-object-{pair_id}",
        )
        right_world = _world(
            seed=11000 + pair_id,
            world_id=f"invariance-right-{pair_id}",
            episode_id=f"invariance-right-{pair_id}",
            self_position=shifted_self,
            target_position=shifted_target,
            target_id=f"renamed-object-{pair_id}",
        )
        invariance_pairs.append(
            (
                _context(left_world, self_id=f"left-self-{pair_id}"),
                _context(
                    right_world,
                    self_id=f"renamed-self-{pair_id}",
                    permuted=True,
                ),
            )
        )
    return ProgramCorpus(
        tuple(training),
        tuple(evaluation),
        tuple(sequences),
        tuple(invariance_pairs),
    )


def _selection_payload(selection: Any) -> dict[str, Any]:
    return {
        "status": selection.status,
        "program_id": selection.program_id,
        "program_sha256": selection.program_sha256,
        "tokens": list(selection.tokens),
        "equivalent_program_ids": list(selection.equivalent_program_ids),
        "margin": selection.margin,
        "score": selection.score,
    }


def _trajectory_fixture(
    *,
    seed: int,
    label: str,
    self_position: tuple[float, float],
    target_position: tuple[float, float],
    hidden_actions: tuple[int, ...],
    target_velocity: tuple[float, float] = (0.0, 0.0),
    warmup_action: int | None = None,
) -> tuple[Any, str, ProgramContext, ProgramContext]:
    self_id = f"self-{label}"
    world = _world(
        seed=seed,
        world_id=f"world-{label}",
        episode_id=f"episode-{label}",
        self_position=self_position,
        target_position=target_position,
        target_id=f"object-{label}",
        target_velocity=target_velocity,
    )
    initial, _ = _atoms(world, self_id=self_id)
    if warmup_action is not None:
        _step(world, warmup_action)
        start = _context(world, self_id=self_id, previous=initial)
    else:
        start = _context(world, self_id=self_id)
    start_world = _clone(world)
    previous = start.current
    for action_id in hidden_actions:
        previous, _ = _atoms(world, self_id=self_id)
        _step(world, action_id)
    goal = _context(world, self_id=self_id, previous=previous)
    return start_world, self_id, start, goal


def _execute_value(
    controller: GenerativeAbstractionController,
    state: Any,
    world: Any,
    self_id: str,
    actions: Sequence[int],
    goal: ProgramContext,
) -> float:
    previous, _ = _atoms(world, self_id=self_id)
    for action_id in actions:
        previous, _ = _atoms(world, self_id=self_id)
        _step(world, action_id)
    observed = _context(world, self_id=self_id, previous=previous)
    selection = controller.select_program(state, "interior")
    if selection.program_id is None:
        return float("inf")
    record = next(
        record
        for record in controller.program_records(state)
        if record.program_id == selection.program_id
    )
    return _relative_residual(
        evaluate_program(record.program, observed),
        evaluate_program(record.program, goal),
    )


def _noisy_context(
    context: ProgramContext,
    *,
    amplitude: float,
    precision: float,
) -> ProgramContext:
    signs = ((1.0, -1.0), (-1.0, 1.0))
    entities = tuple(
        RelationEntity(
            entity.entity_id,
            min(1.0, max(-1.0, entity.x + amplitude * signs[index][0])),
            min(1.0, max(-1.0, entity.y + amplitude * signs[index][1])),
        )
        for index, entity in enumerate(context.current.entities)
    )
    body = json.dumps(
        [(entity.entity_id, entity.x, entity.y) for entity in entities],
        separators=(",", ":"),
    ).encode()
    current = replace(
        context.current,
        state_sha256=hashlib.sha256(body).hexdigest(),
        entities=(entities[0], entities[1]),
    )
    return replace(
        context,
        current_view=observation_from_relation_atoms(current),
        sensor_precision=precision,
    )


def _observable_frames(
    world: Any,
    *,
    self_id: str,
    actions: Sequence[int],
) -> tuple[ObservableEntityFrame, ...]:
    def current_frame() -> ObservableEntityFrame:
        self_entity = None
        objects = []
        regime: Literal["interior", "boundary"] = "interior"
        for target_index in range(world.object_count):
            atoms, self_index = _atoms(
                world,
                self_id=self_id,
                target_index=target_index,
            )
            self_entity = atoms.entities[self_index]
            objects.append(atoms.entities[1 - self_index])
            regime = atoms.regime
        assert self_entity is not None
        return ObservableEntityFrame(
            world_id=world.world_id,
            episode_id=world.episode_id,
            state_sha256=world.state_sha256,
            regime=regime,
            self_entity=self_entity,
            objects=tuple(objects),
        )

    frames = [current_frame()]
    for action_id in actions:
        _step(world, action_id)
        frames.append(current_frame())
    return tuple(frames)


def _shuffled_corpus(corpus: ProgramCorpus) -> ProgramCorpus:
    def shuffled_transitions(
        transitions: tuple[ProgramTransition, ...],
    ) -> tuple[ProgramTransition, ...]:
        result = list(transitions)
        groups: dict[tuple[str, int], list[int]] = {}
        for index, transition in enumerate(transitions):
            groups.setdefault((transition.regime, transition.action_id), []).append(index)
        for indexes in groups.values():
            after = [transitions[index].after for index in indexes]
            for position, index in enumerate(indexes):
                result[index] = replace(
                    transitions[index],
                    after=after[(position + 1) % len(after)],
                )
        return tuple(result)

    sequence_result = list(corpus.sequences)
    groups: dict[str, list[int]] = {}
    for index, sequence in enumerate(corpus.sequences):
        groups.setdefault(sequence.regime, []).append(index)
    for indexes in groups.values():

        finals = [corpus.sequences[index].contexts[-1] for index in indexes]
        for position, index in enumerate(indexes):
            sequence = corpus.sequences[index]
            sequence_result[index] = replace(
                sequence,
                contexts=(*sequence.contexts[:-1], finals[(position + 1) % len(finals)]),
            )
    return ProgramCorpus(
        shuffled_transitions(corpus.training_transitions),
        shuffled_transitions(corpus.evaluation_transitions),
        tuple(sequence_result),
        corpus.invariance_pairs,
    )
_UNIVERSAL_LAYOUTS: tuple[
    tuple[Literal["interior", "boundary"], tuple[float, float], tuple[float, float]],
    ...,
] = (
    ("interior", (-0.60, -0.36), (0.20, 0.28)),
    ("interior", (-0.36, -0.52), (0.44, 0.12)),
    ("interior", (0.52, 0.44), (-0.20, -0.28)),
    ("interior", (0.28, 0.60), (-0.44, -0.12)),
    ("boundary", (-1.00, -0.36), (-0.20, 0.28)),
    ("boundary", (-0.60, -1.00), (0.20, -0.36)),
    ("boundary", (1.00, 0.44), (0.28, -0.28)),
    ("boundary", (0.28, 1.00), (-0.44, 0.28)),
)
_UNIVERSAL_HELDOUT_LAYOUTS: tuple[
    tuple[Literal["interior", "boundary"], tuple[float, float], tuple[float, float]],
    ...,
] = (
    ("interior", (-0.68, -0.20), (0.12, 0.44)),
    ("interior", (-0.28, -0.68), (0.52, -0.04)),
    ("interior", (0.60, 0.28), (-0.12, -0.44)),
    ("interior", (0.20, 0.68), (-0.52, -0.04)),
    ("boundary", (-1.00, -0.20), (-0.20, 0.44)),
    ("boundary", (-0.68, -1.00), (0.12, -0.36)),
    ("boundary", (1.00, 0.28), (0.28, -0.44)),
    ("boundary", (0.20, 1.00), (-0.52, 0.28)),
)
_UNIVERSAL_PROFILE_SHA256 = hashlib.sha256(
    b"cassi.universal-data-field.profile.v1"
).hexdigest()


def _universal_next(
    point: tuple[float, float],
    delta: tuple[float, float],
) -> tuple[float, float]:
    return (
        min(1.0, max(-1.0, point[0] + delta[0])),
        min(1.0, max(-1.0, point[1] + delta[1])),
    )


def _universal_event_id(
    event_index: int,
    action_id: int,
    before: tuple[tuple[float, float], tuple[float, float]],
    after: tuple[tuple[float, float], tuple[float, float]],
) -> str:
    return hashlib.sha256(
        json.dumps(
            {
                "schema": "cassi.universal-paired-event.v1",
                "event_index": event_index,
                "action_id": action_id,
                "before": before,
                "after": after,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _universal_json_payload(
    *,
    points: tuple[tuple[float, float], tuple[float, float]],
    entity_ids: tuple[str, str],
    order: tuple[int, int],
    seed: int,
) -> bytes:
    rng = random.Random(seed)
    id_keys = ("id", "node", "ref", "entity")
    position_keys = ("p", "position", "coords", "site")
    x_keys = ("x", "u", "axis0", "left")
    y_keys = ("y", "v", "axis1", "top")
    records = []
    for entity_index in order:
        position = {
            rng.choice(x_keys): points[entity_index][0],
            rng.choice(y_keys): points[entity_index][1],
        }
        entries = [
            (rng.choice(id_keys), entity_ids[entity_index]),
            (rng.choice(position_keys), position),
        ]
        if rng.randrange(2):
            entries.reverse()
        records.append(dict(entries))
    payload = {rng.choice(("objects", "records", "items", "nodes")): records}
    return json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _universal_grid_cell(value: float) -> int:
    cell = round((value + 1.0) / 0.08)
    if not 0 <= cell < 26 or abs((-1.0 + 0.08 * cell) - value) > 1.0e-12:
        raise QiFieldError("universal raster coordinate is off the 26x26 exact grid")
    return cell


def _universal_raster_payload(
    *,
    points: tuple[tuple[float, float], tuple[float, float]],
    plane_order: tuple[int, int],
) -> bytes:
    payload = bytearray(2 * 26 * 26)
    for plane, entity_index in enumerate(plane_order):
        x, y = points[entity_index]
        column = _universal_grid_cell(x)
        row = _universal_grid_cell(y)
        payload[plane * 26 * 26 + row * 26 + column] = 1
    return bytes(payload)


def _ingest_universal_view(
    journal: QiIngressJournal,
    *,
    event_index: int,
    pair_event_id: str,
    modality: Literal["json", "raster"],
    stage: Literal["before", "after"],
    payload: bytes,
) -> tuple[ObservationView, MnemicObservationReference]:
    codec_id = CODEC_JSON if modality == "json" else CODEC_RASTER
    sequence = 0 if stage == "before" else 1
    stream_id = f"universal:{event_index}:{modality}"
    logical_tick = 2 * event_index + sequence
    packet = BoundaryPacket.create(
        identity=BoundaryIdentity(
            run_id="universal-data-field",
            episode_id=f"episode-{event_index}",
            world_id=f"world-{event_index}",
            session_id="heterogeneous-proof",
            profile_sha256=_UNIVERSAL_PROFILE_SHA256,
            clock_sha256=_UNIVERSAL_PROFILE_SHA256,
            source_epoch="exact-sim-v1",
            source_stream_id=stream_id,
            body_frame_id="anonymous-two-entity-grid",
        ),
        codec_id=codec_id,
        request_id=f"{pair_event_id[:24]}:{modality}:{stage}",
        logical_tick=logical_tick,
        logical_time=Fraction(logical_tick),
        capture_start=Fraction(logical_tick),
        capture_end=Fraction(logical_tick),
        source_sequence=sequence,
        payload_shape=(len(payload),) if modality == "json" else (2, 26, 26),
        payload_dtype="uint8",
        payload=payload,
        ingress_journal_sha256=journal.head_sha256,
        causal_parent_event_id=pair_event_id,
        causal_parent_action_id=f"grid-action-{event_index % 4}",
    )
    packet_reference = journal.append(packet)
    view = adapt(packet, codec_id, evidence=(packet_reference,)).require_selected()
    revision = hashlib.sha256(
        f"{packet.packet_sha256}:{view.view_sha256}".encode()
    ).hexdigest()
    return view, MnemicObservationReference(
        record_id=f"{event_index}:{modality}:{stage}",
        revision=revision,
        packet=packet_reference,
        view_sha256=view.view_sha256,
    )


def _universal_transitions(
    controller: GenerativeAbstractionController,
    journal: QiIngressJournal,
    *,
    event_index: int,
    action_id: int,
    regime: Literal["interior", "boundary"],
    self_position: tuple[float, float],
    target_position: tuple[float, float],
    modalities: tuple[Literal["json", "raster"], ...],
) -> dict[str, ProgramTransition]:
    before_points = (self_position, target_position)
    after_points = (
        _universal_next(self_position, controller.config.action_deltas[action_id]),
        target_position,
    )
    pair_event_id = _universal_event_id(
        event_index,
        action_id,
        before_points,
        after_points,
    )
    entity_ids = (
        f"r-{hashlib.sha256((pair_event_id + ':0').encode()).hexdigest()[:12]}",
        f"r-{hashlib.sha256((pair_event_id + ':1').encode()).hexdigest()[:12]}",
    )
    json_order = (0, 1) if random.Random(event_index).randrange(2) == 0 else (1, 0)
    plane_order = (0, 1) if random.Random(event_index + 1_000_000).randrange(2) == 0 else (1, 0)
    result = {}
    paired = set(modalities) == {"json", "raster"}
    admission = ThalamusAdmission(
        required=paired,
        kind="paired_world_observation" if paired else "world_observation",
        authority="world",
        work_budget=2,
    )
    for modality in modalities:
        if modality == "json":
            before_payload = _universal_json_payload(
                points=before_points,
                entity_ids=entity_ids,
                order=json_order,
                seed=event_index * 7,
            )
            after_payload = _universal_json_payload(
                points=after_points,
                entity_ids=entity_ids,
                order=(json_order[1], json_order[0]),
                seed=event_index * 7 + 1,
            )
        else:
            before_payload = _universal_raster_payload(
                points=before_points,
                plane_order=plane_order,
            )
            after_payload = _universal_raster_payload(
                points=after_points,
                plane_order=plane_order,
            )
        before_view, before_reference = _ingest_universal_view(
            journal,
            event_index=event_index,
            pair_event_id=pair_event_id,
            modality=modality,
            stage="before",
            payload=before_payload,
        )
        after_view, after_reference = _ingest_universal_view(
            journal,
            event_index=event_index,
            pair_event_id=pair_event_id,
            modality=modality,
            stage="after",
            payload=after_payload,
        )
        result[modality] = ProgramTransition(
            action_id=action_id,
            before=ProgramContext(
                current_view=before_view,
                previous_view=before_view,
                output_precision=0.08,
                role_a_index=None,
                regime=regime,
            ),
            after=ProgramContext(
                current_view=after_view,
                previous_view=before_view,
                output_precision=0.08,
                role_a_index=None,
                regime=regime,
            ),
            regime=regime,
            evidence=(before_reference, after_reference),
            admission=admission,
            pair_event_id=pair_event_id if paired else None,
        )
    return result


def _resolved_universal_transition(
    controller: GenerativeAbstractionController,
    transition: ProgramTransition,
) -> ProgramTransition:
    role = controller.infer_observed_role(
        transition.before,
        transition.after,
        transition.action_id,
    )
    if role.status != "selected" or role.value is None:
        raise QiFieldError(role.reason or "universal transition role did not resolve")
    acted_id = transition.before.current.entities[role.value].entity_id
    after_index = next(
        index
        for index, entity in enumerate(transition.after.current.entities)
        if entity.entity_id == acted_id
    )
    return replace(
        transition,
        before=transition.before.resolve_role(role.value),
        after=transition.after.resolve_role(after_index),
    )


def run_universal_data_field_scenario() -> dict[str, Any]:
    controller = GenerativeAbstractionController(GenerativeAbstractionConfig())
    with TemporaryDirectory(prefix="cassi-universal-ingress-") as directory:
        journal = QiIngressJournal(directory, max_bytes=16 * 1024 * 1024)
        experience: dict[
            tuple[int, int],
            dict[str, ProgramTransition],
        ] = {}
        training: list[ProgramTransition] = []
        evaluation: list[ProgramTransition] = []
        training_layouts = {0, 2, 4, 6}
        for layout_index, (regime, self_position, target_position) in enumerate(
            _UNIVERSAL_LAYOUTS
        ):
            for action_id in range(4):
                event_index = layout_index * 4 + action_id
                pair = _universal_transitions(
                    controller,
                    journal,
                    event_index=event_index,
                    action_id=action_id,
                    regime=regime,
                    self_position=self_position,
                    target_position=target_position,
                    modalities=("json", "raster"),
                )
                experience[(layout_index, action_id)] = pair
                destination = training if layout_index in training_layouts else evaluation
                destination.extend((pair["json"], pair["raster"]))

        invariance_pairs = []
        for left_layout, right_layout in ((0, 1), (2, 3), (4, 5), (6, 7)):
            for action_id in range(4):
                for modality in ("json", "raster"):
                    left = _resolved_universal_transition(
                        controller,
                        experience[(left_layout, action_id)][modality],
                    )
                    right = _resolved_universal_transition(
                        controller,
                        experience[(right_layout, action_id)][modality],
                    )
                    invariance_pairs.append((left.before, right.before))
        corpus = ProgramCorpus(
            tuple(training),
            tuple(evaluation),
            invariance_pairs=tuple(invariance_pairs),
        )
        state, receipt = controller.synthesize(corpus)
        field_sha256 = controller._tensor_sha256(state.field)
        if receipt.interior.status != "selected" or receipt.boundary.status != "selected":
            raise RuntimeError("universal field did not select interior and boundary programs")

        experience_results = [
            controller.evaluate_observed_transition(state, transition)
            for pair in experience.values()
            for transition in pair.values()
        ]
        experience_residuals = [
            result.value
            for result in experience_results
            if result.status == "selected" and result.value is not None
        ]

        cross_view_residuals = []
        for pair in experience.values():
            json_transition = _resolved_universal_transition(controller, pair["json"])
            raster_transition = _resolved_universal_transition(controller, pair["raster"])
            selection = (
                receipt.interior
                if json_transition.regime == "interior"
                else receipt.boundary
            )
            assert selection.program_id is not None
            record = next(
                item
                for item in controller.program_records(state)
                if item.program_id == selection.program_id
            )
            left_context = replace(
                json_transition.before,
                action_delta=controller.config.action_deltas[json_transition.action_id],
            )
            right_context = replace(
                raster_transition.before,
                action_delta=controller.config.action_deltas[raster_transition.action_id],
            )
            if record.program.is_transition_law:
                left = evaluate_program(record.program, left_context)
                right = evaluate_program(record.program, right_context)
            else:
                operator = controller.operator(
                    state,
                    record.program_id,
                    json_transition.action_id,
                )
                left = operator @ evaluate_program(record.program, left_context)
                right = operator @ evaluate_program(record.program, right_context)
            cross_view_residuals.append(_relative_residual(left, right))

        heldout: list[ProgramTransition] = []
        modality_counts = {"json": 0, "raster": 0}
        heldout_start = len(_UNIVERSAL_LAYOUTS) * 4
        for layout_index, (regime, self_position, target_position) in enumerate(
            _UNIVERSAL_HELDOUT_LAYOUTS
        ):
            for action_id in range(4):
                modality: Literal["json", "raster"] = (
                    "json" if (layout_index + action_id) % 2 == 0 else "raster"
                )
                event_index = heldout_start + layout_index * 4 + action_id
                transition = _universal_transitions(
                    controller,
                    journal,
                    event_index=event_index,
                    action_id=action_id,
                    regime=regime,
                    self_position=self_position,
                    target_position=target_position,
                    modalities=(modality,),
                )[modality]
                modality_counts[modality] += 1
                heldout.append(transition)
        heldout_results = [
            controller.evaluate_observed_transition(state, transition)
            for transition in heldout
        ]
        heldout_residuals = [
            result.value
            for result in heldout_results
            if result.status == "selected" and result.value is not None
        ]

        def single_view_transition(
            transition: ProgramTransition,
        ) -> ProgramTransition:
            assert transition.admission is not None
            return replace(
                transition,
                admission=replace(
                    transition.admission,
                    kind="single_world_observation",
                ),
                pair_event_id=None,
            )

        directional_transfer: dict[str, dict[str, Any]] = {}
        directions: tuple[
            tuple[
                Literal["json", "raster"],
                Literal["json", "raster"],
            ],
            ...,
        ] = (("json", "raster"), ("raster", "json"))
        for source_modality, destination_modality in directions:
            directional_controller = GenerativeAbstractionController(
                GenerativeAbstractionConfig()
            )
            source_training = tuple(
                single_view_transition(transition)
                for transition in training
                if transition.before.current_view.modality == source_modality
            )
            source_evaluation = tuple(
                single_view_transition(transition)
                for transition in evaluation
                if transition.before.current_view.modality == source_modality
            )
            directional_state, directional_receipt = (
                directional_controller.synthesize(
                    ProgramCorpus(source_training, source_evaluation)
                )
            )
            destination_queries = tuple(
                transition
                for transition in heldout
                if transition.before.current_view.modality == destination_modality
            )
            destination_results = tuple(
                directional_controller.evaluate_observed_transition(
                    directional_state,
                    transition,
                )
                for transition in destination_queries
            )
            destination_residuals = tuple(
                result.value
                for result in destination_results
                if result.status == "selected" and result.value is not None
            )
            exact = (
                len(destination_residuals) == len(destination_queries)
                and max(destination_residuals, default=float("inf")) <= 1.0e-12
            )
            program_hashes = {
                "interior": directional_receipt.interior.program_sha256,
                "boundary": directional_receipt.boundary.program_sha256,
            }
            directional_transfer[
                f"{source_modality}_to_{destination_modality}"
            ] = {
                "status": "supported" if exact else "unsupported",
                "source_experience": len(source_training)
                + len(source_evaluation),
                "heldout_queries": len(destination_queries),
                "heldout_exact": len(destination_residuals),
                "max_residual": max(
                    destination_residuals,
                    default=float("inf"),
                ),
                "program_sha256": program_hashes,
                "programs_match_paired_field": program_hashes
                == {
                    "interior": receipt.interior.program_sha256,
                    "boundary": receipt.boundary.program_sha256,
                },
            }

        ambiguous_pair = _universal_transitions(
            controller,
            journal,
            event_index=heldout_start + len(heldout),
            action_id=0,
            regime="boundary",
            self_position=(-1.0, -0.36),
            target_position=(-1.0, 0.44),
            modalities=("json", "raster"),
        )
        ambiguous_statuses = [
            controller.infer_observed_role(
                transition.before,
                transition.after,
                transition.action_id,
            ).status
            for transition in ambiguous_pair.values()
        ]

        shuffled_training = list(training)
        raster_indexes = [
            index
            for index, transition in enumerate(shuffled_training)
            if transition.before.current_view.modality == "raster"
        ]
        raster_afters = [shuffled_training[index].after for index in raster_indexes]
        for offset, index in enumerate(raster_indexes):
            shuffled_training[index] = replace(
                shuffled_training[index],
                after=raster_afters[(offset + 1) % len(raster_afters)],
            )
        shuffled_pairing_failed = False
        try:
            controller.synthesize(
                replace(corpus, training_transitions=tuple(shuffled_training))
            )
        except QiFieldError:
            shuffled_pairing_failed = True

        missing_pair_identity_failed = False
        try:
            replace(training[0], pair_event_id=None)
        except QiFieldError:
            missing_pair_identity_failed = True

        def hashes_only_view(view: ObservationView) -> ObservationView:
            return ObservationView(
                view.packet,
                view.codec_id,
                view.modality,
                Atom(
                    SourceLocation(
                        view.packet.packet_sha256,
                        view.codec_id,
                        (),
                        (0, len(view.packet.payload)),
                    ),
                    "bytes",
                    None,
                ),
            )

        def hashes_only_context(context: ProgramContext) -> ProgramContext:
            return replace(
                context,
                current_view=hashes_only_view(context.current_view),
                previous_view=(
                    None
                    if context.previous_view is None
                    else hashes_only_view(context.previous_view)
                ),
            )

        def hashes_only_transition(
            transition: ProgramTransition,
        ) -> ProgramTransition:
            return replace(
                transition,
                before=hashes_only_context(transition.before),
                after=hashes_only_context(transition.after),
            )

        hashes_only_failed = False
        try:
            controller.synthesize(
                replace(
                    corpus,
                    training_transitions=tuple(
                        hashes_only_transition(transition)
                        for transition in corpus.training_transitions
                    ),
                    evaluation_transitions=tuple(
                        hashes_only_transition(transition)
                        for transition in corpus.evaluation_transitions
                    ),
                )
            )
        except QiFieldError:
            hashes_only_failed = True

        interior = receipt.interior
        assert interior.program_id is not None
        evidence_ablated = state
        for program_id in interior.equivalent_program_ids:
            evidence_ablated = controller.clear_program_evidence(
                evidence_ablated,
                program_id,
            )
        operator_ablated = controller.clear_program_operators(
            state,
            interior.program_id,
        )

        checkpoint = controller.dump_state_bytes(state)
        restarted = controller.load_state_bytes(checkpoint)
        inference_before = controller._tensor_sha256(restarted.field)
        restarted_results = [
            controller.evaluate_observed_transition(restarted, transition)
            for transition in heldout
        ]
        inference_after = controller._tensor_sha256(restarted.field)

        last_transition = ambiguous_pair["raster"]
        last_reference = last_transition.evidence[-1].packet
        idempotent_reference = journal.append(last_transition.after.current_view.packet)
        replayed = QiIngressJournal(directory, max_bytes=16 * 1024 * 1024)
        replay = replayed.replay()
        replay_exact = all(
            replayed.read_packet(reference).packet_sha256 == reference.packet_sha256
            for reference in replay
        )

        result = {
            "result": "UNIVERSAL_DATA_FIELD_OK",
            "experience_pairs": len(experience),
            "experience_views": len(training) + len(evaluation),
            "experience_exact": len(experience_residuals),
            "experience_max_residual": max(experience_residuals),
            "heldout_queries": len(heldout),
            "heldout_modalities": modality_counts,
            "heldout_exact": len(heldout_residuals),
            "heldout_max_residual": max(heldout_residuals),
            "cross_view_max_residual": max(cross_view_residuals),
            "directional_transfer": directional_transfer,
            "ambiguous_statuses": ambiguous_statuses,
            "pairing_controls": {
                "shuffled_failed": shuffled_pairing_failed,
                "missing_identity_failed": missing_pair_identity_failed,
                "hashes_only_failed": hashes_only_failed,
            },
            "ablations": {
                "evidence_status": controller.select_program(
                    evidence_ablated,
                    "interior",
                ).status,
                "operators_supported": controller.program_operators_supported(
                    operator_ablated,
                    interior.program_id,
                ),
            },
            "restart": {
                "bytes_exact": checkpoint == controller.dump_state_bytes(restarted),
                "field_exact": inference_before == field_sha256,
                "replay_exact": replay_exact,
                "inference_frozen": inference_before == inference_after,
                "outputs_exact": heldout_results == restarted_results,
            },
            "ingress": {
                "entries": len(replay),
                "head_sha256": replayed.head_sha256,
                "idempotent": idempotent_reference == last_reference,
            },
            "controls": {
                "teacher_or_model_calls": 0,
                "adaptive_persistent_objects": ["QiFieldState.field"],
            },
            "field_sha256": field_sha256,
        }
        required = {
            "experience_matrix": len(experience) == 32
            and len(training) + len(evaluation) == 64
            and len(experience_residuals) == 64
            and max(experience_residuals) <= 1.0e-12,
            "heldout_matrix": len(heldout_residuals) == 32
            and modality_counts == {"json": 16, "raster": 16}
            and max(heldout_residuals) <= 1.0e-12,
            "cross_view": max(cross_view_residuals) <= 1.0e-12,
            "ambiguity": ambiguous_statuses == ["ambiguous", "ambiguous"],
            "pairing": (
                shuffled_pairing_failed
                and missing_pair_identity_failed
                and hashes_only_failed
            ),
            "directional_transfer": all(
                row["status"] == "supported"
                and row["source_experience"] == 32
                and row["heldout_queries"] == row["heldout_exact"] == 16
                and row["max_residual"] <= 1.0e-12
                and row["programs_match_paired_field"]
                for row in directional_transfer.values()
            ),
            "ablations": result["ablations"]
            == {"evidence_status": "exhausted", "operators_supported": False},
            "restart": all(result["restart"].values()),
            "ingress": replay_exact
            and idempotent_reference == last_reference
            and len(replay) == len(training) * 2 + len(evaluation) * 2 + len(heldout) * 2 + 4,
        }
        failures = [name for name, passed in required.items() if not passed]
        if failures:
            raise RuntimeError(
                "universal data field scenario failed: "
                + ", ".join(failures)
                + "; metrics="
                + json.dumps(result, sort_keys=True)
            )
        return result



def run_typed_adapter_scenario() -> dict[str, Any]:
    """Exercise one exact conformance case per currently declared adapter."""

    cases = {
        "text": (
            CODEC_TEXT,
            "Cassi field flow: λ\n".encode("utf-8"),
            "uint8",
            None,
            "utf8",
        ),
        "code": (
            CODEC_CODE,
            b"def translate(value: float) -> float:\n    return value + 1.0\n",
            "uint8",
            None,
            "python_ast",
        ),
        "audio": (
            CODEC_AUDIO,
            struct.pack("<6d", -0.5, -0.25, 0.0, 0.25, 0.5, 0.75),
            "float64",
            (2, 3),
            "dense_tensor",
        ),
        "scientific_tensor": (
            CODEC_TENSOR,
            struct.pack("<6f", 1.0, 2.0, 3.0, 4.0, 5.0, 6.0),
            "float32",
            (2, 3),
            "dense_tensor",
        ),
        "opaque": (
            CODEC_OPAQUE,
            bytes((0, 255, 17, 34, 51, 68)),
            "uint8",
            None,
            "opaque_bytes",
        ),
    }

    def nodes(root: ObservationNode) -> tuple[ObservationNode, ...]:
        result: list[ObservationNode] = []

        def visit(node: ObservationNode) -> None:
            result.append(node)
            if isinstance(node, Collection):
                for _, child in node.items:
                    visit(child)
            elif isinstance(node, Event):
                visit(node.operation)

        visit(root)
        return tuple(result)

    def packet_for(
        journal: QiIngressJournal,
        *,
        index: int,
        name: str,
        codec_id: str,
        payload: bytes,
        dtype: str,
        shape: tuple[int, ...] | None,
        valid: bool = True,
    ) -> BoundaryPacket:
        packet_shape = (
            tuple(shape)
            if shape is not None
            else ((len(payload),) if valid else ())
        )
        return BoundaryPacket.create(
            identity=BoundaryIdentity(
                run_id="universal-adapter-conformance",
                episode_id=f"adapter-{index}",
                world_id=f"adapter-{name}",
                session_id="universal-adapter-conformance",
                profile_sha256=_UNIVERSAL_PROFILE_SHA256,
                clock_sha256=_UNIVERSAL_PROFILE_SHA256,
                source_epoch="exact-fixture-v1",
                source_stream_id=f"adapter-{name}-{index}",
                body_frame_id="acquired-payload",
            ),
            codec_id=codec_id,
            request_id=f"adapt-{name}-{index}",
            logical_tick=index,
            logical_time=Fraction(index, 1),
            capture_start=Fraction(index, 1),
            capture_end=Fraction(index, 1),
            source_sequence=0,
            payload_shape=packet_shape,
            payload_dtype=dtype,
            payload=payload,
            ingress_journal_sha256=journal.head_sha256,
            valid=valid,
        )

    with TemporaryDirectory(prefix="cassi-typed-adapters-") as directory:
        journal = QiIngressJournal(directory, max_bytes=4 * 1024 * 1024)
        modalities: dict[str, dict[str, Any]] = {}
        packets: list[BoundaryPacket] = []
        references = []
        for index, (name, case) in enumerate(cases.items()):
            codec_id, payload, dtype, shape, syntax = case
            packet = packet_for(
                journal,
                index=index,
                name=name,
                codec_id=codec_id,
                payload=payload,
                dtype=dtype,
                shape=shape,
            )
            reference = journal.append(packet)
            adapted = adapt(packet, codec_id, evidence=(reference,))
            view = adapted.require_selected()
            repeated = adapt(packet, codec_id, evidence=(reference,)).require_selected()
            view_nodes = nodes(view.root)
            modalities[name] = {
                "adapter_status": adapted.status,
                "codec_id": codec_id,
                "syntax_exposed": syntax,
                "root_constructor": type(view.root).__name__,
                "round_trip_exact": view.round_trip() == payload,
                "deterministic_view": view.view_sha256 == repeated.view_sha256,
                "provenance_exact": all(
                    node.source.packet_sha256 == packet.packet_sha256
                    and node.source.codec_id == codec_id
                    for node in view_nodes
                ),
                "node_count": len(view_nodes),
                "block_backed": isinstance(view.root, Tensor)
                and view.root.block_sha256 == packet.payload_sha256,
                "semantic_status": "unsupported",
                "semantic_reason": "no_measured_semantic_task",
            }
            packets.append(packet)
            references.append(reference)

        last_packet = packets[-1]
        last_reference = references[-1]
        idempotent_reference = journal.append(last_packet)
        replayed = QiIngressJournal(directory, max_bytes=4 * 1024 * 1024)
        replay = replayed.replay()
        replay_exact = all(
            replayed.read_packet(reference).packet_sha256
            == packet.packet_sha256
            and replayed.read_payload(reference) == packet.payload
            for reference, packet in zip(replay, packets, strict=True)
        )

        malformed_cases = {
            "text": (CODEC_TEXT, b"\xff", "uint8", (1,)),
            "code": (CODEC_CODE, b"def broken(", "uint8", (11,)),
            "audio": (CODEC_AUDIO, struct.pack("<d", 0.0), "float64", (2,)),
            "scientific_tensor": (
                CODEC_TENSOR,
                struct.pack("<f", 1.0),
                "float32",
                (2,),
            ),
            "opaque": (CODEC_OPAQUE, b"abc", "uint8", (2,)),
        }
        malformed: dict[str, str | None] = {}
        for offset, (name, case) in enumerate(malformed_cases.items(), start=100):
            codec_id, payload, dtype, shape = case
            packet = packet_for(
                journal,
                index=offset,
                name=f"malformed-{name}",
                codec_id=codec_id,
                payload=payload,
                dtype=dtype,
                shape=shape,
            )
            malformed[name] = adapt(packet, codec_id).reason

        no_sample = packet_for(
            journal,
            index=200,
            name="no-sample",
            codec_id=CODEC_AUDIO,
            payload=b"",
            dtype="float64",
            shape=(),
            valid=False,
        )
        controls = {
            "malformed": malformed,
            "unknown_codec": adapt(
                last_packet,
                "cassi.codec.unknown.v1",
            ).reason,
            "descriptor_mismatch": adapt(last_packet, CODEC_TEXT).reason,
            "no_sample": adapt(no_sample, CODEC_AUDIO).reason,
        }
        result = {
            "result": "TYPED_ADAPTER_CONFORMANCE_OK",
            "modalities": modalities,
            "controls": controls,
            "journal": {
                "entries": len(replay),
                "replay_exact": replay_exact,
                "idempotent": idempotent_reference == last_reference,
                "one_ingress_interface": "adapt",
            },
        }
        required = (
            len(modalities) == len(cases)
            and all(
                row["adapter_status"] == "selected"
                and row["round_trip_exact"]
                and row["deterministic_view"]
                and row["provenance_exact"]
                and row["block_backed"]
                == (name in {"audio", "scientific_tensor"})
                and row["semantic_status"] == "unsupported"
                for name, row in modalities.items()
            )
            and controls["malformed"]
            == {name: "malformed_input" for name in malformed_cases}
            and controls["unknown_codec"] == "no_adapter"
            and controls["descriptor_mismatch"] == "descriptor_mismatch"
            and controls["no_sample"] == "invalid_or_no_sample"
            and all(result["journal"][key] for key in ("replay_exact", "idempotent"))
        )
        if not required:
            raise RuntimeError(
                "typed adapter scenario failed: "
                + json.dumps(result, sort_keys=True)
            )
        return result


def run_generative_abstraction_scenario() -> dict[str, Any]:
    controller = GenerativeAbstractionController(GenerativeAbstractionConfig())
    corpus = _build_corpus()
    state, receipt = controller.synthesize(corpus)
    field_sha256 = controller._tensor_sha256(state.field)
    records = controller.program_records(state)

    interior = receipt.interior
    boundary = receipt.boundary
    temporal = receipt.temporal
    if interior.program_id is None or boundary.program_id is None or temporal.program_id is None:
        raise RuntimeError(
            f"program synthesis did not settle: {interior.status}, {boundary.status}, {temporal.status}"
        )
    record_by_id = {record.program_id: record for record in records}
    interior_record = record_by_id[interior.program_id]
    boundary_record = record_by_id[boundary.program_id]

    left_invariant, right_invariant = corpus.invariance_pairs[0]
    invariance_residual = _relative_residual(
        evaluate_program(interior_record.program, left_invariant),
        evaluate_program(interior_record.program, right_invariant),
    )
    action_id = 1
    left_consequence = controller.operator(state, interior.program_id, action_id) @ evaluate_program(
        interior_record.program,
        left_invariant,
    )
    right_consequence = controller.operator(state, interior.program_id, action_id) @ evaluate_program(
        interior_record.program,
        right_invariant,
    )
    consequence_invariance = _relative_residual(left_consequence, right_consequence)

    stationary_world, stationary_self, stationary_start, stationary_goal = _trajectory_fixture(
        seed=12000,
        label="stationary-endpoint",
        self_position=(-0.16, 0.12),
        target_position=(0.41, -0.27),
        hidden_actions=(1, 2, 0),
    )
    historical = controller.generate_trajectory(
        state,
        stationary_start,
        stationary_goal,
        steps=3,
        mode="historical",
    )
    prospective = controller.generate_trajectory(
        state,
        stationary_start,
        stationary_goal,
        steps=3,
        mode="prospective",
    )
    prospective_execution_residual = (
        _execute_value(
            controller,
            state,
            stationary_world,
            stationary_self,
            prospective.actions or (),
            stationary_goal,
        )
        if prospective.actions is not None
        else float("inf")
    )

    moving_world, moving_self, moving_start, moving_goal = _trajectory_fixture(
        seed=12100,
        label="moving-endpoint",
        self_position=(-0.21, -0.11),
        target_position=(0.28, 0.24),
        hidden_actions=(1, 2, 0),
        target_velocity=(0.012, -0.006),
        warmup_action=3,
    )
    moving = controller.generate_trajectory(
        state,
        moving_start,
        moving_goal,
        steps=3,
        mode="prospective",
    )
    moving_execution_residual = (
        _execute_value(
            controller,
            state,
            moving_world,
            moving_self,
            moving.actions or (),
            moving_goal,
        )
        if moving.actions is not None
        else float("inf")
    )

    noise_rows = []
    for amplitude in (0.0, 0.01, 0.02, 0.03, 0.06):
        noisy_goal = _noisy_context(
            stationary_goal,
            amplitude=amplitude,
            precision=amplitude,
        )
        first = controller.generate_trajectory(
            state,
            stationary_start,
            noisy_goal,
            steps=3,
            mode="prospective",
        )
        second = controller.generate_trajectory(
            state,
            stationary_start,
            noisy_goal,
            steps=3,
            mode="prospective",
        )
        noise_rows.append(
            {
                "amplitude": amplitude,
                "status": first.status,
                "equivalent_count": len(first.equivalent_actions),
                "deterministic": first == second,
                "interval_radius": program_interval_radius(interior_record.program, noisy_goal),
                "true_action_retained": (1, 2, 0) in first.equivalent_actions,
            }
        )

    diagnostic_world = _world(
        seed=13000,
        world_id="diagnostic-world",
        episode_id="diagnostic-episode",
        self_position=(-0.18, 0.16),
        target_position=(0.34, -0.22),
        target_id="relevant-target",
        distractors=(
            ("moving-distractor-a", (-0.42, -0.31), (0.08, 0.0)),
            ("moving-distractor-b", (0.16, 0.48), (0.0, -0.08)),
        ),
    )
    diagnostic_frames = _observable_frames(
        diagnostic_world,
        self_id="diagnostic-self",
        actions=(1, 2, 0),
    )
    diagnostic_hypotheses = controller.expand_each_object(diagnostic_frames)
    diagnostic_resolution = controller.resolve_each_object(
        state,
        diagnostic_frames,
        (1, 2, 0),
    )

    hidden_world = _world(
        seed=13100,
        world_id="hidden-world",
        episode_id="hidden-episode",
        self_position=(0.12, -0.19),
        target_position=(0.38, 0.31),
        target_id="hidden-a",
        distractors=(
            ("hidden-b", (-0.36, 0.27), (0.0, 0.0)),
            ("hidden-c", (0.24, -0.49), (0.0, 0.0)),
        ),
    )
    hidden_frames = _observable_frames(
        hidden_world,
        self_id="hidden-self",
        actions=(1, 2, 0),
    )
    hidden_resolution = controller.resolve_each_object(
        state,
        hidden_frames,
        (1, 2, 0),
    )

    role_attempts = 0
    role_correct = 0
    role_false_confidence = 0
    role_statuses: dict[str, int] = {"selected": 0, "ambiguous": 0, "exhausted": 0}
    quadrants = ((0.42, 0.37), (-0.42, 0.37), (-0.42, -0.37), (0.42, -0.37))
    passive_statuses = []
    for quadrant_id, target_position in enumerate(quadrants):
        passive_world = _world(
            seed=14000 + quadrant_id,
            world_id=f"passive-world-{quadrant_id}",
            episode_id=f"passive-episode-{quadrant_id}",
            self_position=(0.0, 0.0),
            target_position=target_position,
            target_id=f"passive-target-{quadrant_id}",
        )
        passive_atoms, _ = _atoms(passive_world, self_id=f"passive-self-{quadrant_id}")
        passive_statuses.append(controller.resolve_roles(state, passive_atoms).status)
        for action_id in range(4):
            for permuted in (False, True):
                world = _world(
                    seed=14100 + 100 * quadrant_id + 10 * action_id + int(permuted),
                    world_id=f"role-world-{quadrant_id}-{action_id}-{int(permuted)}",
                    episode_id=f"role-episode-{quadrant_id}-{action_id}-{int(permuted)}",
                    self_position=(0.0, 0.0),
                    target_position=target_position,
                    target_id=f"role-target-{quadrant_id}-{action_id}-{int(permuted)}",
                )
                self_id = f"role-self-{quadrant_id}-{action_id}-{int(permuted)}"
                before, true_self = _atoms(world, self_id=self_id, permuted=permuted)
                _step(world, action_id)
                after, _ = _atoms(world, self_id=self_id, permuted=permuted)
                resolution = controller.resolve_roles(
                    state,
                    before,
                    action_id=action_id,
                    after=after,
                )
                role_attempts += 1
                role_statuses[resolution.status] += 1
                role_correct += int(
                    resolution.status == "selected"
                    and resolution.selected_self_index == true_self
                )
                role_false_confidence += int(
                    resolution.status == "selected"
                    and resolution.selected_self_index != true_self
                )

    boundary_cases = (
        (0, (-0.98, -0.31), (0, 0, 2)),
        (0, (-0.98, 0.36), (0, 3, 0)),
        (0, (-0.96, 0.48), (2, 0, 0)),
        (1, (0.98, -0.37), (1, 1, 2)),
        (1, (0.98, 0.29), (1, 3, 1)),
        (1, (0.96, -0.46), (2, 1, 1)),
        (2, (-0.34, 0.98), (2, 2, 1)),
        (2, (0.39, 0.98), (2, 0, 2)),
        (2, (-0.47, 0.96), (1, 2, 2)),
        (3, (-0.32, -0.98), (3, 3, 1)),
        (3, (0.41, -0.98), (3, 0, 3)),
        (3, (-0.45, -0.96), (1, 3, 3)),
    )
    boundary_exact = 0
    boundary_false_settlements = 0
    boundary_residuals = []
    for case_id, (_, self_position, hidden_actions) in enumerate(boundary_cases):
        start_world, self_id, start, goal = _trajectory_fixture(
            seed=15000 + case_id,
            label=f"boundary-probe-{case_id}",
            self_position=self_position,
            target_position=((0.26, 0.21), (-0.28, -0.23))[case_id % 2],
            hidden_actions=hidden_actions,
        )
        proposal = controller.generate_trajectory(
            state,
            start,
            goal,
            steps=3,
            mode="prospective",
            regime="boundary",
        )
        if proposal.actions is None:
            boundary_false_settlements += int(proposal.status == "selected")
            boundary_residuals.append(float("inf"))
            continue
        execution = _clone(start_world)
        previous, _ = _atoms(execution, self_id=self_id)
        for action_id in proposal.actions:
            previous, _ = _atoms(execution, self_id=self_id)
            _step(execution, action_id)
        observed = _context(execution, self_id=self_id, previous=previous)
        residual = _relative_residual(
            evaluate_program(boundary_record.program, observed),
            evaluate_program(boundary_record.program, goal),
        )
        boundary_residuals.append(residual)
        exact = residual <= 1.0e-12
        boundary_exact += int(exact)
        boundary_false_settlements += int(proposal.status == "selected" and not exact)

    shuffled_state, shuffled_receipt = controller.synthesize(_shuffled_corpus(corpus))
    shuffled_changed = (
        shuffled_receipt.interior.status != "selected"
        or shuffled_receipt.interior.program_sha256 != interior.program_sha256
    )

    evidence_ablated = state
    for program_id in interior.equivalent_program_ids:
        evidence_ablated = controller.clear_program_evidence(
            evidence_ablated,
            program_id,
        )
    evidence_ablation = controller.select_program(evidence_ablated, "interior")
    operator_ablated = controller.clear_program_operators(state, interior.program_id)
    operator_ablation = controller.generate_trajectory(
        operator_ablated,
        stationary_start,
        stationary_goal,
        steps=3,
        mode="prospective",
    )

    checkpoint = controller.dump_state_bytes(state)
    restarted = controller.load_state_bytes(checkpoint)
    restart_exact = checkpoint == controller.dump_state_bytes(restarted)
    inference_before = controller._tensor_sha256(restarted.field)
    controller.select_program(restarted, "interior")
    controller.generate_trajectory(
        restarted,
        stationary_start,
        stationary_goal,
        steps=3,
        mode="prospective",
    )
    controller.resolve_roles(restarted, corpus.evaluation_transitions[0].before.current)
    inference_after = controller._tensor_sha256(restarted.field)

    consolidations_before = interior_record.consolidations
    consolidated, confirmed = controller.consolidate_program(
        state,
        interior.program_id,
        left_invariant,
        right_invariant,
    )
    consolidations_after = next(
        record.consolidations
        for record in controller.program_records(consolidated)
        if record.program_id == interior.program_id
    )
    mismatched_context = corpus.evaluation_transitions[0].after
    failed_state, failed_confirmed = controller.consolidate_program(
        state,
        interior.program_id,
        left_invariant,
        mismatched_context,
    )

    provider_error = None
    try:
        DerivedCounterflowRuntime().plan(
            {"mode": "generate_abstraction"},
            primary_field_sha256="0" * 64,
        )
    except QiFieldError as exc:
        provider_error = str(exc)

    add_left = AbstractionProgram(
        (
            ProgramToken.ROLE_A,
            ProgramToken.POSITION,
            ProgramToken.ROLE_B,
            ProgramToken.POSITION,
            ProgramToken.ADD,
            ProgramToken.PACK4,
        )
    )
    add_right = AbstractionProgram(
        (
            ProgramToken.ROLE_B,
            ProgramToken.POSITION,
            ProgramToken.ROLE_A,
            ProgramToken.POSITION,
            ProgramToken.ADD,
            ProgramToken.PACK4,
        )
    )
    folded = AbstractionProgram(
        (
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ONE,
            ProgramToken.ADD,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.PACK4,
        )
    )
    direct = AbstractionProgram(
        (
            ProgramToken.CONST_ONE,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.CONST_ZERO,
            ProgramToken.PACK4,
        )
    )
    each_object_rejected = False
    try:
        AbstractionProgram(
            (
                ProgramToken.EACH_OBJECT,
                ProgramToken.POSITION,
                ProgramToken.PACK4,
            )
        )
    except QiFieldError:
        each_object_rejected = True

    result = {
        "result": "GENERATIVE_ABSTRACTION_OK",
        "claim": "bounded field-generated typed relational abstraction",
        "candidate_count": receipt.candidate_count,
        "grammar_program_count": len(generate_candidate_programs(controller.config)),
        "mask_widths": list(receipt.mask_widths),
        "breaths": receipt.breaths,
        "interior": _selection_payload(interior),
        "boundary": _selection_payload(boundary),
        "temporal": _selection_payload(temporal),
        "program_evidence": {
            str(record.program_id): {
                "tokens": list(record.program.decoded),
                **asdict(record.evidence),
            }
            for record in records
        },
        "cartesian_generated": {
            "contains_role_a": "ROLE_A" in interior.tokens,
            "contains_role_b": "ROLE_B" in interior.tokens,
            "contains_position": "POSITION" in interior.tokens,
            "contains_subtract": "SUBTRACT" in interior.tokens,
            "contains_pack4": "PACK4" in interior.tokens,
            "role_equivalence_count": len(interior.equivalent_program_ids),
            "candidate_source": "bounded_typed_grammar",
        },
        "renaming_translation": {
            "program_residual": invariance_residual,
            "action_consequence_residual": consequence_invariance,
        },
        "canonicalization": {
            "commutative_hash_equal": add_left.sha256 == add_right.sha256,
            "constant_fold_hash_equal": folded.sha256 == direct.sha256,
        },
        "each_object": {
            "directive_rejected_as_scalar_operand": each_object_rejected,
            "expansion_count": len(diagnostic_hypotheses),
            "candidate_entity_ids": list(diagnostic_resolution.candidate_entity_ids),
            "first_observation_has_no_previous": all(
                hypothesis.contexts[0].previous is None
                for hypothesis in diagnostic_hypotheses
            ),
            "moving_candidate_second_delta": [
                float(value.real.item())
                for value in evaluate_program(
                    AbstractionProgram(
                        (
                            ProgramToken.ROLE_B,
                            ProgramToken.DELTA,
                            ProgramToken.PACK4,
                        )
                    ),
                    diagnostic_hypotheses[1].contexts[1],
                )[:2]
            ],
        },
        "stationary_endpoint": {
            "historical_status": historical.status,
            "historical_equivalent_count": len(historical.equivalent_actions),
            "prospective_status": prospective.status,
            "prospective_actions": list(prospective.actions or ()),
            "prospective_equivalent_count": len(prospective.equivalent_actions),
            "execution_residual": prospective_execution_residual,
        },
        "moving_target": {
            "temporal_tokens": list(temporal.tokens),
            "status": moving.status,
            "actions": list(moving.actions or ()),
            "equivalent_count": len(moving.equivalent_actions),
            "execution_residual": moving_execution_residual,
        },
        "noise_sweep": noise_rows,
        "diagnostic_distractors": {
            "status": diagnostic_resolution.status,
            "selected_index": diagnostic_resolution.selected_index,
            "equivalent_indices": list(diagnostic_resolution.equivalent_indices),
            "residuals": list(diagnostic_resolution.residuals),
            "selected_entity_id": diagnostic_resolution.selected_entity_id,
            "equivalent_entity_ids": list(
                diagnostic_resolution.equivalent_entity_ids
            ),
        },
        "hidden_relevance": {
            "status": hidden_resolution.status,
            "selected_index": hidden_resolution.selected_index,
            "equivalent_indices": list(hidden_resolution.equivalent_indices),
            "residuals": list(hidden_resolution.residuals),
            "selected_entity_id": hidden_resolution.selected_entity_id,
            "equivalent_entity_ids": list(hidden_resolution.equivalent_entity_ids),
        },
        "roles": {
            "passive_statuses": passive_statuses,
            "interventional_attempts": role_attempts,
            "interventional_correct": role_correct,
            "false_confidence": role_false_confidence,
            "statuses": role_statuses,
        },
        "boundary_composition": {
            "tokens": list(boundary.tokens),
            "case_count": len(boundary_cases),
            "exact": boundary_exact,
            "false_settlements": boundary_false_settlements,
            "max_residual": max(boundary_residuals),
        },
        "shuffled_program_control": {
            "changed": shuffled_changed,
            "selection": _selection_payload(shuffled_receipt.interior),
            "field_changed": controller._tensor_sha256(shuffled_state.field) != field_sha256,
        },
        "ablations": {
            "evidence_status": evidence_ablation.status,
            "evidence_program_changed": (
                evidence_ablation.program_sha256 != interior.program_sha256
            ),
            "operators_supported": controller.program_operators_supported(
                operator_ablated,
                interior.program_id,
            ),
            "operator_trajectory_status": operator_ablation.status,
        },
        "consolidation": {
            "confirmed": confirmed,
            "count_before": consolidations_before,
            "count_after": consolidations_after,
            "failed_confirmed": failed_confirmed,
            "failed_field_unchanged": controller._tensor_sha256(failed_state.field) == field_sha256,
        },
        "restart": {
            "bytes_exact": restart_exact,
            "field_exact": controller._tensor_sha256(restarted.field) == field_sha256,
            "inference_frozen": inference_before == inference_after,
        },
        "controls": {
            "teacher_or_model_calls": 0,
            "live_provider_route": False,
            "provider_rejection": provider_error,
            "adaptive_persistent_objects": ["QiFieldState.field"],
        },
        "field_sha256": field_sha256,
    }
    required = {
        "cartesian": all(
            token in interior.tokens
            for token in ("ROLE_A", "ROLE_B", "POSITION", "SUBTRACT", "PACK4")
        ),
        "renaming_translation": max(
            invariance_residual,
            consequence_invariance,
        )
        <= 1.0e-12,
        "canonicalization": add_left.sha256 == add_right.sha256
        and folded.sha256 == direct.sha256,
        "each_object": each_object_rejected
        and len(diagnostic_hypotheses) == diagnostic_world.object_count
        and all(
            hypothesis.contexts[0].previous is None
            for hypothesis in diagnostic_hypotheses
        ),
        "historical_ambiguity": historical.status == "ambiguous"
        and len(historical.equivalent_actions) > 1,
        "prospective_synthesis": prospective.status == "selected"
        and len(prospective.equivalent_actions) > 1
        and prospective_execution_residual <= 1.0e-12,
        "moving_target": moving.status == "selected"
        and temporal.tokens == ("ROLE_B", "DELTA", "PACK4")
        and moving_execution_residual <= 1.0e-12,
        "sensor_intervals": all(
            row["deterministic"] and row["true_action_retained"]
            for row in noise_rows
        ),
        "diagnostic_distractors": diagnostic_resolution.status == "selected"
        and diagnostic_resolution.selected_entity_id == "relevant-target",
        "hidden_relevance": hidden_resolution.status == "ambiguous"
        and hidden_resolution.selected_entity_id is None
        and len(hidden_resolution.equivalent_entity_ids) == hidden_world.object_count,
        "passive_roles": passive_statuses == ["ambiguous"] * len(quadrants),
        "interventional_roles": role_correct == role_attempts == 32
        and role_false_confidence == 0,
        "boundary_composition": "CLAMP" in boundary.tokens
        and boundary_exact == len(boundary_cases)
        and boundary_false_settlements == 0,
        "shuffled_control": shuffled_changed
        and shuffled_receipt.interior.status == "exhausted",
        "field_ablations": evidence_ablation.status == "exhausted"
        and not controller.program_operators_supported(
            operator_ablated,
            interior.program_id,
        )
        and operator_ablation.status == "exhausted",
        "consolidation": confirmed
        and consolidations_after == consolidations_before + 1
        and not failed_confirmed
        and controller._tensor_sha256(failed_state.field) == field_sha256,
        "restart_and_freeze": restart_exact
        and controller._tensor_sha256(restarted.field) == field_sha256
        and inference_before == inference_after,
        "provider_control": provider_error
        == "counterflow request mode must be plan or predict",
    }
    failures = [name for name, passed in required.items() if not passed]
    if failures:
        raise RuntimeError(
            "generative abstraction scenario failed: " + ", ".join(failures)
        )
    return result


def main() -> int:
    print(
        json.dumps(
            {
                "result": "UNIVERSAL_FIELD_INTELLIGENCE_OK",
                "generative_abstraction": run_generative_abstraction_scenario(),
                "universal_data_field": run_universal_data_field_scenario(),
                "typed_adapters": run_typed_adapter_scenario(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
