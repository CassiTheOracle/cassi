"""Independent verifier for proof-carrying alias-cut results.

This module deliberately does not import the alias solver, obstruction producer,
or analysis runner.  It recognizes the promised degree-two/degree-three source
itself and checks the structural meaning of every projected cut.  The bounded
truth-table checks in this file are supplementary; structural checks are always
performed first and remain the verifier for large sources.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from verify_p_vs_np_clause_field_probe import audit_proof

RECEIPT = Path("_diag/alias_cut_analysis.json")
SCHEMA = "cassifi.alias-cut-result.v1"
ANALYSIS_SCHEMA = "cassifi.alias-cut-analysis.v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def exact_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name}: expected exact integer")
    result = int(value)
    if minimum is not None:
        require(result >= minimum, f"{name}: integer is below minimum")
    return result


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _source(formula: Any, variable_count: Any) -> dict[str, Any]:
    """Independently recognize a canonical positive exact-one source."""
    variables = exact_int(variable_count, "variable_count", minimum=1)
    require(isinstance(formula, (list, tuple)) and bool(formula), "formula must be a non-empty list")
    clauses: list[tuple[int, int, int]] = []
    for index, raw in enumerate(formula):
        require(isinstance(raw, (list, tuple)) and len(raw) == 3, f"formula clause {index}: malformed triple")
        values = [exact_int(value, f"formula clause {index} literal") for value in raw]
        require(all(1 <= value <= variables for value in values), f"formula clause {index}: variable out of range")
        require(len(set(values)) == 3, f"formula clause {index}: repeated variable")
        require(values == sorted(values), f"formula clause {index}: triple is not canonical")
        clauses.append((values[0], values[1], values[2]))
    require(clauses == sorted(clauses), "formula clauses are not in canonical order")
    incidence: list[list[int]] = [[] for _ in range(variables)]
    for clause_id, clause in enumerate(clauses):
        for variable in clause:
            incidence[variable - 1].append(clause_id)
    degrees = tuple(len(rows) for rows in incidence)
    require(all(degree in (2, 3) for degree in degrees), "every variable must occur exactly two or three times")
    cubic = tuple(variable for variable, degree in enumerate(degrees, 1) if degree == 3)
    return {
        "formula": tuple(clauses),
        "variables": variables,
        "incidence": tuple(tuple(rows) for rows in incidence),
        "degrees": degrees,
        "cubic": cubic,
    }


def _graph(source: Mapping[str, Any]) -> dict[int, set[int]]:
    graph = {clause: set() for clause in range(len(source["formula"]))}
    for variable, degree in enumerate(source["degrees"], 1):
        if degree != 2:
            continue
        left, right = source["incidence"][variable - 1]
        graph[left].add(right)
        graph[right].add(left)
    return graph


def _lit_pins(literals: Sequence[int], cubic: set[int]) -> dict[int, int]:
    pins: dict[int, int] = {}
    previous_abs = 0
    for index, raw in enumerate(literals):
        value = exact_int(raw, f"cut literal {index}")
        require(value != 0 and abs(value) in cubic, f"cut literal {index}: not an original cubic variable")
        require(abs(value) > previous_abs, "cut literals must be sorted by absolute variable")
        previous_abs = abs(value)
        pins[abs(value)] = 0 if value > 0 else 1
    return pins


def _components_after_removed(graph: Mapping[int, set[int]], removed: set[int]) -> list[set[int]]:
    unseen = set(graph) - removed
    result: list[set[int]] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        component = {start}
        stack = [start]
        while stack:
            node = stack.pop()
            for neighbor in graph[node]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    stack.append(neighbor)
        result.append(component)
    return result


def _assignment_counts(source: Mapping[str, Any], assignment: Mapping[int, int]) -> tuple[int, ...]:
    return tuple(sum(assignment.get(variable, 0) for variable in clause) for clause in source["formula"])


def _check_universal(source: Mapping[str, Any], cut: Mapping[str, Any], pins: Mapping[int, int], components: list[set[int]], barrier: set[int]) -> int | None:
    """Bounded activation/reconnection check requested by the continuation proof."""
    cubic = tuple(source["cubic"])
    if len(cubic) > 12:
        return None
    free = [variable for variable in cubic if variable not in pins]
    checked = 0
    graph = _graph(source)
    for bits in itertools.product((0, 1), repeat=len(free)):
        assignment = dict(pins)
        assignment.update(zip(free, bits))
        counts = _assignment_counts(source, assignment)
        checked += 1
        if any(count > 1 for count in counts):
            continue
        if cut["kind"] == "overfill":
            require(False, "overfill cut is not universally overfilled on its cube")
            continue
        active = {clause for clause, count in enumerate(counts) if count == 0}
        active_barrier = barrier & active
        active_graph = {
            clause: {neighbor for neighbor in graph[clause] if neighbor in active}
            for clause in active
        }
        removed_graph = _components_after_removed(active_graph, active_barrier)
        for component in components:
            require(component <= active, "certified Tutte component is not active on every cube extension")
            require(component in removed_graph, "certified Tutte component reconnects after removing active barrier")
    return checked


def verify_obstruction_cut(
    formula: Sequence[Sequence[int]],
    variable_count: int,
    cut: Any,
) -> dict[str, Any]:
    """Verify one structural overfill or Tutte obstruction cut."""
    source = _source(formula, variable_count)
    require(isinstance(cut, dict), "cut must be an object")
    require(set(cut) == {"kind", "literals", "conflict_clause", "barrier", "components", "boundary_witnesses"}, "cut fields are not exact")
    kind = cut.get("kind")
    require(kind in ("overfill", "tutte"), "cut kind is invalid")
    literals = cut.get("literals")
    require(isinstance(literals, list), "cut literals must be a list")
    require(literals == sorted(literals, key=abs), "cut literals are not sorted by absolute variable")
    pins = _lit_pins(literals, set(source["cubic"]))
    clause_count = len(source["formula"])
    conflict = cut.get("conflict_clause")
    if conflict is not None:
        exact_int(conflict, "conflict_clause", minimum=0)
        require(conflict < clause_count, "conflict_clause is out of range")
    barrier_value = cut.get("barrier")
    components_value = cut.get("components")
    witnesses_value = cut.get("boundary_witnesses")
    require(isinstance(barrier_value, list), "barrier must be a list")
    require(isinstance(components_value, list), "components must be a list")
    require(isinstance(witnesses_value, list), "boundary_witnesses must be a list")
    barrier_list = [exact_int(value, "barrier clause") for value in barrier_value]
    require(barrier_list == sorted(set(barrier_list)), "barrier must be sorted and unique")
    require(all(value < clause_count for value in barrier_list), "barrier clause is out of range")
    barrier = set(barrier_list)
    components: list[set[int]] = []
    flat: set[int] = set()
    for index, raw_component in enumerate(components_value):
        require(isinstance(raw_component, list) and bool(raw_component), f"component {index} is empty or malformed")
        values = [exact_int(value, f"component {index} clause") for value in raw_component]
        require(values == sorted(set(values)), f"component {index} must be sorted and unique")
        require(all(value < clause_count for value in values), f"component {index} clause is out of range")
        current = set(values)
        require(not current & barrier, f"component {index} intersects barrier")
        require(not current & flat, f"components {index} overlap")
        flat.update(current)
        components.append(current)
    graph = _graph(source)
    required_endpoints: set[int] = set()
    if kind == "overfill":
        require(conflict is not None, "overfill proof must name its conflict clause")
        require(not barrier_list and not components and not witnesses_value, "overfill proof has extraneous barrier/component/witness data")
        require(len(literals) == 2 and all(value < 0 for value in literals), "overfill cut must pin exactly two cubic variables to one")
        clause = set(source["formula"][conflict])
        selected = {-value for value in literals}
        require(selected <= clause, "overfill literals do not name variables in the conflict clause")
        require(len(selected) == 2, "overfill variables must be distinct")
        require(all(source["degrees"][variable - 1] == 3 for variable in selected), "overfill variables must be cubic")
    else:
        require(conflict is None, "Tutte proof cannot name a conflict clause")
        require(bool(components) and len(components) > len(barrier), "strict Tutte deficiency fails")
        require(not any(len(component) % 2 == 0 for component in components), "every certified Tutte component must be odd")
        require(
            all(
                source["degrees"][variable - 1] != 3 or pins.get(variable) == 0
                for component in components
                for clause in component
                for variable in source["formula"][clause]
            ),
            "Tutte component has an unpinned cubic incidence",
        )
        # Every component must be connected internally, and every edge leaving it
        # (except through the barrier) must terminate at a witnessed inactive clause.
        for component in components:
            unseen = set(component)
            start = min(unseen)
            unseen.remove(start)
            stack = [start]
            while stack:
                node = stack.pop()
                for neighbor in graph[node]:
                    if neighbor in unseen and neighbor in component:
                        unseen.remove(neighbor)
                        stack.append(neighbor)
            require(not unseen, "Tutte component is disconnected in the degree-two graph")
            for node in component:
                for neighbor in graph[node]:
                    if neighbor not in component and neighbor not in barrier:
                        required_endpoints.add(neighbor)
        seen_witnesses: set[tuple[int, int]] = set()
        witness_by_endpoint: dict[int, set[int]] = {}
        for index, raw in enumerate(witnesses_value):
            require(isinstance(raw, list) and len(raw) == 2, f"boundary witness {index} is malformed")
            endpoint = exact_int(raw[0], f"boundary witness {index} endpoint", minimum=0)
            variable = exact_int(raw[1], f"boundary witness {index} variable", minimum=1)
            require(endpoint < clause_count, f"boundary witness {index} endpoint is out of range")
            require(variable in set(source["cubic"]), f"boundary witness {index} variable is not cubic")
            require((endpoint, variable) not in seen_witnesses, "duplicate boundary witness")
            seen_witnesses.add((endpoint, variable))
            require(endpoint in required_endpoints, "boundary witness has no corresponding crossing endpoint")
            require(variable in source["formula"][endpoint], "boundary witness variable is not incident to endpoint clause")
            require(pins.get(variable) == 1, "boundary witness variable is not a negative cut literal")
            witness_by_endpoint.setdefault(endpoint, set()).add(variable)
        require(set(witness_by_endpoint) == required_endpoints, "not every boundary endpoint has a witness")
    enumerated = _check_universal(source, cut, pins, components, barrier)
    return {
        "kind": kind,
        "variable_count": source["variables"],
        "clause_count": clause_count,
        "cubic_variables": list(source["cubic"]),
        "pinned_zero": sorted(variable for variable, value in pins.items() if value == 0),
        "pinned_one": sorted(variable for variable, value in pins.items() if value == 1),
        "components": [sorted(component) for component in components],
        "barrier": barrier_list,
        "odd_components": sum(len(component) % 2 for component in components),
        "deficiency": len(components) - len(barrier),
        "boundary_endpoints": sorted(required_endpoints) if kind == "tutte" else [],
        "universal_extensions_checked": enumerated,
    }


def _cnf_clause(value: Any, variables: int, name: str) -> list[int]:
    require(isinstance(value, list), f"{name}: clause must be a list")
    result = [exact_int(literal, f"{name} literal") for literal in value]
    require(all(literal != 0 and abs(literal) <= variables for literal in result), f"{name}: literal out of range")
    require(len(result) == len(set(result)), f"{name}: duplicate literal")
    require(not any(-literal in result for literal in result), f"{name}: tautological clause")
    return result


def _satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(sum(assignment[abs(literal) - 1] if literal > 0 else 1 - assignment[abs(literal) - 1] for literal in clause) > 0 for clause in formula)


def _exact_one(source: Mapping[str, Any], assignment: Sequence[int]) -> bool:
    return all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in source["formula"])


def _digest(value: Any, name: str) -> None:
    require(isinstance(value, str) and len(value) == 64, f"{name}: digest is malformed")
    try:
        int(value, 16)
    except ValueError as exc:
        raise AssertionError(f"{name}: digest is not hexadecimal") from exc


def verify_result(result: Any) -> dict[str, Any]:
    """Verify one complete alias-cut result, including backend UNSAT proof."""
    require(isinstance(result, dict), "result must be an object")
    expected_fields = {
        "schema", "status", "reason", "formula", "variable_count", "cubic_variables",
        "assignment", "cuts", "alias_clauses", "alias_assignment", "proof", "work",
        "profile", "state_sha256", "alias_learned_clauses", "alias_backend_work",
    }
    require(set(result) == expected_fields, "result fields are not exact")
    require(result.get("schema") == SCHEMA, "result schema mismatch")
    status = result.get("status")
    require(status in ("sat", "unsat", "exhausted"), "result status invalid")
    source = _source(result.get("formula"), result.get("variable_count"))
    expected_formula = [list(clause) for clause in source["formula"]]
    require(isinstance(result.get("reason"), str), "result reason must be a string")
    require(result["formula"] == expected_formula, "result formula is not canonical")
    require(result.get("cubic_variables") == list(source["cubic"]), "cubic variable recognition mismatch")
    assignment = result.get("assignment")
    if assignment is not None:
        require(isinstance(assignment, list) and len(assignment) == source["variables"], "source assignment shape mismatch")
        require(all(exact_int(value, "source assignment value") in (0, 1) for value in assignment), "source assignment is not binary")
    require((status == "sat") == (assignment is not None), "only SAT may carry a source assignment")
    if status == "sat":
        require(_exact_one(source, assignment), "source SAT assignment violates exact-one clauses")
    cuts = result.get("cuts")
    require(isinstance(cuts, list), "cuts must be a list")
    checked_cuts = [verify_obstruction_cut(source["formula"], source["variables"], cut) for cut in cuts]
    k = len(source["cubic"])
    mapping = {variable: index + 1 for index, variable in enumerate(source["cubic"])}
    expected_alias_clauses: list[list[int]] = []
    for cut in cuts:
        expected_alias_clauses.append([int(literal // abs(literal) * mapping[abs(literal)]) for literal in cut["literals"]])
    require(result.get("alias_clauses") == expected_alias_clauses, "alias CNF does not exactly renumber cut literals")
    backend_variables = max(1, k)
    for index, clause in enumerate(result["alias_clauses"]):
        _cnf_clause(clause, backend_variables, f"alias clause {index}")
    alias_assignment = result.get("alias_assignment")
    if status == "sat":
        require(isinstance(alias_assignment, list) and len(alias_assignment) == backend_variables, "SAT alias assignment shape mismatch")
        require(all(exact_int(value, "alias assignment value") in (0, 1) for value in alias_assignment), "alias assignment is not binary")
        expected_alias = [assignment[variable - 1] for variable in source["cubic"]] or [0]
        require(alias_assignment == expected_alias, "alias assignment disagrees with source assignment")
        require(all(_satisfies(result["alias_clauses"], alias_assignment) for _ in [0]), "SAT assignment violates an alias cut")
    else:
        require(alias_assignment is None, "non-SAT result carries an alias assignment")
    learned = result.get("alias_learned_clauses")
    require(isinstance(learned, list), "alias_learned_clauses must be a list")
    for index, clause in enumerate(learned):
        _cnf_clause(clause, backend_variables, f"learned alias clause {index}")
    work = result.get("work")
    require(isinstance(work, dict), "work must be an object")
    for key, value in work.items():
        if key.endswith("runs") or key.endswith("scans") or key.endswith("contractions") or key.endswith("bound"):
            exact_int(value, f"work.{key}", minimum=0)
    backend_work = result.get("alias_backend_work")
    require(isinstance(backend_work, dict), "alias_backend_work must be an object")
    for key, value in backend_work.items():
        if key in {"conflicts", "decisions", "propagations", "learned_clauses", "proof_resolutions", "proof_literal_scans"}:
            exact_int(value, f"alias_backend_work.{key}", minimum=0)
    profile = result.get("profile")
    require(isinstance(profile, dict), "profile must be an object")
    max_learned = exact_int(profile.get("max_learned_clauses"), "profile.max_learned_clauses", minimum=0)
    _digest(result.get("state_sha256"), "state_sha256")
    proof = result.get("proof")
    if status == "unsat":
        require(isinstance(proof, dict), "UNSAT result is missing its proof")
        expected_conflicts = exact_int(backend_work.get("conflicts"), "alias_backend_work.conflicts", minimum=0)
        audit_proof(
            result["alias_clauses"],
            learned,
            proof,
            variables=backend_variables,
            status="unsat",
            expected_conflicts=expected_conflicts,
            max_learned_clauses=max_learned,
        )
    else:
        require(proof is None, "SAT/exhausted result carries an UNSAT proof")
    return {
        "status": status,
        "variables": source["variables"],
        "clauses": len(source["formula"]),
        "cubic_variables": k,
        "cuts": len(cuts),
        "checked_cuts": checked_cuts,
        "universal_extensions_checked": sum(int(row["universal_extensions_checked"] or 0) for row in checked_cuts),
        "proof_checked": status == "unsat",
    }


def _models(source: Mapping[str, Any]) -> list[list[int]]:
    return [list(bits) for bits in itertools.product((0, 1), repeat=source["variables"]) if _exact_one(source, bits)]


def _refusal_controls(formula: Sequence[Sequence[int]], cuts: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts = {"changed_sign": 0, "missing_boundary_witness": 0, "component_corruption": 0, "barrier_corruption": 0}

    def refuse(mutated: dict[str, Any], key: str) -> None:
        try:
            verify_obstruction_cut(formula, max(max(clause) for clause in formula), mutated)
        except (AssertionError, ValueError):
            counts[key] += 1
        else:
            raise AssertionError(f"tamper control {key} was accepted")

    for original in cuts:
        cut: dict[str, Any] = copy.deepcopy(dict(original))
        if cut["literals"]:
            cut["literals"][0] = -cut["literals"][0]
            refuse(cut, "changed_sign")
            break
    for original in cuts:
        if original["kind"] == "tutte" and original["boundary_witnesses"]:
            cut = copy.deepcopy(dict(original))
            endpoint = cut["boundary_witnesses"][0][0]
            cut["boundary_witnesses"] = [witness for witness in cut["boundary_witnesses"] if witness[0] != endpoint]
            refuse(cut, "missing_boundary_witness")
            break
    for original in cuts:
        if original["kind"] == "tutte" and original["components"]:
            cut = copy.deepcopy(dict(original))
            component = cut["components"][0]
            component.append(component[-1])
            refuse(cut, "component_corruption")
            break
    for original in cuts:
        if original["kind"] == "tutte":
            cut = copy.deepcopy(dict(original))
            if cut["barrier"]:
                cut["barrier"].append(cut["barrier"][0])
            else:
                cut["barrier"].append(cut["components"][0][0])
            refuse(cut, "barrier_corruption")
            break
    return counts


def verify(path: Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(receipt, dict) and receipt.get("schema") == ANALYSIS_SCHEMA, "analysis receipt schema mismatch")
    cases = receipt.get("cases")
    require(isinstance(cases, list) and bool(cases), "analysis receipt cases missing")
    audited: list[dict[str, Any]] = []
    refusal = {"changed_sign": 0, "missing_boundary_witness": 0, "component_corruption": 0, "barrier_corruption": 0}
    enumeration_cases = 0
    enumerated_models = 0
    for index, case in enumerate(cases):
        require(isinstance(case, dict), f"case {index} is malformed")
        require(isinstance(case.get("descriptor"), dict), f"case {index} descriptor is invalid")
        require(isinstance(case.get("name"), str) and bool(case["name"]), f"case {index} name is invalid")
        require(case.get("kind") in ("sat", "unsat", "exhausted"), f"case {index} kind is invalid")
        require(isinstance(case.get("restart_verified"), bool), f"case {index} restart_verified is invalid")
        require(case.get("baseline") is None or isinstance(case.get("baseline"), dict), f"case {index} baseline is invalid")
        result = case.get("result")
        report = verify_result(result)
        require(report["status"] == case["kind"], f"case {index} kind/result mismatch")
        for key, value in _refusal_controls(result["formula"], result["cuts"]).items():
            refusal[key] += value
        source = _source(result["formula"], result["variable_count"])
        if source["variables"] <= 16:
            enumeration_cases += 1
            models = _models(source)
            enumerated_models += len(models)
            if result["status"] == "sat":
                require(result["assignment"] in models, f"case {index}: SAT assignment disagrees with exhaustive enumeration")
            elif result["status"] == "unsat":
                require(not models, f"case {index}: UNSAT certificate disagrees with exhaustive enumeration")
            for model in models:
                alias_model = [model[variable - 1] for variable in source["cubic"]] or [0]
                for clause in result["alias_clauses"]:
                    require(_satisfies([clause], alias_model), f"case {index}: cut is not entailed by source models")
        audited.append({"name": case["name"], **{key: value for key, value in report.items() if key != "checked_cuts"}})
    require(all(value > 0 for value in refusal.values()), "receipt lacks valid certificates for every tamper refusal control")
    summary = {
        "cases_checked": len(audited),
        "cuts_checked": sum(row["cuts"] for row in audited),
        "enumeration_cases": enumeration_cases,
        "enumerated_models": enumerated_models,
        "refusal_controls_attempted": sum(refusal.values()),
        "refusal_controls_refused": sum(refusal.values()),
        "refusal_controls": refusal,
    }
    output = {"checked_cases": audited, "summary": summary}
    print(json.dumps(output, sort_keys=True))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=RECEIPT)
    args = parser.parse_args()
    verify(args.path)
