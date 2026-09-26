"""Canonical executable-record views for the programmable field swarm.

The records in this module are immutable descriptions.  Runtime state lives in
``ComputerState.field``; these values are encoded into that state by the Python
regional kernel and never act as a second persistence root.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any, ClassVar, Mapping, Sequence


class RecordError(ValueError):
    """A programmable record is not canonical or internally complete."""


def canonical_json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RecordError("record is not canonical JSON") from exc


def digest_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _text(value: str, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not value and not allow_empty):
        raise RecordError(f"{name} must be text")
    if len(value.encode("utf-8")) > 65_536:
        raise RecordError(f"{name} is too large")
    return value


def _digest(value: str, name: str) -> str:
    if not isinstance(value, str) or len(value) != 64:
        raise RecordError(f"{name} must be a SHA-256 digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise RecordError(f"{name} must be a SHA-256 digest") from exc
    return value.lower()


def _integer(value: int, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise RecordError(f"{name} must be an integer >= {minimum}")
    return value


def _plain(value: Any, name: str) -> Any:
    encoded = canonical_json_bytes(value)
    return json.loads(encoded.decode("utf-8"))


def _texts(values: Sequence[str], name: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise RecordError(f"{name} must be a sequence")
    return tuple(_text(item, name) for item in values)


def _mapping(value: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise RecordError(f"{name} must be a mapping")
    plain = _plain(dict(value), name)
    if not isinstance(plain, dict):
        raise RecordError(f"{name} must be a mapping")
    return plain


@dataclass(frozen=True, slots=True)
class CanonicalRecord:
    SCHEMA: ClassVar[str] = "cassifi.programmable-record.v1"

    def __post_init__(self) -> None:
        canonical_json_bytes(self.as_dict())

    def as_dict(self) -> Mapping[str, Any]:
        return {"schema": self.SCHEMA, **asdict(self)}

    @property
    def sha256(self) -> str:
        return digest_value(self.as_dict())


@dataclass(frozen=True, slots=True)
class PythonSemantics(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.python-semantics.v1"
    python_version: str
    grammar: str
    implementation_abi: str
    implementation_choices: Mapping[str, Any]
    stdlib_manifest: Mapping[str, Any]
    arithmetic_profile: Mapping[str, Any]
    hash_policy: Mapping[str, Any]
    primitive_contracts: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.python_version, "python_version")
        _text(self.grammar, "grammar")
        _text(self.implementation_abi, "implementation_abi")
        object.__setattr__(self, "implementation_choices", _mapping(self.implementation_choices, "implementation_choices"))
        object.__setattr__(self, "stdlib_manifest", _mapping(self.stdlib_manifest, "stdlib_manifest"))
        object.__setattr__(self, "arithmetic_profile", _mapping(self.arithmetic_profile, "arithmetic_profile"))
        object.__setattr__(self, "hash_policy", _mapping(self.hash_policy, "hash_policy"))
        object.__setattr__(self, "primitive_contracts", _texts(self.primitive_contracts, "primitive_contracts"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class InterpreterProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.interpreter-program.v1"
    program_id: str
    version: int
    source_sha256: str
    ir_sha256: str
    semantics_sha256: str
    dependencies: tuple[str, ...]
    entry: str
    source_map: Mapping[str, Any]
    assessment: Mapping[str, Any]
    adoption_state: str

    def __post_init__(self) -> None:
        _text(self.program_id, "program_id")
        _integer(self.version, "version", minimum=1)
        for value, name in ((self.source_sha256, "source_sha256"), (self.ir_sha256, "ir_sha256"), (self.semantics_sha256, "semantics_sha256")):
            _digest(value, name)
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        _text(self.entry, "entry")
        object.__setattr__(self, "source_map", _mapping(self.source_map, "source_map"))
        object.__setattr__(self, "assessment", _mapping(self.assessment, "assessment"))
        if self.adoption_state not in {"candidate", "restricted", "adopted", "retired"}:
            raise RecordError("adoption_state is invalid")
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class PythonProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.python-program.v1"
    program_id: str
    version: int
    source_sha256: str
    source_name: str
    module: str
    package: str | None
    mode: str
    future_flags: tuple[str, ...]
    dependencies: tuple[str, ...]
    capability_requirements: tuple[str, ...]
    code: Mapping[str, Any]
    source_map: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.program_id, "program_id")
        _integer(self.version, "version", minimum=1)
        _digest(self.source_sha256, "source_sha256")
        _text(self.source_name, "source_name")
        _text(self.module, "module")
        if self.package is not None:
            _text(self.package, "package", allow_empty=True)
        if self.mode not in {"exec", "eval", "single"}:
            raise RecordError("mode is invalid")
        object.__setattr__(self, "future_flags", _texts(self.future_flags, "future_flags"))
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        object.__setattr__(self, "capability_requirements", _texts(self.capability_requirements, "capability_requirements"))
        object.__setattr__(self, "code", _mapping(self.code, "code"))
        object.__setattr__(self, "source_map", _mapping(self.source_map, "source_map"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class PyObject(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.py-object.v1"
    object_id: str
    generation: int
    type_name: str
    layout: str
    mutable_version: int
    payload_refs: tuple[str, ...]
    owning_scope: str
    collection: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.object_id, "object_id")
        _integer(self.generation, "generation", minimum=1)
        _text(self.type_name, "type_name")
        _text(self.layout, "layout")
        _integer(self.mutable_version, "mutable_version")
        object.__setattr__(self, "payload_refs", _texts(self.payload_refs, "payload_refs"))
        _text(self.owning_scope, "owning_scope")
        object.__setattr__(self, "collection", _mapping(self.collection, "collection"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class PyFrame(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.py-frame.v1"
    frame_id: str
    interpreter_ref: str
    code_ref: str
    program_counter: int
    locals_ref: str
    globals_ref: str
    builtins_ref: str
    value_stack: tuple[Any, ...]
    block_stack: tuple[Mapping[str, Any], ...]
    closure_cells: tuple[str, ...]
    exception_state: Mapping[str, Any] | None
    unwind_state: Mapping[str, Any] | None
    caller_ref: str | None
    source_span: Mapping[str, Any] | None

    def __post_init__(self) -> None:
        for value, name in ((self.frame_id, "frame_id"), (self.interpreter_ref, "interpreter_ref"), (self.code_ref, "code_ref"), (self.locals_ref, "locals_ref"), (self.globals_ref, "globals_ref"), (self.builtins_ref, "builtins_ref")):
            _text(value, name)
        _integer(self.program_counter, "program_counter")
        object.__setattr__(self, "value_stack", tuple(_plain(list(self.value_stack), "value_stack")))
        object.__setattr__(self, "block_stack", tuple(_mapping(item, "block_stack") for item in self.block_stack))
        object.__setattr__(self, "closure_cells", _texts(self.closure_cells, "closure_cells"))
        if self.exception_state is not None:
            object.__setattr__(self, "exception_state", _mapping(self.exception_state, "exception_state"))
        if self.unwind_state is not None:
            object.__setattr__(self, "unwind_state", _mapping(self.unwind_state, "unwind_state"))
        if self.caller_ref is not None:
            _text(self.caller_ref, "caller_ref")
        if self.source_span is not None:
            object.__setattr__(self, "source_span", _mapping(self.source_span, "source_span"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class PyTask(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.py-task.v1"
    task_id: str
    role: str
    frame_ref: str | None
    suspension: str
    await_target: str | None
    pending_send: Any
    pending_throw: Mapping[str, Any] | None
    schedule_binding: str

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        if self.role not in {"main", "generator", "coroutine", "import", "finalizer", "model"}:
            raise RecordError("task role is invalid")
        if self.frame_ref is not None:
            _text(self.frame_ref, "frame_ref")
        _text(self.suspension, "suspension")
        if self.await_target is not None:
            _text(self.await_target, "await_target")
        object.__setattr__(self, "pending_send", _plain(self.pending_send, "pending_send"))
        if self.pending_throw is not None:
            object.__setattr__(self, "pending_throw", _mapping(self.pending_throw, "pending_throw"))
        _text(self.schedule_binding, "schedule_binding")
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class PyOperation(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.py-operation.v1"
    operation_id: str
    kind: str
    phase: str
    cursor: int
    immutable_input_versions: Mapping[str, int]
    partial_output_ref: str | None
    callback_tokens: tuple[str, ...]
    effect_tokens: tuple[str, ...]
    charged_work: int

    def __post_init__(self) -> None:
        _text(self.operation_id, "operation_id")
        _text(self.kind, "kind")
        _text(self.phase, "phase")
        _integer(self.cursor, "cursor")
        versions = _mapping(self.immutable_input_versions, "immutable_input_versions")
        if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in versions.values()):
            raise RecordError("immutable input versions are invalid")
        object.__setattr__(self, "immutable_input_versions", versions)
        if self.partial_output_ref is not None:
            _text(self.partial_output_ref, "partial_output_ref")
        object.__setattr__(self, "callback_tokens", _texts(self.callback_tokens, "callback_tokens"))
        object.__setattr__(self, "effect_tokens", _texts(self.effect_tokens, "effect_tokens"))
        _integer(self.charged_work, "charged_work")
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class ModelProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.model-program.v1"
    program_id: str
    graph_sha256: str
    tensor_manifest_sha256: str
    tokenizer_sha256: str
    architecture: str
    quantization_profile: Mapping[str, Any]
    operation_versions: Mapping[str, str]
    entry: str
    assessment: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.program_id, "program_id")
        _digest(self.graph_sha256, "graph_sha256")
        _digest(self.tensor_manifest_sha256, "tensor_manifest_sha256")
        _digest(self.tokenizer_sha256, "tokenizer_sha256")
        _text(self.architecture, "architecture")
        object.__setattr__(self, "quantization_profile", _mapping(self.quantization_profile, "quantization_profile"))
        object.__setattr__(self, "operation_versions", _mapping(self.operation_versions, "operation_versions"))
        _text(self.entry, "entry")
        object.__setattr__(self, "assessment", _mapping(self.assessment, "assessment"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class TensorView(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.tensor-view.v1"
    tensor_id: str
    owner_id: str
    scope_id: str
    shape: tuple[int, ...]
    dtype: str
    strides: tuple[int, ...]
    quantization_layout: Mapping[str, Any] | None
    backing_sha256: str | None
    mutable_version: int | None
    rights: tuple[str, ...]
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.tensor_id, "tensor_id")
        _text(self.owner_id, "owner_id")
        _text(self.scope_id, "scope_id")
        if not self.shape or any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in self.shape):
            raise RecordError("tensor shape is invalid")
        if len(self.strides) != len(self.shape) or any(isinstance(item, bool) or not isinstance(item, int) for item in self.strides):
            raise RecordError("tensor strides are invalid")
        _text(self.dtype, "dtype")
        if self.quantization_layout is not None:
            object.__setattr__(self, "quantization_layout", _mapping(self.quantization_layout, "quantization_layout"))
        if self.backing_sha256 is not None:
            _digest(self.backing_sha256, "backing_sha256")
        if self.mutable_version is not None:
            _integer(self.mutable_version, "mutable_version")
        if (self.backing_sha256 is None) == (self.mutable_version is None):
            raise RecordError("tensor must have exactly one immutable or mutable identity")
        object.__setattr__(self, "rights", _texts(self.rights, "rights"))
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class ModelContinuation(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.model-continuation.v1"
    continuation_id: str
    token_position: int
    block_cursor: int
    operation_cursor: int
    live_activation_refs: tuple[str, ...]
    attention_roots: tuple[str, ...]
    recurrent_roots: tuple[str, ...]
    sampler_state: Mapping[str, Any]
    rng_state: Mapping[str, Any]
    pending_deltas: tuple[Mapping[str, Any], ...]
    checkpoint_sha256: str

    def __post_init__(self) -> None:
        _text(self.continuation_id, "continuation_id")
        _integer(self.token_position, "token_position")
        _integer(self.block_cursor, "block_cursor")
        _integer(self.operation_cursor, "operation_cursor")
        object.__setattr__(self, "live_activation_refs", _texts(self.live_activation_refs, "live_activation_refs"))
        object.__setattr__(self, "attention_roots", _texts(self.attention_roots, "attention_roots"))
        object.__setattr__(self, "recurrent_roots", _texts(self.recurrent_roots, "recurrent_roots"))
        object.__setattr__(self, "sampler_state", _mapping(self.sampler_state, "sampler_state"))
        object.__setattr__(self, "rng_state", _mapping(self.rng_state, "rng_state"))
        object.__setattr__(self, "pending_deltas", tuple(_mapping(item, "pending_deltas") for item in self.pending_deltas))
        _digest(self.checkpoint_sha256, "checkpoint_sha256")
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class ComputationView(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.computation-view.v1"
    computation_id: str
    version: int
    owner_id: str
    program_id: str
    status: str
    frame_refs: tuple[str, ...]
    object_refs: tuple[str, ...]
    assumptions: tuple[Mapping[str, Any], ...]
    dependencies: tuple[str, ...]
    effects: tuple[Mapping[str, Any], ...]
    costs: Mapping[str, Any]
    result: Any
    unfinished_reason: str | None
    page: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.computation_id, "computation_id")
        _integer(self.version, "version", minimum=1)
        _text(self.owner_id, "owner_id")
        _text(self.program_id, "program_id")
        _text(self.status, "status")
        object.__setattr__(self, "frame_refs", _texts(self.frame_refs, "frame_refs"))
        object.__setattr__(self, "object_refs", _texts(self.object_refs, "object_refs"))
        object.__setattr__(self, "assumptions", tuple(_mapping(item, "assumptions") for item in self.assumptions))
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        object.__setattr__(self, "effects", tuple(_mapping(item, "effects") for item in self.effects))
        object.__setattr__(self, "costs", _mapping(self.costs, "costs"))
        object.__setattr__(self, "result", _plain(self.result, "result"))
        if self.unfinished_reason is not None:
            _text(self.unfinished_reason, "unfinished_reason")
        object.__setattr__(self, "page", _mapping(self.page, "page"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class RepresentationProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.representation-program.v1"
    representation_id: str
    version: int
    concepts: Mapping[str, Any]
    roles: Mapping[str, Any]
    grammar: Mapping[str, Any] | None
    operator_refs: tuple[str, ...]
    observation_mappings: tuple[Mapping[str, Any], ...]
    preserved_distinctions: tuple[str, ...]
    lost_distinctions: tuple[str, ...]
    applicability: Mapping[str, Any]
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.representation_id, "representation_id")
        _integer(self.version, "version", minimum=1)
        object.__setattr__(self, "concepts", _mapping(self.concepts, "concepts"))
        object.__setattr__(self, "roles", _mapping(self.roles, "roles"))
        if self.grammar is not None:
            object.__setattr__(self, "grammar", _mapping(self.grammar, "grammar"))
        object.__setattr__(self, "operator_refs", _texts(self.operator_refs, "operator_refs"))
        object.__setattr__(self, "observation_mappings", tuple(_mapping(item, "observation_mappings") for item in self.observation_mappings))
        object.__setattr__(self, "preserved_distinctions", _texts(self.preserved_distinctions, "preserved_distinctions"))
        object.__setattr__(self, "lost_distinctions", _texts(self.lost_distinctions, "lost_distinctions"))
        object.__setattr__(self, "applicability", _mapping(self.applicability, "applicability"))
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class WorldProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.world-program.v1"
    world_id: str
    version: int
    state_program_ref: str
    transition_program_ref: str
    readout_program_ref: str
    initial_conditions: Mapping[str, Any]
    boundary_conditions: Mapping[str, Any]
    assumptions: tuple[Mapping[str, Any], ...]
    uncertainty: Mapping[str, Any]
    numerical_regime: Mapping[str, Any]
    failure_regimes: tuple[Mapping[str, Any], ...]
    forecast_history: tuple[Mapping[str, Any], ...]
    observed_outcomes: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        _text(self.world_id, "world_id")
        _integer(self.version, "version", minimum=1)
        for value, name in ((self.state_program_ref, "state_program_ref"), (self.transition_program_ref, "transition_program_ref"), (self.readout_program_ref, "readout_program_ref")):
            _text(value, name)
        object.__setattr__(self, "initial_conditions", _mapping(self.initial_conditions, "initial_conditions"))
        object.__setattr__(self, "boundary_conditions", _mapping(self.boundary_conditions, "boundary_conditions"))
        object.__setattr__(self, "assumptions", tuple(_mapping(item, "assumptions") for item in self.assumptions))
        object.__setattr__(self, "uncertainty", _mapping(self.uncertainty, "uncertainty"))
        object.__setattr__(self, "numerical_regime", _mapping(self.numerical_regime, "numerical_regime"))
        object.__setattr__(self, "failure_regimes", tuple(_mapping(item, "failure_regimes") for item in self.failure_regimes))
        object.__setattr__(self, "forecast_history", tuple(_mapping(item, "forecast_history") for item in self.forecast_history))
        object.__setattr__(self, "observed_outcomes", tuple(_mapping(item, "observed_outcomes") for item in self.observed_outcomes))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class DesignProblem(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.design-problem.v1"
    problem_id: str
    desired_readout: Mapping[str, Any]
    horizon: Mapping[str, Any]
    admissible_variables: tuple[str, ...]
    admissible_interventions: tuple[str, ...]
    constraints: tuple[Mapping[str, Any], ...]
    objectives: tuple[Mapping[str, Any], ...]
    world_version: str
    method_version: str
    search_continuation: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.problem_id, "problem_id")
        object.__setattr__(self, "desired_readout", _mapping(self.desired_readout, "desired_readout"))
        object.__setattr__(self, "horizon", _mapping(self.horizon, "horizon"))
        object.__setattr__(self, "admissible_variables", _texts(self.admissible_variables, "admissible_variables"))
        object.__setattr__(self, "admissible_interventions", _texts(self.admissible_interventions, "admissible_interventions"))
        object.__setattr__(self, "constraints", tuple(_mapping(item, "constraints") for item in self.constraints))
        object.__setattr__(self, "objectives", tuple(_mapping(item, "objectives") for item in self.objectives))
        _text(self.world_version, "world_version")
        _text(self.method_version, "method_version")
        object.__setattr__(self, "search_continuation", _mapping(self.search_continuation, "search_continuation"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class ReasoningStudy(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.reasoning-study.v1"
    study_id: str
    original_episode: str
    predecessor_checkpoint: str
    contrasted_computation: Mapping[str, Any]
    matched_conditions: Mapping[str, Any]
    readouts: tuple[Mapping[str, Any], ...]
    retained_differences: tuple[Mapping[str, Any], ...]
    scope: str
    actual_cost: Mapping[str, Any]
    conclusion_scope: str

    def __post_init__(self) -> None:
        for value, name in ((self.study_id, "study_id"), (self.original_episode, "original_episode"), (self.scope, "scope"), (self.conclusion_scope, "conclusion_scope")):
            _text(value, name)
        _digest(self.predecessor_checkpoint, "predecessor_checkpoint")
        object.__setattr__(self, "contrasted_computation", _mapping(self.contrasted_computation, "contrasted_computation"))
        object.__setattr__(self, "matched_conditions", _mapping(self.matched_conditions, "matched_conditions"))
        object.__setattr__(self, "readouts", tuple(_mapping(item, "readouts") for item in self.readouts))
        object.__setattr__(self, "retained_differences", tuple(_mapping(item, "retained_differences") for item in self.retained_differences))
        object.__setattr__(self, "actual_cost", _mapping(self.actual_cost, "actual_cost"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class InstrumentProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.instrument-program.v1"
    instrument_id: str
    version: int
    callable_program_ref: str
    input_ports: tuple[Mapping[str, Any], ...]
    output_ports: tuple[Mapping[str, Any], ...]
    effects: tuple[str, ...]
    guards: tuple[Mapping[str, Any], ...]
    state_interface: Mapping[str, Any]
    continuation_interface: Mapping[str, Any]
    dependencies: tuple[str, ...]
    composition_assessment: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.instrument_id, "instrument_id")
        _integer(self.version, "version", minimum=1)
        _text(self.callable_program_ref, "callable_program_ref")
        object.__setattr__(self, "input_ports", tuple(_mapping(item, "input_ports") for item in self.input_ports))
        object.__setattr__(self, "output_ports", tuple(_mapping(item, "output_ports") for item in self.output_ports))
        object.__setattr__(self, "effects", _texts(self.effects, "effects"))
        object.__setattr__(self, "guards", tuple(_mapping(item, "guards") for item in self.guards))
        object.__setattr__(self, "state_interface", _mapping(self.state_interface, "state_interface"))
        object.__setattr__(self, "continuation_interface", _mapping(self.continuation_interface, "continuation_interface"))
        object.__setattr__(self, "dependencies", _texts(self.dependencies, "dependencies"))
        object.__setattr__(self, "composition_assessment", _mapping(self.composition_assessment, "composition_assessment"))
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class ConstructorProgram(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.constructor-program.v1"
    constructor_id: str
    version: int
    callable_program_ref: str
    specification_inputs: tuple[Mapping[str, Any], ...]
    output_contract: Mapping[str, Any]
    construction_dependencies: tuple[str, ...]
    unresolved_holes: tuple[Mapping[str, Any], ...]
    product_lineage: tuple[str, ...]
    admission_disposition: str

    def __post_init__(self) -> None:
        _text(self.constructor_id, "constructor_id")
        _integer(self.version, "version", minimum=1)
        _text(self.callable_program_ref, "callable_program_ref")
        object.__setattr__(self, "specification_inputs", tuple(_mapping(item, "specification_inputs") for item in self.specification_inputs))
        object.__setattr__(self, "output_contract", _mapping(self.output_contract, "output_contract"))
        object.__setattr__(self, "construction_dependencies", _texts(self.construction_dependencies, "construction_dependencies"))
        object.__setattr__(self, "unresolved_holes", tuple(_mapping(item, "unresolved_holes") for item in self.unresolved_holes))
        object.__setattr__(self, "product_lineage", _texts(self.product_lineage, "product_lineage"))
        if self.admission_disposition not in {"candidate", "admitted", "rejected", "unresolved"}:
            raise RecordError("admission_disposition is invalid")
        CanonicalRecord.__post_init__(self)


@dataclass(frozen=True, slots=True)
class WorkspaceBinding(CanonicalRecord):
    SCHEMA: ClassVar[str] = "cassifi.workspace-binding.v1"
    binding_id: str
    principal: str
    question_refs: tuple[str, ...]
    object_refs: tuple[str, ...]
    representation_versions: Mapping[str, int]
    view_versions: Mapping[str, int]
    field_revision: str
    annotation_status: str
    selected_branches: tuple[str, ...]
    admitted_guidance_id: str | None

    def __post_init__(self) -> None:
        _text(self.binding_id, "binding_id")
        _text(self.principal, "principal")
        object.__setattr__(self, "question_refs", _texts(self.question_refs, "question_refs"))
        object.__setattr__(self, "object_refs", _texts(self.object_refs, "object_refs"))
        for field_name in ("representation_versions", "view_versions"):
            values = _mapping(getattr(self, field_name), field_name)
            if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values.values()):
                raise RecordError(f"{field_name} is invalid")
            object.__setattr__(self, field_name, values)
        _digest(self.field_revision, "field_revision")
        if self.annotation_status not in {"draft", "admitted", "ambiguous", "stale", "resolved", "cancelled"}:
            raise RecordError("annotation_status is invalid")
        object.__setattr__(self, "selected_branches", _texts(self.selected_branches, "selected_branches"))
        if self.admitted_guidance_id is not None:
            _text(self.admitted_guidance_id, "admitted_guidance_id")
        CanonicalRecord.__post_init__(self)


RECORD_TYPES = {
    record.SCHEMA: record
    for record in (
        PythonSemantics,
        InterpreterProgram,
        PythonProgram,
        PyObject,
        PyFrame,
        PyTask,
        PyOperation,
        ModelProgram,
        TensorView,
        ModelContinuation,
        ComputationView,
        RepresentationProgram,
        WorldProgram,
        DesignProblem,
        ReasoningStudy,
        InstrumentProgram,
        ConstructorProgram,
        WorkspaceBinding,
    )
}


def decode_record(value: Mapping[str, Any]) -> CanonicalRecord:
    if not isinstance(value, Mapping):
        raise RecordError("record must be a mapping")
    schema = value.get("schema")
    record_type = RECORD_TYPES.get(schema)
    if record_type is None:
        raise RecordError("record schema is unsupported")
    kwargs = {key: item for key, item in value.items() if key != "schema"}
    try:
        return record_type(**kwargs)
    except TypeError as exc:
        raise RecordError("record fields are invalid") from exc


def default_python_semantics() -> PythonSemantics:
    """Pinned semantics for the bootstrap field interpreter."""
    return PythonSemantics(
        python_version="3.12",
        grammar="python-3.12-ast",
        implementation_abi="cassifi-field-python-v1",
        implementation_choices={
            "finalization": "incremental-safe-point",
            "id": "stable-logical-object-identity",
            "int": "signed-arbitrary-precision",
            "string_index": "unicode-code-point",
            "native_extension_abi": "explicit-manifest-only",
        },
        stdlib_manifest={
            "builtins": {"kind": "field-runtime", "status": "available"},
            "math": {"kind": "field-runtime", "status": "available"},
            "json": {"kind": "field-runtime", "status": "available"},
            "collections": {"kind": "field-python", "status": "available"},
            "asyncio": {"kind": "field-runtime", "status": "cooperative-subset"},
            "ctypes": {"kind": "native-extension", "status": "unavailable", "abi": "unsupported-native-abi"},
        },
        arithmetic_profile={
            "float": "ieee-754-binary64",
            "rounding": "nearest-ties-even",
            "fast_math": False,
            "negative_division": "python-floor",
        },
        hash_policy={
            "algorithm": "sha256-derived-stable",
            "randomized": False,
            "mutable_values": "unhashable",
        },
        primitive_contracts=(
            "word-u32-v1",
            "integer-limb-v1",
            "binary64-bits-v1",
            "unicode-codepoint-v1",
            "heap-reference-v1",
            "bounded-tensor-v1",
        ),
    )


__all__ = [
    "CanonicalRecord",
    "ComputationView",
    "ConstructorProgram",
    "DesignProblem",
    "InstrumentProgram",
    "InterpreterProgram",
    "ModelContinuation",
    "ModelProgram",
    "PyFrame",
    "PyObject",
    "PyOperation",
    "PyTask",
    "PythonProgram",
    "PythonSemantics",
    "RecordError",
    "RepresentationProgram",
    "TensorView",
    "WorkspaceBinding",
    "WorldProgram",
    "ReasoningStudy",
    "canonical_json_bytes",
    "decode_record",
    "default_python_semantics",
    "digest_value",
]
