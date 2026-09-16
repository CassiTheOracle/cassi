"""Proof-carrying continuation for degree-two/degree-three exact-one formulas.

The cubic variables are fixed by a candidate cube.  Clauses containing one
fixed-one cubic variable are already satisfied, clauses containing two are an
immediate overfill conflict, and the remaining clauses form a graph whose
edges are degree-two variables.  A perfect matching lifts to a source model;
a Tutte barrier lifts to a clause over the cubic cube, including the pins
needed to keep degree-two boundary edges from reopening.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from cassi_alias_exact_one_field import (
    RecognizedAliasFormula,
    recognize_degree_two_three_exact_one,
)
from cassi_general_matched_field import (
    deterministic_maximum_matching,
    deterministic_tutte_barrier,
)
from cassi_field_regions import KernelResult


class AliasObstructionError(ValueError):
    """Malformed candidate or an internally inconsistent obstruction."""


Graph = tuple[tuple[int, ...], ...]


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_recognized(recognized: RecognizedAliasFormula) -> RecognizedAliasFormula:
    if not isinstance(recognized, RecognizedAliasFormula):
        raise AliasObstructionError("recognized must be RecognizedAliasFormula")
    try:
        variable_count = len(recognized.degrees)
        checked = recognize_degree_two_three_exact_one(
            recognized.formula,
            variable_count=variable_count,
        )
    except Exception as exc:
        raise AliasObstructionError("recognized source is malformed") from exc
    if (
        checked.formula != recognized.formula
        or checked.degrees != recognized.degrees
        or checked.cubic_variables != recognized.cubic_variables
        or checked.incidence != recognized.incidence
    ):
        raise AliasObstructionError("recognized source metadata is inconsistent")
    return checked


def _validate_bits(
    recognized: RecognizedAliasFormula,
    cubic_bits: Sequence[int],
) -> tuple[int, ...]:
    if isinstance(cubic_bits, (str, bytes)) or not isinstance(cubic_bits, Sequence):
        raise AliasObstructionError("cubic_bits must be an ordered sequence")
    if len(cubic_bits) != len(recognized.cubic_variables):
        raise AliasObstructionError("cubic_bits length does not match cubic variables")
    bits = tuple(cubic_bits)
    if any(not _is_int(bit) or bit not in (0, 1) for bit in bits):
        raise AliasObstructionError("cubic_bits must contain only integer 0/1 values")
    return bits


def _source_satisfies(
    formula: Sequence[Sequence[int]],
    assignment: Sequence[int],
) -> bool:
    return all(sum(assignment[variable - 1] for variable in clause) == 1 for clause in formula)


def _context(
    recognized: RecognizedAliasFormula,
    bits: tuple[int, ...],
) -> dict[str, Any]:
    cubic_value = dict(zip(recognized.cubic_variables, bits))
    counts = tuple(
        sum(cubic_value.get(variable, 0) for variable in clause)
        for clause in recognized.formula
    )
    conflict = next((index for index, count in enumerate(counts) if count > 1), None)
    residual = tuple(index for index, count in enumerate(counts) if count == 0)
    residual_set = set(residual)
    local_for = {clause: local for local, clause in enumerate(residual)}
    sources_for_pair: dict[tuple[int, int], list[int]] = {}
    # Parallel degree-two variables are retained as source lists while the
    # graph itself remains a simple graph, matching the public matcher API.
    for variable, degree in enumerate(recognized.degrees, 1):
        if degree != 2:
            continue
        incident = recognized.incidence[variable - 1]
        if len(incident) != 2:
            raise AliasObstructionError("degree-two incidence metadata is malformed")
        if all(clause in residual_set for clause in incident):
            left, right = sorted((local_for[incident[0]], local_for[incident[1]]))
            if left == right:
                raise AliasObstructionError("degree-two variable has a self-loop")
            sources_for_pair.setdefault((left, right), []).append(variable)
    adjacency = [set() for _ in residual]
    for left, right in sorted(sources_for_pair):
        adjacency[left].add(right)
        adjacency[right].add(left)
    graph: Graph = tuple(tuple(sorted(neighbors)) for neighbors in adjacency)
    return {
        "bits": bits,
        "cubic_value": cubic_value,
        "counts": counts,
        "conflict": conflict,
        "residual": residual,
        "residual_set": residual_set,
        "sources_for_pair": sources_for_pair,
        "graph": graph,
    }


def _components(
    residual: Sequence[int],
    graph: Graph,
    removed_local: set[int],
) -> list[list[int]]:
    """Return residual graph components as sorted source clause IDs."""
    unseen = set(range(len(graph))) - removed_local
    result: list[list[int]] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        members: list[int] = []
        while stack:
            local = stack.pop()
            members.append(residual[local])
            for neighbor in graph[local]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        result.append(sorted(members))
    result.sort(key=lambda component: component[0])
    return result


def _tutte_barrier(
    graph: Graph,
    maximum_size: int,
) -> tuple[set[int], int]:
    """Get a checked barrier, repairing disconnected-helper corner cases.

    The public extractor is the normal path.  A disconnected graph with
    multiple odd components has the immediate valid barrier ``S = empty``;
    when the helper cannot recognize that shape, this fallback avoids turning
    a valid obstruction into an implementation error.  Even components are
    reduced to an induced non-perfect component and retried through the same
    public extractor.
    """
    count = len(graph)

    def valid(candidate: set[int]) -> bool:
        components = _components(tuple(range(count)), graph, candidate)
        return sum(len(component) % 2 for component in components) > len(candidate)

    components = _components(tuple(range(count)), graph, set())
    if sum(len(component) % 2 for component in components) > 0:
        # count is even here, so a positive number of odd components is at
        # least two and S=empty satisfies Tutte's strict inequality.  Detect
        # this before calling the public helper so run counters stay exact.
        return set(), 0

    def induced_barrier(
        component: list[int],
    ) -> tuple[tuple[set[int], int] | None, int]:
        local_for = {vertex: index for index, vertex in enumerate(component)}
        induced: Graph = tuple(
            tuple(sorted(local_for[neighbor] for neighbor in graph[vertex] if neighbor in local_for))
            for vertex in component
        )
        submates, _, _ = deterministic_maximum_matching(induced)
        subsize = sum(mate != -1 for mate in submates) // 2
        if 2 * subsize == len(component):
            return None, 1
        try:
            subbarrier, subruns = deterministic_tutte_barrier(induced, subsize)
        except Exception as exc:
            raise AliasObstructionError("public Tutte barrier failed on a non-perfect component") from exc
        mapped = {component[local] for local in subbarrier}
        if not valid(mapped):
            return None, 1 + subruns
        # The induced maximum matching above is an additional barrier
        # construction run, and must be included in the ledger.
        return (mapped, 1 + subruns), 1 + subruns

    if len(components) > 1:
        barrier_runs = 0
        for component in components:
            candidate, spent = induced_barrier(component)
            barrier_runs += spent
            if candidate is not None:
                return candidate[0], barrier_runs
        raise AliasObstructionError("no valid Tutte barrier was produced for a non-perfect graph")


    try:
        candidate, runs = deterministic_tutte_barrier(graph, maximum_size)
        candidate = set(candidate)
        if valid(candidate):
            return candidate, runs
    except Exception:
        pass
    raise AliasObstructionError("no valid Tutte barrier was produced for a non-perfect graph")


def _validate_barrier(
    barrier: Sequence[int],
    residual: tuple[int, ...],
) -> list[int]:
    if isinstance(barrier, (str, bytes)) or not isinstance(barrier, Sequence):
        raise AliasObstructionError("barrier must be an ordered sequence")
    values = list(barrier)
    if any(not _is_int(value) for value in values):
        raise AliasObstructionError("barrier clause IDs must be integers")
    if values != sorted(set(values)):
        raise AliasObstructionError("barrier must be sorted and duplicate-free")
    residual_set = set(residual)
    if any(value not in residual_set for value in values):
        raise AliasObstructionError("barrier must contain residual clause IDs")
    return values


def _make_cut(
    recognized: RecognizedAliasFormula,
    context: dict[str, Any],
    *,
    barrier: Sequence[int],
    conflict_clause: int | None,
) -> dict[str, Any]:
    residual = context["residual"]
    counts = context["counts"]
    graph: Graph = context["graph"]
    if conflict_clause is not None:
        if not _is_int(conflict_clause) or not 0 <= conflict_clause < len(recognized.formula):
            raise AliasObstructionError("conflict_clause is outside the source formula")
        clause = recognized.formula[conflict_clause]
        selected = [variable for variable in clause if context["cubic_value"].get(variable, 0) == 1]
        if counts[conflict_clause] <= 1 or len(selected) < 2:
            raise AliasObstructionError("conflict_clause is not an overfilled clause")
        selected = sorted(selected)
        literals = sorted((-variable for variable in selected[:2]), key=lambda value: abs(value))
        return {
            "kind": "overfill",
            "literals": literals,
            "conflict_clause": conflict_clause,
            "barrier": [],
            "components": [],
            "boundary_witnesses": [],
        }

    barrier_values = _validate_barrier(barrier, residual)
    removed_local = {residual.index(clause) for clause in barrier_values}
    components = _components(residual, graph, removed_local)
    odd_components = [component for component in components if len(component) % 2]
    if len(odd_components) <= len(barrier_values):
        raise AliasObstructionError("barrier does not satisfy Tutte's odd-component inequality")
    if len(residual) % 2 == 1 and barrier_values:
        raise AliasObstructionError("odd residual requires an empty barrier")

    # A certificate needs only |S|+1 odd components.  Selecting them in
    # component order keeps the result canonical and avoids unnecessary pins.
    selected_components = odd_components[: len(barrier_values) + 1]
    selected_set = {clause for component in selected_components for clause in component}

    positive: set[int] = set()
    for clause in sorted(selected_set):
        for variable in recognized.formula[clause]:
            if variable in context["cubic_value"]:
                if context["cubic_value"][variable] != 0:
                    raise AliasObstructionError("selected residual component contains a cubic one")
                positive.add(variable)

    witnesses: set[tuple[int, int]] = set()
    # Inspect source degree-two edges, rather than only collapsed graph edges,
    # so parallel edges and every boundary endpoint are covered explicitly.
    for variable, degree in enumerate(recognized.degrees, 1):
        if degree != 2:
            continue
        left_clause, right_clause = recognized.incidence[variable - 1]
        for inside, outside in ((left_clause, right_clause), (right_clause, left_clause)):
            if inside not in selected_set or outside in selected_set or outside in barrier_values:
                continue
            if outside in context["residual_set"]:
                # Such an edge would join two members of one graph component;
                # reaching this branch means the graph/source reconstruction is
                # inconsistent, not that a weaker full-assignment ban is valid.
                raise AliasObstructionError("residual boundary edge escaped a graph component")
            selected = [
                candidate
                for candidate in recognized.formula[outside]
                if candidate in context["cubic_value"]
                and context["cubic_value"][candidate] == 1
            ]
            if len(selected) != 1:
                raise AliasObstructionError("inactive boundary clause lacks one selected cubic witness")
            witnesses.add((outside, selected[0]))

    negative = {variable for _, variable in witnesses}
    if positive & negative:
        raise AliasObstructionError("cut requires contradictory cubic pins")
    literals = sorted(
        [*positive, *(-variable for variable in negative)],
        key=lambda value: abs(value),
    )
    witness_list = [[clause, variable] for clause, variable in sorted(witnesses)]
    return {
        "kind": "tutte",
        "literals": literals,
        "conflict_clause": None,
        "barrier": barrier_values,
        "components": [list(component) for component in selected_components],
        "boundary_witnesses": witness_list,
    }


def derive_obstruction_cut(
    recognized: RecognizedAliasFormula,
    cubic_bits: Sequence[int],
    *,
    barrier: Sequence[int] = (),
    conflict_clause: int | None = None,
) -> dict[str, Any]:
    """Derive and validate one generalized clause excluding a cubic cube."""
    source = _validate_recognized(recognized)
    bits = _validate_bits(source, cubic_bits)
    context = _context(source, bits)
    # Validate even an otherwise-unused barrier: silently accepting malformed
    # caller data would make a later certificate failure hard to diagnose.
    barrier_values = _validate_barrier(barrier, context["residual"])
    actual_conflict = context["conflict"]
    if conflict_clause is not None and conflict_clause != actual_conflict:
        raise AliasObstructionError("conflict_clause is not the first source overfill")
    if actual_conflict is not None:
        if barrier_values:
            raise AliasObstructionError("overfill obstruction cannot carry a barrier")
        return _make_cut(source, context, barrier=(), conflict_clause=actual_conflict)
    return _make_cut(source, context, barrier=barrier_values, conflict_clause=None)


def _matching_edges(
    residual: tuple[int, ...],
    mates: Sequence[int],
    sources_for_pair: dict[tuple[int, int], list[int]],
) -> list[list[int]]:
    result: list[list[int]] = []
    for local, mate in enumerate(mates):
        if mate != -1 and local < mate:
            pair = (local, mate)
            try:
                variable = min(sources_for_pair[pair])
            except (KeyError, ValueError) as exc:
                raise AliasObstructionError("matching returned a non-source edge") from exc
            result.append([residual[local], residual[mate], variable])
    return result


def evaluate_alias_candidate(
    recognized: RecognizedAliasFormula,
    cubic_bits: Sequence[int],
) -> dict[str, Any]:
    """Evaluate one cubic assignment and carry its matching/obstruction proof."""
    source = _validate_recognized(recognized)
    bits = _validate_bits(source, cubic_bits)
    context = _context(source, bits)
    cubic_value = context["cubic_value"]
    conflict = context["conflict"]
    empty_work = {
        "matching_runs": 0,
        "barrier_matching_runs": 0,
        "initial_edge_scans": 0,
        "blossom_contractions": 0,
        "matching_work_bound": 0,
    }
    if conflict is not None:
        return {
            "status": "unsat",
            "assignment": None,
            "matching": [],
            "cut": _make_cut(source, context, barrier=(), conflict_clause=conflict),
            "work": empty_work,
        }

    residual = context["residual"]
    if len(residual) % 2:
        return {
            "status": "unsat",
            "assignment": None,
            "matching": [],
            "cut": _make_cut(source, context, barrier=(), conflict_clause=None),
            "work": empty_work,
        }

    graph: Graph = context["graph"]
    mates, scans, contractions = deterministic_maximum_matching(graph)
    matching = _matching_edges(residual, mates, context["sources_for_pair"])
    matching_size = len(matching)
    if 2 * matching_size == len(residual):
        assignment = [0] * len(source.degrees)
        for variable, bit in cubic_value.items():
            assignment[variable - 1] = bit
        for _, _, variable in matching:
            assignment[variable - 1] = 1
        if not _source_satisfies(source.formula, assignment):
            raise AliasObstructionError("residual perfect matching produced an invalid assignment")
        return {
            "status": "sat",
            "assignment": assignment,
            "matching": matching,
            "cut": None,
            "work": {
                "matching_runs": 1,
                "barrier_matching_runs": 0,
                "initial_edge_scans": scans,
                "blossom_contractions": contractions,
                "matching_work_bound": len(source.formula) ** 3,
            },
        }

    barrier_local, barrier_runs = _tutte_barrier(graph, matching_size)
    barrier = sorted(residual[local] for local in barrier_local)
    cut = derive_obstruction_cut(source, bits, barrier=barrier)
    return {
        "status": "unsat",
        "assignment": None,
        "matching": matching,
        "cut": cut,
        "work": {
            "matching_runs": 1,
            "barrier_matching_runs": barrier_runs,
            # The public barrier extractor exposes only its run count; this
            # counter deliberately reports scans from the initial run only.
            "initial_edge_scans": scans,
            "blossom_contractions": contractions,
            "matching_work_bound": len(source.formula) ** 3 * (1 + barrier_runs),
        },
    }

REGIONAL_KERNEL_NAME = "exact.alias-obstruction"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.alias-obstruction-regional-state.v3"
_REGIONAL_STATE_KEYS = frozenset(
    {
        "schema",
        "source",
        "source_sha256",
        "bits",
        "facts",
        "phase",
        "continuation",
        "progress",
        "journal",
        "outcome",
        "evidence",
        "work",
    }
)
_REGIONAL_WORK_KEYS = frozenset(
    {
        "matching_runs",
        "barrier_matching_runs",
        "initial_edge_scans",
        "blossom_contractions",
        "matching_work_bound",
        "primitive_steps",
    }
)


def _regional_canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise AliasObstructionError("regional value is not canonical JSON") from exc


def _regional_digest(value: Any) -> str:
    return hashlib.sha256(_regional_canonical(value)).hexdigest()


def _regional_source_payload(source: RecognizedAliasFormula) -> dict[str, Any]:
    return {
        "formula": [list(clause) for clause in source.formula],
        "degrees": list(source.degrees),
        "cubic_variables": list(source.cubic_variables),
        "incidence": [list(rows) for rows in source.incidence],
    }


def _regional_source_from_payload(value: Mapping[str, Any]) -> RecognizedAliasFormula:
    if set(value) != {"formula", "degrees", "cubic_variables", "incidence"}:
        raise AliasObstructionError("regional source keys are invalid")
    try:
        formula_rows: list[tuple[int, int, int]] = []
        for clause in value["formula"]:
            if len(clause) != 3 or any(not _is_int(item) for item in clause):
                raise AliasObstructionError("regional source clause is malformed")
            formula_rows.append((clause[0], clause[1], clause[2]))
        degrees = tuple(value["degrees"])
        cubic_variables = tuple(value["cubic_variables"])
        incidence = tuple(tuple(rows) for rows in value["incidence"])
        if (
            any(not _is_int(item) for item in degrees)
            or any(not _is_int(item) for item in cubic_variables)
            or any(
                not _is_int(item)
                for rows in incidence
                for item in rows
            )
        ):
            raise AliasObstructionError("regional source metadata is malformed")
        source = RecognizedAliasFormula(
            tuple(formula_rows),
            degrees,
            cubic_variables,
            incidence,
        )
    except (IndexError, TypeError, ValueError) as exc:
        raise AliasObstructionError("regional source is malformed") from exc
    return _validate_recognized(source)


def _regional_facts(
    source: RecognizedAliasFormula,
    bits: tuple[int, ...],
) -> dict[str, Any]:
    context = _context(source, bits)
    sources = [
        [left, right, sorted(variables)]
        for (left, right), variables in sorted(context["sources_for_pair"].items())
    ]
    components = _components(context["residual"], context["graph"], set())
    return {
        "counts": list(context["counts"]),
        "conflict_clause": context["conflict"],
        "residual_clauses": list(context["residual"]),
        "graph": [list(row) for row in context["graph"]],
        "sources_for_pair": sources,
        "components": [list(component) for component in components],
        "odd_components": sum(len(component) % 2 for component in components),
    }


def _regional_context_from_facts(
    source: RecognizedAliasFormula,
    bits: tuple[int, ...],
    facts: Mapping[str, Any],
) -> dict[str, Any]:
    residual = tuple(int(value) for value in facts["residual_clauses"])
    sources = {
        (int(row[0]), int(row[1])): [int(value) for value in row[2]]
        for row in facts["sources_for_pair"]
    }
    cubic_value = dict(zip(source.cubic_variables, bits))
    return {
        "bits": bits,
        "cubic_value": cubic_value,
        "counts": tuple(int(value) for value in facts["counts"]),
        "conflict": facts["conflict_clause"],
        "residual": residual,
        "residual_set": set(residual),
        "sources_for_pair": sources,
        "graph": tuple(tuple(int(value) for value in row) for row in facts["graph"]),
    }


def _regional_matcher(graph: Sequence[Sequence[int]], removed: int = -1) -> dict[str, Any]:
    count = len(graph)
    return {
        "graph": [list(row) for row in graph],
        "removed": removed,
        "matching": [-1] * count,
        "root": 0,
        "active_root": None,
        "queue": [],
        "current": None,
        "neighbor": 0,
        "parent": [-1] * count,
        "base": list(range(count)),
        "used": [False] * count,
        "finished": False,
        "success": False,
        "scans": 0,
        "contractions": 0,
    }


def _regional_lca(
    matching: Sequence[int],
    parent: Sequence[int],
    base: Sequence[int],
    left: int,
    right: int,
) -> int:
    used = [False] * len(matching)
    current = left
    while True:
        current = base[current]
        used[current] = True
        if matching[current] == -1:
            break
        current = parent[matching[current]]
    current = right
    while not used[base[current]]:
        current = parent[matching[base[current]]]
    return base[current]


def _regional_mark_path(
    matching: Sequence[int],
    parent: list[int],
    base: Sequence[int],
    blossom: list[bool],
    vertex: int,
    blossom_base: int,
    child: int,
) -> None:
    current = vertex
    descendant = child
    while base[current] != blossom_base:
        mate = matching[current]
        if mate < 0:
            raise AliasObstructionError("regional matcher encountered an invalid blossom path")
        blossom[base[current]] = True
        blossom[base[mate]] = True
        parent[current] = descendant
        descendant = mate
        current = parent[mate]


def _regional_match_step(matcher: dict[str, Any]) -> None:
    if matcher["finished"]:
        return
    graph = matcher["graph"]
    matching = matcher["matching"]
    count = len(graph)
    removed = matcher["removed"]
    current = matcher["current"]
    if current is None:
        if matcher["queue"]:
            matcher["current"] = matcher["queue"].pop(0)
            matcher["neighbor"] = 0
            return
        root = matcher["root"]
        while root < count and (root == removed or matching[root] != -1):
            root += 1
        matcher["root"] = root
        if root >= count:
            matcher["finished"] = True
            matcher["success"] = True
            return
        matcher["active_root"] = root
        matcher["parent"] = [-1] * count
        matcher["base"] = list(range(count))
        matcher["used"] = [False] * count
        matcher["used"][root] = True
        matcher["queue"] = [root]
        matcher["current"] = None
        matcher["neighbor"] = 0
        return

    neighbors = graph[current]
    neighbor_cursor = matcher["neighbor"]
    if neighbor_cursor >= len(neighbors):
        matcher["current"] = None
        matcher["neighbor"] = 0
        matcher["root"] = int(matcher["active_root"]) + 1
        return
    neighbor = neighbors[neighbor_cursor]
    matcher["neighbor"] = neighbor_cursor + 1
    if neighbor == removed:
        return
    matcher["scans"] += 1
    base = matcher["base"]
    parent = matcher["parent"]
    if base[current] == base[neighbor] or matching[current] == neighbor:
        return
    if (
        neighbor == matcher["root"]
        or (
            matching[neighbor] != -1
            and parent[matching[neighbor]] != -1
        )
    ):
        blossom_base = _regional_lca(
            matching,
            parent,
            base,
            current,
            neighbor,
        )
        blossom = [False] * count
        _regional_mark_path(
            matching,
            parent,
            base,
            blossom,
            current,
            blossom_base,
            neighbor,
        )
        _regional_mark_path(
            matching,
            parent,
            base,
            blossom,
            neighbor,
            blossom_base,
            current,
        )
        for index in range(count):
            if not blossom[base[index]]:
                continue
            base[index] = blossom_base
            if index != removed and not matcher["used"][index]:
                matcher["used"][index] = True
                matcher["queue"].append(index)
        matcher["contractions"] += 1
        return
    if parent[neighbor] != -1:
        return
    parent[neighbor] = current
    if matching[neighbor] == -1:
        path = neighbor
        while path != -1:
            previous = parent[path]
            following = matching[previous] if previous != -1 else -1
            matching[path] = previous
            if previous != -1:
                matching[previous] = path
            path = following
        matcher["success"] = True
        matcher["root"] += 1
        matcher["queue"] = []
        matcher["current"] = None
        matcher["neighbor"] = 0
        return
    mate = matching[neighbor]
    matcher["used"][mate] = True
    matcher["queue"].append(mate)


def _regional_matching_edges(
    residual: Sequence[int],
    mates: Sequence[int],
    sources_for_pair: Mapping[tuple[int, int], Sequence[int]],
) -> list[list[int]]:
    result: list[list[int]] = []
    for local, mate in enumerate(mates):
        if mate != -1 and local < mate:
            try:
                variable = min(sources_for_pair[(local, mate)])
            except (KeyError, ValueError) as exc:
                raise AliasObstructionError("regional matching returned a non-source edge") from exc
            result.append([int(residual[local]), int(residual[mate]), int(variable)])
    return result


def _regional_set_progress(raw: dict[str, Any]) -> None:
    continuation = raw["continuation"]
    cursor = 0
    if isinstance(continuation, Mapping):
        if isinstance(continuation.get("matcher"), Mapping):
            cursor = int(continuation["matcher"].get("root", 0))
        elif "cursor" in continuation:
            cursor = int(continuation["cursor"])
        elif "component_cursor" in continuation:
            cursor = int(continuation["component_cursor"])
    raw["progress"] = {
        "steps": int(raw["work"]["primitive_steps"]),
        "phase": raw["phase"],
        "cursor": cursor,
    }


def _regional_finish(
    raw: dict[str, Any],
    outcome: Mapping[str, Any],
    *,
    status: str = "done",
) -> None:
    serialized = json.loads(_regional_canonical(dict(outcome)).decode("utf-8"))
    raw["outcome"] = serialized
    raw["evidence"] = serialized
    raw["phase"] = "fault" if status == "fault" else "terminal"


def _regional_emit_immediate(raw: dict[str, Any]) -> None:
    source = _regional_source_from_payload(raw["source"])
    bits = tuple(int(value) for value in raw["bits"])
    facts = raw["facts"]
    context = _regional_context_from_facts(source, bits, facts)
    kind = raw["continuation"]["immediate"]
    if kind == "conflict":
        outcome = {
            "status": "unsat",
            "assignment": None,
            "matching": [],
            "cut": _make_cut(
                source,
                context,
                barrier=(),
                conflict_clause=context["conflict"],
            ),
            "work": {
                "matching_runs": 0,
                "barrier_matching_runs": 0,
                "initial_edge_scans": 0,
                "blossom_contractions": 0,
                "matching_work_bound": 0,
            },
        }
    elif kind == "odd":
        outcome = {
            "status": "unsat",
            "assignment": None,
            "matching": [],
            "cut": _make_cut(source, context, barrier=(), conflict_clause=None),
            "work": {
                "matching_runs": 0,
                "barrier_matching_runs": 0,
                "initial_edge_scans": 0,
                "blossom_contractions": 0,
                "matching_work_bound": 0,
            },
        }
    else:
        raise AliasObstructionError("regional immediate continuation is invalid")
    _regional_finish(raw, outcome)


def _regional_emit_terminal(raw: dict[str, Any]) -> None:
    source = _regional_source_from_payload(raw["source"])
    bits = tuple(int(value) for value in raw["bits"])
    facts = raw["facts"]
    context = _regional_context_from_facts(source, bits, facts)
    initial_matching = raw["continuation"].get("initial_matching")
    if initial_matching is None:
        matcher = raw["continuation"].get("matcher")
        if not isinstance(matcher, Mapping):
            raise AliasObstructionError("regional terminal matcher is missing")
        initial_matching = matcher["matching"]
    mates = [int(value) for value in initial_matching]
    matching = _regional_matching_edges(
        context["residual"],
        mates,
        context["sources_for_pair"],
    )
    work = raw["work"]
    if 2 * len(matching) == len(context["residual"]):
        assignment = [0] * len(source.degrees)
        for variable, bit in zip(source.cubic_variables, bits):
            assignment[variable - 1] = bit
        for _, _, variable in matching:
            assignment[variable - 1] = 1
        if not _source_satisfies(source.formula, assignment):
            raise AliasObstructionError("regional perfect matching produced an invalid assignment")
        raw["work"]["matching_work_bound"] = len(source.formula) ** 3
        outcome = {
            "status": "sat",
            "assignment": assignment,
            "matching": matching,
            "cut": None,
            "work": {
                "matching_runs": 1,
                "barrier_matching_runs": 0,
                "initial_edge_scans": int(work["initial_edge_scans"]),
                "blossom_contractions": int(work["blossom_contractions"]),
                "matching_work_bound": len(source.formula) ** 3,
            },
        }
        _regional_finish(raw, outcome)
        return
    barrier = raw["continuation"].get("barrier")
    if not isinstance(barrier, list):
        raise AliasObstructionError("regional obstruction barrier is missing")
    cut = derive_obstruction_cut(source, bits, barrier=barrier)
    barrier_runs = int(work["barrier_matching_runs"])
    raw["work"]["matching_work_bound"] = len(source.formula) ** 3 * (1 + barrier_runs)
    outcome = {
        "status": "unsat",
        "assignment": None,
        "matching": matching,
        "cut": cut,
        "work": {
            "matching_runs": 1,
            "barrier_matching_runs": barrier_runs,
            "initial_edge_scans": int(work["initial_edge_scans"]),
            "blossom_contractions": int(work["blossom_contractions"]),
            "matching_work_bound": len(source.formula) ** 3 * (1 + barrier_runs),
        },
    }
    _regional_finish(raw, outcome)


def _regional_induced_graph(
    graph: Sequence[Sequence[int]],
    vertices: Sequence[int],
) -> list[list[int]]:
    local_for = {vertex: index for index, vertex in enumerate(vertices)}
    return [
        sorted(local_for[neighbor] for neighbor in graph[vertex] if neighbor in local_for)
        for vertex in vertices
    ]


def _regional_barrier_init(raw: dict[str, Any]) -> None:
    facts = raw["facts"]
    components = [list(component) for component in facts["components"]]
    graph = [[int(value) for value in row] for row in facts["graph"]]
    residual = [int(value) for value in facts["residual_clauses"]]
    initial_matcher = raw["continuation"]["matcher"]
    initial_matching = list(initial_matcher["matching"])
    if int(facts["odd_components"]) > 0:
        raw["continuation"] = {
            "kind": "barrier",
            "barrier": [],
            "runs": 0,
            "initial_matching": initial_matching,
            "matcher": None,
        }
        raw["phase"] = "barrier-emit"
        return
    if len(components) > 1:
        vertices = [residual.index(clause) for clause in components[0]]
        raw["continuation"] = {
            "kind": "barrier-components",
            "components": components,
            "component_cursor": 0,
            "component_vertices": vertices,
            "runs": 0,
            "initial_matching": initial_matching,
            "matcher": _regional_matcher(_regional_induced_graph(graph, vertices)),
            "matcher_mapping": vertices,
        }
        raw["phase"] = "barrier-components"
        return
    raw["continuation"] = {
        "kind": "barrier-removed",
        "graph": graph,
        "mapping": list(range(len(graph))),
        "maximum_size": int(
            sum(value != -1 for value in initial_matcher["matching"]) // 2
        ),
        "cursor": 0,
        "runs": 0,
        "exposed": [],
        "initial_matching": initial_matching,
        "matcher": None,
    }
    raw["phase"] = "barrier-removed"


def _regional_barrier_components_step(raw: dict[str, Any]) -> None:
    continuation = raw["continuation"]
    matcher = continuation["matcher"]
    _regional_match_step(matcher)
    if not matcher["finished"]:
        return
    continuation["runs"] += 1
    raw["work"]["barrier_matching_runs"] = int(continuation["runs"])
    matching_size = sum(value != -1 for value in matcher["matching"]) // 2
    vertices = continuation["component_vertices"]
    if 2 * matching_size == len(vertices):
        continuation["component_cursor"] += 1
        if continuation["component_cursor"] >= len(continuation["components"]):
            raise AliasObstructionError("all residual components unexpectedly have perfect matchings")
        residual = [int(value) for value in raw["facts"]["residual_clauses"]]
        graph = [[int(value) for value in row] for row in raw["facts"]["graph"]]
        vertices = [residual.index(clause) for clause in continuation["components"][continuation["component_cursor"]]]
        continuation["component_vertices"] = vertices
        continuation["matcher"] = _regional_matcher(_regional_induced_graph(graph, vertices))
        continuation["matcher_mapping"] = vertices
        return
    continuation["kind"] = "barrier-removed"
    continuation["graph"] = _regional_induced_graph(
        [[int(value) for value in row] for row in raw["facts"]["graph"]],
        vertices,
    )
    continuation["mapping"] = list(vertices)
    continuation["maximum_size"] = int(matching_size)
    continuation["cursor"] = 0
    continuation["runs"] = int(continuation["runs"])
    continuation["exposed"] = []
    continuation["initial_matching"] = list(continuation["initial_matching"])
    continuation["matcher"] = None
    raw["phase"] = "barrier-removed"


def _regional_barrier_removed_step(raw: dict[str, Any]) -> None:
    continuation = raw["continuation"]
    graph = continuation["graph"]
    cursor = int(continuation["cursor"])
    if cursor < len(graph):
        if continuation["matcher"] is None:
            continuation["matcher"] = _regional_matcher(graph, removed=cursor)
            return
        matcher = continuation["matcher"]
        _regional_match_step(matcher)
        if not matcher["finished"]:
            return
        matching_size = sum(value != -1 for value in matcher["matching"]) // 2
        if matching_size == int(continuation["maximum_size"]):
            continuation["exposed"].append(cursor)
        continuation["runs"] += 1
        raw["work"]["barrier_matching_runs"] = int(continuation["runs"])
        continuation["cursor"] = cursor + 1
        continuation["matcher"] = None
        return

    exposed = set(int(value) for value in continuation["exposed"])
    barrier_induced = sorted(
        neighbor
        for vertex in exposed
        for neighbor in graph[vertex]
        if neighbor not in exposed
    )
    mapped_local = sorted(set(continuation["mapping"][vertex] for vertex in barrier_induced))
    residual = tuple(int(value) for value in raw["facts"]["residual_clauses"])
    original_graph = tuple(tuple(int(value) for value in row) for row in raw["facts"]["graph"])
    components = _components(residual, original_graph, set(mapped_local))
    if sum(len(component) % 2 for component in components) <= len(mapped_local):
        raise AliasObstructionError("regional Tutte barrier failed its odd-component inequality")
    barrier = sorted(residual[local] for local in mapped_local)
    raw["continuation"]["barrier"] = barrier
    raw["work"]["barrier_matching_runs"] = int(continuation["runs"])
    raw["phase"] = "barrier-emit"


def _regional_step(raw: dict[str, Any]) -> None:
    phase = raw["phase"]
    if phase == "preflight":
        conflict = raw["facts"]["conflict_clause"]
        if conflict is not None:
            raw["continuation"] = {"immediate": "conflict", "cursor": 0}
            raw["phase"] = "preflight-result"
            return
        if len(raw["facts"]["residual_clauses"]) % 2:
            raw["continuation"] = {"immediate": "odd", "cursor": 0}
            raw["phase"] = "preflight-result"
            return
        facts = raw["facts"]
        raw["continuation"] = {
            "kind": "matching",
            "matcher": _regional_matcher(facts["graph"]),
        }
        raw["phase"] = "matching"
        return
    if phase == "preflight-result":
        _regional_emit_immediate(raw)
        return
    if phase == "matching":
        matcher = raw["continuation"]["matcher"]
        _regional_match_step(matcher)
        raw["work"]["initial_edge_scans"] = int(matcher["scans"])
        raw["work"]["blossom_contractions"] = int(matcher["contractions"])
        if matcher["finished"]:
            raw["work"]["matching_runs"] = 1
            raw["work"]["initial_edge_scans"] = int(matcher["scans"])
            raw["work"]["blossom_contractions"] = int(matcher["contractions"])
            if 2 * (sum(value != -1 for value in matcher["matching"]) // 2) == len(raw["facts"]["residual_clauses"]):
                raw["phase"] = "emit"
            else:
                raw["phase"] = "barrier-init"
        return
    if phase == "emit":
        _regional_emit_terminal(raw)
        return
    if phase == "barrier-init":
        _regional_barrier_init(raw)
        return
    if phase == "barrier-components":
        _regional_barrier_components_step(raw)
        return
    if phase == "barrier-removed":
        _regional_barrier_removed_step(raw)
        return
    if phase == "barrier-emit":
        _regional_emit_terminal(raw)
        return
    raise AliasObstructionError("regional obstruction phase is invalid")


def _regional_validate_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, Mapping) or set(state) != _REGIONAL_STATE_KEYS:
        raise AliasObstructionError("regional obstruction state keys are invalid")
    if state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise AliasObstructionError("regional obstruction state schema is invalid")
    raw = json.loads(_regional_canonical(dict(state)).decode("utf-8"))
    source = _regional_source_from_payload(raw["source"])
    if raw["source_sha256"] != _regional_digest(raw["source"]):
        raise AliasObstructionError("regional obstruction source identity is invalid")
    try:
        bits = tuple(raw["bits"])
    except TypeError as exc:
        raise AliasObstructionError("regional obstruction bits are malformed") from exc
    checked_bits = _validate_bits(source, bits)
    if list(checked_bits) != raw["bits"]:
        raise AliasObstructionError("regional obstruction bits are noncanonical")
    expected_facts = _regional_facts(source, checked_bits)
    if raw["facts"] != expected_facts:
        raise AliasObstructionError("regional obstruction facts are inconsistent")
    if raw["phase"] not in {
        "preflight",
        "preflight-result",
        "matching",
        "emit",
        "barrier-init",
        "barrier-components",
        "barrier-removed",
        "barrier-emit",
        "terminal",
        "fault",
    }:
        raise AliasObstructionError("regional obstruction phase is invalid")
    if not isinstance(raw["journal"], list):
        raise AliasObstructionError("regional obstruction journal is invalid")
    if not isinstance(raw["progress"], Mapping):
        raise AliasObstructionError("regional obstruction progress is invalid")
    if not isinstance(raw["work"], Mapping) or set(raw["work"]) != _REGIONAL_WORK_KEYS:
        raise AliasObstructionError("regional obstruction work counters are invalid")
    if any(
        not _is_int(value) or value < 0
        for value in raw["work"].values()
    ):
        raise AliasObstructionError("regional obstruction work counters are invalid")
    if raw["phase"] in {"terminal", "fault"}:
        if not isinstance(raw["outcome"], Mapping) or raw["evidence"] != raw["outcome"]:
            raise AliasObstructionError("regional obstruction terminal evidence is invalid")
    elif raw["outcome"] is not None or raw["evidence"] is not None:
        raise AliasObstructionError("unfinished regional obstruction has terminal evidence")
    return raw


def regional_state(
    recognized: RecognizedAliasFormula | Sequence[Sequence[int]],
    cubic_bits: Sequence[int] | None = None,
    *,
    variable_count: int | None = None,
) -> dict[str, Any]:
    """Encode one alias obstruction derivation as a resumable JSON state."""
    if isinstance(recognized, RecognizedAliasFormula):
        source = _validate_recognized(recognized)
    elif isinstance(recognized, Mapping):
        source = _regional_source_from_payload(recognized)
    else:
        if variable_count is None:
            try:
                variable_count = max(int(variable) for clause in recognized for variable in clause)
            except (TypeError, ValueError) as exc:
                raise AliasObstructionError("regional source needs a variable count") from exc
        try:
            source = _validate_recognized(
                recognize_degree_two_three_exact_one(
                    recognized,
                    variable_count=variable_count,
                )
            )
        except Exception as exc:
            raise AliasObstructionError("regional source is malformed") from exc
    bits_input = (
        cubic_bits
        if cubic_bits is not None
        else (0,) * len(source.cubic_variables)
    )
    bits = _validate_bits(source, bits_input)
    payload = _regional_source_payload(source)
    facts = _regional_facts(source, bits)
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": payload,
        "source_sha256": _regional_digest(payload),
        "bits": list(bits),
        "facts": facts,
        "phase": "preflight",
        "continuation": {"cursor": 0},
        "progress": {"steps": 0, "phase": "preflight", "cursor": 0},
        "journal": [{"event": "initialized", "phase": "preflight", "cursor": 0}],
        "outcome": None,
        "evidence": None,
        "work": {
            "matching_runs": 0,
            "barrier_matching_runs": 0,
            "initial_edge_scans": 0,
            "blossom_contractions": 0,
            "matching_work_bound": 0,
            "primitive_steps": 0,
        },
    }


def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> KernelResult:
    """Advance obstruction derivation by at most ``quantum`` native steps."""
    raw = _regional_validate_state(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise AliasObstructionError("regional obstruction kernel takes no arguments")
    if not _is_int(quantum) or not 1 <= quantum <= REGIONAL_KERNEL_MAX_WORK:
        raise AliasObstructionError("regional obstruction quantum is invalid")
    if raw["phase"] == "terminal":
        return KernelResult(state=raw, status="done", work=0, output=raw["outcome"])
    if raw["phase"] == "fault":
        return KernelResult(state=raw, status="fault", work=0, output=raw["outcome"])

    used = 0
    while used < quantum and raw["phase"] not in {"terminal", "fault"}:
        old_phase = raw["phase"]
        used += 1
        try:
            _regional_step(raw)
        except Exception as exc:
            raw["work"]["primitive_steps"] += 1
            raw["journal"].append(
                {
                    "event": "fault",
                    "step": raw["work"]["primitive_steps"],
                    "phase": old_phase,
                    "reason": str(exc),
                }
            )
            _regional_finish(
                raw,
                {
                    "status": "fault",
                    "family": "alias-obstruction",
                    "reason": "regional-obstruction-fault",
                    "message": str(exc),
                },
                status="fault",
            )
            _regional_set_progress(raw)
            break
        raw["work"]["primitive_steps"] += 1
        raw["journal"].append(
            {
                "event": "step",
                "step": raw["work"]["primitive_steps"],
                "phase": old_phase,
                "next_phase": raw["phase"],
            }
        )
        _regional_set_progress(raw)
    if raw["phase"] == "terminal":
        status = "done"
        output = raw["outcome"]
    elif raw["phase"] == "fault":
        status = "fault"
        output = raw["outcome"]
    else:
        status = "yield"
        output = None
    return KernelResult(state=raw, status=status, work=used, output=output)


__all__ = [
    "AliasObstructionError",
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "derive_obstruction_cut",
    "evaluate_alias_candidate",
    "regional_kernel",
    "regional_state",
]

