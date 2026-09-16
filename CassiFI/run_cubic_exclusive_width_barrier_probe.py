"""Search two bounded cubic domains for an exclusive width-two basis barrier.

For a cubic incidence matrix ``M``, let the columns of ``K`` represent
``ker(M)``.  An eligible pair is exclusive over the complete family of
width-two ground bases, has rank two in ``K``, and consists of distinct columns
of ``M``.  Dual-matroid basis extension then guarantees ordinary ground bases
in the missing ``00`` and ``11`` states, so eligibility is exactly a two-sided
width barrier: both escape states exist, but only above width two.

The runner checks every original-column pair in the complete distance-one
neighborhoods of two frozen near-misses and in a deterministic 20,000-draw
simple cubic configuration-model corpus.  A separate rational vector anchor
shows that the barrier predicate can fire outside the cubic-incidence domain.
The finite result is not a proof of the cubic degeneracy conjecture or a
complexity classification.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import random
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import run_cubic_admissible_cell_probe as admissible
import run_cubic_exclusive_pair_neighborhood_probe as neighborhood

OUTPUT = Path("_diag/cubic_exclusive_width_barrier_probe.json")
SCHEMA = "cassifi.cubic-exclusive-width-barrier-probe.v1"
RANDOM_SIZE = 12
RANDOM_ACCEPTED_DRAWS = 20_000
RANDOM_SEED = 0xE11B1E
PAIR_NAMESPACE = "one-based original variable-column numbers"
SWITCH_NAMESPACE = (
    "zero-based clause rows followed by one-based exchanged variable columns"
)

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]
Basis = tuple[int, ...]
Ports = tuple[int, int]
Switch = tuple[int, int, int, int]

EXPECTED_NEIGHBOR_SWITCH_ACCOUNTING = {
    "base_equivalent_specs": 16,
    "canonical_domain_formulas": 766,
    "distinct_nonbase_neighbors": 764,
    "duplicate_nonbase_specs": 80,
    "nonbase_switch_specs": 844,
    "raw_switch_specs": 860,
    "seed_formulas": 2,
}
EXPECTED_NEIGHBOR_SUMMARY = {
    "admissible_pairs": 0,
    "connected_formulas": 766,
    "disconnected_formulas": 0,
    "eligible_pairs": 0,
    "exact_census_formulas": 766,
    "exclusive_pairs": 343,
    "formulas_with_exclusive_pairs": 249,
    "formulas": 766,
    "inconclusive_formulas": 0,
    "no_width_two_formulas": 10,
    "nullity_two_all_bases_width_two": 497,
    "pair_cases_checked": 49_896,
    "pair_cases_inconclusive": 0,
    "pair_cases_not_applicable": 660,
    "pair_opportunities": 50_556,
    "rank_below_two_distinct": 162,
    "rank_below_two_identical": 0,
    "rank_dimension_excluded_formulas": 0,
    "rank_two_identical": 181,
    "width_two_formulas": 756,
}
EXPECTED_RANDOM_SUMMARY = {
    "accepted_draws": 20_000,
    "admissible_pairs": 0,
    "census_attempted_formulas": 2_853,
    "configuration_attempts": 490_819,
    "connected_formulas": 19_993,
    "disconnected_formulas": 7,
    "duplicate_draws": 0,
    "eligible_pairs": 0,
    "exact_census_formulas": 2_853,
    "exclusive_pairs": 252,
    "formulas": 20_000,
    "formulas_with_exclusive_pairs": 195,
    "inconclusive_formulas": 0,
    "no_width_two_formulas": 11,
    "nullity_two_all_bases_width_two": 2_714,
    "pair_cases_checked": 187_572,
    "pair_cases_inconclusive": 0,
    "pair_cases_not_applicable": 726,
    "pair_opportunities_connected": 1_319_538,
    "pair_opportunities_disconnected": 462,
    "pair_opportunities_rank_dimension_excluded": 1_131_240,
    "rank_below_two_distinct": 49,
    "rank_below_two_identical": 118,
    "rank_dimension_excluded_formulas": 17_140,
    "rank_two_identical": 85,
    "unique_formulas": 20_000,
    "width_two_formulas": 2_842,
}
EXPECTED_RANDOM_NULLITY_HISTOGRAM = {
    "0": 6_202,
    "1": 10_938,
    "2": 2_714,
    "3": 138,
    "4": 1,
}

SYNTHETIC_BARRIER_VECTORS = (
    (0, 0, 1),
    (0, 1, -1),
    (0, 1, 0),
    (1, -1, -1),
    (1, -1, 0),
    (1, 0, -1),
)
SYNTHETIC_BARRIER_PORTS = (1, 6)
SYNTHETIC_NO_BARRIER_VECTORS = (
    (1, 0),
    (0, 1),
    (1, 1),
    (1, -1),
)
SYNTHETIC_NO_BARRIER_PORTS = (1, 2)


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = admissible.production.canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _fraction_vectors(
    vectors: Sequence[Sequence[int]],
) -> tuple[Vector, ...]:
    return tuple(tuple(Fraction(value) for value in vector) for vector in vectors)


def _vector_configuration_profile(
    raw_vectors: Sequence[Sequence[int]],
    ports: Ports,
) -> dict[str, Any]:
    vectors = _fraction_vectors(raw_vectors)
    dimension = len(vectors[0])
    if any(len(vector) != dimension for vector in vectors):
        raise ValueError("synthetic vectors must have one common dimension")
    if admissible.production._vector_rank(vectors) != dimension:
        raise ValueError("synthetic vectors must span their ambient dimension")
    if not (1 <= ports[0] < ports[1] <= len(vectors)):
        raise ValueError("synthetic ports must be a sorted in-range pair")

    basis_rows: list[dict[str, Any]] = []
    for selected in itertools.combinations(range(len(vectors)), dimension):
        basis_vectors = tuple(vectors[index] for index in selected)
        if admissible.production._vector_rank(basis_vectors) != dimension:
            continue
        maximum_support = max(
            sum(
                coordinate != 0
                for coordinate in admissible.production._basis_coordinates(
                    basis_vectors,
                    vector,
                )
            )
            for vector in vectors
        )
        basis = tuple(index + 1 for index in selected)
        state = (
            f"{int(ports[0] in basis)}{int(ports[1] in basis)}"
        )
        basis_rows.append(
            {
                "basis": list(basis),
                "state": state,
                "maximum_support": maximum_support,
                "width_two": maximum_support <= 2,
            }
        )

    state_profile: dict[str, Any] = {}
    for state in ("00", "01", "10", "11"):
        rows = [row for row in basis_rows if row["state"] == state]
        minimum = min((row["maximum_support"] for row in rows), default=None)
        witnesses = [
            row["basis"] for row in rows if row["maximum_support"] == minimum
        ]
        state_profile[state] = {
            "ordinary_basis_count": len(rows),
            "minimum_width": minimum,
            "minimum_witness": witnesses[0] if witnesses else None,
            "width_two_basis_count": sum(row["width_two"] for row in rows),
        }
    width_two_states = {
        row["state"] for row in basis_rows if row["width_two"]
    }
    pair_rank = admissible.production._vector_rank(
        (vectors[ports[0] - 1], vectors[ports[1] - 1])
    )
    ordinary_all_states = all(
        state_profile[state]["ordinary_basis_count"] > 0
        for state in ("00", "01", "10", "11")
    )
    exclusive_width_two = width_two_states == {"01", "10"}
    two_sided_barrier = (
        ordinary_all_states
        and exclusive_width_two
        and state_profile["00"]["minimum_width"] > 2
        and state_profile["11"]["minimum_width"] > 2
    )
    return {
        "vectors": [list(vector) for vector in raw_vectors],
        "ports": list(ports),
        "dimension": dimension,
        "pair_rank": pair_rank,
        "ordinary_basis_count": len(basis_rows),
        "width_two_basis_count": sum(row["width_two"] for row in basis_rows),
        "width_two_bases": [
            row["basis"] for row in basis_rows if row["width_two"]
        ],
        "width_two_states": sorted(width_two_states),
        "state_profile": state_profile,
        "ordinary_all_states": ordinary_all_states,
        "exclusive_width_two": exclusive_width_two,
        "two_sided_width_barrier": two_sided_barrier,
    }


def synthetic_controls() -> dict[str, Any]:
    positive = _vector_configuration_profile(
        SYNTHETIC_BARRIER_VECTORS,
        SYNTHETIC_BARRIER_PORTS,
    )
    negative = _vector_configuration_profile(
        SYNTHETIC_NO_BARRIER_VECTORS,
        SYNTHETIC_NO_BARRIER_PORTS,
    )
    if (
        positive["pair_rank"] != 2
        or positive["ordinary_basis_count"] != 16
        or positive["width_two_basis_count"] != 4
        or positive["state_profile"]["00"]["minimum_width"] != 3
        or positive["state_profile"]["01"]["minimum_width"] != 2
        or positive["state_profile"]["10"]["minimum_width"] != 2
        or positive["state_profile"]["11"]["minimum_width"] != 3
        or not positive["two_sided_width_barrier"]
    ):
        raise AssertionError("synthetic positive barrier anchor did not fire")
    if negative["pair_rank"] != 2 or negative["two_sided_width_barrier"]:
        raise AssertionError("synthetic negative barrier anchor fired")
    return {
        "positive_general_vector_anchor": positive,
        "negative_all_bases_width_two_anchor": negative,
        "scope": (
            "predicate controls over rational vector configurations; neither "
            "anchor is claimed to be a cubic incidence kernel"
        ),
    }


def _projective_key(vector: Sequence[Fraction]) -> Vector | None:
    first = next((value for value in vector if value), None)
    if first is None:
        return None
    return tuple(value / first for value in vector)


def _pair_profile(
    formula: Formula,
    bases: tuple[Basis, ...],
    vectors: tuple[Vector, ...],
) -> dict[str, Any]:
    size = len(formula)
    signatures: list[int] = []
    for column in range(1, size + 1):
        signature = 0
        for vertex, basis in enumerate(bases):
            if column in basis:
                signature |= 1 << vertex
        signatures.append(signature)
    supports = admissible.column_supports(formula)
    counts: Counter[str] = Counter(
        pair_cases_checked=math.comb(size, 2),
    )
    exclusive_rows: list[dict[str, Any]] = []
    graph: dict[str, Any] | None = None

    for left, right in itertools.combinations(range(size), 2):
        left_signature = signatures[left]
        right_signature = signatures[right]
        both = (left_signature & right_signature).bit_count()
        state_counts = {
            "00": len(bases)
            - left_signature.bit_count()
            - right_signature.bit_count()
            + both,
            "01": right_signature.bit_count() - both,
            "10": left_signature.bit_count() - both,
            "11": both,
        }
        exclusive = (
            state_counts["00"] == 0
            and state_counts["11"] == 0
            and state_counts["01"] > 0
            and state_counts["10"] > 0
        )
        if not exclusive:
            continue

        counts["exclusive_pairs"] += 1
        pair_rank = admissible.production._vector_rank(
            (vectors[left], vectors[right])
        )
        left_key = _projective_key(vectors[left])
        right_key = _projective_key(vectors[right])
        nonzero = left_key is not None and right_key is not None
        parallel = nonzero and left_key == right_key
        identical = supports[left] == supports[right]
        eligible = pair_rank == 2 and not identical
        if eligible:
            category = "eligible"
            counts["eligible_pairs"] += 1
            if graph is None:
                graph = admissible.build_basis_exchange_graph(bases, size)
            classification = admissible.classify_admissible_pair(
                formula,
                graph,
                (left + 1, right + 1),
            )
            admissible_pair = classification["admissible"]
            rejection_reasons = classification["rejection_reasons"]
            if admissible_pair:
                counts["admissible_pairs"] += 1
        elif pair_rank == 2:
            category = "rank_two_identical"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = ["identical_primal_incidence"]
        elif identical:
            category = "rank_below_two_identical"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = [
                "rank_below_two",
                "identical_primal_incidence",
            ]
        else:
            category = "rank_below_two_distinct"
            counts[category] += 1
            admissible_pair = False
            rejection_reasons = ["rank_below_two"]
        exclusive_rows.append(
            {
                "ports": [left + 1, right + 1],
                "state_counts": state_counts,
                "kernel_columns_nonzero": nonzero,
                "kernel_pair_rank": pair_rank,
                "kernel_projectively_parallel": parallel,
                "primal_column_supports": [
                    list(supports[left]),
                    list(supports[right]),
                ],
                "primal_incidence_identical": identical,
                "category": category,
                "eligible": eligible,
                "ordinary_00_and_11_exist_by_duality": eligible,
                "two_sided_width_barrier": eligible,
                "admissible": admissible_pair,
                "rejection_reasons": rejection_reasons,
            }
        )
    return {
        "counts": {
            key: counts[key]
            for key in (
                "pair_cases_checked",
                "exclusive_pairs",
                "rank_below_two_distinct",
                "rank_below_two_identical",
                "rank_two_identical",
                "eligible_pairs",
                "admissible_pairs",
            )
        },
        "exclusive_pairs": exclusive_rows,
    }


def _analyze_formula(
    formula: Formula,
    source: dict[str, Any],
) -> dict[str, Any]:
    canonical = admissible.production.canonical_cubic_formula(formula)
    size = len(canonical)
    common: dict[str, Any] = {
        "formula_sha256": formula_digest(canonical),
        "variables": size,
        "source": source,
        "pair_opportunities": math.comb(size, 2),
    }
    connected = admissible.production.incidence_connected(canonical)
    if not connected:
        return {
            **common,
            "connected": False,
            "status": "disconnected",
        }

    system, vectors = admissible._kernel_data(canonical)
    nullity = len(system["free_columns_zero_based"])
    rank = size - nullity
    algebra = {
        **common,
        "connected": True,
        "rank": rank,
        "nullity": nullity,
    }
    if nullity < 2:
        return {
            **algebra,
            "status": "rank_dimension_excluded",
            "reason": "kernel_dimension_below_two",
        }

    census = admissible.enumerate_width_two_bases(canonical)
    census_record = {
        "basis_subsets_total": census["basis_subsets_total"],
        "basis_subsets_checked": census["basis_subsets_checked"],
        "independent_ground_bases": census["independent_ground_bases"],
        "width_two_basis_count": census["width_two_basis_count"],
        "exact": census["exact"],
        "status": census["status"],
        "reason": census["reason"],
    }
    if not census["exact"]:
        return {
            **algebra,
            "status": "inconclusive",
            "census": census_record,
        }
    if nullity == 2 and (
        census["width_two_basis_count"]
        != census["independent_ground_bases"]
    ):
        raise AssertionError(
            "a two-dimensional kernel produced a basis above width two"
        )
    if not census["width_two_bases"]:
        return {
            **algebra,
            "status": "not_applicable",
            "reason": "no_width_two_bases",
            "census": census_record,
        }

    bases = tuple(tuple(basis) for basis in census["width_two_bases"])
    profile = _pair_profile(canonical, bases, vectors)
    return {
        **algebra,
        "status": "exact",
        "census": census_record,
        "pair_profile": profile,
    }


def _summary(rows: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter(formulas=len(rows))
    for row in rows:
        if not row["connected"]:
            counts["disconnected_formulas"] += 1
            continue
        counts["connected_formulas"] += 1
        status = row["status"]
        if status == "rank_dimension_excluded":
            counts["rank_dimension_excluded_formulas"] += 1
        elif status == "inconclusive":
            counts["inconclusive_formulas"] += 1
        else:
            counts["exact_census_formulas"] += 1
            if row["nullity"] == 2:
                counts["nullity_two_all_bases_width_two"] += 1
            if status == "not_applicable":
                counts["no_width_two_formulas"] += 1
            else:
                counts["width_two_formulas"] += 1
                pair_counts = row["pair_profile"]["counts"]
                counts.update(pair_counts)
                if pair_counts["exclusive_pairs"]:
                    counts["formulas_with_exclusive_pairs"] += 1
    for key in (
        "connected_formulas",
        "disconnected_formulas",
        "rank_dimension_excluded_formulas",
        "exact_census_formulas",
        "inconclusive_formulas",
        "width_two_formulas",
        "no_width_two_formulas",
        "nullity_two_all_bases_width_two",
        "pair_cases_checked",
        "exclusive_pairs",
        "rank_below_two_distinct",
        "rank_below_two_identical",
        "rank_two_identical",
        "eligible_pairs",
        "admissible_pairs",
        "formulas_with_exclusive_pairs",
    ):
        counts[key] += 0
    return dict(sorted(counts.items()))


def _assert_seed(
    name: str,
    formula: Formula,
    ports_list: tuple[Ports, ...],
) -> Formula:
    canonical = admissible.production.canonical_cubic_formula(formula)
    if formula_digest(canonical) != neighborhood.FROZEN_SEED_DIGESTS[name]:
        raise AssertionError(f"{name}: frozen seed digest changed")
    if not admissible.production.incidence_connected(canonical):
        raise AssertionError(f"{name}: frozen seed is disconnected")
    census = admissible.enumerate_width_two_bases(canonical)
    if not census["exact"] or not census["width_two_bases"]:
        raise AssertionError(f"{name}: frozen seed lost its width-two census")
    graph = admissible.build_basis_exchange_graph(
        census["width_two_bases"],
        len(canonical),
    )
    expected = {
        "rank-two-identical-support": {
            (8, 10): (2, False, True),
        },
        "distinct-support-parallel": {
            (2, 9): (1, True, False),
            (4, 6): (1, True, False),
        },
    }
    for ports in ports_list:
        classification = admissible.classify_admissible_pair(
            canonical,
            graph,
            ports,
        )
        observed = (
            classification["kernel_pair_rank"],
            classification["kernel_projectively_parallel"],
            classification["primal_incidence_identical"],
        )
        if (
            not classification["exclusive_truth_states"]
            or observed != expected[name][ports]
        ):
            raise AssertionError(f"{name} {ports}: frozen defect changed")
    return canonical


def _assert_legal_switch(formula: Formula, spec: Switch) -> None:
    left_row, right_row, variable, partner = spec
    left = set(formula[left_row])
    right = set(formula[right_row])
    if not (
        left_row < right_row
        and variable in left - right
        and partner in right - left
    ):
        raise AssertionError(f"illegal or misoriented switch: {spec}")


def _neighbor_population() -> tuple[
    dict[str, dict[str, Any]],
    dict[str, int],
]:
    formulas: dict[str, dict[str, Any]] = {}
    seed_digests: set[str] = set()
    neighbor_digests: set[str] = set()
    counts: Counter[str] = Counter()
    for name, raw_formula, ports_list in neighborhood.SEED_SPECS:
        formula = _assert_seed(name, raw_formula, ports_list)
        base_digest = formula_digest(formula)
        seed_digests.add(base_digest)
        base = formulas.setdefault(
            base_digest,
            {"formula": formula, "is_seed": True, "sources": []},
        )
        base["is_seed"] = True
        base["sources"].append({"seed": name, "switch": None})
        specs = neighborhood.switch_source.switch_specs(formula)
        counts["raw_switch_specs"] += len(specs)
        for spec in specs:
            _assert_legal_switch(formula, spec)
            switched = neighborhood.switch_source.apply_spec(formula, spec)
            digest = formula_digest(switched)
            if digest == base_digest:
                counts["base_equivalent_specs"] += 1
                continue
            counts["nonbase_switch_specs"] += 1
            neighbor_digests.add(digest)
            entry = formulas.setdefault(
                digest,
                {"formula": switched, "is_seed": False, "sources": []},
            )
            entry["sources"].append({"seed": name, "switch": list(spec)})
    counts["seed_formulas"] = len(seed_digests)
    counts["distinct_nonbase_neighbors"] = len(neighbor_digests)
    counts["duplicate_nonbase_specs"] = (
        counts["nonbase_switch_specs"] - len(neighbor_digests)
    )
    counts["canonical_domain_formulas"] = len(formulas)
    accounting = dict(sorted(counts.items()))
    if accounting != EXPECTED_NEIGHBOR_SWITCH_ACCOUNTING:
        raise AssertionError("frozen neighbor switch accounting changed")
    return formulas, accounting


def build_neighbor_domain() -> dict[str, Any]:
    formulas, switch_accounting = _neighbor_population()
    rows = [
        _analyze_formula(
            formulas[digest]["formula"],
            {
                "kind": "frozen_seed_or_distance_one_neighbor",
                "is_seed": formulas[digest]["is_seed"],
                "sources": formulas[digest]["sources"],
            },
        )
        for digest in sorted(formulas)
    ]
    summary = _summary(rows)
    summary["pair_opportunities"] = sum(
        row["pair_opportunities"] for row in rows
    )
    summary["pair_cases_not_applicable"] = sum(
        row["pair_opportunities"]
        for row in rows
        if row["status"] == "not_applicable"
    )
    summary["pair_cases_inconclusive"] = sum(
        row["pair_opportunities"]
        for row in rows
        if row["status"] == "inconclusive"
    )
    summary = dict(sorted(summary.items()))
    if summary != EXPECTED_NEIGHBOR_SUMMARY:
        raise AssertionError(
            f"frozen all-pair neighbor summary changed: {summary}"
        )
    return {
        "name": "frozen_distance_one_all_pairs",
        "scope": {
            "seed_formulas": [
                {
                    "name": name,
                    "formula": [list(clause) for clause in formula],
                    "formula_sha256": neighborhood.FROZEN_SEED_DIGESTS[name],
                    "designated_ports": [list(ports) for ports in ports_list],
                }
                for name, formula, ports_list in neighborhood.SEED_SPECS
            ],
            "include_seeds": True,
            "include_every_distinct_nonbase_neighbor": True,
            "evaluate_every_original_column_pair": True,
            "switch_namespace": SWITCH_NAMESPACE,
        },
        "switch_accounting": switch_accounting,
        "summary": summary,
        "formulas": rows,
    }


def _random_simple_cubic_formula(
    rng: random.Random,
    size: int,
) -> tuple[Formula, int]:
    labels = list(range(1, size + 1))
    attempts = 0
    while True:
        attempts += 1
        permutations: list[list[int]] = []
        for _ in range(3):
            candidate = labels.copy()
            rng.shuffle(candidate)
            permutations.append(candidate)
        rows = tuple(
            sorted(
                tuple(
                    sorted(permutations[offset][row] for offset in range(3))
                )
                for row in range(size)
            )
        )
        if any(len(set(row)) != 3 for row in rows):
            continue
        if len(set(rows)) != size:
            continue
        return admissible.production.canonical_cubic_formula(rows), attempts


def generate_random_corpus(
    accepted_draws: int = RANDOM_ACCEPTED_DRAWS,
    seed: int = RANDOM_SEED,
    size: int = RANDOM_SIZE,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    rng = random.Random(seed)
    formulas: dict[str, dict[str, Any]] = {}
    configuration_attempts = 0
    stream = hashlib.sha256()
    for draw_index in range(accepted_draws):
        formula, attempts = _random_simple_cubic_formula(rng, size)
        configuration_attempts += attempts
        digest = formula_digest(formula)
        stream.update(f"{draw_index}:{attempts}:{digest}\n".encode("ascii"))
        entry = formulas.setdefault(
            digest,
            {
                "formula": formula,
                "first_draw_index": draw_index,
                "draw_multiplicity": 0,
            },
        )
        entry["draw_multiplicity"] += 1
    generation = {
        "variables": size,
        "accepted_draws": accepted_draws,
        "seed": seed,
        "configuration_attempts": configuration_attempts,
        "unique_formulas": len(formulas),
        "duplicate_draws": accepted_draws - len(formulas),
        "draw_stream_sha256": stream.hexdigest(),
        "draw_stream_record": "draw_index:configuration_attempts:formula_sha256\\n",
    }
    return formulas, generation


def build_random_domain(
    accepted_draws: int = RANDOM_ACCEPTED_DRAWS,
    seed: int = RANDOM_SEED,
    size: int = RANDOM_SIZE,
) -> dict[str, Any]:
    formulas, generation = generate_random_corpus(accepted_draws, seed, size)
    rows = [
        _analyze_formula(
            formulas[digest]["formula"],
            {
                "kind": "deterministic_simple_configuration_model",
                "first_draw_index": formulas[digest]["first_draw_index"],
                "draw_multiplicity": formulas[digest]["draw_multiplicity"],
            },
        )
        for digest in sorted(formulas)
    ]
    summary = _summary(rows)
    summary.update(
        {
            "accepted_draws": generation["accepted_draws"],
            "configuration_attempts": generation["configuration_attempts"],
            "unique_formulas": generation["unique_formulas"],
            "duplicate_draws": generation["duplicate_draws"],
            "census_attempted_formulas": sum(
                row["connected"] and row["nullity"] >= 2
                for row in rows
            ),
            "pair_opportunities_connected": sum(
                row["pair_opportunities"] for row in rows if row["connected"]
            ),
            "pair_opportunities_disconnected": sum(
                row["pair_opportunities"]
                for row in rows
                if not row["connected"]
            ),
            "pair_opportunities_rank_dimension_excluded": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "rank_dimension_excluded"
            ),
            "pair_cases_not_applicable": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "not_applicable"
            ),
            "pair_cases_inconclusive": sum(
                row["pair_opportunities"]
                for row in rows
                if row["status"] == "inconclusive"
            ),
        }
    )
    summary = dict(sorted(summary.items()))
    nullity_histogram = Counter(
        row["nullity"] for row in rows if row["connected"]
    )
    serialized_histogram = {
        str(key): nullity_histogram[key] for key in sorted(nullity_histogram)
    }
    if (
        accepted_draws == RANDOM_ACCEPTED_DRAWS
        and seed == RANDOM_SEED
        and size == RANDOM_SIZE
    ):
        if summary != EXPECTED_RANDOM_SUMMARY:
            raise AssertionError("frozen random corpus summary changed")
        if serialized_histogram != EXPECTED_RANDOM_NULLITY_HISTOGRAM:
            raise AssertionError("frozen random nullity histogram changed")
    return {
        "name": "deterministic_simple_cubic_corpus",
        "scope": {
            "generator": (
                "three independently shuffled permutations; reject repeated "
                "variables within a row and duplicate clause rows"
            ),
            "connected_formula_requirement": True,
            "nullity_zero_or_one": (
                "rank-dimension excluded because no kernel-column pair can "
                "have rank two"
            ),
            "nullity_at_least_two": "complete exact ground-basis census",
            "stopping_rule": "scan every accepted draw",
            "distributional_claim": "none",
        },
        "generation": generation,
        "nullity_histogram_connected": serialized_histogram,
        "summary": summary,
        "formulas": rows,
    }


def build_receipt() -> dict[str, Any]:
    controls = synthetic_controls()
    neighbor_domain = build_neighbor_domain()
    random_domain = build_random_domain()
    domains = [neighbor_domain, random_domain]
    eligible_pairs = sum(
        domain["summary"]["eligible_pairs"] for domain in domains
    )
    admissible_pairs = sum(
        domain["summary"]["admissible_pairs"] for domain in domains
    )
    if eligible_pairs:
        result = "eligible_cubic_width_barrier_found"
    else:
        result = "no_eligible_pair_in_two_bounded_cubic_domains"
    return {
        "schema": SCHEMA,
        "definitions": {
            "ground_basis": (
                "a basis selected from the original kernel-coordinate columns"
            ),
            "basis_width": (
                "maximum coordinate-support size of any original kernel column "
                "relative to the selected ground basis"
            ),
            "exclusive_pair": (
                "the complete width-two basis family realizes only 01 and 10, "
                "with both states nonempty"
            ),
            "projective_parallel_convention": (
                "true only for two nonzero columns with equal normalized "
                "projective keys; zero columns are tracked separately"
            ),
            "eligible_pair": (
                "exclusive, kernel pair rank two, and distinct primal incidence "
                "columns; nonzero and nonparallel follow from rank two"
            ),
            "dual_basis_escape_lemma": (
                "kernel pair rank two extends to an ordinary 11 ground basis; "
                "distinct nonzero equal-weight primal columns extend to a dual "
                "basis whose complement is an ordinary 00 ground basis"
            ),
            "two_sided_width_barrier": (
                "ordinary 00 and 11 bases exist but every width-two ground basis "
                "has state 01 or 10"
            ),
            "pair_namespace": PAIR_NAMESPACE,
        },
        "synthetic_controls": controls,
        "domains": domains,
        "summary": {
            "bounded_domains": len(domains),
            "cubic_formulas": sum(
                domain["summary"]["formulas"] for domain in domains
            ),
            "pair_cases_checked": sum(
                domain["summary"]["pair_cases_checked"] for domain in domains
            ),
            "exclusive_pairs": sum(
                domain["summary"]["exclusive_pairs"] for domain in domains
            ),
            "eligible_pairs": eligible_pairs,
            "admissible_pairs": admissible_pairs,
            "synthetic_positive_barrier_fires": controls[
                "positive_general_vector_anchor"
            ]["two_sided_width_barrier"],
            "synthetic_negative_barrier_rejected": not controls[
                "negative_all_bases_width_two_anchor"
            ]["two_sided_width_barrier"],
        },
        "assessment": {
            "result": result,
            "exclusive_pair_degeneracy_conjecture": "not established",
            "general_vector_impossibility": "falsified by synthetic anchor",
            "cubic_specific_impossibility": "not established",
            "p_equals_np": "not established",
            "scope": (
                "complete only for the frozen distance-one all-pair domain and "
                "the deterministic 20,000-draw simple n=12 corpus"
            ),
        },
    }


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema": receipt["schema"],
                "summary": receipt["summary"],
                "assessment": receipt["assessment"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
