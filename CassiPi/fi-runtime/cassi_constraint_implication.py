"""Candidate-rule screening over compiled CassiFI constraint sources.

This module answers one question, exactly and with evidence:

    under these assumptions, must this consequence hold?

The query is decided over the declared finite source by asking the constraint
field whether

    source and assumptions and not consequence

is satisfiable. Because the compiled encoding is model-preserving on the
declared witness signals, the three outcomes carry the same evidence classes as
the underlying field:

* ``refuted`` -- the field produced a model, so the assumptions hold, the
  consequence fails, and the source is satisfied. The module replays that model
  against the original source with its own evaluator before reporting it, so a
  reported counterexample is never an unchecked assignment.
* ``holds`` -- the field refuted the negated query and the module carries the
  certificate: a resolution refutation, a cutting-plane and GF(2) refutation, or
  both, together with the clause lists an independent auditor needs.
* ``unresolved`` -- a declared bound stopped the run. This claims nothing about
  the rule.
* ``vacuous`` -- a declared boundary contradicts one of the assumptions, so
  the premise is unsatisfiable before the candidate consequence is considered.
  It is reported separately rather than as a success, because a screening
  campaign that counts vacuous rules as confirmed rules is measuring nothing.

The module never edits the field modules it drives; it compiles the source
through the public compiler, routes the query literals into the source
vocabulary, and reports the field's own evidence. Deeper premise
unsatisfiability that is not a syntactic clash against a declared boundary still
reports ``holds``, which is logically correct; the distinction is recorded
honestly in ``reason``.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from cassi_field_regions import KernelResult
from cassi_constraint_field import (
    CompiledConstraintProblem,
    ConstraintField,
    ConstraintFieldError,
    ConstraintFieldProfile,
    compile_circuit,
    compile_transition_problem,
)

IMPLICATION_SCHEMA = "cassifi.implication-result.v1"
REGIONAL_KERNEL_NAME = "exact.implication"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-implication-state.v1"


def _json_safe(value: Any) -> Any:
    """Return the canonical JSON representation used by regional state."""

    try:
        return json.loads(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise ConstraintFieldError("implication regional state is not JSON-safe") from exc


@dataclass(frozen=True, slots=True)
class ImplicationQuery:
    """One candidate rule over one declared finite source."""

    source: Mapping[str, Any]
    consequence: tuple[str, int]
    assumptions: tuple[tuple[str, int], ...] = ()

    def __post_init__(self) -> None:
        name, value = self.consequence
        _signal_label(name, "consequence")
        _bit(value, f"consequence {name}")
        for name, value in self.assumptions:
            _signal_label(name, "assumption")
            _bit(value, f"assumption {name}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": dict(self.source),
            "consequence": [self.consequence[0], self.consequence[1]],
            "assumptions": [[name, value] for name, value in self.assumptions],
        }

    def label(self) -> str:
        """Readable rule label, e.g. ``a=0 and b=1 -> c=0``."""

        return rule_label(self.assumptions, self.consequence)


def rule_label(
    assumptions: Sequence[tuple[str, int]],
    consequence: tuple[str, int],
) -> str:
    left = " and ".join(f"{name}={value}" for name, value in assumptions) or "true"
    return f"{left} -> {consequence[0]}={consequence[1]}"


def _bit(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise ConstraintFieldError(f"{name} must be an exact 0/1 integer")
    return value


def _signal_label(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ConstraintFieldError(f"{name} must be a declared signal label")
    return value


def _is_declared_query_signal(source: Mapping[str, Any], label: str) -> bool:
    """Check public signal spelling and its legal transition time."""

    kind = source.get("kind")
    if kind == "circuit":
        names = {str(name) for name in source.get("inputs", ())}
        names.update(str(gate["out"]) for gate in source.get("gates", ()))
        return label in names
    if kind != "transition":
        return False
    stem, separator, index = label.rpartition("@")
    if separator:
        if not index.isdigit():
            return False
        time = int(index)
    else:
        stem = label
        time = 0
    horizon = int(source["horizon"])
    if stem in {str(name) for name in source["state"]}:
        return 0 <= time <= horizon
    if stem in {str(name) for name in source["inputs"]}:
        return 0 <= time < horizon
    if stem in {str(gate["out"]) for gate in source.get("gates", ())}:
        return 0 <= time < horizon
    return False


def _split_witness(label: str) -> tuple[str, int]:
    stem, _, index = label.rpartition("@")
    if not stem or not index.isdigit():
        raise ConstraintFieldError(f"witness signal {label!r} is not a name@time label")
    return stem, int(index)


def witness_signals(compiled: CompiledConstraintProblem) -> dict[str, int]:
    """Declared unknowns of a compiled source, as ``label -> identifier``."""

    return {label: identifier for label, identifier in compiled.witness_signals}


def _query_units(
    query: ImplicationQuery,
    compiled: CompiledConstraintProblem,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Assumption units plus the negated consequence, split by routing class.

    Literals on declared unknowns become boundary pins, which keeps the witness
    a complete model of the query. Literals on signals the source itself
    determines -- a successor state value like ``p@2``, or a gate output --
    become unit clause rows, because the source does not let those be pinned at
    the boundary. Both route into the same compiled encoding.
    """

    declared = witness_signals(compiled)
    pins: list[tuple[str, int]] = []
    units: list[tuple[str, int]] = []
    consequence = (query.consequence[0], 1 - _bit(query.consequence[1], "consequence"))
    literals = list(query.assumptions) + [consequence]
    for name, value in literals:
        _signal_label(name, "query signal")
        if not _is_declared_query_signal(query.source, name):
            raise ConstraintFieldError(
                f"query signal {name!r} is not declared by the source"
            )
        bit = _bit(value, "query literal")
        (pins if name in declared else units).append((name, bit))
    return pins, units


def _canonical_source_label(source: Mapping[str, Any], name: str) -> str:
    """Use the public time-qualified spelling for a source signal."""

    if source.get("kind") == "circuit":
        return name
    stem, _, index = name.rpartition("@")
    return f"{stem if stem else name}@{int(index) if index.isdigit() else 0}"


def _declared_boundary_units(source: Mapping[str, Any]) -> set[tuple[str, int]]:
    """Collect only facts explicitly declared at the source boundary.

    Compiled unit clauses are broader than boundary facts: a parity or
    cardinality relation can legitimately derive a unit. Those units are
    evidence for a non-vacuous implication, not a syntactic clash that should
    be classified as vacuous.
    """

    boundaries: set[tuple[str, int]] = set()
    kind = source.get("kind")
    if kind == "circuit":
        boundaries.update(
            (str(name), int(value)) for name, value in source.get("assertions", ())
        )
        for row in source.get("clauses", ()):
            if len(row) == 1:
                literal = row[0]
                boundaries.add((str(literal[0]), int(literal[1])))
        return boundaries
    if kind == "transition":
        boundaries.update(
            (f"{name}@0", int(value)) for name, value in source.get("initial", ())
        )
        boundaries.update(
            (f"{name}@{int(time)}", int(value))
            for time, name, value in source.get("input_assertions", ())
        )
        horizon = int(source["horizon"])
        boundaries.update(
            (f"{name}@{horizon}", int(value)) for name, value in source.get("final", ())
        )
        for row in source.get("clauses", ()):
            if len(row) == 1:
                literal = row[0]
                time = int(literal[2]) if len(literal) == 3 else 0
                boundaries.add((f"{literal[0]}@{time}", int(literal[1])))
        return boundaries
    raise ConstraintFieldError("implication sources need a declared kind")


def _clashing_unit(
    source: Mapping[str, Any],
    assumptions: Sequence[tuple[str, int]],
) -> str | None:
    """Find the first query literal contradicted by a declared boundary fact."""

    boundaries = _declared_boundary_units(source)
    for name, value in assumptions:
        label = _canonical_source_label(source, name)
        if (label, 1 - int(value)) in boundaries:
            return f"{name}={value}"
    return None


def _augmented_source(
    source: Mapping[str, Any],
    pins: Sequence[tuple[str, int]],
    units: Sequence[tuple[str, int]],
) -> dict[str, Any]:
    """Route query literals into the declared source vocabulary."""

    payload: dict[str, Any] = dict(source)
    kind = payload.get("kind")
    if kind == "circuit":
        assertions = [list(row) for row in payload.get("assertions", ())]
        for name, value in pins:
            assertions.append([name, value])
        clauses = [list(row) for row in payload.get("clauses", ())]
        for name, value in units:
            clauses.append([[name, value]])
        payload["assertions"] = assertions
        payload["clauses"] = clauses
        return payload
    if kind == "transition":
        state = tuple(payload["state"])
        inputs = tuple(payload["inputs"])
        horizon = int(payload["horizon"])
        initial = [list(row) for row in payload.get("initial", ())]
        input_assertions = [list(row) for row in payload.get("input_assertions", ())]
        for name, value in pins:
            stem, index = _split_witness(name)
            if stem in state and index == 0:
                initial.append([stem, value])
            elif stem in inputs and 0 <= index < horizon:
                input_assertions.append([index, stem, value])
            else:
                raise ConstraintFieldError(
                    f"transition query signal {name!r} is not a declared witness"
                )
        clauses = [list(row) for row in payload.get("clauses", ())]
        for name, value in units:
            stem, time = _split_witness(name) if "@" in name else (name, 0)
            if time > horizon:
                raise ConstraintFieldError(f"query signal {name!r} exceeds the horizon")
            clauses.append([[stem, value, time]])
        payload["initial"] = initial
        payload["input_assertions"] = input_assertions
        payload["clauses"] = clauses
        return payload
    raise ConstraintFieldError("implication queries need a circuit or transition source")


def compile_source(source: Mapping[str, Any]) -> CompiledConstraintProblem:
    kind = source.get("kind")
    if kind == "circuit":
        return compile_circuit(source)
    if kind == "transition":
        return compile_transition_problem(source)
    raise ConstraintFieldError("implication sources must declare kind circuit or transition")


def default_profile(
    compiled: CompiledConstraintProblem,
    *,
    mode: str = "algebraic",
    **overrides: Any,
) -> ConstraintFieldProfile:
    """Declared field geometry for one query, sized from the compiled payload."""

    fields: dict[str, Any] = {
        "max_variables": compiled.variables + 8,
        "max_clauses": len(compiled.clauses) + 64,
        "mode": mode,
    }
    fields.update(overrides)
    return ConstraintFieldProfile(**fields)


def _gate_value(op: str, arguments: Sequence[int], value: int | None) -> int:
    if op == "const":
        if value is None:
            raise ConstraintFieldError("constant gate carries no value")
        return int(value)
    if op == "buf":
        return arguments[0]
    if op == "not":
        return 1 - arguments[0]
    if op == "and":
        return arguments[0] & arguments[1]
    if op == "or":
        return arguments[0] | arguments[1]
    if op == "nand":
        return 1 - (arguments[0] & arguments[1])
    if op == "nor":
        return 1 - (arguments[0] | arguments[1])
    if op == "xor":
        return arguments[0] ^ arguments[1]
    if op == "xnor":
        return 1 - (arguments[0] ^ arguments[1])
    if op == "mux":
        select, yes, no = arguments
        return yes if select == 1 else no
    raise ConstraintFieldError(f"unsupported gate operation {op!r}")


def _resolve_gates(
    gates: Sequence[Mapping[str, Any]],
    values: Mapping[str, int],
) -> dict[str, int]:
    """Resolve every gate in declaration-independent order; cycles are refused."""

    resolved: dict[str, int] = {}
    pending = [dict(gate) for gate in gates]
    while pending:
        remaining: list[dict[str, Any]] = []
        progress = False
        for gate in pending:
            name = str(gate["out"])
            if name in resolved:
                raise ConstraintFieldError(f"gate {name!r} is defined twice")
            if all(str(argument) in resolved or str(argument) in values for argument in gate["args"]):
                arguments = [
                    resolved[str(argument)] if str(argument) in resolved else int(values[str(argument)])
                    for argument in gate["args"]
                ]
                resolved[name] = _gate_value(str(gate["op"]), arguments, gate.get("value"))
                progress = True
            else:
                remaining.append(gate)
        if not progress:
            raise ConstraintFieldError("gate definitions contain a cycle or an unknown signal")
        pending = remaining
    return resolved


def _relation_holds(relation: Mapping[str, Any], values: Mapping[str, int]) -> bool:
    arguments = [int(values[str(name)]) for name in relation["args"]]
    if relation["kind"] == "xor":
        parity = 0
        for value in arguments:
            parity ^= value
        return parity == int(relation["rhs"])
    total = sum(arguments)
    return int(relation["min"]) <= total <= int(relation["max"])


def _clause_rows_hold(
    rows: Sequence[Any],
    resolve: Any,
) -> bool:
    """Check clause rows; circuit rows name a signal, transition rows carry a time."""

    for row in rows or ():
        satisfied = False
        for literal in row:
            name = str(literal[0])
            polarity = int(literal[1])
            time = int(literal[2]) if len(literal) == 3 else 0
            if int(resolve(name, time)) == polarity:
                satisfied = True
                break
        if not satisfied:
            return False
    return True


def _circuit_values(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    values: dict[str, int] = {}
    for name in source["inputs"]:
        if name not in assignment:
            raise ConstraintFieldError(f"assignment does not cover input {name!r}")
        values[name] = _bit(assignment[name], f"assignment {name}")
    values.update(_resolve_gates(source.get("gates", ()), values))
    return values


def _circuit_holds(source: Mapping[str, Any], values: Mapping[str, int]) -> bool:
    for name, value in source.get("assertions", ()):
        if name not in values:
            raise ConstraintFieldError(f"assertion references unknown signal {name!r}")
        if values[name] != int(value):
            return False
    for relation in source.get("relations", ()):
        if not _relation_holds(relation, values):
            return False
    return _clause_rows_hold(source.get("clauses", ()), lambda name, _: values[name])


def _transition_resolver(source: Mapping[str, Any], values: Mapping[str, int]):
    state = set(source["state"])
    inputs = set(source["inputs"])

    def resolve(name: str, time: int) -> int:
        if name in inputs:
            return values[f"i:{name}:{time}"]
        if name in state:
            return values[f"s:{name}:{time}"]
        return values[f"g:{name}:{time}"]

    return resolve


def _transition_values(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    state = list(source["state"])
    inputs = list(source["inputs"])
    horizon = int(source["horizon"])
    values: dict[str, int] = {}
    for name in state:
        key = f"{name}@0"
        if key not in assignment:
            raise ConstraintFieldError(f"assignment does not cover {key!r}")
        values[f"s:{name}:0"] = _bit(assignment[key], f"assignment {key}")
    for name in inputs:
        for time in range(horizon):
            key = f"{name}@{time}"
            if key not in assignment:
                raise ConstraintFieldError(f"assignment does not cover {key!r}")
            values[f"i:{name}:{time}"] = _bit(assignment[key], f"assignment {key}")
    resolve = _transition_resolver(source, values)
    gates = list(source.get("gates", ()))
    state_set = set(state)
    input_set = set(inputs)
    for time in range(horizon):
        pending = {str(gate["out"]): gate for gate in gates}
        computed: dict[str, int] = {}

        def argument_value(argument: str) -> int | None:
            if argument in computed:
                return computed[argument]
            if argument in state_set:
                return int(values[f"s:{argument}:{time}"])
            if argument in input_set:
                return int(values[f"i:{argument}:{time}"])
            return None

        while pending:
            progress = False
            for name in list(pending):
                gate = pending[name]
                arguments = [argument_value(str(argument)) for argument in gate["args"]]
                if any(argument is None for argument in arguments):
                    continue
                resolved = _gate_value(
                    str(gate["op"]),
                    [int(argument) for argument in arguments if argument is not None],
                    gate.get("value"),
                )
                computed[name] = resolved
                values[f"g:{name}:{time}"] = resolved
                del pending[name]
                progress = True
            if not progress:
                raise ConstraintFieldError("gate definitions contain a cycle or an unknown signal")
        for target, origin in source.get("next_state", ()):
            values[f"s:{target}:{time + 1}"] = resolve(str(origin), time)
    return values


def _transition_holds(
    source: Mapping[str, Any],
    values: Mapping[str, int],
    resolve,
) -> bool:
    state = set(source["state"])
    inputs = set(source["inputs"])
    horizon = int(source["horizon"])
    for name, value in source.get("initial", ()):
        if name not in state:
            raise ConstraintFieldError(f"initial references unknown state {name!r}")
        if resolve(name, 0) != int(value):
            return False
    for time, name, value in source.get("input_assertions", ()):
        if name not in inputs or int(time) < 0 or int(time) >= horizon:
            raise ConstraintFieldError("input assertion references an undeclared signal or time")
        if resolve(name, int(time)) != int(value):
            return False
    for name, value in source.get("final", ()):
        if name not in state:
            raise ConstraintFieldError(f"final references unknown state {name!r}")
        if values[f"s:{name}:{horizon}"] != int(value):
            return False
    for time in range(horizon):
        for relation in source.get("relations", ()):
            arguments = {str(name): resolve(str(name), time) for name in relation["args"]}
            if not _relation_holds(relation, arguments):
                return False
    return _clause_rows_hold(source.get("clauses", ()), resolve)


def evaluate_source(source: Mapping[str, Any], assignment: Mapping[str, int]) -> bool:
    """Evaluate a witness on the original source, independently of the compiler.

    Circuits: gates are resolved from the declared inputs, then the assertions,
    relations, and clause rows are checked. Transitions: the declared state at
    time zero and every declared input are read from the assignment, gates are
    evaluated per time index, the successor rows are simulated, and the initial,
    input, final, relation, and clause rows are checked. A witness that does not
    cover the declared unknowns is refused rather than treated as a failure.
    """

    kind = source.get("kind")
    if kind == "circuit":
        return _circuit_holds(source, _circuit_values(source, assignment))
    if kind == "transition":
        values = _transition_values(source, assignment)
        return _transition_holds(source, values, _transition_resolver(source, values))
    raise ConstraintFieldError("implication sources must declare kind circuit or transition")


def signal_value(source: Mapping[str, Any], assignment: Mapping[str, int], label: str) -> int:
    """Value of one declared signal under a witness, by the same evaluator."""

    kind = source.get("kind")
    if kind == "circuit":
        values = _circuit_values(source, assignment)
        if label not in values:
            raise ConstraintFieldError(f"signal {label!r} is not declared by the source")
        return int(values[label])
    if kind == "transition":
        stem, time = _split_witness(label) if "@" in label else (label, 0)
        values = _transition_values(source, assignment)
        horizon = int(source["horizon"])
        if time > horizon:
            raise ConstraintFieldError(f"signal {label!r} exceeds the horizon")
        return int(_transition_resolver(source, values)(stem, time))
    raise ConstraintFieldError("implication sources must declare kind circuit or transition")


def _select_augmentation_arity(
    profile: ConstraintFieldProfile | None,
    augmentation_arity: int | None,
) -> int:
    if augmentation_arity is not None and (
        isinstance(augmentation_arity, bool)
        or not isinstance(augmentation_arity, int)
        or augmentation_arity not in (1, 2)
    ):
        raise ConstraintFieldError("augmentation_arity must be an exact integer in {1, 2}")
    if profile is not None and not isinstance(profile, ConstraintFieldProfile):
        raise ConstraintFieldError("profile must be a ConstraintFieldProfile")
    if profile is None:
        return 1 if augmentation_arity is None else augmentation_arity
    selected = int(profile.max_augmentation_arity)
    if augmentation_arity is not None and augmentation_arity != selected:
        raise ConstraintFieldError("augmentation_arity conflicts with the supplied profile")
    return selected


def _base_result(query: ImplicationQuery, outcome: str, reason: str) -> dict[str, Any]:
    return {
        "schema": IMPLICATION_SCHEMA,
        "outcome": outcome,
        "reason": reason,
        "label": query.label(),
        "assumptions": [[name, value] for name, value in query.assumptions],
        "consequence": [query.consequence[0], query.consequence[1]],
        "compiled": None,
        "literals": None,
        "witness": None,
        "counterexample_verified": False,
        "certificate": None,
        "work": None,
        "state_sha256": None,
    }


def _query_plan(
    query: ImplicationQuery,
    *,
    mode: str,
    profile: ConstraintFieldProfile | None,
    max_transitions: int | None,
    augmentation_arity: int | None,
) -> dict[str, Any]:
    selected_arity = _select_augmentation_arity(profile, augmentation_arity)
    compiled = compile_source(query.source)
    pins, units = _query_units(query, compiled)
    declared = witness_signals(compiled)
    clash = _clashing_unit(query.source, query.assumptions)
    if clash is not None:
        return {
            "selected_arity": selected_arity,
            "compiled": compiled,
            "pins": pins,
            "units": units,
            "declared": declared,
            "clash": clash,
            "augmented": None,
            "query_compiled": None,
            "profile": None,
        }
    augmented = _augmented_source(query.source, pins, units)
    query_compiled = compile_source(augmented)
    if profile is None:
        overrides: dict[str, Any] = (
            {} if max_transitions is None else {"max_transitions": max_transitions}
        )
        if selected_arity != 1:
            overrides["max_augmentation_arity"] = selected_arity
        profile = default_profile(query_compiled, mode=mode, **overrides)
    return {
        "selected_arity": selected_arity,
        "compiled": compiled,
        "pins": pins,
        "units": units,
        "declared": declared,
        "clash": None,
        "augmented": augmented,
        "query_compiled": query_compiled,
        "profile": profile,
    }


def _result_from_field(
    query: ImplicationQuery,
    *,
    query_compiled: CompiledConstraintProblem,
    pins: Sequence[tuple[str, int]],
    units: Sequence[tuple[str, int]],
    declared: Mapping[str, int],
    selected_arity: int,
    result_field: Mapping[str, Any],
) -> dict[str, Any]:
    status = str(result_field["status"])
    try:
        outcome = {"sat": "refuted", "unsat": "holds", "exhausted": "unresolved"}[status]
    except KeyError as exc:
        raise ConstraintFieldError(f"unknown implication field status {status!r}") from exc
    result = _base_result(query, outcome, str(result_field["reason"]))
    result["compiled"] = query_compiled.payload
    result["literals"] = {
        "pin_literals": {
            name: (declared[name] if value == 1 else -declared[name])
            for name, value in pins
        },
        "unit_rows": [[name, value] for name, value in units],
        "consequence_route": "pin" if query.consequence[0] in declared else "clause",
    }
    result["work"] = result_field["work"]
    result["state_sha256"] = result_field["state_sha256"]
    result["augmentation_arity"] = int(selected_arity)

    if status == "unsat":
        hybrid_proof = result_field["hybrid_proof"]
        if hybrid_proof is not None and hybrid_proof["root_line"] is not None:
            kind = "hybrid"
        elif result_field["resolution_proof"] is not None:
            kind = "resolution"
        else:
            kind = "propagation"
        backend_clauses = result_field["backend_clauses"]
        learned_clauses = result_field["learned_clauses"]
        result["certificate"] = {
            "kind": kind,
            "variables": query_compiled.variables,
            "source_clauses": [list(clause) for clause in query_compiled.clauses],
            "backend_clauses": (
                None if backend_clauses is None else [list(clause) for clause in backend_clauses]
            ),
            "learned_clauses": (
                None if learned_clauses is None else [list(clause) for clause in learned_clauses]
            ),
            "resolution_proof": result_field["resolution_proof"],
            "hybrid_proof": hybrid_proof,
        }
        return result

    if status == "sat":
        witness = result_field["witness"]
        if witness is None:
            raise ConstraintFieldError("sat result without a witness")
        for name, value in pins:
            if name not in witness:
                raise ConstraintFieldError("witness does not cover a query literal")
            if int(witness[name]) != value:
                raise ConstraintFieldError("witness contradicts a query literal")
        for name, value in units:
            if signal_value(query.source, witness, name) != value:
                raise ConstraintFieldError("witness refutes a query clause unit")
        if not evaluate_source(query.source, witness):
            raise ConstraintFieldError("counterexample does not satisfy the original source")
        result["witness"] = witness
        result["consequence_value"] = signal_value(
            query.source, witness, query.consequence[0]
        )
        result["counterexample_verified"] = True
    return result


def imply(
    query: ImplicationQuery,
    *,
    mode: str = "algebraic",
    profile: ConstraintFieldProfile | None = None,
    max_transitions: int | None = None,
    augmentation_arity: int | None = None,
) -> dict[str, Any]:
    """Decide one candidate rule and report its evidence class."""

    plan = _query_plan(
        query,
        mode=mode,
        profile=profile,
        max_transitions=max_transitions,
        augmentation_arity=augmentation_arity,
    )
    clash = plan["clash"]
    if clash is not None:
        result = _base_result(query, "vacuous", "declared-boundary-clash")
        result["clash"] = clash
        return result
    query_compiled = plan["query_compiled"]
    selected_arity = int(plan["selected_arity"])
    if not isinstance(query_compiled, CompiledConstraintProblem):
        raise ConstraintFieldError("implication plan has no compiled query")
    field = ConstraintField(plan["profile"])
    state = field.initial(query_compiled)
    while field.status(state) == "running":
        state, _ = field.step(state)
    return _result_from_field(
        query,
        query_compiled=query_compiled,
        pins=plan["pins"],
        units=plan["units"],
        declared=plan["declared"],
        selected_arity=selected_arity,
        result_field=field.result(state),
    )


def _regional_digest(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ConstraintFieldError("implication regional value is not JSON-safe") from exc
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _regional_relation_rows(
    source: Mapping[str, Any],
    *,
    arity: int,
) -> list[dict[str, Any]]:
    """Normalize relation augmentation without retaining a relation object."""

    rows: list[dict[str, Any]] = []
    for index, relation in enumerate(source.get("relations", ())):
        kind = str(relation["kind"])
        arguments = [str(name) for name in relation["args"]]
        if kind == "xor":
            parity: dict[str, int] = {}
            for name in arguments:
                parity[name] = 1 - parity.get(name, 0)
            arguments = sorted(name for name, bit in parity.items() if bit)
        if arity >= 2 and arguments:
            row: dict[str, Any] = {
                "source_index": index,
                "kind": kind,
                "args": arguments,
            }
            for key in ("rhs", "min", "max"):
                if key in relation:
                    row[key] = int(relation[key])
            rows.append(row)
    return rows


def _regional_gate_value(op: str, arguments: Sequence[int], value: Any) -> int:
    if op == "const":
        if value is None:
            raise ConstraintFieldError("constant gate carries no value")
        return int(value)
    if op == "buf":
        return int(arguments[0])
    if op == "not":
        return 1 - int(arguments[0])
    if op == "and":
        return int(arguments[0] & arguments[1])
    if op == "or":
        return int(arguments[0] | arguments[1])
    if op == "nand":
        return 1 - int(arguments[0] & arguments[1])
    if op == "nor":
        return 1 - int(arguments[0] | arguments[1])
    if op == "xor":
        return int(arguments[0] ^ arguments[1])
    if op == "xnor":
        return 1 - int(arguments[0] ^ arguments[1])
    if op == "mux":
        return int(arguments[1] if arguments[0] == 1 else arguments[2])
    raise ConstraintFieldError(f"unsupported regional gate operation {op!r}")


def _regional_circuit_values(
    source: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> dict[str, int]:
    values: dict[str, int] = {}
    for name in source["inputs"]:
        label = str(name)
        if label not in assignment:
            raise ConstraintFieldError(f"regional assignment does not cover {label!r}")
        values[label] = _bit(assignment[label], f"regional assignment {label}")
    pending = [dict(gate) for gate in source.get("gates", ())]
    while pending:
        remaining: list[dict[str, Any]] = []
        progressed = False
        for gate in pending:
            name = str(gate["out"])
            if name in values:
                raise ConstraintFieldError(f"regional gate {name!r} is defined twice")
            arguments = [str(argument) for argument in gate["args"]]
            if not all(argument in values for argument in arguments):
                remaining.append(gate)
                continue
            values[name] = _regional_gate_value(
                str(gate["op"]),
                [values[argument] for argument in arguments],
                gate.get("value"),
            )
            progressed = True
        if not progressed:
            raise ConstraintFieldError("regional gate definitions contain a cycle")
        pending = remaining
    return values


def _regional_relation_holds(
    relation: Mapping[str, Any],
    values: Mapping[str, int],
) -> bool:
    arguments = [int(values[str(name)]) for name in relation["args"]]
    if relation["kind"] == "xor":
        parity = 0
        for bit in arguments:
            parity ^= bit
        return parity == int(relation["rhs"])
    total = sum(arguments)
    return int(relation["min"]) <= total <= int(relation["max"])


def _regional_rows_hold(
    rows: Sequence[Any],
    resolve: Any,
) -> bool:
    for row in rows or ():
        if not any(
            int(resolve(str(literal[0]), int(literal[2]) if len(literal) == 3 else 0))
            == int(literal[1])
            for literal in row
        ):
            return False
    return True


def _regional_transition_values(
    source: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> dict[str, int]:
    state_names = [str(name) for name in source["state"]]
    input_names = [str(name) for name in source["inputs"]]
    horizon = int(source["horizon"])
    values: dict[str, int] = {}
    for name in state_names:
        label = f"{name}@0"
        if label not in assignment:
            raise ConstraintFieldError(f"regional assignment does not cover {label!r}")
        values[f"s:{name}:0"] = _bit(assignment[label], f"regional assignment {label}")
    for name in input_names:
        for time in range(horizon):
            label = f"{name}@{time}"
            if label not in assignment:
                raise ConstraintFieldError(f"regional assignment does not cover {label!r}")
            values[f"i:{name}:{time}"] = _bit(
                assignment[label], f"regional assignment {label}"
            )
    state_set = set(state_names)
    input_set = set(input_names)
    gates = list(source.get("gates", ()))
    for time in range(horizon):
        pending = {str(gate["out"]): dict(gate) for gate in gates}
        computed: dict[str, int] = {}

        def argument_value(argument: str) -> int | None:
            if argument in computed:
                return computed[argument]
            if argument in state_set:
                return values[f"s:{argument}:{time}"]
            if argument in input_set:
                return values[f"i:{argument}:{time}"]
            return None

        while pending:
            progressed = False
            for name in list(pending):
                gate = pending[name]
                arguments = [argument_value(str(argument)) for argument in gate["args"]]
                if any(argument is None for argument in arguments):
                    continue
                computed[name] = _regional_gate_value(
                    str(gate["op"]),
                    [int(argument) for argument in arguments if argument is not None],
                    gate.get("value"),
                )
                values[f"g:{name}:{time}"] = computed[name]
                del pending[name]
                progressed = True
            if not progressed:
                raise ConstraintFieldError("regional gate definitions contain a cycle")
        for target, origin in source.get("next_state", ()):
            target_name = str(target)
            origin_name = str(origin)
            if origin_name in state_set:
                origin_value = values[f"s:{origin_name}:{time}"]
            elif origin_name in input_set:
                origin_value = values[f"i:{origin_name}:{time}"]
            else:
                origin_value = values[f"g:{origin_name}:{time}"]
            values[f"s:{target_name}:{time + 1}"] = int(origin_value)
    return values


def _regional_signal_value(
    source: Mapping[str, Any],
    assignment: Mapping[str, int],
    label: str,
) -> int:
    if source.get("kind") == "circuit":
        values = _regional_circuit_values(source, assignment)
        if label not in values:
            raise ConstraintFieldError(f"regional signal {label!r} is not declared")
        return int(values[label])
    if source.get("kind") != "transition":
        raise ConstraintFieldError("regional source kind is unsupported")
    stem, separator, index = label.rpartition("@")
    if separator:
        if not stem or not index.isdigit():
            raise ConstraintFieldError(f"regional signal {label!r} is not time-qualified")
        time = int(index)
    else:
        stem = label
        time = 0
    horizon = int(source["horizon"])
    if time > horizon:
        raise ConstraintFieldError(f"regional signal {label!r} exceeds the horizon")
    values = _regional_transition_values(source, assignment)
    state_names = {str(name) for name in source["state"]}
    input_names = {str(name) for name in source["inputs"]}
    if stem in state_names:
        return int(values[f"s:{stem}:{time}"])
    if stem in input_names:
        return int(values[f"i:{stem}:{time}"])
    return int(values[f"g:{stem}:{time}"])


def _regional_source_holds(
    source: Mapping[str, Any],
    assignment: Mapping[str, int],
) -> bool:
    if source.get("kind") == "circuit":
        values = _regional_circuit_values(source, assignment)
        for name, value in source.get("assertions", ()):
            if values[str(name)] != int(value):
                return False
        for relation in source.get("relations", ()):
            if not _regional_relation_holds(relation, values):
                return False
        return _regional_rows_hold(
            source.get("clauses", ()),
            lambda name, _time: values[name],
        )
    if source.get("kind") != "transition":
        raise ConstraintFieldError("regional source kind is unsupported")
    values = _regional_transition_values(source, assignment)
    state_names = {str(name) for name in source["state"]}
    input_names = {str(name) for name in source["inputs"]}
    horizon = int(source["horizon"])

    def resolve(name: str, time: int) -> int:
        if name in input_names:
            return values[f"i:{name}:{time}"]
        if name in state_names:
            return values[f"s:{name}:{time}"]
        return values[f"g:{name}:{time}"]

    for name, value in source.get("initial", ()):
        if resolve(str(name), 0) != int(value):
            return False
    for time, name, value in source.get("input_assertions", ()):
        if int(time) < 0 or int(time) >= horizon:
            raise ConstraintFieldError("regional input assertion time is invalid")
        if resolve(str(name), int(time)) != int(value):
            return False
    for name, value in source.get("final", ()):
        if resolve(str(name), horizon) != int(value):
            return False
    for time in range(horizon):
        for relation in source.get("relations", ()):
            relation_values = {
                str(name): resolve(str(name), time) for name in relation["args"]
            }
            if not _regional_relation_holds(relation, relation_values):
                return False
    return _regional_rows_hold(source.get("clauses", ()), resolve)


def _regional_work(
    *,
    compiled: Mapping[str, Any],
    query_compiled: Mapping[str, Any],
    counters: Mapping[str, int],
    cursor: int,
    total: int,
    augmentation_count: int,
) -> dict[str, Any]:
    return {
        "compile": dict(compiled.get("work", {})),
        "prepass": {"status": "direct-enumeration"},
        "hybrid": None,
        "search": {
            "status": "running" if cursor < total else "complete",
            "transitions": int(cursor),
            "candidates": int(counters["candidates"]),
        },
        "controller": {
            "ticks": 0,
            "selections": 0,
            "interventions": 0,
            "enabled": False,
        },
        "journal_bytes": 0,
        "augmentations": int(augmentation_count),
        "enumeration": dict(counters),
        "query_variables": int(query_compiled.get("variables", 0)),
    }


def _regional_result(
    query: ImplicationQuery,
    *,
    query_compiled: Mapping[str, Any],
    pins: Sequence[tuple[str, int]],
    units: Sequence[tuple[str, int]],
    declared: Mapping[str, int],
    selected_arity: int,
    status: str,
    reason: str,
    witness: Mapping[str, int] | None,
    consequence_value: int | None,
    certificate: Mapping[str, Any] | None,
    work: Mapping[str, Any],
    state_sha256: str,
) -> dict[str, Any]:
    outcome = {"sat": "refuted", "unsat": "holds", "exhausted": "unresolved"}[status]
    result = _base_result(query, outcome, reason)
    result["compiled"] = {
        key: value for key, value in query_compiled.items() if key != "sha256"
    }
    result["literals"] = {
        "pin_literals": {
            name: (declared[name] if value == 1 else -declared[name])
            for name, value in pins
        },
        "unit_rows": [[name, value] for name, value in units],
        "consequence_route": "pin" if query.consequence[0] in declared else "clause",
    }
    result["work"] = dict(work)
    result["state_sha256"] = state_sha256
    result["augmentation_arity"] = int(selected_arity)
    if status == "sat":
        if witness is None or consequence_value is None:
            raise ConstraintFieldError("regional sat result lacks its witness")
        if not _regional_source_holds(query.source, witness):
            raise ConstraintFieldError("regional counterexample does not satisfy the source")
        for name, value in pins:
            if int(witness[name]) != value:
                raise ConstraintFieldError("regional witness contradicts a query pin")
        for name, value in units:
            if _regional_signal_value(query.source, witness, name) != value:
                raise ConstraintFieldError("regional witness refutes a query unit")
        result["witness"] = dict(witness)
        result["consequence_value"] = int(consequence_value)
        result["counterexample_verified"] = True
    elif status == "unsat":
        result["certificate"] = dict(certificate or {})
    result["evidence"] = {
        "class": result["outcome"],
        "reason": result["reason"],
        "witness": result.get("witness"),
        "certificate": result.get("certificate"),
        "counterexample_verified": bool(result.get("counterexample_verified")),
    }
    return result

def regional_state(
    query: ImplicationQuery,
    *,
    mode: str = "algebraic",
    profile: ConstraintFieldProfile | None = None,
    max_transitions: int | None = None,
    augmentation_arity: int | None = None,
) -> dict[str, Any]:
    """Encode implication continuation as typed canonical JSON data."""

    plan = _query_plan(
        query,
        mode=mode,
        profile=profile,
        max_transitions=max_transitions,
        augmentation_arity=augmentation_arity,
    )
    selected_arity = int(plan["selected_arity"])
    compiled = plan["compiled"]
    augmentation: dict[str, Any] = {
        "arity": selected_arity,
        "pins": [[name, value] for name, value in plan["pins"]],
        "units": [[name, value] for name, value in plan["units"]],
        "relations": _regional_relation_rows(query.source, arity=selected_arity),
        "source": None,
        "compiled": None,
    }
    if plan["augmented"] is not None:
        query_compiled = plan["query_compiled"]
        augmentation["source"] = _json_safe(plan["augmented"])
        augmentation["compiled"] = _json_safe(query_compiled.as_dict())
    counters = {
        "candidates": 0,
        "source_models": 0,
        "premise_models": 0,
        "assumption_rejections": 0,
        "consequence_rejections": 0,
    }
    continuation: dict[str, Any] = {
        "query": {
            "assumptions": [[name, value] for name, value in query.assumptions],
            "consequence": [query.consequence[0], query.consequence[1]],
        },
        "compiled": _json_safe(compiled.as_dict()),
        "query_compiled": (
            None
            if plan["query_compiled"] is None
            else _json_safe(plan["query_compiled"].as_dict())
        ),
        "witness_signals": [
            [label, identifier] for label, identifier in compiled.witness_signals
        ],
        "augmentation": augmentation,
        "cursor": 0,
        "total": 0,
        "budget": 0,
        "assignment": None,
        "candidate": None,
        "progress": {
            "candidate": None,
            "proof": {
                "checked_assignments": 0,
                "source_models": 0,
                "premise_models": 0,
            },
        },
    }
    base_state = {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": _json_safe(dict(query.source)),
        "profile": (
            None if plan["profile"] is None else _json_safe(plan["profile"].as_dict())
        ),
        "phase": "search",
        "continuation": continuation,
        "journal": [],
        "ledger": {
            "cumulative_work": 0,
            "counters": counters,
        },
        "result": None,
    }
    clash = plan["clash"]
    if clash is not None:
        result = _base_result(query, "vacuous", "declared-boundary-clash")
        result["clash"] = clash
        result["evidence"] = {
            "class": "vacuous",
            "reason": "declared-boundary-clash",
            "clash": clash,
        }
        base_state["phase"] = "terminal"
        base_state["result"] = result
        return _json_safe(base_state)
    query_compiled = plan["query_compiled"]
    selected_profile = plan["profile"]
    if not isinstance(query_compiled, CompiledConstraintProblem):
        raise ConstraintFieldError("implication regional plan has no compiled query")
    if not isinstance(selected_profile, ConstraintFieldProfile):
        raise ConstraintFieldError("implication regional plan has no profile")
    labels = [label for label, _ in compiled.witness_signals]
    total = 1 << len(labels)
    budget = min(total, int(selected_profile.max_transitions))
    continuation["total"] = total
    continuation["budget"] = budget
    continuation["progress"]["total_candidates"] = total
    continuation["progress"]["candidate_budget"] = budget
    return _json_safe(base_state)


def _regional_decode(
    state: Mapping[str, Any],
) -> tuple[
    ImplicationQuery,
    Mapping[str, Any],
    Mapping[str, Any],
    list[str],
    list[tuple[str, int]],
    list[tuple[str, int]],
    dict[str, int],
    int,
]:
    required = {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
    if not isinstance(state, Mapping) or state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise ConstraintFieldError("implication regional state schema is invalid")
    if set(state) != required:
        raise ConstraintFieldError("implication regional state keys are invalid")
    if state["phase"] != "search" or state["result"] is not None:
        raise ConstraintFieldError("implication regional state is not running")
    source = state["source"]
    profile = state["profile"]
    continuation = state["continuation"]
    journal = state["journal"]
    ledger = state["ledger"]
    if (
        not isinstance(source, Mapping)
        or not isinstance(profile, Mapping)
        or not isinstance(continuation, Mapping)
        or not isinstance(journal, list)
        or not isinstance(ledger, Mapping)
    ):
        raise ConstraintFieldError("implication regional envelope is invalid")
    query_value = continuation.get("query")
    if not isinstance(query_value, Mapping):
        raise ConstraintFieldError("implication regional query is invalid")
    assumptions_value = query_value.get("assumptions")
    consequence_value = query_value.get("consequence")
    if not isinstance(assumptions_value, list) or not isinstance(consequence_value, list):
        raise ConstraintFieldError("implication regional query is invalid")
    if len(consequence_value) != 2 or not isinstance(consequence_value[0], str):
        raise ConstraintFieldError("implication regional consequence is invalid")
    assumptions: list[tuple[str, int]] = []
    for row in assumptions_value:
        if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str):
            raise ConstraintFieldError("implication regional assumptions are invalid")
        assumptions.append((row[0], _bit(row[1], "regional assumption")))
    query = ImplicationQuery(
        source=source,
        consequence=(
            consequence_value[0],
            _bit(consequence_value[1], "regional consequence"),
        ),
        assumptions=tuple(assumptions),
    )
    compiled_value = continuation.get("compiled")
    query_compiled_value = continuation.get("query_compiled")
    labels_value = continuation.get("witness_signals")
    augmentation = continuation.get("augmentation")
    progress = continuation.get("progress")
    if (
        not isinstance(compiled_value, Mapping)
        or not isinstance(query_compiled_value, Mapping)
        or not isinstance(labels_value, list)
        or not isinstance(augmentation, Mapping)
        or not isinstance(progress, Mapping)
    ):
        raise ConstraintFieldError("implication regional continuation is invalid")
    compiled = compile_source(source)
    if _json_safe(compiled.as_dict()) != _json_safe(dict(compiled_value)):
        raise ConstraintFieldError("implication regional source digest mismatch")
    labels: list[str] = []
    declared: dict[str, int] = {}
    for row in labels_value:
        if not isinstance(row, list) or len(row) != 2 or not isinstance(row[0], str):
            raise ConstraintFieldError("implication regional witness labels are invalid")
        labels.append(row[0])
        identifier = row[1]
        if (
            isinstance(identifier, bool)
            or not isinstance(identifier, int)
            or not 1 <= identifier <= compiled.variables
        ):
            raise ConstraintFieldError(
                "regional witness identifier is invalid"
            )
        declared[row[0]] = identifier
    if tuple((label, declared[label]) for label in labels) != compiled.witness_signals:
        raise ConstraintFieldError("implication regional witness labels mismatch")
    pins, units = _query_units(query, compiled)
    arity = augmentation.get("arity")
    if isinstance(arity, bool) or not isinstance(arity, int) or arity not in (1, 2):
        raise ConstraintFieldError("implication regional augmentation arity is invalid")
    max_augmentation_arity = profile.get("max_augmentation_arity")
    if arity != max_augmentation_arity:
        raise ConstraintFieldError("implication regional augmentation arity mismatch")
    expected_augmented = _augmented_source(source, pins, units)
    expected_query_compiled = compile_source(expected_augmented)
    if _json_safe(expected_query_compiled.as_dict()) != _json_safe(dict(query_compiled_value)):
        raise ConstraintFieldError("implication regional query source mismatch")
    if augmentation.get("pins") != [[name, value] for name, value in pins]:
        raise ConstraintFieldError("implication regional pin augmentation mismatch")
    if augmentation.get("units") != [[name, value] for name, value in units]:
        raise ConstraintFieldError("implication regional unit augmentation mismatch")
    if augmentation.get("source") != _json_safe(expected_augmented):
        raise ConstraintFieldError("implication regional augmentation source mismatch")
    if augmentation.get("relations") != _regional_relation_rows(source, arity=arity):
        raise ConstraintFieldError("implication regional relation augmentation mismatch")
    max_transitions = profile.get("max_transitions")
    if (
        isinstance(max_transitions, bool)
        or not isinstance(max_transitions, int)
        or max_transitions < 1
    ):
        raise ConstraintFieldError("implication regional transition budget is invalid")
    cursor_value = continuation.get("cursor")
    total_value = continuation.get("total")
    budget_value = continuation.get("budget")
    if (
        isinstance(cursor_value, bool)
        or not isinstance(cursor_value, int)
        or cursor_value < 0
        or isinstance(total_value, bool)
        or not isinstance(total_value, int)
        or total_value < 1
        or isinstance(budget_value, bool)
        or not isinstance(budget_value, int)
        or budget_value < 1
    ):
        raise ConstraintFieldError("implication regional continuation counters are invalid")
    cursor = cursor_value
    total = total_value
    budget = budget_value
    if total != 1 << len(labels) or budget != min(total, max_transitions):
        raise ConstraintFieldError("implication regional continuation bounds mismatch")
    if cursor > total or cursor > budget:
        raise ConstraintFieldError("implication regional cursor exceeds its bound")
    cumulative = ledger.get("cumulative_work")
    counters = ledger.get("counters")
    if (
        isinstance(cumulative, bool)
        or not isinstance(cumulative, int)
        or cumulative < 0
        or not isinstance(counters, Mapping)
    ):
        raise ConstraintFieldError("implication regional ledger is invalid")
    expected_counter_names = {
        "candidates",
        "source_models",
        "premise_models",
        "assumption_rejections",
        "consequence_rejections",
    }
    if set(counters) != expected_counter_names or any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counters.values()
    ):
        raise ConstraintFieldError("implication regional counters are invalid")
    if cumulative != cursor or counters["candidates"] != cursor:
        raise ConstraintFieldError("implication regional ledger/cursor mismatch")
    if len(journal) != cursor or any(
        not isinstance(row, Mapping) or row.get("cursor") != index
        for index, row in enumerate(journal)
    ):
        raise ConstraintFieldError("implication regional journal/cursor mismatch")
    proof = progress.get("proof")
    if not isinstance(proof, Mapping):
        raise ConstraintFieldError("implication regional proof progress is invalid")
    if (
        proof.get("checked_assignments") != counters["candidates"]
        or proof.get("source_models") != counters["source_models"]
        or proof.get("premise_models") != counters["premise_models"]
    ):
        raise ConstraintFieldError("implication regional proof progress mismatch")
    if progress.get("candidate") != (journal[-1] if journal else None):
        raise ConstraintFieldError("implication regional candidate progress mismatch")
    return (
        query,
        compiled.as_dict(),
        expected_query_compiled.as_dict(),
        labels,
        pins,
        units,
        declared,
        cursor,
    )


def _regional_assignment(labels: Sequence[str], cursor: int) -> dict[str, int]:
    width = len(labels)
    return {
        label: (cursor >> (width - index - 1)) & 1
        for index, label in enumerate(labels)
    }


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Perform bounded direct implication candidate work over typed state."""

    if not isinstance(arguments, Mapping) or arguments:
        raise ConstraintFieldError("implication regional kernel takes no arguments")
    if isinstance(quantum, bool) or not isinstance(quantum, int):
        raise ConstraintFieldError("implication regional quantum must be an exact integer")
    if quantum < 1 or quantum > REGIONAL_KERNEL_MAX_WORK:
        raise ConstraintFieldError(
            f"implication regional quantum must be in [1, {REGIONAL_KERNEL_MAX_WORK}]"
        )
    if not isinstance(state, Mapping) or state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise ConstraintFieldError("implication regional state schema is invalid")
    required = {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
    if set(state) != required:
        raise ConstraintFieldError("implication regional state keys are invalid")
    if state.get("phase") == "terminal":
        result = state.get("result")
        if not isinstance(result, Mapping):
            raise ConstraintFieldError("implication regional terminal result is invalid")
        return KernelResult(
            state=_json_safe(dict(state)),
            status="done",
            work=0,
            output=_json_safe(dict(result)),
        )
    if state.get("phase") != "search":
        raise ConstraintFieldError("implication regional phase is invalid")
    (
        query,
        compiled,
        query_compiled,
        labels,
        pins,
        units,
        declared,
        cursor,
    ) = _regional_decode(state)
    continuation = dict(state["continuation"])
    progress = dict(continuation["progress"])
    ledger = dict(state["ledger"])
    counters = dict(ledger["counters"])
    journal = list(state["journal"])
    total = int(continuation["total"])
    budget = int(continuation["budget"])
    used = 0
    witness: dict[str, int] | None = None
    consequence_value: int | None = None
    while used < quantum and cursor < budget:
        assignment = _regional_assignment(labels, cursor)
        counters["candidates"] += 1
        source_ok = _regional_source_holds(query.source, assignment)
        candidate = {
            "cursor": cursor,
            "assignment": assignment,
            "source_holds": bool(source_ok),
            "assumptions_hold": False,
            "consequence_value": None,
        }
        found = False
        if source_ok:
            counters["source_models"] += 1
            assumption_values = all(
                _regional_signal_value(query.source, assignment, name) == value
                for name, value in query.assumptions
            )
            candidate["assumptions_hold"] = assumption_values
            if assumption_values:
                counters["premise_models"] += 1
                consequence_value = _regional_signal_value(
                    query.source,
                    assignment,
                    query.consequence[0],
                )
                candidate["consequence_value"] = consequence_value
                if consequence_value != query.consequence[1]:
                    witness = assignment
                    found = True
                else:
                    counters["consequence_rejections"] += 1
            else:
                counters["assumption_rejections"] += 1
        cursor += 1
        used += 1
        continuation["cursor"] = cursor
        continuation["assignment"] = assignment
        continuation["candidate"] = candidate
        progress["candidate"] = candidate
        journal.append(candidate)
        if found:
            break
    if witness is not None:
        terminal_status = "sat"
        terminal_reason = "model"
        phase = "terminal"
    elif cursor >= total:
        terminal_status = "unsat"
        terminal_reason = "exhaustive-enumeration"
        phase = "terminal"
    elif cursor >= budget:
        terminal_status = "exhausted"
        terminal_reason = "transition-budget"
        phase = "terminal"
    else:
        terminal_status = None
        terminal_reason = None
        phase = "search"
    cumulative = int(ledger["cumulative_work"]) + used
    augmentation = continuation["augmentation"]
    augmentation_count = len(augmentation["relations"])
    work = _regional_work(
        compiled=compiled,
        query_compiled=query_compiled,
        counters=counters,
        cursor=cursor,
        total=total,
        augmentation_count=augmentation_count,
    )
    continuation["cursor"] = cursor
    continuation["total"] = total
    continuation["budget"] = budget
    progress["counters"] = counters
    progress["proof"] = {
        "checked_assignments": int(counters["candidates"]),
        "source_models": int(counters["source_models"]),
        "premise_models": int(counters["premise_models"]),
    }
    continuation["progress"] = progress
    ledger["cumulative_work"] = cumulative
    ledger["counters"] = counters
    outcome = None
    output = None
    if terminal_status is not None:
        state_digest = _regional_digest(
            {
                "compiled": compiled,
                "query_compiled": query_compiled,
                "cursor": cursor,
                "counters": counters,
            }
        )
        certificate = None
        if terminal_status == "unsat":
            certificate = {
                "kind": "exhaustive-enumeration",
                "source_sha256": compiled["sha256"],
                "query_sha256": query_compiled["sha256"],
                "witness_signals": list(labels),
                "assignments_checked": int(counters["candidates"]),
                "source_models": int(counters["source_models"]),
                "premise_models": int(counters["premise_models"]),
                "counterexamples": 0,
                "proof_journal": list(journal),
            }
        outcome = _regional_result(
            query,
            query_compiled=query_compiled,
            pins=pins,
            units=units,
            declared=declared,
            selected_arity=int(augmentation["arity"]),
            status=terminal_status,
            reason=terminal_reason or "terminal",
            witness=witness,
            consequence_value=consequence_value,
            certificate=certificate,
            work=work,
            state_sha256=state_digest,
        )
        output = outcome
        journal.append(
            {
                "kind": "terminal-evidence",
                "class": outcome["outcome"],
                "reason": outcome["reason"],
            }
        )
    next_state = _json_safe(
        {
            **dict(state),
            "phase": phase,
            "continuation": continuation,
            "journal": journal,
            "ledger": ledger,
            "result": outcome,
        }
    )
    return KernelResult(
        state=next_state,
        status="yield" if phase != "terminal" else "done",
        work=used,
        output=output,
    )
__all__ = [
    "IMPLICATION_SCHEMA",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_STATE_SCHEMA",
    "ImplicationQuery",
    "compile_source",
    "default_profile",
    "evaluate_source",
    "imply",
    "regional_kernel",
    "regional_state",
    "rule_label",
    "signal_value",
    "witness_signals",
]
