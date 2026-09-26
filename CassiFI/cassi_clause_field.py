"""A uniform, immutable SAT search state in CassiFI field coordinates.

The problem, provisional assignment, search stack, and learned conflict clauses
all live in one exact-integer float64 tensor with the Cassi ``[S, 9*M, B]``
shape.  The controller is fixed deterministic machinery: repeated ``step``
calls choose and apply the next field-derived operation.  There is no external
candidate generator, adaptive side table, recursion stack, or model fallback.

This module implements a sound polynomial-space DPLL baseline.  It deliberately
does not claim polynomial running time.  Its stored resource ledger counts
field transitions, clause and literal inspections, writes, conflicts, learned
clauses, decisions, propagation, and backtracking.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

SCHEMA = "cassifi.clause-field.v2"
_LAYOUT = "clause-dpll-nine-plane-v2"
_MAGIC = 0xC551
_SAFE_INTEGER = 2**53 - 1

# Nine field planes. Every adaptive or provisional value is stored here.
_CLAUSE_LENGTHS = 0
_CLAUSE_LITERALS = 1
_ASSIGNMENTS = 2
_LEVELS = 3
_REASONS = 4
_TRAIL = 5
_DECISION_LITERALS = 6
_DECISION_PHASES = 7
_HEADER = 8

# Header coordinates in plane 8.
_H_MAGIC = 0
_H_VARIABLES = 1
_H_ORIGINAL_CLAUSES = 2
_H_TOTAL_CLAUSES = 3
_H_STATUS = 4
_H_DECISION_DEPTH = 5
_H_TRAIL_COUNT = 6
_H_TRANSITIONS = 7
_H_DECISIONS = 8
_H_PROPAGATIONS = 9
_H_CONFLICTS = 10
_H_BACKTRACKS = 11
_H_LEARNED_CLAUSES = 12
_H_CLAUSE_SCANS = 13
_H_LITERAL_SCANS = 14
_H_ASSIGNMENT_WRITES = 15
_H_CLAUSE_WRITES = 16
_H_PEAK_TRAIL = 17
_H_PEAK_DEPTH = 18
_H_PROOF_RESOLUTIONS = 19
_H_PROOF_LITERAL_SCANS = 20
_H_COUNT = 21

_RUNNING = 0
_SAT = 1
_UNSAT = 2
_EXHAUSTED = 3
_STATUS_NAMES = {
    _RUNNING: "running",
    _SAT: "sat",
    _UNSAT: "unsat",
    _EXHAUSTED: "exhausted",
}

_COUNTER_HEADERS = (
    _H_TRANSITIONS,
    _H_DECISIONS,
    _H_PROPAGATIONS,
    _H_CONFLICTS,
    _H_BACKTRACKS,
    _H_LEARNED_CLAUSES,
    _H_CLAUSE_SCANS,
    _H_LITERAL_SCANS,
    _H_ASSIGNMENT_WRITES,
    _H_CLAUSE_WRITES,
    _H_PEAK_TRAIL,
    _H_PEAK_DEPTH,
    _H_PROOF_RESOLUTIONS,
    _H_PROOF_LITERAL_SCANS,
)


class ClauseFieldError(ValueError):
    """Invalid clause-field profile, state, or operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _exact_integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > _SAFE_INTEGER:
        raise ClauseFieldError(f"{name} must be an exact bounded integer")
    return value


@dataclass(frozen=True, slots=True)
class ClauseFieldProfile:
    """Fixed storage and work geometry; it contains no problem-dependent state."""

    max_variables: int
    max_original_clauses: int
    max_clause_width: int
    max_learned_clauses: int
    max_transitions: int = 1_000_000

    def __post_init__(self) -> None:
        for name in (
            "max_variables",
            "max_original_clauses",
            "max_clause_width",
            "max_transitions",
        ):
            _exact_integer(getattr(self, name), name, minimum=1)
        _exact_integer(self.max_learned_clauses, "max_learned_clauses")
        if self.max_clause_width < self.max_variables:
            raise ClauseFieldError(
                "max_clause_width must hold a decision nogood over every variable"
            )
        if self.mode_count * 9 > _SAFE_INTEGER:
            raise ClauseFieldError("clause field exceeds exact address capacity")

    @property
    def max_total_clauses(self) -> int:
        return self.max_original_clauses + self.max_learned_clauses

    @property
    def literal_capacity(self) -> int:
        return self.max_total_clauses * self.max_clause_width

    @property
    def mode_count(self) -> int:
        return max(
            _H_COUNT,
            self.max_variables,
            self.max_total_clauses,
            self.literal_capacity,
        )

    @property
    def shape(self) -> tuple[int, int, int]:
        return (1, 9 * self.mode_count, 1)

    @property
    def state_bytes(self) -> int:
        return math.prod(self.shape) * np.dtype(np.float64).itemsize

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical({"layout": _LAYOUT, **asdict(self)})).hexdigest()

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ClauseFieldState:
    """One immutable field tensor bound to a fixed profile fingerprint."""

    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise ClauseFieldError("clause field must be a float64 numpy tensor")
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64:
            raise ClauseFieldError("state profile fingerprint is invalid")
        field = np.array(self._field, dtype=np.float64, copy=True, order="C")
        field.flags.writeable = False
        object.__setattr__(self, "_field", field)

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


@dataclass(slots=True)
class _StepLedger:
    clause_scans: int = 0
    literal_scans: int = 0
    assignment_writes: int = 0
    clause_writes: int = 0
    proof_resolutions: int = 0
    proof_literal_scans: int = 0


@dataclass(frozen=True, slots=True)
class _Analysis:
    conflict_clause: int | None
    unit_literal: int | None
    unit_clause: int | None
    all_satisfied: bool
    positive_activity: np.ndarray
    negative_activity: np.ndarray


class ClauseField:
    """Fixed transition law for a polynomial-space field-owned DPLL search."""

    def __init__(self, profile: ClauseFieldProfile) -> None:
        if not isinstance(profile, ClauseFieldProfile):
            raise ClauseFieldError("ClauseFieldProfile required")
        self.profile = profile

    def _parts(self, state: ClauseFieldState, *, validate: bool = True) -> np.ndarray:
        if not isinstance(state, ClauseFieldState):
            raise ClauseFieldError("ClauseFieldState required")
        if state.profile_sha256 != self.profile.fingerprint:
            raise ClauseFieldError("state belongs to a different clause-field profile")
        if tuple(state._field.shape) != self.profile.shape:
            raise ClauseFieldError("clause field has an invalid shape")
        if validate:
            self.validate(state)
        return state._field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]

    @staticmethod
    def _normalize_clause(clause: Sequence[int], variables: int) -> tuple[int, ...]:
        if isinstance(clause, (str, bytes)) or not isinstance(clause, Sequence):
            raise ClauseFieldError("each clause must be an ordered literal sequence")
        seen: set[int] = set()
        result: list[int] = []
        tautology = False
        for raw in clause:
            if isinstance(raw, bool) or not isinstance(raw, int) or raw == 0 or abs(raw) > variables:
                raise ClauseFieldError("clause literal is outside the declared variables")
            if -raw in seen:
                tautology = True
            if raw not in seen:
                seen.add(raw)
                result.append(raw)
        return () if tautology else tuple(result)

    def initial(
        self,
        clauses: Sequence[Sequence[int]],
        *,
        variable_count: int,
    ) -> ClauseFieldState:
        variables = _exact_integer(variable_count, "variable_count", minimum=1)
        if variables > self.profile.max_variables:
            raise ClauseFieldError("variable count exceeds profile capacity")
        if isinstance(clauses, (str, bytes)) or not isinstance(clauses, Sequence):
            raise ClauseFieldError("clauses must be an ordered sequence")
        normalized: list[tuple[int, ...]] = []
        for clause in clauses:
            row = self._normalize_clause(clause, variables)
            if row == () and len(clause) > 0:
                # A tautology imposes no constraint and has no field record.
                continue
            if len(row) > self.profile.max_clause_width:
                raise ClauseFieldError("clause width exceeds profile capacity")
            normalized.append(row)
        if len(normalized) > self.profile.max_original_clauses:
            raise ClauseFieldError("original clause count exceeds profile capacity")

        raw = np.zeros(self.profile.shape, dtype=np.float64)
        parts = raw.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        header = parts[_HEADER]
        header[_H_MAGIC] = _MAGIC
        header[_H_VARIABLES] = variables
        header[_H_ORIGINAL_CLAUSES] = len(normalized)
        header[_H_TOTAL_CLAUSES] = len(normalized)
        for index, clause in enumerate(normalized):
            self._write_clause(parts, index, clause, None)
        state = ClauseFieldState(raw, self.profile.fingerprint)
        self.validate(state)
        return state

    def _clause(self, parts: np.ndarray, index: int) -> tuple[int, ...]:
        length = int(parts[_CLAUSE_LENGTHS, index])
        start = index * self.profile.max_clause_width
        return tuple(int(value) for value in parts[_CLAUSE_LITERALS, start : start + length])

    def clauses(self, state: ClauseFieldState, *, learned: bool | None = None) -> tuple[tuple[int, ...], ...]:
        parts = self._parts(state)
        header = parts[_HEADER]
        original = int(header[_H_ORIGINAL_CLAUSES])
        total = int(header[_H_TOTAL_CLAUSES])
        if learned is True:
            selected = range(original, total)
        elif learned is False:
            selected = range(original)
        else:
            selected = range(total)
        return tuple(self._clause(parts, index) for index in selected)

    def assignment(self, state: ClauseFieldState) -> tuple[int, ...]:
        parts = self._parts(state)
        variables = int(parts[_HEADER, _H_VARIABLES])
        return tuple(int(value) for value in parts[_ASSIGNMENTS, :variables])

    def decision_context(self, state: ClauseFieldState) -> dict[str, Any]:
        """Transient search summary for external schedulers.

        The returned mapping is derived from the field on demand and is never
        persisted; it reports the pending transition class, the current
        assignment, per-variable occurrence activity, and the eligible set.
        """
        parts = self._parts(state)
        status = int(parts[_HEADER, _H_STATUS])
        if status != _RUNNING:
            raise ClauseFieldError("decision context requires a running field")
        ledger = _StepLedger()
        analysis = self._analyze(parts, ledger)
        if analysis.conflict_clause is not None:
            pending = "conflict"
        elif analysis.unit_literal is not None:
            pending = "unit"
        elif analysis.all_satisfied:
            pending = "sat"
        else:
            pending = "decide"
        variables = int(parts[_HEADER, _H_VARIABLES])
        return {
            "schema": "cassifi.clause-field-context.v1",
            "pending": pending,
            "assignment": [int(value) for value in parts[_ASSIGNMENTS, :variables]],
            "positive": [int(value) for value in analysis.positive_activity],
            "negative": [int(value) for value in analysis.negative_activity],
            "eligible": [int(value) == 0 for value in parts[_ASSIGNMENTS, :variables]],
            "work": {
                "clause_scans": ledger.clause_scans,
                "literal_scans": ledger.literal_scans,
            },
        }

    def _write_clause(
        self,
        parts: np.ndarray,
        index: int,
        clause: Sequence[int],
        ledger: _StepLedger | None,
    ) -> None:
        parts[_CLAUSE_LENGTHS, index] = len(clause)
        start = index * self.profile.max_clause_width
        parts[_CLAUSE_LITERALS, start : start + self.profile.max_clause_width] = 0
        if clause:
            parts[_CLAUSE_LITERALS, start : start + len(clause)] = clause
        if ledger is not None:
            ledger.clause_writes += 1 + len(clause)

    def _state(self, parts: np.ndarray) -> ClauseFieldState:
        state = ClauseFieldState(
            parts.reshape(self.profile.shape),
            self.profile.fingerprint,
        )
        self.validate(state)
        return state

    def state_sha256(self, state: ClauseFieldState) -> str:
        parts = self._parts(state)
        del parts
        digest = hashlib.sha256(
            _canonical(
                {
                    "layout": _LAYOUT,
                    "profile_sha256": self.profile.fingerprint,
                    "shape": self.profile.shape,
                }
            )
        )
        digest.update(state._field)
        return digest.hexdigest()

    def _satisfies(self, clauses: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
        return all(
            any(assignment[abs(literal) - 1] == (1 if literal > 0 else -1) for literal in clause)
            for clause in clauses
        )

    def validate(self, state: ClauseFieldState) -> None:
        if not isinstance(state, ClauseFieldState):
            raise ClauseFieldError("state belongs to a different clause-field profile")
        if state.profile_sha256 != self.profile.fingerprint:
            raise ClauseFieldError("state belongs to a different clause-field profile")
        field = state._field
        if tuple(field.shape) != self.profile.shape or field.dtype != np.float64:
            raise ClauseFieldError("clause field has an invalid shape or dtype")

        # Check finite and integer constraints
        if not np.isfinite(field).all() or not np.equal(field, np.floor(field)).all():
            raise ClauseFieldError("clause field must contain finite exact integers")

        # Check range constraint using vectorized comparison
        if np.any(np.abs(field) > _SAFE_INTEGER):
            raise ClauseFieldError("clause field exceeds exact float64 integer range")

        # Reshape once
        parts = field.reshape(1, 9, self.profile.mode_count, 1)[0, :, :, 0]
        header = parts[_HEADER]

        # Header checks
        if int(header[_H_MAGIC]) != _MAGIC:
            raise ClauseFieldError("clause field magic is invalid")

        variables = int(header[_H_VARIABLES])
        original = int(header[_H_ORIGINAL_CLAUSES])
        total = int(header[_H_TOTAL_CLAUSES])
        status = int(header[_H_STATUS])
        depth = int(header[_H_DECISION_DEPTH])
        trail_count = int(header[_H_TRAIL_COUNT])

        # Variable count check
        if not 1 <= variables <= self.profile.max_variables:
            raise ClauseFieldError("stored variable count is invalid")

        # Original clause count check
        if not 0 <= original <= self.profile.max_original_clauses:
            raise ClauseFieldError("stored original clause count is invalid")

        # Total clause count check
        if not original <= total <= original + self.profile.max_learned_clauses:
            raise ClauseFieldError("stored total clause count is invalid")

        # Status check
        if status not in _STATUS_NAMES:
            raise ClauseFieldError("stored solver status is invalid")

        # Depth and trail count checks
        if not 0 <= depth <= variables or not 0 <= trail_count <= variables:
            raise ClauseFieldError("stored search depth or trail count is invalid")

        # Resource counters non-negative check
        # _COUNTER_HEADERS likely includes indices like _H_DECISION_DEPTH, _H_TRAIL_COUNT, etc.
        # Assuming _COUNTER_HEADERS is a sequence of indices into header that must be >= 0
        # We can check this efficiently
        counter_headers = (_H_DECISION_DEPTH, _H_TRAIL_COUNT, _H_TRANSITIONS, _H_DECISIONS, 
                           _H_PROPAGATIONS, _H_CONFLICTS, _H_BACKTRACKS, _H_LEARNED_CLAUSES,
                           _H_CLAUSE_SCANS, _H_LITERAL_SCANS, _H_ASSIGNMENT_WRITES, 
                           _H_CLAUSE_WRITES, _H_PEAK_TRAIL, _H_PEAK_DEPTH, _H_PROOF_RESOLUTIONS,
                           _H_PROOF_LITERAL_SCANS)
        if any(header[idx] < 0 for idx in counter_headers):
            raise ClauseFieldError("resource counters cannot be negative")

        # Transition counter check
        if int(header[_H_TRANSITIONS]) > self.profile.max_transitions:
            raise ClauseFieldError("transition counter exceeds the profile bound")

        # Learned clauses check
        if int(header[_H_LEARNED_CLAUSES]) != total - original:
            raise ClauseFieldError("learned-clause counter disagrees with field storage")

        # Clause lengths check
        lengths = parts[_CLAUSE_LENGTHS]
        if np.any(lengths[:total] < 0) or np.any(lengths[:total] > self.profile.max_clause_width):
            raise ClauseFieldError("stored clause length is invalid")
        if np.any(lengths[total:] != 0):
            raise ClauseFieldError("unused clause lengths must be zero")

        # Clause literals check
        literals = parts[_CLAUSE_LITERALS]
        max_clause_width = self.profile.max_clause_width
        variables_int = variables

        # Pre-calculate slice ranges to avoid repeated computation in loop
        # We iterate through clauses
        for clause_index in range(total):
            length = int(lengths[clause_index])
            start = clause_index * max_clause_width
            active = literals[start : start + length]
            padding = literals[start + length : start + max_clause_width]

            # Check active literals: no zeros, no abs > variables
            # Check padding: all zeros
            if np.any(active == 0) or np.any(np.abs(active) > variables_int) or np.any(padding != 0):
                raise ClauseFieldError("stored clause literals are invalid")

            # Check uniqueness and tautology
            # Convert to tuple of ints for set operations
            values = tuple(int(value) for value in active)
            if len(values) != len(set(values)) or any(-value in values for value in values):
                raise ClauseFieldError("stored clause is duplicate or tautological")

        # Literal padding check
        if np.any(literals[self.profile.literal_capacity :] != 0):
            raise ClauseFieldError("literal padding outside capacity must be zero")

        # Assignments, Levels, Reasons checks
        assignments = parts[_ASSIGNMENTS, :variables]
        levels = parts[_LEVELS, :variables]
        reasons = parts[_REASONS, :variables]

        # Assignments must be -1, 0, or 1
        # Using np.isin is slow, use boolean mask instead
        if np.any((assignments != -1) & (assignments != 0) & (assignments != 1)):
            raise ClauseFieldError("stored assignments must be -1, 0, or 1")

        # Levels check
        if np.any(levels < 0) or np.any(levels > depth):
            raise ClauseFieldError("stored decision level is invalid")

        # Reasons check
        if np.any(reasons < 0) or np.any(reasons > total):
            raise ClauseFieldError("stored implication reason is invalid")

        # Unassigned variables cannot have level or reason
        if np.any((assignments == 0) & ((levels != 0) | (reasons != 0))):
            raise ClauseFieldError("unassigned variables cannot retain level or reason")

        # Padding checks for assignments, levels, reasons
        if np.any(parts[_ASSIGNMENTS, variables:] != 0) or np.any(parts[_LEVELS, variables:] != 0) or np.any(parts[_REASONS, variables:] != 0):
            raise ClauseFieldError("variable padding must be zero")

        # Trail check
        trail = parts[_TRAIL]
        active_trail = tuple(int(value) for value in trail[:trail_count])

        # Check trail values are within 1..variables and unique
        if any(not 1 <= value <= variables_int for value in active_trail) or len(set(active_trail)) != len(active_trail):
            raise ClauseFieldError("stored trail is invalid")

        # Trail padding check
        if np.any(trail[trail_count:] != 0):
            raise ClauseFieldError("trail padding must be zero")

        # Assignment vs Trail consistency
        assigned_variables = {index + 1 for index, value in enumerate(assignments) if value != 0}
        if assigned_variables != set(active_trail):
            raise ClauseFieldError("trail and assignment planes disagree")

        # Decision literals and phases checks
        decisions = parts[_DECISION_LITERALS]
        phases = parts[_DECISION_PHASES]

        # Active decision frames
        if np.any(decisions[:depth] == 0) or np.any(np.abs(decisions[:depth]) > variables_int):
            raise ClauseFieldError("active decision frames are invalid")

        # Active decision phases must be 1 or 2
        if np.any((phases[:depth] != 1) & (phases[:depth] != 2)):
            raise ClauseFieldError("active decision phases are invalid")

        # Inactive decision frames must be zero
        if np.any(decisions[depth:] != 0) or np.any(phases[depth:] != 0):
            raise ClauseFieldError("inactive decision frames must be zero")

        # Decision stack uniqueness
        if len(set(abs(int(value)) for value in decisions[:depth])) != depth:
            raise ClauseFieldError("decision stack repeats a variable")

        # Decision frame consistency
        for level, literal_value in enumerate(decisions[:depth], 1):
            variable = abs(int(literal_value)) - 1
            expected = 1 if literal_value > 0 else -1
            if assignments[variable] != expected or levels[variable] != level or reasons[variable] != 0:
                raise ClauseFieldError("decision frame does not match its assignment")

        # SAT status check
        if status == _SAT:
            full_assignment = tuple(int(value) for value in assignments)
            if 0 in full_assignment or not self._satisfies(
                tuple(self._clause(parts, index) for index in range(original)),
                full_assignment,
            ):
                raise ClauseFieldError("SAT status lacks a complete satisfying assignment")

        # Padding checks for all planes
        for plane in range(9):
            if plane in (_CLAUSE_LITERALS,):
                used = self.profile.literal_capacity
            elif plane in (_CLAUSE_LENGTHS,):
                used = self.profile.max_total_clauses
            elif plane in (_ASSIGNMENTS, _LEVELS, _REASONS, _TRAIL, _DECISION_LITERALS, _DECISION_PHASES):
                used = variables
            else:
                used = _H_COUNT
            if np.any(parts[plane, used:] != 0):
                raise ClauseFieldError("field plane contains noncanonical padding")

    def _analyze(self, parts: np.ndarray, ledger: _StepLedger) -> _Analysis:
        header = parts[_HEADER]
        variables = int(header[_H_VARIABLES])
        total = int(header[_H_TOTAL_CLAUSES])
        assignments = parts[_ASSIGNMENTS]
        positive = np.zeros(variables, dtype=np.int64)
        negative = np.zeros(variables, dtype=np.int64)
        unit_literal: int | None = None
        unit_clause: int | None = None
        all_satisfied = True
        for clause_index in range(total):
            ledger.clause_scans += 1
            clause = self._clause(parts, clause_index)
            satisfied = False
            unassigned: list[int] = []
            for literal in clause:
                ledger.literal_scans += 1
                value = int(assignments[abs(literal) - 1])
                if value == (1 if literal > 0 else -1):
                    satisfied = True
                elif value == 0:
                    unassigned.append(literal)
            if satisfied:
                continue
            all_satisfied = False
            if not unassigned:
                return _Analysis(
                    clause_index,
                    None,
                    None,
                    False,
                    positive,
                    negative,
                )
            for literal in unassigned:
                if literal > 0:
                    positive[literal - 1] += 1
                else:
                    negative[-literal - 1] += 1
            if len(unassigned) == 1 and unit_literal is None:
                unit_literal = unassigned[0]
                unit_clause = clause_index
        return _Analysis(None, unit_literal, unit_clause, all_satisfied, positive, negative)

    def _append_assignment(
        self,
        parts: np.ndarray,
        literal: int,
        *,
        level: int,
        reason: int,
        ledger: _StepLedger,
    ) -> None:
        variable = abs(literal) - 1
        assignments = parts[_ASSIGNMENTS]
        value = 1 if literal > 0 else -1
        current = int(assignments[variable])
        if current == value:
            return
        if current != 0:
            raise ClauseFieldError("fixed transition attempted a contradictory direct assignment")
        header = parts[_HEADER]
        trail_count = int(header[_H_TRAIL_COUNT])
        if trail_count >= int(header[_H_VARIABLES]):
            raise ClauseFieldError("assignment trail exceeds variable capacity")
        assignments[variable] = value
        parts[_LEVELS, variable] = level
        parts[_REASONS, variable] = reason
        parts[_TRAIL, trail_count] = variable + 1
        header[_H_TRAIL_COUNT] = trail_count + 1
        header[_H_PEAK_TRAIL] = max(int(header[_H_PEAK_TRAIL]), trail_count + 1)
        ledger.assignment_writes += 4

    @staticmethod
    def _resolve_clauses(
        left: Sequence[int],
        right: Sequence[int],
        pivot: int,
    ) -> tuple[int, ...]:
        left_polarity = 1 if pivot in left else -1 if -pivot in left else 0
        right_polarity = 1 if pivot in right else -1 if -pivot in right else 0
        if left_polarity == 0 or right_polarity != -left_polarity:
            raise ClauseFieldError("resolution premises do not contain a complementary pivot")
        result: set[int] = set()
        for literal in (*left, *right):
            if abs(literal) == pivot:
                continue
            if -literal in result:
                raise ClauseFieldError("resolution produced a tautological clause")
            result.add(int(literal))
        return tuple(sorted(result, key=lambda literal: (abs(literal), literal < 0)))

    def _conflict_proof(
        self,
        parts: np.ndarray,
        conflict_clause: int,
        ledger: _StepLedger,
    ) -> dict[str, Any]:
        header = parts[_HEADER]
        depth = int(header[_H_DECISION_DEPTH])
        decisions = tuple(int(value) for value in parts[_DECISION_LITERALS, :depth])
        nogood = tuple(-literal for literal in decisions)
        current = self._clause(parts, conflict_clause)
        steps: list[dict[str, Any]] = []
        trail_count = int(header[_H_TRAIL_COUNT])
        reasons = parts[_REASONS]
        for stored_variable in reversed(parts[_TRAIL, :trail_count]):
            pivot = int(stored_variable)
            if not any(abs(literal) == pivot for literal in current):
                continue
            reason_clause_id = int(reasons[pivot - 1])
            if reason_clause_id == 0:
                continue
            reason_clause = self._clause(parts, reason_clause_id - 1)
            ledger.proof_resolutions += 1
            ledger.proof_literal_scans += len(current) + len(reason_clause)
            current = self._resolve_clauses(current, reason_clause, pivot)
            steps.append(
                {
                    "pivot": pivot,
                    "reason_clause_id": reason_clause_id,
                    "resolvent": list(current),
                }
            )
        for literal in current:
            if int(reasons[abs(literal) - 1]) != 0:
                raise ClauseFieldError("conflict proof retained a propagated literal")
        if not set(current).issubset(set(nogood)):
            raise ClauseFieldError("conflict core is not contained in the decision nogood")
        ledger.proof_literal_scans += len(current) + len(nogood)
        return {
            "schema": "cassifi.clause-field-conflict-proof.v1",
            "decision_literals": list(decisions),
            "conflict_clause_id": conflict_clause + 1,
            "resolution_steps": steps,
            "core_clause": list(current),
            "nogood_clause": list(nogood),
        }

    def _learn_decision_nogood(
        self,
        parts: np.ndarray,
        ledger: _StepLedger,
    ) -> tuple[tuple[int, ...], int | None, bool, str]:
        header = parts[_HEADER]
        depth = int(header[_H_DECISION_DEPTH])
        clause = tuple(-int(value) for value in parts[_DECISION_LITERALS, :depth])
        if depth == 0:
            return clause, None, False, "root"
        original = int(header[_H_ORIGINAL_CLAUSES])
        total = int(header[_H_TOTAL_CLAUSES])
        for index in range(total):
            if self._clause(parts, index) == clause:
                return clause, index + 1, False, "duplicate"
        if total >= original + self.profile.max_learned_clauses:
            return clause, None, False, "capacity"
        self._write_clause(parts, total, clause, ledger)
        header[_H_TOTAL_CLAUSES] = total + 1
        header[_H_LEARNED_CLAUSES] = total + 1 - original
        return clause, total + 1, True, "added"

    def _backtrack_and_flip(self, parts: np.ndarray, ledger: _StepLedger) -> int | None:
        header = parts[_HEADER]
        depth = int(header[_H_DECISION_DEPTH])
        target = depth
        while target > 0 and int(parts[_DECISION_PHASES, target - 1]) == 2:
            target -= 1
        if target == 0:
            return None
        previous = int(parts[_DECISION_LITERALS, target - 1])

        assignments = parts[_ASSIGNMENTS]
        levels = parts[_LEVELS]
        reasons = parts[_REASONS]
        variables = int(header[_H_VARIABLES])
        removed = {index for index in range(variables) if int(levels[index]) >= target}
        for variable in removed:
            assignments[variable] = 0
            levels[variable] = 0
            reasons[variable] = 0
            ledger.assignment_writes += 3

        trail_count = int(header[_H_TRAIL_COUNT])
        retained = [
            int(value)
            for value in parts[_TRAIL, :trail_count]
            if int(value) - 1 not in removed
        ]
        parts[_TRAIL, :trail_count] = 0
        if retained:
            parts[_TRAIL, : len(retained)] = retained
        header[_H_TRAIL_COUNT] = len(retained)
        ledger.assignment_writes += trail_count + len(retained) + 1

        parts[_DECISION_LITERALS, target:depth] = 0
        parts[_DECISION_PHASES, target:depth] = 0
        flipped = -previous
        parts[_DECISION_LITERALS, target - 1] = flipped
        parts[_DECISION_PHASES, target - 1] = 2
        header[_H_DECISION_DEPTH] = target
        self._append_assignment(
            parts,
            flipped,
            level=target,
            reason=0,
            ledger=ledger,
        )
        return flipped

    def step(
        self,
        state: ClauseFieldState,
        *,
        decision_literal: int | None = None,
        propagation_only: bool = False,
    ) -> tuple[ClauseFieldState, Mapping[str, Any]]:
        """Advance the fixed transition law once.

        ``decision_literal`` optionally selects the next branching literal when
        this transition would decide; it is ignored when the transition resolves
        a conflict, propagates a unit, or completes a satisfying assignment.
        ``propagation_only`` forbids branching, reporting ``stalled`` and an
        ``exhausted`` status instead.  Both default to the historical behavior.
        """
        if not isinstance(propagation_only, bool):
            raise ClauseFieldError("propagation_only must be a boolean")
        if decision_literal is not None:
            if propagation_only:
                raise ClauseFieldError("decision override conflicts with a propagation-only step")
            if isinstance(decision_literal, bool) or not isinstance(decision_literal, int):
                raise ClauseFieldError("decision override must be an exact integer literal")
            if decision_literal == 0:
                raise ClauseFieldError("decision override must be a nonzero literal")
        before_sha256 = self.state_sha256(state)
        immutable_parts = self._parts(state)
        status = int(immutable_parts[_HEADER, _H_STATUS])
        if decision_literal is not None:
            variables = int(immutable_parts[_HEADER, _H_VARIABLES])
            if abs(decision_literal) > variables:
                raise ClauseFieldError("decision override exceeds the variable count")
            if int(immutable_parts[_ASSIGNMENTS, abs(decision_literal) - 1]) != 0:
                raise ClauseFieldError("decision override targets an assigned variable")
        if status != _RUNNING:
            return state, {
                "schema": "cassifi.clause-field-step.v1",
                "action": "terminal",
                "status": _STATUS_NAMES[status],
                "previous_state_sha256": before_sha256,
                "state_sha256": before_sha256,
                "state_unchanged": True,
            }

        parts = immutable_parts.copy()
        header = parts[_HEADER]
        if int(header[_H_TRANSITIONS]) >= self.profile.max_transitions:
            header[_H_STATUS] = _EXHAUSTED
            successor = self._state(parts)
            return successor, {
                "schema": "cassifi.clause-field-step.v1",
                "action": "exhaust",
                "status": "exhausted",
                "previous_state_sha256": before_sha256,
                "state_sha256": self.state_sha256(successor),
                "state_unchanged": False,
            }

        ledger = _StepLedger()
        analysis = self._analyze(parts, ledger)
        action = ""
        selected_literal: int | None = None
        conflict_clause: int | None = analysis.conflict_clause
        learned_clause: tuple[int, ...] | None = None
        conflict_proof: dict[str, Any] | None = None

        if analysis.conflict_clause is not None:
            action = "conflict-backtrack"
            header[_H_CONFLICTS] += 1
            conflict_proof = self._conflict_proof(
                parts,
                analysis.conflict_clause,
                ledger,
            )
            nogood, stored_clause_id, stored_new, learning_status = (
                self._learn_decision_nogood(parts, ledger)
            )
            conflict_proof.update(
                {
                    "stored_clause_id": stored_clause_id,
                    "stored_new": stored_new,
                    "learning_status": learning_status,
                }
            )
            learned_clause = nogood if stored_new else None
            flipped = self._backtrack_and_flip(parts, ledger)
            if flipped is None:
                header[_H_STATUS] = _UNSAT
                action = "unsat"
            else:
                selected_literal = flipped
                header[_H_BACKTRACKS] += 1
        elif analysis.unit_literal is not None:
            assert analysis.unit_clause is not None
            action = "propagate"
            selected_literal = analysis.unit_literal
            self._append_assignment(
                parts,
                selected_literal,
                level=int(header[_H_DECISION_DEPTH]),
                reason=analysis.unit_clause + 1,
                ledger=ledger,
            )
            header[_H_PROPAGATIONS] += 1
        elif analysis.all_satisfied:
            action = "sat"
            variables = int(header[_H_VARIABLES])
            for variable in range(variables):
                if int(parts[_ASSIGNMENTS, variable]) == 0:
                    self._append_assignment(
                        parts,
                        -(variable + 1),
                        level=int(header[_H_DECISION_DEPTH]),
                        reason=0,
                        ledger=ledger,
                    )
            header[_H_STATUS] = _SAT
        elif propagation_only:
            action = "stalled"
            header[_H_STATUS] = _EXHAUSTED
        else:
            action = "decide"
            unassigned = np.flatnonzero(parts[_ASSIGNMENTS, : int(header[_H_VARIABLES])] == 0)
            if not len(unassigned):
                raise ClauseFieldError("complete assignment was neither SAT nor conflicting")
            if decision_literal is not None:
                selected_literal = decision_literal
            else:
                activities = analysis.positive_activity + analysis.negative_activity
                best_activity = int(np.max(activities[unassigned]))
                variable = int(next(index for index in unassigned if activities[index] == best_activity))
                selected_literal = (
                    variable + 1
                    if analysis.positive_activity[variable] > analysis.negative_activity[variable]
                    else -(variable + 1)
                )
            depth = int(header[_H_DECISION_DEPTH]) + 1
            parts[_DECISION_LITERALS, depth - 1] = selected_literal
            parts[_DECISION_PHASES, depth - 1] = 1
            header[_H_DECISION_DEPTH] = depth
            header[_H_PEAK_DEPTH] = max(int(header[_H_PEAK_DEPTH]), depth)
            self._append_assignment(
                parts,
                selected_literal,
                level=depth,
                reason=0,
                ledger=ledger,
            )
            header[_H_DECISIONS] += 1

        header[_H_TRANSITIONS] += 1
        header[_H_CLAUSE_SCANS] += ledger.clause_scans
        header[_H_LITERAL_SCANS] += ledger.literal_scans
        header[_H_ASSIGNMENT_WRITES] += ledger.assignment_writes
        header[_H_CLAUSE_WRITES] += ledger.clause_writes
        header[_H_PROOF_RESOLUTIONS] += ledger.proof_resolutions
        header[_H_PROOF_LITERAL_SCANS] += ledger.proof_literal_scans
        successor = self._state(parts)
        result = {
            "schema": "cassifi.clause-field-step.v1",
            "action": action,
            "status": _STATUS_NAMES[int(parts[_HEADER, _H_STATUS])],
            "selected_literal": selected_literal,
            "conflict_clause": conflict_clause,
            "learned_clause": None if learned_clause is None else list(learned_clause),
            "conflict_proof": conflict_proof,
            "work": {
                "clause_scans": ledger.clause_scans,
                "literal_scans": ledger.literal_scans,
                "assignment_writes": ledger.assignment_writes,
                "clause_writes": ledger.clause_writes,
                "proof_resolutions": ledger.proof_resolutions,
                "proof_literal_scans": ledger.proof_literal_scans,
            },
            "previous_state_sha256": before_sha256,
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }
        return successor, result

    def solve(self, state: ClauseFieldState) -> tuple[ClauseFieldState, Mapping[str, Any]]:
        current = state
        initial_sha256 = self.state_sha256(state)
        while self.status(current) == "running":
            current, _ = self.step(current)
        return current, {
            "schema": "cassifi.clause-field-solve.v1",
            "initial_state_sha256": initial_sha256,
            "state_sha256": self.state_sha256(current),
            **self.inspect(current),
        }

    def status(self, state: ClauseFieldState) -> str:
        parts = self._parts(state)
        return _STATUS_NAMES[int(parts[_HEADER, _H_STATUS])]

    def inspect(self, state: ClauseFieldState) -> dict[str, Any]:
        parts = self._parts(state)
        header = parts[_HEADER]
        original = int(header[_H_ORIGINAL_CLAUSES])
        total = int(header[_H_TOTAL_CLAUSES])
        variables = int(header[_H_VARIABLES])
        return {
            "status": _STATUS_NAMES[int(header[_H_STATUS])],
            "variables": variables,
            "original_clauses": original,
            "total_clauses": total,
            "assignment": [int(value) for value in parts[_ASSIGNMENTS, :variables]],
            "decision_depth": int(header[_H_DECISION_DEPTH]),
            "trail_count": int(header[_H_TRAIL_COUNT]),
            "field_bytes": state.nbytes,
            "profile_sha256": self.profile.fingerprint,
            "resource_ledger": {
                "transitions": int(header[_H_TRANSITIONS]),
                "decisions": int(header[_H_DECISIONS]),
                "propagations": int(header[_H_PROPAGATIONS]),
                "conflicts": int(header[_H_CONFLICTS]),
                "backtracks": int(header[_H_BACKTRACKS]),
                "learned_clauses": int(header[_H_LEARNED_CLAUSES]),
                "clause_scans": int(header[_H_CLAUSE_SCANS]),
                "literal_scans": int(header[_H_LITERAL_SCANS]),
                "assignment_writes": int(header[_H_ASSIGNMENT_WRITES]),
                "clause_writes": int(header[_H_CLAUSE_WRITES]),
                "peak_trail": int(header[_H_PEAK_TRAIL]),
                "peak_decision_depth": int(header[_H_PEAK_DEPTH]),
                "proof_resolutions": int(header[_H_PROOF_RESOLUTIONS]),
                "proof_literal_scans": int(header[_H_PROOF_LITERAL_SCANS]),
            },
        }

    def descriptor(self, state: ClauseFieldState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": SCHEMA,
            "layout": _LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "field_b64": base64.b64encode(state._field).decode("ascii"),
            "state_sha256": self.state_sha256(state),
        }

    @classmethod
    def from_descriptor(cls, value: Mapping[str, Any]) -> tuple[ClauseField, ClauseFieldState]:
        required = {
            "schema",
            "layout",
            "profile",
            "profile_sha256",
            "field_b64",
            "state_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ClauseFieldError("invalid clause-field descriptor keys")
        if value["schema"] != SCHEMA or value["layout"] != _LAYOUT:
            raise ClauseFieldError("unsupported clause-field descriptor")
        if not isinstance(value["profile"], Mapping):
            raise ClauseFieldError("descriptor profile is invalid")
        try:
            profile = ClauseFieldProfile(**dict(value["profile"]))
        except (TypeError, ClauseFieldError) as exc:
            raise ClauseFieldError("descriptor profile is invalid") from exc
        controller = cls(profile)
        if value["profile_sha256"] != profile.fingerprint:
            raise ClauseFieldError("descriptor profile digest mismatch")
        encoded = value["field_b64"]
        if not isinstance(encoded, str):
            raise ClauseFieldError("descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            field = np.frombuffer(raw, dtype=np.float64).reshape(profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise ClauseFieldError("descriptor field encoding is invalid") from exc
        state = ClauseFieldState(field, profile.fingerprint)
        controller.validate(state)
        if value["state_sha256"] != controller.state_sha256(state):
            raise ClauseFieldError("descriptor state digest mismatch")
        return controller, state


REGIONAL_KERNEL_NAME = "exact.clause"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-clause-state.v1"


def _regional_profile(
    value: ClauseFieldProfile | Mapping[str, Any] | None,
    *,
    variables: int,
    clause_count: int,
) -> ClauseFieldProfile:
    if value is None:
        return ClauseFieldProfile(
            max_variables=variables,
            max_original_clauses=max(1, clause_count),
            max_clause_width=variables,
            max_learned_clauses=4 * variables,
        )
    if isinstance(value, ClauseFieldProfile):
        return value
    if isinstance(value, Mapping):
        try:
            return ClauseFieldProfile(**dict(value))
        except (TypeError, ClauseFieldError) as exc:
            raise ClauseFieldError("regional clause profile is invalid") from exc
    raise ClauseFieldError("regional clause profile is invalid")


def _regional_frontier(continuation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "status": continuation["status"],
        "decision_depth": len(continuation["decision_literals"]),
        "trail_count": len(continuation["trail"]),
        "total_clauses": len(continuation["clauses"]),
    }


def _regional_ledger() -> dict[str, int]:
    return {
        "transitions": 0,
        "decisions": 0,
        "propagations": 0,
        "conflicts": 0,
        "backtracks": 0,
        "learned_clauses": 0,
        "clause_scans": 0,
        "literal_scans": 0,
        "assignment_writes": 0,
        "clause_writes": 0,
        "peak_trail": 0,
        "peak_decision_depth": 0,
        "proof_resolutions": 0,
        "proof_literal_scans": 0,
    }


def _regional_normalized_source(
    clauses: Sequence[Sequence[int]],
    *,
    variables: int,
    profile: ClauseFieldProfile,
) -> list[list[int]]:
    normalized: list[list[int]] = []
    for clause in clauses:
        row = ClauseField._normalize_clause(clause, variables)
        if row == () and len(clause) > 0:
            continue
        if len(row) > profile.max_clause_width:
            raise ClauseFieldError("clause width exceeds profile capacity")
        normalized.append(list(row))
    if len(normalized) > profile.max_original_clauses:
        raise ClauseFieldError("original clause count exceeds profile capacity")
    return normalized


def _regional_resolve(
    left: Sequence[int],
    right: Sequence[int],
    pivot: int,
) -> tuple[int, ...]:
    left_polarity = 1 if pivot in left else -1 if -pivot in left else 0
    right_polarity = 1 if pivot in right else -1 if -pivot in right else 0
    if left_polarity == 0 or right_polarity != -left_polarity:
        raise ClauseFieldError("resolution premises do not contain a complementary pivot")
    result: set[int] = set()
    for literal in (*left, *right):
        if abs(literal) == pivot:
            continue
        if -literal in result:
            raise ClauseFieldError("resolution produced a tautological clause")
        result.add(int(literal))
    return tuple(sorted(result, key=lambda literal: (abs(literal), literal < 0)))


def _regional_certificate(
    conflicts: Sequence[Mapping[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    closure_steps: list[dict[str, Any]] = []
    root_line: int | None = None
    closure_literal_scans = 0
    if status == "unsat":
        if not conflicts:
            raise ClauseFieldError("UNSAT result has no conflict proof")
        root: dict[str, Any] = {"leaf": None, "children": {}}
        for leaf_line, proof in enumerate(conflicts, 1):
            decisions = tuple(int(value) for value in proof["decision_literals"])
            nogood = tuple(int(value) for value in proof["nogood_clause"])
            if nogood != tuple(-literal for literal in decisions):
                raise ClauseFieldError(
                    "conflict proof does not conclude its decision nogood"
                )
            node = root
            for literal in decisions:
                if node["leaf"] is not None:
                    raise ClauseFieldError("a closed decision prefix has descendants")
                children = node["children"]
                node = children.setdefault(
                    literal, {"leaf": None, "children": {}}
                )
            if node["leaf"] is not None or node["children"]:
                raise ClauseFieldError("duplicate or prefix-overlapping conflict leaf")
            node["leaf"] = leaf_line

        def close(
            node: Mapping[str, Any], prefix: tuple[int, ...]
        ) -> tuple[int, tuple[int, ...]]:
            nonlocal closure_literal_scans
            leaf = node["leaf"]
            children = node["children"]
            if leaf is not None:
                if children:
                    raise ClauseFieldError("proof leaf also has children")
                clause = tuple(
                    int(value) for value in conflicts[int(leaf) - 1]["nogood_clause"]
                )
                if set(clause) != {-literal for literal in prefix}:
                    raise ClauseFieldError(
                        "proof leaf is not the current decision nogood"
                    )
                return int(leaf), clause
            branch_literals = tuple(int(value) for value in children)
            if (
                len(branch_literals) != 2
                or branch_literals[0] != -branch_literals[1]
            ):
                raise ClauseFieldError(
                    "UNSAT search tree is not closed on both decision branches"
                )
            left_line, left_clause = close(
                children[branch_literals[0]], prefix + (branch_literals[0],)
            )
            right_line, right_clause = close(
                children[branch_literals[1]], prefix + (branch_literals[1],)
            )
            pivot = abs(branch_literals[0])
            resolvent = _regional_resolve(left_clause, right_clause, pivot)
            if set(resolvent) != {-literal for literal in prefix}:
                raise ClauseFieldError("branch closure did not derive the parent nogood")
            closure_literal_scans += len(left_clause) + len(right_clause)
            line_id = len(conflicts) + len(closure_steps) + 1
            closure_steps.append(
                {
                    "line_id": line_id,
                    "left_line": left_line,
                    "right_line": right_line,
                    "pivot": pivot,
                    "resolvent": list(resolvent),
                }
            )
            return line_id, resolvent

        root_line, root_clause = close(root, ())
        if root_clause:
            raise ClauseFieldError("UNSAT closure did not derive the empty clause")

    payload = {
        "schema": "cassifi.dpll-wresolution-proof.v1",
        "proof_system": (
            "chronological DPLL resolution DAG with linear conflict derivations, "
            "weakening to decision nogoods, lemma reuse, and a depth-first "
            "branch-closure tree"
        ),
        "conflict_derivations": [dict(proof) for proof in conflicts],
        "closure_steps": closure_steps,
        "root_line": root_line,
    }
    leaf_resolutions = sum(len(proof["resolution_steps"]) for proof in conflicts)
    leaf_weakenings = sum(
        set(proof["core_clause"]) != set(proof["nogood_clause"])
        for proof in conflicts
    )
    return {
        **payload,
        "stats": {
            "conflict_derivations": len(conflicts),
            "leaf_resolution_steps": leaf_resolutions,
            "leaf_weakenings": leaf_weakenings,
            "closure_resolution_steps": len(closure_steps),
            "inference_steps": leaf_resolutions + leaf_weakenings + len(closure_steps),
            "closure_literal_scans": closure_literal_scans,
            "max_core_width": max(
                (len(proof["core_clause"]) for proof in conflicts), default=0
            ),
            "max_nogood_width": max(
                (len(proof["nogood_clause"]) for proof in conflicts), default=0
            ),
            "payload_json_bytes": len(_canonical(payload)),
        },
    }


def _regional_analyze(
    continuation: Mapping[str, Any],
    step_ledger: dict[str, int],
) -> tuple[int | None, int | None, int | None, bool, list[int], list[int]]:
    assignments = continuation["assignments"]
    positive = [0] * len(assignments)
    negative = [0] * len(assignments)
    unit_literal: int | None = None
    unit_clause: int | None = None
    all_satisfied = True
    for clause_index, clause in enumerate(continuation["clauses"]):
        step_ledger["clause_scans"] += 1
        satisfied = False
        unassigned: list[int] = []
        for literal in clause:
            step_ledger["literal_scans"] += 1
            value = int(assignments[abs(literal) - 1])
            if value == (1 if literal > 0 else -1):
                satisfied = True
            elif value == 0:
                unassigned.append(literal)
        if satisfied:
            continue
        all_satisfied = False
        if not unassigned:
            return clause_index, None, None, False, positive, negative
        for literal in unassigned:
            if literal > 0:
                positive[literal - 1] += 1
            else:
                negative[-literal - 1] += 1
        if len(unassigned) == 1 and unit_literal is None:
            unit_literal = unassigned[0]
            unit_clause = clause_index
    return None, unit_literal, unit_clause, all_satisfied, positive, negative


def _regional_append_assignment(
    continuation: dict[str, Any],
    literal: int,
    *,
    level: int,
    reason: int,
    step_ledger: dict[str, int],
) -> None:
    variable = abs(literal) - 1
    assignments = continuation["assignments"]
    value = 1 if literal > 0 else -1
    current = int(assignments[variable])
    if current == value:
        return
    if current != 0:
        raise ClauseFieldError("fixed transition attempted a contradictory direct assignment")
    if len(continuation["trail"]) >= len(assignments):
        raise ClauseFieldError("assignment trail exceeds variable capacity")
    assignments[variable] = value
    continuation["levels"][variable] = level
    continuation["reasons"][variable] = reason
    continuation["trail"].append(variable + 1)
    step_ledger["assignment_writes"] += 4


def _regional_conflict_proof(
    continuation: Mapping[str, Any],
    conflict_clause: int,
    step_ledger: dict[str, int],
) -> dict[str, Any]:
    decisions = tuple(int(value) for value in continuation["decision_literals"])
    nogood = tuple(-literal for literal in decisions)
    current = tuple(continuation["clauses"][conflict_clause])
    steps: list[dict[str, Any]] = []
    reasons = continuation["reasons"]
    for stored_variable in reversed(continuation["trail"]):
        pivot = int(stored_variable)
        if not any(abs(literal) == pivot for literal in current):
            continue
        reason_clause_id = int(reasons[pivot - 1])
        if reason_clause_id == 0:
            continue
        reason_clause = tuple(continuation["clauses"][reason_clause_id - 1])
        step_ledger["proof_resolutions"] += 1
        step_ledger["proof_literal_scans"] += len(current) + len(reason_clause)
        current = _regional_resolve(current, reason_clause, pivot)
        steps.append(
            {
                "pivot": pivot,
                "reason_clause_id": reason_clause_id,
                "resolvent": list(current),
            }
        )
    for literal in current:
        if int(reasons[abs(literal) - 1]) != 0:
            raise ClauseFieldError("conflict proof retained a propagated literal")
    if not set(current).issubset(set(nogood)):
        raise ClauseFieldError("conflict core is not contained in the decision nogood")
    step_ledger["proof_literal_scans"] += len(current) + len(nogood)
    return {
        "schema": "cassifi.clause-field-conflict-proof.v1",
        "decision_literals": list(decisions),
        "conflict_clause_id": conflict_clause + 1,
        "resolution_steps": steps,
        "core_clause": list(current),
        "nogood_clause": list(nogood),
    }


def _regional_learn_nogood(
    continuation: dict[str, Any],
    profile: ClauseFieldProfile,
    step_ledger: dict[str, int],
) -> tuple[tuple[int, ...], int | None, bool, str]:
    depth = len(continuation["decision_literals"])
    clause = tuple(-int(value) for value in continuation["decision_literals"])
    if depth == 0:
        return clause, None, False, "root"
    original = int(continuation["original_clause_count"])
    clauses = continuation["clauses"]
    for index, existing in enumerate(clauses):
        if tuple(existing) == clause:
            return clause, index + 1, False, "duplicate"
    if len(clauses) >= original + profile.max_learned_clauses:
        return clause, None, False, "capacity"
    clauses.append(list(clause))
    step_ledger["clause_writes"] += 1 + len(clause)
    return clause, len(clauses), True, "added"


def _regional_backtrack_and_flip(
    continuation: dict[str, Any],
    step_ledger: dict[str, int],
) -> int | None:
    depth = len(continuation["decision_literals"])
    target = depth
    phases = continuation["decision_phases"]
    while target > 0 and int(phases[target - 1]) == 2:
        target -= 1
    if target == 0:
        return None
    previous = int(continuation["decision_literals"][target - 1])
    assignments = continuation["assignments"]
    levels = continuation["levels"]
    reasons = continuation["reasons"]
    removed = {
        index for index, level in enumerate(levels) if int(level) >= target
    }
    for variable in removed:
        assignments[variable] = 0
        levels[variable] = 0
        reasons[variable] = 0
        step_ledger["assignment_writes"] += 3
    old_trail_count = len(continuation["trail"])
    retained = [
        int(value)
        for value in continuation["trail"]
        if int(value) - 1 not in removed
    ]
    continuation["trail"] = retained
    step_ledger["assignment_writes"] += old_trail_count + len(retained) + 1
    continuation["decision_literals"] = continuation["decision_literals"][:target]
    continuation["decision_phases"] = continuation["decision_phases"][:target]
    flipped = -previous
    continuation["decision_literals"][target - 1] = flipped
    continuation["decision_phases"][target - 1] = 2
    _regional_append_assignment(
        continuation,
        flipped,
        level=target,
        reason=0,
        step_ledger=step_ledger,
    )
    return flipped


def _regional_transition(
    continuation: dict[str, Any],
    profile: ClauseFieldProfile,
) -> tuple[dict[str, Any], dict[str, Any]]:
    step_ledger = {key: 0 for key in _regional_ledger()}
    if int(continuation["ledger_transitions"]) >= profile.max_transitions:
        continuation["status"] = "exhausted"
        return continuation, {"conflict_proof": None, "work": step_ledger}
    (
        conflict_clause,
        unit_literal,
        unit_clause,
        all_satisfied,
        positive,
        negative,
    ) = _regional_analyze(continuation, step_ledger)
    selected_literal: int | None = None
    conflict_proof: dict[str, Any] | None = None
    action: str
    if conflict_clause is not None:
        action = "conflict-backtrack"
        step_ledger["conflicts"] = 1
        conflict_proof = _regional_conflict_proof(
            continuation, conflict_clause, step_ledger
        )
        (
            nogood,
            stored_clause_id,
            stored_new,
            learning_status,
        ) = _regional_learn_nogood(continuation, profile, step_ledger)
        conflict_proof.update(
            {
                "stored_clause_id": stored_clause_id,
                "stored_new": stored_new,
                "learning_status": learning_status,
            }
        )
        flipped = _regional_backtrack_and_flip(continuation, step_ledger)
        if flipped is None:
            continuation["status"] = "unsat"
            action = "unsat"
        else:
            selected_literal = flipped
            step_ledger["backtracks"] = 1
    elif unit_literal is not None:
        action = "propagate"
        assert unit_clause is not None
        selected_literal = unit_literal
        _regional_append_assignment(
            continuation,
            selected_literal,
            level=len(continuation["decision_literals"]),
            reason=int(unit_clause) + 1,
            step_ledger=step_ledger,
        )
        step_ledger["propagations"] = 1
    elif all_satisfied:
        action = "sat"
        for variable, value in enumerate(continuation["assignments"]):
            if int(value) == 0:
                _regional_append_assignment(
                    continuation,
                    -(variable + 1),
                    level=len(continuation["decision_literals"]),
                    reason=0,
                    step_ledger=step_ledger,
                )
        continuation["status"] = "sat"
    else:
        action = "decide"
        unassigned = [
            index
            for index, value in enumerate(continuation["assignments"])
            if int(value) == 0
        ]

        best_activity = max(
            positive[index] + negative[index] for index in unassigned
        )
        variable = next(
            index
            for index in unassigned
            if positive[index] + negative[index] == best_activity
        )
        selected_literal = (
            variable + 1 if positive[variable] > negative[variable] else -(variable + 1)
        )
        depth = len(continuation["decision_literals"]) + 1
        continuation["decision_literals"].append(selected_literal)
        continuation["decision_phases"].append(1)
        _regional_append_assignment(
            continuation,
            selected_literal,
            level=depth,
            reason=0,
            step_ledger=step_ledger,
        )
        step_ledger["decisions"] = 1
    continuation["ledger_transitions"] += 1
    for key, value in step_ledger.items():
        if key == "transitions":
            continue
        continuation["ledger"][key] += value
    continuation["ledger"]["transitions"] = continuation["ledger_transitions"]
    continuation["ledger"]["learned_clauses"] = (
        len(continuation["clauses"]) - int(continuation["original_clause_count"])
    )
    continuation["ledger"]["peak_trail"] = max(
        continuation["ledger"]["peak_trail"], len(continuation["trail"])
    )
    continuation["ledger"]["peak_decision_depth"] = max(
        continuation["ledger"]["peak_decision_depth"],
        len(continuation["decision_literals"]),
    )
    receipt = {
        "schema": "cassifi.clause-field-step.v1",
        "action": action,
        "status": continuation["status"],
        "selected_literal": selected_literal,
        "conflict_clause": conflict_clause,
        "conflict_proof": conflict_proof,
        "work": dict(step_ledger),
    }
    return continuation, receipt


def _regional_inspect(
    continuation: Mapping[str, Any],
    profile: ClauseFieldProfile,
) -> dict[str, Any]:
    return {
        "status": continuation["status"],
        "variables": len(continuation["assignments"]),
        "original_clauses": continuation["original_clause_count"],
        "total_clauses": len(continuation["clauses"]),
        "assignment": list(continuation["assignments"]),
        "decision_depth": len(continuation["decision_literals"]),
        "trail_count": len(continuation["trail"]),
        "field_bytes": profile.state_bytes,
        "profile_sha256": profile.fingerprint,
        "resource_ledger": dict(continuation["ledger"]),
    }


def _regional_digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _regional_result(
    continuation: Mapping[str, Any],
    profile: ClauseFieldProfile,
    *,
    initial_state_sha256: str,
    journal: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    inspected = _regional_inspect(continuation, profile)
    result: dict[str, Any] = {
        "schema": "cassifi.clause-field-solve.v1",
        "initial_state_sha256": initial_state_sha256,
        "state_sha256": _regional_digest(continuation),
        **inspected,
    }
    status = inspected["status"]
    if status == "sat":
        result["evidence"] = {
            "kind": "witness",
            "assignment": list(inspected["assignment"]),
        }
    elif status == "unsat":
        result["evidence"] = {
            "kind": "certificate",
            "proof": _regional_certificate(journal, status=status),
        }
    elif status == "exhausted":
        result["evidence"] = {"kind": "exhausted", "status": "exhausted"}
    else:
        result["evidence"] = {"kind": "unresolved", "status": status}
    return result


def regional_state(
    clauses: Sequence[Sequence[int]],
    *,
    variable_count: int,
    profile: ClauseFieldProfile | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Encode one ClauseField search as typed canonical JSON regional state."""
    if isinstance(clauses, (str, bytes)) or not isinstance(clauses, Sequence):
        raise ClauseFieldError("clauses must be an ordered sequence")
    variables = _exact_integer(variable_count, "variable_count", minimum=1)
    if any(
        isinstance(clause, (str, bytes)) or not isinstance(clause, Sequence)
        for clause in clauses
    ):
        raise ClauseFieldError("each clause must be an ordered literal sequence")
    source_clauses = [list(clause) for clause in clauses]
    controller = _regional_profile(
        profile, variables=variables, clause_count=len(source_clauses)
    )
    normalized = _regional_normalized_source(
        source_clauses, variables=variables, profile=controller
    )
    ledger = _regional_ledger()
    continuation: dict[str, Any] = {
        "status": "running",
        "clauses": normalized,
        "original_clause_count": len(normalized),
        "assignments": [0] * variables,
        "assignment": [0] * variables,
        "levels": [0] * variables,
        "reasons": [0] * variables,
        "trail": [],
        "decision_literals": [],
        "decision_phases": [],
        "ledger": dict(ledger),
        "ledger_transitions": 0,
        "initial_state_sha256": "",
    }
    continuation["frontier"] = _regional_frontier(continuation)
    initial_core = {
        key: continuation[key]
        for key in (
            "status",
            "clauses",
            "original_clause_count",
            "assignments",
            "levels",
            "reasons",
            "trail",
            "decision_literals",
            "decision_phases",
            "ledger",
            "ledger_transitions",
        )
    }
    continuation["initial_state_sha256"] = _regional_digest(initial_core)
    continuation["assignment"] = list(continuation["assignments"])

    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": {"clauses": source_clauses, "variable_count": variables},
        "profile": controller.as_dict(),
        "phase": "search",
        "continuation": continuation,
        "journal": [],
        "ledger": ledger,
        "result": None,
    }


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance the typed ClauseField transition law by a bounded quantum."""
    if not isinstance(state, Mapping) or set(state) != {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }:
        raise ClauseFieldError("regional clause state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise ClauseFieldError("regional clause state schema is invalid")
    if not isinstance(arguments, Mapping) or arguments:
        raise ClauseFieldError("regional clause kernel takes no arguments")
    quantum = _exact_integer(quantum, "regional clause quantum", minimum=1)
    if quantum > REGIONAL_KERNEL_MAX_WORK:
        raise ClauseFieldError("regional clause quantum exceeds the kernel bound")
    source = state["source"]
    if (
        not isinstance(source, Mapping)
        or set(source) != {"clauses", "variable_count"}
        or not isinstance(source["clauses"], list)
    ):
        raise ClauseFieldError("regional clause source is invalid")
    variables = _exact_integer(source["variable_count"], "variable_count", minimum=1)
    if not isinstance(state["profile"], Mapping):
        raise ClauseFieldError("regional clause profile is invalid")
    profile = _regional_profile(
        state["profile"], variables=variables, clause_count=len(source["clauses"])
    )
    normalized = _regional_normalized_source(
        source["clauses"], variables=variables, profile=profile
    )
    continuation_value = state["continuation"]
    if not isinstance(continuation_value, Mapping):
        raise ClauseFieldError("regional clause continuation is invalid")
    continuation = json.loads(json.dumps(continuation_value))
    required_continuation = {
        "status",
        "clauses",
        "original_clause_count",
        "assignments",
        "assignment",
        "levels",
        "reasons",
        "trail",
        "decision_literals",
        "decision_phases",
        "ledger",
        "ledger_transitions",
        "frontier",
        "initial_state_sha256",
    }
    if set(continuation) != required_continuation:
        raise ClauseFieldError("regional clause continuation keys are invalid")
    if (
        continuation["status"] not in {"running", "sat", "unsat", "exhausted"}
        or continuation["original_clause_count"] != len(normalized)
        or not isinstance(continuation["clauses"], list)
        or continuation["clauses"][: len(normalized)] != normalized
        or continuation["assignments"] != continuation["assignment"]
        or len(continuation["assignments"]) != variables
        or len(continuation["levels"]) != variables
        or len(continuation["reasons"]) != variables
        or len(continuation["decision_literals"])
        != len(continuation["decision_phases"])
        or not isinstance(continuation["initial_state_sha256"], str)
    ):
        raise ClauseFieldError("regional clause continuation shape is invalid")
    expected_ledger = state["ledger"]
    if (
        not isinstance(expected_ledger, Mapping)
        or dict(expected_ledger) != continuation["ledger"]
    ):
        raise ClauseFieldError("regional clause ledger is invalid")
    if continuation["frontier"] != _regional_frontier(continuation):
        raise ClauseFieldError("regional clause frontier is invalid")
    journal = state["journal"]
    if not isinstance(journal, list) or any(
        not isinstance(item, Mapping) for item in journal
    ):
        raise ClauseFieldError("regional clause proof journal is invalid")
    phase = state["phase"]
    if phase not in {"search", "terminal"}:
        raise ClauseFieldError("regional clause phase is invalid")
    initial_digest = continuation["initial_state_sha256"]
    journal_copy = [dict(item) for item in journal]
    if phase == "terminal":
        result = state["result"]
        if not isinstance(result, Mapping):
            raise ClauseFieldError("regional clause terminal result is invalid")
        try:
            expected_result = _regional_result(
                continuation,
                profile,
                initial_state_sha256=initial_digest,
                journal=journal_copy,
            )
        except (ClauseFieldError, KeyError, TypeError, ValueError) as exc:
            raise ClauseFieldError("regional clause terminal evidence is invalid") from exc
        if dict(result) != expected_result:
            raise ClauseFieldError("regional clause terminal result is stale")
        return KernelResult(state=dict(state), status="done", work=0, output=dict(result))
    steps = 0
    for _ in range(quantum):
        if continuation["status"] != "running":
            break
        continuation, receipt = _regional_transition(continuation, profile)
        steps += 1
        continuation["assignment"] = list(continuation["assignments"])
        if receipt["conflict_proof"] is not None:
            journal_copy.append(dict(receipt["conflict_proof"]))
    continuation["frontier"] = _regional_frontier(continuation)
    terminal = continuation["status"] != "running"
    result = None
    output = None
    if terminal:
        result = _regional_result(
            continuation,
            profile,
            initial_state_sha256=initial_digest,
            journal=journal_copy,
        )
        output = result
    updated = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": {
            "clauses": [list(clause) for clause in source["clauses"]],
            "variable_count": variables,
        },
        "profile": profile.as_dict(),
        "phase": "terminal" if terminal else "search",
        "continuation": continuation,
        "journal": journal_copy,
        "ledger": dict(continuation["ledger"]),
        "result": result,
    }
    return KernelResult(
        state=updated,
        status="done" if terminal else "yield",
        work=steps,
        output=output,
    )



__all__ = [
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "regional_state",
    "regional_kernel",
    "SCHEMA",
    "ClauseField",
    "ClauseFieldError",
    "ClauseFieldProfile",
    "ClauseFieldState",
]
