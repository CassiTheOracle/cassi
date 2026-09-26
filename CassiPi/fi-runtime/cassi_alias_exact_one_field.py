"""Exact field-owned decision for degree-two/degree-three monotone 1-in-3 SAT.

Degree-three variables are the explicit branching parameter. Once their truth
values are fixed and propagated, every surviving degree-two variable is an
edge between two unsatisfied clauses, so the residual problem is ordinary
perfect matching. Search costs O(2^k c^3); a complete UNSAT certificate has
one checkable branch witness for each of the 2^k assignments.

The regional v3 adapter below keeps the normalized source, typed branch
cursor, proof journal, cumulative ledger, terminal tensor digest, and native
certificate in one canonical-JSON mapping. Each kernel call evaluates no more
than its supplied quantum of cubic candidates; it does not rely on legacy
field descriptors or solver callbacks.
"""

from __future__ import annotations

import base64
import copy
import hashlib
import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult
from cassi_general_matched_field import (
    deterministic_maximum_matching,
    deterministic_tutte_barrier,
    graph_component_sizes,
)

SCHEMA = "cassifi.alias-exact-one-decision.v1"
STATE_SCHEMA = "cassifi.alias-exact-one-state.v1"
REGIONAL_KERNEL_NAME = "exact.alias-enumeration"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.alias-exact-one-regional-state.v3"
_MAGIC = 0x414C584F
_VERSION = 1
_RUNNING = 0
_SAT = 1
_UNSAT = 2
_STATUS_NAMES = {_RUNNING: "running", _SAT: "sat", _UNSAT: "unsat"}
_HEADER = 13
_H_MAGIC = 0
_H_VERSION = 1
_H_STATUS = 2
_H_CLAUSES = 3
_H_VARIABLES = 4
_H_CUBIC = 5
_H_CURSOR = 6
_H_BRANCHES = 7
_H_CHECKED = 8
_H_MATCHING_RUNS = 9
_H_EDGE_SCANS = 10
_H_CONTRACTIONS = 11
_H_SELECTED_BRANCH = 12
_MAX_EXACT_FLOAT64_INTEGER = 2**53 - 1

Clause = tuple[int, int, int]
Formula = tuple[Clause, ...]
Graph = tuple[tuple[int, ...], ...]


class AliasExactOneDecisionError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_monotone_formula(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> Formula:
    if not isinstance(variable_count, int) or isinstance(variable_count, bool) or variable_count < 1:
        raise AliasExactOneDecisionError("variable count must be a positive integer")

    rows: list[Clause] = [None] * len(formula)
    for i, raw_clause in enumerate(formula):
        if len(raw_clause) != 3:
            raise AliasExactOneDecisionError("clauses must contain three positive in-range variables")

        # Single pass validation
        for variable in raw_clause:
            if not isinstance(variable, int) or isinstance(variable, bool) or not 1 <= variable <= variable_count:
                raise AliasExactOneDecisionError("clauses must contain three positive in-range variables")

        # Sort and check for duplicates efficiently
        sorted_clause = tuple(sorted(raw_clause))
        if sorted_clause[0] == sorted_clause[1] or sorted_clause[1] == sorted_clause[2]:
            raise AliasExactOneDecisionError("a clause repeats a variable")

        rows[i] = sorted_clause

    if not rows[0]:
        raise AliasExactOneDecisionError("formula must contain at least one clause")

    return tuple(sorted(rows))


@dataclass(frozen=True, slots=True)
class RecognizedAliasFormula:
    formula: Formula
    degrees: tuple[int, ...]
    cubic_variables: tuple[int, ...]
    incidence: tuple[tuple[int, ...], ...]


def recognize_degree_two_three_exact_one(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> RecognizedAliasFormula:
    source = canonical_monotone_formula(formula, variable_count=variable_count)
    incidence: list[list[int]] = [[] for _ in range(variable_count)]
    for clause_index, clause in enumerate(source):
        for variable in clause:
            incidence[variable - 1].append(clause_index)
    degrees = tuple(len(rows) for rows in incidence)
    if any(degree not in (2, 3) for degree in degrees):
        raise AliasExactOneDecisionError("every variable must occur exactly two or three times")
    cubic = tuple(index + 1 for index, degree in enumerate(degrees) if degree == 3)
    return RecognizedAliasFormula(
        source,
        degrees,
        cubic,
        tuple(tuple(rows) for rows in incidence),
    )


def regular_monotone_formula(
    clause_count: int,
    cubic_variables: int,
    *,
    seed: int,
) -> Formula:
    """Construct a deterministic simple incidence formula with degrees 2/3."""
    if (
        not isinstance(clause_count, int)
        or isinstance(clause_count, bool)
        or clause_count < 2
        or not isinstance(cubic_variables, int)
        or isinstance(cubic_variables, bool)
        or not 0 <= cubic_variables <= clause_count
        or (clause_count - cubic_variables) % 2
    ):
        raise AliasExactOneDecisionError("clause/cubic counts cannot realize degree-two/three incidence")
    degree_two = 3 * (clause_count - cubic_variables) // 2
    degrees = [3] * cubic_variables + [2] * degree_two
    variable_stubs = [
        variable
        for variable, degree in enumerate(degrees, 1)
        for _ in range(degree)
    ]
    clause_stubs = [clause for clause in range(clause_count) for _ in range(3)]
    rng = random.Random(seed)
    for _ in range(20_000):
        rng.shuffle(clause_stubs)
        clauses: list[list[int]] = [[] for _ in range(clause_count)]
        for variable, clause in zip(variable_stubs, clause_stubs):
            clauses[clause].append(variable)
        if any(len(set(clause)) != 3 for clause in clauses):
            continue
        normalized = tuple(sorted(tuple(sorted(clause)) for clause in clauses))
        if len(set(normalized)) != clause_count:
            continue
        return canonical_monotone_formula(normalized, variable_count=len(degrees))
    raise AliasExactOneDecisionError("could not construct a simple regular incidence formula")


@dataclass(frozen=True, slots=True)
class AliasExactOneProfile:
    clauses: int
    variables: int
    cubic_variables: int

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, int) or isinstance(value, bool)
            for value in (self.clauses, self.variables, self.cubic_variables)
        ):
            raise AliasExactOneDecisionError("profile values must be integers")
        if self.clauses < 1 or self.variables < 1 or not 0 <= self.cubic_variables <= self.variables:
            raise AliasExactOneDecisionError("alias profile values are invalid")
        if max(self.clauses, self.variables, self.cubic_variables) > _MAX_EXACT_FLOAT64_INTEGER:
            raise AliasExactOneDecisionError("profile exceeds exact float64 identifier range")
        if self.branch_count * max(1, self.clauses) ** 3 > _MAX_EXACT_FLOAT64_INTEGER:
            raise AliasExactOneDecisionError("profile exceeds exact float64 work-counter range")

    @property
    def branch_count(self) -> int:
        return 1 << self.cubic_variables

    @property
    def field_values(self) -> int:
        return _HEADER + 3 * self.clauses + 2 * self.variables + self.cubic_variables

    @property
    def field_bytes(self) -> int:
        return 8 * self.field_values

    @property
    def shape(self) -> tuple[int, int, int]:
        return 1, self.field_values, 1

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


@dataclass(frozen=True, slots=True)
class AliasExactOneState:
    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        field = np.asarray(self._field)
        if field.dtype != np.float64 or field.ndim != 3:
            raise AliasExactOneDecisionError("alias field must be rank-three float64")
        if field.flags.writeable:
            field = field.copy()
            field.setflags(write=False)
            object.__setattr__(self, "_field", field)

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


@dataclass(frozen=True, slots=True)
class _Layout:
    clauses: int
    degrees: int
    cubic_variables: int
    assignment: int
    total: int


def _layout(profile: AliasExactOneProfile) -> _Layout:
    clauses = _HEADER
    degrees = clauses + 3 * profile.clauses
    cubic = degrees + profile.variables
    assignment = cubic + profile.cubic_variables
    total = assignment + profile.variables
    return _Layout(clauses, degrees, cubic, assignment, total)


@dataclass(frozen=True, slots=True)
class _BranchResult:
    status: str
    reason: str
    branch: int
    cubic_bits: tuple[int, ...]
    residual_clauses: tuple[int, ...]
    matching: tuple[tuple[int, int, int], ...]
    barrier: tuple[int, ...]
    component_sizes: tuple[int, ...]
    conflict_clause: int | None
    assignment: tuple[int, ...] | None
    matching_runs: int
    barrier_matching_runs: int
    edge_scans: int
    contractions: int


def _satisfies(formula: Formula, assignment: Sequence[int]) -> bool:
    return all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula)


def _evaluate_branch(
    recognized: RecognizedAliasFormula,
    branch: int,
    *,
    with_barrier: bool,
) -> _BranchResult:
    cubic_bits = tuple(
        (branch >> index) & 1
        for index in range(len(recognized.cubic_variables))
    )
    cubic_value = dict(zip(recognized.cubic_variables, cubic_bits))
    true_counts = tuple(
        sum(cubic_value.get(variable, 0) for variable in clause)
        for clause in recognized.formula
    )
    conflict = next((index for index, count in enumerate(true_counts) if count > 1), None)
    if conflict is not None:
        return _BranchResult(
            "unsat",
            "clause-conflict",
            branch,
            cubic_bits,
            (),
            (),
            (),
            (),
            conflict,
            None,
            0,
            0,
            0,
            0,
        )
    residual = tuple(index for index, count in enumerate(true_counts) if count == 0)
    residual_set = set(residual)
    if len(residual) % 2:
        return _BranchResult(
            "unsat",
            "odd-residual",
            branch,
            cubic_bits,
            residual,
            (),
            (),
            (),
            None,
            None,
            0,
            0,
            0,
            0,
        )
    local_for = {clause: local for local, clause in enumerate(residual)}
    sources_for_pair: dict[tuple[int, int], list[int]] = {}
    for variable, degree in enumerate(recognized.degrees, 1):
        if degree != 2:
            continue
        incident = recognized.incidence[variable - 1]
        if all(clause in residual_set for clause in incident):
            pair = tuple(sorted((local_for[incident[0]], local_for[incident[1]])))
            sources_for_pair.setdefault((pair[0], pair[1]), []).append(variable)
    adjacency = [set() for _ in residual]
    for left, right in sources_for_pair:
        adjacency[left].add(right)
        adjacency[right].add(left)
    graph: Graph = tuple(tuple(sorted(neighbors)) for neighbors in adjacency)
    mates, scans, contractions = deterministic_maximum_matching(graph)
    pairs = tuple(
        (
            residual[local],
            residual[mate],
            min(sources_for_pair[(local, mate)]),
        )
        for local, mate in enumerate(mates)
        if mate != -1 and local < mate
    )
    if 2 * len(pairs) == len(residual):
        assignment = [0] * len(recognized.degrees)
        for variable, bit in cubic_value.items():
            assignment[variable - 1] = bit
        for _, _, variable in pairs:
            assignment[variable - 1] = 1
        if not _satisfies(recognized.formula, assignment):
            raise AliasExactOneDecisionError("residual perfect matching produced an invalid assignment")
        return _BranchResult(
            "sat",
            "perfect-matching",
            branch,
            cubic_bits,
            residual,
            pairs,
            (),
            (),
            None,
            tuple(assignment),
            1,
            0,
            scans,
            contractions,
        )
    barrier: tuple[int, ...] = ()
    sizes: tuple[int, ...] = ()
    barrier_runs = 0
    reason = "matching-failure"
    if with_barrier:
        selected, barrier_runs = deterministic_tutte_barrier(graph, len(pairs))
        barrier = tuple(residual[local] for local in sorted(selected))
        sizes = tuple(graph_component_sizes(graph, selected))
        reason = "tutte-barrier"
    return _BranchResult(
        "unsat",
        reason,
        branch,
        cubic_bits,
        residual,
        pairs,
        barrier,
        sizes,
        None,
        None,
        1,
        barrier_runs,
        scans,
        contractions,
    )


def _branch_witness(result: _BranchResult) -> dict[str, Any]:
    return {
        "branch": result.branch,
        "cubic_bits": list(result.cubic_bits),
        "status": result.status,
        "reason": result.reason,
        "residual_clauses": list(result.residual_clauses),
        "matching": [list(edge) for edge in result.matching],
        "conflict_clause": result.conflict_clause,
        "tutte_barrier": list(result.barrier) if result.reason == "tutte-barrier" else None,
        "component_sizes": list(result.component_sizes),
        "odd_components": sum(size % 2 for size in result.component_sizes),
        "deficiency": (
            sum(size % 2 for size in result.component_sizes) - len(result.barrier)
            if result.reason == "tutte-barrier"
            else 0
        ),
    }


class AliasExactOneDecisionField:
    """Immutable branch cursor over matching-solvable residual formulas."""

    def __init__(self, profile: AliasExactOneProfile) -> None:
        self.profile = profile
        self.layout = _layout(profile)
        if self.layout.total != profile.field_values:
            raise AliasExactOneDecisionError("internal alias field layout mismatch")

    def _flat(self, state: AliasExactOneState) -> np.ndarray:
        return state._field.reshape(-1)

    def _state(self, values: np.ndarray) -> AliasExactOneState:
        tensor = np.asarray(values, dtype=np.float64).reshape(self.profile.shape).copy()
        tensor.setflags(write=False)
        state = AliasExactOneState(tensor, self.profile.fingerprint)
        self.validate(state)
        return state

    def _recognized(self, values: np.ndarray) -> RecognizedAliasFormula:
        raw = values[self.layout.clauses : self.layout.degrees]
        formula = tuple(
            (int(raw[3 * index]), int(raw[3 * index + 1]), int(raw[3 * index + 2]))
            for index in range(self.profile.clauses)
        )
        return recognize_degree_two_three_exact_one(
            formula,
            variable_count=self.profile.variables,
        )

    @classmethod
    def initialize(
        cls,
        formula: Sequence[Sequence[int]],
        *,
        variable_count: int,
    ) -> tuple["AliasExactOneDecisionField", AliasExactOneState]:
        recognized = recognize_degree_two_three_exact_one(
            formula,
            variable_count=variable_count,
        )
        profile = AliasExactOneProfile(
            len(recognized.formula),
            variable_count,
            len(recognized.cubic_variables),
        )
        field = cls(profile)
        values = np.zeros(profile.field_values, dtype=np.float64)
        values[_H_MAGIC] = _MAGIC
        values[_H_VERSION] = _VERSION
        values[_H_STATUS] = _RUNNING
        values[_H_CLAUSES] = profile.clauses
        values[_H_VARIABLES] = profile.variables
        values[_H_CUBIC] = profile.cubic_variables
        values[_H_BRANCHES] = profile.branch_count
        values[_H_SELECTED_BRANCH] = -1
        values[field.layout.clauses : field.layout.degrees] = [
            variable for clause in recognized.formula for variable in clause
        ]
        values[field.layout.degrees : field.layout.cubic_variables] = recognized.degrees
        values[field.layout.cubic_variables : field.layout.assignment] = recognized.cubic_variables
        values[field.layout.assignment : field.layout.total] = -1
        return field, field._state(values)

    def validate(self, state: AliasExactOneState) -> None:
        if state.profile_sha256 != self.profile.fingerprint:
            raise AliasExactOneDecisionError("alias state/profile digest mismatch")
        if state._field.shape != self.profile.shape or not np.all(np.isfinite(state._field)):
            raise AliasExactOneDecisionError("alias field shape or finiteness mismatch")
        values = self._flat(state)
        if np.any(values != np.rint(values)):
            raise AliasExactOneDecisionError("alias field contains non-integer values")
        header = [int(value) for value in values[:_HEADER]]
        if (
            header[_H_MAGIC] != _MAGIC
            or header[_H_VERSION] != _VERSION
            or header[_H_STATUS] not in _STATUS_NAMES
            or header[_H_CLAUSES] != self.profile.clauses
            or header[_H_VARIABLES] != self.profile.variables
            or header[_H_CUBIC] != self.profile.cubic_variables
            or header[_H_BRANCHES] != self.profile.branch_count
        ):
            raise AliasExactOneDecisionError("alias field header mismatch")
        cursor = header[_H_CURSOR]
        if not 0 <= cursor <= self.profile.branch_count or header[_H_CHECKED] != cursor:
            raise AliasExactOneDecisionError("alias branch cursor is invalid")
        if any(header[index] < 0 for index in (_H_MATCHING_RUNS, _H_EDGE_SCANS, _H_CONTRACTIONS)):
            raise AliasExactOneDecisionError("alias work counter is invalid")
        recognized = self._recognized(values)
        if (
            recognized.degrees
            != tuple(int(value) for value in values[self.layout.degrees : self.layout.cubic_variables])
            or recognized.cubic_variables
            != tuple(int(value) for value in values[self.layout.cubic_variables : self.layout.assignment])
        ):
            raise AliasExactOneDecisionError("alias source metadata mismatch")
        assignment = values[self.layout.assignment : self.layout.total]
        status = header[_H_STATUS]
        selected = header[_H_SELECTED_BRANCH]
        if status == _RUNNING:
            if cursor == self.profile.branch_count or selected != -1 or np.any(assignment != -1):
                raise AliasExactOneDecisionError("running alias field has terminal data")
        elif status == _UNSAT:
            if cursor != self.profile.branch_count or selected != -1 or np.any(assignment != -1):
                raise AliasExactOneDecisionError("UNSAT alias field is incomplete")
        else:
            if not 0 <= selected < cursor or np.any((assignment != 0) & (assignment != 1)):
                raise AliasExactOneDecisionError("SAT alias field data is invalid")
            decoded = [int(value) for value in assignment]
            if not _satisfies(recognized.formula, decoded):
                raise AliasExactOneDecisionError("SAT alias field assignment fails source")
            for index, variable in enumerate(recognized.cubic_variables):
                if decoded[variable - 1] != ((selected >> index) & 1):
                    raise AliasExactOneDecisionError("SAT alias branch/assignment mismatch")

    def state_sha256(self, state: AliasExactOneState) -> str:
        self.validate(state)
        return hashlib.sha256(state._field.tobytes()).hexdigest()

    def _advance(self, values: np.ndarray, recognized: RecognizedAliasFormula) -> int:
        branch = int(values[_H_CURSOR])
        result = _evaluate_branch(recognized, branch, with_barrier=False)
        values[_H_CURSOR] = branch + 1
        values[_H_CHECKED] = branch + 1
        values[_H_MATCHING_RUNS] += result.matching_runs
        values[_H_EDGE_SCANS] += result.edge_scans
        values[_H_CONTRACTIONS] += result.contractions
        if result.status == "sat":
            values[_H_STATUS] = _SAT
            values[_H_SELECTED_BRANCH] = branch
            values[self.layout.assignment : self.layout.total] = result.assignment
        elif branch + 1 == self.profile.branch_count:
            values[_H_STATUS] = _UNSAT
        return branch

    def step(
        self,
        state: AliasExactOneState,
    ) -> tuple[AliasExactOneState, Mapping[str, Any]]:
        self.validate(state)
        before = self.state_sha256(state)
        source = self._flat(state)
        status = int(source[_H_STATUS])
        if status != _RUNNING:
            return state, {
                "schema": "cassifi.alias-exact-one-transition.v1",
                "action": "done",
                "status": _STATUS_NAMES[status],
                "previous_state_sha256": before,
                "state_sha256": before,
                "state_unchanged": True,
            }
        values = source.copy()
        branch = self._advance(values, self._recognized(values))
        successor = self._state(values)
        return successor, {
            "schema": "cassifi.alias-exact-one-transition.v1",
            "action": "evaluate-cubic-assignment",
            "branch": branch,
            "status": _STATUS_NAMES[int(values[_H_STATUS])],
            "previous_state_sha256": before,
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }

    def solve(
        self,
        state: AliasExactOneState,
    ) -> tuple[AliasExactOneState, Mapping[str, Any]]:
        self.validate(state)
        if int(self._flat(state)[_H_STATUS]) != _RUNNING:
            return state, self.certificate(state)
        values = self._flat(state).copy()
        recognized = self._recognized(values)
        while int(values[_H_STATUS]) == _RUNNING:
            self._advance(values, recognized)
        final = self._state(values)
        return final, self.certificate(final)

    def inspect(self, state: AliasExactOneState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        return {
            "status": _STATUS_NAMES[int(values[_H_STATUS])],
            "clauses": self.profile.clauses,
            "variables": self.profile.variables,
            "cubic_variables": self.profile.cubic_variables,
            "branches": self.profile.branch_count,
            "branches_checked": int(values[_H_CHECKED]),
            "matching_runs": int(values[_H_MATCHING_RUNS]),
            "edge_scans": int(values[_H_EDGE_SCANS]),
            "blossom_contractions": int(values[_H_CONTRACTIONS]),
            "selected_branch": int(values[_H_SELECTED_BRANCH]),
            "field_bytes": state.nbytes,
            "state_sha256": self.state_sha256(state),
        }

    def certificate(self, state: AliasExactOneState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        status = _STATUS_NAMES[int(values[_H_STATUS])]
        if status == "running":
            raise AliasExactOneDecisionError("running alias state has no certificate")
        recognized = self._recognized(values)
        proof_matching_runs = 0
        proof_barrier_runs = 0
        if status == "sat":
            selected = int(values[_H_SELECTED_BRANCH])
            result = _evaluate_branch(recognized, selected, with_barrier=True)
            if result.status != "sat" or result.assignment is None:
                raise AliasExactOneDecisionError("stored SAT branch no longer verifies")
            witnesses = [_branch_witness(result)]
            assignment: list[int] | None = list(result.assignment)
            proof_matching_runs = result.matching_runs
        else:
            results = [
                _evaluate_branch(recognized, branch, with_barrier=True)
                for branch in range(self.profile.branch_count)
            ]
            if any(result.status != "unsat" for result in results):
                raise AliasExactOneDecisionError("UNSAT state contains a satisfiable branch")
            witnesses = [_branch_witness(result) for result in results]
            assignment = None
            proof_matching_runs = sum(result.matching_runs for result in results)
            proof_barrier_runs = sum(result.barrier_matching_runs for result in results)
        certificate: dict[str, Any] = {
            "schema": SCHEMA,
            "status": status,
            "clauses": self.profile.clauses,
            "variables": self.profile.variables,
            "cubic_variables": list(recognized.cubic_variables),
            "branches": self.profile.branch_count,
            "formula": [list(clause) for clause in recognized.formula],
            "assignment": assignment,
            "branch_witnesses": witnesses,
            "branches_checked": int(values[_H_CHECKED]),
            "search_matching_runs": int(values[_H_MATCHING_RUNS]),
            "search_edge_scans": int(values[_H_EDGE_SCANS]),
            "search_blossom_contractions": int(values[_H_CONTRACTIONS]),
            "proof_matching_runs": proof_matching_runs,
            "proof_barrier_matching_runs": proof_barrier_runs,
            "field_values": self.profile.field_values,
            "field_bytes": state.nbytes,
            "problem_sha256": hashlib.sha256(_canonical(recognized.formula)).hexdigest(),
            "profile_sha256": self.profile.fingerprint,
            "state_sha256": self.state_sha256(state),
        }
        certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
        return certificate

    def descriptor(self, state: AliasExactOneState) -> dict[str, Any]:
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
    ) -> tuple["AliasExactOneDecisionField", AliasExactOneState]:
        if value.get("schema") != STATE_SCHEMA:
            raise AliasExactOneDecisionError("unsupported alias field descriptor")
        profile_value = value.get("profile")
        if not isinstance(profile_value, Mapping) or set(profile_value) != {
            "clauses",
            "variables",
            "cubic_variables",
        }:
            raise AliasExactOneDecisionError("alias descriptor profile is invalid")
        profile_items = tuple(
            profile_value[key]
            for key in ("clauses", "variables", "cubic_variables")
        )
        if any(
            not isinstance(item, int) or isinstance(item, bool)
            for item in profile_items
        ):
            raise AliasExactOneDecisionError("alias descriptor profile is invalid")
        try:
            profile = AliasExactOneProfile(*profile_items)
        except ValueError as exc:
            raise AliasExactOneDecisionError("alias descriptor profile is invalid") from exc
        field = cls(profile)
        if value.get("profile_sha256") != profile.fingerprint:
            raise AliasExactOneDecisionError("alias profile digest mismatch")
        encoded = value.get("field_b64")
        if not isinstance(encoded, str):
            raise AliasExactOneDecisionError("alias field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            tensor = np.frombuffer(raw, dtype=np.float64).reshape(profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise AliasExactOneDecisionError("alias field encoding is invalid") from exc
        if value.get("state_sha256") != hashlib.sha256(raw).hexdigest():
            raise AliasExactOneDecisionError("alias state digest mismatch")
        return field, field._state(tensor)

_REGIONAL_STATE_KEYS = frozenset(
    {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
)
_REGIONAL_SOURCE_KEYS = frozenset(
    {"formula", "variable_count", "degrees", "cubic_variables", "incidence"}
)
_REGIONAL_PROFILE_KEYS = frozenset(
    {"clauses", "variables", "cubic_variables"}
)

def _regional_integer(
    value: Any,
    name: str,
    *,
    minimum: int = 0,
    maximum: int = _MAX_EXACT_FLOAT64_INTEGER,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise AliasExactOneDecisionError(f"{name} must be an exact bounded integer")
    return value


def _regional_source(recognized: RecognizedAliasFormula, variable_count: int) -> dict[str, Any]:
    return {
        "formula": [list(clause) for clause in recognized.formula],
        "variable_count": int(variable_count),
        "degrees": list(recognized.degrees),
        "cubic_variables": list(recognized.cubic_variables),
        "incidence": [list(rows) for rows in recognized.incidence],
    }


def _regional_recognized(source: Mapping[str, Any]) -> RecognizedAliasFormula:
    if not isinstance(source, Mapping) or set(source) != _REGIONAL_SOURCE_KEYS:
        raise AliasExactOneDecisionError("regional alias source is invalid")
    variable_count = _regional_integer(
        source["variable_count"], "regional alias variable count", minimum=1
    )
    formula_value = source["formula"]
    if not isinstance(formula_value, list):
        raise AliasExactOneDecisionError("regional alias formula is invalid")
    recognized = recognize_degree_two_three_exact_one(
        formula_value,
        variable_count=variable_count,
    )
    expected = _regional_source(recognized, variable_count)
    if dict(source) != expected:
        raise AliasExactOneDecisionError("regional alias source is not normalized")
    return recognized


def _regional_native_values(
    source: Mapping[str, Any],
    *,
    cursor: int,
    selected_branch: int | None,
    assignment: Sequence[int] | None,
    status: str,
    ledger: Mapping[str, Any],
) -> tuple[AliasExactOneProfile, np.ndarray]:
    recognized = _regional_recognized(source)
    profile = AliasExactOneProfile(
        len(recognized.formula),
        int(source["variable_count"]),
        len(recognized.cubic_variables),
    )
    field = np.zeros(profile.field_values, dtype=np.float64)
    field[_H_MAGIC] = _MAGIC
    field[_H_VERSION] = _VERSION
    field[_H_STATUS] = {"running": _RUNNING, "sat": _SAT, "unsat": _UNSAT}[status]
    field[_H_CLAUSES] = profile.clauses
    field[_H_VARIABLES] = profile.variables
    field[_H_CUBIC] = profile.cubic_variables
    field[_H_CURSOR] = cursor
    field[_H_BRANCHES] = profile.branch_count
    field[_H_CHECKED] = cursor
    field[_H_MATCHING_RUNS] = int(ledger["matching_runs"])
    field[_H_EDGE_SCANS] = int(ledger["edge_scans"])
    field[_H_CONTRACTIONS] = int(ledger["blossom_contractions"])
    field[_H_SELECTED_BRANCH] = -1 if selected_branch is None else selected_branch
    layout = _layout(profile)
    field[layout.clauses : layout.degrees] = [
        variable for clause in recognized.formula for variable in clause
    ]
    field[layout.degrees : layout.cubic_variables] = recognized.degrees
    field[layout.cubic_variables : layout.assignment] = recognized.cubic_variables
    field[layout.assignment : layout.total] = (
        [-1] * profile.variables if assignment is None else list(assignment)
    )
    return profile, field


def _regional_terminal_tensor(
    state: Mapping[str, Any],
    *,
    status: str,
    selected_branch: int | None,
    assignment: Sequence[int] | None,
) -> dict[str, Any]:
    profile, field = _regional_native_values(
        state["source"],
        cursor=state["continuation"]["cursor"],
        selected_branch=selected_branch,
        assignment=assignment,
        status=status,
        ledger=state["ledger"],
    )
    return {
        "shape": list(profile.shape),
        "field_values": profile.field_values,
        "state_sha256": hashlib.sha256(field.tobytes()).hexdigest(),
    }




def _regional_certificate(state: Mapping[str, Any]) -> dict[str, Any]:
    source = state["source"]
    recognized = _regional_recognized(source)
    result = state["result"]
    status = result["status"]
    if status not in {"sat", "unsat"}:
        raise AliasExactOneDecisionError("regional alias state has no native certificate")
    profile, field = _regional_native_values(
        source,
        cursor=state["continuation"]["cursor"],
        selected_branch=result["selected_branch"],
        assignment=result["assignment"],
        status=status,
        ledger=state["ledger"],
    )
    journal = state["journal"]
    if status == "sat":
        selected = int(result["selected_branch"])
        witnesses = [
            witness
            for witness in journal["branch_witnesses"]
            if int(witness["branch"]) == selected
        ]
        if len(witnesses) != 1:
            raise AliasExactOneDecisionError("regional SAT evidence is incomplete")
        assignment: list[int] | None = list(result["assignment"])
        proof_matching_runs = int(journal["terminal_proof"]["matching_runs"])
        proof_barrier_runs = int(journal["terminal_proof"]["barrier_matching_runs"])
    else:
        witnesses = list(journal["branch_witnesses"])
        assignment = None
        proof_matching_runs = int(journal["terminal_proof"]["matching_runs"])
        proof_barrier_runs = int(journal["terminal_proof"]["barrier_matching_runs"])
    certificate: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "clauses": profile.clauses,
        "variables": profile.variables,
        "cubic_variables": list(recognized.cubic_variables),
        "branches": profile.branch_count,
        "formula": [list(clause) for clause in recognized.formula],
        "assignment": assignment,
        "branch_witnesses": witnesses,
        "branches_checked": int(state["continuation"]["cursor"]),
        "search_matching_runs": int(state["ledger"]["matching_runs"]),
        "search_edge_scans": int(state["ledger"]["edge_scans"]),
        "search_blossom_contractions": int(state["ledger"]["blossom_contractions"]),
        "proof_matching_runs": proof_matching_runs,
        "proof_barrier_matching_runs": proof_barrier_runs,
        "field_values": profile.field_values,
        "field_bytes": int(field.nbytes),
        "problem_sha256": hashlib.sha256(_canonical(recognized.formula)).hexdigest(),
        "profile_sha256": profile.fingerprint,
        "state_sha256": hashlib.sha256(field.tobytes()).hexdigest(),
    }
    certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
    return certificate


def _validate_regional_state(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping) or set(state) != _REGIONAL_STATE_KEYS:
        raise AliasExactOneDecisionError("regional alias state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise AliasExactOneDecisionError("regional alias state schema is invalid")
    recognized = _regional_recognized(state["source"])
    profile = AliasExactOneProfile(
        len(recognized.formula),
        int(state["source"]["variable_count"]),
        len(recognized.cubic_variables),
    )
    expected_profile = {
        "clauses": profile.clauses,
        "variables": profile.variables,
        "cubic_variables": profile.cubic_variables,
    }
    if not isinstance(state["profile"], Mapping) or set(state["profile"]) != _REGIONAL_PROFILE_KEYS:
        raise AliasExactOneDecisionError("regional alias profile is invalid")
    if dict(state["profile"]) != expected_profile:
        raise AliasExactOneDecisionError("regional alias profile mismatch")
    continuation = state["continuation"]
    journal = state["journal"]
    ledger = state["ledger"]
    result = state["result"]
    if (
        not isinstance(continuation, Mapping)
        or set(continuation) != {"cursor", "branches_total"}
        or not isinstance(journal, Mapping)
        or set(journal) != {"branch_witnesses", "branch_work", "terminal_proof"}
        or not isinstance(journal["branch_work"], list)
        or not isinstance(ledger, Mapping)
        or set(ledger) != {
            "work",
            "matching_runs",
            "barrier_matching_runs",
            "edge_scans",
            "blossom_contractions",
        }
        or not isinstance(result, Mapping)
        or set(result)
        != {"status", "selected_branch", "assignment", "reason", "outcome", "terminal_tensor"}
    ):
        raise AliasExactOneDecisionError("regional alias continuation is invalid")
    cursor = _regional_integer(
        continuation["cursor"],
        "regional alias cursor",
        maximum=profile.branch_count,
    )
    if continuation["branches_total"] != profile.branch_count:
        raise AliasExactOneDecisionError("regional alias branch count mismatch")
    for key in (
        "work",
        "matching_runs",
        "barrier_matching_runs",
        "edge_scans",
        "blossom_contractions",
    ):
        _regional_integer(ledger[key], f"regional alias {key}")
    if ledger["work"] != cursor:
        raise AliasExactOneDecisionError("regional alias cumulative work mismatch")
    if not isinstance(journal["branch_witnesses"], list):
        raise AliasExactOneDecisionError("regional alias branch evidence is invalid")
    if (
        len(journal["branch_witnesses"]) != cursor
        or len(journal["branch_work"]) != cursor
    ):
        raise AliasExactOneDecisionError("regional alias branch evidence is incomplete")
    for branch, witness in enumerate(journal["branch_witnesses"]):
        if not isinstance(witness, Mapping) or int(witness.get("branch", -1)) != branch:
            raise AliasExactOneDecisionError("regional alias branch evidence is unordered")
    for item in journal["branch_work"]:
        if not isinstance(item, Mapping) or set(item) != {
            "matching_runs",
            "barrier_matching_runs",
        }:
            raise AliasExactOneDecisionError("regional alias branch work is invalid")
        _regional_integer(item["matching_runs"], "regional alias branch matching runs")
        _regional_integer(
            item["barrier_matching_runs"],
            "regional alias branch barrier runs",
        )
    expected_matching = sum(item["matching_runs"] for item in journal["branch_work"])
    expected_barrier = sum(
        item["barrier_matching_runs"] for item in journal["branch_work"]
    )
    if ledger["matching_runs"] != expected_matching:
        raise AliasExactOneDecisionError("regional alias matching ledger mismatch")
    if ledger["barrier_matching_runs"] != expected_barrier:
        raise AliasExactOneDecisionError("regional alias barrier ledger mismatch")
    proof = journal["terminal_proof"]
    if not isinstance(proof, Mapping) or set(proof) != {
        "matching_runs",
        "barrier_matching_runs",
    }:
        raise AliasExactOneDecisionError("regional alias proof evidence is invalid")
    _regional_integer(proof["matching_runs"], "regional alias proof matching runs")
    _regional_integer(
        proof["barrier_matching_runs"],
        "regional alias proof barrier runs",
    )
    status = result["status"]
    if status not in {"running", "sat", "unsat", "fault"}:
        raise AliasExactOneDecisionError("regional alias result status is invalid")
    phase = state["phase"]
    if phase not in {"enumerating", "terminal"}:
        raise AliasExactOneDecisionError("regional alias phase is invalid")
    if status == "running":
        if (
            phase != "enumerating"
            or cursor >= profile.branch_count
            or result["outcome"] is not None
            or result["terminal_tensor"] is not None
            or result["selected_branch"] is not None
            or result["assignment"] is not None
        ):
            raise AliasExactOneDecisionError("regional alias running state is invalid")
        if proof != {
            "matching_runs": ledger["matching_runs"],
            "barrier_matching_runs": ledger["barrier_matching_runs"],
        }:
            raise AliasExactOneDecisionError("regional alias running proof mismatch")
    elif status in {"sat", "unsat"}:
        if phase != "terminal" or not isinstance(result["outcome"], Mapping):
            raise AliasExactOneDecisionError("regional alias terminal outcome is invalid")
        assignment = result["assignment"]
        if status == "sat":
            selected = _regional_integer(
                result["selected_branch"],
                "regional alias selected branch",
                maximum=cursor - 1,
            )
            if not isinstance(assignment, list) or len(assignment) != profile.variables:
                raise AliasExactOneDecisionError("regional alias assignment is invalid")
            if any(value not in (0, 1) for value in assignment):
                raise AliasExactOneDecisionError("regional alias assignment is invalid")
            if not _satisfies(recognized.formula, assignment):
                raise AliasExactOneDecisionError("regional alias assignment fails source")
            expected_work = journal["branch_work"][selected]
            if proof != expected_work:
                raise AliasExactOneDecisionError("regional alias SAT proof mismatch")
        else:
            if cursor != profile.branch_count or result["selected_branch"] is not None:
                raise AliasExactOneDecisionError("regional alias UNSAT state is incomplete")
            if assignment is not None:
                raise AliasExactOneDecisionError("regional alias UNSAT state has assignment")
            expected_work = {
                "matching_runs": ledger["matching_runs"],
                "barrier_matching_runs": ledger["barrier_matching_runs"],
            }
            if proof != expected_work:
                raise AliasExactOneDecisionError("regional alias UNSAT proof mismatch")
        if result["outcome"] != _regional_certificate(state):
            raise AliasExactOneDecisionError("regional alias terminal certificate mismatch")
        expected_tensor = _regional_terminal_tensor(
            state,
            status=status,
            selected_branch=result["selected_branch"],
            assignment=assignment,
        )
        if result["terminal_tensor"] != expected_tensor:
            raise AliasExactOneDecisionError("regional alias terminal tensor mismatch")
    else:
        if (
            phase != "terminal"
            or not isinstance(result["outcome"], Mapping)
            or result["terminal_tensor"] is not None
            or proof
            != {
                "matching_runs": ledger["matching_runs"],
                "barrier_matching_runs": ledger["barrier_matching_runs"],
            }
        ):
            raise AliasExactOneDecisionError("regional alias fault outcome is invalid")


def regional_state(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> dict[str, Any]:
    """Encode one normalized exact-one instance for the v3 regional computer."""
    recognized = recognize_degree_two_three_exact_one(
        formula,
        variable_count=variable_count,
    )
    profile = AliasExactOneProfile(
        len(recognized.formula),
        variable_count,
        len(recognized.cubic_variables),
    )
    if profile.branch_count > _MAX_EXACT_FLOAT64_INTEGER:
        raise AliasExactOneDecisionError("regional alias branch count exceeds exact range")
    state: dict[str, Any] = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": _regional_source(recognized, variable_count),
        "profile": asdict(profile),
        "phase": "enumerating",
        "continuation": {"cursor": 0, "branches_total": profile.branch_count},
        "journal": {
            "branch_witnesses": [],
            "branch_work": [],
            "terminal_proof": {"matching_runs": 0, "barrier_matching_runs": 0},
        },
        "ledger": {
            "work": 0,
            "matching_runs": 0,
            "barrier_matching_runs": 0,
            "edge_scans": 0,
            "blossom_contractions": 0,
        },
        "result": {
            "status": "running",
            "selected_branch": None,
            "assignment": None,
            "reason": None,
            "outcome": None,
            "terminal_tensor": None,
        },
    }
    _validate_regional_state(state)
    return state


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance exact alias enumeration by at most ``quantum`` cubic candidates."""
    if not isinstance(state, Mapping):
        raise AliasExactOneDecisionError("regional alias state must be a mapping")
    _validate_regional_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise AliasExactOneDecisionError("regional alias kernel takes no arguments")
    quantum = _regional_integer(
        quantum,
        "regional alias quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    if state["phase"] == "terminal":
        status = state["result"]["status"]
        kernel_status = "fault" if status == "fault" else "done"
        return KernelResult(
            state=dict(state),
            status=kernel_status,
            work=0,
            output=state["result"]["outcome"],
        )
    successor = copy.deepcopy(dict(state))
    recognized = _regional_recognized(successor["source"])
    steps = 0
    while steps < quantum and successor["result"]["status"] == "running":
        branch = int(successor["continuation"]["cursor"])
        try:
            branch_result = _evaluate_branch(recognized, branch, with_barrier=True)
        except AliasExactOneDecisionError as exc:
            successor["phase"] = "terminal"
            successor["result"] = {
                "status": "fault",
                "selected_branch": None,
                "assignment": None,
                "reason": str(exc),
                "outcome": {
                    "schema": "cassifi.alias-exact-one-regional-fault.v1",
                    "family": "alias-exact-one",
                    "status": "fault",
                    "reason": str(exc),
                    "branch": branch,
                },
                "terminal_tensor": None,
            }
            break
        successor["journal"]["branch_witnesses"].append(_branch_witness(branch_result))
        successor["journal"]["branch_work"].append(
            {
                "matching_runs": branch_result.matching_runs,
                "barrier_matching_runs": branch_result.barrier_matching_runs,
            }
        )
        successor["continuation"]["cursor"] = branch + 1
        successor["ledger"]["work"] += 1
        successor["ledger"]["matching_runs"] += branch_result.matching_runs
        successor["ledger"]["barrier_matching_runs"] += branch_result.barrier_matching_runs
        successor["ledger"]["edge_scans"] += branch_result.edge_scans
        successor["ledger"]["blossom_contractions"] += branch_result.contractions
        successor["journal"]["terminal_proof"] = {
            "matching_runs": successor["ledger"]["matching_runs"],
            "barrier_matching_runs": successor["ledger"]["barrier_matching_runs"],
        }
        steps += 1
        if branch_result.status == "sat":
            successor["phase"] = "terminal"
            successor["result"] = {
                "status": "sat",
                "selected_branch": branch,
                "assignment": list(branch_result.assignment or ()),
                "reason": branch_result.reason,
                "outcome": None,
                "terminal_tensor": None,
            }
            successor["journal"]["terminal_proof"] = {
                "matching_runs": branch_result.matching_runs,
                "barrier_matching_runs": branch_result.barrier_matching_runs,
            }
            successor["result"]["terminal_tensor"] = _regional_terminal_tensor(
                successor,
                status="sat",
                selected_branch=branch,
                assignment=successor["result"]["assignment"],
            )
            successor["result"]["outcome"] = _regional_certificate(successor)
        elif branch + 1 == successor["continuation"]["branches_total"]:
            successor["phase"] = "terminal"
            successor["result"] = {
                "status": "unsat",
                "selected_branch": None,
                "assignment": None,
                "reason": "all-cubic-branches-refuted",
                "outcome": None,
                "terminal_tensor": None,
            }
            successor["result"]["terminal_tensor"] = _regional_terminal_tensor(
                successor,
                status="unsat",
                selected_branch=None,
                assignment=None,
            )
            successor["result"]["outcome"] = _regional_certificate(successor)
    _validate_regional_state(successor)
    terminal_status = successor["result"]["status"]
    if terminal_status == "running":
        return KernelResult(state=successor, status="yield", work=steps, output=None)
    if terminal_status == "fault":
        return KernelResult(
            state=successor,
            status="fault",
            work=steps,
            output=successor["result"]["outcome"],
        )
    return KernelResult(
        state=successor,
        status="done",
        work=steps,
        output=successor["result"]["outcome"],
    )



__all__ = [
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "regional_state",
    "regional_kernel",
]
