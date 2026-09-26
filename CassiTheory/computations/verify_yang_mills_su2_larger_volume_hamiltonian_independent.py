#!/usr/bin/env python3
"""Independent reconstruction of the recovered 3x2x2 SU(2) Hamiltonian.

Protocol:
``computations/yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md``.

This verifier rebuilds the graph, complete spin-network basis, spectator-channel
selection, exact Haar link integrals, plaquette matrices, generalized Ritz
problems, and C=1 shell norm from the protocols and shared representation
helper. It does not import the primary larger-volume implementation.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import itertools
import json
import math
from functools import lru_cache
from fractions import Fraction
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh

try:
    _exact = importlib.import_module("verify_yang_mills_exact_block_spectrum")
except ModuleNotFoundError:
    _exact = importlib.import_module("computations.verify_yang_mills_exact_block_spectrum")
def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return str(resolved).replace("\\", "/")


 

Network = _exact.Network
cg_fusion = _exact.cg_fusion
link_integral = _exact.link_integral
metric_tensor = _exact.metric_tensor
three_j = _exact.three_j
valid_triple = _exact.valid_triple

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
SCIENTIFIC_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
SOURCE = Path(__file__).resolve()
PRIMARY = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
HELPER = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
DEFAULT_PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "verification-independent.json"
CUTOFFS = (1, 2)
COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
MATRIX_TOLERANCE = 1.0e-10
EIGEN_RESIDUAL_TOLERANCE = 1.0e-10
HASH_QUANTUM = 1.0e-15
PARSEVAL_TOLERANCE = 1.0e-10
WILSON_SPECTRUM_TOLERANCE = 1.0e-8
WILSON_RESIDUAL_TOLERANCE = 1.0e-8
GROUND_ENERGY_TOLERANCE = 1.0e-8

VERTEX_COORDS = tuple((x, y, z) for x in range(3) for y in range(2) for z in range(2))
VERTEX_BY_COORD = {coord: index for index, coord in enumerate(VERTEX_COORDS)}
LINK_TAIL_COORDS = (
    (0, 0, 0), (0, 0, 1), (0, 1, 0), (0, 1, 1),
    (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1),
    (0, 0, 0), (0, 0, 1), (1, 0, 0), (1, 0, 1),
    (2, 0, 0), (2, 0, 1), (0, 0, 0), (0, 1, 0),
    (1, 0, 0), (1, 1, 0), (2, 0, 0), (2, 1, 0),
)
LINK_HEAD_COORDS = (
    (1, 0, 0), (1, 0, 1), (1, 1, 0), (1, 1, 1),
    (2, 0, 0), (2, 0, 1), (2, 1, 0), (2, 1, 1),
    (0, 1, 0), (0, 1, 1), (1, 1, 0), (1, 1, 1),
    (2, 1, 0), (2, 1, 1), (0, 0, 1), (0, 1, 1),
    (1, 0, 1), (1, 1, 1), (2, 0, 1), (2, 1, 1),
)
LINK_AXES = (0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2)
LINK_TAILS = tuple(VERTEX_BY_COORD[coord] for coord in LINK_TAIL_COORDS)
LINK_HEADS = tuple(VERTEX_BY_COORD[coord] for coord in LINK_HEAD_COORDS)
PLAQUETTE_NAMES = (
    "xy_z0_0", "xy_z0_1", "xy_z1_0", "xy_z1_1",
    "xz_y0_0", "xz_y0_1", "xz_y1_0", "xz_y1_1",
    "yz_x0", "yz_x1", "yz_x2",
)
PLAQUETTES = (
    ((0, +1), (10, +1), (2, -1), (8, -1)),
    ((4, +1), (12, +1), (6, -1), (10, -1)),
    ((1, +1), (11, +1), (3, -1), (9, -1)),
    ((5, +1), (13, +1), (7, -1), (11, -1)),
    ((0, +1), (16, +1), (1, -1), (14, -1)),
    ((4, +1), (18, +1), (5, -1), (16, -1)),
    ((2, +1), (17, +1), (3, -1), (15, -1)),
    ((6, +1), (19, +1), (7, -1), (17, -1)),
    ((8, +1), (15, +1), (9, -1), (14, -1)),
    ((10, +1), (17, +1), (11, -1), (16, -1)),
    ((12, +1), (19, +1), (13, -1), (18, -1)),
)
FOUR_VALENCE_VERTICES = (4, 5, 6, 7)
LEFT_BOUNDARY_EDGES = (0, 1, 2, 3, 8, 9, 14, 15)
RIGHT_BOUNDARY_EDGES = (4, 5, 6, 7, 12, 13, 18, 19)
MIDDLE_EDGES = (10, 11, 16, 17)
State = tuple[int, ...]
FIRING_RIGHT: State = (
    1, 1, 2, 2, 1, 1, 1, 1, 1, 1,
    1, 1, 0, 2, 0, 1, 1, 2, 1, 1,
    0, 0, 3, 1,
)


CandidateGroupKey = tuple[tuple[int, ...], tuple[int, ...]]


def active_vertices(word: Sequence[tuple[int, int]]) -> frozenset[int]:
    return frozenset(
        vertex
        for edge, _ in word
        for vertex in (LINK_TAILS[edge], LINK_HEADS[edge])
    )


def spectator_channel_positions(
    word: Sequence[tuple[int, int]],
) -> tuple[int, ...]:
    active = active_vertices(word)
    return tuple(
        vertex - FOUR_VALENCE_VERTICES[0]
        for vertex in FOUR_VALENCE_VERTICES
        if vertex not in active
    )


def candidate_group_key(
    state: State,
    word: Sequence[tuple[int, int]],
) -> CandidateGroupKey:
    channels = state[20:]
    return (
        state[:20],
        tuple(channels[position] for position in spectator_channel_positions(word)),
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def endpoint(vertex: int, edge: int, orientation: int) -> int:
    if orientation > 0:
        return LINK_HEADS[edge] if LINK_TAILS[edge] == vertex else -1
    return LINK_TAILS[edge] if LINK_HEADS[edge] == vertex else -1


def closed_word(word: Sequence[tuple[int, int]]) -> bool:
    first_edge, first_orientation = word[0]
    current = LINK_TAILS[first_edge] if first_orientation > 0 else LINK_HEADS[first_edge]
    for edge, orientation in word:
        current = endpoint(current, edge, orientation)
        if current < 0:
            return False
    return current == (LINK_TAILS[first_edge] if first_orientation > 0 else LINK_HEADS[first_edge])


def incident_legs(vertex: int) -> tuple[tuple[int, int, int], ...]:
    legs = []
    for edge, (tail, head, axis) in enumerate(zip(LINK_TAILS, LINK_HEADS, LINK_AXES)):
        if tail == vertex:
            legs.append((axis, 0, edge))
        elif head == vertex:
            legs.append((axis, 1, edge))
    return tuple((edge, +1 if outgoing == 0 else -1, axis) for axis, outgoing, edge in sorted(legs))


INCIDENT_LEGS = tuple(incident_legs(vertex) for vertex in range(len(VERTEX_COORDS)))


def valid_channel_options(spins: Sequence[int]) -> tuple[int, ...]:
    if len(spins) == 3:
        return (0,) if valid_triple(*spins) else ()
    a, b, c, d = spins
    return tuple(channel for channel in range(abs(a - b), a + b + 1, 2) if valid_triple(channel, c, d))


def boundary_assignments(cutoff: int, edge_ids: Sequence[int], vertices: Sequence[int]) -> list[tuple[int, ...]]:
    result = []
    for values in itertools.product(range(cutoff + 1), repeat=len(edge_ids)):
        mapping = dict(zip(edge_ids, values))
        if all(valid_triple(*(mapping[edge] for edge, _, _ in INCIDENT_LEGS[vertex])) for vertex in vertices):
            result.append(tuple(int(value) for value in values))
    return result


@lru_cache(maxsize=None)
def basis_states(cutoff: int) -> tuple[State, ...]:
    left = boundary_assignments(cutoff, LEFT_BOUNDARY_EDGES, (0, 1, 2, 3))
    right = boundary_assignments(cutoff, RIGHT_BOUNDARY_EDGES, (8, 9, 10, 11))
    states: list[State] = []
    for left_values in left:
        left_map = dict(zip(LEFT_BOUNDARY_EDGES, left_values))
        for right_values in right:
            right_map = dict(zip(RIGHT_BOUNDARY_EDGES, right_values))
            for middle_values in itertools.product(range(cutoff + 1), repeat=len(MIDDLE_EDGES)):
                edge_map = {**left_map, **right_map, **dict(zip(MIDDLE_EDGES, middle_values))}
                edges = tuple(edge_map[index] for index in range(20))
                channel_choices = []
                for vertex in FOUR_VALENCE_VERTICES:
                    channel_choices.append(valid_channel_options(tuple(edges[edge] for edge, _, _ in INCIDENT_LEGS[vertex])))
                if any(not choices for choices in channel_choices):
                    continue
                for channels in itertools.product(*channel_choices):
                    states.append(edges + tuple(int(value) for value in channels))
    return tuple(sorted(states))


@lru_cache(maxsize=None)
def cg_block(n2a: int, n2b: int, n2c: int) -> np.ndarray:
    table, jblock = cg_fusion(n2a, n2b)
    positions = np.where(jblock == n2c)[0]
    if positions.size != n2c + 1:
        raise ValueError(f"missing CG block {(n2a, n2b, n2c)}")
    return np.asarray(table[:, :, positions], dtype=float)


@lru_cache(maxsize=None)
def vertex_tensor(spins: tuple[int, ...], channel: int | None) -> np.ndarray:
    if len(spins) == 3:
        if channel not in (None, 0) or not valid_triple(*spins):
            raise ValueError(f"invalid trivalent tensor {spins} {channel}")
        return np.asarray(three_j(*spins), dtype=float)
    if channel is None or len(spins) != 4:
        raise ValueError(f"invalid four-valent tensor {spins} {channel}")
    first = cg_block(spins[0], spins[1], channel)
    second = cg_block(channel, spins[2], spins[3])
    tensor = np.einsum("ija,akb,bl->ijkl", first, second, metric_tensor(spins[3]))
    tensor_norm = float(np.linalg.norm(tensor))
    if tensor_norm <= 0.0:
        raise ArithmeticError(f"zero four-valent tensor {spins} {channel}")
    return tensor / tensor_norm


@lru_cache(maxsize=None)
def active_link_tensor(left_spin: int, right_spin: int, conjugated: bool) -> np.ndarray:
    net = Network()
    bra_m = net.label("bm", (left_spin,))
    bra_n = net.label("bn", (left_spin,))
    ket_m = net.label("km", (right_spin,))
    ket_n = net.label("kn", (right_spin,))
    first = net.label("fa", (1,))
    second = net.label("fb", (1,))
    link_integral(net, [(bra_m, bra_n, True), (ket_m, ket_n, False), (first, second, conjugated)], "independent")
    raw = np.asarray(net.contract(open_axes=(bra_m, bra_n, ket_m, ket_n, first, second)))
    return np.einsum("ijklmn,qj,rl->iqkrmn", raw, metric_tensor(left_spin), metric_tensor(right_spin))


@lru_cache(maxsize=None)
def padded_vertex(
    vertex: int,
    left_spins: tuple[int, ...],
    left_channel: int | None,
    right_spins: tuple[int, ...],
    right_channel: int | None,
    active_positions: tuple[int, ...],
    inactive_positions: tuple[int, ...],
) -> np.ndarray:
    left = vertex_tensor(left_spins, left_channel)
    right = vertex_tensor(right_spins, right_channel)
    if any(left.shape[index] != right.shape[index] for index in inactive_positions):
        return np.zeros((3, 3, 3, 3), dtype=float)
    reduced = np.tensordot(left, right, axes=(inactive_positions, inactive_positions))
    shape = tuple(left_spins[index] + 1 for index in active_positions)
    shape += tuple(right_spins[index] + 1 for index in active_positions)
    out = np.zeros((3, 3, 3, 3), dtype=float)
    out[tuple(slice(0, size) for size in shape)] = reduced
    return out


@lru_cache(maxsize=None)
def padded_link(left_spin: int, right_spin: int, conjugated: bool) -> np.ndarray:
    raw = active_link_tensor(left_spin, right_spin, conjugated)
    out = np.zeros((3, 3, 3, 3, 2, 2), dtype=complex)
    out[:left_spin + 1, :left_spin + 1, :right_spin + 1, :right_spin + 1, :, :] = raw
    return out


@lru_cache(maxsize=None)
def transfer_metadata(word: tuple[tuple[int, int], ...]):
    current = LINK_TAILS[word[0][0]] if word[0][1] > 0 else LINK_HEADS[word[0][0]]
    out = []
    for position, (edge, orientation) in enumerate(word):
        next_vertex = endpoint(current, edge, orientation)
        if next_vertex < 0:
            raise ValueError(f"non-closing plaquette {word}")
        legs = INCIDENT_LEGS[current]
        incoming_edge = word[position - 1][0]
        incoming_position = next(index for index, (candidate, _, _) in enumerate(legs) if candidate == incoming_edge)
        outgoing_position = next(index for index, (candidate, _, _) in enumerate(legs) if candidate == edge)
        active_positions = tuple(index for index, (candidate, _, _) in enumerate(legs) if candidate in (incoming_edge, edge))
        inactive_positions = tuple(index for index, (candidate, _, _) in enumerate(legs) if candidate not in (incoming_edge, edge))
        out.append((current, incoming_edge, edge, incoming_position, outgoing_position, active_positions, inactive_positions, orientation))
        current = next_vertex
    return tuple(out)


@lru_cache(maxsize=None)
def transfer_matrix(
    vertex: int,
    incoming_edge: int,
    outgoing_edge: int,
    incoming_position: int,
    outgoing_position: int,
    active_positions: tuple[int, ...],
    inactive_positions: tuple[int, ...],
    left_spins: tuple[int, ...],
    left_channel: int | None,
    right_spins: tuple[int, ...],
    right_channel: int | None,
    left_outgoing_spin: int,
    right_outgoing_spin: int,
    orientation: int,
) -> np.ndarray:
    reduced = padded_vertex(vertex, left_spins, left_channel, right_spins, right_channel, active_positions, inactive_positions)
    incoming_index = active_positions.index(incoming_position)
    outgoing_index = active_positions.index(outgoing_position)
    ordered = np.transpose(reduced, (incoming_index, outgoing_index, len(active_positions) + incoming_index, len(active_positions) + outgoing_index))
    link = padded_link(left_outgoing_spin, right_outgoing_spin, orientation < 0)
    if orientation < 0:
        link = np.transpose(link, (1, 0, 3, 2, 5, 4))
    return np.einsum("abcd,bedfgh->acgefh", ordered, link, optimize=True).reshape(18, 18)


TRANSFER_SPEC = "bij,bjk,bkl,bli->b"
TRANSFER_PATH = np.einsum_path(
    TRANSFER_SPEC,
    np.zeros((1, 18, 18)), np.zeros((1, 18, 18)),
    np.zeros((1, 18, 18)), np.zeros((1, 18, 18)), optimize="greedy",
)[0]


def indexed_groups(states: Sequence[State]):
    groups: dict[tuple[int, ...], list[int]] = {}
    edges = np.asarray([state[:20] for state in states], dtype=np.int8)
    channels = np.asarray([state[20:] for state in states], dtype=np.int8)
    for index, state in enumerate(states):
        groups.setdefault(state[:20], []).append(index)
    return {key: np.asarray(value, dtype=np.int32) for key, value in groups.items()}, edges, channels


def indexed_candidate_groups(
    states: Sequence[State],
    word: Sequence[tuple[int, int]],
) -> dict[CandidateGroupKey, np.ndarray]:
    groups: dict[CandidateGroupKey, list[int]] = {}
    for index, state in enumerate(states):
        groups.setdefault(candidate_group_key(state, word), []).append(index)
    return {
        key: np.asarray(indices, dtype=np.int32)
        for key, indices in groups.items()
    }


def transition_targets(
    edges: tuple[int, ...],
    spectator_channels: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    groups: dict[CandidateGroupKey, np.ndarray],
    cutoff: int,
) -> np.ndarray:
    targets = []
    for signs in itertools.product((-1, +1), repeat=4):
        target = list(edges)
        for edge, sign in zip((edge for edge, _ in word), signs):
            target[edge] += sign
        if any(value < 0 or value > cutoff for value in target):
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


def edge_only_transition_targets(
    edges: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    groups: dict[tuple[int, ...], np.ndarray],
    cutoff: int,
) -> np.ndarray:
    targets = []
    for signs in itertools.product((-1, +1), repeat=4):
        target = list(edges)
        for edge, sign in zip((edge for edge, _ in word), signs):
            target[edge] += sign
        if any(value < 0 or value > cutoff for value in target):
            continue
        group = groups.get(tuple(target))
        if group is not None:
            targets.append(group)
    return np.concatenate(targets) if targets else np.zeros(0, dtype=np.int32)


def transition_tables(states, word, edge_array, channel_array):
    metadata = transfer_metadata(tuple(word))
    ids_by_position = []
    records_by_position = []
    for vertex, _, outgoing_edge, _, _, _, _, _ in metadata:
        legs = INCIDENT_LEGS[vertex]
        records = []
        lookup = {}
        ids = np.empty(len(states), dtype=np.int16)
        for index in range(len(states)):
            spins = tuple(int(edge_array[index, edge]) for edge, _, _ in legs)
            channel = int(channel_array[index, vertex - FOUR_VALENCE_VERTICES[0]]) if vertex in FOUR_VALENCE_VERTICES else None
            key = (spins, channel, int(edge_array[index, outgoing_edge]))
            identifier = lookup.get(key)
            if identifier is None:
                identifier = len(records)
                lookup[key] = identifier
                records.append(key)
            ids[index] = identifier
        ids_by_position.append(ids)
        records_by_position.append(tuple(records))

    pair_maps = []
    transfer_tables = []
    for position, metadata_row in enumerate(metadata):
        vertex, incoming_edge, outgoing_edge, incoming_position, outgoing_position, active_positions, inactive_positions, orientation = metadata_row
        records = records_by_position[position]
        pair_map = np.empty((len(records), len(records)), dtype=np.int16)
        matrices = []
        for left_spins, left_channel, left_outgoing in records:
            for right_spins, right_channel, right_outgoing in records:
                pair_map[len(matrices) // len(records), len(matrices) % len(records)] = len(matrices)
                matrices.append(transfer_matrix(vertex, incoming_edge, outgoing_edge, incoming_position, outgoing_position, active_positions, inactive_positions, left_spins, left_channel, right_spins, right_channel, left_outgoing, right_outgoing, orientation))
        pair_maps.append(pair_map)
        transfer_tables.append(np.asarray(matrices, dtype=complex))
    return ids_by_position, pair_maps, transfer_tables


def transition_values(rows, columns, ids_by_position, pair_maps, transfer_tables):
    pair_ids = [pair_maps[pos][ids_by_position[pos][rows], ids_by_position[pos][columns]] for pos in range(4)]
    radices = [table.shape[0] for table in transfer_tables]
    encoded = pair_ids[0].astype(np.int64)
    for pos in range(1, 4):
        encoded = encoded * radices[pos] + pair_ids[pos]
    unique, inverse = np.unique(encoded, return_inverse=True)
    remaining = unique.copy()
    ids = []
    for radix in reversed(radices):
        ids.append(remaining % radix)
        remaining //= radix
    ids.reverse()
    values = np.einsum(TRANSFER_SPEC, *[transfer_tables[pos][ids[pos]] for pos in range(4)], optimize=TRANSFER_PATH)
    return values[inverse]


def matrix_hash(matrix: csr_matrix) -> str:
    real_quantized = np.rint(matrix.data.real / HASH_QUANTUM).astype(np.int64)
    imag_quantized = np.rint(matrix.data.imag / HASH_QUANTUM).astype(np.int64)
    keep = (real_quantized != 0) | (imag_quantized != 0)
    if not np.any(keep):
        return hashlib.sha256(b"").hexdigest()
    rows = np.repeat(
        np.arange(matrix.shape[0], dtype=np.int64),
        np.diff(matrix.indptr),
    )[keep]
    columns = matrix.indices.astype(np.int64, copy=False)[keep]
    canonical_dtype = np.dtype(
        [("row", "<i8"), ("column", "<i8"), ("real", "<i8"), ("imag", "<i8")],
        align=False,
    )
    canonical = np.empty(rows.size, dtype=canonical_dtype)
    canonical["row"] = rows
    canonical["column"] = columns
    canonical["real"] = real_quantized[keep]
    canonical["imag"] = imag_quantized[keep]
    return hashlib.sha256(canonical.tobytes()).hexdigest()


def assemble(states, word, cutoff: int, chunk_size: int = 262144):
    groups, edge_array, channel_array = indexed_groups(states)
    candidate_groups = indexed_candidate_groups(states, word)
    spectator_positions = spectator_channel_positions(word)
    ids_by_position, pair_maps, transfer_tables = transition_tables(states, tuple(word), edge_array, channel_array)
    active_edges = {edge for edge, _ in word}
    spectator = np.ones(len(states), dtype=float)
    for edge in range(20):
        if edge not in active_edges:
            spectator /= edge_array[:, edge] + 1.0
    target_groups = {
        key: transition_targets(
            key[0],
            key[1],
            word,
            candidate_groups,
            cutoff,
        )
        for key in candidate_groups
    }
    candidate_count = sum(
        len(columns) * len(target_groups[key])
        for key, columns in candidate_groups.items()
    )
    rows = np.empty(candidate_count, dtype=np.int32)
    columns = np.empty(candidate_count, dtype=np.int32)
    values = np.empty(candidate_count, dtype=complex)
    cursor = 0
    pending_rows: list[np.ndarray] = []
    pending_columns: list[np.ndarray] = []
    pending_count = 0

    def flush():
        nonlocal cursor, pending_count
        if not pending_rows:
            return
        batch_rows = np.concatenate(pending_rows)
        batch_columns = np.concatenate(pending_columns)
        if spectator_positions and np.any(
            channel_array[batch_rows][:, spectator_positions]
            != channel_array[batch_columns][:, spectator_positions]
        ):
            raise ArithmeticError("candidate support changed a spectator intertwiner channel")
        batch_values = transition_values(batch_rows, batch_columns, ids_by_position, pair_maps, transfer_tables)
        batch_values *= spectator[batch_columns]
        size = batch_rows.size
        rows[cursor:cursor + size] = batch_rows
        columns[cursor:cursor + size] = batch_columns
        values[cursor:cursor + size] = batch_values
        cursor += size
        pending_rows.clear()
        pending_columns.clear()
        pending_count = 0

    for key, column_group in candidate_groups.items():
        target_rows = target_groups[key]
        if target_rows.size == 0:
            continue
        pending_rows.append(np.tile(target_rows, column_group.size))
        pending_columns.append(np.repeat(column_group, target_rows.size))
        pending_count += target_rows.size * column_group.size
        if pending_count >= chunk_size:
            flush()
    flush()
    if cursor != candidate_count:
        raise RuntimeError(f"assembled {cursor} of {candidate_count} entries")
    matrix = csr_matrix((values, (rows, columns)), shape=(len(states), len(states)))
    matrix.sum_duplicates()
    matrix.sort_indices()
    hermitian = matrix - matrix.T.conjugate()
    digest = matrix_hash(matrix)
    physical = normalized_operator(matrix, states)
    squared = physical.conjugate().multiply(physical)
    column_norms_squared = np.asarray(squared.sum(axis=0)).ravel().real
    maximum_column = int(np.argmax(column_norms_squared)) if column_norms_squared.size else 0
    maximum_column_norm_squared = (
        float(column_norms_squared[maximum_column])
        if column_norms_squared.size
        else 0.0
    )
    return matrix, {
        "candidate_entries": int(candidate_count),
        "nonzero_entries": int(np.count_nonzero(np.abs(values) > MATRIX_TOLERANCE)),
        "matrix_hash": digest,
        "maximum_hermiticity_residual": float(np.max(np.abs(hermitian.data))) if hermitian.nnz else 0.0,
        "finite": bool(np.isfinite(np.real(values)).all() and np.isfinite(np.imag(values)).all()),
        "spectator_channels_preserved": True,
        "candidate_targets_unique": True,
        "maximum_normalized_column_index": maximum_column,
        "maximum_normalized_column_norm_squared": maximum_column_norm_squared,
    }


def norm(state: State) -> float:
    return float(np.prod([1.0 / (state[edge] + 1.0) for edge in range(20)]))


def normalized_operator(matrix: csr_matrix, states: Sequence[State]) -> csr_matrix:
    norms = np.asarray([norm(state) for state in states], dtype=float)
    inverse_sqrt = 1.0 / np.sqrt(norms)
    return matrix.multiply(inverse_sqrt[:, None]).multiply(inverse_sqrt[None, :]).tocsr()


def normalized_operator_extrema(
    matrix: csr_matrix,
    states: Sequence[State],
) -> dict[str, float]:
    physical = normalized_operator(matrix, states)
    physical = (0.5 * (physical + physical.T.conjugate())).tocsr()
    minimum_values, minimum_vectors = eigsh(
        physical,
        k=1,
        which="SA",
        tol=1.0e-11,
        maxiter=max(2000, physical.shape[0] * 20),
    )
    maximum_values, maximum_vectors = eigsh(
        physical,
        k=1,
        which="LA",
        tol=1.0e-11,
        maxiter=max(2000, physical.shape[0] * 20),
    )
    minimum = float(minimum_values[0])
    maximum = float(maximum_values[0])
    return {
        "minimum": minimum,
        "maximum": maximum,
        "minimum_residual": float(
            np.linalg.norm(physical @ minimum_vectors[:, 0] - minimum * minimum_vectors[:, 0])
        ),
        "maximum_residual": float(
            np.linalg.norm(physical @ maximum_vectors[:, 0] - maximum * maximum_vectors[:, 0])
        ),
    }


def energy(state: State) -> float:
    return float(sum((state[edge] / 2.0) * (state[edge] / 2.0 + 1.0) for edge in range(20)))


def basis_hash(states: Sequence[State]) -> str:
    return hashlib.sha256(json.dumps(states, separators=(",", ":")).encode("utf-8")).hexdigest()


def spectator_channel_firing_control(states: Sequence[State]) -> dict[str, Any]:
    state_index = {state: index for index, state in enumerate(states)}
    if FIRING_RIGHT not in state_index:
        raise ArithmeticError("frozen firing-control ket is absent from the C=2 basis")
    word = PLAQUETTES[8]
    right_index = state_index[FIRING_RIGHT]
    edge_groups, edge_array, channel_array = indexed_groups(states)
    legacy_targets = edge_only_transition_targets(
        FIRING_RIGHT[:20],
        word,
        edge_groups,
        2,
    )
    recovered_groups = indexed_candidate_groups(states, word)
    recovered_key = candidate_group_key(FIRING_RIGHT, word)
    recovered_targets = transition_targets(
        recovered_key[0],
        recovered_key[1],
        word,
        recovered_groups,
        2,
    )
    ids_by_position, pair_maps, transfer_tables = transition_tables(
        states,
        word,
        edge_array,
        channel_array,
    )
    active_edges = {edge for edge, _ in word}
    spectator_factor = float(
        np.prod(
            [
                1.0 / (FIRING_RIGHT[edge] + 1.0)
                for edge in range(20)
                if edge not in active_edges
            ]
        )
    )

    def values(targets: np.ndarray) -> np.ndarray:
        columns = np.full(targets.size, right_index, dtype=np.int32)
        return (
            transition_values(
                targets,
                columns,
                ids_by_position,
                pair_maps,
                transfer_tables,
            )
            * spectator_factor
        )

    legacy_values = values(legacy_targets)
    recovered_values = values(recovered_targets)
    legacy_column_norm_squared = float(
        sum(
            abs(value) ** 2 / (norm(states[int(row)]) * norm(FIRING_RIGHT))
            for row, value in zip(legacy_targets, legacy_values)
        )
    )
    recovered_column_norm_squared = float(
        sum(
            abs(value) ** 2 / (norm(states[int(row)]) * norm(FIRING_RIGHT))
            for row, value in zip(recovered_targets, recovered_values)
        )
    )
    mismatched_offsets = [
        offset
        for offset, (row, value) in enumerate(zip(legacy_targets, legacy_values))
        if candidate_group_key(states[int(row)], word)[1] != recovered_key[1]
        and abs(value) > MATRIX_TOLERANCE
    ]
    if not mismatched_offsets:
        raise ArithmeticError("frozen firing control did not expose the legacy support defect")
    mismatch_offset = min(
        mismatched_offsets,
        key=lambda offset: states[int(legacy_targets[offset])],
    )
    mismatch_row = int(legacy_targets[mismatch_offset])
    mismatch_state = states[mismatch_row]
    spectator_position = next(
        position
        for position in spectator_channel_positions(word)
        if mismatch_state[20 + position] != FIRING_RIGHT[20 + position]
    )
    spectator_vertex = FOUR_VALENCE_VERTICES[spectator_position]
    legs = INCIDENT_LEGS[spectator_vertex]
    left_tensor = vertex_tensor(
        tuple(mismatch_state[edge] for edge, _, _ in legs),
        mismatch_state[20 + spectator_position],
    )
    right_tensor = vertex_tensor(
        tuple(FIRING_RIGHT[edge] for edge, _, _ in legs),
        FIRING_RIGHT[20 + spectator_position],
    )
    remote_channel_overlap = 1.0 + 0.0j
    for position in spectator_channel_positions(word):
        vertex = FOUR_VALENCE_VERTICES[position]
        vertex_legs = INCIDENT_LEGS[vertex]
        mismatch_tensor = vertex_tensor(
            tuple(mismatch_state[edge] for edge, _, _ in vertex_legs),
            mismatch_state[20 + position],
        )
        firing_tensor = vertex_tensor(
            tuple(FIRING_RIGHT[edge] for edge, _, _ in vertex_legs),
            FIRING_RIGHT[20 + position],
        )
        remote_channel_overlap *= np.vdot(mismatch_tensor, firing_tensor)
    corrected_mismatched_value = (
        legacy_values[mismatch_offset] * remote_channel_overlap
    )
    local_overlap = np.vdot(left_tensor, right_tensor)
    recovered_target_set = set(int(value) for value in recovered_targets)
    return {
        "plaquette": PLAQUETTE_NAMES[8],
        "right_state_index": right_index,
        "legacy_candidate_count": int(legacy_targets.size),
        "recovered_candidate_count": int(recovered_targets.size),
        "legacy_normalized_column_norm_squared": legacy_column_norm_squared,
        "recovered_normalized_column_norm_squared": recovered_column_norm_squared,
        "mismatched_remote_channel_state_index": mismatch_row,
        "mismatched_remote_channel_position": spectator_position,
        "mismatched_remote_channel_vertex": spectator_vertex,
        "legacy_mismatched_value": [
            float(legacy_values[mismatch_offset].real),
            float(legacy_values[mismatch_offset].imag),
        ],
        "corrected_mismatched_value": [
            float(corrected_mismatched_value.real),
            float(corrected_mismatched_value.imag),
        ],
        "local_channel_overlap": [
            float(local_overlap.real),
            float(local_overlap.imag),
        ],
        "mismatched_state_excluded_from_recovered_support": mismatch_row
        not in recovered_target_set,
    }


def solve(states, operator, coupling: Fraction):
    dimension = len(states)
    norms = np.asarray([norm(state) for state in states], dtype=float)
    kinetic = np.asarray([energy(state) for state in states], dtype=float)
    x = float(coupling)
    diagonal = (kinetic + 22.0 * x) * norms
    hamiltonian = csr_matrix((diagonal, (np.arange(dimension), np.arange(dimension))), shape=(dimension, dimension)) - x * operator
    scale = 1.0 / np.sqrt(norms)
    orthogonal = hamiltonian.multiply(scale[:, None]).multiply(scale[None, :]).tocsr()
    orthogonal = (0.5 * (orthogonal + orthogonal.T.conjugate())).tocsr()
    values, vectors = eigsh(orthogonal, k=2, which="SA", tol=1.0e-12, maxiter=max(1000, dimension * 20))  # type: ignore[arg-type]
    order = np.argsort(values)
    values, vectors = values[order], vectors[:, order]
    residual = orthogonal @ vectors[:, 0] - values[0] * vectors[:, 0]
    return float(values[0]), float(values[1]), float(np.linalg.norm(residual)), int(hamiltonian.nnz)


def shell_norm(states_one, states_two, operator, coupling: float) -> float:
    index_two = {state: index for index, state in enumerate(states_two)}
    retained = np.asarray([index_two[state] for state in states_one], dtype=np.int32)
    mask = np.ones(len(states_two), dtype=bool)
    mask[retained] = False
    shell = np.flatnonzero(mask)
    block = operator[shell, :][:, retained].tocsr()
    shell_norms = np.asarray([norm(states_two[index]) for index in shell], dtype=float)
    retained_norms = np.asarray([norm(state) for state in states_one], dtype=float)
    physical = block.multiply((coupling / np.sqrt(shell_norms))[:, None])
    physical = physical.multiply((1.0 / np.sqrt(retained_norms))[None, :])
    gram = (physical.T.conjugate() @ physical).toarray()
    return math.sqrt(max(0.0, float(np.max(np.linalg.eigvalsh(gram))))) if gram.size else 0.0


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def run(primary_path: Path, output: Path) -> dict[str, Any]:
    primary = json.loads(primary_path.read_text(encoding="utf-8"))
    bases = {cutoff: basis_states(cutoff) for cutoff in CUTOFFS}
    basis_records = {}
    checks = [
        check("protocol_path", PROTOCOL.exists()),
        check("scientific_protocol_path", SCIENTIFIC_PROTOCOL.exists()),
        check("primary_receipt_path", primary_path.exists()),
        check("primary_status", primary.get("status") == "PASS", status=primary.get("status")),
        check("graph_vertex_count", len(VERTEX_COORDS) == 12),
        check("graph_link_count", len(LINK_TAILS) == 20 and len(LINK_HEADS) == 20),
        check("plaquette_count", len(PLAQUETTES) == 11),
        check("all_words_close", all(closed_word(word) for word in PLAQUETTES)),
        check(
            "all_plaquette_links_distinct",
            all(len({edge for edge, _ in word}) == 4 for word in PLAQUETTES),
        ),
    ]
    for cutoff, states in bases.items():
        digest = basis_hash(states)
        expected = primary["basis"][str(cutoff)]
        basis_records[str(cutoff)] = {"dimension": len(states), "state_sha256": digest}
        checks.extend([
            check(f"basis_dimension_C{cutoff}", len(states) == expected["dimension"], observed=len(states), expected=expected["dimension"]),
            check(f"basis_hash_C{cutoff}", digest == expected["state_sha256"], observed=digest, expected=expected["state_sha256"]),
        ])

    matrices: dict[int, list[dict[str, Any]]] = {}
    operators: dict[int, csr_matrix] = {}
    for cutoff, states in bases.items():
        records = []
        operator = csr_matrix((len(states), len(states)), dtype=complex)
        for name, word in zip(PLAQUETTE_NAMES, PLAQUETTES):
            matrix, data = assemble(states, word, cutoff)
            operator = (operator + matrix).tocsr()
            expected = next(item for item in primary["matrices"][str(cutoff)] if item["name"] == name)
            record = {**data, "name": name, "word": [[edge, sign] for edge, sign in word]}
            records.append(record)
            checks.extend([
                check(f"matrix_hash_C{cutoff}_{name}", data["matrix_hash"] == expected["matrix_hash"], observed=data["matrix_hash"], expected=expected["matrix_hash"]),
                check(f"candidate_count_C{cutoff}_{name}", data["candidate_entries"] == expected["candidate_entries"], observed=data["candidate_entries"], expected=expected["candidate_entries"]),
                check(f"nonzero_count_C{cutoff}_{name}", data["nonzero_entries"] == expected["nonzero_entries"], observed=data["nonzero_entries"], expected=expected["nonzero_entries"]),
                check(f"finite_C{cutoff}_{name}", data["finite"]),
                check(f"hermitian_C{cutoff}_{name}", data["maximum_hermiticity_residual"] <= MATRIX_TOLERANCE, residual=data["maximum_hermiticity_residual"]),
                check(
                    f"parseval_C{cutoff}_{name}",
                    data["maximum_normalized_column_norm_squared"]
                    <= 4.0 + PARSEVAL_TOLERANCE,
                    maximum=data["maximum_normalized_column_norm_squared"],
                ),
                check(
                    f"parseval_match_C{cutoff}_{name}",
                    abs(
                        data["maximum_normalized_column_norm_squared"]
                        - expected["maximum_normalized_column_norm_squared"]
                    )
                    <= 1.0e-8,
                    observed=data["maximum_normalized_column_norm_squared"],
                    expected=expected["maximum_normalized_column_norm_squared"],
                ),
                check(
                    f"spectator_channels_C{cutoff}_{name}",
                    data["spectator_channels_preserved"],
                ),
                check(
                    f"unique_candidates_C{cutoff}_{name}",
                    data["candidate_targets_unique"],
                ),
            ])
            del matrix
        operator.sum_duplicates()
        operator.sort_indices()
        matrices[cutoff] = records
        operators[cutoff] = operator
    wilson_spectra = {
        str(cutoff): normalized_operator_extrema(operators[cutoff], bases[cutoff])
        for cutoff in CUTOFFS
    }
    firing_control = spectator_channel_firing_control(bases[2])
    primary_firing = primary["spectator_channel_firing_control"]
    checks.extend([
        check(
            "firing_legacy_parseval_violation",
            firing_control["legacy_normalized_column_norm_squared"]
            > 4.0 + PARSEVAL_TOLERANCE,
            observed=firing_control["legacy_normalized_column_norm_squared"],
        ),
        check(
            "firing_recovered_parseval_bound",
            firing_control["recovered_normalized_column_norm_squared"]
            <= 4.0 + PARSEVAL_TOLERANCE,
            observed=firing_control["recovered_normalized_column_norm_squared"],
        ),
        check(
            "firing_remote_channel_overlap_zero",
            abs(complex(*firing_control["local_channel_overlap"]))
            <= MATRIX_TOLERANCE,
            overlap=firing_control["local_channel_overlap"],
        ),
        check(
            "firing_mismatched_matrix_element_zero",
            abs(complex(*firing_control["corrected_mismatched_value"]))
            <= MATRIX_TOLERANCE,
            value=firing_control["corrected_mismatched_value"],
        ),
        check(
            "firing_mismatched_state_excluded",
            firing_control["mismatched_state_excluded_from_recovered_support"],
        ),
        check(
            "firing_counts_match_primary",
            firing_control["legacy_candidate_count"]
            == primary_firing["legacy_candidate_count"]
            and firing_control["recovered_candidate_count"]
            == primary_firing["recovered_candidate_count"],
        ),
        check(
            "firing_norms_match_primary",
            abs(
                firing_control["legacy_normalized_column_norm_squared"]
                - primary_firing["legacy_normalized_column_norm_squared"]
            )
            <= 1.0e-8
            and abs(
                firing_control["recovered_normalized_column_norm_squared"]
                - primary_firing["recovered_normalized_column_norm_squared"]
            )
            <= 1.0e-8,
        ),
    ])
    for cutoff in CUTOFFS:
        spectrum = wilson_spectra[str(cutoff)]
        expected = primary["wilson_operator_spectra"][str(cutoff)]
        checks.extend([
            check(
                f"wilson_minimum_C{cutoff}",
                spectrum["minimum"] >= -22.0 - WILSON_SPECTRUM_TOLERANCE,
                minimum=spectrum["minimum"],
            ),
            check(
                f"wilson_maximum_C{cutoff}",
                spectrum["maximum"] <= 22.0 + WILSON_SPECTRUM_TOLERANCE,
                maximum=spectrum["maximum"],
            ),
            check(
                f"wilson_minimum_match_C{cutoff}",
                abs(spectrum["minimum"] - expected["minimum"]) <= 1.0e-8,
                observed=spectrum["minimum"],
                expected=expected["minimum"],
            ),
            check(
                f"wilson_maximum_match_C{cutoff}",
                abs(spectrum["maximum"] - expected["maximum"]) <= 1.0e-8,
                observed=spectrum["maximum"],
                expected=expected["maximum"],
            ),
            check(
                f"wilson_extremal_residuals_C{cutoff}",
                max(spectrum["minimum_residual"], spectrum["maximum_residual"])
                <= WILSON_RESIDUAL_TOLERANCE,
                minimum_residual=spectrum["minimum_residual"],
                maximum_residual=spectrum["maximum_residual"],
            ),
        ])

    independent_rows = []
    for coupling in COUPLINGS:
        solved = {}
        for cutoff in CUTOFFS:
            ground, first, residual, nnz = solve(bases[cutoff], operators[cutoff], coupling)
            expected = next(row for row in primary["rows"] if row["coupling"] == coupling.numerator / coupling.denominator)["cutoffs"][str(cutoff)]
            solved[str(cutoff)] = {"ground_energy": ground, "first_excited": first, "generalized_residual": residual, "hamiltonian_nnz": nnz}
            checks.extend([
                check(f"ritz_energy_C{cutoff}_x{coupling}", abs(ground - expected["ground_energy"]) <= 1.0e-8, observed=ground, expected=expected["ground_energy"]),
                check(f"ritz_residual_C{cutoff}_x{coupling}", residual <= EIGEN_RESIDUAL_TOLERANCE, residual=residual),
                check(
                    f"ground_energy_nonnegative_C{cutoff}_x{coupling}",
                    ground >= -GROUND_ENERGY_TOLERANCE,
                    ground_energy=ground,
                ),
            ])
        b1 = shell_norm(bases[1], bases[2], operators[2], float(coupling))
        expected_row = next(row for row in primary["rows"] if row["coupling"] == coupling.numerator / coupling.denominator)
        checks.append(check(f"shell_norm_x{coupling}", abs(b1 - expected_row["b1_shell_norm"]) <= 1.0e-8, observed=b1, expected=expected_row["b1_shell_norm"]))
        independent_rows.append({"coupling": coupling.numerator / coupling.denominator, "cutoffs": solved, "b1_shell_norm": b1})

    passed = all(item["passed"] for item in checks)
    record = {
        "schema": "yang_mills_su2_larger_volume_hamiltonian_recovery_independent_v2",
        "status": "PASS" if passed else "FAIL",
        "primary_receipt": display_path(primary_path),
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "scientific_protocol": str(SCIENTIFIC_PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "primary_source": str(PRIMARY.relative_to(ROOT)).replace("\\", "/"),
        "helper": str(HELPER.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "scientific_protocol_sha256": sha256(SCIENTIFIC_PROTOCOL),
        "source_sha256": sha256(SOURCE),
        "primary_source_sha256": sha256(PRIMARY),
        "helper_sha256": sha256(HELPER),
        "basis": basis_records,
        "matrices": matrices,
        "wilson_operator_spectra": wilson_spectra,
        "spectator_channel_firing_control": firing_control,
        "rows": independent_rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "continuum_claim": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY_RECEIPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.primary, args.output)
    print(f"status={record['status']} checks={record['checks_passed']}/{record['checks_total']}")


if __name__ == "__main__":
    main()
