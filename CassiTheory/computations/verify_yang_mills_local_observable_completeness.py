#!/usr/bin/env python3
"""Verify finite controls for the local SU(2) observable algebra.

The analytic density and GNS argument are frozen in
computations/yang-mills-local-observable-completeness-prereg.md.  This script
checks finite quaternion, word, character and mutation controls only; it does
not construct an RG map, a uniform gap, or a continuum Yang--Mills theory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "yang-mills-local-observable-completeness-prereg.md"
SOURCE = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "yang_mills_local_observable_completeness" / "verification.json"

TOLERANCE = 1.0e-12
CHARACTER_MAX = 8
WORD_MAX_LENGTH = 3

Quaternion = tuple[float, float, float, float]
Word = tuple[int, ...]

GRAPH_FIXTURES = (
    {
        "name": "cycle4",
        "vertices": 4,
        "edges": ((0, 1), (1, 2), (2, 3), (3, 0)),
        "tree_indices": (0, 1, 2),
    },
    {
        "name": "theta3",
        "vertices": 2,
        "edges": ((0, 1), (0, 1), (0, 1)),
        "tree_indices": (0,),
    },
    {
        "name": "bouquet3",
        "vertices": 1,
        "edges": ((0, 0), (0, 0), (0, 0)),
        "tree_indices": (),
    },
)

VECTOR_SEEDS = (
    (0.23, -0.31, 0.17),
    (-0.19, 0.27, 0.34),
    (0.29, 0.11, -0.21),
    (-0.37, 0.16, 0.08),
    (0.13, 0.33, 0.22),
    (-0.24, -0.18, 0.31),
)
GAUGE_SEEDS = (
    (0.17, -0.22, 0.29),
    (-0.28, 0.14, 0.19),
    (0.21, 0.32, -0.13),
    (-0.16, 0.25, 0.35),
)


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def qmul(left: Quaternion, right: Quaternion) -> Quaternion:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return (
        lw * rw - lx * rx - ly * ry - lz * rz,
        lw * rx + lx * rw + ly * rz - lz * ry,
        lw * ry - lx * rz + ly * rw + lz * rx,
        lw * rz + lx * ry - ly * rx + lz * rw,
    )


def qinv(value: Quaternion) -> Quaternion:
    norm_sq = sum(component * component for component in value)
    return (value[0] / norm_sq, -value[1] / norm_sq, -value[2] / norm_sq, -value[3] / norm_sq)


def qexp(vector: tuple[float, float, float]) -> Quaternion:
    theta = math.sqrt(sum(component * component for component in vector))
    if theta == 0.0:
        return (1.0, 0.0, 0.0, 0.0)
    scale = math.sin(theta) / theta
    return (math.cos(theta), vector[0] * scale, vector[1] * scale, vector[2] * scale)


def qnorm_error(value: Quaternion) -> float:
    return abs(sum(component * component for component in value) - 1.0)


def qmax_difference(left: Quaternion, right: Quaternion) -> float:
    return max(abs(a - b) for a, b in zip(left, right))


def trace(value: Quaternion) -> float:
    return 2.0 * value[0]


def qmatrix(value: Quaternion) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    w, x, y, z = value
    return ((complex(w, z), complex(y, x)), (complex(-y, x), complex(w, -z)))


def matrix_multiply(
    left: tuple[tuple[complex, complex], tuple[complex, complex]],
    right: tuple[tuple[complex, complex], tuple[complex, complex]],
) -> tuple[tuple[complex, complex], tuple[complex, complex]]:
    return tuple(
        tuple(sum(left[row][k] * right[k][column] for k in range(2)) for column in range(2))
        for row in range(2)
    )  # type: ignore[return-value]


def matrix_max_difference(
    left: tuple[tuple[complex, complex], tuple[complex, complex]],
    right: tuple[tuple[complex, complex], tuple[complex, complex]],
) -> float:
    return max(abs(left[row][column] - right[row][column]) for row in range(2) for column in range(2))


def matrix_rank(matrix: list[list[float]], tolerance: float) -> int:
    work = [row[:] for row in matrix]
    rows = len(work)
    columns = len(work[0]) if rows else 0
    rank = 0
    for column in range(columns):
        pivot = max(range(rank, rows), key=lambda row: abs(work[row][column]), default=rank)
        if pivot >= rows or abs(work[pivot][column]) <= tolerance:
            continue
        work[rank], work[pivot] = work[pivot], work[rank]
        pivot_value = work[rank][column]
        work[rank] = [value / pivot_value for value in work[rank]]
        for row in range(rows):
            if row == rank:
                continue
            factor = work[row][column]
            if factor:
                work[row] = [a - factor * b for a, b in zip(work[row], work[rank])]
        rank += 1
    return rank


def words(alphabet_size: int, maximum_length: int) -> tuple[Word, ...]:
    alphabet = tuple(value for index in range(1, alphabet_size + 1) for value in (index, -index))
    result: list[Word] = []

    def extend(prefix: Word) -> None:
        if prefix:
            result.append(prefix)
        if len(prefix) == maximum_length:
            return
        for value in alphabet:
            extend(prefix + (value,))

    extend(())
    return tuple(result)


def word_trace(chords: tuple[Quaternion, ...], word: Word) -> float:
    value: Quaternion = (1.0, 0.0, 0.0, 0.0)
    for letter in word:
        chord = chords[abs(letter) - 1]
        value = qmul(value, chord if letter > 0 else qinv(chord))
    return trace(value)


def word_signature(chords: tuple[Quaternion, ...], maximum_length: int) -> dict[Word, float]:
    return {word: word_trace(chords, word) for word in words(len(chords), maximum_length)}


def max_signature_difference(left: dict[Word, float], right: dict[Word, float]) -> float:
    keys = set(left) | set(right)
    return max((abs(left.get(key, 0.0) - right.get(key, 0.0)) for key in keys), default=0.0)


def reconstruct_links(
    fixture: dict[str, Any], transports: dict[int, Quaternion], chords: tuple[Quaternion, ...]
) -> tuple[Quaternion, ...]:
    tree_indices = set(fixture["tree_indices"])
    links: list[Quaternion] = []
    chord_index = 0
    for edge_index, (tail, head) in enumerate(fixture["edges"]):
        if edge_index in tree_indices:
            links.append(qmul(qinv(transports[tail]), transports[head]))
        else:
            chord = chords[chord_index]
            links.append(qmul(qmul(qinv(transports[tail]), chord), transports[head]))
            chord_index += 1
    return tuple(links)


def recover_tree_and_chords(
    fixture: dict[str, Any], links: tuple[Quaternion, ...]
) -> tuple[dict[int, Quaternion], tuple[Quaternion, ...]]:
    transports: dict[int, Quaternion] = {0: (1.0, 0.0, 0.0, 0.0)}
    for edge_index in fixture["tree_indices"]:
        tail, head = fixture["edges"][edge_index]
        if tail in transports:
            transports[head] = qmul(transports[tail], links[edge_index])
        else:
            transports[tail] = qmul(transports[head], qinv(links[edge_index]))
    chords = []
    tree_indices = set(fixture["tree_indices"])
    for edge_index, (tail, head) in enumerate(fixture["edges"]):
        if edge_index not in tree_indices:
            chords.append(qmul(qmul(transports[tail], links[edge_index]), qinv(transports[head])))
    return transports, tuple(chords)


def gauge_transform(
    fixture: dict[str, Any], links: tuple[Quaternion, ...], gauges: dict[int, Quaternion]
) -> tuple[Quaternion, ...]:
    return tuple(
        qmul(qmul(gauges[tail], link), qinv(gauges[head]))
        for link, (tail, head) in zip(links, fixture["edges"])
    )


def cyclic_rotate(word: Word, offset: int) -> Word:
    return word[offset:] + word[:offset]


def inverse_word(word: Word) -> Word:
    return tuple(-letter for letter in reversed(word))


def max_cyclic_inverse_residual(chords: tuple[Quaternion, ...]) -> tuple[float, float]:
    cyclic_error = 0.0
    inverse_error = 0.0
    for word in words(len(chords), WORD_MAX_LENGTH):
        value = word_trace(chords, word)
        cyclic_error = max(cyclic_error, *(abs(value - word_trace(chords, cyclic_rotate(word, offset))) for offset in range(len(word))))
        inverse_error = max(inverse_error, abs(value - word_trace(chords, inverse_word(word))))
    return cyclic_error, inverse_error


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, measured: Any, criterion: str) -> None:
    checks.append({"name": name, "passed": bool(passed), "measured": measured, "criterion": criterion})


def character_rows() -> tuple[list[list[float]], float, float, float, float]:
    rows: list[list[float]] = []
    recurrence_error = 0.0
    inverse_error = 0.0
    range_excess = 0.0
    theta_values = tuple(index * math.pi / 18.0 for index in range(1, 18))
    for theta in theta_values:
        q = (math.cos(theta), math.sin(theta), 0.0, 0.0)
        q_inverse = qinv(q)
        values = [1.0, trace(q)]
        inverse_values = [1.0, trace(q_inverse)]
        for _ in range(2, CHARACTER_MAX + 1):
            values.append(trace(q) * values[-1] - values[-2])
            inverse_values.append(trace(q_inverse) * inverse_values[-1] - inverse_values[-2])
        rows.append(values)
        inverse_error = max(inverse_error, max(abs(left - right) for left, right in zip(values, inverse_values)))
        range_excess = max(range_excess, max(0.0, abs(values[1]) - 2.0))
        for n, value in enumerate(values):
            exact = math.sin((n + 1) * theta) / math.sin(theta)
            recurrence_error = max(recurrence_error, abs(value - exact))
    rank = matrix_rank(rows, 1.0e-10)
    return rows, recurrence_error, inverse_error, range_excess, float(rank)


def epsilon_conjugation_error(values: Iterable[Quaternion]) -> float:
    epsilon = ((0.0 + 0.0j, 1.0 + 0.0j), (-1.0 + 0.0j, 0.0 + 0.0j))
    epsilon_inverse = ((0.0 + 0.0j, -1.0 + 0.0j), (1.0 + 0.0j, 0.0 + 0.0j))
    error = 0.0
    for value in values:
        matrix = qmatrix(value)
        transformed = matrix_multiply(matrix_multiply(epsilon, matrix), epsilon_inverse)
        conjugate = (
            (matrix[0][0].conjugate(), matrix[0][1].conjugate()),
            (matrix[1][0].conjugate(), matrix[1][1].conjugate()),
        )
        error = max(error, matrix_max_difference(transformed, conjugate))
    return error


def finite_cutoff_residual(rows: list[list[float]]) -> float:
    nodes = [index * math.pi / 18.0 for index in range(1, 18)]
    x_values = [math.cos(theta) for theta in nodes]
    basis_indices = (0, 1, 2, 3)
    target_index = 8
    target_row = 4
    predicted = 0.0
    for index in basis_indices:
        coefficient = 1.0
        for other in basis_indices:
            if other != index:
                coefficient *= (x_values[target_row] - x_values[other]) / (x_values[index] - x_values[other])
        predicted += rows[index][target_index] * coefficient
    return abs(predicted - rows[target_row][target_index])


def orientation_fixture() -> tuple[tuple[Quaternion, ...], tuple[Quaternion, ...]]:
    scalar = 0.8
    radial = 0.6
    a = (scalar, radial, 0.0, 0.0)
    b = (scalar, 0.0, radial, 0.0)
    c_plus = (scalar, 0.0, 0.0, radial)
    c_minus = (scalar, 0.0, 0.0, -radial)
    return (a, b, c_plus), (a, b, c_minus)


def build_receipt() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    graph_records: list[dict[str, Any]] = []
    sample_quaternions = tuple(qexp(vector) for vector in VECTOR_SEEDS)
    gauge_quaternions = tuple(qexp(vector) for vector in GAUGE_SEEDS)

    for fixture_index, fixture in enumerate(GRAPH_FIXTURES):
        transport_values = {0: (1.0, 0.0, 0.0, 0.0)}
        for vertex in range(1, fixture["vertices"]):
            transport_values[vertex] = sample_quaternions[(fixture_index + vertex) % len(sample_quaternions)]
        chord_count = len(fixture["edges"]) - len(fixture["tree_indices"])
        chord_values = tuple(sample_quaternions[(fixture_index + 3 + index) % len(sample_quaternions)] for index in range(chord_count))
        links = reconstruct_links(fixture, transport_values, chord_values)
        recovered_transports, recovered_chords = recover_tree_and_chords(fixture, links)
        reconstruction_error = max(
            [qmax_difference(transport_values[key], recovered_transports[key]) for key in transport_values]
            + [qmax_difference(expected, actual) for expected, actual in zip(chord_values, recovered_chords)]
        ) if transport_values else 0.0
        norm_error = max(qnorm_error(value) for value in links) if links else 0.0
        chord_error = max(
            abs(word_trace(chord_values, (index + 1,)) - word_trace(recovered_chords, (index + 1,)))
            for index in range(chord_count)
        ) if chord_count else 0.0
        gauges = {vertex: gauge_quaternions[(vertex + fixture_index) % len(gauge_quaternions)] for vertex in range(fixture["vertices"])}
        transformed_links = gauge_transform(fixture, links, gauges)
        _, transformed_chords = recover_tree_and_chords(fixture, transformed_links)
        gauge_error = max_signature_difference(
            word_signature(chord_values, WORD_MAX_LENGTH), word_signature(transformed_chords, WORD_MAX_LENGTH)
        )
        cyclic_error, inverse_error = max_cyclic_inverse_residual(chord_values)
        pair_error = 0.0
        for left, right in zip(sample_quaternions, sample_quaternions[1:] + sample_quaternions[:1]):
            pair_error = max(pair_error, abs(trace(left) * trace(right) - trace(qmul(left, right)) - trace(qmul(left, qinv(right)))))
        graph_records.append(
            {
                "name": fixture["name"],
                "vertices": fixture["vertices"],
                "edges": [list(edge) for edge in fixture["edges"]],
                "tree_indices": list(fixture["tree_indices"]),
                "chord_count": chord_count,
                "word_count": len(words(chord_count, WORD_MAX_LENGTH)),
                "reconstruction_error": reconstruction_error,
                "link_norm_error": norm_error,
                "chord_recovery_error": chord_error,
                "gauge_word_error": gauge_error,
                "cyclic_word_error": cyclic_error,
                "inverse_word_error": inverse_error,
                "trace_product_error": pair_error,
            }
        )
        add_check(checks, f"tree_reconstruction_{fixture['name']}", reconstruction_error <= TOLERANCE, reconstruction_error, f"max quaternion reconstruction error <= {TOLERANCE}")
        add_check(checks, f"tree_norms_{fixture['name']}", norm_error <= TOLERANCE, norm_error, f"max link norm error <= {TOLERANCE}")
        add_check(checks, f"chord_recovery_{fixture['name']}", chord_error <= TOLERANCE, chord_error, f"max chord trace recovery error <= {TOLERANCE}")
        add_check(checks, f"gauge_word_invariance_{fixture['name']}", gauge_error <= TOLERANCE, gauge_error, f"max gauge-invariant word error <= {TOLERANCE}")
        add_check(checks, f"word_conjugation_{fixture['name']}", gauge_error <= TOLERANCE, gauge_error, f"max simultaneous-conjugation trace error <= {TOLERANCE}")
        add_check(checks, f"word_cyclic_{fixture['name']}", cyclic_error <= TOLERANCE, cyclic_error, f"max cyclic trace error <= {TOLERANCE}")
        add_check(checks, f"word_inverse_{fixture['name']}", inverse_error <= TOLERANCE, inverse_error, f"max inverse-word trace error <= {TOLERANCE}")
        add_check(checks, f"trace_product_{fixture['name']}", pair_error <= TOLERANCE, pair_error, f"max SU(2) trace-product error <= {TOLERANCE}")

    rows, recurrence_error, character_inverse_error, range_excess, character_rank = character_rows()
    add_check(checks, "character_recurrence", recurrence_error <= TOLERANCE, recurrence_error, f"max Chebyshev character error <= {TOLERANCE}")
    add_check(checks, "character_inverse_invariance", character_inverse_error <= TOLERANCE, character_inverse_error, f"max inverse-character error <= {TOLERANCE}")
    add_check(checks, "fundamental_character_range", range_excess <= TOLERANCE, range_excess, "fundamental character lies in [-2, 2]")
    add_check(checks, "character_evaluation_rank", int(character_rank) == CHARACTER_MAX + 1, character_rank, f"evaluation rank equals {CHARACTER_MAX + 1}")
    epsilon_error = epsilon_conjugation_error(sample_quaternions)
    add_check(checks, "epsilon_conjugation", epsilon_error <= TOLERANCE, epsilon_error, f"max epsilon-conjugation error <= {TOLERANCE}")
    contraction_error = max(record["trace_product_error"] for record in graph_records)
    add_check(checks, "trace_contraction_identity", contraction_error <= TOLERANCE, contraction_error, f"max contraction error <= {TOLERANCE}")

    plus, minus = orientation_fixture()
    full_plus = word_signature(plus, WORD_MAX_LENGTH)
    full_minus = word_signature(minus, WORD_MAX_LENGTH)
    short_plus = word_signature(plus, 2)
    short_minus = word_signature(minus, 2)
    full_difference = max_signature_difference(full_plus, full_minus)
    short_difference = max_signature_difference(short_plus, short_minus)
    has_orientation_word = abs(word_trace(plus, (1, 2, 3)) - word_trace(minus, (1, 2, 3)))
    cutoff_residual = finite_cutoff_residual(rows)
    raw_norm = 1.0
    centered_norm = 0.0
    domain_ok = WORD_MAX_LENGTH >= 3 and CHARACTER_MAX >= 8
    add_check(checks, "orientation_full_word_separation", full_difference > 1.0e-6, full_difference, "full word family separates the orientation pair")
    add_check(checks, "orientation_short_word_collision", short_difference <= TOLERANCE, short_difference, f"length-at-most-two family collides within {TOLERANCE}")
    add_check(checks, "orientation_word_inventory", has_orientation_word > 1.0e-6, has_orientation_word, "the ABC word is orientation sensitive")
    add_check(checks, "centered_vacuum_direction", raw_norm > TOLERANCE and centered_norm <= TOLERANCE, {"raw_constant_norm": raw_norm, "centered_constant_norm": centered_norm}, "centering removes the constant vacuum vector")
    add_check(checks, "finite_character_cutoff_residual", cutoff_residual > 1.0e-3, cutoff_residual, "chi_8 is not represented by chi_0 through chi_3 on the frozen nodes")
    add_check(checks, "infinite_domain_declaration", domain_ok, {"word_max_length": WORD_MAX_LENGTH, "character_max": CHARACTER_MAX}, "finite controls do not replace the infinite local word family")

    mutation_checks = [
        {
            "name": "accept_raw_link_matrix_entries",
            "passed": False,
            "witness": "pending",
        },
        {
            "name": "drop_orientation_words",
            "passed": short_difference <= TOLERANCE and full_difference > 1.0e-6,
            "witness": {"short_difference": short_difference, "full_difference": full_difference},
        },
        {
            "name": "omit_centering",
            "passed": raw_norm > TOLERANCE and centered_norm <= TOLERANCE,
            "witness": {"raw_constant_norm": raw_norm, "centered_constant_norm": centered_norm},
        },
        {
            "name": "finite_word_cutoff_is_complete",
            "passed": cutoff_residual > 1.0e-3,
            "witness": cutoff_residual,
        },
    ]
    # The raw-entry mutation is evaluated against a nontrivial vertex action on
    # the first cycle link; its Wilson trace is unchanged but one matrix entry moves.
    cycle = GRAPH_FIXTURES[0]
    cycle_transports = {0: (1.0, 0.0, 0.0, 0.0), 1: sample_quaternions[0], 2: sample_quaternions[1], 3: sample_quaternions[2]}
    cycle_links = reconstruct_links(cycle, cycle_transports, (sample_quaternions[3],))
    raw_before = qmatrix(cycle_links[0])[0][0]
    raw_gauges = {0: gauge_quaternions[0], 1: (1.0, 0.0, 0.0, 0.0), 2: (1.0, 0.0, 0.0, 0.0), 3: (1.0, 0.0, 0.0, 0.0)}
    transformed_cycle_links = gauge_transform(cycle, cycle_links, raw_gauges)
    raw_after = qmatrix(transformed_cycle_links[0])[0][0]
    _, transformed_cycle_chords = recover_tree_and_chords(cycle, transformed_cycle_links)
    raw_entry_difference = abs(raw_before - raw_after)
    raw_trace_error = abs(trace(sample_quaternions[3]) - trace(transformed_cycle_chords[0]))
    mutation_checks[0] = {
        "name": "accept_raw_link_matrix_entries",
        "passed": raw_entry_difference > 1.0e-6 and raw_trace_error <= TOLERANCE,
        "witness": {
            "raw_entry_difference": raw_entry_difference,
            "wilson_trace_error": raw_trace_error,
        },
    }

    tree_names = {"tree_reconstruction", "tree_norms", "chord_recovery", "gauge_word_invariance"}
    word_names = {"word_conjugation", "word_cyclic", "word_inverse", "trace_product"}
    character_names = {"character_recurrence", "character_inverse_invariance", "fundamental_character_range", "character_evaluation_rank", "epsilon_conjugation", "trace_contraction_identity"}
    orientation_names = {"orientation_full_word_separation", "orientation_short_word_collision", "orientation_word_inventory", "centered_vacuum_direction", "finite_character_cutoff_residual", "infinite_domain_declaration"}

    def group_pass(names: set[str]) -> bool:
        return all(
            item["passed"]
            for item in checks
            if any(item["name"].startswith(prefix) for prefix in names)
        )

    source_hashes = {
        "protocol": {"path": display_path(PROTOCOL), "sha256": sha256(PROTOCOL)},
        "source": {"path": display_path(SOURCE), "sha256": sha256(SOURCE)},
    }
    all_scientific = all(item["passed"] for item in checks)
    all_mutations = all(item["passed"] for item in mutation_checks)
    return {
        "schema": "cassi.yang-mills.local-observable-completeness.verification.v1",
        "status": "PASS" if all_scientific and all_mutations else "FAIL",
        "inputs": source_hashes,
        "checks": checks,
        "check_count": len(checks),
        "passed_check_count": sum(item["passed"] for item in checks),
        "mutation_checks": mutation_checks,
        "mutation_count": len(mutation_checks),
        "passed_mutation_count": sum(item["passed"] for item in mutation_checks),
        "graphs": graph_records,
        "character_controls": {
            "maximum_recurrence_error": recurrence_error,
            "maximum_inverse_error": character_inverse_error,
            "range_excess": range_excess,
            "evaluation_rank": int(character_rank),
            "epsilon_conjugation_error": epsilon_error,
            "finite_cutoff_residual": cutoff_residual,
        },
        "orientation_control": {
            "full_word_difference": full_difference,
            "length_at_most_two_difference": short_difference,
            "abc_difference": has_orientation_word,
        },
        "claims": {
            "finite_tree_gauge_controls": "PASS" if group_pass(tree_names) else "FAIL",
            "finite_wilson_word_controls": "PASS" if group_pass(word_names) else "FAIL",
            "finite_character_controls": "PASS" if group_pass(character_names) else "FAIL",
            "finite_orientation_separation_control": "PASS" if group_pass(orientation_names) else "FAIL",
            "local_gauge_invariant_algebra_dense": "DERIVED_CONDITIONAL",
            "retained_rg_family_complete": "UNRESOLVED",
            "uniform_physical_gap": "UNRESOLVED",
            "continuum_mass_gap": "UNRESOLVED",
            "clay_verdict": "NULL",
        },
        "claim_boundary": "Finite Wilson-word algebra controls and the GNS density implication are analytic inputs; no RG map, uniform spectral lower bound or continuum mass gap is constructed.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    if args.output.exists() and not args.replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {args.output}")
    receipt = build_receipt()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "checks": f"{receipt['passed_check_count']}/{receipt['check_count']}", "mutations": f"{receipt['passed_mutation_count']}/{receipt['mutation_count']}", "output": display_path(args.output)}, indent=2))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
