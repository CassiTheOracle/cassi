"""Total field-owned decision for connected matched exact-one/parity CNFs.

The CNF is reduced exactly to perfect matching in a signed subdivision graph.
A deterministic Edmonds blossom controller updates a maximum matching stored in
one immutable float64 field.  SAT emits a Boolean assignment; UNSAT emits a
Tutte odd-component barrier that is independently checkable without rerunning
proof search.
"""

from __future__ import annotations

import base64
import hashlib
import itertools
import json
from collections import deque
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

import cassi_field_regions
import numpy as np

SCHEMA = "cassifi.general-matched-exact-one.v1"
STATE_SCHEMA = "cassifi.general-matched-exact-one-state.v1"
_MAGIC = 0x474D584F
_VERSION = 1
_RUNNING = 0
_SAT = 1
_UNSAT = 2
_STATUS_NAMES = {_RUNNING: "running", _SAT: "sat", _UNSAT: "unsat"}
_HEADER = 12
_H_MAGIC = 0
_H_VERSION = 1
_H_STATUS = 2
_H_BLOCKS = 3
_H_ODD_EDGES = 4
_H_CURSOR = 5
_H_AUGMENTATIONS = 6
_MAX_EXACT_FLOAT64_INTEGER = 2**53 - 1
_H_EDGE_SCANS = 7
_H_CONTRACTIONS = 8
_H_MATCHING_SIZE = 9
_H_BARRIER_RUNS = 10
_H_AUX_VERTICES = 11

Clause = tuple[int, ...]
Formula = tuple[Clause, ...]
Graph = tuple[tuple[int, ...], ...]


class GeneralMatchedDecisionError(ValueError):
    pass


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _literal_key(literal: int) -> tuple[int, bool]:
    return abs(literal), literal < 0


def canonical_formula(formula: Sequence[Sequence[int]]) -> Formula:
    rows: set[Clause] = set()
    for raw_clause in formula:
        if any(
            not isinstance(literal, int) or isinstance(literal, bool)
            for literal in raw_clause
        ):
            raise GeneralMatchedDecisionError("clause literals must be integers")
        clause = tuple(sorted(raw_clause, key=_literal_key))
        if not clause or any(literal == 0 for literal in clause):
            raise GeneralMatchedDecisionError("clauses must be nonempty and contain no zero literal")
        if len({abs(literal) for literal in clause}) != len(clause):
            raise GeneralMatchedDecisionError("clauses must not repeat or complement a variable")
        rows.add(clause)
    if len(rows) != len(formula):
        raise GeneralMatchedDecisionError("formula contains duplicate clauses")
    return tuple(sorted(rows, key=lambda clause: (len(clause), clause)))


def parity_clauses(variables: Sequence[int], parity: int) -> Formula:
    if len(variables) != 2 or parity not in (0, 1):
        raise GeneralMatchedDecisionError("binary parity needs two variables and one parity bit")
    left, right = variables
    if parity == 0:
        return ((left, -right), (-left, right))
    return ((left, right), (-left, -right))


@dataclass(frozen=True, slots=True)
class MatchedEdge:
    left_variable: int
    right_variable: int
    parity: int
    left_block: int
    right_block: int


@dataclass(frozen=True, slots=True)
class RecognizedMatchedFormula:
    formula: Formula
    blocks: tuple[tuple[int, int, int], ...]
    edges: tuple[MatchedEdge, ...]


def recognize_connected_matched_exact_one(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int,
) -> RecognizedMatchedFormula:
    source = canonical_formula(formula)
    source_set = set(source)
    positive_blocks = tuple(
        sorted(
            (
                clause
                for clause in source
                if len(clause) == 3 and all(literal > 0 for literal in clause)
            ),
            key=lambda block: block,
        )
    )
    if len(positive_blocks) < 4 or len(positive_blocks) % 2:
        raise GeneralMatchedDecisionError("mixed class needs an even number of at least four blocks")
    flattened = tuple(variable for block in positive_blocks for variable in block)
    if (
        len(flattened) != variable_count
        or len(set(flattened)) != variable_count
        or set(flattened) != set(range(1, variable_count + 1))
    ):
        raise GeneralMatchedDecisionError("exact-one blocks do not partition the variables")
    block_for = {
        variable: block_index
        for block_index, block in enumerate(positive_blocks)
        for variable in block
    }
    exact_one: set[Clause] = set()
    for block in positive_blocks:
        exact_one.add(block)
        for left, right in itertools.combinations(block, 2):
            exact_one.add(tuple(sorted((-left, -right), key=_literal_key)))
    if not exact_one.issubset(source_set):
        raise GeneralMatchedDecisionError("mixed class is missing an exact-one clause")
    remainder = source_set - exact_one
    groups: dict[tuple[int, int], list[Clause]] = {}
    for clause in remainder:
        if len(clause) != 2:
            raise GeneralMatchedDecisionError("mixed class has a non-binary remainder")
        support = tuple(sorted(abs(literal) for literal in clause))
        if (
            len(set(support)) != 2
            or block_for[support[0]] == block_for[support[1]]
        ):
            raise GeneralMatchedDecisionError("matching edge is repeated or internal to one block")
        groups.setdefault((support[0], support[1]), []).append(clause)

    edges: list[MatchedEdge] = []
    incidence = {variable: 0 for variable in range(1, variable_count + 1)}
    adjacency = [set() for _ in positive_blocks]
    for support in sorted(groups):
        clauses = groups[support]
        if len(clauses) != 2:
            raise GeneralMatchedDecisionError("parity support is incomplete")
        masks = {
            sum(
                1 << position
                for position, variable in enumerate(support)
                if next(
                    literal
                    for literal in clause
                    if abs(literal) == variable
                )
                < 0
            )
            for clause in clauses
        }
        if masks == {0, 3}:
            parity = 1
        elif masks == {1, 2}:
            parity = 0
        else:
            raise GeneralMatchedDecisionError("binary clauses do not encode parity")
        left_variable, right_variable = support
        left_block = block_for[left_variable]
        right_block = block_for[right_variable]
        incidence[left_variable] += 1
        incidence[right_variable] += 1
        adjacency[left_block].add(right_block)
        adjacency[right_block].add(left_block)
        edges.append(
            MatchedEdge(
                left_variable,
                right_variable,
                parity,
                left_block,
                right_block,
            )
        )
    if (
        len(edges) * 2 != variable_count
        or any(count != 1 for count in incidence.values())
    ):
        raise GeneralMatchedDecisionError("parity supports are not a perfect variable matching")
    reached = {0}
    frontier = [0]
    while frontier:
        block = frontier.pop()
        for neighbor in adjacency[block] - reached:
            reached.add(neighbor)
            frontier.append(neighbor)
    if len(reached) != len(positive_blocks):
        raise GeneralMatchedDecisionError("matching quotient graph is disconnected")
    return RecognizedMatchedFormula(
        source,
        tuple((block[0], block[1], block[2]) for block in positive_blocks),
        tuple(edges),
    )


def formula_from_structure(
    blocks: Sequence[Sequence[int]],
    edges: Sequence[MatchedEdge],
) -> Formula:
    clauses: list[Clause] = []
    for block in blocks:
        if len(block) != 3:
            raise GeneralMatchedDecisionError("exact-one block must have three variables")
        a, b, c = block
        clauses.extend(((a, b, c), (-a, -b), (-a, -c), (-b, -c)))
    for edge in edges:
        clauses.extend(
            parity_clauses(
                (edge.left_variable, edge.right_variable),
                edge.parity,
            )
        )
    return canonical_formula(clauses)


def matched_formula_from_topology(
    block_count: int,
    quotient_edges: Sequence[Sequence[int]],
    labels: Sequence[int],
) -> Formula:
    if block_count < 4 or block_count % 2:
        raise GeneralMatchedDecisionError("block count must be even and at least four")
    if len(quotient_edges) != 3 * block_count // 2 or len(labels) != len(quotient_edges):
        raise GeneralMatchedDecisionError("a cubic topology needs 3b/2 edge labels")
    if any(label not in (0, 1) for label in labels):
        raise GeneralMatchedDecisionError("edge labels must be bits")
    ports: list[list[int]] = [[] for _ in range(block_count)]
    normalized: list[tuple[int, int]] = []
    for raw_edge in quotient_edges:
        if len(raw_edge) != 2:
            raise GeneralMatchedDecisionError("quotient edge must have two endpoints")
        left, right = raw_edge
        if (
            not isinstance(left, int)
            or isinstance(left, bool)
            or not isinstance(right, int)
            or isinstance(right, bool)
            or not 0 <= left < block_count
            or not 0 <= right < block_count
            or left == right
        ):
            raise GeneralMatchedDecisionError("quotient edge endpoints are invalid")
        ports[left].append(len(normalized))
        ports[right].append(len(normalized))
        normalized.append((left, right))
    if any(len(incident) != 3 for incident in ports):
        raise GeneralMatchedDecisionError("quotient topology must be cubic")
    variable_for: dict[tuple[int, int], int] = {}
    blocks: list[tuple[int, int, int]] = []
    next_variable = 1
    for block, incident in enumerate(ports):
        variables = []
        for edge_index in sorted(incident):
            variable_for[(block, edge_index)] = next_variable
            variables.append(next_variable)
            next_variable += 1
        blocks.append((variables[0], variables[1], variables[2]))
    edges = []
    for edge_index, ((left, right), parity) in enumerate(zip(normalized, labels)):
        left_variable = variable_for[(left, edge_index)]
        right_variable = variable_for[(right, edge_index)]
        if left_variable > right_variable:
            left_variable, right_variable = right_variable, left_variable
            left, right = right, left
        edges.append(MatchedEdge(left_variable, right_variable, parity, left, right))
    return formula_from_structure(blocks, edges)


@dataclass(frozen=True, slots=True)
class GeneralMatchedProfile:
    blocks: int
    odd_edges: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.blocks, int)
            or isinstance(self.blocks, bool)
            or not isinstance(self.odd_edges, int)
            or isinstance(self.odd_edges, bool)
        ):
            raise GeneralMatchedDecisionError("profile values must be integers")
        if self.blocks < 4 or self.blocks % 2:
            raise GeneralMatchedDecisionError("profile blocks must be even and at least four")
        if not 0 <= self.odd_edges <= self.formula_edges:
            raise GeneralMatchedDecisionError("profile odd-edge count is invalid")
        if self.auxiliary_vertices**3 > _MAX_EXACT_FLOAT64_INTEGER:
            raise GeneralMatchedDecisionError(
                "profile exceeds exact float64 identifier/counter range"
            )

    @property
    def formula_edges(self) -> int:
        return 3 * self.blocks // 2

    @property
    def auxiliary_vertices(self) -> int:
        return self.blocks + self.odd_edges

    @property
    def auxiliary_edges(self) -> int:
        return self.formula_edges + self.odd_edges

    @property
    def field_values(self) -> int:
        return 12 + 17 * self.blocks + 5 * self.odd_edges

    @property
    def field_bytes(self) -> int:
        return 8 * self.field_values

    @property
    def shape(self) -> tuple[int, int, int]:
        return 1, self.field_values, 1

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical(asdict(self))).hexdigest()


@dataclass(frozen=True, slots=True)
class GeneralMatchedState:
    _field: np.ndarray
    profile_sha256: str

    def __post_init__(self) -> None:
        field = np.asarray(self._field)
        if field.dtype != np.float64 or field.ndim != 3:
            raise GeneralMatchedDecisionError("general matching field must be rank-three float64")
        if field.flags.writeable:
            field = field.copy()
            field.setflags(write=False)
            object.__setattr__(self, "_field", field)
        if len(self.profile_sha256) != 64:
            raise GeneralMatchedDecisionError("invalid profile digest")

    @property
    def field(self) -> np.ndarray:
        return self._field.copy()

    @property
    def nbytes(self) -> int:
        return int(self._field.nbytes)


@dataclass(frozen=True, slots=True)
class _Layout:
    block_variables: int
    formula_edges: int
    auxiliary_edges: int
    matching: int
    barrier: int
    assignment: int
    total: int


def _layout(profile: GeneralMatchedProfile) -> _Layout:
    block_variables = _HEADER
    formula_edges = block_variables + 3 * profile.blocks
    auxiliary_edges = formula_edges + 3 * profile.formula_edges
    matching = auxiliary_edges + 3 * profile.auxiliary_edges
    barrier = matching + profile.auxiliary_vertices
    assignment = barrier + profile.auxiliary_vertices
    total = assignment + 3 * profile.blocks
    return _Layout(
        block_variables,
        formula_edges,
        auxiliary_edges,
        matching,
        barrier,
        assignment,
        total,
    )


def _lca(
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


def _mark_path(
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
            raise GeneralMatchedDecisionError("invalid blossom path")
        blossom[base[current]] = True
        blossom[base[mate]] = True
        parent[current] = descendant
        descendant = mate
        current = parent[mate]


def _augment_from_root(
    graph: Graph,
    matching: list[int],
    root: int,
    *,
    removed: int = -1,
) -> tuple[bool, int, int]:
    count = len(graph)
    parent = [-1] * count
    base = list(range(count))
    used = [False] * count
    queue: deque[int] = deque([root])
    used[root] = True
    scans = 0
    contractions = 0
    while queue:
        vertex = queue.popleft()
        for neighbor in graph[vertex]:
            if neighbor == removed:
                continue
            scans += 1
            if base[vertex] == base[neighbor] or matching[vertex] == neighbor:
                continue
            if (
                neighbor == root
                or (
                    matching[neighbor] != -1
                    and parent[matching[neighbor]] != -1
                )
            ):
                blossom_base = _lca(matching, parent, base, vertex, neighbor)
                blossom = [False] * count
                _mark_path(
                    matching,
                    parent,
                    base,
                    blossom,
                    vertex,
                    blossom_base,
                    neighbor,
                )
                _mark_path(
                    matching,
                    parent,
                    base,
                    blossom,
                    neighbor,
                    blossom_base,
                    vertex,
                )
                for index in range(count):
                    if not blossom[base[index]]:
                        continue
                    base[index] = blossom_base
                    if index != removed and not used[index]:
                        used[index] = True
                        queue.append(index)
                contractions += 1
            elif parent[neighbor] == -1:
                parent[neighbor] = vertex
                if matching[neighbor] == -1:
                    current = neighbor
                    while current != -1:
                        previous = parent[current]
                        following = matching[previous] if previous != -1 else -1
                        matching[current] = previous
                        if previous != -1:
                            matching[previous] = current
                        current = following
                    return True, scans, contractions
                mate = matching[neighbor]
                used[mate] = True
                queue.append(mate)
    return False, scans, contractions


def deterministic_maximum_matching(
    graph: Graph,
    *,
    removed: int = -1,
) -> tuple[list[int], int, int]:
    matching = [-1] * len(graph)
    scans = 0
    contractions = 0
    for root in range(len(graph)):
        if root == removed or matching[root] != -1:
            continue
        _, root_scans, root_contractions = _augment_from_root(
            graph,
            matching,
            root,
            removed=removed,
        )
        scans += root_scans
        contractions += root_contractions
    return matching, scans, contractions


def graph_component_sizes(graph: Graph, removed: set[int]) -> list[int]:
    unseen = set(range(len(graph))) - removed
    sizes: list[int] = []
    while unseen:
        start = min(unseen)
        unseen.remove(start)
        stack = [start]
        size = 0
        while stack:
            vertex = stack.pop()
            size += 1
            for neighbor in graph[vertex]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
        sizes.append(size)
    return sizes


def deterministic_tutte_barrier(
    graph: Graph,
    maximum_size: int,
) -> tuple[set[int], int]:
    count = len(graph)
    if count % 2:
        barrier: set[int] = set()
        odd_components = sum(size % 2 for size in graph_component_sizes(graph, barrier))
        if odd_components <= len(barrier):
            raise GeneralMatchedDecisionError("failed to construct odd-order Tutte barrier")
        return barrier, 0
    exposed_in_some_maximum: set[int] = set()
    for vertex in range(count):
        reduced, _, _ = deterministic_maximum_matching(graph, removed=vertex)
        reduced_size = sum(mate != -1 for mate in reduced) // 2
        if reduced_size == maximum_size:
            exposed_in_some_maximum.add(vertex)
    barrier = {
        neighbor
        for vertex in exposed_in_some_maximum
        for neighbor in graph[vertex]
        if neighbor not in exposed_in_some_maximum
    }
    sizes = graph_component_sizes(graph, barrier)
    odd_components = sum(size % 2 for size in sizes)
    if odd_components <= len(barrier):
        raise GeneralMatchedDecisionError("failed to construct a Tutte barrier")
    return barrier, count


class GeneralMatchedDecisionField:
    """Deterministic Edmonds matching state held in one immutable tensor."""

    def __init__(self, profile: GeneralMatchedProfile) -> None:
        self.profile = profile
        self.layout = _layout(profile)
        if self.layout.total != profile.field_values:
            raise GeneralMatchedDecisionError("internal general-matching layout mismatch")

    def _flat(self, state: GeneralMatchedState) -> np.ndarray:
        return state._field.reshape(-1)

    def _state(self, values: np.ndarray) -> GeneralMatchedState:
        field = np.asarray(values, dtype=np.float64).reshape(self.profile.shape).copy()
        field.setflags(write=False)
        state = GeneralMatchedState(field, self.profile.fingerprint)
        self.validate(state)
        return state

    def _blocks(self, values: np.ndarray) -> tuple[tuple[int, int, int], ...]:
        raw = values[self.layout.block_variables : self.layout.formula_edges]
        return tuple(
            (int(raw[3 * index]), int(raw[3 * index + 1]), int(raw[3 * index + 2]))
            for index in range(self.profile.blocks)
        )

    def _edges(self, values: np.ndarray) -> tuple[MatchedEdge, ...]:
        raw = values[self.layout.formula_edges : self.layout.auxiliary_edges]
        block_for = {
            variable: block
            for block, variables in enumerate(self._blocks(values))
            for variable in variables
        }
        return tuple(
            MatchedEdge(
                int(raw[3 * index]),
                int(raw[3 * index + 1]),
                int(raw[3 * index + 2]),
                block_for[int(raw[3 * index])],
                block_for[int(raw[3 * index + 1])],
            )
            for index in range(self.profile.formula_edges)
        )

    def _auxiliary_edges(self, values: np.ndarray) -> tuple[tuple[int, int, int], ...]:
        raw = values[self.layout.auxiliary_edges : self.layout.matching]
        return tuple(
            (int(raw[3 * index]), int(raw[3 * index + 1]), int(raw[3 * index + 2]))
            for index in range(self.profile.auxiliary_edges)
        )

    def _graph(self, values: np.ndarray) -> Graph:
        adjacency = [set() for _ in range(self.profile.auxiliary_vertices)]
        for left, right, _ in self._auxiliary_edges(values):
            adjacency[left].add(right)
            adjacency[right].add(left)
        return tuple(tuple(sorted(neighbors)) for neighbors in adjacency)

    def validate(self, state: GeneralMatchedState) -> None:
        if state.profile_sha256 != self.profile.fingerprint:
            raise GeneralMatchedDecisionError("state/profile digest mismatch")
        if state._field.shape != self.profile.shape:
            raise GeneralMatchedDecisionError("general matching field shape mismatch")
        if not np.all(np.isfinite(state._field)):
            raise GeneralMatchedDecisionError("general matching field contains non-finite values")
        values = self._flat(state)
        if np.any(values != np.rint(values)):
            raise GeneralMatchedDecisionError("general matching field contains non-integer values")
        header = [int(value) for value in values[:_HEADER]]
        if header[_H_MAGIC] != _MAGIC or header[_H_VERSION] != _VERSION:
            raise GeneralMatchedDecisionError("general matching field magic/version mismatch")
        if (
            header[_H_STATUS] not in _STATUS_NAMES
            or header[_H_BLOCKS] != self.profile.blocks
            or header[_H_ODD_EDGES] != self.profile.odd_edges
            or header[_H_AUX_VERTICES] != self.profile.auxiliary_vertices
        ):
            raise GeneralMatchedDecisionError("general matching header mismatch")
        cursor = header[_H_CURSOR]
        if not 0 <= cursor <= self.profile.auxiliary_vertices:
            raise GeneralMatchedDecisionError("general matching cursor is invalid")
        if header[_H_AUGMENTATIONS] < 0 or header[_H_EDGE_SCANS] < 0 or header[_H_CONTRACTIONS] < 0:
            raise GeneralMatchedDecisionError("general matching counters are invalid")
        block_values = values[self.layout.block_variables : self.layout.formula_edges]
        if (
            len(set(int(value) for value in block_values)) != 3 * self.profile.blocks
            or set(int(value) for value in block_values)
            != set(range(1, 3 * self.profile.blocks + 1))
        ):
            raise GeneralMatchedDecisionError("general matching block variables are invalid")
        edges = self._edges(values)
        if (
            any(edge.parity not in (0, 1) for edge in edges)
            or sum(edge.parity for edge in edges) != self.profile.odd_edges
        ):
            raise GeneralMatchedDecisionError("general matching formula edges are invalid")
        auxiliary = self._auxiliary_edges(values)
        if any(
            not 0 <= left < self.profile.auxiliary_vertices
            or not 0 <= right < self.profile.auxiliary_vertices
            or left == right
            or not 0 <= source < self.profile.formula_edges
            for left, right, source in auxiliary
        ):
            raise GeneralMatchedDecisionError("general auxiliary edge is invalid")
        graph = self._graph(values)
        matching = [int(value) for value in values[self.layout.matching : self.layout.barrier]]
        for vertex, mate in enumerate(matching):
            if mate != -1 and (
                not 0 <= mate < len(matching)
                or mate == vertex
                or matching[mate] != vertex
                or mate not in graph[vertex]
            ):
                raise GeneralMatchedDecisionError("general matching relation is invalid")
        matching_size = sum(mate != -1 for mate in matching) // 2
        if matching_size != header[_H_MATCHING_SIZE] or matching_size != header[_H_AUGMENTATIONS]:
            raise GeneralMatchedDecisionError("general matching size counter is invalid")
        barrier = values[self.layout.barrier : self.layout.assignment]
        assignment = values[self.layout.assignment : self.layout.total]
        status = header[_H_STATUS]
        if status == _RUNNING:
            if cursor == self.profile.auxiliary_vertices:
                raise GeneralMatchedDecisionError("completed matching remains running")
            if np.any(barrier != -1) or np.any(assignment != -1):
                raise GeneralMatchedDecisionError("running matching has terminal certificate data")
        else:
            if cursor != self.profile.auxiliary_vertices:
                raise GeneralMatchedDecisionError("matching terminated before all roots")
        if status == _SAT:
            if 2 * matching_size != self.profile.auxiliary_vertices:
                raise GeneralMatchedDecisionError("SAT state lacks a perfect matching")
            if np.any(barrier != -1) or np.any((assignment != 0) & (assignment != 1)):
                raise GeneralMatchedDecisionError("SAT terminal data is invalid")
        elif status == _UNSAT:
            if 2 * matching_size == self.profile.auxiliary_vertices:
                raise GeneralMatchedDecisionError("UNSAT state contains a perfect matching")
            if np.any((barrier != 0) & (barrier != 1)) or np.any(assignment != -1):
                raise GeneralMatchedDecisionError("UNSAT terminal data is invalid")

    @classmethod
    def initialize(
        cls,
        formula: Sequence[Sequence[int]],
        *,
        variable_count: int,
    ) -> tuple["GeneralMatchedDecisionField", GeneralMatchedState]:
        recognized = recognize_connected_matched_exact_one(
            formula,
            variable_count=variable_count,
        )
        odd_edges = sum(edge.parity for edge in recognized.edges)
        profile = GeneralMatchedProfile(len(recognized.blocks), odd_edges)
        field = cls(profile)
        values = np.zeros(profile.field_values, dtype=np.float64)
        values[_H_MAGIC] = _MAGIC
        values[_H_VERSION] = _VERSION
        values[_H_STATUS] = _RUNNING
        values[_H_BLOCKS] = profile.blocks
        values[_H_ODD_EDGES] = profile.odd_edges
        values[_H_AUX_VERTICES] = profile.auxiliary_vertices
        values[field.layout.block_variables : field.layout.formula_edges] = [
            variable
            for block in recognized.blocks
            for variable in block
        ]
        values[field.layout.formula_edges : field.layout.auxiliary_edges] = [
            value
            for edge in recognized.edges
            for value in (edge.left_variable, edge.right_variable, edge.parity)
        ]
        auxiliary: list[tuple[int, int, int]] = []
        odd_index = 0
        for source, edge in enumerate(recognized.edges):
            if edge.parity == 0:
                auxiliary.append((edge.left_block, edge.right_block, source))
            else:
                node = profile.blocks + odd_index
                odd_index += 1
                auxiliary.append((edge.left_block, node, source))
                auxiliary.append((edge.right_block, node, source))
        auxiliary.sort(key=lambda item: (min(item[0], item[1]), max(item[0], item[1]), item[2]))
        values[field.layout.auxiliary_edges : field.layout.matching] = [
            value for edge in auxiliary for value in edge
        ]
        values[field.layout.matching : field.layout.total] = -1
        return field, field._state(values)

    def state_sha256(self, state: GeneralMatchedState) -> str:
        self.validate(state)
        return hashlib.sha256(state._field.tobytes()).hexdigest()

    def _write_assignment(self, values: np.ndarray) -> None:
        matching = [int(value) for value in values[self.layout.matching : self.layout.barrier]]
        auxiliary = self._auxiliary_edges(values)
        edges = self._edges(values)
        sources_for_pair: dict[tuple[int, int], list[int]] = {}
        odd_source_for_node: dict[int, int] = {}
        for left, right, source in auxiliary:
            pair = (min(left, right), max(left, right))
            sources_for_pair.setdefault(pair, []).append(source)
            if left >= self.profile.blocks:
                odd_source_for_node[left] = source
            if right >= self.profile.blocks:
                odd_source_for_node[right] = source
        assignment = [0] * (3 * self.profile.blocks)
        for vertex, mate in enumerate(matching):
            if vertex > mate:
                continue
            if vertex < self.profile.blocks and mate < self.profile.blocks:
                source = min(sources_for_pair[(vertex, mate)])
                edge = edges[source]
                assignment[edge.left_variable - 1] = 1
                assignment[edge.right_variable - 1] = 1
            else:
                node = vertex if vertex >= self.profile.blocks else mate
                block = mate if vertex >= self.profile.blocks else vertex
                source = odd_source_for_node[node]
                edge = edges[source]
                chosen = edge.left_variable if edge.left_block == block else edge.right_variable
                assignment[chosen - 1] = 1
        formula = formula_from_structure(self._blocks(values), edges)
        if not all(
            any(
                assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
                for literal in clause
            )
            for clause in formula
        ):
            raise GeneralMatchedDecisionError("perfect matching did not reconstruct a SAT assignment")
        values[self.layout.assignment : self.layout.total] = assignment

    def _finish(self, values: np.ndarray, graph: Graph) -> None:
        matching_size = int(values[_H_MATCHING_SIZE])
        if 2 * matching_size == self.profile.auxiliary_vertices:
            values[_H_STATUS] = _SAT
            self._write_assignment(values)
            return
        recomputed, _, _ = deterministic_maximum_matching(graph)
        recomputed_size = sum(mate != -1 for mate in recomputed) // 2
        if recomputed_size != matching_size:
            raise GeneralMatchedDecisionError("incremental blossom result is not maximum")
        barrier, runs = deterministic_tutte_barrier(graph, matching_size)
        values[self.layout.barrier : self.layout.assignment] = 0
        for vertex in barrier:
            values[self.layout.barrier + vertex] = 1
        values[_H_BARRIER_RUNS] = runs
        values[_H_STATUS] = _UNSAT

    def _advance_root(self, values: np.ndarray, graph: Graph) -> int:
        root = int(values[_H_CURSOR])
        matching = [int(value) for value in values[self.layout.matching : self.layout.barrier]]
        augmented = False
        scans = 0
        contractions = 0
        if matching[root] == -1:
            augmented, scans, contractions = _augment_from_root(graph, matching, root)
        values[self.layout.matching : self.layout.barrier] = matching
        if augmented:
            values[_H_AUGMENTATIONS] += 1
        values[_H_EDGE_SCANS] += scans
        values[_H_CONTRACTIONS] += contractions
        values[_H_MATCHING_SIZE] = sum(mate != -1 for mate in matching) // 2
        values[_H_CURSOR] = root + 1
        if root + 1 == self.profile.auxiliary_vertices:
            self._finish(values, graph)
        return root

    def step(
        self,
        state: GeneralMatchedState,
    ) -> tuple[GeneralMatchedState, Mapping[str, Any]]:
        self.validate(state)
        before_sha256 = self.state_sha256(state)
        source = self._flat(state)
        status = int(source[_H_STATUS])
        if status != _RUNNING:
            return state, {
                "schema": "cassifi.general-matched-transition.v1",
                "action": "done",
                "status": _STATUS_NAMES[status],
                "previous_state_sha256": before_sha256,
                "state_sha256": before_sha256,
                "state_unchanged": True,
            }
        values = source.copy()
        root = self._advance_root(values, self._graph(values))
        successor = self._state(values)
        return successor, {
            "schema": "cassifi.general-matched-transition.v1",
            "action": "search-root",
            "root": root,
            "status": _STATUS_NAMES[int(values[_H_STATUS])],
            "previous_state_sha256": before_sha256,
            "state_sha256": self.state_sha256(successor),
            "state_unchanged": False,
        }

    def solve(
        self,
        state: GeneralMatchedState,
    ) -> tuple[GeneralMatchedState, Mapping[str, Any]]:
        self.validate(state)
        if int(self._flat(state)[_H_STATUS]) != _RUNNING:
            return state, self.certificate(state)
        values = self._flat(state).copy()
        graph = self._graph(values)
        while int(values[_H_STATUS]) == _RUNNING:
            self._advance_root(values, graph)
        final = self._state(values)
        return final, self.certificate(final)

    def inspect(self, state: GeneralMatchedState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        return {
            "status": _STATUS_NAMES[int(values[_H_STATUS])],
            "blocks": self.profile.blocks,
            "odd_edges": self.profile.odd_edges,
            "auxiliary_vertices": self.profile.auxiliary_vertices,
            "root_cursor": int(values[_H_CURSOR]),
            "augmentations": int(values[_H_AUGMENTATIONS]),
            "edge_scans": int(values[_H_EDGE_SCANS]),
            "blossom_contractions": int(values[_H_CONTRACTIONS]),
            "matching_size": int(values[_H_MATCHING_SIZE]),
            "barrier_matching_runs": int(values[_H_BARRIER_RUNS]),
            "field_bytes": state.nbytes,
            "state_sha256": self.state_sha256(state),
        }

    def certificate(self, state: GeneralMatchedState) -> dict[str, Any]:
        self.validate(state)
        values = self._flat(state)
        status = _STATUS_NAMES[int(values[_H_STATUS])]
        if status == "running":
            raise GeneralMatchedDecisionError("running state has no decision certificate")
        blocks = self._blocks(values)
        edges = self._edges(values)
        auxiliary = self._auxiliary_edges(values)
        graph = self._graph(values)
        matching_values = [int(value) for value in values[self.layout.matching : self.layout.barrier]]
        matching = [
            [vertex, mate]
            for vertex, mate in enumerate(matching_values)
            if mate != -1 and vertex < mate
        ]
        barrier = [
            vertex
            for vertex, selected in enumerate(
                values[self.layout.barrier : self.layout.assignment]
            )
            if selected == 1
        ]
        component_sizes = (
            graph_component_sizes(graph, set(barrier))
            if status == "unsat"
            else []
        )
        assignment = (
            [int(value) for value in values[self.layout.assignment : self.layout.total]]
            if status == "sat"
            else None
        )
        formula = formula_from_structure(blocks, edges)
        certificate: dict[str, Any] = {
            "schema": SCHEMA,
            "status": status,
            "blocks": self.profile.blocks,
            "variables": 3 * self.profile.blocks,
            "formula_edges": [
                {
                    "variables": [edge.left_variable, edge.right_variable],
                    "parity": edge.parity,
                    "blocks": [edge.left_block, edge.right_block],
                }
                for edge in edges
            ],
            "exact_one_blocks": [list(block) for block in blocks],
            "auxiliary_vertices": self.profile.auxiliary_vertices,
            "auxiliary_edges": [list(edge) for edge in auxiliary],
            "matching": matching,
            "matching_size": int(values[_H_MATCHING_SIZE]),
            "assignment": assignment,
            "tutte_barrier": barrier if status == "unsat" else None,
            "component_sizes": component_sizes,
            "odd_components": sum(size % 2 for size in component_sizes),
            "deficiency": (
                sum(size % 2 for size in component_sizes) - len(barrier)
                if status == "unsat"
                else 0
            ),
            "root_searches": int(values[_H_CURSOR]),
            "augmentations": int(values[_H_AUGMENTATIONS]),
            "edge_scans": int(values[_H_EDGE_SCANS]),
            "blossom_contractions": int(values[_H_CONTRACTIONS]),
            "barrier_matching_runs": int(values[_H_BARRIER_RUNS]),
            "field_values": self.profile.field_values,
            "field_bytes": state.nbytes,
            "problem_sha256": hashlib.sha256(_canonical(formula)).hexdigest(),
            "state_sha256": self.state_sha256(state),
            "profile_sha256": self.profile.fingerprint,
        }
        certificate["certificate_sha256"] = hashlib.sha256(_canonical(certificate)).hexdigest()
        return certificate

    def descriptor(self, state: GeneralMatchedState) -> dict[str, Any]:
        self.validate(state)
        return {
            "schema": STATE_SCHEMA,
            "profile": asdict(self.profile),
            "profile_sha256": self.profile.fingerprint,
            "state_sha256": self.state_sha256(state),
            "field_b64": base64.b64encode(state._field.tobytes()).decode("ascii"),
        }

    @classmethod
    def from_descriptor(
        cls,
        value: Mapping[str, Any],
    ) -> tuple["GeneralMatchedDecisionField", GeneralMatchedState]:
        if value.get("schema") != STATE_SCHEMA:
            raise GeneralMatchedDecisionError("unsupported general matching descriptor")
        profile_value = value.get("profile")
        if not isinstance(profile_value, Mapping) or set(profile_value) != {"blocks", "odd_edges"}:
            raise GeneralMatchedDecisionError("invalid general matching profile")
        blocks = profile_value.get("blocks")
        odd_edges = profile_value.get("odd_edges")
        if (
            not isinstance(blocks, int)
            or isinstance(blocks, bool)
            or not isinstance(odd_edges, int)
            or isinstance(odd_edges, bool)
        ):
            raise GeneralMatchedDecisionError("invalid general matching profile values")
        field = cls(GeneralMatchedProfile(blocks, odd_edges))
        if value.get("profile_sha256") != field.profile.fingerprint:
            raise GeneralMatchedDecisionError("general matching profile digest mismatch")
        encoded = value.get("field_b64")
        if not isinstance(encoded, str):
            raise GeneralMatchedDecisionError("general matching field encoding is invalid")
        try:
            raw = base64.b64decode(encoded, validate=True)
            tensor = np.frombuffer(raw, dtype=np.float64).reshape(field.profile.shape).copy()
        except (ValueError, TypeError) as exc:
            raise GeneralMatchedDecisionError("general matching field encoding is invalid") from exc
        digest = value.get("state_sha256")
        if not isinstance(digest, str) or hashlib.sha256(raw).hexdigest() != digest:
            raise GeneralMatchedDecisionError("general matching state digest mismatch")
        return field, field._state(tensor)

REGIONAL_KERNEL_NAME = "exact.matched"
REGIONAL_KERNEL_MAX_WORK = 4_096
REGIONAL_STATE_SCHEMA = "cassifi.regional-exact-matched-state.v1"

_REGIONAL_STATE_KEYS = frozenset(
    {
        "schema",
        "source",
        "profile",
        "phase",
        "continuation",
        "journal",
        "ledger",
        "result",
    }
)
_REGIONAL_LEDGER_KEYS = frozenset(
    {
        "cumulative_work",
        "root_expansions",
        "edge_scans",
        "blossom_contractions",
        "augmentations",
        "matching_size",
        "barrier_matching_runs",
        "assignment_writes",
        "proof_steps",
        "proof_edge_scans",
        "proof_blossom_contractions",
        "proof_augmentations",
    }
)


def _regional_auxiliary_edges(
    recognized: RecognizedMatchedFormula,
) -> tuple[tuple[int, int, int], ...]:
    """Build the deterministic signed-subdivision graph used by the field."""

    blocks = recognized.blocks
    auxiliary_edges: list[tuple[int, int, int]] = []
    odd_index = 0
    for source, edge in enumerate(recognized.edges):
        if edge.parity == 0:
            auxiliary_edges.append((edge.left_block, edge.right_block, source))
        else:
            node = len(blocks) + odd_index
            odd_index += 1
            auxiliary_edges.append((edge.left_block, node, source))
            auxiliary_edges.append((edge.right_block, node, source))
    auxiliary_edges.sort(
        key=lambda item: (min(item[0], item[1]), max(item[0], item[1]), item[2])
    )
    return tuple(auxiliary_edges)


def _regional_graph(
    auxiliary_edges: Sequence[Sequence[int]],
    vertex_count: int,
) -> Graph:
    adjacency = [set() for _ in range(vertex_count)]
    for raw_edge in auxiliary_edges:
        if len(raw_edge) != 3:
            raise GeneralMatchedDecisionError("regional auxiliary edge is invalid")
        left, right, _ = raw_edge
        if (
            isinstance(left, bool)
            or not isinstance(left, int)
            or isinstance(right, bool)
            or not isinstance(right, int)
            or not 0 <= left < vertex_count
            or not 0 <= right < vertex_count
            or left == right
        ):
            raise GeneralMatchedDecisionError("regional auxiliary edge is invalid")
        adjacency[left].add(right)
        adjacency[right].add(left)
    return tuple(tuple(sorted(neighbors)) for neighbors in adjacency)


def _regional_source(
    recognized: RecognizedMatchedFormula,
    variable_count: int,
) -> dict[str, Any]:
    auxiliary_edges = _regional_auxiliary_edges(recognized)
    return {
        "formula": [list(clause) for clause in recognized.formula],
        "variable_count": variable_count,
        "blocks": [list(block) for block in recognized.blocks],
        "edges": [
            {
                "variables": [edge.left_variable, edge.right_variable],
                "parity": edge.parity,
                "blocks": [edge.left_block, edge.right_block],
            }
            for edge in recognized.edges
        ],
        "auxiliary_edges": [list(edge) for edge in auxiliary_edges],
        "auxiliary_vertices": len(recognized.blocks)
        + sum(edge.parity for edge in recognized.edges),
        "problem_sha256": hashlib.sha256(_canonical(recognized.formula)).hexdigest(),
    }


def _regional_ledger() -> dict[str, int]:
    return {key: 0 for key in _REGIONAL_LEDGER_KEYS}


def _regional_continuation(profile: GeneralMatchedProfile) -> dict[str, Any]:
    vertices = profile.auxiliary_vertices
    variables = 3 * profile.blocks
    return {
        "matching": [-1] * vertices,
        "root_cursor": 0,
        "frontier": None,
        "assignment": {
            "plan": None,
            "values": [0] * variables,
            "progress": 0,
        },
        "proof": {
            "candidate_vertex": 0,
            "exposed": [],
            "barrier": [],
            "component_sizes": [],
            "reduction": None,
        },
    }


def regional_state(
    formula: Sequence[Sequence[int]],
    *,
    variable_count: int | None = None,
) -> dict[str, Any]:
    """Encode one connected matched exact-one instance for the regional field."""

    if variable_count is None:
        normalized = canonical_formula(formula)
        variable_count = max(
            (abs(literal) for clause in normalized for literal in clause),
            default=0,
        )
        formula = normalized
    if (
        isinstance(variable_count, bool)
        or not isinstance(variable_count, int)
        or variable_count <= 0
    ):
        raise GeneralMatchedDecisionError("regional variable_count must be a positive integer")
    recognized = recognize_connected_matched_exact_one(
        formula,
        variable_count=variable_count,
    )
    profile = GeneralMatchedProfile(
        len(recognized.blocks),
        sum(edge.parity for edge in recognized.edges),
    )
    return {
        "schema": REGIONAL_STATE_SCHEMA,
        "source": _regional_source(recognized, variable_count),
        "profile": asdict(profile),
        "phase": "matching",
        "continuation": _regional_continuation(profile),
        "journal": [],
        "ledger": _regional_ledger(),
        "result": None,
    }




def _regional_integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GeneralMatchedDecisionError(f"{name} must be an integer >= {minimum}")
    return value


def _regional_load(
    state: Any,
) -> tuple[
    dict[str, Any],
    RecognizedMatchedFormula,
    GeneralMatchedProfile,
    Graph,
]:
    if not isinstance(state, Mapping) or set(state) != _REGIONAL_STATE_KEYS:
        raise GeneralMatchedDecisionError("regional matched state keys are invalid")
    if state.get("schema") != REGIONAL_STATE_SCHEMA:
        raise GeneralMatchedDecisionError("regional matched state schema is invalid")
    try:
        json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise GeneralMatchedDecisionError("regional matched state is not JSON-safe") from exc

    source = state["source"]
    if not isinstance(source, Mapping) or set(source) != {
        "formula",
        "variable_count",
        "blocks",
        "edges",
        "auxiliary_edges",
        "auxiliary_vertices",
        "problem_sha256",
    }:
        raise GeneralMatchedDecisionError("regional matched source is invalid")
    variable_count = _regional_integer(
        source["variable_count"],
        "regional variable_count",
        minimum=1,
    )
    formula = source["formula"]
    if not isinstance(formula, list):
        raise GeneralMatchedDecisionError("regional matched formula is invalid")
    recognized = recognize_connected_matched_exact_one(
        formula,
        variable_count=variable_count,
    )
    expected_source = _regional_source(recognized, variable_count)
    if dict(source) != expected_source:
        raise GeneralMatchedDecisionError("regional matched source is not canonical")
    profile_value = state["profile"]
    if not isinstance(profile_value, Mapping) or set(profile_value) != {
        "blocks",
        "odd_edges",
    }:
        raise GeneralMatchedDecisionError("regional matched profile is invalid")
    try:
        profile = GeneralMatchedProfile(
            _regional_integer(profile_value["blocks"], "regional profile blocks"),
            _regional_integer(profile_value["odd_edges"], "regional profile odd_edges"),
        )
    except (TypeError, ValueError) as exc:
        raise GeneralMatchedDecisionError("regional matched profile is invalid") from exc
    if asdict(profile) != dict(profile_value):
        raise GeneralMatchedDecisionError("regional matched profile is not canonical")
    expected_profile = GeneralMatchedProfile(
        len(recognized.blocks),
        sum(edge.parity for edge in recognized.edges),
    )
    if profile != expected_profile:
        raise GeneralMatchedDecisionError("regional matched profile does not match source")

    phase = state["phase"]
    if phase not in {"matching", "assignment", "proof", "done", "fault"}:
        raise GeneralMatchedDecisionError("regional matched phase is invalid")
    continuation = state["continuation"]
    if not isinstance(continuation, Mapping) or set(continuation) != {
        "matching",
        "root_cursor",
        "frontier",
        "assignment",
        "proof",
    }:
        raise GeneralMatchedDecisionError("regional matched continuation is invalid")
    matching = continuation["matching"]
    vertices = profile.auxiliary_vertices
    if (
        not isinstance(matching, list)
        or len(matching) != vertices
        or any(
            isinstance(mate, bool)
            or not isinstance(mate, int)
            or mate < -1
            or mate >= vertices
            for mate in matching
        )
    ):
        raise GeneralMatchedDecisionError("regional matched matching frontier is invalid")
    graph = _regional_graph(source["auxiliary_edges"], vertices)
    for vertex, mate in enumerate(matching):
        if mate != -1 and (
            mate == vertex
            or matching[mate] != vertex
            or mate not in graph[vertex]
        ):
            raise GeneralMatchedDecisionError("regional matched matching relation is invalid")
    root_cursor = _regional_integer(
        continuation["root_cursor"],
        "regional root cursor",
    )
    if root_cursor > vertices:
        raise GeneralMatchedDecisionError("regional root cursor is invalid")

    frontier = continuation["frontier"]
    if frontier is not None:
        if not isinstance(frontier, Mapping) or set(frontier) != {
            "root",
            "parent",
            "base",
            "used",
            "queue",
            "queue_cursor",
            "neighbor_cursor",
        }:
            raise GeneralMatchedDecisionError("regional matching frontier is invalid")
        root = _regional_integer(frontier["root"], "regional frontier root")
        if root != root_cursor or root >= vertices or matching[root] != -1:
            raise GeneralMatchedDecisionError("regional frontier root is invalid")
        for key in ("parent", "base", "used"):
            values = frontier[key]
            if not isinstance(values, list) or len(values) != vertices:
                raise GeneralMatchedDecisionError("regional frontier vectors are invalid")
        if not isinstance(frontier["queue"], list):
            raise GeneralMatchedDecisionError("regional frontier queue is invalid")
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 0 <= value < vertices
            for value in frontier["queue"]
        ):
            raise GeneralMatchedDecisionError("regional frontier queue is invalid")
        _regional_integer(frontier["queue_cursor"], "regional queue cursor")
        _regional_integer(frontier["neighbor_cursor"], "regional neighbor cursor")
        if frontier["queue_cursor"] > len(frontier["queue"]):
            raise GeneralMatchedDecisionError("regional queue cursor is invalid")
        if frontier["queue_cursor"] < len(frontier["queue"]) and (
            frontier["neighbor_cursor"] > len(
                graph[frontier["queue"][frontier["queue_cursor"]]]
            )
        ):
            raise GeneralMatchedDecisionError("regional neighbor cursor is invalid")

    assignment = continuation["assignment"]
    if not isinstance(assignment, Mapping) or set(assignment) != {
        "plan",
        "values",
        "progress",
    }:
        raise GeneralMatchedDecisionError("regional assignment continuation is invalid")
    assignment_values = assignment["values"]
    variables = 3 * profile.blocks
    if (
        not isinstance(assignment_values, list)
        or len(assignment_values) != variables
        or any(value not in (0, 1) for value in assignment_values)
    ):
        raise GeneralMatchedDecisionError("regional assignment continuation is invalid")
    progress = _regional_integer(assignment["progress"], "regional assignment progress")
    if progress > variables:
        raise GeneralMatchedDecisionError("regional assignment progress is invalid")
    plan = assignment["plan"]
    if plan is not None and (
        not isinstance(plan, list)
        or len(plan) != variables
        or any(value not in (0, 1) for value in plan)
    ):
        raise GeneralMatchedDecisionError("regional assignment plan is invalid")

    proof = continuation["proof"]
    if not isinstance(proof, Mapping) or set(proof) != {
        "candidate_vertex",
        "exposed",
        "barrier",
        "component_sizes",
        "reduction",
    }:
        raise GeneralMatchedDecisionError("regional proof continuation is invalid")
    candidate = _regional_integer(
        proof["candidate_vertex"],
        "regional proof candidate",
    )
    if candidate > vertices:
        raise GeneralMatchedDecisionError("regional proof candidate is invalid")
    for key in ("exposed", "barrier"):
        values = proof[key]
        if (
            not isinstance(values, list)
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value < vertices
                for value in values
            )
            or values != sorted(set(values))
        ):
            raise GeneralMatchedDecisionError("regional proof vertex list is invalid")
    component_sizes = proof["component_sizes"]
    if (
        not isinstance(component_sizes, list)
        or any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value <= 0
            for value in component_sizes
        )
    ):
        raise GeneralMatchedDecisionError("regional proof component sizes are invalid")
    reduction = proof["reduction"]
    if reduction is not None:
        if not isinstance(reduction, Mapping) or set(reduction) != {
            "removed",
            "matching",
            "root_cursor",
            "frontier",
            "edge_scans",
            "blossom_contractions",
            "augmentations",
        }:
            raise GeneralMatchedDecisionError("regional proof reduction is invalid")
        removed = _regional_integer(reduction["removed"], "regional reduction vertex")
        if removed >= vertices:
            raise GeneralMatchedDecisionError("regional reduction vertex is invalid")
        reduced_matching = reduction["matching"]
        if (
            not isinstance(reduced_matching, list)
            or len(reduced_matching) != vertices
            or reduced_matching[removed] != -1
            or any(
                isinstance(mate, bool)
                or not isinstance(mate, int)
                or mate < -1
                or mate >= vertices
                for mate in reduced_matching
            )
        ):
            raise GeneralMatchedDecisionError("regional proof reduction matching is invalid")
        for vertex, mate in enumerate(reduced_matching):
            if mate != -1 and (
                mate == vertex
                or reduced_matching[mate] != vertex
                or mate not in graph[vertex]
            ):
                raise GeneralMatchedDecisionError("regional proof reduction matching is invalid")
        reduction_root = _regional_integer(
            reduction["root_cursor"],
            "regional reduction root cursor",
        )
        if reduction_root > vertices:
            raise GeneralMatchedDecisionError("regional reduction root cursor is invalid")
        if reduction["frontier"] is not None:
            nested = reduction["frontier"]
            if not isinstance(nested, Mapping) or set(nested) != {
                "root",
                "parent",
                "base",
                "used",
                "queue",
                "queue_cursor",
                "neighbor_cursor",
            }:
                raise GeneralMatchedDecisionError("regional reduction frontier is invalid")
            if nested["root"] != reduction_root:
                raise GeneralMatchedDecisionError("regional reduction frontier root is invalid")
        for key in ("edge_scans", "blossom_contractions", "augmentations"):
            _regional_integer(reduction[key], f"regional reduction {key}")

    journal = state["journal"]
    if (
        not isinstance(journal, list)
        or any(not isinstance(event, Mapping) for event in journal)
    ):
        raise GeneralMatchedDecisionError("regional matched journal is invalid")
    ledger_value = state["ledger"]
    if not isinstance(ledger_value, Mapping) or set(ledger_value) != _REGIONAL_LEDGER_KEYS:
        raise GeneralMatchedDecisionError("regional matched ledger is invalid")
    ledger = dict(ledger_value)
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in ledger.values()
    ):
        raise GeneralMatchedDecisionError("regional matched ledger counters are invalid")
    if ledger["matching_size"] != sum(mate != -1 for mate in matching) // 2:
        raise GeneralMatchedDecisionError("regional matched ledger matching size is invalid")
    result = state["result"]
    if phase in {"matching", "assignment", "proof"} and result is not None:
        raise GeneralMatchedDecisionError("regional running state has a result")
    if phase == "done" and not isinstance(result, Mapping):
        raise GeneralMatchedDecisionError("regional terminal state has no result")
    if phase != "done" and phase != "fault" and result is not None:
        raise GeneralMatchedDecisionError("regional nonterminal result is invalid")
    detached = json.loads(
        json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    return detached, recognized, profile, graph


def _regional_assignment_plan(
    recognized: RecognizedMatchedFormula,
    matching: Sequence[int],
) -> list[int]:
    blocks = recognized.blocks
    edges = recognized.edges
    sources_for_pair: dict[tuple[int, int], list[int]] = {}
    odd_source_for_node: dict[int, int] = {}
    for source, edge in enumerate(_regional_auxiliary_edges(recognized)):
        left, right, original = edge
        pair = (min(left, right), max(left, right))
        sources_for_pair.setdefault(pair, []).append(original)
        if left >= len(blocks):
            odd_source_for_node[left] = original
        if right >= len(blocks):
            odd_source_for_node[right] = original
    assignment = [0] * (3 * len(blocks))
    for vertex, mate in enumerate(matching):
        if mate == -1 or vertex > mate:
            continue
        if vertex < len(blocks) and mate < len(blocks):
            source = min(sources_for_pair[(vertex, mate)])
            edge = edges[source]
            assignment[edge.left_variable - 1] = 1
            assignment[edge.right_variable - 1] = 1
        else:
            node = vertex if vertex >= len(blocks) else mate
            block = mate if vertex >= len(blocks) else vertex
            source = odd_source_for_node[node]
            edge = edges[source]
            chosen = edge.left_variable if edge.left_block == block else edge.right_variable
            assignment[chosen - 1] = 1
    formula = formula_from_structure(blocks, edges)
    if not all(
        any(
            assignment[abs(literal) - 1] == (1 if literal > 0 else 0)
            for literal in clause
        )
        for clause in formula
    ):
        raise GeneralMatchedDecisionError(
            "perfect matching did not reconstruct a regional SAT assignment"
        )
    return assignment


def _regional_terminal_certificate(
    recognized: RecognizedMatchedFormula,
    profile: GeneralMatchedProfile,
    continuation: Mapping[str, Any],
    ledger: Mapping[str, int],
    status: str,
) -> dict[str, Any]:
    """Serialize the native decision without consulting the legacy controller."""

    blocks = recognized.blocks
    edges = recognized.edges
    auxiliary = _regional_auxiliary_edges(recognized)
    graph = _regional_graph(auxiliary, profile.auxiliary_vertices)
    matching = [int(value) for value in continuation["matching"]]
    matching_size = sum(mate != -1 for mate in matching) // 2
    barrier = (
        sorted(int(value) for value in continuation["proof"]["barrier"])
        if status == "unsat"
        else []
    )
    component_sizes = (
        graph_component_sizes(graph, set(barrier)) if status == "unsat" else []
    )
    assignment = (
        [int(value) for value in continuation["assignment"]["values"]]
        if status == "sat"
        else None
    )

    values = np.zeros(profile.field_values, dtype=np.float64)
    values[_H_MAGIC] = _MAGIC
    values[_H_VERSION] = _VERSION
    values[_H_STATUS] = _SAT if status == "sat" else _UNSAT
    values[_H_BLOCKS] = profile.blocks
    values[_H_ODD_EDGES] = profile.odd_edges
    values[_H_AUX_VERTICES] = profile.auxiliary_vertices
    layout = _layout(profile)
    values[layout.block_variables : layout.formula_edges] = [
        variable for block in blocks for variable in block
    ]
    values[layout.formula_edges : layout.auxiliary_edges] = [
        value for edge in edges for value in (
            edge.left_variable,
            edge.right_variable,
            edge.parity,
        )
    ]
    values[layout.auxiliary_edges : layout.matching] = [
        value for edge in auxiliary for value in edge
    ]
    values[layout.matching : layout.barrier] = matching
    values[layout.barrier : layout.assignment] = 0
    values[layout.assignment : layout.total] = -1
    values[_H_CURSOR] = profile.auxiliary_vertices
    values[_H_AUGMENTATIONS] = ledger["augmentations"]
    values[_H_EDGE_SCANS] = ledger["edge_scans"]
    values[_H_CONTRACTIONS] = ledger["blossom_contractions"]
    values[_H_MATCHING_SIZE] = matching_size
    values[_H_BARRIER_RUNS] = ledger["barrier_matching_runs"]
    if status == "sat":
        values[layout.assignment : layout.total] = assignment
    else:
        for vertex in barrier:
            values[layout.barrier + vertex] = 1
    state_sha256 = hashlib.sha256(values.tobytes()).hexdigest()
    matching_pairs = [
        [vertex, mate]
        for vertex, mate in enumerate(matching)
        if mate != -1 and vertex < mate
    ]
    formula = formula_from_structure(blocks, edges)
    certificate: dict[str, Any] = {
        "schema": SCHEMA,
        "status": status,
        "blocks": profile.blocks,
        "variables": 3 * profile.blocks,
        "formula_edges": [
            {
                "variables": [edge.left_variable, edge.right_variable],
                "parity": edge.parity,
                "blocks": [edge.left_block, edge.right_block],
            }
            for edge in edges
        ],
        "exact_one_blocks": [list(block) for block in blocks],
        "auxiliary_vertices": profile.auxiliary_vertices,
        "auxiliary_edges": [list(edge) for edge in auxiliary],
        "matching": matching_pairs,
        "matching_size": matching_size,
        "assignment": assignment,
        "tutte_barrier": barrier if status == "unsat" else None,
        "component_sizes": component_sizes,
        "odd_components": sum(size % 2 for size in component_sizes),
        "deficiency": (
            sum(size % 2 for size in component_sizes) - len(barrier)
            if status == "unsat"
            else 0
        ),
        "root_searches": profile.auxiliary_vertices,
        "augmentations": ledger["augmentations"],
        "edge_scans": ledger["edge_scans"],
        "blossom_contractions": ledger["blossom_contractions"],
        "barrier_matching_runs": ledger["barrier_matching_runs"],
        "field_values": profile.field_values,
        "field_bytes": 8 * profile.field_values,
        "problem_sha256": hashlib.sha256(_canonical(formula)).hexdigest(),
        "state_sha256": state_sha256,
        "profile_sha256": profile.fingerprint,
    }
    certificate["certificate_sha256"] = hashlib.sha256(
        _canonical(certificate)
    ).hexdigest()
    return certificate


def _regional_record(state: dict[str, Any], action: str) -> None:
    ledger = state["ledger"]
    state["journal"].append(
        {
            "step": ledger["cumulative_work"],
            "phase": state["phase"],
            "action": action,
            "root_cursor": state["continuation"]["root_cursor"],
            "matching_size": ledger["matching_size"],
        }
    )


def _regional_search_primitive(
    matching: list[int],
    root_cursor: int,
    frontier: dict[str, Any] | None,
    graph: Graph,
    *,
    removed: int = -1,
) -> dict[str, Any]:
    """Consume one edge/frontier operation of deterministic blossom search."""

    vertices = len(graph)
    root = root_cursor
    root_started = 0
    if frontier is None:
        if root >= vertices:
            return {
                "root_cursor": root,
                "frontier": None,
                "complete": True,
                "augmented": False,
                "root_started": 0,
                "edge_scans": 0,
                "contractions": 0,
                "action": "search-complete",
            }
        root_started = 1
        if root == removed or matching[root] != -1:
            return {
                "root_cursor": root + 1,
                "frontier": None,
                "complete": root + 1 >= vertices,
                "augmented": False,
                "root_started": root_started,
                "edge_scans": 0,
                "contractions": 0,
                "action": "search-root",
            }
        frontier = {
            "root": root,
            "parent": [-1] * vertices,
            "base": list(range(vertices)),
            "used": [0] * vertices,
            "queue": [root],
            "queue_cursor": 0,
            "neighbor_cursor": 0,
        }
        frontier["used"][root] = 1

    queue = frontier["queue"]
    queue_cursor = frontier["queue_cursor"]
    if queue_cursor >= len(queue):
        return {
            "root_cursor": root + 1,
            "frontier": None,
            "complete": root + 1 >= vertices,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 0,
            "contractions": 0,
            "action": "search-root",
        }

    vertex = queue[queue_cursor]
    neighbors = graph[vertex]
    neighbor_cursor = frontier["neighbor_cursor"]
    if neighbor_cursor >= len(neighbors):
        frontier["queue_cursor"] = queue_cursor + 1
        frontier["neighbor_cursor"] = 0
        return {
            "root_cursor": root,
            "frontier": frontier,
            "complete": False,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 0,
            "contractions": 0,
            "action": "frontier-pop",
        }
    neighbor = neighbors[neighbor_cursor]
    frontier["neighbor_cursor"] = neighbor_cursor + 1
    if neighbor == removed:
        return {
            "root_cursor": root,
            "frontier": frontier,
            "complete": False,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 0,
            "contractions": 0,
            "action": "edge-skip",
        }

    parent = frontier["parent"]
    base = frontier["base"]
    used = frontier["used"]
    if base[vertex] == base[neighbor] or matching[vertex] == neighbor:
        return {
            "root_cursor": root,
            "frontier": frontier,
            "complete": False,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 1,
            "contractions": 0,
            "action": "edge-scan",
        }
    if neighbor == root or (
        matching[neighbor] != -1 and parent[matching[neighbor]] != -1
    ):
        blossom_base = _lca(matching, parent, base, vertex, neighbor)
        blossom = [False] * vertices
        _mark_path(
            matching,
            parent,
            base,
            blossom,
            vertex,
            blossom_base,
            neighbor,
        )
        _mark_path(
            matching,
            parent,
            base,
            blossom,
            neighbor,
            blossom_base,
            vertex,
        )
        for index in range(vertices):
            if not blossom[base[index]]:
                continue
            base[index] = blossom_base
            if not used[index]:
                used[index] = 1
                queue.append(index)
        return {
            "root_cursor": root,
            "frontier": frontier,
            "complete": False,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 1,
            "contractions": 1,
            "action": "blossom-contract",
        }
    if parent[neighbor] != -1:
        return {
            "root_cursor": root,
            "frontier": frontier,
            "complete": False,
            "augmented": False,
            "root_started": root_started,
            "edge_scans": 1,
            "contractions": 0,
            "action": "edge-scan",
        }
    parent[neighbor] = vertex
    if matching[neighbor] == -1:
        current = neighbor
        while current != -1:
            previous = parent[current]
            following = matching[previous] if previous != -1 else -1
            matching[current] = previous
            if previous != -1:
                matching[previous] = current
            current = following
        return {
            "root_cursor": root + 1,
            "frontier": None,
            "complete": root + 1 >= vertices,
            "augmented": True,
            "root_started": root_started,
            "edge_scans": 1,
            "contractions": 0,
            "action": "augment",
        }
    mate = matching[neighbor]
    used[mate] = 1
    queue.append(mate)
    return {
        "root_cursor": root,
        "frontier": frontier,
        "complete": False,
        "augmented": False,
        "root_started": root_started,
        "edge_scans": 1,
        "contractions": 0,
        "action": "frontier-push",
    }


def _regional_matching_primitive(
    state: dict[str, Any],
    recognized: RecognizedMatchedFormula,
    profile: GeneralMatchedProfile,
    graph: Graph,
) -> str:
    continuation = state["continuation"]
    ledger = state["ledger"]
    search = _regional_search_primitive(
        continuation["matching"],
        continuation["root_cursor"],
        continuation["frontier"],
        graph,
    )
    continuation["root_cursor"] = search["root_cursor"]
    continuation["frontier"] = search["frontier"]
    ledger["root_expansions"] += search["root_started"]
    ledger["edge_scans"] += search["edge_scans"]
    ledger["blossom_contractions"] += search["contractions"]
    if search["augmented"]:
        ledger["augmentations"] += 1
        ledger["matching_size"] = sum(
            mate != -1 for mate in continuation["matching"]
        ) // 2
    if search["complete"]:
        if ledger["matching_size"] * 2 == profile.auxiliary_vertices:
            continuation["assignment"]["plan"] = _regional_assignment_plan(
                recognized,
                continuation["matching"],
            )
            state["phase"] = "assignment"
        else:
            state["phase"] = "proof"
    return search["action"]


def _regional_proof_primitive(
    state: dict[str, Any],
    recognized: RecognizedMatchedFormula,
    profile: GeneralMatchedProfile,
    graph: Graph,
) -> str:
    continuation = state["continuation"]
    proof = continuation["proof"]
    ledger = state["ledger"]
    vertices = profile.auxiliary_vertices
    if vertices % 2:
        proof["barrier"] = []
        proof["component_sizes"] = graph_component_sizes(graph, set())
        state["phase"] = "done"
        state["result"] = _regional_terminal_certificate(
            recognized,
            profile,
            continuation,
            ledger,
            "unsat",
        )
        return "tutte-barrier"

    reduction = proof["reduction"]
    candidate = proof["candidate_vertex"]
    if reduction is None and candidate < vertices:
        reduction = {
            "removed": candidate,
            "matching": [-1] * vertices,
            "root_cursor": 0,
            "frontier": None,
            "edge_scans": 0,
            "blossom_contractions": 0,
            "augmentations": 0,
        }
        proof["reduction"] = reduction
    if reduction is not None:
        search = _regional_search_primitive(
            reduction["matching"],
            reduction["root_cursor"],
            reduction["frontier"],
            graph,
            removed=reduction["removed"],
        )
        reduction["root_cursor"] = search["root_cursor"]
        reduction["frontier"] = search["frontier"]
        reduction["edge_scans"] += search["edge_scans"]
        reduction["blossom_contractions"] += search["contractions"]
        if search["augmented"]:
            reduction["augmentations"] += 1
        ledger["proof_edge_scans"] += search["edge_scans"]
        ledger["proof_blossom_contractions"] += search["contractions"]
        ledger["proof_augmentations"] += int(search["augmented"])
        ledger["proof_steps"] += 1
        if not search["complete"]:
            return search["action"]
        reduced_size = sum(
            mate != -1 for mate in reduction["matching"]
        ) // 2
        if reduced_size == ledger["matching_size"]:
            proof["exposed"].append(candidate)
        proof["candidate_vertex"] = candidate + 1
        proof["reduction"] = None
        ledger["barrier_matching_runs"] += 1
        return "barrier-matching"

    exposed = set(proof["exposed"])
    barrier = {
        neighbor
        for vertex in exposed
        for neighbor in graph[vertex]
        if neighbor not in exposed
    }
    component_sizes = graph_component_sizes(graph, barrier)
    odd_components = sum(size % 2 for size in component_sizes)
    if odd_components <= len(barrier):
        raise GeneralMatchedDecisionError("failed to construct a regional Tutte barrier")
    proof["barrier"] = sorted(barrier)
    proof["component_sizes"] = component_sizes
    state["phase"] = "done"
    state["result"] = _regional_terminal_certificate(
        recognized,
        profile,
        continuation,
        ledger,
        "unsat",
    )
    return "tutte-barrier"






def regional_kernel(
    state: Any,
    arguments: Mapping[str, Any],
    quantum: int,
) -> cassi_field_regions.KernelResult:
    """Advance matching, assignment, or Tutte proof by bounded primitives."""

    loaded, recognized, profile, graph = _regional_load(state)
    if not isinstance(arguments, Mapping) or arguments:
        raise GeneralMatchedDecisionError("regional matched kernel takes no arguments")
    quantum = _regional_integer(
        quantum,
        "regional matched quantum",
        minimum=1,
    )
    if quantum > REGIONAL_KERNEL_MAX_WORK:
        raise GeneralMatchedDecisionError("regional matched quantum exceeds kernel bound")
    if loaded["phase"] == "done":
        return cassi_field_regions.KernelResult(
            state=loaded,
            status="done",
            work=0,
            output=loaded["result"],
        )
    if loaded["phase"] == "fault":
        return cassi_field_regions.KernelResult(
            state=loaded,
            status="fault",
            work=0,
            output=loaded["result"],
        )

    consumed = 0
    while consumed < quantum and loaded["phase"] not in {"done", "fault"}:
        phase = loaded["phase"]
        if phase == "matching":
            action = _regional_matching_primitive(
                loaded,
                recognized,
                profile,
                graph,
            )
        elif phase == "assignment":
            assignment = loaded["continuation"]["assignment"]
            progress = assignment["progress"]
            plan = assignment["plan"]
            if not isinstance(plan, list) or progress >= len(plan):
                loaded["phase"] = "done"
                loaded["result"] = _regional_terminal_certificate(
                    recognized,
                    profile,
                    loaded["continuation"],
                    loaded["ledger"],
                    "sat",
                )
                action = "assignment-complete"
            else:
                assignment["values"][progress] = plan[progress]
                assignment["progress"] = progress + 1
                loaded["ledger"]["assignment_writes"] += 1
                action = "assignment-write"
                if assignment["progress"] == len(plan):
                    loaded["phase"] = "done"
                    loaded["result"] = _regional_terminal_certificate(
                        recognized,
                        profile,
                        loaded["continuation"],
                        loaded["ledger"],
                        "sat",
                    )
        elif phase == "proof":
            action = _regional_proof_primitive(
                loaded,
                recognized,
                profile,
                graph,
            )
        else:
            raise GeneralMatchedDecisionError("regional matched phase cannot advance")
        consumed += 1
        loaded["ledger"]["cumulative_work"] += 1
        _regional_record(loaded, action)

    status = "yield"
    output = None
    if loaded["phase"] == "done":
        status = "done"
        output = loaded["result"]
    elif loaded["phase"] == "fault":
        status = "fault"
        output = loaded["result"]
    return cassi_field_regions.KernelResult(
        state=loaded,
        status=status,
        work=consumed,
        output=output,
    )



__all__ = [
    "REGIONAL_KERNEL_MAX_WORK",
    "REGIONAL_KERNEL_NAME",
    "REGIONAL_STATE_SCHEMA",
    "SCHEMA",
    "STATE_SCHEMA",
    "GeneralMatchedDecisionError",
    "GeneralMatchedDecisionField",
    "GeneralMatchedProfile",
    "GeneralMatchedState",
    "MatchedEdge",
    "RecognizedMatchedFormula",
    "canonical_formula",
    "deterministic_maximum_matching",
    "deterministic_tutte_barrier",
    "formula_from_structure",
    "graph_component_sizes",
    "matched_formula_from_topology",
    "parity_clauses",
    "recognize_connected_matched_exact_one",
    "regional_kernel",
    "regional_state",
]
