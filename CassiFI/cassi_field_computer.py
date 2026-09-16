"""A deterministic programmable computer owned by one immutable nine-plane field.

The runtime is a fixed five-word-instruction, two-stack interpreter.  Its
program, stacks, accumulator, instruction boundary, terminal state, budget,
and resource ledger are all coordinates in one exact-integer ``float64``
tensor. Public states are immutable: ``step`` seals one successor per
instruction, while ``run`` applies that exact transition function inside one
bounded working copy and seals one successor for the requested batch. The step
simulation invariant is:

    at every running instruction boundary, ``pc`` names one canonical
    instruction, the two stack planes contain their bottom-to-top sequences,
    and the accumulator holds the preceding POP/PROPAGATE result (or ``EMPTY``).

Executing one instruction preserves that invariant (or records an explicit
terminal exhaustion/fault) and increments the transition ledger exactly once
for an instruction that was attempted.  A PUSH that cannot fit is an explicit
storage exhaustion before the instruction is attempted, so resizing can retry
the same boundary without silently losing work.  A bounded ``run(...,
steps=n)`` is a resumable pause, not exhaustion.

The compiler below translates any finite, total deterministic single-tape
Turing-machine table into this vocabulary.  Abstractly, two stacks provide
expandable storage and therefore the usual universal-machine argument applies
to the abstract machine.  A concrete profile has finite program/stack/budget
limits: no finite execution, and no finite tensor, proves universality.

No host-side Turing-machine step is performed by :class:`FieldComputer`; all
machine work is represented by the generated instruction stream and executed
by the same interpreter as hand-written programs.

PROPAGATE extends the six scalar primitives with one bounded CNF operation.
The selected byte stack contains its versioned data frame and all automaton
lanes. A shared stateless lane kernel selects one currently legal unit row;
the instruction applies at most one deduction and returns a status byte for
ordinary control flow. No standalone solver or secondary state object runs.
This is a local propagation accelerator, not a complete SAT procedure or a
constant-scalar-cost instruction. Turing/structured compilers still target the
original six primitives; raw programs may invoke PROPAGATE directly.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from struct import Struct
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_constraint_dynamics import (
    ExcitableConstraintController,
    ExcitableConstraintProfile,
)
import cassi_field_regions as field_regions


SCHEMA = "cassifi.field-computer.v2"
_PREVIOUS_SCHEMA = "cassifi.field-computer.v1"
_LAYOUT = "field-computer-two-stack-nine-plane-v1"
_MAGIC = 0xC5FC
_SAFE_INTEGER = 2**53 - 1

# Public instruction vocabulary.
HALT = 0
PUSH = 1
POP = 2
BRANCH = 3
PUSH_ACC = 4
JUMP = 5
PROPAGATE = 6
PROPAGATION_PROGRESS = 1
PROPAGATION_FIXED_POINT = 2
PROPAGATION_CONFLICT = 3
PROPAGATION_SATISFIED = 4

# Fixed-size, little-endian byte frame on an ordinary machine stack:
# header, tri-state assignment, uint16 row lengths, int32 literals,
# exact float64 automaton lanes, uint32 total frame length. No sidecar state.
_PROPAGATION_HEADER = Struct("<4sHHBHQQQ")
_PROPAGATION_MAGIC = b"CFP1"
_PROPAGATION_RESULTS = {
    0: "ready",
    PROPAGATION_PROGRESS: "progress",
    PROPAGATION_FIXED_POINT: "fixed_point",
    PROPAGATION_CONFLICT: "conflict",
    PROPAGATION_SATISFIED: "satisfied",
}
EMPTY = 256
_BLOCK_HOT_THRESHOLD = 8
_HEAT_LIMIT = 65_535

# Logical nine-plane layout.  The stored tensor is [1, 9*M, 1], matching the
# existing Cassi field convention while retaining nine independently named
# planes when reshaped.
_PROGRAM_OPCODE = 0
_PROGRAM_A = 1
_PROGRAM_B = 2
_PROGRAM_C = 3
_PROGRAM_D = 4
_LEFT_STACK = 5
_RIGHT_STACK = 6
_HEADER = 7
_AUX = 8

# Header coordinates live in plane 7. Plane 8 is the field-owned per-program-
# counter observation plane used to admit verified straight-line execution
# blocks without a host-side learned cache.
_H_MAGIC = 0
_H_PROGRAM_LENGTH = 1
_H_PC = 2
_H_ACCUMULATOR = 3
_H_STATUS = 4
_H_REASON = 5
_H_LEFT_HEIGHT = 6
_H_RIGHT_HEIGHT = 7
_H_MAX_STEPS = 8
_H_TRANSITIONS = 9
_H_STACK_READS = 10
_H_STACK_WRITES = 11
_H_FIELD_CELLS_COPIED = 12
_H_COUNT = 13

_RUNNING = 0
_HALTED = 1
_EXHAUSTED = 2
_FAULTED = 3
_STATUS_NAMES = {
    _RUNNING: "running",
    _HALTED: "halted",
    _EXHAUSTED: "exhausted",
    _FAULTED: "faulted",
}

_REASON_NONE = 0
_REASON_HALT = 1
_REASON_STEP_BUDGET = 2
_REASON_STACK_CAPACITY = 3
_REASON_PUSH_ACC_EMPTY = 4
_REASON_INVALID_INSTRUCTION = 5
_REASON_INVALID_STATE = 6
_REASON_NAMES = {
    _REASON_NONE: "none",
    _REASON_HALT: "halt",
    _REASON_STEP_BUDGET: "step_budget",
    _REASON_STACK_CAPACITY: "stack_capacity",
    _REASON_PUSH_ACC_EMPTY: "push_acc_empty",
    _REASON_INVALID_INSTRUCTION: "invalid_instruction",
    _REASON_INVALID_STATE: "invalid_state",
}



class FieldComputerError(ValueError):
    """Raised for an invalid profile, program, state descriptor, or operation."""




def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _exact_integer(
    value: Any,
    name: str,
    *,
    minimum: int | None = 0,
    maximum: int = _SAFE_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise FieldComputerError(f"{name} must be an exact bounded integer")
    if minimum is not None and value < minimum:
        raise FieldComputerError(f"{name} must be an exact bounded integer")
    if value > maximum:
        raise FieldComputerError(f"{name} must be an exact bounded integer")
    return value


def _state_id(value: Any, name: str) -> int:
    return _exact_integer(value, name, minimum=-_SAFE_INTEGER)


def _canonical_symbol(value: Any, name: str, *, allow_empty: bool = False) -> int:
    maximum = EMPTY if allow_empty else 255
    return _exact_integer(value, name, minimum=0, maximum=maximum)


def _canonical_instruction(row: Any, program_length: int, name: str = "instruction") -> tuple[int, int, int, int, int]:
    if isinstance(row, (str, bytes, bytearray)):
        raise FieldComputerError(f"{name} must be a five-word instruction")
    try:
        words = tuple(row)
    except TypeError as exc:
        raise FieldComputerError(f"{name} must be a five-word instruction") from exc
    if len(words) != 5:
        raise FieldComputerError(f"{name} must be a five-word instruction")
    opcode = _exact_integer(words[0], f"{name}.opcode", minimum=HALT, maximum=PROPAGATE)
    a = _exact_integer(words[1], f"{name}.a")
    b = _exact_integer(words[2], f"{name}.b")
    c = _exact_integer(words[3], f"{name}.c")
    d = _exact_integer(words[4], f"{name}.d")
    if opcode == HALT:
        if (a, b, c, d) != (0, 0, 0, 0):
            raise FieldComputerError(f"{name} has nonzero HALT operands")
    elif opcode == PUSH:
        if a not in (0, 1):
            raise FieldComputerError(f"{name} has an invalid stack")
        if b > 255:
            raise FieldComputerError(f"{name} has an invalid symbol")
        if c >= program_length:
            raise FieldComputerError(f"{name} target is outside the program")
        if d != 0:
            raise FieldComputerError(f"{name} has noncanonical operands")
    elif opcode == POP:
        if a not in (0, 1):
            raise FieldComputerError(f"{name} has an invalid stack")
        if b >= program_length:
            raise FieldComputerError(f"{name} target is outside the program")
        if c != 0 or d != 0:
            raise FieldComputerError(f"{name} has noncanonical operands")
    elif opcode == BRANCH:
        if a > EMPTY:
            raise FieldComputerError(f"{name} has an invalid branch symbol")
        if b >= program_length or c >= program_length:
            raise FieldComputerError(f"{name} target is outside the program")
        if d != 0:
            raise FieldComputerError(f"{name} has noncanonical operands")
    elif opcode in (PUSH_ACC, PROPAGATE):
        if a not in (0, 1):
            raise FieldComputerError(f"{name} has an invalid stack")
        if b >= program_length:
            raise FieldComputerError(f"{name} target is outside the program")
        if c != 0 or d != 0:
            raise FieldComputerError(f"{name} has noncanonical operands")
    elif opcode == JUMP:
        if a >= program_length:
            raise FieldComputerError(f"{name} target is outside the program")
        if b != 0 or c != 0 or d != 0:
            raise FieldComputerError(f"{name} has noncanonical operands")
    return (opcode, a, b, c, d)


def _canonical_program(program: Any) -> tuple[tuple[int, int, int, int, int], ...]:
    if isinstance(program, (str, bytes, bytearray)):
        raise FieldComputerError("program must be a finite sequence of instructions")
    try:
        rows = tuple(program)
    except TypeError as exc:
        raise FieldComputerError("program must be a finite sequence of instructions") from exc
    if not rows:
        raise FieldComputerError("program must contain at least one instruction")
    # Targets are validated after the length is known.
    return tuple(
        _canonical_instruction(row, len(rows), f"program[{index}]")
        for index, row in enumerate(rows)
    )


def build_execution_blocks(
    program: Any,
) -> dict[int, tuple[int, ...]]:
    """Derive straight-line blocks whose execution is instruction-equivalent.

    Blocks extend through fall-through PUSH/POP/PUSH_ACC instructions. Branches,
    jumps, halts, PROPAGATE, shared entries, and non-sequential targets end a
    block, so specialization never elides an observable control boundary.
    """

    canonical = _canonical_program(program)
    incoming = [0] * len(canonical)
    for opcode, a, b, c, _ in canonical:
        targets: tuple[int, ...]
        if opcode == PUSH:
            targets = (c,)
        elif opcode in (POP, PUSH_ACC, PROPAGATE):
            targets = (b,)
        elif opcode == BRANCH:
            targets = (b, c)
        elif opcode == JUMP:
            targets = (a,)
        else:
            targets = ()
        for target in targets:
            incoming[target] += 1
    blocks: dict[int, tuple[int, ...]] = {}
    for entry in range(len(canonical)):
        block = [entry]
        current = entry
        while True:
            opcode, _, next_b, next_c, _ = canonical[current]
            if opcode == PUSH:
                successor = next_c
            elif opcode in (POP, PUSH_ACC):
                successor = next_b
            else:
                break
            if successor != current + 1 or successor >= len(canonical):
                break
            if incoming[successor] != 1:
                break
            block.append(successor)
            current = successor
        if len(block) >= 2:
            blocks[entry] = tuple(block)
    return blocks

def _canonical_stack(values: Any, name: str, capacity: int) -> tuple[int, ...]:
    if isinstance(values, (str, bytes, bytearray)):
        raise FieldComputerError(f"{name} must be a finite sequence of byte symbols")
    try:
        result = tuple(values)
    except TypeError as exc:
        raise FieldComputerError(f"{name} must be a finite sequence of byte symbols") from exc
    if len(result) > capacity:
        raise FieldComputerError(f"{name} exceeds stack capacity")
    return tuple(_canonical_symbol(value, f"{name}[{i}]") for i, value in enumerate(result))


def propagation_workspace(
    clauses: Sequence[Sequence[int]],
    *,
    variable_count: int,
    assignment: Sequence[int] = (),
    excitation: Sequence[int] = (),
) -> tuple[int, ...]:
    """Encode data for PROPAGATE; perform no propagation or solver search.

    Variables are one-based signed literals. Assignments use 0 for unknown,
    +1 for true, -1 for false. Clause order is retained as automaton site order;
    duplicate literals are removed. Empty clauses and an empty CNF are valid.
    The uint16 dimensions bound the encoding; the ordinary stack capacity
    bounds execution/storage. The initial excitation vector is optional input,
    not a retained controller or an alternative learned state.
    """

    variables = _exact_integer(variable_count, "variable_count", maximum=65535)
    try:
        rows = []
        for row in clauses:
            literals = set()
            for value in row:
                literal = _exact_integer(value, "literal", minimum=-variables, maximum=variables)
                if literal == 0:
                    raise FieldComputerError("zero is not a literal")
                literals.add(literal)
            rows.append(tuple(sorted(literals, key=lambda value: (abs(value), value < 0))))
        values = tuple(assignment)
        drive = tuple(excitation)
    except TypeError as exc:
        raise FieldComputerError("propagation inputs must be finite sequences") from exc
    if len(rows) > 65535 or any(len(row) > 65535 for row in rows):
        raise FieldComputerError("propagation row dimensions exceed uint16 capacity")
    if not values:
        values = (0,) * variables
    if len(values) != variables:
        raise FieldComputerError("assignment length does not match variable_count")
    encoded_assignment = bytes(
        {0: 0, 1: 1, -1: 2}[_exact_integer(value, "assignment", minimum=-1, maximum=1)]
        for value in values
    )
    controller = ExcitableConstraintController(ExcitableConstraintProfile(
        size=max(1, len(rows)), max_ticks=max(4, 4 * variables),
    ))
    lanes = controller.initial_lanes()
    if drive:
        if len(drive) != len(rows):
            raise FieldComputerError("excitation length does not match clause count")
        lanes[:len(rows)] = [
            _exact_integer(value, "excitation", maximum=controller.profile.scale)
            for value in drive
        ]
    raw = bytearray(_PROPAGATION_HEADER.pack(
        _PROPAGATION_MAGIC, variables, len(rows), 0, 0, 0, 0, 0,
    ))
    raw.extend(encoded_assignment)
    raw.extend(np.asarray([len(row) for row in rows], dtype="<u2").tobytes())
    raw.extend(np.asarray([value for row in rows for value in row], dtype="<i4").tobytes())
    raw.extend(lanes.astype("<f8", copy=False).tobytes())
    raw.extend((len(raw) + 4).to_bytes(4, "little"))
    return tuple(raw)


def _decode_propagation_frame(raw: bytes | bytearray) -> tuple[Any, ...]:
    """Return transient views into a machine frame; retain no state objects."""

    if len(raw) < _PROPAGATION_HEADER.size + 4:
        raise FieldComputerError("propagation frame is truncated")
    if int.from_bytes(raw[-4:], "little") != len(raw):
        raise FieldComputerError("propagation frame length is invalid")
    metadata = _PROPAGATION_HEADER.unpack_from(raw)
    magic, variables, rows, result, selected, calls, row_visits, literal_visits = metadata
    if magic != _PROPAGATION_MAGIC or result not in _PROPAGATION_RESULTS or selected > rows:
        raise FieldComputerError("propagation frame header is invalid")
    for count in (calls, row_visits, literal_visits):
        _exact_integer(count, "propagation counter")
    lengths_start = _PROPAGATION_HEADER.size + variables
    literals_start = lengths_start + 2 * rows
    if literals_start > len(raw) - 4:
        raise FieldComputerError("propagation row table is truncated")
    assignment = np.frombuffer(raw, dtype=np.uint8, count=variables, offset=_PROPAGATION_HEADER.size)
    if np.any(assignment > 2):
        raise FieldComputerError("propagation assignment is invalid")
    lengths = np.frombuffer(raw, dtype="<u2", count=rows, offset=lengths_start)
    literal_count = int(lengths.sum(dtype=np.uint64))
    lanes_start = literals_start + 4 * literal_count
    controller = ExcitableConstraintController(ExcitableConstraintProfile(
        size=max(1, rows), max_ticks=max(4, 4 * variables),
    ))
    if lanes_start + controller.profile.lane_count * 8 + 4 != len(raw):
        raise FieldComputerError("propagation frame dimensions are invalid")
    literals = np.frombuffer(raw, dtype="<i4", count=literal_count, offset=literals_start)
    if np.any(literals == 0) or np.any(literals > variables) or np.any(literals < -variables):
        raise FieldComputerError("propagation literal is outside the variable domain")
    cursor = 0
    for length in lengths:
        previous = (0, False)
        for literal in literals[cursor:cursor + int(length)]:
            key = (abs(int(literal)), literal < 0)
            if key <= previous:
                raise FieldComputerError("propagation literals are not canonical")
            previous = key
        cursor += int(length)
    lanes = np.frombuffer(raw, dtype="<f8", count=controller.profile.lane_count, offset=lanes_start)
    controller.validate_lanes(lanes)
    return metadata, assignment, lengths, literals, lanes, controller


def inspect_propagation_workspace(stack: Sequence[int]) -> dict[str, Any]:
    """Decode the top frame without changing the machine or advancing time."""

    values = _canonical_stack(stack, "propagation stack", _SAFE_INTEGER)
    if len(values) < 4:
        raise FieldComputerError("propagation frame is missing")
    length = int.from_bytes(bytes(values[-4:]), "little")
    if not _PROPAGATION_HEADER.size + 4 <= length <= len(values):
        raise FieldComputerError("propagation frame length is invalid")
    metadata, assignment, lengths, literals, lanes, controller = _decode_propagation_frame(bytes(values[-length:]))
    _, variables, rows, result, selected, calls, row_visits, literal_visits = metadata
    clauses = []
    cursor = 0
    for size in lengths:
        clauses.append(literals[cursor:cursor + int(size)].tolist())
        cursor += int(size)
    sites = controller.profile.size
    return {
        "schema": "cassifi.machine-propagation.v1",
        "variable_count": variables,
        "clauses": clauses,
        "assignment": [{0: 0, 1: 1, 2: -1}[int(value)] for value in assignment],
        "result": _PROPAGATION_RESULTS[result],
        "selected_row": None if selected == 0 else selected - 1,
        "calls": calls,
        "work": {"clause_visits": row_visits, "literal_visits": literal_visits},
        "automaton": {
            **{
                name: lanes[index * sites:(index + 1) * sites].astype(np.int64).tolist()
                for index, name in enumerate(("excitation", "recovery", "trace", "previous"))
            },
            "ticks": int(lanes[4 * sites + 3]),
            "selections": int(lanes[4 * sites + 4]),
        },
    }


def _advance_propagation_frame(
    raw: bytearray, *, include_detail: bool,
) -> tuple[int, int, int, dict[str, Any] | None]:
    """One bounded local operation, never a whole solver or a search loop.

    Each call examines the resident CNF and applies at most one unit deduction.
    Work is linear in frame bytes plus at most four synchronous automaton ticks
    over clause sites. The machine transition count is an instruction count,
    not a claim that this operation costs one scalar arithmetic operation.
    """

    metadata, assignment, lengths, literals, lanes, controller = _decode_propagation_frame(raw)
    _, variables, rows, _, _, calls, row_visits, literal_visits = metadata
    calls = _exact_integer(calls + 1, "propagation calls")
    row_visits = _exact_integer(row_visits + rows, "propagation row visits")
    literal_visits = _exact_integer(literal_visits + len(literals), "propagation literal visits")
    units = [0] * rows
    conflict = False
    all_satisfied = True
    cursor = 0
    for row, length in enumerate(lengths):
        satisfied = False
        unknowns = 0
        unit = 0
        previous = 0
        for value in literals[cursor:cursor + int(length)]:
            literal = int(value)
            known = int(assignment[abs(literal) - 1])
            if literal == -previous or known == (1 if literal > 0 else 2):
                satisfied = True
            if known == 0:
                unknowns += 1
                unit = literal
            previous = literal
        cursor += int(length)
        if not satisfied:
            all_satisfied = False
            if unknowns == 0:
                conflict = True
            elif unknowns == 1:
                units[row] = unit
    selected = 0
    ticks = 0
    if conflict:
        result = PROPAGATION_CONFLICT
    elif any(units):
        ready = [int(value != 0) for value in units]
        decision, event = controller.advance_lanes(
            lanes, positive=ready, negative=[0] * rows, eligible=ready,
        )
        if decision is None or not 1 <= decision <= rows or units[decision - 1] == 0:
            raise FieldComputerError("automaton selected an ineligible propagation row")
        selected = decision
        literal = units[selected - 1]
        assignment[abs(literal) - 1] = 1 if literal > 0 else 2
        ticks = event["work"]["ticks"]
        result = PROPAGATION_PROGRESS
    else:
        result = PROPAGATION_SATISFIED if all_satisfied else PROPAGATION_FIXED_POINT
    _PROPAGATION_HEADER.pack_into(
        raw, 0, _PROPAGATION_MAGIC, variables, rows, result, selected,
        calls, row_visits, literal_visits,
    )
    event = {
        "result": _PROPAGATION_RESULTS[result],
        "selected_row": None if selected == 0 else selected - 1,
        "clause_visits": rows,
        "literal_visits": len(literals),
        "automaton_ticks": ticks,
    } if include_detail else None
    return result, _PROPAGATION_HEADER.size + variables, len(raw) - 4 - lanes.nbytes, event


@dataclass(frozen=True, slots=True)
class ComputerProfile:
    """Fixed geometry and total transition budget for one computer."""

    program_capacity: int = 1024
    stack_capacity: int = 4096
    max_steps: int = 1_000_000

    def __post_init__(self) -> None:
        _exact_integer(self.program_capacity, "program_capacity", minimum=1)
        _exact_integer(self.stack_capacity, "stack_capacity", minimum=1)
        _exact_integer(self.max_steps, "max_steps", minimum=0)
        if self.mode_count * 9 > _SAFE_INTEGER:
            raise FieldComputerError("computer field exceeds exact address capacity")
        # Every immutable transition copy is counted in a float64 exact
        # integer.  Refuse profiles whose declared bound could overflow it.
        if self.field_cells * (1 + 2 * self.max_steps) > _SAFE_INTEGER:
            raise FieldComputerError("computer copy ledger exceeds exact integer capacity")

    @property
    def mode_count(self) -> int:
        return max(self.program_capacity, self.stack_capacity, _H_COUNT)

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, 9 * self.mode_count, 1)

    @property
    def field_cells(self) -> int:
        return 9 * self.mode_count

    @property
    def state_bytes(self) -> int:
        return self.field_cells * np.dtype(np.float64).itemsize

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(
            _canonical({"layout": _LAYOUT, **asdict(self)})
        ).hexdigest()

    @property
    def profile_sha256(self) -> str:
        return self.fingerprint

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ComputerState:
    """An immutable field tensor bound to one :class:`ComputerProfile`."""

    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise FieldComputerError("computer field must be a float64 numpy tensor")
        if (
            not isinstance(self.profile_sha256, str)
            or len(self.profile_sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.profile_sha256)
        ):
            raise FieldComputerError("state profile fingerprint is invalid")
        # A numpy array's WRITEABLE flag can be re-enabled when it owns its
        # allocation.  Backing the stored view with immutable ``bytes`` makes
        # that escape impossible while avoiding a second ndarray allocation.
        raw = self._field.tobytes(order="C")
        field = np.frombuffer(raw, dtype=np.float64).reshape(self._field.shape)
        object.__setattr__(self, "_field", field)

    @property
    def field(self) -> np.ndarray:
        raw = self._field.tobytes(order="C")
        return np.frombuffer(raw, dtype=np.float64).reshape(self._field.shape)


    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)

    @property
    def status(self) -> str:
        if (
            self._field.ndim == 3
            and self._field.shape[0] == 1
            and self._field.shape[2] == 1
            and self._field.shape[1] >= field_regions.HEADER_WORDS
            and int(self._field.reshape(-1)[field_regions.H_MAGIC])
            == field_regions.REGIONAL_MAGIC
        ):
            return field_regions.STATUS_NAMES.get(
                int(self._field.reshape(-1)[field_regions.H_STATUS]), "invalid"
            )
        if (
            self._field.ndim == 3
            and self._field.shape[0] == 1
            and self._field.shape[2] == 1
            and self._field.shape[1] >= 9 * _H_COUNT
            and self._field.shape[1] % 9 == 0
        ):
            parts = self._field.reshape(1, 9, self._field.shape[1] // 9, 1)[0, :, :, 0]
            return _STATUS_NAMES.get(int(parts[_HEADER, _H_STATUS]), "invalid")
        return "invalid"


@dataclass(frozen=True, slots=True)
class CompiledTuringMachine:
    """Canonical instruction stream produced from a finite TM transition table."""

    program: tuple[tuple[int, int, int, int, int], ...]
    entry: int
    state_entries: Mapping[int, int]

    def __post_init__(self) -> None:
        program = _canonical_program(self.program)
        entry = _exact_integer(self.entry, "entry", minimum=0)
        if entry >= len(program):
            raise FieldComputerError("compiled entry is outside the program")
        if not isinstance(self.state_entries, Mapping):
            raise FieldComputerError("state_entries must be a mapping")
        entries: dict[int, int] = {}
        for state, target in self.state_entries.items():
            sid = _state_id(state, "state entry")
            pc = _exact_integer(target, "state entry target", minimum=0)
            if pc >= len(program):
                raise FieldComputerError("state entry target is outside the program")
            entries[sid] = pc
        object.__setattr__(self, "program", program)
        object.__setattr__(self, "entry", entry)
        object.__setattr__(self, "state_entries", MappingProxyType(entries))

    def as_dict(self) -> dict[str, Any]:
        return {
            "program": [list(row) for row in self.program],
            "entry": self.entry,
            "state_entries": {str(state): target for state, target in self.state_entries.items()},
        }


class FieldComputer:
    """Interpreter for canonical five-word instructions in field coordinates."""

    def __init__(self, profile: ComputerProfile):
        if not isinstance(profile, ComputerProfile):
            raise FieldComputerError("ComputerProfile required")
        self.profile: Any = profile
        self._profile_sha256 = profile.fingerprint
        self._regional_catalog = field_regions.EMPTY_KERNEL_CATALOG

    @classmethod
    def regional(
        cls,
        profile: field_regions.RegionalProfile,
        *,
        catalog: field_regions.KernelCatalog = field_regions.EMPTY_KERNEL_CATALOG,
    ) -> FieldComputer:
        """Create the v3 mode of this computer with a fixed kernel catalog."""

        if not isinstance(profile, field_regions.RegionalProfile):
            raise FieldComputerError("RegionalProfile required")
        if not isinstance(catalog, field_regions.KernelCatalog):
            raise FieldComputerError("KernelCatalog required")
        if profile.kernel_names != catalog.names:
            raise FieldComputerError("regional profile/catalog mismatch")
        machine = cls.__new__(cls)
        machine.profile = profile
        machine._profile_sha256 = profile.fingerprint
        machine._regional_catalog = catalog
        return machine

    @property
    def is_regional(self) -> bool:
        return isinstance(self.profile, field_regions.RegionalProfile)

    def _parts(self, state: ComputerState, *, validate: bool = True) -> np.ndarray:
        if not isinstance(state, ComputerState):
            raise FieldComputerError("ComputerState required")
        if validate:
            self.validate(state)
        return state._field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]

    def _field_state(
        self, field: np.ndarray, *, validate: bool = True
    ) -> ComputerState:
        state = ComputerState(field.reshape(self.profile.shape), self._profile_sha256)
        if validate:
            self.validate(state)
        return state

    def initial(
        self,
        program: Any,
        *,
        left: Any = (),
        right: Any = (),
        entry: int = 0,
        values: Mapping[str, Any] | None = None,
        value_capacities: Mapping[str, int] | None = None,
    ) -> ComputerState:
        if self.is_regional:
            if values is not None and not isinstance(values, Mapping):
                raise FieldComputerError("regional values must be a mapping")
            initial_values = dict(values or {})
            if left:
                initial_values["left"] = list(left)
            if right:
                initial_values["right"] = list(right)
            if value_capacities is not None and not isinstance(
                value_capacities, Mapping
            ):
                raise FieldComputerError(
                    "regional value capacities must be a mapping"
                )
            try:
                field = field_regions.initial_field(
                    self.profile,
                    program,
                    values=initial_values,
                    value_capacities=value_capacities,
                    catalog=self._regional_catalog,
                    entry=entry,
                )
                state = ComputerState(field, self._profile_sha256)
                self.validate(state)
                return state
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        canonical = _canonical_program(program)
        if len(canonical) > self.profile.program_capacity:
            raise FieldComputerError("program exceeds profile capacity")
        entry = _exact_integer(entry, "entry", minimum=0)
        if entry >= len(canonical):
            raise FieldComputerError("entry is outside the program")
        left_values = _canonical_stack(left, "left", self.profile.stack_capacity)
        right_values = _canonical_stack(right, "right", self.profile.stack_capacity)
        field = np.zeros(self.profile.shape, dtype=np.float64)
        parts = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        if canonical:
            rows = np.asarray(canonical, dtype=np.float64)
            parts[_PROGRAM_OPCODE, : len(canonical)] = rows[:, 0]
            parts[_PROGRAM_A, : len(canonical)] = rows[:, 1]
            parts[_PROGRAM_B, : len(canonical)] = rows[:, 2]
            parts[_PROGRAM_C, : len(canonical)] = rows[:, 3]
            parts[_PROGRAM_D, : len(canonical)] = rows[:, 4]
        if left_values:
            parts[_LEFT_STACK, : len(left_values)] = left_values
        if right_values:
            parts[_RIGHT_STACK, : len(right_values)] = right_values
        parts[_HEADER, _H_MAGIC] = _MAGIC
        parts[_HEADER, _H_PROGRAM_LENGTH] = len(canonical)
        parts[_HEADER, _H_PC] = entry
        parts[_HEADER, _H_ACCUMULATOR] = EMPTY
        parts[_HEADER, _H_LEFT_HEIGHT] = len(left_values)
        parts[_HEADER, _H_RIGHT_HEIGHT] = len(right_values)
        parts[_HEADER, _H_MAX_STEPS] = self.profile.max_steps
        # Initial construction seals one full field tensor behind immutable
        # bytes; account that copy in the persistent ledger.
        parts[_HEADER, _H_FIELD_CELLS_COPIED] = field.size
        status = _HALTED if canonical[entry][0] == HALT else _RUNNING
        reason = _REASON_HALT if status == _HALTED else _REASON_NONE
        if status == _RUNNING and self.profile.max_steps == 0:
            status = _EXHAUSTED
            reason = _REASON_STEP_BUDGET
        parts[_HEADER, _H_STATUS] = status
        parts[_HEADER, _H_REASON] = reason
        state = ComputerState(field, self._profile_sha256)
        self.validate(state)
        return state

    def validate(self, state: ComputerState) -> None:
        if not isinstance(state, ComputerState):
            raise FieldComputerError("ComputerState required")
        if state.profile_sha256 != self._profile_sha256:
            raise FieldComputerError("state belongs to a different computer profile")
        if self.is_regional:
            try:
                field_regions.validate_field(
                    state._field, self.profile, self._regional_catalog
                )
                return
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        field = state._field
        if field.shape != self.profile.shape or field.dtype != np.float64 or not field.flags.c_contiguous:
            raise FieldComputerError("computer field shape or dtype is invalid")
        if not np.isfinite(field).all():
            raise FieldComputerError("computer field contains nonfinite values")
        if not np.equal(field, np.floor(field)).all():
            raise FieldComputerError("computer field contains nonintegral values")
        parts = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        header = parts[_HEADER]
        if int(header[_H_MAGIC]) != _MAGIC:
            raise FieldComputerError("computer field magic is invalid")
        program_length = int(header[_H_PROGRAM_LENGTH])
        if not 1 <= program_length <= self.profile.program_capacity:
            raise FieldComputerError("program length is invalid")
        pc = int(header[_H_PC])
        if not 0 <= pc < program_length:
            raise FieldComputerError("program counter is invalid")
        accumulator = int(header[_H_ACCUMULATOR])
        if not 0 <= accumulator <= EMPTY:
            raise FieldComputerError("accumulator is invalid")
        status = int(header[_H_STATUS])
        reason = int(header[_H_REASON])
        if status not in _STATUS_NAMES or reason not in _REASON_NAMES:
            raise FieldComputerError("computer status or reason is invalid")
        left_height = int(header[_H_LEFT_HEIGHT])
        right_height = int(header[_H_RIGHT_HEIGHT])
        if not 0 <= left_height <= self.profile.stack_capacity:
            raise FieldComputerError("left stack height is invalid")
        if not 0 <= right_height <= self.profile.stack_capacity:
            raise FieldComputerError("right stack height is invalid")
        if int(header[_H_MAX_STEPS]) != self.profile.max_steps:
            raise FieldComputerError("state budget does not match computer profile")
        transitions = int(header[_H_TRANSITIONS])
        if not 0 <= transitions <= self.profile.max_steps:
            raise FieldComputerError("transition ledger is invalid")
        for coordinate in (_H_STACK_READS, _H_STACK_WRITES, _H_FIELD_CELLS_COPIED):
            if int(header[coordinate]) < 0 or int(header[coordinate]) > _SAFE_INTEGER:
                raise FieldComputerError("resource ledger is invalid")
        for plane in range(5):
            if np.any(parts[plane, program_length:] != 0):
                raise FieldComputerError("program padding is noncanonical")
        if np.any(parts[_LEFT_STACK, left_height:] != 0) or np.any(parts[_RIGHT_STACK, right_height:] != 0):
            raise FieldComputerError("stack padding is noncanonical")
        if left_height and np.any((parts[_LEFT_STACK, :left_height] < 0) | (parts[_LEFT_STACK, :left_height] > 255)):
            raise FieldComputerError("left stack contains an invalid symbol")
        if right_height and np.any((parts[_RIGHT_STACK, :right_height] < 0) | (parts[_RIGHT_STACK, :right_height] > 255)):
            raise FieldComputerError("right stack contains an invalid symbol")
        if np.any(parts[_HEADER, _H_COUNT:] != 0):
            raise FieldComputerError("metadata padding is noncanonical")
        heat = parts[_AUX]
        if (
            np.any(heat[:program_length] < 0)
            or np.any(heat[:program_length] > _HEAT_LIMIT)
            or np.any(heat[program_length:] != 0)
        ):
            raise FieldComputerError("execution-learning plane is noncanonical")
        program = tuple(
            tuple(int(parts[plane, index]) for plane in range(5))
            for index in range(program_length)
        )
        for index, instruction in enumerate(program):
            _canonical_instruction(instruction, program_length, f"program[{index}]")
        opcode = program[pc][0]
        if status == _RUNNING:
            if reason != _REASON_NONE or transitions >= self.profile.max_steps:
                raise FieldComputerError("running state has an exhausted budget or reason")
        elif status == _HALTED:
            if reason != _REASON_HALT or opcode != HALT:
                raise FieldComputerError("halted state is not at a canonical HALT")
        elif status == _EXHAUSTED:
            if reason == _REASON_STEP_BUDGET and transitions < self.profile.max_steps:
                raise FieldComputerError("step-budget exhaustion is premature")
            if reason not in (_REASON_STEP_BUDGET, _REASON_STACK_CAPACITY):
                raise FieldComputerError("exhausted state has a fault reason")
        elif status == _FAULTED:
            if reason not in (_REASON_PUSH_ACC_EMPTY, _REASON_INVALID_INSTRUCTION, _REASON_INVALID_STATE):
                raise FieldComputerError("faulted state has a nonfault reason")

    def status(self, state: ComputerState) -> str:
        return self.inspect(state)["status"]

    def _state_digest(self, state: ComputerState) -> str:
        if self.is_regional:
            return field_regions.state_sha256(state._field, self.profile)
        digest = hashlib.sha256(
            _canonical(
                {
                    "layout": _LAYOUT,
                    "profile_sha256": self._profile_sha256,
                    "shape": self.profile.shape,
                }
            )
        )
        digest.update(state._field.tobytes(order="C"))
        return digest.hexdigest()

    def _apply_instruction(
        self,
        parts: np.ndarray,
        detail: dict[str, Any] | None = None,
    ) -> bool:
        """Apply one instruction and optionally populate a public event."""

        header = parts[_HEADER]
        if int(header[_H_STATUS]) != _RUNNING:
            raise FieldComputerError("internal transition requires a running state")
        pc = int(header[_H_PC])
        opcode, a, b, c, _ = (
            int(parts[plane, pc]) for plane in range(5)
        )
        transitions_before = int(header[_H_TRANSITIONS])
        left_height = int(header[_H_LEFT_HEIGHT])
        right_height = int(header[_H_RIGHT_HEIGHT])
        stack_read = False
        stack_write = False
        kind = "instruction"
        fault = False
        exhausted = False
        next_pc = pc
        # This is the stable logical public-successor charge. Batched run()
        # avoids the physical copies but preserves state/counter equivalence.
        copied = int(header[_H_FIELD_CELLS_COPIED]) + 2 * self.profile.field_cells
        if copied > _SAFE_INTEGER:
            raise FieldComputerError("computer copy ledger overflow")
        header[_H_FIELD_CELLS_COPIED] = copied
        if opcode == HALT:
            header[_H_STATUS] = _HALTED
            header[_H_REASON] = _REASON_HALT
            kind = "halt"
        elif opcode == PUSH:
            height_coordinate = _H_LEFT_HEIGHT if a == 0 else _H_RIGHT_HEIGHT
            height = left_height if a == 0 else right_height
            if height >= self.profile.stack_capacity:
                header[_H_STATUS] = _EXHAUSTED
                header[_H_REASON] = _REASON_STACK_CAPACITY
                exhausted = True
                kind = "exhausted"
            else:
                plane = _LEFT_STACK if a == 0 else _RIGHT_STACK
                parts[plane, height] = b
                header[height_coordinate] = height + 1
                header[_H_STACK_WRITES] = int(header[_H_STACK_WRITES]) + 1
                stack_write = True
                next_pc = c
        elif opcode == POP:
            height_coordinate = _H_LEFT_HEIGHT if a == 0 else _H_RIGHT_HEIGHT
            height = left_height if a == 0 else right_height
            plane = _LEFT_STACK if a == 0 else _RIGHT_STACK
            if height == 0:
                header[_H_ACCUMULATOR] = EMPTY
            else:
                value = int(parts[plane, height - 1])
                parts[plane, height - 1] = 0
                header[_H_ACCUMULATOR] = value
                header[height_coordinate] = height - 1
            header[_H_STACK_READS] = int(header[_H_STACK_READS]) + 1
            stack_read = True
            next_pc = b
        elif opcode == BRANCH:
            next_pc = b if int(header[_H_ACCUMULATOR]) == a else c
        elif opcode == PUSH_ACC:
            accumulator = int(header[_H_ACCUMULATOR])
            if accumulator == EMPTY:
                header[_H_STATUS] = _FAULTED
                header[_H_REASON] = _REASON_PUSH_ACC_EMPTY
                fault = True
                kind = "fault"
            else:
                height_coordinate = _H_LEFT_HEIGHT if a == 0 else _H_RIGHT_HEIGHT
                height = left_height if a == 0 else right_height
                if height >= self.profile.stack_capacity:
                    header[_H_STATUS] = _EXHAUSTED
                    header[_H_REASON] = _REASON_STACK_CAPACITY
                    exhausted = True
                    kind = "exhausted"
                else:
                    plane = _LEFT_STACK if a == 0 else _RIGHT_STACK
                    parts[plane, height] = accumulator
                    header[height_coordinate] = height + 1
                    header[_H_STACK_WRITES] = int(header[_H_STACK_WRITES]) + 1
                    stack_write = True
                    next_pc = b
        elif opcode == PROPAGATE:
            plane = _LEFT_STACK if a == 0 else _RIGHT_STACK
            height = left_height if a == 0 else right_height
            try:
                if height < 4:
                    raise FieldComputerError("propagation frame is missing")
                length = int.from_bytes(bytes(int(value) for value in parts[plane, height - 4:height]), "little")
                if not _PROPAGATION_HEADER.size + 4 <= length <= height:
                    raise FieldComputerError("propagation frame length is invalid")
                start = height - length
                raw = bytearray(int(value) for value in parts[plane, start:height])
                result, prefix_end, lanes_start, propagation = _advance_propagation_frame(
                    raw, include_detail=detail is not None,
                )
                reads = _exact_integer(
                    int(header[_H_STACK_READS]) + length + 4, "computer stack reads",
                )
                writes = _exact_integer(
                    int(header[_H_STACK_WRITES]) + prefix_end + length - 4 - lanes_start,
                    "computer stack writes",
                )
                # Commit only mutable regions after the entire operation has
                # succeeded. A malformed frame leaves both stacks and ACC intact.
                updated = np.frombuffer(raw, dtype=np.uint8)
                parts[plane, start:start + prefix_end] = updated[:prefix_end]
                parts[plane, start + lanes_start:height - 4] = updated[lanes_start:-4]
                header[_H_STACK_READS] = reads
                header[_H_STACK_WRITES] = writes
                header[_H_ACCUMULATOR] = result
                stack_read = True
                stack_write = True
                next_pc = b
                kind = "propagation"
                if detail is not None:
                    detail["propagation"] = propagation
            except (ValueError, OverflowError):
                header[_H_STATUS] = _FAULTED
                header[_H_REASON] = _REASON_INVALID_STATE
                fault = True
                kind = "fault"
        elif opcode == JUMP:
            next_pc = a
        else:
            header[_H_STATUS] = _FAULTED
            header[_H_REASON] = _REASON_INVALID_INSTRUCTION
            fault = True
            kind = "fault"
        attempted = not exhausted
        if attempted:
            header[_H_TRANSITIONS] = transitions_before + 1
            header[_H_PC] = next_pc
            if int(parts[_AUX, pc]) >= _HEAT_LIMIT:
                parts[_AUX, pc] = int(parts[_AUX, pc]) // 2
            parts[_AUX, pc] = int(parts[_AUX, pc]) + 1
            if not fault and kind != "halt":
                if int(header[_H_TRANSITIONS]) >= self.profile.max_steps:
                    header[_H_STATUS] = _EXHAUSTED
                    header[_H_REASON] = _REASON_STEP_BUDGET
                else:
                    header[_H_STATUS] = _RUNNING
                    header[_H_REASON] = _REASON_NONE
        if detail is not None:
            detail.update(
                {
                    "kind": kind,
                    "opcode": opcode,
                    "pc_before": pc,
                    "pc_after": int(header[_H_PC]),
                    "status": _STATUS_NAMES[
                        int(header[_H_STATUS])
                    ],
                    "reason": _REASON_NAMES[
                        int(header[_H_REASON])
                    ],
                    "transition_attempted": attempted,
                    "stack_read": stack_read,
                    "stack_write": stack_write,
                }
            )
        return attempted

    def step(self, state: ComputerState) -> tuple[ComputerState, dict[str, Any]]:
        if self.is_regional:
            self.validate(state)
            try:
                field, receipt = field_regions.step_field(
                    state._field, self.profile, self._regional_catalog
                )
                successor = (
                    state
                    if field is state._field
                    else ComputerState(field, self._profile_sha256)
                )
                return successor, receipt
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        self.validate(state)
        before_digest = self._state_digest(state)
        parts = self._parts(state, validate=False)
        header = parts[_HEADER]
        if int(header[_H_STATUS]) != _RUNNING:
            status_name = _STATUS_NAMES[int(header[_H_STATUS])]
            return state, {
                "schema": SCHEMA,
                "kind": "noop",
                "status": status_name,
                "reason": _REASON_NAMES[int(header[_H_REASON])],
                "pc": int(header[_H_PC]),
                "state_unchanged": True,
                "previous_state_sha256": before_digest,
                "state_sha256": before_digest,
                "physical_copy_work": {
                    "working_copy_cells": 0,
                    "sealed_copy_cells": 0,
                },
            }
        field = np.array(state._field, dtype=np.float64, copy=True, order="C")
        mutable = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        detail: dict[str, Any] = {}
        self._apply_instruction(mutable, detail)
        successor = self._field_state(field)
        return successor, {
            "schema": SCHEMA,
            **detail,
            "state_unchanged": False,
            "previous_state_sha256": before_digest,
            "state_sha256": self._state_digest(successor),
            "physical_copy_work": {
                "working_copy_cells": self.profile.field_cells,
                "sealed_copy_cells": self.profile.field_cells,
            },
        }

    def run(
        self,
        state: ComputerState,
        *,
        steps: int | None = None,
        use_blocks: bool = True,
    ) -> tuple[ComputerState, dict[str, Any]]:
        """Run in one private buffer and seal one immutable successor.

        Every primitive transition is identical to :meth:`step`, including
        heat and logical ledger updates. ``use_blocks`` only groups already-hot
        straight-line dispatch; it cannot cross a branch, halt, fault,
        capacity refusal, requested pause, or declared transition ceiling.
        """
        if self.is_regional:
            self.validate(state)
            try:
                field, receipt = field_regions.run_field(
                    state._field,
                    self.profile,
                    self._regional_catalog,
                    steps=steps,
                )
                successor = (
                    state
                    if field is state._field
                    else ComputerState(field, self._profile_sha256)
                )
                return successor, receipt
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc

        self.validate(state)
        if steps is not None:
            steps = _exact_integer(steps, "steps", minimum=0)
        if not isinstance(use_blocks, bool):
            raise FieldComputerError("use_blocks must be boolean")
        initial_digest = self._state_digest(state)
        initial_parts = self._parts(state, validate=False)
        initially_running = int(initial_parts[_HEADER, _H_STATUS]) == _RUNNING
        if not initially_running or steps == 0:
            final = self.inspect(state)
            return state, {
                "schema": SCHEMA,
                "initial_state_sha256": initial_digest,
                "state_sha256": initial_digest,
                "status": final["status"],
                "reason": final["reason"],
                "paused": bool(initially_running and steps == 0),
                "transitions_executed": 0,
                "resource_ledger": final["resource_ledger"],
                "field_bytes": state.nbytes,
                "physical_copy_work": {
                    "working_copy_cells": 0,
                    "sealed_copy_cells": 0,
                },
                "specialization": {
                    "enabled": use_blocks,
                    "hot_threshold": _BLOCK_HOT_THRESHOLD,
                    "block_invocations": 0,
                    "block_transitions": 0,
                    "derived_blocks": 0,
                    "derivation_deferred": bool(use_blocks),
                },
            }
        field = np.array(state._field, dtype=np.float64, copy=True, order="C")
        parts = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        blocks: dict[int, tuple[int, ...]] | None = None
        executed = 0
        paused = False
        block_invocations = 0
        block_transitions = 0
        while int(parts[_HEADER, _H_STATUS]) == _RUNNING:
            if steps is not None and executed >= steps:
                paused = True
                break
            pc = int(parts[_HEADER, _H_PC])
            block: tuple[int, ...] | None = None
            if (
                use_blocks
                and int(parts[_AUX, pc]) >= _BLOCK_HOT_THRESHOLD
            ):
                if blocks is None:
                    program_length = int(
                        parts[_HEADER, _H_PROGRAM_LENGTH]
                    )
                    program = tuple(
                        tuple(
                            int(parts[plane, index])
                            for plane in range(5)
                        )
                        for index in range(program_length)
                    )
                    blocks = build_execution_blocks(program)
                block = blocks.get(pc)
            hot = block is not None
            planned = block if block is not None else (pc,)
            applied = 0
            for expected_pc in planned:
                if int(parts[_HEADER, _H_STATUS]) != _RUNNING:
                    break
                if steps is not None and executed >= steps:
                    paused = True
                    break
                if int(parts[_HEADER, _H_PC]) != expected_pc:
                    break
                attempted = self._apply_instruction(parts)
                if attempted:
                    executed += 1
                    applied += 1
                if int(parts[_HEADER, _H_STATUS]) != _RUNNING:
                    break
            if hot and applied >= 2:
                block_invocations += 1
                block_transitions += applied
            if int(parts[_HEADER, _H_STATUS]) == _EXHAUSTED:
                break
        successor = self._field_state(field)
        final = self.inspect(successor)
        return successor, {
            "schema": SCHEMA,
            "initial_state_sha256": initial_digest,
            "state_sha256": self._state_digest(successor),
            "status": final["status"],
            "reason": final["reason"],
            "paused": paused,
            "transitions_executed": executed,
            "resource_ledger": final["resource_ledger"],
            "field_bytes": successor.nbytes,
            "physical_copy_work": {
                "working_copy_cells": self.profile.field_cells,
                "sealed_copy_cells": self.profile.field_cells,
            },
            "specialization": {
                "enabled": use_blocks,
                "hot_threshold": _BLOCK_HOT_THRESHOLD,
                "derived_blocks": 0 if blocks is None else len(blocks),
                "derivation_deferred": bool(
                    use_blocks and blocks is None
                ),
                "block_invocations": block_invocations,
                "block_transitions": block_transitions,
            },
        }

    def inspect(self, state: ComputerState) -> dict[str, Any]:
        if self.is_regional:
            try:
                return field_regions.inspect_field(
                    state._field, self.profile, self._regional_catalog
                )
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        parts = self._parts(state)
        header = parts[_HEADER]
        program_length = int(header[_H_PROGRAM_LENGTH])
        left_height = int(header[_H_LEFT_HEIGHT])
        right_height = int(header[_H_RIGHT_HEIGHT])
        heat = [int(value) for value in parts[_AUX, :program_length]]
        return {
            "schema": SCHEMA,
            "status": _STATUS_NAMES[int(header[_H_STATUS])],
            "pc": int(header[_H_PC]),
            "accumulator": int(header[_H_ACCUMULATOR]),
            "left": [int(value) for value in parts[_LEFT_STACK, :left_height]],
            "right": [int(value) for value in parts[_RIGHT_STACK, :right_height]],
            "reason": _REASON_NAMES[int(header[_H_REASON])],
            "program_length": program_length,
            "max_steps": int(header[_H_MAX_STEPS]),
            "profile_sha256": self._profile_sha256,
            "resource_ledger": {
                "transitions": int(header[_H_TRANSITIONS]),
                "stack_reads": int(header[_H_STACK_READS]),
                "stack_writes": int(header[_H_STACK_WRITES]),
                "field_cells_copied": int(header[_H_FIELD_CELLS_COPIED]),
            },
            "execution_learning": {
                "hot_threshold": _BLOCK_HOT_THRESHOLD,
                "observation_limit": _HEAT_LIMIT,
                "pc_observations": heat,
                "hot_pcs": [
                    index for index, count in enumerate(heat)
                    if count >= _BLOCK_HOT_THRESHOLD
                ],
            },
            "field_bytes": state.nbytes,
        }
    def restart(
        self,
        state: ComputerState,
        *,
        left: Any = (),
        right: Any = (),
        entry: int = 0,
        values: Mapping[str, Any] | None = None,
    ) -> tuple[ComputerState, dict[str, Any]]:
        if self.is_regional:
            replacements: dict[str, Any] = dict(values or {})
            if left != ():
                replacements["left"] = left
            if right != ():
                replacements["right"] = right
            try:
                field, receipt = field_regions.restart_field(
                    state._field,
                    self.profile,
                    self._regional_catalog,
                    entry=entry,
                    values=replacements,
                )
                return ComputerState(field, self._profile_sha256), receipt
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        """Start the retained program again while preserving field-owned heat."""
        if values is not None:
            raise FieldComputerError(
                "named restart values require a regional computer"
            )

        self.validate(state)
        old_parts = self._parts(state, validate=False)
        program_length = int(old_parts[_HEADER, _H_PROGRAM_LENGTH])
        entry = _exact_integer(entry, "entry", minimum=0)
        if entry >= program_length:
            raise FieldComputerError("entry is outside the program")
        left_values = _canonical_stack(left, "left", self.profile.stack_capacity)
        right_values = _canonical_stack(right, "right", self.profile.stack_capacity)
        field = np.array(state._field, dtype=np.float64, copy=True, order="C")
        parts = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        parts[_LEFT_STACK, :] = 0
        parts[_RIGHT_STACK, :] = 0
        parts[_HEADER, :] = 0
        if left_values:
            parts[_LEFT_STACK, : len(left_values)] = left_values
        if right_values:
            parts[_RIGHT_STACK, : len(right_values)] = right_values
        header = parts[_HEADER]
        header[_H_MAGIC] = _MAGIC
        header[_H_PROGRAM_LENGTH] = program_length
        header[_H_PC] = entry
        header[_H_ACCUMULATOR] = EMPTY
        header[_H_LEFT_HEIGHT] = len(left_values)
        header[_H_RIGHT_HEIGHT] = len(right_values)
        header[_H_MAX_STEPS] = self.profile.max_steps
        header[_H_FIELD_CELLS_COPIED] = self.profile.field_cells
        status = _HALTED if int(parts[_PROGRAM_OPCODE, entry]) == HALT else _RUNNING
        reason = _REASON_HALT if status == _HALTED else _REASON_NONE
        if status == _RUNNING and self.profile.max_steps == 0:
            status = _EXHAUSTED
            reason = _REASON_STEP_BUDGET
        header[_H_STATUS] = status
        header[_H_REASON] = reason
        successor = self._field_state(field)
        return successor, {
            "schema": SCHEMA,
            "kind": "restart",
            "previous_state_sha256": self._state_digest(state),
            "state_sha256": self._state_digest(successor),
            "retained_execution_observations": sum(
                int(value) for value in parts[_AUX, :program_length]
            ),
            "physical_copy_work": {
                "working_copy_cells": self.profile.field_cells,
                "sealed_copy_cells": self.profile.field_cells,
            },
        }

    def _descriptor_schema(self, state: ComputerState) -> str:
        # The byte layout and old instruction meanings are unchanged. Preserve
        # v1 descriptors verbatim so enclosing atlas checkpoint hashes survive.
        parts = self._parts(state, validate=False)
        length = int(parts[_HEADER, _H_PROGRAM_LENGTH])
        return SCHEMA if np.any(parts[_PROGRAM_OPCODE, :length] == PROPAGATE) else _PREVIOUS_SCHEMA

    def descriptor(self, state: ComputerState) -> dict[str, Any]:
        if self.is_regional:
            try:
                return field_regions.descriptor(
                    state._field, self.profile, self._regional_catalog
                )
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        self.validate(state)
        return {
            "schema": self._descriptor_schema(state),
            "layout": _LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": self._profile_sha256,
            "field_b64": base64.b64encode(state._field.tobytes(order="C")).decode("ascii"),
            "state_sha256": self.state_sha256(state),
        }

    @classmethod
    def from_descriptor(
        cls,
        value: Mapping[str, Any],
        *,
        catalog: field_regions.KernelCatalog = field_regions.EMPTY_KERNEL_CATALOG,
    ) -> tuple[FieldComputer, ComputerState]:
        if (
            isinstance(value, Mapping)
            and value.get("schema") == field_regions.REGIONAL_SCHEMA
        ):
            try:
                profile, field = field_regions.from_descriptor(value, catalog)
                machine = cls.regional(profile, catalog=catalog)
                state = ComputerState(field, profile.fingerprint)
                machine.validate(state)
                return machine, state
            except field_regions.RegionalFieldError as exc:
                raise FieldComputerError(str(exc)) from exc
        required = {
            "schema",
            "layout",
            "profile",
            "profile_sha256",
            "field_b64",
            "state_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise FieldComputerError("invalid computer descriptor keys")
        if value["schema"] not in (SCHEMA, _PREVIOUS_SCHEMA) or value["layout"] != _LAYOUT:
            raise FieldComputerError("unsupported computer descriptor")
        if not isinstance(value["profile"], Mapping):
            raise FieldComputerError("descriptor profile is invalid")
        try:
            profile = ComputerProfile(**dict(value["profile"]))
        except (TypeError, FieldComputerError) as exc:
            raise FieldComputerError("descriptor profile is invalid") from exc
        machine = cls(profile)
        if value["profile_sha256"] != profile.fingerprint:
            raise FieldComputerError("descriptor profile digest mismatch")
        encoded = value["field_b64"]
        if not isinstance(encoded, str):
            raise FieldComputerError("descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            if base64.b64encode(raw).decode("ascii") != encoded:
                raise ValueError("noncanonical base64")
            if len(raw) != profile.state_bytes:
                raise ValueError("field byte length mismatch")
            field = np.frombuffer(raw, dtype=np.float64).reshape(profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise FieldComputerError("descriptor field encoding is invalid") from exc
        state = ComputerState(field, profile.fingerprint)
        machine.validate(state)
        if value["schema"] != machine._descriptor_schema(state):
            raise FieldComputerError("descriptor instruction-set version mismatch")
        if value["state_sha256"] != machine.state_sha256(state):
            raise FieldComputerError("descriptor state digest mismatch")
        return machine, state

    def write_named_value(
        self,
        state: ComputerState,
        name: str,
        value: Any,
    ) -> tuple[ComputerState, dict[str, Any]]:
        """Publish one declared regional input as a field transition."""

        if not self.is_regional:
            raise FieldComputerError("named values require a regional computer")
        successor, receipt = field_regions.write_named_value(
            state._field,
            self.profile,
            self._regional_catalog,
            name,
            value,
        )
        return ComputerState(successor, self.profile.fingerprint), receipt

    def state_sha256(self, state: ComputerState) -> str:
        self.validate(state)
        return self._state_digest(state)
    def object_value(self, state: ComputerState, object_id: int) -> Any:
        """Read one v3 object through the protected registry."""

        if not self.is_regional:
            raise FieldComputerError("object_value requires a regional computer")
        try:
            return field_regions.object_value(
                state._field, self.profile, self._regional_catalog, object_id
            )
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc

    def named_value(self, state: ComputerState, name: str) -> Any:
        """Read one named v3 value without creating parallel persistent state."""

        if not self.is_regional:
            raise FieldComputerError("named_value requires a regional computer")
        try:
            return field_regions.named_values(
                state._field,
                self.profile,
                self._regional_catalog,
                (name,),
            )[name]
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc

    def named_values(
        self, state: ComputerState, names: Sequence[str]
    ) -> Mapping[str, Any]:
        """Read several named values from one validated regional image."""

        if not self.is_regional:
            raise FieldComputerError("named_values require a regional computer")
        try:
            return field_regions.named_values(
                state._field,
                self.profile,
                self._regional_catalog,
                names,
            )
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc

    def intervene_automaton(
        self, state: ComputerState, *, site: int, excitation: int
    ) -> tuple[ComputerState, dict[str, Any]]:
        """Apply a scheduler-lane intervention as a visible field transition."""

        if not self.is_regional:
            raise FieldComputerError(
                "intervene_automaton requires a regional computer"
            )
        try:

            field, receipt = field_regions.intervene_automaton(
                state._field,
                self.profile,
                self._regional_catalog,
                site=site,
                excitation=excitation,
            )
            return ComputerState(field, self._profile_sha256), receipt
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc
    def enqueue_event(
        self,
        state: ComputerState,
        event: Mapping[str, Any],
    ) -> tuple[ComputerState, dict[str, Any]]:
        """Admit external work into the v3 field-owned event queue."""

        if not self.is_regional:
            raise FieldComputerError("enqueue_event requires a regional computer")
        try:
            field, receipt = field_regions.enqueue_event(
                state._field,
                self.profile,
                self._regional_catalog,
                event,
            )
            return ComputerState(field, self._profile_sha256), receipt
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc


    def grow(
        self,
        state: ComputerState,
        *,
        mode_count: int,
        max_steps: int | None = None,
    ) -> tuple[FieldComputer, ComputerState, dict[str, Any]]:
        """Grow v3 storage or transition capacity through one explicit event."""

        if not self.is_regional:
            raise FieldComputerError("grow requires a regional computer")
        try:
            profile, field, receipt = field_regions.grow_field(
                state._field,
                self.profile,
                self._regional_catalog,
                mode_count=mode_count,
                max_steps=max_steps,
            )
            machine = FieldComputer.regional(
                profile, catalog=self._regional_catalog
            )
            return machine, ComputerState(field, profile.fingerprint), receipt
        except field_regions.RegionalFieldError as exc:
            raise FieldComputerError(str(exc)) from exc


    def resize(
        self,
        state: ComputerState,
        *,
        stack_capacity: int,
        max_steps: int | None = None,
    ) -> tuple[FieldComputer, ComputerState]:
        self.validate(state)
        stack_capacity = _exact_integer(
            stack_capacity, "stack_capacity", minimum=1
        )
        if self.is_regional:
            machine, successor, _receipt = self.grow(
                state,
                mode_count=stack_capacity,
                max_steps=max_steps,
            )
            return machine, successor
        if stack_capacity < self.profile.stack_capacity:
            raise FieldComputerError("stack_capacity must grow monotonically")
        if max_steps is None:
            new_max_steps = self.profile.max_steps
        else:
            new_max_steps = _exact_integer(max_steps, "max_steps", minimum=0)
            if new_max_steps < self.profile.max_steps:
                raise FieldComputerError("max_steps must grow monotonically")
        if stack_capacity == self.profile.stack_capacity and new_max_steps == self.profile.max_steps:
            raise FieldComputerError("resize must increase at least one bound")
        profile = ComputerProfile(
            program_capacity=self.profile.program_capacity,
            stack_capacity=stack_capacity,
            max_steps=new_max_steps,
        )
        old_parts = state._field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        field = np.zeros(profile.shape, dtype=np.float64)
        new_parts = field.reshape(1, 9, profile.mode_count, 1)[0, :, :, 0]
        new_parts[:, : self.profile.mode_count] = old_parts
        header = new_parts[_HEADER]
        # Resizing copies the old tensor into the expanded allocation and
        # then seals the new tensor behind immutable bytes.
        header[_H_FIELD_CELLS_COPIED] = (
            int(header[_H_FIELD_CELLS_COPIED])
            + state._field.size
            + field.size
        )
        header[_H_MAX_STEPS] = new_max_steps
        status = int(header[_H_STATUS])
        reason = int(header[_H_REASON])
        if status == _EXHAUSTED:
            resumable = (
                reason == _REASON_STEP_BUDGET and new_max_steps > self.profile.max_steps
            ) or (
                reason == _REASON_STACK_CAPACITY
                and stack_capacity > self.profile.stack_capacity
            )
            if resumable:
                header[_H_STATUS] = _RUNNING
                header[_H_REASON] = _REASON_NONE
        successor = ComputerState(field, profile.fingerprint)
        machine = FieldComputer(profile)
        machine.validate(successor)
        return machine, successor


# -- Turing-machine compiler -------------------------------------------------


def compile_turing_machine(
    transitions: Mapping[Any, Any],
    *,
    start_state: int = 0,
    halt_states: Sequence[int] = (1,),
    blank: int = 0,
    alphabet_size: int = 2,
) -> CompiledTuringMachine:
    """Compile a finite total deterministic single-tape TM transition table.

    At each generated state entry, stack 0 contains the cells strictly left
    of the head with the nearest cell on top, and stack 1 contains the current
    cell followed by cells to its right with the current cell on top.  Thus a
    logical input ``[head, right1, right2]`` is supplied as stack 1
    ``[right2, right1, head]`` (bottom-to-top).  Missing cells are represented
    by an empty stack and interpreted as ``blank``.
    """
    if not isinstance(transitions, Mapping):
        raise FieldComputerError("transitions must be a mapping")
    start_state = _state_id(start_state, "start_state")
    if isinstance(halt_states, (str, bytes, bytearray)):
        raise FieldComputerError("halt_states must be a finite sequence")
    try:
        halt_tuple = tuple(halt_states)
    except TypeError as exc:
        raise FieldComputerError("halt_states must be a finite sequence") from exc
    halt_set: set[int] = set()
    for index, value in enumerate(halt_tuple):
        state = _state_id(value, f"halt_states[{index}]")
        if state in halt_set:
            raise FieldComputerError("halt_states must be disjoint")
        halt_set.add(state)
    alphabet_size = _exact_integer(alphabet_size, "alphabet_size", minimum=1, maximum=256)
    blank = _canonical_symbol(blank, "blank")
    if blank >= alphabet_size:
        raise FieldComputerError("blank must belong to the alphabet")

    normalized: dict[tuple[int, int], tuple[int, int, str]] = {}
    states: set[int] = set(halt_set)
    states.add(start_state)
    for key, raw_value in transitions.items():
        if isinstance(key, (str, bytes, bytearray)):
            raise FieldComputerError("transition key must be (state, symbol)")
        try:
            key_tuple = tuple(key)
        except TypeError as exc:
            raise FieldComputerError("transition key must be (state, symbol)") from exc
        if len(key_tuple) != 2:
            raise FieldComputerError("transition key must be (state, symbol)")
        state = _state_id(key_tuple[0], "transition state")
        symbol = _canonical_symbol(key_tuple[1], "transition symbol")
        if symbol >= alphabet_size:
            raise FieldComputerError("transition symbol is outside the alphabet")
        if state in halt_set:
            raise FieldComputerError("halting states must not have transition rows")
        if (state, symbol) in normalized:
            raise FieldComputerError("duplicate transition row")
        if isinstance(raw_value, (str, bytes, bytearray)):
            raise FieldComputerError("transition value must be (next_state, write_symbol, direction)")
        try:
            value_tuple = tuple(raw_value)
        except TypeError as exc:
            raise FieldComputerError("transition value must be (next_state, write_symbol, direction)") from exc
        if len(value_tuple) != 3:
            raise FieldComputerError("transition value must be (next_state, write_symbol, direction)")
        next_state = _state_id(value_tuple[0], "transition next_state")
        write_symbol = _canonical_symbol(value_tuple[1], "transition write_symbol")
        if write_symbol >= alphabet_size:
            raise FieldComputerError("transition write symbol is outside the alphabet")
        direction = value_tuple[2]
        if not isinstance(direction, str) or direction not in ("L", "R", "S"):
            raise FieldComputerError("transition direction must be L, R, or S")
        normalized[(state, symbol)] = (next_state, write_symbol, direction)
        states.add(state)
        states.add(next_state)

    nonhalting_states = sorted(state for state in states if state not in halt_set)
    for state in nonhalting_states:
        for symbol in range(alphabet_size):
            if (state, symbol) not in normalized:
                raise FieldComputerError(
                    f"transition table is not total for state {state} and symbol {symbol}"
                )

    program: list[tuple[Any, ...]] = []
    labels: dict[str, int] = {}

    def mark(label: str) -> None:
        if label in labels:
            raise FieldComputerError("internal compiler label collision")
        labels[label] = len(program)

    def emit(row: tuple[Any, ...]) -> None:
        program.append(row)

    def state_label(state: int) -> str:
        return f"state:{state}"

    def handler_label(state: int, symbol: int) -> str:
        return f"handler:{state}:{symbol}"

    for state in nonhalting_states:
        mark(state_label(state))
        dispatch_labels = [f"dispatch:{state}:{symbol}" for symbol in range(alphabet_size)]
        dispatch_labels.append(f"dispatch:{state}:empty")
        emit((POP, 1, dispatch_labels[0], 0, 0))
        for index, symbol in enumerate(tuple(range(alphabet_size)) + (EMPTY,)):
            mark(dispatch_labels[index])
            next_dispatch = dispatch_labels[index + 1] if index + 1 < len(dispatch_labels) else handler_label(state, blank)
            branch_handler = handler_label(state, blank if symbol == EMPTY else symbol)
            emit((BRANCH, symbol, branch_handler, next_dispatch, 0))
        for symbol in range(alphabet_size):
            next_state, write_symbol, direction = normalized[(state, symbol)]
            mark(handler_label(state, symbol))
            destination = state_label(next_state)
            if direction == "S":
                emit((PUSH, 1, write_symbol, destination, 0))
            elif direction == "R":
                emit((PUSH, 0, write_symbol, len(program) + 1, 0))
                emit((POP, 1, len(program) + 1, 0, 0))
                mark(f"after_pop_r:{state}:{symbol}")
                emit((BRANCH, EMPTY, f"blank_r:{state}:{symbol}", f"acc_r:{state}:{symbol}", 0))
                mark(f"blank_r:{state}:{symbol}")
                emit((PUSH, 1, blank, destination, 0))
                mark(f"acc_r:{state}:{symbol}")
                emit((PUSH_ACC, 1, destination, 0, 0))
            else:  # L
                emit((PUSH, 1, write_symbol, len(program) + 1, 0))
                emit((POP, 0, len(program) + 1, 0, 0))
                mark(f"after_pop_l:{state}:{symbol}")
                emit((BRANCH, EMPTY, f"blank_l:{state}:{symbol}", f"acc_l:{state}:{symbol}", 0))
                mark(f"blank_l:{state}:{symbol}")
                emit((PUSH, 1, blank, destination, 0))
                mark(f"acc_l:{state}:{symbol}")
                emit((PUSH_ACC, 1, destination, 0, 0))

    for state in sorted(halt_set):
        mark(state_label(state))
        emit((HALT, 0, 0, 0, 0))

    patched: list[tuple[int, int, int, int, int]] = []
    for index, raw_row in enumerate(program):
        row = list(raw_row)
        for position, word in enumerate(row):
            if isinstance(word, str):
                if word not in labels:
                    raise FieldComputerError(f"unresolved compiler label {word}")
                row[position] = labels[word]
        patched.append(_canonical_instruction(tuple(row), len(program), f"compiled[{index}]"))

    state_entries = {
        state: labels[state_label(state)]
        for state in sorted(states)
    }
    return CompiledTuringMachine(
        tuple(patched),
        state_entries[start_state],
        state_entries,
    )


__all__ = [
    "SCHEMA",
    "HALT",
    "PUSH",
    "POP",
    "BRANCH",
    "PUSH_ACC",
    "JUMP",
    "PROPAGATE",
    "PROPAGATION_PROGRESS",
    "PROPAGATION_FIXED_POINT",
    "PROPAGATION_CONFLICT",
    "PROPAGATION_SATISFIED",
    "propagation_workspace",
    "inspect_propagation_workspace",
    "EMPTY",
    "FieldComputerError",
    "ComputerProfile",
    "ComputerState",
    "CompiledTuringMachine",
    "FieldComputer",
    "compile_turing_machine",
]
