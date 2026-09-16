"""Proof-oriented exact reductions for cubic monotone one-in-three SAT.

The reducer is deliberately fail closed.  It applies only transformations whose
Boolean satisfiability equivalence can be checked from exact affine guards or
bounded nonnegative row combinations, solves only a fixed-nullity terminal, and
returns ``unresolved`` for every
remaining residual.  An ``unresolved`` result is a concrete counterexample to
this finite rule set, not evidence that the source formula is unsatisfiable.

Reduction preferences adapt only inside one invocation.  Their exact counters
live in one immutable nine-plane float64 field and are never loaded as advice
for a later input.  Only the deterministic rule descriptor and independently
checkable proof are exportable.
"""

from __future__ import annotations

import hashlib
import itertools
import heapq
import json
import math
from dataclasses import asdict, dataclass
from fractions import Fraction
from functools import cmp_to_key
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

import cubic_kernel_decision as kernel

SCHEMA = "cassifi.cubic-reduction-result.v1"
ALGORITHM_SCHEMA = "cassifi.cubic-reduction-algorithm.v1"
SYSTEM_SCHEMA = "cassifi.affine-boolean-system.v1"
FIELD_SCHEMA = "cassifi.transient-reduction-preference-field.v1"

_SAFE_INTEGER = 2**53 - 1
_FIELD_MAGIC = 0xC552
_ROW_BOUND_SUPPORT_CAP = 4
_STRATEGIES = (
    "sparse_witness",
    "bounded_nullity",
    "forced_variable",
    "functional_pair",
    "literal_probe",
    "nonnegative_row_bound",
    "bounded_separator_relation",
)

# One strategy column per rule; the header uses the first cells of plane eight.
_F_SUPPORT = 0
_F_APPLICABLE = 1
_F_TERMINAL = 2
_F_REMOVED = 3
_F_WORK = 4
_F_PROJECTIONS = 5
_F_LAST_EPOCH = 6
_F_FIRST_CHOICES = 7
_F_HEADER = 8
_H_MAGIC = 0
_H_EPOCH = 1
_H_OBSERVATIONS = 2
_FIELD_MODES = max(8, len(_STRATEGIES))
_FIELD_SHAPE = (1, 9 * _FIELD_MODES, 1)


class CubicReductionError(ValueError):
    """Malformed input, profile, field, certificate, or internal reduction."""


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CubicReductionError("value is not JSON-canonical") from exc


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _exact_integer(
    value: Any,
    name: str,
    *,
    minimum: int | None = None,
    maximum: int = _SAFE_INTEGER,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or (minimum is not None and value < minimum)
        or abs(value) > maximum
    ):
        bound = "" if minimum is None else f" at least {minimum} and"
        raise CubicReductionError(
            f"{name} must be an exact integer{bound} with absolute value at most {maximum}"
        )
    return int(value)


@dataclass(frozen=True, slots=True)
class ReductionProfile:
    """Input-independent constants for one uniform reducer."""

    terminal_nullity: int = 5
    schedule_mode: str = "fixed"
    literal_probing: bool = False

    def __post_init__(self) -> None:
        _exact_integer(
            self.terminal_nullity,
            "terminal_nullity",
            minimum=0,
            maximum=12,
        )
        if self.schedule_mode not in ("adaptive", "fixed"):
            raise CubicReductionError("schedule_mode must be 'adaptive' or 'fixed'")
        if not isinstance(self.literal_probing, bool):
            raise CubicReductionError("literal_probing must be a Boolean")

    @property
    def fingerprint(self) -> str:
        return _digest({"schema": ALGORITHM_SCHEMA, "profile": asdict(self)})


@dataclass(frozen=True, slots=True)
class AffineBooleanSystem:
    """Canonical integer equations ``A x = b`` with Boolean variables."""

    variable_count: int
    coefficients: tuple[tuple[int, ...], ...]
    rhs: tuple[int, ...]

    def __post_init__(self) -> None:
        _exact_integer(self.variable_count, "variable_count", minimum=0)
        coefficients = tuple(tuple(row) for row in self.coefficients)
        rhs = tuple(self.rhs)
        if len(coefficients) != len(rhs):
            raise CubicReductionError("coefficient rows and rhs length disagree")
        for row in coefficients:
            if len(row) != self.variable_count:
                raise CubicReductionError("coefficient row width is invalid")
            for value in row:
                _exact_integer(value, "coefficient")
        for value in rhs:
            _exact_integer(value, "rhs")
        object.__setattr__(self, "coefficients", coefficients)
        object.__setattr__(self, "rhs", rhs)

    @property
    def equation_count(self) -> int:
        return len(self.coefficients)

    @property
    def nonzero_count(self) -> int:
        return sum(value != 0 for row in self.coefficients for value in row)

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SYSTEM_SCHEMA,
            "variable_count": self.variable_count,
            "coefficients": [list(row) for row in self.coefficients],
            "rhs": list(self.rhs),
        }

    @property
    def sha256(self) -> str:
        return _digest(self.as_dict())


@dataclass(slots=True)
class _WorkLedger:
    canonicalizations: int = 0
    rows_normalized: int = 0
    gcd_reductions: int = 0
    duplicate_rows_removed: int = 0
    affine_profiles: int = 0
    rref_calls: int = 0
    rref_pivots: int = 0
    fraction_updates: int = 0
    projection_queries: int = 0
    projection_states_checked: int = 0
    projection_fast_queries: int = 0
    projection_vector_entries_checked: int = 0
    variable_guards_checked: int = 0
    pair_guards_checked: int = 0
    substitutions: int = 0
    component_splits: int = 0
    components_created: int = 0
    candidate_assignments: int = 0
    equation_evaluations: int = 0
    sparse_witness_candidates: int = 0
    literal_probe_trials: int = 0
    propagation_rows_checked: int = 0
    propagation_bound_checks: int = 0
    propagation_assignments: int = 0
    row_bound_combinations: int = 0
    row_bound_coefficient_updates: int = 0
    separator_candidates_checked: int = 0
    separator_components_checked: int = 0
    separator_relations_enumerated: int = 0
    separator_assignments_checked: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    field_observations: int = 0
    proof_nodes: int = 0
    maximum_variables: int = 0
    maximum_equations: int = 0
    maximum_nonzero_coefficients: int = 0
    maximum_integer_bit_length: int = 0
    maximum_system_encoding_bits: int = 0

    def work_units(self) -> int:
        return (
            self.fraction_updates
            + self.projection_states_checked
            + self.projection_vector_entries_checked
            + self.variable_guards_checked
            + self.pair_guards_checked
            + self.candidate_assignments
            + self.sparse_witness_candidates
            + self.literal_probe_trials
            + self.propagation_rows_checked
            + self.propagation_bound_checks
            + self.propagation_assignments
            + self.row_bound_combinations
            + self.row_bound_coefficient_updates
            + self.equation_evaluations
            + self.separator_candidates_checked
            + self.separator_components_checked
            + self.separator_relations_enumerated
            + self.substitutions
        )

    def observe_system(self, system: AffineBooleanSystem) -> None:
        self.maximum_variables = max(self.maximum_variables, system.variable_count)
        self.maximum_equations = max(self.maximum_equations, system.equation_count)
        self.maximum_nonzero_coefficients = max(
            self.maximum_nonzero_coefficients,
            system.nonzero_count,
        )
        values = [abs(value) for row in system.coefficients for value in row]
        values.extend(abs(value) for value in system.rhs)
        bits = max((value.bit_length() for value in values), default=0)
        self.maximum_integer_bit_length = max(self.maximum_integer_bit_length, bits)
        self.maximum_system_encoding_bits = max(
            self.maximum_system_encoding_bits,
            8 * len(_canonical_bytes(system.as_dict())),
        )

    def as_dict(self) -> dict[str, int]:
        return {name: int(value) for name, value in asdict(self).items()}


def canonical_affine_system(
    variable_count: int,
    coefficients: Sequence[Sequence[int]],
    rhs: Sequence[int],
    *,
    ledger: _WorkLedger | None = None,
) -> AffineBooleanSystem:
    """Normalize row scale/order and remove exact duplicate equations."""

    _exact_integer(variable_count, "variable_count", minimum=0)
    rows = tuple(tuple(row) for row in coefficients)
    targets = tuple(rhs)
    if len(rows) != len(targets):
        raise CubicReductionError("coefficient rows and rhs length disagree")
    normalized: list[tuple[tuple[int, ...], int]] = []
    if ledger is not None:
        ledger.canonicalizations += 1
    for row, target in zip(rows, targets, strict=True):
        if len(row) != variable_count:
            raise CubicReductionError("coefficient row width is invalid")
        integer_row = tuple(_exact_integer(value, "coefficient") for value in row)
        integer_target = _exact_integer(target, "rhs")
        if ledger is not None:
            ledger.rows_normalized += 1
        divisor = 0
        for value in (*integer_row, integer_target):
            divisor = math.gcd(divisor, abs(value))
        divisor = max(1, divisor)
        if divisor > 1 and ledger is not None:
            ledger.gcd_reductions += 1
        integer_row = tuple(value // divisor for value in integer_row)
        integer_target //= divisor
        first = next(
            (value for value in (*integer_row, integer_target) if value != 0),
            0,
        )
        if first < 0:
            integer_row = tuple(-value for value in integer_row)
            integer_target = -integer_target
        if not any(integer_row) and integer_target == 0:
            continue
        normalized.append((integer_row, integer_target))
    normalized.sort()
    unique: list[tuple[tuple[int, ...], int]] = []
    for row in normalized:
        if unique and row == unique[-1]:
            if ledger is not None:
                ledger.duplicate_rows_removed += 1
            continue
        unique.append(row)
    system = AffineBooleanSystem(
        variable_count,
        tuple(row for row, _ in unique),
        tuple(target for _, target in unique),
    )
    if ledger is not None:
        ledger.observe_system(system)
    return system


def system_from_cubic_formula(
    formula: Sequence[Sequence[int]],
    *,
    ledger: _WorkLedger | None = None,
) -> tuple[tuple[tuple[int, int, int], ...], AffineBooleanSystem]:
    canonical = kernel.canonical_cubic_formula(formula)
    size = len(canonical)
    system = canonical_affine_system(
        size,
        tuple(
            tuple(int(variable in clause) for variable in range(1, size + 1))
            for clause in canonical
        ),
        (1,) * size,
        ledger=ledger,
    )
    return canonical, system


@dataclass(frozen=True, slots=True, eq=False)
class _PreferenceState:
    """One invocation-local exact field; no load/save API is provided."""

    _field: np.ndarray

    def __post_init__(self) -> None:
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise CubicReductionError("preference field must be a float64 tensor")
        if tuple(self._field.shape) != _FIELD_SHAPE:
            raise CubicReductionError("preference field shape is invalid")
        field = np.array(self._field, dtype=np.float64, copy=True, order="C")
        if (
            not np.all(np.isfinite(field))
            or not np.all(field == np.floor(field))
            or np.any(field < 0)
            or np.any(field > _SAFE_INTEGER)
        ):
            raise CubicReductionError("preference field cells are not exact counters")
        parts = field.reshape(1, 9, _FIELD_MODES, 1)[0, :, :, 0]
        if int(parts[_F_HEADER, _H_MAGIC]) != _FIELD_MAGIC:
            raise CubicReductionError("preference field magic is invalid")
        support = parts[_F_SUPPORT, : len(_STRATEGIES)]
        applicable = parts[_F_APPLICABLE, : len(_STRATEGIES)]
        terminal = parts[_F_TERMINAL, : len(_STRATEGIES)]
        if np.any(applicable > support) or np.any(terminal > applicable):
            raise CubicReductionError("preference evidence counters disagree")
        if int(parts[_F_HEADER, _H_OBSERVATIONS]) != int(np.sum(support)):
            raise CubicReductionError("preference observation total disagrees")
        if (
            np.any(parts[:_F_HEADER, len(_STRATEGIES) :] != 0)
            or np.any(parts[_F_HEADER, _H_OBSERVATIONS + 1 :] != 0)
        ):
            raise CubicReductionError("preference field padding is noncanonical")
        field.setflags(write=False)
        object.__setattr__(self, "_field", field)

    @property
    def sha256(self) -> str:
        digest = hashlib.sha256(
            _canonical_bytes(
                {
                    "schema": FIELD_SCHEMA,
                    "shape": list(_FIELD_SHAPE),
                    "dtype": "float64",
                }
            )
        )
        digest.update(self._field.tobytes(order="C"))
        return digest.hexdigest()


class _PreferenceField:
    @staticmethod
    def initial_state() -> _PreferenceState:
        field = np.zeros(_FIELD_SHAPE, dtype=np.float64)
        parts = field.reshape(1, 9, _FIELD_MODES, 1)[0, :, :, 0]
        parts[_F_HEADER, _H_MAGIC] = _FIELD_MAGIC
        return _PreferenceState(field)

    @staticmethod
    def _parts(state: _PreferenceState) -> np.ndarray:
        return state._field.reshape(1, 9, _FIELD_MODES, 1)[0, :, :, 0]

    def order(
        self,
        state: _PreferenceState,
        *,
        nullity: int,
        terminal_cap: int,
        schedule_mode: str,
        literal_probing: bool,
    ) -> tuple[str, ...]:
        parts = self._parts(state)

        def compare(left: int, right: int) -> int:
            left_support = int(parts[_F_SUPPORT, left])
            right_support = int(parts[_F_SUPPORT, right])
            if left_support == 0 or right_support == 0:
                if left_support == 0 and right_support != 0:
                    return -1
                if right_support == 0 and left_support != 0:
                    return 1
            left_work = max(1, int(parts[_F_WORK, left]))
            right_work = max(1, int(parts[_F_WORK, right]))
            left_yield = int(parts[_F_REMOVED, left] + parts[_F_TERMINAL, left])
            right_yield = int(parts[_F_REMOVED, right] + parts[_F_TERMINAL, right])
            comparison = left_yield * right_work - right_yield * left_work
            if comparison:
                return -1 if comparison > 0 else 1
            left_applicable = int(parts[_F_APPLICABLE, left])
            right_applicable = int(parts[_F_APPLICABLE, right])
            comparison = left_applicable * max(1, right_support) - right_applicable * max(1, left_support)
            if comparison:
                return -1 if comparison > 0 else 1
            return -1 if left < right else (1 if left > right else 0)

        indices = [
            index
            for index, strategy in enumerate(_STRATEGIES)
            if literal_probing or strategy != "literal_probe"
        ]
        if schedule_mode == "adaptive":
            indices.sort(key=cmp_to_key(compare))
        elif schedule_mode != "fixed":
            raise CubicReductionError("unknown preference schedule mode")
        bounded = _STRATEGIES.index("bounded_nullity")
        if nullity <= terminal_cap:
            indices.remove(bounded)
            indices.insert(0, bounded)
        return tuple(_STRATEGIES[index] for index in indices)

    def observe(
        self,
        state: _PreferenceState,
        strategy: str,
        *,
        applicable: bool,
        terminal: bool,
        variables_removed: int,
        work: int,
        projections: int,
        first_choice: bool,
    ) -> _PreferenceState:
        try:
            index = _STRATEGIES.index(strategy)
        except ValueError as exc:
            raise CubicReductionError("unknown reduction strategy") from exc
        for name, value in (
            ("variables_removed", variables_removed),
            ("work", work),
            ("projections", projections),
        ):
            _exact_integer(value, name, minimum=0)
        if terminal and not applicable:
            raise CubicReductionError("terminal observation must be applicable")
        field = state._field.copy()
        parts = field.reshape(1, 9, _FIELD_MODES, 1)[0, :, :, 0]
        epoch = int(parts[_F_HEADER, _H_EPOCH]) + 1
        updates = {
            _F_SUPPORT: 1,
            _F_APPLICABLE: int(applicable),
            _F_TERMINAL: int(terminal),
            _F_REMOVED: variables_removed,
            _F_WORK: max(1, work),
            _F_PROJECTIONS: projections,
            _F_FIRST_CHOICES: int(first_choice),
        }
        for plane, increment in updates.items():
            value = int(parts[plane, index]) + increment
            if value > _SAFE_INTEGER:
                raise CubicReductionError("preference field counter overflow")
            parts[plane, index] = value
        parts[_F_LAST_EPOCH, index] = epoch
        parts[_F_HEADER, _H_EPOCH] = epoch
        parts[_F_HEADER, _H_OBSERVATIONS] += 1
        return _PreferenceState(field)

    def inspect(
        self,
        state: _PreferenceState,
        *,
        terminal_cap: int,
        schedule_mode: str,
        literal_probing: bool,
    ) -> dict[str, Any]:
        parts = self._parts(state)
        rows = []
        for index, name in enumerate(_STRATEGIES):
            rows.append(
                {
                    "strategy": name,
                    "support": int(parts[_F_SUPPORT, index]),
                    "applicable": int(parts[_F_APPLICABLE, index]),
                    "terminal": int(parts[_F_TERMINAL, index]),
                    "variables_removed": int(parts[_F_REMOVED, index]),
                    "work": int(parts[_F_WORK, index]),
                    "projection_states_checked": int(parts[_F_PROJECTIONS, index]),
                    "last_epoch": int(parts[_F_LAST_EPOCH, index]),
                    "first_choices": int(parts[_F_FIRST_CHOICES, index]),
                }
            )
        return {
            "schema": FIELD_SCHEMA,
            "persistence": "invocation_local_only",
            "shape": list(_FIELD_SHAPE),
            "field_bytes": int(state._field.nbytes),
            "state_sha256": state.sha256,
            "epoch": int(parts[_F_HEADER, _H_EPOCH]),
            "schedule_mode": schedule_mode,
            "literal_probing": literal_probing,
            "observations": int(parts[_F_HEADER, _H_OBSERVATIONS]),
            "evidence": rows,
            "preferred_order_at_large_nullity": list(
                self.order(
                    state,
                    nullity=terminal_cap + 1,
                    terminal_cap=terminal_cap,
                    schedule_mode=schedule_mode,
                    literal_probing=literal_probing,
                )
            ),
        }


@dataclass(frozen=True, slots=True)
class _AffineProfile:
    consistent: bool
    rank: int
    nullity: int
    pivot_columns: tuple[int, ...]
    free_columns: tuple[int, ...]
    particular: tuple[Fraction, ...]
    vectors: tuple[tuple[Fraction, ...], ...]


def _rref(
    matrix: Sequence[Sequence[Fraction]],
    column_count: int,
    ledger: _WorkLedger,
) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    ledger.rref_calls += 1
    values = [list(row) for row in matrix]
    if any(len(row) != column_count for row in values):
        raise CubicReductionError("RREF row width is invalid")
    pivot_row = 0
    pivots: list[int] = []
    for column in range(column_count):
        selected = next(
            (row for row in range(pivot_row, len(values)) if values[row][column]),
            None,
        )
        if selected is None:
            continue
        values[pivot_row], values[selected] = values[selected], values[pivot_row]
        pivot = values[pivot_row][column]
        for index in range(column, column_count):
            values[pivot_row][index] /= pivot
            ledger.fraction_updates += 1
        for row in range(len(values)):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            for index in range(column, column_count):
                values[row][index] -= factor * values[pivot_row][index]
                ledger.fraction_updates += 2
        pivots.append(column)
        ledger.rref_pivots += 1
        pivot_row += 1
        if pivot_row == len(values):
            break
    return values, tuple(pivots)


def _affine_profile(system: AffineBooleanSystem, ledger: _WorkLedger) -> _AffineProfile:
    ledger.affine_profiles += 1
    n = system.variable_count
    augmented = [
        [Fraction(value) for value in row] + [Fraction(target)]
        for row, target in zip(system.coefficients, system.rhs, strict=True)
    ]
    reduced, pivots = _rref(augmented, n + 1, ledger)
    if n in pivots:
        return _AffineProfile(False, len(pivots) - 1, 0, (), (), (), ())
    coefficient_pivots = tuple(column for column in pivots if column < n)
    free = tuple(column for column in range(n) if column not in coefficient_pivots)
    pivot_rows = {column: row for row, column in enumerate(coefficient_pivots)}
    free_positions = {column: index for index, column in enumerate(free)}
    particular: list[Fraction] = []
    vectors: list[tuple[Fraction, ...]] = []
    for column in range(n):
        if column in free_positions:
            free_index = free_positions[column]
            particular.append(Fraction(0))
            vectors.append(
                tuple(Fraction(int(index == free_index)) for index in range(len(free)))
            )
        else:
            row = pivot_rows[column]
            particular.append(reduced[row][-1])
            vectors.append(tuple(-reduced[row][free_column] for free_column in free))
    return _AffineProfile(
        True,
        len(coefficient_pivots),
        len(free),
        coefficient_pivots,
        free,
        tuple(particular),
        tuple(vectors),
    )


def _allowed_boolean_states(
    profile: _AffineProfile,
    indices: Sequence[int],
    ledger: _WorkLedger,
) -> tuple[tuple[int, ...], ...]:
    """Project one or two coordinates by exact zero/proportionality tests."""

    if not profile.consistent:
        return ()
    selected = tuple(indices)
    if (
        len(selected) not in (1, 2)
        or len(set(selected)) != len(selected)
        or any(not 0 <= index < len(profile.vectors) for index in selected)
    ):
        raise CubicReductionError("Boolean projection ports must contain one or two coordinates")
    vectors = tuple(profile.vectors[index] for index in selected)
    first_nonzero: list[int | None] = []
    for vector in vectors:
        first: int | None = None
        for position, value in enumerate(vector):
            ledger.projection_vector_entries_checked += 1
            if value and first is None:
                first = position
        first_nonzero.append(first)

    proportional = False
    pivot: int | None = None
    if len(vectors) == 2 and first_nonzero[0] is not None and first_nonzero[1] is not None:
        pivot = first_nonzero[0]
        left_scale = vectors[0][pivot]
        right_scale = vectors[1][pivot]
        disagreements = 0
        for left, right in zip(vectors[0], vectors[1], strict=True):
            ledger.projection_vector_entries_checked += 1
            disagreements += int(right * left_scale != left * right_scale)
        proportional = disagreements == 0

    ledger.projection_queries += 1
    ledger.projection_fast_queries += 1
    allowed: list[tuple[int, ...]] = []
    for state in itertools.product((0, 1), repeat=len(selected)):
        ledger.projection_states_checked += 1
        targets = tuple(
            Fraction(value) - profile.particular[index]
            for index, value in zip(selected, state, strict=True)
        )
        if len(selected) == 1:
            possible = first_nonzero[0] is not None or targets[0] == 0
        elif first_nonzero[0] is None and first_nonzero[1] is None:
            possible = targets == (0, 0)
        elif first_nonzero[0] is None:
            possible = targets[0] == 0
        elif first_nonzero[1] is None:
            possible = targets[1] == 0
        elif not proportional:
            possible = True
        else:
            assert pivot is not None
            possible = (
                targets[1] * vectors[0][pivot]
                == targets[0] * vectors[1][pivot]
            )
        if possible:
            allowed.append(tuple(state))
    return tuple(allowed)


def _system_satisfied(
    system: AffineBooleanSystem,
    assignment: Sequence[int],
    ledger: _WorkLedger | None = None,
) -> bool:
    if len(assignment) != system.variable_count or any(value not in (0, 1) for value in assignment):
        return False
    for row, target in zip(system.coefficients, system.rhs, strict=True):
        if ledger is not None:
            ledger.equation_evaluations += 1
        if sum(value * bit for value, bit in zip(row, assignment, strict=True)) != target:
            return False
    return True


def _propagate_literal(
    system: AffineBooleanSystem,
    column: int,
    value: int,
    ledger: _WorkLedger,
) -> dict[str, Any]:
    """Propagate one Boolean assumption through exact integer row bounds."""

    _exact_integer(column, "literal column", minimum=0, maximum=system.variable_count - 1)
    _exact_integer(value, "literal value", minimum=0, maximum=1)
    assignments: list[int | None] = [None] * system.variable_count
    assignments[column] = value
    column_rows: list[list[int]] = [[] for _ in range(system.variable_count)]
    for row_index, row in enumerate(system.coefficients):
        for candidate, coefficient in enumerate(row):
            if coefficient:
                column_rows[candidate].append(row_index)

    queue = list(range(system.equation_count))
    heapq.heapify(queue)
    queued = [True] * system.equation_count
    deductions: list[dict[str, Any]] = []
    while queue:
        row_index = heapq.heappop(queue)
        queued[row_index] = False
        ledger.propagation_rows_checked += 1
        row = system.coefficients[row_index]
        target = system.rhs[row_index]
        premises = [
            {
                "column": candidate + 1,
                "coefficient": coefficient,
                "value": assignments[candidate],
            }
            for candidate, coefficient in enumerate(row)
            if coefficient and assignments[candidate] is not None
        ]
        assigned_sum = 0
        for candidate, coefficient in enumerate(row):
            assigned_value = assignments[candidate]
            if coefficient and assigned_value is not None:
                assigned_sum += coefficient * assigned_value
        residual_rhs = target - assigned_sum
        unknown = [
            candidate
            for candidate, coefficient in enumerate(row)
            if coefficient and assignments[candidate] is None
        ]
        minimum = sum(min(0, row[candidate]) for candidate in unknown)
        maximum = sum(max(0, row[candidate]) for candidate in unknown)
        ledger.propagation_bound_checks += 1
        if not minimum <= residual_rhs <= maximum:
            return {
                "assumption": {"column": column + 1, "value": value},
                "outcome": "conflict",
                "assignment": assignments,
                "deductions": deductions,
                "conflict": {
                    "kind": "equation_interval_empty",
                    "row": row_index + 1,
                    "equation_rhs": target,
                    "premises": premises,
                    "residual_rhs": residual_rhs,
                    "remaining_minimum": minimum,
                    "remaining_maximum": maximum,
                },
            }

        for candidate in unknown:
            coefficient = row[candidate]
            other_minimum = minimum - min(0, coefficient)
            other_maximum = maximum - max(0, coefficient)
            zero_residual = residual_rhs
            one_residual = residual_rhs - coefficient
            ledger.propagation_bound_checks += 2
            zero_possible = other_minimum <= zero_residual <= other_maximum
            one_possible = other_minimum <= one_residual <= other_maximum
            if not zero_possible and not one_possible:
                return {
                    "assumption": {"column": column + 1, "value": value},
                    "outcome": "conflict",
                    "assignment": assignments,
                    "deductions": deductions,
                    "conflict": {
                        "kind": "Boolean_domain_empty",
                        "row": row_index + 1,
                        "column": candidate + 1,
                        "equation_rhs": target,
                        "premises": premises,
                        "residual_rhs": residual_rhs,
                        "other_minimum": other_minimum,
                        "other_maximum": other_maximum,
                        "zero_residual_rhs": zero_residual,
                        "one_residual_rhs": one_residual,
                    },
                }
            if zero_possible == one_possible:
                continue
            forced_value = int(one_possible)
            rejected_value = 1 - forced_value
            rejected_residual = (
                zero_residual if rejected_value == 0 else one_residual
            )
            assignments[candidate] = forced_value
            ledger.propagation_assignments += 1
            deductions.append(
                {
                    "row": row_index + 1,
                    "column": candidate + 1,
                    "value": forced_value,
                    "rejected_value": rejected_value,
                    "equation_rhs": target,
                    "premises": premises,
                    "residual_rhs": residual_rhs,
                    "other_minimum": other_minimum,
                    "other_maximum": other_maximum,
                    "rejected_residual_rhs": rejected_residual,
                }
            )
            for affected in column_rows[candidate]:
                if not queued[affected]:
                    heapq.heappush(queue, affected)
                    queued[affected] = True
            break

    complete_assignment = tuple(
        item for item in assignments if item is not None
    )
    outcome = (
        "complete"
        if len(complete_assignment) == system.variable_count
        else "partial"
    )
    if outcome == "complete" and not _system_satisfied(system, complete_assignment):
        raise CubicReductionError("complete propagation assignment is invalid")
    return {
        "assumption": {"column": column + 1, "value": value},
        "outcome": outcome,
        "assignment": assignments,
        "deductions": deductions,
        "conflict": None,
    }


def _bounded_literal_probe(
    system: AffineBooleanSystem,
    ledger: _WorkLedger,
) -> dict[str, Any] | None:
    """Try each single literal once; never branch below propagation."""

    checked = 0
    for column in range(system.variable_count):
        for value in (0, 1):
            checked += 1
            ledger.literal_probe_trials += 1
            trace = _propagate_literal(system, column, value, ledger)
            if trace["outcome"] == "complete":
                assignment = tuple(int(item) for item in trace["assignment"])
                return {
                    "terminal": True,
                    "status": "sat",
                    "assignment": assignment,
                    "certificate": {
                        "kind": "literal_probe_witness",
                        "trials_checked": checked,
                        "trial_bound": 2 * system.variable_count,
                        "selected_trial": trace,
                        "selected_columns": [
                            index + 1
                            for index, bit in enumerate(assignment)
                            if bit
                        ],
                    },
                }
            if trace["outcome"] == "conflict":
                return {
                    "terminal": False,
                    "column": column,
                    "certificate": {
                        "kind": "literal_probe_forcing",
                        "trials_checked": checked,
                        "trial_bound": 2 * system.variable_count,
                        "selected_trial": trace,
                        "forced_column": column + 1,
                        "forced_value": 1 - value,
                    },
                }
    return None


def _sparse_boolean_witness(
    system: AffineBooleanSystem,
    ledger: _WorkLedger,
) -> tuple[tuple[int, ...], dict[str, Any]] | None:
    """Return a directly checked zero, all-one, unit, or private-cover witness."""

    candidates: list[tuple[str, tuple[int, ...]]] = [
        ("zero", (0,) * system.variable_count),
        ("all_one", (1,) * system.variable_count),
    ]
    candidates.extend(
        (
            "unit",
            tuple(int(index == column) for index in range(system.variable_count)),
        )
        for column in range(system.variable_count)
    )
    supports = tuple(
        sum(row[column] != 0 for row in system.coefficients)
        for column in range(system.variable_count)
    )
    private_assignment = [0] * system.variable_count
    private_columns: list[int] = []
    for row, target in zip(system.coefficients, system.rhs, strict=True):
        if target == 0:
            continue
        column = next(
            (
                index
                for index, coefficient in enumerate(row)
                if supports[index] == 1 and coefficient == target
            ),
            None,
        )
        if column is None:
            break
        private_assignment[column] = 1
        private_columns.append(column + 1)
    else:
        candidates.append(("private_row_cover", tuple(private_assignment)))

    checked = 0
    for witness_kind, assignment in candidates:
        ledger.sparse_witness_candidates += 1
        checked += 1
        if not _system_satisfied(system, assignment, ledger):
            continue
        return assignment, {
            "kind": "sparse_boolean_witness",
            "witness_kind": witness_kind,
            "selected_columns": [
                index + 1 for index, value in enumerate(assignment) if value
            ],
            "private_cover_columns": (
                private_columns if witness_kind == "private_row_cover" else None
            ),
            "candidates_checked": checked,
        }
    return None


def _nonnegative_row_bound(
    system: AffineBooleanSystem,
    ledger: _WorkLedger,
) -> tuple[int, dict[str, Any]] | None:
    """Find the first bounded row combination that forces one variable to zero."""

    checked = 0
    row_count = system.equation_count
    for support_size in range(1, min(_ROW_BOUND_SUPPORT_CAP, row_count) + 1):
        for selected_rows in itertools.combinations(range(row_count), support_size):
            for signs in itertools.product((-1, 1), repeat=support_size):
                checked += 1
                ledger.row_bound_combinations += 1
                combined = [0] * system.variable_count
                target = 0
                for row_index, multiplier in zip(selected_rows, signs, strict=True):
                    target += multiplier * system.rhs[row_index]
                    ledger.row_bound_coefficient_updates += 1
                    row = system.coefficients[row_index]
                    for column, coefficient in enumerate(row):
                        combined[column] += multiplier * coefficient
                        ledger.row_bound_coefficient_updates += 1
                if target < 0 or any(coefficient < 0 for coefficient in combined):
                    continue
                forced_column = next(
                    (
                        column
                        for column, coefficient in enumerate(combined)
                        if coefficient > target
                    ),
                    None,
                )
                if forced_column is None:
                    continue
                multipliers = [0] * row_count
                for row_index, multiplier in zip(selected_rows, signs, strict=True):
                    multipliers[row_index] = multiplier
                return forced_column, {
                    "kind": "nonnegative_row_bound",
                    "support_cap": _ROW_BOUND_SUPPORT_CAP,
                    "combinations_checked": checked,
                    "row_multipliers": multipliers,
                    "combined_coefficients": combined,
                    "combined_rhs": target,
                    "forced_column": forced_column + 1,
                    "forced_value": 0,
                }
    return None


def _transform_system(
    system: AffineBooleanSystem,
    offset: Sequence[int],
    transform: Sequence[Sequence[int]],
    ledger: _WorkLedger,
) -> AffineBooleanSystem:
    n = system.variable_count
    offset_tuple = tuple(offset)
    transform_tuple = tuple(tuple(row) for row in transform)
    if len(offset_tuple) != n or len(transform_tuple) != n:
        raise CubicReductionError("substitution source dimension is invalid")
    target_n = len(transform_tuple[0]) if transform_tuple else 0
    if any(len(row) != target_n for row in transform_tuple):
        raise CubicReductionError("substitution target dimension is invalid")
    if any(value not in (-1, 0, 1) for value in offset_tuple):
        raise CubicReductionError("substitution offset leaves the Boolean template")
    if any(value not in (-1, 0, 1) for row in transform_tuple for value in row):
        raise CubicReductionError("substitution transform leaves the Boolean template")
    coefficients: list[tuple[int, ...]] = []
    rhs: list[int] = []
    for source_row, source_rhs in zip(system.coefficients, system.rhs, strict=True):
        coefficients.append(
            tuple(
                sum(source_row[old] * transform_tuple[old][new] for old in range(n))
                for new in range(target_n)
            )
        )
        rhs.append(
            source_rhs
            - sum(source_row[old] * offset_tuple[old] for old in range(n))
        )
    ledger.substitutions += 1
    return canonical_affine_system(target_n, coefficients, rhs, ledger=ledger)


def _substitution_for_states(
    system: AffineBooleanSystem,
    ports: Sequence[int],
    states: Sequence[Sequence[int]],
    ledger: _WorkLedger,
) -> tuple[AffineBooleanSystem, tuple[int, ...], tuple[tuple[int, ...], ...]]:
    selected = tuple(ports)
    state_tuple = tuple(tuple(state) for state in states)
    if len(set(selected)) != len(selected) or any(
        not 0 <= index < system.variable_count for index in selected
    ):
        raise CubicReductionError("substitution ports are invalid")
    if len(state_tuple) not in (1, 2) or any(
        len(state) != len(selected) or any(value not in (0, 1) for value in state)
        for state in state_tuple
    ):
        raise CubicReductionError("substitution states are invalid")
    survivors = tuple(
        index for index in range(system.variable_count) if index not in set(selected)
    )
    target_n = len(survivors) + int(len(state_tuple) == 2)
    survivor_positions = {old: new for new, old in enumerate(survivors)}
    offset = [0] * system.variable_count
    transform = [[0] * target_n for _ in range(system.variable_count)]
    for old, new in survivor_positions.items():
        transform[old][new] = 1
    for position, old in enumerate(selected):
        offset[old] = state_tuple[0][position]
        if len(state_tuple) == 2:
            transform[old][-1] = state_tuple[1][position] - state_tuple[0][position]
    target = _transform_system(system, offset, transform, ledger)
    return target, tuple(offset), tuple(tuple(row) for row in transform)


def _drop_unconstrained(
    system: AffineBooleanSystem,
    columns: Sequence[int],
    ledger: _WorkLedger,
) -> tuple[AffineBooleanSystem, tuple[int, ...], tuple[tuple[int, ...], ...]]:
    selected = set(columns)
    survivors = tuple(index for index in range(system.variable_count) if index not in selected)
    transform = tuple(
        tuple(int(old == survivor) for survivor in survivors)
        for old in range(system.variable_count)
    )
    offset = (0,) * system.variable_count
    return _transform_system(system, offset, transform, ledger), offset, transform


def _lift_assignment(
    offset: Sequence[int],
    transform: Sequence[Sequence[int]],
    assignment: Sequence[int],
) -> tuple[int, ...]:
    return tuple(
        int(base + sum(coefficient * value for coefficient, value in zip(row, assignment, strict=True)))
        for base, row in zip(offset, transform, strict=True)
    )


def _components(
    system: AffineBooleanSystem,
    ledger: _WorkLedger,
) -> tuple[tuple[tuple[int, ...], AffineBooleanSystem], ...]:
    n = system.variable_count
    variable_rows = [set() for _ in range(n)]
    row_variables: list[set[int]] = []
    for row_index, row in enumerate(system.coefficients):
        active = {index for index, value in enumerate(row) if value}
        row_variables.append(active)
        for index in active:
            variable_rows[index].add(row_index)
    visited: set[int] = set()
    result: list[tuple[tuple[int, ...], AffineBooleanSystem]] = []
    for start in range(n):
        if start in visited:
            continue
        stack = [start]
        variables: set[int] = set()
        rows: set[int] = set()
        while stack:
            variable = stack.pop()
            if variable in variables:
                continue
            variables.add(variable)
            visited.add(variable)
            for row_index in variable_rows[variable]:
                if row_index in rows:
                    continue
                rows.add(row_index)
                stack.extend(row_variables[row_index] - variables)
        ordered_variables = tuple(sorted(variables))
        ordered_rows = tuple(sorted(rows))
        child = canonical_affine_system(
            len(ordered_variables),
            tuple(
                tuple(system.coefficients[row][column] for column in ordered_variables)
                for row in ordered_rows
            ),
            tuple(system.rhs[row] for row in ordered_rows),
            ledger=ledger,
        )
        result.append((ordered_variables, child))
    return tuple(result)


def _separator_components(
    system: AffineBooleanSystem,
    ports: Sequence[int],
) -> tuple[tuple[int, ...], ...]:
    excluded = set(ports)
    neighbors = [set() for _ in range(system.variable_count)]
    for row in system.coefficients:
        active = [column for column, coefficient in enumerate(row) if coefficient]
        for column in active:
            neighbors[column].update(other for other in active if other != column)
    remaining = set(range(system.variable_count)) - excluded
    result: list[tuple[int, ...]] = []
    while remaining:
        start = min(remaining)
        stack = [start]
        component: set[int] = set()
        while stack:
            column = stack.pop()
            if column not in remaining:
                continue
            remaining.remove(column)
            component.add(column)
            stack.extend(neighbors[column] & remaining)
        result.append(tuple(sorted(component)))
    return tuple(result)


def _separator_relation_equations(
    width: int,
    states: Sequence[Sequence[int]],
) -> tuple[tuple[tuple[int, ...], ...], tuple[int, ...]] | None:
    canonical_states = tuple(sorted(set(tuple(state) for state in states)))
    if any(len(state) != width or any(value not in (0, 1) for value in state) for state in canonical_states):
        raise CubicReductionError("separator relation contains a non-Boolean state")
    if not canonical_states:
        relation = canonical_affine_system(width, ((0,) * width,), (1,))
    elif len(canonical_states) == 1:
        relation = canonical_affine_system(
            width,
            tuple(
                tuple(int(column == fixed) for column in range(width))
                for fixed in range(width)
            ),
            canonical_states[0],
        )
    elif len(canonical_states) == 2:
        left, right = canonical_states
        if width == 1:
            relation = canonical_affine_system(width, (), ())
        else:
            delta = (right[0] - left[0], right[1] - left[1])
            normal = (delta[1], -delta[0])
            relation = canonical_affine_system(
                width,
                (normal,),
                (normal[0] * left[0] + normal[1] * left[1],),
            )
    elif width == 2 and len(canonical_states) == 3:
        return None
    elif len(canonical_states) == 1 << width:
        relation = canonical_affine_system(width, (), ())
    else:
        raise CubicReductionError("separator relation cardinality is unsupported")
    return relation.coefficients, relation.rhs


def _bounded_boolean_relation(
    system: AffineBooleanSystem,
    profile: _AffineProfile,
    port_width: int,
    ledger: _WorkLedger,
) -> tuple[tuple[tuple[int, ...], ...], dict[tuple[int, ...], tuple[int, ...]], int]:
    if not profile.consistent:
        return (), {}, 0
    witnesses: dict[tuple[int, ...], tuple[int, ...]] = {}
    checked = 0
    for free_values in itertools.product((0, 1), repeat=profile.nullity):
        checked += 1
        ledger.candidate_assignments += 1
        ledger.separator_assignments_checked += 1
        candidate = tuple(
            particular
            + sum(
                coefficient * value
                for coefficient, value in zip(vector, free_values, strict=True)
            )
            for particular, vector in zip(
                profile.particular,
                profile.vectors,
                strict=True,
            )
        )
        if any(value not in (0, 1) for value in candidate):
            continue
        integer_candidate = tuple(int(value) for value in candidate)
        if not _system_satisfied(system, integer_candidate, ledger):
            continue
        state = integer_candidate[:port_width]
        witnesses.setdefault(state, integer_candidate)
    states = tuple(sorted(witnesses))
    return states, witnesses, checked


def _bounded_separator_relation(
    system: AffineBooleanSystem,
    cap: int,
    ledger: _WorkLedger,
) -> dict[str, Any] | None:
    n = system.variable_count
    for width in (1, 2):
        for ports in itertools.combinations(range(n), width):
            ledger.separator_candidates_checked += 1
            components = _separator_components(system, ports)
            if len(components) < 2:
                continue
            for interior in components:
                ledger.separator_components_checked += 1
                interior_set = set(interior)
                local_order = (*ports, *interior)
                local_set = set(local_order)
                local_rows: list[tuple[int, ...]] = []
                local_rhs: list[int] = []
                retained_rows: list[tuple[int, ...]] = []
                retained_rhs: list[int] = []
                retained = tuple(column for column in range(n) if column not in interior_set)
                for row, target in zip(system.coefficients, system.rhs, strict=True):
                    active = {column for column, coefficient in enumerate(row) if coefficient}
                    if active & interior_set:
                        if not active <= local_set:
                            raise CubicReductionError("separator failed to isolate its component")
                        local_rows.append(tuple(row[column] for column in local_order))
                        local_rhs.append(target)
                    else:
                        retained_rows.append(tuple(row[column] for column in retained))
                        retained_rhs.append(target)
                local = canonical_affine_system(
                    len(local_order),
                    local_rows,
                    local_rhs,
                    ledger=ledger,
                )
                local_profile = _affine_profile(local, ledger)
                if local_profile.consistent and local_profile.nullity > cap:
                    continue
                ledger.separator_relations_enumerated += 1
                states, witnesses, checked = _bounded_boolean_relation(
                    local,
                    local_profile,
                    width,
                    ledger,
                )
                relation = _separator_relation_equations(width, states)
                if relation is None:
                    continue
                relation_rows, relation_rhs = relation
                positions = {column: index for index, column in enumerate(retained)}
                for row, target in zip(relation_rows, relation_rhs, strict=True):
                    expanded = [0] * len(retained)
                    for port, coefficient in zip(ports, row, strict=True):
                        expanded[positions[port]] = coefficient
                    retained_rows.append(tuple(expanded))
                    retained_rhs.append(target)
                target = canonical_affine_system(
                    len(retained),
                    retained_rows,
                    retained_rhs,
                    ledger=ledger,
                )
                return {
                    "target": target,
                    "retained_columns": retained,
                    "certificate": {
                        "kind": "bounded_separator_relation",
                        "separator_width_cap": 2,
                        "terminal_nullity_cap": cap,
                        "separator_variables": [column + 1 for column in ports],
                        "eliminated_variables": [column + 1 for column in interior],
                        "retained_columns": [column + 1 for column in retained],
                        "local_variable_order": [column + 1 for column in local_order],
                        "local_system": local.as_dict(),
                        "local_rank": local_profile.rank,
                        "local_nullity": local_profile.nullity,
                        "candidates_checked": checked,
                        "candidate_bound": (
                            0
                            if not local_profile.consistent
                            else 1 << local_profile.nullity
                        ),
                        "feasible_separator_states": [
                            list(state) for state in states
                        ],
                        "state_witnesses": [
                            {
                                "state": list(state),
                                "assignment": list(witnesses[state]),
                            }
                            for state in states
                        ],
                        "relation_coefficients": [list(row) for row in relation_rows],
                        "relation_rhs": list(relation_rhs),
                    },
                }
    return None


def _lift_separator_assignment(
    variable_count: int,
    certificate: Mapping[str, Any],
    child_assignment: Sequence[int],
) -> tuple[int, ...]:
    retained = tuple(int(value) - 1 for value in certificate["retained_columns"])
    separator = tuple(int(value) - 1 for value in certificate["separator_variables"])
    local_order = tuple(int(value) - 1 for value in certificate["local_variable_order"])
    if len(retained) != len(child_assignment):
        raise CubicReductionError("separator child assignment has the wrong dimension")
    assignment = [0] * variable_count
    for column, value in zip(retained, child_assignment, strict=True):
        assignment[column] = int(value)
    state = tuple(assignment[column] for column in separator)
    witness = next(
        (
            tuple(int(value) for value in row["assignment"])
            for row in certificate["state_witnesses"]
            if tuple(row["state"]) == state
        ),
        None,
    )
    if witness is None or len(witness) != len(local_order):
        raise CubicReductionError("separator relation lacks a lifting witness")
    for column, value in zip(local_order, witness, strict=True):
        if column in separator and assignment[column] != value:
            raise CubicReductionError("separator witness disagrees with its state")
        assignment[column] = value
    return tuple(assignment)


@dataclass(slots=True)
class _ProgressTracker:
    current: int
    initial: int
    events: list[dict[str, Any]]

    @classmethod
    def for_variables(cls, variable_count: int) -> _ProgressTracker:
        value = variable_count * variable_count
        return cls(value, value, [])

    def replace(
        self,
        *,
        kind: str,
        component_before: int,
        component_after: int,
        source_sha256: str,
        target_sha256: str | None,
    ) -> int | None:
        if component_before == 0:
            if component_after != 0:
                raise CubicReductionError("zero potential cannot create work")
            return None
        if not 0 <= component_after < component_before:
            raise CubicReductionError("reduction potential did not strictly descend")
        global_before = self.current
        if component_before > global_before:
            raise CubicReductionError("component potential exceeds active frontier")
        self.current = global_before - component_before + component_after
        event = {
            "index": len(self.events),
            "kind": kind,
            "source_system_sha256": source_sha256,
            "target_system_sha256": target_sha256,
            "component_before": component_before,
            "component_after": component_after,
            "global_before": global_before,
            "global_after": self.current,
            "decrement": component_before - component_after,
        }
        self.events.append(event)
        return event["index"]


@dataclass(frozen=True, slots=True)
class _MemoEntry:
    status: str
    assignment: tuple[int, ...] | None
    proof_sha256: str


@dataclass(frozen=True, slots=True)
class _CoreResult:
    status: str
    assignment: tuple[int, ...] | None
    proof: Mapping[str, Any]


@dataclass(slots=True)
class _Context:
    profile: ReductionProfile
    ledger: _WorkLedger
    preference: _PreferenceField
    field_state: _PreferenceState
    progress: _ProgressTracker
    memo: dict[str, _MemoEntry]


def _proof_node(context: _Context, value: dict[str, Any]) -> dict[str, Any]:
    proof_sha256 = _digest(value)
    node = {**value, "proof_sha256": proof_sha256}
    context.ledger.proof_nodes += 1
    return node


def _memoize(
    context: _Context,
    system: AffineBooleanSystem,
    result: _CoreResult,
) -> _CoreResult:
    entry = _MemoEntry(
        result.status,
        result.assignment,
        str(result.proof["proof_sha256"]),
    )
    previous = context.memo.get(system.sha256)
    if previous is not None and previous != entry:
        raise CubicReductionError("canonical residual acquired conflicting results")
    context.memo[system.sha256] = entry
    return result


def _terminal_result(
    context: _Context,
    system: AffineBooleanSystem,
    *,
    kind: str,
    status: str,
    assignment: tuple[int, ...] | None,
    certificate: Mapping[str, Any],
) -> _CoreResult:
    event = context.progress.replace(
        kind=kind,
        component_before=system.variable_count**2,
        component_after=0,
        source_sha256=system.sha256,
        target_sha256=None,
    )
    if status == "sat" and (
        assignment is None or not _system_satisfied(system, assignment, context.ledger)
    ):
        raise CubicReductionError("terminal SAT assignment does not satisfy its system")
    if status != "sat" and assignment is not None:
        raise CubicReductionError("non-SAT terminal cannot carry an assignment")
    node = _proof_node(
        context,
        {
            "kind": kind,
            "system": system.as_dict(),
            "system_sha256": system.sha256,
            "status": status,
            "assignment": None if assignment is None else list(assignment),
            "certificate": dict(certificate),
            "progress_event": event,
        },
    )
    return _memoize(context, system, _CoreResult(status, assignment, node))


def _bounded_terminal(
    system: AffineBooleanSystem,
    profile: _AffineProfile,
    cap: int,
    ledger: _WorkLedger,
) -> tuple[str, tuple[int, ...] | None, dict[str, Any]] | None:
    if profile.nullity > cap:
        return None
    assignment: tuple[int, ...] | None = None
    checked = 0
    for free_values in itertools.product((0, 1), repeat=profile.nullity):
        checked += 1
        ledger.candidate_assignments += 1
        candidate = tuple(
            particular
            + sum(coefficient * value for coefficient, value in zip(vector, free_values, strict=True))
            for particular, vector in zip(profile.particular, profile.vectors, strict=True)
        )
        if any(value not in (0, 1) for value in candidate):
            continue
        integer_candidate = tuple(int(value) for value in candidate)
        if _system_satisfied(system, integer_candidate, ledger):
            assignment = integer_candidate
            break
    status = "sat" if assignment is not None else "unsat"
    return status, assignment, {
        "kind": "bounded_nullity_enumeration",
        "terminal_nullity_cap": cap,
        "rank": profile.rank,
        "nullity": profile.nullity,
        "pivot_columns": [index + 1 for index in profile.pivot_columns],
        "free_columns": [index + 1 for index in profile.free_columns],
        "candidates_checked": checked,
        "candidate_bound": 1 << profile.nullity,
    }


def _solve_system(context: _Context, system: AffineBooleanSystem) -> _CoreResult:
    context.ledger.observe_system(system)
    source_sha256 = system.sha256
    cached = context.memo.get(source_sha256)
    if cached is not None:
        context.ledger.cache_hits += 1
        event = context.progress.replace(
            kind="canonical_cache_hit",
            component_before=system.variable_count**2,
            component_after=0,
            source_sha256=source_sha256,
            target_sha256=None,
        )
        node = _proof_node(
            context,
            {
                "kind": "canonical_cache_hit",
                "system": system.as_dict(),
                "system_sha256": source_sha256,
                "status": cached.status,
                "assignment": (
                    None if cached.assignment is None else list(cached.assignment)
                ),
                "reference_proof_sha256": cached.proof_sha256,
                "progress_event": event,
            },
        )
        return _CoreResult(cached.status, cached.assignment, node)
    context.ledger.cache_misses += 1

    affine = _affine_profile(system, context.ledger)
    if not affine.consistent:
        return _terminal_result(
            context,
            system,
            kind="affine_contradiction",
            status="unsat",
            assignment=None,
            certificate={"kind": "inconsistent_exact_rref"},
        )

    zero_columns = tuple(
        column
        for column in range(system.variable_count)
        if all(row[column] == 0 for row in system.coefficients)
    )
    if zero_columns:
        target, offset, transform = _drop_unconstrained(
            system,
            zero_columns,
            context.ledger,
        )
        event = context.progress.replace(
            kind="drop_unconstrained_variables",
            component_before=system.variable_count**2,
            component_after=target.variable_count**2,
            source_sha256=source_sha256,
            target_sha256=target.sha256,
        )
        child = _solve_system(context, target)
        assignment = (
            None
            if child.assignment is None
            else _lift_assignment(offset, transform, child.assignment)
        )
        if assignment is not None and not _system_satisfied(system, assignment, context.ledger):
            raise CubicReductionError("unconstrained-variable lift is invalid")
        node = _proof_node(
            context,
            {
                "kind": "drop_unconstrained_variables",
                "system": system.as_dict(),
                "system_sha256": source_sha256,
                "status": child.status,
                "assignment": None if assignment is None else list(assignment),
                "certificate": {
                    "columns": [index + 1 for index in zero_columns],
                    "offset": list(offset),
                    "transform": [list(row) for row in transform],
                    "target_system": target.as_dict(),
                    "target_system_sha256": target.sha256,
                },
                "child": child.proof,
                "progress_event": event,
            },
        )
        return _memoize(context, system, _CoreResult(child.status, assignment, node))

    components = _components(system, context.ledger)
    if len(components) > 1:
        context.ledger.component_splits += 1
        context.ledger.components_created += len(components)
        child_potential = sum(child.variable_count**2 for _, child in components)
        event = context.progress.replace(
            kind="component_split",
            component_before=system.variable_count**2,
            component_after=child_potential,
            source_sha256=source_sha256,
            target_sha256=_digest([child.sha256 for _, child in components]),
        )
        children: list[dict[str, Any]] = []
        assignments = [0] * system.variable_count
        statuses: list[str] = []
        for columns, child_system in components:
            child = _solve_system(context, child_system)
            statuses.append(child.status)
            if child.assignment is not None:
                for column, value in zip(columns, child.assignment, strict=True):
                    assignments[column] = value
            children.append(
                {
                    "columns": [index + 1 for index in columns],
                    "proof": child.proof,
                }
            )
        if "unsat" in statuses:
            status = "unsat"
            assignment = None
        elif "unresolved" in statuses:
            status = "unresolved"
            assignment = None
        else:
            status = "sat"
            assignment = tuple(assignments)
            if not _system_satisfied(system, assignment, context.ledger):
                raise CubicReductionError("component assignments do not satisfy parent")
        node = _proof_node(
            context,
            {
                "kind": "component_split",
                "system": system.as_dict(),
                "system_sha256": source_sha256,
                "status": status,
                "assignment": None if assignment is None else list(assignment),
                "components": children,
                "progress_event": event,
            },
        )
        return _memoize(context, system, _CoreResult(status, assignment, node))

    if system.variable_count == 0:
        assignment = ()
        if not _system_satisfied(system, assignment, context.ledger):
            raise CubicReductionError("zero-variable consistent system is invalid")
        node = _proof_node(
            context,
            {
                "kind": "empty_system",
                "system": system.as_dict(),
                "system_sha256": source_sha256,
                "status": "sat",
                "assignment": [],
                "certificate": {"kind": "empty_consistent_system"},
                "progress_event": None,
            },
        )
        return _memoize(context, system, _CoreResult("sat", assignment, node))

    order = context.preference.order(
        context.field_state,
        nullity=affine.nullity,
        terminal_cap=context.profile.terminal_nullity,
        schedule_mode=context.profile.schedule_mode,
        literal_probing=context.profile.literal_probing,
    )
    attempted: list[dict[str, Any]] = []
    for order_index, strategy in enumerate(order):
        work_before = context.ledger.work_units()
        projections_before = context.ledger.projection_states_checked
        action: dict[str, Any] | None = None
        if strategy == "sparse_witness":
            witness = _sparse_boolean_witness(system, context.ledger)
            if witness is not None:
                assignment, certificate = witness
                action = {
                    "terminal": True,
                    "status": "sat",
                    "assignment": assignment,
                    "certificate": certificate,
                }
        elif strategy == "bounded_nullity":
            terminal = _bounded_terminal(
                system,
                affine,
                context.profile.terminal_nullity,
                context.ledger,
            )
            if terminal is not None:
                status, assignment, certificate = terminal
                action = {
                    "terminal": True,
                    "status": status,
                    "assignment": assignment,
                    "certificate": certificate,
                }
        elif strategy == "forced_variable":
            for column in range(system.variable_count):
                context.ledger.variable_guards_checked += 1
                allowed = _allowed_boolean_states(affine, (column,), context.ledger)
                if len(allowed) == 0:
                    action = {
                        "terminal": True,
                        "status": "unsat",
                        "assignment": None,
                        "certificate": {
                            "kind": "empty_boolean_projection",
                            "ports": [column + 1],
                            "allowed_states": [],
                            "rank": affine.rank,
                            "nullity": affine.nullity,
                        },
                    }
                    break
                if len(allowed) == 1:
                    target, offset, transform = _substitution_for_states(
                        system,
                        (column,),
                        allowed,
                        context.ledger,
                    )
                    action = {
                        "terminal": False,
                        "target": target,
                        "offset": offset,
                        "transform": transform,
                        "certificate": {
                            "kind": "forced_variable",
                            "ports": [column + 1],
                            "allowed_states": [list(state) for state in allowed],
                            "rank": affine.rank,
                            "nullity": affine.nullity,
                        },
                    }
                    break
        elif strategy == "functional_pair":
            for left, right in itertools.combinations(range(system.variable_count), 2):
                context.ledger.pair_guards_checked += 1
                allowed = _allowed_boolean_states(
                    affine,
                    (left, right),
                    context.ledger,
                )
                if len(allowed) > 2:
                    continue
                if len(allowed) == 0:
                    action = {
                        "terminal": True,
                        "status": "unsat",
                        "assignment": None,
                        "certificate": {
                            "kind": "empty_boolean_projection",
                            "ports": [left + 1, right + 1],
                            "allowed_states": [],
                            "rank": affine.rank,
                            "nullity": affine.nullity,
                        },
                    }
                else:
                    target, offset, transform = _substitution_for_states(
                        system,
                        (left, right),
                        allowed,
                        context.ledger,
                    )
                    action = {
                        "terminal": False,
                        "target": target,
                        "offset": offset,
                        "transform": transform,
                        "certificate": {
                            "kind": "functional_pair",
                            "ports": [left + 1, right + 1],
                            "allowed_states": [list(state) for state in allowed],
                            "rank": affine.rank,
                            "nullity": affine.nullity,
                        },
                    }
                break
        elif strategy == "literal_probe":
            probe = _bounded_literal_probe(system, context.ledger)
            if probe is not None:
                if probe["terminal"]:
                    action = probe
                else:
                    column = int(probe["column"])
                    forced_value = int(probe["certificate"]["forced_value"])
                    target, offset, transform = _substitution_for_states(
                        system,
                        (column,),
                        ((forced_value,),),
                        context.ledger,
                    )
                    action = {
                        "terminal": False,
                        "target": target,
                        "offset": offset,
                        "transform": transform,
                        "certificate": probe["certificate"],
                    }
        elif strategy == "nonnegative_row_bound":
            bound = _nonnegative_row_bound(system, context.ledger)
            if bound is not None:
                column, certificate = bound
                target, offset, transform = _substitution_for_states(
                    system,
                    (column,),
                    ((0,),),
                    context.ledger,
                )
                action = {
                    "terminal": False,
                    "target": target,
                    "offset": offset,
                    "transform": transform,
                    "certificate": certificate,
                }
        elif strategy == "bounded_separator_relation":
            relation = _bounded_separator_relation(
                system,
                context.profile.terminal_nullity,
                context.ledger,
            )
            if relation is not None:
                action = {"terminal": False, **relation}
        else:  # pragma: no cover - the constant strategy tuple controls this.
            raise CubicReductionError("unsupported reduction strategy")

        work = context.ledger.work_units() - work_before
        projections = context.ledger.projection_states_checked - projections_before
        target = None if action is None or action.get("terminal") else action["target"]
        removed = 0 if target is None else system.variable_count - target.variable_count
        context.field_state = context.preference.observe(
            context.field_state,
            strategy,
            applicable=action is not None,
            terminal=bool(action is not None and action.get("terminal")),
            variables_removed=removed,
            work=work,
            projections=projections,
            first_choice=order_index == 0,
        )
        context.ledger.field_observations += 1
        attempt = {
            "strategy": strategy,
            "order": order_index,
            "applicable": action is not None,
            "work": max(1, work),
            "projection_states_checked": projections,
        }
        attempted.append(attempt)
        if action is None:
            continue
        if action["terminal"]:
            return _terminal_result(
                context,
                system,
                kind=str(action["certificate"]["kind"]),
                status=str(action["status"]),
                assignment=action["assignment"],
                certificate={
                    **action["certificate"],
                    "strategy_order": list(order),
                    "attempted": attempted,
                },
            )

        target = action["target"]
        event = context.progress.replace(
            kind=str(action["certificate"]["kind"]),
            component_before=system.variable_count**2,
            component_after=target.variable_count**2,
            source_sha256=source_sha256,
            target_sha256=target.sha256,
        )
        child = _solve_system(context, target)
        if child.assignment is None:
            assignment = None
        elif action["certificate"]["kind"] == "bounded_separator_relation":
            assignment = _lift_separator_assignment(
                system.variable_count,
                action["certificate"],
                child.assignment,
            )
        else:
            assignment = _lift_assignment(
                action["offset"],
                action["transform"],
                child.assignment,
            )
        if assignment is not None and not _system_satisfied(system, assignment, context.ledger):
            raise CubicReductionError("reduction lift does not satisfy source")
        certificate_details = {
            **action["certificate"],
            "strategy_order": list(order),
            "attempted": attempted,
            "target_system": target.as_dict(),
            "target_system_sha256": target.sha256,
        }
        if action["certificate"]["kind"] != "bounded_separator_relation":
            certificate_details.update(
                {
                    "offset": list(action["offset"]),
                    "transform": [list(row) for row in action["transform"]],
                }
            )
        node = _proof_node(
            context,
            {
                "kind": str(action["certificate"]["kind"]),
                "system": system.as_dict(),
                "system_sha256": source_sha256,
                "status": child.status,
                "assignment": None if assignment is None else list(assignment),
                "certificate": certificate_details,
                "child": child.proof,
                "progress_event": event,
            },
        )
        return _memoize(context, system, _CoreResult(child.status, assignment, node))

    return _terminal_result(
        context,
        system,
        kind="unresolved_residual",
        status="unresolved",
        assignment=None,
        certificate={
            "kind": "finite_rule_set_exhausted",
            "rank": affine.rank,
            "nullity": affine.nullity,
            "terminal_nullity_cap": context.profile.terminal_nullity,
            "strategy_order": list(order),
            "attempted": attempted,
        },
    )


def candidate_algorithm_descriptor(
    profile: ReductionProfile = ReductionProfile(),
) -> dict[str, Any]:
    """Export the finite uniform rule set, never learned invocation evidence."""

    body: dict[str, Any] = {
        "schema": ALGORITHM_SCHEMA,
        "profile": asdict(profile),
        "profile_sha256": profile.fingerprint,
        "domain": (
            "square cubic monotone one-in-three SAT incidence formulas with "
            "three distinct variables per clause"
        ),
        "outcomes": {
            "sat": "a supplied Boolean assignment is checked on the source formula",
            "unsat": "an exact affine or fixed-nullity certificate refutes every Boolean assignment",
            "unresolved": "the finite guarded rule set has no applicable rule; no truth claim",
        },
        "rules": [
            {
                "id": "drop_unconstrained_variables",
                "guard": "all source coefficients of each removed variable are zero",
                "effect": "remove all guarded variables and lift them as zero",
            },
            {
                "id": "component_split",
                "guard": "the exact equation-variable incidence graph is disconnected",
                "effect": "solve every canonical component; conjunction preserves satisfiability",
            },
            {
                "id": "sparse_witness",
                "guard": (
                    "direct evaluation accepts a zero, all-one, unit, or "
                    "one private support-one column per nonzero-target row"
                ),
                "effect": "return SAT only with the checked source assignment",
            },
            {
                "id": "bounded_nullity",
                "guard": f"exact affine nullity <= fixed constant {profile.terminal_nullity}",
                "effect": "enumerate at most 2^constant free Boolean coordinates",
            },
            {
                "id": "forced_variable",
                "guard": "the exact affine projection onto one coordinate has at most one Boolean state",
                "effect": "empty projection refutes; singleton projection substitutes a constant",
            },
            {
                "id": "functional_pair",
                "guard": "the exact affine projection onto a coordinate pair has at most two Boolean states",
                "effect": "empty projection refutes; one/two states substitute zero/one Boolean parameter",
            },
            {
                "id": "literal_probe",
                "guard": (
                    "profile literal_probing is enabled and the first deterministic "
                    "single-Boolean assumption either propagates to a complete witness "
                    "or reaches an exact integer row-bound contradiction"
                ),
                "effect": (
                    "return the checked witness or substitute the opposite Boolean value; "
                    "probing never recurses below the temporary assumption"
                ),
            },
            {
                "id": "nonnegative_row_bound",
                "guard": (
                    "the first row combination with support at most 4 and "
                    "multipliers in {-1,+1} has nonnegative derived coefficients "
                    "and one coefficient strictly larger than its nonnegative rhs"
                ),
                "effect": (
                    "force that Boolean variable to zero and record the exact "
                    "row-combination certificate"
                ),
            },
            {
                "id": "bounded_separator_relation",
                "guard": (
                    "deleting one or two separator variables disconnects the primal graph, "
                    "and one side has bounded affine nullity with an affine-representable "
                    "exact Boolean relation on the separator"
                ),
                "effect": (
                    "replace that side by its exact separator relation and retain one "
                    "checked lifting witness for every feasible boundary state"
                ),
            },
        ],
        "schedule": {
            "kind": "fresh invocation-local exact preference field",
            "mode": profile.schedule_mode,
            "field_role": (
                "adaptive_scheduler"
                if profile.schedule_mode == "adaptive"
                else "observation_only"
            ),
            "default_condition": (
                "adaptive ordering is not the default unless a held-out exact-resource "
                "ablation protects completion and beats the fixed schedule"
            ),
            "literal_probing": (
                "bounded_nonrecursive" if profile.literal_probing else "disabled"
            ),
            "persistent_advice": False,
            "training_corpus": None,
            "truth_authority": "exact guards and proof checking only",
            "fallback": None,
        },
        "progress": {
            "potential": "sum of squared variable counts over the active residual frontier",
            "initial_upper_bound": "n^2",
            "strict_descent": "every split, quotient, cache discharge, or terminal decreases the integer potential",
            "transition_upper_bound": "n^2 plus the zero-variable leaf",
        },
        "conservative_cost_envelope": {
            "affine_rank": "polynomial exact rational elimination",
            "projection_states_per_pair": 4,
            "projection_implementation": "exact zero/proportionality tests on one or two affine-coordinate vectors; no per-state elimination",
            "pairs_per_state": "at most n(n-1)/2",
            "literal_probe_trials_per_residual": "at most 2n",
            "literal_propagation": (
                "deterministic affected-row work queue with exact integer interval bounds"
            ),
            "arithmetic_operations": "O(n^7) under the n^2 progress bound",
            "integer_bit_length": "input_bit_length + O(n), because every quotient uses {-1,0,1} affine templates",
            "proof_bits": "O(n^4 * (input_bit_length + n))",
        },
        "open_obligation": (
            "P=NP would require a proof that unresolved_residual is unreachable on every legal input; "
            "this implementation measures and minimizes counterexamples instead of assuming that obligation."
        ),
    }
    return {**body, "descriptor_sha256": _digest(body)}


def solve_cubic_reduction(
    formula: Sequence[Sequence[int]],
    *,
    profile: ReductionProfile = ReductionProfile(),
) -> dict[str, Any]:
    """Run the finite exact reducer and return a self-contained proof result."""

    ledger = _WorkLedger()
    canonical, source = system_from_cubic_formula(formula, ledger=ledger)
    input_bits = max(
        (
            abs(value).bit_length()
            for row in source.coefficients
            for value in row
        ),
        default=0,
    )
    input_bits = max(input_bits, *(abs(value).bit_length() for value in source.rhs))
    preference = _PreferenceField()
    context = _Context(
        profile,
        ledger,
        preference,
        preference.initial_state(),
        _ProgressTracker.for_variables(source.variable_count),
        {},
    )
    core = _solve_system(context, source)
    if context.progress.current != 0:
        raise CubicReductionError("reduction frontier did not halt")
    assignment = core.assignment
    if core.status == "sat":
        if assignment is None or not all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in canonical
        ):
            raise CubicReductionError("root SAT witness failed the cubic source")
    elif assignment is not None:
        raise CubicReductionError("non-SAT root carries an assignment")

    algorithm = candidate_algorithm_descriptor(profile)
    proof_bytes = len(_canonical_bytes(core.proof))
    coefficient_bit_bound = input_bits + 2 * source.variable_count + 1
    if ledger.maximum_integer_bit_length > coefficient_bit_bound:
        raise CubicReductionError("observed coefficient growth exceeded conservative bound")
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "algorithm": algorithm,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": _digest([list(clause) for clause in canonical]),
        "source_system_sha256": source.sha256,
        "status": core.status,
        "assignment": None if assignment is None else list(assignment),
        "proof": core.proof,
        "progress": {
            "potential_name": "active_residual_squared_variable_sum",
            "initial": context.progress.initial,
            "final": context.progress.current,
            "events": context.progress.events,
            "strictly_descending": all(
                event["global_after"] < event["global_before"]
                for event in context.progress.events
            ),
            "event_count": len(context.progress.events),
            "event_bound": source.variable_count**2,
        },
        "field_preference": preference.inspect(
            context.field_state,
            terminal_cap=profile.terminal_nullity,
            schedule_mode=profile.schedule_mode,
            literal_probing=profile.literal_probing,
        ),
        "resource_ledger": ledger.as_dict(),
        "representation": {
            "input_integer_bit_length": input_bits,
            "coefficient_bit_length_bound": coefficient_bit_bound,
            "observed_maximum_integer_bit_length": ledger.maximum_integer_bit_length,
            "bound_respected": True,
            "proof_bytes": proof_bytes,
            "proof_nodes": ledger.proof_nodes,
            "canonical_residuals": len(context.memo),
            "cache_hits": ledger.cache_hits,
            "cache_persistence": "invocation_local_only",
        },
        "assessment": {
            "truth_claim": core.status if core.status in ("sat", "unsat") else None,
            "rule_set_complete_on_input": core.status != "unresolved",
            "p_equals_np_claim": False,
            "remaining_obligation": (
                None
                if core.status != "unresolved"
                else "prove a new exact reduction covering this residual or prove a total alternative"
            ),
        },
    }
    result["result_sha256"] = _digest(result)
    return result


REGIONAL_KERNEL_NAME = "exact.cubic"
REGIONAL_KERNEL_MAX_WORK = 4096
REGIONAL_STATE_SCHEMA = "cassifi.regional-cubic-state.v1"


def _regional_fraction(value: str) -> Fraction:
    if not isinstance(value, str) or not value:
        raise CubicReductionError("regional affine fraction is invalid")
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            result = Fraction(int(numerator), int(denominator))
        else:
            result = Fraction(int(value))
    except (TypeError, ValueError, ZeroDivisionError) as exc:
        raise CubicReductionError("regional affine fraction is invalid") from exc
    return result


def _regional_fraction_text(value: Fraction) -> str:
    if value.denominator == 1:
        return str(value.numerator)
    return f"{value.numerator}/{value.denominator}"


def _regional_affine_dict(profile: _AffineProfile) -> dict[str, Any]:
    return {
        "consistent": bool(profile.consistent),
        "rank": int(profile.rank),
        "nullity": int(profile.nullity),
        "pivot_columns": [int(value) for value in profile.pivot_columns],
        "free_columns": [int(value) for value in profile.free_columns],
        "particular": [
            _regional_fraction_text(value) for value in profile.particular
        ],
        "vectors": [
            [_regional_fraction_text(value) for value in vector]
            for vector in profile.vectors
        ],
    }


def _regional_affine(value: Mapping[str, Any]) -> _AffineProfile:
    if not isinstance(value, Mapping):
        raise CubicReductionError("regional affine profile is invalid")
    required = {
        "consistent",
        "rank",
        "nullity",
        "pivot_columns",
        "free_columns",
        "particular",
        "vectors",
    }
    if set(value) != required or not isinstance(value["consistent"], bool):
        raise CubicReductionError("regional affine profile keys are invalid")
    try:
        rank = int(value["rank"])
        nullity = int(value["nullity"])
        pivots = tuple(int(item) for item in value["pivot_columns"])
        free = tuple(int(item) for item in value["free_columns"])
        particular = tuple(_regional_fraction(item) for item in value["particular"])
        vectors = tuple(
            tuple(_regional_fraction(item) for item in vector)
            for vector in value["vectors"]
        )
    except (TypeError, ValueError) as exc:
        raise CubicReductionError("regional affine profile values are invalid") from exc
    if rank < 0 or nullity < 0 or len(particular) != len(vectors):
        raise CubicReductionError("regional affine profile dimensions are invalid")
    if any(len(vector) != nullity for vector in vectors):
        raise CubicReductionError("regional affine vector dimensions are invalid")
    return _AffineProfile(
        bool(value["consistent"]),
        rank,
        nullity,
        pivots,
        free,
        particular,
        vectors,
    )


def _regional_system(value: Mapping[str, Any]) -> AffineBooleanSystem:
    if not isinstance(value, Mapping) or set(value) != {
        "schema",
        "variable_count",
        "coefficients",
        "rhs",
    }:
        raise CubicReductionError("regional affine system is invalid")
    if value["schema"] != SYSTEM_SCHEMA:
        raise CubicReductionError("regional affine system schema is invalid")
    try:
        return AffineBooleanSystem(
            int(value["variable_count"]),
            tuple(tuple(int(item) for item in row) for row in value["coefficients"]),
            tuple(int(item) for item in value["rhs"]),
        )
    except (TypeError, ValueError) as exc:
        raise CubicReductionError("regional affine system values are invalid") from exc


def _regional_ledger(value: Mapping[str, Any]) -> tuple[_WorkLedger, int, int]:
    if not isinstance(value, Mapping):
        raise CubicReductionError("regional ledger is invalid")
    defaults = asdict(_WorkLedger())
    try:
        ledger = _WorkLedger(
            **{
                name: _exact_integer(value.get(name, default), name, minimum=0)
                for name, default in defaults.items()
            }
        )
        primitive = _exact_integer(
            value.get("primitive_expansions", 0),
            "primitive_expansions",
            minimum=0,
        )
        work_total = _exact_integer(
            value.get("work_total", primitive),
            "work_total",
            minimum=0,
        )
    except (TypeError, ValueError) as exc:
        raise CubicReductionError("regional ledger values are invalid") from exc
    return ledger, primitive, work_total


def _regional_memo(value: Mapping[str, Any]) -> dict[str, _MemoEntry]:
    if not isinstance(value, Mapping):
        raise CubicReductionError("regional memo is invalid")
    memo: dict[str, _MemoEntry] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, Mapping):
            raise CubicReductionError("regional memo entry is invalid")
        if set(raw) != {"status", "assignment", "proof_sha256"}:
            raise CubicReductionError("regional memo entry keys are invalid")
        assignment = raw["assignment"]
        if assignment is not None:
            if not isinstance(assignment, list) or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in assignment
            ):
                raise CubicReductionError("regional memo assignment is invalid")
            assignment_value: tuple[int, ...] | None = tuple(assignment)
        else:
            assignment_value = None
        memo[key] = _MemoEntry(
            str(raw["status"]),
            assignment_value,
            str(raw["proof_sha256"]),
        )
    return memo


def _regional_context(state: Mapping[str, Any]) -> _Context:
    continuation = state["continuation"]
    ledger, _, _ = _regional_ledger(state["ledger"])
    profile = ReductionProfile(**dict(state["profile"]))
    preference = _PreferenceField()
    raw_field = continuation.get("preference_field")
    if raw_field is None:
        field_state = preference.initial_state()
    else:
        if not isinstance(raw_field, list):
            raise CubicReductionError("regional preference field is invalid")
        try:
            field = np.asarray(raw_field, dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise CubicReductionError("regional preference field is invalid") from exc
        if field.size != math.prod(_FIELD_SHAPE):
            raise CubicReductionError("regional preference field size is invalid")
        field_state = _PreferenceState(field.reshape(_FIELD_SHAPE))
    progress_value = continuation.get("progress")
    if not isinstance(progress_value, Mapping) or set(progress_value) != {
        "current",
        "initial",
        "events",
    }:
        raise CubicReductionError("regional progress is invalid")
    progress = _ProgressTracker(
        _exact_integer(progress_value["current"], "progress current", minimum=0),
        _exact_integer(progress_value["initial"], "progress initial", minimum=0),
        [dict(event) for event in progress_value["events"]],
    )
    return _Context(
        profile,
        ledger,
        preference,
        field_state,
        progress,
        _regional_memo(continuation.get("memo", {})),
    )


def _regional_sync(
    state: dict[str, Any],
    context: _Context,
    *,
    primitive: int | None = None,
) -> None:
    continuation = dict(state["continuation"])
    continuation["memo"] = {
        key: {
            "status": entry.status,
            "assignment": (
                None if entry.assignment is None else list(entry.assignment)
            ),
            "proof_sha256": entry.proof_sha256,
        }
        for key, entry in sorted(context.memo.items())
    }
    continuation["progress"] = {
        "current": int(context.progress.current),
        "initial": int(context.progress.initial),
        "events": [dict(event) for event in context.progress.events],
    }
    continuation["preference_field"] = [
        int(value) for value in context.field_state._field.reshape(-1)
    ]
    state["continuation"] = continuation
    previous = state["ledger"]
    _, old_primitive, old_work = _regional_ledger(previous)
    increment = 0 if primitive is None else int(primitive)
    state["ledger"] = {
        **context.ledger.as_dict(),
        "primitive_expansions": old_primitive + increment,
        "work_total": old_work + increment,
    }


def _regional_core_dict(core: _CoreResult) -> dict[str, Any]:
    return {
        "status": core.status,
        "assignment": (
            None if core.assignment is None else list(core.assignment)
        ),
        "proof": dict(core.proof),
    }


def _regional_core(value: Mapping[str, Any]) -> _CoreResult:
    if not isinstance(value, Mapping) or set(value) != {
        "status",
        "assignment",
        "proof",
    }:
        raise CubicReductionError("regional core result is invalid")
    assignment = value["assignment"]
    if assignment is not None:
        if not isinstance(assignment, list):
            raise CubicReductionError("regional core assignment is invalid")
        assignment_value: tuple[int, ...] | None = tuple(int(item) for item in assignment)
    else:
        assignment_value = None
    if not isinstance(value["proof"], Mapping):
        raise CubicReductionError("regional core proof is invalid")
    return _CoreResult(str(value["status"]), assignment_value, dict(value["proof"]))


def _regional_action_dict(action: Mapping[str, Any]) -> dict[str, Any]:
    encoded = dict(action)
    target = encoded.get("target")
    if isinstance(target, AffineBooleanSystem):
        encoded["target"] = target.as_dict()
    if isinstance(encoded.get("offset"), tuple):
        encoded["offset"] = list(encoded["offset"])
    if isinstance(encoded.get("transform"), tuple):
        encoded["transform"] = [list(row) for row in encoded["transform"]]
    if isinstance(encoded.get("assignment"), tuple):
        encoded["assignment"] = list(encoded["assignment"])
    return encoded


def _regional_strategy_action(
    context: _Context,
    system: AffineBooleanSystem,
    affine: _AffineProfile,
    strategy: str,
) -> dict[str, Any] | None:
    action: dict[str, Any] | None = None
    if strategy == "sparse_witness":
        witness = _sparse_boolean_witness(system, context.ledger)
        if witness is not None:
            assignment, certificate = witness
            action = {
                "terminal": True,
                "status": "sat",
                "assignment": assignment,
                "certificate": certificate,
            }
    elif strategy == "bounded_nullity":
        terminal = _bounded_terminal(
            system,
            affine,
            context.profile.terminal_nullity,
            context.ledger,
        )
        if terminal is not None:
            status, assignment, certificate = terminal
            action = {
                "terminal": True,
                "status": status,
                "assignment": assignment,
                "certificate": certificate,
            }
    elif strategy == "forced_variable":
        for column in range(system.variable_count):
            context.ledger.variable_guards_checked += 1
            allowed = _allowed_boolean_states(affine, (column,), context.ledger)
            if len(allowed) == 0:
                action = {
                    "terminal": True,
                    "status": "unsat",
                    "assignment": None,
                    "certificate": {
                        "kind": "empty_boolean_projection",
                        "ports": [column + 1],
                        "allowed_states": [],
                        "rank": affine.rank,
                        "nullity": affine.nullity,
                    },
                }
                break
            if len(allowed) == 1:
                target, offset, transform = _substitution_for_states(
                    system,
                    (column,),
                    allowed,
                    context.ledger,
                )
                action = {
                    "terminal": False,
                    "target": target,
                    "offset": offset,
                    "transform": transform,
                    "certificate": {
                        "kind": "forced_variable",
                        "ports": [column + 1],
                        "allowed_states": [list(state) for state in allowed],
                        "rank": affine.rank,
                        "nullity": affine.nullity,
                    },
                }
                break
    elif strategy == "functional_pair":
        for left, right in itertools.combinations(range(system.variable_count), 2):
            context.ledger.pair_guards_checked += 1
            allowed = _allowed_boolean_states(
                affine,
                (left, right),
                context.ledger,
            )
            if len(allowed) > 2:
                continue
            if len(allowed) == 0:
                action = {
                    "terminal": True,
                    "status": "unsat",
                    "assignment": None,
                    "certificate": {
                        "kind": "empty_boolean_projection",
                        "ports": [left + 1, right + 1],
                        "allowed_states": [],
                        "rank": affine.rank,
                        "nullity": affine.nullity,
                    },
                }
            else:
                target, offset, transform = _substitution_for_states(
                    system,
                    (left, right),
                    allowed,
                    context.ledger,
                )
                action = {
                    "terminal": False,
                    "target": target,
                    "offset": offset,
                    "transform": transform,
                    "certificate": {
                        "kind": "functional_pair",
                        "ports": [left + 1, right + 1],
                        "allowed_states": [list(state) for state in allowed],
                        "rank": affine.rank,
                        "nullity": affine.nullity,
                    },
                }
            break
    elif strategy == "literal_probe":
        probe = _bounded_literal_probe(system, context.ledger)
        if probe is not None:
            if probe["terminal"]:
                action = probe
            else:
                column = int(probe["column"])
                forced_value = int(probe["certificate"]["forced_value"])
                target, offset, transform = _substitution_for_states(
                    system,
                    (column,),
                    ((forced_value,),),
                    context.ledger,
                )
                action = {
                    "terminal": False,
                    "target": target,
                    "offset": offset,
                    "transform": transform,
                    "certificate": probe["certificate"],
                }
    elif strategy == "nonnegative_row_bound":
        bound = _nonnegative_row_bound(system, context.ledger)
        if bound is not None:
            column, certificate = bound
            target, offset, transform = _substitution_for_states(
                system,
                (column,),
                ((0,),),
                context.ledger,
            )
            action = {
                "terminal": False,
                "target": target,
                "offset": offset,
                "transform": transform,
                "certificate": certificate,
            }
    elif strategy == "bounded_separator_relation":
        relation = _bounded_separator_relation(
            system,
            context.profile.terminal_nullity,
            context.ledger,
        )
        if relation is not None:
            action = {"terminal": False, **relation}
    else:  # pragma: no cover
        raise CubicReductionError("unsupported reduction strategy")
    return action


def _regional_push_child(
    frames: list[dict[str, Any]],
    target: AffineBooleanSystem,
) -> None:
    frames.append({"kind": "enter", "system": target.as_dict()})


def _regional_attach_child(
    context: _Context,
    frames: list[dict[str, Any]],
) -> None:
    child_frame = frames.pop()
    child = _regional_core(child_frame["result"])
    if not frames:
        raise CubicReductionError("regional root child attachment is invalid")
    parent = frames[-1]
    system = _regional_system(parent["system"])
    if parent["kind"] == "await_child":
        action = parent["action"]
        target_system = _regional_system(action["target"])
        certificate = dict(action["certificate"])
        assignment = child.assignment
        if assignment is None:
            lifted = None
        elif certificate["kind"] == "bounded_separator_relation":
            if assignment is None:
                raise CubicReductionError("regional child assignment is missing")
            lifted = _lift_separator_assignment(
                system.variable_count,
                certificate,
                assignment,
            )
        else:
            if assignment is None:
                raise CubicReductionError("regional child assignment is missing")
            lifted = _lift_assignment(
                tuple(int(item) for item in action["offset"]),
                tuple(tuple(int(item) for item in row) for row in action["transform"]),
                assignment,
            )
        if lifted is not None and not _system_satisfied(
            system,
            lifted,
            context.ledger,
        ):
            raise CubicReductionError("regional reduction lift does not satisfy source")
        if certificate["kind"] == "drop_unconstrained_variables":
            details = {
                **certificate,
                "target_system": target_system.as_dict(),
                "target_system_sha256": target_system.sha256,
            }
        else:
            details = {
                **certificate,
                "strategy_order": list(parent["strategy_order"]),
                "attempted": list(parent["attempted"]),
                "target_system": target_system.as_dict(),
                "target_system_sha256": target_system.sha256,
            }
        if certificate["kind"] != "bounded_separator_relation":
            details.update(
                {
                    "offset": list(action["offset"]),
                    "transform": [list(row) for row in action["transform"]],
                }
            )
        node = _proof_node(
            context,
            {
                "kind": str(certificate["kind"]),
                "system": system.as_dict(),
                "system_sha256": system.sha256,
                "status": child.status,
                "assignment": None if lifted is None else list(lifted),
                "certificate": details,
                "child": child.proof,
                "progress_event": parent["progress_event"],
            },
        )
        parent["result"] = _regional_core_dict(
            _memoize(context, system, _CoreResult(child.status, lifted, node))
        )
        parent["kind"] = "return"
        return
    if parent["kind"] != "await_components":
        raise CubicReductionError("regional child has no parent frame")
    parent["component_results"].append(_regional_core_dict(child))
    index = len(parent["component_results"])
    if index < len(parent["components"]):
        _regional_push_child(
            frames,
            _regional_system(parent["components"][index]["system"]),
        )
        return
    assignments = [0] * system.variable_count
    statuses: list[str] = []
    children: list[dict[str, Any]] = []
    for component, result_value in zip(
        parent["components"],
        parent["component_results"],
        strict=True,
    ):
        result = _regional_core(result_value)
        statuses.append(result.status)
        if result.assignment is not None:
            for column, value in zip(
                component["columns"],
                result.assignment,
                strict=True,
            ):
                assignments[int(column)] = value
        children.append(
            {
                "columns": [int(column) + 1 for column in component["columns"]],
                "proof": result.proof,
            }
        )
    if "unsat" in statuses:
        status = "unsat"
        assignment = None
    elif "unresolved" in statuses:
        status = "unresolved"
        assignment = None
    else:
        status = "sat"
        assignment = tuple(assignments)
        if not _system_satisfied(system, assignment, context.ledger):
            raise CubicReductionError("regional component assignment is invalid")
    node = _proof_node(
        context,
        {
            "kind": "component_split",
            "system": system.as_dict(),
            "system_sha256": system.sha256,
            "status": status,
            "assignment": None if assignment is None else list(assignment),
            "components": children,
            "progress_event": parent["progress_event"],
        },
    )
    parent["result"] = _regional_core_dict(
        _memoize(context, system, _CoreResult(status, assignment, node))
    )
    parent["kind"] = "return"


def _regional_reduction_step(
    context: _Context,
    frames: list[dict[str, Any]],
    continuation: dict[str, Any] | None = None,
) -> None:
    if not frames:
        raise CubicReductionError("regional reduction frontier is empty")
    frame = frames[-1]
    kind = frame["kind"]
    if kind == "build_system":
        canonical = tuple(
            tuple(int(item) for item in clause) for clause in frame["source"]
        )
        _, system = system_from_cubic_formula(canonical, ledger=context.ledger)
        if continuation is not None:
            continuation["root_system"] = system.as_dict()
        frame.clear()
        frame.update({"kind": "enter", "system": system.as_dict()})
        return
    if kind == "return":
        if len(frames) == 1:
            return
        _regional_attach_child(context, frames)
        return
    if kind == "enter":
        system = _regional_system(frame["system"])
        context.ledger.observe_system(system)
        source_sha256 = system.sha256
        cached = context.memo.get(source_sha256)
        if cached is not None:
            context.ledger.cache_hits += 1
            event = context.progress.replace(
                kind="canonical_cache_hit",
                component_before=system.variable_count**2,
                component_after=0,
                source_sha256=source_sha256,
                target_sha256=None,
            )
            node = _proof_node(
                context,
                {
                    "kind": "canonical_cache_hit",
                    "system": system.as_dict(),
                    "system_sha256": source_sha256,
                    "status": cached.status,
                    "assignment": (
                        None
                        if cached.assignment is None
                        else list(cached.assignment)
                    ),
                    "reference_proof_sha256": cached.proof_sha256,
                    "progress_event": event,
                },
            )
            frame["result"] = _regional_core_dict(
                _CoreResult(cached.status, cached.assignment, node)
            )
            frame["kind"] = "return"
            return
        context.ledger.cache_misses += 1
        affine = _affine_profile(system, context.ledger)
        if not affine.consistent:
            frame["result"] = _regional_core_dict(
                _terminal_result(
                    context,
                    system,
                    kind="affine_contradiction",
                    status="unsat",
                    assignment=None,
                    certificate={"kind": "inconsistent_exact_rref"},
                )
            )
            frame["kind"] = "return"
            return
        zero_columns = tuple(
            column
            for column in range(system.variable_count)
            if all(row[column] == 0 for row in system.coefficients)
        )
        if zero_columns:
            target, offset, transform = _drop_unconstrained(
                system,
                zero_columns,
                context.ledger,
            )
            event = context.progress.replace(
                kind="drop_unconstrained_variables",
                component_before=system.variable_count**2,
                component_after=target.variable_count**2,
                source_sha256=source_sha256,
                target_sha256=target.sha256,
            )
            frame.update(
                {
                    "kind": "await_child",
                    "action": _regional_action_dict(
                        {
                            "target": target,
                            "offset": offset,
                            "transform": transform,
                            "certificate": {
                                "kind": "drop_unconstrained_variables",
                                "columns": [index + 1 for index in zero_columns],
                                "offset": list(offset),
                                "transform": [list(row) for row in transform],
                            },
                        }
                    ),
                    "strategy_order": [],
                    "attempted": [],
                    "progress_event": event,
                }
            )
            _regional_push_child(frames, target)
            return
        components = _components(system, context.ledger)
        if len(components) > 1:
            context.ledger.component_splits += 1
            context.ledger.components_created += len(components)
            child_potential = sum(child.variable_count**2 for _, child in components)
            event = context.progress.replace(
                kind="component_split",
                component_before=system.variable_count**2,
                component_after=child_potential,
                source_sha256=source_sha256,
                target_sha256=_digest([child.sha256 for _, child in components]),
            )
            encoded_components = [
                {
                    "columns": list(columns),
                    "system": child.as_dict(),
                }
                for columns, child in components
            ]
            frame.update(
                {
                    "kind": "await_components",
                    "components": encoded_components,
                    "component_results": [],
                    "progress_event": event,
                }
            )
            _regional_push_child(frames, components[0][1])
            return
        if system.variable_count == 0:
            node = _proof_node(
                context,
                {
                    "kind": "empty_system",
                    "system": system.as_dict(),
                    "system_sha256": source_sha256,
                    "status": "sat",
                    "assignment": [],
                    "certificate": {"kind": "empty_consistent_system"},
                    "progress_event": None,
                },
            )
            frame["result"] = _regional_core_dict(
                _memoize(context, system, _CoreResult("sat", (), node))
            )
            frame["kind"] = "return"
            return
        order = context.preference.order(
            context.field_state,
            nullity=affine.nullity,
            terminal_cap=context.profile.terminal_nullity,
            schedule_mode=context.profile.schedule_mode,
            literal_probing=context.profile.literal_probing,
        )
        frame.update(
            {
                "kind": "strategies",
                "affine": _regional_affine_dict(affine),
                "strategy_order": list(order),
                "strategy_index": 0,
                "attempted": [],
            }
        )
        return
    if kind == "strategies":
        system = _regional_system(frame["system"])
        affine = _regional_affine(frame["affine"])
        order = tuple(str(item) for item in frame["strategy_order"])
        strategy_index = int(frame["strategy_index"])
        if strategy_index >= len(order):
            frame["result"] = _regional_core_dict(
                _terminal_result(
                    context,
                    system,
                    kind="unresolved_residual",
                    status="unresolved",
                    assignment=None,
                    certificate={
                        "kind": "finite_rule_set_exhausted",
                        "rank": affine.rank,
                        "nullity": affine.nullity,
                        "terminal_nullity_cap": context.profile.terminal_nullity,
                        "strategy_order": list(order),
                        "attempted": list(frame["attempted"]),
                    },
                )
            )
            frame["kind"] = "return"
            return
        strategy = order[strategy_index]
        work_before = context.ledger.work_units()
        projections_before = context.ledger.projection_states_checked
        action = _regional_strategy_action(context, system, affine, strategy)
        work = context.ledger.work_units() - work_before
        projections = (
            context.ledger.projection_states_checked - projections_before
        )
        target = None if action is None or action.get("terminal") else action["target"]
        removed = 0 if target is None else system.variable_count - target.variable_count
        context.field_state = context.preference.observe(
            context.field_state,
            strategy,
            applicable=action is not None,
            terminal=bool(action is not None and action.get("terminal")),
            variables_removed=removed,
            work=work,
            projections=projections,
            first_choice=strategy_index == 0,
        )
        context.ledger.field_observations += 1
        frame["attempted"].append(
            {
                "strategy": strategy,
                "order": strategy_index,
                "applicable": action is not None,
                "work": max(1, work),
                "projection_states_checked": projections,
            }
        )
        frame["strategy_index"] = strategy_index + 1
        if action is None:
            return
        if action["terminal"]:
            frame["result"] = _regional_core_dict(
                _terminal_result(
                    context,
                    system,
                    kind=str(action["certificate"]["kind"]),
                    status=str(action["status"]),
                    assignment=action["assignment"],
                    certificate={
                        **action["certificate"],
                        "strategy_order": list(order),
                        "attempted": list(frame["attempted"]),
                    },
                )
            )
            frame["kind"] = "return"
            return
        target_system = action["target"]
        event = context.progress.replace(
            kind=str(action["certificate"]["kind"]),
            component_before=system.variable_count**2,
            component_after=target_system.variable_count**2,
            source_sha256=system.sha256,
            target_sha256=target_system.sha256,
        )
        frame.update(
            {
                "kind": "await_child",
                "action": _regional_action_dict(action),
                "progress_event": event,
            }
        )
        _regional_push_child(frames, target_system)
        return
    if kind in {"await_child", "await_components"}:
        raise CubicReductionError("regional reduction is waiting for a child")
    raise CubicReductionError("regional reduction frame kind is invalid")


def _regional_finish_reduction(
    state: dict[str, Any],
    context: _Context,
    core: _CoreResult,
    root_system: AffineBooleanSystem,
) -> dict[str, Any]:
    source = tuple(tuple(int(item) for item in clause) for clause in state["source"])
    if context.progress.current != 0:
        raise CubicReductionError("regional reduction frontier did not halt")
    assignment = core.assignment
    if core.status == "sat":
        if assignment is None or not all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in source
        ):
            raise CubicReductionError("regional root SAT witness failed the cubic source")
    elif assignment is not None:
        raise CubicReductionError("regional non-SAT root carries an assignment")
    input_bits = max(
        (
            abs(value).bit_length()
            for row in root_system.coefficients
            for value in row
        ),
        default=0,
    )
    input_bits = max(
        input_bits,
        *(abs(value).bit_length() for value in root_system.rhs),
    )
    algorithm = candidate_algorithm_descriptor(context.profile)
    proof_bytes = len(_canonical_bytes(core.proof))
    coefficient_bit_bound = input_bits + 2 * root_system.variable_count + 1
    if context.ledger.maximum_integer_bit_length > coefficient_bit_bound:
        raise CubicReductionError("regional coefficient growth exceeded conservative bound")
    result: dict[str, Any] = {
        "schema": SCHEMA,
        "algorithm": algorithm,
        "formula": [list(clause) for clause in source],
        "formula_sha256": _digest([list(clause) for clause in source]),
        "source_system_sha256": root_system.sha256,
        "status": core.status,
        "assignment": None if assignment is None else list(assignment),
        "proof": core.proof,
        "progress": {
            "potential_name": "active_residual_squared_variable_sum",
            "initial": context.progress.initial,
            "final": context.progress.current,
            "events": context.progress.events,
            "strictly_descending": all(
                event["global_after"] < event["global_before"]
                for event in context.progress.events
            ),
            "event_count": len(context.progress.events),
            "event_bound": root_system.variable_count**2,
        },
        "field_preference": context.preference.inspect(
            context.field_state,
            terminal_cap=context.profile.terminal_nullity,
            schedule_mode=context.profile.schedule_mode,
            literal_probing=context.profile.literal_probing,
        ),
        "resource_ledger": context.ledger.as_dict(),
        "representation": {
            "input_integer_bit_length": input_bits,
            "coefficient_bit_length_bound": coefficient_bit_bound,
            "observed_maximum_integer_bit_length": context.ledger.maximum_integer_bit_length,
            "bound_respected": True,
            "proof_bytes": proof_bytes,
            "proof_nodes": context.ledger.proof_nodes,
            "canonical_residuals": len(context.memo),
            "cache_hits": context.ledger.cache_hits,
            "cache_persistence": "invocation_local_only",
        },
        "assessment": {
            "truth_claim": core.status if core.status in ("sat", "unsat") else None,
            "rule_set_complete_on_input": core.status != "unresolved",
            "p_equals_np_claim": False,
            "remaining_obligation": (
                None
                if core.status != "unresolved"
                else "prove a new exact reduction covering this residual or prove a total alternative"
            ),
        },
    }
    result["result_sha256"] = _digest(result)
    return result


def _regional_fault(
    state: dict[str, Any],
    *,
    kind: str,
    error: Exception,
) -> dict[str, Any]:
    result = {
        "status": "fault",
        "evidence": {
            "kind": kind,
            "error": str(error),
        },
    }
    continuation = dict(state["continuation"])
    continuation["result_sha256"] = _digest(result)
    state["continuation"] = continuation
    state["phase"] = "fault"
    state["result"] = result
    return result


def _regional_validate_state(state: Any) -> dict[str, Any]:
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
        raise CubicReductionError("regional cubic state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise CubicReductionError("regional cubic state schema is invalid")
    if not isinstance(state["source"], list):
        raise CubicReductionError("regional cubic source is invalid")
    canonical = kernel.canonical_cubic_formula(state["source"])
    if state["source"] != [list(clause) for clause in canonical]:
        raise CubicReductionError("regional cubic source is not canonical")
    if not isinstance(state["profile"], Mapping):
        raise CubicReductionError("regional cubic profile is invalid")
    if not isinstance(state["continuation"], Mapping):
        raise CubicReductionError("regional cubic continuation is invalid")
    continuation = state["continuation"]
    if continuation.get("source_sha256") != _digest(state["source"]):
        raise CubicReductionError("regional cubic source digest is invalid")
    if not isinstance(continuation.get("result_sha256"), (str, type(None))):
        raise CubicReductionError("regional cubic result digest is invalid")
    if not isinstance(continuation.get("frontier"), list):
        raise CubicReductionError("regional cubic frontier is invalid")
    if not isinstance(continuation.get("memo"), Mapping):
        raise CubicReductionError("regional cubic memo is invalid")
    if not isinstance(continuation.get("progress"), Mapping):
        raise CubicReductionError("regional cubic progress is invalid")
    if not isinstance(continuation.get("kernel_state"), Mapping):
        raise CubicReductionError("regional cubic kernel state is invalid")
    if not isinstance(continuation.get("mode"), str) or continuation["mode"] not in {
        "kernel_decision",
        "recursive_reduction",
    }:
        raise CubicReductionError("regional cubic mode is invalid")
    if continuation.get("subprocedure") != continuation["mode"]:
        raise CubicReductionError("regional cubic subprocedure is invalid")
    if not isinstance(state["journal"], list):
        raise CubicReductionError("regional cubic journal is invalid")
    result = state["result"]
    if result is not None and not isinstance(result, Mapping):
        raise CubicReductionError("regional cubic result is invalid")
    if result is None and continuation["result_sha256"] is not None:
        raise CubicReductionError("regional cubic result digest is premature")
    if result is not None and continuation["result_sha256"] != _digest(result):
        raise CubicReductionError("regional cubic result digest is invalid")
    return dict(state)


def regional_state(
    formula: Sequence[Sequence[int]],
    *,
    mode: str = "kernel_decision",
    subprocedure: str | None = None,
    profile: ReductionProfile | Mapping[str, Any] | None = None,
    pivot_columns: Sequence[int] | None = None,
) -> dict[str, Any]:
    """Create a canonical JSON state for either cubic exact subprocedure."""
    selected = mode if subprocedure is None else subprocedure
    if selected not in {"kernel_decision", "recursive_reduction"}:
        raise CubicReductionError("regional cubic mode is invalid")
    canonical = kernel.canonical_cubic_formula(formula)
    source = [list(clause) for clause in canonical]
    source_digest = _digest(source)
    if selected == "recursive_reduction":
        if profile is None:
            regional_profile = asdict(ReductionProfile())
        elif isinstance(profile, ReductionProfile):
            regional_profile = asdict(profile)
        elif isinstance(profile, Mapping):
            regional_profile = dict(profile)
            try:
                regional_profile = asdict(ReductionProfile(**regional_profile))
            except (TypeError, ValueError) as exc:
                raise CubicReductionError("regional reduction profile is invalid") from exc
        else:
            raise CubicReductionError("regional reduction profile is invalid")
        initial_progress = len(canonical) ** 2
        frontier = [
            {
                "kind": "build_system",
                "source": source,
            }
        ]
    else:
        if pivot_columns is None and isinstance(profile, Mapping):
            pivot_columns = profile.get("pivot_columns")
        if pivot_columns is not None:
            if isinstance(pivot_columns, (str, bytes)):
                raise CubicReductionError("regional pivot columns are invalid")
            pivot_columns = [int(item) for item in pivot_columns]
        regional_profile = {
            "pivot_columns": (
                None if pivot_columns is None else list(pivot_columns)
            )
        }
        initial_progress = 2
        frontier = [
            {"kind": "kernel_profile"},
        ]
    continuation = {
        "mode": selected,
        "subprocedure": selected,
        "source_sha256": source_digest,
        "result_sha256": None,
        "frontier": frontier,
        "memo": {},
        "progress": {
            "current": initial_progress,
            "initial": initial_progress,
            "events": [],
        },
        "preference_field": (
            [
                int(value)
                for value in _PreferenceField.initial_state()._field.reshape(-1)
            ]
            if selected == "recursive_reduction"
            else None
        ),
        "kernel_state": {
            "profile": None,
            "decision": None,
            "candidate_cursor": 0,
        },
    }
    ledger = _WorkLedger().as_dict()
    ledger.update({"primitive_expansions": 0, "work_total": 0})
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": source,
        "profile": regional_profile,
        "phase": "reduction_system" if selected == "recursive_reduction" else "kernel_profile",
        "continuation": continuation,
        "journal": [],
        "ledger": ledger,
        "result": None,
    }


def _regional_kernel_system(system: Mapping[str, Any]) -> dict[str, Any]:
    """Decode only the rational kernel data needed by one cursor step."""
    if not isinstance(system, Mapping):
        raise CubicReductionError("regional kernel system is invalid")
    try:
        return {
            "pivot_columns_zero_based": tuple(
                int(item) for item in system["pivot_columns_zero_based"]
            ),
            "free_columns_zero_based": tuple(
                int(item) for item in system["free_columns_zero_based"]
            ),
            "pivot_free_coefficients": tuple(
                tuple(_regional_fraction(item) for item in row)
                for row in system["pivot_free_coefficients"]
            ),
            "pivot_free_supports": tuple(
                int(item) for item in system["pivot_free_supports"]
            ),
            "system_digest": str(system["system_digest"]),
            "maximum_numerator_bits": int(system["maximum_numerator_bits"]),
            "maximum_denominator_bits": int(system["maximum_denominator_bits"]),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise CubicReductionError("regional kernel system is invalid") from exc


def _regional_kernel_system_dict(system: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pivot_columns_zero_based": [
            int(item) for item in system["pivot_columns_zero_based"]
        ],
        "free_columns_zero_based": [
            int(item) for item in system["free_columns_zero_based"]
        ],
        "pivot_free_coefficients": [
            [_regional_fraction_text(item) for item in row]
            for row in system["pivot_free_coefficients"]
        ],
        "pivot_free_supports": [
            int(item) for item in system["pivot_free_supports"]
        ],
        "system_digest": str(system["system_digest"]),
        "maximum_numerator_bits": int(system["maximum_numerator_bits"]),
        "maximum_denominator_bits": int(system["maximum_denominator_bits"]),
    }


def _regional_kernel_common(
    source: Sequence[Sequence[int]],
    system: Mapping[str, Any],
) -> dict[str, Any]:
    pivots = tuple(int(item) for item in system["pivot_columns_zero_based"])
    free = tuple(int(item) for item in system["free_columns_zero_based"])
    supports = tuple(int(item) for item in system["pivot_free_supports"])
    histogram = {
        str(support): supports.count(support)
        for support in sorted(set(supports))
    }
    size = len(source)
    return {
        "clauses": size,
        "variables": size,
        "rank": len(pivots),
        "nullity": len(free),
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "candidate_kernel_vectors": 1 << len(free),
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": histogram,
        "system_digest": system["system_digest"],
        "maximum_numerator_bits": int(system["maximum_numerator_bits"]),
        "maximum_denominator_bits": int(system["maximum_denominator_bits"]),
    }


def _regional_kernel_profile(
    source: Sequence[Sequence[int]],
    system: Mapping[str, Any],
) -> dict[str, Any]:
    pivots = tuple(int(item) for item in system["pivot_columns_zero_based"])
    free = tuple(int(item) for item in system["free_columns_zero_based"])
    coefficients = system["pivot_free_coefficients"]
    basis: list[list[str]] = []
    for free_index in range(len(free)):
        free_values = tuple(
            Fraction(int(index == free_index)) for index in range(len(free))
        )
        vector = kernel._candidate_vector(
            len(source),
            pivots,
            free,
            coefficients,
            free_values,
        )
        basis.append([_regional_fraction_text(value) for value in vector])
    supports = tuple(int(item) for item in system["pivot_free_supports"])
    return {
        "clauses": len(source),
        "variables": len(source),
        "rank": len(pivots),
        "nullity": len(free),
        "candidate_kernel_vectors": 1 << len(free),
        "pivot_columns": [column + 1 for column in pivots],
        "free_columns": [column + 1 for column in free],
        "kernel_basis": basis,
        "maximum_pivot_free_support": max(supports, default=0),
        "pivot_free_support_histogram": {
            str(support): supports.count(support)
            for support in sorted(set(supports))
        },
        "fraction_updates": int(system["fraction_updates"]),
        "maximum_numerator_bits": int(system["maximum_numerator_bits"]),
        "maximum_denominator_bits": int(system["maximum_denominator_bits"]),
        "system_digest": system["system_digest"],
    }


def _regional_kernel_terminal(
    state: dict[str, Any],
    decision: Mapping[str, Any],
) -> None:
    continuation = state["continuation"]
    kernel_state = dict(continuation["kernel_state"])
    kernel_state["decision"] = dict(decision)
    continuation["kernel_state"] = kernel_state
    continuation["result_sha256"] = _digest(decision)
    state["result"] = dict(decision)
    state["phase"] = "done"
    state["journal"].append(
        {
            "index": len(state["journal"]),
            "kind": "kernel_terminal",
            "source_sha256": continuation["source_sha256"],
            "result_sha256": continuation["result_sha256"],
        }
    )


def _regional_kernel_step(
    state: dict[str, Any],
) -> None:
    continuation = state["continuation"]
    frontier = continuation["frontier"]
    if not frontier:
        raise CubicReductionError("regional kernel frontier is empty")
    frame = frontier.pop()
    source = state["source"]
    kernel_state = dict(continuation["kernel_state"])
    if frame["kind"] == "kernel_profile":
        pivot_value = state["profile"].get("pivot_columns")
        canonical_system = kernel._system(tuple(tuple(item) for item in source))
        profile = _regional_kernel_profile(source, canonical_system)
        if pivot_value is None:
            system = canonical_system
        else:
            requested = tuple(int(item) for item in pivot_value)
            rank = len(canonical_system["pivot_columns_zero_based"])
            size = len(source)
            if (
                len(requested) != rank
                or len(set(requested)) != len(requested)
                or any(column < 1 or column > size for column in requested)
            ):
                raise kernel.CubicKernelDecisionError(
                    f"pivot_columns must contain exactly {rank} columns"
                )
            system = kernel._system_for_pivot_basis(
                kernel.incidence_matrix(tuple(tuple(item) for item in source)),
                tuple(column - 1 for column in requested),
            )
            if system is None:
                raise kernel.CubicKernelDecisionError(
                    "pivot_columns do not form a column basis"
                )
        kernel_state["profile"] = profile
        kernel_state["system"] = _regional_kernel_system_dict(system)
        kernel_state["candidate_cursor"] = 0
        kernel_state["rejections"] = []
        frontier.append({"kind": "kernel_prepare"})
        state["phase"] = "kernel_prepare"
        state["journal"].append(
            {
                "index": len(state["journal"]),
                "kind": "kernel_profile",
                "source_sha256": continuation["source_sha256"],
            }
        )
    elif frame["kind"] == "kernel_prepare":
        system = _regional_kernel_system(kernel_state["system"])
        common = _regional_kernel_common(source, system)
        nullity = len(system["free_columns_zero_based"])
        if nullity == 0:
            _regional_kernel_terminal(
                state,
                {
                    **common,
                    "status": "unsat",
                    "reason": "full_rank",
                    "candidates_checked": 0,
                    "assignment": None,
                    "kernel_vector": None,
                    "rejection_digest": None,
                    "two_sat_certificate": None,
                },
            )
        elif len(source) % 3:
            _regional_kernel_terminal(
                state,
                {
                    **common,
                    "status": "unsat",
                    "reason": "cardinality_not_divisible_by_three",
                    "candidates_checked": 0,
                    "assignment": None,
                    "kernel_vector": None,
                    "rejection_digest": None,
                    "two_sat_certificate": None,
                },
            )
        elif max(system["pivot_free_supports"], default=0) <= 2:
            frontier.append({"kind": "kernel_2sat"})
            state["phase"] = "kernel_2sat"
        else:
            frontier.append({"kind": "kernel_candidate"})
            state["phase"] = "kernel_candidate"
            kernel_state["candidate_bound"] = 1 << nullity
    elif frame["kind"] == "kernel_2sat":
        system = _regional_kernel_system(kernel_state["system"])
        assignment, certificate = kernel._bounded_support_2sat(system)
        certificate = {
            **certificate,
            "satisfying_free_bits": (
                None if assignment is None else list(assignment)
            ),
        }
        common = _regional_kernel_common(source, system)
        if assignment is None:
            decision = {
                **common,
                "status": "unsat",
                "reason": (
                    "forced_zero_pivot"
                    if certificate["empty_relation_pivot"] is not None
                    else "bounded_support_2sat_unsat"
                ),
                "candidates_checked": 0,
                "assignment": None,
                "kernel_vector": None,
                "rejection_digest": None,
                "two_sat_certificate": certificate,
            }
        else:
            free_values = tuple(Fraction(3 * bit - 1) for bit in assignment)
            vector = kernel._candidate_vector(
                len(source),
                system["pivot_columns_zero_based"],
                system["free_columns_zero_based"],
                system["pivot_free_coefficients"],
                free_values,
            )
            decision = {
                **common,
                "status": "sat",
                "reason": "bounded_support_2sat_sat",
                "candidates_checked": 0,
                "assignment": [
                    int((value + 1) / 3) for value in vector
                ],
                "kernel_vector": [int(value) for value in vector],
                "rejection_digest": None,
                "two_sat_certificate": certificate,
            }
        _regional_kernel_terminal(state, decision)
    elif frame["kind"] == "kernel_candidate":
        system = _regional_kernel_system(kernel_state["system"])
        free = system["free_columns_zero_based"]
        pivots = system["pivot_columns_zero_based"]
        coefficients = system["pivot_free_coefficients"]
        cursor = int(kernel_state["candidate_cursor"])
        bound = int(kernel_state["candidate_bound"])
        if cursor >= bound:
            rejected = "".join(kernel_state["rejections"])
            _regional_kernel_terminal(
                state,
                {
                    **_regional_kernel_common(source, system),
                    "status": "unsat",
                    "reason": "alphabet_exhausted",
                    "candidates_checked": cursor,
                    "assignment": None,
                    "kernel_vector": None,
                    "rejection_digest": hashlib.sha256(
                        rejected.encode("ascii")
                    ).hexdigest(),
                    "two_sat_certificate": None,
                },
            )
        else:
            bits = tuple(
                (cursor >> (len(free) - index - 1)) & 1
                for index in range(len(free))
            )
            free_values = tuple(
                Fraction(-1 if bit == 0 else 2) for bit in bits
            )
            vector = kernel._candidate_vector(
                len(source),
                pivots,
                free,
                coefficients,
                free_values,
            )
            invalid = next(
                (
                    (column, vector[column])
                    for column in pivots
                    if vector[column] not in (Fraction(-1), Fraction(2))
                ),
                None,
            )
            kernel_state["candidate_cursor"] = cursor + 1
            if invalid is not None:
                column, value = invalid
                kernel_state["rejections"] = [
                    *kernel_state["rejections"],
                    (
                        ",".join(
                            _regional_fraction_text(item)
                            for item in free_values
                        )
                        + f"|{column + 1}|{_regional_fraction_text(value)}\n"
                    ),
                ]
                frontier.append({"kind": "kernel_candidate"})
            else:
                assignment = [
                    int((value + 1) / 3) for value in vector
                ]
                _regional_kernel_terminal(
                    state,
                    {
                        **_regional_kernel_common(source, system),
                        "status": "sat",
                        "reason": "alphabet_kernel_vector",
                        "candidates_checked": cursor + 1,
                        "assignment": assignment,
                        "kernel_vector": [int(value) for value in vector],
                        "rejection_digest": hashlib.sha256(
                            "".join(kernel_state["rejections"]).encode("ascii")
                        ).hexdigest(),
                        "two_sat_certificate": None,
                    },
                )
    else:
        raise CubicReductionError("regional kernel frame kind is invalid")
    if state["result"] is not None:
        kernel_state = dict(continuation["kernel_state"])
    continuation["kernel_state"] = kernel_state

def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance one cubic subprocedure by at most ``quantum`` expansions."""
    checked = _regional_validate_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise CubicReductionError("regional cubic kernel takes no arguments")
    quantum = _exact_integer(
        quantum,
        "regional cubic quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )

    if checked["phase"] == "done":
        return KernelResult(
            state=checked,
            status="done",
            work=0,
            output=checked["result"],
        )
    if checked["phase"] == "fault":
        return KernelResult(
            state=checked,
            status="fault",
            work=0,
            output=checked["result"],
        )
    updated = json.loads(_canonical_bytes(checked).decode("utf-8"))
    mode = updated["continuation"]["mode"]
    executed = 0
    try:
        if mode == "kernel_decision":
            while executed < quantum and updated["result"] is None:
                _regional_kernel_step(updated)
                executed += 1
        else:
            context = _regional_context(updated)
            frontier = updated["continuation"]["frontier"]
            while executed < quantum and updated["result"] is None:
                if not frontier:
                    root_system_value = updated["continuation"].get("root_system")
                    root_system = _regional_system(root_system_value)
                    root_value = updated["continuation"].get("root_result")
                    if not isinstance(root_value, Mapping):
                        raise CubicReductionError("regional root result is missing")
                    updated["result"] = _regional_finish_reduction(
                        updated,
                        context,
                        _regional_core(root_value),
                        root_system,
                    )
                    updated["continuation"]["result_sha256"] = _digest(
                        updated["result"]
                    )
                    updated["phase"] = "done"
                    break
                progress_before = len(context.progress.events)
                _regional_reduction_step(
                    context,
                    frontier,
                    updated["continuation"],
                )
                executed += 1
                for event in context.progress.events[progress_before:]:
                    updated["journal"].append(
                        {
                            "index": len(updated["journal"]),
                            "kind": "progress",
                            "event": dict(event),
                        }
                    )
                if len(frontier) == 1 and frontier[0].get("kind") == "return":
                    root_frame = frontier.pop()
                    updated["continuation"]["root_result"] = root_frame["result"]
                if not frontier and updated["result"] is None:
                    root_value = updated["continuation"].get("root_result")
                    if isinstance(root_value, Mapping):
                        root_system = _regional_system(
                            updated["continuation"]["root_system"]
                        )
                        updated["result"] = _regional_finish_reduction(
                            updated,
                            context,
                            _regional_core(root_value),
                            root_system,
                        )
                        updated["continuation"]["result_sha256"] = _digest(
                            updated["result"]
                        )
                        updated["phase"] = "done"
                if updated["result"] is None and frontier:
                    updated["phase"] = f"reduction_{frontier[-1]['kind']}"
            if updated["phase"] == "done":
                terminal_result = updated["result"]
                if not isinstance(terminal_result, Mapping):
                    raise CubicReductionError("regional terminal result is missing")
                updated["journal"].append(
                    {
                        "index": len(updated["journal"]),
                        "kind": "terminal",
                        "status": terminal_result["status"],
                        "result_sha256": updated["continuation"]["result_sha256"],
                    }
                )
            _regional_sync(updated, context, primitive=executed)
        if mode == "kernel_decision":
            ledger = dict(updated["ledger"])
            ledger["primitive_expansions"] = int(ledger.get("primitive_expansions", 0)) + executed
            ledger["work_total"] = int(ledger.get("work_total", 0)) + executed
            updated["ledger"] = ledger
    except (
        CubicReductionError,
        kernel.CubicKernelDecisionError,
        ValueError,
        TypeError,
        KeyError,
    ) as exc:
        executed = max(1, executed)
        if mode == "kernel_decision":
            ledger = dict(updated["ledger"])
            ledger["primitive_expansions"] = (
                int(ledger.get("primitive_expansions", 0)) + executed
            )
            ledger["work_total"] = int(ledger.get("work_total", 0)) + executed
            updated["ledger"] = ledger
        elif "context" in locals():
            _regional_sync(updated, context, primitive=executed)
        _regional_fault(
            updated,
            kind=type(exc).__name__,
            error=exc,
        )
    status = "yield"
    if updated["phase"] == "done":
        status = "done"
    elif updated["phase"] == "fault":
        status = "fault"
    output = updated["result"] if status != "yield" else None
    return KernelResult(
        state=updated,
        status=status,
        work=min(quantum, executed),
        output=output,
    )
__all__ = [
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "regional_state",
    "regional_kernel",
    "ALGORITHM_SCHEMA",
    "FIELD_SCHEMA",
    "SCHEMA",
    "SYSTEM_SCHEMA",
    "AffineBooleanSystem",
    "CubicReductionError",
    "ReductionProfile",
    "candidate_algorithm_descriptor",
    "canonical_affine_system",
    "solve_cubic_reduction",
    "system_from_cubic_formula",
]
