#!/usr/bin/env python3
"""Exercise and falsify the finite proof-oriented cubic reduction algorithm.

The receipt contains frozen controls, connected growing-nullity constructions,
and a deterministic legal-cubic adversarial corpus.  SAT/UNSAT outputs are
checked by complete Boolean evaluation at these bounded orders.  Unresolved
outputs are retained and minimized only within exact cubic connected-component
deletion; they are counterexamples to the exported rule set, not to P=NP.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import random
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Sequence

import cassi_cubic_reduction as reduction
import cubic_kernel_decision as kernel
from run_cubic_kernel_analysis import (
    ALL_BASES_TERNARY_SAT,
    ALL_BASES_TERNARY_UNSAT,
    FULL_SUPPORT_ALPHABET_UNSAT,
    GREEDY_EXCHANGE_TRAP_SAT,
    SINGULAR_ALPHABET_UNSAT,
    SUPPORT_THREE_SAT,
    SUPPORT_THREE_UNSAT,
    switched_component_family,
)

SCHEMA = "cassifi.cubic-reduction-discovery.v1"
OUTPUT = Path("_diag/cubic_reduction_discovery.json")
RANDOM_SEED = 0xCA551F1
RANDOM_SIZES = (9, 12, 15)
RANDOM_DRAWS_PER_SIZE = 8

Formula = tuple[tuple[int, int, int], ...]
_WORK_UNIT_FIELDS = (
    "fraction_updates",
    "projection_states_checked",
    "projection_vector_entries_checked",
    "variable_guards_checked",
    "pair_guards_checked",
    "candidate_assignments",
    "sparse_witness_candidates",
    "literal_probe_trials",
    "propagation_rows_checked",
    "propagation_bound_checks",
    "propagation_assignments",
    "row_bound_combinations",
    "row_bound_coefficient_updates",
    "equation_evaluations",
    "separator_candidates_checked",
    "separator_components_checked",
    "separator_relations_enumerated",
    "substitutions",
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = kernel.canonical_cubic_formula(formula)
    return digest([list(clause) for clause in canonical])


def direct_sum(left: Sequence[Sequence[int]], right: Sequence[Sequence[int]]) -> Formula:
    canonical_left = kernel.canonical_cubic_formula(left)
    canonical_right = kernel.canonical_cubic_formula(right)
    offset = len(canonical_left)
    return kernel.canonical_cubic_formula(
        (*canonical_left, *(tuple(value + offset for value in clause) for clause in canonical_right))
    )


def brute_force_truth(formula: Sequence[Sequence[int]]) -> tuple[str, tuple[int, ...] | None, int]:
    canonical = kernel.canonical_cubic_formula(formula)
    checked = 0
    for assignment in itertools.product((0, 1), repeat=len(canonical)):
        checked += 1
        if all(sum(assignment[value - 1] for value in clause) == 1 for clause in canonical):
            return "sat", assignment, checked
    return "unsat", None, checked


def _proof_nodes(proof: dict[str, Any]) -> Iterable[dict[str, Any]]:
    yield proof
    child = proof.get("child")
    if isinstance(child, dict):
        yield from _proof_nodes(child)
    for component in proof.get("components", ()):
        yield from _proof_nodes(component["proof"])


def residual_profile(result: dict[str, Any]) -> dict[str, Any]:
    unresolved = [
        node for node in _proof_nodes(result["proof"]) if node["kind"] == "unresolved_residual"
    ]
    return {
        "count": len(unresolved),
        "variable_counts": sorted(node["system"]["variable_count"] for node in unresolved),
        "maximum_variables": max(
            (node["system"]["variable_count"] for node in unresolved),
            default=0,
        ),
        "system_sha256": sorted(node["system_sha256"] for node in unresolved),
    }


def hardness(result: dict[str, Any]) -> tuple[int, int, int, int, int]:
    residual = residual_profile(result)
    ledger = result["resource_ledger"]
    return (
        int(result["status"] == "unresolved"),
        residual["maximum_variables"],
        ledger["pair_guards_checked"],
        ledger["projection_states_checked"],
        result["progress"]["event_count"],
    )


def evaluate_formula(
    name: str,
    group: str,
    formula: Sequence[Sequence[int]],
    *,
    profile: reduction.ReductionProfile,
) -> dict[str, Any]:
    canonical = kernel.canonical_cubic_formula(formula)
    result = reduction.solve_cubic_reduction(canonical, profile=profile)
    truth_status, truth_witness, assignments_checked = brute_force_truth(canonical)
    if result["status"] in ("sat", "unsat") and result["status"] != truth_status:
        raise AssertionError(f"{name}: reducer truth claim disagrees with exhaustive truth")
    if result["status"] == "sat":
        assignment = result["assignment"]
        if assignment is None or not all(
            sum(assignment[value - 1] for value in clause) == 1 for clause in canonical
        ):
            raise AssertionError(f"{name}: reducer SAT witness failed")
    if not result["progress"]["strictly_descending"] or result["progress"]["final"] != 0:
        raise AssertionError(f"{name}: progress certificate failed")
    if not result["representation"]["bound_respected"]:
        raise AssertionError(f"{name}: coefficient-growth bound failed")
    if result["field_preference"]["persistence"] != "invocation_local_only":
        raise AssertionError(f"{name}: adaptive state escaped the invocation")
    score = hardness(result)
    return {
        "name": name,
        "group": group,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": formula_digest(canonical),
        "variables": len(canonical),
        "connected": kernel.incidence_connected(canonical),
        "truth": {
            "status": truth_status,
            "first_witness": None if truth_witness is None else list(truth_witness),
            "assignments_checked": assignments_checked,
        },
        "reduction": result,
        "residual": residual_profile(result),
        "hardness": {
            "tuple": list(score),
            "semantics": [
                "unresolved_indicator",
                "maximum_unresolved_variables",
                "pair_guards_checked",
                "projection_states_checked",
                "progress_events",
            ],
        },
    }


def _random_simple_connected_cubic_formula(
    rng: random.Random,
    size: int,
) -> tuple[Formula, int]:
    if size < 4:
        raise ValueError("a simple cubic formula needs at least four variables")
    labels = list(range(1, size + 1))
    attempts = 0
    while attempts < 1_000_000:
        attempts += 1
        permutations: list[list[int]] = []
        for _ in range(3):
            candidate = labels.copy()
            rng.shuffle(candidate)
            permutations.append(candidate)
        rows = tuple(
            sorted(
                tuple(sorted(permutations[layer][row] for layer in range(3)))
                for row in range(size)
            )
        )
        if any(len(set(row)) != 3 for row in rows) or len(set(rows)) != size:
            continue
        canonical = kernel.canonical_cubic_formula(rows)
        if not kernel.incidence_connected(canonical):
            continue
        return canonical, attempts
    raise RuntimeError("deterministic cubic generator exceeded its attempt bound")


def random_corpus(
    *,
    sizes: Sequence[int],
    draws_per_size: int,
    seed: int,
) -> tuple[list[tuple[str, str, Formula]], dict[str, Any]]:
    if isinstance(draws_per_size, bool) or draws_per_size < 1:
        raise ValueError("draws_per_size must be positive")
    rng = random.Random(seed)
    cases: list[tuple[str, str, Formula]] = []
    seen: set[str] = set()
    attempts = 0
    draw_stream = hashlib.sha256()
    for size in sizes:
        accepted = 0
        draw_index = 0
        while accepted < draws_per_size:
            formula, consumed = _random_simple_connected_cubic_formula(rng, int(size))
            attempts += consumed
            formula_sha256 = formula_digest(formula)
            draw_stream.update(
                f"{size}:{draw_index}:{consumed}:{formula_sha256}\n".encode("ascii")
            )
            draw_index += 1
            if formula_sha256 in seen:
                continue
            seen.add(formula_sha256)
            cases.append((f"random-n{size}-{accepted:02d}", "adversarial_random", formula))
            accepted += 1
    return cases, {
        "kind": "seeded_three_permutation_simple_connected_cubic",
        "seed": seed,
        "sizes": list(sizes),
        "draws_per_size": draws_per_size,
        "accepted_formulas": len(cases),
        "configuration_attempts": attempts,
        "draw_stream_sha256": draw_stream.hexdigest(),
        "draw_stream_record": "size:draw_index:configuration_attempts:formula_sha256\\n",
    }


def cubic_components(formula: Sequence[Sequence[int]]) -> tuple[Formula, ...]:
    canonical = kernel.canonical_cubic_formula(formula)
    size = len(canonical)
    variable_rows = [set() for _ in range(size)]
    for row_index, clause in enumerate(canonical):
        for variable in clause:
            variable_rows[variable - 1].add(row_index)
    seen_variables: set[int] = set()
    components: list[Formula] = []
    for start in range(size):
        if start in seen_variables:
            continue
        variables: set[int] = set()
        rows: set[int] = set()
        stack = [start]
        while stack:
            variable = stack.pop()
            if variable in variables:
                continue
            variables.add(variable)
            seen_variables.add(variable)
            for row in variable_rows[variable]:
                if row in rows:
                    continue
                rows.add(row)
                stack.extend(item - 1 for item in canonical[row] if item - 1 not in variables)
        ordered_variables = tuple(sorted(variables))
        if len(rows) != len(ordered_variables):
            raise AssertionError("cubic incidence component is not balanced")
        relabel = {old + 1: new + 1 for new, old in enumerate(ordered_variables)}
        child = kernel.canonical_cubic_formula(
            tuple(
                tuple(relabel[value] for value in canonical[row])
                for row in sorted(rows)
            )
        )
        components.append(child)
    return tuple(components)


def _two_switch_candidates(
    formula: Sequence[Sequence[int]],
) -> tuple[tuple[Formula, dict[str, int]], ...]:
    """Enumerate each legal degree-preserving two-switch result once."""

    canonical = kernel.canonical_cubic_formula(formula)
    candidates: dict[str, tuple[Formula, tuple[int, int, int, int]]] = {}
    for left_index, right_index in itertools.combinations(range(len(canonical)), 2):
        left_clause = canonical[left_index]
        right_clause = canonical[right_index]
        for left_variable in left_clause:
            if left_variable in right_clause:
                continue
            for right_variable in right_clause:
                if right_variable in left_clause:
                    continue
                rows = [list(clause) for clause in canonical]
                rows[left_index][rows[left_index].index(left_variable)] = right_variable
                rows[right_index][rows[right_index].index(right_variable)] = left_variable
                try:
                    candidate = kernel.canonical_cubic_formula(rows)
                except kernel.CubicKernelDecisionError:
                    continue
                if candidate == canonical:
                    continue
                candidate_sha256 = formula_digest(candidate)
                operation = (
                    left_index + 1,
                    right_index + 1,
                    left_variable,
                    right_variable,
                )
                previous = candidates.get(candidate_sha256)
                if previous is None or operation < previous[1]:
                    candidates[candidate_sha256] = (candidate, operation)
    return tuple(
        (
            candidates[sha256][0],
            {
                "left_clause": candidates[sha256][1][0],
                "right_clause": candidates[sha256][1][1],
                "left_variable": candidates[sha256][1][2],
                "right_variable": candidates[sha256][1][3],
            },
        )
        for sha256 in sorted(candidates)
    )


def _evaluate_unswitch_scan(
    formula: Sequence[Sequence[int]],
    *,
    profile: reduction.ReductionProfile,
) -> dict[str, Any]:
    canonical = kernel.canonical_cubic_formula(formula)
    candidates = _two_switch_candidates(canonical)
    candidate_identity = [
        {
            "formula_sha256": formula_digest(candidate),
            "operation": operation,
        }
        for candidate, operation in candidates
    ]
    disconnecting: list[dict[str, Any]] = []
    for candidate, operation in candidates:
        if kernel.incidence_connected(candidate):
            continue
        components = cubic_components(candidate)
        component_rows = []
        for component in components:
            result = reduction.solve_cubic_reduction(component, profile=profile)
            component_rows.append(
                {
                    "formula": [list(clause) for clause in component],
                    "formula_sha256": formula_digest(component),
                    "variables": len(component),
                    "connected": kernel.incidence_connected(component),
                    "reduction": result,
                }
            )
        disconnecting.append(
            {
                "operation": operation,
                "formula": [list(clause) for clause in candidate],
                "formula_sha256": formula_digest(candidate),
                "components": component_rows,
            }
        )
    return {
        "source_formula_sha256": formula_digest(canonical),
        "source_variables": len(canonical),
        "candidate_count": len(candidates),
        "candidate_stream_sha256": digest(candidate_identity),
        "disconnecting_candidate_count": len(disconnecting),
        "disconnecting_candidates": disconnecting,
    }


def _unresolved_scan_targets(
    scan: dict[str, Any],
) -> list[tuple[Formula, dict[str, Any], dict[str, Any]]]:
    targets = []
    for candidate in scan["disconnecting_candidates"]:
        for component in candidate["components"]:
            if component["reduction"]["status"] == "unresolved":
                targets.append(
                    (
                        kernel.canonical_cubic_formula(component["formula"]),
                        component["reduction"],
                        candidate,
                    )
                )
    return targets


def minimize_connected_counterexample(
    formula: Sequence[Sequence[int]],
    *,
    profile: reduction.ReductionProfile,
) -> dict[str, Any]:
    """Shrink a connected unresolved formula by exhaustive inverse two-switches."""

    current = kernel.canonical_cubic_formula(formula)
    if not kernel.incidence_connected(current):
        raise ValueError("connected counterexample minimization requires a connected formula")
    source_sha256 = formula_digest(current)
    source_result = reduction.solve_cubic_reduction(current, profile=profile)
    if source_result["status"] != "unresolved":
        raise ValueError("counterexample minimization requires an unresolved formula")
    current_result = source_result
    steps: list[dict[str, Any]] = []
    while True:
        scan = _evaluate_unswitch_scan(current, profile=profile)
        targets = _unresolved_scan_targets(scan)
        if not targets:
            terminal_scan = scan
            break
        target, target_result, candidate = min(
            targets,
            key=lambda row: (
                len(row[0]),
                formula_digest(row[0]),
                row[2]["formula_sha256"],
            ),
        )
        if len(target) >= len(current) or not kernel.incidence_connected(target):
            raise AssertionError("unswitch minimizer did not make connected size progress")
        steps.append(
            {
                **scan,
                "selected_candidate_formula_sha256": candidate["formula_sha256"],
                "selected_target_formula_sha256": formula_digest(target),
            }
        )
        current = target
        current_result = target_result
    return {
        "method": "exhaustive_single_two_switch_disconnect_and_component_selection",
        "source_formula_sha256": source_sha256,
        "source_variables": len(kernel.canonical_cubic_formula(formula)),
        "source_connected": True,
        "source_reduction": source_result,
        "steps": steps,
        "terminal_scan": terminal_scan,
        "formula": [list(clause) for clause in current],
        "formula_sha256": formula_digest(current),
        "variables": len(current),
        "connected": kernel.incidence_connected(current),
        "status": current_result["status"],
        "reduction": current_result,
        "irreducible_under_method": True,
        "scope": (
            "minimal only under one legal degree-preserving two-switch that "
            "disconnects the formula followed by selection of an unresolved "
            "connected component; not globally minimum"
        ),
    }


def connected_chain(
    blocks: Sequence[Sequence[Sequence[int]]],
    links: Sequence[tuple[int, int]],
) -> Formula:
    """Join cubic blocks by deterministic degree-preserving two-switches."""

    clauses: list[list[int]] = []
    offsets: list[tuple[int, int]] = []
    variable_offset = 0
    for block in blocks:
        canonical = kernel.canonical_cubic_formula(block)
        offsets.append((len(clauses), variable_offset))
        clauses.extend(
            [[value + variable_offset for value in clause] for clause in canonical]
        )
        variable_offset += len(canonical)
    for link_index, (left, right) in enumerate(links):
        left_row = offsets[left][0] + link_index % 3
        right_row = offsets[right][0] + link_index % 3
        left_clause, right_clause = clauses[left_row], clauses[right_row]
        left_variable = next(value for value in left_clause if value not in right_clause)
        right_variable = next(value for value in right_clause if value not in left_clause)
        left_clause[left_clause.index(left_variable)] = right_variable
        right_clause[right_clause.index(right_variable)] = left_variable
        clauses[left_row] = sorted(left_clause)
        clauses[right_row] = sorted(right_clause)
    result = kernel.canonical_cubic_formula(clauses)
    if not kernel.incidence_connected(result):
        raise AssertionError("deterministic chain is not connected")
    return result


def connected_two_lift(
    base: Sequence[Sequence[int]],
    seed: int,
) -> Formula:
    """Construct a deterministic connected cubic two-lift."""

    canonical = kernel.canonical_cubic_formula(base)
    rng = random.Random(seed)
    signs = {
        (row_index, variable): rng.randrange(2)
        for row_index, row in enumerate(canonical)
        for variable in row
    }
    lifted = kernel.canonical_cubic_formula(
        tuple(
            tuple(
                sorted(
                    2 * (variable - 1)
                    + (sheet ^ signs[row_index, variable])
                    + 1
                    for variable in row
                )
            )
            for row_index, row in enumerate(canonical)
            for sheet in range(2)
        )
    )
    if not kernel.incidence_connected(lifted):
        raise ValueError("two-lift seed does not produce a connected formula")
    return lifted
def deterministic_relabel(
    formula: Sequence[Sequence[int]],
    seed: int,
) -> Formula:
    """Apply one seeded variable permutation, then canonicalize the formula."""

    canonical = kernel.canonical_cubic_formula(formula)
    labels = list(range(1, len(canonical) + 1))
    random.Random(seed).shuffle(labels)
    return kernel.canonical_cubic_formula(
        tuple(
            tuple(labels[variable - 1] for variable in clause)
            for clause in canonical
        )
    )


def connected_two_switch_walk(
    formula: Sequence[Sequence[int]],
    *,
    seed: int,
    steps: int,
) -> tuple[Formula, dict[str, Any]]:
    """Take a deterministic walk through legal connected two-switch neighbors."""

    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("two-switch walk seed must be an integer")
    if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
        raise ValueError("two-switch walk steps must be positive")
    current = kernel.canonical_cubic_formula(formula)
    trace: list[dict[str, Any]] = []
    for step in range(steps):
        candidates = tuple(
            (candidate, operation)
            for candidate, operation in _two_switch_candidates(current)
            if kernel.incidence_connected(candidate)
        )
        if not candidates:
            raise RuntimeError("connected two-switch walk has no legal successor")
        identities = [
            {
                "formula_sha256": formula_digest(candidate),
                "operation": operation,
            }
            for candidate, operation in candidates
        ]
        selector = hashlib.sha256(
            f"{seed}:{step}:{formula_digest(current)}".encode("ascii")
        ).digest()
        selected_index = int.from_bytes(selector[:8], "big") % len(candidates)
        selected, operation = candidates[selected_index]
        trace.append(
            {
                "step": step + 1,
                "source_formula_sha256": formula_digest(current),
                "connected_candidate_count": len(candidates),
                "candidate_stream_sha256": digest(identities),
                "selected_index": selected_index,
                "operation": operation,
                "target_formula_sha256": formula_digest(selected),
            }
        )
        current = selected
    return current, {
        "seed": seed,
        "steps": steps,
        "trace": trace,
        "trace_sha256": digest(trace),
    }


def structured_corpus() -> tuple[
    list[tuple[str, str, Formula]],
    dict[str, Any],
]:
    """Build frozen connected families structurally distinct from random draws."""

    cases: list[tuple[str, str, Formula]] = []
    provenance: list[dict[str, Any]] = []

    def add(
        name: str,
        group: str,
        family: str,
        formula: Formula,
        construction: dict[str, Any],
    ) -> None:
        canonical = kernel.canonical_cubic_formula(formula)
        if not kernel.incidence_connected(canonical):
            raise AssertionError("structured held-out formula is disconnected")
        cases.append((name, group, canonical))
        provenance.append(
            {
                "name": name,
                "group": group,
                "family": family,
                "construction": construction,
                "variables": len(canonical),
                "formula_sha256": formula_digest(canonical),
            }
        )

    for steps in (1, 3, 5):
        formula, trace = connected_two_switch_walk(
            ALL_BASES_TERNARY_SAT,
            seed=17,
            steps=steps,
        )
        add(
            f"heldout-all-bases-switch-seed17-step{steps:02d}",
            "heldout_switch_walk",
            "connected_two_switch_walk",
            formula,
            {
                "base": "all-bases-ternary-sat",
                **trace,
            },
        )

    for name, base_name, base, seed in (
        (
            "heldout-support-sat-two-lift-seed0",
            "support-three-sat",
            SUPPORT_THREE_SAT,
            0,
        ),
        (
            "heldout-support-sat-two-lift-seed11",
            "support-three-sat",
            SUPPORT_THREE_SAT,
            11,
        ),
        (
            "heldout-greedy-trap-two-lift-seed1",
            "greedy-exchange-trap-sat",
            GREEDY_EXCHANGE_TRAP_SAT,
            1,
        ),
        (
            "heldout-all-bases-sat-two-lift-seed15",
            "all-bases-ternary-sat",
            ALL_BASES_TERNARY_SAT,
            15,
        ),
    ):
        add(
            name,
            "heldout_two_lift",
            "connected_two_lift",
            connected_two_lift(base, seed),
            {"base": base_name, "seed": seed},
        )

    for name, base_name, base, seed in (
        (
            "heldout-switched-k33-five-relabel-seed29",
            "switched-k33-five",
            switched_component_family(5, crown_core=False)[0],
            29,
        ),
        (
            "heldout-all-bases-unsat-relabel-seed9182",
            "all-bases-ternary-unsat",
            ALL_BASES_TERNARY_UNSAT,
            9182,
        ),
    ):
        add(
            name,
            "heldout_relabeling",
            "variable_relabeling",
            deterministic_relabel(base, seed),
            {"base": base_name, "seed": seed},
        )

    add(
        "heldout-support-greedy-connected-chain",
        "heldout_connected_chain",
        "heterogeneous_two_switch_chain",
        connected_chain(
            (SUPPORT_THREE_SAT, GREEDY_EXCHANGE_TRAP_SAT),
            ((0, 1),),
        ),
        {
            "blocks": ["support-three-sat", "greedy-exchange-trap-sat"],
            "links": [[0, 1]],
        },
    )
    add(
        "heldout-switched-k33-six",
        "heldout_growing_nullity",
        "growing_switched_family",
        switched_component_family(6, crown_core=False)[0],
        {"blocks": 6, "crown_core": False},
    )
    hashes = [row["formula_sha256"] for row in provenance]
    if len(set(hashes)) != len(hashes):
        raise AssertionError("structured held-out corpus contains a duplicate")
    return cases, {
        "kind": "frozen_structurally_held_out_connected_cubic",
        "cases": provenance,
        "accepted_formulas": len(cases),
        "family_counts": dict(
            sorted(Counter(row["family"] for row in provenance).items())
        ),
        "case_stream_sha256": digest(provenance),
    }




def fixed_cases() -> list[tuple[str, str, Formula]]:
    switched_three = switched_component_family(3, crown_core=False)[0]
    switched_four = switched_component_family(4, crown_core=False)[0]
    switched_five = switched_component_family(5, crown_core=False)[0]
    duplicate_support = direct_sum(SUPPORT_THREE_SAT, SUPPORT_THREE_SAT)
    width_three_chain = connected_chain(
        (ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    separator_sat_chain = connected_chain(
        (SUPPORT_THREE_SAT, ALL_BASES_TERNARY_SAT),
        ((0, 1),),
    )
    nullity_five_unsat = connected_chain(
        (SUPPORT_THREE_UNSAT, SUPPORT_THREE_SAT),
        ((0, 1),),
    )
    return [
        ("support-three-sat", "frozen_control", SUPPORT_THREE_SAT),
        ("support-three-unsat", "frozen_control", SUPPORT_THREE_UNSAT),
        ("all-bases-ternary-sat", "frozen_control", ALL_BASES_TERNARY_SAT),
        ("all-bases-ternary-unsat", "frozen_control", ALL_BASES_TERNARY_UNSAT),
        ("singular-alphabet-unsat", "frozen_control", SINGULAR_ALPHABET_UNSAT),
        ("full-support-alphabet-unsat", "frozen_control", FULL_SUPPORT_ALPHABET_UNSAT),
        ("greedy-exchange-trap-sat", "frozen_control", GREEDY_EXCHANGE_TRAP_SAT),
        ("duplicate-support-direct-sum", "cache_control", duplicate_support),
        ("switched-k33-three", "growing_nullity", switched_three),
        ("switched-k33-four", "growing_nullity", switched_four),
        ("switched-k33-five", "growing_nullity", switched_five),
        (
            "width-three-sat-chain-two",
            "refinement_hard_core",
            width_three_chain,
        ),
        (
            "bounded-separator-sat-chain",
            "bounded_separator_control",
            separator_sat_chain,
        ),
        (
            "nullity-five-connected-unsat",
            "nullity_five_control",
            nullity_five_unsat,
        ),
    ]
def _reduction_metrics(result: dict[str, Any]) -> dict[str, Any]:
    attempts = [
        attempt
        for node in _proof_nodes(result["proof"])
        for attempt in node.get("certificate", {}).get("attempted", ())
    ]
    ledger = result["resource_ledger"]
    return {
        "status": result["status"],
        "completed": result["status"] != "unresolved",
        "result_sha256": result["result_sha256"],
        "work_units": sum(ledger[field] for field in _WORK_UNIT_FIELDS),
        "rule_attempts": len(attempts),
        "failed_rule_attempts": sum(
            not attempt["applicable"] for attempt in attempts
        ),
        "rref_calls": ledger["rref_calls"],
        "fraction_updates": ledger["fraction_updates"],
        "projection_queries": ledger["projection_queries"],
        "projection_states_checked": ledger["projection_states_checked"],
        "literal_probe_trials": ledger["literal_probe_trials"],
        "propagation_rows_checked": ledger["propagation_rows_checked"],
        "propagation_bound_checks": ledger["propagation_bound_checks"],
        "propagation_assignments": ledger["propagation_assignments"],
        "row_bound_combinations": ledger["row_bound_combinations"],
        "separator_candidates_checked": ledger["separator_candidates_checked"],
        "proof_bytes": result["representation"]["proof_bytes"],
        "reduction": result,
    }


def schedule_ablation(
    specs: Sequence[tuple[str, str, Formula]],
    *,
    terminal_nullity: int,
    truth_by_formula: dict[str, str],
    literal_probing: bool,
) -> dict[str, Any]:
    """Compare adaptive and fixed schedules on the same held-out formulas."""

    rows: list[dict[str, Any]] = []
    descriptors = {
        mode: reduction.candidate_algorithm_descriptor(
            reduction.ReductionProfile(
                terminal_nullity=terminal_nullity,
                schedule_mode=mode,
                literal_probing=literal_probing,
            )
        )
        for mode in ("adaptive", "fixed")
    }
    for name, group, formula in specs:
        canonical = kernel.canonical_cubic_formula(formula)
        formula_sha256 = formula_digest(canonical)
        truth_status = truth_by_formula[formula_sha256]
        modes: dict[str, dict[str, Any]] = {}
        for mode in ("adaptive", "fixed"):
            result = reduction.solve_cubic_reduction(
                canonical,
                profile=reduction.ReductionProfile(
                    terminal_nullity=terminal_nullity,
                    schedule_mode=mode,
                    literal_probing=literal_probing,
                ),
            )
            if (
                result["status"] in ("sat", "unsat")
                and result["status"] != truth_status
            ):
                raise AssertionError(
                    f"{name}: {mode} ablation claim disagrees with exhaustive truth"
                )
            modes[mode] = _reduction_metrics(result)
        rows.append(
            {
                "name": name,
                "group": group,
                "formula_sha256": formula_sha256,
                "variables": len(canonical),
                "truth_status": truth_status,
                **modes,
            }
        )

    aggregate_fields = (
        "work_units",
        "rule_attempts",
        "failed_rule_attempts",
        "rref_calls",
        "fraction_updates",
        "projection_queries",
        "projection_states_checked",
        "row_bound_combinations",
        "separator_candidates_checked",
        "literal_probe_trials",
        "propagation_rows_checked",
        "propagation_bound_checks",
        "propagation_assignments",
        "proof_bytes",
    )
    aggregates: dict[str, dict[str, Any]] = {}
    for mode in ("adaptive", "fixed"):
        statuses = Counter(row[mode]["status"] for row in rows)
        aggregates[mode] = {
            "completed_cases": len(rows) - statuses["unresolved"],
            "unresolved_cases": statuses["unresolved"],
            "statuses": dict(sorted(statuses.items())),
            **{
                field: sum(row[mode][field] for row in rows)
                for field in aggregate_fields
            },
        }
    fixed_only_completions = [
        row["name"]
        for row in rows
        if row["fixed"]["completed"] and not row["adaptive"]["completed"]
    ]
    adaptive_only_completions = [
        row["name"]
        for row in rows
        if row["adaptive"]["completed"] and not row["fixed"]["completed"]
    ]
    score_fields = (
        "unresolved_cases",
        "work_units",
        "failed_rule_attempts",
        "proof_bytes",
    )
    adaptive_score = [aggregates["adaptive"][field] for field in score_fields]
    fixed_score = [aggregates["fixed"][field] for field in score_fields]
    completion_protected = not fixed_only_completions
    adaptive_benefit = completion_protected and adaptive_score < fixed_score
    selected_default = "adaptive" if adaptive_benefit else "fixed"
    return {
        "schema": "cassifi.cubic-reduction-schedule-ablation.v1",
        "corpus": "structured_held_out_only",
        "case_count": len(rows),
        "case_stream_sha256": digest(
            [
                {
                    "name": row["name"],
                    "formula_sha256": row["formula_sha256"],
                }
                for row in rows
            ]
        ),
        "profiles": descriptors,
        "cases": rows,
        "aggregates": aggregates,
        "decision": {
            "metric_order": list(score_fields),
            "comparison": "lexicographic_completion_first_exact_resource_cost",
            "fixed_only_completions": fixed_only_completions,
            "adaptive_only_completions": adaptive_only_completions,
            "completion_protected": completion_protected,
            "adaptive_score": adaptive_score,
            "fixed_score": fixed_score,
            "adaptive_measured_benefit": adaptive_benefit,
            "selected_default_schedule_mode": selected_default,
            "default_field_role": (
                "adaptive_scheduler"
                if selected_default == "adaptive"
                else "observation_only"
            ),
        },
        "timing_policy": (
            "wall clock is excluded from the canonical decision because it is "
            "not independently replayable; exact resource counters are primary"
        ),
    }




def inference_ablation(
    specs: Sequence[tuple[str, str, Formula]],
    *,
    truth_by_formula: dict[str, str],
) -> dict[str, Any]:
    """Compare the two bounded upgrades against the cap-four baseline."""

    profiles = {
        "cap4_baseline": reduction.ReductionProfile(
            terminal_nullity=4,
            schedule_mode="fixed",
            literal_probing=False,
        ),
        "cap5_baseline": reduction.ReductionProfile(
            terminal_nullity=5,
            schedule_mode="fixed",
            literal_probing=False,
        ),
        "cap4_literal_probe": reduction.ReductionProfile(
            terminal_nullity=4,
            schedule_mode="fixed",
            literal_probing=True,
        ),
    }
    descriptors = {
        name: reduction.candidate_algorithm_descriptor(profile)
        for name, profile in profiles.items()
    }
    rows: list[dict[str, Any]] = []
    for name, group, formula in specs:
        canonical = kernel.canonical_cubic_formula(formula)
        formula_sha256 = formula_digest(canonical)
        truth_status = truth_by_formula[formula_sha256]
        variants: dict[str, dict[str, Any]] = {}
        for profile_name, profile in profiles.items():
            result = reduction.solve_cubic_reduction(canonical, profile=profile)
            if (
                result["status"] in ("sat", "unsat")
                and result["status"] != truth_status
            ):
                raise AssertionError(
                    f"{name}: {profile_name} claim disagrees with exhaustive truth"
                )
            variants[profile_name] = _reduction_metrics(result)
        rows.append(
            {
                "name": name,
                "group": group,
                "formula_sha256": formula_sha256,
                "variables": len(canonical),
                "truth_status": truth_status,
                **variants,
            }
        )

    aggregate_fields = (
        "work_units",
        "rule_attempts",
        "failed_rule_attempts",
        "rref_calls",
        "fraction_updates",
        "projection_queries",
        "projection_states_checked",
        "row_bound_combinations",
        "separator_candidates_checked",
        "literal_probe_trials",
        "propagation_rows_checked",
        "propagation_bound_checks",
        "propagation_assignments",
        "proof_bytes",
    )
    aggregates: dict[str, dict[str, Any]] = {}
    for profile_name in profiles:
        statuses = Counter(row[profile_name]["status"] for row in rows)
        aggregates[profile_name] = {
            "completed_cases": len(rows) - statuses["unresolved"],
            "unresolved_cases": statuses["unresolved"],
            "statuses": dict(sorted(statuses.items())),
            **{
                field: sum(row[profile_name][field] for row in rows)
                for field in aggregate_fields
            },
        }

    baseline = "cap4_baseline"
    score_fields = (
        "unresolved_cases",
        "work_units",
        "failed_rule_attempts",
        "proof_bytes",
    )
    baseline_only: dict[str, list[str]] = {}
    completion_gain: dict[str, list[str]] = {}
    eligible: list[str] = []
    for profile_name in profiles:
        baseline_only[profile_name] = [
            row["name"]
            for row in rows
            if row[baseline]["completed"] and not row[profile_name]["completed"]
        ]
        completion_gain[profile_name] = [
            row["name"]
            for row in rows
            if row[profile_name]["completed"] and not row[baseline]["completed"]
        ]
        if not baseline_only[profile_name]:
            eligible.append(profile_name)
    selected = min(
        eligible,
        key=lambda profile_name: (
            *(aggregates[profile_name][field] for field in score_fields),
            profile_name,
        ),
    )
    return {
        "schema": "cassifi.cubic-reduction-inference-ablation.v1",
        "corpus": "complete_fixed_structured_and_random",
        "case_count": len(rows),
        "case_stream_sha256": digest(
            [
                {
                    "name": row["name"],
                    "formula_sha256": row["formula_sha256"],
                }
                for row in rows
            ]
        ),
        "profiles": descriptors,
        "cases": rows,
        "aggregates": aggregates,
        "decision": {
            "baseline_profile": baseline,
            "metric_order": list(score_fields),
            "comparison": "completion_protected_lexicographic_exact_resource_cost",
            "baseline_only_completions": baseline_only,
            "completion_gain_cases": completion_gain,
            "eligible_profiles": eligible,
            "scores": {
                profile_name: [
                    aggregates[profile_name][field] for field in score_fields
                ]
                for profile_name in profiles
            },
            "selected_default_profile_name": selected,
            "selected_default_profile": descriptors[selected]["profile"],
        },
        "timing_policy": (
            "wall clock is reported only outside the canonical receipt; "
            "independently replayable exact resource counters select the profile"
        ),
    }


def build_receipt(
    *,
    random_sizes: Sequence[int] = RANDOM_SIZES,
    draws_per_size: int = RANDOM_DRAWS_PER_SIZE,
    seed: int = RANDOM_SEED,
    profile: reduction.ReductionProfile = reduction.ReductionProfile(),
) -> dict[str, Any]:
    random_specs, generation = random_corpus(
        sizes=random_sizes,
        draws_per_size=draws_per_size,
        seed=seed,
    )
    structured_specs, structured_generation = structured_corpus()
    fixed_specs = fixed_cases()
    specs = [*fixed_specs, *structured_specs, *random_specs]
    formula_hashes = [formula_digest(formula) for _, _, formula in specs]
    if len(set(formula_hashes)) != len(formula_hashes):
        raise AssertionError("fixed, structured, and random corpus partitions overlap")
    cases = [
        evaluate_formula(name, group, formula, profile=profile)
        for name, group, formula in specs
    ]
    truth_by_formula = {
        case["formula_sha256"]: case["truth"]["status"] for case in cases
    }
    inference = inference_ablation(
        specs,
        truth_by_formula=truth_by_formula,
    )
    selected_profile_name = inference["decision"]["selected_default_profile_name"]
    selected_profile = inference["decision"]["selected_default_profile"]
    if reduction.candidate_algorithm_descriptor(profile)["profile"] != selected_profile:
        raise AssertionError(
            "canonical receipt profile does not use the full-corpus inference selection"
        )
    ablation = schedule_ablation(
        structured_specs,
        terminal_nullity=profile.terminal_nullity,
        truth_by_formula=truth_by_formula,
        literal_probing=profile.literal_probing,
    )
    selected_schedule = ablation["decision"]["selected_default_schedule_mode"]
    if profile.schedule_mode != selected_schedule:
        raise AssertionError(
            "canonical receipt profile does not use the held-out ablation selection"
        )
    unresolved = [case for case in cases if case["reduction"]["status"] == "unresolved"]
    hardest = max(
        cases,
        key=lambda case: (*case["hardness"]["tuple"], case["formula_sha256"]),
    )
    minimal_observed = (
        None
        if not unresolved
        else min(unresolved, key=lambda case: (case["variables"], case["formula_sha256"]))
    )
    if not unresolved:
        raise AssertionError(
            "adversarial screen unexpectedly found no finite-rule counterexample; "
            "the completeness obligation must be re-audited before changing this expectation"
        )
    composite = connected_chain(
        (
            tuple(tuple(row) for row in hardest["formula"]),
            SUPPORT_THREE_SAT,
        ),
        ((0, 1),),
    )
    minimization = minimize_connected_counterexample(composite, profile=profile)
    if (
        not minimization["source_connected"]
        or minimization["variables"] >= minimization["source_variables"]
    ):
        raise AssertionError("connected minimizer failed to shrink its unresolved source")

    statuses = Counter(case["reduction"]["status"] for case in cases)
    truth_statuses = Counter(case["truth"]["status"] for case in cases)
    group_statuses: dict[str, dict[str, int]] = {}
    for group in sorted({case["group"] for case in cases}):
        group_statuses[group] = dict(
            sorted(
                Counter(
                    case["reduction"]["status"]
                    for case in cases
                    if case["group"] == group
                ).items()
            )
        )
    summary = {
        "cases": len(cases),
        "fixed_cases": len(fixed_specs),
        "structured_heldout_cases": len(structured_specs),
        "seeded_random_cases": len(random_specs),
        "variables_minimum": min(case["variables"] for case in cases),
        "variables_maximum": max(case["variables"] for case in cases),
        "reduction_statuses": dict(sorted(statuses.items())),
        "truth_statuses": dict(sorted(truth_statuses.items())),
        "group_statuses": group_statuses,
        "truth_claim_mismatches": sum(
            case["reduction"]["status"] in ("sat", "unsat")
            and case["reduction"]["status"] != case["truth"]["status"]
            for case in cases
        ),
        "progress_failures": sum(
            not case["reduction"]["progress"]["strictly_descending"]
            or case["reduction"]["progress"]["final"] != 0
            for case in cases
        ),
        "representation_bound_failures": sum(
            not case["reduction"]["representation"]["bound_respected"]
            for case in cases
        ),
        "persistent_adaptive_states": sum(
            case["reduction"]["field_preference"]["persistence"]
            != "invocation_local_only"
            for case in cases
        ),
        "canonical_cache_hits": sum(
            case["reduction"]["representation"]["cache_hits"] for case in cases
        ),
        "hardest_formula_sha256": hardest["formula_sha256"],
        "hardest_score": hardest["hardness"]["tuple"],
        "minimal_observed_unresolved_variables": (
            None if minimal_observed is None else minimal_observed["variables"]
        ),
        "minimal_observed_unresolved_sha256": (
            None if minimal_observed is None else minimal_observed["formula_sha256"]
        ),
        "connected_minimization_reduction": (
            minimization["source_variables"] - minimization["variables"]
        ),
        "selected_schedule_mode": selected_schedule,
        "selected_inference_profile": selected_profile_name,
    }
    if any(
        summary[key] != 0
        for key in (
            "truth_claim_mismatches",
            "progress_failures",
            "representation_bound_failures",
            "persistent_adaptive_states",
        )
    ):
        raise AssertionError("a proof-oriented safety invariant failed")
    if summary["canonical_cache_hits"] < 1:
        raise AssertionError("canonical duplicate-component cache path was not exercised")

    algorithm = reduction.candidate_algorithm_descriptor(profile)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "measured",
        "algorithm": algorithm,
        "generation": generation,
        "structured_generation": structured_generation,
        "selection": {
            "hardness_order": [
                "unresolved_indicator",
                "maximum_unresolved_variables",
                "pair_guards_checked",
                "projection_states_checked",
                "progress_events",
                "formula_sha256",
            ],
            "hardest_case": hardest["name"],
            "minimal_observed_unresolved_case": (
                None if minimal_observed is None else minimal_observed["name"]
            ),
        },
        "cases": cases,
        "case_stream_sha256": digest(cases),
        "minimization": minimization,
        "schedule_ablation": ablation,
        "inference_ablation": inference,
        "summary": summary,
        "assessment": {
            "measured_result": (
                "All bounded SAT/UNSAT claims matched complete Boolean evaluation; "
                "the finite exact rule set still has legal unresolved residuals."
            ),
            "proof_status": "incomplete_algorithm",
            "p_equals_np": "not_established",
            "next_target": (
                "derive and independently verify a new exact rule for the smallest or "
                "highest-scoring retained unresolved residual family"
            ),
            "scope": (
                "frozen controls, frozen structurally held-out connected families, "
                "and a seeded finite connected cubic corpus; neither coverage nor "
                "single-unswitch minimization is an arbitrary-order theorem"
            ),
        },
    }
    receipt["receipt_sha256"] = digest(receipt)
    return receipt


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--draws-per-size", type=int, default=RANDOM_DRAWS_PER_SIZE)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--terminal-nullity", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    receipt = build_receipt(
        draws_per_size=args.draws_per_size,
        seed=args.seed,
        profile=reduction.ReductionProfile(args.terminal_nullity),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["summary"], sort_keys=True))
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
