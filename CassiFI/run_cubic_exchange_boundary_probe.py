"""Measure exact exchange boundaries for exclusive cubic width-two pairs.

This probe takes the five exclusive pairs found by the admissible-cell screen and
records every 01-to-10 exchange edge, including the exact one-dimensional kernel
relation on the common basis plus the two exchanged columns.  It verifies the
local identity that a crossing edge removes the right port and adds the left
port; it does not claim that the crossing itself causes a global shadow or
alternate partition.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import run_cubic_admissible_cell_probe as admissible

OUTPUT = Path("_diag/cubic_exchange_boundary_probe.json")
SCHEMA = "cassifi.cubic-exchange-boundary-probe.v1"

Formula = tuple[tuple[int, int, int], ...]
Vector = tuple[Fraction, ...]

TRUTH_STATES = admissible.TRUTH_STATES
PORT_NAMESPACE = admissible.PORT_NAMESPACE
VERTEX_NAMESPACE = admissible.VERTEX_NAMESPACE


FROZEN_FIXTURE_DIGESTS = dict(admissible.FROZEN_FIXTURE_DIGESTS)


def formula_digest(formula: Sequence[Sequence[int]]) -> str:
    canonical = admissible.production.canonical_cubic_formula(formula)
    return hashlib.sha256(
        json.dumps(canonical, separators=(",", ":")).encode("ascii")
    ).hexdigest()


def _fraction_text(value: Fraction) -> str:
    return str(value)


def _rref(matrix: Sequence[Sequence[Fraction]]) -> tuple[list[list[Fraction]], tuple[int, ...]]:
    values = [list(row) for row in matrix]
    row_count = len(values)
    column_count = len(values[0]) if values else 0
    pivots: list[int] = []
    pivot_row = 0
    for column in range(column_count):
        source = next(
            (
                row
                for row in range(pivot_row, row_count)
                if values[row][column] != 0
            ),
            None,
        )
        if source is None:
            continue
        values[pivot_row], values[source] = values[source], values[pivot_row]
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        for row in range(row_count):
            if row == pivot_row:
                continue
            factor = values[row][column]
            if factor:
                values[row] = [
                    left - factor * right
                    for left, right in zip(values[row], values[pivot_row])
                ]
        pivots.append(column)
        pivot_row += 1
        if pivot_row == row_count:
            break
    return values, tuple(pivots)


def _null_relation(vectors: Sequence[Vector]) -> tuple[Fraction, ...]:
    if not vectors:
        raise ValueError("cannot derive a relation from no vectors")
    dimension = len(vectors[0])
    matrix = [
        [vectors[column][row] for column in range(len(vectors))]
        for row in range(dimension)
    ]
    reduced, pivots = _rref(matrix)
    if len(pivots) != len(vectors) - 1:
        raise ValueError("exchange relation is not one-dimensional")
    free = next(column for column in range(len(vectors)) if column not in pivots)
    relation = [Fraction(0) for _ in vectors]
    relation[free] = Fraction(1)
    for row, pivot in enumerate(pivots):
        relation[pivot] = -reduced[row][free]
    first = next(value for value in relation if value)
    return tuple(value / first for value in relation)


def _boundary_record(
    formula: Formula,
    ports: tuple[int, int],
) -> dict[str, Any]:
    census = admissible.enumerate_width_two_bases(formula)
    if not census["exact"]:
        return {
            "status": "inconclusive",
            "reason": census.get("reason", "basis_subset_cap"),
            "formula": [list(clause) for clause in formula],
            "formula_sha256": formula_digest(formula),
            "ports": list(ports),
            "census": census,
        }
    graph = admissible.build_basis_exchange_graph(
        census["width_two_bases"], len(formula)
    )
    classification = admissible.classify_admissible_pair(formula, graph, ports)
    if not classification["exclusive_truth_states"]:
        raise AssertionError(f"{ports}: expected an exclusive pair")
    _, vectors = admissible._kernel_data(formula)
    states = tuple(
        admissible._state_signature(tuple(basis), ports)
        for basis in graph["vertices"]
    )
    boundary_edges: list[dict[str, Any]] = []
    for left_vertex, right_vertex in graph["edges"]:
        left_state = states[left_vertex]
        right_state = states[right_vertex]
        if {left_state, right_state} != set(TRUTH_STATES):
            continue
        if left_state == "01":
            from_vertex, to_vertex = left_vertex, right_vertex
        else:
            from_vertex, to_vertex = right_vertex, left_vertex
        from_basis = tuple(graph["vertices"][from_vertex])
        to_basis = tuple(graph["vertices"][to_vertex])
        removed = tuple(sorted(set(from_basis) - set(to_basis)))
        added = tuple(sorted(set(to_basis) - set(from_basis)))
        common = tuple(sorted(set(from_basis) & set(to_basis)))
        if removed != (ports[1],) or added != (ports[0],):
            raise AssertionError(
                f"{ports}: boundary edge does not remove right and add left: "
                f"{from_basis} -> {to_basis}"
            )
        ordered_columns = common + (ports[0], ports[1])
        relation = _null_relation(
            tuple(vectors[column - 1] for column in ordered_columns)
        )
        relation_by_column = {
            str(column): _fraction_text(coefficient)
            for column, coefficient in zip(ordered_columns, relation)
        }
        boundary_edges.append(
            {
                "edge": [left_vertex, right_vertex],
                "from_state": "01",
                "to_state": "10",
                "from_vertex": from_vertex,
                "to_vertex": to_vertex,
                "from_basis": list(from_basis),
                "to_basis": list(to_basis),
                "common_basis": list(common),
                "removed_column": ports[1],
                "added_column": ports[0],
                "symmetric_difference": [ports[0], ports[1]],
                "ordered_relation_columns": list(ordered_columns),
                "kernel_relation": relation_by_column,
                "port_relation_coefficients_nonzero": (
                    relation_by_column[str(ports[0])] != "0"
                    and relation_by_column[str(ports[1])] != "0"
                ),
            }
        )
    shadows = classification["auxiliary_column_shadows"]
    alternates = classification["alternate_pair_partitions"]
    reasons = classification["rejection_reasons"]
    return {
        "status": "exact",
        "formula": [list(clause) for clause in formula],
        "formula_sha256": formula_digest(formula),
        "variables": len(formula),
        "ports": list(ports),
        "census": census,
        "exchange_graph": graph,
        "state_counts": classification["signature_counts"],
        "port_membership_signatures": classification["port_membership_signatures"],
        "truth_fibres": classification["exchange"]["truth_fibres"],
        "cross_state_edge_count": classification["exchange"]["cross_state_edge_count"],
        "boundary_edge_count": len(boundary_edges),
        "boundary_edges": boundary_edges,
        "auxiliary_column_shadows": shadows,
        "alternate_pair_partitions": alternates,
        "kernel_pair_rank": classification["kernel_pair_rank"],
        "kernel_projectively_parallel": classification["kernel_projectively_parallel"],
        "primal_column_supports": classification["primal_column_supports"],
        "primal_incidence_identical": classification["primal_incidence_identical"],
        "rejection_reasons": reasons,
        "boundary_port_swap_identity": all(
            edge["removed_column"] == ports[1]
            and edge["added_column"] == ports[0]
            and edge["symmetric_difference"] == list(ports)
            for edge in boundary_edges
        ),
        "boundary_relation_identity": all(
            edge["port_relation_coefficients_nonzero"] for edge in boundary_edges
        ),
    }


def build_receipt() -> dict[str, Any]:
    fixture_rows: list[dict[str, Any]] = []
    source_fixtures = 0
    applicable_fixtures = 0
    not_applicable_fixtures = 0
    candidate_pairs_total = 0
    candidate_pairs_attempted = 0
    candidate_pairs_checked = 0
    not_applicable_candidate_pairs = 0
    exclusive_pairs = 0
    boundary_edges = 0
    all_port_swaps = True
    all_relations_nonzero = True
    for name, role, formula in admissible.fixture_specs():
        source_fixtures += 1
        canonical = admissible.production.canonical_cubic_formula(formula)
        digest = formula_digest(canonical)
        if digest != FROZEN_FIXTURE_DIGESTS[name]:
            raise AssertionError(f"{name}: frozen fixture digest changed")
        pair_total = math.comb(len(canonical), 2)
        candidate_pairs_total += pair_total
        census = admissible.enumerate_width_two_bases(canonical)
        if not census["exact"]:
            raise AssertionError(f"{name}: frozen basis census is inconclusive")
        if census["status"] != "exact":
            not_applicable_fixtures += 1
            not_applicable_candidate_pairs += pair_total
            continue
        applicable_fixtures += 1
        graph = admissible.build_basis_exchange_graph(
            census["width_two_bases"], len(canonical)
        )
        classifications = [
            admissible.classify_admissible_pair(canonical, graph, ports)
            for ports in itertools.combinations(range(1, len(canonical) + 1), 2)
        ]
        candidate_pairs_attempted += len(classifications)
        candidate_pairs_checked += len(classifications)
        exclusive = [
            tuple(row["ports"])
            for row in classifications
            if row["exclusive_truth_states"]
        ]
        if not exclusive:
            continue
        boundaries = [_boundary_record(canonical, ports) for ports in exclusive]
        for row in boundaries:
            exclusive_pairs += 1
            boundary_edges += row["boundary_edge_count"]
            all_port_swaps = all_port_swaps and row["boundary_port_swap_identity"]
            all_relations_nonzero = (
                all_relations_nonzero and row["boundary_relation_identity"]
            )
        fixture_rows.append(
            {
                "name": name,
                "role": role,
                "formula": [list(clause) for clause in canonical],
                "formula_sha256": digest,
                "variables": len(canonical),
                "census": census,
                "exclusive_pairs": [list(pair) for pair in exclusive],
                "boundary_records": boundaries,
            }
        )
    pair_scan_complete = (
        candidate_pairs_attempted == candidate_pairs_checked
        and candidate_pairs_total
        == candidate_pairs_checked + not_applicable_candidate_pairs
    )
    result = (
        "boundary_identity_verified_on_frozen_exclusive_pairs"
        if (
            pair_scan_complete
            and exclusive_pairs > 0
            and boundary_edges > 0
            and all_port_swaps
            and all_relations_nonzero
        )
        else "inconclusive_boundary_identity"
    )
    return {
        "schema": SCHEMA,
        "definition": {
            "port_namespace": PORT_NAMESPACE,
            "vertex_namespace": VERTEX_NAMESPACE,
            "boundary_edge": (
                "an exchange-graph edge whose endpoint states are 01 and 10 for "
                "one exclusive pair"
            ),
            "boundary_orientation": (
                "each boundary edge is normalized from state 01 to state 10; "
                "the right port is removed and the left port is added"
            ),
            "kernel_relation": (
                "the unique exact dependence among the common basis columns and "
                "the two exchanged port columns, normalized by its first nonzero "
                "coefficient"
            ),
            "scope": (
                "finite exchange-boundary measurement on the frozen exclusive "
                "pairs; it does not claim that a boundary edge causes a global "
                "auxiliary shadow or alternate partition"
            ),
        },
        "frozen_domain": {
            "fixture_names": [name for name, _, _ in admissible.fixture_specs()],
            "fixture_sha256": FROZEN_FIXTURE_DIGESTS,
            "exclusive_pair_source": (
                "all original-column pairs are reconstructed and filtered by "
                "the exclusive 01/10 state predicate"
            ),
            "candidate_pair_accounting": (
                "total counts every original-column pair in the frozen fixtures; "
                "attempted and checked count only exact width-two fixtures; "
                "pairs in exact no-width-two fixtures are not applicable"
            ),
        },
        "fixtures": fixture_rows,
        "summary": {
            "source_fixtures": source_fixtures,
            "applicable_fixtures": applicable_fixtures,
            "not_applicable_fixtures": not_applicable_fixtures,
            "candidate_pairs_total": candidate_pairs_total,
            "candidate_pairs_attempted": candidate_pairs_attempted,
            "candidate_pairs_checked": candidate_pairs_checked,
            "not_applicable_candidate_pairs": not_applicable_candidate_pairs,
            "candidate_pair_scan_complete": pair_scan_complete,
            "fixtures_with_exclusive_pairs": len(fixture_rows),
            "exclusive_pairs": exclusive_pairs,
            "boundary_edges": boundary_edges,
            "all_boundary_port_swaps": all_port_swaps,
            "all_boundary_relations_nonzero": all_relations_nonzero,
        },
        "assessment": {
            "result": result,
            "scope": (
                "five exclusive pairs in the six frozen connected cubic controls"
            ),
            "interpretation": (
                "the boundary identity is verified on the frozen pairs; this "
                "does not prove a universal exchange-boundary theorem"
            ),
            "global_admissible_cell_theorem": "not established",
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