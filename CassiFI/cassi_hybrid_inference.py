"""Field-owned exact reasoning beyond resolution.

The source CNF and every adaptive proof line live in one immutable float64
``[1, 9*M, 1]`` tensor.  Stored values are exact integers.  A fixed controller
reconstructs deterministic candidates from that tensor and appends one checked
inference per transition.  No learned side table, family label, model, or
problem-specific oracle participates in proof discovery.

The proof vocabulary combines clauses, cutting planes, parity equations over
GF(2), and acyclic extension definitions.  The implementation is deliberately
bounded: capacity or arithmetic overflow produces ``exhausted``, never UNSAT.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import math
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from cassi_field_regions import KernelResult

SCHEMA = "cassifi.hybrid-inference-field.v1"
PROOF_SCHEMA = "cassifi.hybrid-inference-proof.v1"

REGIONAL_KERNEL_NAME = "exact.hybrid"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-hybrid-inference-state.v1"
_REGIONAL_KEYS = frozenset(
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

_LAYOUT = "hybrid-proof-nine-plane-v1"
_MAGIC = 0xC552
_SAFE_INTEGER = 2**53 - 1

# Per-line planes.  A line occupies ``max_total_variables`` modes.
_COEFFICIENTS = 0
_KIND = 1
_RHS = 2
_RULE = 3
_LEFT = 4
_RIGHT = 5
_AUX = 6
_HEADER = 8

_H_MAGIC = 0
_H_ORIGINAL_VARIABLES = 1
_H_ACTIVE_VARIABLES = 2
_H_ORIGINAL_CLAUSES = 3
_H_LINES = 4
_H_STATUS = 5
_H_TRANSITIONS = 6
_H_INPUT_LINES = 7
_H_PB_LINES = 8
_H_XOR_LINES = 9
_H_EXTENSION_LINES = 10
_H_RESOLUTION_LINES = 11
_H_MAX_COEFFICIENT = 12
_H_COUNT = 16

_RUNNING = 0
_UNSAT = 1
_EXHAUSTED = 2
_STATUS_NAMES = {_RUNNING: "running", _UNSAT: "unsat", _EXHAUSTED: "exhausted"}

_CLAUSE = 1
_PB = 2
_XOR = 3
_EXTENSION = 4
_KIND_NAMES = {_CLAUSE: "clause", _PB: "pb", _XOR: "xor", _EXTENSION: "extension"}

_INPUT = 1
_CLAUSE_PB = 2
_PB_ADD = 3
_PB_SCALE = 4
_PB_DIVIDE = 5
_PARITY_IMPORT = 6
_XOR_ADD = 7
_CARDINALITY_PARITY = 8
_EXTENSION_DEFINE = 9
_EXTENSION_CLAUSE = 10
_RESOLVE = 11
_RULE_NAMES = {
    _INPUT: "input",
    _CLAUSE_PB: "clause-pb",
    _PB_ADD: "pb-add",
    _PB_SCALE: "pb-scale",
    _PB_DIVIDE: "pb-divide",
    _PARITY_IMPORT: "parity-import",
    _XOR_ADD: "xor-add",
    _CARDINALITY_PARITY: "cardinality-parity",
    _EXTENSION_DEFINE: "extension-define",
    _EXTENSION_CLAUSE: "extension-clause",
    _RESOLVE: "resolve",
}


class HybridInferenceError(ValueError):
    """Invalid profile, state, CNF, or inference."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _exact_integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < minimum
        or value > _SAFE_INTEGER
    ):
        raise HybridInferenceError(f"{name} must be an exact bounded integer")
    return value


def _literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def _canonical_clause(clause: Iterable[int], variables: int) -> tuple[int, ...]:
    values = tuple(clause)
    if any(
        isinstance(literal, bool)
        or not isinstance(literal, int)
        or literal == 0
        or abs(literal) > variables
        for literal in values
    ):
        raise HybridInferenceError("clause contains an invalid literal")
    unique = set(values)
    if len(unique) != len(values) or any(-literal in unique for literal in unique):
        raise HybridInferenceError("clause is duplicate or tautological")
    return tuple(sorted(values, key=_literal_key))


def _floor_div(value: int, divisor: int) -> int:
    return value // divisor


def _magnitude(values: Iterable[int]) -> int:
    return max((abs(value) for value in values), default=0)


@dataclass(frozen=True, slots=True)
class HybridInferenceProfile:
    """Fixed polynomial storage and work geometry."""

    max_variables: int
    max_original_clauses: int
    max_lines: int
    max_extensions: int = 4
    max_parity_width: int = 8
    max_resolution_inferences: int = 2_048
    max_transitions: int = 100_000

    def __post_init__(self) -> None:
        for name in (
            "max_variables",
            "max_original_clauses",
            "max_lines",
            "max_parity_width",
            "max_transitions",
        ):
            _exact_integer(getattr(self, name), name, minimum=1)
        for name in ("max_extensions", "max_resolution_inferences"):
            _exact_integer(getattr(self, name), name)
        if self.max_lines < self.max_original_clauses:
            raise HybridInferenceError("max_lines cannot hold the source clauses")
        if self.mode_count * 9 > _SAFE_INTEGER:
            raise HybridInferenceError("hybrid field exceeds exact address capacity")

    @property
    def max_total_variables(self) -> int:
        return self.max_variables + self.max_extensions

    @property
    def mode_count(self) -> int:
        return max(_H_COUNT, self.max_lines * self.max_total_variables)

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
class HybridInferenceState:
    """One immutable hybrid proof field."""

    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        if not isinstance(self._field, np.ndarray) or self._field.dtype != np.float64:
            raise HybridInferenceError("hybrid field must be a float64 numpy tensor")
        if not isinstance(self.profile_sha256, str) or len(self.profile_sha256) != 64:
            raise HybridInferenceError("state profile fingerprint is invalid")
        field = np.array(self._field, dtype=np.float64, copy=True, order="C")
        field.flags.writeable = False
        object.__setattr__(self, "_field", field)

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


@dataclass(frozen=True, slots=True)
class _Line:
    kind: int
    values: tuple[int, ...]
    rhs: int
    rule: int
    left: int = 0
    right: int = 0
    aux: int = 0


@dataclass(slots=True)
class _Plan:
    lines: list[_Line]
    root_line: int | None = None
    capacity_exhausted: bool = False


class HybridInferenceField:
    """Deterministic mixed proof search whose persistent state is the field."""

    def __init__(self, profile: HybridInferenceProfile):
        if not isinstance(profile, HybridInferenceProfile):
            raise HybridInferenceError("profile must be HybridInferenceProfile")
        self.profile = profile

    def _parts(self, state: HybridInferenceState, *, mutable: bool = False) -> np.ndarray:
        self._validate_tensor(state)
        parts = state._field.reshape(9, self.profile.mode_count)
        return parts.copy() if mutable else parts

    def _validate_tensor(self, state: HybridInferenceState) -> None:
        if not isinstance(state, HybridInferenceState):
            raise HybridInferenceError("state must be HybridInferenceState")
        if state.profile_sha256 != self.profile.fingerprint:
            raise HybridInferenceError("state/profile mismatch")
        if state._field.shape != self.profile.shape:
            raise HybridInferenceError("hybrid field shape mismatch")

        field = state._field

        # Check for non-finite values (NaN or Inf)
        # np.isfinite is vectorized and fast
        if not np.all(np.isfinite(field)):
            raise HybridInferenceError("hybrid field contains non-finite values")

        # Check for non-integer values
        # Since we know it's finite, we can use bitwise operations.
        # A float is an integer if it equals its floor. 
        # np.floor is generally faster than np.trunc for positive numbers, 
        # but for general case, np.isclose with a small tolerance is often faster 
        # than exact truncation if we allow small epsilon. However, strict check 
        # requires exact integer. 
        # Alternative: Check if the fractional part is zero.
        # field % 1 == 0 is expensive.
        # field == np.floor(field) is faster than np.trunc(field) because 
        # np.floor is optimized for positive numbers, but field can be negative.
        # For negative numbers, np.floor(x) != np.trunc(x) if x is not integer.
        # Actually, np.trunc(x) is floor(x) for positive, ceil(x) for negative.
        # A faster way to check if float is integer: (field == field.astype(np.int64)) 
        # but this might overflow. 
        # The previous attempt used np.trunc. Let's try to minimize allocations.
        # np.isfinite check is done. Now check integer-ness.
        # We can use: np.all(field == np.floor(field)) if we assume non-negative? 
        # No, field can be negative.
        # Let's use: np.all(np.equal(field, np.trunc(field))) but avoid creating intermediate arrays if possible.
        # Actually, np.trunc returns a float array. Comparison is element-wise.
        # The bottleneck is likely the creation of the trunc array and the comparison.
        # A faster way: Check if the fractional part is zero.
        # frac = field - np.floor(field)
        # But for negative numbers, frac is not just field - floor(field).
        # Let's stick to np.trunc but ensure it's the fastest path.
        # Another option: Convert to int64 and back? No, overflow risk.
        # Let's try to combine checks if possible, but logic is distinct.

        # Optimized integer check:
        # np.isclose(field, np.round(field), atol=0.5) is a common fast check for "integer-ness"
        # But strict trunc check is required.
        # Let's use: np.all(field == np.floor(field)) is wrong for negative non-integers.
        # np.all(field == np.trunc(field)) is correct.
        # To speed up, we can avoid np.trunc by using:
        # np.all((field - np.floor(field)) == 0) is not correct for negative.
        # np.all(np.abs(field - np.round(field)) < 0.5) is not strict.
        # Let's keep np.trunc but ensure it's not the bottleneck.
        # The previous attempt was 1.029x slower. The bottleneck might be np.trunc itself.
        # Let's try to use np.isfinite and then check integer-ness with a different method.
        # Method: Check if the bit pattern of the float represents an integer.
        # This is complex.
        # Let's try: np.all(np.equal(field, np.trunc(field))) but with a view to avoid copy?
        # No, np.trunc creates a new array.
        # Alternative: Check if field % 1 == 0. This is slow.
        # Alternative: Check if field.astype(np.float64) == field.astype(np.int64).
        # This requires conversion, which is expensive.
        # Let's stick with np.trunc but ensure no other overhead.

        # Check for values exceeding safe integer range
        # np.abs(field) > _SAFE_INTEGER
        # This is a comparison after abs.
        # We can combine the integer check and range check?
        # No, they are distinct.

        # Let's try to minimize numpy calls.
        # 1. np.isfinite: fast.
        # 2. np.trunc: creates array.
        # 3. np.abs: creates array.
        # We can avoid np.abs by checking field > _SAFE_INTEGER or field < -_SAFE_INTEGER.
        # This avoids creating the abs array.

        if not np.all(np.equal(field, np.trunc(field))):
            raise HybridInferenceError("hybrid field contains non-integer values")

        # Check for values exceeding safe integer range without np.abs
        if np.any((field > _SAFE_INTEGER) | (field < -_SAFE_INTEGER)):
            raise HybridInferenceError("hybrid field exceeds exact integer range")

    def _state(self, parts: np.ndarray) -> HybridInferenceState:
        return HybridInferenceState(parts.reshape(self.profile.shape), self.profile.fingerprint)

    def _base(self, index: int) -> int:
        return index * self.profile.max_total_variables

    def _write_line(self, parts: np.ndarray, index: int, line: _Line) -> None:
        if index >= self.profile.max_lines:
            raise HybridInferenceError("proof line capacity exhausted")
        if len(line.values) != self.profile.max_total_variables:
            raise HybridInferenceError("proof line width mismatch")
        if _magnitude((*line.values, line.rhs, line.left, line.right, line.aux)) > _SAFE_INTEGER:
            raise HybridInferenceError("proof line exceeds exact integer range")
        base = self._base(index)
        width = self.profile.max_total_variables
        parts[_COEFFICIENTS, base : base + width] = line.values
        parts[_KIND, base] = line.kind
        parts[_RHS, base] = line.rhs
        parts[_RULE, base] = line.rule
        parts[_LEFT, base] = line.left
        parts[_RIGHT, base] = line.right
        parts[_AUX, base] = line.aux

    def _read_line(self, parts: np.ndarray, index: int) -> _Line:
        base = self._base(index)
        width = self.profile.max_total_variables
        return _Line(
            kind=int(parts[_KIND, base]),
            values=tuple(int(value) for value in parts[_COEFFICIENTS, base : base + width]),
            rhs=int(parts[_RHS, base]),
            rule=int(parts[_RULE, base]),
            left=int(parts[_LEFT, base]),
            right=int(parts[_RIGHT, base]),
            aux=int(parts[_AUX, base]),
        )

    @staticmethod
    def _line_magnitude(line: _Line) -> int:
        return _magnitude((*line.values, line.rhs))

    def initial(
        self,
        clauses: Sequence[Sequence[int]],
        *,
        variable_count: int,
    ) -> HybridInferenceState:
        variables = _exact_integer(variable_count, "variable_count", minimum=1)
        if variables > self.profile.max_variables:
            raise HybridInferenceError("variable count exceeds profile")
        if len(clauses) > self.profile.max_original_clauses:
            raise HybridInferenceError("clause count exceeds profile")
        canonical = tuple(
            sorted(
                {_canonical_clause(clause, variables) for clause in clauses},
                key=lambda clause: (len(clause), clause),
            )
        )
        if len(canonical) > self.profile.max_original_clauses:
            raise HybridInferenceError("canonical clause count exceeds profile")
        parts = np.zeros((9, self.profile.mode_count), dtype=np.float64)
        header = parts[_HEADER]
        header[_H_MAGIC] = _MAGIC
        header[_H_ORIGINAL_VARIABLES] = variables
        header[_H_ACTIVE_VARIABLES] = variables
        header[_H_ORIGINAL_CLAUSES] = len(canonical)
        header[_H_LINES] = len(canonical)
        header[_H_STATUS] = _RUNNING
        header[_H_INPUT_LINES] = len(canonical)
        width = self.profile.max_total_variables
        for index, clause in enumerate(canonical):
            values = [0] * width
            for literal in clause:
                values[abs(literal) - 1] = 1 if literal > 0 else -1
            self._write_line(parts, index, _Line(_CLAUSE, tuple(values), 0, _INPUT))
        header[_H_MAX_COEFFICIENT] = 1 if any(canonical) else 0
        state = self._state(parts)
        self.validate(state)
        return state

    @staticmethod
    def _clause(line: _Line) -> tuple[int, ...]:
        return tuple(
            index + 1 if value > 0 else -(index + 1)
            for index, value in enumerate(line.values)
            if value
        )

    @staticmethod
    def _clause_pb(line: _Line) -> tuple[tuple[int, ...], int]:
        negative = sum(value < 0 for value in line.values)
        coefficients = tuple(-1 if value > 0 else 1 if value < 0 else 0 for value in line.values)
        return coefficients, negative - 1

    @staticmethod
    def _resolve(left: _Line, right: _Line, pivot: int) -> tuple[int, ...] | None:
        a = left.values[pivot - 1]
        b = right.values[pivot - 1]
        if a == 0 or b != -a:
            return None
        values = []
        for index, (lv, rv) in enumerate(zip(left.values, right.values)):
            if index == pivot - 1:
                values.append(0)
            elif lv and rv and lv != rv:
                return None
            else:
                values.append(lv or rv)
        return tuple(values)

    def _source_clauses(self, parts: np.ndarray) -> tuple[tuple[int, ...], ...]:
        count = int(parts[_HEADER, _H_ORIGINAL_CLAUSES])
        return tuple(self._clause(self._read_line(parts, index)) for index in range(count))

    def _append(self, plan: _Plan, line: _Line) -> int | None:
        if len(plan.lines) >= self.profile.max_lines:
            plan.capacity_exhausted = True
            return None
        if self._line_magnitude(line) > _SAFE_INTEGER:
            plan.capacity_exhausted = True
            return None
        plan.lines.append(line)
        line_id = len(plan.lines)
        if (
            (line.kind == _CLAUSE and not any(line.values))
            or (line.kind == _PB and not any(line.values) and line.rhs < 0)
            or (line.kind == _XOR and not any(line.values) and line.rhs == 1)
        ):
            plan.root_line = line_id
        return line_id

    def _discover_extensions(self, plan: _Plan, original_count: int, original_variables: int) -> list[tuple[int, int, int, int]]:
        pair_rows: dict[tuple[int, int], list[tuple[int, tuple[int, ...]]]] = defaultdict(list)
        for line_id in range(1, original_count + 1):
            clause = self._clause(plan.lines[line_id - 1])
            if len(clause) < 3:
                continue
            for pair in itertools.combinations(clause, 2):
                if pair[0] == -pair[1]:
                    continue
                residue = tuple(literal for literal in clause if literal not in pair)
                pair_key = (pair[0], pair[1])
                pair_rows[pair_key].append((line_id, residue))
        candidates: list[tuple[int, tuple[int, int], list[tuple[int, tuple[int, ...]]]]] = []
        for pair, rows in pair_rows.items():
            residues = {residue for _, residue in rows}
            complementary = any(
                len(residue) == 1 and (-residue[0],) in residues for residue in residues
            )
            if complementary:
                candidates.append((len(rows), pair, rows))
        candidates.sort(key=lambda item: (-item[0], tuple(_literal_key(value) for value in item[1])))
        extensions: list[tuple[int, int, int, int]] = []
        width = self.profile.max_total_variables
        for offset, (_, pair, _) in enumerate(candidates[: self.profile.max_extensions], 1):
            new_variable = original_variables + offset
            values = [0] * width
            for literal in pair:
                values[abs(literal) - 1] = 1 if literal > 0 else -1
            definition_id = self._append(
                plan,
                _Line(_EXTENSION, tuple(values), 0, _EXTENSION_DEFINE, aux=new_variable),
            )
            if definition_id is None:
                break
            first, second = pair
            axioms = (
                (-new_variable, first, second),
                (new_variable, -first),
                (new_variable, -second),
            )
            axiom_ids: list[int] = []
            for axiom_index, clause in enumerate(axioms, 1):
                row = [0] * width
                for literal in clause:
                    row[abs(literal) - 1] = 1 if literal > 0 else -1
                line_id = self._append(
                    plan,
                    _Line(
                        _CLAUSE,
                        tuple(row),
                        0,
                        _EXTENSION_CLAUSE,
                        left=definition_id,
                        aux=axiom_index,
                    ),
                )
                if line_id is None:
                    return extensions
                axiom_ids.append(line_id)
            extensions.append((definition_id, new_variable, axiom_ids[1], axiom_ids[2]))
        return extensions

    def _parity_imports(self, plan: _Plan, original_count: int) -> list[int]:
        groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
        for line_id in range(1, original_count + 1):
            line = plan.lines[line_id - 1]
            support = tuple(index + 1 for index, value in enumerate(line.values) if value)
            if 1 <= len(support) <= self.profile.max_parity_width:
                groups[support].append(line_id)
        imported: list[int] = []
        for support in sorted(groups):
            line_ids = groups[support]
            masks: dict[int, int] = {}
            for line_id in line_ids:
                line = plan.lines[line_id - 1]
                mask = sum(
                    1 << index
                    for index, variable in enumerate(support)
                    if line.values[variable - 1] < 0
                )
                masks.setdefault(mask, line_id)
            values = tuple(
                1 if index + 1 in support else 0
                for index in range(self.profile.max_total_variables)
            )
            for forbidden_parity in (0, 1):
                required = {
                    mask
                    for mask in range(1 << len(support))
                    if mask.bit_count() & 1 == forbidden_parity
                }
                if not required.issubset(masks):
                    continue
                line_id = self._append(
                    plan,
                    _Line(
                        _XOR,
                        values,
                        1 - forbidden_parity,
                        _PARITY_IMPORT,
                        left=masks[min(required)],
                    ),
                )
                if line_id is None:
                    return imported
                imported.append(line_id)
        return imported

    def _xor_reduce(self, plan: _Plan, candidates: Sequence[int], basis: dict[int, int]) -> None:
        for candidate_id in candidates:
            current_id = candidate_id
            while True:
                current = plan.lines[current_id - 1]
                support = [index + 1 for index, value in enumerate(current.values) if value]
                if not support:
                    if current.rhs == 1:
                        plan.root_line = current_id
                    break
                pivot = support[0]
                prior_id = basis.get(pivot)
                if prior_id is None:
                    basis[pivot] = current_id
                    break
                prior = plan.lines[prior_id - 1]
                values = tuple(a ^ b for a, b in zip(current.values, prior.values))
                next_id = self._append(
                    plan,
                    _Line(
                        _XOR,
                        values,
                        current.rhs ^ prior.rhs,
                        _XOR_ADD,
                        left=current_id,
                        right=prior_id,
                        aux=pivot,
                    ),
                )
                if next_id is None:
                    return
                current_id = next_id
            if plan.root_line is not None:
                return

    def _derive_at_most_one(self, plan: _Plan, pb_ids: Sequence[int]) -> list[int]:
        edge_rows: dict[tuple[int, int], int] = {}
        for line_id in pb_ids:
            line = plan.lines[line_id - 1]
            support = tuple(index + 1 for index, value in enumerate(line.values) if value)
            if (
                len(support) == 2
                and line.rhs == 1
                and all(line.values[variable - 1] == 1 for variable in support)
            ):
                edge_rows.setdefault((support[0], support[1]), line_id)
        adjacency: dict[int, set[int]] = defaultdict(set)
        for left, right in edge_rows:
            adjacency[left].add(right)
            adjacency[right].add(left)
        candidates: set[tuple[int, ...]] = set()
        all_variables = sorted(adjacency)
        for edge in sorted(edge_rows):
            clique = list(edge)
            for variable in all_variables:
                if variable not in clique and all(variable in adjacency[item] for item in clique):
                    clique.append(variable)
            candidates.add(tuple(sorted(clique)))
        maximal = [
            candidate
            for candidate in sorted(candidates, key=lambda row: (-len(row), row))
            if not any(set(candidate) < set(other) for other in candidates)
        ]
        bounds: list[int] = []
        for clique in maximal:
            current_variables = list(clique[:2])
            current_id = edge_rows[(current_variables[0], current_variables[1])]
            for variable in clique[2:]:
                pair_ids = [
                    edge_rows[(min(item, variable), max(item, variable))]
                    for item in current_variables
                ]
                pair_sum_id = pair_ids[0]
                for pair_id in pair_ids[1:]:
                    left = plan.lines[pair_sum_id - 1]
                    right = plan.lines[pair_id - 1]
                    pair_sum_id = self._append(
                        plan,
                        _Line(
                            _PB,
                            tuple(a + b for a, b in zip(left.values, right.values)),
                            left.rhs + right.rhs,
                            _PB_ADD,
                            left=pair_sum_id,
                            right=pair_id,
                        ),
                    ) or 0
                    if pair_sum_id == 0:
                        return bounds
                factor = len(current_variables) - 1
                scaled_id = current_id
                if factor != 1:
                    current = plan.lines[current_id - 1]
                    scaled_id = self._append(
                        plan,
                        _Line(
                            _PB,
                            tuple(factor * value for value in current.values),
                            factor * current.rhs,
                            _PB_SCALE,
                            left=current_id,
                            aux=factor,
                        ),
                    ) or 0
                    if scaled_id == 0:
                        return bounds
                scaled = plan.lines[scaled_id - 1]
                pairs = plan.lines[pair_sum_id - 1]
                total_id = self._append(
                    plan,
                    _Line(
                        _PB,
                        tuple(a + b for a, b in zip(scaled.values, pairs.values)),
                        scaled.rhs + pairs.rhs,
                        _PB_ADD,
                        left=scaled_id,
                        right=pair_sum_id,
                    ),
                ) or 0
                if total_id == 0:
                    return bounds
                total = plan.lines[total_id - 1]
                divisor = len(current_variables)
                if any(value % divisor for value in total.values):
                    raise HybridInferenceError("internal non-divisible counting inference")
                current_id = self._append(
                    plan,
                    _Line(
                        _PB,
                        tuple(value // divisor for value in total.values),
                        _floor_div(total.rhs, divisor),
                        _PB_DIVIDE,
                        left=total_id,
                        aux=divisor,
                    ),
                ) or 0
                if current_id == 0:
                    return bounds
                current_variables.append(variable)
            bounds.append(current_id)
        return bounds

    def _aggregate_disjoint(self, plan: _Plan, rows: Sequence[int]) -> int | None:
        selected: list[int] = []
        used: set[int] = set()
        for line_id in sorted(rows, key=lambda item: tuple(index for index, value in enumerate(plan.lines[item - 1].values) if value)):
            support = {index for index, value in enumerate(plan.lines[line_id - 1].values) if value}
            if support and support.isdisjoint(used):
                selected.append(line_id)
                used.update(support)
        if not selected:
            return None
        current_id = selected[0]
        for line_id in selected[1:]:
            left = plan.lines[current_id - 1]
            right = plan.lines[line_id - 1]
            current_id = self._append(
                plan,
                _Line(
                    _PB,
                    tuple(a + b for a, b in zip(left.values, right.values)),
                    left.rhs + right.rhs,
                    _PB_ADD,
                    left=current_id,
                    right=line_id,
                ),
            ) or 0
            if current_id == 0:
                return None
        return current_id

    def _cardinality_bridges(
        self,
        plan: _Plan,
        pb_ids: Sequence[int],
        basis: dict[int, int],
    ) -> None:
        representatives: dict[tuple[tuple[int, ...], int], int] = {}
        for line_id in pb_ids:
            line = plan.lines[line_id - 1]
            if line.kind == _PB:
                representatives.setdefault((line.values, line.rhs), line_id)
        bridge_ids: list[int] = []
        for (values, rhs), upper_id in list(representatives.items()):
            if not values or any(value not in (0, 1) for value in values):
                continue
            negative = tuple(-value for value in values)
            lower_id = representatives.get((negative, -rhs))
            if lower_id is None:
                continue
            bridge_id = self._append(
                plan,
                _Line(
                    _XOR,
                    values,
                    rhs & 1,
                    _CARDINALITY_PARITY,
                    left=upper_id,
                    right=lower_id,
                ),
            )
            if bridge_id is None:
                return
            bridge_ids.append(bridge_id)
        self._xor_reduce(plan, bridge_ids, basis)

    def _extension_resolution(self, plan: _Plan, extensions: Sequence[tuple[int, int, int, int]], original_count: int) -> None:
        if not extensions:
            return
        known: dict[tuple[int, ...], int] = {}
        clause_ids = [index + 1 for index, line in enumerate(plan.lines) if line.kind == _CLAUSE]
        for line_id in clause_ids:
            known.setdefault(plan.lines[line_id - 1].values, line_id)
        resolution_count = 0

        def derive(left_id: int, right_id: int, pivot: int) -> int | None:
            nonlocal resolution_count
            if resolution_count >= self.profile.max_resolution_inferences:
                return None
            values = self._resolve(plan.lines[left_id - 1], plan.lines[right_id - 1], pivot)
            if values is None:
                return None
            existing = known.get(values)
            if existing is not None:
                return existing
            line_id = self._append(
                plan,
                _Line(_CLAUSE, values, 0, _RESOLVE, left=left_id, right=right_id, aux=pivot),
            )
            if line_id is not None:
                known[values] = line_id
                resolution_count += 1
            return line_id

        # First use each extension as an actual abbreviation wherever its two
        # literals occur together.  These are ordinary resolution steps.
        for definition_id, _, first_axiom_id, second_axiom_id in extensions:
            definition = plan.lines[definition_id - 1]
            operands = [
                index + 1 if value > 0 else -(index + 1)
                for index, value in enumerate(definition.values)
                if value
            ]
            if len(operands) != 2:
                continue
            first, second = operands
            compressed: list[int] = []
            for source_id in range(1, original_count + 1):
                source = plan.lines[source_id - 1]
                if source.values[abs(first) - 1] != (1 if first > 0 else -1):
                    continue
                if source.values[abs(second) - 1] != (1 if second > 0 else -1):
                    continue
                intermediate_id = derive(source_id, first_axiom_id, abs(first))
                if intermediate_id is None:
                    continue
                compressed_id = derive(intermediate_id, second_axiom_id, abs(second))
                if compressed_id is not None:
                    compressed.append(compressed_id)
            for left_id, right_id in itertools.combinations(compressed, 2):
                left = plan.lines[left_id - 1]
                right = plan.lines[right_id - 1]
                for pivot in range(1, self.profile.max_total_variables + 1):
                    if left.values[pivot - 1] == -right.values[pivot - 1] != 0:
                        result_id = derive(left_id, right_id, pivot)
                        if result_id is not None and plan.root_line is not None:
                            return

        # Bounded, deterministic resolution saturation.  Pairs touching an
        # extension variable are prioritized, then all remaining pairs.
        while resolution_count < self.profile.max_resolution_inferences and plan.root_line is None:
            ids = sorted(known.values())
            candidates: list[tuple[int, int, int, int]] = []
            for position, left_id in enumerate(ids):
                left = plan.lines[left_id - 1]
                for right_id in ids[position + 1 :]:
                    right = plan.lines[right_id - 1]
                    for pivot in range(1, self.profile.max_total_variables + 1):
                        if left.values[pivot - 1] == -right.values[pivot - 1] != 0:
                            priority = 0 if pivot > int(self.profile.max_variables) else 1
                            candidates.append((priority, left_id, right_id, pivot))
            added = False
            for _, left_id, right_id, pivot in sorted(candidates):
                before = len(known)
                result_id = derive(left_id, right_id, pivot)
                if result_id is not None and len(known) > before:
                    added = True
                    if plan.root_line is not None:
                        return
                    break
            if not added:
                return

    def _build_plan(self, clauses: Sequence[Sequence[int]], original_variables: int) -> _Plan:
        width = self.profile.max_total_variables
        plan = _Plan([])
        for clause in clauses:
            values = [0] * width
            for literal in clause:
                values[abs(literal) - 1] = 1 if literal > 0 else -1
            self._append(plan, _Line(_CLAUSE, tuple(values), 0, _INPUT))
        original_count = len(plan.lines)
        if any(not any(line.values) for line in plan.lines):
            plan.root_line = next(index + 1 for index, line in enumerate(plan.lines) if not any(line.values))
            return plan

        extensions = self._discover_extensions(plan, original_count, original_variables)

        pb_ids: list[int] = []
        for source_id in range(1, original_count + 1):
            values, rhs = self._clause_pb(plan.lines[source_id - 1])
            line_id = self._append(
                plan,
                _Line(_PB, values, rhs, _CLAUSE_PB, left=source_id),
            )
            if line_id is None:
                return plan
            pb_ids.append(line_id)

        imported = self._parity_imports(plan, original_count)
        basis: dict[int, int] = {}
        self._xor_reduce(plan, imported, basis)
        if plan.root_line is not None:
            return plan

        bounds = self._derive_at_most_one(plan, pb_ids)
        all_pb_ids = [index + 1 for index, line in enumerate(plan.lines) if line.kind == _PB]
        lower_rows = [
            line_id
            for line_id in pb_ids
            if plan.lines[line_id - 1].rhs == -1
            and any(plan.lines[line_id - 1].values)
            and all(value in (0, -1) for value in plan.lines[line_id - 1].values)
        ]
        lower_total = self._aggregate_disjoint(plan, lower_rows)
        upper_total = self._aggregate_disjoint(plan, bounds)
        if lower_total is not None and upper_total is not None:
            lower = plan.lines[lower_total - 1]
            upper = plan.lines[upper_total - 1]
            if all(a == -b for a, b in zip(lower.values, upper.values)):
                contradiction_id = self._append(
                    plan,
                    _Line(
                        _PB,
                        tuple(a + b for a, b in zip(lower.values, upper.values)),
                        lower.rhs + upper.rhs,
                        _PB_ADD,
                        left=lower_total,
                        right=upper_total,
                    ),
                )
                if contradiction_id is not None and plan.lines[contradiction_id - 1].rhs < 0:
                    plan.root_line = contradiction_id
                    return plan

        all_pb_ids = [index + 1 for index, line in enumerate(plan.lines) if line.kind == _PB]
        self._cardinality_bridges(plan, all_pb_ids, basis)
        if plan.root_line is not None:
            return plan

        self._extension_resolution(plan, extensions, original_count)
        return plan

    def _validate_line(self, line_id: int, line: _Line, prior: Sequence[_Line], original_count: int, original_variables: int) -> None:
        if line.kind not in _KIND_NAMES or line.rule not in _RULE_NAMES:
            raise HybridInferenceError(f"line {line_id}: unknown kind or rule")
        if any(value and index >= original_variables + self.profile.max_extensions for index, value in enumerate(line.values)):
            raise HybridInferenceError(f"line {line_id}: coefficient outside variable capacity")
        for premise in (line.left, line.right):
            if premise < 0 or premise >= line_id:
                raise HybridInferenceError(f"line {line_id}: invalid premise")
        if line.rule == _INPUT:
            if line_id > original_count or line.kind != _CLAUSE or line.rhs or line.left or line.right or line.aux:
                raise HybridInferenceError(f"line {line_id}: invalid input clause")
            if any(value not in (-1, 0, 1) for value in line.values):
                raise HybridInferenceError(f"line {line_id}: invalid clause literal")
            return
        if line_id <= original_count:
            raise HybridInferenceError(f"line {line_id}: source line has derived rule")
        if line.rule == _CLAUSE_PB:
            source = prior[line.left - 1]
            values, rhs = self._clause_pb(source)
            expected = _Line(_PB, values, rhs, _CLAUSE_PB, left=line.left)
        elif line.rule == _PB_ADD:
            left, right = prior[line.left - 1], prior[line.right - 1]
            expected = _Line(_PB, tuple(a + b for a, b in zip(left.values, right.values)), left.rhs + right.rhs, _PB_ADD, line.left, line.right)
        elif line.rule == _PB_SCALE:
            source = prior[line.left - 1]
            if line.aux < 0:
                raise HybridInferenceError(f"line {line_id}: negative multiplier")
            expected = _Line(_PB, tuple(line.aux * value for value in source.values), line.aux * source.rhs, _PB_SCALE, line.left, 0, line.aux)
        elif line.rule == _PB_DIVIDE:
            source = prior[line.left - 1]
            if line.aux <= 0 or any(value % line.aux for value in source.values):
                raise HybridInferenceError(f"line {line_id}: invalid division")
            expected = _Line(_PB, tuple(value // line.aux for value in source.values), _floor_div(source.rhs, line.aux), _PB_DIVIDE, line.left, 0, line.aux)
        elif line.rule == _XOR_ADD:
            left, right = prior[line.left - 1], prior[line.right - 1]
            if left.kind != _XOR or right.kind != _XOR:
                raise HybridInferenceError(f"line {line_id}: XOR premise kind mismatch")
            expected = _Line(_XOR, tuple(a ^ b for a, b in zip(left.values, right.values)), left.rhs ^ right.rhs, _XOR_ADD, line.left, line.right, line.aux)
        elif line.rule == _CARDINALITY_PARITY:
            upper, lower = prior[line.left - 1], prior[line.right - 1]
            if upper.kind != _PB or lower.kind != _PB or upper.values != tuple(-value for value in lower.values) or upper.rhs != -lower.rhs or any(value not in (0, 1) for value in upper.values):
                raise HybridInferenceError(f"line {line_id}: invalid cardinality bridge")
            expected = _Line(_XOR, upper.values, upper.rhs & 1, _CARDINALITY_PARITY, line.left, line.right)
        elif line.rule == _PARITY_IMPORT:
            if line.kind != _XOR or line.rhs not in (0, 1) or any(value not in (0, 1) for value in line.values):
                raise HybridInferenceError(f"line {line_id}: invalid parity import")
            support = tuple(index + 1 for index, value in enumerate(line.values) if value)
            source_rows = [
                row
                for row in prior[:original_count]
                if tuple(
                    index + 1 for index, value in enumerate(row.values) if value
                )
                == support
            ]
            required_masks = {
                mask
                for mask in range(1 << len(support))
                if mask.bit_count() & 1 == 1 - line.rhs
            }
            source_masks = {
                sum(
                    1 << index
                    for index, variable in enumerate(support)
                    if row.values[variable - 1] < 0
                )
                for row in source_rows
            }
            if not support or not required_masks.issubset(source_masks):
                raise HybridInferenceError(
                    f"line {line_id}: parity import is not entailed by source block"
                )
            expected = line
        elif line.rule == _EXTENSION_DEFINE:
            operands = [value for value in line.values if value]
            prior_extensions = sum(row.kind == _EXTENSION for row in prior)
            if line.kind != _EXTENSION or len(operands) != 2 or any(value not in (-1, 1) for value in operands) or line.aux != original_variables + prior_extensions + 1:
                raise HybridInferenceError(f"line {line_id}: invalid extension definition")
            expected = line
        elif line.rule == _EXTENSION_CLAUSE:
            definition = prior[line.left - 1]
            operands = [index + 1 if value > 0 else -(index + 1) for index, value in enumerate(definition.values) if value]
            if definition.kind != _EXTENSION or len(operands) != 2 or line.aux not in (1, 2, 3):
                raise HybridInferenceError(f"line {line_id}: invalid extension clause")
            first, second = operands
            clauses = ((-definition.aux, first, second), (definition.aux, -first), (definition.aux, -second))
            values = [0] * self.profile.max_total_variables
            for literal in clauses[line.aux - 1]:
                values[abs(literal) - 1] = 1 if literal > 0 else -1
            expected = _Line(_CLAUSE, tuple(values), 0, _EXTENSION_CLAUSE, line.left, 0, line.aux)
        elif line.rule == _RESOLVE:
            left, right = prior[line.left - 1], prior[line.right - 1]
            values = self._resolve(left, right, line.aux)
            if values is None:
                raise HybridInferenceError(f"line {line_id}: invalid resolution")
            expected = _Line(_CLAUSE, values, 0, _RESOLVE, line.left, line.right, line.aux)
        else:
            raise HybridInferenceError(f"line {line_id}: unsupported inference rule")
        if line != expected:
            raise HybridInferenceError(f"line {line_id}: false {_RULE_NAMES[line.rule]} inference")

    def validate(self, state: HybridInferenceState) -> None:
        parts = self._parts(state)
        header = parts[_HEADER]
        if int(header[_H_MAGIC]) != _MAGIC:
            raise HybridInferenceError("hybrid field magic mismatch")
        original_variables = int(header[_H_ORIGINAL_VARIABLES])
        active_variables = int(header[_H_ACTIVE_VARIABLES])
        original_count = int(header[_H_ORIGINAL_CLAUSES])
        line_count = int(header[_H_LINES])
        status = int(header[_H_STATUS])
        transitions = int(header[_H_TRANSITIONS])
        if not 1 <= original_variables <= self.profile.max_variables:
            raise HybridInferenceError("invalid original variable count")
        if not original_variables <= active_variables <= self.profile.max_total_variables:
            raise HybridInferenceError("invalid active variable count")
        if not 0 <= original_count <= min(line_count, self.profile.max_original_clauses):
            raise HybridInferenceError("invalid original clause count")
        if not original_count <= line_count <= self.profile.max_lines:
            raise HybridInferenceError("invalid proof line count")
        if status not in _STATUS_NAMES or not 0 <= transitions <= self.profile.max_transitions:
            raise HybridInferenceError("invalid status or transition count")
        lines: list[_Line] = []
        for index in range(line_count):
            line = self._read_line(parts, index)
            self._validate_line(index + 1, line, lines, original_count, original_variables)
            lines.append(line)
        extension_count = sum(line.kind == _EXTENSION for line in lines)
        if active_variables != original_variables + extension_count:
            raise HybridInferenceError("active variable count does not match extensions")
        expected_counts = {
            _H_INPUT_LINES: sum(line.rule == _INPUT for line in lines),
            _H_PB_LINES: sum(line.kind == _PB for line in lines),
            _H_XOR_LINES: sum(line.kind == _XOR for line in lines),
            _H_EXTENSION_LINES: extension_count,
            _H_RESOLUTION_LINES: sum(line.rule == _RESOLVE for line in lines),
        }
        for coordinate, expected in expected_counts.items():
            if int(header[coordinate]) != expected:
                raise HybridInferenceError("hybrid field counter mismatch")
        maximum = max((self._line_magnitude(line) for line in lines), default=0)
        if int(header[_H_MAX_COEFFICIENT]) != maximum:
            raise HybridInferenceError("maximum coefficient counter mismatch")
        roots = [
            index + 1
            for index, line in enumerate(lines)
            if (line.kind == _CLAUSE and not any(line.values))
            or (line.kind == _PB and not any(line.values) and line.rhs < 0)
            or (line.kind == _XOR and not any(line.values) and line.rhs == 1)
        ]
        if status == _UNSAT and not roots:
            raise HybridInferenceError("UNSAT state has no contradiction")
        if status != _UNSAT and roots:
            raise HybridInferenceError("contradiction stored without UNSAT status")

    def _refresh_header(self, parts: np.ndarray, lines: Sequence[_Line], status: int, transitions: int) -> None:
        header = parts[_HEADER]
        original_variables = int(header[_H_ORIGINAL_VARIABLES])
        header[_H_ACTIVE_VARIABLES] = original_variables + sum(line.kind == _EXTENSION for line in lines)
        header[_H_LINES] = len(lines)
        header[_H_STATUS] = status
        header[_H_TRANSITIONS] = transitions
        header[_H_INPUT_LINES] = sum(line.rule == _INPUT for line in lines)
        header[_H_PB_LINES] = sum(line.kind == _PB for line in lines)
        header[_H_XOR_LINES] = sum(line.kind == _XOR for line in lines)
        header[_H_EXTENSION_LINES] = sum(line.kind == _EXTENSION for line in lines)
        header[_H_RESOLUTION_LINES] = sum(line.rule == _RESOLVE for line in lines)
        header[_H_MAX_COEFFICIENT] = max((self._line_magnitude(line) for line in lines), default=0)

    def state_sha256(self, state: HybridInferenceState) -> str:
        self.validate(state)
        return hashlib.sha256(state._field.tobytes(order="C")).hexdigest()

    def status(self, state: HybridInferenceState) -> str:
        return _STATUS_NAMES[int(self._parts(state)[_HEADER, _H_STATUS])]

    def step(self, state: HybridInferenceState) -> tuple[HybridInferenceState, Mapping[str, Any]]:
        self.validate(state)
        if self.status(state) != "running":
            digest = self.state_sha256(state)
            return state, {
                "schema": "cassifi.hybrid-inference-step.v1",
                "action": "terminal",
                "status": self.status(state),
                "previous_state_sha256": digest,
                "state_sha256": digest,
                "state_unchanged": True,
            }
        before = self.state_sha256(state)
        parts = self._parts(state, mutable=True)
        header = parts[_HEADER]
        line_count = int(header[_H_LINES])
        transitions = int(header[_H_TRANSITIONS])
        clauses = self._source_clauses(parts)
        plan = self._build_plan(clauses, int(header[_H_ORIGINAL_VARIABLES]))
        current_lines = [self._read_line(parts, index) for index in range(line_count)]
        if current_lines != plan.lines[:line_count]:
            raise HybridInferenceError("field proof is not the deterministic plan prefix")
        if transitions >= self.profile.max_transitions or line_count >= len(plan.lines):
            self._refresh_header(parts, current_lines, _EXHAUSTED, transitions + 1)
            successor = self._state(parts)
            self.validate(successor)
            return successor, {
                "schema": "cassifi.hybrid-inference-step.v1",
                "action": "exhaust",
                "status": "exhausted",
                "line_id": None,
                "rule": None,
                "previous_state_sha256": before,
                "state_sha256": self.state_sha256(successor),
                "state_unchanged": False,
            }
        line = plan.lines[line_count]
        self._write_line(parts, line_count, line)
        current_lines.append(line)
        root_now = plan.root_line == line_count + 1
        status = _UNSAT if root_now else _RUNNING
        self._refresh_header(parts, current_lines, status, transitions + 1)
        successor = self._state(parts)
        self.validate(successor)
        return successor, {
            "schema": "cassifi.hybrid-inference-step.v1",
            "action": "unsat" if root_now else _RULE_NAMES[line.rule],
            "status": _STATUS_NAMES[status],
            "line_id": line_count + 1,
            "rule": _RULE_NAMES[line.rule],
            "previous_state_sha256": before,
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }

    def solve(self, state: HybridInferenceState) -> tuple[HybridInferenceState, Mapping[str, Any]]:
        self.validate(state)
        initial_sha256 = self.state_sha256(state)
        if self.status(state) != "running":
            return state, {
                "schema": "cassifi.hybrid-inference-solve.v1",
                "initial_state_sha256": initial_sha256,
                "state_sha256": initial_sha256,
                **self.inspect(state),
            }
        parts = self._parts(state, mutable=True)
        header = parts[_HEADER]
        line_count = int(header[_H_LINES])
        transitions = int(header[_H_TRANSITIONS])
        clauses = self._source_clauses(parts)
        plan = self._build_plan(
            clauses,
            int(header[_H_ORIGINAL_VARIABLES]),
        )
        current_lines = [
            self._read_line(parts, index) for index in range(line_count)
        ]
        if current_lines != plan.lines[:line_count]:
            raise HybridInferenceError(
                "field proof is not the deterministic plan prefix"
            )
        target = plan.root_line or len(plan.lines)
        available = max(0, self.profile.max_transitions - transitions)
        append_count = min(max(0, target - line_count), available)
        for index in range(append_count):
            line = plan.lines[line_count + index]
            self._write_line(parts, line_count + index, line)
            current_lines.append(line)
        transitions += append_count
        reached_root = (
            plan.root_line is not None
            and len(current_lines) >= plan.root_line
        )
        if reached_root:
            status = _UNSAT
        else:
            status = _EXHAUSTED
            if transitions < self.profile.max_transitions:
                transitions += 1
        self._refresh_header(parts, current_lines, status, transitions)
        current = self._state(parts)
        self.validate(current)
        return current, {
            "schema": "cassifi.hybrid-inference-solve.v1",
            "initial_state_sha256": initial_sha256,
            "state_sha256": self.state_sha256(current),
            **self.inspect(current),
        }

    def _line_dict(self, line_id: int, line: _Line) -> dict[str, Any]:
        row: dict[str, Any] = {
            "line_id": line_id,
            "kind": _KIND_NAMES[line.kind],
            "rule": _RULE_NAMES[line.rule],
        }
        if line.kind == _CLAUSE:
            row["literals"] = list(self._clause(line))
        elif line.kind == _PB:
            row["terms"] = [[index + 1, value] for index, value in enumerate(line.values) if value]
            row["rhs"] = line.rhs
        elif line.kind == _XOR:
            row["variables"] = [index + 1 for index, value in enumerate(line.values) if value]
            row["rhs"] = line.rhs
        else:
            row["operands"] = [index + 1 if value > 0 else -(index + 1) for index, value in enumerate(line.values) if value]
            row["new_variable"] = line.aux
        if line.left:
            row["left"] = line.left
        if line.right:
            row["right"] = line.right
        if line.aux and line.kind != _EXTENSION:
            row["aux"] = line.aux
        return row

    def proof(self, state: HybridInferenceState) -> dict[str, Any]:
        self.validate(state)
        parts = self._parts(state)
        count = int(parts[_HEADER, _H_LINES])
        lines = [self._read_line(parts, index) for index in range(count)]
        roots = [
            index + 1
            for index, line in enumerate(lines)
            if (line.kind == _CLAUSE and not any(line.values))
            or (line.kind == _PB and not any(line.values) and line.rhs < 0)
            or (line.kind == _XOR and not any(line.values) and line.rhs == 1)
        ]
        payload = {
            "schema": PROOF_SCHEMA,
            "proof_system": "CNF resolution plus cutting planes, GF(2) elimination, cardinality-parity bridges, and acyclic extension definitions",
            "original_variables": int(parts[_HEADER, _H_ORIGINAL_VARIABLES]),
            "original_clauses": int(parts[_HEADER, _H_ORIGINAL_CLAUSES]),
            "status": self.status(state),
            "root_line": roots[0] if roots else None,
            "lines": [self._line_dict(index + 1, line) for index, line in enumerate(lines)],
        }
        payload["proof_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
        return payload

    def inspect(self, state: HybridInferenceState) -> dict[str, Any]:
        self.validate(state)
        parts = self._parts(state)
        header = parts[_HEADER]
        return {
            "status": _STATUS_NAMES[int(header[_H_STATUS])],
            "original_variables": int(header[_H_ORIGINAL_VARIABLES]),
            "active_variables": int(header[_H_ACTIVE_VARIABLES]),
            "original_clauses": int(header[_H_ORIGINAL_CLAUSES]),
            "proof_lines": int(header[_H_LINES]),
            "field_bytes": state.nbytes,
            "profile_sha256": self.profile.fingerprint,
            "resource_ledger": {
                "transitions": int(header[_H_TRANSITIONS]),
                "input_lines": int(header[_H_INPUT_LINES]),
                "pb_lines": int(header[_H_PB_LINES]),
                "xor_lines": int(header[_H_XOR_LINES]),
                "extension_definitions": int(header[_H_EXTENSION_LINES]),
                "resolution_lines": int(header[_H_RESOLUTION_LINES]),
                "maximum_integer_magnitude": int(header[_H_MAX_COEFFICIENT]),
            },
        }

    def descriptor(self, state: HybridInferenceState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": SCHEMA,
            "layout": _LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": self.profile.fingerprint,
            "field_b64": base64.b64encode(state._field.tobytes(order="C")).decode("ascii"),
            "state_sha256": self.state_sha256(state),
        }

    @classmethod
    def from_descriptor(cls, value: Mapping[str, Any]) -> tuple["HybridInferenceField", HybridInferenceState]:
        required = {"schema", "layout", "profile", "profile_sha256", "field_b64", "state_sha256"}
        if not isinstance(value, Mapping) or set(value) != required:
            raise HybridInferenceError("invalid hybrid-field descriptor keys")
        if value["schema"] != SCHEMA or value["layout"] != _LAYOUT:
            raise HybridInferenceError("unsupported hybrid-field descriptor")
        if not isinstance(value["profile"], Mapping):
            raise HybridInferenceError("descriptor profile is invalid")
        try:

            profile = HybridInferenceProfile(**dict(value["profile"]))
        except (TypeError, HybridInferenceError) as exc:
            raise HybridInferenceError("descriptor profile is invalid") from exc
        controller = cls(profile)
        if value["profile_sha256"] != profile.fingerprint:
            raise HybridInferenceError("descriptor profile digest mismatch")
        encoded = value["field_b64"]
        if not isinstance(encoded, str):
            raise HybridInferenceError("descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            field = np.frombuffer(raw, dtype=np.float64).reshape(profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise HybridInferenceError("descriptor field encoding is invalid") from exc
        state = HybridInferenceState(field, profile.fingerprint)
        controller.validate(state)
        if value["state_sha256"] != controller.state_sha256(state):
            raise HybridInferenceError("descriptor state digest mismatch")
        return controller, state



def _regional_profile(
    profile: HybridInferenceProfile | Mapping[str, Any] | None,
    *,
    variable_count: int,
    clause_count: int,
    options: Mapping[str, Any],
) -> HybridInferenceProfile:
    if profile is None:
        values: dict[str, Any] = {
            "max_variables": variable_count,
            "max_original_clauses": max(1, clause_count),
            "max_lines": max(512, 5 * clause_count + 16 * variable_count + 256),
        }
        values.update(dict(options))
    else:
        if options:
            raise HybridInferenceError(
                "profile options cannot accompany an explicit regional profile"
            )
        values = dict(profile) if isinstance(profile, Mapping) else asdict(profile)
    try:
        return HybridInferenceProfile(**values)
    except (TypeError, HybridInferenceError) as exc:
        raise HybridInferenceError("regional hybrid profile is invalid") from exc


def _regional_record(line: _Line) -> dict[str, Any]:
    return {
        "kind": line.kind,
        "values": list(line.values),
        "rhs": line.rhs,
        "rule": line.rule,
        "left": line.left,
        "right": line.right,
        "aux": line.aux,
    }


def _regional_line(
    record: Mapping[str, Any],
    *,
    width: int,
) -> _Line:
    required = {"kind", "values", "rhs", "rule", "left", "right", "aux"}
    if set(record) != required:
        raise HybridInferenceError("regional hybrid line record keys are invalid")
    kind = _exact_integer(record["kind"], "regional hybrid line kind", minimum=1)
    rule = _exact_integer(record["rule"], "regional hybrid line rule", minimum=1)
    values = record["values"]
    if not isinstance(values, list) or len(values) != width:
        raise HybridInferenceError("regional hybrid line width is invalid")
    if any(
        isinstance(value, bool)
        or not isinstance(value, int)
        or abs(value) > _SAFE_INTEGER
        for value in values
    ):
        raise HybridInferenceError("regional hybrid line coefficients are invalid")
    rhs = record["rhs"]
    if (
        isinstance(rhs, bool)
        or not isinstance(rhs, int)
        or abs(rhs) > _SAFE_INTEGER
    ):
        raise HybridInferenceError("regional hybrid line rhs is invalid")
    left = _exact_integer(record["left"], "regional hybrid line left")
    right = _exact_integer(record["right"], "regional hybrid line right")
    aux = _exact_integer(record["aux"], "regional hybrid line aux")
    if kind not in _KIND_NAMES or rule not in _RULE_NAMES:
        raise HybridInferenceError("regional hybrid line kind or rule is unknown")
    return _Line(kind, tuple(values), rhs, rule, left, right, aux)


def _regional_clause_record(
    clause: Sequence[int],
    *,
    width: int,
) -> dict[str, Any]:
    values = [0] * width
    for literal in clause:
        values[abs(literal) - 1] = 1 if literal > 0 else -1
    return _regional_record(_Line(_CLAUSE, tuple(values), 0, _INPUT))


def _regional_line_dict(record: Mapping[str, Any], line_id: int) -> dict[str, Any]:
    line = _regional_line(record, width=len(record["values"]))
    row: dict[str, Any] = {
        "line_id": line_id,
        "kind": _KIND_NAMES[line.kind],
        "rule": _RULE_NAMES[line.rule],
    }
    if line.kind == _CLAUSE:
        row["literals"] = [
            index + 1 if value > 0 else -(index + 1)
            for index, value in enumerate(line.values)
            if value
        ]
    elif line.kind == _PB:
        row["terms"] = [
            [index + 1, value]
            for index, value in enumerate(line.values)
            if value
        ]
        row["rhs"] = line.rhs
    elif line.kind == _XOR:
        row["variables"] = [
            index + 1
            for index, value in enumerate(line.values)
            if value
        ]
        row["rhs"] = line.rhs
    else:
        row["operands"] = [
            index + 1 if value > 0 else -(index + 1)
            for index, value in enumerate(line.values)
            if value
        ]
        row["new_variable"] = line.aux
    if line.left:
        row["left"] = line.left
    if line.right:
        row["right"] = line.right
    if line.aux and line.kind != _EXTENSION:
        row["aux"] = line.aux
    return row


def _regional_proof(
    source: Mapping[str, Any],
    proof_lines: Sequence[Mapping[str, Any]],
    *,
    status: str,
    root_line: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "proof_system": (
            "CNF resolution plus cutting planes, GF(2) elimination, "
            "cardinality-parity bridges, and acyclic extension definitions"
        ),
        "original_variables": int(source["variable_count"]),
        "original_clauses": len(source["clauses"]),
        "status": status,
        "root_line": root_line if status == "unsat" else None,
        "lines": [
            _regional_line_dict(record, index + 1)
            for index, record in enumerate(proof_lines)
        ],
    }
    payload["proof_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _regional_extension_candidates(
    clauses: Sequence[Sequence[int]],
    *,
    original_variables: int,
    max_extensions: int,
)-> list[tuple[int, tuple[int, int]]]:
    pair_rows: dict[tuple[int, int], list[tuple[int, tuple[int, ...]]]] = defaultdict(list)
    for line_id, clause in enumerate(clauses, 1):
        if len(clause) < 3:
            continue
        for pair in itertools.combinations(clause, 2):
            if pair[0] == -pair[1]:
                continue
            residue = tuple(literal for literal in clause if literal not in pair)
            pair_rows[pair].append((line_id, residue))
    candidates: list[tuple[int, tuple[int, int]]] = []
    for pair, rows in pair_rows.items():
        residues = {residue for _, residue in rows}
        if any(
            len(residue) == 1 and (-residue[0],) in residues
            for residue in residues
        ):
            candidates.append((len(rows), pair))
    candidates.sort(
        key=lambda item: (
            -item[0],
            tuple(_literal_key(value) for value in item[1]),
        )
    )
    return [
        (original_variables + offset, pair)
        for offset, (_, pair) in enumerate(candidates[:max_extensions], 1)
    ]



def _regional_pivot_order(
    *,
    original_variables: int,
    total_variables: int,
) -> tuple[int, ...]:
    extension_variables = tuple(
        range(original_variables + 1, total_variables + 1)
    )
    original = tuple(range(1, original_variables + 1))
    return extension_variables + original

def _regional_extension_record(
    new_variable: int,
    pair: Sequence[int],
    *,
    width: int,
    definition_id: int,
    substep: int,
) -> dict[str, Any]:
    if substep == 0:
        values = [0] * width
        for literal in pair:
            values[abs(literal) - 1] = 1 if literal > 0 else -1
        return _regional_record(
            _Line(_EXTENSION, tuple(values), 0, _EXTENSION_DEFINE, aux=new_variable)
        )
    clauses = (
        (-new_variable, pair[0], pair[1]),
        (new_variable, -pair[0]),
        (new_variable, -pair[1]),
    )
    values = [0] * width
    for literal in clauses[substep - 1]:
        values[abs(literal) - 1] = 1 if literal > 0 else -1
    return _regional_record(
        _Line(
            _CLAUSE,
            tuple(values),
            0,
            _EXTENSION_CLAUSE,
            left=definition_id,
            aux=substep,
        )
    )


def _regional_pb_record(
    clause: Sequence[int],
    *,
    width: int,
    source_id: int,
) -> dict[str, Any]:
    values = [0] * width
    negative = 0
    for literal in clause:
        if literal > 0:
            values[literal - 1] = -1
        else:
            values[-literal - 1] = 1
            negative += 1
    return _regional_record(
        _Line(_PB, tuple(values), negative - 1, _CLAUSE_PB, left=source_id)
    )


def _regional_parity_candidates(
    clauses: Sequence[Sequence[int]],
    *,
    width: int,
    max_parity_width: int,
) -> list[dict[str, Any]]:
    groups: dict[tuple[int, ...], list[tuple[int, Sequence[int]]]] = defaultdict(list)
    for line_id, clause in enumerate(clauses, 1):
        support = tuple(sorted(abs(literal) for literal in clause))
        if 1 <= len(support) <= max_parity_width:
            groups[support].append((line_id, clause))
    candidates: list[dict[str, Any]] = []
    for support in sorted(groups):
        masks: dict[int, int] = {}
        for line_id, clause in groups[support]:
            mask = sum(
                1 << index
                for index, variable in enumerate(support)
                if -variable in clause
            )
            masks.setdefault(mask, line_id)
        values = tuple(
            1 if index + 1 in support else 0
            for index in range(width)
        )
        for forbidden_parity in (0, 1):
            required = {
                mask
                for mask in range(1 << len(support))
                if mask.bit_count() & 1 == forbidden_parity
            }
            if required.issubset(masks):
                candidates.append(
                    _regional_record(
                        _Line(
                            _XOR,
                            values,
                            1 - forbidden_parity,
                            _PARITY_IMPORT,
                            left=masks[min(required)],
                        )
                    )
                )
    return candidates


def _regional_resolve(
    left: _Line,
    right: _Line,
    pivot: int,
) -> tuple[int, ...] | None:
    a = left.values[pivot - 1]
    b = right.values[pivot - 1]
    if left.kind != _CLAUSE or right.kind != _CLAUSE or a == 0 or b != -a:
        return None
    values: list[int] = []
    for index, (lv, rv) in enumerate(zip(left.values, right.values)):
        if index == pivot - 1:
            values.append(0)
        elif lv and rv and lv != rv:
            return None
        else:
            values.append(lv or rv)
    return tuple(values)


def _regional_witness(
    clauses: Sequence[Sequence[int]],
    variable_count: int,
    cursor: int,
) -> dict[str, bool] | None:
    assignment = {
        str(variable): bool(cursor & (1 << (variable - 1)))
        for variable in range(1, variable_count + 1)
    }
    if all(
        any(assignment[str(abs(literal))] == (literal > 0) for literal in clause)
        for clause in clauses
    ):
        return assignment
    return None


def _regional_sat_result(
    source: Mapping[str, Any],
    witness: Mapping[str, bool],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "proof_system": (
            "CNF resolution plus cutting planes, GF(2) elimination, "
            "cardinality-parity bridges, and acyclic extension definitions"
        ),
        "original_variables": int(source["variable_count"]),
        "original_clauses": len(source["clauses"]),
        "status": "sat",
        "root_line": None,
        "lines": [],
        "witness": dict(witness),
    }
    payload["proof_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _regional_fault_result(
    source: Mapping[str, Any],
    error: Exception,
) -> dict[str, Any]:
    variable_count = source.get("variable_count", 0)
    clauses = source.get("clauses", [])
    payload: dict[str, Any] = {
        "schema": PROOF_SCHEMA,
        "proof_system": "hybrid regional kernel",
        "original_variables": variable_count if isinstance(variable_count, int) else 0,
        "original_clauses": len(clauses) if isinstance(clauses, list) else 0,
        "status": "faulted",

        "root_line": None,
        "lines": [],
        "error": {
            "type": type(error).__name__,
            "message": str(error),
        },
    }
    payload["proof_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload
def _regional_cliques(
    proof_lines: Sequence[Mapping[str, Any]],
    *,
    width: int,
    original_count: int,
) -> list[tuple[tuple[int, ...], dict[tuple[int, int], int]]]:
    edge_rows: dict[tuple[int, int], int] = {}
    for line_id, record in enumerate(proof_lines, 1):
        line = _regional_line(record, width=width)
        if (
            line.kind == _PB
            and line.rule == _CLAUSE_PB
            and line.left <= original_count
        ):
            support = tuple(index + 1 for index, value in enumerate(line.values) if value)
            if (
                len(support) == 2
                and line.rhs == 1
                and all(line.values[variable - 1] == 1 for variable in support)
            ):
                edge_rows.setdefault((support[0], support[1]), line_id)
    adjacency: dict[int, set[int]] = defaultdict(set)
    for left, right in edge_rows:
        adjacency[left].add(right)
        adjacency[right].add(left)
    candidates: set[tuple[int, ...]] = set()
    all_variables = sorted(adjacency)
    for edge in sorted(edge_rows):
        clique = list(edge)
        for variable in all_variables:
            if variable not in clique and all(variable in adjacency[item] for item in clique):
                clique.append(variable)
        candidates.add(tuple(sorted(clique)))
    maximal = [
        candidate
        for candidate in sorted(candidates, key=lambda row: (-len(row), row))
        if not any(set(candidate) < set(other) for other in candidates)
    ]
    return [(clique, edge_rows) for clique in maximal]


def _regional_aggregate_rows(
    proof_lines: Sequence[Mapping[str, Any]],
    row_ids: Sequence[int],
    *,
    width: int,
) -> list[int]:
    selected: list[int] = []
    used: set[int] = set()
    for line_id in sorted(
        row_ids,
        key=lambda item: tuple(
            index
            for index, value in enumerate(
                _regional_line(proof_lines[item - 1], width=width).values
            )
            if value
        ),
    ):
        support = {
            index
            for index, value in enumerate(
                _regional_line(proof_lines[line_id - 1], width=width).values
            )
            if value
        }
        if support and support.isdisjoint(used):
            selected.append(line_id)
            used.update(support)
    return selected
def _regional_bridge_pairs(
    proof_lines: Sequence[Mapping[str, Any]],
    *,
    width: int,
) -> list[tuple[int, int, tuple[int, ...], int]]:
    representatives: dict[tuple[tuple[int, ...], int], int] = {}
    for line_id, record in enumerate(proof_lines, 1):
        line = _regional_line(record, width=width)
        if line.kind == _PB:
            representatives.setdefault((line.values, line.rhs), line_id)
    pairs: list[tuple[int, int, tuple[int, ...], int]] = []
    for (values, rhs), upper_id in representatives.items():
        if not values or any(value not in (0, 1) for value in values):
            continue
        lower_id = representatives.get((tuple(-value for value in values), -rhs))
        if lower_id is not None:
            pairs.append((upper_id, lower_id, values, rhs))
    return pairs




def regional_state(
    clauses: Sequence[Sequence[int]],
    *,
    variable_count: int,
    profile: HybridInferenceProfile | Mapping[str, Any] | None = None,
    **profile_options: Any,
) -> dict[str, Any]:
    """Create a typed, JSON-safe regional state for hybrid exact inference."""

    if not isinstance(clauses, Sequence) or isinstance(clauses, (str, bytes)):
        raise HybridInferenceError("regional hybrid clauses must be a sequence")
    try:
        raw_clauses = tuple(tuple(clause) for clause in clauses)
    except TypeError as exc:
        raise HybridInferenceError("regional hybrid clauses are invalid") from exc
    variables = _exact_integer(variable_count, "variable_count", minimum=1)
    regional_profile = _regional_profile(
        profile,
        variable_count=variables,
        clause_count=len(raw_clauses),
        options=profile_options,
    )
    try:
        canonical = tuple(
            sorted(
                {_canonical_clause(clause, variables) for clause in raw_clauses},
                key=lambda clause: (len(clause), clause),
            )
        )
    except (TypeError, HybridInferenceError) as exc:
        raise HybridInferenceError("regional hybrid source is invalid") from exc
    if len(canonical) > regional_profile.max_original_clauses:
        raise HybridInferenceError("regional hybrid source exceeds clause capacity")
    source = {
        "clauses": [list(clause) for clause in canonical],
        "variable_count": variables,
    }
    width = regional_profile.max_total_variables
    input_records = [
        _regional_clause_record(clause, width=width) for clause in canonical
    ]
    root_line = (
        next(
            (index + 1 for index, record in enumerate(input_records)
             if not any(record["values"])),
            None,
        )
    )
    continuation = {
        "method": "resolution" if root_line is not None else "extensions",
        "pc": len(input_records),
        "assignment_cursor": 0,
        "extensions": {"cursor": 0, "substep": 0},
        "pb_cursor": 0,
        "parity_cursor": 0,
        "xor_candidate": 0,
        "xor_current": 0,
        "xor_basis": {},
        "bounds": {
            "clique_cursor": 0,
            "stage": "start",
            "variables": [],
            "variable_index": 2,
            "current_id": 0,
            "pair_ids": [],
            "pair_index": 1,
            "pair_sum_id": 0,
            "total_id": 0,
            "ids": [],
        },
        "aggregate": {
            "stage": "lower",
            "initialized": False,
            "rows": [],
            "index": 1,
            "current_id": 0,
            "lower_total": None,
            "upper_total": None,
        },
        "bridges": {
            "cursor": 0,
            "pairs": [],
            "xor_candidate": 0,
            "xor_current": 0,
        },
        "pair_left": 0,
        "pair_right": 1,
        "pivot": _regional_pivot_order(
            original_variables=variables,
            total_variables=width,
        )[0],
        "root_line": root_line,
        "proof_lines": input_records,
    }
    state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": source,
        "profile": regional_profile.as_dict(),
        "phase": "ready",
        "continuation": continuation,
        "journal": [],
        "ledger": {
            "invocations": 0,
            "primitive_work": 0,
            "max_primitive_work": regional_profile.max_transitions,
            "max_proof_lines": regional_profile.max_lines,
        },
        "result": None,
    }
    _validate_regional_state(state)
    return state


def _validate_regional_cursors(
    continuation: Mapping[str, Any],
    *,
    profile: HybridInferenceProfile,
    proof_count: int,
) -> None:
    extensions = continuation["extensions"]
    for name in ("cursor", "substep"):
        _exact_integer(
            extensions.get(name),
            f"regional hybrid extensions {name}",
        )
    if extensions["cursor"] > profile.max_extensions:
        raise HybridInferenceError("regional hybrid extension cursor is invalid")
    if extensions["substep"] not in (0, 1, 2, 3):
        raise HybridInferenceError("regional hybrid extension substep is invalid")

    bounds = continuation["bounds"]
    _exact_integer(bounds.get("clique_cursor"), "regional hybrid clique cursor")
    _exact_integer(bounds.get("variable_index"), "regional hybrid variable index")
    _exact_integer(bounds.get("current_id"), "regional hybrid bound current")
    _exact_integer(bounds.get("pair_index"), "regional hybrid pair cursor")
    _exact_integer(bounds.get("pair_sum_id"), "regional hybrid pair sum")
    _exact_integer(bounds.get("total_id"), "regional hybrid bound total")
    if bounds["stage"] not in {"start", "pair-init", "pair-add", "scale", "total", "divide"}:
        raise HybridInferenceError("regional hybrid bound stage is invalid")
    if not isinstance(bounds.get("variables"), list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in bounds["variables"]
    ):
        raise HybridInferenceError("regional hybrid bound variables are invalid")
    if not isinstance(bounds.get("pair_ids"), list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in bounds["pair_ids"]
    ):
        raise HybridInferenceError("regional hybrid bound pair ids are invalid")
    if not isinstance(bounds.get("ids"), list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in bounds["ids"]
    ):
        raise HybridInferenceError("regional hybrid bound ids are invalid")
    if bounds["current_id"] > proof_count or bounds["pair_sum_id"] > proof_count:
        raise HybridInferenceError("regional hybrid bound proof cursor is invalid")
    if bounds["total_id"] > proof_count:
        raise HybridInferenceError("regional hybrid bound total cursor is invalid")
    if bounds["pair_index"] < 1:
        raise HybridInferenceError("regional hybrid bound pair cursor is invalid")
    aggregate = continuation["aggregate"]
    if aggregate["stage"] not in {"lower", "upper", "final"}:
        raise HybridInferenceError("regional hybrid aggregate stage is invalid")
    if not isinstance(aggregate.get("initialized"), bool):
        raise HybridInferenceError("regional hybrid aggregate initialization is invalid")
    _exact_integer(aggregate.get("index"), "regional hybrid aggregate cursor", minimum=1)
    _exact_integer(aggregate.get("current_id"), "regional hybrid aggregate current")
    for name in ("lower_total", "upper_total"):
        value = aggregate.get(name)
        if value is not None:
            _exact_integer(value, f"regional hybrid aggregate {name}", minimum=1)
            if value > proof_count:
                raise HybridInferenceError("regional hybrid aggregate line is invalid")
    if not isinstance(aggregate.get("rows"), list) or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 1
        for value in aggregate["rows"]
    ):
        raise HybridInferenceError("regional hybrid aggregate rows are invalid")
    if aggregate["current_id"] > proof_count:
        raise HybridInferenceError("regional hybrid aggregate current is invalid")

    bridges = continuation["bridges"]
    _exact_integer(bridges.get("cursor"), "regional hybrid bridge cursor")
    _exact_integer(bridges.get("xor_candidate"), "regional hybrid bridge XOR candidate")
    _exact_integer(bridges.get("xor_current"), "regional hybrid bridge XOR current")
    if not isinstance(bridges.get("pairs"), list):
        raise HybridInferenceError("regional hybrid bridge pairs are invalid")
    for pair in bridges["pairs"]:
        if (
            not isinstance(pair, list)
            or len(pair) != 4
            or any(
                isinstance(value, bool) or not isinstance(value, int) or value < 1
                for value in pair[:2]
            )
            or not isinstance(pair[2], list)
            or len(pair[2]) != profile.max_total_variables
            or any(
                isinstance(value, bool) or not isinstance(value, int)
                for value in pair[2]
            )
            or isinstance(pair[3], bool)
            or not isinstance(pair[3], int)
        ):
            raise HybridInferenceError("regional hybrid bridge pair is invalid")
    if bridges["cursor"] > len(bridges["pairs"]):
        raise HybridInferenceError("regional hybrid bridge cursor is invalid")
    if bridges["xor_current"] > proof_count:
        raise HybridInferenceError("regional hybrid bridge XOR line is invalid")


def _validate_regional_state(state: Any) -> None:
    if not isinstance(state, Mapping) or set(state) != _REGIONAL_KEYS:
        raise HybridInferenceError("regional hybrid state keys are invalid")
    if state["schema"] != REGIONAL_STATE_SCHEMA:
        raise HybridInferenceError("regional hybrid state schema is invalid")
    if state["phase"] not in {"ready", "running", "terminal", "faulted"}:
        raise HybridInferenceError("regional hybrid state phase is invalid")
    source = state["source"]
    if not isinstance(source, Mapping) or set(source) != {"clauses", "variable_count"}:
        raise HybridInferenceError("regional hybrid source is invalid")
    variables = _exact_integer(
        source["variable_count"],
        "regional hybrid variable_count",
        minimum=1,
    )
    clauses = source["clauses"]
    if not isinstance(clauses, list):
        raise HybridInferenceError("regional hybrid source clauses are invalid")
    try:
        canonical = tuple(
            sorted(
                {_canonical_clause(clause, variables) for clause in clauses},
                key=lambda clause: (len(clause), clause),
            )
        )
    except (TypeError, HybridInferenceError) as exc:
        raise HybridInferenceError("regional hybrid source clauses are invalid") from exc
    if [list(clause) for clause in canonical] != clauses:
        raise HybridInferenceError("regional hybrid source is not canonical")
    try:
        profile = HybridInferenceProfile(**dict(state["profile"]))
    except (TypeError, HybridInferenceError) as exc:
        raise HybridInferenceError("regional hybrid profile is invalid") from exc
    continuation = state["continuation"]
    if not isinstance(continuation, Mapping):
        raise HybridInferenceError("regional hybrid continuation is invalid")
    methods = {
        "extensions",
        "clause-pb",
        "parity",
        "xor",
        "bounds",
        "aggregate",
        "bridges",
        "bridge-xor",
        "resolution",
        "assignments",
    }
    if continuation.get("method") not in methods:
        raise HybridInferenceError("regional hybrid continuation method is invalid")
    for name in ("pc", "assignment_cursor", "pb_cursor", "parity_cursor"):
        _exact_integer(continuation.get(name), f"regional hybrid continuation {name}")
    for name in ("xor_candidate", "xor_current", "pair_left", "pair_right", "pivot"):
        _exact_integer(continuation.get(name), f"regional hybrid continuation {name}")
    if not isinstance(continuation.get("xor_basis"), Mapping):
        raise HybridInferenceError("regional hybrid XOR basis is invalid")
    root_line = continuation.get("root_line")
    if root_line is not None:
        _exact_integer(root_line, "regional hybrid root line", minimum=1)
    proof_lines = continuation.get("proof_lines")
    if not isinstance(proof_lines, list):
        raise HybridInferenceError("regional hybrid proof journal is invalid")
    pc = int(continuation["pc"])
    if not 0 <= pc == len(proof_lines) <= profile.max_lines:
        raise HybridInferenceError("regional hybrid proof cursor is invalid")
    width = profile.max_total_variables
    for record in proof_lines:
        if not isinstance(record, Mapping):
            raise HybridInferenceError("regional hybrid proof line is invalid")
        _regional_line(record, width=width)
    expected_input = [
        _regional_clause_record(clause, width=width) for clause in clauses
    ]
    if proof_lines[: len(expected_input)] != expected_input:
        raise HybridInferenceError("regional hybrid input proof prefix is invalid")
    for name in ("extensions", "bounds", "aggregate", "bridges"):
        if not isinstance(continuation.get(name), Mapping):
            raise HybridInferenceError(f"regional hybrid {name} cursor is invalid")
    _validate_regional_cursors(
        continuation,
        profile=profile,
        proof_count=pc,
    )
    if not isinstance(state["journal"], list) or any(
        not isinstance(event, Mapping) for event in state["journal"]
    ):
        raise HybridInferenceError("regional hybrid journal is invalid")
    ledger = state["ledger"]
    if not isinstance(ledger, Mapping):
        raise HybridInferenceError("regional hybrid ledger is invalid")
    for name in (
        "invocations",
        "primitive_work",
        "max_primitive_work",
        "max_proof_lines",
    ):
        _exact_integer(ledger.get(name), f"regional hybrid ledger {name}")
    if ledger["max_proof_lines"] != profile.max_lines:
        raise HybridInferenceError("regional hybrid proof capacity mismatch")
    result = state["result"]
    if state["phase"] in {"terminal", "faulted"} and not isinstance(result, Mapping):
        raise HybridInferenceError("terminal regional hybrid state has no result")
    if state["phase"] in {"ready", "running"} and result is not None:
        raise HybridInferenceError("running regional hybrid state has a result")
    try:
        _canonical(state)
    except (TypeError, ValueError) as exc:
        raise HybridInferenceError("regional hybrid state is not JSON-safe") from exc


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Perform at most ``quantum`` direct typed hybrid rule/search steps."""

    _validate_regional_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise HybridInferenceError("regional hybrid kernel takes no arguments")
    quantum = _exact_integer(quantum, "regional hybrid quantum", minimum=1)
    if quantum > REGIONAL_KERNEL_MAX_WORK:
        raise HybridInferenceError("regional hybrid quantum exceeds kernel bound")
    updated = dict(state)
    ledger = dict(state["ledger"])
    if int(ledger["invocations"]) >= _SAFE_INTEGER:
        raise HybridInferenceError("regional hybrid invocation ledger exhausted")
    ledger["invocations"] = int(ledger["invocations"]) + 1
    updated["ledger"] = ledger
    if state["phase"] == "terminal":
        return KernelResult(state=updated, status="done", work=0, output=state["result"])
    if state["phase"] == "faulted":
        return KernelResult(state=updated, status="fault", work=0, output=state["result"])

    source = state["source"]
    performed = 0
    events: list[Mapping[str, Any]] = []
    try:
        profile = HybridInferenceProfile(**dict(state["profile"]))
        continuation = json.loads(_canonical(state["continuation"]).decode("utf-8"))
        method = continuation["method"]
        pc = int(continuation["pc"])
        cursor = int(continuation["assignment_cursor"])
        extension_cursor = int(continuation["extensions"]["cursor"])
        extension_substep = int(continuation["extensions"]["substep"])
        pb_cursor = int(continuation["pb_cursor"])
        parity_cursor = int(continuation["parity_cursor"])
        xor_candidate = int(continuation["xor_candidate"])
        xor_current = int(continuation["xor_current"])
        xor_basis = {
            int(key): int(value)
            for key, value in continuation["xor_basis"].items()
        }
        pair_left = int(continuation["pair_left"])
        pair_right = int(continuation["pair_right"])
        pivot = int(continuation["pivot"])
        root_line = continuation["root_line"]
        proof_lines = continuation["proof_lines"]
        clauses = tuple(tuple(clause) for clause in source["clauses"])
        variable_count = int(source["variable_count"])
        terminal_result: dict[str, Any] | None = None
        terminal_status: str | None = None
        extensions = _regional_extension_candidates(
            clauses,
            original_variables=variable_count,
            max_extensions=profile.max_extensions,
        )
        pivot_order = _regional_pivot_order(
            original_variables=variable_count,
            total_variables=profile.max_total_variables,
        )
        parity_candidates = _regional_parity_candidates(
            clauses,
            width=profile.max_total_variables,
            max_parity_width=profile.max_parity_width,
        )
        bound_state = continuation["bounds"]
        aggregate_state = continuation["aggregate"]
        bridge_state = continuation["bridges"]
        while performed < quantum and terminal_status is None:
            if int(ledger["primitive_work"]) + performed >= int(
                ledger["max_primitive_work"]
            ):
                terminal_status = "exhausted"
                break
            if method == "extensions":
                if extension_cursor >= len(extensions):
                    method = "clause-pb"
                    continue
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                new_variable, pair = extensions[extension_cursor]
                definition_id = pc + 1 - extension_substep
                record = _regional_extension_record(
                    new_variable,
                    pair,
                    width=profile.max_total_variables,
                    definition_id=definition_id,
                    substep=extension_substep,
                )
                proof_lines.append(record)
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": _RULE_NAMES[int(record["rule"])],
                        "line_id": pc,
                        "rule": _RULE_NAMES[int(record["rule"])],
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                extension_substep += 1
                if extension_substep >= 4:
                    extension_cursor += 1
                    extension_substep = 0
                continue
            if method == "clause-pb":
                if pb_cursor >= len(clauses):
                    method = "parity"
                    continue
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                record = _regional_pb_record(
                    clauses[pb_cursor],
                    width=profile.max_total_variables,
                    source_id=pb_cursor + 1,
                )
                proof_lines.append(record)
                pb_cursor += 1
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": "clause-pb",
                        "line_id": pc,
                        "rule": "clause-pb",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                continue
            if method == "parity":
                if parity_cursor >= len(parity_candidates):
                    method = "xor"
                    continue
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                record = json.loads(
                    _canonical(parity_candidates[parity_cursor]).decode("utf-8")
                )
                proof_lines.append(record)
                parity_cursor += 1
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": "parity-import",
                        "line_id": pc,
                        "rule": "parity-import",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                continue
            if method == "xor":
                imports = [
                    index + 1
                    for index, record in enumerate(proof_lines)
                    if int(record["rule"]) == _PARITY_IMPORT
                ]
                if xor_candidate >= len(imports):
                    method = "bounds"
                    continue
                if xor_current == 0:
                    xor_current = imports[xor_candidate]
                    continue
                current = _regional_line(
                    proof_lines[xor_current - 1],
                    width=profile.max_total_variables,
                )
                support = [
                    index + 1 for index, value in enumerate(current.values) if value
                ]
                if not support:
                    if current.rhs == 1:
                        root_line = xor_current
                        terminal_status = "unsat"
                    else:
                        xor_candidate += 1
                        xor_current = 0
                    continue
                pivot_var = support[0]
                prior_id = xor_basis.get(pivot_var)
                if prior_id is None:
                    xor_basis[pivot_var] = xor_current
                    xor_candidate += 1
                    xor_current = 0
                    continue
                prior = _regional_line(
                    proof_lines[prior_id - 1],
                    width=profile.max_total_variables,
                )
                record = _regional_record(
                    _Line(
                        _XOR,
                        tuple(a ^ b for a, b in zip(current.values, prior.values)),
                        current.rhs ^ prior.rhs,
                        _XOR_ADD,
                        left=xor_current,
                        right=prior_id,
                        aux=pivot_var,
                    )
                )
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                proof_lines.append(record)
                xor_current = len(proof_lines)
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": "xor-add",
                        "line_id": pc,
                        "rule": "xor-add",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                continue
            if method == "bounds":
                cliques = _regional_cliques(
                    proof_lines,
                    width=profile.max_total_variables,
                    original_count=len(clauses),
                )
                clique_cursor = int(bound_state["clique_cursor"])
                if clique_cursor >= len(cliques):
                    method = "aggregate"
                    continue
                clique, edge_rows = cliques[clique_cursor]
                stage = bound_state["stage"]
                if stage == "start":
                    if len(clique) < 2:
                        bound_state["clique_cursor"] = clique_cursor + 1
                        continue
                    bound_state["variables"] = list(clique[:2])
                    bound_state["variable_index"] = 2
                    bound_state["current_id"] = edge_rows[
                        (clique[0], clique[1])
                    ]
                    bound_state["stage"] = "pair-init"
                    continue
                variables = list(bound_state["variables"])
                variable_index = int(bound_state["variable_index"])
                if stage == "pair-init":
                    if variable_index >= len(clique):
                        bound_state["ids"].append(int(bound_state["current_id"]))
                        bound_state["clique_cursor"] = clique_cursor + 1
                        bound_state["stage"] = "start"
                        continue
                    variable = clique[variable_index]
                    pair_ids = [
                        edge_rows[(min(item, variable), max(item, variable))]
                        for item in variables
                    ]
                    bound_state["pair_ids"] = pair_ids
                    bound_state["pair_index"] = 1
                    bound_state["pair_sum_id"] = pair_ids[0]
                    bound_state["stage"] = (
                        "pair-add" if len(pair_ids) > 1 else "scale"
                    )
                    continue
                if stage == "pair-add":
                    pair_ids = bound_state["pair_ids"]
                    pair_index = int(bound_state["pair_index"])
                    if pair_index >= len(pair_ids):
                        bound_state["stage"] = "scale"
                        continue
                    left_id = int(bound_state["pair_sum_id"])
                    right_id = int(pair_ids[pair_index])
                    left = _regional_line(
                        proof_lines[left_id - 1],
                        width=profile.max_total_variables,
                    )
                    right = _regional_line(
                        proof_lines[right_id - 1],
                        width=profile.max_total_variables,
                    )
                    if len(proof_lines) >= profile.max_lines:
                        terminal_status = "exhausted"
                        continue
                    record = _regional_record(
                        _Line(
                            _PB,
                            tuple(a + b for a, b in zip(left.values, right.values)),
                            left.rhs + right.rhs,
                            _PB_ADD,
                            left=left_id,
                            right=right_id,
                        )
                    )
                    proof_lines.append(record)
                    pc += 1
                    bound_state["pair_sum_id"] = pc
                    bound_state["pair_index"] = pair_index + 1
                    performed += 1
                    events.append(
                        {
                            "action": "pb-add",
                            "line_id": pc,
                            "rule": "pb-add",
                            "derivation": _regional_line_dict(record, pc),
                        }
                    )
                    continue
                if stage == "scale":
                    factor = len(variables) - 1
                    if factor == 1:
                        bound_state["stage"] = "total"
                        continue
                    if len(proof_lines) >= profile.max_lines:
                        terminal_status = "exhausted"
                        continue
                    current_id = int(bound_state["current_id"])
                    current = _regional_line(
                        proof_lines[current_id - 1],
                        width=profile.max_total_variables,
                    )
                    record = _regional_record(
                        _Line(
                            _PB,
                            tuple(factor * value for value in current.values),
                            factor * current.rhs,
                            _PB_SCALE,
                            left=current_id,
                            aux=factor,
                        )
                    )
                    proof_lines.append(record)
                    pc += 1
                    bound_state["current_id"] = pc
                    bound_state["stage"] = "total"
                    performed += 1
                    events.append(
                        {
                            "action": "pb-scale",
                            "line_id": pc,
                            "rule": "pb-scale",
                            "derivation": _regional_line_dict(record, pc),
                        }
                    )
                    continue
                if stage == "total":
                    if len(proof_lines) >= profile.max_lines:
                        terminal_status = "exhausted"
                        continue
                    left_id = int(bound_state["current_id"])
                    right_id = int(bound_state["pair_sum_id"])
                    left = _regional_line(
                        proof_lines[left_id - 1],
                        width=profile.max_total_variables,
                    )
                    right = _regional_line(
                        proof_lines[right_id - 1],
                        width=profile.max_total_variables,
                    )
                    record = _regional_record(
                        _Line(
                            _PB,
                            tuple(a + b for a, b in zip(left.values, right.values)),
                            left.rhs + right.rhs,
                            _PB_ADD,
                            left=left_id,
                            right=right_id,
                        )
                    )
                    proof_lines.append(record)
                    pc += 1
                    bound_state["total_id"] = pc
                    bound_state["stage"] = "divide"
                    performed += 1
                    events.append(
                        {
                            "action": "pb-add",
                            "line_id": pc,
                            "rule": "pb-add",
                            "derivation": _regional_line_dict(record, pc),
                        }
                    )
                    continue
                if stage == "divide":
                    divisor = len(variables)
                    total_id = int(bound_state["total_id"])
                    total = _regional_line(
                        proof_lines[total_id - 1],
                        width=profile.max_total_variables,
                    )
                    if any(value % divisor for value in total.values):
                        terminal_status = "exhausted"
                        continue
                    if len(proof_lines) >= profile.max_lines:
                        terminal_status = "exhausted"
                        continue
                    record = _regional_record(
                        _Line(
                            _PB,
                            tuple(value // divisor for value in total.values),
                            _floor_div(total.rhs, divisor),
                            _PB_DIVIDE,
                            left=total_id,
                            aux=divisor,
                        )
                    )
                    proof_lines.append(record)
                    pc += 1
                    bound_state["current_id"] = pc
                    bound_state["variables"] = [*variables, clique[variable_index]]
                    bound_state["variable_index"] = variable_index + 1
                    bound_state["stage"] = "pair-init"
                    performed += 1
                    events.append(
                        {
                            "action": "pb-divide",
                            "line_id": pc,
                            "rule": "pb-divide",
                            "derivation": _regional_line_dict(record, pc),
                        }
                    )
                    continue
            if method == "aggregate":
                stage = aggregate_state["stage"]
                if not aggregate_state.get("initialized", False):
                    if stage == "lower":
                        lower_rows = [
                            index + 1
                            for index, record in enumerate(proof_lines)
                            if int(record["rule"]) == _CLAUSE_PB
                            and _regional_line(
                                record,
                                width=profile.max_total_variables,
                            ).rhs == -1
                            and all(value in (0, -1) for value in record["values"])
                        ]
                        rows = _regional_aggregate_rows(
                            proof_lines,
                            lower_rows,
                            width=profile.max_total_variables,
                        )
                    elif stage == "upper":
                        rows = _regional_aggregate_rows(
                            proof_lines,
                            bound_state["ids"],
                            width=profile.max_total_variables,
                        )
                    else:
                        rows = []
                    aggregate_state["rows"] = rows
                    aggregate_state["index"] = 1
                    aggregate_state["current_id"] = rows[0] if rows else 0
                    aggregate_state["initialized"] = True
                    continue
                rows = aggregate_state["rows"]
                index = int(aggregate_state["index"])
                if index < len(rows):
                    if len(proof_lines) >= profile.max_lines:
                        terminal_status = "exhausted"
                        continue
                    left_id = int(aggregate_state["current_id"])
                    right_id = int(rows[index])
                    left = _regional_line(
                        proof_lines[left_id - 1],
                        width=profile.max_total_variables,
                    )
                    right = _regional_line(
                        proof_lines[right_id - 1],
                        width=profile.max_total_variables,
                    )
                    record = _regional_record(
                        _Line(
                            _PB,
                            tuple(a + b for a, b in zip(left.values, right.values)),
                            left.rhs + right.rhs,
                            _PB_ADD,
                            left=left_id,
                            right=right_id,
                        )
                    )
                    proof_lines.append(record)
                    pc += 1
                    aggregate_state["current_id"] = pc
                    aggregate_state["index"] = index + 1
                    performed += 1
                    events.append(
                        {
                            "action": "pb-add",
                            "line_id": pc,
                            "rule": "pb-add",
                            "derivation": _regional_line_dict(record, pc),
                        }
                    )
                    continue
                total_id = int(aggregate_state["current_id"]) if rows else None
                if stage == "lower":
                    aggregate_state["lower_total"] = total_id
                    aggregate_state["stage"] = "upper"
                elif stage == "upper":
                    aggregate_state["upper_total"] = total_id
                    aggregate_state["stage"] = "final"
                else:
                    lower_id = aggregate_state["lower_total"]
                    upper_id = aggregate_state["upper_total"]
                    if lower_id is not None and upper_id is not None:
                        lower = _regional_line(
                            proof_lines[int(lower_id) - 1],
                            width=profile.max_total_variables,
                        )
                        upper = _regional_line(
                            proof_lines[int(upper_id) - 1],
                            width=profile.max_total_variables,
                        )
                        if all(a == -b for a, b in zip(lower.values, upper.values)):
                            if len(proof_lines) >= profile.max_lines:
                                terminal_status = "exhausted"
                                continue
                            record = _regional_record(
                                _Line(
                                    _PB,
                                    tuple(a + b for a, b in zip(lower.values, upper.values)),
                                    lower.rhs + upper.rhs,
                                    _PB_ADD,
                                    left=int(lower_id),
                                    right=int(upper_id),
                                )
                            )
                            proof_lines.append(record)
                            pc += 1
                            performed += 1
                            events.append(
                                {
                                    "action": "pb-add",
                                    "line_id": pc,
                                    "rule": "pb-add",
                                    "derivation": _regional_line_dict(record, pc),
                                }
                            )
                            if record["rhs"] < 0:
                                root_line = pc
                                terminal_status = "unsat"
                                continue
                    bridge_state["pairs"] = [
                        list(pair)
                        for pair in _regional_bridge_pairs(
                            proof_lines,
                            width=profile.max_total_variables,
                        )
                    ]
                    bridge_state["cursor"] = 0
                    bridge_state["xor_candidate"] = 0
                    bridge_state["xor_current"] = 0
                    method = "bridges"
                    continue
                aggregate_state["rows"] = []
                aggregate_state["index"] = 1
                aggregate_state["current_id"] = 0
                aggregate_state["initialized"] = False
                continue
            if method == "bridges":
                pairs = bridge_state["pairs"]
                bridge_cursor = int(bridge_state["cursor"])
                if bridge_cursor >= len(pairs):
                    method = "bridge-xor"
                    continue
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                upper_id, lower_id, values, rhs = pairs[bridge_cursor]
                record = _regional_record(
                    _Line(
                        _XOR,
                        tuple(values),
                        int(rhs) & 1,
                        _CARDINALITY_PARITY,
                        left=int(upper_id),
                        right=int(lower_id),
                    )
                )
                proof_lines.append(record)
                bridge_cursor += 1
                bridge_state["cursor"] = bridge_cursor
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": "cardinality-parity",
                        "line_id": pc,
                        "rule": "cardinality-parity",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                continue
            if method == "bridge-xor":
                bridge_ids = [
                    index + 1
                    for index, record in enumerate(proof_lines)
                    if int(record["rule"]) == _CARDINALITY_PARITY
                ]
                bridge_candidate = int(bridge_state["xor_candidate"])
                bridge_current = int(bridge_state["xor_current"])
                if bridge_candidate >= len(bridge_ids):
                    method = "resolution"
                    continue
                if bridge_current == 0:
                    bridge_current = bridge_ids[bridge_candidate]
                    bridge_state["xor_current"] = bridge_current
                    continue
                current = _regional_line(
                    proof_lines[bridge_current - 1],
                    width=profile.max_total_variables,
                )
                support = [
                    index + 1 for index, value in enumerate(current.values) if value
                ]
                if not support:
                    if current.rhs == 1:
                        root_line = bridge_current
                        terminal_status = "unsat"
                    else:
                        bridge_candidate += 1
                        bridge_current = 0
                    bridge_state["xor_candidate"] = bridge_candidate
                    bridge_state["xor_current"] = bridge_current
                    continue
                pivot_var = support[0]
                prior_id = xor_basis.get(pivot_var)
                if prior_id is None:
                    xor_basis[pivot_var] = bridge_current
                    bridge_candidate += 1
                    bridge_current = 0
                    bridge_state["xor_candidate"] = bridge_candidate
                    bridge_state["xor_current"] = bridge_current
                    continue
                prior = _regional_line(
                    proof_lines[prior_id - 1],
                    width=profile.max_total_variables,
                )
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                record = _regional_record(
                    _Line(
                        _XOR,
                        tuple(a ^ b for a, b in zip(current.values, prior.values)),
                        current.rhs ^ prior.rhs,
                        _XOR_ADD,
                        left=bridge_current,
                        right=prior_id,
                        aux=pivot_var,
                    )
                )
                proof_lines.append(record)
                bridge_current = len(proof_lines)
                bridge_state["xor_current"] = bridge_current
                pc += 1
                performed += 1
                events.append(
                    {
                        "action": "xor-add",
                        "line_id": pc,
                        "rule": "xor-add",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                continue
            if method == "resolution":
                if root_line is not None and pc >= int(root_line):
                    terminal_status = "unsat"
                    continue
                if len(proof_lines) >= profile.max_lines:
                    terminal_status = "exhausted"
                    continue
                if pair_left >= len(proof_lines) - 1:
                    method = "assignments"
                    continue
                if pair_right >= len(proof_lines):
                    pair_left += 1
                    pair_right = pair_left + 1
                    pivot = pivot_order[0]
                    continue
                left = _regional_line(
                    proof_lines[pair_left],
                    width=profile.max_total_variables,
                )
                right = _regional_line(
                    proof_lines[pair_right],
                    width=profile.max_total_variables,
                )
                left_id = pair_left + 1
                right_id = pair_right + 1
                pivot_used = pivot
                candidate = _regional_resolve(left, right, pivot_used)
                pivot_index = pivot_order.index(pivot_used) + 1
                if pivot_index >= len(pivot_order):
                    next_pivot = pivot_order[0]
                    pair_right += 1
                    if pair_right >= len(proof_lines):
                        pair_left += 1
                        pair_right = pair_left + 1
                else:
                    next_pivot = pivot_order[pivot_index]
                pivot = next_pivot
                performed += 1
                if candidate is None:
                    events.append(
                        {
                            "action": "resolve-search",
                            "line_id": None,
                            "rule": "resolve",
                            "pair_left": pair_left,
                            "pair_right": pair_right,
                            "pivot": pivot,
                        }
                    )
                    continue
                known = {
                    tuple(record["values"])
                    for record in proof_lines
                    if int(record["kind"]) == _CLAUSE
                }
                if candidate in known:
                    events.append(
                        {
                            "action": "resolve-duplicate",
                            "line_id": None,
                            "rule": "resolve",
                        }
                    )
                    continue
                record = _regional_record(
                    _Line(
                        _CLAUSE,
                        candidate,
                        0,
                        _RESOLVE,
                        left=left_id,
                        right=right_id,
                        aux=pivot_used,
                    )
                )
                proof_lines.append(record)
                pc += 1
                pair_left = 0
                pair_right = 1
                pivot = pivot_order[0]
                events.append(
                    {
                        "action": "resolve",
                        "line_id": pc,
                        "rule": "resolve",
                        "derivation": _regional_line_dict(record, pc),
                    }
                )
                if not any(candidate):
                    root_line = pc
                    terminal_status = "unsat"
                continue
            witness = _regional_witness(clauses, variable_count, cursor)
            events.append(
                {
                    "action": "assignment",
                    "assignment_cursor": cursor,
                    "accepted": witness is not None,
                    **({"witness": witness} if witness is not None else {}),
                }
            )
            cursor += 1
            performed += 1
            if witness is not None:
                terminal_result = _regional_sat_result(source, witness)
                terminal_status = "sat"
            elif cursor >= (1 << variable_count):
                terminal_status = "exhausted"

        if terminal_result is None and terminal_status is not None:
            terminal_root = (
                int(root_line)
                if terminal_status == "unsat" and root_line is not None
                else None
            )
            terminal_result = _regional_proof(
                source,
                proof_lines,
                status=terminal_status,
                root_line=terminal_root,
            )
        continuation.update(
            {
                "method": method,
                "pc": pc,
                "assignment_cursor": cursor,
                "pb_cursor": pb_cursor,
                "parity_cursor": parity_cursor,
                "xor_candidate": xor_candidate,
                "xor_current": xor_current,
                "xor_basis": {str(key): value for key, value in xor_basis.items()},
                "pair_left": pair_left,
                "pair_right": pair_right,
                "pivot": pivot,
                "root_line": root_line,
                "proof_lines": proof_lines,
            }
        )
        updated["continuation"] = continuation
        updated["journal"] = [*state["journal"], *events]
        ledger["primitive_work"] = int(ledger["primitive_work"]) + performed
        updated["ledger"] = ledger
        if terminal_result is not None:
            updated["phase"] = "terminal"
            updated["result"] = terminal_result
            return KernelResult(
                state=updated,
                status="done",
                work=performed,
                output=terminal_result,
                events=tuple(events),
            )
        updated["phase"] = "running"
        return KernelResult(
            state=updated,
            status="yield",
            work=performed,
            output=None,
            events=tuple(events),
        )
    except Exception as exc:
        fault = _regional_fault_result(source, exc)
        updated["phase"] = "faulted"
        updated["result"] = fault
        updated["journal"] = [
            *state["journal"],
            {"action": "fault", "error": fault["error"]},
        ]
        return KernelResult(
            state=updated,
            status="fault",
            work=performed,
            output=fault,
            events=tuple(events),
        )


__all__ = [
    "PROOF_SCHEMA",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "SCHEMA",
    "HybridInferenceError",
    "HybridInferenceField",
    "HybridInferenceProfile",
    "HybridInferenceState",
    "regional_kernel",
    "regional_state",
]
