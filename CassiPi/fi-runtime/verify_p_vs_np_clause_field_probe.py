#!/usr/bin/env python
"""Independently verify the frozen CassiFI clause-field experiment receipt.

This verifier intentionally imports neither the clause field nor probe runner.
It checks serialized CNFs, truth tables, SAT assignments, every conflict
resolution/weakening derivation, complete UNSAT branch-closure refutations,
resource identities, storage, representation controls, and scaling aggregates
using only the Python standard library.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import statistics
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

SCHEMA = "cassifi.p-vs-np-clause-field-probe.v2"
DEFAULT_RECEIPT = Path("_diag/p_vs_np_clause_field_probe.json")
ACTIONS = ("decide", "propagate", "conflict-backtrack", "sat", "unsat", "exhaust")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def formula_from(row: Mapping[str, Any]) -> tuple[tuple[int, ...], ...]:
    variables_value = row.get("variables")
    raw_value = row.get("formula")
    require(
        isinstance(variables_value, int)
        and not isinstance(variables_value, bool)
        and variables_value >= 1,
        "invalid variable count",
    )
    require(isinstance(raw_value, list), f"{row.get('name')}: formula must be a list")
    variables = cast(int, variables_value)
    raw = cast(list[Any], raw_value)
    formula: list[tuple[int, ...]] = []
    for clause_value in raw:
        require(isinstance(clause_value, list), f"{row.get('name')}: clause must be a list")
        clause = cast(list[Any], clause_value)
        require(isinstance(clause, list), f"{row.get('name')}: clause must be a list")
        parsed: list[int] = []
        for literal_value in clause:
            require(
                isinstance(literal_value, int)
                and not isinstance(literal_value, bool)
                and literal_value != 0
                and abs(literal_value) <= variables,
                f"{row.get('name')}: invalid literal",
            )
            parsed.append(cast(int, literal_value))
        require(len(parsed) == len(set(parsed)), f"{row.get('name')}: duplicate literal")
        require(not any(-literal in parsed for literal in parsed), f"{row.get('name')}: tautological clause")
        formula.append(tuple(parsed))
    require(len(formula) == row.get("clauses"), f"{row.get('name')}: clause count mismatch")
    require(
        max((len(clause) for clause in formula), default=0) == row.get("max_clause_width"),
        f"{row.get('name')}: maximum clause width mismatch",
    )
    return tuple(formula)


def satisfies(
    formula: Sequence[Sequence[int]], assignment: Sequence[int]
) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (1 if literal > 0 else -1) for literal in clause)
        for clause in formula
    )


def truth_table_audit(
    formula: tuple[tuple[int, ...], ...],
    learned: tuple[tuple[int, ...], ...],
    variables: int,
) -> tuple[bool, bool, int]:
    has_model = False
    learned_sound = True
    models = 0
    for assignment in itertools.product((-1, 1), repeat=variables):
        if satisfies(formula, assignment):
            has_model = True
            models += 1
            if not satisfies(learned, assignment):
                learned_sound = False
    return has_model, learned_sound, models


def pigeonhole(holes: int) -> tuple[tuple[int, ...], ...]:
    pigeons = holes + 1

    def variable(pigeon: int, hole: int) -> int:
        return pigeon * holes + hole + 1

    clauses: list[tuple[int, ...]] = []
    for pigeon in range(pigeons):
        clauses.append(tuple(variable(pigeon, hole) for hole in range(holes)))
    for hole in range(holes):
        for first in range(pigeons):
            for second in range(first + 1, pigeons):
                clauses.append((-variable(first, hole), -variable(second, hole)))
    return tuple(clauses)


def digest_text(value: Any, name: str) -> str:
    require(isinstance(value, str) and len(value) == 64, f"{name}: invalid digest length")
    require(all(character in "0123456789abcdef" for character in value), f"{name}: invalid digest")
    return value


def expected_field_bytes(variables: int, clauses: int) -> int:
    total_capacity = max(1, clauses) + max(16, 8 * variables)
    mode_count = max(21, variables, total_capacity, total_capacity * variables)
    return 72 * mode_count
def resolve_clause(
    left: Sequence[int],
    right: Sequence[int],
    pivot: int,
) -> tuple[int, ...]:
    left_polarity = 1 if pivot in left else -1 if -pivot in left else 0
    right_polarity = 1 if pivot in right else -1 if -pivot in right else 0
    require(
        left_polarity != 0 and right_polarity == -left_polarity,
        "resolution premises lack a complementary pivot",
    )
    result: set[int] = set()
    for literal in (*left, *right):
        if abs(literal) == pivot:
            continue
        require(-literal not in result, "resolution produced a tautology")
        result.add(int(literal))
    return tuple(sorted(result, key=lambda literal: (abs(literal), literal < 0)))


def clause_value(value: Any, variables: int, name: str) -> tuple[int, ...]:
    require(isinstance(value, list), f"{name}: clause is not a list")
    clause = tuple(cast(list[int], value))
    require(
        all(
            isinstance(literal, int)
            and not isinstance(literal, bool)
            and 0 < abs(literal) <= variables
            for literal in clause
        ),
        f"{name}: invalid literal",
    )
    require(
        len(clause) == len(set(clause))
        and not any(-literal in clause for literal in clause),
        f"{name}: duplicate or tautological clause",
    )
    return clause


def audit_proof(
    formula: Sequence[Sequence[int]],
    learned: Sequence[Sequence[int]],
    value: Any,
    *,
    variables: int,
    status: str,
    expected_conflicts: int,
    max_learned_clauses: int,
) -> dict[str, int]:
    require(isinstance(value, dict), "missing proof certificate")
    proof = cast(dict[str, Any], value)
    require(
        proof.get("schema") == "cassifi.dpll-wresolution-proof.v1",
        "proof certificate schema mismatch",
    )
    expected_system = (
        "chronological DPLL resolution DAG with linear conflict derivations, "
        "weakening to decision nogoods, lemma reuse, and a depth-first "
        "branch-closure tree"
    )
    require(proof.get("proof_system") == expected_system, "proof-system label mismatch")
    conflicts_value = proof.get("conflict_derivations")
    closures_value = proof.get("closure_steps")
    require(
        isinstance(conflicts_value, list)
        and all(isinstance(row, dict) for row in conflicts_value),
        "conflict derivations are invalid",
    )
    require(
        isinstance(closures_value, list)
        and all(isinstance(row, dict) for row in closures_value),
        "closure derivations are invalid",
    )
    conflicts = cast(list[dict[str, Any]], conflicts_value)
    closures = cast(list[dict[str, Any]], closures_value)
    require(len(conflicts) == expected_conflicts, "proof/conflict count mismatch")

    database = [tuple(clause) for clause in formula]
    original_count = len(database)
    proof_lines: dict[int, tuple[int, ...]] = {}
    dependencies: dict[int, frozenset[int]] = {}
    leaf_resolution_steps = 0
    leaf_weakenings = 0
    proof_literal_scans = 0
    max_core_width = 0
    max_nogood_width = 0
    for leaf_line, row in enumerate(conflicts, 1):
        require(
            row.get("schema") == "cassifi.clause-field-conflict-proof.v1",
            f"proof leaf {leaf_line}: schema mismatch",
        )
        decisions_value = row.get("decision_literals")
        require(isinstance(decisions_value, list), f"proof leaf {leaf_line}: invalid decisions")
        decisions = tuple(cast(list[int], decisions_value))
        require(
            all(
                isinstance(literal, int)
                and not isinstance(literal, bool)
                and 0 < abs(literal) <= variables
                for literal in decisions
            )
            and len({abs(literal) for literal in decisions}) == len(decisions),
            f"proof leaf {leaf_line}: invalid decision path",
        )
        nogood = clause_value(row.get("nogood_clause"), variables, f"proof leaf {leaf_line}")
        require(
            nogood == tuple(-literal for literal in decisions),
            f"proof leaf {leaf_line}: decision nogood mismatch",
        )
        conflict_clause_id = row.get("conflict_clause_id")
        require(
            isinstance(conflict_clause_id, int)
            and not isinstance(conflict_clause_id, bool)
            and 1 <= conflict_clause_id <= len(database),
            f"proof leaf {leaf_line}: conflict clause reference is invalid",
        )
        conflict_clause_id = cast(int, conflict_clause_id)
        current = database[conflict_clause_id - 1]
        steps_value = row.get("resolution_steps")
        require(isinstance(steps_value, list), f"proof leaf {leaf_line}: invalid resolution steps")
        for step_index, step_value in enumerate(cast(list[Any], steps_value), 1):
            require(isinstance(step_value, dict), f"proof leaf {leaf_line}: invalid resolution step")
            step = cast(dict[str, Any], step_value)
            pivot = step.get("pivot")
            reason_clause_id = step.get("reason_clause_id")
            require(
                isinstance(pivot, int)
                and not isinstance(pivot, bool)
                and 1 <= pivot <= variables,
                f"proof leaf {leaf_line}: invalid pivot",
            )
            require(
                isinstance(reason_clause_id, int)
                and not isinstance(reason_clause_id, bool)
                and 1 <= reason_clause_id <= len(database),
                f"proof leaf {leaf_line}: invalid reason reference",
            )
            pivot = cast(int, pivot)
            reason_clause_id = cast(int, reason_clause_id)
            reason = database[reason_clause_id - 1]
            expected_resolvent = resolve_clause(current, reason, pivot)
            resolvent = clause_value(
                step.get("resolvent"),
                variables,
                f"proof leaf {leaf_line} resolution {step_index}",
            )
            require(
                resolvent == expected_resolvent,
                f"proof leaf {leaf_line}: false resolution inference",
            )
            proof_literal_scans += len(current) + len(reason)
            leaf_resolution_steps += 1
            current = resolvent
        core = clause_value(row.get("core_clause"), variables, f"proof leaf {leaf_line} core")
        require(core == current, f"proof leaf {leaf_line}: conflict core mismatch")
        require(
            set(core).issubset(set(nogood)),
            f"proof leaf {leaf_line}: invalid weakening",
        )
        proof_literal_scans += len(core) + len(nogood)
        leaf_weakenings += set(core) != set(nogood)
        max_core_width = max(max_core_width, len(core))
        max_nogood_width = max(max_nogood_width, len(nogood))

        stored_new = row.get("stored_new")
        stored_clause_id = row.get("stored_clause_id")
        learning_status = row.get("learning_status")
        require(isinstance(stored_new, bool), f"proof leaf {leaf_line}: invalid storage flag")
        if learning_status == "added":
            require(stored_new is True, f"proof leaf {leaf_line}: added clause flag mismatch")
            require(stored_clause_id == len(database) + 1, f"proof leaf {leaf_line}: added clause id mismatch")
            database.append(nogood)
        elif learning_status == "duplicate":
            require(stored_new is False, f"proof leaf {leaf_line}: duplicate flag mismatch")
            require(
                isinstance(stored_clause_id, int)
                and 1 <= stored_clause_id <= len(database)
                and database[stored_clause_id - 1] == nogood,
                f"proof leaf {leaf_line}: duplicate clause reference mismatch",
            )
        elif learning_status == "root":
            require(
                not nogood and stored_new is False and stored_clause_id is None,
                f"proof leaf {leaf_line}: invalid root conflict",
            )
        elif learning_status == "capacity":
            require(
                bool(nogood)
                and stored_new is False
                and stored_clause_id is None
                and len(database) - original_count >= max_learned_clauses,
                f"proof leaf {leaf_line}: false capacity claim",
            )
        else:
            raise AssertionError(f"proof leaf {leaf_line}: invalid learning status")
        proof_lines[leaf_line] = nogood
        dependencies[leaf_line] = frozenset((leaf_line,))

    require(
        tuple(database[original_count:]) == tuple(tuple(clause) for clause in learned),
        "proof-derived lemma database mismatch",
    )
    closure_literal_scans = 0
    for closure_index, row in enumerate(closures, 1):
        line_id = len(conflicts) + closure_index
        require(row.get("line_id") == line_id, f"closure line {line_id}: id mismatch")
        left_line = row.get("left_line")
        right_line = row.get("right_line")
        pivot = row.get("pivot")
        require(
            isinstance(left_line, int)
            and isinstance(right_line, int)
            and left_line in proof_lines
            and right_line in proof_lines,
            f"closure line {line_id}: invalid premise",
        )
        require(
            isinstance(pivot, int)
            and not isinstance(pivot, bool)
            and 1 <= pivot <= variables,
            f"closure line {line_id}: invalid pivot",
        )
        left_line = cast(int, left_line)
        right_line = cast(int, right_line)
        pivot = cast(int, pivot)
        left = proof_lines[left_line]
        right = proof_lines[right_line]
        expected_resolvent = resolve_clause(left, right, pivot)
        resolvent = clause_value(
            row.get("resolvent"),
            variables,
            f"closure line {line_id}",
        )
        require(resolvent == expected_resolvent, f"closure line {line_id}: false inference")
        require(
            dependencies[left_line].isdisjoint(dependencies[right_line]),
            f"closure line {line_id}: reused conflict leaf",
        )
        proof_lines[line_id] = resolvent
        dependencies[line_id] = dependencies[left_line] | dependencies[right_line]
        closure_literal_scans += len(left) + len(right)

    root_line = proof.get("root_line")
    if status == "unsat":
        require(
            isinstance(root_line, int)
            and root_line in proof_lines
            and proof_lines[root_line] == (),
            "UNSAT proof does not derive the empty clause",
        )
        root_line = cast(int, root_line)
        require(
            dependencies[root_line] == frozenset(range(1, len(conflicts) + 1)),
            "UNSAT proof does not close every conflict leaf",
        )
    else:
        require(root_line is None and not closures, "SAT row carries a refutation")

    payload = {
        "schema": proof["schema"],
        "proof_system": proof["proof_system"],
        "conflict_derivations": conflicts,
        "closure_steps": closures,
        "root_line": root_line,
    }
    expected_stats = {
        "conflict_derivations": len(conflicts),
        "leaf_resolution_steps": leaf_resolution_steps,
        "leaf_weakenings": leaf_weakenings,
        "closure_resolution_steps": len(closures),
        "inference_steps": leaf_resolution_steps + leaf_weakenings + len(closures),
        "closure_literal_scans": closure_literal_scans,
        "max_core_width": max_core_width,
        "max_nogood_width": max_nogood_width,
        "payload_json_bytes": len(canonical(payload)),
    }
    require(proof.get("stats") == expected_stats, "proof statistics mismatch")
    return {**expected_stats, "proof_literal_scans": proof_literal_scans}




def audit_row(row: Mapping[str, Any], *, permit_structural_oracle: bool) -> dict[str, Any]:
    name_value = row.get("name")
    require(isinstance(name_value, str) and bool(name_value), "case name is invalid")
    name = cast(str, name_value)
    formula = formula_from(row)
    variables = int(row["variables"])
    require(
        row.get("problem_sha256") == hashlib.sha256(canonical(formula)).hexdigest(),
        f"{name}: problem digest mismatch",
    )
    digest_text(row.get("initial_state_sha256"), f"{name} initial state")
    digest_text(row.get("state_sha256"), f"{name} final state")
    digest_text(row.get("trace_sha256"), f"{name} trace")
    proof_value = row.get("proof")
    require(
        row.get("proof_sha256") == hashlib.sha256(canonical(proof_value)).hexdigest(),
        f"{name}: proof digest mismatch",
    )

    learned_value = row.get("learned_clauses")
    require(isinstance(learned_value, list), f"{name}: missing learned clauses")
    learned_raw = cast(list[Any], learned_value)
    require(all(isinstance(clause, list) for clause in learned_raw), f"{name}: learned clause encoding invalid")
    learned = tuple(tuple(int(literal) for literal in cast(list[Any], clause)) for clause in learned_raw)
    for clause in learned:
        require(bool(clause) and len(clause) <= variables, f"{name}: learned clause width invalid")
        require(
            len(clause) == len(set(clause))
            and not any(-literal in clause for literal in clause)
            and all(0 < abs(literal) <= variables for literal in clause),
            f"{name}: learned clause invalid",
        )

    exact = row.get("exact_truth_table_oracle") is True
    has_model: bool
    learned_sound: bool | None
    models: int | None
    if exact:
        has_model, learned_sound, models = truth_table_audit(formula, learned, variables)
        require(row.get("learned_clause_sound") is learned_sound, f"{name}: learned soundness mismatch")
        require(learned_sound is True, f"{name}: learned clause removes an original model")
    else:
        require(permit_structural_oracle, f"{name}: structural oracle is not allowed here")
        require(name == "pigeonhole_5_into_4", f"{name}: unknown non-enumerated case")
        require(variables == 20 and formula == pigeonhole(4), f"{name}: pigeonhole construction mismatch")
        # Four holes cannot receive five pigeons injectively. The formula above
        # independently checks every at-least-one and pairwise exclusion clause.
        has_model = False
        learned_sound = None
        models = None
        require(row.get("learned_clause_sound") is None, f"{name}: unexpected learned oracle claim")

    expected_sat = row.get("expected_sat")
    require(isinstance(expected_sat, bool), f"{name}: expected label must be Boolean")
    require(has_model is expected_sat, f"{name}: expected label disagrees with independent oracle")
    status = row.get("status")
    require(status == ("sat" if has_model else "unsat"), f"{name}: field decision mismatch")

    assignment_value = row.get("assignment")
    if status == "sat":
        require(
            isinstance(assignment_value, list)
            and len(assignment_value) == variables
            and all(value in (-1, 1) and not isinstance(value, bool) for value in assignment_value),
            f"{name}: SAT assignment encoding invalid",
        )
        assignment = cast(list[int], assignment_value)
        require(satisfies(formula, assignment), f"{name}: SAT certificate is false")
        require(row.get("certificate_verified") is True, f"{name}: certificate flag mismatch")
    else:
        require(assignment_value is None, f"{name}: UNSAT row must not carry an assignment")
        require(row.get("certificate_verified") is False, f"{name}: UNSAT certificate flag mismatch")
    profile_value = row.get("profile")
    require(isinstance(profile_value, dict), f"{name}: missing field profile")
    profile = cast(dict[str, int], profile_value)
    expected_profile = {
        "max_variables": variables,
        "max_original_clauses": max(1, len(formula)),
        "max_clause_width": variables,
        "max_learned_clauses": max(16, 8 * variables),
        "max_transitions": 1_000_000,
    }
    require(profile == expected_profile, f"{name}: field profile mismatch")

    field_bytes_value = row.get("field_bytes")
    require(isinstance(field_bytes_value, int) and not isinstance(field_bytes_value, bool), f"{name}: field byte count invalid")
    field_bytes = cast(int, field_bytes_value)
    require(field_bytes == expected_field_bytes(variables, len(formula)), f"{name}: field byte count mismatch")
    require(
        field_bytes <= max(72 * 21, 72 * (len(formula) + 8 * variables) * variables),
        f"{name}: polynomial storage bound exceeded",
    )

    actions_value = row.get("action_counts")
    require(isinstance(actions_value, dict) and set(actions_value) == set(ACTIONS), f"{name}: action vocabulary mismatch")
    actions = cast(dict[str, int], actions_value)
    require(all(isinstance(value, int) and value >= 0 for value in actions.values()), f"{name}: invalid action count")
    ledger_value = row.get("resource_ledger")
    require(isinstance(ledger_value, dict), f"{name}: missing resource ledger")
    ledger = cast(dict[str, int], ledger_value)
    required_ledger = {
        "transitions",
        "decisions",
        "propagations",
        "conflicts",
        "backtracks",
        "learned_clauses",
        "clause_scans",
        "literal_scans",
        "assignment_writes",
        "clause_writes",
        "peak_trail",
        "peak_decision_depth",
        "proof_resolutions",
        "proof_literal_scans",
    }
    require(set(ledger) == required_ledger, f"{name}: resource ledger keys mismatch")
    require(all(isinstance(value, int) and value >= 0 for value in ledger.values()), f"{name}: invalid resource count")
    require(sum(actions.values()) == ledger["transitions"], f"{name}: action/transition mismatch")
    require(actions["decide"] == ledger["decisions"], f"{name}: decision count mismatch")
    require(actions["propagate"] == ledger["propagations"], f"{name}: propagation count mismatch")
    require(actions["conflict-backtrack"] == ledger["backtracks"], f"{name}: backtrack count mismatch")
    require(
        actions["conflict-backtrack"] + actions["unsat"] == ledger["conflicts"],
        f"{name}: conflict count mismatch",
    )
    require(len(learned) == ledger["learned_clauses"] <= ledger["conflicts"], f"{name}: learned count mismatch")
    require(ledger["peak_trail"] <= variables and ledger["peak_decision_depth"] <= variables, f"{name}: peak state bound exceeded")
    proof_audit = audit_proof(
        formula,
        learned,
        proof_value,
        variables=variables,
        status=cast(str, status),
        expected_conflicts=ledger["conflicts"],
        max_learned_clauses=profile["max_learned_clauses"],
    )
    require(
        ledger["proof_resolutions"] == proof_audit["leaf_resolution_steps"],
        f"{name}: proof resolution ledger mismatch",
    )
    require(
        ledger["proof_literal_scans"] == proof_audit["proof_literal_scans"],
        f"{name}: proof literal-scan ledger mismatch",
    )
    require(
        row.get("unsat_certificate_verified") is (status == "unsat"),
        f"{name}: UNSAT certificate flag mismatch",
    )
    require(actions["sat"] + actions["unsat"] == 1, f"{name}: missing unique terminal action")
    require(actions["exhaust"] == 0, f"{name}: completed row contains exhaustion")
    first_actions = row.get("first_actions")
    last_actions = row.get("last_actions")
    require(
        isinstance(first_actions, list)
        and isinstance(last_actions, list)
        and 1 <= len(first_actions) <= 8
        and 1 <= len(last_actions) <= 8,
        f"{name}: trace preview invalid",
    )
    return {
        "name": name,
        "family": row.get("family"),
        "proof_stats": {
            key: value
            for key, value in proof_audit.items()
            if key != "proof_literal_scans"
        },
        "variables": variables,
        "transitions": ledger["transitions"],
        "status": status,
        "models": models,
        "learned_sound": learned_sound,
        "proof_inferences": proof_audit["inference_steps"],
        "unsat_proof_verified": status == "unsat",
    }


def linear_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    denominator = sum((value - x_mean) ** 2 for value in xs)
    require(denominator > 0, "scaling regression has duplicate sizes")
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator


def audit_scaling(receipt: Mapping[str, Any], audited: Sequence[Mapping[str, Any]]) -> None:
    scaling_value = receipt.get("scaling")
    require(isinstance(scaling_value, dict), "missing scaling summary")
    scaling = cast(dict[str, Any], scaling_value)
    families = sorted({str(row["family"]) for row in audited})
    require(sorted(scaling) == families, "scaling family set mismatch")
    for family in families:
        family_rows = [row for row in audited if row["family"] == family]
        sizes = sorted({int(row["variables"]) for row in family_rows})
        expected_points = []
        for variables in sizes:
            selected = [
                row for row in family_rows if int(row["variables"]) == variables
            ]
            transitions = [int(row["transitions"]) for row in selected]
            proof_inferences = [
                int(cast(Mapping[str, Any], row["proof_stats"])["inference_steps"])
                for row in selected
            ]
            expected_points.append(
                {
                    "variables": variables,
                    "runs": len(selected),
                    "min_transitions": min(transitions),
                    "median_transitions": float(statistics.median(transitions)),
                    "max_transitions": max(transitions),
                    "min_proof_inferences": min(proof_inferences),
                    "median_proof_inferences": float(statistics.median(proof_inferences)),
                    "max_proof_inferences": max(proof_inferences),
                }
            )
        actual_value = scaling[family]
        require(isinstance(actual_value, dict), f"{family}: scaling summary must be an object")
        actual = cast(dict[str, Any], actual_value)
        require(actual.get("points") == expected_points, f"{family}: scaling points mismatch")
        if len(expected_points) >= 3:
            xs = [float(point["variables"]) for point in expected_points]
            transition_medians = [
                float(point["median_transitions"]) for point in expected_points
            ]
            if all(value > 0 for value in transition_medians):
                expected_loglog = linear_slope(
                    [math.log(value) for value in xs],
                    [math.log(value) for value in transition_medians],
                )
                expected_exponential = linear_slope(
                    xs,
                    [math.log2(value) for value in transition_medians],
                )
                require(
                    math.isclose(float(actual["descriptive_loglog_slope"]), expected_loglog, rel_tol=1e-12, abs_tol=1e-12),
                    f"{family}: log-log slope mismatch",
                )
                require(
                    math.isclose(float(actual["descriptive_log2_slope_per_variable"]), expected_exponential, rel_tol=1e-12, abs_tol=1e-12),
                    f"{family}: exponential slope mismatch",
                )
            proof_medians = [
                float(point["median_proof_inferences"]) for point in expected_points
            ]
            if all(value > 0 for value in proof_medians):
                expected_proof_loglog = linear_slope(
                    [math.log(value) for value in xs],
                    [math.log(value) for value in proof_medians],
                )
                expected_proof_exponential = linear_slope(
                    xs,
                    [math.log2(value) for value in proof_medians],
                )
                require(
                    math.isclose(float(actual["descriptive_proof_loglog_slope"]), expected_proof_loglog, rel_tol=1e-12, abs_tol=1e-12),
                    f"{family}: proof log-log slope mismatch",
                )
                require(
                    math.isclose(float(actual["descriptive_proof_log2_slope_per_variable"]), expected_proof_exponential, rel_tol=1e-12, abs_tol=1e-12),
                    f"{family}: proof exponential slope mismatch",
                )


def audit_representation(value: Mapping[str, Any]) -> int:
    variants_value = value.get("variants")
    padded_value = value.get("irrelevant_variable_variant")
    require(
        isinstance(variants_value, list)
        and len(variants_value) == 13
        and all(isinstance(row, dict) for row in variants_value),
        "representation variant count mismatch",
    )
    require(isinstance(padded_value, dict), "missing irrelevant-variable control")
    variants = cast(list[Mapping[str, Any]], variants_value)
    padded = cast(Mapping[str, Any], padded_value)
    audited = [audit_row(row, permit_structural_oracle=False) for row in variants]
    padded_audit = audit_row(padded, permit_structural_oracle=False)
    require(value.get("all_statuses_identical") is (len({row["status"] for row in audited}) == 1), "representation status aggregate mismatch")
    require(value.get("all_certificates_verified") is True, "representation certificate aggregate mismatch")
    transitions = [int(row["transitions"]) for row in audited]
    require(value.get("transition_range") == [min(transitions), max(transitions)], "representation transition range mismatch")
    require(math.isclose(float(value["transition_ratio"]), max(transitions) / min(transitions), rel_tol=1e-15), "representation transition ratio mismatch")
    require(
        math.isclose(
            float(value["irrelevant_padding_transition_ratio"]),
            padded_audit["transitions"] / audited[0]["transitions"],
            rel_tol=1e-15,
        ),
        "irrelevant padding transition ratio mismatch",
    )
    require(
        math.isclose(
            float(value["irrelevant_padding_field_byte_ratio"]),
            int(padded["field_bytes"]) / int(variants[0]["field_bytes"]),
            rel_tol=1e-15,
        ),
        "irrelevant padding byte ratio mismatch",
    )
    return len(audited) + 1


def verify(path: Path) -> dict[str, Any]:
    receipt_value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(receipt_value, dict) and receipt_value.get("schema") == SCHEMA, "receipt schema mismatch")
    receipt = cast(dict[str, Any], receipt_value)
    rows_value = receipt.get("cases")
    require(
        isinstance(rows_value, list)
        and len(rows_value) == 282
        and all(isinstance(row, dict) for row in rows_value),
        "corpus case count mismatch",
    )
    rows = cast(list[Mapping[str, Any]], rows_value)
    names = [row.get("name") for row in rows]
    require(len(names) == len(set(names)), "case names are not unique")
    require(sum(str(name).startswith("complete3_") for name in names) == 255, "complete CNF corpus mismatch")

    audited = [audit_row(row, permit_structural_oracle=True) for row in rows]
    exact = [row for row, source in zip(audited, rows) if source["exact_truth_table_oracle"]]
    corpus_value = receipt.get("corpus")
    require(isinstance(corpus_value, dict), "missing corpus summary")
    corpus = cast(dict[str, Any], corpus_value)
    expected_corpus = {
        "cases": len(audited),
        "sat": sum(row["status"] == "sat" for row in audited),
        "unsat": sum(row["status"] == "unsat" for row in audited),
        "exhausted": 0,
        "exact_truth_table_cases": len(exact),
        "complete_three_variable_formulas": 255,
        "all_unsat_refutations_built": all(
            row["unsat_proof_verified"]
            for row in audited
            if row["status"] == "unsat"
        ),
        "all_expected_decisions": True,
        "all_sat_certificates_verified": True,
        "all_exact_oracles_matched": True,
        "all_checked_learned_clauses_sound": all(row["learned_sound"] is not False for row in exact),
    }
    require(corpus == expected_corpus, "corpus aggregate mismatch")

    representation_value = receipt.get("representation")
    require(isinstance(representation_value, dict), "missing representation receipt")
    representation_count = audit_representation(cast(dict[str, Any], representation_value))
    proof_summary_value = receipt.get("proof_complexity")
    require(isinstance(proof_summary_value, dict), "missing proof-complexity summary")
    proof_summary = cast(dict[str, Any], proof_summary_value)
    proof_stats = [
        cast(Mapping[str, int], row["proof_stats"])
        for row in audited
    ]
    expected_proof_summary = {
        "proof_system": (
            "chronological DPLL resolution DAG with linear conflict derivations, "
            "weakening to decision nogoods, lemma reuse, and a depth-first "
            "branch-closure tree"
        ),
        "all_unsat_refutations_built": all(
            row["unsat_proof_verified"]
            for row in audited
            if row["status"] == "unsat"
        ),
        "unsat_refutations": sum(row["status"] == "unsat" for row in audited),
        "total_conflict_derivations": sum(row["conflict_derivations"] for row in proof_stats),
        "total_leaf_resolution_steps": sum(row["leaf_resolution_steps"] for row in proof_stats),
        "total_leaf_weakenings": sum(row["leaf_weakenings"] for row in proof_stats),
        "total_closure_resolution_steps": sum(row["closure_resolution_steps"] for row in proof_stats),
        "total_inference_steps": sum(row["inference_steps"] for row in proof_stats),
        "maximum_proof_payload_bytes": max(
            (row["payload_json_bytes"] for row in proof_stats),
            default=0,
        ),
        "known_lower_bound": {
            "formula_family": "standard PHP_(h+1)^h over N=h(h+1) variables",
            "resolution_size": "2^Omega(h) = 2^Omega(sqrt(N))",
            "trace_translation": "the emitted resolution DAG has O(N*T) inferences for T field transitions",
            "consequence": "the implemented transition law has superpolynomial worst-case T on this family",
            "source": "Haken, The Intractability of Resolution, doi:10.1016/0304-3975(85)90144-6",
        },
    }
    require(proof_summary == expected_proof_summary, "proof-complexity aggregate mismatch")
    storage_value = receipt.get("polynomial_storage")
    require(isinstance(storage_value, dict), "missing storage receipt")
    storage = cast(dict[str, Any], storage_value)
    require(storage.get("checked_cases") == len(audited) + representation_count, "storage case count mismatch")
    require(storage.get("bound_bytes") == "72 * max(21, n, m+8n, (m+8n)n)", "storage bound label mismatch")
    audit_scaling(receipt, audited)

    contract_value = receipt.get("field_contract")
    require(isinstance(contract_value, dict), "missing field contract")
    contract = cast(dict[str, Any], contract_value)
    require(
        contract.get("proof_output")
        == "conflict derivations and branch-closure refutations are nonadaptive receipts and are never fed back into search",
        "proof output contract mismatch",
    )
    require(contract.get("fixed_action_vocabulary") == list(ACTIONS), "fixed action contract mismatch")
    for key in ("host_candidate_generation", "host_search_scheduling", "learned_side_tables", "model_calls"):
        require(contract.get(key) == 0, f"field contract reports nonzero {key}")
    assessment_value = receipt.get("assessment")
    require(isinstance(assessment_value, dict), "missing assessment")
    assessment = cast(dict[str, Any], assessment_value)
    require(
        assessment.get("polynomial_running_time")
        == "ruled out for this solver by Haken's standard pigeonhole resolution lower bound and the O(N*T) trace-to-refutation translation",
        "runtime assessment mismatch",
    )
    require(assessment.get("p_equals_np") == "not established", "P versus NP assessment overclaims")
    return {
        "corpus_cases": len(audited),
        "representation_cases": representation_count,
        "truth_table_cases": len(exact),
        "sat": expected_corpus["sat"],
        "all_unsat_resolution_refutations_verified": expected_proof_summary[
            "all_unsat_refutations_built"
        ],
        "proof_inference_steps": expected_proof_summary["total_inference_steps"],
        "unsat": expected_corpus["unsat"],
        "all_learned_clauses_sound_where_enumerated": expected_corpus["all_checked_learned_clauses_sound"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = verify(args.receipt)
    print(json.dumps(result, indent=2, sort_keys=True))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
