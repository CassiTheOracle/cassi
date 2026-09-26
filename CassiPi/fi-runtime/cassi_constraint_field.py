"""Field-owned exact constraint solving over compiled Boolean sources.

The module compiles a finite Boolean circuit DAG, or a bounded synchronous
transition system, into a checked Tseitin CNF with explicit native-relation
provenance.
The legacy ``ConstraintField`` API keeps evolving search state in the
``ClauseField`` tensor, or in the ``HybridInferenceField`` tensor during the
algebraic prepass.  The v3 ``exact.constraint`` regional kernel is a separate
stateless native transition law: its source, phase, assignments, propagation
frontier, decisions, proof journal, counters, and terminal evidence are all
JSON primitives in the passed/returned mapping.  No descriptor, callback, or
host-side cache is authoritative for that path.

Three inference configurations share one interface:

``local``       sound propagation only; an unresolved stall reports
                ``exhausted`` rather than a satisfiability claim.
``conflict``    the complete bounded chronological search with persistent
                conflict learning and checked resolution refutations.
``algebraic``   an exact parity/counting prepass whose derived singleton
                facts are admitted with line provenance before the same
                complete bounded search runs.

Every SAT result carries a witness evaluated against the original source; every
UNSAT result carries a certificate that an independent checker can audit; an
exhausted run claims neither.  This is an exact constraint subsystem for
bounded sources.  It does not claim a polynomial worst-case bound, and it does
not claim that continuous field dynamics perform the reasoning.
"""

from __future__ import annotations

import base64
import hashlib
import heapq
import json
import math
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from cassi_clause_field import (
    ClauseField,
    ClauseFieldError,
    ClauseFieldProfile,
    ClauseFieldState,
)
from cassi_hybrid_inference import (
    HybridInferenceError,
    HybridInferenceField,
    HybridInferenceProfile,
    HybridInferenceState,
)
from run_p_vs_np_clause_field_probe import build_proof_certificate
import cassi_field_regions as field_regions

REGIONAL_KERNEL_NAME = "exact.constraint"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-constraint-state.v1"

PROBLEM_SCHEMA = "cassifi.constraint-problem.v1"
STATE_SCHEMA = "cassifi.constraint-field.v1"
RESULT_SCHEMA = "cassifi.constraint-result.v1"
DESCRIPTOR_SCHEMA = "cassifi.constraint-descriptor.v1"
STEP_SCHEMA = "cassifi.constraint-step.v1"
INTERVENTION_SCHEMA = "cassifi.constraint-intervention.v1"
_LAYOUT = "constraint-compiler-clause-field-v1"

_SAFE_INTEGER = 2**53 - 1
_MAX_RELATION_CLAUSES = 65_536
_MAX_COMPILED_CLAUSES = 262_144
_SIGNAL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")

_GATE_ARITY = {
    "const": 0,
    "buf": 1,
    "not": 1,
    "and": 2,
    "or": 2,
    "xor": 2,
    "nand": 2,
    "nor": 2,
    "xnor": 2,
    "mux": 3,
}

_STATUS_NAMES = ("running", "sat", "unsat", "exhausted")
_MAX_AUGMENTATION_ARITY = 2
_MODE_NAMES = ("local", "conflict", "algebraic")


class ConstraintFieldError(ValueError):
    """Invalid constraint source, profile, state, or field operation."""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _exact_integer(value: Any, name: str, *, minimum: int = 0, maximum: int = _SAFE_INTEGER) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum or value > maximum:
        raise ConstraintFieldError(f"{name} must be an exact bounded integer")
    return value


def _literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def _normalize_clause(clause: Sequence[int]) -> tuple[int, ...] | None:
    """Canonical clause; ``None`` for a tautology, ``()`` for a contradiction."""

    seen: set[int] = set()
    for literal in clause:
        if isinstance(literal, bool) or not isinstance(literal, int) or literal == 0:
            raise ConstraintFieldError("clause literals must be exact nonzero integers")
        if abs(literal) > _SAFE_INTEGER:
            raise ConstraintFieldError("clause literal exceeds exact range")
        if -literal in seen:
            return None
        seen.add(literal)
    return tuple(sorted(seen, key=_literal_key))


def _signal_name(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _SIGNAL_PATTERN.match(value):
        raise ConstraintFieldError(f"{name} must match [A-Za-z][A-Za-z0-9_]*")
    return value


def _unit_clause(literal: int) -> tuple[int, ...]:
    return (int(literal),)


def _holds_empty_clause(clauses: Sequence[tuple[int, ...]]) -> bool:
    """True when the compiled CNF already carries the contradictory clause.

    The parity/counting field refuses to load a contradiction as an input line,
    and its deductions cannot matter for a source that is refuted at load time,
    so the algebraic configuration sends such a source straight to the complete
    search and reports the same refutation class as the other configurations.
    """

    return any(len(clause) == 0 for clause in clauses)


def _identifier(identifiers: Mapping[str, int], name: str, names: str) -> int:
    identifier = identifiers.get(name)
    if identifier is None:
        raise ConstraintFieldError(f"{names} references unknown signal {name!r}")
    return identifier


def _resolve_signal(resolve, name: str, time: int, names: str) -> int:
    try:
        return resolve(name, time)
    except KeyError as exc:
        raise ConstraintFieldError(f"{names} references unknown signal {name!r}") from exc


def _gate_clauses(op: str, args: Sequence[int], out: int) -> list[tuple[int, ...]]:
    """Complete Tseitin definition of one gate; the output is its own variable."""

    if op == "and":
        a, b = args
        return [(-a, -b, out), (a, -out), (b, -out)]
    if op == "or":
        a, b = args
        return [(a, b, -out), (-a, out), (-b, out)]
    if op == "xor":
        a, b = args
        return [(a, b, -out), (a, -b, out), (-a, b, out), (-a, -b, -out)]
    if op == "nand":
        a, b = args
        return [(a, b, out), (a, -b, out), (-a, b, out), (-a, -b, -out)]
    if op == "nor":
        a, b = args
        return [(a, b, out), (a, -b, -out), (-a, b, -out), (-a, -b, -out)]
    if op == "xnor":
        a, b = args
        return [(a, b, out), (a, -b, -out), (-a, b, -out), (-a, -b, out)]
    if op == "buf":
        (a,) = args
        return [(-a, out), (a, -out)]
    if op == "not":
        (a,) = args
        return [(a, out), (-a, -out)]
    if op == "mux":
        s, t, f = args
        return [(-s, t, -out), (-s, -t, out), (s, f, -out), (s, -f, out)]
    raise ConstraintFieldError(f"unsupported gate operation {op!r}")


def _xor_support(args: Sequence[int]) -> list[int]:
    """Parity support: first-appearance order, arguments of odd multiplicity."""

    counts: dict[int, int] = {}
    order: list[int] = []
    for variable in args:
        if variable not in counts:
            counts[variable] = 0
            order.append(variable)
        counts[variable] += 1
    return [variable for variable in order if counts[variable] % 2 == 1]


def _xor_chain(
    args: Sequence[int],
    rhs: int,
    auxiliaries: Sequence[int],
) -> list[tuple[int, ...]]:
    """Exact GF(2) relation as a Tseitin chain; duplicates cancel in pairs."""

    support = _xor_support(args)
    if not support:
        return [()] if rhs == 1 else []
    if len(support) == 1:
        return [_unit_clause(support[0] if rhs == 1 else -support[0])]
    if len(auxiliaries) != len(support) - 1:
        raise ConstraintFieldError("XOR chain auxiliary count mismatch")
    clauses: list[tuple[int, ...]] = []
    current = support[0]
    for position in range(1, len(support)):
        target = auxiliaries[position - 1]
        clauses.extend(_gate_clauses("xor", (current, support[position]), target))
        current = target
    clauses.append(_unit_clause(current if rhs == 1 else -current))
    return clauses


def _cardinality_clauses(args: Sequence[int], minimum: int, maximum: int) -> list[tuple[int, ...]]:
    n = len(args)
    if not 0 <= minimum <= maximum <= n:
        raise ConstraintFieldError("cardinality bounds must satisfy 0 <= min <= max <= len(args)")
    required = 0
    if maximum < n:
        required += math.comb(n, maximum + 1)
    if minimum > 0:
        required += math.comb(n, n - minimum + 1)
    if required > _MAX_RELATION_CLAUSES:
        raise ConstraintFieldError("cardinality relation exceeds the relation clause capacity")
    clauses: list[tuple[int, ...]] = []
    if maximum < n:
        for subset in _combinations(args, maximum + 1):
            clauses.append(tuple(sorted((-value for value in subset), key=_literal_key)))
    if minimum > 0:
        for subset in _combinations(args, n - minimum + 1):
            clauses.append(tuple(sorted(subset, key=_literal_key)))
    return clauses


def _combinations(values: Sequence[int], size: int):
    from itertools import combinations

    return combinations(values, size)


@dataclass(frozen=True, slots=True)
class CircuitSpec:
    """One finite combinational Boolean DAG with boundary requirements."""

    inputs: tuple[str, ...]
    gates: tuple[Mapping[str, Any], ...] = ()
    assertions: tuple[tuple[str, int], ...] = ()
    relations: tuple[Mapping[str, Any], ...] = ()
    clauses: tuple[tuple[tuple[str, int], ...], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "circuit",
            "inputs": list(self.inputs),
            "gates": [dict(gate) for gate in self.gates],
            "assertions": [list(row) for row in self.assertions],
            "relations": [dict(row) for row in self.relations],
            "clauses": [[list(literal) for literal in clause] for clause in self.clauses],
        }


@dataclass(frozen=True, slots=True)
class TransitionProblem:
    """One bounded synchronous transition system with boundary requirements."""

    state: tuple[str, ...]
    inputs: tuple[str, ...]
    gates: tuple[Mapping[str, Any], ...]
    next_state: tuple[tuple[str, str], ...]
    horizon: int
    initial: tuple[tuple[str, int], ...] = ()
    input_assertions: tuple[tuple[int, str, int], ...] = ()
    final: tuple[tuple[str, int], ...] = ()
    relations: tuple[Mapping[str, Any], ...] = ()
    clauses: tuple[tuple[tuple[str, int] | tuple[str, int, int], ...], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": "transition",
            "state": list(self.state),
            "inputs": list(self.inputs),
            "gates": [dict(gate) for gate in self.gates],
            "next_state": [list(row) for row in self.next_state],
            "horizon": self.horizon,
            "initial": [list(row) for row in self.initial],
            "input_assertions": [list(row) for row in self.input_assertions],
            "final": [list(row) for row in self.final],
            "relations": [dict(row) for row in self.relations],
            "clauses": [[list(literal) for literal in clause] for clause in self.clauses],
        }


@dataclass(frozen=True, slots=True)
class ConstraintFieldProfile:
    """Fixed storage and work geometry for one constraint field."""

    max_variables: int
    max_clauses: int
    max_transitions: int = 10_000
    max_learned_clauses: int = 128
    max_proof_bytes: int = 262_144
    max_field_bytes: int = 134_217_728
    mode: str = "conflict"
    controller: bool = False
    controller_size: int = 64
    max_hybrid_lines: int = 4_096
    max_hybrid_transitions: int = 4_096
    max_parity_width: int = 8
    max_resolution_inferences: int = 2_048
    max_augmentations: int = 64
    max_augmentation_arity: int = 1

    def __post_init__(self) -> None:
        for name in (
            "max_variables",
            "max_clauses",
            "max_transitions",
            "max_proof_bytes",
            "max_field_bytes",
            "controller_size",
            "max_hybrid_lines",
            "max_hybrid_transitions",
            "max_parity_width",
        ):
            _exact_integer(getattr(self, name), name, minimum=1)
        _exact_integer(self.max_learned_clauses, "max_learned_clauses")
        _exact_integer(self.max_augmentations, "max_augmentations")
        _exact_integer(self.max_resolution_inferences, "max_resolution_inferences")
        _exact_integer(self.max_augmentation_arity, "max_augmentation_arity", minimum=1)
        if self.max_augmentation_arity > _MAX_AUGMENTATION_ARITY:
            raise ConstraintFieldError(
                f"max_augmentation_arity exceeds the supported bound {_MAX_AUGMENTATION_ARITY}"
            )
        if not isinstance(self.controller, bool):
            raise ConstraintFieldError("controller must be a boolean")
        if self.mode not in _MODE_NAMES:
            raise ConstraintFieldError("mode must be one of local, conflict, algebraic")
        if self.mode == "local" and self.controller:
            raise ConstraintFieldError(
                "local mode never schedules a decision, so it cannot carry a controller"
            )
        if self.max_variables > _SAFE_INTEGER or self.max_clauses > _SAFE_INTEGER:
            raise ConstraintFieldError("profile exceeds exact address capacity")

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical({"layout": _LAYOUT, **asdict(self)})).hexdigest()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CompiledConstraintProblem:
    """Canonical compiled source bound to its digest."""

    payload: Mapping[str, Any]
    sha256: str

    def __post_init__(self) -> None:
        required = {
            "schema",
            "kind",
            "source",
            "variables",
            "signals",
            "witness_signals",
            "clauses",
            "native_relations",
            "work",
        }
        if set(self.payload) != required or self.payload.get("schema") != PROBLEM_SCHEMA:
            raise ConstraintFieldError("compiled problem payload is not canonical")
        _exact_integer(self.payload.get("variables"), "compiled variables", minimum=1)
        expected = hashlib.sha256(_canonical(dict(self.payload))).hexdigest()
        if self.sha256 != expected:
            raise ConstraintFieldError("compiled problem digest mismatch")

    def as_dict(self) -> dict[str, Any]:
        return {**dict(self.payload), "sha256": self.sha256}

    @property
    def variables(self) -> int:
        return int(self.payload["variables"])

    @property
    def clauses(self) -> tuple[tuple[int, ...], ...]:
        return tuple(tuple(clause) for clause in self.payload["clauses"])

    @property
    def witness_signals(self) -> tuple[tuple[str, int], ...]:
        return tuple((str(label), int(identifier)) for label, identifier in self.payload["witness_signals"])


def _compiled(payload: Mapping[str, Any]) -> CompiledConstraintProblem:
    canonical = {key: payload[key] for key in sorted(payload)}
    return CompiledConstraintProblem(canonical, hashlib.sha256(_canonical(canonical)).hexdigest())


def _parse_gates(gates: Sequence[Mapping[str, Any]], names: str) -> dict[str, dict[str, Any]]:
    parsed: dict[str, dict[str, Any]] = {}
    for index, gate in enumerate(gates, 1):
        if not isinstance(gate, Mapping):
            raise ConstraintFieldError(f"{names} gate {index} must be an object")
        op = gate.get("op")
        if op not in _GATE_ARITY:
            raise ConstraintFieldError(f"{names} gate {index} has an unsupported operation")
        out = _signal_name(gate.get("out"), f"{names} gate {index} out")
        if out in parsed:
            raise ConstraintFieldError(f"{names} gate {out!r} is defined twice")
        raw_args = gate.get("args")
        if not isinstance(raw_args, (list, tuple)):
            raise ConstraintFieldError(f"{names} gate {out!r} args must be a sequence")
        arguments = tuple(_signal_name(value, f"{names} gate {out!r} arg") for value in raw_args)
        if len(arguments) != _GATE_ARITY[op]:
            raise ConstraintFieldError(f"{names} gate {out!r} has the wrong arity")
        entry: dict[str, Any] = {"op": op, "out": out, "args": arguments}
        if op == "const":
            value = gate.get("value")
            if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
                raise ConstraintFieldError(f"{names} constant {out!r} must be 0 or 1")
            entry["value"] = value
        elif "value" in gate:
            raise ConstraintFieldError(f"{names} gate {out!r} cannot carry a constant value")
        parsed[out] = entry
    return parsed


def _topological_order(gates: Mapping[str, Mapping[str, Any]], names: str) -> list[str]:
    remaining = {
        name: {argument for argument in gate["args"] if argument in gates}
        for name, gate in gates.items()
    }
    dependents: dict[str, list[str]] = {name: [] for name in gates}
    for name, dependencies in remaining.items():
        for dependency in dependencies:
            dependents[dependency].append(name)
    ready = [name for name in gates if not remaining[name]]
    heapq.heapify(ready)
    order: list[str] = []
    while ready:
        name = heapq.heappop(ready)
        order.append(name)
        for dependent in sorted(dependents[name]):
            remaining[dependent].discard(name)
            if not remaining[dependent]:
                heapq.heappush(ready, dependent)
    if len(order) != len(gates):
        raise ConstraintFieldError(f"{names} gate graph contains a cycle")
    return order


def _assertion_rows(rows: Sequence[Any], names: str) -> list[tuple[str, int]]:
    parsed: list[tuple[str, int]] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, (list, tuple)) or len(row) != 2:
            raise ConstraintFieldError(f"{names} assertion {index} must be a (signal, bit) pair")
        signal = _signal_name(row[0], f"{names} assertion {index} signal")
        bit = row[1]
        if isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1):
            raise ConstraintFieldError(f"{names} assertion {index} bit must be 0 or 1")
        parsed.append((signal, bit))
    return parsed


def _relation_rows(rows: Sequence[Any], names: str) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, Mapping):
            raise ConstraintFieldError(f"{names} relation {index} must be an object")
        kind = row.get("kind")
        raw_args = row.get("args")
        if not isinstance(raw_args, (list, tuple)):
            raise ConstraintFieldError(f"{names} relation {index} args must be a sequence")
        arguments = tuple(_signal_name(value, f"{names} relation {index} arg") for value in raw_args)
        if kind == "xor":
            rhs = row.get("rhs")
            if isinstance(rhs, bool) or not isinstance(rhs, int) or rhs not in (0, 1):
                raise ConstraintFieldError(f"{names} relation {index} rhs must be 0 or 1")
            parsed.append({"kind": "xor", "args": arguments, "rhs": rhs})
        elif kind == "cardinality":
            minimum = _exact_integer(row.get("min"), f"{names} relation {index} min")
            maximum = _exact_integer(row.get("max"), f"{names} relation {index} max")
            if maximum > len(arguments):
                raise ConstraintFieldError(f"{names} relation {index} max exceeds its arity")
            if len(set(arguments)) != len(arguments):
                raise ConstraintFieldError(f"{names} relation {index} repeats an argument")
            parsed.append({"kind": "cardinality", "args": arguments, "min": minimum, "max": maximum})
        else:
            raise ConstraintFieldError(f"{names} relation {index} has an unsupported kind")
    return parsed


def _source_clauses(
    rows: Sequence[Any],
    names: str,
    *,
    time_annotated: bool = False,
) -> list[list[list[Any]]]:
    """Parse clause rows; transition rows carry the documented optional time."""

    parsed: list[list[list[Any]]] = []
    for index, clause in enumerate(rows, 1):
        if not isinstance(clause, (list, tuple)):
            raise ConstraintFieldError(f"{names} clause {index} must be a sequence")
        literals: list[list[Any]] = []
        for literal in clause:
            shape = (2, 3) if time_annotated else (2,)
            if not isinstance(literal, (list, tuple)) or len(literal) not in shape:
                expected = "(signal, polarity[, time])" if time_annotated else "(signal, polarity)"
                raise ConstraintFieldError(
                    f"{names} clause {index} literals must be {expected} pairs"
                )
            signal = _signal_name(literal[0], f"{names} clause {index} signal")
            polarity = literal[1]
            if isinstance(polarity, bool) or not isinstance(polarity, int) or polarity not in (0, 1):
                raise ConstraintFieldError(f"{names} clause {index} polarity must be 0 or 1")
            row = [signal, polarity]
            if len(literal) == 3:
                row.append(_exact_integer(literal[2], f"{names} clause {index} time"))
            literals.append(row)
        parsed.append(literals)
    return parsed


def _canonical_source(kind: str, source: Mapping[str, Any]) -> dict[str, Any]:
    """Record the source with every encoding-irrelevant ordering removed.

    Declared order stays significant where it fixes the variable numbering
    (``inputs``, transition ``state``, relations) and is canonicalized
    everywhere else, so equivalent declarations share one digest.
    """

    record = {key: source[key] for key in source}
    clauses = record.get("clauses")
    if isinstance(clauses, (list, tuple)):
        normalized = {
            tuple(
                sorted(
                    (tuple(literal) for literal in clause),
                    key=lambda literal: (str(literal[0]), int(literal[1]), int(literal[2]) if len(literal) > 2 else -1),
                )
            )
            for clause in clauses
        }
        record["clauses"] = [list(clause) for clause in sorted(normalized, key=lambda row: (len(row), [[str(x) for x in literal] for literal in row]))]
    gates = record.get("gates")
    if isinstance(gates, (list, tuple)):
        record["gates"] = sorted((dict(gate) for gate in gates), key=lambda gate: str(gate.get("out", "")))
    for key, selectors in (
        ("assertions", 2),
        ("initial", 2),
        ("final", 2),
        ("input_assertions", 3),
    ):
        rows = record.get(key)
        if isinstance(rows, (list, tuple)) and all(
            isinstance(row, (list, tuple)) and len(row) == selectors for row in rows
        ):
            record[key] = [list(row) for row in sorted((tuple(row) for row in rows), key=lambda row: tuple(str(item) for item in row))]
    next_rows = record.get("next_state")
    if isinstance(next_rows, (list, tuple)):
        record["next_state"] = [list(row) for row in sorted((tuple(row) for row in next_rows), key=lambda row: str(row[0]))]
    return record


def _finish(
    kind: str,
    source: Mapping[str, Any],
    variables: int,
    signals: list[list[Any]],
    witness: list[list[Any]],
    clauses: list[tuple[int, ...]],
    relations: list[dict[str, Any]],
    work: dict[str, int],
) -> CompiledConstraintProblem:
    if variables < 1:
        variables = 1
        clauses = [*clauses, (1,)]
    normalized: set[tuple[int, ...]] = set()
    for clause in clauses:
        canonical = _normalize_clause(clause)
        if canonical is None:
            continue
        normalized.add(canonical)
    ordered = sorted(normalized, key=lambda clause: (len(clause), clause))
    if len(ordered) > _MAX_COMPILED_CLAUSES:
        raise ConstraintFieldError("compiled clause count exceeds the compiler capacity")
    payload = {
        "schema": PROBLEM_SCHEMA,
        "kind": kind,
        "source": _canonical_source(kind, source),
        "variables": int(variables),
        "signals": signals,
        "witness_signals": witness,
        "clauses": [list(clause) for clause in ordered],
        "native_relations": relations,
        "work": work,
    }
    return _compiled(payload)


def compile_circuit(
    source: CircuitSpec | Mapping[str, Any],
    *,
    profile: ConstraintFieldProfile | None = None,
) -> CompiledConstraintProblem:
    """Compile one combinational circuit with its boundary requirements."""

    raw = source.as_dict() if isinstance(source, CircuitSpec) else dict(source)
    if raw.get("kind") != "circuit":
        raise ConstraintFieldError("circuit source must declare kind 'circuit'")
    inputs = tuple(_signal_name(value, "circuit input") for value in raw["inputs"])
    if len(set(inputs)) != len(inputs):
        raise ConstraintFieldError("circuit inputs must be unique")
    gates = _parse_gates(raw["gates"], "circuit")
    for name in gates:
        if name in inputs:
            raise ConstraintFieldError(f"circuit signal {name!r} is both input and gate")
    order = _topological_order(gates, "circuit")

    identifiers: dict[str, int] = {}
    signals: list[list[Any]] = []
    for name in inputs:
        identifiers[name] = len(identifiers) + 1
        signals.append([name, identifiers[name]])
    for name in order:
        identifiers[name] = len(identifiers) + 1
        signals.append([name, identifiers[name]])

    clauses: list[tuple[int, ...]] = []
    gate_clauses = 0
    for name in order:
        gate = gates[name]
        out = identifiers[name]
        if gate["op"] == "const":
            clauses.append(_unit_clause(out if gate["value"] == 1 else -out))
            gate_clauses += 1
        else:
            arguments = tuple(
                _identifier(identifiers, argument, f"circuit gate {name!r}") for argument in gate["args"]
            )
            expanded = _gate_clauses(gate["op"], arguments, out)
            gate_clauses += len(expanded)
            clauses.extend(expanded)

    assertions = _assertion_rows(raw["assertions"], "circuit")
    assertion_rows: set[tuple[int, ...]] = set()
    for signal, bit in assertions:
        if signal not in identifiers:
            raise ConstraintFieldError(f"circuit assertion references unknown signal {signal!r}")
        assertion_rows.add(_unit_clause(identifiers[signal] if bit == 1 else -identifiers[signal]))
    clauses.extend(sorted(assertion_rows, key=lambda clause: (len(clause), clause)))
    assertion_clauses = len(assertion_rows)

    relations: list[dict[str, Any]] = []
    relation_clauses = 0
    for index, relation in enumerate(_relation_rows(raw["relations"], "circuit")):
        row: dict[str, Any] = {"kind": relation["kind"], "source_index": index}
        arguments = tuple(_identifier(identifiers, name, "circuit relation") for name in relation["args"])
        row["args"] = list(arguments)
        if relation["kind"] == "xor":
            row["rhs"] = relation["rhs"]
            support = _xor_support(arguments)
            auxiliary = [
                len(identifiers) + position + 1
                for position in range(max(0, len(support) - 1))
            ]
            expanded = _xor_chain(arguments, relation["rhs"], auxiliary)
            relation_clauses += len(expanded)
            for position, identifier in enumerate(auxiliary):
                name = f"@xor:{index}:{position}"
                identifiers[name] = identifier
                signals.append([name, identifier])
            clauses.extend(expanded)
        else:
            row["min"] = relation["min"]
            row["max"] = relation["max"]
            expanded = _cardinality_clauses(arguments, relation["min"], relation["max"])
            relation_clauses += len(expanded)
            clauses.extend(expanded)
        relations.append(row)

    source_rows: set[tuple[int, ...]] = set()
    for clause in _source_clauses(raw["clauses"], "circuit"):
        literals: list[int] = []
        for signal, polarity in clause:
            if signal not in identifiers:
                raise ConstraintFieldError(f"circuit clause references unknown signal {signal!r}")
            literal = identifiers[signal]
            literals.append(literal if polarity == 1 else -literal)
        normalized = _normalize_clause(literals)
        if normalized is not None:
            source_rows.add(normalized)
    clauses.extend(sorted(source_rows, key=lambda clause: (len(clause), clause)))

    variables = len(identifiers)
    if variables >= 1:
        for identifier in identifiers.values():
            if identifier > variables:
                raise ConstraintFieldError("circuit variable allocation is inconsistent")
    witness = [[name, identifiers[name]] for name in inputs]
    work = {
        "inputs": len(inputs),
        "gates": len(order),
        "auxiliary_variables": max(0, len(identifiers) - len(inputs) - len(order)),
        "dummy_variables": 1 if not identifiers else 0,
        "gate_clauses": gate_clauses,
        "assertion_clauses": assertion_clauses,
        "relation_clauses": relation_clauses,
        "source_clauses": len(source_rows),
        "total_clauses": len(set(clauses)),
    }
    compiled = _finish("circuit", raw, variables, signals, witness, clauses, relations, work)
    _check_profile(compiled, profile)
    return compiled


def compile_transition_problem(
    source: TransitionProblem | Mapping[str, Any],
    *,
    profile: ConstraintFieldProfile | None = None,
) -> CompiledConstraintProblem:
    """Compile one bounded synchronous transition system with boundary requirements."""

    raw: dict[str, Any] = source.as_dict() if isinstance(source, TransitionProblem) else dict(source)
    if raw.get("kind") != "transition":
        raise ConstraintFieldError("transition source must declare kind 'transition'")
    state = tuple(_signal_name(value, "transition state") for value in raw["state"])
    inputs = tuple(_signal_name(value, "transition input") for value in raw["inputs"])
    if len(set(state)) != len(state) or len(set(inputs)) != len(inputs):
        raise ConstraintFieldError("transition state and input names must be unique")
    if set(state) & set(inputs):
        raise ConstraintFieldError("transition state and input names must be disjoint")
    horizon = _exact_integer(raw["horizon"], "transition horizon")
    if horizon > 4096:
        raise ConstraintFieldError("transition horizon exceeds the compiler bound")
    gates = _parse_gates(raw["gates"], "transition")
    for name in gates:
        if name in state or name in inputs:
            raise ConstraintFieldError(f"transition signal {name!r} is not a distinct gate")
    order = _topological_order(gates, "transition")

    next_rows: list[tuple[str, str]] = []
    for index, raw_row in enumerate(raw["next_state"], 1):
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != 2:
            raise ConstraintFieldError(f"transition next_state {index} must be a (state, signal) pair")
        target = _signal_name(raw_row[0], f"transition next_state {index} state")
        origin = _signal_name(raw_row[1], f"transition next_state {index} signal")
        next_rows.append((target, origin))
    if sorted(target for target, _ in next_rows) != sorted(state):
        raise ConstraintFieldError("transition next_state must cover every state name exactly once")
    for target, origin in next_rows:
        if origin not in gates and origin not in inputs and origin not in state:
            raise ConstraintFieldError(f"transition next_state references unknown signal {origin!r}")

    identifiers: dict[str, int] = {}
    signals: list[list[Any]] = []

    def allocate(name: str) -> int:
        identifiers[name] = len(identifiers) + 1
        signals.append([name, identifiers[name]])
        return identifiers[name]

    for time in range(horizon + 1):
        for name in state:
            allocate(f"s:{name}:{time}")
    for time in range(horizon):
        for name in inputs:
            allocate(f"i:{name}:{time}")

    def resolve(name: str, time: int) -> int:
        if name in inputs:
            if time >= horizon:
                raise ConstraintFieldError("transition input used past the horizon")
            return identifiers[f"i:{name}:{time}"]
        if name in state:
            return identifiers[f"s:{name}:{time}"]
        if name in gates:
            return identifiers[f"g:{name}:{time}"]
        raise ConstraintFieldError(f"transition gate argument references unknown signal {name!r}")

    clauses: list[tuple[int, ...]] = []
    for time in range(horizon):
        for name in order:
            gate = gates[name]
            out = allocate(f"g:{name}:{time}")
            if gate["op"] == "const":
                clauses.append(_unit_clause(out if gate["value"] == 1 else -out))
            else:
                arguments = tuple(resolve(argument, time) for argument in gate["args"])
                clauses.extend(_gate_clauses(gate["op"], arguments, out))
        for target, origin in next_rows:
            successor = identifiers[f"s:{target}:{time + 1}"]
            source_id = resolve(origin, time)
            clauses.append(tuple(sorted((-source_id, successor), key=_literal_key)))
            clauses.append(tuple(sorted((source_id, -successor), key=_literal_key)))

    assertion_rows: set[tuple[int, ...]] = set()
    initial_rows = _assertion_rows(raw["initial"], "transition initial")
    for name, bit in initial_rows:
        if name not in state:
            raise ConstraintFieldError(f"transition initial references unknown state {name!r}")
        literal = identifiers[f"s:{name}:0"]
        assertion_rows.add(_unit_clause(literal if bit == 1 else -literal))
    final_rows = _assertion_rows(raw["final"], "transition final")
    for name, bit in final_rows:
        if name not in state:
            raise ConstraintFieldError(f"transition final references unknown state {name!r}")
        literal = identifiers[f"s:{name}:{horizon}"]
        assertion_rows.add(_unit_clause(literal if bit == 1 else -literal))
    for index, raw_row in enumerate(raw["input_assertions"], 1):
        if not isinstance(raw_row, (list, tuple)) or len(raw_row) != 3:
            raise ConstraintFieldError(f"transition input assertion {index} must be a (time, input, bit) triple")
        time = _exact_integer(raw_row[0], f"transition input assertion {index} time")
        if time >= horizon:
            raise ConstraintFieldError(f"transition input assertion {index} exceeds the horizon")
        name = _signal_name(raw_row[1], f"transition input assertion {index} input")
        if name not in inputs:
            raise ConstraintFieldError(f"transition input assertion {index} references unknown input {name!r}")
        bit = raw_row[2]
        if isinstance(bit, bool) or not isinstance(bit, int) or bit not in (0, 1):
            raise ConstraintFieldError(f"transition input assertion {index} bit must be 0 or 1")
        literal = identifiers[f"i:{name}:{time}"]
        assertion_rows.add(_unit_clause(literal if bit == 1 else -literal))
    clauses.extend(sorted(assertion_rows, key=lambda clause: (len(clause), clause)))
    assertion_clauses = len(assertion_rows)

    relations: list[dict[str, Any]] = []
    relation_clauses = 0
    for index, relation in enumerate(_relation_rows(raw["relations"], "transition")):
        row: dict[str, Any] = {"kind": relation["kind"], "source_index": index}
        if relation["kind"] == "xor":
            row["rhs"] = relation["rhs"]
            for time in range(horizon):
                arguments = tuple(_resolve_signal(resolve, name, time, "transition relation") for name in relation["args"])
                support = _xor_support(arguments)
                auxiliary = [
                    len(identifiers) + position + 1
                    for position in range(max(0, len(support) - 1))
                ]
                expanded = _xor_chain(arguments, relation["rhs"], auxiliary)
                relation_clauses += len(expanded)
                for position, identifier in enumerate(auxiliary):
                    name = f"@xor:{time}:{index}:{position}"
                    identifiers[name] = identifier
                    signals.append([name, identifier])
                clauses.extend(expanded)
        else:
            row["min"] = relation["min"]
            row["max"] = relation["max"]
            for time in range(horizon):
                arguments = tuple(_resolve_signal(resolve, name, time, "transition relation") for name in relation["args"])
                expanded = _cardinality_clauses(arguments, relation["min"], relation["max"])
                relation_clauses += len(expanded)
                clauses.extend(expanded)
        relations.append(row)

    source_rows: set[tuple[int, ...]] = set()
    for clause in _source_clauses(raw["clauses"], "transition", time_annotated=True):
        literals = []
        for name, polarity, time in _time_literals(clause):
            identifier = _resolve_signal(resolve, name, time, "transition clause")
            literals.append(identifier if polarity == 1 else -identifier)
        normalized = _normalize_clause(literals)
        if normalized is not None:
            source_rows.add(normalized)
    clauses.extend(sorted(source_rows, key=lambda clause: (len(clause), clause)))

    variables = len(identifiers)
    witness = [[f"{name}@0", identifiers[f"s:{name}:0"]] for name in state]
    witness.extend(
        [f"{name}@{time}", identifiers[f"i:{name}:{time}"]]
        for time in range(horizon)
        for name in inputs
    )
    work = {
        "state": len(state),
        "inputs": len(inputs),
        "gates": len(order),
        "horizon": horizon,
        "auxiliary_variables": max(0, len(identifiers) - (len(state) * (horizon + 1)) - (len(inputs) * horizon) - (len(order) * horizon)),
        "dummy_variables": 1 if not identifiers else 0,
        "assertion_clauses": assertion_clauses,
        "relation_clauses": relation_clauses,
        "source_clauses": len(source_rows),
        "total_clauses": len(set(clauses)),
    }
    compiled = _finish("transition", raw, variables, signals, witness, clauses, relations, work)
    _check_profile(compiled, profile)
    return compiled


def _time_literals(clause: Sequence[Any]) -> list[tuple[str, int, int]]:
    """Transition source clauses carry optional third entries ``time``."""

    rows: list[tuple[str, int, int]] = []
    for literal in clause:
        if not isinstance(literal, (list, tuple)) or len(literal) not in (2, 3):
            raise ConstraintFieldError("transition clause literals must be (signal, polarity[, time])")
        signal = _signal_name(literal[0], "transition clause signal")
        polarity = literal[1]
        if isinstance(polarity, bool) or not isinstance(polarity, int) or polarity not in (0, 1):
            raise ConstraintFieldError("transition clause polarity must be 0 or 1")
        time = 0
        if len(literal) == 3:
            time = _exact_integer(literal[2], "transition clause time")
        rows.append((signal, polarity, time))
    return rows


def _check_profile(compiled: CompiledConstraintProblem, profile: ConstraintFieldProfile | None) -> None:
    if profile is None:
        return
    if compiled.variables > profile.max_variables:
        raise ConstraintFieldError("compiled variable count exceeds the profile")
    if len(compiled.clauses) > profile.max_clauses:
        raise ConstraintFieldError("compiled clause count exceeds the profile")


def _parse_compiled(source: CompiledConstraintProblem | Mapping[str, Any]) -> CompiledConstraintProblem:
    if isinstance(source, CompiledConstraintProblem):
        return source
    if not isinstance(source, Mapping) or source.get("schema") != PROBLEM_SCHEMA:
        raise ConstraintFieldError("compiled source is not a constraint problem payload")
    payload = {key: source[key] for key in source if key != "sha256"}
    digest = source.get("sha256")
    if digest is not None and digest != hashlib.sha256(_canonical(payload)).hexdigest():
        raise ConstraintFieldError("compiled source digest mismatch")
    return _compiled(payload)


@dataclass(frozen=True, slots=True)
class ConstraintFieldState:
    """Immutable constraint field state: source, search tensors, journal, counters."""

    compiled: CompiledConstraintProblem
    profile_sha256: str
    backend_profile: Mapping[str, Any] | None
    hybrid_profile: Mapping[str, Any] | None
    status: str
    reason: str
    journal: bytes
    backend: ClauseFieldState | None
    hybrid: HybridInferenceState | None
    controller: Any | None
    controller_ticks: int
    controller_selections: int

    @property
    def nbytes(self) -> int:
        backend = 0 if self.backend is None else self.backend.nbytes
        hybrid = 0 if self.hybrid is None else self.hybrid.nbytes
        controller = 0 if self.controller is None else self.controller.nbytes
        return int(backend + hybrid + controller + len(self.journal))


def _journal_lines(journal: bytes) -> list[dict[str, Any]]:
    if not journal:
        return []
    rows: list[dict[str, Any]] = []
    for line in journal.split(b"\n"):
        if not line:
            continue
        rows.append(json.loads(line.decode("utf-8")))
    return rows


def _journal_event(row: Mapping[str, Any]) -> bytes:
    return _canonical(dict(row)) + b"\n"


class ConstraintField:
    """Fixed transition law over compiled constraint sources."""

    def __init__(self, profile: ConstraintFieldProfile):
        if not isinstance(profile, ConstraintFieldProfile):
            raise ConstraintFieldError("profile must be a ConstraintFieldProfile")
        self.profile = profile
        self._dynamics_module: Any | None = None

    # -- construction ----------------------------------------------------

    def _dynamics(self):
        module = self._dynamics_module
        if module is None:
            try:
                from cassi_constraint_dynamics import (
                    ExcitableConstraintController,
                    ExcitableConstraintProfile,
                )
            except ImportError as exc:  # pragma: no cover - import guard
                raise ConstraintFieldError("the excitable controller module is unavailable") from exc
            module = (ExcitableConstraintController, ExcitableConstraintProfile)
            self._dynamics_module = module
        return module

    def _backend_reserve(self, compiled: CompiledConstraintProblem) -> int:
        """Augmentation capacity: the declared cap, bounded by clause capacity."""

        if self.profile.mode != "algebraic":
            return 0
        return min(
            self.profile.max_augmentations,
            max(0, self.profile.max_clauses - len(compiled.clauses)),
        )

    def _backend_profile(self, compiled: CompiledConstraintProblem) -> ClauseFieldProfile:
        original = len(compiled.clauses) + self._backend_reserve(compiled)
        if original > self.profile.max_clauses:
            raise ConstraintFieldError("clause capacity cannot hold the source and augmentations")
        profile = ClauseFieldProfile(
            max_variables=compiled.variables,
            max_original_clauses=max(1, original),
            max_clause_width=max(1, compiled.variables),
            max_learned_clauses=max(1, self.profile.max_learned_clauses),
            max_transitions=self.profile.max_transitions,
        )
        if profile.state_bytes > self.profile.max_field_bytes:
            raise ConstraintFieldError("backend field exceeds the declared field byte bound")
        return profile

    def _hybrid_profile(self, compiled: CompiledConstraintProblem) -> HybridInferenceProfile:
        profile = HybridInferenceProfile(
            max_variables=compiled.variables,
            max_original_clauses=max(1, len(compiled.clauses)),
            max_lines=max(self.profile.max_hybrid_lines, max(1, len(compiled.clauses))),
            max_extensions=0,
            max_parity_width=min(self.profile.max_parity_width, max(3, compiled.variables)),
            max_resolution_inferences=self.profile.max_resolution_inferences,
            max_transitions=self.profile.max_hybrid_transitions,
        )
        if profile.state_bytes > self.profile.max_field_bytes:
            raise ConstraintFieldError("hybrid field exceeds the declared field byte bound")
        return profile

    def initial(self, source: CompiledConstraintProblem | Mapping[str, Any]) -> ConstraintFieldState:
        compiled = _parse_compiled(source)
        if compiled.variables > self.profile.max_variables:
            raise ConstraintFieldError("compiled variable count exceeds the profile")
        if len(compiled.clauses) > self.profile.max_clauses:
            raise ConstraintFieldError("compiled clause count exceeds the profile")
        controller = None
        if self.profile.controller:
            controller_class, controller_profile_class = self._dynamics()
            controller = controller_class(
                controller_profile_class(size=self.profile.controller_size)
            ).initial()
        if self.profile.mode == "algebraic" and not _holds_empty_clause(compiled.clauses):
            hybrid_profile = self._hybrid_profile(compiled)
            hybrid_field = HybridInferenceField(hybrid_profile)
            hybrid = hybrid_field.initial(compiled.clauses, variable_count=compiled.variables)
            return ConstraintFieldState(
                compiled=compiled,
                profile_sha256=self.profile.fingerprint,
                backend_profile=asdict(self._backend_profile(compiled)),
                hybrid_profile=asdict(hybrid_profile),
                status="running",
                reason="prepass",
                journal=b"",
                backend=None,
                hybrid=hybrid,
                controller=controller,
                controller_ticks=0,
                controller_selections=0,
            )
        backend_profile = self._backend_profile(compiled)
        backend = ClauseField(backend_profile).initial(compiled.clauses, variable_count=compiled.variables)
        return ConstraintFieldState(
            compiled=compiled,
            profile_sha256=self.profile.fingerprint,
            backend_profile=asdict(backend_profile),
            hybrid_profile=None,
            status="running",
            reason="search",
            journal=b"",
            backend=backend,
            hybrid=None,
            controller=controller,
            controller_ticks=0,
            controller_selections=0,
        )

    def _backend_field(self, state: ConstraintFieldState) -> ClauseField:
        if state.backend_profile is None:
            raise ConstraintFieldError("constraint state has no backend profile")
        return ClauseField(ClauseFieldProfile(**dict(state.backend_profile)))

    def _hybrid_field(self, state: ConstraintFieldState) -> HybridInferenceField:
        if state.hybrid_profile is None:
            raise ConstraintFieldError("constraint state has no hybrid profile")
        return HybridInferenceField(HybridInferenceProfile(**dict(state.hybrid_profile)))

    # -- transitions -----------------------------------------------------

    def _replace(self, state: ConstraintFieldState, **changes: Any) -> ConstraintFieldState:
        values = {
            "compiled": state.compiled,
            "profile_sha256": state.profile_sha256,
            "backend_profile": state.backend_profile,
            "hybrid_profile": state.hybrid_profile,
            "status": state.status,
            "reason": state.reason,
            "journal": state.journal,
            "backend": state.backend,
            "hybrid": state.hybrid,
            "controller": state.controller,
            "controller_ticks": state.controller_ticks,
            "controller_selections": state.controller_selections,
            **changes,
        }
        return ConstraintFieldState(**values)

    def step(self, state: ConstraintFieldState) -> tuple[ConstraintFieldState, Mapping[str, Any]]:
        self.validate(state)
        before = self.state_sha256(state)
        if state.status != "running":
            return state, {
                "schema": STEP_SCHEMA,
                "action": "terminal",
                "status": state.status,
                "reason": state.reason,
                "previous_state_sha256": before,
                "state_sha256": before,
                "state_unchanged": True,
            }
        if state.hybrid is not None and state.backend is None:
            successor, event = self._prepass_step(state, before)
        else:
            successor, event = self._search_step(state, before)
        event["state_sha256"] = self.state_sha256(successor)
        return successor, {**event, "previous_state_sha256": before, "state_unchanged": False}

    def _prepass_step(
        self,
        state: ConstraintFieldState,
        before: str,
    ) -> tuple[ConstraintFieldState, dict[str, Any]]:
        assert state.hybrid is not None
        hybrid_field = self._hybrid_field(state)
        hybrid, outcome = hybrid_field.solve(state.hybrid)
        proof = hybrid_field.proof(hybrid)
        journal = state.journal + _journal_event(
            {
                "type": "hybrid-prepass",
                "status": proof["status"],
                "lines": len(proof["lines"]),
                "root_line": proof["root_line"],
            }
        )
        if proof["status"] == "unsat" or proof["root_line"] is not None:
            if proof["root_line"] is None:
                raise ConstraintFieldError("hybrid refutation is not backed by a root line")
            successor = self._replace(
                state,
                hybrid=hybrid,
                journal=journal,
                status="unsat",
                reason="hybrid-refutation",
            )
            return successor, {
                "schema": STEP_SCHEMA,
                "action": "hybrid-refutation",
                "status": "unsat",
                "reason": "hybrid-refutation",
                "hybrid": outcome,
            }
        facts, contradiction = _hybrid_facts(
            proof,
            state.compiled.variables,
            max_arity=self.profile.max_augmentation_arity,
        )
        if contradiction:
            raise ConstraintFieldError("hybrid proof carries a contradiction without UNSAT status")
        if state.backend_profile is None:
            raise ConstraintFieldError("prepass state has no reserved backend profile")
        reserve = max(
            0,
            int(state.backend_profile["max_original_clauses"]) - len(state.compiled.clauses),
        )
        rows: list[dict[str, Any]] = []
        seen = {clause for clause in state.compiled.clauses}
        for fact in facts:
            clause = tuple(fact["clause"])
            if clause in seen:
                continue
            if len(rows) >= reserve:
                break
            seen.add(clause)
            rows.append({"clause": list(clause), "via": fact["via"], "line_id": fact["line_id"]})
        clauses = list(state.compiled.clauses) + [tuple(row["clause"]) for row in rows]
        journal += _journal_event({"type": "augmentations", "rows": rows})
        backend_field = self._backend_field(state)
        backend = backend_field.initial(clauses, variable_count=state.compiled.variables)
        successor = self._replace(
            state,
            hybrid=hybrid,
            backend=backend,
            journal=journal,
            status="running",
            reason="search",
        )
        return successor, {
            "schema": STEP_SCHEMA,
            "action": "augment",
            "status": "running",
            "reason": "search",
            "augmentations": rows,
            "hybrid": proof["status"],
        }

    def _search_step(
        self,
        state: ConstraintFieldState,
        before: str,
    ) -> tuple[ConstraintFieldState, dict[str, Any]]:
        assert state.backend is not None
        backend_field = self._backend_field(state)
        controller_receipt: Mapping[str, Any] | None = None
        controller = state.controller
        ticks = state.controller_ticks
        selections = state.controller_selections
        if self.profile.controller and controller is not None:
            context = backend_field.decision_context(state.backend)
            if context["pending"] == "decide":
                controller_class, _ = self._dynamics()
                driver = controller_class(self._controller_descriptor_profile(state))
                successor_controller, literal, receipt = driver.advance(
                    controller,
                    positive=context["positive"],
                    negative=context["negative"],
                    eligible=context["eligible"],
                )
                controller = successor_controller
                controller_receipt = receipt
                ticks += int(receipt["work"]["ticks"])
                selections += 0 if literal is None else 1
                if literal is None:
                    raise ConstraintFieldError("controller produced no literal for a pending decision")
                successor_backend, outcome = backend_field.step(state.backend, decision_literal=literal)
            else:
                successor_backend, outcome = backend_field.step(state.backend)
        elif self.profile.mode == "local":
            successor_backend, outcome = backend_field.step(state.backend, propagation_only=True)
        else:
            successor_backend, outcome = backend_field.step(state.backend)

        journal = state.journal
        backend_status = backend_field.status(successor_backend)
        status = state.status
        reason = state.reason
        if outcome["action"] == "unsat":
            status, reason = "unsat", ("propagation-refutation" if self.profile.mode == "local" else "resolution-refutation")
        elif outcome["action"] == "sat":
            status, reason = "sat", "model"
        elif outcome["action"] == "exhaust":
            status, reason = "exhausted", "transition-budget"
        elif outcome["action"] == "stalled":
            status, reason = "exhausted", "local-stall"
        if backend_status == "exhausted" and status == "running":
            status, reason = "exhausted", "backend-exhausted"
        conflict = outcome.get("conflict_proof")
        if conflict is not None:
            if status == "unsat" or status == "running":
                event = _journal_event({"type": "conflict", "proof": conflict})
                if len(journal) + len(event) > self.profile.max_proof_bytes:
                    status, reason = "exhausted", "proof-journal-capacity"
                else:
                    journal = journal + event
        successor = self._replace(
            state,
            backend=successor_backend,
            controller=controller,
            journal=journal,
            status=status,
            reason=reason,
            controller_ticks=ticks,
            controller_selections=selections,
        )
        return successor, {
            "schema": STEP_SCHEMA,
            "action": str(outcome["action"]),
            "status": status,
            "reason": reason,
            "selected_literal": outcome.get("selected_literal"),
            "controller": None if controller_receipt is None else dict(controller_receipt),
            "journal_bytes": len(journal),
        }

    def intervene(
        self,
        state: ConstraintFieldState,
        *,
        variable: int,
        excitation: int,
    ) -> tuple[ConstraintFieldState, Mapping[str, Any]]:
        """Clamp one controller site's excitation as a deliberate, journaled intervention.

        The write is exactly bounded (one excitation lane plus the intervention
        counter), the successor digest is recomputed, and the journal records the
        clamp so a resumed or replayed run accounts for it.
        """

        self.validate(state)
        if not self.profile.controller or state.controller is None:
            raise ConstraintFieldError("intervention requires an enabled controller")
        if state.status != "running":
            raise ConstraintFieldError("intervention requires a running field")
        controller_class, _ = self._dynamics()
        driver = controller_class(self._controller_descriptor_profile(state))
        successor_controller = driver.intervene(
            state.controller,
            variable=variable,
            excitation=excitation,
        )
        event = _journal_event(
            {
                "schema": INTERVENTION_SCHEMA,
                "type": "intervention",
                "variable": int(variable),
                "excitation": int(excitation),
            }
        )
        if len(state.journal) + len(event) > self.profile.max_proof_bytes:
            raise ConstraintFieldError("intervention exceeds the proof journal byte bound")
        successor = self._replace(
            state,
            controller=successor_controller,
            journal=state.journal + event,
        )
        return successor, {
            "schema": STEP_SCHEMA,
            "action": "intervention",
            "status": state.status,
            "reason": state.reason,
            "variable": int(variable),
            "excitation": int(excitation),
            "previous_state_sha256": self.state_sha256(state),
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }

    def _controller_descriptor_profile(self, state: ConstraintFieldState):
        _, controller_profile_class = self._dynamics()
        return controller_profile_class(size=self.profile.controller_size)

    # -- results ---------------------------------------------------------

    def solve(self, state: ConstraintFieldState) -> tuple[ConstraintFieldState, Mapping[str, Any]]:
        current = state
        while self.status(current) == "running":
            current, _ = self.step(current)
        return current, self.result(current)

    def status(self, state: ConstraintFieldState) -> str:
        if not isinstance(state, ConstraintFieldState):
            raise ConstraintFieldError("state must be a ConstraintFieldState")
        if state.status not in _STATUS_NAMES:
            raise ConstraintFieldError("state status is invalid")
        return state.status

    def _prepass_work(self, state: ConstraintFieldState) -> dict[str, Any] | None:
        """Receipt for the algebraic prepass: absent, running, complete, or skipped."""

        if self.profile.mode != "algebraic":
            return None
        if state.hybrid is None:
            return {"status": "skipped", "reason": "compiled-contradiction"}
        if state.backend is None:
            return {"status": "running"}
        return {"status": "complete"}

    def result(self, state: ConstraintFieldState) -> dict[str, Any]:
        self.validate(state)
        assignment: list[int] | None = None
        witness: dict[str, int] | None = None
        backend_clauses: list[list[int]] | None = None
        learned: list[list[int]] = []
        resolution_proof: dict[str, Any] | None = None
        hybrid_proof: dict[str, Any] | None = None
        search_ledger: dict[str, Any] | None = None
        if state.backend is not None:
            backend_field = self._backend_field(state)
            backend_clauses = [list(clause) for clause in backend_field.clauses(state.backend, learned=False)]
            learned = [list(clause) for clause in backend_field.clauses(state.backend, learned=True)]
            search_ledger = backend_field.inspect(state.backend)["resource_ledger"]
            values = backend_field.assignment(state.backend)
            assignment = list(values)
            if state.status == "sat":
                witness = {
                    label: (1 if values[identifier - 1] == 1 else 0)
                    for label, identifier in state.compiled.witness_signals
                }
            if state.status == "unsat" and state.reason in ("resolution-refutation", "propagation-refutation"):
                conflicts = [
                    row["proof"]
                    for row in _journal_lines(state.journal)
                    if row.get("type") == "conflict"
                ]
                resolution_proof = build_proof_certificate(conflicts, status="unsat")
        if state.hybrid is not None:
            hybrid_field = self._hybrid_field(state)
            hybrid_proof = hybrid_field.proof(state.hybrid)
        augmentations = [
            row
            for row in _journal_lines(state.journal)
            if row.get("type") == "augmentations"
        ]
        hybrid_work = None
        if state.hybrid is not None:
            hybrid_inspect = self._hybrid_field(state).inspect(state.hybrid)
            hybrid_work = {
                "status": hybrid_inspect["status"],
                "proof_lines": hybrid_inspect["proof_lines"],
                "resource_ledger": hybrid_inspect["resource_ledger"],
            }
        return {
            "schema": RESULT_SCHEMA,
            "compiled": state.compiled.as_dict(),
            "profile": self.profile.as_dict(),
            "profile_sha256": state.profile_sha256,
            "status": state.status,
            "reason": state.reason,
            "assignment": assignment,
            "witness": witness,
            "backend_clauses": backend_clauses,
            "augmentations": augmentations[0]["rows"] if augmentations else [],
            "learned_clauses": learned,
            "resolution_proof": resolution_proof,
            "hybrid_proof": hybrid_proof,
            "work": {
                "compile": dict(state.compiled.payload["work"]),
                "prepass": self._prepass_work(state),
                "hybrid": hybrid_work,
                "search": search_ledger,
                "controller": {
                    "ticks": int(state.controller_ticks),
                    "selections": int(state.controller_selections),
                    "interventions": sum(
                        1
                        for row in _journal_lines(state.journal)
                        if row.get("type") == "intervention"
                    ),
                    "enabled": bool(self.profile.controller),
                },
                "journal_bytes": len(state.journal),
                "augmentations": len(augmentations[0]["rows"]) if augmentations else 0,
            },
            "checkpoint": {
                "schema": DESCRIPTOR_SCHEMA,
                "profile_sha256": state.profile_sha256,
                "state_sha256": self.state_sha256(state),
                "field_bytes": state.nbytes,
                "journal_bytes": len(state.journal),
            },
            "state_sha256": self.state_sha256(state),
        }

    # -- state codec -----------------------------------------------------

    def state_sha256(self, state: ConstraintFieldState) -> str:
        controller_value = state.controller
        if state.backend is not None:
            backend_digest: str | None = self._backend_field(state).state_sha256(state.backend)
        else:
            backend_digest = None
        if state.hybrid is not None:
            hybrid_digest: str | None = self._hybrid_field(state).state_sha256(state.hybrid)
        else:
            hybrid_digest = None
        if controller_value is None:
            controller_digest: str | None = None
        else:
            controller_digest = self._controller_sha256(state)
        payload = {
            "schema": STATE_SCHEMA,
            "profile_sha256": state.profile_sha256,
            "compiled": state.compiled.sha256,
            "backend_profile": None if state.backend_profile is None else dict(state.backend_profile),
            "hybrid_profile": None if state.hybrid_profile is None else dict(state.hybrid_profile),
            "status": state.status,
            "reason": state.reason,
            "journal_sha256": hashlib.sha256(state.journal).hexdigest(),
            "journal_bytes": len(state.journal),
            "backend": backend_digest,
            "hybrid": hybrid_digest,
            "controller": controller_digest,
            "controller_ticks": int(state.controller_ticks),
            "controller_selections": int(state.controller_selections),
        }
        return hashlib.sha256(_canonical(payload)).hexdigest()

    def _controller_sha256(self, state: ConstraintFieldState) -> str:
        controller_value = state.controller
        if controller_value is None:
            raise ConstraintFieldError("state carries no controller tensor")
        controller_class, _ = self._dynamics()
        driver = controller_class(self._controller_descriptor_profile(state))
        return str(driver.state_sha256(controller_value))

    def validate(self, state: ConstraintFieldState) -> None:
        if not isinstance(state, ConstraintFieldState):
            raise ConstraintFieldError("state must be a ConstraintFieldState")
        if state.profile_sha256 != self.profile.fingerprint:
            raise ConstraintFieldError("state/profile mismatch")
        if state.status not in _STATUS_NAMES:
            raise ConstraintFieldError("state status is invalid")
        if not isinstance(state.journal, bytes):
            raise ConstraintFieldError("state journal must be bytes")
        if state.backend is not None:
            self._backend_field(state).validate(state.backend)
        if state.hybrid is not None:
            self._hybrid_field(state).validate(state.hybrid)
        if self.profile.controller and state.controller is not None:
            controller_class, _ = self._dynamics()
            controller_class(self._controller_descriptor_profile(state)).validate(state.controller)
        if self.profile.controller and state.controller is None:
            raise ConstraintFieldError("controller is enabled but the state carries none")

    def descriptor(self, state: ConstraintFieldState) -> dict[str, Any]:
        self.validate(state)
        payload: dict[str, Any] = {
            "schema": DESCRIPTOR_SCHEMA,
            "layout": _LAYOUT,
            "profile": self.profile.as_dict(),
            "profile_sha256": state.profile_sha256,
            "compiled": state.compiled.as_dict(),
            "backend_profile": None if state.backend_profile is None else dict(state.backend_profile),
            "hybrid_profile": None if state.hybrid_profile is None else dict(state.hybrid_profile),
            "status": state.status,
            "reason": state.reason,
            "journal_b64": base64.b64encode(state.journal).decode("ascii"),
            "controller_ticks": int(state.controller_ticks),
            "controller_selections": int(state.controller_selections),
            "backend": None if state.backend is None else self._backend_field(state).descriptor(state.backend),
            "hybrid": None if state.hybrid is None else self._hybrid_field(state).descriptor(state.hybrid),
            "controller": None if state.controller is None else self._controller_descriptor(state),
        }
        payload["state_sha256"] = self.state_sha256(state)
        return payload

    def _controller_descriptor(self, state: ConstraintFieldState) -> Mapping[str, Any]:
        controller_value = state.controller
        if controller_value is None:
            raise ConstraintFieldError("state carries no controller tensor")
        controller_class, _ = self._dynamics()
        driver = controller_class(self._controller_descriptor_profile(state))
        return driver.descriptor(controller_value)

    @classmethod
    def from_descriptor(cls, value: Mapping[str, Any]) -> tuple[ConstraintField, ConstraintFieldState]:
        required = {
            "schema",
            "layout",
            "profile",
            "profile_sha256",
            "compiled",
            "backend_profile",
            "hybrid_profile",
            "status",
            "reason",
            "journal_b64",
            "controller_ticks",
            "controller_selections",
            "backend",
            "hybrid",
            "controller",
            "state_sha256",
        }
        if not isinstance(value, Mapping) or set(value) != required:
            raise ConstraintFieldError("invalid constraint-field descriptor keys")
        if value["schema"] != DESCRIPTOR_SCHEMA or value["layout"] != _LAYOUT:
            raise ConstraintFieldError("unsupported constraint-field descriptor")
        try:
            profile = ConstraintFieldProfile(**dict(value["profile"]))
        except (TypeError, ConstraintFieldError) as exc:
            raise ConstraintFieldError("descriptor profile is invalid") from exc
        controller = cls(profile)
        if value["profile_sha256"] != profile.fingerprint:
            raise ConstraintFieldError("descriptor profile digest mismatch")
        compiled = _parse_compiled(value["compiled"])
        journal_value = value["journal_b64"]
        if not isinstance(journal_value, str):
            raise ConstraintFieldError("descriptor journal encoding is invalid")
        try:
            journal = base64.b64decode(journal_value, validate=True)
        except (ValueError, TypeError) as exc:
            raise ConstraintFieldError("descriptor journal encoding is invalid") from exc
        backend: ClauseFieldState | None = None
        if value["backend"] is not None:
            try:
                backend_field, backend = ClauseField.from_descriptor(value["backend"])
            except (ClauseFieldError, TypeError, KeyError, ValueError) as exc:
                raise ConstraintFieldError("descriptor backend block is invalid") from exc
            _ = backend_field.state_sha256(backend)
        hybrid: HybridInferenceState | None = None
        if value["hybrid"] is not None:
            try:
                hybrid_field, hybrid = HybridInferenceField.from_descriptor(value["hybrid"])
            except (HybridInferenceError, TypeError, KeyError, ValueError) as exc:
                raise ConstraintFieldError("descriptor hybrid block is invalid") from exc
            _ = hybrid_field.state_sha256(hybrid)
        controller_state = None
        if value["controller"] is not None:
            controller_class, _ = controller._dynamics()
            _, controller_state = controller_class.from_descriptor(value["controller"])
        state = ConstraintFieldState(
            compiled=compiled,
            profile_sha256=profile.fingerprint,
            backend_profile=None if value["backend_profile"] is None else dict(value["backend_profile"]),
            hybrid_profile=None if value["hybrid_profile"] is None else dict(value["hybrid_profile"]),
            status=value["status"],
            reason=value["reason"],
            journal=journal,
            backend=backend,
            hybrid=hybrid,
            controller=controller_state,
            controller_ticks=_exact_integer(value["controller_ticks"], "descriptor controller ticks"),
            controller_selections=_exact_integer(value["controller_selections"], "descriptor controller selections"),
        )
        controller.validate(state)
        if value["state_sha256"] != controller.state_sha256(state):
            raise ConstraintFieldError("descriptor state digest mismatch")
        return controller, state


def _binary_pb_clauses(
    terms: Sequence[tuple[int, int]],
    rhs: int,
) -> list[list[int]]:
    """Exact two-term reading of a stored plane.

    A stored plane is the set of allowed assignments, so every assignment it
    falsifies yields one blocking clause, and a two-term plane has at most four.
    """

    (first, first_coefficient), (second, second_coefficient) = terms
    rows: list[list[int]] = []
    for first_value in (0, 1):
        for second_value in (0, 1):
            if first_coefficient * first_value + second_coefficient * second_value > rhs:
                rows.append(
                    [
                        first if first_value == 0 else -first,
                        second if second_value == 0 else -second,
                    ]
                )
    return rows


def _hybrid_facts(
    proof: Mapping[str, Any],
    variables: int,
    *,
    max_arity: int = 1,
) -> tuple[list[dict[str, Any]], bool]:
    """Extract entailed facts up to ``max_arity`` from an audited hybrid proof.

    Arity one is the singleton extraction the field has always used. Arity two
    additionally reads the binary consequences each line already carries: a
    two-literal clause line, the two clauses of a two-variable parity line, and
    the blocking clauses of a two-term plane. Every emitted clause is a
    consequence of the single line it is attributed to, which is what an auditor
    can check against that line's own relation.
    """

    facts: list[dict[str, Any]] = []
    contradiction = False
    for line_id, row in enumerate(proof["lines"], 1):
        kind = row.get("kind")
        if kind == "clause":
            literals = [int(value) for value in row.get("literals", [])]
            if not literals:
                contradiction = True
            elif len(literals) == 1:
                facts.append({"clause": [literals[0]], "via": "clause", "line_id": line_id})
            elif len(literals) == 2 and max_arity >= 2:
                facts.append({"clause": [literals[0], literals[1]], "via": "clause", "line_id": line_id})
        elif kind == "xor":
            support = [int(value) for value in row.get("variables", [])]
            rhs = int(row.get("rhs", 0))
            if not support:
                if rhs == 1:
                    contradiction = True
            elif len(support) == 1:
                facts.append(
                    {
                        "clause": [support[0] if rhs == 1 else -support[0]],
                        "via": "xor",
                        "line_id": line_id,
                    }
                )
            elif len(support) == 2 and max_arity >= 2:
                first, second = support
                parity = (
                    [[first, second], [-first, -second]]
                    if rhs == 1
                    else [[first, -second], [-first, second]]
                )
                facts.extend(
                    {"clause": clause, "via": "xor", "line_id": line_id} for clause in parity
                )
        elif kind == "pb":
            terms = [(int(variable), int(coefficient)) for variable, coefficient in row.get("terms", [])]
            rhs = int(row.get("rhs", 0))
            nonzero = [(variable, coefficient) for variable, coefficient in terms if coefficient]
            if not nonzero:
                if rhs < 0:
                    contradiction = True
            elif len(nonzero) == 1:
                # Stored planes read ``sum(coefficient * variable) <= rhs``.
                variable, coefficient = nonzero[0]
                if coefficient > 0:
                    if rhs < 0:
                        contradiction = True
                    elif rhs < coefficient:
                        facts.append({"clause": [-variable], "via": "pb", "line_id": line_id})
                elif rhs < coefficient:
                    contradiction = True
                elif rhs < 0:
                    facts.append({"clause": [variable], "via": "pb", "line_id": line_id})
            elif len(nonzero) == 2 and max_arity >= 2:
                for clause in _binary_pb_clauses(nonzero, rhs):
                    facts.append({"clause": clause, "via": "pb", "line_id": line_id})
        if contradiction:
            break
    for fact in facts:
        if len(fact["clause"]) > max_arity:
            raise ConstraintFieldError("hybrid proof fact exceeds the declared augmentation arity")
        for literal in fact["clause"]:
            value = int(literal)
            if value == 0 or abs(value) > variables:
                raise ConstraintFieldError("hybrid proof fact exceeds the original variables")
    root = proof.get("root_line")
    if (root is not None) != contradiction:
        raise ConstraintFieldError("hybrid proof contradiction does not match its root line")
    return facts, contradiction


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


def _regional_json(value: Any) -> Any:
    """Return a detached JSON value, rejecting NaN and non-JSON state."""

    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
        )
    except (TypeError, ValueError) as exc:
        raise ConstraintFieldError("regional constraint state is not canonical JSON") from exc


def _regional_profile(
    compiled: CompiledConstraintProblem,
    profile: ConstraintFieldProfile | Mapping[str, Any] | None,
) -> ConstraintFieldProfile:
    if profile is None:
        return ConstraintFieldProfile(
            max_variables=compiled.variables,
            max_clauses=max(1, len(compiled.clauses) + 64),
            max_transitions=20_000,
            max_learned_clauses=64,
            mode="conflict",
        )
    if isinstance(profile, ConstraintFieldProfile):
        selected = profile
    elif isinstance(profile, Mapping):
        try:
            selected = ConstraintFieldProfile(**dict(profile))
        except (TypeError, ConstraintFieldError) as exc:
            raise ConstraintFieldError("regional constraint profile is invalid") from exc
    else:
        raise ConstraintFieldError("regional constraint profile is invalid")
    _check_profile(compiled, selected)
    return selected


def _regional_clause_value(clause: Sequence[int], assignments: Sequence[int]) -> tuple[bool, list[int]]:
    unassigned: list[int] = []
    for literal in clause:
        value = int(assignments[abs(int(literal)) - 1])
        if value == (1 if literal > 0 else -1):
            return True, []
        if value == 0:
            unassigned.append(int(literal))
    return False, unassigned


def _regional_analyze(
    clauses: Sequence[Sequence[int]],
    assignments: Sequence[int],
) -> tuple[int | None, int | None, bool, list[int], list[int]]:
    """Match ClauseField's deterministic conflict/unit/activity scan."""

    positive = [0] * len(assignments)
    negative = [0] * len(assignments)
    unit_literal: int | None = None
    all_satisfied = True
    for clause_index, raw_clause in enumerate(clauses):
        clause = tuple(int(value) for value in raw_clause)
        satisfied, unassigned = _regional_clause_value(clause, assignments)
        if satisfied:
            continue
        all_satisfied = False
        if not unassigned:
            return clause_index, None, False, positive, negative
        for literal in unassigned:
            if literal > 0:
                positive[literal - 1] += 1
            else:
                negative[-literal - 1] += 1
        if len(unassigned) == 1 and unit_literal is None:
            unit_literal = unassigned[0]
    return (
        None,
        unit_literal,
        all_satisfied,
        positive,
        negative,
    )


def _regional_assign(
    continuation: dict[str, Any],
    literal: int,
    *,
    level: int,
    reason: int,
) -> None:
    variable = abs(int(literal))
    expected = 1 if literal > 0 else -1
    assignments = continuation["assignments"]
    current = int(assignments[variable - 1])
    if current == expected:
        return
    if current != 0:
        raise ConstraintFieldError("regional search attempted a contradictory assignment")
    assignments[variable - 1] = expected
    continuation["levels"][variable - 1] = int(level)
    continuation["reasons"][variable - 1] = int(reason)
    continuation["trail"].append(variable)


def _regional_resolution(left: Sequence[int], right: Sequence[int], pivot: int) -> tuple[int, ...]:
    left_values = tuple(int(value) for value in left)
    right_values = tuple(int(value) for value in right)
    left_polarity = 1 if pivot in left_values else -1 if -pivot in left_values else 0
    right_polarity = 1 if pivot in right_values else -1 if -pivot in right_values else 0
    if left_polarity == 0 or right_polarity != -left_polarity:
        raise ConstraintFieldError("regional proof premises lack complementary pivot")
    result: set[int] = set()
    for literal in (*left_values, *right_values):
        if abs(literal) == pivot:
            continue
        if -literal in result:
            raise ConstraintFieldError("regional resolution produced a tautology")
        result.add(literal)
    return tuple(sorted(result, key=_literal_key))


def _regional_decision_literals(continuation: Mapping[str, Any]) -> tuple[int, ...]:
    """Return the decision path in force, in decision order."""

    return tuple(int(row["literal"]) for row in continuation["decisions"])


def _regional_learn_nogood(
    continuation: Mapping[str, Any],
    profile: Mapping[str, Any],
    decisions: Sequence[int],
) -> tuple[tuple[int, ...], int | None, bool, str]:
    """Decide storage for a conflict nogood without mutating the continuation.

    Returns the nogood, its clause id when one already exists or would be
    stored, the storage flag, and the learning status
    ``root``/``duplicate``/``capacity``/``added``.
    """

    clause = tuple(-int(literal) for literal in decisions)
    if not decisions:
        return clause, None, False, "root"
    backend = continuation["backend_clauses"]
    for index, existing in enumerate(backend):
        if tuple(int(value) for value in existing) == clause:
            return clause, index + 1, False, "duplicate"
    if len(continuation["learned_clauses"]) >= int(profile["max_learned_clauses"]):
        return clause, None, False, "capacity"
    return clause, len(backend) + 1, True, "added"


def _regional_commit_nogood(
    continuation: dict[str, Any],
    nogood: Sequence[int],
    stored_new: bool,
) -> None:
    """Bind a stored nogood into the search exactly where it was journaled."""

    if not stored_new:
        return
    continuation["backend_clauses"].append([int(value) for value in nogood])
    continuation["learned_clauses"].append([int(value) for value in nogood])


def _regional_conflict_proof(
    continuation: Mapping[str, Any],
    conflict_clause: int,
    clauses: Sequence[Sequence[int]],
) -> dict[str, Any]:
    """Build the same leaf proof vocabulary as ClauseField._conflict_proof."""

    decisions = _regional_decision_literals(continuation)
    current = tuple(int(value) for value in clauses[conflict_clause])
    steps: list[dict[str, Any]] = []
    reasons = continuation["reasons"]
    for stored_variable in reversed(continuation["trail"]):
        pivot = int(stored_variable)
        if pivot not in current and -pivot not in current:
            continue
        reason_clause_id = int(reasons[pivot - 1])
        if reason_clause_id == 0:
            continue
        reason_clause = tuple(int(value) for value in clauses[reason_clause_id - 1])
        current = _regional_resolution(current, reason_clause, pivot)
        steps.append(
            {
                "pivot": pivot,
                "reason_clause_id": reason_clause_id,
                "resolvent": list(current),
            }
        )
    nogood = tuple(-literal for literal in decisions)
    if not set(current).issubset(set(nogood)):
        raise ConstraintFieldError("regional conflict core is not contained in its decision nogood")
    return {
        "schema": "cassifi.clause-field-conflict-proof.v1",
        "decision_literals": list(decisions),
        "conflict_clause_id": int(conflict_clause) + 1,
        "resolution_steps": steps,
        "core_clause": list(current),
        "nogood_clause": list(nogood),
    }


def _regional_hybrid_proof(
    continuation: Mapping[str, Any],
    clauses: Sequence[Sequence[int]],
    variables: int,
    conflict_clause: int | None,
) -> dict[str, Any]:
    """Serialize an auditable hybrid proof for a prepass root conflict."""

    lines: list[dict[str, Any]] = []
    for index, clause in enumerate(clauses, 1):
        lines.append(
            {
                "line_id": index,
                "kind": "clause",
                "rule": "input",
                "literals": [int(value) for value in clause],
            }
        )
    root_line: int | None = None
    if conflict_clause is not None:
        current = tuple(int(value) for value in clauses[conflict_clause])
        current_id = conflict_clause + 1
        reasons = continuation["reasons"]
        for stored_variable in reversed(continuation["trail"]):
            pivot = int(stored_variable)
            if pivot not in current and -pivot not in current:
                continue
            reason_clause_id = int(reasons[pivot - 1])
            if reason_clause_id == 0:
                continue
            reason_clause = tuple(int(value) for value in clauses[reason_clause_id - 1])
            current = _regional_resolution(current, reason_clause, pivot)
            lines.append(
                {
                    "line_id": len(lines) + 1,
                    "kind": "clause",
                    "rule": "resolve",
                    "literals": list(current),
                    "left": int(current_id),
                    "right": int(reason_clause_id),
                    "aux": int(pivot),
                }
            )
            current_id = len(lines)
        if not current:
            root_line = current_id
    payload = {
        "schema": "cassifi.hybrid-inference-proof.v1",
        "proof_system": "CNF resolution plus cutting planes, GF(2) elimination, cardinality-parity bridges, and acyclic extension definitions",
        "original_variables": int(variables),
        "original_clauses": len(clauses),
        "status": "unsat" if root_line is not None else "exhausted",
        "root_line": root_line,
        "lines": lines,
    }
    payload["proof_sha256"] = hashlib.sha256(_canonical(payload)).hexdigest()
    return payload


def _regional_relation_facts(
    relation: Mapping[str, Any],
    *,
    max_arity: int,
) -> list[tuple[list[int], str]]:
    args = [int(value) for value in relation.get("args", [])]
    kind = relation.get("kind")
    facts: list[tuple[list[int], str]] = []
    if kind == "xor":
        support = _xor_support(args)
        rhs = int(relation.get("rhs", 0))
        if len(support) == 1:
            facts.append(([support[0] if rhs else -support[0]], "xor"))
        elif len(support) == 2 and max_arity >= 2:
            first, second = support
            rows = (
                [[first, second], [-first, -second]]
                if rhs
                else [[first, -second], [-first, second]]
            )
            facts.extend((row, "xor") for row in rows)
    elif kind == "cardinality" and len(args) <= 2:
        minimum = int(relation.get("min", 0))
        maximum = int(relation.get("max", len(args)))
        if len(args) == 1:
            if minimum == 1:
                facts.append(([args[0]], "pb"))
            if maximum == 0:
                facts.append(([-args[0]], "pb"))
        elif len(args) == 2 and max_arity >= 2:
            if maximum == 0:
                facts.append(([-args[0], -args[1]], "pb"))
            if minimum == 2:
                facts.append(([args[0], args[1]], "pb"))
    return facts


def _regional_journal_bytes(journal: Sequence[Mapping[str, Any]]) -> int:
    return sum(len(_canonical(dict(row))) + 1 for row in journal)


def _regional_profile_digest(profile: Mapping[str, Any]) -> str:
    return ConstraintFieldProfile(**dict(profile)).fingerprint


def _regional_state_digest(state: Mapping[str, Any]) -> str:
    payload = {key: value for key, value in state.items() if key != "result"}
    return hashlib.sha256(_canonical(payload)).hexdigest()


def _regional_result(
    state: Mapping[str, Any],
    *,
    status: str,
    reason: str,
) -> dict[str, Any]:
    continuation = state["continuation"]
    source = state["source"]
    profile = state["profile"]
    assignments = [int(value) for value in continuation["assignments"]]
    witness: dict[str, int] | None = None
    if status == "sat":
        witness = {
            str(label): (1 if assignments[int(identifier) - 1] == 1 else 0)
            for label, identifier in source.get("witness_signals", [])
        }
    resolution_proof = None
    if status == "unsat" and reason in {"resolution-refutation", "propagation-refutation"}:
        conflicts = [
            row["proof"]
            for row in state["journal"]
            if isinstance(row, Mapping) and row.get("type") == "conflict"
        ]
        resolution_proof = build_proof_certificate(conflicts, status="unsat")
    hybrid_proof = continuation.get("hybrid_proof")
    if (
        hybrid_proof is None
        and profile.get("mode") == "algebraic"
        and status == "sat"
        and not continuation.get("prepass_skipped", False)
    ):
        hybrid_proof = _regional_hybrid_proof(
            continuation,
            [list(clause) for clause in source["clauses"]],
            int(source["variables"]),
            None,
        )
    backend_clauses = [list(clause) for clause in continuation["backend_clauses"]]
    augmentations = [dict(row) for row in continuation["augmentations"]]
    learned_clauses = [list(clause) for clause in continuation["learned_clauses"]]
    # Stored nogoods are appended after the searchable backend; the auditor
    # replays them from the conflict journal, so they travel separately.
    searchable_backend = backend_clauses[: len(backend_clauses) - len(learned_clauses)]
    prepass_work: dict[str, Any] | None = None
    if profile.get("mode") == "algebraic":
        if continuation.get("prepass_skipped", False):
            prepass_work = {"status": "skipped", "reason": "compiled-contradiction"}
        elif reason == "hybrid-refutation":
            prepass_work = {"status": "running"}
        else:
            prepass_work = {"status": "complete"}
    search_ledger = {
        key: int(continuation["search_ledger"].get(key, 0))
        for key in ("propagations", "decisions", "conflicts", "backtracks")
    }
    digest = _regional_state_digest(state)
    profile_digest = _regional_profile_digest(profile)
    return {
        "schema": RESULT_SCHEMA,
        "compiled": _regional_json(source),
        "profile": dict(profile),
        "profile_sha256": profile_digest,
        "status": status,
        "reason": reason,
        "assignment": assignments,
        "witness": witness,
        "backend_clauses": searchable_backend,
        "augmentations": augmentations,
        "learned_clauses": learned_clauses,
        "resolution_proof": resolution_proof,
        "hybrid_proof": hybrid_proof,
        "work": {
            "compile": dict(source.get("work", {})),
            "prepass": prepass_work,
            "hybrid": None,
            "search": search_ledger,
            "controller": {
                "ticks": 0,
                "selections": 0,
                "interventions": 0,
                "enabled": bool(profile.get("controller", False)),
            },
            "journal_bytes": _regional_journal_bytes(state["journal"]),
            "augmentations": len(augmentations),
        },
        "checkpoint": {
            "schema": REGIONAL_STATE_SCHEMA,
            "profile_sha256": profile_digest,
            "state_sha256": digest,
            "journal_bytes": _regional_journal_bytes(state["journal"]),
        },
        "state_sha256": digest,
    }


def regional_state(
    compiled_or_source: CompiledConstraintProblem | Mapping[str, Any],
    profile: ConstraintFieldProfile | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Encode one compiled constraint source as a JSON-safe regional state."""

    if isinstance(compiled_or_source, CompiledConstraintProblem):
        compiled = compiled_or_source
    elif isinstance(compiled_or_source, Mapping) and compiled_or_source.get("schema") == PROBLEM_SCHEMA:
        compiled = _parse_compiled(compiled_or_source)
    elif isinstance(compiled_or_source, Mapping) and compiled_or_source.get("kind") == "circuit":
        compiled = compile_circuit(compiled_or_source)
    elif isinstance(compiled_or_source, Mapping) and compiled_or_source.get("kind") == "transition":
        compiled = compile_transition_problem(compiled_or_source)
    else:
        raise ConstraintFieldError("regional state requires a compiled constraint source")
    selected = _regional_profile(compiled, profile)
    source = _regional_json(compiled.as_dict())
    profile_value = _regional_json(selected.as_dict())
    continuation = {
        "variables": int(compiled.variables),
        "backend_clauses": [list(clause) for clause in compiled.clauses],
        "learned_clauses": [],
        "augmentations": [],
        "assignments": [0] * compiled.variables,
        "levels": [0] * compiled.variables,
        "reasons": [0] * compiled.variables,
        "trail": [],
        "decisions": [],
        "propagation": {"cursor": 0, "frontier": list(range(1, compiled.variables + 1))},
        "prepass": {"relation_cursor": 0, "clause_cursor": 0},
        "search_ledger": {"propagations": 0, "decisions": 0, "conflicts": 0, "backtracks": 0},
        "hybrid_proof": None,
        "prepass_skipped": bool(_holds_empty_clause(compiled.clauses)),
    }
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": source,
        "profile": profile_value,
        "phase": (
            "prepass"
            if selected.mode == "algebraic" and not _holds_empty_clause(compiled.clauses)
            else "search"
        ),
        "continuation": continuation,
        "journal": [],
        "ledger": {"invocations": 0, "primitive_work": 0},
        "result": None,
    }


def _regional_validate_state(state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping) or set(state) != _REGIONAL_KEYS:
        raise ConstraintFieldError("regional constraint state keys are invalid")
    if state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise ConstraintFieldError("regional constraint state schema is invalid")
    phase = state["phase"]
    if phase not in {"prepass", "search", "terminal"}:
        raise ConstraintFieldError("regional constraint phase is invalid")
    if phase == "terminal" and not isinstance(state.get("result"), Mapping):
        raise ConstraintFieldError("terminal regional state lacks its result")
    if phase != "terminal" and state.get("result") is not None:
        raise ConstraintFieldError("running regional state carries a terminal result")
    source = state["source"]
    if not isinstance(source, Mapping):
        raise ConstraintFieldError("regional constraint source is invalid")
    compiled = _parse_compiled(source)
    profile_value = state["profile"]
    if not isinstance(profile_value, Mapping):
        raise ConstraintFieldError("regional constraint profile is invalid")
    profile = _regional_profile(compiled, profile_value)
    continuation = state["continuation"]
    if not isinstance(continuation, Mapping):
        raise ConstraintFieldError("regional continuation is invalid")
    variables = compiled.variables
    for key in ("assignments", "levels", "reasons"):
        values = continuation.get(key)
        if not isinstance(values, list) or len(values) != variables:
            raise ConstraintFieldError("regional assignment state is invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value not in (-1, 0, 1)
        for value in continuation["assignments"]
    ):
        raise ConstraintFieldError("regional assignments are invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in continuation["levels"]
    ):
        raise ConstraintFieldError("regional levels are invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in continuation["reasons"]
    ):
        raise ConstraintFieldError("regional reasons are invalid")
    if not isinstance(continuation.get("trail"), list):
        raise ConstraintFieldError("regional trail is invalid")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= variables
        for value in continuation["trail"]
    ):
        raise ConstraintFieldError("regional trail contains an invalid variable")
    if len(set(continuation["trail"])) != len(continuation["trail"]):
        raise ConstraintFieldError("regional trail repeats a variable")
    if any(
        int(continuation["assignments"][value - 1]) == 0
        for value in continuation["trail"]
    ):
        raise ConstraintFieldError("regional trail contains an unassigned variable")
    if not isinstance(continuation.get("backend_clauses"), list):
        raise ConstraintFieldError("regional backend clauses are invalid")
    if not isinstance(continuation.get("learned_clauses"), list) or not isinstance(
        continuation.get("augmentations"), list
    ):
        raise ConstraintFieldError("regional proof clauses are invalid")
    base_clauses = [list(clause) for clause in compiled.clauses]
    backend_clauses = continuation["backend_clauses"]
    learned_clauses = continuation["learned_clauses"]
    # The searchable backend (source plus augmentations) and the learned tail
    # are independent capacities; stored nogoods extend the search but never
    # widen the workspace the backend was admitted with.
    searchable_clauses = backend_clauses[: len(backend_clauses) - len(learned_clauses)]
    if (
        len(searchable_clauses) > int(profile.max_clauses)
        or backend_clauses[: len(base_clauses)] != base_clauses
    ):
        raise ConstraintFieldError("regional backend clauses exceed their source capacity")
    if len(learned_clauses) > int(profile.max_learned_clauses):
        raise ConstraintFieldError("regional learned clauses exceed their capacity")
    if learned_clauses and backend_clauses[-len(learned_clauses):] != learned_clauses:
        raise ConstraintFieldError("regional learned clauses are not the backend tail")
    for clause in backend_clauses:
        _normalize_clause(clause)
    if not isinstance(state["journal"], list) or not isinstance(state["ledger"], Mapping):
        raise ConstraintFieldError("regional journal or ledger is invalid")
    if _regional_journal_bytes(state["journal"]) > int(profile.max_proof_bytes):
        raise ConstraintFieldError("regional journal exceeds its byte capacity")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in state["ledger"].values()
    ):
        raise ConstraintFieldError("regional ledger counters are invalid")
    if profile.mode == "local" and continuation.get("decisions"):
        raise ConstraintFieldError("local regional state cannot carry decisions")
    decisions = continuation.get("decisions")
    if not isinstance(decisions, list):
        raise ConstraintFieldError("regional decision state is invalid")
    seen_decisions: set[int] = set()
    for depth, frame in enumerate(decisions, 1):
        if (
            not isinstance(frame, Mapping)
            or isinstance(frame.get("literal"), bool)
            or not isinstance(frame.get("literal"), int)
            or frame["literal"] == 0
            or abs(frame["literal"]) > variables
            or frame.get("phase") not in (1, 2)
        ):
            raise ConstraintFieldError("regional decision frame is invalid")
        variable = abs(int(frame["literal"]))
        if variable in seen_decisions:
            raise ConstraintFieldError("regional decision stack repeats a variable")
        seen_decisions.add(variable)
        if continuation["assignments"][variable - 1] != (1 if frame["literal"] > 0 else -1):
            raise ConstraintFieldError("regional decision frame disagrees with assignment")
        if (
            continuation["levels"][variable - 1] != depth
            or continuation["reasons"][variable - 1] != 0
        ):
            raise ConstraintFieldError("regional decision frame has invalid provenance")


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> field_regions.KernelResult:
    """Advance the JSON-owned constraint search by at most ``quantum`` steps."""

    if not isinstance(arguments, Mapping) or arguments:
        raise ConstraintFieldError("exact.constraint takes no arguments")
    _regional_validate_state(state)
    quantum = _exact_integer(
        quantum,
        "regional constraint quantum",
        minimum=1,
        maximum=REGIONAL_KERNEL_MAX_WORK,
    )
    current = _regional_json(state)
    if current["phase"] == "terminal":
        return field_regions.KernelResult(
            state=current,
            status="done",
            work=0,
            output=current["result"],
        )
    current["ledger"]["invocations"] = int(current["ledger"]["invocations"]) + 1
    source = current["source"]
    profile = current["profile"]
    continuation = current["continuation"]
    base_clauses = [list(clause) for clause in source["clauses"]]
    work = 0
    while work < quantum and current["phase"] != "terminal":
        ledger = current["ledger"]
        if int(ledger["primitive_work"]) >= int(profile["max_transitions"]):
            current["phase"] = "terminal"
            current["result"] = _regional_result(
                current,
                status="exhausted",
                reason="transition-budget",
            )
            work += 1
            continue
        if current["phase"] == "prepass":
            prepass = continuation["prepass"]
            relations = source.get("native_relations", [])
            relation_cursor = int(prepass["relation_cursor"])
            if relation_cursor < len(relations):
                relation = relations[relation_cursor]
                relation_rows: list[dict[str, Any]] = []
                planned_clauses: list[list[int]] = []
                for clause, via in _regional_relation_facts(
                    relation,
                    max_arity=int(profile["max_augmentation_arity"]),
                ):
                    if (
                        len(continuation["backend_clauses"]) + len(planned_clauses)
                        >= int(profile["max_clauses"])
                    ):
                        break
                    canonical = _normalize_clause(clause)
                    if canonical is None or list(canonical) in continuation["backend_clauses"]:
                        continue
                    if list(canonical) in planned_clauses:
                        continue
                    if len(canonical) > int(profile["max_augmentation_arity"]):
                        continue
                    if len(continuation["augmentations"]) + len(relation_rows) >= int(
                        profile["max_augmentations"]
                    ):
                        break
                    row = {
                        "clause": list(canonical),
                        "via": via,
                        "line_id": relation_cursor + 1,
                    }
                    relation_rows.append(row)
                    planned_clauses.append(list(canonical))
                if relation_rows:
                    event = {"type": "augmentations", "rows": relation_rows}
                    if _regional_journal_bytes([*current["journal"], event]) <= int(
                        profile["max_proof_bytes"]
                    ):
                        continuation["augmentations"].extend(relation_rows)
                        continuation["backend_clauses"].extend(planned_clauses)
                        current["journal"].append(event)
                prepass["relation_cursor"] = relation_cursor + 1
                work += 1
                ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
                continue
            cursor = int(prepass["clause_cursor"])
            if cursor < len(base_clauses):
                clause = base_clauses[cursor]
                satisfied, unassigned = _regional_clause_value(
                    clause,
                    continuation["assignments"],
                )
                prepass["clause_cursor"] = cursor + 1
                if not satisfied and not unassigned:
                    hybrid_proof = _regional_hybrid_proof(
                        continuation,
                        base_clauses,
                        int(source["variables"]),
                        cursor,
                    )
                    event = {"type": "hybrid", "proof": hybrid_proof}
                    if _regional_journal_bytes([*current["journal"], event]) > int(
                        profile["max_proof_bytes"]
                    ):
                        current["phase"] = "terminal"
                        current["result"] = _regional_result(
                            current,
                            status="exhausted",
                            reason="proof-journal-capacity",
                        )
                    else:
                        continuation["hybrid_proof"] = hybrid_proof
                        current["journal"].append(event)
                        current["phase"] = "terminal"
                        current["result"] = _regional_result(
                            current,
                            status="unsat",
                            reason="hybrid-refutation",
                        )
                elif not satisfied and len(unassigned) == 1:
                    literal = int(unassigned[0])
                    _regional_assign(
                        continuation,
                        literal,
                        level=len(continuation["decisions"]),
                        reason=cursor + 1,
                    )
                    prepass["clause_cursor"] = 0
                    continuation["search_ledger"]["propagations"] += 1
                work += 1
                ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
                continue
            current["phase"] = "search"
            continuation["propagation"]["cursor"] = 0
            work += 1
            ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
            continue
        clauses = continuation["backend_clauses"]
        conflict, unit, all_satisfied, positive, negative = _regional_analyze(
            clauses,
            continuation["assignments"],
        )
        if conflict is not None:
            proof = _regional_conflict_proof(continuation, conflict, clauses)
            nogood_clause, stored_clause_id, stored_new, learning_status = _regional_learn_nogood(
                continuation,
                profile,
                _regional_decision_literals(continuation),
            )
            proof.update(
                {
                    "stored_clause_id": stored_clause_id,
                    "stored_new": stored_new,
                    "learning_status": learning_status,
                }
            )
            journal_event = {"type": "conflict", "proof": proof}
            candidate_journal = [*current["journal"], journal_event]
            if _regional_journal_bytes(candidate_journal) > int(profile["max_proof_bytes"]):
                current["phase"] = "terminal"
                current["result"] = _regional_result(
                    current,
                    status="exhausted",
                    reason="proof-journal-capacity",
                )
            else:
                current["journal"].append(journal_event)
                continuation["search_ledger"]["conflicts"] += 1
                _regional_commit_nogood(continuation, nogood_clause, stored_new)
                decisions = continuation["decisions"]
                flipped: int | None = None
                while decisions:
                    frame = decisions[-1]
                    if int(frame["phase"]) == 1:
                        frame["phase"] = 2
                        flipped = -int(frame["literal"])
                        frame["literal"] = flipped
                        target_level = len(decisions)
                        removed = {
                            index + 1
                            for index, level in enumerate(continuation["levels"])
                            if int(level) >= target_level
                        }
                        for variable in removed:
                            continuation["assignments"][variable - 1] = 0
                            continuation["levels"][variable - 1] = 0
                            continuation["reasons"][variable - 1] = 0
                        continuation["trail"] = [
                            variable
                            for variable in continuation["trail"]
                            if variable not in removed
                        ]
                        _regional_assign(
                            continuation,
                            flipped,
                            level=target_level,
                            reason=0,
                        )
                        continuation["search_ledger"]["backtracks"] += 1
                        break
                    decisions.pop()
                if flipped is None:
                    current["phase"] = "terminal"
                    current["result"] = _regional_result(
                        current,
                        status="unsat",
                        reason=(
                            "propagation-refutation"
                            if profile["mode"] == "local"
                            else "resolution-refutation"
                        ),
                    )
            work += 1
            ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
            continue
        if unit is not None:
            unit_reason = next(
                index + 1
                for index, clause in enumerate(clauses)
                if _regional_clause_value(clause, continuation["assignments"])[1] == [unit]
            )
            _regional_assign(
                continuation,
                int(unit),
                level=len(continuation["decisions"]),
                reason=unit_reason,
            )
            continuation["propagation"]["cursor"] = 0
            continuation["search_ledger"]["propagations"] += 1
            work += 1
            ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
            continue
        if all_satisfied:
            for index, value in enumerate(continuation["assignments"]):
                if int(value) == 0:
                    _regional_assign(
                        continuation,
                        -(index + 1),
                        level=len(continuation["decisions"]),
                        reason=0,
                    )
            current["phase"] = "terminal"
            current["result"] = _regional_result(current, status="sat", reason="model")
            work += 1
            ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
            continue
        if profile["mode"] == "local":
            current["phase"] = "terminal"
            current["result"] = _regional_result(
                current,
                status="exhausted",
                reason="local-stall",
            )
            work += 1
            ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
            continue
        unassigned = [
            index
            for index, value in enumerate(continuation["assignments"])
            if int(value) == 0
        ]
        if not unassigned:
            raise ConstraintFieldError("regional search has no legal transition")
        best_activity = max(positive[index] + negative[index] for index in unassigned)
        variable_index = next(
            index
            for index in unassigned
            if positive[index] + negative[index] == best_activity
        )
        literal = (
            variable_index + 1
            if positive[variable_index] > negative[variable_index]
            else -(variable_index + 1)
        )
        continuation["decisions"].append({"literal": literal, "phase": 1})
        _regional_assign(
            continuation,
            literal,
            level=len(continuation["decisions"]),
            reason=0,
        )
        continuation["search_ledger"]["decisions"] += 1
        work += 1
        ledger["primitive_work"] = int(ledger["primitive_work"]) + 1
    continuation["propagation"]["frontier"] = [
        index + 1
        for index, value in enumerate(continuation["assignments"])
        if int(value) == 0
    ]
    if current["phase"] == "terminal":
        digest = _regional_state_digest(current)
        if isinstance(current["result"], Mapping):
            current["result"]["state_sha256"] = digest
            checkpoint = current["result"].get("checkpoint")
            if isinstance(checkpoint, dict):
                checkpoint["state_sha256"] = digest
        return field_regions.KernelResult(
            state=current,
            status="done",
            work=work,
            output=current["result"],
        )
    return field_regions.KernelResult(state=current, status="yield", work=work, output=None)


__all__ = [
    "CompiledConstraintProblem",
    "ConstraintField",
    "ConstraintFieldError",
    "ConstraintFieldProfile",
    "ConstraintFieldState",
    "CircuitSpec",
    "DESCRIPTOR_SCHEMA",
    "INTERVENTION_SCHEMA",
    "PROBLEM_SCHEMA",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "RESULT_SCHEMA",
    "STATE_SCHEMA",
    "STEP_SCHEMA",
    "TransitionProblem",
    "compile_circuit",
    "compile_transition_problem",
    "regional_kernel",
    "regional_state",
]
