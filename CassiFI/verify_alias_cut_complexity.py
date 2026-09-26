"""Independent verifier for the projected alias-cut complexity receipt.

This checker deliberately does not import the alias solver, obstruction
producer, or analysis runner.  It reconstructs the degree-two/degree-three
incidence graph, checks candidate cubes with an independent matching search,
audits source-clause subsumption, enumerates the tiny source instances, and
replays malformed-cut refusals.  Its finite checks are evidence about the
recognized family only; they are not a P-vs-NP theorem.
"""

from __future__ import annotations

import copy
import itertools
import json
from math import comb
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

from verify_alias_cut_field import verify_obstruction_cut, verify_result

RECEIPT = Path("_diag/alias_cut_complexity.json")
SCHEMA = "cassifi.alias-cut-complexity.v2"
FULLY_CUBIC_CENSUS_MIN_CLAUSES = 4
FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF = 6
FULLY_CUBIC_CENSUS_MAX_CLAUSES = FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF
FULLY_CUBIC_CENSUS_MAX_VARIABLES = FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF
FULLY_CUBIC_C7_COUNT_CLAUSES = 7


class VerificationError(AssertionError):
    """Raised when a receipt or one of its certificates is invalid."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise VerificationError(message)


def _exact_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    require(isinstance(value, int) and not isinstance(value, bool), f"{name}: expected integer")
    result = int(value)
    if minimum is not None:
        require(result >= minimum, f"{name}: integer is below minimum")
    return result


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _digest(value: Any, name: str) -> None:
    require(isinstance(value, str) and len(value) == 64, f"{name}: digest is malformed")
    try:
        int(value, 16)
    except ValueError as exc:
        raise VerificationError(f"{name}: digest is not hexadecimal") from exc


def _source(formula: Any, variable_count: Any) -> dict[str, Any]:
    """Independently canonicalize and recognize a source incidence formula."""
    variables = _exact_int(variable_count, "variable_count", minimum=1)
    require(isinstance(formula, (list, tuple)) and bool(formula), "formula must be a non-empty list")
    clauses: list[tuple[int, int, int]] = []
    for clause_index, raw in enumerate(formula):
        require(
            isinstance(raw, (list, tuple)) and len(raw) == 3,
            f"formula clause {clause_index}: expected a triple",
        )
        values = [
            _exact_int(value, f"formula clause {clause_index} literal", minimum=1)
            for value in raw
        ]
        require(all(value <= variables for value in values), f"formula clause {clause_index}: variable out of range")
        require(values == sorted(values), f"formula clause {clause_index}: triple is not canonical")
        require(len(set(values)) == 3, f"formula clause {clause_index}: triple repeats a variable")
        clauses.append((values[0], values[1], values[2]))
    require(clauses == sorted(clauses), "formula clauses are not in canonical order")

    incidence: list[list[int]] = [[] for _ in range(variables)]
    for clause_index, clause in enumerate(clauses):
        for variable in clause:
            incidence[variable - 1].append(clause_index)
    degrees = tuple(len(rows) for rows in incidence)
    require(all(degree in (2, 3) for degree in degrees), "source variable degree is outside {2,3}")
    cubic = tuple(index + 1 for index, degree in enumerate(degrees) if degree == 3)
    return {
        "formula": tuple(clauses),
        "variables": variables,
        "incidence": tuple(tuple(rows) for rows in incidence),
        "degrees": degrees,
        "cubic": cubic,
    }


def _is_connected(formula: Sequence[Sequence[int]], variables: int) -> bool:
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
        for neighbor in graph[node]:
            if neighbor not in seen:
                seen.add(neighbor)
                stack.append(neighbor)
    return len(seen) == total


def exact_one_cnf(formula: Sequence[Sequence[int]]) -> list[list[int]]:
    result: list[list[int]] = []
    for raw in formula:
        a, b, c = sorted(raw)
        result.extend(([a, b, c], [-a, -b], [-a, -c], [-b, -c]))
    return result


def _expected_subsumption(
    formula: Sequence[Sequence[int]],
    cut: Mapping[str, Any],
) -> dict[str, Any] | None:
    cnf = exact_one_cnf(formula)
    literals = cut.get("literals")
    if not isinstance(literals, list) or not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in literals
    ):
        raise VerificationError("cut literals must be a list of integers")
    cut_set = {int(value) for value in literals}
    for cnf_index, clause in enumerate(cnf):
        if set(clause) <= cut_set:
            return {
                "cnf_index": cnf_index,
                "source_clause": cnf_index // 4,
                "clause": list(clause),
                "relation": "equal" if set(clause) == cut_set else "proper",
            }
    return None


def verify_cut_subsumption(
    formula: Sequence[Sequence[int]],
    cut: Mapping[str, Any],
    witness: Any,
) -> None:
    """Verify the exact first source-CNF clause subsuming a projected cut."""
    require(isinstance(cut, Mapping), "cut must be an object")
    source = _source(formula, max(max(clause) for clause in formula))
    literals = cut.get("literals")
    if not isinstance(literals, list) or not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in literals
    ):
        raise VerificationError("cut literals must be a list of integers")
    checked_literals = [int(value) for value in literals]
    require(
        checked_literals == sorted(checked_literals, key=lambda value: abs(value)),
        "cut literals are not sorted by absolute variable",
    )
    require(len(checked_literals) == len(set(checked_literals)), "cut literals contain duplicates")
    require(
        all(value != 0 and abs(value) in source["cubic"] for value in checked_literals),
        "cut literal is not a cubic source variable",
    )

    expected = _expected_subsumption(source["formula"], cut)
    if expected is None:
        require(witness is None, "subsumption witness claims a nonexistent source clause")
        return

    require(isinstance(witness, dict), "subsumption witness must be an object")
    require(
        set(witness) == {"cnf_index", "source_clause", "clause", "relation"},
        "subsumption witness fields are not exact",
    )
    require(_exact_int(witness["cnf_index"], "subsumption cnf_index", minimum=0) == expected["cnf_index"], "subsumption CNF index is wrong")
    require(_exact_int(witness["source_clause"], "subsumption source_clause", minimum=0) == expected["source_clause"], "subsumption source clause is wrong")
    require(witness["clause"] == expected["clause"], "subsumption clause is wrong")
    require(witness["relation"] == expected["relation"], "subsumption relation is wrong")


def _perfect_matching(graph: Sequence[Sequence[int]]) -> bool:
    adjacency = tuple(tuple(sorted(set(neighbors))) for neighbors in graph)

    @lru_cache(maxsize=None)
    def search(remaining: frozenset[int]) -> bool:
        if not remaining:
            return True
        left = min(remaining)
        for right in adjacency[left]:
            if right not in remaining:
                continue
            next_remaining = frozenset(node for node in remaining if node not in (left, right))
            if search(next_remaining):
                return True
        return False

    return search(frozenset(range(len(adjacency))))


def _candidate_is_sat(source: Mapping[str, Any], bits: Sequence[int]) -> bool:
    cubic = tuple(source["cubic"])
    values = dict(zip(cubic, bits))
    counts = tuple(
        sum(values.get(variable, 0) for variable in clause)
        for clause in source["formula"]
    )
    if any(count > 1 for count in counts):
        return False
    residual = tuple(index for index, count in enumerate(counts) if count == 0)
    if len(residual) % 2:
        return False
    local_for = {clause: local for local, clause in enumerate(residual)}
    graph: list[set[int]] = [set() for _ in residual]
    for variable, degree in enumerate(source["degrees"], 1):
        if degree != 2:
            continue
        incident = source["incidence"][variable - 1]
        if all(clause in local_for for clause in incident):
            left, right = (local_for[incident[0]], local_for[incident[1]])
            if left == right:
                return False
            graph[left].add(right)
            graph[right].add(left)
    return _perfect_matching([tuple(neighbors) for neighbors in graph])

def _enumerate_simple_fully_cubic_sources_with_accounting(
    clause_count: int,
) -> tuple[list[tuple[tuple[int, int, int], ...]], dict[str, int]]:
    """Independently enumerate sources and every degree-filter outcome."""
    require(
        clause_count <= FULLY_CUBIC_CENSUS_MAX_VARIABLES,
        "fully cubic source exceeds the complete census cutoff",
    )
    triples: tuple[tuple[int, int, int], ...] = tuple(
        (triple[0], triple[1], triple[2])
        for triple in itertools.combinations(range(1, clause_count + 1), 3)
    )
    sources: list[tuple[tuple[int, int, int], ...]] = []
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
        sources.append(tuple(selected))
    expected_row_subsets = comb(len(triples), clause_count)
    require(examined == expected_row_subsets, "source enumeration missed a row subset")
    return sources, {
        "candidate_triples": len(triples),
        "naive_row_subsets": examined,
        "accepted_sources": len(sources),
        "degree_filter_rejections": degree_filter_rejections,
    }


def _enumerate_simple_fully_cubic_sources(
    clause_count: int,
) -> list[tuple[tuple[int, int, int], ...]]:
    """Enumerate the same explicitly bounded simple source universe independently."""
    sources, _ = _enumerate_simple_fully_cubic_sources_with_accounting(clause_count)
    return sources


def _source_universe_accounting(
    clause_sizes: Sequence[int],
    enumeration_stats: Mapping[int, Mapping[str, int]],
) -> dict[str, Any]:
    """Independently account for every row subset and filter outcome."""
    by_clause_count: dict[str, dict[str, int]] = {}
    total_row_subsets = 0
    total_sources = 0
    total_rejections = 0
    for clause_count in clause_sizes:
        require(
            clause_count in enumeration_stats,
            "enumeration statistics are missing a clause size",
        )
        observed = enumeration_stats[clause_count]
        expected = {
            "candidate_triples": comb(clause_count, 3),
            "naive_row_subsets": comb(comb(clause_count, 3), clause_count),
            "accepted_sources": 0,
            "degree_filter_rejections": 0,
        }
        for key in ("candidate_triples", "naive_row_subsets"):
            require(
                observed.get(key) == expected[key],
                f"source accounting mismatch for {key}",
            )
        accepted = _exact_int(
            observed.get("accepted_sources"),
            f"accepted source count for c={clause_count}",
            minimum=0,
        )
        rejected = _exact_int(
            observed.get("degree_filter_rejections"),
            f"degree-filter rejection count for c={clause_count}",
            minimum=0,
        )
        require(
            accepted + rejected == expected["naive_row_subsets"],
            "source accounting does not partition row subsets",
        )
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
    # and degree_S(v)=3 for every variable v; DP states are not returned.
    require(
        3 <= clause_count <= FULLY_CUBIC_C7_COUNT_CLAUSES,
        "count-only DP supports clause sizes from 3 through c=7",
    )

    # Generate all possible triples (as bitmasks) from clause_count variables.
    # Variables are 0-indexed here for bit manipulation convenience, 
    # corresponding to 1..clause_count in the problem description.
    triples = []
    for i in range(clause_count):
        for j in range(i + 1, clause_count):
            for k in range(j + 1, clause_count):
                mask = (1 << i) | (1 << j) | (1 << k)
                triples.append(mask)

    # Target degree bitmask: each of the clause_count variables must have degree 3.
    # Since we are summing degrees, and max degree is 3, we can track exact counts.
    # However, tracking exact counts in the state key is expensive.
    # Optimization: The state is (num_triples_selected, degrees_tuple).
    # degrees_tuple is a tuple of length clause_count with values 0..3.

    # Initial state: 0 triples selected, all degrees 0.
    # We use a dictionary for DP.
    # Key: (selected_count, degrees_tuple)
    # Value: number of ways to reach this state

    initial_degrees = tuple(0 for _ in range(clause_count))
    dp = {(0, initial_degrees): 1}

    # Iterate through each possible triple mask
    for mask in triples:
        new_dp = dict(dp)
        for (count, degrees), ways in dp.items():
            # If we've already selected 'clause_count' triples, we can't add more.
            # But since we iterate through ALL possible triples, we must ensure
            # we don't select the same triple twice or select more than needed.
            # The structure of the loop implies we process each triple once.
            # So if count == clause_count, we stop adding for this branch?
            # Actually, the original code continues if selected == clause_count.
            if count == clause_count:
                continue

            # Try adding this triple
            # Check if adding this triple violates degree constraints (degree > 3)
            # Also update degrees
            new_degrees_list = list(degrees)
            valid_addition = True

            # Decode the mask to find which variables are in this triple
            # We can iterate bits or precompute variable indices for each mask.
            # Since clause_count is small (<=7), iterating bits is fast.
            temp_mask = mask
            var_indices = []
            idx = 0
            while temp_mask:
                if temp_mask & 1:
                    var_indices.append(idx)
                temp_mask >>= 1
                idx += 1

            for var in var_indices:
                new_degrees_list[var] += 1
                if new_degrees_list[var] > 3:
                    valid_addition = False
                    break

            if not valid_addition:
                continue

            new_degrees_tuple = tuple(new_degrees_list)
            new_count = count + 1
            new_key = (new_count, new_degrees_tuple)

            # Accumulate ways
            if new_key in new_dp:
                new_dp[new_key] += ways
            else:
                new_dp[new_key] = ways
        dp = new_dp

    # The answer is the number of ways to reach state (clause_count, (3, 3, ..., 3))
    target_degrees = tuple(3 for _ in range(clause_count))
    return dp.get((clause_count, target_degrees), 0)


def _count_simple_fully_cubic_sources_c7() -> int:
    """Count c=7 sources without materializing formulas or certificates."""
    return _count_simple_fully_cubic_sources_dp(FULLY_CUBIC_C7_COUNT_CLAUSES)


def _verify_census_source(
    row: Any,
    expected_formula: tuple[tuple[int, int, int], ...],
) -> dict[str, Any]:
    require(isinstance(row, dict), "fully-cubic census source must be an object")
    require(
        set(row)
        == {
            "clauses",
            "formula",
            "connected",
            "candidate_assignments",
            "sat_candidates",
            "unsat_candidates",
            "conflict_precedence_violations",
            "emitted_certificate_records",
            "distinct_certificate_records",
            "distinct_projected_clauses",
            "cut_kinds",
            "subsumption_relations",
            "certificate_records",
            "emissions",
            "counterexamples",
        },
        "fully-cubic census source fields are not exact",
    )
    clauses = _exact_int(row["clauses"], "census source clauses", minimum=1)
    require(clauses == len(expected_formula), "census source clause count is wrong")
    source = _source([list(clause) for clause in expected_formula], clauses)
    require(all(degree == 3 for degree in source["degrees"]), "census source is not fully cubic")
    require(source["cubic"] == tuple(range(1, clauses + 1)), "census source cubic IDs are incomplete")
    formula = source["formula"]
    require(row["formula"] == [list(clause) for clause in formula], "census source formula changed")
    require(row["connected"] is _is_connected(formula, clauses), "census source connectivity is wrong")

    records = row["certificate_records"]
    emissions = row["emissions"]
    counterexamples = row["counterexamples"]
    require(isinstance(records, list), "census certificate records must be a list")
    require(isinstance(emissions, list), "census emissions must be a list")
    require(isinstance(counterexamples, list), "census counterexamples must be a list")

    record_keys: set[bytes] = set()
    projected_clauses: set[tuple[int, ...]] = set()
    checked_records: list[dict[str, Any]] = []
    for record_index, record in enumerate(records):
        require(isinstance(record, dict), f"census certificate record {record_index} is malformed")
        require(set(record) == {"cut", "subsumption"}, f"census certificate record {record_index} fields are not exact")
        cut = record["cut"]
        require(isinstance(cut, dict), f"census certificate record {record_index} cut is malformed")
        verify_obstruction_cut([list(clause) for clause in formula], clauses, cut)
        expected = _expected_subsumption(formula, cut)
        verify_cut_subsumption([list(clause) for clause in formula], cut, expected)
        require(record["subsumption"] == expected, f"census certificate record {record_index} witness is wrong")
        key = _canonical(cut)
        require(key not in record_keys, f"census certificate record {record_index} is duplicated")
        record_keys.add(key)
        projected_clauses.add(tuple(int(literal) for literal in cut["literals"]))
        checked_records.append(record)

    expected_unsat: set[tuple[int, ...]] = set()
    expected_counterexamples: list[dict[str, Any]] = []
    sat_candidates = 0
    cut_kinds: dict[str, int] = {}
    relations = {"equal": 0, "proper": 0, "null": 0}
    seen_emissions: set[tuple[int, ...]] = set()
    candidate_conflicts: dict[tuple[int, ...], int | None] = {}
    conflict_precedence_violations = 0
    for bits in itertools.product((0, 1), repeat=clauses):
        bits_key = tuple(bits)
        counts = tuple(
            sum(bits[variable - 1] for variable in clause)
            for clause in source["formula"]
        )
        first_conflict = next(
            (index for index, count in enumerate(counts) if count > 1),
            None,
        )
        candidate_conflicts[bits_key] = first_conflict
        if _candidate_is_sat(source, bits):
            sat_candidates += 1
            continue
        expected_unsat.add(bits_key)

    for emission_index, emission in enumerate(emissions):
        require(isinstance(emission, dict), f"census emission {emission_index} is malformed")
        require(set(emission) == {"bits", "record_index"}, f"census emission {emission_index} fields are not exact")
        raw_bits = emission["bits"]
        require(isinstance(raw_bits, list), f"census emission {emission_index} bits must be a list")
        require(len(raw_bits) == clauses, f"census emission {emission_index} bit width is wrong")
        bits = tuple(
            _exact_int(value, f"census emission {emission_index} bit", minimum=0)
            for value in raw_bits
        )
        require(all(value in (0, 1) for value in bits), f"census emission {emission_index} bit is not binary")
        require(bits in expected_unsat, f"census emission {emission_index} covers a SAT cube")
        require(bits not in seen_emissions, f"census emission {emission_index} is duplicated")
        seen_emissions.add(bits)
        record_index = _exact_int(emission["record_index"], f"census emission {emission_index} record index", minimum=0)
        require(record_index < len(checked_records), f"census emission {emission_index} record index is out of range")
        record = checked_records[record_index]
        cut = record["cut"]
        first_conflict = candidate_conflicts[bits]
        if first_conflict is not None:
            if (
                cut["kind"] != "overfill"
                or cut["conflict_clause"] != first_conflict
            ):
                conflict_precedence_violations += 1
        elif cut["kind"] == "overfill":
            conflict_precedence_violations += 1
        values = dict(zip(source["cubic"], bits))
        require(
            not any(_literal_is_true(literal, values) for literal in cut["literals"]),
            f"census emission {emission_index} does not falsify its projected cut",
        )
        kind = cut["kind"]
        require(kind in ("overfill", "tutte"), f"census emission {emission_index} has an unknown cut kind")
        cut_kinds[kind] = cut_kinds.get(kind, 0) + 1
        witness = record["subsumption"]
        relation = "null" if witness is None else witness["relation"]
        relations[relation] += 1
        if relation != "equal":
            expected_counterexamples.append({
                "bits": list(bits),
                "record_index": record_index,
                "cut": cut,
                "subsumption": witness,
            })

    require(seen_emissions == expected_unsat, "census emissions do not cover exactly every UNSAT cube")
    require(row["candidate_assignments"] == 1 << clauses, "census candidate count is wrong")
    require(row["sat_candidates"] == sat_candidates, "census SAT candidate count is wrong")
    require(row["unsat_candidates"] == len(expected_unsat), "census UNSAT candidate count is wrong")
    require(
        row["conflict_precedence_violations"] == conflict_precedence_violations,
        "census conflict-precedence count is wrong",
    )
    require(row["emitted_certificate_records"] == len(emissions), "census emitted-record count is wrong")
    require(row["distinct_certificate_records"] == len(records), "census certificate-record count is wrong")
    require(row["distinct_projected_clauses"] == len(projected_clauses), "census projected-clause count is wrong")
    require(row["cut_kinds"] == cut_kinds, "census cut-kind counts are wrong")
    require(row["subsumption_relations"] == relations, "census subsumption counts are wrong")
    require(counterexamples == expected_counterexamples, "census counterexamples do not match emitted cuts")
    return row


def _verify_fully_cubic_census(census: Any) -> dict[str, Any]:
    require(isinstance(census, dict), "fully-cubic census must be an object")
    require(
        set(census)
        == {
            "definition",
            "producer_path",
            "min_clauses",
            "max_clauses",
            "max_variables",
            "complete_cutoff",
            "clause_sizes",
            "universe",
            "sources",
            "summary",
        },
        "fully-cubic census fields are not exact",
    )
    require(
        census["definition"]
        == (
            "simple canonical labelled c-by-c incidence matrices with three "
            "ones in every row and column; duplicate source triples excluded"
        ),
        "fully-cubic census definition changed",
    )
    require(census["producer_path"] == "evaluate_alias_candidate", "census producer path is not explicit")
    require(census["min_clauses"] == FULLY_CUBIC_CENSUS_MIN_CLAUSES, "census minimum is wrong")
    require(census["max_clauses"] == FULLY_CUBIC_CENSUS_MAX_CLAUSES, "census maximum is wrong")
    require(census["max_variables"] == FULLY_CUBIC_CENSUS_MAX_VARIABLES, "census variable bound is wrong")
    require(
        census["complete_cutoff"] == FULLY_CUBIC_CENSUS_COMPLETE_CUTOFF,
        "census complete cutoff is wrong",
    )
    clause_sizes = list(
        range(FULLY_CUBIC_CENSUS_MIN_CLAUSES, FULLY_CUBIC_CENSUS_MAX_CLAUSES + 1)
    )
    require(census["clause_sizes"] == clause_sizes, "census clause sizes are wrong")
    require(isinstance(census["sources"], list), "fully-cubic census sources must be a list")

    expected_sources: list[tuple[tuple[int, int, int], ...]] = []
    enumeration_stats: dict[int, dict[str, int]] = {}
    for clauses in clause_sizes:
        formulas, stats = _enumerate_simple_fully_cubic_sources_with_accounting(clauses)
        enumeration_stats[clauses] = stats
        expected_sources.extend(formulas)
    expected_universe = _source_universe_accounting(clause_sizes, enumeration_stats)
    require(census["universe"] == expected_universe, "census universe accounting is wrong")
    require(len(census["sources"]) == len(expected_sources), "census source count is wrong")
    audited_sources = [
        _verify_census_source(row, formula)
        for row, formula in zip(census["sources"], expected_sources)
    ]

    def total(key: str) -> int:
        return sum(int(row[key]) for row in audited_sources)

    cut_kinds: dict[str, int] = {}
    relations = {"equal": 0, "proper": 0, "null": 0}
    for row in audited_sources:
        for kind, count in row["cut_kinds"].items():
            cut_kinds[kind] = cut_kinds.get(kind, 0) + int(count)
        for relation, count in row["subsumption_relations"].items():
            relations[relation] += int(count)
    expected_summary = {
        "sources": len(audited_sources),
        "connected_sources": sum(bool(row["connected"]) for row in audited_sources),
        "candidate_assignments": total("candidate_assignments"),
        "sat_candidates": total("sat_candidates"),
        "unsat_candidates": total("unsat_candidates"),
        "emitted_certificate_records": total("emitted_certificate_records"),
        "distinct_certificate_records": total("distinct_certificate_records"),
        "distinct_projected_clauses": total("distinct_projected_clauses"),
        "conflict_precedence_violations": total("conflict_precedence_violations"),
        "cut_kinds": cut_kinds,
        "subsumption_relations": relations,
        "counterexamples": sum(len(row["counterexamples"]) for row in audited_sources),
    }
    require(census["summary"] == expected_summary, "fully-cubic census summary is wrong")
    return expected_summary


def _literal_is_true(literal: int, values: Mapping[int, int]) -> bool:
    value = values[abs(literal)]
    return value == 1 if literal > 0 else value == 0


def _verify_scan(
    formula: Sequence[Sequence[int]],
    variable_count: int,
    scan: Any,
) -> dict[str, int]:
    source = _source(formula, variable_count)
    require(isinstance(scan, dict), "candidate scan must be an object")
    require(set(scan) == {"outcomes", "cuts"}, "candidate scan fields are not exact")
    outcomes = scan["outcomes"]
    cuts = scan["cuts"]
    require(isinstance(outcomes, list), "candidate outcomes must be a list")
    require(isinstance(cuts, list), "candidate cuts must be a list")
    expected_outcomes = 1 << len(source["cubic"])
    require(len(outcomes) == expected_outcomes, "candidate scan does not cover its cubic cube")

    cut_keys: set[bytes] = set()
    for index, record in enumerate(cuts):
        require(isinstance(record, dict), f"candidate cut {index} is malformed")
        require(set(record) == {"cut", "subsumption"}, f"candidate cut {index} fields are not exact")
        cut = record["cut"]
        require(isinstance(cut, dict), f"candidate cut {index} payload is malformed")
        verify_obstruction_cut(formula, variable_count, cut)
        verify_cut_subsumption(formula, cut, record["subsumption"])
        key = _canonical(cut)
        require(key not in cut_keys, f"candidate cut {index} is duplicated")
        cut_keys.add(key)

    referenced: set[int] = set()
    for branch, bits in enumerate(itertools.product((0, 1), repeat=len(source["cubic"]))):
        outcome = outcomes[branch]
        require(isinstance(outcome, int) and not isinstance(outcome, bool), f"candidate outcome {branch} is not an integer")
        candidate_sat = _candidate_is_sat(source, bits)
        if candidate_sat:
            require(outcome == -1, f"candidate {branch} incorrectly carries an obstruction")
            continue
        require(0 <= outcome < len(cuts), f"candidate {branch} does not reference a cut")
        referenced.add(outcome)
        cut = cuts[outcome]["cut"]
        values = dict(zip(source["cubic"], bits))
        require(
            not any(_literal_is_true(literal, values) for literal in cut["literals"]),
            f"candidate {branch} does not falsify its obstruction cut",
        )
    require(referenced == set(range(len(cuts))), "candidate scan stores an unreferenced cut")
    return {"assignments": len(outcomes), "distinct_cuts": len(cuts)}


def _models(source: Mapping[str, Any]) -> list[list[int]]:
    return [
        list(bits)
        for bits in itertools.product((0, 1), repeat=source["variables"])
        if all(sum(bits[variable - 1] for variable in clause) == 1 for clause in source["formula"])
    ]


def _result_cut_witnesses(
    formula: Sequence[Sequence[int]],
    variable_count: int,
    result: Mapping[str, Any],
) -> list[dict[str, Any] | None]:
    cuts = result["cuts"]
    require(isinstance(cuts, list), "result cuts must be a list")
    checked: list[dict[str, Any] | None] = []
    for index, cut in enumerate(cuts):
        require(isinstance(cut, dict), f"result cut {index} is malformed")
        verify_obstruction_cut(formula, variable_count, cut)
        expected = _expected_subsumption(formula, cut)
        verify_cut_subsumption(formula, cut, expected)
        checked.append(expected)
    return checked


def _verify_source_refutation(
    fully_cubic: bool,
    result: Mapping[str, Any],
    witnesses: Sequence[dict[str, Any] | None],
    refutation: Any,
) -> None:
    if not fully_cubic or result["status"] != "unsat":
        require(refutation is None, "non-UNSAT fully-cubic result carries a source refutation")
        return
    require(isinstance(refutation, dict), "fully-cubic UNSAT result lacks a source refutation")
    require(
        set(refutation) == {
            "cnf_indices",
            "backend_inference_steps",
            "added_weakenings",
            "total_inference_steps",
        },
        "source refutation fields are not exact",
    )
    indices = refutation["cnf_indices"]
    require(isinstance(indices, list), "source refutation indices must be a list")
    expected_indices = [witness["cnf_index"] for witness in witnesses if witness is not None]
    require(indices == expected_indices, "source refutation does not name its source clauses")
    proof = result["proof"]
    require(isinstance(proof, dict) and isinstance(proof.get("stats"), dict), "source refutation proof stats are missing")
    backend_steps = _exact_int(proof["stats"].get("inference_steps"), "backend inference steps", minimum=0)
    require(_exact_int(refutation["backend_inference_steps"], "source refutation backend steps", minimum=0) == backend_steps, "source refutation backend count is wrong")
    require(_exact_int(refutation["added_weakenings"], "source refutation weakenings", minimum=0) == 0, "fully-cubic source refutation added a weakening")
    require(_exact_int(refutation["total_inference_steps"], "source refutation total steps", minimum=0) == backend_steps, "source refutation total count is wrong")
    require(all(witness is not None and witness["relation"] == "equal" for witness in witnesses), "fully-cubic cut is not an exact source clause")


def _verify_control(
    formula: Sequence[Sequence[int]],
    variable_count: int,
    control: Any,
) -> dict[str, Any]:
    require(isinstance(control, dict), "certificate control must be an object")
    require(set(control) == {"name", "cut", "subsumption"}, "certificate control fields are not exact")
    require(isinstance(control["name"], str) and bool(control["name"]), "certificate control name is invalid")
    cut = control["cut"]
    require(isinstance(cut, dict), "certificate control cut is malformed")
    verify_obstruction_cut(formula, variable_count, cut)
    verify_cut_subsumption(formula, cut, control["subsumption"])
    expected = _expected_subsumption(formula, cut)
    require(control["subsumption"] == expected, "certificate control witness is wrong")
    return control


def _refusal_controls(
    formula: Sequence[Sequence[int]],
    variable_count: int,
    controls: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Apply deterministic malformed mutations and require each refusal."""
    counts = {
        "bad_witness": 0,
        "bad_kind": 0,
        "bad_literal": 0,
        "bad_barrier": 0,
        "missing_boundary_witness": 0,
    }

    def expect_refusal(action: Any, label: str) -> None:
        try:
            action()
        except (AssertionError, ValueError, KeyError, TypeError):
            counts[label] += 1
        else:
            raise VerificationError(f"malformed control {label} was accepted")

    for control in controls:
        witness = control["subsumption"]
        if isinstance(witness, dict):
            bad_witness = copy.deepcopy(witness)
            bad_witness["cnf_index"] = -1
            expect_refusal(
                lambda bad_witness=bad_witness, control=control: verify_cut_subsumption(
                    formula, control["cut"], bad_witness
                ),
                "bad_witness",
            )
            break

    for control in controls:
        bad_kind = copy.deepcopy(control["cut"])
        bad_kind["kind"] = "invalid"
        expect_refusal(
            lambda bad_kind=bad_kind: verify_obstruction_cut(formula, variable_count, bad_kind),
            "bad_kind",
        )
        break

    for control in controls:
        bad_literal = copy.deepcopy(control["cut"])
        bad_literal["literals"] = list(bad_literal["literals"]) + [0]
        expect_refusal(
            lambda bad_literal=bad_literal: verify_obstruction_cut(formula, variable_count, bad_literal),
            "bad_literal",
        )
        break

    for control in controls:
        if control["cut"]["kind"] == "tutte":
            bad_barrier = copy.deepcopy(control["cut"])
            if bad_barrier["barrier"]:
                bad_barrier["barrier"].append(bad_barrier["barrier"][0])
            else:
                bad_barrier["barrier"].append(variable_count + 1)
            expect_refusal(
                lambda bad_barrier=bad_barrier: verify_obstruction_cut(formula, variable_count, bad_barrier),
                "bad_barrier",
            )
            break

    for control in controls:
        cut = control["cut"]
        if cut["kind"] == "tutte" and cut["boundary_witnesses"]:
            bad_boundary = copy.deepcopy(cut)
            endpoint = bad_boundary["boundary_witnesses"][0][0]
            bad_boundary["boundary_witnesses"] = [
                witness for witness in bad_boundary["boundary_witnesses"] if witness[0] != endpoint
            ]
            expect_refusal(
                lambda bad_boundary=bad_boundary: verify_obstruction_cut(formula, variable_count, bad_boundary),
                "missing_boundary_witness",
            )
            break
    return counts


def _verify_case(case: Any, index: int) -> dict[str, Any]:
    require(isinstance(case, dict), f"case {index} is malformed")
    require(
        set(case)
        == {
            "name",
            "formula",
            "variable_count",
            "fully_cubic",
            "connected",
            "counting_obstruction",
            "cnf",
            "candidate_scan",
            "certificate_controls",
            "solver",
        },
        f"case {index} fields are not exact",
    )
    name = case["name"]
    require(isinstance(name, str) and bool(name), f"case {index} name is invalid")
    variables = _exact_int(case["variable_count"], f"case {index} variable_count", minimum=1)
    source = _source(case["formula"], variables)
    formula = source["formula"]
    expected_formula = [list(clause) for clause in formula]
    require(case["formula"] == expected_formula, f"case {index}: formula is not canonical")
    fully_cubic = all(degree == 3 for degree in source["degrees"])
    require(case["fully_cubic"] is fully_cubic, f"case {index}: fully-cubic flag is wrong")
    connected = _is_connected(formula, variables)
    require(case["connected"] is connected, f"case {index}: connected flag is wrong")
    expected_counting = (len(formula) % 3 != 0) if fully_cubic else None
    require(case["counting_obstruction"] is expected_counting, f"case {index}: counting flag is wrong")
    require(case["cnf"] == exact_one_cnf(formula), f"case {index}: source CNF expansion is wrong")

    scan = case["candidate_scan"]
    scan_report = None
    if variables <= 10:
        require(scan is not None, f"case {index}: bounded candidate scan is missing")
        scan_report = _verify_scan(formula, variables, scan)
    else:
        require(scan is None, f"case {index}: candidate scan exceeds its declared bound")

    solver = case["solver"]
    require(isinstance(solver, dict), f"case {index}: solver receipt is malformed")
    require(
        set(solver) == {"result", "cut_subsumptions", "restart_state_sha256", "source_refutation"},
        f"case {index}: solver fields are not exact",
    )
    _digest(solver["restart_state_sha256"], f"case {index} restart_state_sha256")
    result = solver["result"]
    report = verify_result(result)
    require(result["formula"] == expected_formula, f"case {index}: result formula differs from case source")
    require(result["variable_count"] == variables, f"case {index}: result variable count differs")
    witnesses = _result_cut_witnesses(formula, variables, result)
    require(solver["cut_subsumptions"] == witnesses, f"case {index}: solver witness ledger differs")
    if fully_cubic:
        require(
            all(witness is not None and witness["relation"] == "equal" for witness in witnesses),
            f"case {index}: fully-cubic production cut is not a source clause",
        )
        require(len(result["cuts"]) <= 4 * len(formula), f"case {index}: cut count exceeds source CNF bound")
    _verify_source_refutation(fully_cubic, result, witnesses, solver["source_refutation"])

    controls = case["certificate_controls"]
    require(isinstance(controls, list), f"case {index}: certificate controls are missing")
    checked_controls = [_verify_control(formula, variables, control) for control in controls]

    models: list[list[int]] | None = None
    if variables <= 16:
        models = _models(source)
        if result["status"] == "sat":
            require(result["assignment"] in models, f"case {index}: SAT assignment disagrees with source enumeration")
        elif result["status"] == "unsat":
            require(not models, f"case {index}: UNSAT result disagrees with source enumeration")

    return {
        "name": name,
        "status": report["status"],
        "variables": variables,
        "clauses": len(formula),
        "fully_cubic": fully_cubic,
        "connected": connected,
        "cuts": len(result["cuts"]),
        "candidate_assignments": 0 if scan_report is None else scan_report["assignments"],
        "candidate_distinct_cuts": 0 if scan_report is None else scan_report["distinct_cuts"],
        "controls": checked_controls,
        "models": 0 if models is None else len(models),
    }


def verify(path: Path = RECEIPT) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(receipt, dict), "complexity receipt must be an object")
    require(
        set(receipt) == {"schema", "cases", "fully_cubic_census", "summary"},
        "complexity receipt fields are not exact",
    )
    require(receipt.get("schema") == SCHEMA, "complexity receipt schema mismatch")
    cases = receipt["cases"]
    require(isinstance(cases, list) and bool(cases), "complexity receipt cases are missing")
    census_summary = _verify_fully_cubic_census(receipt["fully_cubic_census"])
    names: set[str] = set()
    audited: list[dict[str, Any]] = []
    refusal = {
        "bad_witness": 0,
        "bad_kind": 0,
        "bad_literal": 0,
        "bad_barrier": 0,
        "missing_boundary_witness": 0,
    }
    for index, case in enumerate(cases):
        audited_case = _verify_case(case, index)
        require(audited_case["name"] not in names, f"case {index}: duplicate case name")
        names.add(audited_case["name"])
        for key, value in _refusal_controls(
            case["formula"],
            case["variable_count"],
            case["certificate_controls"],
        ).items():
            refusal[key] += value
        audited.append(audited_case)

    fully_cubic = [case for case in audited if case["fully_cubic"]]
    mixed = [case for case in audited if not case["fully_cubic"]]
    strict_weakenings = sum(
        control["subsumption"] is not None and control["subsumption"]["relation"] == "proper"
        for case in audited
        for control in case["controls"]
    )
    nonlocal_mixed = sum(
        record["subsumption"] is None
        for case in cases
        if not case["fully_cubic"] and case["candidate_scan"] is not None
        for record in case["candidate_scan"]["cuts"]
    )
    summary = {
        "cases": len(cases),
        "fully_cubic_cases": len(fully_cubic),
        "mixed_cases": len(mixed),
        "sat": sum(case["status"] == "sat" for case in audited),
        "unsat": sum(case["status"] == "unsat" for case in audited),
        "exhausted": sum(case["status"] == "exhausted" for case in audited),
        "candidate_assignments": sum(case["candidate_assignments"] for case in audited),
        "candidate_distinct_cuts": sum(case["candidate_distinct_cuts"] for case in audited),
        "candidate_nonlocal_mixed_cuts": nonlocal_mixed,
        "retained_cuts": sum(case["cuts"] for case in audited),
        "fully_cubic_retained_cuts": sum(case["cuts"] for case in fully_cubic),
        "fully_cubic_max_cuts": max(case["cuts"] for case in fully_cubic),
        "fully_cubic_max_cut_bound": max(4 * case["clauses"] for case in fully_cubic),
        "source_refutations": sum(
            case["fully_cubic"] and case["status"] == "unsat" for case in audited
        ),
        "certificate_controls": sum(len(case["controls"]) for case in audited),
        "strict_weakenings": strict_weakenings,
        "fully_cubic_census_sources": census_summary["sources"],
        "fully_cubic_census_candidates": census_summary["candidate_assignments"],
        "fully_cubic_census_emitted_records": census_summary["emitted_certificate_records"],
        "fully_cubic_census_projected_clauses": census_summary["distinct_projected_clauses"],
        "fully_cubic_census_certificate_records": census_summary["distinct_certificate_records"],
        "fully_cubic_census_counterexamples": census_summary["counterexamples"],
        "fully_cubic_census_conflict_precedence_violations": census_summary["conflict_precedence_violations"],
    }
    require(receipt["summary"] == summary, "complexity summary does not match independently audited cases")
    require(all(case["connected"] for case in audited), "receipt contains a disconnected source")
    require(summary["fully_cubic_cases"] > 0 and summary["mixed_cases"] > 0, "receipt lacks both source regimes")
    require(summary["candidate_nonlocal_mixed_cuts"] > 0, "receipt lacks a mixed nonlocal cut")
    require(summary["strict_weakenings"] > 0, "receipt lacks a strict source-clause weakening control")
    require(summary["source_refutations"] > 0, "receipt lacks a fully-cubic source refutation")

    all_controls = [control for case in audited for control in case["controls"]]
    require(
        any(
            case["fully_cubic"]
            and control["subsumption"] is not None
            and control["subsumption"]["relation"] == "proper"
            for case in audited
            for control in case["controls"]
        ),
        "receipt lacks a fully-cubic strict weakening control",
    )
    require(
        any(
            control["cut"]["kind"] == "tutte"
            and bool(control["cut"]["barrier"])
            and bool(control["cut"]["boundary_witnesses"])
            for control in all_controls
        ),
        "receipt lacks a nonempty-barrier boundary-witness control",
    )
    require(
        any(
            control["cut"]["kind"] == "tutte"
            and bool(control["cut"]["barrier"])
            and any(literal > 0 for literal in control["cut"]["literals"])
            and any(literal < 0 for literal in control["cut"]["literals"])
            for control in all_controls
        ),
        "receipt lacks a signed nonempty-barrier control",
    )
    require(all(value > 0 for value in refusal.values()), "malformed certificate controls were not all refused")

    output = {
        "summary": summary,
        "refusal_controls": refusal,
        "refusal_controls_refused": sum(refusal.values()),
    }
    print(json.dumps(output, sort_keys=True))
    print("ALL CHECKS PASSED")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", type=Path, default=RECEIPT)
    arguments = parser.parse_args()
    verify(arguments.path)
