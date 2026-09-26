"""Independent verifier for the general matched exact-one decision receipt.

This module imports neither the field implementation nor its scenario runner.
SAT is accepted only from a checked perfect matching and source assignment.
UNSAT is accepted only from a checked Tutte odd-component obstruction.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import struct
from pathlib import Path
from typing import Any, Sequence

RECEIPT = Path("_diag/general_matched_decision.json")
MAGIC = 0x474D584F
VERSION = 1
HEADER = 12


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


def literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def canonical_formula(value: Any, variables: int, name: str) -> tuple[tuple[int, ...], ...]:
    require(isinstance(value, list), f"{name}: formula is not a list")
    rows = []
    for raw_clause in value:
        require(isinstance(raw_clause, list), f"{name}: clause is not a list")
        require(
            all(isinstance(literal, int) and not isinstance(literal, bool) for literal in raw_clause),
            f"{name}: clause contains a non-integer",
        )
        clause = tuple(sorted(raw_clause, key=literal_key))
        require(bool(clause) and all(literal != 0 for literal in clause), f"{name}: empty/zero clause")
        require(
            all(abs(literal) <= variables for literal in clause),
            f"{name}: literal outside variable range",
        )
        require(
            len({abs(literal) for literal in clause}) == len(clause),
            f"{name}: repeated/complementary literal",
        )
        rows.append(clause)
    require(len(set(rows)) == len(rows), f"{name}: duplicate clause")
    return tuple(sorted(rows, key=lambda clause: (len(clause), clause)))


def recognize(formula_value: Any, variables: int, name: str) -> dict[str, Any]:
    source = canonical_formula(formula_value, variables, name)
    source_set = set(source)
    blocks = tuple(
        sorted(
            (
                clause
                for clause in source
                if len(clause) == 3 and all(literal > 0 for literal in clause)
            )
        )
    )
    require(len(blocks) >= 4 and len(blocks) % 2 == 0, f"{name}: block count invalid")
    flattened = tuple(variable for block in blocks for variable in block)
    require(
        len(flattened) == variables
        and len(set(flattened)) == variables
        and set(flattened) == set(range(1, variables + 1)),
        f"{name}: blocks do not partition variables",
    )
    block_for = {
        variable: block_index
        for block_index, block in enumerate(blocks)
        for variable in block
    }
    exact = set()
    for block in blocks:
        exact.add(block)
        for left_index in range(3):
            for right_index in range(left_index + 1, 3):
                exact.add(
                    tuple(
                        sorted(
                            (-block[left_index], -block[right_index]),
                            key=literal_key,
                        )
                    )
                )
    require(exact.issubset(source_set), f"{name}: incomplete exact-one block")
    groups: dict[tuple[int, int], list[tuple[int, ...]]] = {}
    for clause in source_set - exact:
        require(len(clause) == 2, f"{name}: non-binary remainder")
        support = tuple(sorted(abs(literal) for literal in clause))
        require(
            len(set(support)) == 2 and block_for[support[0]] != block_for[support[1]],
            f"{name}: repeated/internal matching support",
        )
        groups.setdefault((support[0], support[1]), []).append(clause)
    edges = []
    incidence = {variable: 0 for variable in range(1, variables + 1)}
    adjacency = [set() for _ in blocks]
    for support in sorted(groups):
        clauses = groups[support]
        require(len(clauses) == 2, f"{name}: incomplete parity support")
        masks = set()
        for clause in clauses:
            mask = 0
            for position, variable in enumerate(support):
                literal = next(item for item in clause if abs(item) == variable)
                if literal < 0:
                    mask |= 1 << position
            masks.add(mask)
        require(masks in ({0, 3}, {1, 2}), f"{name}: malformed parity clauses")
        parity = 1 if masks == {0, 3} else 0
        left, right = support
        left_block = block_for[left]
        right_block = block_for[right]
        incidence[left] += 1
        incidence[right] += 1
        adjacency[left_block].add(right_block)
        adjacency[right_block].add(left_block)
        edges.append(
            {
                "variables": [left, right],
                "parity": parity,
                "blocks": [left_block, right_block],
            }
        )
    require(
        len(edges) * 2 == variables and all(count == 1 for count in incidence.values()),
        f"{name}: variable supports are not a perfect matching",
    )
    reached = {0}
    stack = [0]
    while stack:
        block = stack.pop()
        for neighbor in adjacency[block] - reached:
            reached.add(neighbor)
            stack.append(neighbor)
    require(len(reached) == len(blocks), f"{name}: quotient disconnected")
    return {"source": source, "blocks": blocks, "edges": edges}


def build_auxiliary(recognized: dict[str, Any]) -> tuple[int, list[list[int]]]:
    blocks = len(recognized["blocks"])
    odd_rank = 0
    auxiliary = []
    for source, edge in enumerate(recognized["edges"]):
        left, right = edge["blocks"]
        if edge["parity"] == 0:
            auxiliary.append([left, right, source])
        else:
            node = blocks + odd_rank
            odd_rank += 1
            auxiliary.append([left, node, source])
            auxiliary.append([right, node, source])
    auxiliary.sort(key=lambda item: (min(item[0], item[1]), max(item[0], item[1]), item[2]))
    return blocks + odd_rank, auxiliary


def graph_from(vertex_count: int, edges: Sequence[Sequence[int]]) -> tuple[tuple[int, ...], ...]:
    adjacency = [set() for _ in range(vertex_count)]
    for edge in edges:
        require(len(edge) == 3, "auxiliary edge arity mismatch")
        left, right, _ = edge
        require(
            isinstance(left, int)
            and not isinstance(left, bool)
            and isinstance(right, int)
            and not isinstance(right, bool)
            and 0 <= left < vertex_count
            and 0 <= right < vertex_count
            and left != right,
            "auxiliary edge endpoint invalid",
        )
        adjacency[left].add(right)
        adjacency[right].add(left)
    return tuple(tuple(sorted(neighbors)) for neighbors in adjacency)


def component_sizes(graph: Sequence[Sequence[int]], removed: set[int]) -> list[int]:
    unseen = set(range(len(graph))) - removed
    sizes = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        size = 0
        while stack:
            vertex = stack.pop()
            size += 1
            for neighbor in graph[vertex]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sizes


def check_matching(value: Any, graph: Sequence[Sequence[int]], name: str) -> set[int]:
    require(isinstance(value, list), f"{name}: matching missing")
    used: set[int] = set()
    for pair in value:
        require(
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(vertex, int) and not isinstance(vertex, bool) for vertex in pair),
            f"{name}: matching pair invalid",
        )
        left, right = pair
        require(0 <= left < right < len(graph), f"{name}: matching pair range/order invalid")
        require(left not in used and right not in used, f"{name}: matching repeats a vertex")
        require(right in graph[left], f"{name}: matching uses a non-edge")
        used.update(pair)
    return used


def assignment_from_matching(
    matching: Sequence[Sequence[int]],
    recognized: dict[str, Any],
    auxiliary: Sequence[Sequence[int]],
) -> list[int]:
    block_count = len(recognized["blocks"])
    sources_for_pair: dict[tuple[int, int], list[int]] = {}
    odd_source: dict[int, int] = {}
    for left, right, source in auxiliary:
        pair = (min(left, right), max(left, right))
        sources_for_pair.setdefault(pair, []).append(source)
        if left >= block_count:
            odd_source[left] = source
        if right >= block_count:
            odd_source[right] = source
    assignment = [0] * (3 * block_count)
    for left, right in matching:
        if right < block_count:
            source = min(sources_for_pair[(left, right)])
            edge = recognized["edges"][source]
            for variable in edge["variables"]:
                assignment[variable - 1] = 1
            continue
        source = odd_source[right]
        edge = recognized["edges"][source]
        chosen_block = left
        chosen_index = edge["blocks"].index(chosen_block)
        assignment[edge["variables"][chosen_index] - 1] = 1
    return assignment


def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def verify_state(
    descriptor: Any,
    certificate: dict[str, Any],
    recognized: dict[str, Any],
    auxiliary: list[list[int]],
    name: str,
) -> None:
    require(isinstance(descriptor, dict), f"{name}: state descriptor missing")
    require(
        descriptor.get("schema") == "cassifi.general-matched-exact-one-state.v1",
        f"{name}: state schema mismatch",
    )
    blocks = len(recognized["blocks"])
    odd_edges = sum(edge["parity"] for edge in recognized["edges"])
    profile = {"blocks": blocks, "odd_edges": odd_edges}
    require(descriptor.get("profile") == profile, f"{name}: profile mismatch")
    profile_sha256 = hashlib.sha256(canonical(profile)).hexdigest()
    require(
        descriptor.get("profile_sha256") == profile_sha256 == certificate.get("profile_sha256"),
        f"{name}: profile digest mismatch",
    )
    encoded = descriptor.get("field_b64")
    require(isinstance(encoded, str), f"{name}: field base64 missing")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError) as exc:
        raise AssertionError(f"{name}: field base64 invalid") from exc
    require(
        descriptor.get("state_sha256") == hashlib.sha256(raw).hexdigest()
        == certificate.get("state_sha256"),
        f"{name}: state digest mismatch",
    )
    expected_values = 12 + 17 * blocks + 5 * odd_edges
    require(len(raw) == 8 * expected_values, f"{name}: field byte count mismatch")
    values = struct.unpack(f"<{expected_values}d", raw)
    require(all(math.isfinite(value) and value == int(value) for value in values), f"{name}: field non-integer")
    integers = [int(value) for value in values]
    status_code = 1 if certificate["status"] == "sat" else 2
    auxiliary_vertices = blocks + odd_edges
    require(
        integers[:5] == [MAGIC, VERSION, status_code, blocks, odd_edges],
        f"{name}: field header mismatch",
    )
    require(
        integers[5] == auxiliary_vertices
        and integers[6] == certificate["augmentations"]
        and integers[7] == certificate["edge_scans"]
        and integers[8] == certificate["blossom_contractions"]
        and integers[9] == certificate["matching_size"]
        and integers[10] == certificate["barrier_matching_runs"]
        and integers[11] == auxiliary_vertices
        and certificate["field_values"] == expected_values
        and certificate["field_bytes"] == len(raw),
        f"{name}: field terminal counters mismatch",
    )
    block_start = HEADER
    formula_start = block_start + 3 * blocks
    aux_start = formula_start + 3 * len(recognized["edges"])
    matching_start = aux_start + 3 * len(auxiliary)
    barrier_start = matching_start + auxiliary_vertices
    assignment_start = barrier_start + auxiliary_vertices
    expected_blocks = [value for block in recognized["blocks"] for value in block]
    expected_edges = [
        value
        for edge in recognized["edges"]
        for value in (*edge["variables"], edge["parity"])
    ]
    expected_auxiliary = [value for edge in auxiliary for value in edge]
    require(integers[block_start:formula_start] == expected_blocks, f"{name}: field blocks mismatch")
    require(integers[formula_start:aux_start] == expected_edges, f"{name}: field formula edges mismatch")
    require(integers[aux_start:matching_start] == expected_auxiliary, f"{name}: field graph mismatch")
    expected_mates = [-1] * auxiliary_vertices
    for left, right in certificate["matching"]:
        expected_mates[left] = right
        expected_mates[right] = left
    require(integers[matching_start:barrier_start] == expected_mates, f"{name}: field matching mismatch")
    if certificate["status"] == "sat":
        require(
            integers[barrier_start:assignment_start] == [-1] * auxiliary_vertices,
            f"{name}: SAT field has barrier",
        )
        require(
            integers[assignment_start:] == certificate["assignment"],
            f"{name}: SAT field assignment mismatch",
        )
    else:
        expected_barrier = [0] * auxiliary_vertices
        for vertex in certificate["tutte_barrier"]:
            expected_barrier[vertex] = 1
        require(
            integers[barrier_start:assignment_start] == expected_barrier,
            f"{name}: UNSAT field barrier mismatch",
        )
        require(
            integers[assignment_start:] == [-1] * (3 * blocks),
            f"{name}: UNSAT field has assignment",
        )


def verify_case(row: Any) -> dict[str, Any]:
    require(isinstance(row, dict), "case is not an object")
    name = row.get("name")
    blocks = row.get("blocks")
    require(isinstance(name, str) and bool(name), "case name invalid")
    require(isinstance(blocks, int) and not isinstance(blocks, bool), f"{name}: blocks invalid")
    variables = 3 * blocks
    recognized = recognize(row.get("formula"), variables, name)
    require(len(recognized["blocks"]) == blocks, f"{name}: case block count mismatch")
    require(
        row.get("labels") == [edge["parity"] for edge in recognized["edges"]],
        f"{name}: serialized labels disagree with source CNF",
    )
    certificate = row.get("certificate")
    require(isinstance(certificate, dict), f"{name}: certificate missing")
    require(
        certificate.get("schema") == "cassifi.general-matched-exact-one.v1",
        f"{name}: certificate schema mismatch",
    )
    require(
        certificate.get("blocks") == blocks
        and certificate.get("variables") == variables
        and certificate.get("exact_one_blocks") == [list(block) for block in recognized["blocks"]]
        and certificate.get("formula_edges") == recognized["edges"],
        f"{name}: source/certificate theorem structure mismatch",
    )
    auxiliary_vertices, auxiliary = build_auxiliary(recognized)
    require(
        certificate.get("auxiliary_vertices") == auxiliary_vertices
        and certificate.get("auxiliary_edges") == auxiliary,
        f"{name}: canonical auxiliary graph mismatch",
    )
    graph = graph_from(auxiliary_vertices, auxiliary)
    used = check_matching(certificate.get("matching"), graph, name)
    require(
        certificate.get("matching_size") == len(used) // 2,
        f"{name}: matching size mismatch",
    )
    status = certificate.get("status")
    require(status in ("sat", "unsat"), f"{name}: terminal status invalid")
    expected_barrier_runs = (
        auxiliary_vertices
        if status == "unsat" and auxiliary_vertices % 2 == 0
        else 0
    )
    require(
        certificate.get("root_searches") == auxiliary_vertices
        and certificate.get("augmentations") == certificate.get("matching_size")
        and certificate.get("barrier_matching_runs") == expected_barrier_runs
        and isinstance(certificate.get("edge_scans"), int)
        and 0 <= certificate["edge_scans"] <= auxiliary_vertices**3
        and isinstance(certificate.get("blossom_contractions"), int)
        and 0 <= certificate["blossom_contractions"] <= auxiliary_vertices**3,
        f"{name}: controller resource counters mismatch",
    )
    if status == "sat":
        require(len(used) == auxiliary_vertices, f"{name}: SAT matching is not perfect")
        assignment = certificate.get("assignment")
        require(
            isinstance(assignment, list)
            and len(assignment) == variables
            and all(bit in (0, 1) and not isinstance(bit, bool) for bit in assignment),
            f"{name}: SAT assignment invalid",
        )
        require(
            assignment
            == assignment_from_matching(
                certificate["matching"],
                recognized,
                auxiliary,
            ),
            f"{name}: SAT assignment is not the canonical matching lift",
        )
        require(satisfies(recognized["source"], assignment), f"{name}: SAT assignment fails source CNF")
        require(
            certificate.get("tutte_barrier") is None
            and certificate.get("component_sizes") == []
            and certificate.get("deficiency") == 0,
            f"{name}: SAT certificate contains UNSAT data",
        )
    else:
        require(certificate.get("assignment") is None, f"{name}: UNSAT certificate has assignment")
        barrier_value = certificate.get("tutte_barrier")
        require(
            isinstance(barrier_value, list)
            and all(isinstance(vertex, int) and not isinstance(vertex, bool) for vertex in barrier_value)
            and len(set(barrier_value)) == len(barrier_value)
            and all(0 <= vertex < auxiliary_vertices for vertex in barrier_value),
            f"{name}: Tutte barrier invalid",
        )
        barrier = set(barrier_value)
        sizes = component_sizes(graph, barrier)
        odd_components = sum(size % 2 for size in sizes)
        require(odd_components > len(barrier), f"{name}: Tutte inequality does not hold")
        require(
            certificate.get("component_sizes") == sizes
            and certificate.get("odd_components") == odd_components
            and certificate.get("deficiency") == odd_components - len(barrier),
            f"{name}: Tutte aggregates mismatch",
        )
    problem_sha256 = hashlib.sha256(canonical(recognized["source"])).hexdigest()
    require(certificate.get("problem_sha256") == problem_sha256, f"{name}: problem digest mismatch")
    claimed_digest = certificate.get("certificate_sha256")
    digest_value = dict(certificate)
    digest_value.pop("certificate_sha256", None)
    require(
        isinstance(claimed_digest, str)
        and hashlib.sha256(canonical(digest_value)).hexdigest() == claimed_digest,
        f"{name}: certificate digest mismatch",
    )
    verify_state(row.get("state"), certificate, recognized, auxiliary, name)
    return {
        "status": status,
        "enumerated": row.get("enumerated") is True,
        "step_replayed": row.get("public_steps_replayed") is True,
        "blocks": blocks,
        "variables": variables,
        "auxiliary_vertices": auxiliary_vertices,
        "field_bytes": certificate["field_bytes"],
        "edge_scans": certificate["edge_scans"],
        "blossom_contractions": certificate["blossom_contractions"],
        "parity_consistent_unsat": status == "unsat" and sum(row["labels"]) % 2 == 0,
    }


def verify(path: Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(
        receipt.get("schema") == "cassifi.general-matched-decision-receipt.v1",
        "receipt schema mismatch",
    )
    cases = receipt.get("cases")
    require(isinstance(cases, list) and bool(cases), "receipt cases missing")
    audited = [verify_case(row) for row in cases]
    controls = receipt.get("controls")
    require(
        isinstance(controls, list)
        and len(controls) == 4
        and all(
            isinstance(row, dict)
            and row.get("status") == "rejected"
            and isinstance(row.get("error"), str)
            for row in controls
        ),
        "fail-closed controls mismatch",
    )
    summary = {
        "cases": len(audited),
        "exhaustive_cases": sum(row["enumerated"] for row in audited),
        "step_replays": sum(row["step_replayed"] for row in audited),
        "sat": sum(row["status"] == "sat" for row in audited),
        "unsat": sum(row["status"] == "unsat" for row in audited),
        "parity_consistent_unsat": sum(row["parity_consistent_unsat"] for row in audited),
        "maximum_blocks": max(row["blocks"] for row in audited),
        "maximum_variables": max(row["variables"] for row in audited),
        "maximum_auxiliary_vertices": max(row["auxiliary_vertices"] for row in audited),
        "maximum_field_bytes": max(row["field_bytes"] for row in audited),
        "maximum_edge_scans": max(row["edge_scans"] for row in audited),
        "maximum_blossom_contractions": max(row["blossom_contractions"] for row in audited),
        "all_checkpoints_exact": True,
        "all_enumerated_decisions_agree": True,
    }
    require(receipt.get("summary") == summary, "receipt summary mismatch")
    output = {
        "all_certificates_independently_checked": True,
        **summary,
        "controls": len(controls),
    }
    print(json.dumps(output, sort_keys=True))
    return output


if __name__ == "__main__":
    verify()
