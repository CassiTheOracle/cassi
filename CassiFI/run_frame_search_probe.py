"""Complete non-enumerative frame decision for cubic incidence duals.

The frame-separation probe decides the width question by enumerating all
``C(n, nullity)`` complementary free subsets.  This runner decides the same
question with a search over the *classes* of the dual representation: pick the
first class not yet covered by pairwise joins of the chosen classes, branch over
every class pair whose join covers it, and stop when every class is covered by
an independent chosen set that extends to a ground basis.  A success is a
width-two certificate (re-verified here); an exhausted search with no success is
a proof that no ground basis frames the dual, hence ``omega >= 3``.

The composed families are connected chains of the two width-three all-bases
controls joined by incidence two-switches, one switch per consecutive pair of
copies.  At ``t`` copies the chain has ``12 t`` or ``15 t`` elements and nullity
``2 t + 1``: the largest instance here has ``n = 60``, ``k = 9``, where the
census would need ``C(60, 9) ~ 1.5e10`` free subsets while the search exhausts
its subtree at tens of thousands of nodes.

No hardness claim: the search is complete but exponential in the worst case, and
the families are constructed, not arbitrary.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_frame_separation_probe as fsp
import run_mixed_schaefer_frame_obstruction as runner
from cubic_kernel_decision import canonical_cubic_formula
from run_cubic_kernel_analysis import ALL_BASES_TERNARY_SAT, ALL_BASES_TERNARY_UNSAT

OUTPUT = Path("_diag/frame_search_probe.json")
SCHEMA = "cassifi.frame-search-probe.v1"
NODE_CAP = 200_000
SWITCH_SAMPLE = 24

CONTROL_EXPECTATIONS: dict[str, str] = {
    "support-three-sat-n9": "frame",
    "support-three-unsat-n15": "frame",
    "greedy-exchange-trap-sat-n9": "frame",
    "all-bases-ternary-sat-n12": "no_frame",
    "all-bases-ternary-unsat-n15": "no_frame",
}

SUM_EXPECTATIONS: dict[str, str] = {
    "sum-three-sat+three-sat-n18": "frame",
    "sum-three-sat+three-unsat-n24": "frame",
    "sum-three-sat+bases-sat-n21": "no_frame",
    "sum-bases-sat+bases-sat-n24": "no_frame",
    "sum-bases-sat+bases-unsat-n27": "no_frame",
}


def rank_of(rows: Sequence[Sequence[int]]) -> int:
    """Exact rank by fraction-free integer elimination."""

    matrix = [[int(value) for value in row] for row in rows if any(row)]
    if not matrix:
        return 0
    width = len(matrix[0])
    rank = 0
    for column in range(width):
        pivot = next(
            (row for row in range(rank, len(matrix)) if matrix[row][column]), None
        )
        if pivot is None:
            continue
        matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
        pivot_value = matrix[rank][column]
        for row in range(rank + 1, len(matrix)):
            if not matrix[row][column]:
                continue
            factor = matrix[row][column]
            matrix[row] = [
                a * pivot_value - b * factor
                for a, b in zip(matrix[row], matrix[rank], strict=True)
            ]
            common = 0
            for value in matrix[row]:
                common = math.gcd(common, abs(value))
            if common > 1:
                matrix[row] = [value // common for value in matrix[row]]
        rank += 1
        if rank == len(matrix):
            break
    return rank


def in_span(left: Sequence[int], right: Sequence[int], point: Sequence[int]) -> bool:
    """Dimension-general membership test for the join of two classes."""

    return rank_of((left, right, point)) <= 2


def span_masks(
    classes: Sequence[tuple[int, ...]],
) -> tuple[list[int], list[list[int]], int]:
    """Class-pair cover masks: which classes each pair join spans."""

    count = len(classes)
    pair_masks: list[int] = []
    pairs_by_target: list[list[int]] = [[] for _ in range(count)]
    for left, right in itertools.combinations(range(count), 2):
        mask = (1 << left) | (1 << right)
        for target in range(count):
            if in_span(classes[left], classes[right], classes[target]):
                mask |= 1 << target
        index = len(pair_masks)
        pair_masks.append(mask)
        for target in range(count):
            if mask >> target & 1:
                pairs_by_target[target].append(index)
    return pair_masks, pairs_by_target, (1 << count) - 1


def frame_search(
    classes: Sequence[tuple[int, ...]], rank: int, node_cap: int = NODE_CAP
) -> tuple[list[int] | None, int, bool]:
    """Complete width-two frame search over dual classes.

    Returns ``(chosen class indices, nodes, capped)``.  A returned list is an
    independent covering set; ``None`` with ``capped`` false means no ground
    basis frames the dual, so ``omega >= 3``.
    """

    pair_masks, pairs_by_target, full = span_masks(classes)
    pair_elements = list(itertools.combinations(range(len(classes)), 2))
    pair_bits = [
        ((1 << left) | (1 << right), pair_masks[index])
        for index, (left, right) in enumerate(pair_elements)
    ]
    nodes = 0
    capped = False

    def search(chosen_mask: int, chosen: list[int]) -> list[int] | None:
        nonlocal nodes, capped
        nodes += 1
        if nodes > node_cap:
            capped = True
            return None
        covered = 0
        for endpoints, mask in pair_bits:
            if chosen_mask & endpoints == endpoints:
                covered |= mask
        uncovered = full & ~covered
        if not uncovered:
            return chosen if rank_of([classes[index] for index in chosen]) == len(chosen) else None
        if len(chosen) == rank:
            return None
        target = (uncovered & -uncovered).bit_length() - 1
        for pair_index in pairs_by_target[target]:
            left, right = pair_elements[pair_index]
            addition = ((1 << left) | (1 << right)) & ~chosen_mask
            trial = chosen + [index for index in (left, right) if addition >> index & 1]
            if len(trial) > rank:
                continue
            if rank_of([classes[index] for index in trial]) != len(trial):
                continue
            result = search(chosen_mask | addition, trial)
            if result is not None:
                return result
            if capped:
                return None
        return None

    chosen = search(0, [])
    return chosen, nodes, capped


def extend_to_basis(
    classes: Sequence[tuple[int, ...]], chosen: Sequence[int], rank: int
) -> list[int]:
    """Grow an independent covering set to a full ground basis of the dual."""

    basis = list(chosen)
    for index in range(len(classes)):
        if len(basis) == rank:
            break
        if index in basis:
            continue
        if rank_of([classes[item] for item in basis + [index]]) == len(basis) + 1:
            basis.append(index)
    if len(basis) != rank:
        raise AssertionError("independent set does not extend to a ground basis")
    return basis


def incidence_graph_connected(formula: Sequence[Sequence[int]]) -> bool:
    """True when the clause-variable incidence graph is connected."""

    size = len(formula)
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for row, clause in enumerate(formula):
        for variable in clause:
            root_row, root_variable = find(row), find(size + variable)
            if root_row != root_variable:
                parent[root_variable] = root_row
    roots = {find(node) for row, clause in enumerate(formula) for node in (row, *(size + v for v in clause))}
    return len(roots) == 1


def element_index_for_class(
    columns: Sequence[Sequence[int]], point: tuple[int, ...]
) -> int:
    """First ground element realizing one class."""

    for index, column in enumerate(columns):
        if fsp.normalize(column) == point:
            return index
    raise AssertionError("class has no realizing element")


def evaluate_case(
    name: str, formula: Sequence[Sequence[int]], expected: str | None
) -> dict[str, Any]:
    """Decide one formula and re-verify every certificate it produces."""

    started = time.perf_counter()
    canonical = canonical_cubic_formula(formula)
    columns = runner.dual_columns(canonical)
    classes = fsp.classes_of(columns)
    rank = len(columns[0])
    chosen, nodes, capped = frame_search(classes, rank)
    record: dict[str, Any] = {
        "name": name,
        "size": len(canonical),
        "rank": len(canonical) - rank,
        "nullity": rank,
        "classes": len(classes),
        "connected": incidence_graph_connected(canonical),
        "nodes": nodes,
        "capped": capped,
    }
    if chosen is None:
        record["verdict"] = "inconclusive" if capped else "no_frame"
    else:
        basis = extend_to_basis(classes, chosen, rank)
        covered = all(
            any(
                in_span(classes[left], classes[right], point)
                for left, right in itertools.combinations(basis, 2)
            )
            for point in classes
        )
        independent = rank_of([classes[index] for index in basis]) == len(basis)
        free = sorted(element_index_for_class(columns, classes[index]) for index in basis)
        width = runner.basis_width(columns, free)
        if not covered or not independent or width > 2:
            raise AssertionError(
                f"{name}: certificate failed covered={covered} independent={independent} width={width}"
            )
        record["verdict"] = "frame"
        record["width"] = width
        record["free_set"] = free
        record["frame_classes"] = [list(classes[index]) for index in basis]
    record["expected"] = expected
    record["matches_expected"] = expected is None or expected == record["verdict"]
    record["seconds"] = round(time.perf_counter() - started, 3)
    return record


def assemble(blocks: Sequence[Sequence[Sequence[int]]]) -> tuple[list[list[int]], list[tuple[int, int]]]:
    """Concatenate block formulas, returning clauses and (offset, variable) starts."""

    clauses: list[list[int]] = []
    offsets: list[tuple[int, int]] = []
    variable_offset = 0
    for block in blocks:
        offsets.append((len(clauses), variable_offset))
        clauses.extend([[value + variable_offset for value in clause] for clause in block])
        variable_offset += len(block)
    return clauses, offsets


def apply_switch(clauses: list[list[int]], left_row: int, right_row: int) -> None:
    """Swap one incidence between two clauses, preserving degrees."""

    left, right = clauses[left_row], clauses[right_row]
    left_variable = next(value for value in left if value not in right)
    right_variable = next(value for value in right if value not in left)
    left[left.index(left_variable)] = right_variable
    right[right.index(right_variable)] = left_variable
    clauses[left_row] = sorted(left)
    clauses[right_row] = sorted(right)


def chain(blocks: Sequence[Sequence[Sequence[int]]], links: Sequence[tuple[int, int]]):
    """Chain blocks with one cross two-switch per link."""

    clauses, offsets = assemble(blocks)
    for link_index, (left, right) in enumerate(links):
        apply_switch(
            clauses,
            offsets[left][0] + link_index % 3,
            offsets[right][0] + link_index % 3,
        )
    return canonical_cubic_formula(tuple(tuple(clause) for clause in clauses))


def switch_formulas() -> list[tuple[tuple[int, int, int], ...]]:
    """Every incidence two-switch between the two all-bases controls."""

    sat_size = len(ALL_BASES_TERNARY_SAT)
    formulas = []
    for left_row, left_clause in enumerate(ALL_BASES_TERNARY_SAT):
        for left_variable in left_clause:
            for right_row, right_clause in enumerate(ALL_BASES_TERNARY_UNSAT):
                for right_variable in right_clause:
                    formulas.append(
                        runner.switch_formula(
                            left_row, left_variable, sat_size + right_row,
                            sat_size + right_variable,
                        )
                    )
    return formulas


def build_cases() -> list[tuple[str, str, Any, str | None]]:
    """(group, name, formula, expected verdict) tuples."""

    cases: list[tuple[str, str, Any, str | None]] = []
    for name, formula in fsp.CONTROLS:
        cases.append(("controls", name, formula, CONTROL_EXPECTATIONS[name]))
    sat = ALL_BASES_TERNARY_SAT
    unsat = ALL_BASES_TERNARY_UNSAT
    sums = {
        "sum-three-sat+three-sat-n18": (fsp.SUPPORT_THREE_SAT, fsp.SUPPORT_THREE_SAT),
        "sum-three-sat+three-unsat-n24": (fsp.SUPPORT_THREE_SAT, fsp.SUPPORT_THREE_UNSAT),
        "sum-three-sat+bases-sat-n21": (fsp.SUPPORT_THREE_SAT, sat),
        "sum-bases-sat+bases-sat-n24": (sat, sat),
        "sum-bases-sat+bases-unsat-n27": (sat, unsat),
    }
    for name, components in sums.items():
        cases.append(("sums", name, fsp.direct_sum(components), SUM_EXPECTATIONS[name]))
    formulas = switch_formulas()
    stride = max(1, len(formulas) // SWITCH_SAMPLE)
    for index in range(0, len(formulas), stride)[:SWITCH_SAMPLE]:
        cases.append(("switches", f"mixed-switch-{index}", formulas[index], "no_frame"))
    for label, block in (("sat", sat), ("unsat", unsat)):
        for count in (2, 3, 4):
            links = [(index, index + 1) for index in range(count - 1)]
            cases.append(
                (
                    "chains",
                    f"path-{label}-x{count}",
                    chain([block] * count, links),
                    "no_frame",
                )
            )
    for count in (2, 3):
        blocks = [sat if index % 2 == 0 else unsat for index in range(count)]
        links = [(index, index + 1) for index in range(count - 1)]
        cases.append(("chains", f"path-alternating-x{count}", chain(blocks, links), "no_frame"))
    cases.append(("chains", "star-sat-x3", chain([sat] * 3, [(0, 1), (0, 2)]), "no_frame"))
    return cases


def verdict_histogram(records: Sequence[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[record["verdict"]] = counts.get(record["verdict"], 0) + 1
    return dict(sorted(counts.items()))


def digest(formula: Sequence[Sequence[int]]) -> str:
    payload = json.dumps(canonical_cubic_formula(formula), separators=(",", ":"))
    return hashlib.sha256(payload.encode("ascii")).hexdigest()


def build_receipt() -> dict[str, Any]:
    started = time.perf_counter()
    records: list[dict[str, Any]] = []
    for group, name, formula, expected in build_cases():
        record = evaluate_case(name, formula, expected)
        record["group"] = group
        records.append(record)
        print(
            f"{group:9s} {name:30s} n={record['size']:3d} k={record['nullity']} "
            f"conn={int(record['connected'])} {record['verdict']:12s} "
            f"nodes={record['nodes']:6d} capped={int(record['capped'])} {record['seconds']:6.2f}s"
        )
    groups = sorted({record["group"] for record in records})
    return {
        "schema": SCHEMA,
        "status": "measured",
        "algorithm": {
            "name": "ground-class frame search",
            "branch": "first uncovered class, all class pairs whose join covers it",
            "success": "independent covering set, extended to a ground basis by verified rank steps",
            "certificate": "coverage, independence and exact pivot-free width two re-verified on every success",
            "completeness": "every frame must cover the branching target, so an exhausted search proves omega >= 3",
            "node_cap": NODE_CAP,
        },
        "summary": {
            group: {
                "cases": sum(1 for record in records if record["group"] == group),
                "verdicts": verdict_histogram(
                    [record for record in records if record["group"] == group]
                ),
                "max_nodes": max(
                    record["nodes"] for record in records if record["group"] == group
                ),
                "total_seconds": round(
                    sum(record["seconds"] for record in records if record["group"] == group), 3
                ),
            }
            for group in groups
        },
        "cases": records,
        "criteria": {
            "expected_verdicts_matched": sum(record["matches_expected"] for record in records),
            "expected_verdicts_total": len(records),
            "connected_chains": sum(
                1
                for record in records
                if record["group"] == "chains" and record["connected"]
            ),
            "chain_sizes": sorted(
                record["size"] for record in records if record["group"] == "chains"
            ),
            "largest_chain_nullity": max(
                record["nullity"] for record in records if record["group"] == "chains"
            ),
            "largest_chain_census_size": math.comb(60, 9),
            "largest_chain_nodes": max(
                record["nodes"] for record in records if record["group"] == "chains"
            ),
            "switch_sample": SWITCH_SAMPLE,
            "switch_population": len(switch_formulas()),
            "no_hardness_claim": True,
        },
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def main() -> None:
    receipt = build_receipt()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "schema": receipt["schema"],
        "summary": receipt["summary"],
        "criteria": receipt["criteria"],
        "elapsed_seconds": receipt["elapsed_seconds"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
