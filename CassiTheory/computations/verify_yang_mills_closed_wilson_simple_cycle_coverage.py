#!/usr/bin/env python3
"""Measure finite coverage from all canonical simple Wilson cycles.

Protocol:
``computations/yang-mills-closed-wilson-simple-cycle-coverage-prereg.md``.

The verifier enumerates every unoriented simple cycle of the recovered
3x2x2 graph, assembles its variable-length fundamental Wilson multiplication
matrix with exact finite SU(2) link contractions, and augments the degree-four
plaquette-product vectors.  The result is a finite operator-coverage screen;
it is not an all-closed-word or continuum claim.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import sys
import string
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROTOCOL = ROOT / "computations" / "yang-mills-closed-wilson-simple-cycle-coverage-prereg.md"
SOURCE = Path(__file__).resolve()
BASELINE_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage.py"
BASELINE_PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v3.md"
V4_SOURCE = ROOT / "computations" / "verify_yang_mills_plaquette_cyclic_coverage_v4.py"
V4_PROTOCOL = ROOT / "computations" / "yang-mills-plaquette-cyclic-coverage-prereg-v4.md"
INDEPENDENT_SOURCE = ROOT / "computations" / "verify_yang_mills_closed_wilson_simple_cycle_coverage_independent.py"
LARGE_SOURCE = ROOT / "computations" / "verify_yang_mills_su2_larger_volume_hamiltonian.py"
LARGE_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-prereg.md"
LARGE_RECOVERY_PROTOCOL = ROOT / "computations" / "yang-mills-su2-larger-volume-hamiltonian-recovery-prereg.md"
LARGE_HELPER = ROOT / "computations" / "verify_yang_mills_exact_block_spectrum.py"
LARGE_RECEIPT = ROOT / "runs" / "yang_mills_su2_larger_volume_hamiltonian_recovery" / "current-verification.json"
LARGE_RECEIPT_TAIL_QUALIFICATIONS = (
    "tail_separation_C1_x0.25",
    "tail_separation_C2_x0.25",
    "tail_separation_C1_x1.0",
    "tail_separation_C2_x1.0",
)
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_closed_wilson_simple_cycle_coverage" / "verification.json"

COUPLINGS = (Fraction(1, 64), Fraction(1, 16), Fraction(1, 4), Fraction(1, 1))
MATRIX_TOLERANCE = 1.0e-10
RANK_TOLERANCE = 1.0e-10
Q_DIMENSION = 867
EXPECTED_RAW_CYCLES = 3880
EXPECTED_CYCLE_COUNT = 225
EXPECTED_LENGTH_COUNTS = {4: 11, 6: 36, 8: 72, 10: 84, 12: 22}
EXPECTED_PLAQUETTE_COUNTS = (11, 121, 1331, 14641)
EXPECTED_PROJECTED_COLUMNS = 16329
SAMPLE_STATE_PAIRS = ((0, 0), (10, 17), (100, 200), (867, 866))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def check(name: str, passed: bool, **details: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), **details}


def load_baseline() -> Any:
    spec = importlib.util.spec_from_file_location("cassi_ym_plaquette_v3", BASELINE_SOURCE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load degree-four source builder: {BASELINE_SOURCE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_large_source() -> Any:
    return importlib.import_module("computations.verify_yang_mills_su2_larger_volume_hamiltonian")




def as_real(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value)
    imaginary = float(np.max(np.abs(array.imag))) if np.iscomplexobj(array) and array.size else 0.0
    if imaginary > MATRIX_TOLERANCE:
        raise ArithmeticError(f"{name} has imaginary residual {imaginary}")
    return np.asarray(array.real, dtype=float)


def rank_from_singular_values(values: np.ndarray) -> int:
    if values.size == 0:
        return 0
    scale = max(1.0, float(values[0]))
    return int(np.count_nonzero(values > RANK_TOLERANCE * scale))


def _rotations(word: Sequence[tuple[int, int]]) -> list[tuple[tuple[int, int], ...]]:
    return [tuple(word[index:]) + tuple(word[:index]) for index in range(len(word))]


def canonical_cycle(large: Any, word: Sequence[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    forward = tuple(word)
    reverse = tuple(large.reverse_word(forward))
    return min(_rotations(forward) + _rotations(reverse))


def enumerate_simple_cycles(large: Any) -> tuple[int, tuple[tuple[tuple[int, int], ...], ...]]:
    adjacency: dict[int, list[tuple[int, int, int]]] = {vertex: [] for vertex in range(len(large.VERTEX_COORDS))}
    for edge, (tail, head) in enumerate(zip(large.LINK_TAILS, large.LINK_HEADS)):
        adjacency[tail].append((head, edge, +1))
        adjacency[head].append((tail, edge, -1))
    occurrences: list[tuple[tuple[int, int], ...]] = []

    def extend(
        root: int,
        current: int,
        visited: set[int],
        word: list[tuple[int, int]],
    ) -> None:
        for next_vertex, edge, orientation in sorted(
            adjacency[current], key=lambda item: (item[0], item[1], item[2])
        ):
            if next_vertex == root:
                if len(word) + 1 >= 4:
                    occurrences.append(tuple(word + [(edge, orientation)]))
                continue
            if next_vertex in visited:
                continue
            extend(root, next_vertex, visited | {next_vertex}, word + [(edge, orientation)])

    for root in range(len(large.VERTEX_COORDS)):
        extend(root, root, {root}, [])
    canonical = sorted({canonical_cycle(large, word) for word in occurrences}, key=lambda word: (len(word), word))
    return len(occurrences), tuple(canonical)


@lru_cache(maxsize=None)
def transfer_batch_spec(length: int) -> str:
    labels = string.ascii_lowercase
    if length > len(labels):
        raise ValueError(f"cycle length {length} exceeds einsum labels")
    return ",".join(
        f"Z{labels[index]}{labels[(index + 1) % length]}" for index in range(length)
    ) + "->Z"


def variable_transition_values(
    rows: np.ndarray,
    columns: np.ndarray,
    descriptor_ids: Sequence[np.ndarray],
    pair_maps: Sequence[np.ndarray],
    transfer_matrices: Sequence[np.ndarray],
) -> np.ndarray:
    if rows.size == 0:
        return np.zeros(0, dtype=complex)
    pair_ids = [
        pair_maps[position][descriptor_ids[position][rows], descriptor_ids[position][columns]]
        for position in range(len(pair_maps))
    ]
    pair_table = np.column_stack(pair_ids)
    unique, inverse = np.unique(pair_table, axis=0, return_inverse=True)
    local = np.einsum(
        transfer_batch_spec(len(transfer_matrices)),
        *[
            transfer_matrices[position][unique[:, position]]
            for position in range(len(transfer_matrices))
        ],
        optimize=True,
    )
    return local[inverse]


def candidate_targets_c1(
    edges: tuple[int, ...],
    spectator_channels: tuple[int, ...],
    word: Sequence[tuple[int, int]],
    candidate_groups: dict[Any, np.ndarray],
) -> np.ndarray:
    link_ids = tuple(edge for edge, _ in word)
    if len(set(link_ids)) != len(link_ids):
        raise ValueError("simple-cycle candidate path received a repeated active edge")
    target = list(edges)
    for edge in link_ids:
        if target[edge] == 0:
            target[edge] = 1
        elif target[edge] == 1:
            target[edge] = 0
        else:
            raise ValueError(f"C=1 state has unexpected edge spin {target[edge]}")
    group = candidate_groups.get((tuple(target), spectator_channels))
    return group if group is not None else np.zeros(0, dtype=np.int32)


def assemble_simple_cycle(
    large: Any,
    states: tuple[Any, ...],
    word: tuple[tuple[int, int], ...],
) -> tuple[csr_matrix, dict[str, Any]]:
    if not large.closed_word(word):
        raise ArithmeticError(f"non-closing simple cycle: {word}")
    if len(set(edge for edge, _ in word)) != len(word):
        raise ArithmeticError(f"repeated active edge in simple cycle: {word}")
    edge_groups, edge_array, channel_array = large._indexed_edge_groups(states)
    candidate_groups = large._indexed_candidate_groups(states, word)
    descriptor_ids, pair_maps, transfer_matrices, metadata = large._transition_tables(
        states, word, edge_array, channel_array
    )
    active_edges = {edge for edge, _ in word}
    spectators = np.ones(len(states), dtype=float)
    for edge in range(20):
        if edge not in active_edges:
            spectators /= edge_array[:, edge] + 1.0
    target_groups = {
        key: candidate_targets_c1(key[0], key[1], word, candidate_groups)
        for key in candidate_groups
    }
    candidate_count = sum(
        len(columns) * len(target_groups[key])
        for key, columns in candidate_groups.items()
    )
    rows_out: list[np.ndarray] = []
    columns_out: list[np.ndarray] = []
    values_out: list[np.ndarray] = []
    for key, columns in candidate_groups.items():
        target_rows = target_groups[key]
        if target_rows.size == 0:
            continue
        rows = np.tile(target_rows, columns.size)
        columns_for_rows = np.repeat(columns, target_rows.size)
        values = variable_transition_values(
            rows,
            columns_for_rows,
            descriptor_ids,
            pair_maps,
            transfer_matrices,
        )
        values *= spectators[columns_for_rows]
        rows_out.append(rows)
        columns_out.append(columns_for_rows)
        values_out.append(values)
    if rows_out:
        rows_array = np.concatenate(rows_out)
        columns_array = np.concatenate(columns_out)
        values_array = np.concatenate(values_out)
        matrix = csr_matrix(
            (values_array, (rows_array, columns_array)),
            shape=(len(states), len(states)),
        )
    else:
        rows_array = np.zeros(0, dtype=np.int32)
        values_array = np.zeros(0, dtype=complex)
        matrix = csr_matrix((len(states), len(states)), dtype=complex)
    matrix.sum_duplicates()
    matrix.sort_indices()
    residual = matrix - matrix.T.conjugate()
    hermiticity = float(np.max(np.abs(residual.data))) if residual.nnz else 0.0
    finite = bool(
        np.isfinite(matrix.data.real).all()
        and np.isfinite(matrix.data.imag).all()
    )
    return matrix, {
        "word": [[edge, orientation] for edge, orientation in word],
        "length": len(word),
        "candidate_entries": int(candidate_count),
        "nonzero_entries": int(np.count_nonzero(np.abs(values_array) > MATRIX_TOLERANCE)),
        "matrix_hash": large.matrix_hash(matrix),
        "hermiticity_residual": hermiticity,
        "finite": finite,
        "metadata_length": len(metadata),
    }


def direct_network_matrix_element(
    large: Any,
    left: Any,
    right: Any,
    word: tuple[tuple[int, int], ...],
) -> complex:
    net = large.Network()
    bra = large.SpinNetworkCopy(net, left, "direct_bra")
    ket = large.SpinNetworkCopy(net, right, "direct_ket")
    loops = [net.label(f"direct_loop{index}", (1,)) for index in range(len(word))]
    by_edge: dict[int, list[tuple[Any, Any, bool]]] = {}
    for position, (edge, orientation) in enumerate(word):
        first = loops[position]
        second = loops[(position + 1) % len(word)]
        factor = (first, second, False) if orientation > 0 else (second, first, True)
        by_edge.setdefault(edge, []).append(factor)
    for edge in range(20):
        factors = [
            (bra.m[edge], bra.n[edge], True),
            (ket.m[edge], ket.n[edge], False),
        ]
        factors.extend(by_edge.get(edge, ()))
        large.link_integral(net, factors, f"direct_link{edge}")
    return complex(net.contract())


def projected_plaquette_words(
    omega: np.ndarray,
    normalized_operators: list[Any],
) -> tuple[list[np.ndarray], list[int]]:
    words = omega.reshape(omega.size, 1)
    blocks: list[np.ndarray] = []
    counts: list[int] = []
    for _degree in range(1, 5):
        words = np.column_stack([operator @ words for operator in normalized_operators])
        words = as_real(words, f"plaquette degree {_degree} words")
        centered = words - omega[:, None] * (omega @ words)[None, :]
        blocks.append(as_real(centered, f"plaquette degree {_degree} projected words"))
        counts.append(int(centered.shape[1]))
    return blocks, counts


def block_ranks(
    simple_centered: np.ndarray,
    plaquette_blocks: list[np.ndarray],
) -> tuple[list[dict[str, Any]], np.ndarray]:
    blocks = [("simple_cycles", simple_centered)] + [
        (f"plaquette_degree_{degree}", block)
        for degree, block in enumerate(plaquette_blocks, start=1)
    ]
    cumulative: list[np.ndarray] = []
    records: list[dict[str, Any]] = []
    for name, block in blocks:
        cumulative.append(block)
        matrix = np.column_stack(cumulative)
        singular_values = np.linalg.svd(matrix, compute_uv=False)
        rank = rank_from_singular_values(singular_values)
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
        BASELINE_SOURCE,
        BASELINE_PROTOCOL,
        V4_SOURCE,
        V4_PROTOCOL,
        INDEPENDENT_SOURCE,
        LARGE_SOURCE,
        LARGE_PROTOCOL,
        LARGE_RECOVERY_PROTOCOL,
        LARGE_HELPER,
        LARGE_RECEIPT,
    )
    if not all(path.is_file() for path in required):
        missing = [relative(path) for path in required if not path.is_file()]
        raise FileNotFoundError(f"missing simple-cycle coverage dependency: {missing}")
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    source_receipt = json.loads(LARGE_RECEIPT.read_text(encoding="utf-8"))
    source_failed_checks = tuple(
        item.get("name") for item in source_receipt.get("checks", []) if item.get("passed") is False
    )
    source_qualification_ok = (
        source_receipt.get("checks_passed") == 234
        and source_receipt.get("checks_total") == 238
        and set(source_failed_checks) == set(LARGE_RECEIPT_TAIL_QUALIFICATIONS)
        and len(source_failed_checks) == len(LARGE_RECEIPT_TAIL_QUALIFICATIONS)
    )
    large = load_large_source()
    baseline = load_baseline()
    states = tuple(large.basis_states(1))
    if len(states) != 868:
        raise ArithmeticError(f"unexpected C=1 dimension {len(states)}")
    raw_cycle_count, cycles = enumerate_simple_cycles(large)
    length_counts: dict[int, int] = {}
    for cycle in cycles:
        length_counts[len(cycle)] = length_counts.get(len(cycle), 0) + 1

    simple_matrices: list[csr_matrix] = []
    cycle_records: list[dict[str, Any]] = []
    for cycle in cycles:
        matrix, record = assemble_simple_cycle(large, states, cycle)
        simple_matrices.append(matrix)
        cycle_records.append(record)

    length_four_errors: list[float] = []
    for cycle, matrix in zip(cycles, simple_matrices):
        if len(cycle) != 4:
            continue
        reference, *_ = large._assemble_plaquette(states, cycle, 1)
        difference = matrix - reference
        length_four_errors.append(float(np.max(np.abs(difference.data))) if difference.nnz else 0.0)
    maximum_length_four_error = max(length_four_errors, default=0.0)
    sampled_length_eight = next(cycle for cycle in cycles if len(cycle) == 8)
    sampled_index = cycles.index(sampled_length_eight)
    sampled_matrix = simple_matrices[sampled_index]
    sample_errors = [
        abs(
            sampled_matrix[row, column]
            - direct_network_matrix_element(large, states[row], states[column], sampled_length_eight)
        )
        for row, column in SAMPLE_STATE_PAIRS
    ]
    maximum_network_sample_error = float(max(sample_errors, default=0.0))

    plaquette_rows, plaquette_operator, matrix_checks = baseline.build_plaquette_source(
        large, states, source_receipt
    )
    normalized_plaquettes = [large.normalized_operator(row["matrix"], states) for row in plaquette_rows]
    normalized_cycles = [large.normalized_operator(matrix, states) for matrix in simple_matrices]

    dependencies = {
        relative(PROTOCOL): sha256(PROTOCOL),
        relative(SOURCE): sha256(SOURCE),
        relative(BASELINE_PROTOCOL): sha256(BASELINE_PROTOCOL),
        relative(BASELINE_SOURCE): sha256(BASELINE_SOURCE),
        relative(V4_SOURCE): sha256(V4_SOURCE),
        relative(V4_PROTOCOL): sha256(V4_PROTOCOL),
        relative(LARGE_SOURCE): sha256(LARGE_SOURCE),
        relative(LARGE_PROTOCOL): sha256(LARGE_PROTOCOL),
        relative(LARGE_RECOVERY_PROTOCOL): sha256(LARGE_RECOVERY_PROTOCOL),
        relative(LARGE_HELPER): sha256(LARGE_HELPER),
        relative(LARGE_RECEIPT): sha256(LARGE_RECEIPT),
    }
    checks: list[dict[str, Any]] = [
        check("protocol_path", PROTOCOL.is_file()),
        check("source_path", relative(SOURCE) == "computations/verify_yang_mills_closed_wilson_simple_cycle_coverage.py"),
        check("independent_source_path", INDEPENDENT_SOURCE.is_file()),
        check(
            "degree_four_source_path",
            BASELINE_SOURCE.is_file()
            and BASELINE_PROTOCOL.is_file()
            and V4_SOURCE.is_file()
            and V4_PROTOCOL.is_file(),
        ),
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
            unresolved_tail_qualifications=list(LARGE_RECEIPT_TAIL_QUALIFICATIONS),
        ),
        check("graph_dimension", len(states) == 868),
        check("raw_simple_cycle_inventory", raw_cycle_count == EXPECTED_RAW_CYCLES, observed=raw_cycle_count),
        check("canonical_simple_cycle_count", len(cycles) == EXPECTED_CYCLE_COUNT, observed=len(cycles)),
        check(
            "simple_cycle_length_distribution",
            length_counts == EXPECTED_LENGTH_COUNTS,
            observed=length_counts,
            expected=EXPECTED_LENGTH_COUNTS,
        ),
        check(
            "cycle_closure_and_simple_support",
            all(
                large.closed_word(cycle)
                and len(set(edge for edge, _ in cycle)) == len(cycle)
                and len({vertex for edge, _ in cycle for vertex in (large.LINK_TAILS[edge], large.LINK_HEADS[edge])}) == len(cycle)
                for cycle in cycles
            ),
            cycle_count=len(cycles),
        ),
        check(
            "length_four_assembler_equivalence",
            len(length_four_errors) == EXPECTED_LENGTH_COUNTS[4]
            and maximum_length_four_error <= MATRIX_TOLERANCE,
            class_count=len(length_four_errors),
            maximum_error=maximum_length_four_error,
        ),
        check(
            "length_eight_network_equivalence",
            len(sample_errors) == len(SAMPLE_STATE_PAIRS)
            and maximum_network_sample_error <= MATRIX_TOLERANCE,
            sampled_word=[[edge, orientation] for edge, orientation in sampled_length_eight],
            sampled_cycle_index=sampled_index,
            maximum_error=maximum_network_sample_error,
            sample_errors=[float(value) for value in sample_errors],
        ),
        check(
            "simple_cycle_matrix_finiteness_and_hermiticity",
            len(cycle_records) == EXPECTED_CYCLE_COUNT
            and all(record["finite"] for record in cycle_records)
            and all(record["hermiticity_residual"] <= MATRIX_TOLERANCE for record in cycle_records),
            matrix_count=len(cycle_records),
            maximum_hermiticity_residual=max(
                (record["hermiticity_residual"] for record in cycle_records), default=0.0
            ),
        ),
        check(
            "schedule_and_augmented_column_count",
            tuple(EXPECTED_PLAQUETTE_COUNTS) == (11, 121, 1331, 14641)
            and EXPECTED_PROJECTED_COLUMNS == EXPECTED_CYCLE_COUNT + sum(EXPECTED_PLAQUETTE_COUNTS),
            simple_cycle_count=EXPECTED_CYCLE_COUNT,
            plaquette_counts=list(EXPECTED_PLAQUETTE_COUNTS),
            projected_columns=EXPECTED_PROJECTED_COLUMNS,
        ),
        check(
            "plaquette_source_matrix_hashes",
            len(plaquette_rows) == 11 and all(item["pass"] for item in matrix_checks),
            matrix_checks=matrix_checks,
        ),
    ]
    if len(checks) != 16:
        raise ArithmeticError(f"global check contract changed before rows: {len(checks)}")

    rows: list[dict[str, Any]] = []
    for coupling in COUPLINGS:
        solved = large.solve_ritz(states, plaquette_rows, coupling, operator=plaquette_operator)
        omega = as_real(solved["physical_vector"], "ground vector")
        omega_norm = float(omega @ omega)
        simple_vectors = as_real(
            np.column_stack([operator @ omega for operator in normalized_cycles]),
            "simple-cycle vectors",
        )
        simple_centered = as_real(
            simple_vectors - omega[:, None] * (omega @ simple_vectors)[None, :],
            "simple-cycle centered vectors",
        )
        plaquette_blocks, plaquette_counts = projected_plaquette_words(omega, normalized_plaquettes)
        family_rows, projected = block_ranks(simple_centered, plaquette_blocks)
        final_singular_values = np.asarray(family_rows[-1]["singular_values"], dtype=float)
        final_rank = int(family_rows[-1]["rank"])
        q_dimension = len(states) - 1
        first_full_block = next(
            (item["block"] for item in family_rows if item["rank"] == q_dimension),
            None,
        )
        max_vacuum_overlap = float(np.max(np.abs(omega @ projected))) if projected.size else 0.0
        classification = (
            "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE"
            if final_rank == q_dimension
            else "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE"
        )
        row_key = str(coupling)
        row_checks = [
            check(
                f"ground_state_q_decomposition_x{row_key}",
                np.isfinite(solved["ground_energy"])
                and np.isfinite(solved["ritz_gap"])
                and solved["ritz_gap"] > 0.0
                and solved["generalized_residual"] <= MATRIX_TOLERANCE
                and abs(omega_norm - 1.0) <= MATRIX_TOLERANCE
                and max_vacuum_overlap <= MATRIX_TOLERANCE,
                ground_energy=float(solved["ground_energy"]),
                ritz_gap=float(solved["ritz_gap"]),
                generalized_residual=float(solved["generalized_residual"]),
                omega_norm_squared=omega_norm,
                maximum_vacuum_overlap=max_vacuum_overlap,
            ),
            check(
                f"simple_cycle_matrix_controls_x{row_key}",
                simple_centered.shape == (len(states), EXPECTED_CYCLE_COUNT)
                and bool(np.isfinite(simple_centered).all()),
                shape=list(simple_centered.shape),
                finite=bool(np.isfinite(simple_centered).all()),
            ),
            check(
                f"degree_four_plaquette_schedule_x{row_key}",
                tuple(plaquette_counts) == EXPECTED_PLAQUETTE_COUNTS
                and all(block.shape[0] == len(states) for block in plaquette_blocks),
                block_counts=plaquette_counts,
                block_shapes=[list(block.shape) for block in plaquette_blocks],
            ),
            check(
                f"augmented_column_shape_x{row_key}",
                projected.shape == (len(states), EXPECTED_PROJECTED_COLUMNS)
                and bool(np.isfinite(projected).all()),
                shape=list(projected.shape),
                finite=bool(np.isfinite(projected).all()),
            ),
            check(
                f"singular_values_nullity_x{row_key}",
                all(
                    item["nullity"] == q_dimension - item["rank"]
                    and all(
                        item["singular_values"][index] >= item["singular_values"][index + 1]
                        for index in range(len(item["singular_values"]) - 1)
                    )
                    and bool(np.isfinite(np.asarray(item["singular_values"], dtype=float)).all())
                    for item in family_rows
                )
                and all(
                    family_rows[index]["rank"] <= family_rows[index + 1]["rank"]
                    for index in range(len(family_rows) - 1)
                )
                and bool(np.isfinite(final_singular_values).all()),
                family_block_ranks=[item["rank"] for item in family_rows],
                family_block_nullities=[item["nullity"] for item in family_rows],
            ),
            check(
                f"full_q_boundary_x{row_key}",
                q_dimension == Q_DIMENSION
                and final_rank <= q_dimension
                and classification
                in {
                    "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE",
                    "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE",
                },
                q_dimension=q_dimension,
                final_rank=final_rank,
                finite_deficiency=q_dimension - final_rank,
                first_full_block=first_full_block,
                classification=classification,
            ),
        ]
        rows.append(
            {
                "coupling": float(coupling),
                "dimension": len(states),
                "ground_energy": float(solved["ground_energy"]),
                "first_excited": float(solved["first_excited"]),
                "ritz_gap": float(solved["ritz_gap"]),
                "generalized_residual": float(solved["generalized_residual"]),
                "omega_norm_squared": omega_norm,
                "q_dimension": q_dimension,
                "simple_cycle_column_count": EXPECTED_CYCLE_COUNT,
                "plaquette_block_counts": plaquette_counts,
                "augmented_column_count": int(projected.shape[1]),
                "family_blocks": family_rows,
                "first_full_block": first_full_block,
                "final_rank": final_rank,
                "finite_deficiency": q_dimension - final_rank,
                "classification": classification,
                "checks": row_checks,
            }
        )
        checks.extend(row_checks)
    if len(checks) != 40:
        raise ArithmeticError(f"primary check contract changed: {len(checks)}")

    checks_passed = all(item["passed"] for item in checks)
    complete = all(row["classification"] == "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE" for row in rows)
    record: dict[str, Any] = {
        "schema": "yang_mills_closed_wilson_simple_cycle_coverage_v1",
        "status": "PASS" if checks_passed and complete else "FAIL",
        "classification": (
            "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_COMPLETE"
            if checks_passed and complete
            else "CLOSED_WILSON_SIMPLE_CYCLE_COVERAGE_INCOMPLETE"
            if checks_passed
            else "FAIL"
        ),
        "protocol": relative(PROTOCOL),
        "source": relative(SOURCE),
        "degree_four_source": relative(V4_SOURCE),
        "degree_four_protocol": relative(V4_PROTOCOL),
        "independent_source": relative(INDEPENDENT_SOURCE),
        "larger_source": relative(LARGE_SOURCE),
        "larger_protocol": relative(LARGE_PROTOCOL),
        "larger_recovery_protocol": relative(LARGE_RECOVERY_PROTOCOL),
        "larger_helper": relative(LARGE_HELPER),
        "larger_receipt": relative(LARGE_RECEIPT),
        "larger_receipt_status": source_receipt.get("status"),
        "larger_receipt_classification": source_receipt.get("classification"),
        "larger_receipt_checks_passed": source_receipt.get("checks_passed"),
        "larger_receipt_checks_total": source_receipt.get("checks_total"),
        "larger_receipt_failed_checks": list(source_failed_checks),
        "larger_receipt_tail_qualifications": list(LARGE_RECEIPT_TAIL_QUALIFICATIONS),
        "larger_receipt_qualification_passed": source_qualification_ok,
        "dependencies": dependencies,
        "graph": {
            "vertices": len(large.VERTEX_COORDS),
            "links": len(large.LINK_TAILS),
            "state_dimension_C1": len(states),
            "q_dimension": len(states) - 1,
        },
        "cycle_inventory": {
            "raw_directed_occurrences": raw_cycle_count,
            "canonical_count": len(cycles),
            "length_counts": {str(key): value for key, value in sorted(length_counts.items())},
            "cycles": cycle_records,
        },
        "sampled_length_eight": {
            "cycle_index": sampled_index,
            "word": [[edge, orientation] for edge, orientation in sampled_length_eight],
            "state_pairs": [list(pair) for pair in SAMPLE_STATE_PAIRS],
            "maximum_network_error": maximum_network_sample_error,
        },
        "plaquette_counts": list(EXPECTED_PLAQUETTE_COUNTS),
        "projected_column_count": EXPECTED_PROJECTED_COLUMNS,
        "couplings": [float(coupling) for coupling in COUPLINGS],
        "rows": rows,
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "minimum_final_rank": min(row["final_rank"] for row in rows),
        "maximum_finite_deficiency": max(row["finite_deficiency"] for row in rows),
        "continuum_claim": False,
        "thermodynamic_claim": False,
        "mass_gap_claim": False,
        "scope": "finite C=1 coverage from all canonical unoriented simple cycles plus degree-four plaquette products on the recovered open 3x2x2 SU(2) graph",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    record = run(args.output)
    print(
        f"status={record['status']} classification={record['classification']} "
        f"checks={record['checks_passed']}/{record['checks_total']} "
        f"minimum_final_rank={record['minimum_final_rank']} "
        f"maximum_finite_deficiency={record['maximum_finite_deficiency']}"
    )
    return 0 if record["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
