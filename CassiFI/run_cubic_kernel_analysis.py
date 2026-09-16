"""Generate exact evidence for the cubic incidence-kernel theorem.

The receipt combines prior pure-cubic scenarios, exact column-basis censuses,
a singular non-cardinality UNSAT obstruction, circulant SAT families, and
connected switched-component families whose matrix nullity grows linearly.
The latter are a stopping test: nullity parameterization alone cannot become
a polynomial-time proof.
"""

from __future__ import annotations

import hashlib
from fractions import Fraction
import itertools
import json
from pathlib import Path
from typing import Any, Sequence

from cubic_kernel_decision import (
    canonical_cubic_formula,
    cubic_kernel_basis_width,
    cubic_kernel_dual_triangle_profile,
    cubic_kernel_profile,
    decide_cubic_kernel,
    cubic_kernel_zero_valid_basis,
    incidence_connected,
)

SOURCE = Path("_diag/alias_exact_one_decision.json")
OUTPUT = Path("_diag/cubic_kernel_analysis.json")
SCHEMA = "cassifi.cubic-kernel-analysis.v6"

SINGULAR_ALPHABET_UNSAT = (
    (1, 7, 9),
    (2, 5, 3),
    (3, 1, 7),
    (4, 8, 2),
    (5, 4, 8),
    (6, 9, 5),
    (7, 6, 1),
    (8, 2, 6),
    (9, 3, 4),
)

FULL_SUPPORT_ALPHABET_UNSAT = (
    (1, 5, 9),
    (2, 4, 5),
    (3, 2, 1),
    (4, 9, 3),
    (5, 3, 8),
    (6, 8, 2),
    (7, 1, 4),
    (8, 7, 6),
    (9, 6, 7),
)

SUPPORT_THREE_SAT = (
    (1, 6, 3),
    (1, 3, 5),
    (1, 8, 2),
    (4, 6, 8),
    (4, 8, 5),
    (4, 3, 2),
    (7, 9, 5),
    (7, 9, 2),
    (7, 9, 6),
)

SUPPORT_THREE_UNSAT = (
    (1, 14, 11),
    (2, 1, 15),
    (3, 10, 5),
    (4, 8, 14),
    (5, 11, 7),
    (6, 12, 1),
    (7, 9, 2),
    (8, 15, 12),
    (9, 5, 6),
    (10, 13, 3),
    (11, 4, 8),
    (12, 3, 10),
    (13, 6, 4),
    (14, 7, 13),
    (15, 2, 9),
)

ALL_BASES_TERNARY_SAT = (
    (1, 2, 7),
    (1, 4, 10),
    (1, 6, 10),
    (2, 7, 9),
    (2, 11, 12),
    (3, 4, 11),
    (3, 6, 7),
    (3, 8, 12),
    (4, 9, 10),
    (5, 6, 11),
    (5, 8, 9),
    (5, 8, 12),
)

ALL_BASES_TERNARY_UNSAT = (
    (1, 3, 7),
    (1, 6, 12),
    (1, 7, 8),
    (2, 3, 6),
    (2, 10, 13),
    (2, 13, 15),
    (3, 4, 12),
    (4, 7, 9),
    (4, 11, 12),
    (5, 8, 10),
    (5, 11, 15),
    (5, 13, 14),
    (6, 9, 14),
    (8, 11, 14),
    (9, 10, 15),
)

GREEDY_EXCHANGE_TRAP_SAT = (
    (1, 2, 6),
    (1, 3, 5),
    (1, 3, 7),
    (2, 4, 6),
    (2, 4, 9),
    (3, 4, 5),
    (5, 8, 9),
    (6, 7, 8),
    (7, 8, 9),
)


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = canonical_cubic_formula(formula)
    payload = json.dumps(canonical, separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def satisfies(formula: Sequence[Sequence[int]], assignment: Sequence[int]) -> bool:
    return all(
        sum(assignment[variable - 1] for variable in clause) == 1
        for clause in formula
    )

SCHAEFER_CLASSES = (
    "zero_valid",
    "one_valid",
    "horn",
    "dual_horn",
    "bijunctive",
    "affine",
)


def relation_properties(
    tuples: Sequence[tuple[int, ...]], arity: int
) -> dict[str, bool]:
    members = set(tuples)
    horn = all(
        tuple(left[i] & right[i] for i in range(arity)) in members
        for left in tuples
        for right in tuples
    )
    dual_horn = all(
        tuple(left[i] | right[i] for i in range(arity)) in members
        for left in tuples
        for right in tuples
    )
    bijunctive = all(
        tuple(
            int(left[i] + middle[i] + right[i] >= 2) for i in range(arity)
        )
        in members
        for left in tuples
        for middle in tuples
        for right in tuples
    )
    affine = all(
        tuple(left[i] ^ middle[i] ^ right[i] for i in range(arity))
        in members
        for left in tuples
        for middle in tuples
        for right in tuples
    )
    return {
        "zero_valid": (0,) * arity in members,
        "one_valid": (1,) * arity in members,
        "horn": horn,
        "dual_horn": dual_horn,
        "bijunctive": bijunctive,
        "affine": affine,
    }


def relation_language_profile(profile: dict[str, Any]) -> dict[str, Any]:
    maximum_support = profile["maximum_pivot_free_support"]
    if maximum_support > 3:
        return {
            "analyzed": False,
            "maximum_supported_arity": 3,
            "common_schaefer_classes": None,
            "support_histogram": profile["pivot_free_support_histogram"],
            "ternary_relations": None,
        }

    basis = [
        [Fraction(value) for value in vector]
        for vector in profile["kernel_basis"]
    ]
    relations = []
    for pivot in profile["pivot_columns"]:
        coefficients = [vector[pivot - 1] for vector in basis]
        support = tuple(
            index for index, coefficient in enumerate(coefficients) if coefficient
        )
        allowed = []
        for bits in itertools.product((0, 1), repeat=len(support)):
            pivot_value = sum(
                (
                    coefficients[index] * (3 * bit - 1)
                    for index, bit in zip(support, bits, strict=True)
                ),
                start=Fraction(0),
            )
            if pivot_value in (-1, 2):
                allowed.append(bits)
        properties = relation_properties(allowed, len(support))
        relations.append(
            {
                "pivot_column": pivot,
                "free_columns": [profile["free_columns"][index] for index in support],
                "coefficients": [
                    str(coefficients[index]) for index in support
                ],
                "allowed_tuples": [list(bits) for bits in allowed],
                "properties": properties,
            }
        )

    common = [
        property_name
        for property_name in SCHAEFER_CLASSES
        if all(relation["properties"][property_name] for relation in relations)
    ]
    return {
        "analyzed": True,
        "maximum_supported_arity": 3,
        "common_schaefer_classes": common,
        "support_histogram": profile["pivot_free_support_histogram"],
        "ternary_relations": [
            relation for relation in relations if len(relation["free_columns"]) == 3
        ],
    }


def circulant_formula(size: int) -> tuple[tuple[int, int, int], ...]:
    return tuple(
        (
            index + 1,
            (index + 1) % size + 1,
            (index + 2) % size + 1,
        )
        for index in range(size)
    )


def switched_component_family(
    k33_blocks: int, *, crown_core: bool
) -> tuple[tuple[tuple[int, int, int], ...], list[int] | None, dict[str, int]]:
    """Connect cubic components with rank-one degree-preserving 2-switches."""

    if k33_blocks < 1:
        raise ValueError("at least one K3,3 block is required")
    rows: list[set[int]] = []
    components: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    variable_offset = 0

    if crown_core:
        crown_variables = tuple(range(variable_offset + 1, variable_offset + 5))
        crown_rows = tuple(range(len(rows), len(rows) + 4))
        for excluded in crown_variables:
            rows.append(set(crown_variables) - {excluded})
        components.append((crown_rows, crown_variables))
        variable_offset += 4

    k33_variable_starts: list[int] = []
    for _ in range(k33_blocks):
        variables = tuple(range(variable_offset + 1, variable_offset + 4))
        block_rows = tuple(range(len(rows), len(rows) + 3))
        rows.extend(set(variables) for _ in range(3))
        components.append((block_rows, variables))
        k33_variable_starts.append(variable_offset)
        variable_offset += 3

    for left, right in zip(components, components[1:]):
        left_rows, left_variables = left
        right_rows, right_variables = right
        left_row = left_rows[-1]
        right_row = right_rows[0]
        left_variable = left_variables[1]
        right_variable = right_variables[1]
        if left_variable not in rows[left_row] or right_variable not in rows[right_row]:
            raise AssertionError("rank-one switch source edge is absent")
        if right_variable in rows[left_row] or left_variable in rows[right_row]:
            raise AssertionError("rank-one switch would create a duplicate edge")
        rows[left_row].remove(left_variable)
        rows[left_row].add(right_variable)
        rows[right_row].remove(right_variable)
        rows[right_row].add(left_variable)

    formula = tuple(tuple(sorted(row)) for row in rows)
    canonical = canonical_cubic_formula(formula)
    links = len(components) - 1
    initial_nullity = 2 * k33_blocks
    lower_bound = initial_nullity - links
    construction = {
        "k33_blocks": k33_blocks,
        "crown_core_vertices_per_side": 4 if crown_core else 0,
        "rank_one_switches": links,
        "initial_block_diagonal_nullity": initial_nullity,
        "proved_nullity_lower_bound": lower_bound,
    }

    if crown_core:
        return canonical, None, construction

    assignment = [0] * len(canonical)
    for start in k33_variable_starts:
        assignment[start] = 1
    if not satisfies(canonical, assignment):
        raise AssertionError("switched K3,3 witness no longer satisfies the formula")
    return canonical, assignment, construction


def build_case(
    *,
    name: str,
    category: str,
    formula: Sequence[Sequence[int]],
    expected_status: str,
    witness: Sequence[int] | None = None,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    canonical = canonical_cubic_formula(formula)
    profile = cubic_kernel_profile(canonical)
    if witness is not None:
        if len(witness) != len(canonical) or any(value not in (0, 1) for value in witness):
            raise AssertionError(f"{name}: invalid witness shape")
        if not satisfies(canonical, witness):
            raise AssertionError(f"{name}: witness does not satisfy the source formula")
    result = decide_cubic_kernel(canonical)
    if result["status"] != expected_status:
        raise AssertionError(f"{name}: kernel decision disagrees with expected status")
    if (
        expected_status == "sat"
        and witness is None
        and result["assignment"] is None
    ):
        raise AssertionError(f"{name}: SAT case has no checked witness")

    return {
        "name": name,
        "category": category,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": formula_digest(canonical),
        "connected": incidence_connected(canonical),
        "expected_status": expected_status,
        "profile": profile,
        "relation_language": relation_language_profile(profile),
        "decision": result,
        "construction_witness": list(witness) if witness is not None else None,
        "provenance": provenance or {},
    }


def build_basis_width_case(
    *,
    name: str,
    formula: Sequence[Sequence[int]],
    expected_status: str,
    expect_binary_basis: bool,
    expect_exchange_trap: bool = False,
) -> dict[str, Any]:
    canonical = canonical_cubic_formula(formula)
    basis_width = cubic_kernel_basis_width(
        canonical, analyze_basis_exchange=True
    )
    if (
        basis_width["bounded_support_2sat_basis_exists"]
        != expect_binary_basis
    ):
        raise AssertionError(f"{name}: unexpected basis-width boundary")
    exchange = basis_width["basis_exchange"]
    if (
        exchange is None
        or bool(exchange["nonglobal_local_minima"]) != expect_exchange_trap
    ):
        raise AssertionError(f"{name}: unexpected basis-exchange landscape")
    canonical_decision = decide_cubic_kernel(canonical)
    if canonical_decision["status"] != expected_status:
        raise AssertionError(f"{name}: canonical decision mismatch")
    optimized_decision = None
    if expect_binary_basis:
        optimized_decision = decide_cubic_kernel(
            canonical,
            pivot_columns=basis_width["witness"]["pivot_columns"],
        )
        if (
            optimized_decision["status"] != expected_status
            or optimized_decision["maximum_pivot_free_support"] > 2
            or optimized_decision["candidates_checked"] != 0
        ):
            raise AssertionError(f"{name}: optimized 2-SAT decision mismatch")
    zero_valid_basis = None
    if expected_status == "sat":
        zero_valid_basis = cubic_kernel_zero_valid_basis(
            canonical, canonical_decision["assignment"]
        )
        if any(
            canonical_decision["assignment"][column - 1] != 0
            for column in zero_valid_basis["free_columns"]
        ):
            raise AssertionError(f"{name}: zero-valid basis uses a one coordinate")
        zero_basis_decision = decide_cubic_kernel(
            canonical,
            pivot_columns=zero_valid_basis["pivot_columns"],
        )
        if zero_basis_decision["status"] != "sat":
            raise AssertionError(f"{name}: zero-valid basis lost its SAT witness")
    return {
        "name": name,
        "formula": [list(clause) for clause in canonical],
        "formula_sha256": formula_digest(canonical),
        "expected_status": expected_status,
        "expected_boundary": (
            "canonical_to_binary"
            if expect_binary_basis
            else "all_bases_ternary"
        ),
        "expected_exchange_boundary": (
            "strict_descent_trap"
            if expect_exchange_trap
            else "no_strict_descent_trap"
        ),
        "canonical_profile": cubic_kernel_profile(canonical),
        "canonical_decision": canonical_decision,
        "basis_width": basis_width,
        "dual_triangle_profile": cubic_kernel_dual_triangle_profile(canonical),
        "optimized_decision": optimized_decision,
        "zero_valid_basis": zero_valid_basis,
    }


def main() -> None:
    source_raw = SOURCE.read_bytes()
    source = json.loads(source_raw)
    cases: list[dict[str, Any]] = []

    grouped_source: dict[
        tuple[tuple[int, int, int], ...], dict[str, Any]
    ] = {}
    for row in source["cases"]:
        if len(row["certificate"]["cubic_variables"]) != row["variables"]:
            continue
        canonical = canonical_cubic_formula(row["formula"])
        existing = grouped_source.setdefault(
            canonical,
            {
                "names": [],
                "status": row["certificate"]["status"],
            },
        )
        if existing["status"] != row["certificate"]["status"]:
            raise AssertionError("duplicate pure-cubic formula has conflicting verdicts")
        existing["names"].append(row["name"])

    for index, (formula, source_group) in enumerate(
        sorted(grouped_source.items(), key=lambda item: (len(item[0]), item[0]))
    ):
        cases.append(
            build_case(
                name=f"source-pure-cubic-{index:02d}",
                category="prior_pure_cubic",
                formula=formula,
                expected_status=source_group["status"],
                provenance={"source_case_names": source_group["names"]},
            )
        )

    cases.append(
        build_case(
            name="singular-alphabet-unsat-n9",
            category="singular_noncardinality_unsat",
            formula=SINGULAR_ALPHABET_UNSAT,
            expected_status="unsat",
            provenance={
                "obstruction": (
                    "rank 8 and n divisible by 3, but the one-dimensional "
                    "kernel has seven identically zero coordinates"
                )
            },
        )
    )

    cases.append(
        build_case(
            name="full-support-alphabet-unsat-n9",
            category="bounded_support_noncardinality_unsat",
            formula=FULL_SUPPORT_ALPHABET_UNSAT,
            expected_status="unsat",
            provenance={
                "obstruction": (
                    "the one-dimensional kernel has full coordinate support, "
                    "but neither allowed value of its free coordinate puts "
                    "every pivot coordinate in {-1,2}"
                )
            },
        )
    )
    cases.append(
        build_case(
            name="support-three-planted-sat-n9",
            category="support_three_boundary_sat",
            formula=SUPPORT_THREE_SAT,
            expected_status="sat",
            witness=[1, 0, 0, 1, 0, 0, 1, 0, 0],
            provenance={"construction": "degree-preserving planted-cover switches"},
        )
    )
    cases.append(
        build_case(
            name="support-three-unsat-n15",
            category="support_three_boundary_unsat",
            formula=SUPPORT_THREE_UNSAT,
            expected_status="unsat",
            provenance={
                "obstruction": (
                    "rank, cardinality, and binary-support 2-SAT do not decide; "
                    "all eight free-coordinate alphabet vectors are rejected"
                )
            },
        )
    )

    for size in (3, 6, 9, 12, 24):
        formula = circulant_formula(size)
        witness = [int(index % 3 == 0) for index in range(size)]
        cases.append(
            build_case(
                name=f"circulant-period-three-sat-n{size}",
                category="circulant_sat",
                formula=formula,
                expected_status="sat",
                witness=witness,
                provenance={"offsets": [0, 1, 2]},
            )
        )

    for blocks in (1, 2, 4, 8, 16, 32):
        formula, witness, construction = switched_component_family(
            blocks, crown_core=False
        )
        case = build_case(
            name=f"connected-k33-chain-sat-b{blocks}",
            category="connected_linear_nullity_sat",
            formula=formula,
            expected_status="sat",
            witness=witness,
            provenance=construction,
        )
        if case["profile"]["nullity"] < construction["proved_nullity_lower_bound"]:
            raise AssertionError("rank-one SAT family violated its nullity bound")
        cases.append(case)

        formula, _, construction = switched_component_family(
            blocks, crown_core=True
        )
        case = build_case(
            name=f"connected-crown-k33-unsat-b{blocks}",
            category="connected_linear_nullity_cardinality_unsat",
            formula=formula,
            expected_status="unsat",
            provenance=construction,
        )
        if len(formula) % 3 == 0:
            raise AssertionError("cardinality obstruction was not preserved")
        if case["profile"]["nullity"] < construction["proved_nullity_lower_bound"]:
            raise AssertionError("rank-one UNSAT family violated its nullity bound")
        cases.append(case)

    basis_width_cases = [
        build_basis_width_case(
            name="support-three-sat-canonical-to-binary",
            formula=SUPPORT_THREE_SAT,
            expected_status="sat",
            expect_binary_basis=True,
        ),
        build_basis_width_case(
            name="support-three-unsat-canonical-to-binary",
            formula=SUPPORT_THREE_UNSAT,
            expected_status="unsat",
            expect_binary_basis=True,
        ),
        build_basis_width_case(
            name="greedy-exchange-trap-sat-n9",
            formula=GREEDY_EXCHANGE_TRAP_SAT,
            expected_status="sat",
            expect_binary_basis=True,
            expect_exchange_trap=True,
        ),
        build_basis_width_case(
            name="all-bases-ternary-sat-n12",
            formula=ALL_BASES_TERNARY_SAT,
            expected_status="sat",
            expect_binary_basis=False,
        ),
        build_basis_width_case(
            name="all-bases-ternary-unsat-n15",
            formula=ALL_BASES_TERNARY_UNSAT,
            expected_status="unsat",
            expect_binary_basis=False,
        ),
    ]

    singular_noncardinality = [
        row
        for row in cases
        if row["expected_status"] == "unsat"
        and row["profile"]["nullity"] > 0
        and row["profile"]["clauses"] % 3 == 0
    ]
    high_nullity = [
        row
        for row in cases
        if row["category"].startswith("connected_linear_nullity")
    ]
    largest_family = max(
        high_nullity, key=lambda row: row["profile"]["variables"]
    )
    by_name = {row["name"]: row for row in cases}
    relation_boundary = {
        "support_three_sat_common_schaefer_classes": by_name[
            "support-three-planted-sat-n9"
        ]["relation_language"]["common_schaefer_classes"],
        "support_three_unsat_common_schaefer_classes": by_name[
            "support-three-unsat-n15"
        ]["relation_language"]["common_schaefer_classes"],
        "interpretation": (
            "the measured support-three UNSAT residual has no single standard "
            "Schaefer closure shared by all pivot relations; this does not prove "
            "NP-hardness for the restricted family of RREF-generated languages"
        ),
    }
    summary = {
        "basis_width_cases": len(basis_width_cases),
        "canonical_to_binary_basis_cases": sum(
            row["expected_boundary"] == "canonical_to_binary"
            for row in basis_width_cases
        ),
        "all_bases_ternary_cases": sum(
            row["expected_boundary"] == "all_bases_ternary"
            for row in basis_width_cases
        ),
        "basis_column_subsets_checked": sum(
            row["basis_width"]["column_subsets_checked"]
            for row in basis_width_cases
        ),
        "basis_column_bases_checked": sum(
            row["basis_width"]["column_bases_found"]
            for row in basis_width_cases
        ),
        "basis_exchange_nodes_checked": sum(
            row["basis_width"]["basis_exchange"]["basis_nodes"]
            for row in basis_width_cases
        ),
        "basis_exchange_edges_checked": sum(
            row["basis_width"]["basis_exchange"]["exchange_edges"]
            for row in basis_width_cases
        ),
        "strict_descent_trap_cases": sum(
            bool(
                row["basis_width"]["basis_exchange"][
                    "nonglobal_local_minima"
                ]
            )
            for row in basis_width_cases
        ),
        "nonglobal_strict_local_minima": sum(
            row["basis_width"]["basis_exchange"]["nonglobal_local_minima"]
            for row in basis_width_cases
        ),
        "all_exchange_graphs_connected": all(
            row["basis_width"]["basis_exchange"]["connected"]
            for row in basis_width_cases
        ),
        "dual_small_circuits_checked": sum(
            row["dual_triangle_profile"]["small_circuit_count"]
            for row in basis_width_cases
        ),
        "zero_valid_basis_certificates": sum(
            row["zero_valid_basis"] is not None for row in basis_width_cases
        ),
        "cases": len(cases),
        "sat": sum(row["expected_status"] == "sat" for row in cases),
        "unsat": sum(row["expected_status"] == "unsat" for row in cases),
        "full_rank_unsat": sum(
            row["expected_status"] == "unsat" and row["profile"]["nullity"] == 0
            for row in cases
        ),
        "singular_noncardinality_unsat": len(singular_noncardinality),
        "forced_zero_pivot_unsat": sum(
            row["decision"]["reason"] == "forced_zero_pivot" for row in cases
        ),
        "bounded_support_2sat_decisions": sum(
            row["decision"]["reason"].startswith("bounded_support_2sat")
            for row in cases
        ),
        "enumerated_kernel_decisions": sum(
            row["decision"]["reason"].startswith("alphabet_") for row in cases
        ),
        "maximum_clauses": max(row["profile"]["clauses"] for row in cases),
        "maximum_nullity": max(row["profile"]["nullity"] for row in cases),
        "maximum_pivot_free_support": max(
            row["profile"]["maximum_pivot_free_support"] for row in cases
        ),
        "support_three_sat_common_schaefer_classes": relation_boundary[
            "support_three_sat_common_schaefer_classes"
        ],
        "support_three_unsat_common_schaefer_classes": relation_boundary[
            "support_three_unsat_common_schaefer_classes"
        ],
        "maximum_connected_nullity_ratio": max(
            row["profile"]["nullity"] / row["profile"]["variables"]
            for row in high_nullity
        ),
        "largest_family_nullity_ratio": (
            largest_family["profile"]["nullity"]
            / largest_family["profile"]["variables"]
        ),
        "all_family_nullities_meet_rank_one_bound": all(
            row["profile"]["nullity"]
            >= row["provenance"]["proved_nullity_lower_bound"]
            for row in high_nullity
        ),
        "all_decisions_agree": all(
            row["decision"]["status"] == row["expected_status"] for row in cases
        ),
        "all_sat_witnesses_check": all(
            row["expected_status"] != "sat"
            or satisfies(
                row["formula"],
                row["construction_witness"] or row["decision"]["assignment"],
            )
            for row in cases
        ),
        "linear_nullity_families_checked": len(high_nullity),
    }
    theorem = {
        "domain": (
            "square 0/1 incidence matrices with exactly three ones in every "
            "row and column"
        ),
        "equivalence": "Mx = 1, x in {0,1}^n iff M(3x-1) = 0",
        "kernel_alphabet": "z in ker(M) intersect {-1,2}^n",
        "rank_corollary": "full column rank implies UNSAT",
        "cardinality_corollary": "SAT implies n is divisible by 3",
        "algorithm": (
            "use 2-SAT when every pivot relation for a supplied column basis "
            "has at most two free coordinates; otherwise enumerate {-1,2} "
            "on free columns"
        ),
        "bounded_support_theorem": (
            "a supplied basis with maximum pivot free-support at most two "
            "is verifiable and decidable in polynomial time"
        ),
        "basis_width_matroid_equivalence": (
            "for pivot basis B and free complement F, pivot support plus one "
            "is fundamental-cocircuit size in the column matroid, equivalently "
            "fundamental-circuit size for basis F in its dual; width at most "
            "two exactly says F frames the dual"
        ),
        "dual_frame_boundary": (
            "width at most two is exactly the existence of a ground-set basis "
            "that frames the dual column matroid; this is stronger than merely "
            "having a row-equivalent external frame representation"
        ),
        "fixed_nullity_basis_search": (
            "for every fixed nullity k, enumerating the binomial(n,k) dual "
            "bases is O(n^k) and therefore polynomial; this does not cover "
            "families whose nullity grows with n"
        ),
        "zero_valid_basis_equivalence": (
            "a cubic exact-one formula is SAT iff some dual ground-set basis "
            "makes every induced pivot relation contain the all-zero Boolean "
            "free tuple; a satisfying assignment and such a basis certificate "
            "convert to one another in polynomial time"
        ),
        "zero_valid_basis_complexity": (
            "existence of a zero-valid dual ground-set basis is NP-complete "
            "even for planar square incidence matrices with exactly three "
            "ones in every row and column"
        ),
        "graphic_dual_subclass": (
            "when the dual column matroid is graphic, a width-two basis is "
            "exactly a spanning forest that is a tree 2-spanner in each "
            "component; graphic recognition and tree-2-spanner construction "
            "are polynomial"
        ),
        "graphic_primal_subclass": (
            "when the column matroid is graphic, a width-two basis is exactly "
            "a spanning forest of congestion at most three in each component; "
            "graphic recognition and threshold-three spanning-tree-congestion "
            "construction are polynomial"
        ),
        "basis_search": (
            "the exact analyzer enumerates binomial(n,rank) column subsets; "
            "it proves small-instance optima but is not a polynomial basis finder"
        ),
        "bit_complexity": (
            "poly(n) for a supplied binary-support basis; "
            "O(2^nullity poly(n)) for the fallback, using exact rational arithmetic"
        ),
        "limitation": (
            "zero-valid internal basis recognition is NP-complete, while fixed "
            "nullity and graphic primal or dual structure give polynomially "
            "recognizable subclasses for the width-two question; the "
            "unrestricted internal frame-basis problem for this cubic rational-"
            "matrix family is not classified here, and exhaustive controls "
            "contain strict local minima under improving one-column exchange"
        ),
        "p_equals_np": "not established",
    }
    receipt = {
        "schema": SCHEMA,
        "source_receipt_sha256": hashlib.sha256(source_raw).hexdigest(),
        "theorem": theorem,
        "relation_boundary": relation_boundary,
        "basis_width_cases": basis_width_cases,
        "cases": cases,
        "summary": summary,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
