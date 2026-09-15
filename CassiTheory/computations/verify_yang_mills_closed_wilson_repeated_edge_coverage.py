#!/usr/bin/env python3
"""Measure the finite closed-Wilson family with repeated-edge words.

The retained simple-cycle assembler supplies the 225 simple classes. This source
adds the 55 length-eight cyclically reduced classes with repeated edge or vertex
support using a full exact link-Haar tensor network. The result is finite-volume,
finite-cutoff evidence only.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from fractions import Fraction
import importlib
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import computations.verify_yang_mills_closed_wilson_simple_cycle_coverage as simple

large = simple.load_large_source()

PROTOCOL = ROOT / "computations" / "yang-mills-closed-wilson-repeated-edge-coverage-prereg.md"
SOURCE = Path(__file__).resolve()
INDEPENDENT_SOURCE = ROOT / "computations" / "verify_yang_mills_closed_wilson_repeated_edge_coverage_independent.py"
SIMPLE_SOURCE = ROOT / "computations" / "verify_yang_mills_closed_wilson_simple_cycle_coverage.py"
SIMPLE_PROTOCOL = ROOT / "computations" / "yang-mills-closed-wilson-simple-cycle-coverage-prereg.md"
BASELINE_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage.py"
BASELINE_PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v3.md"
V4_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage_v4.py"
V4_PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v4.md"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
LARGE_RECOVERY_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_HELPER = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_closed_wilson_repeated_edge_coverage" / "verification.json"

COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0)
MATRIX_TOLERANCE = 1.0e-10
LINK_SUPPORT_TOLERANCE = 1.0e-14
Q_DIMENSION = 867
EXPECTED_STATE_DIMENSION = 868
EXPECTED_RAW_COUNTS = {4: 88, 6: 432, 8: 1944}
EXPECTED_LENGTH_COUNTS = {4: 11, 6: 36, 8: 127, 10: 84, 12: 22}
EXPECTED_SIMPLE_RAW_COUNTS = {10: 1680, 12: 528}
EXPECTED_REPEATED_RAW_LENGTH8 = 792
EXPECTED_REPEATED_COUNT = 55
EXPECTED_SIMPLE_COUNT = 225
EXPECTED_FAMILY_COUNT = 280
EXPECTED_PLAQUETTE_COUNTS = (11, 121, 1331, 14641)
EXPECTED_PROJECTED_COLUMNS = EXPECTED_FAMILY_COUNT + sum(EXPECTED_PLAQUETTE_COUNTS)
SAMPLE_STATE_PAIRS = ((0, 0), (10, 17), (100, 200), (867, 866))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def inverse(term: tuple[int, int]) -> tuple[int, int]:
    return term[0], -term[1]


def rotations(word: Sequence[tuple[int, int]]) -> list[tuple[tuple[int, int], ...]]:
    return [tuple(word[index:]) + tuple(word[:index]) for index in range(len(word))]


def canonical_word(word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    forward = tuple(word)
    reverse = tuple(large.reverse_word(forward))
    return min(rotations(forward) + rotations(reverse))


def word_is_simple(word: Sequence[tuple[int, int]]) -> bool:
    return (
        len(set(edge for edge, _ in word)) == len(word)
        and len({vertex for edge, _ in word for vertex in (large.LINK_TAILS[edge], large.LINK_HEADS[edge])}) == len(word)
    )


def enumerate_closed_reduced(
    lengths: Sequence[int],
) -> tuple[dict[int, int], dict[int, int], dict[int, set[tuple[tuple[int, int], ...]]], dict[int, set[tuple[tuple[int, int], ...]]]]:
    adjacency: dict[int, list[tuple[int, int, int]]] = {vertex: [] for vertex in range(len(large.VERTEX_COORDS))}
    for edge, (tail, head) in enumerate(zip(large.LINK_TAILS, large.LINK_HEADS)):
        adjacency[tail].append((head, edge, +1))
        adjacency[head].append((tail, edge, -1))
    for vertex in adjacency:
        adjacency[vertex].sort(key=lambda item: (item[0], item[1], item[2]))

    raw_counts: dict[int, int] = {}
    simple_raw_counts: dict[int, int] = {}
    canonical: dict[int, set[tuple[tuple[int, int], ...]]] = {length: set() for length in lengths}
    simple_canonical: dict[int, set[tuple[tuple[int, int], ...]]] = {length: set() for length in lengths}
    for length in lengths:
        raw = 0
        simple_raw = 0

        def extend(root: int, current: int, word: tuple[tuple[int, int], ...]) -> None:
            nonlocal raw, simple_raw
            if len(word) == length:
                if current == root and (not word or word[-1] != inverse(word[0])):
                    raw += 1
                    key = canonical_word(word)
                    canonical[length].add(key)
                    if word_is_simple(word):
                        simple_raw += 1
                        simple_canonical[length].add(key)
                return
            for next_vertex, edge, orientation in adjacency[current]:
                term = (edge, orientation)
                if word and term == inverse(word[-1]):
                    continue
                extend(root, next_vertex, word + (term,))

        for root in adjacency:
            extend(root, root, ())
        raw_counts[length] = raw
        simple_raw_counts[length] = simple_raw
    return raw_counts, simple_raw_counts, canonical, simple_canonical


def make_link_tensor(
    left_spin: int,
    right_spin: int,
    positions: tuple[int, ...],
    word: tuple[tuple[int, int], ...],
) -> np.ndarray:
    net = large.Network()
    bra_m = net.label("bm", (left_spin,))
    bra_head = net.label("bh", (left_spin,))
    ket_m = net.label("km", (right_spin,))
    ket_head = net.label("kh", (right_spin,))
    loop_indices = tuple(
        sorted({index for position in positions for index in (position, (position + 1) % len(word))})
    )
    loop_labels = {index: net.label(f"l{index}", (1,)) for index in loop_indices}
    factors: list[tuple[Any, Any, bool]] = [
        (bra_m, bra_head, True),
        (ket_m, ket_head, False),
    ]
    for position in positions:
        _, orientation = word[position]
        first = position if orientation > 0 else (position + 1) % len(word)
        second = (position + 1) % len(word) if orientation > 0 else position
        factors.append((loop_labels[first], loop_labels[second], orientation < 0))
    large.link_integral(net, factors, "link")
    raw = np.asarray(
        net.contract(open_axes=(bra_m, bra_head, ket_m, ket_head) + tuple(loop_labels[index] for index in loop_indices))
    )
    return np.einsum(
        "xyzt...,uy,vt->xuzv...",
        raw,
        large.metric_tensor(left_spin),
        large.metric_tensor(right_spin),
        optimize=True,
    )


def build_word_context(
    states: tuple[Any, ...],
    word: tuple[tuple[int, int], ...],
    vertex_cache: tuple[tuple[np.ndarray, ...], ...],
) -> tuple[dict[tuple[int, int, int], np.ndarray], list[tuple[int, int]], int]:
    active_edges = {edge for edge, _ in word}
    positions = {
        edge: tuple(index for index, (candidate, _) in enumerate(word) if candidate == edge)
        for edge in range(len(large.LINK_TAILS))
    }
    link_cache: dict[tuple[int, int, int], np.ndarray] = {}
    support: dict[tuple[int, int, int], bool] = {}
    for edge in range(len(large.LINK_TAILS)):
        for left_spin in range(2):
            for right_spin in range(2):
                tensor = make_link_tensor(left_spin, right_spin, positions[edge], word)
                key = (edge, left_spin, right_spin)
                link_cache[key] = tensor
                support[key] = bool(np.any(np.abs(tensor) > LINK_SUPPORT_TOLERANCE))
    inactive_edges = tuple(edge for edge in range(len(large.LINK_TAILS)) if edge not in active_edges)
    groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index, state in enumerate(states):
        groups[tuple(state[edge] for edge in inactive_edges)].append(index)
    pairs: list[tuple[int, int]] = []
    for group in groups.values():
        for column in group:
            for row in group:
                if all(support[(edge, states[row][edge], states[column][edge])] for edge in active_edges):
                    pairs.append((row, column))
    return link_cache, pairs, sum(len(group) * len(group) for group in groups.values())


def effective_network_matrix_element(
    left_index: int,
    right_index: int,
    states: tuple[Any, ...],
    word: tuple[tuple[int, int], ...],
    vertex_cache: tuple[tuple[np.ndarray, ...], ...],
    link_cache: dict[tuple[int, int, int], np.ndarray],
) -> complex:
    left = states[left_index]
    right = states[right_index]
    left_edges = left[:20]
    right_edges = right[:20]
    net = large.Network()
    bra_m = {edge: net.label(f"bm{edge}", (left_edges[edge],)) for edge in range(20)}
    bra_head = {edge: net.label(f"bh{edge}", (left_edges[edge],)) for edge in range(20)}
    ket_m = {edge: net.label(f"km{edge}", (right_edges[edge],)) for edge in range(20)}
    ket_head = {edge: net.label(f"kh{edge}", (right_edges[edge],)) for edge in range(20)}
    loops = {position: net.label(f"loop{position}", (1,)) for position in range(len(word))}
    for vertex, legs in enumerate(large.INCIDENT_LEGS):
        bra_axes = tuple(bra_m[edge] if orientation > 0 else bra_head[edge] for edge, orientation, _ in legs)
        ket_axes = tuple(ket_m[edge] if orientation > 0 else ket_head[edge] for edge, orientation, _ in legs)
        net.add(vertex_cache[left_index][vertex], bra_axes)
        net.add(vertex_cache[right_index][vertex], ket_axes)
    for edge in range(20):
        loop_indices = tuple(
            sorted({index for position, (candidate, _) in enumerate(word) if candidate == edge for index in (position, (position + 1) % len(word))})
        )
        loop_axes = tuple(loops[index] for index in loop_indices)
        net.add(
            link_cache[(edge, left_edges[edge], right_edges[edge])],
            (bra_m[edge], bra_head[edge], ket_m[edge], ket_head[edge]) + loop_axes,
        )
    return complex(net.contract())


def assemble_word(
    states: tuple[Any, ...],
    word: tuple[tuple[int, int], ...],
    vertex_cache: tuple[tuple[np.ndarray, ...], ...],
) -> tuple[csr_matrix, dict[str, Any], dict[tuple[int, int, int], np.ndarray], list[tuple[int, int]]]:
    if not large.closed_word(word):
        raise ArithmeticError(f"non-closing word: {word}")
    if any(word[index + 1] == inverse(word[index]) for index in range(len(word) - 1)):
        raise ArithmeticError(f"adjacent inverse in word: {word}")
    if word[-1] == inverse(word[0]):
        raise ArithmeticError(f"cyclic inverse in word: {word}")
    link_cache, pairs, group_pair_count = build_word_context(states, word, vertex_cache)
    rows: list[int] = []
    columns: list[int] = []
    values: list[complex] = []
    for row, column in pairs:
        value = effective_network_matrix_element(row, column, states, word, vertex_cache, link_cache)
        rows.append(row)
        columns.append(column)
        values.append(value)
    matrix = csr_matrix((np.asarray(values, dtype=complex), (rows, columns)), shape=(len(states), len(states)))
    matrix.sum_duplicates()
    matrix.eliminate_zeros()
    matrix.sort_indices()
    residual = matrix - matrix.T.conjugate()
    hermiticity = float(np.max(np.abs(residual.data))) if residual.nnz else 0.0
    finite = bool(np.isfinite(matrix.data.real).all() and np.isfinite(matrix.data.imag).all())
    return matrix, {
        "word": [[edge, orientation] for edge, orientation in word],
        "length": len(word),
        "active_edge_count": len(set(edge for edge, _ in word)),
        "candidate_entries": len(pairs),
        "group_pair_count": group_pair_count,
        "nonzero_entries": int(matrix.nnz),
        "matrix_hash": large.matrix_hash(matrix),
        "hermiticity_residual": hermiticity,
        "finite": finite,
    }, link_cache, pairs


def augmented_block_ranks(wilson_centered: np.ndarray, plaquette_blocks: list[np.ndarray]) -> tuple[list[dict[str, Any]], np.ndarray]:
    blocks = [("closed_wilson", wilson_centered)] + [
        (f"plaquette_degree_{degree}", block)
        for degree, block in enumerate(plaquette_blocks, start=1)
    ]
    cumulative: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for name, block in blocks:
        cumulative.append(block)
        matrix = np.column_stack(cumulative)
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        rank = simple.rank_from_singular_values(singular_values)
        records.append(
            {
                "block": name,
                "block_column_count": int(block.shape[1]),
                "cumulative_column_count": int(matrix.shape[1]),
                "rank": rank,
                "nullity": int(Q_DIMENSION - rank),
                "singular_values": singular_values.tolist(),
            }
        )
    return records, np.column_stack(cumulative)


def run(output: Path) -> dict[str, Any]:
    required = (
        PROTOCOL,
        SOURCE,
        INDEPENDENT_SOURCE,
        SIMPLE_SOURCE,
        SIMPLE_PROTOCOL,
        BASELINE_SOURCE,
        BASELINE_PROTOCOL,
        V4_SOURCE,
        V4_PROTOCOL,
        LARGE_SOURCE,
        LARGE_PROTOCOL,
        LARGE_RECOVERY_PROTOCOL,
        LARGE_HELPER,
        LARGE_RECEIPT,
    )
    if not all(path.is_file() for path in required):
        missing = [relative(path) for path in required if not path.is_file()]
        raise FileNotFoundError(f"missing repeated-edge coverage dependency: {missing}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    source_receipt = json.loads(LARGE_RECEIPT.read_text(encoding="utf-8"))
    source_failed_checks = tuple(item.get("name") for item in source_receipt.get("checks", []) if item.get("passed") is False)
    source_qualification_ok = (
        source_receipt.get("checks_passed") == 234
        and source_receipt.get("checks_total") == 238
        and set(source_failed_checks) == set(simple.LARGE_RECEIPT_TAIL_QUALIFICATIONS)
        and len(source_failed_checks) == len(simple.LARGE_RECEIPT_TAIL_QUALIFICATIONS)
    )
    states = tuple(large.basis_states(1))
    if len(states) != EXPECTED_STATE_DIMENSION:
        raise ArithmeticError(f"unexpected C=1 dimension {len(states)}")
    vertex_cache = tuple(
        tuple(
            large.vertex_tensor(
                tuple(state[edge] for edge, _, _ in large.INCIDENT_LEGS[vertex]),
                dict(zip(large.FOUR_VALENCE_VERTICES, state[20:])).get(vertex),
            )
            for vertex in range(len(large.INCIDENT_LEGS))
        )
        for state in states
    )

    raw_counts, simple_raw_counts, canonical_by_length, simple_canonical_by_length = enumerate_closed_reduced((4, 6, 8, 10, 12))
    family_canonical_by_length = {
        4: canonical_by_length[4],
        6: canonical_by_length[6],
        8: canonical_by_length[8],
        10: simple_canonical_by_length[10],
        12: simple_canonical_by_length[12],
    }
    all_words = tuple(sorted(set().union(*family_canonical_by_length.values()), key=lambda word: (len(word), word)))
    simple_raw_count, simple_words = simple.enumerate_simple_cycles(large)
    simple_words = tuple(simple_words)
    simple_set = set(simple_words)
    repeated_words = tuple(word for word in all_words if word not in simple_set)
    repeated_length8 = tuple(word for word in repeated_words if len(word) == 8)
    repeated_profiles: dict[str, tuple[tuple[int, int], ...]] = {}
    for word in repeated_length8:
        profile = ",".join(str(value) for value in sorted(Counter(edge for edge, _ in word).values(), reverse=True))
        repeated_profiles.setdefault(profile, word)
    sampled_repeated_words = tuple(repeated_profiles[key] for key in sorted(repeated_profiles))

    simple_matrices: dict[tuple[tuple[int, int], ...], csr_matrix] = {}
    simple_records: dict[tuple[tuple[int, int], ...], dict[str, Any]] = {}
    for word in simple_words:
        matrix, record = simple.assemble_simple_cycle(large, states, word)
        simple_matrices[word] = matrix
        simple_records[word] = record

    repeated_matrices: dict[tuple[tuple[int, int], ...], csr_matrix] = {}
    repeated_records: dict[tuple[tuple[int, int], ...], dict[str, Any]] = {}
    repeated_contexts: dict[tuple[tuple[int, int], ...], tuple[dict[tuple[int, int, int], np.ndarray], list[tuple[int, int]]]] = {}
    for word in repeated_length8:
        matrix, record, link_cache, pairs = assemble_word(states, word, vertex_cache)
        repeated_matrices[word] = matrix
        repeated_records[word] = record
        repeated_contexts[word] = (link_cache, pairs)

    length_four_errors = []
    for word in simple_words:
        if len(word) != 4:
            continue
        reference, *_ = large._assemble_plaquette(states, word, 1)
        difference = simple_matrices[word] - reference
        length_four_errors.append(float(np.max(np.abs(difference.data))) if difference.nnz else 0.0)

    direct_sample_errors: list[float] = []
    reversal_errors: list[float] = []
    for word in sampled_repeated_words:
        matrix = repeated_matrices[word]
        link_cache, _ = repeated_contexts[word]
        reverse_word = tuple(large.reverse_word(word))
        reverse_link_cache, _, _ = build_word_context(states, reverse_word, vertex_cache)
        for row, column in SAMPLE_STATE_PAIRS:
            direct_sample_errors.append(
                abs(matrix[row, column] - simple.direct_network_matrix_element(large, states[row], states[column], word))
            )
            forward = effective_network_matrix_element(row, column, states, word, vertex_cache, link_cache)
            reverse = effective_network_matrix_element(row, column, states, reverse_word, vertex_cache, reverse_link_cache)
            reversal_errors.append(abs(forward - reverse))

    all_matrices = {**simple_matrices, **repeated_matrices}
    family_words = tuple(sorted(all_matrices, key=lambda word: (len(word), word)))
    normalized_family = [large.normalized_operator(all_matrices[word], states) for word in family_words]
    plaquette_baseline = simple.load_baseline()
    plaquette_rows, plaquette_operator, matrix_checks = plaquette_baseline.build_plaquette_source(large, states, source_receipt)
    normalized_plaquettes = [large.normalized_operator(row["matrix"], states) for row in plaquette_rows]

    dependencies = {
        relative(PROTOCOL): sha256(PROTOCOL),
        relative(SOURCE): sha256(SOURCE),
        relative(INDEPENDENT_SOURCE): sha256(INDEPENDENT_SOURCE),
        relative(SIMPLE_SOURCE): sha256(SIMPLE_SOURCE),
        relative(SIMPLE_PROTOCOL): sha256(SIMPLE_PROTOCOL),
        relative(BASELINE_SOURCE): sha256(BASELINE_SOURCE),
        relative(BASELINE_PROTOCOL): sha256(BASELINE_PROTOCOL),
        relative(V4_SOURCE): sha256(V4_SOURCE),
        relative(V4_PROTOCOL): sha256(V4_PROTOCOL),
        relative(LARGE_SOURCE): sha256(LARGE_SOURCE),
        relative(LARGE_PROTOCOL): sha256(LARGE_PROTOCOL),
        relative(LARGE_RECOVERY_PROTOCOL): sha256(LARGE_RECOVERY_PROTOCOL),
        relative(LARGE_HELPER): sha256(LARGE_HELPER),
        relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT),
    }
    length_counts = {length: len(family_canonical_by_length[length]) for length in family_canonical_by_length}
    declared_raw_counts = {
        4: raw_counts[4],
        6: raw_counts[6],
        8: raw_counts[8],
        10: simple_raw_counts[10],
        12: simple_raw_counts[12],
    }
    repeated_raw_length8 = raw_counts[8] - simple_raw_counts[8]
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("source_path", relative(SOURCE) == "computations/verify_yang_mills_closed_wilson_repeated_edge_coverage.py"),
        check("independent_source_path", INDEPENDENT_SOURCE.is_file()),
        check("simple_cycle_lineage_path", SIMPLE_SOURCE.is_file() and SIMPLE_PROTOCOL.is_file()),
        check("degree_four_lineage_path", BASELINE_SOURCE.is_file() and BASELINE_PROTOCOL.is_file() and V4_SOURCE.is_file() and V4_PROTOCOL.is_file()),
        check("larger_source_path", LARGE_SOURCE.is_file()),
        check(
            "larger_receipt_binding",
            source_receipt.get("status") == "PASS"
            and source_receipt.get("classification") == "PASS_RECOVERED_FINITE_CONSTRUCTION"
            and source_receipt.get("source_sha256") == sha256(LARGE_SOURCE)
            and source_receipt.get("helper_sha256") == sha256(LARGE_HELPER)
            and source_receipt.get("protocol_sha256") == sha256(LARGE_RECOVERY_PROTOCOL)
            and source_receipt.get("scientific_protocol_sha256") == sha256(LARGE_PROTOCOL)
            and source_qualification_ok,
            source_status=source_receipt.get("status"),
            source_classification=source_receipt.get("classification"),
            source_checks_passed=source_receipt.get("checks_passed"),
            source_checks_total=source_receipt.get("checks_total"),
            source_failed_checks=list(source_failed_checks),
        ),
        check("graph_dimension", len(states) == EXPECTED_STATE_DIMENSION),
        check("raw_inventory_counts", {key: raw_counts[key] for key in EXPECTED_RAW_COUNTS} == EXPECTED_RAW_COUNTS and {key: simple_raw_counts[key] for key in EXPECTED_SIMPLE_RAW_COUNTS} == EXPECTED_SIMPLE_RAW_COUNTS, observed=raw_counts, observed_simple=simple_raw_counts),
        check("canonical_inventory_counts", length_counts == EXPECTED_LENGTH_COUNTS, observed=length_counts),
        check("repeated_edge_inventory", len(repeated_length8) == EXPECTED_REPEATED_COUNT and repeated_raw_length8 == EXPECTED_REPEATED_RAW_LENGTH8, observed_count=len(repeated_length8), observed_raw=repeated_raw_length8),
        check("closure_reduction_and_canonical_keys", all(large.closed_word(word) and all(word[index + 1] != inverse(word[index]) for index in range(len(word) - 1)) and word[-1] != inverse(word[0]) and canonical_word(word) == word for word in all_words), family_count=len(all_words)),
        check("simple_subset_identity", len(simple_set) == EXPECTED_SIMPLE_COUNT and simple_set == set().union(*simple_canonical_by_length.values()) and simple_set.issubset(set(all_words)), simple_count=len(simple_set), family_count=len(all_words)),
        check("length_four_and_network_controls", len(length_four_errors) == EXPECTED_LENGTH_COUNTS[4] and max(length_four_errors, default=0.0) <= MATRIX_TOLERANCE and len(direct_sample_errors) == len(sampled_repeated_words) * len(SAMPLE_STATE_PAIRS) and max(direct_sample_errors, default=0.0) <= MATRIX_TOLERANCE and max(reversal_errors, default=0.0) <= MATRIX_TOLERANCE, length_four_max_error=max(length_four_errors, default=0.0), direct_sample_max_error=max(direct_sample_errors, default=0.0), reversal_max_error=max(reversal_errors, default=0.0), sampled_profiles=sorted(repeated_profiles)),
        check("family_matrix_controls", len(simple_records) == EXPECTED_SIMPLE_COUNT and all(item["finite"] and item["hermiticity_residual"] <= MATRIX_TOLERANCE for item in simple_records.values()) and len(repeated_records) == EXPECTED_REPEATED_COUNT and all(item["finite"] and item["hermiticity_residual"] <= MATRIX_TOLERANCE for item in repeated_records.values()), simple_matrix_count=len(simple_records), repeated_matrix_count=len(repeated_records), maximum_hermiticity_residual=max([item["hermiticity_residual"] for item in simple_records.values()] + [item["hermiticity_residual"] for item in repeated_records.values()])),
        check("family_column_count", len(family_words) == EXPECTED_FAMILY_COUNT and tuple(EXPECTED_PLAQUETTE_COUNTS) == (11, 121, 1331, 14641) and EXPECTED_PROJECTED_COLUMNS == EXPECTED_FAMILY_COUNT + sum(EXPECTED_PLAQUETTE_COUNTS), family_count=len(family_words), projected_columns=EXPECTED_PROJECTED_COLUMNS),
        check("plaquette_source_matrix_hashes", len(plaquette_rows) == 11 and all(item["pass"] for item in matrix_checks), matrix_checks=matrix_checks),
    ]
    if len(checks) != 17:
        raise ArithmeticError(f"primary check contract changed before rows: {len(checks)}")
    rows: list[dict[str, Any]] = []
    for coupling in COUPLINGS:
        solved = large.solve_ritz(states, plaquette_rows, Fraction(str(coupling)).limit_denominator(), operator=plaquette_operator)
        omega = simple.as_real(solved["physical_vector"], "ground vector")
        omega_norm = float(omega @ omega)
        family_vectors = simple.as_real(np.column_stack([operator @ omega for operator in normalized_family]), "closed-Wilson vectors")
        family_centered = simple.as_real(family_vectors - omega[:, None] * (omega @ family_vectors)[None, :], "closed-Wilson centered vectors")
        plaquette_blocks, plaquette_counts = simple.projected_plaquette_words(omega, normalized_plaquettes)
        family_rows, projected = augmented_block_ranks(family_centered, plaquette_blocks)
        final_singular_values = np.asarray(family_rows[-1]["singular_values"], dtype=float)
        final_rank = int(family_rows[-1]["rank"])
        first_full_block = next((item["block"] for item in family_rows if item["rank"] == Q_DIMENSION), None)
        max_vacuum_overlap = float(np.max(np.abs(omega @ projected))) if projected.size else 0.0
        classification = "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE" if final_rank == Q_DIMENSION else "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE"
        row_key = str(coupling)
        row_checks = [
            check(f"ground_state_q_decomposition_x{row_key}", np.isfinite(solved["ground_energy"]) and np.isfinite(solved["ritz_gap"]) and solved["ritz_gap"] > 0.0 and solved["generalized_residual"] <= MATRIX_TOLERANCE and abs(omega_norm - 1.0) <= MATRIX_TOLERANCE and max_vacuum_overlap <= MATRIX_TOLERANCE, ground_energy=float(solved["ground_energy"]), ritz_gap=float(solved["ritz_gap"]), generalized_residual=float(solved["generalized_residual"]), omega_norm_squared=omega_norm, maximum_vacuum_overlap=max_vacuum_overlap),
            check(f"closed_wilson_matrix_controls_x{row_key}", family_centered.shape == (EXPECTED_STATE_DIMENSION, EXPECTED_FAMILY_COUNT) and bool(np.isfinite(family_centered).all()), shape=list(family_centered.shape), finite=bool(np.isfinite(family_centered).all())),
            check(f"degree_four_plaquette_schedule_x{row_key}", tuple(plaquette_counts) == EXPECTED_PLAQUETTE_COUNTS and all(block.shape[0] == EXPECTED_STATE_DIMENSION for block in plaquette_blocks), block_counts=plaquette_counts, block_shapes=[list(block.shape) for block in plaquette_blocks]),
            check(f"augmented_column_shape_x{row_key}", projected.shape == (EXPECTED_STATE_DIMENSION, EXPECTED_PROJECTED_COLUMNS) and bool(np.isfinite(projected).all()), shape=list(projected.shape), finite=bool(np.isfinite(projected).all())),
            check(f"singular_values_nullity_x{row_key}", all(item["nullity"] == Q_DIMENSION - item["rank"] and all(item["singular_values"][index] >= item["singular_values"][index + 1] for index in range(len(item["singular_values"]) - 1)) and bool(np.isfinite(np.asarray(item["singular_values"], dtype=float)).all()) for item in family_rows) and all(family_rows[index]["rank"] <= family_rows[index + 1]["rank"] for index in range(len(family_rows) - 1)) and bool(np.isfinite(final_singular_values).all()), family_block_ranks=[item["rank"] for item in family_rows], family_block_nullities=[item["nullity"] for item in family_rows]),
            check(f"full_q_boundary_x{row_key}", Q_DIMENSION == Q_DIMENSION and final_rank <= Q_DIMENSION and classification in {"REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE", "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE"}, q_dimension=Q_DIMENSION, final_rank=final_rank, finite_deficiency=Q_DIMENSION - final_rank, first_full_block=first_full_block, classification=classification),
        ]
        rows.append({"coupling": coupling, "dimension": EXPECTED_STATE_DIMENSION, "ground_energy": float(solved["ground_energy"]), "first_excited": float(solved["first_excited"]), "ritz_gap": float(solved["ritz_gap"]), "generalized_residual": float(solved["generalized_residual"]), "omega_norm_squared": omega_norm, "q_dimension": Q_DIMENSION, "closed_wilson_column_count": EXPECTED_FAMILY_COUNT, "plaquette_block_counts": plaquette_counts, "augmented_column_count": int(projected.shape[1]), "family_blocks": family_rows, "first_full_block": first_full_block, "final_rank": final_rank, "finite_deficiency": Q_DIMENSION - final_rank, "classification": classification, "checks": row_checks})
        checks.extend(row_checks)
    if len(checks) != 41:
        raise ArithmeticError(f"primary check contract changed: {len(checks)}")

    checks_passed = all(item["passed"] for item in checks)
    complete = all(row["classification"] == "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE" for row in rows)
    record: dict[str, Any] = {
        "schema": "yang_mills_closed_wilson_repeated_edge_coverage_v1",
        "status": "PASS" if checks_passed and complete else "FAIL",
        "classification": "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_COMPLETE" if checks_passed and complete else "REPEATED_EDGE_CLOSED_WILSON_COVERAGE_INCOMPLETE" if checks_passed else "FAIL",
        "protocol": relative(PROTOCOL), "source": relative(SOURCE), "independent_source": relative(INDEPENDENT_SOURCE), "simple_source": relative(SIMPLE_SOURCE), "simple_protocol": relative(SIMPLE_PROTOCOL), "larger_source": relative(LARGE_SOURCE), "larger_protocol": relative(LARGE_PROTOCOL), "larger_recovery_protocol": relative(LARGE_RECOVERY_PROTOCOL), "larger_helper": relative(LARGE_HELPER), "larger_receipt": relative(LARGE_RECEIPT),
        "larger_receipt_status": source_receipt.get("status"), "larger_receipt_classification": source_receipt.get("classification"), "larger_receipt_checks_passed": source_receipt.get("checks_passed"), "larger_receipt_checks_total": source_receipt.get("checks_total"), "larger_receipt_failed_checks": list(source_failed_checks),
        "dependencies": dependencies,
        "graph": {"vertices": len(large.VERTEX_COORDS), "links": len(large.LINK_TAILS), "state_dimension_C1": EXPECTED_STATE_DIMENSION, "q_dimension": Q_DIMENSION},
        "cycle_inventory": {"raw_directed_occurrences_by_length": {str(key): value for key, value in sorted(declared_raw_counts.items())}, "enumerated_raw_directed_occurrences_by_length": {str(key): value for key, value in sorted(raw_counts.items())}, "simple_raw_directed_occurrences_by_length": {str(key): value for key, value in sorted(simple_raw_counts.items())}, "raw_directed_occurrences": sum(declared_raw_counts.values()), "canonical_count": len(all_words), "length_counts": {str(key): value for key, value in sorted(length_counts.items())}, "repeated_edge_length8_raw_directed_occurrences": repeated_raw_length8, "repeated_edge_length8_count": len(repeated_length8), "simple_count": len(simple_words), "words": [[[edge, orientation] for edge, orientation in word] for word in family_words]},
        "simple_cycle_records": [simple_records[word] for word in simple_words], "repeated_edge_records": [repeated_records[word] for word in repeated_length8], "repeated_edge_sample_profiles": {profile: [[edge, orientation] for edge, orientation in word] for profile, word in sorted(repeated_profiles.items())}, "sample_state_pairs": [list(pair) for pair in SAMPLE_STATE_PAIRS], "sampled_direct_network_max_error": max(direct_sample_errors, default=0.0), "sampled_reversal_max_error": max(reversal_errors, default=0.0), "length_four_max_error": max(length_four_errors, default=0.0), "plaquette_counts": list(EXPECTED_PLAQUETTE_COUNTS), "projected_column_count": EXPECTED_PROJECTED_COLUMNS, "couplings": list(COUPLINGS), "rows": rows, "checks": checks, "checks_passed": sum(item["passed"] for item in checks), "checks_total": len(checks), "minimum_final_rank": min(row["final_rank"] for row in rows), "maximum_finite_deficiency": max(row["finite_deficiency"] for row in rows), "continuum_claim": False, "thermodynamic_claim": False, "mass_gap_claim": False, "scope": "finite C=1 coverage from the complete declared length-4/6/8 cyclically reduced family, simple length-10/12 cycles, repeated-edge length-eight words and degree-four plaquette products on the recovered open 3x2x2 SU(2) graph",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(f"status={record['status']} classification={record['classification']} checks={record['checks_passed']}/{record['checks_total']} minimum_final_rank={record['minimum_final_rank']} maximum_finite_deficiency={record['maximum_finite_deficiency']}")
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
