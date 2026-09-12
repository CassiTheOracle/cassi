#!/usr/bin/env python3
"""Exact finite-volume SU(2) Hamiltonian on the frozen 3x2x2 graph.

Protocol: ``computations/yang-mills-su2-larger-volume-hamiltonian-prereg.md``.

The program enumerates the complete gauge-invariant spin-network basis with the
fixed degree-three and degree-four coupling trees, contracts every fundamental
Wilson plaquette entry with the exact SU(2) tensor network primitives, solves
the two finite generalized Ritz problems, and evaluates the declared C=1 shell
and C=2 analytic character-tail bounds.  All results are finite-volume and
finite-cutoff results; no continuum claim is emitted.
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

Network = _exact.Network
block_diagonal = _exact.block_diagonal
cg_fusion = _exact.cg_fusion
link_integral = _exact.link_integral
metric_tensor = _exact.metric_tensor
three_j = _exact.three_j
valid_triple = _exact.valid_triple

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
SOURCE = Path(__file__).resolve()
HELPER = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian" / "verification.json"

CUTOFFS = (1, 2)
COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
MATRIX_TOLERANCE = 1.0e-10
EIGEN_RESIDUAL_TOLERANCE = 1.0e-10
NESTED_ENERGY_TOLERANCE = 1.0e-10
FORBIDDEN_SAMPLE_SIZE = 128
HASH_QUANTUM = 1.0e-15

VERTEX_COORDS = tuple(
    (x, y, z)
    for x in range(3)
    for y in range(2)
    for z in range(2)
)
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(name: str, passed: bool, **detail: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **detail}


def casimir(n2: int) -> float:
    j = n2 / 2.0
    return j * (j + 1.0)


def endpoint(vertex: int, edge: int, orientation: int) -> int:
    if orientation > 0:
        return LINK_HEADS[edge] if LINK_TAILS[edge] == vertex else -1
    return LINK_TAILS[edge] if LINK_HEADS[edge] == vertex else -1


def closed_word(word: Sequence[tuple[int, int]]) -> bool:
    if not word:
        return False
    edge, orientation = word[0]
    current = LINK_TAILS[edge] if orientation > 0 else LINK_HEADS[edge]
    for edge, orientation in word:
        next_vertex = endpoint(current, edge, orientation)
        if next_vertex < 0:
            return False
        current = next_vertex
    return current == (LINK_TAILS[word[0][0]] if word[0][1] > 0 else LINK_HEADS[word[0][0]])


def incident_legs(vertex: int) -> tuple[tuple[int, int, int], ...]:
    legs = []
    for edge, (tail, head, axis) in enumerate(zip(LINK_TAILS, LINK_HEADS, LINK_AXES)):
        if tail == vertex:
            legs.append((axis, 0, edge))
        elif head == vertex:
            legs.append((axis, 1, edge))
    return tuple((edge, +1 if outgoing == 0 else -1, axis) for axis, outgoing, edge in sorted(legs))


INCIDENT_LEGS = tuple(incident_legs(vertex) for vertex in range(len(VERTEX_COORDS)))


def _channel_options(spins: Sequence[int]) -> tuple[int, ...]:
    if len(spins) == 3:
        return (0,) if valid_triple(*spins) else ()
    if len(spins) != 4:
        raise ValueError(f"unsupported valence {len(spins)}")
    a, b, c, d = spins
    return tuple(channel for channel in range(abs(a - b), a + b + 1, 2) if valid_triple(channel, c, d))


def _state_edges(state: State) -> tuple[int, ...]:
    return state[:20]


def _state_channels(state: State) -> tuple[int, ...]:
    return state[20:]


def _channels_for_edges(edges: Sequence[int]) -> tuple[tuple[int, ...], ...]:
    values = []
    for vertex in FOUR_VALENCE_VERTICES:
        spins = tuple(edges[edge] for edge, _, _ in INCIDENT_LEGS[vertex])
        choices = _channel_options(spins)
        if not choices:
            return ()
        values.append(choices)
    return tuple(values)


def _boundary_assignments(cutoff: int, side: str) -> list[tuple[int, ...]]:
    edge_ids = LEFT_BOUNDARY_EDGES if side == "left" else RIGHT_BOUNDARY_EDGES
    boundary_vertices = (0, 1, 2, 3) if side == "left" else (8, 9, 10, 11)
    result = []
    for values in itertools.product(range(cutoff + 1), repeat=len(edge_ids)):
        edge_map = dict(zip(edge_ids, values))
        if all(
            valid_triple(*(edge_map[edge] for edge, _, _ in INCIDENT_LEGS[vertex]))
            for vertex in boundary_vertices
        ):
            result.append(tuple(int(value) for value in values))
    return result


@lru_cache(maxsize=None)
def basis_states(cutoff: int) -> tuple[State, ...]:
    left = _boundary_assignments(cutoff, "left")
    right = _boundary_assignments(cutoff, "right")
    states: list[State] = []
    for left_values in left:
        left_map = dict(zip(LEFT_BOUNDARY_EDGES, left_values))
        for right_values in right:
            right_map = dict(zip(RIGHT_BOUNDARY_EDGES, right_values))
            for middle_values in itertools.product(range(cutoff + 1), repeat=len(MIDDLE_EDGES)):
                edge_map = {**left_map, **right_map, **dict(zip(MIDDLE_EDGES, middle_values))}
                edges = tuple(edge_map[index] for index in range(20))
                channel_choices = _channels_for_edges(edges)
                if not channel_choices:
                    continue
                for channels in itertools.product(*channel_choices):
                    states.append(edges + tuple(int(value) for value in channels))
    return tuple(sorted(states))


@lru_cache(maxsize=None)
def _cg_block(n2a: int, n2b: int, n2c: int) -> np.ndarray:
    table, jblock = cg_fusion(n2a, n2b)
    positions = np.where(jblock == n2c)[0]
    if positions.size != n2c + 1:
        raise ValueError(f"missing CG block {(n2a, n2b, n2c)}")
    start = int(positions[0])
    return np.asarray(table[:, :, start:start + n2c + 1], dtype=float)


@lru_cache(maxsize=None)
def vertex_tensor(spins: tuple[int, ...], channel: int | None) -> np.ndarray:
    if len(spins) == 3:
        if channel not in (None, 0) or not valid_triple(*spins):
            raise ValueError(f"invalid trivalent tensor {spins} {channel}")
        return np.asarray(three_j(*spins), dtype=float)
    if len(spins) != 4 or channel is None:
        raise ValueError(f"invalid four-valent tensor {spins} {channel}")
    first = _cg_block(spins[0], spins[1], channel)
    second = _cg_block(channel, spins[2], spins[3])
    tensor = np.einsum("ija,akb,bl->ijkl", first, second, metric_tensor(spins[3]))
    tensor_norm = float(np.linalg.norm(tensor))
    if tensor_norm <= 0.0:
        raise ArithmeticError(f"zero four-valent tensor {spins} {channel}")
    return tensor / tensor_norm


class SpinNetworkCopy:
    def __init__(self, net: Network, state: State, prefix: str) -> None:
        self.net = net
        self.state = state
        edges = _state_edges(state)
        channels = _state_channels(state)
        self.m = {edge: net.label(f"{prefix}m{edge}", (edges[edge],)) for edge in range(20)}
        self.n = {edge: net.label(f"{prefix}n{edge}", (edges[edge],)) for edge in range(20)}
        channel_map = dict(zip(FOUR_VALENCE_VERTICES, channels))
        for vertex, legs in enumerate(INCIDENT_LEGS):
            axes = []
            spins = tuple(edges[edge] for edge, _, _ in legs)
            for edge, orientation, _ in legs:
                if orientation > 0:
                    axes.append(self.m[edge])
                else:
                    converted = net.label(f"{prefix}v{vertex}e{edge}", (edges[edge],))
                    net.add(metric_tensor(edges[edge]), (converted, self.n[edge]))
                    axes.append(converted)
            tensor = vertex_tensor(spins, channel_map.get(vertex))
            net.add(tensor, tuple(axes))

    def factors(self) -> dict[int, tuple[Any, Any]]:
        return {edge: (self.m[edge], self.n[edge]) for edge in range(20)}


def reverse_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    return tuple((edge, -orientation) for edge, orientation in reversed(word))


def plaquette_loop_factors(
    net: Network,
    word: Sequence[tuple[int, int]],
    tag: str,
    dagger: bool = False,
) -> dict[int, tuple[Any, Any, bool]]:
    loop_labels = [net.label(f"{tag}l{index}", (1,)) for index in range(4)]
    factors: dict[int, tuple[Any, Any, bool]] = {}
    for position, (edge, orientation) in enumerate(word):
        first = loop_labels[position]
        second = loop_labels[(position + 1) % 4]
        if orientation > 0:
            pair = (first, second, False)
        else:
            pair = (second, first, True)
        factors[edge] = (pair[0], pair[1], pair[2] != dagger)
    return factors


@lru_cache(maxsize=None)
def _active_link_tensor(left_spin: int, right_spin: int, conjugated: bool) -> np.ndarray:
    """Return one active-link Haar tensor in local vertex-index coordinates."""

    net = Network()
    bra_m = net.label("bm", (left_spin,))
    bra_n = net.label("bn", (left_spin,))
    ket_m = net.label("km", (right_spin,))
    ket_n = net.label("kn", (right_spin,))
    first = net.label("fa", (1,))
    second = net.label("fb", (1,))
    factor = (first, second, conjugated)
    link_integral(net, [(bra_m, bra_n, True), (ket_m, ket_n, False), factor], "active")
    raw = np.asarray(net.contract(open_axes=(bra_m, bra_n, ket_m, ket_n, first, second)))
    return np.einsum(
        "ijklmn,qj,rl->iqkrmn",
        raw,
        metric_tensor(left_spin),
        metric_tensor(right_spin),
    )


def _active_loop_labels(
    net: Network,
    word: Sequence[tuple[int, int]],
) -> dict[int, tuple[Any, Any, bool]]:
    labels = [net.label(f"loop{index}", (1,)) for index in range(4)]
    factors: dict[int, tuple[Any, Any, bool]] = {}
    for position, (edge, orientation) in enumerate(word):
        first = labels[position]
        second = labels[(position + 1) % 4]
        factors[edge] = (first, second, False) if orientation > 0 else (second, first, True)
    return factors
 
@lru_cache(maxsize=None)
def _plaquette_kernel(
    word: tuple[tuple[int, int], ...],
 ) -> tuple[str, tuple[tuple[int, tuple[int, ...], tuple[int, ...]], ...], tuple, tuple[int, ...], str, tuple]:
    """Build one small, reusable einsum kernel for a signed square."""

    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
    labels: dict[tuple[Any, ...], str] = {}

    def letter(key: tuple[Any, ...]) -> str:
        if key not in labels:
            if len(labels) >= len(alphabet):
                raise ValueError("plaquette kernel needs more than 52 axes")
            labels[key] = alphabet[len(labels)]
        return labels[key]

    active_edges = tuple(edge for edge, _ in word)
    active_set = set(active_edges)
    vertex_terms: list[str] = []
    vertex_metadata: list[tuple[int, tuple[int, ...], tuple[int, ...]]] = []
    for vertex in sorted(
        {endpoint for edge in active_edges for endpoint in (LINK_TAILS[edge], LINK_HEADS[edge])}
    ):
        legs = INCIDENT_LEGS[vertex]
        active_positions = tuple(index for index, (edge, _, _) in enumerate(legs) if edge in active_set)
        inactive_positions = tuple(index for index, (edge, _, _) in enumerate(legs) if edge not in active_set)
        if len(active_positions) != 2:
            raise ValueError(f"plaquette vertex {vertex} has {len(active_positions)} active legs")
        vertex_terms.append(
            "".join(letter(("b", vertex, legs[position][0])) for position in active_positions)
            + "".join(letter(("k", vertex, legs[position][0])) for position in active_positions)
        )
        vertex_metadata.append((vertex, active_positions, inactive_positions))

    link_terms: list[str] = []
    for position, (edge, orientation) in enumerate(word):
        first = position if orientation > 0 else (position + 1) % 4
        second = (position + 1) % 4 if orientation > 0 else position
        link_terms.append(
            "".join(
                (
                    letter(("b", LINK_TAILS[edge], edge)),
                    letter(("b", LINK_HEADS[edge], edge)),
                    letter(("k", LINK_TAILS[edge], edge)),
                    letter(("k", LINK_HEADS[edge], edge)),
                    letter(("l", first)),
                    letter(("l", second)),
                )
            )
        )

    spec = ",".join(vertex_terms + link_terms) + "->"
    dummy_shapes = [
        tuple(3 for _ in range(len(meta[1]) * 2)) for meta in vertex_metadata
    ] + [(3, 3, 3, 3, 2, 2) for _ in active_edges]
    dummy = [np.zeros(shape, dtype=float) for shape in dummy_shapes]
    path = np.einsum_path(spec, *dummy, optimize="greedy")[0]
    inputs = spec[:-2]
    batch_spec = ",".join("z" + term for term in inputs.split(",")) + "->z"
    batch_dummy = [np.zeros((1,) + shape, dtype=float) for shape in dummy_shapes]
    batch_path = np.einsum_path(batch_spec, *batch_dummy, optimize="greedy")[0]
    return spec, tuple(vertex_metadata), path, active_edges, batch_spec, batch_path


def _fast_matrix_element(
    left: State,
    right: State,
    word: Sequence[tuple[int, int]],
    dagger: bool = False,
) -> complex:
    if dagger:
        word = reverse_word(word)
    word = tuple(word)
    left_edges = _state_edges(left)
    right_edges = _state_edges(right)
    active_edges = {edge for edge, _ in word}
    if any(left_edges[edge] != right_edges[edge] for edge in range(20) if edge not in active_edges):
        return 0.0j

    spec, vertex_metadata, path, ordered_edges, _, _ = _plaquette_kernel(word)
    left_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(left)))
    right_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(right)))
    operands: list[np.ndarray] = []
    for vertex, active_positions, inactive_positions in vertex_metadata:
        legs = INCIDENT_LEGS[vertex]
        left_tensor = vertex_tensor(
            tuple(left_edges[edge] for edge, _, _ in legs),
            left_channels.get(vertex),
        )
        right_tensor = vertex_tensor(
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
        operands.append(_active_link_tensor(left_edges[edge], right_edges[edge], orientation < 0))
    local = np.einsum(spec, *operands, optimize=path)
    spectator_factor = math.prod(1.0 / (right_edges[edge] + 1.0) for edge in range(20) if edge not in active_edges)
    return complex(spectator_factor * local)

@lru_cache(maxsize=None)
def _padded_vertex_pair(
    vertex: int,
    left_spins: tuple[int, ...],
    left_channel: int | None,
    right_spins: tuple[int, ...],
    right_channel: int | None,
    active_positions: tuple[int, ...],
    inactive_positions: tuple[int, ...],
) -> np.ndarray:
    left_tensor = vertex_tensor(left_spins, left_channel)
    right_tensor = vertex_tensor(right_spins, right_channel)
    if any(left_tensor.shape[index] != right_tensor.shape[index] for index in inactive_positions):
        return np.zeros((3, 3, 3, 3), dtype=float)
    reduced = np.tensordot(left_tensor, right_tensor, axes=(inactive_positions, inactive_positions))
    shape = tuple(left_spins[index] + 1 for index in active_positions)
    shape += tuple(right_spins[index] + 1 for index in active_positions)
    padded = np.zeros((3, 3, 3, 3), dtype=float)
    padded[tuple(slice(0, size) for size in shape)] = reduced
    return padded


@lru_cache(maxsize=None)
def _padded_link_tensor(left_spin: int, right_spin: int, conjugated: bool) -> np.ndarray:
    tensor = _active_link_tensor(left_spin, right_spin, conjugated)
    padded = np.zeros((3, 3, 3, 3, 2, 2), dtype=complex)
    padded[
        :left_spin + 1,
        :left_spin + 1,
        :right_spin + 1,
        :right_spin + 1,
        :,
        :,
    ] = tensor
    return padded


def _batch_matrix_elements(
    pairs: Sequence[tuple[State, State]],
    word: Sequence[tuple[int, int]],
) -> np.ndarray:
    if not pairs:
        return np.zeros(0, dtype=complex)
    word = tuple(word)
    _, vertex_metadata, _, ordered_edges, batch_spec, batch_path = _plaquette_kernel(word)
    batch_size = len(pairs)
    vertex_batches = [
        np.zeros((batch_size, 3, 3, 3, 3), dtype=float)
        for _ in vertex_metadata
    ]
    link_batches = [
        np.zeros((batch_size, 3, 3, 3, 3, 2, 2), dtype=complex)
        for _ in ordered_edges
    ]
    spectators = np.zeros(batch_size, dtype=float)
    for batch_index, (left, right) in enumerate(pairs):
        left_edges = _state_edges(left)
        right_edges = _state_edges(right)
        active_set = set(ordered_edges)
        if any(left_edges[edge] != right_edges[edge] for edge in range(20) if edge not in active_set):
            continue
        left_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(left)))
        right_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(right)))
        for vertex_index, (vertex, active_positions, inactive_positions) in enumerate(vertex_metadata):
            legs = INCIDENT_LEGS[vertex]
            left_spins = tuple(left_edges[edge] for edge, _, _ in legs)
            right_spins = tuple(right_edges[edge] for edge, _, _ in legs)
            vertex_batches[vertex_index][batch_index] = _padded_vertex_pair(
                vertex,
                left_spins,
                left_channels.get(vertex),
                right_spins,
                right_channels.get(vertex),
                active_positions,
                inactive_positions,
            )
        for link_index, (edge, orientation) in enumerate(zip(ordered_edges, (orientation for _, orientation in word))):
            link_batches[link_index][batch_index] = _padded_link_tensor(
                left_edges[edge],
                right_edges[edge],
                orientation < 0,
            )
        spectators[batch_index] = math.prod(
            1.0 / (right_edges[edge] + 1.0)
            for edge in range(20)
            if edge not in active_set
        )
    operands = vertex_batches + link_batches
    return spectators * np.einsum(batch_spec, *operands, optimize=batch_path)

@lru_cache(maxsize=None)
def _transfer_metadata(
    word: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int, int, int, int, tuple[int, ...], tuple[int, ...], int], ...]:
    current = LINK_TAILS[word[0][0]] if word[0][1] > 0 else LINK_HEADS[word[0][0]]
    metadata = []
    for position, (edge, orientation) in enumerate(word):
        next_vertex = endpoint(current, edge, orientation)
        if next_vertex < 0:
            raise ValueError(f"non-closing word at position {position}: {word}")
        legs = INCIDENT_LEGS[current]
        incoming_edge = word[position - 1][0]
        incoming_position = next(index for index, (candidate, _, _) in enumerate(legs) if candidate == incoming_edge)
        outgoing_position = next(index for index, (candidate, _, _) in enumerate(legs) if candidate == edge)
        active_positions = tuple(index for index, (candidate, _, _) in enumerate(legs) if candidate in {incoming_edge, edge})
        inactive_positions = tuple(index for index, (candidate, _, _) in enumerate(legs) if candidate not in {incoming_edge, edge})
        metadata.append(
            (
                current,
                incoming_edge,
                edge,
                incoming_position,
                outgoing_position,
                active_positions,
                inactive_positions,
                orientation,
            )
        )
        current = next_vertex
    return tuple(metadata)


@lru_cache(maxsize=None)
def _padded_transfer(
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
    outgoing_left_spin: int,
    outgoing_right_spin: int,
    orientation: int,
) -> np.ndarray:
    reduced = _padded_vertex_pair(
        vertex,
        left_spins,
        left_channel,
        right_spins,
        right_channel,
        active_positions,
        inactive_positions,
    )
    incoming_index = active_positions.index(incoming_position)
    outgoing_index = active_positions.index(outgoing_position)
    permutation = (
        incoming_index,
        outgoing_index,
        len(active_positions) + incoming_index,
        len(active_positions) + outgoing_index,
    )
    vertex_tensor_ordered = np.transpose(reduced, permutation)
    link_tensor = _padded_link_tensor(outgoing_left_spin, outgoing_right_spin, orientation < 0)
    if orientation < 0:
        link_tensor = np.transpose(link_tensor, (1, 0, 3, 2, 5, 4))
    transfer = np.einsum(
        "abcd,bedfgh->acgefh",
        vertex_tensor_ordered,
        link_tensor,
        optimize=True,
    )
    return transfer.reshape(18, 18)


_TRANSFER_BATCH_SPEC = "bij,bjk,bkl,bli->b"
_TRANSFER_BATCH_PATH = np.einsum_path(
    _TRANSFER_BATCH_SPEC,
    np.zeros((1, 18, 18)),
    np.zeros((1, 18, 18)),
    np.zeros((1, 18, 18)),
    np.zeros((1, 18, 18)),
    optimize="greedy",
)[0]


def _batch_transfer_matrix_elements(
    pairs: Sequence[tuple[State, State]],
    word: Sequence[tuple[int, int]],
) -> np.ndarray:
    if not pairs:
        return np.zeros(0, dtype=complex)
    word = tuple(word)
    metadata = _transfer_metadata(word)
    batch_size = len(pairs)
    transfers = [np.zeros((batch_size, 18, 18), dtype=complex) for _ in metadata]
    spectators = np.zeros(batch_size, dtype=float)
    active_set = {edge for edge, _ in word}
    for batch_index, (left, right) in enumerate(pairs):
        left_edges = _state_edges(left)
        right_edges = _state_edges(right)
        if any(left_edges[edge] != right_edges[edge] for edge in range(20) if edge not in active_set):
            continue
        left_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(left)))
        right_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(right)))
        for transfer_index, (
            vertex,
            incoming_edge,
            outgoing_edge,
            incoming_position,
            outgoing_position,
            active_positions,
            inactive_positions,
            orientation,
        ) in enumerate(metadata):
            legs = INCIDENT_LEGS[vertex]
            left_spins = tuple(left_edges[edge] for edge, _, _ in legs)
            right_spins = tuple(right_edges[edge] for edge, _, _ in legs)
            transfers[transfer_index][batch_index] = _padded_transfer(
                vertex,
                incoming_edge,
                outgoing_edge,
                incoming_position,
                outgoing_position,
                active_positions,
                inactive_positions,
                left_spins,
                left_channels.get(vertex),
                right_spins,
                right_channels.get(vertex),
                left_edges[outgoing_edge],
                right_edges[outgoing_edge],
                orientation,
            )
        spectators[batch_index] = math.prod(
            1.0 / (right_edges[edge] + 1.0)
            for edge in range(20)
            if edge not in active_set
        )
    local = np.einsum(_TRANSFER_BATCH_SPEC, *transfers, optimize=_TRANSFER_BATCH_PATH)
    return spectators * local


def matrix_element(left: State, right: State, word: Sequence[tuple[int, int]], dagger: bool = False) -> complex:
    return _fast_matrix_element(left, right, word, dagger=dagger)



def direct_local_matrix_element(left: State, right: State, word: Sequence[tuple[int, int]]) -> complex:
    """Exact-link oracle after reducing spectator vertices."""

    left_edges = _state_edges(left)
    right_edges = _state_edges(right)
    active_edges = {edge for edge, _ in word}
    net = Network()
    loop_factors = _active_loop_labels(net, word)
    bra_axes: dict[tuple[int, int], Any] = {}
    ket_axes: dict[tuple[int, int], Any] = {}
    left_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(left)))
    right_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(right)))
    active_vertices = {vertex for edge in active_edges for vertex in (LINK_TAILS[edge], LINK_HEADS[edge])}
    for vertex in sorted(active_vertices):
        legs = INCIDENT_LEGS[vertex]
        active_positions = [i for i, (edge, _, _) in enumerate(legs) if edge in active_edges]
        inactive_positions = [i for i, (edge, _, _) in enumerate(legs) if edge not in active_edges]
        left_tensor = vertex_tensor(tuple(left_edges[e] for e, _, _ in legs), left_channels.get(vertex))
        right_tensor = vertex_tensor(tuple(right_edges[e] for e, _, _ in legs), right_channels.get(vertex))
        reduced = np.tensordot(left_tensor, right_tensor, axes=(inactive_positions, inactive_positions))
        bra_labels = []
        ket_labels = []
        for position in active_positions:
            edge = legs[position][0]
            bra_axis = net.label(f"db{vertex}e{edge}", (left_edges[edge],))
            ket_axis = net.label(f"dk{vertex}e{edge}", (right_edges[edge],))
            bra_axes[(vertex, edge)] = bra_axis
            ket_axes[(vertex, edge)] = ket_axis
            bra_labels.append(bra_axis)
            ket_labels.append(ket_axis)
        net.add(reduced, tuple(bra_labels + ket_labels))
    for edge, factor in loop_factors.items():
        bra_n = net.label(f"dbn{edge}", (left_edges[edge],))
        ket_n = net.label(f"dkn{edge}", (right_edges[edge],))
        net.add(metric_tensor(left_edges[edge]), (bra_axes[(LINK_HEADS[edge], edge)], bra_n))
        net.add(metric_tensor(right_edges[edge]), (ket_axes[(LINK_HEADS[edge], edge)], ket_n))
        link_integral(
            net,
            [
                (bra_axes[(LINK_TAILS[edge], edge)], bra_n, True),
                (ket_axes[(LINK_TAILS[edge], edge)], ket_n, False),
                factor,
            ],
            f"direct{edge}",
        )
    spectator_factor = math.prod(1.0 / (right_edges[edge] + 1.0) for edge in range(20) if edge not in active_edges)
    return complex(spectator_factor * net.contract())


def overlap_element(left: State, right: State) -> complex:
    left_edges = _state_edges(left)
    right_edges = _state_edges(right)
    if left_edges != right_edges:
        return 0.0j
    left_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(left)))
    right_channels = dict(zip(FOUR_VALENCE_VERTICES, _state_channels(right)))
    value = 1.0
    for vertex, legs in enumerate(INCIDENT_LEGS):
        spins = tuple(left_edges[edge] for edge, _, _ in legs)
        value *= float(np.vdot(vertex_tensor(spins, left_channels.get(vertex)), vertex_tensor(spins, right_channels.get(vertex))).real)
    value *= math.prod(1.0 / (spin + 1.0) for spin in left_edges)
    return complex(value)


def candidate_states(
    right: State,
    word: Sequence[tuple[int, int]],
    cutoff: int,
    index_by_edges: dict[tuple[int, ...], tuple[State, ...]],
) -> tuple[State, ...]:
    edges = list(_state_edges(right))
    targets: set[State] = set()
    link_ids = tuple(edge for edge, _ in word)
    for signs in itertools.product((-1, +1), repeat=4):
        target = edges[:]
        for edge, sign in zip(link_ids, signs):
            target[edge] += sign
        if any(value < 0 or value > cutoff for value in target):
            continue
        for state in index_by_edges.get(tuple(target), ()):


            targets.add(state)
    return tuple(sorted(targets))


def matrix_hash(matrix: csr_matrix) -> str:
    """Hash the finalized CSR matrix after 1e-15 canonical quantization."""
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

def _indexed_edge_groups(states: Sequence[State]) -> tuple[dict[tuple[int, ...], np.ndarray], np.ndarray, np.ndarray]:
    edge_groups: dict[tuple[int, ...], list[int]] = {}
    edge_array = np.asarray([state[:20] for state in states], dtype=np.int8)
    channel_array = np.asarray([state[20:] for state in states], dtype=np.int8)
    for index, state in enumerate(states):
        edge_groups.setdefault(_state_edges(state), []).append(index)
    return (
        {edges: np.asarray(indices, dtype=np.int32) for edges, indices in edge_groups.items()},
        edge_array,
        channel_array,
    )


def _transition_tables(
    states: Sequence[State],
    word: Sequence[tuple[int, int]],
    edge_array: np.ndarray,
    channel_array: np.ndarray,
) -> tuple[list[np.ndarray], list[np.ndarray], list[np.ndarray], tuple[tuple[Any, ...], ...]]:
    metadata = _transfer_metadata(tuple(word))
    descriptor_ids: list[np.ndarray] = []
    descriptor_records: list[tuple[tuple[tuple[int, ...], int | None, int], ...]] = []
    for vertex, _, outgoing_edge, _, _, _, _, _ in metadata:
        legs = INCIDENT_LEGS[vertex]
        records: list[tuple[tuple[int, ...], int | None, int]] = []
        record_index: dict[tuple[tuple[int, ...], int | None, int], int] = {}
        ids = np.empty(len(states), dtype=np.int16)
        for state_index in range(len(states)):
            spins = tuple(int(edge_array[state_index, edge]) for edge, _, _ in legs)
            channel = int(channel_array[state_index, vertex - FOUR_VALENCE_VERTICES[0]]) if vertex in FOUR_VALENCE_VERTICES else None
            key = (spins, channel, int(edge_array[state_index, outgoing_edge]))
            identifier = record_index.get(key)
            if identifier is None:
                identifier = len(records)
                record_index[key] = identifier
                records.append(key)
            ids[state_index] = identifier
        descriptor_ids.append(ids)
        descriptor_records.append(tuple(records))

    pair_maps: list[np.ndarray] = []
    transfer_matrices: list[np.ndarray] = []
    for position, (
        vertex,
        incoming_edge,
        outgoing_edge,
        incoming_position,
        outgoing_position,
        active_positions,
        inactive_positions,
        orientation,
    ) in enumerate(metadata):
        records = descriptor_records[position]
        pair_map = np.empty((len(records), len(records)), dtype=np.int16)
        matrices: list[np.ndarray] = []
        for left_index, (left_spins, left_channel, left_outgoing_spin) in enumerate(records):
            for right_index, (right_spins, right_channel, right_outgoing_spin) in enumerate(records):
                pair_map[left_index, right_index] = len(matrices)
                matrices.append(
                    _padded_transfer(
                        vertex,
                        incoming_edge,
                        outgoing_edge,
                        incoming_position,
                        outgoing_position,
                        active_positions,
                        inactive_positions,
                        left_spins,
                        left_channel,
                        right_spins,
                        right_channel,
                        left_outgoing_spin,
                        right_outgoing_spin,
                        orientation,
                    )
                )
        pair_maps.append(pair_map)
        transfer_matrices.append(np.asarray(matrices, dtype=complex))
    return descriptor_ids, pair_maps, transfer_matrices, metadata


def _transition_values(
    rows: np.ndarray,
    columns: np.ndarray,
    descriptor_ids: Sequence[np.ndarray],
    pair_maps: Sequence[np.ndarray],
    transfer_matrices: Sequence[np.ndarray],
) -> np.ndarray:
    pair_ids = [
        pair_maps[position][descriptor_ids[position][rows], descriptor_ids[position][columns]]
        for position in range(4)
    ]
    encoded = pair_ids[0].astype(np.int64)
    radices = [matrices.shape[0] for matrices in transfer_matrices]
    for position in range(1, 4):
        encoded = encoded * radices[position] + pair_ids[position]
    unique, inverse = np.unique(encoded, return_inverse=True)
    remaining = unique.copy()
    identifiers = []
    for radix in reversed(radices):
        identifiers.append(remaining % radix)
        remaining //= radix
    identifiers.reverse()
    local_values = np.einsum(
        _TRANSFER_BATCH_SPEC,
        *[
            transfer_matrices[position][identifiers[position]]
            for position in range(4)
        ],
        optimize=_TRANSFER_BATCH_PATH,
    )
    return local_values[inverse]


def _candidate_edge_targets(
    edges: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    edge_groups: dict[tuple[int, ...], np.ndarray],
    cutoff: int,
) -> np.ndarray:
    targets: list[np.ndarray] = []
    link_ids = tuple(edge for edge, _ in word)
    for signs in itertools.product((-1, +1), repeat=4):
        target = list(edges)
        for edge, sign in zip(link_ids, signs):
            target[edge] += sign
        if any(value < 0 or value > cutoff for value in target):
            continue
        group = edge_groups.get(tuple(target))
        if group is not None:
            targets.append(group)
    return np.concatenate(targets) if targets else np.zeros(0, dtype=np.int32)


def _assemble_plaquette(
    states: Sequence[State],
    word: Sequence[tuple[int, int]],
    cutoff: int,
    chunk_size: int = 262144,
) -> tuple[csr_matrix, int, int, str, float]:
    edge_groups, edge_array, channel_array = _indexed_edge_groups(states)
    descriptor_ids, pair_maps, transfer_matrices, _ = _transition_tables(
        states,
        word,
        edge_array,
        channel_array,
    )
    active_edges = {edge for edge, _ in word}
    spectators = np.ones(len(states), dtype=float)
    for edge in range(20):
        if edge not in active_edges:
            spectators /= edge_array[:, edge] + 1.0
    target_groups = {
        edges: _candidate_edge_targets(edges, word, edge_groups, cutoff)
        for edges in edge_groups
    }
    candidate_count = sum(
        len(columns) * len(target_groups[edges])
        for edges, columns in edge_groups.items()
    )
    rows_out = np.empty(candidate_count, dtype=np.int32)
    columns_out = np.empty(candidate_count, dtype=np.int32)
    values_out = np.empty(candidate_count, dtype=complex)
    cursor = 0
    pending_rows: list[np.ndarray] = []
    pending_columns: list[np.ndarray] = []
    pending_count = 0

    def flush() -> None:
        nonlocal cursor, pending_count
        if not pending_rows:
            return
        rows = np.concatenate(pending_rows)
        columns = np.concatenate(pending_columns)
        values = _transition_values(rows, columns, descriptor_ids, pair_maps, transfer_matrices)
        values *= spectators[columns]
        size = rows.size
        rows_out[cursor:cursor + size] = rows
        columns_out[cursor:cursor + size] = columns
        values_out[cursor:cursor + size] = values
        cursor += size
        pending_rows.clear()
        pending_columns.clear()
        pending_count = 0

    for edges, columns in edge_groups.items():
        target_rows = target_groups[edges]
        if target_rows.size == 0:
            continue
        pending_rows.append(np.tile(target_rows, columns.size))
        pending_columns.append(np.repeat(columns, target_rows.size))
        pending_count += columns.size * target_rows.size
        if pending_count >= chunk_size:
            flush()
    flush()
    if cursor != candidate_count:
        raise RuntimeError(f"candidate assembly wrote {cursor} of {candidate_count} entries")

    order = np.lexsort((columns_out, rows_out))
    matrix = csr_matrix(
        (values_out, (rows_out, columns_out)),
        shape=(len(states), len(states)),
    )
    matrix.sum_duplicates()
    matrix.sort_indices()
    difference = matrix - matrix.T.conjugate()
    hermiticity = float(np.max(np.abs(difference.data))) if difference.nnz else 0.0
    nonzero = int(np.count_nonzero(np.abs(values_out) > MATRIX_TOLERANCE))
    finite = bool(np.isfinite(values_out.real).all() and np.isfinite(values_out.imag).all())
    return matrix, candidate_count, nonzero, matrix_hash(matrix), hermiticity


def evaluate_plaquette(
    states: Sequence[State],
    index: dict[State, int],
    index_by_edges: dict[tuple[int, ...], tuple[State, ...]],
    word: Sequence[tuple[int, int]],
    cutoff: int,
) -> dict[str, Any]:
    del index, index_by_edges
    word = tuple(word)
    matrix, candidate_count, nonzero, matrix_digest, hermiticity = _assemble_plaquette(states, word, cutoff)
    reverse = reverse_word(word)
    edge_groups, _, _ = _indexed_edge_groups(states)
    reverse_count = sum(
        len(columns) * len(_candidate_edge_targets(edges, reverse, edge_groups, cutoff))
        for edges, columns in edge_groups.items()
    )
    candidate_sample = sorted(zip(*matrix.nonzero()))[: min(64, matrix.nnz)]
    dagger_residual = max(
        (
            abs(
                matrix_element(states[row], states[column], reverse)
                - np.conj(matrix[column, row])
            )
            for row, column in candidate_sample
        ),
        default=0.0,
    )
    active_edges = {edge for edge, _ in word}
    forbidden: list[tuple[int, int]] = []
    for column in range(min(len(states), 256)):
        right_edges = _state_edges(states[column])
        for row in range(min(len(states), 256)):
            left_edges = _state_edges(states[row])
            if any(left_edges[edge] != right_edges[edge] for edge in range(20) if edge not in active_edges):
                forbidden.append((row, column))
                if len(forbidden) >= FORBIDDEN_SAMPLE_SIZE:
                    break
        if len(forbidden) >= FORBIDDEN_SAMPLE_SIZE:
            break
    forbidden_values = [matrix_element(states[row], states[column], word) for row, column in forbidden]
    forbidden_max = max((abs(value) for value in forbidden_values), default=0.0)
    return {
        "name": PLAQUETTE_NAMES[PLAQUETTES.index(word)],
        "word": [[edge, sign] for edge, sign in word],
        "dagger_word": [[edge, sign] for edge, sign in reverse],
        "candidate_entries": candidate_count,
        "nonzero_entries": nonzero,
        "forbidden_entries": len(states) * len(states) - candidate_count,
        "forbidden_sample_count": len(forbidden),
        "forbidden_sample_zero": forbidden_max <= MATRIX_TOLERANCE,
        "maximum_forbidden_sample_magnitude": float(forbidden_max),
        "finite": bool(np.isfinite(matrix.data.real).all() and np.isfinite(matrix.data.imag).all()),
        "maximum_hermiticity_residual": hermiticity,
        "reverse_support_matches": reverse_count == candidate_count,
        "maximum_dagger_residual": float(dagger_residual),
        "matrix_hash": matrix_digest,
        "matrix": matrix,
    }

def sparse_from_row(row: dict[str, Any], dimension: int) -> csr_matrix:
    if "matrix" in row:
        return row["matrix"]
    data = np.asarray([complex(real, imag) for real, imag in row["values"]], dtype=complex)
    return csr_matrix((data, (row["rows"], row["columns"])), shape=(dimension, dimension))


def state_norm(state: State) -> float:
    return float(np.prod([1.0 / (state[edge] + 1.0) for edge in range(20)]))


def state_energy(state: State) -> float:
    return float(sum(casimir(state[edge]) for edge in range(20)))


def basis_hash(states: Sequence[State]) -> str:
    return hashlib.sha256(json.dumps(states, separators=(",", ":")).encode("utf-8")).hexdigest()


def selected_overlap_checks(states: Sequence[State]) -> list[dict[str, Any]]:
    if not states:
        return []
    candidates = [0, len(states) - 1, len(states) // 2]
    multiplicity = next((index for index, state in enumerate(states) if any(state[20:])), 0)
    candidates.append(multiplicity)
    selected = sorted(set(candidates))
    values = []
    for row in selected:
        for column in selected:
            observed = overlap_element(states[row], states[column])
            expected = state_norm(states[row]) if row == column else 0.0
            values.append({"row": row, "column": column, "observed": [observed.real, observed.imag], "expected": expected, "residual": abs(observed - expected)})
    return values


def solve_ritz(
    states: Sequence[State],
    plaquette_rows: Sequence[dict[str, Any]],
    coupling: Fraction,
    operator: csr_matrix | None = None,
) -> dict[str, Any]:
    dimension = len(states)
    W = operator if operator is not None else sum(
        (sparse_from_row(row, dimension) for row in plaquette_rows),
        csr_matrix((dimension, dimension), dtype=complex),
    )
    nu = np.asarray([state_norm(state) for state in states], dtype=float)
    kinetic = np.asarray([state_energy(state) for state in states], dtype=float)
    x = float(coupling)
    diagonal = (kinetic + 22.0 * x) * nu
    H = csr_matrix((diagonal, (np.arange(dimension), np.arange(dimension))), shape=(dimension, dimension)) - x * W
    scale = 1.0 / np.sqrt(nu)
    A = H.multiply(scale[:, None]).multiply(scale[None, :]).tocsr()
    asymmetry = A - A.T.conjugate()
    symmetry_residual = float(np.max(np.abs(asymmetry.data))) if asymmetry.nnz else 0.0
    A = (0.5 * (A + A.T.conjugate())).tocsr()
    if dimension <= 3:
        values, vectors = np.linalg.eigh(A.toarray())
    else:
        values, vectors = eigsh(A, k=min(2, dimension - 1), which="SA", tol=1.0e-12, maxiter=max(1000, dimension * 20))
        order = np.argsort(values)
        values, vectors = values[order], vectors[:, order]
    q_complex = np.asarray(vectors[:, 0], dtype=complex)
    pivot = int(np.argmax(np.abs(q_complex)))
    pivot_value = q_complex[pivot]
    if abs(pivot_value) > 0.0:
        q_complex = q_complex * (np.conjugate(pivot_value) / abs(pivot_value))
    if np.max(np.abs(q_complex.imag)) > EIGEN_RESIDUAL_TOLERANCE:
        raise ArithmeticError("Ritz ground vector has a non-negligible imaginary component after phase fixing")
    complex_residual = A @ q_complex - values[0] * q_complex
    if np.linalg.norm(complex_residual) > EIGEN_RESIDUAL_TOLERANCE:
        raise ArithmeticError("Ritz ground vector residual exceeds tolerance after phase fixing")
    q = np.asarray(q_complex.real, dtype=float)
    alpha = q / np.sqrt(nu)
    phase_index = next((index for index, value in enumerate(alpha) if abs(value) > 1.0e-14), 0)
    if alpha[phase_index] < 0:
        alpha = -alpha
        q = -q
    residual = A @ q - values[0] * q
    return {
        "coupling": coupling.numerator / coupling.denominator,
        "ground_energy": float(values[0]),
        "first_excited": float(values[1]) if len(values) > 1 else None,
        "ritz_gap": float(values[1] - values[0]) if len(values) > 1 else None,
        "generalized_residual": float(np.linalg.norm(residual)),
        "matrix_symmetry_residual_before_cleaning": symmetry_residual,
        "coefficients": [float(value) for value in alpha],
        "physical_vector": [float(value) for value in q],
        "kinetic_min": float(np.min(kinetic)),
        "dimension": dimension,
        "hamiltonian_nnz": int(H.nnz),
    }


def cross_shell_norm(
    states_one: Sequence[State],
    states_two: Sequence[State],
    rows: Sequence[dict[str, Any]],
    coupling: Fraction,
    operator: csr_matrix | None = None,
) -> float:
    index_two = {state: index for index, state in enumerate(states_two)}
    retained_indices = np.asarray([index_two[state] for state in states_one], dtype=np.int32)
    shell_mask = np.ones(len(states_two), dtype=bool)
    shell_mask[retained_indices] = False
    shell_indices = np.flatnonzero(shell_mask)
    if shell_indices.size == 0:
        return 0.0
    dimension = len(states_two)
    W = operator if operator is not None else sum(
        (sparse_from_row(row, dimension) for row in rows),
        csr_matrix((dimension, dimension), dtype=complex),
    )
    block = W[shell_indices, :][:, retained_indices].tocsr()
    nu_shell = np.asarray([state_norm(states_two[index]) for index in shell_indices], dtype=float)
    nu_one = np.asarray([state_norm(state) for state in states_one], dtype=float)
    physical = block.multiply((float(coupling) / np.sqrt(nu_shell))[:, None])
    physical = physical.multiply((1.0 / np.sqrt(nu_one))[None, :])
    gram = (physical.T.conjugate() @ physical).toarray()
    largest = float(np.max(np.linalg.eigvalsh(gram))) if gram.size else 0.0
    return math.sqrt(max(0.0, largest))


def run(output: Path) -> dict[str, Any]:
    closure = [closed_word(word) for word in PLAQUETTES]
    if not all(closure):
        raise ArithmeticError(f"non-closing plaquette word: {closure}")
    bases: dict[int, tuple[State, ...]] = {cutoff: basis_states(cutoff) for cutoff in CUTOFFS}
    basis_records = {}
    for cutoff, states in bases.items():
        overlaps = selected_overlap_checks(states)
        basis_records[str(cutoff)] = {
            "dimension": len(states),
            "states": [list(state) for state in states],
            "state_sha256": basis_hash(states),
            "overlap_checks": overlaps,
            "overlap_checks_pass": all(item["residual"] <= MATRIX_TOLERANCE for item in overlaps),
        }
    matrices: dict[int, list[dict[str, Any]]] = {}
    operators: dict[int, csr_matrix] = {}
    for cutoff, states in bases.items():
        records: list[dict[str, Any]] = []
        operator = csr_matrix((len(states), len(states)), dtype=complex)
        for word in PLAQUETTES:
            evaluated = evaluate_plaquette(states, {}, {}, word, cutoff)
            plaquette_matrix = evaluated.pop("matrix")
            operator = (operator + plaquette_matrix).tocsr()
            records.append(evaluated)
            del plaquette_matrix
        operator.sum_duplicates()
        operator.sort_indices()
        matrices[cutoff] = records
        operators[cutoff] = operator
    rows: list[dict[str, Any]] = []
    nested: dict[str, Any] = {}
    for coupling in COUPLINGS:
        key = str(coupling)
        solved = {}
        for cutoff in CUTOFFS:
            solved[str(cutoff)] = solve_ritz(
                bases[cutoff],
                matrices[cutoff],
                coupling,
                operator=operators[cutoff],
            )
        e1 = solved["1"]["ground_energy"]
        e2 = solved["2"]["ground_energy"]
        nested[key] = {"E1": e1, "E2": e2, "difference": e2 - e1, "nonincreasing": e2 <= e1 + NESTED_ENERGY_TOLERANCE}
        for cutoff in CUTOFFS:
            solved[str(cutoff)]["tail"] = {
                "kappa": (cutoff + 1) * (cutoff + 3) / 4.0,
                "separation": (cutoff + 1) * (cutoff + 3) / 4.0 - solved[str(cutoff)]["ground_energy"],
            }
        b1 = cross_shell_norm(
            bases[1],
            bases[2],
            matrices[2],
            coupling,
            operator=operators[2],
        )
        for cutoff in CUTOFFS:
            separation = solved[str(cutoff)]["tail"]["separation"]
            bound = b1 if cutoff == 1 else 22.0 * float(coupling)
            status = "TAIL_UNRESOLVED" if separation <= 0 else ("TAIL_CERTIFIED_EXACT_SHELL" if cutoff == 1 else "TAIL_CERTIFIED_ANALYTIC")
            if separation > 0 and bound / separation >= 0.1:
                status = status + ":COARSE"
            solved[str(cutoff)]["tail"].update({"coupling_bound": bound, "ratio": min(1.0, bound / separation) if separation > 0 else None, "status": status})
        rows.append({"coupling": coupling.numerator / coupling.denominator, "cutoffs": solved, "nested_energy": nested[key], "b1_shell_norm": b1})
    oracle_edges, _, _ = _indexed_edge_groups(bases[1])
    oracle_right = next(
        state for state in bases[1] if all(value == 0 for value in _state_edges(state))
    )
    oracle_targets = _candidate_edge_targets(
        _state_edges(oracle_right),
        PLAQUETTES[0],
        oracle_edges,
        1,
    )
    oracle_left = bases[1][int(oracle_targets[0])]
    oracle_residual = abs(
        matrix_element(oracle_left, oracle_right, PLAQUETTES[0])
        - direct_local_matrix_element(oracle_left, oracle_right, PLAQUETTES[0])
    )
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.exists()),
        check("source_path", SOURCE.relative_to(ROOT).as_posix() == "computations/verify_yang_mills_su2_larger_volume_hamiltonian.py"),
        check("helper_path", HELPER.exists()),
        check("graph_vertex_count", len(VERTEX_COORDS) == 12),
        check("graph_link_count", len(LINK_TAILS) == 20 and len(LINK_HEADS) == 20),
        check("plaquette_count", len(PLAQUETTES) == 11),
        check("all_words_close", all(closure), closure=closure),
        check("nested_basis", set(bases[1]).issubset(set(bases[2]))),
        check("local_exact_oracle_C1", oracle_residual <= MATRIX_TOLERANCE, residual=oracle_residual),
    ]
    for cutoff, states in bases.items():
        checks.append(check(f"basis_nonempty_C{cutoff}", bool(states), dimension=len(states)))
        checks.append(check(f"overlap_controls_C{cutoff}", basis_records[str(cutoff)]["overlap_checks_pass"], controls=basis_records[str(cutoff)]["overlap_checks"]))
        for matrix in matrices[cutoff]:
            checks.extend([
                check(f"finite_C{cutoff}_{matrix['name']}", matrix["finite"]),
                check(f"support_C{cutoff}_{matrix['name']}", matrix["reverse_support_matches"]),
                check(f"hermitian_C{cutoff}_{matrix['name']}", matrix["maximum_hermiticity_residual"] <= MATRIX_TOLERANCE, residual=matrix["maximum_hermiticity_residual"]),
                check(f"dagger_C{cutoff}_{matrix['name']}", matrix["maximum_dagger_residual"] <= MATRIX_TOLERANCE, residual=matrix["maximum_dagger_residual"]),
                check(f"forbidden_C{cutoff}_{matrix['name']}", matrix["forbidden_sample_zero"], maximum=matrix["maximum_forbidden_sample_magnitude"]),
            ])
    for row in rows:
        for cutoff in CUTOFFS:
            solved = row["cutoffs"][str(cutoff)]
            checks.extend([
                check(f"ritz_residual_C{cutoff}_x{row['coupling']}", solved["generalized_residual"] <= EIGEN_RESIDUAL_TOLERANCE, residual=solved["generalized_residual"]),
                check(f"ritz_gap_C{cutoff}_x{row['coupling']}", solved["ritz_gap"] is None or solved["ritz_gap"] >= -MATRIX_TOLERANCE, gap=solved["ritz_gap"]),
                check(f"tail_separation_C{cutoff}_x{row['coupling']}", solved["tail"]["separation"] > 0, separation=solved["tail"]["separation"]),
            ])
        checks.append(check(f"nested_energy_x{row['coupling']}", row["nested_energy"]["nonincreasing"], difference=row["nested_energy"]["difference"]))
    finite_checks = [
        item for item in checks
        if not item["name"].startswith(("tail_separation_", "nested_energy_"))
    ]
    cutoff_checks = [item for item in checks if item["name"].startswith("nested_energy_")]
    finite_pass = all(item["passed"] for item in finite_checks)
    cutoff_energy_pass = all(item["passed"] for item in cutoff_checks)
    tail_rows = [
        item for row in rows for item in row["cutoffs"].values()
        if item["tail"]["status"].startswith("TAIL_CERTIFIED")
        and item["tail"]["ratio"] is not None
        and item["tail"]["ratio"] <= 0.1
    ]
    tail_status_c1 = {str(row["coupling"]): row["cutoffs"]["1"]["tail"]["status"] for row in rows}
    tail_status_c2 = {str(row["coupling"]): row["cutoffs"]["2"]["tail"]["status"] for row in rows}
    cutoff_qualifications = {}
    for row in rows:
        useful = all(
            row["cutoffs"][str(cutoff)]["tail"]["status"].startswith("TAIL_CERTIFIED")
            and row["cutoffs"][str(cutoff)]["tail"]["ratio"] is not None
            and row["cutoffs"][str(cutoff)]["tail"]["ratio"] <= 0.1
            for cutoff in CUTOFFS
        )
        cutoff_qualifications[str(row["coupling"])] = (
            "SUPPORTS_FINITE_VOLUME_CUTOFF_TAIL_CONTROL"
            if finite_pass and row["nested_energy"]["nonincreasing"] and useful
            else "INCONCLUSIVE"
        )
    classification = (
        "FAIL"
        if not finite_pass
        else "SUPPORTS_FINITE_VOLUME_CUTOFF_TAIL_CONTROL"
        if all(value == "SUPPORTS_FINITE_VOLUME_CUTOFF_TAIL_CONTROL" for value in cutoff_qualifications.values())
        else "PASS_FINITE_CONSTRUCTION"
    )
    record: dict[str, Any] = {
        "schema": "yang_mills_su2_larger_volume_hamiltonian_v1",
        "status": "PASS" if finite_pass else "FAIL",
        "classification": classification,
        "protocol": str(PROTOCOL.relative_to(ROOT)).replace("\\", "/"),
        "source": str(SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "helper": str(HELPER.relative_to(ROOT)).replace("\\", "/"),
        "protocol_sha256": sha256(PROTOCOL),
        "source_sha256": sha256(SOURCE),
        "helper_sha256": sha256(HELPER),
        "cutoffs": list(CUTOFFS),
        "couplings": [value.numerator / value.denominator for value in COUPLINGS],
        "vertices": [list(coord) for coord in VERTEX_COORDS],
        "tails": list(LINK_TAILS),
        "heads": list(LINK_HEADS),
        "axes": list(LINK_AXES),
        "plaquettes": [{"name": name, "word": [[edge, sign] for edge, sign in word]} for name, word in zip(PLAQUETTE_NAMES, PLAQUETTES)],
        "basis": basis_records,
        "matrices": {str(cutoff): matrices[cutoff] for cutoff in CUTOFFS},
        "rows": rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "finite_checks_passed": sum(item["passed"] for item in finite_checks),
        "finite_checks_total": len(finite_checks),
        "cutoff_checks_passed": sum(item["passed"] for item in cutoff_checks),
        "cutoff_checks_total": len(cutoff_checks),
        "finite_construction": "PASS" if finite_pass else "FAIL",
        "cutoff_energy_comparison": "PASS" if cutoff_energy_pass else "INCONCLUSIVE",
        "cutoff_qualifications": cutoff_qualifications,
        "tail_status_C1": tail_status_c1,
        "tail_status_C2": tail_status_c2,
        "useful_tail_rows": len(tail_rows),
        "continuum_claim": False,
        "scope": "finite open 3x2x2 SU(2) gauge-invariant character Hamiltonian with C=1,2",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']}"
    )
    for row in record["rows"]:
        print(
            f"x={row['coupling']} dim_C1={row['cutoffs']['1']['dimension']} "
            f"dim_C2={row['cutoffs']['2']['dimension']} "
            f"E1={row['cutoffs']['1']['ground_energy']:.12g} "
            f"E2={row['cutoffs']['2']['ground_energy']:.12g}"
        )


if __name__ == "__main__":
    main()
