"""Independent standard-library verifier for alias exact-one receipts."""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
import math
import struct
from pathlib import Path
from typing import Any

RECEIPT = Path("_diag/alias_exact_one_decision.json")
MAGIC = 0x414C584F
VERSION = 1
HEADER = 13


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def recognize(value: Any, variables: int, name: str) -> dict[str, Any]:
    require(isinstance(value, list) and bool(value), f"{name}: formula missing")
    clauses = []
    for raw in value:
        require(
            isinstance(raw, list)
            and len(raw) == 3
            and all(
                isinstance(variable, int)
                and not isinstance(variable, bool)
                and 1 <= variable <= variables
                for variable in raw
            ),
            f"{name}: malformed clause",
        )
        clause = tuple(sorted(raw))
        require(len(set(clause)) == 3, f"{name}: repeated clause variable")
        clauses.append(clause)
    formula = tuple(sorted(clauses))
    incidence: list[list[int]] = [[] for _ in range(variables)]
    for clause_index, clause in enumerate(formula):
        for variable in clause:
            incidence[variable - 1].append(clause_index)
    degrees = tuple(len(rows) for rows in incidence)
    require(all(degree in (2, 3) for degree in degrees), f"{name}: degree promise fails")
    cubic = tuple(index + 1 for index, degree in enumerate(degrees) if degree == 3)
    return {
        "formula": formula,
        "incidence": tuple(tuple(rows) for rows in incidence),
        "degrees": degrees,
        "cubic": cubic,
    }


def branch_structure(
    recognized: dict[str, Any],
    branch: int,
) -> dict[str, Any]:
    cubic = recognized["cubic"]
    bits = tuple((branch >> index) & 1 for index in range(len(cubic)))
    values = dict(zip(cubic, bits))
    counts = tuple(
        sum(values.get(variable, 0) for variable in clause)
        for clause in recognized["formula"]
    )
    conflict = next((index for index, count in enumerate(counts) if count > 1), None)
    residual = tuple(index for index, count in enumerate(counts) if count == 0)
    residual_set = set(residual)
    pair_variables: dict[tuple[int, int], list[int]] = {}
    for variable, degree in enumerate(recognized["degrees"], 1):
        if degree != 2:
            continue
        incident = recognized["incidence"][variable - 1]
        if all(clause in residual_set for clause in incident):
            pair = tuple(sorted(incident))
            pair_variables.setdefault((pair[0], pair[1]), []).append(variable)
    adjacency = {clause: set() for clause in residual}
    for left, right in pair_variables:
        adjacency[left].add(right)
        adjacency[right].add(left)
    return {
        "bits": bits,
        "conflict": conflict,
        "residual": residual,
        "pair_variables": pair_variables,
        "adjacency": adjacency,
    }


def component_sizes(adjacency: dict[int, set[int]], removed: set[int]) -> list[int]:
    unseen = set(adjacency) - removed
    sizes = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        size = 0
        while stack:
            clause = stack.pop()
            size += 1
            for neighbor in adjacency[clause]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sizes


def verify_matching(
    value: Any,
    structure: dict[str, Any],
    name: str,
) -> tuple[set[int], list[int]]:
    require(isinstance(value, list), f"{name}: matching missing")
    used: set[int] = set()
    selected_variables = []
    pair_variables = structure["pair_variables"]
    for edge in value:
        require(
            isinstance(edge, list)
            and len(edge) == 3
            and all(isinstance(item, int) and not isinstance(item, bool) for item in edge),
            f"{name}: malformed matching edge",
        )
        left, right, variable = edge
        require(left < right and (left, right) in pair_variables, f"{name}: matching non-edge")
        require(left not in used and right not in used, f"{name}: matching repeats a clause")
        require(variable == min(pair_variables[(left, right)]), f"{name}: noncanonical source lift")
        used.update((left, right))
        selected_variables.append(variable)
    return used, selected_variables


def verify_witness(
    witness: Any,
    recognized: dict[str, Any],
    expected_branch: int,
    name: str,
) -> tuple[str, list[int] | None, int, int]:
    require(isinstance(witness, dict), f"{name}: branch witness missing")
    require(witness.get("branch") == expected_branch, f"{name}: branch order mismatch")
    structure = branch_structure(recognized, expected_branch)
    require(witness.get("cubic_bits") == list(structure["bits"]), f"{name}: cubic bits mismatch")
    expected_residual = (
        []
        if structure["conflict"] is not None
        else list(structure["residual"])
    )
    require(
        witness.get("residual_clauses") == expected_residual,
        f"{name}: residual clause set mismatch",
    )
    reason = witness.get("reason")
    status = witness.get("status")
    require(status in ("sat", "unsat"), f"{name}: witness status invalid")
    used, selected_variables = verify_matching(witness.get("matching"), structure, name)
    proof_matching_runs = 0
    proof_barrier_runs = 0
    assignment = None
    if structure["conflict"] is not None:
        require(
            status == "unsat"
            and reason == "clause-conflict"
            and witness.get("conflict_clause") == structure["conflict"]
            and not used
            and witness.get("tutte_barrier") is None,
            f"{name}: conflict witness mismatch",
        )
    elif len(structure["residual"]) % 2:
        require(
            status == "unsat"
            and reason == "odd-residual"
            and witness.get("conflict_clause") is None
            and not used
            and witness.get("tutte_barrier") is None,
            f"{name}: odd residual witness mismatch",
        )
    elif status == "sat":
        proof_matching_runs = 1
        require(
            reason == "perfect-matching"
            and used == set(structure["residual"])
            and witness.get("conflict_clause") is None
            and witness.get("tutte_barrier") is None,
            f"{name}: SAT residual is not perfectly matched",
        )
        assignment = [0] * len(recognized["degrees"])
        for variable, bit in zip(recognized["cubic"], structure["bits"]):
            assignment[variable - 1] = bit
        for variable in selected_variables:
            assignment[variable - 1] = 1
        require(
            all(
                sum(assignment[variable - 1] for variable in clause) == 1
                for clause in recognized["formula"]
            ),
            f"{name}: reconstructed assignment fails source",
        )
    else:
        proof_matching_runs = 1
        require(reason == "tutte-barrier", f"{name}: even residual lacks Tutte witness")
        barrier_value = witness.get("tutte_barrier")
        require(
            isinstance(barrier_value, list)
            and barrier_value == sorted(set(barrier_value))
            and all(clause in structure["adjacency"] for clause in barrier_value),
            f"{name}: Tutte barrier invalid",
        )
        barrier = set(barrier_value)
        sizes = component_sizes(structure["adjacency"], barrier)
        odd = sum(size % 2 for size in sizes)
        require(odd > len(barrier), f"{name}: Tutte inequality fails")
        require(
            witness.get("component_sizes") == sizes
            and witness.get("odd_components") == odd
            and witness.get("deficiency") == odd - len(barrier),
            f"{name}: Tutte aggregates mismatch",
        )
        proof_barrier_runs = len(structure["residual"])
    return status, assignment, proof_matching_runs, proof_barrier_runs


def verify_state(
    descriptor: Any,
    certificate: dict[str, Any],
    recognized: dict[str, Any],
    name: str,
) -> None:
    require(isinstance(descriptor, dict), f"{name}: state descriptor missing")
    require(descriptor.get("schema") == "cassifi.alias-exact-one-state.v1", f"{name}: state schema")
    clauses = len(recognized["formula"])
    variables = len(recognized["degrees"])
    cubic_count = len(recognized["cubic"])
    profile = {"clauses": clauses, "variables": variables, "cubic_variables": cubic_count}
    profile_sha = hashlib.sha256(canonical(profile)).hexdigest()
    require(
        descriptor.get("profile") == profile
        and descriptor.get("profile_sha256") == profile_sha == certificate.get("profile_sha256"),
        f"{name}: profile mismatch",
    )
    encoded = descriptor.get("field_b64")
    require(isinstance(encoded, str), f"{name}: field encoding missing")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise AssertionError(f"{name}: field encoding invalid") from exc
    require(
        descriptor.get("state_sha256") == hashlib.sha256(raw).hexdigest()
        == certificate.get("state_sha256"),
        f"{name}: state digest mismatch",
    )
    expected_values = HEADER + 3 * clauses + 2 * variables + cubic_count
    require(len(raw) == 8 * expected_values, f"{name}: field size mismatch")
    values = struct.unpack(f"<{expected_values}d", raw)
    require(all(math.isfinite(value) and value == int(value) for value in values), f"{name}: noninteger field")
    values = tuple(int(value) for value in values)
    status_code = 1 if certificate["status"] == "sat" else 2
    branches = 1 << cubic_count
    selected = (
        certificate["branch_witnesses"][0]["branch"]
        if certificate["status"] == "sat"
        else -1
    )
    require(
        values[:6] == (MAGIC, VERSION, status_code, clauses, variables, cubic_count)
        and values[6] == certificate["branches_checked"]
        and values[7] == branches
        and values[8] == certificate["branches_checked"]
        and values[9] == certificate["search_matching_runs"]
        and values[10] == certificate["search_edge_scans"]
        and values[11] == certificate["search_blossom_contractions"]
        and values[12] == selected,
        f"{name}: field header/counter mismatch",
    )
    clause_start = HEADER
    degree_start = clause_start + 3 * clauses
    cubic_start = degree_start + variables
    assignment_start = cubic_start + cubic_count
    require(
        values[clause_start:degree_start]
        == tuple(variable for clause in recognized["formula"] for variable in clause)
        and values[degree_start:cubic_start] == recognized["degrees"]
        and values[cubic_start:assignment_start] == recognized["cubic"],
        f"{name}: field source coordinates mismatch",
    )
    expected_assignment = (
        tuple(certificate["assignment"])
        if certificate["status"] == "sat"
        else (-1,) * variables
    )
    require(values[assignment_start:] == expected_assignment, f"{name}: field assignment mismatch")
    require(
        certificate.get("field_values") == expected_values
        and certificate.get("field_bytes") == len(raw),
        f"{name}: certificate field resources mismatch",
    )


def brute_has_model(recognized: dict[str, Any]) -> bool:
    for assignment in itertools.product((0, 1), repeat=len(recognized["degrees"])):
        if all(
            sum(assignment[variable - 1] for variable in clause) == 1
            for clause in recognized["formula"]
        ):
            return True
    return False


def verify_case(row: Any) -> dict[str, Any]:
    require(isinstance(row, dict), "case malformed")
    name = row.get("name")
    variables = row.get("variables")
    require(isinstance(name, str) and bool(name), "case name invalid")
    require(isinstance(variables, int) and not isinstance(variables, bool), f"{name}: variables invalid")
    recognized = recognize(row.get("formula"), variables, name)
    certificate = row.get("certificate")
    require(isinstance(certificate, dict), f"{name}: certificate missing")
    require(certificate.get("schema") == "cassifi.alias-exact-one-decision.v1", f"{name}: schema")
    branches = 1 << len(recognized["cubic"])
    require(
        certificate.get("formula") == [list(clause) for clause in recognized["formula"]]
        and certificate.get("clauses") == len(recognized["formula"])
        and certificate.get("variables") == variables
        and certificate.get("cubic_variables") == list(recognized["cubic"])
        and certificate.get("branches") == branches,
        f"{name}: theorem premises mismatch",
    )
    witnesses = certificate.get("branch_witnesses")
    require(isinstance(witnesses, list) and bool(witnesses), f"{name}: witnesses missing")
    status = certificate.get("status")
    require(status in ("sat", "unsat"), f"{name}: status invalid")
    expected_branches = (
        [witnesses[0].get("branch")]
        if status == "sat" and isinstance(witnesses[0], dict)
        else list(range(branches))
    )
    require(len(witnesses) == len(expected_branches), f"{name}: witness count mismatch")
    proof_matching_runs = 0
    proof_barrier_runs = 0
    reconstructed_assignment = None
    for witness, branch in zip(witnesses, expected_branches):
        require(isinstance(branch, int) and 0 <= branch < branches, f"{name}: branch invalid")
        branch_status, assignment, matching_runs, barrier_runs = verify_witness(
            witness,
            recognized,
            branch,
            name,
        )
        require(branch_status == ("sat" if status == "sat" else "unsat"), f"{name}: branch verdict mismatch")
        reconstructed_assignment = assignment
        proof_matching_runs += matching_runs
        proof_barrier_runs += barrier_runs
    if status == "sat":
        require(
            certificate.get("assignment") == reconstructed_assignment
            and certificate.get("branches_checked") == expected_branches[0] + 1,
            f"{name}: SAT assignment/search stopping mismatch",
        )
    else:
        require(
            certificate.get("assignment") is None
            and certificate.get("branches_checked") == branches,
            f"{name}: UNSAT enumeration incomplete",
        )
    require(
        certificate.get("proof_matching_runs") == proof_matching_runs
        and certificate.get("proof_barrier_matching_runs") == proof_barrier_runs,
        f"{name}: proof resource aggregates mismatch",
    )
    problem_sha = hashlib.sha256(canonical(recognized["formula"])).hexdigest()
    require(certificate.get("problem_sha256") == problem_sha, f"{name}: problem digest")
    claimed = certificate.get("certificate_sha256")
    digest_value = dict(certificate)
    digest_value.pop("certificate_sha256", None)
    require(
        isinstance(claimed, str) and hashlib.sha256(canonical(digest_value)).hexdigest() == claimed,
        f"{name}: certificate digest",
    )
    verify_state(row.get("state"), certificate, recognized, name)
    if row.get("enumerated") is True:
        require(brute_has_model(recognized) == (status == "sat"), f"{name}: truth-table disagreement")
    return {
        "status": status,
        "enumerated": row.get("enumerated") is True,
        "step_replayed": row.get("public_steps_replayed") is True,
        "clauses": len(recognized["formula"]),
        "variables": variables,
        "cubic": len(recognized["cubic"]),
        "branches": branches,
        "branches_checked": certificate["branches_checked"],
        "field_bytes": certificate["field_bytes"],
        "search_matching_runs": certificate["search_matching_runs"],
        "proof_barrier_runs": certificate["proof_barrier_matching_runs"],
    }


def verify(path: Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") == "cassifi.alias-exact-one-receipt.v1", "receipt schema")
    cases = receipt.get("cases")
    require(isinstance(cases, list) and bool(cases), "receipt cases missing")
    audited = [verify_case(row) for row in cases]
    controls = receipt.get("controls")
    require(
        controls
        == [
            {
                "name": "degree-one-variable",
                "status": "rejected",
                "error": "every variable must occur exactly two or three times",
            },
            {
                "name": "repeated-clause-variable",
                "status": "rejected",
                "error": "a clause repeats a variable",
            },
            {
                "name": "negative-variable",
                "status": "rejected",
                "error": "clauses must contain three positive in-range variables",
            },
            {
                "name": "damaged-checkpoint",
                "status": "rejected",
                "error": "alias state digest mismatch",
            },
        ],
        "receipt controls mismatch",
    )
    summary = {
        "cases": len(audited),
        "truth_table_cases": sum(row["enumerated"] for row in audited),
        "step_replays": sum(row["step_replayed"] for row in audited),
        "sat": sum(row["status"] == "sat" for row in audited),
        "unsat": sum(row["status"] == "unsat" for row in audited),
        "maximum_clauses": max(row["clauses"] for row in audited),
        "maximum_variables": max(row["variables"] for row in audited),
        "maximum_cubic_variables": max(row["cubic"] for row in audited),
        "maximum_available_branches": max(row["branches"] for row in audited),
        "maximum_branches_checked": max(row["branches_checked"] for row in audited),
        "maximum_field_bytes": max(row["field_bytes"] for row in audited),
        "maximum_search_matching_runs": max(row["search_matching_runs"] for row in audited),
        "maximum_proof_barrier_runs": max(row["proof_barrier_runs"] for row in audited),
        "all_checkpoints_exact": True,
        "all_truth_tables_agree": True,
    }
    require(receipt.get("summary") == summary, "receipt summary mismatch")
    result = {
        "all_branch_certificates_independently_checked": True,
        **summary,
        "controls": len(controls),
    }
    print(json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    verify()
