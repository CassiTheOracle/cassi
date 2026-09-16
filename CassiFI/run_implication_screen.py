"""Measure implication outcomes over small declared CassiFI sources.

The runner builds a deterministic matrix of exact-one, parity, cubic/Schaefer,
and transition sources, decides bounded candidate rules with the frozen
implication engine, independently enumerates each small source, audits every
available certificate, and writes a machine-checkable receipt.
"""

from __future__ import annotations

import itertools
import json
import platform
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_alias_exact_one_field import regular_monotone_formula
from cassi_constraint_implication import ImplicationQuery, compile_source, imply, rule_label, witness_signals
from cubic_kernel_decision import canonical_cubic_formula, cubic_kernel_profile, incidence_connected
from run_mixed_schaefer_frame_obstruction import mixed_formula
import verify_hybrid_inference as hybrid_audit
import verify_p_vs_np_clause_field_probe as clause_audit

OUTPUT = Path("_diag/implication_screen.json")
SCHEMA = "cassifi.implication-screen.v1"
UNRESOLVED_BOUND = 1


def _exact_one_clauses(names: Sequence[str]) -> list[list[list[Any]]]:
    rows: list[list[list[Any]]] = [[[name, 1] for name in names]]
    rows.extend([[left, 0], [right, 0]] for left, right in itertools.combinations(names, 2))
    return rows


def _formula_source(names: Sequence[str], formula: Sequence[Sequence[int]]) -> dict[str, Any]:
    clauses: list[list[list[Any]]] = []
    for row in formula:
        clauses.extend(_exact_one_clauses([names[int(variable) - 1] for variable in row]))
    return {"kind": "circuit", "inputs": list(names), "gates": [], "assertions": [], "relations": [], "clauses": clauses}


def _build_sources() -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    alias3 = {"kind": "circuit", "inputs": ["a", "b", "c"], "gates": [], "assertions": [], "relations": [{"kind": "cardinality", "args": ["a", "b", "c"], "min": 1, "max": 1}], "clauses": [[["a", 1], ["b", 0]], [["a", 0], ["b", 1]]]}
    sources.append({"name": "alias-cardinality-3", "family": "alias/exact-one", "source": alias3, "extras": []})
    alias4 = {"kind": "circuit", "inputs": ["x0", "x1", "x2", "x3"], "gates": [], "assertions": [], "relations": [{"kind": "cardinality", "args": ["x0", "x1", "x2", "x3"], "min": 1, "max": 1}], "clauses": [[["x0", 1], ["x1", 0]], [["x0", 0], ["x1", 1]]]}
    sources.append({"name": "alias-cardinality-4", "family": "alias/exact-one", "source": alias4, "extras": []})
    regular = _formula_source([f"r{index}" for index in range(1, 7)], regular_monotone_formula(4, 0, seed=20260910))
    sources.append({"name": "alias-regular-incidence", "family": "alias/exact-one", "source": regular, "extras": []})

    parity_equal = {"kind": "circuit", "inputs": ["p", "q", "r"], "gates": [], "assertions": [], "relations": [{"kind": "xor", "args": ["p", "q"], "rhs": 0}, {"kind": "xor", "args": ["p", "q", "r"], "rhs": 0}], "clauses": []}
    sources.append({"name": "parity-two-three", "family": "parity/GF(2)", "source": parity_equal, "extras": []})
    parity_force = {"kind": "circuit", "inputs": ["p", "q", "r"], "gates": [], "assertions": [], "relations": [{"kind": "xor", "args": ["p", "q"], "rhs": 1}, {"kind": "xor", "args": ["p", "q", "r"], "rhs": 1}], "clauses": []}
    sources.append({"name": "parity-forced-support", "family": "parity/GF(2)", "source": parity_force, "extras": []})
    parity_conflict = {"kind": "circuit", "inputs": ["u", "v"], "gates": [], "assertions": [], "relations": [{"kind": "xor", "args": ["u", "v"], "rhs": 0}, {"kind": "xor", "args": ["u", "v"], "rhs": 1}], "clauses": []}
    sources.append({"name": "parity-inconsistency", "family": "parity/GF(2)", "source": parity_conflict, "extras": []})

    cubic_formula = canonical_cubic_formula(((1, 2, 3), (1, 2, 3), (1, 2, 3)))
    cubic_source = _formula_source(["a", "b", "c"], cubic_formula)
    sources.append({"name": "cubic-clause-exact-one", "family": "cubic/Schaefer", "source": cubic_source, "extras": []})
    pinned_cubic = _formula_source(["a", "b", "c"], cubic_formula)
    pinned_cubic["assertions"] = [["b", 0]]
    sources.append({"name": "cubic-two-pinned-neighbours", "family": "cubic/Schaefer", "source": pinned_cubic, "extras": [("c", 1, (("a", 0),))]})
    mixed_row = tuple(mixed_formula()[0])
    local_ids = {variable: index + 1 for index, variable in enumerate(sorted(mixed_row))}
    mixed_source = _formula_source(["m0", "m1", "m2"], (tuple(local_ids[variable] for variable in mixed_row),))
    sources.append({"name": "schaefer-mixed-local", "family": "cubic/Schaefer", "source": mixed_source, "extras": []})
    unresolved_source = {"kind": "circuit", "inputs": ["a", "b", "c"], "gates": [], "assertions": [], "relations": [], "clauses": [[["a", 1], ["b", 1]], [["b", 1], ["c", 1]], [["a", 1], ["c", 1]], [["a", 0], ["b", 0]], [["b", 0], ["c", 0]], [["a", 0], ["c", 0]]]}
    sources.append({"name": "schaefer-local-bound", "family": "cubic/Schaefer", "source": unresolved_source, "extras": []})

    transition_copy = {"kind": "transition", "state": ["p"], "inputs": ["u"], "gates": [], "next_state": [["p", "u"]], "horizon": 2, "initial": [["p", 0]], "input_assertions": [], "final": [], "relations": [], "clauses": []}
    sources.append({"name": "transition-copy", "family": "transition", "source": transition_copy, "extras": [("p@1", 1, (("u@0", 1),)), ("p@2", 1, (("u@0", 1), ("u@1", 1)))]})
    transition_toggle = {"kind": "transition", "state": ["p"], "inputs": ["u"], "gates": [{"op": "not", "out": "n", "args": ["u"]}], "next_state": [["p", "n"]], "horizon": 2, "initial": [["p", 0]], "input_assertions": [], "final": [], "relations": [], "clauses": []}
    sources.append({"name": "transition-toggle", "family": "transition", "source": transition_toggle, "extras": [("p@1", 1, (("u@0", 0),)), ("p@2", 0, (("u@0", 1), ("u@1", 1)))]})
    transition_boundary = {"kind": "transition", "state": ["p"], "inputs": ["u"], "gates": [], "next_state": [["p", "u"]], "horizon": 1, "initial": [["p", 1]], "input_assertions": [[0, "u", 1]], "final": [], "relations": [], "clauses": []}
    sources.append({"name": "transition-boundary", "family": "transition", "source": transition_boundary, "extras": [("p@1", 1, (("u@0", 1),))]})
    return sources


def _gate_value(op: str, args: Sequence[int], value: int | None = None) -> int:
    if op == "const": return int(value)
    if op == "buf": return int(args[0])
    if op == "not": return 1 - int(args[0])
    if op == "and": return int(all(args))
    if op == "or": return int(any(args))
    if op == "xor":
        result = 0
        for bit in args: result ^= int(bit)
        return result
    if op == "nand": return 1 - int(all(args))
    if op == "nor": return 1 - int(any(args))
    if op == "xnor":
        result = 0
        for bit in args: result ^= int(bit)
        return 1 - result
    if op == "mux": return int(args[1] if args[0] else args[2])
    raise ValueError(op)


def _resolve_circuit(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    values = {str(name): int(assignment[str(name)]) for name in source["inputs"]}
    pending = [dict(gate) for gate in source.get("gates", ())]
    while pending:
        rest: list[dict[str, Any]] = []
        progressed = False
        for gate in pending:
            args = [str(arg) for arg in gate["args"]]
            if all(arg in values for arg in args):
                values[str(gate["out"])] = _gate_value(str(gate["op"]), [values[arg] for arg in args], gate.get("value"))
                progressed = True
            else: rest.append(gate)
        if not progressed: raise ValueError("cyclic or unknown circuit gate")
        pending = rest
    return values


def _rows_hold(rows: Sequence[Any], resolver: Any) -> bool:
    return all(any(int(resolver(str(literal[0]), int(literal[2]) if len(literal) == 3 else 0)) == int(literal[1]) for literal in row) for row in rows or ())


def _relation_holds(relation: Mapping[str, Any], values: Mapping[str, int]) -> bool:
    bits = [int(values[str(name)]) for name in relation["args"]]
    if relation["kind"] == "xor":
        parity = 0
        for bit in bits: parity ^= bit
        return parity == int(relation["rhs"])
    return int(relation["min"]) <= sum(bits) <= int(relation["max"])


def _own_values(source: Mapping[str, Any], assignment: Mapping[str, int]) -> dict[str, int]:
    if source["kind"] == "circuit": return _resolve_circuit(source, assignment)
    state = tuple(str(name) for name in source["state"]); inputs = tuple(str(name) for name in source["inputs"]); horizon = int(source["horizon"])
    values: dict[str, int] = {f"s:{name}:0": int(assignment[f"{name}@0"]) for name in state}
    values.update({f"i:{name}:{time_index}": int(assignment[f"{name}@{time_index}"]) for time_index in range(horizon) for name in inputs})
    for time_index in range(horizon):
        local = {name: values[f"s:{name}:{time_index}"] for name in state}; local.update({name: values[f"i:{name}:{time_index}"] for name in inputs})
        pending = [dict(gate) for gate in source.get("gates", ())]
        while pending:
            rest: list[dict[str, Any]] = []; progressed = False
            for gate in pending:
                args = [str(arg) for arg in gate["args"]]
                if all(arg in local for arg in args):
                    gate_name = str(gate["out"]); gate_result = _gate_value(str(gate["op"]), [local[arg] for arg in args], gate.get("value"))
                    local[gate_name] = gate_result; values[f"g:{gate_name}:{time_index}"] = gate_result; progressed = True
                else: rest.append(gate)
            if not progressed: raise ValueError("cyclic or unknown transition gate")
            pending = rest
        for name in state:
            origin = next(origin for target, origin in source["next_state"] if target == name)
            values[f"s:{name}:{time_index + 1}"] = int(local[str(origin)])
    return values


def _own_signal(source: Mapping[str, Any], assignment: Mapping[str, int], label: str, values: Mapping[str, int] | None = None) -> int:
    values = values if values is not None else _own_values(source, assignment)
    if source["kind"] == "circuit": return int(values[label])
    stem, _, index_text = label.partition("@"); time_index = int(index_text) if index_text else 0
    if stem in source["state"]: return int(values[f"s:{stem}:{time_index}"])
    if stem in source["inputs"]: return int(values[f"i:{stem}:{time_index}"])
    return int(values[f"g:{stem}:{time_index}"])


def _own_holds(source: Mapping[str, Any], assignment: Mapping[str, int]) -> bool:
    if source["kind"] == "circuit":
        values = _resolve_circuit(source, assignment)
        return all(values[str(name)] == int(bit) for name, bit in source.get("assertions", ())) and all(_relation_holds(relation, values) for relation in source.get("relations", ())) and _rows_hold(source.get("clauses", ()), lambda name, _time: values[name])
    values = _own_values(source, assignment); state = set(source["state"]); inputs = set(source["inputs"]); horizon = int(source["horizon"])
    def resolve(name: str, time_index: int) -> int:
        if name in state: return int(values[f"s:{name}:{time_index}"])
        if name in inputs: return int(values[f"i:{name}:{time_index}"])
        return int(values[f"g:{name}:{time_index}"])
    if not all(resolve(str(name), 0) == int(bit) for name, bit in source.get("initial", ())): return False
    if not all(resolve(str(name), int(time_index)) == int(bit) for time_index, name, bit in source.get("input_assertions", ())): return False
    if not all(resolve(str(name), horizon) == int(bit) for name, bit in source.get("final", ())): return False
    if not all(_relation_holds(relation, {str(name): resolve(str(name), time_index) for name in relation["args"]}) for time_index in range(horizon) for relation in source.get("relations", ())): return False
    return _rows_hold(source.get("clauses", ()), resolve)


def _witness_labels(source: Mapping[str, Any]) -> list[str]:
    if source["kind"] == "circuit": return [str(name) for name in source["inputs"]]
    labels = [f"{name}@0" for name in source["state"]]
    labels.extend(f"{name}@{time_index}" for time_index in range(int(source["horizon"])) for name in source["inputs"])
    return labels


def _enumerate(source: Mapping[str, Any]) -> list[dict[str, int]]:
    labels = _witness_labels(source)
    return [dict(zip(labels, bits)) for bits in itertools.product((0, 1), repeat=len(labels)) if _own_holds(source, dict(zip(labels, bits)))]


def _declared_boundary_literals(source: Mapping[str, Any]) -> set[tuple[str, int]]:
    rows: set[tuple[str, int]] = set()
    if source["kind"] == "circuit":
        rows.update((str(name), int(bit)) for name, bit in source.get("assertions", ()))
        rows.update((str(clause[0][0]), int(clause[0][1])) for clause in source.get("clauses", ()) if len(clause) == 1)
    else:
        rows.update((f"{name}@0", int(bit)) for name, bit in source.get("initial", ()))
        rows.update((f"{name}@{int(time_index)}", int(bit)) for time_index, name, bit in source.get("input_assertions", ()))
        rows.update((f"{name}@{int(source['horizon'])}", int(bit)) for name, bit in source.get("final", ()))
        rows.update((f"{clause[0][0]}@{int(clause[0][2]) if len(clause[0]) == 3 else 0}", int(clause[0][1])) for clause in source.get("clauses", ()) if len(clause) == 1)
    return rows


def _boundary_clash(
    source: Mapping[str, Any], assumptions: Sequence[tuple[str, int]]
) -> bool:
    boundaries = _declared_boundary_literals(source)
    return any(
        (str(name), 1 - int(value)) in boundaries
        for name, value in assumptions
    )


def _make_rule_specs(record: Mapping[str, Any]) -> list[tuple[tuple[str, int], tuple[tuple[str, int], ...]]]:
    source = record["source"]; witness = _witness_labels(source); labels = list(witness)
    if source["kind"] == "transition": labels.extend(f"{state}@{time_index}" for time_index in range(1, int(source["horizon"]) + 1) for state in source["state"])
    specs: list[tuple[tuple[str, int], tuple[tuple[str, int], ...]]] = []; seen: set[Any] = set()
    def add(consequence: tuple[str, int], assumptions: Sequence[tuple[str, int]]) -> None:
        key = (consequence, tuple(assumptions))
        if len(specs) < 24 and key not in seen: specs.append(key); seen.add(key)
    for consequence_label, consequence_bit, assumptions in record.get("extras", ()): add((str(consequence_label), int(consequence_bit)), assumptions)
    for consequence_label in labels:
        for bit in (0, 1): add((consequence_label, bit), ())
    for consequence_label in labels:
        for assumption_label in witness:
            if assumption_label == consequence_label: continue
            for assumption_bit in (0, 1):
                for consequence_bit in (0, 1): add((consequence_label, consequence_bit), ((assumption_label, assumption_bit),))
    return specs


def _check_rule(record: Mapping[str, Any], query: ImplicationQuery, result: Mapping[str, Any], models: Sequence[Mapping[str, int]], unresolved: bool) -> tuple[dict[str, bool], bool | None, bool, list[str]]:
    failures: list[str] = []; outcome = str(result["outcome"]); certificate = result.get("certificate"); audit = {"resolution": False, "hybrid": False}
    if outcome == "holds":
        if not isinstance(certificate, Mapping): failures.append("holds-without-certificate")
        else:
            if certificate.get("resolution_proof") is not None:
                try:
                    clause_audit.audit_proof(certificate["backend_clauses"], certificate["learned_clauses"], certificate["resolution_proof"], variables=int(certificate["variables"]), status="unsat", expected_conflicts=len(certificate["resolution_proof"]["conflict_derivations"]), max_learned_clauses=256); audit["resolution"] = True
                except Exception as exc: failures.append(f"resolution-audit:{exc}")
            if certificate.get("hybrid_proof") is not None:
                try:
                    hybrid_audit.audit_proof(certificate["source_clauses"], certificate["hybrid_proof"], variables=int(certificate["variables"])); audit["hybrid"] = True
                except Exception as exc: failures.append(f"hybrid-audit:{exc}")
            if not (audit["resolution"] or audit["hybrid"]): failures.append("holds-without-audited-proof")
    witness_replay: bool | None = None
    if outcome == "refuted":
        witness = result.get("witness"); witness_replay = isinstance(witness, Mapping) and _own_holds(record["source"], witness) and all(int(witness[name]) == int(value) for name, value in query.assumptions) and _own_signal(record["source"], witness, query.consequence[0]) != int(query.consequence[1])
        if not witness_replay: failures.append("witness-independent-replay-failed")
    if outcome == "vacuous" and not _boundary_clash(record["source"], query.assumptions): failures.append("vacuous-boundary-replay-failed")
    if outcome == "unresolved" and (not unresolved or certificate is not None or result.get("witness") is not None): failures.append("unresolved-evidence-or-schedule-failed")
    cex_exists = any(all(int(model[name]) == int(value) for name, value in query.assumptions) and _own_signal(record["source"], model, query.consequence[0]) != int(query.consequence[1]) for model in models)
    agrees = not ((outcome == "holds" and cex_exists) or (outcome == "refuted" and not cex_exists))
    if not agrees: failures.append("enumeration-disagrees")
    if outcome == "refuted" and not any(all(int(model[name]) == int(value) for name, value in query.assumptions) and _own_signal(record["source"], model, query.consequence[0]) != int(query.consequence[1]) for model in models): failures.append("enumeration-found-no-counterexample")
    return audit, witness_replay, agrees, failures


def run() -> dict[str, Any]:
    started = time.perf_counter(); source_records = _build_sources(); rules: list[dict[str, Any]] = []; failures: list[str] = []; outcomes = {"holds": 0, "refuted": 0, "unresolved": 0, "vacuous": 0}; certificate_audits = 0; witness_replays = 0; disagreements = 0
    cubic_formula = canonical_cubic_formula(((1, 2, 3), (1, 2, 3), (1, 2, 3))); cubic_profile = cubic_kernel_profile(cubic_formula); cubic_connected = incidence_connected(cubic_formula)
    observations = [f"cubic-profile-rank={cubic_profile['rank']};nullity={cubic_profile['nullity']};connected={cubic_connected}", "The cubic two-neighbour rule uses one declared boundary pin plus one query pin; the candidate scan itself contains zero- and one-assumption rules.", "Each source contributes at most 24 deterministic rules."]
    for record in source_records:
        source = record["source"]; models = _enumerate(source)
        for rule_index, (consequence, assumptions) in enumerate(_make_rule_specs(record)):
            query = ImplicationQuery(source=source, consequence=consequence, assumptions=assumptions); unresolved = record["name"] == "schaefer-local-bound" and rule_index == 0; bound = UNRESOLVED_BOUND if unresolved else None; rule_started = time.perf_counter()
            try: result = imply(query, mode="local" if unresolved else "algebraic", max_transitions=bound)
            except Exception as exc: failures.append(f"{record['name']}:{query.label()}:engine:{exc}"); continue
            audit, witness_replay, agrees, local_failures = _check_rule(record, query, result, models, unresolved)
            failures.extend(f"{record['name']}:{query.label()}:{failure}" for failure in local_failures)
            outcome = str(result["outcome"])
            if outcome not in outcomes: failures.append(f"{record['name']}:{query.label()}:unknown-outcome:{outcome}"); continue
            outcomes[outcome] += 1; certificate_audits += int(audit["resolution"] or audit["hybrid"]); witness_replays += int(bool(witness_replay)); disagreements += int(not agrees)
            compiled = compile_source(source); route = "pin" if consequence[0] in witness_signals(compiled) else "clause"
            rules.append({"source": record["name"], "family": record["family"], "label": rule_label(assumptions, consequence), "route": route, "outcome": outcome, "reason": result.get("reason"), "certificate_audit": audit, "witness_replay": witness_replay, "enumeration_agrees": agrees, "seconds": time.perf_counter() - rule_started})
    if outcomes["holds"] < 10: failures.append(f"holds-count:{outcomes['holds']}<10")
    if outcomes["refuted"] < 10: failures.append(f"refuted-count:{outcomes['refuted']}<10")
    if outcomes["unresolved"] < 1: failures.append("unresolved-count<1")
    if outcomes["vacuous"] < 1: failures.append("vacuous-count<1")
    wall_clock = time.perf_counter() - started
    receipt = {"schema": SCHEMA, "python": sys.version, "platform": platform.platform(), "matrix": {"sources": len(source_records), "rules": len(rules), "bound": UNRESOLVED_BOUND}, "rules": rules, "summary": {"outcomes": outcomes, "certificate_audits": certificate_audits, "witness_replays": witness_replays, "enumeration_disagreements": disagreements, "failures": len(failures), "wall_clock_seconds": wall_clock}, "failures": failures, "observations": observations}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True); OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    slowest = sorted(rules, key=lambda row: row["seconds"], reverse=True)[:3]
    print(json.dumps({"sources": len(source_records), "rules": len(rules), "outcomes": outcomes, "wall_clock_seconds": wall_clock, "slowest": [{"source": row["source"], "label": row["label"], "seconds": row["seconds"]} for row in slowest], "failures": failures}, indent=2, sort_keys=True))
    return receipt


if __name__ == "__main__":
    result = run(); raise SystemExit(1 if result["failures"] else 0)
