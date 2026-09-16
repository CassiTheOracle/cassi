"""Measure the source-clause boundary of projected matching cuts.

The existing alias-cut receipt remains the dynamic search experiment.  This
runner adds a separate, syntactic analysis: on fully cubic sources, compare
accepted projected cuts with the four ordinary exact-one CNF clauses generated
from each source triple.  It records finite certificates and an explicit
exhaustion control without claiming an unrestricted polynomial algorithm.
"""

from __future__ import annotations

import itertools
import json
from functools import lru_cache
from math import comb
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_alias_cut_field import AliasCutField
from cassi_alias_exact_one_field import (
    RecognizedAliasFormula,
    recognize_degree_two_three_exact_one,
    regular_monotone_formula,
)
from cassi_alias_obstruction import derive_obstruction_cut, evaluate_alias_candidate

OUTPUT = Path("_diag/alias_cut_complexity.json")
SCHEMA = "cassifi.alias-cut-complexity.v2"
FULLY_CUBIC_CENSUS_MIN_CLAUSES = 4
FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF = 6
FULLY_CUBIC_CENSUS_MAX_CLAUSES = FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF
FULLY_CUBIC_CENSUS_MAX_VARIABLES = FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF
FULLY_CUBIC_C7_COUNT_CLAUSES = 7

Formula = tuple[tuple[int, int, int], ...]


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")




def _variable_count(formula: Sequence[Sequence[int]]) -> int:
    return max(variable for clause in formula for variable in clause)


def _canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    return tuple(sorted(tuple(sorted(clause)) for clause in formula))  # type: ignore[return-value]


def _is_connected(formula: Formula, variables: int) -> bool:
    total = variables + len(formula)
    graph = [set() for _ in range(total)]
    for clause_index, clause in enumerate(formula):
        clause_node = variables + clause_index
        for variable in clause:
            variable_node = variable - 1
            graph[variable_node].add(clause_node)
            graph[clause_node].add(variable_node)
    seen = {0}
    stack = [0]
    while stack:
        node = stack.pop()
        for neighbor in sorted(graph[node]):
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == total


def exact_one_cnf(formula: Sequence[Sequence[int]]) -> list[list[int]]:
    """Return one positive triple and three negative pairs per source row."""
    result: list[list[int]] = []
    for raw in formula:
        a, b, c = sorted(raw)
        result.extend(([a, b, c], [-a, -b], [-a, -c], [-b, -c]))
    return result


def classify_cut_subsumption(
    formula: Sequence[Sequence[int]], cut: Mapping[str, Any]
) -> dict[str, Any] | None:
    """Return the first exact-one clause that subsumes the projected cut."""
    cut_literals = cut.get("literals")
    if not isinstance(cut_literals, list):
        raise ValueError("cut literal list is missing")
    cut_set = {int(literal) for literal in cut_literals}
    cnf = exact_one_cnf(formula)
    for cnf_index, clause in enumerate(cnf):
        clause_set = set(clause)
        if clause_set <= cut_set:
            return {
                "cnf_index": cnf_index,
                "source_clause": cnf_index // 4,
                "clause": list(clause),
                "relation": "equal" if clause_set == cut_set else "proper",
            }
    return None


def _recognized(formula: Sequence[Sequence[int]]) -> RecognizedAliasFormula:
    canonical = _canonical_formula(formula)
    return recognize_degree_two_three_exact_one(
        canonical,
        variable_count=_variable_count(canonical),
    )


def _cut_record(formula: Formula, cut: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "cut": dict(cut),
        "subsumption": classify_cut_subsumption(formula, cut),
    }


def _candidate_scan(
    recognized: RecognizedAliasFormula,
    formula: Formula,
) -> dict[str, Any]:
    cuts: list[dict[str, Any]] = []
    cut_positions: dict[bytes, int] = {}
    outcomes: list[int] = []
    for bits in itertools.product((0, 1), repeat=len(recognized.cubic_variables)):
        candidate = evaluate_alias_candidate(recognized, bits)
        if candidate["status"] == "sat":
            outcomes.append(-1)
            continue
        cut = candidate.get("cut")
        if not isinstance(cut, dict):
            raise AssertionError("UNSAT candidate did not carry an obstruction cut")
        key = _canonical(cut)
        position = cut_positions.get(key)
        if position is None:
            position = len(cuts)
            cut_positions[key] = position
            cuts.append(_cut_record(formula, cut))
        outcomes.append(position)
    return {"outcomes": outcomes, "cuts": cuts}


def _first_candidate_cut(recognized: RecognizedAliasFormula) -> dict[str, Any]:
    for bits in itertools.product((0, 1), repeat=len(recognized.cubic_variables)):
        candidate = evaluate_alias_candidate(recognized, bits)
        cut = candidate.get("cut")
        if isinstance(cut, dict):
            return cut
    raise AssertionError("source has no candidate obstruction cut")


def _signed_barrier_cut(recognized: RecognizedAliasFormula) -> dict[str, Any]:
    for bits in itertools.product((0, 1), repeat=len(recognized.cubic_variables)):
        candidate = evaluate_alias_candidate(recognized, bits)
        cut = candidate.get("cut")
        if (
            isinstance(cut, dict)
            and cut.get("kind") == "tutte"
            and cut.get("barrier")
            and any(int(literal) < 0 for literal in cut.get("literals", []))
        ):
            return cut
    raise AssertionError("source has no signed nonempty-barrier control cut")


def _proper_fully_cubic_barrier_cut(recognized: RecognizedAliasFormula) -> dict[str, Any]:
    if not recognized.cubic_variables or len(recognized.formula) < 4:
        raise AssertionError("fully cubic barrier control needs a nontrivial source")
    bits = (0,) * len(recognized.cubic_variables)
    return derive_obstruction_cut(recognized, bits, barrier=[0])


def _relabel_formula(
    formula: Sequence[Sequence[int]], mapping: Mapping[int, int]
) -> Formula:
    return _canonical_formula(
        [[mapping[variable] for variable in clause] for clause in formula]
    )


def _noncontiguous_mixed_formula() -> Formula:
    base = regular_monotone_formula(8, 4, seed=0)
    mapping = {
        1: 2,
        2: 4,
        3: 7,
        4: 10,
        5: 1,
        6: 3,
        7: 5,
        8: 6,
        9: 8,
        10: 9,
    }
    formula = _relabel_formula(base, mapping)
    recognized = _recognized(formula)
    if recognized.cubic_variables != (2, 4, 7, 10):
        raise AssertionError("non-contiguous cubic-ID control was not preserved")
    return recognized.formula


def _case_specs() -> list[tuple[str, Formula, str, dict[str, int]]]:
    specs: list[tuple[str, Formula, str, dict[str, int]]] = []

    for clauses, seed, expected in (
        (4, 0, "unsat"),
        (5, 0, "unsat"),
        (6, 0, "sat"),
        (6, 6, "unsat"),
        (9, 0, "sat"),
        (9, 2, "unsat"),
        (12, 0, "sat"),
        (12, 1, "unsat"),
    ):
        formula = _recognized(regular_monotone_formula(clauses, clauses, seed=seed)).formula
        label = "pure-count" if clauses % 3 else "pure-structural"
        specs.append((f"{label}-{expected}-c{clauses}-k{clauses}-s{seed}", formula, expected, {}))

    mixed_specs = (
        ("mixed-sat-c6-k2-s0", regular_monotone_formula(6, 2, seed=0), "sat", {}),
        ("mixed-unsat-c6-k2-s1", regular_monotone_formula(6, 2, seed=1), "unsat", {}),
        ("mixed-noncontiguous-sat-c8-k4-s0", _noncontiguous_mixed_formula(), "sat", {}),
        ("mixed-signed-barrier-unsat-c10-k4-s0", regular_monotone_formula(10, 4, seed=0), "unsat", {}),
        ("mixed-exhausted-c6-k2-s0", regular_monotone_formula(6, 2, seed=0), "exhausted", {"max_steps": 1}),
    )
    for name, formula, expected, limits in mixed_specs:
        specs.append((name, _recognized(formula).formula, expected, limits))
    return specs

def _enumerate_simple_fully_cubic_sources_with_accounting(
    clause_count: int,
) -> tuple[list[Formula], dict[str, int]]:
    """Enumerate labelled sources and count every degree-filter outcome."""
    if clause_count > FULLY_CUBIC_CENSUS_MAX_VARIABLES:
        raise ValueError("fully cubic source exceeds the complete census cutoff")
    triples: tuple[tuple[int, int, int], ...] = tuple(
        (triple[0], triple[1], triple[2])
        for triple in itertools.combinations(range(1, clause_count + 1), 3)
    )
    sources: list[Formula] = []
    examined = 0
    degree_filter_rejections = 0
    for selected in itertools.combinations(triples, clause_count):
        examined += 1
        degrees = [0] * clause_count
        for clause in selected:
            for variable in clause:
                degrees[variable - 1] += 1
        if degrees != [3] * clause_count:
            degree_filter_rejections += 1
            continue
        formula: Formula = tuple(selected)
        sources.append(formula)
    expected_row_subsets = comb(len(triples), clause_count)
    if examined != expected_row_subsets:
        raise AssertionError("source enumeration did not cover every row subset")
    return sources, {
        "candidate_triples": len(triples),
        "naive_row_subsets": examined,
        "accepted_sources": len(sources),
        "degree_filter_rejections": degree_filter_rejections,
    }


def _enumerate_simple_fully_cubic_sources(clause_count: int) -> list[Formula]:
    """Enumerate all simple labelled c-by-c 3-regular incidence sources."""
    sources, _ = _enumerate_simple_fully_cubic_sources_with_accounting(clause_count)
    return sources


def _source_universe_accounting(
    clause_sizes: Sequence[int],
    enumeration_stats: Mapping[int, Mapping[str, int]],
) -> dict[str, Any]:
    """Account for every raw row subset and degree-filter outcome."""
    by_clause_count: dict[str, dict[str, int]] = {}
    total_row_subsets = 0
    total_sources = 0
    total_rejections = 0
    for clause_count in clause_sizes:
        if clause_count not in enumeration_stats:
            raise AssertionError("enumeration statistics are missing a clause size")
        observed = enumeration_stats[clause_count]
        expected = {
            "candidate_triples": comb(clause_count, 3),
            "naive_row_subsets": comb(comb(clause_count, 3), clause_count),
            "accepted_sources": 0,
            "degree_filter_rejections": 0,
        }
        for key in ("candidate_triples", "naive_row_subsets"):
            if observed.get(key) != expected[key]:
                raise AssertionError(f"source accounting mismatch for {key}")
        accepted = observed.get("accepted_sources")
        rejected = observed.get("degree_filter_rejections")
        if not isinstance(accepted, int) or isinstance(accepted, bool):
            raise AssertionError("accepted source count is not an integer")
        if not isinstance(rejected, int) or isinstance(rejected, bool):
            raise AssertionError("degree-filter rejection count is not an integer")
        if accepted < 0 or rejected < 0:
            raise AssertionError("source accounting contains a negative count")
        if accepted + rejected != expected["naive_row_subsets"]:
            raise AssertionError("source accounting does not partition row subsets")
        expected["accepted_sources"] = accepted
        expected["degree_filter_rejections"] = rejected
        by_clause_count[str(clause_count)] = expected
        total_row_subsets += expected["naive_row_subsets"]
        total_sources += accepted
        total_rejections += rejected
    return {
        "universe_kind": "labelled_simple_clause_triple_subsets",
        "clause_labels": "not separately labelled; clauses are the selected triples",
        "variable_labels": "1..c",
        "row_order": "lexicographic combinations; row permutations are not distinct",
        "filter_rule": "retain iff every variable has degree exactly 3 after selecting all c distinct triples",
        "graph_isomorphism_quotient": "none",
        "unlabeled_graphs_enumerated": False,
        "complete_cutoff": FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF,
        "by_clause_count": by_clause_count,
        "total_naive_row_subsets": total_row_subsets,
        "total_accepted_sources": total_sources,
        "total_degree_filter_rejections": total_rejections,
    }


def _count_simple_fully_cubic_sources_dp(clause_count: int) -> int:
    """Return the number of valid distinct triple subsets for this c."""
    # The counted objects are S subset of C({1,...,c}, 3) with |S|=c
    # and degree_S(v)=3 for every variable v; cache states are not returned.
    if not 3 <= clause_count <= FULLY_CUBIC_C7_COUNT_CLAUSES:
        raise ValueError("count-only DP supports clause sizes from 3 through c=7")
    triple_masks = tuple(
        sum(1 << (variable - 1) for variable in triple)
        for triple in itertools.combinations(range(1, clause_count + 1), 3)
    )
    target = (3,) * clause_count

    @lru_cache(maxsize=None)
    def count(
        triple_index: int,
        selected: int,
        degrees: tuple[int, ...],
    ) -> int:
        if selected == clause_count:
            return int(degrees == target)
        if triple_index == len(triple_masks):
            return 0
        if selected + len(triple_masks) - triple_index < clause_count:
            return 0

        total = count(triple_index + 1, selected, degrees)
        mask = triple_masks[triple_index]
        updated = list(degrees)
        for variable in range(clause_count):
            if mask & (1 << variable):
                updated[variable] += 1
                if updated[variable] > 3:
                    break
        else:
            total += count(triple_index + 1, selected + 1, tuple(updated))
        return total

    return count(0, 0, (0,) * clause_count)


def _count_simple_fully_cubic_sources_c7() -> int:
    """Count c=7 sources without materializing formulas or certificates."""
    return _count_simple_fully_cubic_sources_dp(FULLY_CUBIC_C7_COUNT_CLAUSES)


def _audit_fully_cubic_source(formula: Formula) -> dict[str, Any]:
    recognized = _recognized(formula)
    clause_count = len(formula)
    if recognized.cubic_variables != tuple(range(1, clause_count + 1)):
        raise AssertionError("fully cubic census source has an incomplete cubic variable set")

    certificate_records: list[dict[str, Any]] = []
    record_positions: dict[bytes, int] = {}
    projected_clauses: set[tuple[int, ...]] = set()
    emissions: list[dict[str, Any]] = []
    cut_kinds: dict[str, int] = {}
    relations = {"equal": 0, "proper": 0, "null": 0}
    counterexamples: list[dict[str, Any]] = []
    sat_candidates = 0
    unsat_candidates = 0
    conflict_precedence_violations = 0

    for bits in itertools.product((0, 1), repeat=clause_count):
        counts = tuple(
            sum(bits[variable - 1] for variable in clause)
            for clause in formula
        )
        first_conflict = next(
            (index for index, count in enumerate(counts) if count > 1),
            None,
        )

        candidate = evaluate_alias_candidate(recognized, bits)
        status = candidate.get("status")
        cut = candidate.get("cut")
        if first_conflict is not None:
            if (
                status != "unsat"
                or not isinstance(cut, dict)
                or cut.get("kind") != "overfill"
                or cut.get("conflict_clause") != first_conflict
            ):
                conflict_precedence_violations += 1
        elif isinstance(cut, dict) and cut.get("kind") == "overfill":
            conflict_precedence_violations += 1

        if status == "sat":
            if cut is not None:
                raise AssertionError("SAT producer branch carried a certificate cut")
            sat_candidates += 1
            continue
        if status != "unsat":
            raise AssertionError("fully cubic producer returned an unknown candidate status")
        unsat_candidates += 1
        if not isinstance(cut, dict):
            raise AssertionError("UNSAT producer branch lacked a certificate cut")
        kind = cut.get("kind")
        if kind not in ("overfill", "tutte"):
            raise AssertionError("producer emitted an unknown obstruction kind")
        cut_kinds[kind] = cut_kinds.get(kind, 0) + 1
        subsumption = classify_cut_subsumption(formula, cut)
        relation = "null" if subsumption is None else subsumption["relation"]
        if relation not in relations:
            raise AssertionError("classifier emitted an unknown subsumption relation")
        relations[relation] += 1
        projected_clauses.add(tuple(int(literal) for literal in cut["literals"]))

        key = _canonical(cut)
        record_index = record_positions.get(key)
        if record_index is None:
            record_index = len(certificate_records)
            record_positions[key] = record_index
            certificate_records.append({
                "cut": dict(cut),
                "subsumption": subsumption,
            })
        emissions.append({"bits": list(bits), "record_index": record_index})
        if relation != "equal":
            counterexamples.append({
                "bits": list(bits),
                "record_index": record_index,
                "cut": dict(cut),
                "subsumption": subsumption,
            })

    return {
        "clauses": clause_count,
        "formula": [list(clause) for clause in formula],
        "connected": _is_connected(formula, clause_count),
        "candidate_assignments": 1 << clause_count,
        "sat_candidates": sat_candidates,
        "unsat_candidates": unsat_candidates,
        "conflict_precedence_violations": conflict_precedence_violations,
        "emitted_certificate_records": len(emissions),
        "distinct_certificate_records": len(certificate_records),
        "distinct_projected_clauses": len(projected_clauses),
        "cut_kinds": cut_kinds,
        "subsumption_relations": relations,
        "certificate_records": certificate_records,
        "emissions": emissions,
        "counterexamples": counterexamples,
    }


def _fully_cubic_census() -> dict[str, Any]:
    clause_sizes = list(
        range(FULLY_CUBIC_CENSUS_MIN_CLAUSES, FULLY_CUBIC_CENSUS_MAX_CLAUSES + 1)
    )
    if FULLY_CUBIC_CENSUS_MAX_CLAUSES != FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF:
        raise AssertionError("census maximum must equal the complete cutoff")
    if any(clause_count > FULLY_CUBIC_CENSUS_MAX_VARIABLES for clause_count in clause_sizes):
        raise AssertionError("fully cubic census clause bound exceeds variable bound")

    source_rows: list[dict[str, Any]] = []
    enumeration_stats: dict[int, dict[str, int]] = {}
    for clause_count in clause_sizes:
        formulas, stats = _enumerate_simple_fully_cubic_sources_with_accounting(clause_count)
        enumeration_stats[clause_count] = stats
        for formula in formulas:
            source_rows.append(_audit_fully_cubic_source(formula))
    universe = _source_universe_accounting(clause_sizes, enumeration_stats)

    def total(key: str) -> int:
        return sum(int(row[key]) for row in source_rows)

    cut_kinds: dict[str, int] = {}
    relations = {"equal": 0, "proper": 0, "null": 0}
    for row in source_rows:
        for kind, count in row["cut_kinds"].items():
            cut_kinds[kind] = cut_kinds.get(kind, 0) + int(count)
        for relation, count in row["subsumption_relations"].items():
            relations[relation] += int(count)

    summary = {
        "sources": len(source_rows),
        "connected_sources": sum(bool(row["connected"]) for row in source_rows),
        "candidate_assignments": total("candidate_assignments"),
        "sat_candidates": total("sat_candidates"),
        "unsat_candidates": total("unsat_candidates"),
        "emitted_certificate_records": total("emitted_certificate_records"),
        "distinct_certificate_records": total("distinct_certificate_records"),
        "distinct_projected_clauses": total("distinct_projected_clauses"),
        "conflict_precedence_violations": total("conflict_precedence_violations"),
        "cut_kinds": cut_kinds,
        "subsumption_relations": relations,
        "counterexamples": sum(len(row["counterexamples"]) for row in source_rows),
    }
    return {
        "definition": (
            "simple canonical labelled c-by-c incidence matrices with three "
            "ones in every row and column; duplicate source triples excluded"
        ),
        "producer_path": "evaluate_alias_candidate",
        "min_clauses": FULLY_CUBIC_CENSUS_MIN_CLAUSES,
        "max_clauses": FULLY_CUBIC_CENSUS_MAX_CLAUSES,
        "max_variables": FULLY_CUBIC_CENSUS_MAX_VARIABLES,
        "complete_cutoff": FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF,
        "clause_sizes": clause_sizes,
        "universe": universe,
        "sources": source_rows,
        "summary": summary,
    }


def _controls_for(
    name: str,
    formula: Formula,
    recognized: RecognizedAliasFormula,
    result_cuts: Sequence[Mapping[str, Any]],
    scan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    if result_cuts:
        controls.append({
            "name": f"{name}-retained",
            "cut": dict(result_cuts[0]),
            "subsumption": classify_cut_subsumption(formula, result_cuts[0]),
        })
    elif scan and scan["cuts"]:
        record = scan["cuts"][0]
        controls.append({"name": f"{name}-candidate", **record})

    if name == "pure-structural-sat-c6-k6-s0":
        cut = _proper_fully_cubic_barrier_cut(recognized)
        controls.append({
            "name": "fully-cubic-proper-barrier-control",
            "cut": cut,
            "subsumption": classify_cut_subsumption(formula, cut),
        })
    if name == "mixed-sat-c6-k2-s0":
        cut = _first_candidate_cut(recognized)
        controls.append({
            "name": "mixed-null-subsumption-control",
            "cut": cut,
            "subsumption": classify_cut_subsumption(formula, cut),
        })
    if name == "mixed-signed-barrier-unsat-c10-k4-s0":
        cut = _signed_barrier_cut(recognized)
        controls.append({
            "name": "mixed-signed-nonempty-barrier-control",
            "cut": cut,
            "subsumption": classify_cut_subsumption(formula, cut),
        })
    return controls


def _source_refutation(
    formula: Formula,
    result: Mapping[str, Any],
    subsumptions: Sequence[dict[str, Any] | None],
    *,
    fully_cubic: bool,
) -> dict[str, Any] | None:
    if not fully_cubic or result.get("status") != "unsat":
        return None
    if any(row is None or row["relation"] != "equal" for row in subsumptions):
        raise AssertionError("fully cubic production cut is not an exact source CNF clause")
    proof = result.get("proof")
    if not isinstance(proof, dict) or not isinstance(proof.get("stats"), dict):
        raise AssertionError("fully cubic UNSAT result has no proof statistics")
    backend_steps = int(proof["stats"]["inference_steps"])
    indices = [int(row["cnf_index"]) for row in subsumptions if row is not None]
    return {
        "cnf_indices": indices,
        "backend_inference_steps": backend_steps,
        "added_weakenings": 0,
        "total_inference_steps": backend_steps,
    }


def _run_case(
    name: str,
    formula: Formula,
    expected: str,
    limits: Mapping[str, int],
) -> dict[str, Any]:
    recognized = _recognized(formula)
    formula = recognized.formula
    variables = _variable_count(formula)
    fully_cubic = all(degree == 3 for degree in recognized.degrees)
    if fully_cubic and variables != len(formula):
        raise AssertionError(f"{name}: fully cubic incidence count mismatch")
    connected = _is_connected(formula, variables)
    if not connected:
        raise AssertionError(f"{name}: source is not connected")

    options = {
        "max_cuts": 512,
        "max_cut_bytes": 65_536,
        "max_journal_bytes": 65_536,
        "max_steps": 50_000,
        "max_learned_clauses": 512,
    }
    options.update(limits)
    field, initial = AliasCutField.initialize(
        formula,
        variable_count=variables,
        **options,
    )
    final, result = field.solve(initial)
    if result["status"] != expected:
        raise AssertionError(f"{name}: expected {expected}, got {result['status']}")
    restored_field, restored_state = AliasCutField.from_descriptor(field.descriptor(final))
    restored_result = restored_field.result(restored_state)
    if restored_result != result:
        raise AssertionError(f"{name}: descriptor restart changed the result")

    result_cuts = [dict(cut) for cut in result["cuts"]]
    result_subsumptions = [classify_cut_subsumption(formula, cut) for cut in result_cuts]
    scan = _candidate_scan(recognized, formula) if variables <= 10 else None
    controls = _controls_for(name, formula, recognized, result_cuts, scan)
    source_refutation = _source_refutation(
        formula,
        result,
        result_subsumptions,
        fully_cubic=fully_cubic,
    )
    return {
        "name": name,
        "formula": [list(row) for row in formula],
        "variable_count": variables,
        "fully_cubic": fully_cubic,
        "connected": connected,
        "counting_obstruction": (len(formula) % 3 != 0) if fully_cubic else None,
        "cnf": exact_one_cnf(formula),
        "candidate_scan": scan,
        "certificate_controls": controls,
        "solver": {
            "result": result,
            "cut_subsumptions": result_subsumptions,
            "restart_state_sha256": restored_field.state_sha256(restored_state),
            "source_refutation": source_refutation,
        },
    }




def run_analysis(output: Path = OUTPUT) -> dict[str, Any]:
    census = _fully_cubic_census()
    cases = [_run_case(name, formula, expected, limits) for name, formula, expected, limits in _case_specs()]

    fully_cubic = [case for case in cases if case["fully_cubic"]]
    mixed = [case for case in cases if not case["fully_cubic"]]
    scans = [case["candidate_scan"] for case in cases if case["candidate_scan"] is not None]
    scan_cut_records = [record for scan in scans for record in scan["cuts"]]
    all_result_cuts = [
        cut
        for case in cases
        for cut in case["solver"]["result"]["cuts"]
    ]
    mixed_scan_records = [
        record
        for case in mixed
        if case["candidate_scan"] is not None
        for record in case["candidate_scan"]["cuts"]
    ]
    strict_controls = [
        control["subsumption"]
        for case in cases
        for control in case["certificate_controls"]
        if control["subsumption"] is not None
        and control["subsumption"]["relation"] == "proper"
    ]
    summary = {
        "cases": len(cases),
        "fully_cubic_cases": len(fully_cubic),
        "mixed_cases": len(mixed),
        "sat": sum(case["solver"]["result"]["status"] == "sat" for case in cases),
        "unsat": sum(case["solver"]["result"]["status"] == "unsat" for case in cases),
        "exhausted": sum(case["solver"]["result"]["status"] == "exhausted" for case in cases),
        "candidate_assignments": sum(len(scan["outcomes"]) for scan in scans),
        "candidate_distinct_cuts": len(scan_cut_records),
        "candidate_nonlocal_mixed_cuts": sum(
            record["subsumption"] is None for record in mixed_scan_records
        ),
        "retained_cuts": len(all_result_cuts),
        "fully_cubic_retained_cuts": sum(
            len(case["solver"]["result"]["cuts"]) for case in fully_cubic
        ),
        "fully_cubic_max_cuts": max(
            len(case["solver"]["result"]["cuts"]) for case in fully_cubic
        ),
        "fully_cubic_max_cut_bound": max(4 * len(case["formula"]) for case in fully_cubic),
        "source_refutations": sum(
            case["solver"]["source_refutation"] is not None for case in cases
        ),
        "certificate_controls": sum(len(case["certificate_controls"]) for case in cases),
        "strict_weakenings": len(strict_controls),
        "fully_cubic_census_sources": census["summary"]["sources"],
        "fully_cubic_census_candidates": census["summary"]["candidate_assignments"],
        "fully_cubic_census_emitted_records": census["summary"]["emitted_certificate_records"],
        "fully_cubic_census_projected_clauses": census["summary"]["distinct_projected_clauses"],
        "fully_cubic_census_certificate_records": census["summary"]["distinct_certificate_records"],
        "fully_cubic_census_counterexamples": census["summary"]["counterexamples"],
        "fully_cubic_census_conflict_precedence_violations": census["summary"]["conflict_precedence_violations"],
    }
    receipt = {
        "schema": SCHEMA,
        "cases": cases,
        "fully_cubic_census": census,
        "summary": summary,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary, "census": census["summary"]}, sort_keys=True))
    return receipt


if __name__ == "__main__":
    run_analysis()
