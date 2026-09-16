#!/usr/bin/env python
"""Measure the smallest exact SAT search implemented by CassiFI field state.

The temporal field learns a complete lexicographic assignment-enumeration policy.
During use, the field chooses each candidate assignment; a fixed CNF verifier
returns only ``sat`` or ``miss``.  The scenario then measures where the search
resource lives and separately audits CassiFI's explicit structural-mode budget.

This is a bounded computational experiment, not evidence that P equals NP.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from cassi_field_atlas import FieldAtlas, FieldIntelligenceError, RelationChart
from cassi_temporal_field import TemporalField, TemporalFieldError

Literal = int
Clause = tuple[Literal, ...]
Formula = tuple[Clause, ...]

MAX_TEMPORAL_VARIABLES = 6
MAX_STATES = 128
OBSERVATIONS = ("miss", "sat")
SEED = 0xCA551F1


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    family: str
    n: int
    clauses: Formula
    expected_sat: bool


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def bits_of(index: int, n: int) -> tuple[bool, ...]:
    return tuple(bool((index >> shift) & 1) for shift in range(n - 1, -1, -1))


def action_of(index: int, n: int) -> str:
    return "test-" + format(index, f"0{n}b")


def index_of(action: str) -> int:
    prefix, bits = action.split("-", 1)
    if prefix != "test" or not bits or set(bits) - {"0", "1"}:
        raise ValueError("invalid assignment action")
    return int(bits, 2)


def satisfies(clauses: Formula, assignment: Sequence[bool]) -> bool:
    return all(
        any(assignment[abs(literal) - 1] == (literal > 0) for literal in clause)
        for clause in clauses
    )


def certificate(clauses: Formula, assignment: Sequence[bool]) -> dict[str, Any]:
    clause_values = [
        [assignment[abs(literal) - 1] == (literal > 0) for literal in clause]
        for clause in clauses
    ]
    return {
        "assignment": [int(value) for value in assignment],
        "clause_values": clause_values,
        "verified": all(any(row) for row in clause_values),
    }


def unique_assignment_formula(assignment: Sequence[bool]) -> Formula:
    return tuple((index if value else -index,) for index, value in enumerate(assignment, 1))


def planted_3sat(n: int, *, seed: int, clause_count: int | None = None) -> Formula:
    rng = random.Random(seed)
    target = bits_of(rng.randrange(1 << n), n)
    count = clause_count if clause_count is not None else max(4, math.ceil(4.25 * n))
    clauses: list[Clause] = []
    while len(clauses) < count:
        variables = tuple(sorted(rng.sample(range(1, n + 1), min(3, n))))
        signs = [bool(rng.getrandbits(1)) for _ in variables]
        if not any(target[variable - 1] == sign for variable, sign in zip(variables, signs)):
            forced = rng.randrange(len(signs))
            signs[forced] = target[variables[forced] - 1]
        clauses.append(
            tuple(variable if sign else -variable for variable, sign in zip(variables, signs))
        )
    assert satisfies(tuple(clauses), target)
    return tuple(clauses)


def pigeonhole_3_into_2() -> Formula:
    # Variable p*2+h+1 means pigeon p occupies hole h.
    clauses: list[Clause] = []
    for pigeon in range(3):
        clauses.append((pigeon * 2 + 1, pigeon * 2 + 2))
    for left in range(3):
        for right in range(left + 1, 3):
            for hole in range(2):
                clauses.append((-(left * 2 + hole + 1), -(right * 2 + hole + 1)))
    return tuple(clauses)


def permute_formula(clauses: Formula, permutation: Sequence[int]) -> Formula:
    return tuple(
        tuple(
            permutation[abs(literal) - 1] if literal > 0 else -permutation[abs(literal) - 1]
            for literal in clause
        )
        for clause in clauses
    )


def first_solution(clauses: Formula, n: int) -> int | None:
    return next((index for index in range(1 << n) if satisfies(clauses, bits_of(index, n))), None)


def exhaustive_episode(n: int) -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "action": action_of(index, n),
            "observation": "sat" if index == (1 << n) - 1 else "miss",
        }
        for index in range(1 << n)
    )


def build_enumerator(n: int) -> tuple[TemporalField, dict[str, Any]]:
    actions = tuple(action_of(index, n) for index in range(1 << n))
    field = TemporalField.initial(
        f"sat-enumerator-{n}",
        action_ids=actions,
        observation_ids=OBSERVATIONS,
        max_states=MAX_STATES,
        context={"semantics": "lexicographic-complete-assignment-enumeration", "variables": n},
    )
    episode = exhaustive_episode(n)
    learned, learning = field.learn(
        (episode,),
        source_revision_ids=(digest(f"complete-enumerator:{n}:v1"),),
    )
    skilled, skill = learned.condense_skill(
        "find-sat",
        goal_observations=("sat",),
    )
    if not skill["start_state_supported"]:
        raise AssertionError(f"enumeration skill did not form for n={n}")
    restored = TemporalField.from_dict(json.loads(json.dumps(skilled.as_dict())))
    if restored.state_sha256 != skilled.state_sha256 or restored.field.tobytes() != skilled.field.tobytes():
        raise AssertionError("temporal field round-trip changed learned state")
    ablated = TemporalField.initial(
        skilled.memory_id,
        action_ids=actions,
        observation_ids=OBSERVATIONS,
        max_states=MAX_STATES,
        context=skilled.context,
    )
    ablated, ablated_skill = ablated.condense_skill("find-sat", goal_observations=("sat",))
    if ablated.skill_action("find-sat")["status"] != "unresolved":
        raise AssertionError("unlearned ablation unexpectedly retained the SAT policy")
    return restored, {
        "learning": dict(learning),
        "skill": dict(skill),
        "ablated_skill": dict(ablated_skill),
        "roundtrip_exact": True,
        "field_causal_ablation": "policy-unresolved-with-learned-planes-removed",
    }


def run_case(field: TemporalField, case: Case) -> dict[str, Any]:
    working = field.reset()
    attempted: list[int] = []
    final_status = "unresolved"
    found: tuple[bool, ...] | None = None
    goal_transition_supported: bool | None = None
    for _ in range(1 << case.n):
        proposal = working.skill_action("find-sat")
        if proposal["status"] != "proposed" or proposal["action"] is None:
            final_status = str(proposal["status"])
            break
        candidate_index = index_of(str(proposal["action"]))
        candidate = bits_of(candidate_index, case.n)
        attempted.append(candidate_index)
        observation = "sat" if satisfies(case.clauses, candidate) else "miss"
        working, consumed = working.consume(str(proposal["action"]), observation)
        if observation == "sat":
            found = candidate
            goal_transition_supported = not bool(consumed["unknown_successor"])
            final_status = str(working.skill_action("find-sat")["status"])
            break
    if found is None and len(attempted) == (1 << case.n):
        # The all-ones miss is intentionally absent from the successful source
        # episode. The field must become unresolved rather than emit UNSAT.
        final_status = str(working.skill_action("find-sat")["status"])
    cert = None if found is None else certificate(case.clauses, found)
    actual_sat = first_solution(case.clauses, case.n) is not None
    if actual_sat != case.expected_sat:
        raise AssertionError(f"bad expected SAT label for {case.name}")
    if found is not None and (cert is None or not cert["verified"]):
        raise AssertionError(f"invalid field-selected certificate for {case.name}")
    if case.expected_sat and found is None:
        raise AssertionError(f"field failed promised-SAT case {case.name}")
    if not case.expected_sat and found is not None:
        raise AssertionError(f"field produced a false SAT certificate for {case.name}")
    return {
        "goal_transition_supported": goal_transition_supported,
        "name": case.name,
        "family": case.family,
        "n": case.n,
        "m": len(case.clauses),
        "clauses": [list(clause) for clause in case.clauses],
        "expected_sat": case.expected_sat,
        "first_solution_index": first_solution(case.clauses, case.n),
        "field_status": final_status,
        "attempted_assignments": len(attempted),
        "attempted_indices": attempted,
        "certificate": cert,
    }


def cases_for(n: int) -> tuple[Case, ...]:
    last = (1 << n) - 1
    positions = tuple(dict.fromkeys((0, (1 << n) // 2, last)))
    rows = [
        Case(
            name=f"unique-{n}-{position}",
            family="unique-unit",
            n=n,
            clauses=unique_assignment_formula(bits_of(position, n)),
            expected_sat=True,
        )
        for position in positions
    ]
    planted = planted_3sat(n, seed=SEED + n)
    rows.append(Case(f"planted3-{n}", "planted-3sat", n, planted, True))
    if n == 6:
        unsat = pigeonhole_3_into_2()
        rows.append(Case("php-3-2", "pigeonhole-unsat", n, unsat, False))
        permutation = (6, 2, 5, 1, 4, 3)
        rows.append(
            Case(
                "planted3-6-permuted",
                "representation-permutation",
                n,
                permute_formula(planted, permutation),
                True,
            )
        )
    return tuple(rows)


def branch_budget_audit() -> dict[str, Any]:
    atlas = FieldAtlas()
    counts: list[dict[str, int]] = []
    rejection: dict[str, Any] | None = None
    for n in range(1, 8):
        charts = tuple(
            RelationChart.empty(
                chart_id=f"binary-{group}-{mode}",
                scope=("x",),
                mode_group=f"variable-{group}",
                mode=str(mode),
            )
            for group in range(n)
            for mode in (0, 1)
        )
        try:
            branches = atlas._branches(charts, 64)
            counts.append({"binary_mode_groups": n, "branches": len(branches)})
        except FieldIntelligenceError as exc:
            rejection = {
                "binary_mode_groups": n,
                "code": exc.code,
                "message": str(exc),
                "details": dict(exc.details),
            }
            break
    if counts[-1] != {"binary_mode_groups": 6, "branches": 64}:
        raise AssertionError("unexpected structural branch scaling")
    if rejection is None or rejection["code"] != "BRANCH_BUDGET" or rejection["details"] != {"required": 128, "limit": 64}:
        raise AssertionError("structural branch budget did not reject 2^7 alternatives")
    return {"counts": counts, "first_rejection": rejection}


def temporal_capacity_rejection() -> dict[str, Any]:
    try:
        TemporalField.initial(
            "sat-enumerator-7",
            action_ids=tuple(action_of(index, 7) for index in range(1 << 7)),
            observation_ids=OBSERVATIONS,
            max_states=MAX_STATES,
        )
    except TemporalFieldError as exc:
        return {"n": 7, "required_actions": 128, "limit": 64, "message": str(exc)}
    raise AssertionError("temporal field accepted an action vocabulary above its hard limit")


def run() -> dict[str, Any]:
    sizes: list[dict[str, Any]] = []
    case_results: list[dict[str, Any]] = []
    causality: list[dict[str, Any]] = []
    for n in range(2, MAX_TEMPORAL_VARIABLES + 1):
        field, field_receipt = build_enumerator(n)
        signal = field.skill_pool_signal("find-sat")
        expected = 1 << n
        if field.state_count != expected + 1 or signal["maximum_rank"] != expected:
            raise AssertionError(f"field resource accounting mismatch for n={n}")
        sizes.append(
            {
                "n": n,
                "assignments": expected,
                "action_ids": len(field.action_ids),
                "learned_states": field.state_count,
                "maximum_safe_rank": signal["maximum_rank"],
                "field_bytes": field.nbytes,
                "serialized_json_bytes": len(json.dumps(field.as_dict(), sort_keys=True).encode("utf-8")),
                "memory_sha256": field.memory_sha256,
                "state_sha256": field.state_sha256,
            }
        )
        causality.append(
            {
                "n": n,
                "roundtrip_exact": field_receipt["roundtrip_exact"],
                "field_causal_ablation": field_receipt["field_causal_ablation"],
                "formed_skill": field_receipt["skill"]["status"],
                "ablated_skill": field_receipt["ablated_skill"]["status"],
            }
        )
        case_results.extend(run_case(field, case) for case in cases_for(n))

    for previous, current in zip(sizes, sizes[1:]):
        if current["assignments"] != 2 * previous["assignments"]:
            raise AssertionError("candidate count did not double")
        if current["field_bytes"] != 2 * previous["field_bytes"]:
            raise AssertionError("temporal field storage did not expose action-vocabulary doubling")

    sat_rows = [row for row in case_results if row["expected_sat"]]
    unsat_rows = [row for row in case_results if not row["expected_sat"]]
    if not sat_rows or not all(row["certificate"]["verified"] for row in sat_rows):
        raise AssertionError("SAT certificate verification failed")
    if not unsat_rows or not all(row["field_status"] == "unresolved" for row in unsat_rows):
        raise AssertionError("UNSAT control must exhaust into unresolved")

    return {
        "schema": "cassifi.p-vs-np-field-probe.v1",
        "seed": SEED,
        "model": {
            "adaptive_owner": "TemporalField numeric planes and derived safe-policy ranks",
            "fixed_world_operation": "evaluate one complete assignment against the supplied CNF",
            "search_order": "field-selected lexicographic assignment actions",
            "claim_boundary": "promised-SAT certificate search only; no UNSAT certificate",
        },
        "temporal_scaling": sizes,
        "field_causality": causality,
        "cases": case_results,
        "temporal_capacity_rejection": temporal_capacity_rejection(),
        "structural_branch_budget": branch_budget_audit(),
        "verdicts": {
            "C1_field_owned_policy": "PASS",
            "C2_bounded_promised_sat_search": "PASS",
            "C3_unsat_decision": "CONTRADICTS",
            "C4_polynomial_representation": "CONTRADICTS",
            "C5_polynomial_structural_branching": "CONTRADICTS",
            "overall_p_equals_np_route": "REJECT",
            "bounded_field_computation": "SUPPORTS",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("_diag/p_vs_np_cassifi_probe.json"))
    args = parser.parse_args()
    receipt = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"CassiFI SAT field probe: {len(receipt['cases'])} cases")
    for row in receipt["temporal_scaling"]:
        print(
            f"n={row['n']} assignments={row['assignments']} states={row['learned_states']} "
            f"rank={row['maximum_safe_rank']} field_bytes={row['field_bytes']}"
        )
    print(json.dumps(receipt["verdicts"], sort_keys=True))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
