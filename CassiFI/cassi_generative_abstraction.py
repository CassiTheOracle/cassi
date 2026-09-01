from __future__ import annotations

from dataclasses import asdict, dataclass, field as dataclass_field, replace
from enum import IntEnum
from fractions import Fraction
import hashlib
import itertools
import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Literal

import torch

from cassi_bilateral_counterflow import (
    BasinReceipt,
    BilateralCounterflowConfig,
    BilateralCounterflowController,
)
from cassi_qi_field import QiFieldError, QiFieldState
from cassi_relational_basis import RelationAtoms, RelationEntity
from cassi_universal_data import (
    BoundaryResult,
    Atom,
    BoundaryIdentity,
    BoundaryPacket,
    CODEC_JSON,
    Collection,
    MnemicObservationReference,
    ObservationNode,
    ObservationView,
    Tensor,
    ThalamusAdmission,
    ZERO_SHA256,
    adapt,
)


_PROGRAM_SCHEMA = "cassi.generative-abstraction.program.v1"
_REGIME_BITS = {"interior": 1, "boundary": 2, "temporal": 4}
_EVIDENCE_NAMES = (
    "closure",
    "inverse",
    "composition",
    "invariance",
    "collision",
    "boundary",
    "uncertainty",
    "outcome",
    "complexity",
    "score",
    "up_activation",
    "down_activation",
    "coherence",
)


class ProgramToken(IntEnum):
    ROLE_A = 1
    ROLE_B = 2
    POSITION = 3
    DELTA = 4
    SWAP_ROLES = 5
    ACTION_DELTA = 6
    LOWER_BOUND = 7
    UPPER_BOUND = 8
    SENSOR_PRECISION = 9
    CONST_NEG_ONE = 10
    CONST_ZERO = 11
    CONST_ONE = 12
    ADD = 13
    SUBTRACT = 14
    MULTIPLY = 15
    NORM2 = 16
    SQRT = 17
    NORMALIZE = 18
    MIN = 19
    MAX = 20
    CLAMP = 21
    HEADROOM = 22
    LESS = 23
    GREATER = 24
    SELECT = 25
    X = 26
    Y = 27
    PACK4 = 28
    EACH_OBJECT = 29


def _node_children(node: ObservationNode) -> tuple[ObservationNode, ...]:
    return tuple(value for _, value in node.items) if isinstance(node, Collection) else ()


def _first_text(node: ObservationNode) -> str | None:
    if isinstance(node, Atom) and node.primitive_type == "utf8":
        assert isinstance(node.value, str)
        return node.value
    return next(
        (value for child in _node_children(node) if (value := _first_text(child)) is not None),
        None,
    )


def _direct_vec2(node: ObservationNode) -> tuple[float, float] | None:
    if not isinstance(node, Collection):
        return None
    values = [
        float(child.value)
        for child in _node_children(node)
        if isinstance(child, Atom)
        and child.primitive_type in {"int", "float"}
        and not isinstance(child.value, bool)
        and isinstance(child.value, (int, float))
    ]
    if len(values) == 2 and all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
        return values[0], values[1]
    return next(
        (value for child in _node_children(node) if (value := _direct_vec2(child)) is not None),
        None,
    )


def _json_entities(view: ObservationView) -> tuple[RelationEntity, RelationEntity] | None:
    def candidate_sequence(node: ObservationNode) -> tuple[RelationEntity, RelationEntity] | None:
        if isinstance(node, Collection) and node.kind == "sequence" and len(node.items) == 2:
            entities = []
            for index, (_, child) in enumerate(node.items):
                point = _direct_vec2(child)
                if point is None:
                    break
                identity = _first_text(child) or f"{view.packet.identity.source_stream_id}:item:{index}"
                entities.append(RelationEntity(identity, *point))
            if len(entities) == 2:
                return entities[0], entities[1]
        return next(
            (
                result
                for child in _node_children(node)
                if (result := candidate_sequence(child)) is not None
            ),
            None,
        )

    return candidate_sequence(view.root)


def _raster_entities(view: ObservationView) -> tuple[RelationEntity, RelationEntity] | None:
    root = view.root
    if (
        not isinstance(root, Tensor)
        or root.dtype != "uint8"
        or len(root.shape) != 3
        or root.shape[0] != 2
        or len(view.packet.payload) != math.prod(root.shape)
    ):
        return None
    _, height, width = root.shape
    plane_size = height * width
    entities = []
    for plane in range(2):
        block = view.packet.payload[plane * plane_size : (plane + 1) * plane_size]
        occupied = [index for index, value in enumerate(block) if value != 0]
        if len(occupied) != 1 or block[occupied[0]] != 1:
            return None
        row, column = divmod(occupied[0], width)
        x = -1.0 + 0.08 * column
        y = -1.0 + 0.08 * row
        if not -1.0 <= x <= 1.0 or not -1.0 <= y <= 1.0:
            return None
        entities.append(
            RelationEntity(
                f"{view.packet.identity.source_stream_id}:plane:{plane}",
                x,
                y,
            )
        )
    return entities[0], entities[1]


def observation_relation_atoms(
    view: ObservationView,
    regime: Literal["interior", "boundary"],
) -> RelationAtoms | None:
    entities = (
        _json_entities(view)
        if view.modality == "json"
        else _raster_entities(view)
        if view.modality == "raster"
        else None
    )
    if entities is None:
        return None
    return RelationAtoms(
        world_id=view.packet.identity.world_id,
        episode_id=view.packet.identity.episode_id,
        state_sha256=view.packet.packet_sha256,
        regime=regime,
        entities=entities,
    )


def observation_from_relation_atoms(atoms: RelationAtoms) -> ObservationView:
    """Create a deterministic typed view for controller-derived relational state."""

    payload = json.dumps(
        {
            "entities": [
                {"id": entity.entity_id, "position": [entity.x, entity.y]}
                for entity in atoms.entities
            ]
        },
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    semantic = hashlib.sha256(b"cassi.generative-abstraction.derived-view.v1").hexdigest()
    packet = BoundaryPacket.create(
        identity=BoundaryIdentity(
            run_id="generative-abstraction",
            episode_id=atoms.episode_id,
            world_id=atoms.world_id,
            session_id="standalone",
            profile_sha256=semantic,
            clock_sha256=semantic,
            source_epoch="derived",
            source_stream_id=f"{atoms.world_id}:{atoms.episode_id}",
            body_frame_id="relational-grid",
        ),
        codec_id=CODEC_JSON,
        request_id=atoms.state_sha256,
        logical_tick=0,
        logical_time=Fraction(0),
        capture_start=Fraction(0),
        capture_end=Fraction(0),
        source_sequence=0,
        payload_shape=(len(payload),),
        payload_dtype="uint8",
        payload=payload,
        ingress_journal_sha256=ZERO_SHA256,
    )
    return adapt(packet, CODEC_JSON).require_selected()


@dataclass(frozen=True)
class ProgramContext:
    current_view: ObservationView
    previous_view: ObservationView | None = None
    action_delta: tuple[float, float] = (0.0, 0.0)
    sensor_precision: float = 0.0
    output_precision: float = 0.0
    role_a_index: int | None = 0
    regime: Literal["interior", "boundary"] = "interior"
    _current: RelationAtoms | None = dataclass_field(init=False, repr=False, compare=False)
    _previous: RelationAtoms | None = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        current = observation_relation_atoms(self.current_view, self.regime)
        previous = (
            None
            if self.previous_view is None
            else observation_relation_atoms(self.previous_view, self.regime)
        )
        object.__setattr__(self, "_current", current)
        object.__setattr__(self, "_previous", previous)
        if self.role_a_index not in (None, 0, 1):
            raise QiFieldError("program role_a_index must be zero, one, or unresolved")
        if (
            len(self.action_delta) != 2
            or any(not math.isfinite(value) for value in self.action_delta)
            or any(abs(value) > 1.0 for value in self.action_delta)
        ):
            raise QiFieldError("program action_delta must contain two finite bounded values")
        if (
            not math.isfinite(self.sensor_precision)
            or not 0.0 <= self.sensor_precision <= 1.0
        ):
            raise QiFieldError("program sensor_precision must be in [0, 1]")
        if (
            not math.isfinite(self.output_precision)
            or not 0.0 <= self.output_precision <= 1.0
        ):
            raise QiFieldError("program output_precision must be in [0, 1]")
        if current is not None and previous is not None:
            current_ids = {entity.entity_id for entity in current.entities}
            previous_ids = {entity.entity_id for entity in previous.entities}
            if current_ids != previous_ids:
                raise QiFieldError("program temporal contexts must contain the same entities")

    @property
    def current(self) -> RelationAtoms:
        if self._current is None:
            raise QiFieldError("typed observation is unsupported by the relational task")
        return self._current

    @property
    def previous(self) -> RelationAtoms | None:
        return self._previous

    @property
    def resolved_role_a_index(self) -> int:
        if self.role_a_index is None:
            raise QiFieldError("program role remains unresolved")
        return self.role_a_index

    @property
    def role_b_index(self) -> int:
        if self.role_a_index is None:
            raise QiFieldError("program role remains unresolved")
        return 1 - self.role_a_index

    def resolve_role(self, role_a_index: int) -> ProgramContext:
        if role_a_index not in (0, 1):
            raise QiFieldError("resolved program role must be zero or one")
        return replace(self, role_a_index=role_a_index)


@dataclass(frozen=True)
class ProgramTransition:
    action_id: int
    before: ProgramContext
    after: ProgramContext
    regime: Literal["interior", "boundary", "temporal"] = "interior"
    evidence: tuple[MnemicObservationReference, ...] = ()
    admission: ThalamusAdmission | None = None
    pair_event_id: str | None = None

    def __post_init__(self) -> None:
        if self.admission is not None:
            if not self.evidence:
                raise QiFieldError("admitted transition must retain exact Mnemic evidence")
            if len(self.evidence) > self.admission.work_budget:
                raise QiFieldError("transition exceeds its fixed Thalamus work budget")
            if self.admission.kind == "paired_world_observation" and (
                self.pair_event_id is None
                or len(self.pair_event_id) != 64
                or any(value not in "0123456789abcdef" for value in self.pair_event_id)
            ):
                raise QiFieldError("paired transition requires one exact event identity")


@dataclass(frozen=True)
class ProgramSequence:
    actions: tuple[int, ...]
    contexts: tuple[ProgramContext, ...]
    regime: Literal["interior", "boundary", "temporal"] = "interior"
    evidence: tuple[MnemicObservationReference, ...] = ()
    admission: ThalamusAdmission | None = None

    def __post_init__(self) -> None:
        if not self.actions or len(self.contexts) != len(self.actions) + 1:
            raise QiFieldError("program sequence must contain one more context than actions")
        if self.admission is not None:
            if not self.evidence:
                raise QiFieldError("admitted sequence must retain exact Mnemic evidence")
            if len(self.evidence) > self.admission.work_budget:
                raise QiFieldError("sequence exceeds its fixed Thalamus work budget")


@dataclass(frozen=True)
class ProgramCorpus:
    training_transitions: tuple[ProgramTransition, ...]
    evaluation_transitions: tuple[ProgramTransition, ...]
    sequences: tuple[ProgramSequence, ...] = ()
    invariance_pairs: tuple[tuple[ProgramContext, ProgramContext], ...] = ()

    def __post_init__(self) -> None:
        if not self.training_transitions or not self.evaluation_transitions:
            raise QiFieldError("program corpus requires training and evaluation observations")


@dataclass(frozen=True)
class _Node:
    kind: Literal["entity", "scalar", "vec2", "vec4", "bool"]
    token: ProgramToken
    children: tuple[_Node, ...] = ()


_LEAF_KINDS: dict[ProgramToken, Literal["entity", "scalar", "vec2"]] = {
    ProgramToken.ROLE_A: "entity",
    ProgramToken.ROLE_B: "entity",
    ProgramToken.ACTION_DELTA: "vec2",
    ProgramToken.LOWER_BOUND: "vec2",
    ProgramToken.UPPER_BOUND: "vec2",
    ProgramToken.SENSOR_PRECISION: "scalar",
    ProgramToken.CONST_NEG_ONE: "scalar",
    ProgramToken.CONST_ZERO: "scalar",
    ProgramToken.CONST_ONE: "scalar",
}
_COMMUTATIVE = {
    ProgramToken.ADD,
    ProgramToken.MULTIPLY,
    ProgramToken.MIN,
    ProgramToken.MAX,
}


def _parse_program(tokens: Sequence[ProgramToken]) -> _Node:
    stack: list[_Node] = []
    for token in tokens:
        if token == ProgramToken.EACH_OBJECT:
            raise QiFieldError(
                "EACH_OBJECT expands observable hypotheses and is not a scalar program operand"
            )
        if token in _LEAF_KINDS:
            stack.append(_Node(_LEAF_KINDS[token], token))
            continue
        if token in {
            ProgramToken.POSITION,
            ProgramToken.DELTA,
            ProgramToken.SWAP_ROLES,
            ProgramToken.HEADROOM,
            ProgramToken.X,
            ProgramToken.Y,
            ProgramToken.NORM2,
            ProgramToken.SQRT,
            ProgramToken.NORMALIZE,
        }:
            if not stack:
                raise QiFieldError(f"program token {token.name} has no operand")
            child = stack.pop()
            if token in {
                ProgramToken.POSITION,
                ProgramToken.DELTA,
                ProgramToken.SWAP_ROLES,
                ProgramToken.HEADROOM,
            } and child.kind != "entity":
                raise QiFieldError(f"program token {token.name} requires an entity")
            if token in {ProgramToken.X, ProgramToken.Y, ProgramToken.NORM2, ProgramToken.NORMALIZE} and child.kind != "vec2":
                raise QiFieldError(f"program token {token.name} requires a vec2")
            if token == ProgramToken.SQRT and child.kind != "scalar":
                raise QiFieldError("program token SQRT requires a scalar")
            result_kind: Literal["entity", "scalar", "vec2"]
            if token == ProgramToken.SWAP_ROLES:
                result_kind = "entity"
            elif token in {ProgramToken.X, ProgramToken.Y, ProgramToken.NORM2, ProgramToken.SQRT}:
                result_kind = "scalar"
            else:
                result_kind = "vec2"
            stack.append(_Node(result_kind, token, (child,)))
            continue
        if token in {
            ProgramToken.ADD,
            ProgramToken.SUBTRACT,
            ProgramToken.MULTIPLY,
            ProgramToken.MIN,
            ProgramToken.MAX,
            ProgramToken.LESS,
            ProgramToken.GREATER,
        }:
            if len(stack) < 2:
                raise QiFieldError(f"program token {token.name} has too few operands")
            right = stack.pop()
            left = stack.pop()
            if token in {ProgramToken.LESS, ProgramToken.GREATER}:
                if left.kind != "scalar" or right.kind != "scalar":
                    raise QiFieldError(f"program token {token.name} requires scalars")
                stack.append(_Node("bool", token, (left, right)))
                continue
            if token == ProgramToken.MULTIPLY and {left.kind, right.kind} == {"scalar", "vec2"}:
                stack.append(_Node("vec2", token, (left, right)))
                continue
            if left.kind != right.kind or left.kind not in {"scalar", "vec2"}:
                raise QiFieldError(
                    f"program token {token.name} requires matching scalar or vec2 operands"
                )
            stack.append(_Node(left.kind, token, (left, right)))
            continue
        if token == ProgramToken.CLAMP:
            if len(stack) < 3:
                raise QiFieldError("program token CLAMP has too few operands")
            upper = stack.pop()
            lower = stack.pop()
            value = stack.pop()
            if value.kind != lower.kind or value.kind != upper.kind or value.kind not in {"scalar", "vec2"}:
                raise QiFieldError("program token CLAMP requires matching bounded operands")
            stack.append(_Node(value.kind, token, (value, lower, upper)))
            continue
        if token == ProgramToken.SELECT:
            if len(stack) < 3:
                raise QiFieldError("program token SELECT has too few operands")
            false_value = stack.pop()
            true_value = stack.pop()
            condition = stack.pop()
            if condition.kind != "bool" or true_value.kind != false_value.kind:
                raise QiFieldError("program token SELECT requires a bool and matching branches")
            stack.append(_Node(true_value.kind, token, (condition, true_value, false_value)))
            continue
        if token == ProgramToken.PACK4:
            if stack and stack[-1].kind == "vec2":
                stack.append(_Node("vec4", token, (stack.pop(),)))
            elif len(stack) >= 4 and all(node.kind == "scalar" for node in stack[-4:]):
                children = tuple(stack[-4:])
                del stack[-4:]
                stack.append(_Node("vec4", token, children))
            else:
                raise QiFieldError("program token PACK4 requires one vec2 or four scalars")
            continue
        raise QiFieldError(f"unsupported program token: {token!r}")
    if len(stack) != 1 or stack[0].kind != "vec4":
        raise QiFieldError("program must leave exactly one vec4 result")
    return stack[0]


def _node_key(node: _Node) -> tuple[Any, ...]:
    return (int(node.token), node.kind, tuple(_node_key(child) for child in node.children))

_CONSTANT_VALUES = {
    ProgramToken.CONST_NEG_ONE: -1.0,
    ProgramToken.CONST_ZERO: 0.0,
    ProgramToken.CONST_ONE: 1.0,
}
_VALUE_CONSTANTS = {value: token for token, value in _CONSTANT_VALUES.items()}


def _constant_value(node: _Node) -> float | None:
    return _CONSTANT_VALUES.get(node.token) if not node.children else None



def _canonical_node(node: _Node) -> _Node:
    children = tuple(_canonical_node(child) for child in node.children)
    if node.token in _COMMUTATIVE:
        children = tuple(sorted(children, key=_node_key))
    if node.token == ProgramToken.SWAP_ROLES and children[0].token == ProgramToken.SWAP_ROLES:
        return children[0].children[0]
    if node.token == ProgramToken.NORMALIZE and children[0].token == ProgramToken.NORMALIZE:
        return children[0]
    if (
        node.token == ProgramToken.CLAMP
        and children[0].token == ProgramToken.CLAMP
        and children[0].children[1:] == children[1:]
    ):
        return children[0]
    if node.token in {ProgramToken.ADD, ProgramToken.SUBTRACT}:
        if _constant_value(children[1]) == 0.0:
            return children[0]
        if node.token == ProgramToken.ADD and _constant_value(children[0]) == 0.0:
            return children[1]
    if node.token == ProgramToken.MULTIPLY:
        if _constant_value(children[0]) == 1.0:
            return children[1]
        if _constant_value(children[1]) == 1.0:
            return children[0]
    if node.token in {
        ProgramToken.ADD,
        ProgramToken.SUBTRACT,
        ProgramToken.MULTIPLY,
        ProgramToken.MIN,
        ProgramToken.MAX,
    }:
        left = _constant_value(children[0])
        right = _constant_value(children[1])
        if left is not None and right is not None:
            operations = {
                ProgramToken.ADD: lambda: left + right,
                ProgramToken.SUBTRACT: lambda: left - right,
                ProgramToken.MULTIPLY: lambda: left * right,
                ProgramToken.MIN: lambda: min(left, right),
                ProgramToken.MAX: lambda: max(left, right),
            }
            constant = _VALUE_CONSTANTS.get(operations[node.token]())
            if constant is not None:
                return _Node("scalar", constant)
    return _Node(node.kind, node.token, children)


def _emit_node(node: _Node) -> tuple[ProgramToken, ...]:
    return tuple(
        token
        for child in node.children
        for token in _emit_node(child)
    ) + (node.token,)


def canonicalize_program(tokens: Sequence[ProgramToken | int]) -> tuple[ProgramToken, ...]:
    try:
        normalized = tuple(ProgramToken(int(token)) for token in tokens)
    except (TypeError, ValueError) as exc:
        raise QiFieldError("program contains an unknown token") from exc
    if not normalized:
        raise QiFieldError("program must contain at least one token")
    return _emit_node(_canonical_node(_parse_program(normalized)))


@dataclass(frozen=True)
class AbstractionProgram:
    tokens: tuple[ProgramToken, ...]

    def __post_init__(self) -> None:
        canonical = canonicalize_program(self.tokens)
        object.__setattr__(self, "tokens", canonical)

    @property
    def sha256(self) -> str:
        body = {
            "schema": _PROGRAM_SCHEMA,
            "tokens": [int(token) for token in self.tokens],
        }
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def decoded(self) -> tuple[str, ...]:
        return tuple(token.name for token in self.tokens)

    @property
    def is_transition_law(self) -> bool:
        return ProgramToken.ACTION_DELTA in self.tokens and ProgramToken.CLAMP in self.tokens

    @property
    def regime(self) -> Literal["interior", "boundary", "temporal"]:
        if ProgramToken.DELTA in self.tokens:
            return "temporal"
        if self.is_transition_law or ProgramToken.HEADROOM in self.tokens:
            return "boundary"
        return "interior"

    def role_swapped(self) -> AbstractionProgram:
        swapped = []
        for token in self.tokens:
            if token == ProgramToken.ROLE_A:
                swapped.append(ProgramToken.ROLE_B)
            elif token == ProgramToken.ROLE_B:
                swapped.append(ProgramToken.ROLE_A)
            else:
                swapped.append(token)
        return AbstractionProgram(tuple(swapped))

    @property
    def role_equivalence_sha256(self) -> str:
        return min(self.sha256, self.role_swapped().sha256)


@dataclass(frozen=True)
class _RuntimeValue:
    kind: Literal["entity", "scalar", "vec2", "vec4", "bool"]
    value: Any


def _entity_position(atoms: RelationAtoms, index: int) -> tuple[float, float]:
    entity = atoms.entities[index]
    return entity.x, entity.y


def _previous_entity_position(context: ProgramContext, index: int) -> tuple[float, float]:
    if context.previous is None:
        raise QiFieldError("program DELTA requires a previous observation")
    entity_id = context.current.entities[index].entity_id
    for entity in context.previous.entities:
        if entity.entity_id == entity_id:
            return entity.x, entity.y
    raise QiFieldError("program DELTA could not resolve the previous entity")




def _binary_numeric(left: Any, right: Any, operation: Any) -> Any:
    if isinstance(left, tuple) and isinstance(right, tuple):
        return tuple(operation(a, b) for a, b in zip(left, right, strict=True))
    if isinstance(left, tuple):
        return tuple(operation(component, right) for component in left)
    if isinstance(right, tuple):
        return tuple(operation(left, component) for component in right)
    return operation(left, right)


def _evaluate_node(node: _Node, context: ProgramContext) -> _RuntimeValue:
    token = node.token
    if token == ProgramToken.ROLE_A:
        return _RuntimeValue("entity", context.resolved_role_a_index)
    if token == ProgramToken.ROLE_B:
        return _RuntimeValue("entity", context.role_b_index)
    if token == ProgramToken.ACTION_DELTA:
        return _RuntimeValue("vec2", context.action_delta)
    if token == ProgramToken.LOWER_BOUND:
        return _RuntimeValue("vec2", (-1.0, -1.0))
    if token == ProgramToken.UPPER_BOUND:
        return _RuntimeValue("vec2", (1.0, 1.0))
    if token == ProgramToken.SENSOR_PRECISION:
        return _RuntimeValue("scalar", context.sensor_precision)
    if token in {ProgramToken.CONST_NEG_ONE, ProgramToken.CONST_ZERO, ProgramToken.CONST_ONE}:
        return _RuntimeValue(
            "scalar",
            {
                ProgramToken.CONST_NEG_ONE: -1.0,
                ProgramToken.CONST_ZERO: 0.0,
                ProgramToken.CONST_ONE: 1.0,
            }[token],
        )

    children = tuple(_evaluate_node(child, context) for child in node.children)
    if token == ProgramToken.POSITION:
        return _RuntimeValue("vec2", _entity_position(context.current, children[0].value))
    if token == ProgramToken.DELTA:
        index = children[0].value
        current = _entity_position(context.current, index)
        previous = _previous_entity_position(context, index)
        return _RuntimeValue("vec2", (current[0] - previous[0], current[1] - previous[1]))
    if token == ProgramToken.SWAP_ROLES:
        return _RuntimeValue("entity", 1 - children[0].value)
    if token == ProgramToken.HEADROOM:
        position = _entity_position(context.current, children[0].value)
        moved = tuple(
            min(1.0, max(-1.0, coordinate + delta))
            for coordinate, delta in zip(position, context.action_delta, strict=True)
        )
        return _RuntimeValue("vec2", (moved[0] - position[0], moved[1] - position[1]))
    if token == ProgramToken.X:
        return _RuntimeValue("scalar", children[0].value[0])
    if token == ProgramToken.Y:
        return _RuntimeValue("scalar", children[0].value[1])
    if token == ProgramToken.NORM2:
        return _RuntimeValue("scalar", sum(value * value for value in children[0].value))
    if token == ProgramToken.SQRT:
        return _RuntimeValue("scalar", math.sqrt(max(0.0, children[0].value)))
    if token == ProgramToken.NORMALIZE:
        x, y = children[0].value
        norm = math.hypot(x, y)
        return _RuntimeValue("vec2", (0.0, 0.0) if norm == 0.0 else (x / norm, y / norm))
    if token in {ProgramToken.ADD, ProgramToken.SUBTRACT, ProgramToken.MULTIPLY, ProgramToken.MIN, ProgramToken.MAX}:
        operations = {
            ProgramToken.ADD: lambda left, right: left + right,
            ProgramToken.SUBTRACT: lambda left, right: left - right,
            ProgramToken.MULTIPLY: lambda left, right: left * right,
            ProgramToken.MIN: min,
            ProgramToken.MAX: max,
        }
        return _RuntimeValue(
            node.kind,
            _binary_numeric(children[0].value, children[1].value, operations[token]),
        )
    if token == ProgramToken.CLAMP:
        value, lower, upper = (child.value for child in children)
        return _RuntimeValue(
            node.kind,
            _binary_numeric(
                _binary_numeric(value, lower, max),
                upper,
                min,
            ),
        )
    if token in {ProgramToken.LESS, ProgramToken.GREATER}:
        operation = (lambda left, right: left < right) if token == ProgramToken.LESS else (lambda left, right: left > right)
        return _RuntimeValue("bool", operation(children[0].value, children[1].value))
    if token == ProgramToken.SELECT:
        return children[1] if children[0].value else children[2]
    if token == ProgramToken.PACK4:
        if len(children) == 1:
            x, y = children[0].value
            values = (x, y, 1.0, x * y)
        else:
            values = tuple(child.value for child in children)
        return _RuntimeValue("vec4", values)
    raise QiFieldError(f"program interpreter does not implement {token.name}")


def evaluate_program(program: AbstractionProgram, context: ProgramContext) -> torch.Tensor:
    result = _evaluate_node(_parse_program(program.tokens), context)
    tensor = torch.tensor(result.value, dtype=torch.complex128)
    if tensor.shape != (4,) or not torch.isfinite(tensor.real).all().item() or not torch.isfinite(tensor.imag).all().item():
        raise QiFieldError("program evaluation must produce one finite vec4")
    return tensor


def _context_variants(context: ProgramContext) -> tuple[ProgramContext, ...]:
    precision = context.sensor_precision
    if precision == 0.0:
        return (context,)
    variants = []
    for signs in itertools.product((-1.0, 1.0), repeat=4):
        entities = []
        for entity_index, entity in enumerate(context.current.entities):
            x = min(1.0, max(-1.0, entity.x + precision * signs[2 * entity_index]))
            y = min(1.0, max(-1.0, entity.y + precision * signs[2 * entity_index + 1]))
            entities.append(RelationEntity(entity.entity_id, x, y))
        atoms = RelationAtoms(
            world_id=context.current.world_id,
            episode_id=context.current.episode_id,
            state_sha256=context.current.state_sha256,
            regime=context.current.regime,
            entities=(entities[0], entities[1]),
        )
        variants.append(
            replace(context, current_view=observation_from_relation_atoms(atoms))
        )
    return tuple(variants)


def program_interval_radius(program: AbstractionProgram, context: ProgramContext) -> float:
    nominal = evaluate_program(program, context)
    return max(
        float(torch.linalg.vector_norm(evaluate_program(program, variant) - nominal).item())
        for variant in _context_variants(context)
    )


@dataclass(frozen=True)
class GenerativeAbstractionConfig(BilateralCounterflowConfig):
    max_programs: int = 12
    action_count: int = 4
    max_basins: int = 48
    token_capacity: int = 16
    program_breaths: int = 4
    closure_weight: float = 1.0
    inverse_weight: float = 0.5
    composition_weight: float = 1.0
    invariance_weight: float = 2.0
    collision_weight: float = 2.0
    boundary_weight: float = 2.0
    uncertainty_weight: float = 1.0
    outcome_weight: float = 8.0
    complexity_weight: float = 0.01
    selection_margin: float = 1.0e-3
    max_outcome: float = 0.08
    max_score: float = 0.1
    equivalence_tolerance: float = 0.04
    action_deltas: tuple[tuple[float, float], ...] = (
        (-0.08, 0.0),
        (0.08, 0.0),
        (0.0, 0.08),
        (0.0, -0.08),
    )

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.max_programs < 3 or self.max_basins != self.max_programs * self.action_count:
            raise QiFieldError("generative max_basins must equal max_programs * action_count")
        if not 8 <= self.token_capacity <= 32:
            raise QiFieldError("generative token_capacity must be in [8, 32]")
        if not 1 <= self.program_breaths <= 16:
            raise QiFieldError("generative program_breaths must be in [1, 16]")
        if len(self.action_deltas) != self.action_count:
            raise QiFieldError("generative action_deltas must match action_count")
        if self.max_basins > 52:
            raise QiFieldError("generative max_basins exceeds exact float64 mask capacity")
        for delta in self.action_deltas:
            if len(delta) != 2 or any(not math.isfinite(value) or abs(value) > 1.0 for value in delta):
                raise QiFieldError("generative action deltas must be finite and bounded")
        for name in (
            "closure_weight",
            "inverse_weight",
            "composition_weight",
            "invariance_weight",
            "collision_weight",
            "boundary_weight",
            "uncertainty_weight",
            "outcome_weight",
            "complexity_weight",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value < 0.0:
                raise QiFieldError(f"{name} must be finite and non-negative")
        for name in (
            "selection_margin",
            "max_outcome",
            "max_score",
            "equivalence_tolerance",
        ):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0.0:
                raise QiFieldError(f"{name} must be finite and positive")

    @property
    def program_width(self) -> int:
        return 2 + self.token_capacity + 3 + len(_EVIDENCE_NAMES)

    @property
    def program_start(self) -> int:
        return self.basin_end

    @property
    def program_end(self) -> int:
        return self.program_start + self.max_programs * self.program_width

    @property
    def metadata_start(self) -> int:
        return self.program_end


@dataclass(frozen=True)
class ProgramEvidence:
    program_id: int
    program_sha256: str
    support: int
    closure: float
    inverse: float
    composition: float
    invariance: float
    collision: float
    boundary: float
    uncertainty: float
    outcome: float
    complexity: float
    score: float
    up_activation: float
    down_activation: float
    coherence: float


@dataclass(frozen=True)
class ProgramRecord:
    program_id: int
    program: AbstractionProgram
    regime_mask: int
    role_mask: int
    consolidations: int
    evidence: ProgramEvidence


@dataclass(frozen=True)
class ProgramSelection:
    status: Literal["selected", "ambiguous", "exhausted"]
    regime: Literal["interior", "boundary", "temporal"]
    program_id: int | None
    program_sha256: str | None
    tokens: tuple[str, ...]
    equivalent_program_ids: tuple[int, ...]
    margin: float | None
    score: float | None
    field_sha256: str


@dataclass(frozen=True)
class SynthesisReceipt:
    candidate_count: int
    mask_widths: tuple[int, ...]
    breaths: int
    interior: ProgramSelection
    boundary: ProgramSelection
    temporal: ProgramSelection
    field_sha256: str


@dataclass(frozen=True)
class TrajectoryProposal:
    status: Literal["selected", "ambiguous", "exhausted"]
    mode: Literal["historical", "prospective"]
    regime: Literal["interior", "boundary"]
    program_id: int
    actions: tuple[int, ...] | None
    equivalent_actions: tuple[tuple[int, ...], ...]
    final_value: tuple[float, float, float, float] | None
    residual: float | None
    field_sha256: str


@dataclass(frozen=True)
class RoleResolution:
    status: Literal["selected", "ambiguous", "exhausted"]
    selected_self_index: int | None
    equivalent_self_indices: tuple[int, ...]
    residuals: tuple[float, float] | None
    field_sha256: str


@dataclass(frozen=True)
class ObservableEntityFrame:
    world_id: str
    episode_id: str
    state_sha256: str
    regime: Literal["interior", "boundary"]
    self_entity: RelationEntity
    objects: tuple[RelationEntity, ...]

    def __post_init__(self) -> None:
        if not self.world_id or not self.episode_id:
            raise QiFieldError("observable entity frame identities must be nonempty")
        if (
            len(self.state_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.state_sha256)
        ):
            raise QiFieldError("observable entity frame state hash must be lowercase SHA-256")
        if self.regime not in {"interior", "boundary"}:
            raise QiFieldError("observable entity frame regime is unsupported")
        if not self.objects:
            raise QiFieldError("EACH_OBJECT requires at least one observable object")
        identities = [self.self_entity.entity_id, *(item.entity_id for item in self.objects)]
        if len(set(identities)) != len(identities):
            raise QiFieldError("observable entity frame identities must be distinct")


@dataclass(frozen=True)
class EntityHypothesis:
    entity_id: str
    contexts: tuple[ProgramContext, ...]


@dataclass(frozen=True)
class EntityResolution:
    status: Literal["selected", "ambiguous", "exhausted"]
    selected_index: int | None
    equivalent_indices: tuple[int, ...]
    residuals: tuple[float, ...]
    field_sha256: str
    candidate_entity_ids: tuple[str, ...] = ()
    selected_entity_id: str | None = None
    equivalent_entity_ids: tuple[str, ...] = ()


def generate_candidate_programs(config: GenerativeAbstractionConfig) -> tuple[AbstractionProgram, ...]:
    positions = (
        (ProgramToken.ROLE_A, ProgramToken.POSITION),
        (ProgramToken.ROLE_B, ProgramToken.POSITION),
    )
    candidates: list[tuple[ProgramToken, ...]] = [
        (*position, ProgramToken.PACK4) for position in positions
    ]
    for left, right in itertools.permutations(positions, 2):
        for operator in (ProgramToken.ADD, ProgramToken.SUBTRACT):
            expression = (*left, *right, operator)
            candidates.append((*expression, ProgramToken.PACK4))
            candidates.append(
                (*expression, ProgramToken.NORMALIZE, ProgramToken.PACK4)
            )
    for role in (ProgramToken.ROLE_A, ProgramToken.ROLE_B):
        candidates.append((role, ProgramToken.DELTA, ProgramToken.PACK4))
    candidates.extend(
        (
            (
                *positions[1],
                *positions[0],
                ProgramToken.ACTION_DELTA,
                ProgramToken.ADD,
                ProgramToken.LOWER_BOUND,
                ProgramToken.UPPER_BOUND,
                ProgramToken.CLAMP,
                ProgramToken.SUBTRACT,
                ProgramToken.PACK4,
            ),
            (ProgramToken.ROLE_A, ProgramToken.HEADROOM, ProgramToken.PACK4),
        )
    )
    unique: dict[str, AbstractionProgram] = {}
    for tokens in candidates:
        program = AbstractionProgram(tokens)
        if len(program.tokens) <= config.token_capacity:
            unique.setdefault(program.sha256, program)
    programs = tuple(unique.values())
    if len(programs) > config.max_programs:
        raise QiFieldError("typed grammar generated more programs than field capacity")
    return programs


class GenerativeAbstractionController(BilateralCounterflowController):
    def __init__(self, config: GenerativeAbstractionConfig | None = None) -> None:
        super().__init__(config or GenerativeAbstractionConfig())
        self.config: GenerativeAbstractionConfig

    def initial_state(
        self,
        *,
        device: str | torch.device = "cpu",
        dtype: torch.dtype = torch.float64,
    ) -> QiFieldState:
        if dtype != torch.float64:
            raise QiFieldError("generative abstraction requires float64 field storage")
        return super().initial_state(device=device, dtype=dtype)

    def _program_slice(self, program_id: int) -> slice:
        if not 0 <= program_id < self.config.max_programs:
            raise QiFieldError("program_id is outside the configured capacity")
        start = self.config.program_start + program_id * self.config.program_width
        return slice(start, start + self.config.program_width)

    def _program_basin_id(self, program_id: int, action_id: int) -> int:
        if not 0 <= action_id < self.config.action_count:
            raise QiFieldError("action_id is outside the configured capacity")
        self._program_slice(program_id)
        return program_id * self.config.action_count + action_id

    def validate_state(self, state: QiFieldState) -> None:
        super().validate_state(state)
        if state.field.dtype != torch.float64:
            raise QiFieldError("generative abstraction field must use float64")
        packed = self._packed(state)
        modes = slice(self.config.program_start, self.config.program_end)
        self._require_zero("generative program field components", packed[0, :8, modes, :])
        self._require_zero("non-root generative programs", packed[1:, :, modes, :])
        for program_id in range(self.config.max_programs):
            row = packed[0, 8, self._program_slice(program_id), 0]
            support = self._require_integer(
                f"program_support[{program_id}]",
                float(row[0].item()),
                0,
                self._MAX_EXACT_INTEGER,
            )
            if support == 0:
                if torch.count_nonzero(row).item() != 0:
                    raise QiFieldError("unsupported generative program row must be zero")
                continue
            length = self._require_integer(
                f"program_length[{program_id}]",
                float(row[1].item()),
                1,
                self.config.token_capacity,
            )
            token_values = row[2 : 2 + self.config.token_capacity]
            for token_index, value in enumerate(token_values[:length].tolist()):
                token_id = self._require_integer(
                    f"program_token[{program_id},{token_index}]",
                    value,
                    1,
                    max(int(token) for token in ProgramToken),
                )
                try:
                    ProgramToken(token_id)
                except ValueError as exc:
                    raise QiFieldError("stored generative program token is unknown") from exc
            self._require_zero(
                f"unused program tokens[{program_id}]",
                token_values[length:],
            )
            cursor = 2 + self.config.token_capacity
            self._require_integer(
                f"program_regime_mask[{program_id}]",
                float(row[cursor].item()),
                1,
                sum(_REGIME_BITS.values()),
            )
            self._require_integer(
                f"program_role_mask[{program_id}]",
                float(row[cursor + 1].item()),
                1,
                3,
            )
            self._require_integer(
                f"program_consolidations[{program_id}]",
                float(row[cursor + 2].item()),
                0,
                self._MAX_EXACT_INTEGER,
            )
            evidence = row[cursor + 3 :]
            if not torch.isfinite(evidence).all().item() or (evidence < 0.0).any().item():
                raise QiFieldError("generative program evidence must be finite and non-negative")
            tokens = tuple(ProgramToken(int(value)) for value in token_values[:length].tolist())
            if AbstractionProgram(tokens).tokens != tokens:
                raise QiFieldError("stored generative program must be canonical")

    def _write_program(
        self,
        state: QiFieldState,
        program_id: int,
        program: AbstractionProgram,
        evidence: ProgramEvidence,
        *,
        regime_mask: int,
        role_mask: int = 3,
        consolidations: int = 0,
    ) -> QiFieldState:
        self.validate_state(state)
        if len(program.tokens) > self.config.token_capacity:
            raise QiFieldError("program exceeds token capacity")
        result = QiFieldState(field=state.field.clone())
        packed = self._packed(result)
        row = packed[0, 8, self._program_slice(program_id), 0]
        row.zero_()
        row[0] = float(evidence.support)
        row[1] = float(len(program.tokens))
        row[2 : 2 + len(program.tokens)] = torch.tensor(
            [int(token) for token in program.tokens],
            dtype=row.dtype,
            device=row.device,
        )
        cursor = 2 + self.config.token_capacity
        row[cursor] = float(regime_mask)
        row[cursor + 1] = float(role_mask)
        row[cursor + 2] = float(consolidations)
        row[cursor + 3 :] = torch.tensor(
            [getattr(evidence, name) for name in _EVIDENCE_NAMES],
            dtype=row.dtype,
            device=row.device,
        )
        self.validate_state(result)
        return result

    def program_records(self, state: QiFieldState) -> tuple[ProgramRecord, ...]:
        self.validate_state(state)
        packed = self._packed(state)
        records = []
        for program_id in range(self.config.max_programs):
            row = packed[0, 8, self._program_slice(program_id), 0]
            support = int(round(float(row[0].item())))
            if support == 0:
                continue
            length = int(round(float(row[1].item())))
            program = AbstractionProgram(
                tuple(ProgramToken(int(value)) for value in row[2 : 2 + length].tolist())
            )
            cursor = 2 + self.config.token_capacity
            metrics = {
                name: float(value)
                for name, value in zip(
                    _EVIDENCE_NAMES,
                    row[cursor + 3 :].tolist(),
                    strict=True,
                )
            }
            evidence = ProgramEvidence(
                program_id=program_id,
                program_sha256=program.sha256,
                support=support,
                **metrics,
            )
            records.append(
                ProgramRecord(
                    program_id=program_id,
                    program=program,
                    regime_mask=int(round(float(row[cursor].item()))),
                    role_mask=int(round(float(row[cursor + 1].item()))),
                    consolidations=int(round(float(row[cursor + 2].item()))),
                    evidence=evidence,
                )
            )
        return tuple(records)

    def _observe_grouped_transitions(
        self,
        state: QiFieldState,
        program_id: int,
        action_id: int,
        before: Sequence[torch.Tensor],
        after: Sequence[torch.Tensor],
    ) -> tuple[QiFieldState, BasinReceipt]:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("program transitions require an idle field")
        x = self._coerce_examples(torch.stack(tuple(before)), state)
        y = self._coerce_examples(torch.stack(tuple(after)), state)
        if x.shape != y.shape:
            raise QiFieldError("program before and after examples must have equal shape")
        basin_id = self._program_basin_id(program_id, action_id)
        support_values = self._basin_support(packed)
        occupied_before = int((support_values >= self.config.occupancy_floor).sum().item())
        support_before = int(round(float(support_values[basin_id].item())))
        sample_count = int(x.shape[0])
        forward_gram = torch.einsum("ni,nj->ij", x, x.conj()) / float(sample_count)
        forward_cross = torch.einsum("ni,nj->ij", y, x.conj()) / float(sample_count)
        backward_gram = torch.einsum("ni,nj->ij", y, y.conj()) / float(sample_count)
        backward_cross = torch.einsum("ni,nj->ij", x, y.conj()) / float(sample_count)
        candidate = self._operator_from_moments(forward_cross, forward_gram)
        candidate_error = float(
            self._relative_residual(torch.einsum("ij,nj->ni", candidate, x), y)
            .mean()
            .item()
        )
        support = sample_count
        dispersion = candidate_error
        generation = max(1, self._basin_generation(packed, basin_id))
        decision: Literal["create", "reinforce"] = "create"
        if support_before:
            (
                old_forward_cross,
                old_forward_gram,
                old_backward_cross,
                old_backward_gram,
                old_support,
                old_dispersion,
            ) = self._read_moments(packed, basin_id)
            support = old_support + sample_count
            forward_cross = (old_support * old_forward_cross + sample_count * forward_cross) / float(support)
            forward_gram = (old_support * old_forward_gram + sample_count * forward_gram) / float(support)
            backward_cross = (old_support * old_backward_cross + sample_count * backward_cross) / float(support)
            backward_gram = (old_support * old_backward_gram + sample_count * backward_gram) / float(support)
            dispersion = (old_support * old_dispersion + sample_count * candidate_error) / float(support)
            generation = self._basin_generation(packed, basin_id)
            decision = "reinforce"
        if support > self._MAX_EXACT_INTEGER:
            raise QiFieldError("program basin support exceeds exact field capacity")
        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        self._write_macro_metadata(target, basin_id, generation)
        self._write_moments(
            target,
            basin_id,
            forward_cross,
            forward_gram,
            backward_cross,
            backward_gram,
            support,
            dispersion,
        )
        self.validate_state(result)
        return result, BasinReceipt(
            decision=decision,
            basin_id=basin_id,
            best_residual=candidate_error,
            best_similarity=1.0,
            occupied_before=occupied_before,
            occupied_after=occupied_before + int(not support_before),
            support_before=support_before,
            support_after=support,
            dispersion_after=dispersion,
            field_sha256=self._tensor_sha256(result.field),
        )

    def operator(self, state: QiFieldState, program_id: int, action_id: int) -> torch.Tensor:
        self.validate_state(state)
        basin_id = self._program_basin_id(program_id, action_id)
        packed = self._packed(state)
        if self._basin_support(packed)[basin_id].item() < self.config.occupancy_floor:
            raise QiFieldError("requested generative operator has no field support")
        cross, gram, *_ = self._read_moments(packed, basin_id)
        return self._operator_from_moments(cross, gram)
    def program_operators_supported(
        self,
        state: QiFieldState,
        program_id: int,
    ) -> bool:
        self.validate_state(state)
        support = self._basin_support(self._packed(state))
        return all(
            support[self._program_basin_id(program_id, action_id)].item()
            >= self.config.occupancy_floor
            for action_id in range(self.config.action_count)
        )


    @staticmethod
    def _mean(values: Sequence[float]) -> float:
        return sum(values) / float(len(values)) if values else 0.0

    @staticmethod
    def _relative_residual_value(predicted: torch.Tensor, observed: torch.Tensor) -> float:
        denominator = max(1.0, float(torch.linalg.vector_norm(observed).item()))
        return float(torch.linalg.vector_norm(predicted - observed).item()) / denominator

    def _with_action(self, context: ProgramContext, action_id: int) -> ProgramContext:
        return replace(context, action_delta=self.config.action_deltas[action_id])

    def infer_observed_role(
        self,
        before: ProgramContext,
        after: ProgramContext,
        action_id: int,
    ) -> BoundaryResult[int]:
        if not 0 <= action_id < self.config.action_count:
            return BoundaryResult("unsupported", None, (), "invalid_action", ())
        before_entities = before.current.entities
        after_by_id = {entity.entity_id: entity for entity in after.current.entities}
        if {entity.entity_id for entity in before_entities} != set(after_by_id):
            return BoundaryResult(
                "unsupported",
                None,
                (),
                "stable_entity_identity_unavailable",
                (),
            )
        delta = self.config.action_deltas[action_id]
        tolerance = max(
            0.5 * before.sensor_precision,
            0.5 * after.sensor_precision,
            1.0e-9,
        )
        residuals = []
        for acted_index in (0, 1):
            residual = 0.0
            for index, source in enumerate(before_entities):
                observed = after_by_id[source.entity_id]
                expected_x = (
                    min(1.0, max(-1.0, source.x + delta[0]))
                    if index == acted_index
                    else source.x
                )
                expected_y = (
                    min(1.0, max(-1.0, source.y + delta[1]))
                    if index == acted_index
                    else source.y
                )
                residual = max(
                    residual,
                    abs(expected_x - observed.x),
                    abs(expected_y - observed.y),
                )
            residuals.append(residual)
        selected = tuple(
            index for index, residual in enumerate(residuals) if residual <= tolerance
        )
        if len(selected) == 1:
            return BoundaryResult("selected", selected[0], (), None, ())
        if selected:
            return BoundaryResult("ambiguous", None, selected, "role_not_identified", ())
        return BoundaryResult("unsupported", None, (), "outcome_mismatch", ())

    def _resolve_transition(self, transition: ProgramTransition) -> ProgramTransition:
        before_role = transition.before.role_a_index
        if before_role is not None and transition.after.role_a_index is not None:
            after_role = transition.after.resolved_role_a_index
        else:
            role = self.infer_observed_role(
                transition.before,
                transition.after,
                transition.action_id,
            )
            if role.status != "selected" or role.value is None:
                raise QiFieldError(role.reason or "observed transition role remains ambiguous")
            before_role = role.value
            acted_id = transition.before.current.entities[before_role].entity_id
            after_role = next(
                (
                    index
                    for index, entity in enumerate(transition.after.current.entities)
                    if entity.entity_id == acted_id
                ),
                None,
            )
            if after_role is None:
                raise QiFieldError("stable acted entity is absent from transition outcome")
        return replace(
            transition,
            before=transition.before.resolve_role(before_role),
            after=transition.after.resolve_role(after_role),
        )

    def _resolve_corpus(self, corpus: ProgramCorpus) -> ProgramCorpus:
        resolved = replace(
            corpus,
            training_transitions=tuple(
                self._resolve_transition(transition)
                for transition in corpus.training_transitions
            ),
            evaluation_transitions=tuple(
                self._resolve_transition(transition)
                for transition in corpus.evaluation_transitions
            ),
        )
        self._validate_paired_observations(resolved)
        return resolved

    def _validate_paired_observations(self, corpus: ProgramCorpus) -> None:
        groups: dict[str, list[ProgramTransition]] = {}
        for transition in (
            *corpus.training_transitions,
            *corpus.evaluation_transitions,
        ):
            if (
                transition.admission is not None
                and transition.admission.kind == "paired_world_observation"
            ):
                assert transition.pair_event_id is not None
                groups.setdefault(transition.pair_event_id, []).append(transition)
        for pair_event_id, transitions in groups.items():
            modalities = {transition.before.current_view.modality for transition in transitions}
            if len(transitions) != 2 or modalities != {"json", "raster"}:
                raise QiFieldError(
                    f"paired event {pair_event_id} requires one JSON and one raster observation"
                )
            left, right = transitions
            if left.action_id != right.action_id or left.regime != right.regime:
                raise QiFieldError("paired observations disagree on action or regime")
            for left_context, right_context in (
                (left.before, right.before),
                (left.after, right.after),
            ):
                if self._relative_residual_value(
                    self._relation_value(left_context),
                    self._relation_value(right_context),
                ) > 1.0e-12:
                    raise QiFieldError("paired observations disagree on exact consequence")

    def evaluate_observed_transition(
        self,
        state: QiFieldState,
        transition: ProgramTransition,
    ) -> BoundaryResult[float]:
        self.validate_state(state)
        if transition.before.role_a_index is None:
            role = self.infer_observed_role(
                transition.before,
                transition.after,
                transition.action_id,
            )
            if role.status != "selected":
                return BoundaryResult(role.status, None, (), role.reason, ())
        resolved = self._resolve_transition(transition)
        selection = self.select_program(state, transition.regime)
        if selection.status != "selected" or selection.program_id is None:
            return BoundaryResult("unsupported", None, (), "no_selected_program", ())
        record = self._program_record(state, selection.program_id)
        before = self._with_action(resolved.before, resolved.action_id)
        if record.program.is_transition_law:
            predicted = evaluate_program(record.program, before)
            observed = self._relation_value(resolved.after)
        else:
            predicted = self.operator(state, record.program_id, resolved.action_id) @ evaluate_program(
                record.program,
                before,
            )
            observed = evaluate_program(record.program, resolved.after)
        precision = max(resolved.before.output_precision, resolved.after.output_precision)
        if precision > 0.0 and ProgramToken.NORMALIZE not in record.program.tokens:
            predicted = self._quantize_packed_relation(predicted, precision)
            observed = self._quantize_packed_relation(observed, precision)
        return BoundaryResult(
            "selected",
            self._relative_residual_value(predicted, observed),
            (),
            None,
            (),
        )
    @staticmethod
    def _quantize_packed_relation(
        value: torch.Tensor,
        precision: float,
    ) -> torch.Tensor:
        x = round(float(value[0].real.item()) / precision) * precision
        y = round(float(value[1].real.item()) / precision) * precision
        return torch.tensor(
            (x, y, 1.0, x * y),
            dtype=value.dtype,
            device=value.device,
        )



    @staticmethod
    def _relation_value(context: ProgramContext) -> torch.Tensor:
        self_entity = context.current.entities[context.resolved_role_a_index]
        target = context.current.entities[context.role_b_index]
        x, y = target.x - self_entity.x, target.y - self_entity.y
        return torch.tensor((x, y, 1.0, x * y), dtype=torch.complex128)

    def _training_values(
        self,
        program: AbstractionProgram,
        transition: ProgramTransition,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        before = self._with_action(transition.before, transition.action_id)
        if program.is_transition_law:
            return self._relation_value(before), evaluate_program(program, before)
        return evaluate_program(program, before), evaluate_program(program, transition.after)

    def _program_value(self, program: AbstractionProgram, context: ProgramContext) -> torch.Tensor:
        return self._relation_value(context) if program.is_transition_law else evaluate_program(program, context)

    def _compute_evidence(
        self,
        state: QiFieldState,
        program_id: int,
        program: AbstractionProgram,
        corpus: ProgramCorpus,
    ) -> ProgramEvidence:
        transitions = tuple(
            transition
            for transition in corpus.evaluation_transitions
            if transition.regime == program.regime
        )
        sequences = tuple(
            sequence
            for sequence in corpus.sequences
            if sequence.regime == program.regime
        )
        closure_values = []
        boundary_values = []
        inverse_values = []
        grouped_contexts: dict[tuple[str, str, str, int], ProgramContext] = {}
        for transition in transitions:
            before = self._with_action(transition.before, transition.action_id)
            if program.is_transition_law:
                predicted = evaluate_program(program, before)
                observed = self._relation_value(transition.after)
            else:
                predicted = self.operator(state, program_id, transition.action_id) @ evaluate_program(program, before)
                observed = evaluate_program(program, transition.after)
            residual = self._relative_residual_value(predicted, observed)
            closure_values.append(residual)
            if transition.regime == "boundary":
                boundary_values.append(residual)
            start = self._program_value(program, before)
            inverse_id = transition.action_id ^ 1
            if program.is_transition_law:
                forward_context = self._boundary_step_context(
                    program,
                    transition.before,
                    transition.action_id,
                )
                cycled_context = self._boundary_step_context(
                    program,
                    forward_context,
                    inverse_id,
                )
                cycled = self._relation_value(cycled_context)
            else:
                cycled = self.operator(state, program_id, inverse_id) @ (
                    self.operator(state, program_id, transition.action_id) @ start
                )
            inverse_values.append(self._relative_residual_value(cycled, start))
            key = (
                before.current.world_id,
                before.current.episode_id,
                before.current.state_sha256,
                before.resolved_role_a_index,
            )
            grouped_contexts[key] = before

        composition_values = []
        for sequence in sequences:
            if program.is_transition_law:
                context = sequence.contexts[0]
                for action_id in sequence.actions:
                    context = self._boundary_step_context(program, context, action_id)
                value = self._relation_value(context)
            else:
                value = self._program_value(program, sequence.contexts[0])
                for action_id in sequence.actions:
                    value = self.operator(state, program_id, action_id) @ value
            observed = self._program_value(program, sequence.contexts[-1])
            composition_values.append(self._relative_residual_value(value, observed))

        invariance_values = [
            self._relative_residual_value(
                evaluate_program(program, left),
                evaluate_program(program, right),
            )
            for left, right in corpus.invariance_pairs
            if not program.is_transition_law
        ]
        if program.is_transition_law:
            invariance_values = [
                self._relative_residual_value(
                    evaluate_program(program, left),
                    evaluate_program(program, right),
                )
                for left, right in corpus.invariance_pairs
            ]

        collision_values = []
        for context in grouped_contexts.values():
            origin = self._program_value(program, context)
            if program.is_transition_law:
                deltas = [
                    evaluate_program(program, self._with_action(context, action_id)) - origin
                    for action_id in range(self.config.action_count)
                ]
            else:
                deltas = [
                    self.operator(state, program_id, action_id) @ origin - origin
                    for action_id in range(self.config.action_count)
                ]
            for left, right in itertools.combinations(deltas, 2):
                distance = self._relative_residual_value(left, right)
                collision_values.append(
                    max(0.0, self.config.equivalence_tolerance - distance)
                    / self.config.equivalence_tolerance
                )

        uncertainty_values = [
            program_interval_radius(program, transition.before)
            / max(1.0, float(torch.linalg.vector_norm(evaluate_program(program, transition.before)).item()))
            for transition in transitions
            if not program.is_transition_law
        ]
        if program.is_transition_law:
            uncertainty_values = [
                program_interval_radius(program, self._with_action(transition.before, transition.action_id))
                for transition in transitions
            ]

        closure = self._mean(closure_values)
        inverse = self._mean(inverse_values)
        composition = self._mean(composition_values)
        invariance = self._mean(invariance_values)
        collision = self._mean(collision_values)
        boundary = self._mean(boundary_values)
        uncertainty = self._mean(uncertainty_values)
        outcome = self._mean(composition_values) + self._mean(
            [float(value > self.config.trajectory_tolerance) for value in composition_values]
        )
        if program.regime == "temporal":
            temporal_values = [
                evaluate_program(program, transition.before)
                for transition in transitions
                if transition.before.previous is not None
            ]
            if temporal_values:
                center = torch.stack(temporal_values).mean(dim=0)
                temporal_variation = self._mean(
                    [self._relative_residual_value(value, center) for value in temporal_values]
                )
                closure = temporal_variation
                composition = temporal_variation
                outcome = temporal_variation
                collision = 0.0
                boundary = 0.0
        complexity = len(program.tokens) / float(self.config.token_capacity)
        score = (
            self.config.closure_weight * closure
            + self.config.inverse_weight * inverse
            + self.config.composition_weight * composition
            + self.config.invariance_weight * invariance
            + self.config.collision_weight * collision
            + self.config.boundary_weight * boundary
            + self.config.uncertainty_weight * uncertainty
            + self.config.outcome_weight * outcome
            + self.config.complexity_weight * complexity
        )
        return ProgramEvidence(
            program_id=program_id,
            program_sha256=program.sha256,
            support=len(transitions) + len(sequences),
            closure=closure,
            inverse=inverse,
            composition=composition,
            invariance=invariance,
            collision=collision,
            boundary=boundary,
            uncertainty=uncertainty,
            outcome=outcome,
            complexity=complexity,
            score=score,
            up_activation=0.0,
            down_activation=0.0,
            coherence=0.0,
        )

    def _refine_evidence(
        self,
        programs: Sequence[AbstractionProgram],
        evidence: Sequence[ProgramEvidence],
    ) -> tuple[ProgramEvidence, ...]:
        result = list(evidence)
        for regime in _REGIME_BITS:
            indexes = [
                index
                for index, program in enumerate(programs)
                if program.regime == regime and result[index].support > 0
            ]
            if not indexes:
                continue
            local_energy = [
                result[index].closure
                + 0.5 * result[index].inverse
                + result[index].composition
                + 2.0 * result[index].invariance
                + 2.0 * result[index].collision
                + result[index].uncertainty
                + self.config.complexity_weight * result[index].complexity
                for index in indexes
            ]
            downward_energy = [
                2.0 * result[index].boundary + 8.0 * result[index].outcome
                for index in indexes
            ]
            up = [math.exp(-min(80.0, value)) for value in local_energy]
            down = [math.exp(-min(80.0, value)) for value in downward_energy]
            for _ in range(self.config.program_breaths):
                next_up = [
                    (1.0 - self.config.relaxation_rate) * value
                    + self.config.relaxation_rate * math.exp(-min(80.0, energy)) * (1.0 + self.config.cross_gain * down[position])
                    for position, (value, energy) in enumerate(zip(up, local_energy, strict=True))
                ]
                next_down = [
                    (1.0 - self.config.relaxation_rate) * value
                    + self.config.relaxation_rate * math.exp(-min(80.0, energy)) * (1.0 + self.config.cross_gain * next_up[position])
                    for position, (value, energy) in enumerate(zip(down, downward_energy, strict=True))
                ]
                up_scale = max(next_up) or 1.0
                down_scale = max(next_down) or 1.0
                up = [value / up_scale for value in next_up]
                down = [value / down_scale for value in next_down]
            for position, index in enumerate(indexes):
                result[index] = replace(
                    result[index],
                    up_activation=up[position],
                    down_activation=down[position],
                    coherence=math.sqrt(up[position] * down[position]),
                )
        return tuple(result)

    def synthesize(self, corpus: ProgramCorpus) -> tuple[QiFieldState, SynthesisReceipt]:
        corpus = self._resolve_corpus(corpus)
        programs = generate_candidate_programs(self.config)
        state = self.initial_state(dtype=torch.float64)
        for program_id, program in enumerate(programs):
            for action_id in range(self.config.action_count):
                transitions = [
                    transition
                    for transition in corpus.training_transitions
                    if transition.action_id == action_id
                    and transition.regime == program.regime
                ]
                if not transitions:
                    continue
                pairs = [self._training_values(program, transition) for transition in transitions]
                state, _ = self._observe_grouped_transitions(
                    state,
                    program_id,
                    action_id,
                    [pair[0] for pair in pairs],
                    [pair[1] for pair in pairs],
                )
        evidence = tuple(
            self._compute_evidence(state, program_id, program, corpus)
            for program_id, program in enumerate(programs)
        )
        evidence = self._refine_evidence(programs, evidence)
        for program_id, (program, item) in enumerate(zip(programs, evidence, strict=True)):
            if item.support <= 0:
                continue
            state = self._write_program(
                state,
                program_id,
                program,
                item,
                regime_mask=_REGIME_BITS[program.regime],
            )
        mask_widths = tuple(
            len({program.tokens[index] for program in programs if index < len(program.tokens)})
            for index in range(max(len(program.tokens) for program in programs))
        )
        receipt = SynthesisReceipt(
            candidate_count=len(programs),
            mask_widths=mask_widths,
            breaths=self.config.program_breaths,
            interior=self.select_program(state, "interior"),
            boundary=self.select_program(state, "boundary"),
            temporal=self.select_program(state, "temporal"),
            field_sha256=self._tensor_sha256(state.field),
        )
        return state, receipt

    def select_program(
        self,
        state: QiFieldState,
        regime: Literal["interior", "boundary", "temporal"],
    ) -> ProgramSelection:
        self.validate_state(state)
        records = [
            record
            for record in self.program_records(state)
            if record.regime_mask & _REGIME_BITS[regime]
            and record.evidence.support > 0
            and record.evidence.outcome <= self.config.max_outcome
            and record.evidence.score <= self.config.max_score
        ]
        field_sha256 = self._tensor_sha256(state.field)
        if not records:
            return ProgramSelection(
                status="exhausted",
                regime=regime,
                program_id=None,
                program_sha256=None,
                tokens=(),
                equivalent_program_ids=(),
                margin=None,
                score=None,
                field_sha256=field_sha256,
            )
        groups: dict[str, list[ProgramRecord]] = {}
        for record in records:
            groups.setdefault(record.program.role_equivalence_sha256, []).append(record)
        ranked = sorted(
            groups.values(),
            key=lambda group: (-max(item.evidence.coherence for item in group), min(item.evidence.score for item in group)),
        )
        best_group = ranked[0]
        representative = min(best_group, key=lambda item: (item.evidence.score, item.program.sha256))
        next_coherence = max(item.evidence.coherence for item in ranked[1]) if len(ranked) > 1 else 0.0
        margin = max(item.evidence.coherence for item in best_group) - next_coherence
        status: Literal["selected", "ambiguous", "exhausted"] = (
            "selected" if len(ranked) == 1 or margin >= self.config.selection_margin else "ambiguous"
        )
        return ProgramSelection(
            status=status,
            regime=regime,
            program_id=representative.program_id if status == "selected" else None,
            program_sha256=representative.program.sha256 if status == "selected" else None,
            tokens=representative.program.decoded if status == "selected" else (),
            equivalent_program_ids=tuple(sorted(item.program_id for item in best_group)),
            margin=margin,
            score=representative.evidence.score,
            field_sha256=field_sha256,
        )

    def clear_program_evidence(
        self,
        state: QiFieldState,
        program_id: int,
    ) -> QiFieldState:
        self.validate_state(state)
        if program_id not in {record.program_id for record in self.program_records(state)}:
            raise QiFieldError("cannot clear unsupported generative program evidence")
        result = QiFieldState(field=state.field.clone())
        self._packed(result)[:, :, self._program_slice(program_id), :] = 0.0
        self.validate_state(result)
        return result

    def clear_program_operators(
        self,
        state: QiFieldState,
        program_id: int,
    ) -> QiFieldState:
        self.validate_state(state)
        if program_id not in {record.program_id for record in self.program_records(state)}:
            raise QiFieldError("cannot clear unsupported generative program operators")
        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        for action_id in range(self.config.action_count):
            basin_id = self._program_basin_id(program_id, action_id)
            target[:, :, self._basin_storage_slice(basin_id), :] = 0.0
        self.validate_state(result)
        return result

    def clear_program(self, state: QiFieldState, program_id: int) -> QiFieldState:
        self.validate_state(state)
        packed = self._packed(state)
        _, status, _, _, _ = self._metadata(packed)
        if status != self._IDLE:
            raise QiFieldError("a program may be cleared only while no thought is active")
        records = {record.program_id: record for record in self.program_records(state)}
        if program_id not in records:
            raise QiFieldError("cannot clear an unsupported generative program")
        result = QiFieldState(field=state.field.clone())
        target = self._packed(result)
        target[:, :, self._program_slice(program_id), :] = 0.0
        for action_id in range(self.config.action_count):
            basin_id = self._program_basin_id(program_id, action_id)
            target[:, :, self._basin_storage_slice(basin_id), :] = 0.0
        self.validate_state(result)
        return result

    def consolidate_program(
        self,
        state: QiFieldState,
        program_id: int,
        predicted: ProgramContext,
        observed: ProgramContext,
    ) -> tuple[QiFieldState, bool]:
        records = {record.program_id: record for record in self.program_records(state)}
        if program_id not in records:
            raise QiFieldError("cannot consolidate an unsupported generative program")
        record = records[program_id]
        residual = self._relative_residual_value(
            evaluate_program(record.program, predicted),
            evaluate_program(record.program, observed),
        )
        if residual > self.config.trajectory_tolerance:
            return state, False
        if record.consolidations >= self._MAX_EXACT_INTEGER:
            raise QiFieldError("program consolidation exceeds exact field capacity")
        return (
            self._write_program(
                state,
                program_id,
                record.program,
                record.evidence,
                regime_mask=record.regime_mask,
                role_mask=record.role_mask,
                consolidations=record.consolidations + 1,
            ),
            True,
        )

    def _program_record(self, state: QiFieldState, program_id: int) -> ProgramRecord:
        for record in self.program_records(state):
            if record.program_id == program_id:
                return record
        raise QiFieldError("requested generative program has no field support")

    def _drift_effect(
        self,
        state: QiFieldState,
        context: ProgramContext,
        program: AbstractionProgram,
    ) -> tuple[float, float]:
        temporal = self.select_program(state, "temporal")
        if temporal.status != "selected" or temporal.program_id is None or context.previous is None:
            return 0.0, 0.0
        temporal_record = self._program_record(state, temporal.program_id)
        drift_value = evaluate_program(temporal_record.program, context)
        raw_drift = (float(drift_value[0].real.item()), float(drift_value[1].real.item()))
        target_index = context.role_b_index
        entities = list(context.current.entities)
        target = entities[target_index]
        entities[target_index] = RelationEntity(
            target.entity_id,
            min(1.0, max(-1.0, target.x + raw_drift[0])),
            min(1.0, max(-1.0, target.y + raw_drift[1])),
        )
        shifted_atoms = RelationAtoms(
            world_id=context.current.world_id,
            episode_id=context.current.episode_id,
            state_sha256=context.current.state_sha256,
            regime=context.current.regime,
            entities=(entities[0], entities[1]),
        )
        shifted = replace(
            context,
            current_view=observation_from_relation_atoms(shifted_atoms),
        )
        before = evaluate_program(program, context)
        after = evaluate_program(program, shifted)
        return (
            float((after[0] - before[0]).real.item()),
            float((after[1] - before[1]).real.item()),
        )

    def _boundary_step_context(
        self,
        program: AbstractionProgram,
        context: ProgramContext,
        action_id: int,
    ) -> ProgramContext:
        action_context = self._with_action(context, action_id)
        predicted = evaluate_program(program, action_context)
        relation = (float(predicted[0].real.item()), float(predicted[1].real.item()))
        target_index = context.role_b_index
        self_index = context.resolved_role_a_index
        entities = list(context.current.entities)
        target = entities[target_index]
        drift = (0.0, 0.0)
        if context.previous is not None:
            previous_target = next(
                entity for entity in context.previous.entities if entity.entity_id == target.entity_id
            )
            drift = (target.x - previous_target.x, target.y - previous_target.y)
        target_next = RelationEntity(
            target.entity_id,
            min(1.0, max(-1.0, target.x + drift[0])),
            min(1.0, max(-1.0, target.y + drift[1])),
        )
        self_entity = entities[self_index]
        self_next = RelationEntity(
            self_entity.entity_id,
            min(1.0, max(-1.0, target_next.x - relation[0])),
            min(1.0, max(-1.0, target_next.y - relation[1])),
        )
        entities[target_index] = target_next
        entities[self_index] = self_next
        body = json.dumps(
            {
                "previous": context.current.state_sha256,
                "action_id": action_id,
                "entities": [asdict(entity) for entity in entities],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        atoms = RelationAtoms(
            world_id=context.current.world_id,
            episode_id=context.current.episode_id,
            state_sha256=hashlib.sha256(body).hexdigest(),
            regime="boundary",
            entities=(entities[0], entities[1]),
        )
        return ProgramContext(
            current_view=observation_from_relation_atoms(atoms),
            previous_view=context.current_view,
            sensor_precision=context.sensor_precision,
            role_a_index=context.role_a_index,
            regime="boundary",
        )

    def generate_trajectory(
        self,
        state: QiFieldState,
        start: ProgramContext,
        goal: ProgramContext,
        *,
        steps: int,
        mode: Literal["historical", "prospective"],
        regime: Literal["interior", "boundary"] = "interior",
        constraints: Mapping[int, ProgramContext] | None = None,
    ) -> TrajectoryProposal:
        if not 1 <= steps <= self.config.slot_count - 1:
            raise QiFieldError("trajectory steps exceed configured slots")
        selection = self.select_program(state, regime)
        if selection.status != "selected" or selection.program_id is None:
            return TrajectoryProposal(
                status="exhausted" if selection.status == "exhausted" else "ambiguous",
                mode=mode,
                regime=regime,
                program_id=-1,
                actions=None,
                equivalent_actions=(),
                final_value=None,
                residual=None,
                field_sha256=self._tensor_sha256(state.field),
            )
        record = self._program_record(state, selection.program_id)
        if regime != "boundary" and not self.program_operators_supported(
            state,
            record.program_id,
        ):
            return TrajectoryProposal(
                status="exhausted",
                mode=mode,
                regime=regime,
                program_id=record.program_id,
                actions=None,
                equivalent_actions=(),
                final_value=None,
                residual=None,
                field_sha256=self._tensor_sha256(state.field),
            )
        goal_value = evaluate_program(record.program, goal)
        valid: list[tuple[tuple[int, ...], torch.Tensor, float]] = []
        for actions in itertools.product(range(self.config.action_count), repeat=steps):
            context = start
            value = evaluate_program(record.program, start)
            accepted = True
            for slot, action_id in enumerate(actions, start=1):
                if regime == "boundary":
                    context = self._boundary_step_context(record.program, context, action_id)
                    value = evaluate_program(record.program, context)
                else:
                    value = self.operator(state, record.program_id, action_id) @ value
                    drift_x, drift_y = self._drift_effect(state, context, record.program)
                    if drift_x or drift_y:
                        x = float(value[0].real.item()) + drift_x
                        y = float(value[1].real.item()) + drift_y
                        value = torch.tensor((x, y, 1.0, x * y), dtype=torch.complex128)
                if constraints and slot in constraints:
                    target = evaluate_program(record.program, constraints[slot])
                    tolerance = self.config.trajectory_tolerance + 4.0 * (
                        constraints[slot].sensor_precision + start.sensor_precision
                    )
                    if self._relative_residual_value(value, target) > tolerance:
                        accepted = False
                        break
            if not accepted:
                continue
            residual = self._relative_residual_value(value, goal_value)
            tolerance = self.config.trajectory_tolerance + 4.0 * (
                start.sensor_precision + goal.sensor_precision
            )
            if residual <= tolerance:
                valid.append((tuple(actions), value, residual))
        if not valid:
            return TrajectoryProposal(
                status="exhausted",
                mode=mode,
                regime=regime,
                program_id=record.program_id,
                actions=None,
                equivalent_actions=(),
                final_value=None,
                residual=None,
                field_sha256=self._tensor_sha256(state.field),
            )
        best_residual = min(item[2] for item in valid)
        equivalence_band = self.config.selection_margin + 4.0 * (
            start.sensor_precision + goal.sensor_precision
        )
        settled = tuple(
            item for item in valid if item[2] <= best_residual + equivalence_band
        )
        equivalents = tuple(sorted(item[0] for item in settled))
        if mode == "historical" and len(equivalents) != 1:
            return TrajectoryProposal(
                status="ambiguous",
                mode=mode,
                regime=regime,
                program_id=record.program_id,
                actions=None,
                equivalent_actions=equivalents,
                final_value=None,
                residual=best_residual,
                field_sha256=self._tensor_sha256(state.field),
            )
        chosen = min(settled, key=lambda item: (item[2], item[0]))
        final_values = tuple(float(value.real.item()) for value in chosen[1])
        assert len(final_values) == 4
        return TrajectoryProposal(
            status="selected",
            mode=mode,
            regime=regime,
            program_id=record.program_id,
            actions=chosen[0],
            equivalent_actions=equivalents,
            final_value=(
                final_values[0],
                final_values[1],
                final_values[2],
                final_values[3],
            ),
            residual=chosen[2],
            field_sha256=self._tensor_sha256(state.field),
        )

    def resolve_roles(
        self,
        state: QiFieldState,
        before: RelationAtoms,
        *,
        action_id: int | None = None,
        after: RelationAtoms | None = None,
    ) -> RoleResolution:
        selection = self.select_program(state, "interior")
        field_sha256 = self._tensor_sha256(state.field)
        if selection.status != "selected" or selection.program_id is None:
            return RoleResolution("exhausted", None, (), None, field_sha256)
        if action_id is None or after is None:
            return RoleResolution("ambiguous", None, (0, 1), None, field_sha256)
        record = self._program_record(state, selection.program_id)
        residuals = []
        for self_index in (0, 1):
            before_context = ProgramContext(
                current_view=observation_from_relation_atoms(before),
                action_delta=self.config.action_deltas[action_id],
                role_a_index=self_index,
                regime=before.regime,
            )
            acted_id = before.entities[self_index].entity_id
            after_index = next(
                (
                    index
                    for index, entity in enumerate(after.entities)
                    if entity.entity_id == acted_id
                ),
                None,
            )
            if after_index is None:
                continue
            after_context = ProgramContext(
                current_view=observation_from_relation_atoms(after),
                role_a_index=after_index,
                regime=after.regime,
            )
            predicted = self.operator(state, record.program_id, action_id) @ evaluate_program(
                record.program,
                before_context,
            )
            residuals.append(
                self._relative_residual_value(
                    predicted,
                    evaluate_program(record.program, after_context),
                )
            )
        eligible = tuple(
            index
            for index, residual in enumerate(residuals)
            if residual <= self.config.trajectory_tolerance
        )
        if len(eligible) == 1:
            return RoleResolution("selected", eligible[0], eligible, tuple(residuals), field_sha256)
        if eligible:
            return RoleResolution("ambiguous", None, eligible, tuple(residuals), field_sha256)
        return RoleResolution("exhausted", None, (), tuple(residuals), field_sha256)

    def expand_each_object(
        self,
        frames: Sequence[ObservableEntityFrame],
        *,
        sensor_precision: float = 0.0,
        permuted: bool = False,
    ) -> tuple[EntityHypothesis, ...]:
        if not frames:
            raise QiFieldError("EACH_OBJECT requires at least one observable frame")
        first = frames[0]
        object_ids = tuple(item.entity_id for item in first.objects)
        for frame in frames[1:]:
            if (
                frame.world_id != first.world_id
                or frame.episode_id != first.episode_id
                or frame.self_entity.entity_id != first.self_entity.entity_id
                or {item.entity_id for item in frame.objects} != set(object_ids)
            ):
                raise QiFieldError(
                    "EACH_OBJECT frames must preserve world, self, and object identities"
                )
        hypotheses = []
        for object_id in object_ids:
            contexts = []
            previous_view = None
            for frame in frames:
                objects = {item.entity_id: item for item in frame.objects}
                candidate = objects[object_id]
                entities = (
                    (candidate, frame.self_entity)
                    if permuted
                    else (frame.self_entity, candidate)
                )
                atoms = RelationAtoms(
                    world_id=frame.world_id,
                    episode_id=frame.episode_id,
                    state_sha256=frame.state_sha256,
                    regime=frame.regime,
                    entities=entities,
                )
                current_view = observation_from_relation_atoms(atoms)
                contexts.append(
                    ProgramContext(
                        previous_view=previous_view,
                        current_view=current_view,
                        sensor_precision=sensor_precision,
                        role_a_index=1 if permuted else 0,
                        regime=frame.regime,
                    )
                )
                previous_view = current_view
            hypotheses.append(EntityHypothesis(object_id, tuple(contexts)))
        return tuple(hypotheses)

    def resolve_each_object(
        self,
        state: QiFieldState,
        frames: Sequence[ObservableEntityFrame],
        actions: Sequence[int],
        *,
        sensor_precision: float = 0.0,
        permuted: bool = False,
    ) -> EntityResolution:
        hypotheses = self.expand_each_object(
            frames,
            sensor_precision=sensor_precision,
            permuted=permuted,
        )
        resolution = self.resolve_entities(
            state,
            [hypothesis.contexts for hypothesis in hypotheses],
            actions,
        )
        candidate_ids = tuple(hypothesis.entity_id for hypothesis in hypotheses)
        equivalent_ids = tuple(
            candidate_ids[index] for index in resolution.equivalent_indices
        )
        return replace(
            resolution,
            candidate_entity_ids=candidate_ids,
            selected_entity_id=(
                candidate_ids[resolution.selected_index]
                if resolution.selected_index is not None
                else None
            ),
            equivalent_entity_ids=equivalent_ids,
        )

    def resolve_entities(
        self,
        state: QiFieldState,
        candidate_sequences: Sequence[Sequence[ProgramContext]],
        actions: Sequence[int],
    ) -> EntityResolution:
        selection = self.select_program(state, "interior")
        field_sha256 = self._tensor_sha256(state.field)
        if selection.status != "selected" or selection.program_id is None:
            return EntityResolution("exhausted", None, (), (), field_sha256)
        record = self._program_record(state, selection.program_id)
        residuals = []
        for contexts in candidate_sequences:
            if len(contexts) != len(actions) + 1:
                raise QiFieldError("entity candidate sequence length mismatch")
            value = evaluate_program(record.program, contexts[0])
            for action_id in actions:
                value = self.operator(state, record.program_id, action_id) @ value
            residuals.append(
                self._relative_residual_value(
                    value,
                    evaluate_program(record.program, contexts[-1]),
                )
            )
        eligible = tuple(
            index
            for index, residual in enumerate(residuals)
            if residual <= self.config.action_residual_tolerance
        )
        if len(eligible) == 1:
            return EntityResolution("selected", eligible[0], eligible, tuple(residuals), field_sha256)
        if eligible:
            return EntityResolution("ambiguous", None, eligible, tuple(residuals), field_sha256)
        return EntityResolution("exhausted", None, (), tuple(residuals), field_sha256)
