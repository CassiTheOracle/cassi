#!/usr/bin/env python
"""Independently verify canonical mixed exact-one decision receipts.

This checker uses only the Python standard library.  It imports neither the
field implementation nor the scenario runner.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import itertools
import json
import math
import struct
from pathlib import Path
from typing import Any, Mapping, Sequence, cast

RECEIPT_SCHEMA = "cassifi.canonical-mixed-decision-probe.v1"
CERTIFICATE_SCHEMA = "cassifi.canonical-mixed-decision.v1"
STATE_SCHEMA = "cassifi.canonical-mixed-decision-state.v1"
DEFAULT_RECEIPT = Path("_diag/mixed_exact_one_decision.json")
MAGIC = 0x434D5844
VERSION = 1
RUNNING = 0
SAT = 1
UNSAT = 2
HEADER = 8

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]


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


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    rows: set[Clause] = set()
    for raw_clause in formula:
        require(
            all(isinstance(literal, int) and not isinstance(literal, bool) for literal in raw_clause),
            "formula contains a non-integer literal",
        )
        clause = tuple(sorted(raw_clause, key=literal_key))
        require(bool(clause) and all(literal != 0 for literal in clause), "formula contains an invalid clause")
        require(
            len({abs(literal) for literal in clause}) == len(clause),
            "formula repeats or complements a variable within a clause",
        )
        rows.add(clause)
    require(len(rows) == len(formula), "formula contains duplicate clauses")
    return tuple(sorted(rows, key=lambda clause: (len(clause), clause)))


def parity_clauses(pair: tuple[int, int], parity: int) -> Formula:
    left, right = pair
    if parity == 0:
        return ((left, -right), (-left, right))
    return ((left, right), (-left, -right))


def formula_from_labels(blocks: int, labels: Sequence[int]) -> Formula:
    require(blocks >= 4 and blocks % 2 == 0, "invalid block count")
    require(
        len(labels) == 3 * blocks // 2 and all(label in (0, 1) for label in labels),
        "invalid edge labels",
    )

    def variable(block: int, port: int) -> int:
        return 3 * block + port + 1

    clauses: list[Clause] = []
    for block in range(blocks):
        a, b, c = (variable(block, port) for port in range(3))
        clauses.extend(((a, b, c), (-a, -b), (-a, -c), (-b, -c)))
    matching = [
        (variable(block, 1), variable((block + 1) % blocks, 0))
        for block in range(blocks)
    ]
    matching.extend(
        (variable(block, 2), variable(block + 1, 2))
        for block in range(0, blocks, 2)
    )
    for pair, label in zip(matching, labels):
        clauses.extend(parity_clauses(pair, label))
    return canonical_formula(clauses)


def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def has_model(formula: Formula, variables: int) -> bool:
    return any(
        satisfies(formula, assignment)
        for assignment in itertools.product((0, 1), repeat=variables)
    )


def pair_valid(
    cycle: Sequence[int],
    chord: Sequence[int],
    blocks: int,
    pair: int,
    previous: int,
    even: int,
    odd: int,
) -> bool:
    block = 2 * pair
    incoming_even = previous ^ cycle[(block - 1) % blocks]
    if incoming_even + even > 1:
        return False
    third_even = 1 - incoming_even - even
    incoming_odd = even ^ cycle[block]
    if incoming_odd + odd > 1:
        return False
    third_odd = 1 - incoming_odd - odd
    return third_even ^ third_odd == chord[pair]


def expected_dynamic_program(
    blocks: int,
    labels: Sequence[int],
) -> tuple[list[list[list[int]]], list[dict[tuple[int, int], tuple[int, int]]]]:
    pairs = blocks // 2
    cycle = labels[:blocks]
    chord = labels[blocks:]
    layers: list[list[list[int]]] = [[[1, 0], [0, 1]]]
    parents: list[dict[tuple[int, int], tuple[int, int]]] = [{}]
    for pair in range(pairs):
        prior = layers[-1]
        reached = [[0, 0], [0, 0]]
        parent: dict[tuple[int, int], tuple[int, int]] = {}
        for boundary in (0, 1):
            for previous in (0, 1):
                for even in (0, 1):
                    for odd in (0, 1):
                        if (
                            not prior[boundary][previous]
                            or not pair_valid(
                                cycle,
                                chord,
                                blocks,
                                pair,
                                previous,
                                even,
                                odd,
                            )
                            or reached[boundary][odd]
                        ):
                            continue
                        reached[boundary][odd] = 1
                        parent[(boundary, odd)] = (previous, even)
        layers.append(reached)
        parents.append(parent)
    return layers, parents


def assignment_from_path(
    blocks: int,
    labels: Sequence[int],
    boundary: int,
    parents: Sequence[Mapping[tuple[int, int], tuple[int, int]]],
) -> list[int]:
    outgoing = [-1] * blocks
    current = boundary
    for pair in range(blocks // 2 - 1, -1, -1):
        previous, even = parents[pair + 1][(boundary, current)]
        outgoing[2 * pair] = even
        outgoing[2 * pair + 1] = current
        current = previous
    require(current == boundary, "DP predecessor path does not close")
    cycle = labels[:blocks]
    assignment = [-1] * (3 * blocks)
    for block in range(blocks):
        port_one = outgoing[block]
        port_zero = outgoing[(block - 1) % blocks] ^ cycle[(block - 1) % blocks]
        port_two = 1 - port_zero - port_one
        require(port_two in (0, 1), "DP witness violates exact-one")
        assignment[3 * block : 3 * block + 3] = [port_zero, port_one, port_two]
    return assignment


def layout(blocks: int) -> dict[str, int]:
    pairs = blocks // 2
    cycle = HEADER
    chord = cycle + blocks
    reach = chord + pairs
    parent_previous = reach + 4 * (pairs + 1)
    parent_even = parent_previous + 4 * pairs
    assignment = parent_even + 4 * pairs
    total = assignment + 3 * blocks
    require(total == 12 + 21 * blocks // 2, "field layout formula mismatch")
    return {
        "cycle": cycle,
        "chord": chord,
        "reach": reach,
        "parent_previous": parent_previous,
        "parent_even": parent_even,
        "assignment": assignment,
        "total": total,
    }


def reach_index(layout_value: Mapping[str, int], pairs: int, boundary: int, layer: int, carry: int) -> int:
    return layout_value["reach"] + ((boundary * (pairs + 1) + layer) * 2 + carry)


def parent_index(pairs: int, boundary: int, layer: int, carry: int) -> int:
    return (boundary * pairs + layer - 1) * 2 + carry


def expected_field_values(
    blocks: int,
    labels: Sequence[int],
    layers: Sequence[Sequence[Sequence[int]]],
    parents: Sequence[Mapping[tuple[int, int], tuple[int, int]]],
    status: str,
    boundary: int | None,
    assignment: Sequence[int] | None,
    *,
    initial: bool,
) -> list[float]:
    positions = layout(blocks)
    pairs = blocks // 2
    values = [0.0] * positions["total"]
    cursor = 0 if initial else pairs
    state_code = RUNNING if initial else SAT if status == "sat" else UNSAT
    values[:HEADER] = [
        float(MAGIC),
        float(VERSION),
        float(state_code),
        float(blocks),
        float(cursor),
        float(cursor),
        float(16 * cursor),
        float(-1 if initial or boundary is None else boundary),
    ]
    values[positions["cycle"] : positions["reach"]] = [float(label) for label in labels]
    values[positions["parent_previous"] : positions["total"]] = [-1.0] * (
        positions["total"] - positions["parent_previous"]
    )
    final_layer = 0 if initial else pairs
    for layer_index in range(final_layer + 1):
        for boundary_index in (0, 1):
            for carry in (0, 1):
                values[
                    reach_index(
                        positions,
                        pairs,
                        boundary_index,
                        layer_index,
                        carry,
                    )
                ] = float(layers[layer_index][boundary_index][carry])
                if layer_index and layers[layer_index][boundary_index][carry]:
                    previous, even = parents[layer_index][(boundary_index, carry)]
                    offset = parent_index(
                        pairs,
                        boundary_index,
                        layer_index,
                        carry,
                    )
                    values[positions["parent_previous"] + offset] = float(previous)
                    values[positions["parent_even"] + offset] = float(even)
    if not initial and assignment is not None:
        values[positions["assignment"] : positions["total"]] = [
            float(bit) for bit in assignment
        ]
    return values


def verify_descriptor(
    row: Mapping[str, Any],
    expected_values: Sequence[float],
    profile_sha256: str,
) -> None:
    name = cast(str, row["name"])
    descriptor = row.get("descriptor")
    require(isinstance(descriptor, dict), f"{name}: descriptor missing")
    descriptor = cast(dict[str, Any], descriptor)
    require(descriptor.get("schema") == STATE_SCHEMA, f"{name}: descriptor schema mismatch")
    require(
        descriptor.get("profile") == {"blocks": row["blocks"]}
        and descriptor.get("profile_sha256") == profile_sha256,
        f"{name}: descriptor profile mismatch",
    )
    encoded = descriptor.get("field_b64")
    require(isinstance(encoded, str), f"{name}: descriptor field missing")
    try:
        raw = base64.b64decode(cast(str, encoded), validate=True)
    except (ValueError, TypeError) as exc:
        raise AssertionError(f"{name}: descriptor base64 is invalid") from exc
    require(len(raw) == 8 * len(expected_values), f"{name}: descriptor field length mismatch")
    require(
        hashlib.sha256(raw).hexdigest() == descriptor.get("state_sha256") == row.get("state_sha256"),
        f"{name}: descriptor state digest mismatch",
    )
    decoded = struct.unpack(f"<{len(expected_values)}d", raw)
    require(all(math.isfinite(value) and value == int(value) for value in decoded), f"{name}: non-integral field value")
    require(list(decoded) == list(expected_values), f"{name}: persisted field content mismatch")


def verify_case(row: Mapping[str, Any]) -> dict[str, Any]:
    name_value = row.get("name")
    require(isinstance(name_value, str), "case name missing")
    name = cast(str, name_value)
    blocks_value = row.get("blocks")
    require(isinstance(blocks_value, int) and not isinstance(blocks_value, bool), f"{name}: invalid blocks")
    blocks = cast(int, blocks_value)
    variables = 3 * blocks
    require(row.get("variables") == variables, f"{name}: variable count mismatch")
    labels_value = row.get("labels")
    require(
        isinstance(labels_value, list)
        and len(labels_value) == 3 * blocks // 2
        and all(label in (0, 1) for label in labels_value),
        f"{name}: labels malformed",
    )
    labels = cast(list[int], labels_value)
    formula_value = row.get("formula")
    require(isinstance(formula_value, list), f"{name}: formula missing")
    formula = canonical_formula(cast(list[list[int]], formula_value))
    require(formula == formula_from_labels(blocks, labels), f"{name}: formula/labels mismatch")
    problem_sha256 = hashlib.sha256(canonical(formula)).hexdigest()
    require(row.get("problem_sha256") == problem_sha256, f"{name}: problem digest mismatch")
    require(row.get("label_xor") == (sum(labels) & 1), f"{name}: label parity mismatch")

    certificate_value = row.get("certificate")
    require(isinstance(certificate_value, dict), f"{name}: certificate missing")
    certificate = cast(dict[str, Any], certificate_value)
    claimed_digest = certificate.get("certificate_sha256")
    unsigned = dict(certificate)
    unsigned.pop("certificate_sha256", None)
    require(
        isinstance(claimed_digest, str)
        and claimed_digest == hashlib.sha256(canonical(unsigned)).hexdigest(),
        f"{name}: certificate digest mismatch",
    )
    profile_sha256 = hashlib.sha256(canonical({"blocks": blocks})).hexdigest()
    require(
        certificate.get("schema") == CERTIFICATE_SCHEMA
        and certificate.get("blocks") == blocks
        and certificate.get("variables") == variables
        and certificate.get("labels") == labels
        and certificate.get("problem_sha256") == problem_sha256
        and certificate.get("profile_sha256") == profile_sha256,
        f"{name}: certificate metadata mismatch",
    )
    pairs = blocks // 2
    require(
        certificate.get("transitions") == pairs
        and certificate.get("candidate_checks") == 8 * blocks
        and certificate.get("field_bytes") == 96 + 84 * blocks
        and row.get("field_bytes") == 96 + 84 * blocks,
        f"{name}: polynomial resource formula mismatch",
    )

    layers, parents = expected_dynamic_program(blocks, labels)
    layers_value = certificate.get("layers")
    require(isinstance(layers_value, list) and len(layers_value) == pairs + 1, f"{name}: DP layers malformed")
    for layer_index, layer_value in enumerate(cast(list[Any], layers_value)):
        require(isinstance(layer_value, dict), f"{name}: DP layer is not an object")
        layer = cast(dict[str, Any], layer_value)
        expected_parents = []
        if layer_index:
            for boundary in (0, 1):
                for carry in (0, 1):
                    if not layers[layer_index][boundary][carry]:
                        continue
                    previous, even = parents[layer_index][(boundary, carry)]
                    expected_parents.append(
                        {
                            "boundary": boundary,
                            "carry": carry,
                            "previous": previous,
                            "even": even,
                        }
                    )
        require(
            layer
            == {
                "reachable": layers[layer_index],
                "parents": expected_parents,
            },
            f"{name}: DP layer {layer_index} mismatch",
        )

    accepting = [
        boundary
        for boundary in (0, 1)
        if layers[-1][boundary][boundary]
    ]
    expected_status = "sat" if accepting else "unsat"
    require(
        certificate.get("status") == expected_status
        and row.get("status") == expected_status,
        f"{name}: decision status mismatch",
    )
    if accepting:
        selected = accepting[0]
        assignment = assignment_from_path(blocks, labels, selected, parents)
        require(
            certificate.get("selected_boundary") == selected
            and certificate.get("assignment") == assignment
            and satisfies(formula, assignment),
            f"{name}: SAT witness mismatch",
        )
    else:
        selected = None
        assignment = None
        require(
            certificate.get("selected_boundary") is None
            and certificate.get("assignment") is None,
            f"{name}: UNSAT certificate contains a witness",
        )
    model = row.get("truth_table_model")
    require(model is None or isinstance(model, bool), f"{name}: truth-table field malformed")
    if isinstance(model, bool):
        require(variables == 12, f"{name}: unexpected truth-table size")
        require(has_model(formula, variables) == model, f"{name}: truth-table result mismatch")
        require(model == (expected_status == "sat"), f"{name}: DP/truth-table disagreement")

    final_values = expected_field_values(
        blocks,
        labels,
        layers,
        parents,
        expected_status,
        selected,
        assignment,
        initial=False,
    )
    initial_values = expected_field_values(
        blocks,
        labels,
        layers,
        parents,
        "running",
        None,
        None,
        initial=True,
    )
    initial_raw = struct.pack(f"<{len(initial_values)}d", *initial_values)
    require(
        row.get("initial_state_sha256") == hashlib.sha256(initial_raw).hexdigest(),
        f"{name}: initial state digest mismatch",
    )
    verify_descriptor(row, final_values, profile_sha256)
    require(
        certificate.get("state_sha256") == row.get("state_sha256")
        and row.get("checkpoint_roundtrip_exact") is True
        and row.get("deterministic_replay_exact") is True,
        f"{name}: persistence or replay mismatch",
    )
    return {
        "name": name,
        "blocks": blocks,
        "status": expected_status,
        "label_xor": sum(labels) & 1,
        "transitions": pairs,
        "candidate_checks": 8 * blocks,
        "field_bytes": 96 + 84 * blocks,
        "scaling_kind": row.get("scaling_kind"),
        "certificate_bytes": len(canonical(certificate)),
    }


def aggregate(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "sat": sum(row["status"] == "sat" for row in rows),
        "unsat": sum(row["status"] == "unsat" for row in rows),
        "parity_inconsistent": sum(row["label_xor"] == 1 for row in rows),
        "parity_consistent_unsat": sum(
            row["label_xor"] == 0 and row["status"] == "unsat"
            for row in rows
        ),
        "maximum_transitions": max((row["transitions"] for row in rows), default=0),
        "maximum_candidate_checks": max((row["candidate_checks"] for row in rows), default=0),
        "maximum_field_bytes": max((row["field_bytes"] for row in rows), default=0),
    }


def verify_receipt(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict) and value.get("schema") == RECEIPT_SCHEMA, "receipt schema mismatch")
    receipt = cast(dict[str, Any], value)
    contract_value = receipt.get("field_contract")
    require(isinstance(contract_value, dict), "field contract missing")
    contract = cast(dict[str, Any], contract_value)
    require(
        contract.get("persistent_adaptive_side_tables") == 0
        and contract.get("family_labels_used_after_initialization") == 0
        and contract.get("host_search_hints") == 0
        and contract.get("model_calls") == 0,
        "field ownership contract mismatch",
    )
    cases_value = receipt.get("cases")
    require(isinstance(cases_value, list) and all(isinstance(row, dict) for row in cases_value), "receipt cases malformed")
    cases = cast(list[dict[str, Any]], cases_value)
    expected_names = [
        f"exhaustive_b{blocks}_mask_{mask:0{(3 * blocks // 2 + 3) // 4}x}"
        for blocks in (4, 6)
        for mask in range(1 << (3 * blocks // 2))
    ]
    expected_names.extend(
        f"scaling_b{blocks}_{kind}"
        for blocks in (8, 12, 24, 48, 96, 192, 384, 768)
        for kind in ("zero", "one_odd", "dense_odd")
    )
    require([row.get("name") for row in cases] == expected_names, "scenario corpus mismatch")
    audited = [verify_case(row) for row in cases]

    expected_summary = aggregate(audited)
    expected_summary["all_certificates_independently_checkable"] = True
    require(receipt.get("summary") == expected_summary, "receipt summary mismatch")
    expected_exhaustive = {
        f"b{blocks}": aggregate(
            [row for row in audited if cast(str, row["name"]).startswith(f"exhaustive_b{blocks}_")]
        )
        for blocks in (4, 6)
    }
    require(receipt.get("exhaustive") == expected_exhaustive, "exhaustive aggregate mismatch")
    expected_scaling = [
        {
            "name": row["name"],
            "blocks": row["blocks"],
            "labels": 3 * row["blocks"] // 2,
            "label_xor": row["label_xor"],
            "status": row["status"],
            "transitions": row["transitions"],
            "candidate_checks": row["candidate_checks"],
            "field_bytes": row["field_bytes"],
            "certificate_bytes": row["certificate_bytes"],
        }
        for row in audited
        if row["scaling_kind"] is not None
    ]
    require(receipt.get("scaling") == expected_scaling, "scaling table mismatch")
    require(
        receipt.get("theorem")
        == {
            "class": "canonical cycle-plus-adjacent-pair matched exact-one CNFs with arbitrary edge labels",
            "total_decision": True,
            "transitions": "b/2",
            "candidate_checks": "8b",
            "field_values": "12 + 21b/2",
            "field_bytes": "96 + 84b",
            "dynamic_program_work": "O(b)",
            "end_to_end_controller_work": "O(b log b) including CNF canonicalization",
            "public_step_replay_work": "O(b^2)",
            "state_space": "O(b)",
            "certificate_size": "O(b)",
            "p_equals_np": "not established",
        },
        "theorem statement mismatch",
    )
    return expected_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", nargs="?", type=Path, default=DEFAULT_RECEIPT)
    args = parser.parse_args()
    result = verify_receipt(args.receipt)
    print(json.dumps(result, sort_keys=True))
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
