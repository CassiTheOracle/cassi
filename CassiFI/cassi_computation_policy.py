"""Field-owned empirical portfolio policy for exact CassiFI constraint solving.

The policy is intentionally small and deterministic.  All adaptive observations
(attempt support, checked completions, elapsed cost, and exact work) live in one
immutable float64 tensor.  The tensor stores bounded integers exactly; no model,
side table, or unverified performance claim participates in selection.  Solver
results remain finite-source exact results: SAT is accepted only after evaluating
the original compiled clauses, UNSAT only after an independent proof auditor,
and exhaustion carries neither claim.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field as dataclass_field, replace
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_constraint_field import (
    PROBLEM_SCHEMA,
    CompiledConstraintProblem,
    ConstraintField,
    ConstraintFieldError,
    ConstraintFieldProfile,
    compile_circuit,
    compile_transition_problem,
)
from cassi_field_regions import KernelResult

SCHEMA = "cassifi.computation-policy.v4"
V3_SCHEMA = "cassifi.computation-policy.v3"
PREVIOUS_SCHEMA = "cassifi.computation-policy.v2"
LEGACY_SCHEMA = "cassifi.computation-policy.v1"
RECEIPT_SCHEMA = "cassifi.computation-policy-receipt.v4"
_LAYOUT = "computation-policy-refined-nine-plane-v4"
_V3_LAYOUT = "computation-policy-budgeted-nine-plane-v3"
_PREVIOUS_LAYOUT = "computation-policy-budgeted-seven-plane-v2"
_LEGACY_LAYOUT = "computation-policy-seven-plane-v1"
REGIONAL_KERNEL_NAME = "learning.computation-policy"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-computation-policy-state.v1"
_SAFE_INTEGER = 2**53 - 1
METHODS = (
    "conflict",
    "conflict-controller",
    "algebraic-1",
    "algebraic-1-controller",
    "algebraic-2",
    "algebraic-2-controller",
)

# Sixty-four structural contexts remain independent of source identity. Each
# has one legacy/unscoped prior and four real execution-budget classes.
_STRUCTURAL_CONTEXT_COUNT = 64
_BUDGET_CLASS_COUNT = 5
_CONTEXT_COUNT = _STRUCTURAL_CONTEXT_COUNT * _BUDGET_CLASS_COUNT
_BUDGET_CUTOFFS = (64, 512, 4096)
_RECENT_LIMIT = 32
_LONG_LIMIT = 4096
_EXPLORATION_INTERVAL = 4
_REEVALUATION_PERIOD = 24
_RECENT_DECAY_PERIOD = 16
_EPOCH_LIMIT = 1_000_000
_OBSERVED_ELAPSED_CAP_NS = 1_000_000_000_000
_OBSERVED_WORK_CAP = 1_000_000_000
_FEATURE_NAMES = (
    "transition_shape",
    "variable_bucket",
    "clause_bucket",
    "width_bucket",
    "density_bucket",
    "unit_bucket",
    "binary_bucket",
    "relation_bucket",
    "gate_bucket",
    "horizon_bucket",
    "native_xor",
    "native_cardinality",
    "pinned_density_bucket",
    "budget_class",
    "complexity_refinement",
)
_PLANES = (
    "long_support",
    "long_completion",
    "long_elapsed_ns",
    "long_work",
    "recent_support",
    "recent_completion",
    "recent_elapsed_ns",
    "context_epoch",
    "last_observed_epoch",
)
_PLANE_INDEX = {name: index for index, name in enumerate(_PLANES)}
_EVIDENCE_PLANES = _PLANES[:7]
_SHAPE = (9, _CONTEXT_COUNT, len(METHODS))
_V3_SHAPE = _SHAPE
_PREVIOUS_SHAPE = (7, _CONTEXT_COUNT, len(METHODS))
_LEGACY_SHAPE = (7, _STRUCTURAL_CONTEXT_COUNT, len(METHODS))


class PolicyError(ValueError):
    """Invalid policy, source, receipt evidence, or bounded execution."""


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PolicyError("value is not JSON-canonical") from exc


def _integer(value: Any, name: str, *, minimum: int = 0, maximum: int = _SAFE_INTEGER) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise PolicyError(f"{name} must be an exact bounded integer")
    return int(value)


def _safe_add(left: int, right: int, name: str) -> int:
    result = int(left) + int(right)
    if result < 0 or result > _SAFE_INTEGER:
        raise PolicyError(f"{name} counter overflow")
    return result


def _digest_field(field: np.ndarray, *, layout: str = _LAYOUT) -> str:
    digest = hashlib.sha256()
    digest.update(_canonical({"layout": layout, "shape": list(field.shape), "dtype": "float64"}))
    digest.update(field.tobytes(order="C"))
    return digest.hexdigest()


@dataclass(frozen=True, slots=True, eq=False)
class PolicyState:
    """Immutable exact policy field with lossless v1/v2 loading boundaries.

    Current fields keep long-horizon and synchronized recent observations,
    a context-local observation epoch, and each method's last observation in
    exact integer cells. Frozen v1/v2 descriptors remain byte-identical when
    loaded; the first learning operation migrates them deterministically.
    """

    _field: np.ndarray
    _schema: str = SCHEMA
    _layout: str = _LAYOUT
    _field_bytes: bytes = dataclass_field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        value = self._field
        if not isinstance(value, np.ndarray) or value.dtype != np.float64:
            raise PolicyError("policy field must be a float64 numpy tensor")

        versions = {
            SCHEMA: (_LAYOUT, _SHAPE),
            V3_SCHEMA: (_V3_LAYOUT, _V3_SHAPE),
            PREVIOUS_SCHEMA: (_PREVIOUS_LAYOUT, _PREVIOUS_SHAPE),
            LEGACY_SCHEMA: (_LEGACY_LAYOUT, _LEGACY_SHAPE),
        }
        if self._schema not in versions:
            raise PolicyError("unsupported policy field version")
        expected_layout, expected_shape = versions[self._schema]

        if self._layout != expected_layout:
            raise PolicyError("unsupported policy field version")

        if value.shape != expected_shape:
            raise PolicyError("policy field shape is invalid")

        # Single pass for finiteness, range, and integer check
        # Using boolean masks to avoid multiple full-array scans
        finite_mask = np.isfinite(value)
        if not np.all(finite_mask):
            raise PolicyError("policy field contains an out-of-range value")

        range_mask = (value < 0) | (value > _SAFE_INTEGER)
        if np.any(range_mask):
            raise PolicyError("policy field contains an out-of-range value")

        int_mask = value != np.floor(value)
        if np.any(int_mask):
            raise PolicyError("policy field cells must be exact integers")

        if self._schema == LEGACY_SCHEMA:
            support, completion, elapsed, work, audited, exhausted, observations = value

            # Early exit checks using boolean logic
            if not np.array_equal(support, observations):
                raise PolicyError("legacy support/observation counters disagree")
            if not np.array_equal(completion, audited):
                raise PolicyError("legacy completion/audit counters disagree")
            if not np.array_equal(completion + exhausted, support):
                raise PolicyError("legacy outcome counters disagree")

            # Check for unsupported legacy cells carrying cost
            if np.any((support == 0) & ((elapsed != 0) | (work != 0))):
                raise PolicyError("unsupported legacy cells carry cost")

            # Check for supported legacy cells lacking elapsed cost
            if np.any((support > 0) & (elapsed <= 0)):
                raise PolicyError("supported legacy cells lack elapsed cost")
        else:
            long_support, long_completion, long_elapsed, long_work, recent_support, recent_completion, recent_elapsed = value[:7]

            if np.any(long_support > _LONG_LIMIT):
                raise PolicyError("long-horizon support exceeds its bound")
            if np.any(recent_support > _RECENT_LIMIT):
                raise PolicyError("recent support exceeds its bound")
            if np.any(long_completion > long_support):
                raise PolicyError("long-horizon completion exceeds support")
            if np.any(recent_completion > recent_support):
                raise PolicyError("recent completion exceeds support")

            if np.any((long_support == 0) & ((long_elapsed != 0) | (long_work != 0))):
                raise PolicyError("unsupported long-horizon cells carry cost")

            if np.any(
                (long_support > 0)
                & (
                    (long_elapsed < long_support)
                    | (long_elapsed > long_support * _OBSERVED_ELAPSED_CAP_NS)
                    | (long_work > long_support * _OBSERVED_WORK_CAP)
                )
            ):
                raise PolicyError(
                    "long-horizon sample totals exceed observation bounds"
                )

            if np.any((recent_support == 0) & (recent_elapsed != 0)):
                raise PolicyError("unsupported recent cells carry cost")

            if np.any(
                (recent_support > 0)
                & (
                    (recent_elapsed < recent_support)
                    | (recent_elapsed > recent_support * _OBSERVED_ELAPSED_CAP_NS)
                )
            ):
                raise PolicyError(
                    "recent sample totals exceed observation bounds"
                )

            if self._schema in {SCHEMA, V3_SCHEMA}:
                epochs = value[_PLANE_INDEX["context_epoch"]]
                last = value[_PLANE_INDEX["last_observed_epoch"]]

                # Check canonical method-zero cell
                if np.any(epochs[:, 1:] != 0):
                    raise PolicyError(
                        "context epoch must use its canonical method-zero cell"
                    )

                context_epochs = epochs[:, 0]
                if np.any(context_epochs > _EPOCH_LIMIT):
                    raise PolicyError("policy context epoch exceeds its bound")

                if np.any(last > context_epochs[:, None]):
                    raise PolicyError(
                        "method observation epoch exceeds its context epoch"
                    )

                if np.any((long_support == 0) & (last != 0)) or np.any(
                    (long_support > 0) & (last == 0)
                ):
                    raise PolicyError(
                        "method support and last-observation epoch disagree"
                    )

        # Optimization: Use view instead of tobytes/frombuffer/reshape
        # This avoids creating intermediate byte arrays and reshaping copies
        raw = value.view(np.uint8).tobytes(order="C")
        immutable = np.frombuffer(raw, dtype=np.float64).reshape(value.shape)
        object.__setattr__(self, "_field_bytes", raw)
        object.__setattr__(self, "_field", immutable)

    @property
    def field(self) -> np.ndarray:
        copied = self._field.copy()
        copied.setflags(write=False)
        return copied

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)

    @property
    def state_sha256(self) -> str:
        return _digest_field(self._field, layout=self._layout)

    @property
    def is_legacy(self) -> bool:
        return self._schema != SCHEMA

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self._schema,
            "layout": self._layout,
            "shape": list(self._field.shape),
            "dtype": "float64",
            "field_b64": base64.b64encode(self._field.tobytes(order="C")).decode("ascii"),
            "state_sha256": self.state_sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PolicyState":
        required = {"schema", "layout", "shape", "dtype", "field_b64", "state_sha256"}
        if not isinstance(value, Mapping) or set(value) != required:
            raise PolicyError("invalid policy descriptor keys")
        schema = value["schema"]
        layout = value["layout"]
        if value["dtype"] != "float64":
            raise PolicyError("unsupported policy descriptor")
        if schema == SCHEMA and layout == _LAYOUT:
            shape = _SHAPE
        elif schema == V3_SCHEMA and layout == _V3_LAYOUT:
            shape = _V3_SHAPE
        elif schema == PREVIOUS_SCHEMA and layout == _PREVIOUS_LAYOUT:
            shape = _PREVIOUS_SHAPE
        elif schema == LEGACY_SCHEMA and layout == _LEGACY_LAYOUT:
            shape = _LEGACY_SHAPE
        else:
            raise PolicyError("unsupported policy descriptor")
        if value["shape"] != list(shape):
            raise PolicyError("policy descriptor shape mismatch")
        encoded = value["field_b64"]
        if not isinstance(encoded, str):
            raise PolicyError("policy descriptor field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            if base64.b64encode(raw).decode("ascii") != encoded:
                raise ValueError("noncanonical base64")
            if len(raw) != int(np.prod(shape)) * np.dtype(np.float64).itemsize:
                raise ValueError("field byte count mismatch")
            field = np.frombuffer(raw, dtype=np.float64).reshape(shape).copy()
        except (ValueError, TypeError) as exc:
            raise PolicyError("policy descriptor field encoding is invalid") from exc
        state = cls(field, _schema=str(schema), _layout=str(layout))
        if value["state_sha256"] != state.state_sha256:
            raise PolicyError("policy descriptor state digest mismatch")
        return state

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, PolicyState)
            and self._schema == other._schema
            and self.state_sha256 == other.state_sha256
        )


def initial_policy() -> PolicyState:
    """Return the zero-evidence current policy field."""

    return PolicyState(np.zeros(_SHAPE, dtype=np.float64))


def migrate_policy(policy: PolicyState) -> PolicyState:
    """Migrate frozen v1-v3 evidence into the current exact field layout."""

    if not isinstance(policy, PolicyState):
        raise PolicyError("policy must be PolicyState")
    if not policy.is_legacy:
        return policy
    if policy._schema == V3_SCHEMA:
        return PolicyState(policy._field.copy())
    field = np.zeros(_SHAPE, dtype=np.float64)
    if policy._schema == PREVIOUS_SCHEMA:
        field[: len(_EVIDENCE_PLANES)] = policy._field
        for context in range(_CONTEXT_COUNT):
            epoch = sum(
                int(policy._field[0, context, method])
                for method in range(len(METHODS))
            )
            while epoch > _EPOCH_LIMIT:
                epoch = (epoch + 1) // 2
            field[_PLANE_INDEX["context_epoch"], context, 0] = epoch
            for method in range(len(METHODS)):
                if int(policy._field[0, context, method]) > 0:
                    field[
                        _PLANE_INDEX["last_observed_epoch"], context, method
                    ] = epoch
        return PolicyState(field)
    for structural in range(_STRUCTURAL_CONTEXT_COUNT):
        target = structural * _BUDGET_CLASS_COUNT
        for method in range(len(METHODS)):
            support = int(policy._field[0, structural, method])
            completion = int(policy._field[1, structural, method])
            elapsed = int(policy._field[2, structural, method])
            work = int(policy._field[3, structural, method])
            while support > _LONG_LIMIT:
                support = (support + 1) // 2
                completion = (completion + 1) // 2
                elapsed = (elapsed + 1) // 2
                work = (work + 1) // 2
            if support:
                completion = min(completion, support)
                elapsed = min(
                    max(support, elapsed),
                    _OBSERVED_ELAPSED_CAP_NS * support,
                )
                work = min(work, _OBSERVED_WORK_CAP * support)
            field[_PLANE_INDEX["long_support"], target, method] = support
            field[_PLANE_INDEX["long_completion"], target, method] = completion
            field[_PLANE_INDEX["long_elapsed_ns"], target, method] = elapsed
            field[_PLANE_INDEX["long_work"], target, method] = work
        epoch = sum(
            int(field[_PLANE_INDEX["long_support"], target, method])
            for method in range(len(METHODS))
        )
        field[_PLANE_INDEX["context_epoch"], target, 0] = epoch
        for method in range(len(METHODS)):
            if int(field[_PLANE_INDEX["long_support"], target, method]) > 0:
                field[
                    _PLANE_INDEX["last_observed_epoch"], target, method
                ] = epoch
    return PolicyState(field)


def _bucket(value: int, *, cutoffs: Sequence[int]) -> int:
    for index, cutoff in enumerate(cutoffs):
        if value <= cutoff:
            return index
    return len(cutoffs)


def context_features(
    compiled: CompiledConstraintProblem, *, budget: int = 2000
) -> dict[str, Any]:
    """Encode fixed source structure and the declared execution-budget class.

    No source digest, signal/gate name, family label, or method answer enters
    the representation. Relabelings therefore share evidence, while runs with
    materially different ceilings cannot silently share completion statistics.
    """

    if not isinstance(compiled, CompiledConstraintProblem):
        raise PolicyError("context_features requires a compiled source")
    budget = _integer(budget, "budget", minimum=1)
    clauses = compiled.clauses
    variables = _integer(compiled.variables, "compiled variables", minimum=1)
    clause_count = len(clauses)
    max_width = max((len(row) for row in clauses), default=0)
    literal_count = sum(len(row) for row in clauses)
    unit_count = sum(len(row) == 1 for row in clauses)
    binary_count = sum(len(row) == 2 for row in clauses)
    work = compiled.payload.get("work", {})
    if not isinstance(work, Mapping):
        raise PolicyError("compiled work metadata is invalid")
    relation_count = _integer(work.get("relation_clauses", 0), "relation clause count")
    gate_count = _integer(work.get("gate_clauses", 0), "gate clause count")
    horizon = _integer(work.get("horizon", 0), "source horizon")
    native_relations = compiled.payload.get("native_relations", ())
    if not isinstance(native_relations, (list, tuple)):
        raise PolicyError("compiled native relation metadata is invalid")
    native_xor = int(any(isinstance(row, Mapping) and row.get("kind") == "xor" for row in native_relations))
    native_cardinality = int(any(isinstance(row, Mapping) and row.get("kind") == "cardinality" for row in native_relations))
    pinned_density_bucket = min(3, (unit_count * 4) // max(1, variables))
    detailed_values = (
        1 if compiled.payload.get("kind") == "transition" else 0,
        _bucket(variables, cutoffs=(1, 2, 4, 8, 16, 32, 64)),
        _bucket(clause_count, cutoffs=(0, 1, 2, 4, 8, 16, 32, 64, 128, 256)),
        _bucket(max_width, cutoffs=(0, 1, 2, 3, 4, 8, 16, 32)),
        _bucket(literal_count, cutoffs=(0, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)),
        _bucket(unit_count, cutoffs=(0, 1, 2, 4, 8, 16, 32, 64)),
        _bucket(binary_count, cutoffs=(0, 1, 2, 4, 8, 16, 32, 64, 128)),
        _bucket(relation_count, cutoffs=(0, 1, 2, 4, 8, 16, 32)),
        _bucket(gate_count, cutoffs=(0, 1, 2, 4, 8, 16, 32, 64)),
        _bucket(horizon, cutoffs=(0, 1, 2, 4, 8, 16, 32, 64)),
    )
    complexity_refinement = int(
        variables > 4 or clause_count > 8 or max_width > 3 or horizon > 2
    )
    budget_class = 1 + _bucket(budget, cutoffs=_BUDGET_CUTOFFS)
    feature_values = (
        *detailed_values,
        native_xor,
        native_cardinality,
        pinned_density_bucket,
        budget_class,
        complexity_refinement,
    )
    transition_shape = int(detailed_values[0])
    structural_key = (
        (
            (transition_shape * 2 + native_xor) * 2
            + native_cardinality
        )
        * 4
        + pinned_density_bucket
    ) * 2 + complexity_refinement
    key = structural_key * _BUDGET_CLASS_COUNT + budget_class
    return {
        "schema": "cassifi.computation-context.v3",
        "features": {name: int(value) for name, value in zip(_FEATURE_NAMES, feature_values)},
        "feature_vector": [int(value) for value in feature_values],
        "structural_context_key": int(structural_key),
        "budget_class": int(budget_class),
        "budget_cutoffs": list(_BUDGET_CUTOFFS),
        "context_key": int(key),
    }
def _gate_value(op: str, args: Sequence[int], value: Any = None) -> int:
    if op == "const":
        return _integer(value, "constant value", minimum=0, maximum=1)
    bits = tuple(_integer(item, "gate input", minimum=0, maximum=1) for item in args)
    if op == "buf":
        return bits[0]
    if op == "not":
        return 1 - bits[0]
    if op == "and":
        return int(all(bits))
    if op == "or":
        return int(any(bits))
    if op == "xor":
        return sum(bits) & 1
    if op == "nand":
        return int(not all(bits))
    if op == "nor":
        return int(not any(bits))
    if op == "xnor":
        return 1 - (sum(bits) & 1)
    if op == "mux":
        return bits[1] if bits[0] else bits[2]
    raise PolicyError("source evaluator encountered an unsupported gate")


def _source_clause_holds(clause: Any, values: Mapping[str, int], *, time: int | None = None) -> bool:
    if not isinstance(clause, (list, tuple)):
        raise PolicyError("source clause is malformed")
    for literal in clause:
        if not isinstance(literal, (list, tuple)) or len(literal) not in ((2, 3) if time is not None else (2,)):
            raise PolicyError("source literal is malformed")
        name = literal[0]
        polarity = literal[1]
        if not isinstance(name, str) or polarity not in (0, 1) or isinstance(polarity, bool):
            raise PolicyError("source literal is malformed")
        if time is None:
            key = name
        else:
            at = _integer(literal[2], "source clause time") if len(literal) == 3 else 0
            key = f"{name}@{at}"
        if key not in values:
            raise PolicyError("source clause references an unavailable signal")
        if values[key] == int(polarity):
            return True
    return False


def _source_holds(compiled: CompiledConstraintProblem, assignment: Sequence[int]) -> bool:
    """Evaluate the declared circuit/transition source independently of CNF rows."""

    source = compiled.payload.get("source")
    if not isinstance(source, Mapping):
        raise PolicyError("compiled source declaration is unavailable")
    witness = {
        label: (1 if assignment[identifier - 1] == 1 else 0)
        for label, identifier in compiled.witness_signals
    }
    kind = compiled.payload.get("kind")
    if kind == "circuit":
        values: dict[str, int] = dict(witness)
        gates = source.get("gates", [])
        if not isinstance(gates, (list, tuple)):
            raise PolicyError("circuit gate source is malformed")
        pending: list[dict[str, Any]] = [dict(row) for row in gates if isinstance(row, Mapping)]
        if len(pending) != len(gates):
            raise PolicyError("circuit gate source is malformed")
        while pending:
            progress = False
            for row in tuple(pending):
                args_value = row.get("args", ())
                if not isinstance(args_value, (list, tuple)):
                    raise PolicyError("circuit gate arguments are malformed")
                args = tuple(str(arg) for arg in args_value)
                if any(arg not in values for arg in args):
                    continue
                values[str(row["out"])] = _gate_value(
                    str(row["op"]),
                    [values[arg] for arg in args],
                    row.get("value"),
                )
                pending.remove(row)
                progress = True
            if not progress:
                raise PolicyError("circuit source evaluator cannot resolve gates")
        for name, bit in source.get("assertions", ()):
            if values.get(str(name)) != int(bit):
                return False
        for relation in source.get("relations", ()):
            args = [values[str(name)] for name in relation["args"]]
            if relation["kind"] == "xor" and (sum(args) & 1) != int(relation["rhs"]):
                return False
            if relation["kind"] == "cardinality" and not int(relation["min"]) <= sum(args) <= int(relation["max"]):
                return False
        return all(_source_clause_holds(clause, values) for clause in source.get("clauses", ()))
    if kind != "transition":
        raise PolicyError("compiled source kind is unsupported")
    state_names = tuple(str(name) for name in source.get("state", ()))
    input_names = tuple(str(name) for name in source.get("inputs", ()))
    horizon = _integer(source.get("horizon"), "source horizon")
    states: list[dict[str, int]] = [{} for _ in range(horizon + 1)]
    timeline: dict[str, int] = {}
    for name in state_names:
        label = f"{name}@0"
        if label not in witness:
            raise PolicyError("transition witness lacks an initial state")
        states[0][name] = witness[label]
        timeline[label] = witness[label]
    inputs: list[dict[str, int]] = []
    for at in range(horizon):
        row: dict[str, int] = {}
        for name in input_names:
            label = f"{name}@{at}"
            if label not in witness:
                raise PolicyError("transition witness lacks an input")
            row[name] = witness[label]
            timeline[label] = witness[label]
        inputs.append(row)
    for name, bit in source.get("initial", ()):
        if states[0].get(str(name)) != int(bit):
            return False
    for at in range(horizon):
        values: dict[str, int] = {**states[at], **inputs[at]}
        for row in source.get("gates", ()):
            if not isinstance(row, Mapping):
                raise PolicyError("transition gate source is malformed")
            args_value = row.get("args", ())
            if not isinstance(args_value, (list, tuple)):
                raise PolicyError("transition gate arguments are malformed")
            args = tuple(str(arg) for arg in args_value)
            if any(arg not in values for arg in args):
                raise PolicyError("transition source gate references an unavailable signal")
            values[str(row["out"])] = _gate_value(
                str(row["op"]),
                [values[arg] for arg in args],
                row.get("value"),
            )
        for name, bit in values.items():
            timeline[f"{name}@{at}"] = int(bit)
        for target, origin in source.get("next_state", ()):
            if str(origin) not in values:
                raise PolicyError("transition next-state source is unavailable")
            states[at + 1][str(target)] = values[str(origin)]
        for relation in source.get("relations", ()):
            args = [values[str(name)] for name in relation["args"]]
            if relation["kind"] == "xor" and (sum(args) & 1) != int(relation["rhs"]):
                return False
            if relation["kind"] == "cardinality" and not int(relation["min"]) <= sum(args) <= int(relation["max"]):
                return False
        for at_assert, name, bit in source.get("input_assertions", ()):
            if int(at_assert) == at and inputs[at].get(str(name)) != int(bit):
                return False
    for name, bit in states[-1].items():
        timeline[f"{name}@{horizon}"] = int(bit)
    for name, bit in source.get("final", ()):
        if states[horizon].get(str(name)) != int(bit):
            return False
    return all(_source_clause_holds(clause, timeline, time=0) for clause in source.get("clauses", ()))


def _ensure_compiled(source: CompiledConstraintProblem | Mapping[str, Any]) -> CompiledConstraintProblem:
    if isinstance(source, CompiledConstraintProblem):
        return source
    if not isinstance(source, Mapping):
        raise PolicyError("source must be a compiled problem or declared source mapping")
    if source.get("schema") == PROBLEM_SCHEMA:
        expected = source.get("sha256")
        if not isinstance(expected, str):
            raise PolicyError("compiled source mapping lacks sha256")
        payload = {key: source[key] for key in source if key != "sha256"}
        try:
            return CompiledConstraintProblem(payload, expected)
        except (ConstraintFieldError, TypeError, ValueError) as exc:
            raise PolicyError("compiled source mapping is invalid") from exc
    kind = source.get("kind")
    raw: Mapping[str, Any] = source
    if "source" in source:
        declared = source.get("source")
        if not isinstance(declared, Mapping):
            raise PolicyError("source envelope payload must be a mapping")
        raw_payload = dict(declared)
        raw_kind = raw_payload.get("kind", kind)
        if raw_kind != kind:
            raise PolicyError("source envelope kind mismatch")
        raw_payload["kind"] = kind
        raw = raw_payload
    try:
        if kind == "circuit":
            return compile_circuit(raw)
        if kind == "transition":
            return compile_transition_problem(raw)
    except (ConstraintFieldError, TypeError, KeyError, ValueError) as exc:
        raise PolicyError("declared source failed exact compilation") from exc
    raise PolicyError("source kind must be circuit or transition")


def compile_source(source: CompiledConstraintProblem | Mapping[str, Any]) -> CompiledConstraintProblem:
    """Compile a native declared source or validate a serialized compiled payload."""

    return _ensure_compiled(source)


def _profile_for(
    compiled: CompiledConstraintProblem,
    method: str,
    *,
    hybrid_budget: int,
    search_budget: int,
    max_field_bytes: int,
) -> ConstraintFieldProfile:
    if method not in METHODS:
        raise PolicyError(f"unknown computation method {method!r}")
    algebraic = method.startswith("algebraic")
    controller = method.endswith("-controller")
    if algebraic:
        arity = 2 if method.startswith("algebraic-2") else 1
        max_augmentations = min(64, max(0, 262_144 - len(compiled.clauses)))
        max_hybrid_lines = max(1, min(4096, max(len(compiled.clauses), len(compiled.clauses) * 4 + 16)))
    else:
        arity = 1
        max_augmentations = 0
        max_hybrid_lines = 1
    return ConstraintFieldProfile(
        max_variables=compiled.variables,
        max_clauses=max(1, len(compiled.clauses) + max_augmentations),
        max_transitions=max(1, search_budget),
        max_learned_clauses=max(1, min(128, max(16, compiled.variables * 2))),
        max_proof_bytes=max(4096, min(262_144, max(4096, len(compiled.clauses) * 256))),
        max_field_bytes=max_field_bytes,
        mode="algebraic" if algebraic else "conflict",
        controller=controller,
        controller_size=max(1, min(64, compiled.variables)),
        max_hybrid_lines=max_hybrid_lines,
        max_hybrid_transitions=max(1, hybrid_budget),
        max_parity_width=min(8, max(3, compiled.variables)),
        max_resolution_inferences=max(1, min(2048, max(1, hybrid_budget))),
        max_augmentations=max_augmentations,
        max_augmentation_arity=arity,
    )


def _work_snapshot(field: ConstraintField, state: Any) -> dict[str, Any]:
    """Read bounded counters without materializing solver evidence."""

    try:
        work: dict[str, Any] = {
            "compile": dict(state.compiled.payload["work"]),
            "prepass": field._prepass_work(state),
            "journal_bytes": len(state.journal),
            "controller": {
                "ticks": int(state.controller_ticks),
                "selections": int(state.controller_selections),
            },
        }
        if state.hybrid is not None:
            hybrid = field._hybrid_field(state).inspect(state.hybrid)
            work["hybrid"] = {
                "status": hybrid["status"],
                "proof_lines": hybrid["proof_lines"],
                "resource_ledger": dict(hybrid["resource_ledger"]),
            }
        if state.backend is not None:
            search = field._backend_field(state).inspect(state.backend)
            work["search"] = dict(search["resource_ledger"])
        return work
    except PolicyError:
        raise
    except Exception as exc:
        raise PolicyError("solver work ledger is unavailable") from exc


def _counter_from_work(work: Mapping[str, Any], path: Sequence[str]) -> int:
    value: Any = work
    for key in path:
        if not isinstance(value, Mapping):
            return 0
        value = value.get(key)
    return _integer(value if value is not None else 0, ".".join(path))


def _usage(work: Mapping[str, Any]) -> tuple[int, int, int]:
    hybrid = _counter_from_work(work, ("hybrid", "resource_ledger", "transitions"))
    search = _counter_from_work(work, ("search", "transitions"))
    controller = _counter_from_work(work, ("controller", "ticks"))
    return hybrid, search, controller


def _mark_exhausted(state: Any, reason: str = "transition-budget") -> Any:
    if getattr(state, "status", None) != "running":
        return state
    return replace(state, status="exhausted", reason=reason)


def _rate_compare(
    numerator_left: int,
    denominator_left: int,
    numerator_right: int,
    denominator_right: int,
) -> int:
    if denominator_left == 0 or denominator_right == 0:
        return (denominator_left > 0) - (denominator_right > 0)
    left = numerator_left * denominator_right
    right = numerator_right * denominator_left
    return (left > right) - (left < right)


def _selection_better(field: np.ndarray, context: int, left: int, right: int) -> bool:
    """Compare two methods using exact bounded sample evidence."""

    long_s_l = int(field[_PLANE_INDEX["long_support"], context, left])
    long_s_r = int(field[_PLANE_INDEX["long_support"], context, right])
    long_c_l = int(field[_PLANE_INDEX["long_completion"], context, left])
    long_c_r = int(field[_PLANE_INDEX["long_completion"], context, right])
    recent_s_l = int(field[_PLANE_INDEX["recent_support"], context, left])
    recent_s_r = int(field[_PLANE_INDEX["recent_support"], context, right])
    recent_c_l = int(field[_PLANE_INDEX["recent_completion"], context, left])
    recent_c_r = int(field[_PLANE_INDEX["recent_completion"], context, right])
    # One observed success is withheld from each rate as a deterministic
    # finite-sample penalty. It is a conservative score, not a probability.
    for completed_left, support_left, completed_right, support_right in (
        (recent_c_l, recent_s_l, recent_c_r, recent_s_r),
        (long_c_l, long_s_l, long_c_r, long_s_r),
    ):
        comparison = _rate_compare(
            max(0, completed_left - 1),
            support_left,
            max(0, completed_right - 1),
            support_right,
        )
        if comparison:
            return comparison > 0
        comparison = _rate_compare(
            completed_left, support_left, completed_right, support_right
        )
        if comparison:
            return comparison > 0
    for elapsed_plane, support_left, support_right in (
        ("recent_elapsed_ns", recent_s_l, recent_s_r),
        ("long_elapsed_ns", long_s_l, long_s_r),
    ):
        if support_left and support_right:
            elapsed_left = int(field[_PLANE_INDEX[elapsed_plane], context, left])
            elapsed_right = int(field[_PLANE_INDEX[elapsed_plane], context, right])
            comparison = _rate_compare(
                elapsed_right, support_right, elapsed_left, support_left
            )
            if comparison:
                return comparison > 0
    if long_s_l and long_s_r:
        work_left = int(field[_PLANE_INDEX["long_work"], context, left])
        work_right = int(field[_PLANE_INDEX["long_work"], context, right])
        comparison = _rate_compare(work_right, long_s_r, work_left, long_s_l)
        if comparison:
            return comparison > 0
    if recent_s_l != recent_s_r:
        return recent_s_l > recent_s_r
    if long_s_l != long_s_r:
        return long_s_l > long_s_r
    return left < right


def _selection_index(field: np.ndarray, context: int, candidates: Sequence[int]) -> int:
    selected = int(candidates[0])
    for candidate in candidates[1:]:
        candidate = int(candidate)
        if _selection_better(field, context, candidate, selected):
            selected = candidate
    return selected


def _evidence_rows(field: np.ndarray, context: int) -> list[dict[str, Any]]:
    rows = []
    for method_index, method in enumerate(METHODS):
        rows.append(
            {
                "method": method,
                **{
                    plane: int(
                        field[_PLANE_INDEX[plane], context, method_index]
                    )
                    for plane in _EVIDENCE_PLANES
                },
                "last_observed_epoch": int(
                    field[
                        _PLANE_INDEX["last_observed_epoch"],
                        context,
                        method_index,
                    ]
                ),
            }
        )
    return rows


def _structural_incumbent(compiled: CompiledConstraintProblem) -> int:
    """Return the declared nonlearned method for a zero-evidence context."""

    work = compiled.payload.get("work", {})
    if not isinstance(work, Mapping):
        raise PolicyError("compiled work metadata is invalid")
    relations = compiled.payload.get("native_relations", ())
    if not isinstance(relations, (list, tuple)):
        raise PolicyError("compiled native relation metadata is invalid")
    if relations:
        method = (
            "algebraic-1-controller"
            if compiled.variables >= 12
            else "algebraic-1"
        )
    elif (
        compiled.payload.get("kind") == "transition"
        or _integer(work.get("gates", 0), "compiled gate count") >= 7
    ):
        method = "conflict-controller"
    else:
        method = "conflict"
    return METHODS.index(method)


def _next_unseen_epoch(epoch: int) -> int:
    if epoch <= 1:
        return 1
    remainder = epoch % _EXPLORATION_INTERVAL
    return epoch if remainder == 0 else epoch + _EXPLORATION_INTERVAL - remainder


def _support_vector(field: np.ndarray, context: int) -> list[int]:
    return [
        int(field[_PLANE_INDEX["long_support"], context, index])
        for index in range(len(METHODS))
    ]


def _related_evidence_keys(context_value: Mapping[str, Any]) -> tuple[int, ...]:
    """Return same-budget sibling then unbudgeted refined priors."""

    structural = int(context_value["structural_context_key"])
    budget_class = int(context_value["budget_class"])
    sibling = structural ^ 1
    keys = (
        sibling * _BUDGET_CLASS_COUNT + budget_class,
        structural * _BUDGET_CLASS_COUNT,
        sibling * _BUDGET_CLASS_COUNT,
    )
    if any(key < 0 or key >= _CONTEXT_COUNT for key in keys):
        raise PolicyError("refined policy context is out of bounds")
    return keys

def _first_supported_context(
    field: np.ndarray,
    contexts: Sequence[int],
    candidates: Sequence[int],
) -> int | None:
    for context in contexts:
        if any(
            int(field[_PLANE_INDEX["long_support"], context, candidate]) > 0
            for candidate in candidates
        ):
            return int(context)
    return None


def select_method(
    policy: PolicyState,
    compiled: CompiledConstraintProblem,
    *,
    budget: int = 2000,
    explore: bool = True,
) -> tuple[str, dict[str, Any]]:
    """Select with a structural incumbent and field-clocked challenger quota."""

    if not isinstance(policy, PolicyState):
        raise PolicyError("policy must be PolicyState")
    if not isinstance(compiled, CompiledConstraintProblem):
        raise PolicyError("select_method requires a compiled source")
    if not isinstance(explore, bool):
        raise PolicyError("explore must be boolean")
    budget = _integer(budget, "budget", minimum=1)
    working = migrate_policy(policy)
    context_value = context_features(compiled, budget=budget)
    context_key = int(context_value["context_key"])
    values = working._field
    supports = _support_vector(values, context_key)
    total_support = sum(supports)
    epoch = int(
        values[_PLANE_INDEX["context_epoch"], context_key, 0]
    )
    last_observed = [
        int(
            values[
                _PLANE_INDEX["last_observed_epoch"], context_key, index
            ]
        )
        for index in range(len(METHODS))
    ]
    unseen = [index for index, support in enumerate(supports) if support == 0]
    incumbent = _structural_incumbent(compiled)
    evidence_key = context_key
    comparisons = 0
    exploration_reason: str | None = None

    related_keys = _related_evidence_keys(context_value)
    related_key = _first_supported_context(
        values, related_keys, tuple(range(len(METHODS)))
    )
    if total_support == 0 and related_key is not None:
        evidence_key = related_key
        related_supports = _support_vector(values, evidence_key)
        observed = tuple(
            index
            for index, support in enumerate(related_supports)
            if support > 0
        )
        selected = _selection_index(values, evidence_key, observed)
        comparisons = max(0, len(observed) - 1)
        phase = (
            "refined-sibling-prior"
            if evidence_key == related_keys[0]
            else "structural-prior"
        )
        exploration_reason = "evidence-driven-context-refinement"
    elif total_support == 0:
        selected = incumbent
        phase = "cold-start"
        exploration_reason = "declared-structural-incumbent"
    elif (
        explore
        and unseen
        and epoch == _next_unseen_epoch(epoch)
    ):
        exploration_key = _first_supported_context(
            values, related_keys, unseen
        )
        if exploration_key is not None:
            supported_unseen = tuple(
                candidate
                for candidate in unseen
                if int(
                    values[
                        _PLANE_INDEX["long_support"],
                        exploration_key,
                        candidate,
                    ]
                )
                > 0
            )
            selected = _selection_index(
                values, exploration_key, supported_unseen
            )
            evidence_key = exploration_key
            comparisons = max(0, len(supported_unseen) - 1)
            exploration_reason = "related-evidence-completion-cost"
        else:
            challenger_order = tuple(
                (incumbent + offset) % len(METHODS)
                for offset in range(1, len(METHODS) + 1)
            )
            selected = next(
                candidate
                for candidate in challenger_order
                if candidate in unseen
            )
            exploration_reason = "scheduled-unseen-challenger"
        phase = "explore"
    elif (
        explore
        and not unseen
        and epoch > 0
        and epoch % _REEVALUATION_PERIOD == 0
    ):
        selected = min(
            range(len(METHODS)),
            key=lambda index: (
                last_observed[index],
                supports[index],
                index,
            ),
        )
        phase = "reevaluate"
        exploration_reason = "stale-method-reevaluation"
    else:
        observed = tuple(
            index for index, support in enumerate(supports) if support > 0
        )
        selected = _selection_index(values, context_key, observed)
        comparisons = max(0, len(observed) - 1)
        phase = "empirical"

    evidence = _evidence_rows(values, evidence_key)
    ages = [
        None if support == 0 else epoch - last_observed[index]
        for index, support in enumerate(supports)
    ]
    return METHODS[selected], {
        "schema": "cassifi.computation-selection.v4",
        "method": METHODS[selected],
        "context": context_value,
        "phase": phase,
        "exploration_reason": exploration_reason,
        "observation_context_key": context_key,
        "evidence_context_key": evidence_key,
        "structural_incumbent": METHODS[incumbent],
        "context_epoch": epoch,
        "exploration_interval": _EXPLORATION_INTERVAL,
        "exploration_complete": not unseen,
        "unseen_methods": [METHODS[index] for index in unseen],
        "next_unseen_exploration_epoch": (
            None if not unseen else _next_unseen_epoch(epoch)
        ),
        "reevaluation_period": _REEVALUATION_PERIOD,
        "recent_decay_period": _RECENT_DECAY_PERIOD,
        "observed_support": supports,
        "checked_completion": [
            int(
                values[
                    _PLANE_INDEX["long_completion"], context_key, index
                ]
            )
            for index in range(len(METHODS))
        ],
        "last_observed_epoch": last_observed,
        "method_age": ages,
        "evidence": evidence,
        "work": {
            "field_cells_read": len(_PLANES)
            * len(METHODS)
            * (2 if evidence_key != context_key else 1),
            "feature_cells_read": len(context_value["feature_vector"]),
            "candidate_comparisons": comparisons,
            "operations": 1,
        },
    }


def inspect_policy(
    policy: PolicyState,
    source: CompiledConstraintProblem | Mapping[str, Any],
    *,
    budget: int = 2000,
    explore: bool = True,
) -> dict[str, Any]:
    """Project a read-only explanation from one policy context."""

    compiled = _ensure_compiled(source)
    working = migrate_policy(policy)
    selected, selection = select_method(
        working, compiled, budget=budget, explore=explore
    )
    return {
        "schema": "cassifi.computation-policy-inspection.v1",
        "policy_schema": working._schema,
        "policy_state_sha256": working.state_sha256,
        "policy_field_bytes": working.nbytes,
        "selected_method": selected,
        "selection": selection,
        "completion_first": True,
        "adaptive_state": "field-only",
    }


def _audit_hybrid(compiled: CompiledConstraintProblem, proof: Mapping[str, Any]) -> dict[str, Any]:
    try:
        from verify_hybrid_inference import audit_proof

        checked = audit_proof(compiled.clauses, proof, variables=compiled.variables)
    except Exception as exc:
        raise PolicyError("independent hybrid proof audit failed") from exc
    return {"checked": True, "auditor": "verify_hybrid_inference.audit_proof", **dict(checked)}




def _hybrid_fact_candidates(line: Mapping[str, Any]) -> tuple[tuple[int, ...], ...]:
    kind = line.get("kind")
    if kind == "clause":
        literals = tuple(_integer(value, "hybrid clause literal") for value in line.get("literals", ()))
        return (literals,) if 0 < len(literals) <= 2 else ()
    if kind == "xor":
        variables = tuple(_integer(value, "hybrid parity variable", minimum=1) for value in line.get("variables", ()))
        rhs = _integer(line.get("rhs"), "hybrid parity rhs", maximum=1)
        if len(variables) == 1:
            return ((variables[0] if rhs else -variables[0],),)
        if len(variables) == 2:
            first, second = variables
            return (
                ((first, second), (-first, -second))
                if rhs
                else ((first, -second), (-first, second))
            )
        return ()
    if kind != "pb":
        return ()
    raw_terms = line.get("terms", ())
    if not isinstance(raw_terms, (list, tuple)):
        return ()
    terms = tuple(
        (_integer(row[0], "hybrid PB variable", minimum=1), _integer(row[1], "hybrid PB coefficient"))
        for row in raw_terms
        if isinstance(row, (list, tuple)) and len(row) == 2
    )
    if len(terms) != len(raw_terms):
        return ()
    rhs = _integer(line.get("rhs"), "hybrid PB rhs", minimum=-_SAFE_INTEGER)
    nonzero = tuple((variable, coefficient) for variable, coefficient in terms if coefficient)
    if len(nonzero) == 1:
        variable, coefficient = nonzero[0]
        if coefficient > 0 and rhs < coefficient:
            return ((-variable,),)
        if coefficient < 0 and rhs < 0:
            return ((variable,),)
        return ()
    if len(nonzero) != 2:
        return ()
    (first, first_coefficient), (second, second_coefficient) = nonzero
    candidates: list[tuple[int, ...]] = []
    for first_bit in (0, 1):
        for second_bit in (0, 1):
            if first_coefficient * first_bit + second_coefficient * second_bit > rhs:
                candidates.append(
                    (
                        first if first_bit == 0 else -first,
                        second if second_bit == 0 else -second,
                    )
                )
    return tuple(candidates)


def _audit_augmentations(
    compiled: CompiledConstraintProblem,
    result: Mapping[str, Any],
    backend_clauses: Sequence[Sequence[int]],
) -> None:
    original_count = len(compiled.clauses)
    appended = tuple(tuple(row) for row in backend_clauses[original_count:])
    rows = result.get("augmentations", [])
    if not isinstance(rows, list):
        raise PolicyError("augmentation evidence is malformed")
    declared: list[tuple[int, ...]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise PolicyError("augmentation journal row is malformed")
        clause = row.get("clause")
        if not isinstance(clause, list):
            raise PolicyError("augmentation journal clause is malformed")
        declared.append(tuple(clause))
    if tuple(declared) != appended:
        raise PolicyError("backend augmentations do not match their journal evidence")
    if not appended:
        return
    hybrid = result.get("hybrid_proof")
    if not isinstance(hybrid, Mapping):
        raise PolicyError("backend augmentations lack a hybrid derivation")
    _audit_hybrid(compiled, hybrid)
    lines = hybrid.get("lines")
    if not isinstance(lines, list):
        raise PolicyError("hybrid derivation lines are malformed")
    for row, clause in zip(rows, appended):
        line_id = row.get("line_id")
        via = row.get("via")
        if not isinstance(line_id, int) or not isinstance(via, str) or not 1 <= line_id <= len(lines):
            raise PolicyError("augmentation provenance is malformed")
        line = lines[line_id - 1]
        if not isinstance(line, Mapping):
            raise PolicyError("augmentation provenance line is malformed")
        if via not in {"clause", "xor", "pb"}:
            raise PolicyError("augmentation provenance rule is unsupported")
        candidates = _hybrid_fact_candidates(line)
        if tuple(clause) not in candidates:
            raise PolicyError("augmentation is not a consequence of its hybrid line")

def _audit_clause(
    compiled_clauses: Sequence[Sequence[int]],
    result: Mapping[str, Any],
    *,
    variables: int,
) -> dict[str, Any]:
    try:
        from verify_p_vs_np_clause_field_probe import audit_proof

        proof = result.get("resolution_proof")
        if not isinstance(proof, Mapping):
            raise PolicyError("resolution proof is missing")
        work = result.get("work", {})
        search = work.get("search", {}) if isinstance(work, Mapping) else {}
        expected_conflicts = (
            _integer(search.get("conflicts", 0), "proof conflict count")
            if isinstance(search, Mapping)
            else 0
        )
        profile = result.get("profile", {})
        max_learned = (
            _integer(profile.get("max_learned_clauses", 0), "proof learned-clause bound")
            if isinstance(profile, Mapping)
            else 0
        )
        checked = audit_proof(
            compiled_clauses,
            result.get("learned_clauses", []),
            proof,
            variables=variables,
            status="unsat",
            expected_conflicts=expected_conflicts,
            max_learned_clauses=max_learned,
        )
    except PolicyError:
        raise
    except Exception as exc:
        raise PolicyError("independent clause proof audit failed") from exc
    return {
        "checked": True,
        "auditor": "verify_p_vs_np_clause_field_probe.audit_proof",
        **dict(checked),
    }


def audit_result(compiled: CompiledConstraintProblem, result: Mapping[str, Any]) -> dict[str, Any]:
    """Independently validate result evidence against the compiled source."""

    if not isinstance(compiled, CompiledConstraintProblem) or not isinstance(result, Mapping):
        raise PolicyError("audit_result requires a compiled source and result mapping")
    if result.get("schema") != "cassifi.constraint-result.v1":
        raise PolicyError("constraint result schema mismatch")
    compiled_value = result.get("compiled")
    if not isinstance(compiled_value, Mapping) or compiled_value.get("schema") != PROBLEM_SCHEMA:
        raise PolicyError("result is not bound to the original compiled source")
    # The descriptor travels through JSON-normalised state, so tuples and lists
    # of the same content are equivalent transports.  Bind by the canonical
    # payload digest, which is invariant under that transport and still rejects
    # any content, shape-independent change.
    try:
        bound = _ensure_compiled(compiled_value)
    except PolicyError as exc:
        raise PolicyError("result is not bound to the original compiled source") from exc
    if bound.sha256 != compiled.sha256:
        raise PolicyError("result is not bound to the original compiled source")
    status = result.get("status")
    if status not in ("sat", "unsat", "exhausted"):
        raise PolicyError("result status is not terminal")
    if status == "sat":
        assignment = result.get("assignment")
        witness = result.get("witness")
        if not isinstance(assignment, list) or len(assignment) != compiled.variables:
            raise PolicyError("SAT assignment is malformed")
        if any(value not in (-1, 1) or isinstance(value, bool) for value in assignment):
            raise PolicyError("SAT assignment contains an invalid value")
        if not all(
            any(
                assignment[abs(literal) - 1] == (1 if literal > 0 else -1)
                for literal in clause
            )
            for clause in compiled.clauses
        ):
            raise PolicyError("SAT assignment does not satisfy original source")
        try:
            source_holds = _source_holds(compiled, assignment)
        except PolicyError as exc:
            raise PolicyError("original source evaluation failed") from exc
        if not source_holds:
            raise PolicyError("SAT witness does not satisfy the declared source")
        expected_witness = {
            label: (1 if assignment[identifier - 1] == 1 else 0)
            for label, identifier in compiled.witness_signals
        }
        if witness != expected_witness:
            raise PolicyError("SAT witness is not bound to the original source")
        return {
            "checked": True,
            "status": "sat",
            "auditor": "original-source-evaluator",
            "witness_variables": len(expected_witness),
        }
    if result.get("witness") is not None:
        raise PolicyError("non-SAT result carries a witness")
    # The backend retains its diagnostic assignment even after a refutation;
    # only the SAT witness is a claimed model of the source.
    diagnostic = result.get("assignment")
    if diagnostic is not None and (
        not isinstance(diagnostic, list) or len(diagnostic) != compiled.variables
        or any(type(value) is not int or value not in (-1, 0, 1) for value in diagnostic)
    ):
        raise PolicyError("non-SAT diagnostic assignment is malformed")
    if status == "exhausted":
        if result.get("witness") is not None or result.get("resolution_proof") is not None:
            raise PolicyError("exhausted result carries decided evidence")
        hybrid_evidence = result.get("hybrid_proof")
        if hybrid_evidence is not None:
            if not isinstance(hybrid_evidence, Mapping) or hybrid_evidence.get("status") not in ("running", "exhausted") or hybrid_evidence.get("root_line") is not None:
                raise PolicyError("exhausted result carries a proof")
        return {"checked": True, "status": "exhausted", "auditor": "exhaustion-boundary"}
    hybrid = result.get("hybrid_proof")
    if isinstance(hybrid, Mapping) and hybrid.get("status") == "unsat":
        checked = _audit_hybrid(compiled, hybrid)
        if checked.get("status") != "unsat":
            raise PolicyError("hybrid audit did not establish UNSAT")
        return {"status": "unsat", **checked}
    backend_value = result.get("backend_clauses")
    if not isinstance(backend_value, list):
        raise PolicyError("UNSAT result lacks backend clause binding")
    try:
        backend_clauses = [tuple(row) for row in backend_value]
    except (TypeError, ValueError) as exc:
        raise PolicyError("UNSAT backend clauses are malformed") from exc
    if tuple(backend_clauses[: len(compiled.clauses)]) != compiled.clauses:
        raise PolicyError("UNSAT backend clauses do not preserve original source")
    _audit_augmentations(compiled, result, backend_clauses)
    return {
        "status": "unsat",
        **_audit_clause(backend_clauses, result, variables=compiled.variables),
    }
def _compress_window(
    field: np.ndarray,
    context: int,
    method_index: int,
    planes: Sequence[str],
) -> None:
    for plane in planes:
        coordinate = _PLANE_INDEX[plane]
        field[coordinate, context, method_index] = (
            int(field[coordinate, context, method_index]) // 2
        )
    prefix = "long" if "long_support" in planes else "recent"
    support_name = f"{prefix}_support"
    support = int(
        field[_PLANE_INDEX[support_name], context, method_index]
    )
    completion_name = f"{prefix}_completion"
    if completion_name in planes:
        field[
            _PLANE_INDEX[completion_name], context, method_index
        ] = min(
            support,
            int(
                field[
                    _PLANE_INDEX[completion_name],
                    context,
                    method_index,
                ]
            ),
        )
    elapsed_name = f"{prefix}_elapsed_ns"
    if elapsed_name in planes:
        elapsed = int(
            field[_PLANE_INDEX[elapsed_name], context, method_index]
        )
        field[_PLANE_INDEX[elapsed_name], context, method_index] = (
            0
            if support == 0
            else min(
                max(support, elapsed),
                support * _OBSERVED_ELAPSED_CAP_NS,
            )
        )
    if prefix == "long" and "long_work" in planes:
        retained_work = int(
            field[_PLANE_INDEX["long_work"], context, method_index]
        )
        field[_PLANE_INDEX["long_work"], context, method_index] = (
            0
            if support == 0
            else min(retained_work, support * _OBSERVED_WORK_CAP)
        )


def _record_observation(
    policy: PolicyState,
    context: int,
    method_index: int,
    *,
    elapsed_ns: int,
    work: int,
    status: str,
) -> tuple[PolicyState, dict[str, Any]]:
    if policy.is_legacy:
        raise PolicyError("recording requires a migrated policy")
    context = _integer(
        context, "context", maximum=_CONTEXT_COUNT - 1
    )
    method_index = _integer(
        method_index, "method_index", maximum=len(METHODS) - 1
    )
    elapsed_ns = _integer(elapsed_ns, "elapsed_ns")
    work = _integer(work, "work")
    if status not in ("sat", "unsat", "exhausted"):
        raise PolicyError("cannot record nonterminal observation")
    retained_elapsed = max(
        1, min(elapsed_ns, _OBSERVED_ELAPSED_CAP_NS)
    )
    retained_work = min(work, _OBSERVED_WORK_CAP)
    completed = int(status in ("sat", "unsat"))
    field = policy._field.copy()
    epoch_coordinate = _PLANE_INDEX["context_epoch"]
    last_coordinate = _PLANE_INDEX["last_observed_epoch"]
    epoch_before = int(field[epoch_coordinate, context, 0])
    epoch_compressed = epoch_before >= _EPOCH_LIMIT
    if epoch_compressed:
        field[epoch_coordinate, context, 0] = epoch_before // 2
        for candidate in range(len(METHODS)):
            field[last_coordinate, context, candidate] = (
                int(field[last_coordinate, context, candidate]) // 2
            )
    epoch_base = int(field[epoch_coordinate, context, 0])
    epoch_after = epoch_base + 1
    synchronized_recent_decay = (
        epoch_after % _RECENT_DECAY_PERIOD == 0
        or any(
            int(
                field[
                    _PLANE_INDEX["recent_support"],
                    context,
                    candidate,
                ]
            )
            >= _RECENT_LIMIT
            for candidate in range(len(METHODS))
        )
    )
    if synchronized_recent_decay:
        for candidate in range(len(METHODS)):
            _compress_window(
                field,
                context,
                candidate,
                (
                    "recent_support",
                    "recent_completion",
                    "recent_elapsed_ns",
                ),
            )
    long_decayed = (
        int(
            field[
                _PLANE_INDEX["long_support"], context, method_index
            ]
        )
        >= _LONG_LIMIT
    )
    if long_decayed:
        _compress_window(
            field,
            context,
            method_index,
            (
                "long_support",
                "long_completion",
                "long_elapsed_ns",
                "long_work",
            ),
        )
    before = {
        plane: int(
            field[_PLANE_INDEX[plane], context, method_index]
        )
        for plane in _EVIDENCE_PLANES
    }
    before["last_observed_epoch"] = int(
        field[last_coordinate, context, method_index]
    )
    increments = {
        "long_support": 1,
        "long_completion": completed,
        "long_elapsed_ns": retained_elapsed,
        "long_work": retained_work,
        "recent_support": 1,
        "recent_completion": completed,
        "recent_elapsed_ns": retained_elapsed,
    }
    for plane, increment in increments.items():
        coordinate = _PLANE_INDEX[plane]
        field[coordinate, context, method_index] = _safe_add(
            int(field[coordinate, context, method_index]),
            increment,
            plane,
        )
    field[epoch_coordinate, context, 0] = epoch_after
    field[last_coordinate, context, method_index] = epoch_after
    next_policy = PolicyState(field)
    after = {
        plane: int(
            next_policy._field[
                _PLANE_INDEX[plane], context, method_index
            ]
        )
        for plane in _EVIDENCE_PLANES
    }
    after["last_observed_epoch"] = epoch_after
    return next_policy, {
        "schema": "cassifi.computation-observation.v3",
        "context_key": context,
        "method": METHODS[method_index],
        "status": status,
        "elapsed_ns_observed": elapsed_ns,
        "elapsed_ns_retained": retained_elapsed,
        "work_observed": work,
        "work_retained": retained_work,
        "elapsed_clipped": elapsed_ns != retained_elapsed,
        "work_clipped": work != retained_work,
        "long_decayed": bool(long_decayed),
        "recent_synchronized_decay": bool(
            synchronized_recent_decay
        ),
        "recent_decay_period": _RECENT_DECAY_PERIOD,
        "context_epoch_before": epoch_before,
        "context_epoch_compressed": bool(epoch_compressed),
        "context_epoch_after": epoch_after,
        "before": before,
        "increments": increments,
        "after": after,
    }


def _flatten_ledger(work: Mapping[str, Any], *, selector: int, hybrid: int, search: int, controller: int) -> dict[str, Any]:
    ledger: dict[str, Any] = {
        "selector_operations": int(selector),
        "hybrid_transitions": int(hybrid),
        "search_transitions": int(search),
        "backend_transitions": int(search),
        "controller_ticks": int(controller),
        "transitions": int(hybrid + search),
    }
    for key in ("compile", "prepass", "hybrid", "search", "controller"):
        value = work.get(key)
        if value is not None:
            ledger[key] = value
    for key in ("journal_bytes", "augmentations"):
        if key in work:
            ledger[key] = _integer(work[key], key)
    return ledger


def solve_and_learn(
    policy: PolicyState,
    source: CompiledConstraintProblem | Mapping[str, Any],
    *,
    budget: int = 2000,
    learn: bool = True,
    method: str | None = None,
    max_field_bytes: int = 134_217_728,
) -> tuple[PolicyState, dict[str, Any]]:
    """Execute one exact portfolio member under one shared bounded budget."""

    started = time.perf_counter_ns()
    if not isinstance(policy, PolicyState):
        raise PolicyError("policy must be PolicyState")
    budget = _integer(budget, "budget", minimum=1)
    max_field_bytes = _integer(max_field_bytes, "max_field_bytes", minimum=1)
    if not isinstance(learn, bool):
        raise PolicyError("learn must be boolean")
    compiled = _ensure_compiled(source)
    working_policy = migrate_policy(policy)
    migrated = working_policy is not policy
    context = context_features(compiled, budget=budget)
    if method is not None:
        if not isinstance(method, str) or method not in METHODS:
            raise PolicyError(f"unknown computation method {method!r}")
        selected = method
        context_key = int(context["context_key"])
        values = working_policy._field
        supports = [
            int(
                values[
                    _PLANE_INDEX["long_support"], context_key, index
                ]
            )
            for index in range(len(METHODS))
        ]
        epoch = int(
            values[_PLANE_INDEX["context_epoch"], context_key, 0]
        )
        unseen = [
            METHODS[index]
            for index, support in enumerate(supports)
            if support == 0
        ]
        selection = {
            "schema": "cassifi.computation-selection.v4",
            "method": selected,
            "context": context,
            "phase": "fixed",
            "exploration_reason": None,
            "observation_context_key": context_key,
            "evidence_context_key": context_key,
            "structural_incumbent": METHODS[
                _structural_incumbent(compiled)
            ],
            "context_epoch": epoch,
            "exploration_interval": _EXPLORATION_INTERVAL,
            "exploration_complete": not unseen,
            "unseen_methods": unseen,
            "next_unseen_exploration_epoch": (
                None if not unseen else _next_unseen_epoch(epoch)
            ),
            "reevaluation_period": _REEVALUATION_PERIOD,
            "recent_decay_period": _RECENT_DECAY_PERIOD,
            "observed_support": supports,
            "checked_completion": [
                int(
                    values[
                        _PLANE_INDEX["long_completion"],
                        context_key,
                        index,
                    ]
                )
                for index in range(len(METHODS))
            ],
            "last_observed_epoch": [
                int(
                    values[
                        _PLANE_INDEX["last_observed_epoch"],
                        context_key,
                        index,
                    ]
                )
                for index in range(len(METHODS))
            ],
            "method_age": [
                None
                if support == 0
                else epoch
                - int(
                    values[
                        _PLANE_INDEX["last_observed_epoch"],
                        context_key,
                        index,
                    ]
                )
                for index, support in enumerate(supports)
            ],
            "evidence": _evidence_rows(values, context_key),
            "work": {
                "field_cells_read": 0,
                "feature_cells_read": len(context["feature_vector"]),
                "candidate_comparisons": 0,
                "operations": 0,
            },
        }
    else:
        selected, selection = select_method(
            working_policy, compiled, budget=budget, explore=learn
        )
    selector_budget = _integer(
        selection.get("work", {}).get("operations", 0),
        "selector operations",
    )
    available = max(0, budget - selector_budget)
    if selected.startswith("algebraic"):
        hybrid_budget = available // 2
        search_budget = available - hybrid_budget
    else:
        hybrid_budget = 0
        search_budget = available
    try:
        profile = _profile_for(
            compiled,
            selected,
            hybrid_budget=hybrid_budget,
            search_budget=search_budget,
            max_field_bytes=max_field_bytes,
        )
        field = ConstraintField(profile)
        state = field.initial(compiled)
    except (ConstraintFieldError, TypeError, ValueError) as exc:
        raise PolicyError("solver initialization failed") from exc
    peak_field_bytes = state.nbytes
    if peak_field_bytes > max_field_bytes:
        raise PolicyError("solver state exceeds max_field_bytes")
    current = state
    # Ceilings are disjoint and fixed before the first solver operation.  The
    # hybrid prepass is one public field step but its complete internal work is
    # charged from its hybrid ledger, never rounded to one transition.
    while current.status == "running":
        work_now = _work_snapshot(field, current)
        h_now, s_now, c_now = _usage(work_now)
        if h_now > hybrid_budget or s_now > search_budget or c_now > search_budget:
            raise PolicyError("solver exceeded its reserved work ceiling")
        if h_now + s_now + c_now >= available:
            current = _mark_exhausted(current)
            break
        if current.hybrid is not None and current.backend is None:
            if hybrid_budget <= h_now:
                current = _mark_exhausted(current)
                break
        else:
            # A controller advance consumes up to four ticks and one backend
            # transition atomically.  Refuse the call if the reserved search
            # ceiling cannot pay its exact worst-case charge.
            pending_controller = False
            potential_ticks = 0
            if current.controller is not None and current.backend is not None:
                try:
                    backend_field = field._backend_field(current)
                    pending_controller = backend_field.decision_context(current.backend)["pending"] == "decide"
                    if pending_controller:
                        potential_ticks = min(4, search_budget - c_now)
                except Exception as exc:
                    raise PolicyError("controller/search scheduling failed") from exc
            potential = 1 + potential_ticks
            if s_now + c_now + potential > search_budget:
                current = _mark_exhausted(current)
                break
        try:
            current, _ = field.step(current)
        except (ConstraintFieldError, TypeError, ValueError) as exc:
            raise PolicyError("solver execution failed") from exc
        peak_field_bytes = max(peak_field_bytes, current.nbytes)
        if current.nbytes > max_field_bytes:
            raise PolicyError("solver state exceeds max_field_bytes")
    try:
        result = field.result(current)
        terminal_descriptor = field.descriptor(current)
    except (ConstraintFieldError, TypeError, ValueError) as exc:
        raise PolicyError("solver terminal state is invalid") from exc
    # Internal assignments/proof snapshots on a ConstraintField exhaustion
    # state are not evidence.  Strip them from the public receipt.
    if result.get("status") == "exhausted":
        result = dict(result)
        result["assignment"] = None
        result["witness"] = None
        result["resolution_proof"] = None
        result["hybrid_proof"] = None
    audit = audit_result(compiled, result)
    decision_cost_ns = _safe_add(time.perf_counter_ns() - started, 0, "decision_cost_ns")
    final_work = result.get("work")
    if not isinstance(final_work, Mapping):
        raise PolicyError("solver result lacks work ledger")
    hybrid_used, search_used, controller_used = _usage(final_work)
    used = selector_budget + hybrid_used + search_used + controller_used
    if used > budget:
        raise PolicyError("shared budget accounting overflow")
    remaining = budget - used
    evidence = (
        result.get("witness")
        if result.get("status") == "sat"
        else result.get("resolution_proof") or result.get("hybrid_proof")
    )
    proof_bytes = (
        len(_canonical(evidence))
        if isinstance(evidence, Mapping) and result.get("status") == "unsat"
        else 0
    )
    ledger = _flatten_ledger(
        final_work,
        selector=selector_budget,
        hybrid=hybrid_used,
        search=search_used,
        controller=controller_used,
    )
    observation = None
    if learn:
        method_index = METHODS.index(selected)
        learning_started = time.perf_counter_ns()
        next_policy, observation = _record_observation(
            working_policy,
            int(context["context_key"]),
            method_index,
            elapsed_ns=decision_cost_ns,
            work=used,
            status=str(result["status"]),
        )
        learning_elapsed_ns = _safe_add(
            time.perf_counter_ns() - learning_started,
            0,
            "learning_elapsed_ns",
        )
    else:
        next_policy = policy
        learning_elapsed_ns = 0
    total_elapsed_ns = _safe_add(time.perf_counter_ns() - started, 0, "total_elapsed_ns")
    migration = None
    if migrated:
        migration = {
            "schema": "cassifi.computation-policy-migration.v2",
            "from_schema": policy._schema,
            "to_schema": working_policy._schema,
            "from_state_sha256": policy.state_sha256,
            "selection_state_sha256": working_policy.state_sha256,
            "applied": bool(learn),
            "destination": (
                "budget-scoped evidence with field epochs"
                if policy._schema == PREVIOUS_SCHEMA
                else "budget-unscoped structural prior with field epochs"
            ),
            "long_support_limit": _LONG_LIMIT,
            "recent_evidence_preserved": (
                policy._schema == PREVIOUS_SCHEMA
            ),
            "context_epoch_initialized_from_support": True,
        }
    receipt: dict[str, Any] = {
        "schema": RECEIPT_SCHEMA,
        "method": selected,
        "source_sha256": compiled.sha256,
        "context": context,
        "selection": selection,
        "selection_work": dict(selection.get("work", {})),
        "policy_migrated": bool(migrated and learn),
        "policy_schema_before": policy._schema,
        "policy_schema_after": next_policy._schema,
        "policy_state_sha256_before": policy.state_sha256,
        "policy_state_sha256_after": next_policy.state_sha256,
        "migration": migration,
        "observation": observation,
        "status": result["status"],
        "reason": result.get("reason"),
        "elapsed_ns": int(total_elapsed_ns),
        "decision_cost_ns": int(decision_cost_ns),
        "learning_elapsed_ns": int(learning_elapsed_ns),
        "total_elapsed_ns": int(total_elapsed_ns),
        "resource_ledger": ledger,
        "work": final_work,
        "result": result,
        "field_bytes": int(current.nbytes),
        "peak_field_bytes": int(peak_field_bytes),
        "policy_field_bytes": int(policy.nbytes),
        "retained_field_bytes": int(next_policy.nbytes),
        "peak_workspace_bytes": int(max(policy.nbytes, working_policy.nbytes, next_policy.nbytes) + peak_field_bytes),
        "max_field_bytes": int(max_field_bytes),
        "proof_bytes": int(proof_bytes),
        "audit": audit,
        "audit_result": audit,
        "witness": result.get("witness"),
        "proof": evidence if result.get("status") == "unsat" else None,
        "terminal_descriptor": terminal_descriptor,
        "budget": {
            "declared": int(budget),
            "used": int(used),
            "remaining": int(remaining),
            "selector": selector_budget,
            "hybrid": hybrid_budget,
            "search": search_budget,
        },
        "budget_used": int(used),
        "budget_remaining": int(remaining),
        "state_sha256": terminal_descriptor.get("state_sha256"),
    }
    return next_policy, receipt


def _next_atomic_charge(
    field: ConstraintField,
    state: Any,
    *,
    hybrid_budget: int,
    search_budget: int,
) -> tuple[int, bool]:
    """Return the worst-case charge of the next indivisible solver step."""

    work = _work_snapshot(field, state)
    hybrid_used, search_used, controller_used = _usage(work)
    if state.hybrid is not None and state.backend is None:
        remaining = hybrid_budget - hybrid_used
        return max(0, remaining), remaining <= 0
    potential_ticks = 0
    if state.controller is not None and state.backend is not None:
        try:
            backend_field = field._backend_field(state)
            pending = (
                backend_field.decision_context(state.backend)["pending"]
                == "decide"
            )
        except Exception as exc:
            raise PolicyError(
                "controller/search continuation failed"
            ) from exc
        if pending:
            potential_ticks = min(
                4,
                max(0, search_budget - controller_used),
            )
    charge = 1 + potential_ticks
    exhausted = (
        search_used + controller_used + charge > search_budget
    )
    return charge, exhausted

CONTINUATION_SCHEMA = "cassifi.solver-continuation.v1"
CONTINUATION_RECEIPT_SCHEMA = (
    "cassifi.solver-continuation-receipt.v1"
)


@dataclass(frozen=True, slots=True)
class SolverContinuation:
    """One exact running solver field plus its frozen selection boundary."""

    source_sha256: str
    method: str
    selection: Mapping[str, Any]
    context: Mapping[str, Any]
    field_descriptor: Mapping[str, Any]
    lifetime_budget: int
    selector_budget: int
    hybrid_budget: int
    search_budget: int
    minimum_resume_budget: int
    learn: bool
    episode: int
    cumulative_elapsed_ns: int
    policy_state_sha256: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.source_sha256, str)
            or len(self.source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.source_sha256
            )
        ):
            raise PolicyError("continuation source digest is invalid")
        if self.method not in METHODS:
            raise PolicyError("continuation method is invalid")
        if not isinstance(self.learn, bool):
            raise PolicyError("continuation learning flag is invalid")
        for name in (
            "lifetime_budget",
            "selector_budget",
            "hybrid_budget",
            "search_budget",
            "minimum_resume_budget",
            "episode",
            "cumulative_elapsed_ns",
        ):
            minimum = (
                1
                if name
                in (
                    "lifetime_budget",
                    "minimum_resume_budget",
                    "episode",
                )
                else 0
            )
            _integer(getattr(self, name), name, minimum=minimum)
        if (
            self.selector_budget
            + self.hybrid_budget
            + self.search_budget
            != self.lifetime_budget
        ):
            raise PolicyError(
                "continuation budget partition is inconsistent"
            )
        if (
            not isinstance(self.policy_state_sha256, str)
            or len(self.policy_state_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in self.policy_state_sha256
            )
        ):
            raise PolicyError("continuation policy digest is invalid")
        try:
            selection = json.loads(
                _canonical(dict(self.selection)).decode("utf-8")
            )
            context = json.loads(
                _canonical(dict(self.context)).decode("utf-8")
            )
            descriptor = json.loads(
                _canonical(dict(self.field_descriptor)).decode("utf-8")
            )
            field, state = ConstraintField.from_descriptor(descriptor)
        except (
            ConstraintFieldError,
            KeyError,
            TypeError,
            ValueError,
        ) as exc:
            raise PolicyError(
                "continuation field descriptor is invalid"
            ) from exc
        if state.status != "running":
            raise PolicyError(
                "continuation must retain a running solver boundary"
            )
        hybrid_used, search_used, controller_used = _usage(
            _work_snapshot(field, state)
        )
        if (
            hybrid_used > self.hybrid_budget
            or search_used + controller_used > self.search_budget
            or field.profile.max_hybrid_transitions
            != max(1, self.hybrid_budget)
            or field.profile.max_transitions
            != max(1, self.search_budget)
        ):
            raise PolicyError(
                "continuation work exceeds its frozen capacity"
            )
        if state.compiled.sha256 != self.source_sha256:
            raise PolicyError(
                "continuation source does not match its solver field"
            )
        if (
            selection.get("method") != self.method
            or selection.get("context") != context
        ):
            raise PolicyError(
                "continuation selection boundary is inconsistent"
            )
        expected_mode = (
            "algebraic"
            if self.method.startswith("algebraic")
            else "conflict"
        )
        if (
            field.profile.mode != expected_mode
            or field.profile.controller
            != self.method.endswith("-controller")
        ):
            raise PolicyError(
                "continuation solver profile differs from its method"
            )
        next_charge, capacity_exhausted = _next_atomic_charge(
            field,
            state,
            hybrid_budget=self.hybrid_budget,
            search_budget=self.search_budget,
        )
        if (
            capacity_exhausted
            or next_charge != self.minimum_resume_budget
        ):
            raise PolicyError(
                "continuation atomic resume budget is inconsistent"
            )
        object.__setattr__(self, "selection", selection)
        object.__setattr__(self, "context", context)
        object.__setattr__(self, "field_descriptor", descriptor)

    @property
    def state_sha256(self) -> str:
        return str(self.field_descriptor["state_sha256"])

    @property
    def nbytes(self) -> int:
        return len(_canonical(self.as_dict()))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": CONTINUATION_SCHEMA,
            "source_sha256": self.source_sha256,
            "method": self.method,
            "selection": dict(self.selection),
            "context": dict(self.context),
            "field_descriptor": dict(self.field_descriptor),
            "lifetime_budget": self.lifetime_budget,
            "selector_budget": self.selector_budget,
            "hybrid_budget": self.hybrid_budget,
            "search_budget": self.search_budget,
            "minimum_resume_budget": self.minimum_resume_budget,
            "learn": self.learn,
            "episode": self.episode,
            "cumulative_elapsed_ns": self.cumulative_elapsed_ns,
            "policy_state_sha256": self.policy_state_sha256,
        }

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> SolverContinuation:
        required = {
            "schema",
            "source_sha256",
            "method",
            "selection",
            "context",
            "field_descriptor",
            "lifetime_budget",
            "selector_budget",
            "hybrid_budget",
            "search_budget",
            "minimum_resume_budget",
            "learn",
            "episode",
            "cumulative_elapsed_ns",
            "policy_state_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise PolicyError(
                "continuation descriptor keys are not canonical"
            )
        if value["schema"] != CONTINUATION_SCHEMA:
            raise PolicyError(
                "unsupported solver continuation schema"
            )
        return cls(
            source_sha256=value["source_sha256"],
            method=value["method"],
            selection=value["selection"],
            context=value["context"],
            field_descriptor=value["field_descriptor"],
            lifetime_budget=value["lifetime_budget"],
            selector_budget=value["selector_budget"],
            hybrid_budget=value["hybrid_budget"],
            search_budget=value["search_budget"],
            minimum_resume_budget=value["minimum_resume_budget"],
            learn=value["learn"],
            episode=value["episode"],
            cumulative_elapsed_ns=value["cumulative_elapsed_ns"],
            policy_state_sha256=value["policy_state_sha256"],
        )


def _continuation_fixed_selection(
    working_policy: PolicyState,
    compiled: CompiledConstraintProblem,
    context: Mapping[str, Any],
    method: str,
) -> dict[str, Any]:
    context_key = int(context["context_key"])
    values = working_policy._field
    return {
        "schema": "cassifi.computation-continuation-selection.v1",
        "method": method,
        "context": dict(context),
        "phase": "fixed",
        "forced": True,
        "structural_incumbent": METHODS[
            _structural_incumbent(compiled)
        ],
        "context_epoch": int(
            values[
                _PLANE_INDEX["context_epoch"],
                context_key,
                0,
            ]
        ),
        "work": {
            "field_cells_read": 0,
            "feature_cells_read": len(context["feature_vector"]),
            "candidate_comparisons": 0,
            "operations": 0,
        },
    }


def _solve_continuation_episode(
    policy: PolicyState,
    source: CompiledConstraintProblem | Mapping[str, Any],
    *,
    budget: int,
    max_field_bytes: int,
    continuation: SolverContinuation | None,
    learn: bool = True,
    method: str | None = None,
    lifetime_budget: int | None = None,
) -> tuple[PolicyState, dict[str, Any], SolverContinuation | None]:
    started = time.perf_counter_ns()
    if not isinstance(policy, PolicyState):
        raise PolicyError("policy must be PolicyState")
    budget = _integer(budget, "budget", minimum=1)
    max_field_bytes = _integer(
        max_field_bytes, "max_field_bytes", minimum=1
    )
    compiled = _ensure_compiled(source)
    working_policy = migrate_policy(policy)
    resumed = continuation is not None
    if continuation is None:
        if not isinstance(learn, bool):
            raise PolicyError("learn must be boolean")
        total_budget = _integer(
            budget if lifetime_budget is None else lifetime_budget,
            "lifetime_budget",
            minimum=budget,
        )
        context = context_features(compiled, budget=total_budget)
        if method is None:
            selected, selection = select_method(
                working_policy,
                compiled,
                budget=total_budget,
                explore=learn,
            )
        else:
            if method not in METHODS:
                raise PolicyError(
                    f"unknown computation method {method!r}"
                )
            selected = method
            selection = _continuation_fixed_selection(
                working_policy,
                compiled,
                context,
                method,
            )
        selector_budget = _integer(
            selection.get("work", {}).get("operations", 0),
            "selector operations",
        )
        first_available = max(0, budget - selector_budget)
        total_available = max(0, total_budget - selector_budget)
        if selected.startswith("algebraic"):
            hybrid_budget = first_available // 2
            search_budget = total_available - hybrid_budget
        else:
            hybrid_budget = 0
            search_budget = total_available
        try:
            profile = _profile_for(
                compiled,
                selected,
                hybrid_budget=hybrid_budget,
                search_budget=search_budget,
                max_field_bytes=max_field_bytes,
            )
            field = ConstraintField(profile)
            current = field.initial(compiled)
        except (
            ConstraintFieldError,
            TypeError,
            ValueError,
        ) as exc:
            raise PolicyError(
                "solver continuation initialization failed"
            ) from exc
        learning_requested = learn
        episode_before = 0
        cumulative_elapsed_before = 0
        policy_boundary_sha256 = policy.state_sha256
    else:
        if not isinstance(continuation, SolverContinuation):
            raise PolicyError(
                "continuation must be SolverContinuation"
            )
        if lifetime_budget is not None or method is not None:
            raise PolicyError(
                "continued solving cannot change method or lifetime budget"
            )
        if compiled.sha256 != continuation.source_sha256:
            raise PolicyError(
                "continued solve source differs from its checkpoint"
            )
        if policy.state_sha256 != continuation.policy_state_sha256:
            raise PolicyError(
                "continued solve policy boundary has changed"
            )
        if budget < continuation.minimum_resume_budget:
            raise PolicyError(
                "continuation episode budget cannot cover the next "
                "atomic solver step; requires at least "
                f"{continuation.minimum_resume_budget}"
            )
        try:
            field, current = ConstraintField.from_descriptor(
                continuation.field_descriptor
            )
        except (
            ConstraintFieldError,
            TypeError,
            ValueError,
        ) as exc:
            raise PolicyError(
                "solver continuation restore failed"
            ) from exc
        selected = continuation.method
        selection = dict(continuation.selection)
        context = dict(continuation.context)
        total_budget = continuation.lifetime_budget
        selector_budget = continuation.selector_budget
        hybrid_budget = continuation.hybrid_budget
        search_budget = continuation.search_budget
        learning_requested = continuation.learn
        episode_before = continuation.episode
        cumulative_elapsed_before = (
            continuation.cumulative_elapsed_ns
        )
        policy_boundary_sha256 = (
            continuation.policy_state_sha256
        )
    if current.nbytes > max_field_bytes:
        raise PolicyError(
            "solver continuation exceeds max_field_bytes"
        )
    state_sha256_before = field.state_sha256(current)
    peak_field_bytes = current.nbytes
    before_work = _work_snapshot(field, current)
    before_hybrid, before_search, before_controller = _usage(
        before_work
    )
    episode_selector = 0 if resumed else selector_budget
    episode_available = max(0, budget - episode_selector)
    total_available = hybrid_budget + search_budget
    paused = False
    minimum_resume_budget: int | None = None
    while current.status == "running":
        work_now = _work_snapshot(field, current)
        hybrid_now, search_now, controller_now = _usage(work_now)
        if (
            hybrid_now > hybrid_budget
            or search_now + controller_now > search_budget
        ):
            raise PolicyError(
                "solver exceeded its continuation capacity"
            )
        total_solver_used = (
            hybrid_now + search_now + controller_now
        )
        episode_solver_used = (
            hybrid_now
            - before_hybrid
            + search_now
            - before_search
            + controller_now
            - before_controller
        )
        if total_solver_used >= total_available:
            current = _mark_exhausted(current)
            break
        charge, capacity_exhausted = _next_atomic_charge(
            field,
            current,
            hybrid_budget=hybrid_budget,
            search_budget=search_budget,
        )
        if capacity_exhausted:
            current = _mark_exhausted(current)
            break
        if episode_solver_used + charge > episode_available:
            minimum_resume_budget = charge
            paused = True
            break
        state_before_step = field.state_sha256(current)
        work_before_step = total_solver_used
        try:
            current, _ = field.step(current)
        except (
            ConstraintFieldError,
            TypeError,
            ValueError,
        ) as exc:
            raise PolicyError(
                "solver continuation execution failed"
            ) from exc
        after_hybrid, after_search, after_controller = _usage(
            _work_snapshot(field, current)
        )
        work_after_step = (
            after_hybrid + after_search + after_controller
        )
        episode_after_step = (
            after_hybrid
            - before_hybrid
            + after_search
            - before_search
            + after_controller
            - before_controller
        )
        if (
            work_after_step < work_before_step
            or work_after_step > work_before_step + charge
            or episode_after_step > episode_available
        ):
            raise PolicyError(
                "solver atomic step violated continuation accounting"
            )
        if (
            current.status == "running"
            and work_after_step == work_before_step
            and field.state_sha256(current) == state_before_step
        ):
            raise PolicyError(
                "solver atomic step made no observable progress"
            )
        peak_field_bytes = max(peak_field_bytes, current.nbytes)
        if current.nbytes > max_field_bytes:
            raise PolicyError(
                "solver continuation exceeds max_field_bytes"
            )
    reported = (
        _mark_exhausted(current, "episode-budget")
        if paused
        else current
    )
    try:
        result = field.result(reported)
    except (
        ConstraintFieldError,
        TypeError,
        ValueError,
    ) as exc:
        raise PolicyError(
            "solver continuation result is invalid"
        ) from exc
    if result.get("status") == "exhausted":
        result = dict(result)
        result["assignment"] = None
        result["witness"] = None
        result["resolution_proof"] = None
        result["hybrid_proof"] = None
    audit = audit_result(compiled, result)
    episode_elapsed = _safe_add(
        time.perf_counter_ns() - started,
        0,
        "continuation episode elapsed",
    )
    cumulative_elapsed = _safe_add(
        cumulative_elapsed_before,
        episode_elapsed,
        "continuation cumulative elapsed",
    )
    final_work = result.get("work")
    if not isinstance(final_work, Mapping):
        raise PolicyError(
            "solver continuation result lacks work ledger"
        )
    hybrid_after, search_after, controller_after = _usage(
        final_work
    )
    delta_hybrid = hybrid_after - before_hybrid
    delta_search = search_after - before_search
    delta_controller = controller_after - before_controller
    episode_used = (
        episode_selector
        + delta_hybrid
        + delta_search
        + delta_controller
    )
    cumulative_used = (
        selector_budget
        + hybrid_after
        + search_after
        + controller_after
    )
    if episode_used > budget or cumulative_used > total_budget:
        raise PolicyError(
            "solver continuation budget accounting overflow"
        )
    final = not paused
    observation = None
    if final and learning_requested:
        learning_started = time.perf_counter_ns()
        next_policy, observation = _record_observation(
            working_policy,
            int(context["context_key"]),
            METHODS.index(selected),
            elapsed_ns=cumulative_elapsed,
            work=cumulative_used,
            status=str(result["status"]),
        )
        learning_elapsed = _safe_add(
            time.perf_counter_ns() - learning_started,
            0,
            "continuation learning elapsed",
        )
    else:
        next_policy = policy
        learning_elapsed = 0
    next_continuation = None
    if paused:
        if minimum_resume_budget is None:
            raise PolicyError(
                "paused continuation is missing its atomic budget"
            )
        next_continuation = SolverContinuation(
            source_sha256=compiled.sha256,
            method=selected,
            selection=selection,
            context=context,
            field_descriptor=field.descriptor(current),
            lifetime_budget=total_budget,
            selector_budget=selector_budget,
            hybrid_budget=hybrid_budget,
            search_budget=search_budget,
            minimum_resume_budget=minimum_resume_budget,
            learn=learning_requested,
            episode=episode_before + 1,
            cumulative_elapsed_ns=cumulative_elapsed,
            policy_state_sha256=policy_boundary_sha256,
        )
    evidence = (
        result.get("witness")
        if result.get("status") == "sat"
        else result.get("resolution_proof")
        or result.get("hybrid_proof")
    )
    proof_bytes = (
        len(_canonical(evidence))
        if isinstance(evidence, Mapping)
        and result.get("status") == "unsat"
        else 0
    )
    delta_ledger = _flatten_ledger(
        final_work,
        selector=episode_selector,
        hybrid=delta_hybrid,
        search=delta_search,
        controller=delta_controller,
    )
    cumulative_ledger = _flatten_ledger(
        final_work,
        selector=selector_budget,
        hybrid=hybrid_after,
        search=search_after,
        controller=controller_after,
    )
    receipt = {
        "schema": CONTINUATION_RECEIPT_SCHEMA,
        "method": selected,
        "source_sha256": compiled.sha256,
        "context": context,
        "selection": selection,
        "selection_work": dict(selection.get("work", {})),
        "status": result["status"],
        "reason": result.get("reason"),
        "elapsed_ns": episode_elapsed,
        "cumulative_elapsed_ns": cumulative_elapsed,
        "learning_elapsed_ns": learning_elapsed,
        "resource_ledger": delta_ledger,
        "cumulative_resource_ledger": cumulative_ledger,
        "work": final_work,
        "result": result,
        "field_bytes": int(current.nbytes),
        "peak_field_bytes": int(peak_field_bytes),
        "max_field_bytes": int(max_field_bytes),
        "policy_field_bytes": int(policy.nbytes),
        "retained_policy_field_bytes": int(next_policy.nbytes),
        "proof_bytes": int(proof_bytes),
        "audit": audit,
        "audit_result": audit,
        "witness": result.get("witness"),
        "proof": (
            evidence if result.get("status") == "unsat" else None
        ),
        "policy_state_sha256_before": policy.state_sha256,
        "policy_state_sha256_after": next_policy.state_sha256,
        "policy_schema_before": policy._schema,
        "policy_schema_after": next_policy._schema,
        "observation": observation,
        "budget": {
            "declared": budget,
            "used": episode_used,
            "remaining": budget - episode_used,
            "selector": episode_selector,
            "hybrid": delta_hybrid,
            "search": delta_search + delta_controller,
            "lifetime_declared": total_budget,
            "cumulative_used": cumulative_used,
            "cumulative_remaining": total_budget - cumulative_used,
            "minimum_next_episode": minimum_resume_budget,
        },
        "budget_used": episode_used,
        "budget_remaining": budget - episode_used,
        "continuation": {
            "resumed": resumed,
            "episode": episode_before + 1,
            "continuable": paused,
            "final": final,
            "minimum_resume_budget": minimum_resume_budget,
            "learning_requested": learning_requested,
            "learning_deferred": bool(
                paused and learning_requested
            ),
            "learning_applied": bool(
                final and learning_requested
            ),
            "state_sha256_before": state_sha256_before,
            "state_sha256_after": field.state_sha256(current),
            "retained_state_sha256": (
                None
                if next_continuation is None
                else next_continuation.state_sha256
            ),
        },
    }
    return next_policy, receipt, next_continuation


def start_solver_continuation(
    policy: PolicyState,
    source: CompiledConstraintProblem | Mapping[str, Any],
    *,
    budget: int = 2000,
    lifetime_budget: int = 4096,
    learn: bool = True,
    method: str | None = None,
    max_field_bytes: int = 134_217_728,
) -> tuple[PolicyState, dict[str, Any], SolverContinuation | None]:
    """Start one bounded episode and retain its exact running field."""

    return _solve_continuation_episode(
        policy,
        source,
        budget=budget,
        max_field_bytes=max_field_bytes,
        continuation=None,
        learn=learn,
        method=method,
        lifetime_budget=lifetime_budget,
    )


def continue_solver_continuation(
    policy: PolicyState,
    continuation: SolverContinuation,
    source: CompiledConstraintProblem | Mapping[str, Any],
    *,
    budget: int = 2000,
    max_field_bytes: int = 134_217_728,
) -> tuple[PolicyState, dict[str, Any], SolverContinuation | None]:
    """Advance the same exact solver field by one bounded episode."""

    return _solve_continuation_episode(
        policy,
        source,
        budget=budget,
        max_field_bytes=max_field_bytes,
        continuation=continuation,
    )


def encode_regional_policy(policy: PolicyState) -> dict[str, Any]:
    working = migrate_policy(policy)
    return {
        "schema": SCHEMA,
        "layout": _LAYOUT,
        "planes": [
            [
                [int(value) for value in method_row]
                for method_row in context_rows
            ]
            for context_rows in working._field
        ],
    }


def _regional_policy_field(value: Any) -> np.ndarray:
    if (
        not isinstance(value, Mapping)
        or set(value) != {"schema", "layout", "planes"}
        or value.get("schema") != SCHEMA
        or value.get("layout") != _LAYOUT
    ):
        raise PolicyError("regional policy data is invalid")
    try:
        field = np.asarray(value["planes"], dtype=np.float64)
    except (TypeError, ValueError, OverflowError) as exc:
        raise PolicyError("regional policy planes are invalid") from exc
    if field.shape != (len(_PLANES), _CONTEXT_COUNT, len(METHODS)):
        raise PolicyError("regional policy plane shape is invalid")
    if (
        not np.all(np.isfinite(field))
        or np.any(field < 0)
        or np.any(field > _SAFE_INTEGER)
        or not np.all(field == np.floor(field))
    ):
        raise PolicyError("regional policy cells are invalid")
    return field


def _regional_policy_value(field: np.ndarray) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "layout": _LAYOUT,
        "planes": [
            [
                [int(value) for value in method_row]
                for method_row in context_rows
            ]
            for context_rows in field
        ],
    }


def _regional_select(
    field: np.ndarray,
    compiled: CompiledConstraintProblem,
    *,
    budget: int,
    explore: bool,
    requested_method: str | None,
) -> tuple[str, dict[str, Any]]:
    context_value = context_features(compiled, budget=budget)
    context_key = int(context_value["context_key"])
    supports = _support_vector(field, context_key)
    epoch = int(field[_PLANE_INDEX["context_epoch"], context_key, 0])
    last_observed = [
        int(field[_PLANE_INDEX["last_observed_epoch"], context_key, index])
        for index in range(len(METHODS))
    ]
    unseen = [index for index, support in enumerate(supports) if support == 0]
    incumbent = _structural_incumbent(compiled)
    evidence_key = context_key
    comparisons = 0
    exploration_reason: str | None = None
    if requested_method is not None:
        selected = METHODS.index(requested_method)
        phase = "requested"
    else:
        related_keys = _related_evidence_keys(context_value)
        related_key = _first_supported_context(
            field, related_keys, tuple(range(len(METHODS)))
        )
        if sum(supports) == 0 and related_key is not None:
            evidence_key = related_key
            related_supports = _support_vector(field, evidence_key)
            observed = tuple(
                index
                for index, support in enumerate(related_supports)
                if support > 0
            )
            selected = _selection_index(field, evidence_key, observed)
            comparisons = max(0, len(observed) - 1)
            phase = (
                "refined-sibling-prior"
                if evidence_key == related_keys[0]
                else "structural-prior"
            )
            exploration_reason = "evidence-driven-context-refinement"
        elif sum(supports) == 0:
            selected = incumbent
            phase = "cold-start"
            exploration_reason = "declared-structural-incumbent"
        elif explore and unseen and epoch == _next_unseen_epoch(epoch):
            exploration_key = _first_supported_context(
                field, related_keys, unseen
            )
            if exploration_key is not None:
                supported_unseen = tuple(
                    candidate
                    for candidate in unseen
                    if int(
                        field[
                            _PLANE_INDEX["long_support"],
                            exploration_key,
                            candidate,
                        ]
                    )
                    > 0
                )
                selected = _selection_index(
                    field, exploration_key, supported_unseen
                )
                evidence_key = exploration_key
                comparisons = max(0, len(supported_unseen) - 1)
                exploration_reason = "related-evidence-completion-cost"
            else:
                challenger_order = tuple(
                    (incumbent + offset) % len(METHODS)
                    for offset in range(1, len(METHODS) + 1)
                )
                selected = next(
                    candidate
                    for candidate in challenger_order
                    if candidate in unseen
                )
                exploration_reason = "scheduled-unseen-challenger"
            phase = "explore"
        elif (
            explore
            and not unseen
            and epoch > 0
            and epoch % _REEVALUATION_PERIOD == 0
        ):
            selected = min(
                range(len(METHODS)),
                key=lambda index: (
                    last_observed[index], supports[index], index
                ),
            )
            phase = "reevaluate"
            exploration_reason = "stale-method-reevaluation"
        else:
            observed = tuple(
                index for index, support in enumerate(supports) if support > 0
            )
            selected = _selection_index(field, context_key, observed)
            comparisons = max(0, len(observed) - 1)
            phase = "empirical"
    method = METHODS[selected]
    ages = [
        None if support == 0 else epoch - last_observed[index]
        for index, support in enumerate(supports)
    ]
    return method, {
        "schema": "cassifi.computation-selection.v4",
        "method": method,
        "context": context_value,
        "phase": phase,
        "exploration_reason": exploration_reason,
        "observation_context_key": context_key,
        "evidence_context_key": evidence_key,
        "structural_incumbent": METHODS[incumbent],
        "context_epoch": epoch,
        "exploration_interval": _EXPLORATION_INTERVAL,
        "exploration_complete": not unseen,
        "unseen_methods": [METHODS[index] for index in unseen],
        "next_unseen_exploration_epoch": (
            None if not unseen else _next_unseen_epoch(epoch)
        ),
        "reevaluation_period": _REEVALUATION_PERIOD,
        "recent_decay_period": _RECENT_DECAY_PERIOD,
        "observed_support": supports,
        "checked_completion": [
            int(field[_PLANE_INDEX["long_completion"], context_key, index])
            for index in range(len(METHODS))
        ],
        "last_observed_epoch": last_observed,
        "method_age": ages,
        "evidence": _evidence_rows(field, evidence_key),
        "work": {
            "field_cells_read": len(_PLANES) * len(METHODS)
            * (2 if evidence_key != context_key else 1),
            "feature_cells_read": len(context_value["feature_vector"]),
            "candidate_comparisons": comparisons,
            "operations": 1,
        },
    }


def _regional_record_observation(
    field: np.ndarray,
    *,
    context: int,
    method_index: int,
    elapsed_ns: int,
    work: int,
    status: str,
) -> tuple[np.ndarray, dict[str, Any]]:
    context = _integer(context, "context", maximum=_CONTEXT_COUNT - 1)
    method_index = _integer(
        method_index, "method_index", maximum=len(METHODS) - 1
    )
    elapsed_ns = _integer(elapsed_ns, "elapsed_ns")
    work = _integer(work, "work")
    if status not in ("sat", "unsat", "exhausted"):
        raise PolicyError("cannot record nonterminal observation")
    retained_elapsed = max(1, min(elapsed_ns, _OBSERVED_ELAPSED_CAP_NS))
    retained_work = min(work, _OBSERVED_WORK_CAP)
    completed = int(status in ("sat", "unsat"))
    updated = field.copy()
    epoch_coordinate = _PLANE_INDEX["context_epoch"]
    last_coordinate = _PLANE_INDEX["last_observed_epoch"]
    epoch_before = int(updated[epoch_coordinate, context, 0])
    epoch_compressed = epoch_before >= _EPOCH_LIMIT
    if epoch_compressed:
        updated[epoch_coordinate, context, 0] = epoch_before // 2
        for candidate in range(len(METHODS)):
            updated[last_coordinate, context, candidate] = (
                int(updated[last_coordinate, context, candidate]) // 2
            )
    epoch_base = int(updated[epoch_coordinate, context, 0])
    epoch_after = epoch_base + 1
    synchronized_recent_decay = (
        epoch_after % _RECENT_DECAY_PERIOD == 0
        or any(
            int(updated[_PLANE_INDEX["recent_support"], context, candidate])
            >= _RECENT_LIMIT
            for candidate in range(len(METHODS))
        )
    )
    if synchronized_recent_decay:
        for candidate in range(len(METHODS)):
            _compress_window(
                updated,
                context,
                candidate,
                (
                    "recent_support",
                    "recent_completion",
                    "recent_elapsed_ns",
                ),
            )
    long_decayed = (
        int(updated[_PLANE_INDEX["long_support"], context, method_index])
        >= _LONG_LIMIT
    )
    if long_decayed:
        _compress_window(
            updated,
            context,
            method_index,
            (
                "long_support",
                "long_completion",
                "long_elapsed_ns",
                "long_work",
            ),
        )
    before = {
        plane: int(updated[_PLANE_INDEX[plane], context, method_index])
        for plane in _EVIDENCE_PLANES
    }
    before["last_observed_epoch"] = int(
        updated[last_coordinate, context, method_index]
    )
    increments = {
        "long_support": 1,
        "long_completion": completed,
        "long_elapsed_ns": retained_elapsed,
        "long_work": retained_work,
        "recent_support": 1,
        "recent_completion": completed,
        "recent_elapsed_ns": retained_elapsed,
    }
    for plane, increment in increments.items():
        coordinate = _PLANE_INDEX[plane]
        updated[coordinate, context, method_index] = _safe_add(
            int(updated[coordinate, context, method_index]), increment, plane
        )
    updated[epoch_coordinate, context, 0] = epoch_after
    updated[last_coordinate, context, method_index] = epoch_after
    after = {
        plane: int(updated[_PLANE_INDEX[plane], context, method_index])
        for plane in _EVIDENCE_PLANES
    }
    after["last_observed_epoch"] = epoch_after
    return updated, {
        "schema": "cassifi.computation-observation.v3",
        "context_key": context,
        "method": METHODS[method_index],
        "status": status,
        "elapsed_ns_observed": elapsed_ns,
        "elapsed_ns_retained": retained_elapsed,
        "work_observed": work,
        "work_retained": retained_work,
        "elapsed_clipped": elapsed_ns != retained_elapsed,
        "work_clipped": work != retained_work,
        "long_decayed": bool(long_decayed),
        "recent_synchronized_decay": bool(synchronized_recent_decay),
        "recent_decay_period": _RECENT_DECAY_PERIOD,
        "context_epoch_before": epoch_before,
        "context_epoch_compressed": bool(epoch_compressed),
        "context_epoch_after": epoch_after,
        "before": before,
        "increments": increments,
        "after": after,
    }


def regional_state(
    source: Mapping[str, Any],
    *,
    learn: bool = True,
    method: str | None = None,
    lifetime_budget: int = 4_096,
    max_field_bytes: int = 134_217_728,
    max_episodes: int = 256,
    policy: PolicyState | Mapping[str, Any] | None = None,
    feedback: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Lower method selection and an optional identified outcome into typed data."""

    if not isinstance(source, Mapping):
        raise PolicyError("regional policy source must be a mapping")
    compiled = compile_source(source)
    selected_policy = initial_policy() if policy is None else policy
    if isinstance(selected_policy, Mapping):
        policy_value = _regional_policy_value(
            _regional_policy_field(selected_policy)
        )
    elif isinstance(selected_policy, PolicyState):
        policy_value = encode_regional_policy(selected_policy)
    else:
        raise PolicyError("regional policy requires typed policy data")
    if method is not None and method not in METHODS:
        raise PolicyError("regional policy method is invalid")
    if not isinstance(learn, bool):
        raise PolicyError("regional learn must be boolean")
    canonical_feedback = None
    if feedback is not None:
        if not isinstance(feedback, Mapping):
            raise PolicyError("regional feedback must be a mapping")
        canonical_feedback = json.loads(_canonical(dict(feedback)).decode("utf-8"))
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": compiled.as_dict(),
        "profile": {
            "learn": learn,
            "requested_method": method,
            "budget": _integer(lifetime_budget, "lifetime_budget", minimum=1),
            "max_field_bytes": _integer(
                max_field_bytes, "max_field_bytes", minimum=1
            ),
            "max_episodes": _integer(max_episodes, "max_episodes", minimum=1),
            "source_sha256": compiled.sha256,
        },
        "phase": "ready",
        "continuation": {
            "policy": policy_value,
            "feedback": canonical_feedback,
            "selection": None,
            "observation": None,
        },
        "journal": [],
        "ledger": {"native_operations": 0, "feedback_events": 0},
        "result": None,
    }


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Select and update methods directly over typed field-owned policy planes."""

    required = {
        "schema", "source", "profile", "phase", "continuation",
        "journal", "ledger", "result",
    }
    if (
        not isinstance(state, Mapping)
        or set(state) != required
        or state.get("schema") != REGIONAL_STATE_SCHEMA
    ):
        raise PolicyError("regional policy state is invalid")
    if arguments:
        raise PolicyError("regional policy kernel takes no arguments")
    _integer(
        quantum, "regional policy quantum",
        minimum=1, maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    if state["phase"] == "terminal":
        return KernelResult(
            state=dict(state), status="done", work=0, output=state["result"]
        )
    if state["phase"] == "faulted":
        return KernelResult(
            state=dict(state), status="fault", work=0, output=state["result"]
        )
    profile = state["profile"]
    continuation = state["continuation"]
    ledger = state["ledger"]
    if (
        not isinstance(profile, Mapping)
        or not isinstance(continuation, Mapping)
        or set(continuation)
        != {"policy", "feedback", "selection", "observation"}
        or not isinstance(ledger, Mapping)
        or set(ledger) != {"native_operations", "feedback_events"}
        or not isinstance(state["journal"], list)
    ):
        raise PolicyError("regional policy continuation is invalid")
    compiled = _ensure_compiled(state["source"])
    if compiled.sha256 != profile.get("source_sha256"):
        raise PolicyError("regional policy source binding changed")
    field = _regional_policy_field(continuation["policy"])
    method, selection = _regional_select(
        field,
        compiled,
        budget=_integer(profile.get("budget"), "regional policy budget", minimum=1),
        explore=True,
        requested_method=profile.get("requested_method"),
    )
    feedback = continuation["feedback"]
    observation = None
    feedback_events = _integer(
        ledger["feedback_events"], "regional feedback events"
    )
    if feedback is not None:
        if (
            not isinstance(feedback, Mapping)
            or set(feedback) != {"id", "method", "status", "elapsed_ns", "work"}
            or not isinstance(feedback.get("id"), str)
            or not feedback["id"]
        ):
            raise PolicyError("regional feedback event is invalid")
        if feedback.get("method") != method:
            raise PolicyError("only the executed selected method may learn")
        if bool(profile.get("learn")):
            field, observation = _regional_record_observation(
                field,
                context=int(selection["observation_context_key"]),
                method_index=METHODS.index(method),
                elapsed_ns=_integer(feedback.get("elapsed_ns"), "elapsed_ns"),
                work=_integer(feedback.get("work"), "work"),
                status=str(feedback.get("status")),
            )
            feedback_events += 1
    result = {
        "schema": "cassifi.regional-computation-policy-result.v1",
        "status": "learned" if observation is not None else "selected",
        "method": method,
        "selection": selection,
        "observation": observation,
        "feedback_id": None if feedback is None else feedback["id"],
    }
    updated = {
        **dict(state),
        "phase": "terminal",
        "continuation": {
            "policy": _regional_policy_value(field),
            "feedback": feedback,
            "selection": selection,
            "observation": observation,
        },
        "journal": [
            *state["journal"],
            {
                "kind": "selection",
                "method": method,
                "feedback_id": result["feedback_id"],
            },
        ],
        "ledger": {
            "native_operations": _safe_add(
                _integer(ledger["native_operations"], "regional native operations"),
                1,
                "regional native operations",
            ),
            "feedback_events": feedback_events,
        },
        "result": result,
    }
    return KernelResult(state=updated, status="done", work=1, output=result)


def decode_regional_policy(value: Mapping[str, Any]) -> PolicyState:
    """Explicit offline projection for legacy API comparisons and export."""

    return PolicyState(_regional_policy_field(value))


__all__ = [
    "CONTINUATION_RECEIPT_SCHEMA",
    "CONTINUATION_SCHEMA",
    "METHODS",
    "PolicyError",
    "PolicyState",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "SolverContinuation",
    "audit_result",
    "compile_source",
    "continue_solver_continuation",
    "context_features",
    "initial_policy",
    "inspect_policy",
    "migrate_policy",
    "regional_kernel",
    "decode_regional_policy",
    "encode_regional_policy",
    "regional_state",
    "select_method",
    "solve_and_learn",
    "start_solver_continuation",
]
