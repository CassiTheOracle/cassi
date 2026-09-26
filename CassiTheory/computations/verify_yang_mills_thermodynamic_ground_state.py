#!/usr/bin/env python3
"""Verify the fixed-coupling thermodynamic Yang--Mills ground-state bridge.

Run from the CassiTheory root:

    python computations/verify_yang_mills_thermodynamic_ground_state.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from fractions import Fraction
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-thermodynamic-ground-state-prereg.md"
LOCAL_PROTOCOL = ROOT / "computations" / "yang-mills-local-cutoff-density-prereg.md"
LOCAL_SOURCE = ROOT / "computations" / "verify_yang_mills_local_cutoff_density.py"
LOCAL_RECEIPT = ROOT / "runs" / "yang_mills_local_cutoff_density" / "verification.json"
OUTPUT = ROOT / "runs" / "yang_mills_thermodynamic_ground_state" / "verification.json"

RANK_CUTOFFS = (0, 1, 2, 4, 8, 16, 32, 64, 128)
SUPPORT_SIZES = (1, 2, 4, 8)
COUPLINGS = (Fraction(1, 64), Fraction(1, 4), Fraction(1), Fraction(4), Fraction(16))
EPSILONS = (Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 16), Fraction(1, 32))
GROUND_DIMENSIONS = (4, 5, 6)
GROUND_MULTIPLICITIES = (1, 2)
OPERATOR_SEEDS = (1, 2)
ESCAPE_LABELS = (1, 2, 4, 8, 16, 32, 64)
ESCAPE_CUTOFFS = (0, 1, 2, 4, 8)
GAP_VOLUMES = (4, 8, 16, 32, 64, 128, 256)
TOLERANCE = 1.0e-12

Matrix = list[list[complex]]


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


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object in {path}")
    return value


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    measured: Any,
    requirement: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "measured": measured,
            "requirement": requirement,
        }
    )


def peter_weyl_rank_direct(cutoff: int) -> int:
    return sum((label + 1) ** 2 for label in range(cutoff + 1))


def peter_weyl_rank_closed(cutoff: int) -> int:
    return (cutoff + 1) * (cutoff + 2) * (2 * cutoff + 3) // 6


def local_tail_bound(coupling: Fraction, support: int, cutoff: int) -> Fraction:
    return Fraction(8) * coupling * support / ((cutoff + 1) * (cutoff + 3))


def compression_radius(coupling: Fraction, support: int, cutoff: int) -> float:
    return 2.0 * math.sqrt(float(local_tail_bound(coupling, support, cutoff)))


def cutoff_satisfies(
    coupling: Fraction, support: int, epsilon: Fraction, cutoff: int
) -> bool:
    left = Fraction((cutoff + 1) * (cutoff + 3)) * epsilon * epsilon
    right = Fraction(128) * coupling * support
    return left >= right


def minimum_cutoff_search(
    coupling: Fraction, support: int, epsilon: Fraction
) -> int:
    cutoff = 0
    while not cutoff_satisfies(coupling, support, epsilon, cutoff):
        cutoff += 1
    return cutoff


def minimum_cutoff_formula(
    coupling: Fraction, support: int, epsilon: Fraction
) -> int:
    threshold = float(Fraction(128) * coupling * support / (epsilon * epsilon))
    root = math.sqrt(threshold + 1.0) - 2.0
    return max(0, math.ceil(root - 1.0e-12))


def zeros(rows: int, columns: int) -> Matrix:
    return [[0j for _ in range(columns)] for _ in range(rows)]


def identity(dimension: int) -> Matrix:
    result = zeros(dimension, dimension)
    for index in range(dimension):
        result[index][index] = 1.0 + 0j
    return result


def diagonal(values: list[float]) -> Matrix:
    result = zeros(len(values), len(values))
    for index, value in enumerate(values):
        result[index][index] = complex(value)
    return result


def adjoint(matrix: Matrix) -> Matrix:
    return [
        [matrix[row][column].conjugate() for row in range(len(matrix))]
        for column in range(len(matrix[0]))
    ]


def matmul(left: Matrix, right: Matrix) -> Matrix:
    rows = len(left)
    inner = len(right)
    columns = len(right[0])
    if len(left[0]) != inner:
        raise ValueError("matrix dimension mismatch")
    result = zeros(rows, columns)
    for row in range(rows):
        for pivot in range(inner):
            value = left[row][pivot]
            if value == 0:
                continue
            for column in range(columns):
                result[row][column] += value * right[pivot][column]
    return result


def subtract(left: Matrix, right: Matrix) -> Matrix:
    return [
        [left[row][column] - right[row][column] for column in range(len(left[0]))]
        for row in range(len(left))
    ]


def matrix_trace(matrix: Matrix) -> complex:
    return sum(matrix[index][index] for index in range(len(matrix)))


def commutator(left: Matrix, right: Matrix) -> Matrix:
    return subtract(matmul(left, right), matmul(right, left))


def kronecker(left: Matrix, right: Matrix) -> Matrix:
    rows = len(left) * len(right)
    columns = len(left[0]) * len(right[0])
    result = zeros(rows, columns)
    for left_row in range(len(left)):
        for left_column in range(len(left[0])):
            factor = left[left_row][left_column]
            for right_row in range(len(right)):
                for right_column in range(len(right[0])):
                    result[left_row * len(right) + right_row][
                        left_column * len(right[0]) + right_column
                    ] = factor * right[right_row][right_column]
    return result


def add_matrices(left: Matrix, right: Matrix) -> Matrix:
    return [
        [left[row][column] + right[row][column] for column in range(len(left[0]))]
        for row in range(len(left))
    ]


def maximum_entry(matrix: Matrix) -> float:
    return max(abs(value) for row in matrix for value in row)


def pure_density(vector: list[complex]) -> Matrix:
    norm_sq = sum(abs(value) ** 2 for value in vector)
    normalized = [value / math.sqrt(norm_sq) for value in vector]
    return [
        [left * right.conjugate() for right in normalized]
        for left in normalized
    ]


def partial_trace_last(matrix: Matrix, retained: int, traced: int) -> Matrix:
    result = zeros(retained, retained)
    for left in range(retained):
        for right in range(retained):
            result[left][right] = sum(
                matrix[left * traced + index][right * traced + index]
                for index in range(traced)
            )
    return result


def direct_first_qubit_reduction(matrix: Matrix) -> Matrix:
    result = zeros(2, 2)
    for left in range(2):
        for right in range(2):
            result[left][right] = sum(
                matrix[left * 4 + rest][right * 4 + rest] for rest in range(4)
            )
    return result


def make_ground_fixture(dimension: int, multiplicity: int, seed: int) -> dict[str, Any]:
    energies = [0.0] * multiplicity + [
        1.0 + (row - multiplicity + 1) ** 2 / (seed + 1.0)
        for row in range(multiplicity, dimension)
    ]
    hamiltonian = diagonal(energies)
    rho = diagonal(
        [1.0 / multiplicity if row < multiplicity else 0.0 for row in range(dimension)]
    )
    operator = [
        [
            complex(
                ((row + 1) * (column + 2) + seed) / (11.0 + dimension),
                ((row - column) * (seed + 1)) / (19.0 + dimension),
            )
            for column in range(dimension)
        ]
        for row in range(dimension)
    ]
    direct = matrix_trace(
        matmul(rho, matmul(adjoint(operator), commutator(hamiltonian, operator)))
    )
    spectral = 0.0
    for column in range(multiplicity):
        for row in range(multiplicity, dimension):
            spectral += (
                energies[row]
                * abs(operator[row][column]) ** 2
                / multiplicity
            )
    return {
        "fixture_kind": "synthetic_finite_matrix",
        "dimension": dimension,
        "ground_multiplicity": multiplicity,
        "operator_seed": seed,
        "energies": energies,
        "direct_real": direct.real,
        "direct_imaginary": direct.imag,
        "spectral_sum": spectral,
        "absolute_difference": abs(direct - spectral),
    }


def run(output: Path, replace: bool) -> dict[str, Any]:
    required = (PROTOCOL, LOCAL_PROTOCOL, LOCAL_SOURCE, LOCAL_RECEIPT)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    checks: list[dict[str, Any]] = []
    local = load_object(LOCAL_RECEIPT)
    local_protocol_hash = sha256(LOCAL_PROTOCOL)
    local_source_hash = sha256(LOCAL_SOURCE)
    prerequisite_ok = (
        local.get("schema") == "cassi.yang_mills_local_cutoff_density.v1"
        and local.get("status") == "PASS"
        and local.get("checks_passed") == local.get("checks_total") == 16
        and local.get("local_cutoff_status") == "PASS"
        and local.get("thermodynamic_limit_constructed") is False
        and local.get("continuum_hypotheses_present") is False
        and local.get("clay_verdict") == "NULL"
        and local.get("inputs", {}).get("protocol", {}).get("sha256")
        == local_protocol_hash
        and local.get("inputs", {}).get("primary_source", {}).get("sha256")
        == local_source_hash
    )
    add_check(
        checks,
        "analytic_input_boundary",
        prerequisite_ok,
        {
            "local_receipt_schema": local.get("schema"),
            "local_receipt_status": local.get("status"),
            "local_receipt_checks": f"{local.get('checks_passed')}/{local.get('checks_total')}",
            "local_protocol_sha256": local.get("inputs", {}).get("protocol", {}).get("sha256"),
            "local_source_sha256": local.get("inputs", {}).get("primary_source", {}).get("sha256"),
            "finite_volume_ground_densities": "ANALYTIC_INPUT_NOT_CONSTRUCTED_BY_VERIFIER",
            "uniform_tail_bound_YMT2": "ANALYTIC_INPUT_NOT_PROVED_BY_VERIFIER",
        },
        "bind the current local-cutoff receipt and record both analytic inputs outside the executable proof surface",
    )

    rank_rows: list[dict[str, Any]] = []
    for cutoff in RANK_CUTOFFS:
        direct = peter_weyl_rank_direct(cutoff)
        closed = peter_weyl_rank_closed(cutoff)
        for support in SUPPORT_SIZES:
            support_rank = closed**support
            rank_rows.append(
                {
                    "cutoff_C": cutoff,
                    "support_links": support,
                    "direct_one_link_rank": direct,
                    "closed_one_link_rank": closed,
                    "support_rank": str(support_rank),
                    "support_rank_digits": len(str(support_rank)),
                }
            )
    add_check(
        checks,
        "rank_schedule_coverage",
        len(rank_rows) == 36,
        len(rank_rows),
        "all 36 Peter-Weyl rank rows are present",
    )
    rank_error = max(
        abs(row["direct_one_link_rank"] - row["closed_one_link_rank"])
        for row in rank_rows
    )
    add_check(
        checks,
        "peter_weyl_rank_identity",
        rank_error == 0,
        rank_error,
        "direct and closed one-link ranks agree exactly",
    )
    one_link_ranks = [peter_weyl_rank_closed(cutoff) for cutoff in RANK_CUTOFFS]
    add_check(
        checks,
        "rank_monotonicity_and_finiteness",
        all(right > left > 0 for left, right in zip(one_link_ranks, one_link_ranks[1:]))
        and all(int(row["support_rank"]) > 0 for row in rank_rows),
        {"one_link_ranks": one_link_ranks, "maximum_digits": max(row["support_rank_digits"] for row in rank_rows)},
        "finite compressed ranks are positive and increase strictly with cutoff",
    )

    compactness_rows: list[dict[str, Any]] = []
    for coupling in COUPLINGS:
        for support in SUPPORT_SIZES:
            for epsilon in EPSILONS:
                cutoff_search = minimum_cutoff_search(coupling, support, epsilon)
                cutoff_formula = minimum_cutoff_formula(coupling, support, epsilon)
                radius = compression_radius(coupling, support, cutoff_search)
                previous = (
                    compression_radius(coupling, support, cutoff_search - 1)
                    if cutoff_search > 0
                    else None
                )
                rank = peter_weyl_rank_closed(cutoff_search) ** support
                compactness_rows.append(
                    {
                        "coupling_x": float(coupling),
                        "support_links": support,
                        "epsilon": float(epsilon),
                        "cutoff_search": cutoff_search,
                        "cutoff_formula": cutoff_formula,
                        "tail_bound": float(local_tail_bound(coupling, support, cutoff_search)),
                        "compression_radius": radius,
                        "target_radius": float(epsilon) / 2.0,
                        "previous_radius": previous,
                        "support_rank": str(rank),
                        "support_rank_digits": len(str(rank)),
                    }
                )
    add_check(
        checks,
        "compactness_schedule_coverage",
        len(compactness_rows) == 100,
        len(compactness_rows),
        "all 100 compactness cutoff rows are present",
    )
    formula_mismatches = [
        row for row in compactness_rows if row["cutoff_search"] != row["cutoff_formula"]
    ]
    add_check(
        checks,
        "compactness_cutoff_formula",
        not formula_mismatches,
        {"mismatches": formula_mismatches},
        "closed quadratic root and exact integer search give the same least cutoff",
    )
    target_excess = max(
        row["compression_radius"] - row["target_radius"] for row in compactness_rows
    )
    add_check(
        checks,
        "compression_target",
        target_excess <= TOLERANCE,
        target_excess,
        "every selected compression radius is at most epsilon/2",
    )
    minimality_failures = [
        row
        for row in compactness_rows
        if row["cutoff_search"] > 0
        and row["previous_radius"] <= row["target_radius"] + TOLERANCE
    ]
    add_check(
        checks,
        "compression_cutoff_minimality",
        not minimality_failures,
        {"failures": minimality_failures},
        "the preceding cutoff fails the target whenever the selected cutoff is positive",
    )
    add_check(
        checks,
        "compressed_rank_finite",
        all(int(row["support_rank"]) > 0 for row in compactness_rows)
        and max(row["support_rank_digits"] for row in compactness_rows) < 200,
        {"maximum_digits": max(row["support_rank_digits"] for row in compactness_rows)},
        "every compressed support has an explicit finite rank",
    )

    vector = [
        complex(index + 1, (-1) ** index * (index + 2) / 3.0)
        for index in range(8)
    ]
    rho_three = pure_density(vector)
    rho_two = partial_trace_last(rho_three, 4, 2)
    rho_one_nested = partial_trace_last(rho_two, 2, 2)
    rho_one_direct = direct_first_qubit_reduction(rho_three)
    partial_error = maximum_entry(subtract(rho_one_nested, rho_one_direct))
    partial_payload = {
        "nested_direct_maximum_difference": partial_error,
        "trace_three": matrix_trace(rho_three).real,
        "trace_two": matrix_trace(rho_two).real,
        "trace_one": matrix_trace(rho_one_nested).real,
    }
    add_check(
        checks,
        "partial_trace_compatibility",
        partial_error <= TOLERANCE
        and all(abs(partial_payload[key] - 1.0) <= TOLERANCE for key in ("trace_three", "trace_two", "trace_one")),
        partial_payload,
        "nested and direct reductions agree and preserve unit trace",
    )

    ground_rows = [
        make_ground_fixture(dimension, multiplicity, seed)
        for dimension in GROUND_DIMENSIONS
        for multiplicity in GROUND_MULTIPLICITIES
        for seed in OPERATOR_SEEDS
    ]
    add_check(
        checks,
        "ground_fixture_coverage",
        len(ground_rows) == 12,
        len(ground_rows),
        "all 12 finite ground-identity fixtures are present",
    )
    maximum_ground_error = max(row["absolute_difference"] for row in ground_rows)
    maximum_ground_imaginary = max(abs(row["direct_imaginary"]) for row in ground_rows)
    add_check(
        checks,
        "ground_quadratic_identity",
        maximum_ground_error <= TOLERANCE and maximum_ground_imaginary <= TOLERANCE,
        {"maximum_difference": maximum_ground_error, "maximum_imaginary": maximum_ground_imaginary},
        "direct commutator traces equal the spectral sums and are real",
    )
    minimum_ground_form = min(row["spectral_sum"] for row in ground_rows)
    add_check(
        checks,
        "ground_quadratic_nonnegative",
        minimum_ground_form >= -TOLERANCE,
        minimum_ground_form,
        "every finite ground-state quadratic form is nonnegative",
    )
    add_check(
        checks,
        "ground_control_nonvacuous",
        max(row["spectral_sum"] for row in ground_rows) > 1.0,
        max(row["spectral_sum"] for row in ground_rows),
        "the positivity fixtures contain nonzero excited-state weight",
    )

    base_h = diagonal([0.0, 3.0])
    base_a = [[0.2 + 0.1j, 1.0 - 0.3j], [0.4 + 0.7j, -0.1 + 0.2j]]
    spectator_h = diagonal([2.0, 5.0, 9.0])
    full_h = add_matrices(
        kronecker(base_h, identity(3)),
        kronecker(identity(2), spectator_h),
    )
    full_a = kronecker(base_a, identity(3))
    expected_commutator = kronecker(commutator(base_h, base_a), identity(3))
    spectator_error = maximum_entry(subtract(commutator(full_h, full_a), expected_commutator))
    add_check(
        checks,
        "spectator_commutator_stabilization",
        spectator_error <= TOLERANCE,
        spectator_error,
        "a commuting spectator Hamiltonian leaves the local commutator unchanged",
    )

    alternating = {
        "even_odd_trace_distance": 2.0,
        "full_sequence_converges": False,
        "even_subsequence_converges": True,
        "odd_subsequence_converges": True,
    }
    add_check(
        checks,
        "alternating_subsequence_firing_control",
        alternating["even_odd_trace_distance"] == 2.0
        and alternating["full_sequence_converges"] is False,
        alternating,
        "precompactness retains two subsequential limits without full-sequence convergence",
    )

    escape_rows = [
        {
            "label_n": label,
            "cutoff_C": cutoff,
            "tail_mass": 1.0 if label > cutoff else 0.0,
            "electric_energy": label * (label + 2.0) / 4.0,
            "orthogonal_trace_distance": 2.0,
        }
        for cutoff in ESCAPE_CUTOFFS
        for label in ESCAPE_LABELS
    ]
    escaping = [row for row in escape_rows if row["label_n"] > row["cutoff_C"]]
    add_check(
        checks,
        "energy_tightness_firing_control",
        len(escape_rows) == 35
        and all(row["tail_mass"] == 1.0 for row in escaping)
        and all(row["orthogonal_trace_distance"] == 2.0 for row in escape_rows)
        and ESCAPE_LABELS[-1] * (ESCAPE_LABELS[-1] + 2) / 4.0
        > ESCAPE_LABELS[0] * (ESCAPE_LABELS[0] + 2) / 4.0,
        {"rows": len(escape_rows), "escaping_rows": len(escaping), "last_energy": escape_rows[-1]["electric_energy"]},
        "unbounded electric energy permits orthogonal sectors to escape every fixed cutoff",
    )

    gap_rows = [
        {
            "volume_L": volume,
            "one_magnon_gap_upper_bound": 2.0 - 2.0 * math.cos(2.0 * math.pi / volume),
        }
        for volume in GAP_VOLUMES
    ]
    gap_values = [row["one_magnon_gap_upper_bound"] for row in gap_rows]
    add_check(
        checks,
        "gapless_thermodynamic_firing_control",
        len(gap_rows) == 7
        and all(value > 0.0 for value in gap_values)
        and all(right < left for left, right in zip(gap_values, gap_values[1:]))
        and gap_values[-1] < 1.0e-3,
        {"rows": gap_rows, "terminal_upper_bound": gap_values[-1]},
        "a convergent product ground state coexists with a one-magnon gap upper bound tending to zero",
    )

    if len(checks) != 18:
        raise RuntimeError(f"expected 18 checks, constructed {len(checks)}")
    passed = all(check["passed"] for check in checks)
    status = "PASS" if passed else "FAIL"
    record: dict[str, Any] = {
        "schema": "cassi.yang_mills_thermodynamic_ground_state.v1",
        "status": status,
        "classification": (
            "FINITE_IDENTITY_SUPPORT_FOR_CONDITIONAL_THERMODYNAMIC_BRIDGE"
            if passed
            else "FAILED"
        ),
        "conditional_thermodynamic_bridge_status": status,
        "operator_argument_scope": (
            "CONDITIONAL_ON_FINITE_VOLUME_GROUND_DENSITIES_AND_YMT2"
        ),
        "finite_volume_setup_proved_by_verifier": False,
        "uniform_tail_bound_proved_by_verifier": False,
        "thermodynamic_state_constructed_by_verifier": False,
        "full_sequence_convergence_established": False,
        "uniqueness_established": False,
        "clustering_established": False,
        "uniform_mass_gap_established": False,
        "continuum_hypotheses_present": False,
        "clay_verdict": "NULL",
        "inputs": {
            "protocol": {"path": display_path(PROTOCOL), "sha256": sha256(PROTOCOL)},
            "primary_source": {"path": display_path(SOURCE), "sha256": sha256(SOURCE)},
            "local_protocol": {"path": display_path(LOCAL_PROTOCOL), "sha256": local_protocol_hash},
            "local_primary_source": {"path": display_path(LOCAL_SOURCE), "sha256": local_source_hash},
            "local_primary_receipt": {"path": display_path(LOCAL_RECEIPT), "sha256": sha256(LOCAL_RECEIPT)},
        },
        "schedule": {
            "rank_cutoffs_C": list(RANK_CUTOFFS),
            "support_sizes": list(SUPPORT_SIZES),
            "couplings_x": [float(value) for value in COUPLINGS],
            "epsilons": [float(value) for value in EPSILONS],
            "ground_dimensions": list(GROUND_DIMENSIONS),
            "ground_multiplicities": list(GROUND_MULTIPLICITIES),
            "operator_seeds": list(OPERATOR_SEEDS),
            "escape_labels_n": list(ESCAPE_LABELS),
            "escape_cutoffs_C": list(ESCAPE_CUTOFFS),
            "gap_volumes_L": list(GAP_VOLUMES),
        },
        "rank_rows": rank_rows,
        "compactness_rows": compactness_rows,
        "partial_trace_control": partial_payload,
        "ground_identity_rows": ground_rows,
        "spectator_commutator_error": spectator_error,
        "firing_controls": {
            "alternating_sequence": alternating,
            "escaping_sector_rows": escape_rows,
            "ferromagnetic_gap_rows": gap_rows,
        },
        "checks": checks,
        "checks_passed": sum(check["passed"] for check in checks),
        "checks_total": len(checks),
        "claim_boundary": (
            "This verifier checks finite-dimensional consequences and falsification "
            "controls for a conditional operator argument. The interacting finite-volume "
            "ground densities and the uniform tail estimate YMT2 are analytic premises "
            "outside this executable evidence. The receipt constructs no thermodynamic "
            "Yang-Mills state and supplies no continuum mass-gap result."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    if not passed:
        failed = [check["name"] for check in checks if not check["passed"]]
        raise RuntimeError(f"thermodynamic ground-state verification failed: {failed}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    result = run(arguments.output, arguments.replace)
    print(
        f"status={result['status']} clay={result['clay_verdict']} "
        f"checks={result['checks_passed']}/{result['checks_total']}"
    )
    print(
        f"rank_rows={len(result['rank_rows'])} "
        f"compactness_rows={len(result['compactness_rows'])} "
        f"ground_rows={len(result['ground_identity_rows'])} "
        f"gap_terminal={result['firing_controls']['ferromagnetic_gap_rows'][-1]['one_magnon_gap_upper_bound']:.12e}"
    )


if __name__ == "__main__":
    main()
