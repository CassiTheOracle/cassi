#!/usr/bin/env python
"""Exercise total field-owned decisions on the canonical mixed CNF class."""

from __future__ import annotations

import argparse
import itertools
import json
from pathlib import Path
from typing import Any, Sequence

from cassi_mixed_exact_one_field import (
    CanonicalMixedDecisionField,
    CanonicalMixedDecisionProfile,
    canonical_formula_from_labels,
)

SCHEMA = "cassifi.canonical-mixed-decision-probe.v1"
OUTPUT = Path("_diag/mixed_exact_one_decision.json")


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    )


def truth_table_model(
    formula: Sequence[Sequence[int]],
    variables: int,
) -> bool:
    return any(
        satisfies(formula, assignment)
        for assignment in itertools.product((0, 1), repeat=variables)
    )


def labels_for_mask(blocks: int, mask: int) -> tuple[int, ...]:
    return tuple(
        (mask >> index) & 1
        for index in range(3 * blocks // 2)
    )


def dense_odd_labels(blocks: int) -> tuple[int, ...]:
    count = 3 * blocks // 2
    return tuple(
        1 if count % 2 or index < count - 1 else 0
        for index in range(count)
    )


def run_case(
    name: str,
    blocks: int,
    labels: Sequence[int],
    *,
    truth_table: bool,
    scaling_kind: str | None = None,
) -> dict[str, Any]:
    formula = canonical_formula_from_labels(blocks, labels)
    profile = CanonicalMixedDecisionProfile(blocks)
    field = CanonicalMixedDecisionField(profile)
    initial = field.initial(formula, variable_count=3 * blocks)
    initial_bytes = initial.field.tobytes()
    final, certificate = field.solve(initial)
    if initial.field.tobytes() != initial_bytes:
        raise AssertionError(f"{name}: solve mutated its input state")
    replay_final, replay_certificate = field.solve(
        field.initial(formula, variable_count=3 * blocks)
    )
    if (
        field.state_sha256(final) != field.state_sha256(replay_final)
        or certificate["certificate_sha256"]
        != replay_certificate["certificate_sha256"]
    ):
        raise AssertionError(f"{name}: deterministic replay mismatch")
    restored_field, restored = CanonicalMixedDecisionField.from_descriptor(
        field.descriptor(final)
    )
    if restored_field.state_sha256(restored) != field.state_sha256(final):
        raise AssertionError(f"{name}: checkpoint roundtrip mismatch")
    assignment = certificate["assignment"]
    if certificate["status"] == "sat":
        if not isinstance(assignment, list) or not satisfies(formula, assignment):
            raise AssertionError(f"{name}: invalid SAT certificate")
    elif assignment is not None:
        raise AssertionError(f"{name}: UNSAT certificate contains an assignment")
    model = truth_table_model(formula, 3 * blocks) if truth_table else None
    if model is not None and model != (certificate["status"] == "sat"):
        raise AssertionError(f"{name}: truth-table decision mismatch")
    return {
        "name": name,
        "blocks": blocks,
        "variables": 3 * blocks,
        "labels": list(labels),
        "label_xor": sum(labels) & 1,
        "formula": formula,
        "problem_sha256": certificate["problem_sha256"],
        "status": certificate["status"],
        "truth_table_model": model,
        "scaling_kind": scaling_kind,
        "initial_state_sha256": field.state_sha256(initial),
        "state_sha256": field.state_sha256(final),
        "field_bytes": final.nbytes,
        "checkpoint_roundtrip_exact": True,
        "deterministic_replay_exact": True,
        "descriptor": field.descriptor(final),
        "certificate": certificate,
    }


def aggregate(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cases": len(rows),
        "sat": sum(row["status"] == "sat" for row in rows),
        "unsat": sum(row["status"] == "unsat" for row in rows),
        "parity_inconsistent": sum(row["label_xor"] == 1 for row in rows),
        "parity_consistent_unsat": sum(
            row["label_xor"] == 0 and row["status"] == "unsat"
            for row in rows
        ),
        "maximum_transitions": max(
            (row["certificate"]["transitions"] for row in rows),
            default=0,
        ),
        "maximum_candidate_checks": max(
            (row["certificate"]["candidate_checks"] for row in rows),
            default=0,
        ),
        "maximum_field_bytes": max(
            (row["field_bytes"] for row in rows),
            default=0,
        ),
    }


def run(output: Path = OUTPUT) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for blocks in (4, 6):
        count = 1 << (3 * blocks // 2)
        for mask in range(count):
            rows.append(
                run_case(
                    f"exhaustive_b{blocks}_mask_{mask:0{(3 * blocks // 2 + 3) // 4}x}",
                    blocks,
                    labels_for_mask(blocks, mask),
                    truth_table=blocks == 4,
                )
            )
        print(f"exhaustive b={blocks}: {count}/{count}")
    for blocks in (8, 12, 24, 48, 96, 192, 384, 768):
        patterns = (
            ("zero", (0,) * (3 * blocks // 2)),
            ("one_odd", (1,) + (0,) * (3 * blocks // 2 - 1)),
            ("dense_odd", dense_odd_labels(blocks)),
        )
        for kind, labels in patterns:
            rows.append(
                run_case(
                    f"scaling_b{blocks}_{kind}",
                    blocks,
                    labels,
                    truth_table=False,
                    scaling_kind=kind,
                )
            )
        print(f"scaling b={blocks}: 3/3")

    exhaustive = {
        f"b{blocks}": aggregate(
            [row for row in rows if row["name"].startswith(f"exhaustive_b{blocks}_")]
        )
        for blocks in (4, 6)
    }
    scaling = [
        {
            "name": row["name"],
            "blocks": row["blocks"],
            "labels": len(row["labels"]),
            "label_xor": row["label_xor"],
            "status": row["status"],
            "transitions": row["certificate"]["transitions"],
            "candidate_checks": row["certificate"]["candidate_checks"],
            "field_bytes": row["field_bytes"],
            "certificate_bytes": len(canonical(row["certificate"])),
        }
        for row in rows
        if row["scaling_kind"] is not None
    ]
    summary = aggregate(rows)
    summary["all_certificates_independently_checkable"] = True
    receipt = {
        "schema": SCHEMA,
        "field_contract": {
            "tensor": "one immutable float64 [1, 12 + 21b/2, 1] field",
            "owned_state": "canonical edge labels, DP frontiers, predecessors, assignment, status, and work counters",
            "persistent_adaptive_side_tables": 0,
            "family_labels_used_after_initialization": 0,
            "host_search_hints": 0,
            "model_calls": 0,
            "transition": "one adjacent block pair and exactly sixteen candidate checks",
        },
        "theorem": {
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
        "summary": summary,
        "exhaustive": exhaustive,
        "scaling": scaling,
        "cases": rows,
        "assessment": {
            "result": "total polynomial decision and certificates for the canonical bounded-pathwidth mixed class",
            "parity_only_incomplete": True,
            "broader_connected_topologies": "not established",
            "unrestricted_sat": "not established",
            "p_equals_np": "not established",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    print(f"Wrote {output}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    run(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
