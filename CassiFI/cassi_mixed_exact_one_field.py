"""Field-owned total decision for the canonical matched exact-one CNF class.

The immutable float64 field stores the canonical edge labels, dynamic-program
frontiers, predecessor choices, final assignment, status, and work counters.
One transition processes one adjacent block pair with a fixed sixteen-candidate
schedule.  No formula-family label, host hint, learned side table, or model is
consulted after initialization.

The regional entry points below retain the same DP as canonical JSON data and
advance one candidate transition per unit of native work.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

SCHEMA = "cassifi.canonical-mixed-decision.v1"
STATE_SCHEMA = "cassifi.canonical-mixed-decision-state.v1"
REGIONAL_KERNEL_NAME = "exact.mixed-exact-one"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.regional-mixed-exact-one-state.v1"
_MAGIC = 0x434D5844
_VERSION = 1
_RUNNING = 0
_SAT = 1
_UNSAT = 2
_STATUS_NAMES = {_RUNNING: "running", _SAT: "sat", _UNSAT: "unsat"}
_HEADER = 8
_H_MAGIC = 0
_H_VERSION = 1
_H_STATUS = 2
_H_BLOCKS = 3
_H_CURSOR = 4
_H_TRANSITIONS = 5
_H_CANDIDATE_CHECKS = 6
_H_SELECTED_BOUNDARY = 7

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]


class MixedExactOneDecisionError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    rows: set[Clause] = set()
    for raw_clause in formula:
        if any(
            not isinstance(literal, int) or isinstance(literal, bool)
            for literal in raw_clause
        ):
            raise MixedExactOneDecisionError("clause literals must be integers")
        clause = tuple(sorted(raw_clause, key=_literal_key))
        if not clause or any(literal == 0 for literal in clause):
            raise MixedExactOneDecisionError("clauses must be nonempty and contain no zero literal")
        if len({abs(literal) for literal in clause}) != len(clause):
            raise MixedExactOneDecisionError("clauses must not repeat or complement a variable")
        rows.add(clause)
    if len(rows) != len(formula):
        raise MixedExactOneDecisionError("formula contains duplicate clauses")
    return tuple(sorted(rows, key=lambda clause: (len(clause), clause)))


def parity_clauses(variables: Sequence[int], parity: int) -> Formula:
    if len(variables) != 2 or parity not in (0, 1):
        raise MixedExactOneDecisionError("binary parity needs two variables and one parity bit")
    left, right = variables
    if parity == 0:
        return ((left, -right), (-left, right))
    return ((left, right), (-left, -right))


def canonical_formula_from_labels(blocks: int, labels: Sequence[int]) -> Formula:
    if blocks < 4 or blocks % 2:
        raise MixedExactOneDecisionError("blocks must be even and at least four")
    if len(labels) != 3 * blocks // 2 or any(label not in (0, 1) for label in labels):
        raise MixedExactOneDecisionError("labels must contain one bit per canonical edge")

    def variable(block: int, port: int) -> int:
        return 3 * block + port + 1

    clauses: list[Clause] = []
    for block in range(blocks):
        a, b, c = (variable(block, port) for port in range(3))
        clauses.extend(((a, b, c), (-a, -b), (-a, -c), (-b, -c)))
    matching = [
        (variable(block, 1), variable((block + 1) % blocks, 0))
        for block in range(blocks)
    ]
    matching.extend(
        (variable(block, 2), variable(block + 1, 2))
        for block in range(0, blocks, 2)
    )
    for pair, label in zip(matching, labels):
        clauses.extend(parity_clauses(pair, label))
    return canonical_formula(clauses)


def labels_from_canonical_formula(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> tuple[Formula, tuple[int, ...]]:
    if variable_count < 12 or variable_count % 6:
        raise MixedExactOneDecisionError("canonical class needs 3b variables for even b >= 4")
    blocks = variable_count // 3
    source = canonical_formula(formula)
    source_set = set(source)

    def variable(block: int, port: int) -> int:
        return 3 * block + port + 1

    fixed: set[Clause] = set()
    for block in range(blocks):
        a, b, c = (variable(block, port) for port in range(3))
        fixed.update(
            canonical_formula(((a, b, c), (-a, -b), (-a, -c), (-b, -c)))
        )
    matching = [
        (variable(block, 1), variable((block + 1) % blocks, 0))
        for block in range(blocks)
    ]
    matching.extend(
        (variable(block, 2), variable(block + 1, 2))
        for block in range(0, blocks, 2)
    )
    labels: list[int] = []
    expected = set(fixed)
    for pair in matching:
        even = set(canonical_formula(parity_clauses(pair, 0)))
        odd = set(canonical_formula(parity_clauses(pair, 1)))
        if even.issubset(source_set):
            label = 0
            expected.update(even)
        elif odd.issubset(source_set):
            label = 1
            expected.update(odd)
        else:
            raise MixedExactOneDecisionError("canonical matching parity block is incomplete")
        labels.append(label)
    if source_set != expected:
        raise MixedExactOneDecisionError("formula is not exactly the canonical mixed class")
    return source, tuple(labels)


@dataclass(frozen=True, slots=True)
class CanonicalMixedDecisionProfile:
    blocks: int

    def __post_init__(self) -> None:
        if self.blocks < 4 or self.blocks % 2:
            raise MixedExactOneDecisionError("profile blocks must be even and at least four")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()

    @property
    def pairs(self) -> int:
        return self.blocks // 2

    @property
    def label_count(self) -> int:
        return 3 * self.blocks // 2

    @property
    def field_values(self) -> int:
        return 12 + 21 * self.blocks // 2
    @property
    def field_bytes(self) -> int:
        return 8 * self.field_values


    @property
    def shape(self) -> tuple[int, int, int]:
        return 1, self.field_values, 1


@dataclass(frozen=True, slots=True)
class CanonicalMixedDecisionState:
    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        field = np.asarray(self._field)
        if field.dtype != np.float64 or field.ndim != 3:
            raise MixedExactOneDecisionError("decision field must be a rank-three float64 tensor")
        if field.flags.writeable:
            field = field.copy()
            field.setflags(write=False)
            object.__setattr__(self, "_field", field)
        if len(self.profile_sha256) != 64:
            raise MixedExactOneDecisionError("invalid profile digest")

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


@dataclass(frozen=True, slots=True)
class _Layout:
    cycle: int
    chord: int
    reach: int
    parent_previous: int
    parent_even: int
    assignment: int
    total: int


def _layout(blocks: int) -> _Layout:
    pairs = blocks // 2
    cycle = _HEADER
    chord = cycle + blocks
    reach = chord + pairs
    parent_previous = reach + 4 * (pairs + 1)
    parent_even = parent_previous + 4 * pairs
    assignment = parent_even + 4 * pairs
    total = assignment + 3 * blocks
    return _Layout(cycle, chord, reach, parent_previous, parent_even, assignment, total)


def _reach_index(layout: _Layout, pairs: int, boundary: int, layer: int, carry: int) -> int:
    return layout.reach + ((boundary * (pairs + 1) + layer) * 2 + carry)


def _parent_index(layout: _Layout, pairs: int, boundary: int, layer: int, carry: int) -> int:
    return (boundary * pairs + layer - 1) * 2 + carry


class CanonicalMixedDecisionField:
    """Deterministic constant-width DP whose complete state is one tensor."""

    def __init__(self, profile: CanonicalMixedDecisionProfile) -> None:
        self.profile = profile
        self.layout = _layout(profile.blocks)
        if self.layout.total != profile.field_values:
            raise MixedExactOneDecisionError("internal decision layout mismatch")

    @staticmethod
    def _exact(value: float, name: str) -> int:
        integer = int(value)
        if float(integer) != float(value):
            raise MixedExactOneDecisionError(f"{name} is not an exact integer")
        return integer

    def _state(self, values: np.ndarray) -> CanonicalMixedDecisionState:
        field = np.asarray(values, dtype=np.float64).reshape(self.profile.shape).copy()
        field.setflags(write=False)
        state = CanonicalMixedDecisionState(field, self.profile.fingerprint)
        self.validate(state)
        return state

    def _flat(self, state: CanonicalMixedDecisionState) -> np.ndarray:
        return state._field.reshape(-1)

    def validate(self, state: CanonicalMixedDecisionState) -> None:
        if state.profile_sha256 != self.profile.fingerprint:
            raise MixedExactOneDecisionError("state/profile digest mismatch")
        if state._field.shape != self.profile.shape:
            raise MixedExactOneDecisionError("decision field shape mismatch")
        if not np.all(np.isfinite(state._field)):
            raise MixedExactOneDecisionError("decision field contains non-finite values")
        values = self._flat(state)
        if np.any(values != np.rint(values)):
            raise MixedExactOneDecisionError("decision field contains non-integer values")
        header = [self._exact(value, "header") for value in values[:_HEADER]]
        if header[_H_MAGIC] != _MAGIC or header[_H_VERSION] != _VERSION:
            raise MixedExactOneDecisionError("decision field magic/version mismatch")
        if header[_H_BLOCKS] != self.profile.blocks:
            raise MixedExactOneDecisionError("decision field block count mismatch")
        if header[_H_STATUS] not in _STATUS_NAMES:
            raise MixedExactOneDecisionError("decision field status is invalid")
        cursor = header[_H_CURSOR]
        if not 0 <= cursor <= self.profile.pairs:
            raise MixedExactOneDecisionError("decision field cursor is invalid")
        if header[_H_TRANSITIONS] != cursor or header[_H_CANDIDATE_CHECKS] != 16 * cursor:
            raise MixedExactOneDecisionError("decision field work counters are invalid")
        selected = header[_H_SELECTED_BOUNDARY]
        if selected not in (-1, 0, 1):
            raise MixedExactOneDecisionError("decision field selected boundary is invalid")
        labels = values[self.layout.cycle : self.layout.reach]
        if np.any((labels != 0) & (labels != 1)):
            raise MixedExactOneDecisionError("decision field labels are invalid")
        reach_end = self.layout.parent_previous
        reach = values[self.layout.reach : reach_end]
        if np.any((reach != 0) & (reach != 1)):
            raise MixedExactOneDecisionError("decision reachability is invalid")
        parents = values[self.layout.parent_previous : self.layout.assignment]
        if np.any((parents != -1) & (parents != 0) & (parents != 1)):
            raise MixedExactOneDecisionError("decision predecessor is invalid")
        assignment = values[self.layout.assignment : self.layout.total]
        if np.any((assignment != -1) & (assignment != 0) & (assignment != 1)):
            raise MixedExactOneDecisionError("decision assignment is invalid")
        status = header[_H_STATUS]
        if status == _RUNNING and cursor == self.profile.pairs:
            raise MixedExactOneDecisionError("completed decision remains running")
        if status != _RUNNING and cursor != self.profile.pairs:
            raise MixedExactOneDecisionError("decision terminated before all pairs")
        if status == _SAT and (selected not in (0, 1) or np.any(assignment < 0)):
            raise MixedExactOneDecisionError("SAT state lacks a complete assignment")
        if status != _SAT and (selected != -1 or np.any(assignment != -1)):
            raise MixedExactOneDecisionError("non-SAT state contains a witness")

    def initial(
        self,
        formula: Sequence[Sequence[int]],
        *,
        variable_count: int,
    ) -> CanonicalMixedDecisionState:
        _, labels = labels_from_canonical_formula(formula, variable_count=variable_count)
        if variable_count != 3 * self.profile.blocks:
            raise MixedExactOneDecisionError("formula/profile block count mismatch")
        values = np.zeros(self.profile.field_values, dtype=np.float64)
        values[_H_MAGIC] = _MAGIC
        values[_H_VERSION] = _VERSION
        values[_H_STATUS] = _RUNNING
        values[_H_BLOCKS] = self.profile.blocks
        values[_H_SELECTED_BOUNDARY] = -1
        values[self.layout.cycle : self.layout.reach] = labels
        values[self.layout.parent_previous : self.layout.total] = -1
        for boundary in (0, 1):
            values[
                _reach_index(
                    self.layout,
                    self.profile.pairs,
                    boundary,
                    0,
                    boundary,
                )
            ] = 1
        return self._state(values)

    def state_sha256(self, state: CanonicalMixedDecisionState) -> str:
        self.validate(state)
        return hashlib.sha256(state._field.tobytes()).hexdigest()
    def inspect(self, state: CanonicalMixedDecisionState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        status = _STATUS_NAMES[int(values[_H_STATUS])]
        selected = int(values[_H_SELECTED_BOUNDARY])
        return {
            "status": status,
            "blocks": self.profile.blocks,
            "cursor": int(values[_H_CURSOR]),
            "transitions": int(values[_H_TRANSITIONS]),
            "candidate_checks": int(values[_H_CANDIDATE_CHECKS]),
            "selected_boundary": selected if status == "sat" else None,
            "field_bytes": state.nbytes,
            "state_sha256": self.state_sha256(state),
        }


    def _labels(self, values: np.ndarray) -> tuple[tuple[int, ...], tuple[int, ...]]:
        cycle = tuple(int(value) for value in values[self.layout.cycle : self.layout.chord])
        chord = tuple(int(value) for value in values[self.layout.chord : self.layout.reach])
        return cycle, chord

    @staticmethod
    def _pair_valid(
        cycle: Sequence[int],
        chord: Sequence[int],
        blocks: int,
        pair: int,
        previous: int,
        even: int,
        odd: int,
    ) -> bool:
        block = 2 * pair
        incoming_even = previous ^ cycle[(block - 1) % blocks]
        if incoming_even + even > 1:
            return False
        third_even = 1 - incoming_even - even
        incoming_odd = even ^ cycle[block]
        if incoming_odd + odd > 1:
            return False
        third_odd = 1 - incoming_odd - odd
        return third_even ^ third_odd == chord[pair]

    def _write_assignment(self, values: np.ndarray, boundary: int) -> None:
        pairs = self.profile.pairs
        cycle, _ = self._labels(values)
        outgoing = [-1] * self.profile.blocks
        current = boundary
        for pair in range(pairs - 1, -1, -1):
            output = current
            parent_offset = _parent_index(
                self.layout,
                pairs,
                boundary,
                pair + 1,
                output,
            )
            previous = int(values[self.layout.parent_previous + parent_offset])
            even = int(values[self.layout.parent_even + parent_offset])
            if previous not in (0, 1) or even not in (0, 1):
                raise MixedExactOneDecisionError("accepting path has no predecessor")
            outgoing[2 * pair] = even
            outgoing[2 * pair + 1] = output
            current = previous
        if current != boundary:
            raise MixedExactOneDecisionError("accepting path does not close")
        assignment = [-1] * (3 * self.profile.blocks)
        for block in range(self.profile.blocks):
            port_one = outgoing[block]
            port_zero = outgoing[(block - 1) % self.profile.blocks] ^ cycle[(block - 1) % self.profile.blocks]
            port_two = 1 - port_zero - port_one
            if port_two not in (0, 1):
                raise MixedExactOneDecisionError("accepting path violates exact-one")
            assignment[3 * block : 3 * block + 3] = [port_zero, port_one, port_two]
        values[self.layout.assignment : self.layout.total] = assignment

    def _advance_values(
        self,
        values: np.ndarray,
        cycle: Sequence[int],
        chord: Sequence[int],
    ) -> int:
        pair = int(values[_H_CURSOR])
        layer = pair + 1
        pairs = self.profile.pairs
        for boundary in (0, 1):
            for carry in (0, 1):
                values[_reach_index(self.layout, pairs, boundary, layer, carry)] = 0
                parent_offset = _parent_index(self.layout, pairs, boundary, layer, carry)
                values[self.layout.parent_previous + parent_offset] = -1
                values[self.layout.parent_even + parent_offset] = -1
            for previous in (0, 1):
                reachable = bool(
                    values[_reach_index(self.layout, pairs, boundary, pair, previous)]
                )
                for even in (0, 1):
                    for odd in (0, 1):
                        if not reachable or not self._pair_valid(
                            cycle,
                            chord,
                            self.profile.blocks,
                            pair,
                            previous,
                            even,
                            odd,
                        ):
                            continue
                        reach_index = _reach_index(
                            self.layout,
                            pairs,
                            boundary,
                            layer,
                            odd,
                        )
                        if values[reach_index]:
                            continue
                        values[reach_index] = 1
                        parent_offset = _parent_index(
                            self.layout,
                            pairs,
                            boundary,
                            layer,
                            odd,
                        )
                        values[self.layout.parent_previous + parent_offset] = previous
                        values[self.layout.parent_even + parent_offset] = even
        values[_H_CURSOR] = layer
        values[_H_TRANSITIONS] = layer
        values[_H_CANDIDATE_CHECKS] = 16 * layer
        if layer == pairs:
            accepting = [
                boundary
                for boundary in (0, 1)
                if values[_reach_index(self.layout, pairs, boundary, layer, boundary)]
            ]
            if accepting:
                selected = accepting[0]
                values[_H_STATUS] = _SAT
                values[_H_SELECTED_BOUNDARY] = selected
                self._write_assignment(values, selected)
            else:
                values[_H_STATUS] = _UNSAT
        return pair

    def step(
        self,
        state: CanonicalMixedDecisionState,
    ) -> tuple[CanonicalMixedDecisionState, Mapping[str, Any]]:
        self.validate(state)
        before_sha256 = self.state_sha256(state)
        source = self._flat(state)
        status = int(source[_H_STATUS])
        if status != _RUNNING:
            return state, {
                "schema": "cassifi.canonical-mixed-transition.v1",
                "action": "done",
                "status": _STATUS_NAMES[status],
                "previous_state_sha256": before_sha256,
                "state_sha256": before_sha256,
                "state_unchanged": True,
            }
        values = source.copy()

        cycle, chord = self._labels(values)
        pair = self._advance_values(values, cycle, chord)
        successor = self._state(values)
        return successor, {
            "schema": "cassifi.canonical-mixed-transition.v1",
            "action": "advance-pair",
            "pair": pair,
            "candidate_checks": 16,
            "status": _STATUS_NAMES[int(values[_H_STATUS])],
            "previous_state_sha256": before_sha256,
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }

    def solve(
        self,
        state: CanonicalMixedDecisionState,
    ) -> tuple[CanonicalMixedDecisionState, Mapping[str, Any]]:
        self.validate(state)
        if int(self._flat(state)[_H_STATUS]) != _RUNNING:
            return state, self.certificate(state)
        values = self._flat(state).copy()
        cycle, chord = self._labels(values)
        while int(values[_H_STATUS]) == _RUNNING:
            self._advance_values(values, cycle, chord)
        current = self._state(values)
        return current, self.certificate(current)

    def certificate(self, state: CanonicalMixedDecisionState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        status = _STATUS_NAMES[int(values[_H_STATUS])]
        cycle, chord = self._labels(values)
        cursor = int(values[_H_CURSOR])
        layers: list[dict[str, Any]] = []
        for layer in range(cursor + 1):
            reachable = [
                [
                    int(values[_reach_index(self.layout, self.profile.pairs, boundary, layer, carry)])
                    for carry in (0, 1)
                ]
                for boundary in (0, 1)
            ]
            parents: list[dict[str, int]] = []
            if layer:
                for boundary in (0, 1):
                    for carry in (0, 1):
                        if not reachable[boundary][carry]:
                            continue
                        parent_offset = _parent_index(
                            self.layout,
                            self.profile.pairs,
                            boundary,
                            layer,
                            carry,
                        )
                        parents.append(
                            {
                                "boundary": boundary,
                                "carry": carry,
                                "previous": int(values[self.layout.parent_previous + parent_offset]),
                                "even": int(values[self.layout.parent_even + parent_offset]),
                            }
                        )
            layers.append({"reachable": reachable, "parents": parents})
        assignment_values = values[self.layout.assignment : self.layout.total]
        assignment = (
            [int(value) for value in assignment_values]
            if status == "sat"
            else None
        )
        labels = list(cycle + chord)
        formula = canonical_formula_from_labels(self.profile.blocks, labels)
        certificate: dict[str, Any] = {
            "schema": SCHEMA,
            "status": status,
            "blocks": self.profile.blocks,
            "variables": 3 * self.profile.blocks,
            "labels": labels,
            "problem_sha256": hashlib.sha256(_canonical(formula)).hexdigest(),
            "transitions": int(values[_H_TRANSITIONS]),
            "candidate_checks": int(values[_H_CANDIDATE_CHECKS]),
            "selected_boundary": (
                int(values[_H_SELECTED_BOUNDARY]) if status == "sat" else None
            ),
            "assignment": assignment,
            "layers": layers,
            "field_bytes": state.nbytes,
            "state_sha256": self.state_sha256(state),
            "profile_sha256": self.profile.fingerprint,
        }
        certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
        return certificate

    def descriptor(self, state: CanonicalMixedDecisionState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": STATE_SCHEMA,
            "profile": asdict(self.profile),
            "profile_sha256": self.profile.fingerprint,
            "state_sha256": self.state_sha256(state),
            "field_b64": base64.b64encode(state._field.tobytes()).decode("ascii"),
        }

    @classmethod
    def from_descriptor(
        cls,
        value: Mapping[str, Any],
    ) -> tuple["CanonicalMixedDecisionField", CanonicalMixedDecisionState]:
        if value.get("schema") != STATE_SCHEMA:
            raise MixedExactOneDecisionError("unsupported decision descriptor")
        profile_value = value.get("profile")
        if not isinstance(profile_value, Mapping) or set(profile_value) != {"blocks"}:
            raise MixedExactOneDecisionError("invalid decision profile")
        blocks = profile_value.get("blocks")
        if not isinstance(blocks, int) or isinstance(blocks, bool):
            raise MixedExactOneDecisionError("invalid decision block count")
        field = cls(CanonicalMixedDecisionProfile(blocks))
        if value.get("profile_sha256") != field.profile.fingerprint:
            raise MixedExactOneDecisionError("decision descriptor profile digest mismatch")
        encoded = value.get("field_b64")
        if not isinstance(encoded, str):
            raise MixedExactOneDecisionError("decision descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            tensor = np.frombuffer(raw, dtype=np.float64).reshape(field.profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise MixedExactOneDecisionError("decision descriptor field encoding is invalid") from exc
        digest = value.get("state_sha256")
        if not isinstance(digest, str) or hashlib.sha256(raw).hexdigest() != digest:
            raise MixedExactOneDecisionError("decision descriptor state digest mismatch")
        state = field._state(tensor)
        return field, state


def _regional_integer(value: Any, name: str, *, minimum: int = 0, maximum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MixedExactOneDecisionError(f"{name} must be an integer")
    integer = int(value)
    if integer < minimum or (maximum is not None and integer > maximum):
        bound = f"[{minimum}, {maximum}]" if maximum is not None else f">={minimum}"
        raise MixedExactOneDecisionError(f"{name} must be in {bound}")
    return integer


def _regional_copy(value: Any) -> Any:
    """Copy a canonical state through the same JSON representation as callers."""

    return json.loads(_canonical(value).decode("utf-8"))


def _regional_cursor_number(continuation: Mapping[str, Any]) -> int:
    return (
        ((int(continuation["boundary"]) * 2 + int(continuation["previous"])) * 2
         + int(continuation["even"])) * 2
        + int(continuation["odd"])
    )


def _regional_validate(state: Any) -> None:
    if not isinstance(state, Mapping):
        raise MixedExactOneDecisionError("regional mixed state must be a mapping")
    if set(state) != {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }:
        raise MixedExactOneDecisionError("regional mixed state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise MixedExactOneDecisionError("regional mixed state schema is invalid")

    profile = state["profile"]
    if not isinstance(profile, Mapping) or set(profile) != {"blocks", "variable_count"}:
        raise MixedExactOneDecisionError("regional mixed profile is invalid")
    blocks = _regional_integer(profile.get("blocks"), "regional mixed blocks", minimum=4)
    variable_count = _regional_integer(
        profile.get("variable_count"),
        "regional mixed variable count",
        minimum=12,
    )
    if blocks % 2 or variable_count != 3 * blocks:
        raise MixedExactOneDecisionError("regional mixed profile dimensions are invalid")

    source = state["source"]
    if not isinstance(source, list):
        raise MixedExactOneDecisionError("regional mixed source is invalid")
    normalized_source, labels = labels_from_canonical_formula(
        source,
        variable_count=variable_count,
    )
    expected_source = [list(clause) for clause in normalized_source]
    if source != expected_source:
        raise MixedExactOneDecisionError("regional mixed source is not canonical")

    continuation = state["continuation"]
    if not isinstance(continuation, Mapping) or set(continuation) != {
        "instance",
        "pair",
        "boundary",
        "previous",
        "even",
        "odd",
        "frontier",
        "parents",
        "selected_boundary",
        "assignment",
    }:
        raise MixedExactOneDecisionError("regional mixed continuation is invalid")
    instance = continuation["instance"]
    if not isinstance(instance, Mapping) or set(instance) != {
        "labels",
        "cycle",
        "chord",
        "problem_sha256",
    }:
        raise MixedExactOneDecisionError("regional mixed normalized instance is invalid")
    labels_list = list(labels)
    if (
        instance["labels"] != labels_list
        or instance["cycle"] != labels_list[:blocks]
        or instance["chord"] != labels_list[blocks:]
        or instance["problem_sha256"] != hashlib.sha256(_canonical(normalized_source)).hexdigest()
    ):
        raise MixedExactOneDecisionError("regional mixed normalized instance mismatch")

    pairs = blocks // 2
    pair = _regional_integer(continuation["pair"], "regional mixed pair", maximum=pairs)
    phase = state["phase"]
    if phase not in {"dp", "terminal"}:
        raise MixedExactOneDecisionError("regional mixed phase is invalid")
    boundary = _regional_integer(continuation["boundary"], "regional mixed boundary", maximum=1)
    previous = _regional_integer(continuation["previous"], "regional mixed previous", maximum=1)
    even = _regional_integer(continuation["even"], "regional mixed even", maximum=1)
    odd = _regional_integer(continuation["odd"], "regional mixed odd", maximum=1)
    if phase == "terminal" and pair != pairs:
        raise MixedExactOneDecisionError("regional mixed terminal pair is invalid")
    if phase == "dp" and pair == pairs:
        raise MixedExactOneDecisionError("regional mixed DP pair is exhausted")

    frontier = continuation["frontier"]
    parents = continuation["parents"]
    if (
        not isinstance(frontier, list)
        or len(frontier) != 2
        or any(not isinstance(row, list) or len(row) != pairs + 1 for row in frontier)
        or not isinstance(parents, list)
        or len(parents) != 2
        or any(not isinstance(row, list) or len(row) != pairs + 1 for row in parents)
    ):
        raise MixedExactOneDecisionError("regional mixed DP table shape is invalid")
    for boundary_index in (0, 1):
        for layer in range(pairs + 1):
            if (
                not isinstance(frontier[boundary_index][layer], list)
                or len(frontier[boundary_index][layer]) != 2
                or not isinstance(parents[boundary_index][layer], list)
                or len(parents[boundary_index][layer]) != 2
            ):
                raise MixedExactOneDecisionError("regional mixed DP row is invalid")
            for carry in (0, 1):
                reachable = _regional_integer(
                    frontier[boundary_index][layer][carry],
                    "regional mixed reachability",
                    maximum=1,
                )
                parent = parents[boundary_index][layer][carry]
                if parent is not None:
                    if not isinstance(parent, Mapping) or set(parent) != {"previous", "even"}:
                        raise MixedExactOneDecisionError("regional mixed predecessor is invalid")
                    _regional_integer(parent["previous"], "regional mixed predecessor", maximum=1)
                    _regional_integer(parent["even"], "regional mixed predecessor", maximum=1)
                if layer == 0 and parent is not None:
                    raise MixedExactOneDecisionError("regional mixed initial layer has a predecessor")
                if reachable and layer > 0 and parent is None:
                    raise MixedExactOneDecisionError("regional mixed reachable cell lacks a predecessor")

    selected_boundary = continuation["selected_boundary"]
    if selected_boundary is not None:
        _regional_integer(selected_boundary, "regional mixed selected boundary", maximum=1)
    assignment = continuation["assignment"]
    if assignment is not None:
        if not isinstance(assignment, list) or len(assignment) != variable_count:
            raise MixedExactOneDecisionError("regional mixed assignment is invalid")
        for value in assignment:
            _regional_integer(value, "regional mixed assignment", maximum=1)
    if phase == "dp" and (selected_boundary is not None or assignment is not None):
        raise MixedExactOneDecisionError("unfinished regional mixed state has terminal evidence")

    journal = state["journal"]
    if not isinstance(journal, Mapping) or set(journal) != {"entries", "terminal"}:
        raise MixedExactOneDecisionError("regional mixed journal is invalid")
    entries = journal["entries"]
    if not isinstance(entries, list) or any(not isinstance(entry, Mapping) for entry in entries):
        raise MixedExactOneDecisionError("regional mixed journal entries are invalid")
    if journal["terminal"] not in {None, "sat", "unsat"}:
        raise MixedExactOneDecisionError("regional mixed journal terminal status is invalid")
    if phase == "dp" and journal["terminal"] is not None:
        raise MixedExactOneDecisionError("unfinished regional mixed journal is terminal")
    if phase == "terminal" and journal["terminal"] not in {"sat", "unsat"}:
        raise MixedExactOneDecisionError("terminal regional mixed journal lacks status")

    ledger = state["ledger"]
    if not isinstance(ledger, Mapping) or set(ledger) != {
        "invocations",
        "primitive_work",
        "transitions",
        "candidate_checks",
    }:
        raise MixedExactOneDecisionError("regional mixed ledger is invalid")
    invocations = _regional_integer(ledger["invocations"], "regional mixed invocations")
    primitive_work = _regional_integer(ledger["primitive_work"], "regional mixed primitive work")
    transitions = _regional_integer(ledger["transitions"], "regional mixed transitions")
    candidate_checks = _regional_integer(ledger["candidate_checks"], "regional mixed candidate checks")
    if transitions != pair or primitive_work != candidate_checks:
        raise MixedExactOneDecisionError("regional mixed cumulative work is inconsistent")
    expected_checks = 16 * pair if phase == "terminal" else 16 * pair + _regional_cursor_number(continuation)
    if candidate_checks != expected_checks:
        raise MixedExactOneDecisionError("regional mixed candidate cursor is inconsistent")
    if phase == "terminal" and _regional_cursor_number(continuation) != 0:
        raise MixedExactOneDecisionError("terminal regional mixed cursor is not reset")

    result = state["result"]
    if phase == "dp" and result is not None:
        raise MixedExactOneDecisionError("unfinished regional mixed state has a result")
    if phase == "terminal":
        if not isinstance(result, Mapping) or result.get("schema") != SCHEMA:
            raise MixedExactOneDecisionError("regional mixed terminal result is invalid")
        if result.get("status") not in {"sat", "unsat"}:
            raise MixedExactOneDecisionError("regional mixed terminal result status is invalid")
        if selected_boundary is None and result["status"] == "sat":
            raise MixedExactOneDecisionError("regional mixed SAT result lacks a boundary")
        if selected_boundary is not None and result["status"] != "sat":
            raise MixedExactOneDecisionError("regional mixed UNSAT result has a boundary")
        if result["status"] == "sat" and assignment is None:
            raise MixedExactOneDecisionError("regional mixed SAT result lacks an assignment")
        if result["status"] == "unsat" and assignment is not None:
            raise MixedExactOneDecisionError("regional mixed UNSAT result has an assignment")
    del invocations


def _regional_pair_valid(
    cycle: Sequence[int],
    chord: Sequence[int],
    blocks: int,
    pair: int,
    previous: int,
    even: int,
    odd: int,
) -> bool:
    block = 2 * pair
    incoming_even = previous ^ cycle[(block - 1) % blocks]
    if incoming_even + even > 1:
        return False
    third_even = 1 - incoming_even - even
    incoming_odd = even ^ cycle[block]
    if incoming_odd + odd > 1:
        return False
    third_odd = 1 - incoming_odd - odd
    return third_even ^ third_odd == chord[pair]


def _regional_assignment(
    continuation: Mapping[str, Any],
    layout: _Layout,
    blocks: int,
) -> list[int]:
    selected = continuation["selected_boundary"]
    if selected not in (0, 1):
        raise MixedExactOneDecisionError("regional mixed SAT state lacks boundary")
    pairs = blocks // 2
    parents = continuation["parents"]
    cycle = continuation["instance"]["cycle"]
    outgoing = [-1] * blocks
    current = int(selected)
    for pair in range(pairs - 1, -1, -1):
        parent = parents[int(selected)][pair + 1][current]
        if not isinstance(parent, Mapping):
            raise MixedExactOneDecisionError("regional mixed accepting path lacks predecessor")
        previous = parent["previous"]
        even = parent["even"]
        if previous not in (0, 1) or even not in (0, 1):
            raise MixedExactOneDecisionError("regional mixed predecessor is invalid")
        outgoing[2 * pair] = int(even)
        outgoing[2 * pair + 1] = current
        current = int(previous)
    if current != int(selected):
        raise MixedExactOneDecisionError("regional mixed accepting path does not close")
    assignment = [-1] * (3 * blocks)
    for block in range(blocks):
        port_one = outgoing[block]
        port_zero = outgoing[(block - 1) % blocks] ^ int(cycle[(block - 1) % blocks])
        port_two = 1 - port_zero - port_one
        if port_two not in (0, 1):
            raise MixedExactOneDecisionError("regional mixed accepting path violates exact-one")
        assignment[3 * block : 3 * block + 3] = [port_zero, port_one, port_two]
    return assignment


def _regional_values(
    state: Mapping[str, Any],
    status: str,
) -> tuple[np.ndarray, _Layout, list[int] | None]:
    blocks = int(state["profile"]["blocks"])
    pairs = blocks // 2
    layout = _layout(blocks)
    continuation = state["continuation"]
    values = np.zeros(layout.total, dtype=np.float64)
    values[_H_MAGIC] = _MAGIC
    values[_H_VERSION] = _VERSION
    values[_H_STATUS] = _SAT if status == "sat" else _UNSAT
    values[_H_BLOCKS] = blocks
    values[_H_CURSOR] = pairs
    values[_H_TRANSITIONS] = int(state["ledger"]["transitions"])
    values[_H_CANDIDATE_CHECKS] = int(state["ledger"]["candidate_checks"])
    selected = continuation["selected_boundary"]
    values[_H_SELECTED_BOUNDARY] = -1 if selected is None else int(selected)
    instance = continuation["instance"]
    labels = instance["labels"]
    values[layout.cycle : layout.reach] = labels
    values[layout.parent_previous : layout.assignment] = -1
    frontier = continuation["frontier"]
    parents = continuation["parents"]
    for boundary in (0, 1):
        for layer in range(pairs + 1):
            for carry in (0, 1):
                values[_reach_index(layout, pairs, boundary, layer, carry)] = frontier[
                    boundary
                ][layer][carry]
                if layer:
                    parent_offset = _parent_index(layout, pairs, boundary, layer, carry)
                    parent = parents[boundary][layer][carry]
                    if parent is not None:
                        values[layout.parent_previous + parent_offset] = parent["previous"]
                        values[layout.parent_even + parent_offset] = parent["even"]
    values[layout.assignment : layout.total] = -1
    assignment: list[int] | None = None
    if status == "sat":
        assignment = _regional_assignment(continuation, layout, blocks)
        values[layout.assignment : layout.total] = assignment
    return values, layout, assignment


def _regional_certificate(state: Mapping[str, Any], status: str) -> dict[str, Any]:
    values, layout, assignment = _regional_values(state, status)
    blocks = int(state["profile"]["blocks"])
    pairs = blocks // 2
    continuation = state["continuation"]
    instance = continuation["instance"]
    cycle = tuple(int(value) for value in instance["cycle"])
    chord = tuple(int(value) for value in instance["chord"])
    layers: list[dict[str, Any]] = []
    for layer in range(pairs + 1):
        reachable = [
            [
                int(values[_reach_index(layout, pairs, boundary, layer, carry)])
                for carry in (0, 1)
            ]
            for boundary in (0, 1)
        ]
        parents: list[dict[str, int]] = []
        if layer:
            for boundary in (0, 1):
                for carry in (0, 1):
                    if not reachable[boundary][carry]:
                        continue
                    parent = continuation["parents"][boundary][layer][carry]
                    if not isinstance(parent, Mapping):
                        raise MixedExactOneDecisionError("regional mixed layer lacks predecessor")
                    parents.append(
                        {
                            "boundary": boundary,
                            "carry": carry,
                            "previous": int(parent["previous"]),
                            "even": int(parent["even"]),
                        }
                    )
        layers.append({"reachable": reachable, "parents": parents})
    labels = list(cycle + chord)
    formula = canonical_formula_from_labels(blocks, labels)
    certificate: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "blocks": blocks,
        "variables": 3 * blocks,
        "labels": labels,
        "problem_sha256": hashlib.sha256(_canonical(formula)).hexdigest(),
        "transitions": int(state["ledger"]["transitions"]),
        "candidate_checks": int(state["ledger"]["candidate_checks"]),
        "selected_boundary": (
            int(continuation["selected_boundary"]) if status == "sat" else None
        ),
        "assignment": assignment,
        "layers": layers,
        "field_bytes": int(values.nbytes),
        "state_sha256": hashlib.sha256(values.tobytes()).hexdigest(),
        "profile_sha256": hashlib.sha256(_canonical({"blocks": blocks})).hexdigest(),
    }
    certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
    return certificate


def regional_state(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> dict[str, Any]:
    """Create a JSON-safe continuation for the mixed exact-one DP."""

    variable_count = _regional_integer(
        variable_count,
        "regional mixed variable count",
        minimum=12,
    )
    source, labels = labels_from_canonical_formula(
        formula,
        variable_count=variable_count,
    )
    blocks = variable_count // 3
    pairs = blocks // 2
    frontier = [
        [[0, 0] for _ in range(pairs + 1)]
        for _ in range(2)
    ]
    for boundary in (0, 1):
        frontier[boundary][0][boundary] = 1
    parents = [
        [[None, None] for _ in range(pairs + 1)]
        for _ in range(2)
    ]
    labels_list = list(labels)
    state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": [list(clause) for clause in source],
        "profile": {"blocks": blocks, "variable_count": variable_count},
        "phase": "dp",
        "continuation": {
            "instance": {
                "labels": labels_list,
                "cycle": labels_list[:blocks],
                "chord": labels_list[blocks:],
                "problem_sha256": hashlib.sha256(_canonical(source)).hexdigest(),
            },
            "pair": 0,
            "boundary": 0,
            "previous": 0,
            "even": 0,
            "odd": 0,
            "frontier": frontier,
            "parents": parents,
            "selected_boundary": None,
            "assignment": None,
        },
        "journal": {"entries": [], "terminal": None},
        "ledger": {
            "invocations": 0,
            "primitive_work": 0,
            "transitions": 0,
            "candidate_checks": 0,
        },
        "result": None,
    }
    _regional_validate(state)
    return state


def _regional_fault(state: Any, message: str) -> KernelResult:
    try:
        _canonical(state)
        safe_state = state
    except (TypeError, ValueError):
        safe_state = {}
    evidence = {
        "schema": SCHEMA,
        "family": REGIONAL_KERNEL_NAME,
        "status": "fault",
        "error_type": "MixedExactOneDecisionError",
        "message": message,
        "evidence": {"kind": "fault", "family": REGIONAL_KERNEL_NAME},
    }
    return KernelResult(state=safe_state, status="fault", work=0, output=evidence)


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance at most ``quantum`` candidate transitions of the retained DP."""

    try:
        _regional_validate(state)
        if not isinstance(arguments, Mapping) or arguments:
            raise MixedExactOneDecisionError("regional mixed kernel takes no arguments")
        quantum = _regional_integer(
            quantum,
            "regional mixed quantum",
            minimum=1,
            maximum=REGIONAL_KERNEL_MAX_WORK,
        )
        if state["phase"] == "terminal":
            return KernelResult(
                state=state,
                status="done",
                work=0,
                output=state["result"],
            )

        updated = _regional_copy(state)
        ledger = updated["ledger"]
        ledger["invocations"] += 1
        continuation = updated["continuation"]
        instance = continuation["instance"]
        cycle = instance["cycle"]
        chord = instance["chord"]
        blocks = int(updated["profile"]["blocks"])
        pairs = blocks // 2
        frontier = continuation["frontier"]
        parents = continuation["parents"]
        entries: list[dict[str, Any]] = []
        consumed = 0
        while consumed < quantum and updated["phase"] == "dp":
            pair = int(continuation["pair"])
            boundary = int(continuation["boundary"])
            previous = int(continuation["previous"])
            even = int(continuation["even"])
            odd = int(continuation["odd"])
            reachable = bool(frontier[boundary][pair][previous])
            valid = reachable and _regional_pair_valid(
                cycle,
                chord,
                blocks,
                pair,
                previous,
                even,
                odd,
            )
            accepted = False
            if valid and not frontier[boundary][pair + 1][odd]:
                frontier[boundary][pair + 1][odd] = 1
                parents[boundary][pair + 1][odd] = {
                    "previous": previous,
                    "even": even,
                }
                accepted = True
            entries.append(
                {
                    "pair": pair,
                    "boundary": boundary,
                    "previous": previous,
                    "even": even,
                    "odd": odd,
                    "reachable": reachable,
                    "valid": bool(valid),
                    "accepted": accepted,
                }
            )
            consumed += 1
            ledger["primitive_work"] += 1
            ledger["candidate_checks"] += 1

            odd += 1
            if odd == 2:
                odd = 0
                even += 1
                if even == 2:
                    even = 0
                    previous += 1
                    if previous == 2:
                        previous = 0
                        boundary += 1
                        if boundary == 2:
                            boundary = 0
                            continuation["pair"] = pair + 1
                            continuation["boundary"] = 0
                            continuation["previous"] = 0
                            continuation["even"] = 0
                            continuation["odd"] = 0
                            ledger["transitions"] += 1
                            if pair + 1 == pairs:
                                accepting = [
                                    candidate_boundary
                                    for candidate_boundary in (0, 1)
                                    if frontier[candidate_boundary][pairs][candidate_boundary]
                                ]
                                status = "sat" if accepting else "unsat"
                                continuation["selected_boundary"] = (
                                    accepting[0] if accepting else None
                                )
                                updated["phase"] = "terminal"
                                certificate = _regional_certificate(updated, status)
                                if status == "sat":
                                    continuation["assignment"] = certificate["assignment"]
                                updated["result"] = certificate
                            continue
            continuation["boundary"] = boundary
            continuation["previous"] = previous
            continuation["even"] = even
            continuation["odd"] = odd

        updated["journal"]["entries"].extend(entries)
        if updated["phase"] == "terminal":
            updated["journal"]["terminal"] = updated["result"]["status"]
            return KernelResult(
                state=updated,
                status="done",
                work=consumed,
                output=updated["result"],
                events=tuple(entries),
            )
        return KernelResult(
            state=updated,
            status="yield",
            work=consumed,
            output=None,
            events=tuple(entries),
        )
    except (MixedExactOneDecisionError, TypeError, KeyError, IndexError, ValueError) as exc:
        return _regional_fault(state, str(exc) or "regional mixed state is invalid")


__all__ = [
    "SCHEMA",
    "STATE_SCHEMA",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "regional_state",
    "regional_kernel",
    "CanonicalMixedDecisionField",
    "CanonicalMixedDecisionProfile",
    "CanonicalMixedDecisionState",
    "MixedExactOneDecisionError",
    "canonical_formula",
    "canonical_formula_from_labels",
    "labels_from_canonical_formula",
    "parity_clauses",
]
