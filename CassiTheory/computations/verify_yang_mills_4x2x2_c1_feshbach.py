#!/usr/bin/env python3
"""Sparse finite-volume Feshbach screen on the open 4x2x2 SU(2) graph.

The graph is larger than the recovered 3x2x2 construction, while the
character cutoff stays fixed at C=1.  The full outer Hamiltonian is sparse;
the discarded-sector lower edge is bounded below by the measured full
finite-volume gap, so no dense complement basis is formed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import sys
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix, diags
from scipy.sparse.linalg import eigsh

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations/yang-mills-4x2x2-c1-feshbach-prereg.md"
INDEPENDENT_SOURCE = ROOT / "computations/verify_yang_mills_4x2x2_c1_feshbach_independent.py"
EXACT_SOURCE = ROOT / "computations/verify_yang_mills_exact_block_spectrum.py"
REFERENCE_SOURCE = ROOT / "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"
REFERENCE_PROTOCOL = ROOT / "computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs/yang_mills_4x2x2_c1_feshbach/verification.json"

CUTOFF = 1
COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
RELATIVE_SVD_THRESHOLD = 1.0e-10
MATRIX_TOLERANCE = 1.0e-10
EIGEN_RESIDUAL_TOLERANCE = 1.0e-9
ROOT_TOLERANCE = 1.0e-8


def load_reference() -> Any:
    spec = importlib.util.spec_from_file_location("ym_large_reference_4x2x2", REFERENCE_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load reference source: {REFERENCE_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ym_large_reference_4x2x2"] = module
    spec.loader.exec_module(module)
    return module


REFERENCE = load_reference()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array_sha256(array: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def casimir(n2: int) -> float:
    j = n2 / 2.0
    return j * (j + 1.0)


def valid_triple(a: int, b: int, c: int) -> bool:
    return (a + b + c) % 2 == 0 and abs(a - b) <= c <= a + b


def channel_options(spins: Sequence[int]) -> tuple[int, ...]:
    if len(spins) == 3:
        return (0,) if valid_triple(*spins) else ()
    if len(spins) != 4:
        raise ValueError(f"unsupported valence {len(spins)}")
    a, b, c, d = spins
    return tuple(channel for channel in range(abs(a - b), a + b + 1, 2) if valid_triple(channel, c, d))


VERTEX_COORDS = tuple((x, y, z) for x in range(4) for y in range(2) for z in range(2))
VERTEX_BY_COORD = {coord: index for index, coord in enumerate(VERTEX_COORDS)}

_EDGE_BY_KEY: dict[tuple[str, int, int, int], int] = {}
_LINK_TAILS: list[int] = []
_LINK_HEADS: list[int] = []
_LINK_AXES: list[int] = []
for x in range(3):
    for y in range(2):
        for z in range(2):
            _EDGE_BY_KEY[("x", x, y, z)] = len(_LINK_TAILS)
            _LINK_TAILS.append(VERTEX_BY_COORD[(x, y, z)])
            _LINK_HEADS.append(VERTEX_BY_COORD[(x + 1, y, z)])
            _LINK_AXES.append(0)
for x in range(4):
    for y in range(1):
        for z in range(2):
            _EDGE_BY_KEY[("y", x, y, z)] = len(_LINK_TAILS)
            _LINK_TAILS.append(VERTEX_BY_COORD[(x, y, z)])
            _LINK_HEADS.append(VERTEX_BY_COORD[(x, y + 1, z)])
            _LINK_AXES.append(1)
for x in range(4):
    for y in range(2):
        for z in range(1):
            _EDGE_BY_KEY[("z", x, y, z)] = len(_LINK_TAILS)
            _LINK_TAILS.append(VERTEX_BY_COORD[(x, y, z)])
            _LINK_HEADS.append(VERTEX_BY_COORD[(x, y, z + 1)])
            _LINK_AXES.append(2)
LINK_TAILS = tuple(_LINK_TAILS)
LINK_HEADS = tuple(_LINK_HEADS)
LINK_AXES = tuple(_LINK_AXES)
EDGE_COUNT = len(LINK_TAILS)


def x_edge(x: int, y: int, z: int) -> int:
    return _EDGE_BY_KEY[("x", x, y, z)]


def y_edge(x: int, y: int, z: int) -> int:
    return _EDGE_BY_KEY[("y", x, y, z)]


def z_edge(x: int, y: int, z: int) -> int:
    return _EDGE_BY_KEY[("z", x, y, z)]


plaquette_names: list[str] = []
plaquettes: list[tuple[tuple[int, int], ...]] = []
for z in range(2):
    for x in range(3):
        plaquette_names.append(f"xy_z{z}_{x}")
        plaquettes.append(((x_edge(x, 0, z), +1), (y_edge(x + 1, 0, z), +1),
                           (x_edge(x, 1, z), -1), (y_edge(x, 0, z), -1)))
for y in range(2):
    for x in range(3):
        plaquette_names.append(f"xz_y{y}_{x}")
        plaquettes.append(((x_edge(x, y, 0), +1), (z_edge(x + 1, y, 0), +1),
                           (x_edge(x, y, 1), -1), (z_edge(x, y, 0), -1)))
for x in range(4):
    plaquette_names.append(f"yz_x{x}")
    plaquettes.append(((y_edge(x, 0, 0), +1), (z_edge(x, 1, 0), +1),
                       (y_edge(x, 0, 1), -1), (z_edge(x, 0, 0), -1)))
PLAQUETTE_NAMES = tuple(plaquette_names)
PLAQUETTES = tuple(plaquettes)
PLAQUETTE_COUNT = len(PLAQUETTES)

_incident: list[list[tuple[int, int, int]]] = [[] for _ in VERTEX_COORDS]
for edge, (tail, head, axis) in enumerate(zip(LINK_TAILS, LINK_HEADS, LINK_AXES)):
    _incident[tail].append((axis, 0, edge))
    _incident[head].append((axis, 1, edge))
INCIDENT_LEGS = tuple(
    tuple((edge, +1 if outgoing == 0 else -1, axis) for axis, outgoing, edge in sorted(legs))
    for legs in _incident
)
FOUR_VALENCE_VERTICES = tuple(vertex for vertex, legs in enumerate(INCIDENT_LEGS) if len(legs) == 4)
FOUR_VALENCE_POSITION = {vertex: position for position, vertex in enumerate(FOUR_VALENCE_VERTICES)}

LEFT_BOUNDARY_EDGES = tuple(
    edge for edge, (tail, head) in enumerate(zip(LINK_TAILS, LINK_HEADS))
    if min(VERTEX_COORDS[tail][0], VERTEX_COORDS[head][0]) == 0
    and max(VERTEX_COORDS[tail][0], VERTEX_COORDS[head][0]) <= 1
)
RIGHT_BOUNDARY_EDGES = tuple(
    edge for edge, (tail, head) in enumerate(zip(LINK_TAILS, LINK_HEADS))
    if min(VERTEX_COORDS[tail][0], VERTEX_COORDS[head][0]) >= 2
    and max(VERTEX_COORDS[tail][0], VERTEX_COORDS[head][0]) == 3
)
MIDDLE_EDGES = tuple(edge for edge in range(EDGE_COUNT) if edge not in LEFT_BOUNDARY_EDGES + RIGHT_BOUNDARY_EDGES)

# The reference contraction routines read these module globals.  The lists are
# graph data, not a second source of physics.
REFERENCE.VERTEX_COORDS = VERTEX_COORDS
REFERENCE.LINK_TAILS = LINK_TAILS
REFERENCE.LINK_HEADS = LINK_HEADS
REFERENCE.LINK_AXES = LINK_AXES
REFERENCE.INCIDENT_LEGS = INCIDENT_LEGS
REFERENCE.FOUR_VALENCE_VERTICES = FOUR_VALENCE_VERTICES
REFERENCE.PLAQUETTES = PLAQUETTES
REFERENCE.PLAQUETTE_NAMES = PLAQUETTE_NAMES
REFERENCE._state_edges = lambda state: state[:EDGE_COUNT]
REFERENCE._state_channels = lambda state: state[EDGE_COUNT:]
for cached in (
    REFERENCE._cg_block,
    REFERENCE.vertex_tensor,
    REFERENCE._active_link_tensor,
    REFERENCE._plaquette_kernel,
    REFERENCE._padded_vertex_pair,
    REFERENCE._padded_link_tensor,
    REFERENCE._padded_transfer,
    REFERENCE._transfer_metadata,
):
    cached.cache_clear()

State = tuple[int, ...]


def _boundary_assignments(edge_ids: Sequence[int], boundary_vertices: Sequence[int]) -> list[tuple[int, ...]]:
    assignments: list[tuple[int, ...]] = []
    for values in itertools.product(range(CUTOFF + 1), repeat=len(edge_ids)):
        edge_map = dict(zip(edge_ids, values))
        if all(valid_triple(*(edge_map[edge] for edge, _, _ in INCIDENT_LEGS[vertex])) for vertex in boundary_vertices):
            assignments.append(tuple(int(value) for value in values))
    return assignments


@lru_cache(maxsize=None)
def basis_states(cutoff: int = CUTOFF) -> tuple[State, ...]:
    if cutoff != CUTOFF:
        raise ValueError("this screen freezes C=1")
    left = _boundary_assignments(
        LEFT_BOUNDARY_EDGES,
        tuple(vertex for vertex, coord in enumerate(VERTEX_COORDS) if coord[0] == 0),
    )
    right = _boundary_assignments(
        RIGHT_BOUNDARY_EDGES,
        tuple(vertex for vertex, coord in enumerate(VERTEX_COORDS) if coord[0] == 3),
    )
    left_maps = [dict(zip(LEFT_BOUNDARY_EDGES, values)) for values in left]
    right_maps = [dict(zip(RIGHT_BOUNDARY_EDGES, values)) for values in right]
    states: list[State] = []
    for middle_values in itertools.product(range(cutoff + 1), repeat=len(MIDDLE_EDGES)):
        middle_map = dict(zip(MIDDLE_EDGES, middle_values))
        for left_map in left_maps:
            for right_map in right_maps:
                edge_map = left_map | right_map | middle_map
                edges = tuple(edge_map[index] for index in range(EDGE_COUNT))
                channel_choices: list[tuple[int, ...]] = []
                valid = True
                for vertex in FOUR_VALENCE_VERTICES:
                    choices = channel_options(tuple(edges[edge] for edge, _, _ in INCIDENT_LEGS[vertex]))
                    if not choices:
                        valid = False
                        break
                    channel_choices.append(choices)
                if valid:
                    for channels in itertools.product(*channel_choices):
                        states.append(edges + tuple(int(value) for value in channels))
    return tuple(sorted(states))


def state_edges(state: State) -> tuple[int, ...]:
    return state[:EDGE_COUNT]


def state_channels(state: State) -> tuple[int, ...]:
    return state[EDGE_COUNT:]


def state_norm(state: State) -> float:
    return float(np.prod([1.0 / (state[edge] + 1.0) for edge in range(EDGE_COUNT)]))


def state_energy(state: State) -> float:
    return float(sum(casimir(state[edge]) for edge in range(EDGE_COUNT)))


def basis_hash(states: Sequence[State]) -> str:
    return hashlib.sha256(json.dumps(states, separators=(",", ":")).encode("utf-8")).hexdigest()


def overlap_element(left: State, right: State) -> complex:
    left_edges = state_edges(left)
    right_edges = state_edges(right)
    if left_edges != right_edges:
        return 0.0j
    left_channels = dict(zip(FOUR_VALENCE_VERTICES, state_channels(left)))
    right_channels = dict(zip(FOUR_VALENCE_VERTICES, state_channels(right)))
    value = 1.0
    for vertex, legs in enumerate(INCIDENT_LEGS):
        spins = tuple(left_edges[edge] for edge, _, _ in legs)
        value *= float(np.vdot(
            REFERENCE.vertex_tensor(spins, left_channels.get(vertex)),
            REFERENCE.vertex_tensor(spins, right_channels.get(vertex)),
        ).real)
    value *= state_norm(left)
    return complex(value)


def selected_overlap_checks(states: Sequence[State]) -> list[dict[str, Any]]:
    selected = sorted(set((0, len(states) - 1, len(states) // 2)))
    values: list[dict[str, Any]] = []
    for row in selected:
        for column in selected:
            observed = overlap_element(states[row], states[column])
            expected = state_norm(states[row]) if row == column else 0.0
            values.append({
                "row": row,
                "column": column,
                "observed": [observed.real, observed.imag],
                "expected": expected,
                "residual": abs(observed - expected),
            })
    return values


def reverse_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return tuple((edge, -orientation) for edge, orientation in reversed(word))


def spectator_channel_positions(word: Sequence[tuple[int, int]]) -> tuple[int, ...]:
    active = {
        vertex
        for edge, _ in word
        for vertex in (LINK_TAILS[edge], LINK_HEADS[edge])
    }
    return tuple(
        position for position, vertex in enumerate(FOUR_VALENCE_VERTICES) if vertex not in active
    )


def indexed_groups(states: Sequence[State], word: Sequence[tuple[int, int]]) -> dict[tuple[tuple[int, ...], tuple[int, ...]], np.ndarray]:
    positions = spectator_channel_positions(word)
    groups: dict[tuple[tuple[int, ...], tuple[int, ...]], list[int]] = {}
    for index, state in enumerate(states):
        key = (state_edges(state), tuple(state_channels(state)[position] for position in positions))
        groups.setdefault(key, []).append(index)
    return {key: np.asarray(indices, dtype=np.int32) for key, indices in groups.items()}


def candidate_targets(
    edges: tuple[int, ...],
    spectator_channels: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    groups: dict[tuple[tuple[int, ...], tuple[int, ...]], np.ndarray],
) -> np.ndarray:
    targets: list[np.ndarray] = []
    link_ids = tuple(edge for edge, _ in word)
    for signs in itertools.product((-1, +1), repeat=4):
        target = list(edges)
        for edge, sign in zip(link_ids, signs):
            target[edge] += sign
        if any(value < 0 or value > CUTOFF for value in target):
            continue
        group = groups.get((tuple(target), spectator_channels))
        if group is not None:
            targets.append(group)
    if not targets:
        return np.zeros(0, dtype=np.int32)
    combined = np.concatenate(targets)
    if np.unique(combined).size != combined.size:
        raise RuntimeError("duplicate candidate target index")
    return combined

def fast_matrix_element(left: State, right: State, word: Sequence[tuple[int, int]]) -> complex:
    left_edges = state_edges(left)
    right_edges = state_edges(right)
    active_edges = {edge for edge, _ in word}
    if any(
        left_edges[edge] != right_edges[edge]
        for edge in range(EDGE_COUNT)
        if edge not in active_edges
    ):
        return 0.0j
    word = tuple(word)
    spec, vertex_metadata, path, ordered_edges, _, _ = REFERENCE._plaquette_kernel(word)
    left_channels = dict(zip(FOUR_VALENCE_VERTICES, state_channels(left)))
    right_channels = dict(zip(FOUR_VALENCE_VERTICES, state_channels(right)))
    if any(
        left_channels[vertex] != right_channels[vertex]
        for vertex in FOUR_VALENCE_VERTICES
        if vertex not in {
            endpoint
            for edge in active_edges
            for endpoint in (LINK_TAILS[edge], LINK_HEADS[edge])
        }
    ):
        return 0.0j
    operands: list[np.ndarray] = []
    for vertex, active_positions, inactive_positions in vertex_metadata:
        legs = INCIDENT_LEGS[vertex]
        left_tensor = REFERENCE.vertex_tensor(
            tuple(left_edges[edge] for edge, _, _ in legs),
            left_channels.get(vertex),
        )
        right_tensor = REFERENCE.vertex_tensor(
            tuple(right_edges[edge] for edge, _, _ in legs),
            right_channels.get(vertex),
        )
        if any(left_tensor.shape[index] != right_tensor.shape[index] for index in inactive_positions):
            return 0.0j
        reduced = np.tensordot(left_tensor, right_tensor, axes=(inactive_positions, inactive_positions))
        expected = tuple(left_edges[legs[index][0]] for index in active_positions)
        expected += tuple(right_edges[legs[index][0]] for index in active_positions)
        if reduced.shape != tuple(value + 1 for value in expected):
            raise ValueError(f"reduced vertex shape {reduced.shape} != axes {expected}")
        operands.append(reduced)
    for edge, orientation in zip(ordered_edges, (orientation for _, orientation in word)):
        operands.append(REFERENCE._active_link_tensor(left_edges[edge], right_edges[edge], orientation < 0))
    local = np.einsum(spec, *operands, optimize=path)
    spectator_factor = math.prod(
        1.0 / (right_edges[edge] + 1.0)
        for edge in range(EDGE_COUNT)
        if edge not in active_edges
    )
    return complex(spectator_factor * local)


def matrix_hash(matrix: csr_matrix) -> str:
    quantum = 1.0e-15
    real = np.rint(matrix.data.real / quantum).astype(np.int64)
    imag = np.rint(matrix.data.imag / quantum).astype(np.int64)
    keep = (real != 0) | (imag != 0)
    if not np.any(keep):
        return hashlib.sha256(b"").hexdigest()
    rows = np.repeat(np.arange(matrix.shape[0], dtype=np.int64), np.diff(matrix.indptr))[keep]
    dtype = np.dtype([("row", "<i8"), ("column", "<i8"), ("real", "<i8"), ("imag", "<i8")])
    canonical = np.empty(int(np.count_nonzero(keep)), dtype=dtype)
    canonical["row"] = rows
    canonical["column"] = matrix.indices.astype(np.int64, copy=False)[keep]
    canonical["real"] = real[keep]
    canonical["imag"] = imag[keep]
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def assemble_plaquette(states: Sequence[State], word: Sequence[tuple[int, int]]) -> tuple[csr_matrix, dict[str, Any]]:
    groups = indexed_groups(states, word)
    active_edges = {edge for edge, _ in word}
    target_groups = {
        key: candidate_targets(key[0], key[1], word, groups) for key in groups
    }
    candidate_count = sum(len(columns) * len(target_groups[key]) for key, columns in groups.items())
    rows_out = np.empty(candidate_count, dtype=np.int32)
    columns_out = np.empty(candidate_count, dtype=np.int32)
    values_out = np.empty(candidate_count, dtype=complex)
    cursor = 0
    for key, columns in groups.items():
        target_rows = target_groups[key]
        for column in columns:
            size = target_rows.size
            rows_out[cursor:cursor + size] = target_rows
            columns_out[cursor:cursor + size] = column
            values_out[cursor:cursor + size] = [
                fast_matrix_element(states[int(row)], states[int(column)], word)
                for row in target_rows
            ]
            cursor += size
    if cursor != candidate_count:
        raise RuntimeError(f"candidate assembly wrote {cursor} of {candidate_count} entries")
    matrix = csr_matrix(
        (values_out, (rows_out, columns_out)),
        shape=(len(states), len(states)),
    )
    matrix.sum_duplicates()
    matrix.sort_indices()
    residual = matrix - matrix.T.conjugate()
    hermiticity = float(np.max(np.abs(residual.data))) if residual.nnz else 0.0
    nonzero = int(np.count_nonzero(np.abs(values_out) > MATRIX_TOLERANCE))
    finite = bool(np.isfinite(values_out.real).all() and np.isfinite(values_out.imag).all())
    sample = sorted(zip(*matrix.nonzero()))[:64]
    forbidden: list[tuple[int, int]] = []
    for column in range(min(len(states), 256)):
        right_edges = state_edges(states[column])
        for row in range(min(len(states), 256)):
            left_edges = state_edges(states[row])
            if any(left_edges[edge] != right_edges[edge] for edge in range(EDGE_COUNT) if edge not in active_edges):
                forbidden.append((row, column))
                if len(forbidden) >= 128:
                    break
        if len(forbidden) >= 128:
            break
    forbidden_max = max((abs(matrix[row, column]) for row, column in forbidden), default=0.0)
    reverse = reverse_word(word)
    reverse_groups = indexed_groups(states, reverse)
    reverse_candidate_count = sum(
        len(columns) * len(candidate_targets(key[0], key[1], reverse, reverse_groups))
        for key, columns in reverse_groups.items()
    )
    details = {
        "candidate_entries": int(candidate_count),
        "nonzero_entries": nonzero,
        "forbidden_entries": int(len(states) * len(states) - candidate_count),
        "forbidden_sample_count": len(forbidden),
        "forbidden_sample_zero": bool(forbidden_max <= MATRIX_TOLERANCE),
        "maximum_forbidden_sample_magnitude": float(forbidden_max),
        "finite": finite and bool(np.isfinite(matrix.data.real).all() and np.isfinite(matrix.data.imag).all()),
        "maximum_hermiticity_residual": hermiticity,
        "reverse_support_matches": candidate_count == reverse_candidate_count,
        "candidate_targets_unique": True,
        "matrix_hash": matrix_hash(matrix),
        "nnz": int(matrix.nnz),
        "shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "sample_count": len(sample),
    }
    return matrix, details


def normalized_matrix(matrix: csr_matrix, inverse_sqrt: np.ndarray) -> csr_matrix:
    return matrix.multiply(inverse_sqrt[:, None]).multiply(inverse_sqrt[None, :]).tocsr()


def orthonormal_range(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    left, singular, _ = np.linalg.svd(np.asarray(matrix, dtype=float), full_matrices=False)
    if singular.size == 0 or singular[0] <= 0.0:
        return np.zeros((matrix.shape[0], 0), dtype=float), singular, 0
    rank = int(np.count_nonzero(singular > RELATIVE_SVD_THRESHOLD * singular[0]))
    return left[:, :rank], singular, rank


def eigensystem(matrix: csr_matrix) -> tuple[float, np.ndarray, float, float]:
    initial = np.full(matrix.shape[0], 1.0 / math.sqrt(matrix.shape[0]), dtype=float)
    values, vectors = eigsh(matrix, k=2, which="SA", tol=1.0e-10, maxiter=10000, v0=initial)
    order = np.argsort(values)
    values = values[order]
    vectors = vectors[:, order]
    omega = np.asarray(vectors[:, 0].real, dtype=float)
    pivot = int(np.argmax(np.abs(omega)))
    if omega[pivot] < 0.0:
        omega = -omega
    energy = float(values[0])
    gap = float(values[1] - values[0])
    residual = float(np.linalg.norm(matrix @ omega - energy * omega))
    return energy, omega, gap, residual


def feshbach_row(
    states: Sequence[State],
    physical_plaquette: csr_matrix,
    hamiltonian: csr_matrix,
    energy: float,
    omega: np.ndarray,
    gap: float,
    coupling: Fraction,
    plaquette_ordinal: int,
    source_meta: dict[str, Any],
) -> dict[str, Any]:
    dimension = len(states)
    vacuum = np.zeros(dimension, dtype=float)
    vacuum[states.index(tuple(0 for _ in range(EDGE_COUNT + len(FOUR_VALENCE_VERTICES))))] = 1.0
    source = physical_plaquette @ vacuum
    columns = np.column_stack((vacuum, np.asarray(source.real, dtype=float)))
    projected = columns - np.outer(omega, omega @ columns)
    retained, projected_singular, retained_rank = orthonormal_range(projected)
    if retained_rank == 0:
        return {
            "coupling": str(coupling),
            "x": float(coupling),
            "plaquette_ordinal": plaquette_ordinal,
            "plaquette_name": PLAQUETTE_NAMES[plaquette_ordinal],
            "full_dimension": dimension,
            "retained_source_rank": source_meta["rank"],
            "retained_dimension": 0,
            "discarded_dimension": dimension - 1,
            "source_singular_values": source_meta["singular_values"],
            "projected_source_singular_values": [float(value) for value in projected_singular],
            "ground_energy": energy,
            "ground_residual": float(np.linalg.norm(hamiltonian @ omega - energy * omega)),
            "finite_gap": gap,
            "failure": "empty_projected_source",
            "outer_matrix_sha256": matrix_hash(hamiltonian),
        }
    shifted_retained = retained.T @ (hamiltonian @ retained - energy * retained)
    shifted_retained = 0.5 * (shifted_retained + shifted_retained.T)
    alpha = float(np.min(np.linalg.eigvalsh(shifted_retained)))
    shifted_retained_action = hamiltonian @ retained - energy * retained
    complement_action = shifted_retained_action - retained @ shifted_retained
    complement_action -= np.outer(omega, omega @ complement_action)
    beta = float(np.linalg.svd(complement_action, compute_uv=False)[0])
    delta = gap
    lambda_test = 0.5 * delta
    phi_test = float(alpha - lambda_test - beta * beta / (delta - lambda_test)) if delta > 0.0 else float("-inf")
    phi_zero = float(alpha - beta * beta / delta) if delta > 0.0 else float("-inf")
    certified_gap = None
    if phi_zero > 0.0:
        discriminant = (alpha - delta) ** 2 + 4.0 * beta * beta
        certified_gap = float(0.5 * (alpha + delta - math.sqrt(discriminant)))
    row = {
        "coupling": str(coupling),
        "x": float(coupling),
        "plaquette_ordinal": plaquette_ordinal,
        "plaquette_name": PLAQUETTE_NAMES[plaquette_ordinal],
        "full_dimension": dimension,
        "retained_source_column_count": 2,
        "retained_source_rank": source_meta["rank"],
        "retained_dimension": retained_rank,
        "discarded_dimension": dimension - retained_rank - 1,
        "source_singular_values": source_meta["singular_values"],
        "projected_source_singular_values": [float(value) for value in projected_singular],
        "ground_energy": energy,
        "ground_residual": float(np.linalg.norm(hamiltonian @ omega - energy * omega)),
        "finite_gap": gap,
        "alpha_retained": alpha,
        "delta_oracle": delta,
        "beta_coupling": beta,
        "lambda_test": lambda_test,
        "phi_test": phi_test,
        "phi_zero": phi_zero,
        "conditional_gap_lower_bound": certified_gap,
        "root_to_gap_ratio": None if certified_gap is None else certified_gap / gap,
        "outer_matrix_sha256": matrix_hash(hamiltonian),
        "certificate_type": "full-gap-complement-lower-bound",
    }
    return row


def run(output: Path) -> dict[str, Any]:
    states = basis_states(CUTOFF)
    dimension = len(states)
    edge_zero = tuple(0 for _ in range(EDGE_COUNT))
    vacuum_state = edge_zero + tuple(0 for _ in FOUR_VALENCE_VERTICES)
    vacuum_index = states.index(vacuum_state)
    overlap_checks = selected_overlap_checks(states)
    inverse_sqrt = 1.0 / np.sqrt(np.asarray([state_norm(state) for state in states], dtype=float))
    kinetic = np.asarray([state_energy(state) for state in states], dtype=float)
    matrices: list[csr_matrix] = []
    matrix_records: list[dict[str, Any]] = []
    for ordinal, word in enumerate(PLAQUETTES):
        matrix, details = assemble_plaquette(states, word)
        details.update({
            "ordinal": ordinal,
            "name": PLAQUETTE_NAMES[ordinal],
            "word": [[edge, sign] for edge, sign in word],
            "dagger_word": [[edge, sign] for edge, sign in reverse_word(word)],
            "physical_matrix_hash": matrix_hash(normalized_matrix(matrix, inverse_sqrt)),
        })
        matrices.append(matrix)
        matrix_records.append(details)
    physical_matrices = [normalized_matrix(matrix, inverse_sqrt) for matrix in matrices]
    wilson = csr_matrix((dimension, dimension), dtype=complex)
    for matrix in physical_matrices:
        wilson = (wilson + matrix).tocsr()
    wilson = (0.5 * (wilson + wilson.T.conjugate())).tocsr()
    rows: list[dict[str, Any]] = []
    eigensystems: dict[str, dict[str, Any]] = {}
    for coupling in COUPLINGS:
        x = float(coupling)
        hamiltonian = diags(kinetic + 2.0 * PLAQUETTE_COUNT * x, format="csr") - x * wilson
        hamiltonian = (0.5 * (hamiltonian + hamiltonian.T.conjugate())).tocsr()
        energy, omega, gap, residual = eigensystem(hamiltonian)
        key = str(coupling)
        eigensystems[key] = {
            "ground_energy": energy,
            "gap": gap,
            "ground_residual": residual,
            "hamiltonian_nnz": int(hamiltonian.nnz),
            "hamiltonian_hash": matrix_hash(hamiltonian),
        }
        for ordinal, matrix in enumerate(physical_matrices):
            source_meta = {
                "rank": 2,
                "singular_values": [1.0, 1.0],
            }
            source_vacuum = matrix @ np.eye(dimension, 1, vacuum_index, dtype=float).ravel()
            source_columns = np.column_stack((np.eye(dimension, 1, vacuum_index, dtype=float).ravel(), source_vacuum.real))
            _, singular, rank = orthonormal_range(source_columns)
            source_meta["singular_values"] = [float(value) for value in singular]
            source_meta["rank"] = rank
            row = feshbach_row(
                states, matrix, hamiltonian, energy, omega, gap, coupling, ordinal, source_meta
            )
            row["source_vector_sha256"] = array_sha256(source_vacuum.real)
            rows.append(row)
    per_plaquette: dict[str, Any] = {}
    for name in PLAQUETTE_NAMES:
        family = [row for row in rows if row["plaquette_name"] == name]
        positive = [row for row in family if row.get("conditional_gap_lower_bound") is not None and row["conditional_gap_lower_bound"] > 0.0]
        per_plaquette[name] = {
            "rows": len(family),
            "positive_roots": len(positive),
            "min_conditional_gap_lower_bound": min((row["conditional_gap_lower_bound"] for row in positive), default=None),
            "max_beta": max((row["beta_coupling"] for row in family), default=None),
            "max_root_to_gap_ratio": max((row["root_to_gap_ratio"] for row in positive), default=None),
        }
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.exists()),
        check("independent_source_path", INDEPENDENT_SOURCE.exists()),
        check("exact_source_path", EXACT_SOURCE.exists()),
        check("reference_source_path", REFERENCE_SOURCE.exists()),
        check("reference_protocol_path", REFERENCE_PROTOCOL.exists()),
        check("graph_vertex_count", len(VERTEX_COORDS) == 16),
        check("graph_link_count", EDGE_COUNT == 28),
        check("four_valence_vertex_count", len(FOUR_VALENCE_VERTICES) == 8),
        check("plaquette_count", PLAQUETTE_COUNT == 16),
        check("basis_dimension", dimension == 25676, observed=dimension),
        check("basis_nonempty", bool(states)),
        check("vacuum_index", vacuum_index == 0, observed=vacuum_index),
        check("selected_overlap_controls", all(item["residual"] <= MATRIX_TOLERANCE for item in overlap_checks), controls=overlap_checks),
        check("all_words_close", all(REFERENCE.closed_word(word) for word in PLAQUETTES)),
        check("source_schedule", tuple(PLAQUETTE_NAMES) == (
            "xy_z0_0", "xy_z0_1", "xy_z0_2", "xy_z1_0", "xy_z1_1", "xy_z1_2",
            "xz_y0_0", "xz_y0_1", "xz_y0_2", "xz_y1_0", "xz_y1_1", "xz_y1_2",
            "yz_x0", "yz_x1", "yz_x2", "yz_x3",
        )),
    ]
    for record in matrix_records:
        prefix = record["name"]
        checks.extend([
            check(f"finite_{prefix}", record["finite"]),
            check(f"hermitian_{prefix}", record["maximum_hermiticity_residual"] <= MATRIX_TOLERANCE, residual=record["maximum_hermiticity_residual"]),
            check(f"forbidden_{prefix}", record["forbidden_sample_zero"], maximum=record["maximum_forbidden_sample_magnitude"]),
            check(f"support_{prefix}", record["reverse_support_matches"]),
            check(f"unique_{prefix}", record["candidate_targets_unique"]),
        ])
    for coupling in COUPLINGS:
        eig = eigensystems[str(coupling)]
        checks.extend([
            check(f"eigen_residual_x{coupling}", eig["ground_residual"] <= EIGEN_RESIDUAL_TOLERANCE, residual=eig["ground_residual"]),
            check(f"positive_gap_x{coupling}", eig["gap"] > 0.0, gap=eig["gap"]),
        ])
    for row in rows:
        label = f"{row['plaquette_name']}_x{row['coupling']}"
        checks.extend([
            check(f"source_rank_{label}", row["retained_source_rank"] == 2 and row["retained_dimension"] == 2, rank=row["retained_source_rank"]),
            check(f"row_ground_residual_{label}", row["ground_residual"] <= EIGEN_RESIDUAL_TOLERANCE, residual=row["ground_residual"]),
            check(f"row_positive_floors_{label}", row["alpha_retained"] > 0.0 and row["delta_oracle"] > 0.0),
            check(f"row_test_inequality_{label}", row["phi_test"] > 0.0, phi_test=row["phi_test"]),
            check(f"row_root_bound_{label}", row["conditional_gap_lower_bound"] is None or row["conditional_gap_lower_bound"] <= row["finite_gap"] + ROOT_TOLERANCE, root=row["conditional_gap_lower_bound"], gap=row["finite_gap"]),
        ])
    finite_pass = all(item["passed"] for item in checks)
    positive_rows = [row for row in rows if row.get("conditional_gap_lower_bound") is not None and row["conditional_gap_lower_bound"] > 0.0]
    classification = (
        "SUPPORTS_FINITE_4X2X2_C1_TRANSLATED_FAMILY"
        if finite_pass and len(positive_rows) == len(rows)
        else "NO_POSITIVE_4X2X2_C1_TRANSLATED_FAMILY"
        if finite_pass
        else "INCONCLUSIVE"
    )
    record: dict[str, Any] = {
        "schema": "cassi.yang-mills.4x2x2-c1-feshbach.v1",
        "status": "PASS" if finite_pass else "FAIL",
        "classification": classification,
        "protocol": PROTOCOL.relative_to(ROOT).as_posix(),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "independent_source": INDEPENDENT_SOURCE.relative_to(ROOT).as_posix(),
        "exact_source": EXACT_SOURCE.relative_to(ROOT).as_posix(),
        "reference_source": REFERENCE_SOURCE.relative_to(ROOT).as_posix(),
        "reference_protocol": REFERENCE_PROTOCOL.relative_to(ROOT).as_posix(),
        "source_hashes": {
            "protocol": sha256(PROTOCOL),
            "source": sha256(SOURCE),
            "independent_source": sha256(INDEPENDENT_SOURCE),
            "exact_source": sha256(EXACT_SOURCE),
            "reference_source": sha256(REFERENCE_SOURCE),
            "reference_protocol": sha256(REFERENCE_PROTOCOL),
        },
        "graph": {
            "shape": [4, 2, 2],
            "vertices": [list(coord) for coord in VERTEX_COORDS],
            "tails": list(LINK_TAILS),
            "heads": list(LINK_HEADS),
            "axes": list(LINK_AXES),
            "four_valence_vertices": list(FOUR_VALENCE_VERTICES),
            "cutoff": CUTOFF,
        },
        "plaquettes": [{"name": name, "word": [[edge, sign] for edge, sign in word]} for name, word in zip(PLAQUETTE_NAMES, PLAQUETTES)],
        "basis": {
            "dimension": dimension,
            "state_sha256": basis_hash(states),
            "vacuum_index": vacuum_index,
            "overlap_checks": overlap_checks,
        },
        "matrices": matrix_records,
        "eigensystems": eigensystems,
        "rows": rows,
        "per_plaquette": per_plaquette,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "positive_conditional_rows": len(positive_rows),
        "row_count": len(rows),
        "scope": {
            "outer_graph": "open 4x2x2",
            "character_cutoff": "C=1",
            "retained_family": "vacuum plus one translated fundamental plaquette",
            "complement_bound": "full finite-volume gap used as a Ritz-resolution oracle; exact spectral enclosure unresolved",
            "character_cutoff_removal": "UNRESOLVED",
            "volume_uniform_bound": "UNRESOLVED",
            "lattice_spacing_uniform_bound": "UNRESOLVED",
            "continuum_recovery": "UNRESOLVED",
            "continuum_mass_gap": "UNRESOLVED",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return record


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    record = run(args.output.resolve())
    print(json.dumps({key: record[key] for key in ("status", "classification", "checks_passed", "checks_total", "positive_conditional_rows", "row_count")}, indent=2))
    for name, summary in record["per_plaquette"].items():
        print(f"plaquette {name}: {json.dumps(summary, sort_keys=True)}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
