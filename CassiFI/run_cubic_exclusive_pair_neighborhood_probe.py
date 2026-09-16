"""Exhaust the distance-one switch neighborhoods of three exclusive near-misses.

Two frozen connected cubic formulas supply three designated exclusive pairs.
Every legal degree-preserving incidence two-switch is generated, canonicalized,
and deduplicated.  Every distinct non-base neighbor is checked for connectivity,
a complete internal width-two basis census, and the designated pair
classifications.  The search is finite evidence: a null result neither proves
the exclusive-pair degeneracy conjecture nor classifies a complexity problem.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import run_cubic_admissible_cell_probe as admissible
import run_switch_neighborhood_probe as switch_source

OUTPUT = Path("_diag/cubic_exclusive_pair_neighborhood_probe.json")
SCHEMA = "cassifi.cubic-exclusive-pair-neighborhood-probe.v1"
MAX_BASIS_SUBSETS = admissible.MAX_BASIS_SUBSETS

Formula = tuple[tuple[int, int, int], ...]
Ports = tuple[int, int]
Switch = tuple[int, int, int, int]

RANK_TWO_IDENTICAL_SUPPORT: Formula = (
    (1, 2, 12),
    (1, 6, 11),
    (1, 11, 12),
    (2, 3, 6),
    (2, 3, 12),
    (3, 8, 10),
    (4, 5, 9),
    (4, 6, 9),
    (4, 8, 10),
    (5, 7, 9),
    (5, 7, 11),
    (7, 8, 10),
)

DISTINCT_SUPPORT_PARALLEL: Formula = (
    (1, 4, 5),
    (1, 4, 11),
    (1, 6, 12),
    (2, 3, 10),
    (2, 4, 7),
    (2, 6, 7),
    (3, 5, 9),
    (3, 9, 11),
    (5, 8, 12),
    (6, 7, 9),
    (8, 10, 11),
    (8, 10, 12),
)

SEED_SPECS: tuple[tuple[str, Formula, tuple[Ports, ...]], ...] = (
    (
        "rank-two-identical-support",
        RANK_TWO_IDENTICAL_SUPPORT,
        ((8, 10),),
    ),
    (
        "distinct-support-parallel",
        DISTINCT_SUPPORT_PARALLEL,
        ((2, 9), (4, 6)),
    ),
)

FROZEN_SEED_DIGESTS = {
    "rank-two-identical-support": (
        "a08c300f3fcc70b791c37bd6e3999e0656f70b5efdc2d68e4b8da89c2642c859"
    ),
    "distinct-support-parallel": (
        "c26d0346c837aa4af28c0f4e687eff573ee441abbc3d340a3e7785e714bac37e"
    ),
}


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = admissible.production.canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _compact_census(census: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": census["status"],
        "reason": census["reason"],
        "exact": census["exact"],
        "maximum_subsets": census["maximum_subsets"],
        "rank": census["rank"],
        "nullity": census["nullity"],
        "basis_subsets_total": census["basis_subsets_total"],
        "basis_subsets_checked": census["basis_subsets_checked"],
        "independent_ground_bases": census["independent_ground_bases"],
        "width_two_basis_count": census["width_two_basis_count"],
    }


def _eligible(classification: dict[str, Any]) -> bool:
    return (
        classification["exclusive_truth_states"]
        and classification["kernel_columns_nonzero"]
        and classification["kernel_pair_rank"] == 2
        and not classification["kernel_projectively_parallel"]
        and not classification["primal_incidence_identical"]
    )


def _compact_pair(
    classification: dict[str, Any], ports: Ports
) -> dict[str, Any]:
    exchange = classification["exchange"]
    return {
        "status": "exact",
        "ports": list(ports),
        "state_counts": classification["signature_counts"],
        "exclusive": classification["exclusive_truth_states"],
        "eligible": _eligible(classification),
        "admissible": classification["admissible"],
        "kernel_columns_nonzero": classification["kernel_columns_nonzero"],
        "kernel_pair_rank": classification["kernel_pair_rank"],
        "kernel_projectively_parallel": classification[
            "kernel_projectively_parallel"
        ],
        "primal_column_supports": classification["primal_column_supports"],
        "primal_incidence_identical": classification[
            "primal_incidence_identical"
        ],
        "full_exchange_graph_connected": exchange["full_graph_connected"],
        "truth_fibres_connected": {
            state: exchange["truth_fibres"][state]["connected"]
            for state in ("01", "10")
        },
        "cross_state_edge_count": exchange["cross_state_edge_count"],
        "single_exchange_truth_flip": exchange["single_exchange_truth_flip"],
        "auxiliary_column_shadow_count": len(
            classification["auxiliary_column_shadows"]
        ),
        "alternate_pair_partition_count": len(
            classification["alternate_pair_partitions"]
        ),
        "rejection_reasons": classification["rejection_reasons"],
    }


def _unavailable_pair(ports: Ports, status: str, reason: str) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "ports": list(ports),
    }


def _baseline_record(formula: Formula, ports_list: tuple[Ports, ...]) -> dict[str, Any]:
    census = admissible.enumerate_width_two_bases(formula)
    if not census["exact"] or census["status"] != "exact":
        raise AssertionError("frozen near-miss seed lacks an exact width-two census")
    graph = admissible.build_basis_exchange_graph(
        census["width_two_bases"], len(formula)
    )
    return {
        "census": _compact_census(census),
        "pairs": [
            _compact_pair(
                admissible.classify_admissible_pair(formula, graph, ports),
                ports,
            )
            for ports in ports_list
        ],
    }


def _neighbor_record(
    formula: Formula,
    representative: Switch,
    multiplicity: int,
    ports_list: tuple[Ports, ...],
) -> dict[str, Any]:
    connected = admissible.production.incidence_connected(formula)
    record: dict[str, Any] = {
        "formula_sha256": formula_digest(formula),
        "representative_switch": list(representative),
        "switch_multiplicity": multiplicity,
        "connected": connected,
    }
    if not connected:
        record["census"] = None
        record["pairs"] = [
            _unavailable_pair(ports, "not_applicable", "disconnected_neighbor")
            for ports in ports_list
        ]
        return record
    census = admissible.enumerate_width_two_bases(formula)
    record["census"] = _compact_census(census)
    if not census["exact"]:
        record["pairs"] = [
            _unavailable_pair(ports, "inconclusive", census["reason"])
            for ports in ports_list
        ]
        return record
    if census["status"] != "exact":
        record["pairs"] = [
            _unavailable_pair(ports, "not_applicable", census["reason"])
            for ports in ports_list
        ]
        return record
    graph = admissible.build_basis_exchange_graph(
        census["width_two_bases"], len(formula)
    )
    record["pairs"] = [
        _compact_pair(
            admissible.classify_admissible_pair(formula, graph, ports),
            ports,
        )
        for ports in ports_list
    ]
    return record


def _seed_record(
    name: str,
    raw_formula: Formula,
    ports_list: tuple[Ports, ...],
) -> dict[str, Any]:
    formula = admissible.production.canonical_cubic_formula(raw_formula)
    digest = formula_digest(formula)
    if digest != FROZEN_SEED_DIGESTS[name]:
        raise AssertionError(f"{name}: frozen seed digest changed")
    specs = switch_source.switch_specs(formula)
    base_digest = formula_digest(formula)
    populations: dict[str, dict[str, Any]] = {}
    base_equivalent_specs = 0
    for spec in specs:
        neighbor = switch_source.apply_spec(formula, spec)
        neighbor_digest = formula_digest(neighbor)
        if neighbor_digest == base_digest:
            base_equivalent_specs += 1
            continue
        population = populations.setdefault(
            neighbor_digest,
            {
                "formula": neighbor,
                "representative": spec,
                "multiplicity": 0,
            },
        )
        population["multiplicity"] += 1
    neighbors = [
        _neighbor_record(
            populations[key]["formula"],
            populations[key]["representative"],
            populations[key]["multiplicity"],
            ports_list,
        )
        for key in sorted(populations)
    ]
    counts: Counter[str] = Counter(
        switch_specs=len(specs),
        base_equivalent_specs=base_equivalent_specs,
        duplicate_nonbase_specs=(
            len(specs) - base_equivalent_specs - len(neighbors)
        ),
        distinct_neighbors=len(neighbors),
        connected_neighbors=0,
        disconnected_neighbors=0,
        exact_censuses=0,
        inconclusive_censuses=0,
        width_two_neighbors=0,
        no_width_two_neighbors=0,
        designated_pair_cases=len(neighbors) * len(ports_list),
        pair_cases_checked=0,
        pair_cases_not_applicable=0,
        pair_cases_inconclusive=0,
        exclusive_pairs=0,
        eligible_pairs=0,
        admissible_pairs=0,
    )
    rejection_combinations: Counter[str] = Counter()
    nullity_histogram: Counter[str] = Counter()
    for neighbor in neighbors:
        if neighbor["connected"]:
            counts["connected_neighbors"] += 1
        else:
            counts["disconnected_neighbors"] += 1
        census = neighbor["census"]
        if census is not None:
            if census["exact"]:
                counts["exact_censuses"] += 1
                nullity_histogram[str(census["nullity"])] += 1
            else:
                counts["inconclusive_censuses"] += 1
            if census["status"] == "exact":
                counts["width_two_neighbors"] += 1
            elif census["exact"]:
                counts["no_width_two_neighbors"] += 1
        for pair in neighbor["pairs"]:
            if pair["status"] == "inconclusive":
                counts["pair_cases_inconclusive"] += 1
                continue
            if pair["status"] != "exact":
                counts["pair_cases_not_applicable"] += 1
                continue
            counts["pair_cases_checked"] += 1
            if not pair["exclusive"]:
                continue
            counts["exclusive_pairs"] += 1
            reasons = pair["rejection_reasons"]
            rejection_combinations["+".join(reasons) or "admissible"] += 1
            if pair["eligible"]:
                counts["eligible_pairs"] += 1
            if pair["admissible"]:
                counts["admissible_pairs"] += 1
    pair_accounting_complete = (
        counts["designated_pair_cases"]
        == counts["pair_cases_checked"]
        + counts["pair_cases_not_applicable"]
        + counts["pair_cases_inconclusive"]
    )
    switch_accounting_complete = (
        counts["switch_specs"]
        == counts["base_equivalent_specs"]
        + counts["duplicate_nonbase_specs"]
        + counts["distinct_neighbors"]
    )
    return {
        "name": name,
        "formula": [list(clause) for clause in formula],
        "formula_sha256": digest,
        "ports": [list(ports) for ports in ports_list],
        "baseline": _baseline_record(formula, ports_list),
        "neighbors": neighbors,
        "counts": dict(sorted(counts.items())),
        "nullity_histogram": dict(sorted(nullity_histogram.items())),
        "exclusive_rejection_combinations": dict(
            sorted(rejection_combinations.items())
        ),
        "switch_accounting_complete": switch_accounting_complete,
        "pair_accounting_complete": pair_accounting_complete,
    }


def build_receipt() -> dict[str, Any]:
    seeds = [
        _seed_record(name, formula, ports)
        for name, formula, ports in SEED_SPECS
    ]
    summary_fields = (
        "switch_specs",
        "base_equivalent_specs",
        "duplicate_nonbase_specs",
        "distinct_neighbors",
        "connected_neighbors",
        "disconnected_neighbors",
        "exact_censuses",
        "inconclusive_censuses",
        "width_two_neighbors",
        "no_width_two_neighbors",
        "designated_pair_cases",
        "pair_cases_checked",
        "pair_cases_not_applicable",
        "pair_cases_inconclusive",
        "exclusive_pairs",
        "eligible_pairs",
        "admissible_pairs",
    )
    summary = {
        field: sum(seed["counts"][field] for seed in seeds)
        for field in summary_fields
    }
    summary.update(
        {
            "seed_formulas": len(seeds),
            "designated_pairs": sum(len(seed["ports"]) for seed in seeds),
            "switch_accounting_complete": all(
                seed["switch_accounting_complete"] for seed in seeds
            ),
            "pair_accounting_complete": all(
                seed["pair_accounting_complete"] for seed in seeds
            ),
        }
    )
    exact = (
        summary["switch_accounting_complete"]
        and summary["pair_accounting_complete"]
        and summary["inconclusive_censuses"] == 0
        and summary["pair_cases_inconclusive"] == 0
    )
    if not exact:
        result = "inconclusive_distance_one_search"
    elif summary["eligible_pairs"]:
        result = "eligible_pair_found"
    else:
        result = "finite_distance_one_search_null"
    return {
        "schema": SCHEMA,
        "definition": {
            "switch": (
                "a legal degree-preserving exchange of one distinct variable "
                "between two clause rows; tuple entries are zero-based left row, "
                "zero-based right row, left variable, right variable"
            ),
            "neighbor_scope": (
                "every distinct non-base canonical formula reachable by exactly "
                "one legal switch from either frozen seed"
            ),
            "designated_pair_case": (
                "one frozen port pair evaluated on one distinct neighbor; exact, "
                "not_applicable, and inconclusive cases are all counted"
            ),
            "eligible_pair": (
                "exclusive with nonzero rank-two nonparallel kernel columns and "
                "distinct primal incidence columns"
            ),
            "admissible_pair": (
                "eligible and satisfying the complete exchange, truth-fibre, "
                "auxiliary-shadow, and alternate-partition certificate"
            ),
            "basis_subset_cap": MAX_BASIS_SUBSETS,
        },
        "frozen_domain": {
            "seed_names": [name for name, _, _ in SEED_SPECS],
            "seed_sha256": FROZEN_SEED_DIGESTS,
            "distance": 1,
            "search_complete": True,
        },
        "seeds": seeds,
        "summary": summary,
        "assessment": {
            "result": result,
            "scope": (
                "complete canonical distance-one switch neighborhoods of two "
                "frozen formulas and three designated exclusive pairs"
            ),
            "exclusive_pair_degeneracy_conjecture": "not established",
            "complexity_classification": "not established",
            "p_equals_np": "not established",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    arguments = parser.parse_args()
    receipt = build_receipt()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema": receipt["schema"],
                "result": receipt["assessment"]["result"],
                **receipt["summary"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
