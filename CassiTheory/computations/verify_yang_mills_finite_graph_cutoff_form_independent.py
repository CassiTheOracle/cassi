"""Independent deterministic check of the finite-graph cutoff-form lemma.

This source uses dense Hermitian diagonalization and independent SU(2)
coordinate routines.  It reads the primary receipt only after recomputing the
frozen schedule, then compares the two artifacts.  A finite-graph PASS is
reported separately from the necessarily NULL Clay verdict.

Run from the CassiTheory root after the primary verifier:

    python computations/verify_yang_mills_finite_graph_cutoff_form_independent.py
    python computations/verify_yang_mills_finite_graph_cutoff_form_independent.py --replace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-finite-graph-cutoff-form-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "verify_yang_mills_finite_graph_cutoff_form.py"
PRIMARY_RECEIPT = ROOT / "runs" / "yang_mills_finite_graph_cutoff_form" / "verification.json"
OUTPUT = ROOT / "runs" / "yang_mills_finite_graph_cutoff_form" / "verification-independent.json"

REFERENCE_CUTOFF = 64
UPPER_CUTOFF = 2
COUPLINGS = (0.015625, 0.0625, 0.25, 1.0, 4.0, 16.0)
CUTOFFS = (1, 2, 4, 8, 16, 32, 48)
LEVELS = (0, 1)
COORDINATE_VECTORS = (
    (0.23, -0.17, 0.31),
    (-0.29, 0.37, 0.11),
    (0.19, 0.41, -0.27),
    (-0.33, 0.14, 0.26),
)
FD_STEP = 1.0e-6
ALGEBRA_TOL = 1.0e-12
EIGEN_TOL = 1.0e-10
JACOBIAN_TOL = 1.0e-6
INEQUALITY_TOL = 1.0e-11
CROSSCHECK_TOL = 1.0e-10


def digest(path: Path) -> str:
    state = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1024 * 1024):
            state.update(block)
    return state.hexdigest()


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_record(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise TypeError(f"expected object receipt: {path}")
    return value


def product(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    scalar = a[0] * b[0] - float(a[1:] @ b[1:])
    vector = a[0] * b[1:] + b[0] * a[1:] + np.cross(a[1:], b[1:])
    return np.concatenate(([scalar], vector))


def inverse(a: np.ndarray) -> np.ndarray:
    return np.concatenate(([a[0]], -a[1:])) / float(a @ a)


def rotor(vector: np.ndarray) -> np.ndarray:
    radius = float(np.linalg.norm(vector))
    if radius == 0.0:
        return np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)
    return np.concatenate(
        ([math.cos(radius)], math.sin(radius) * vector / radius)
    )


def logarithm(quaternion: np.ndarray) -> np.ndarray:
    unit = quaternion / np.linalg.norm(quaternion)
    if unit[0] < 0.0:
        unit = -unit
    radius = float(np.linalg.norm(unit[1:]))
    if radius < 1.0e-15:
        return unit[1:].copy()
    return math.atan2(radius, float(unit[0])) * unit[1:] / radius


def rotation(quaternion: np.ndarray) -> np.ndarray:
    q = quaternion / np.linalg.norm(quaternion)
    w = float(q[0])
    x, y, z = (float(item) for item in q[1:])
    return np.array(
        [
            [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - w * z), 2.0 * (x * z + w * y)],
            [2.0 * (x * y + w * z), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - w * x)],
            [2.0 * (x * z - w * y), 2.0 * (y * z + w * x), 1.0 - 2.0 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def links_from_tree(values: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    a, b, c, loop = values
    return (
        a,
        product(inverse(a), b),
        product(inverse(b), c),
        product(inverse(c), loop),
    )


def tree_from_links(edges: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    a = edges[0]
    b = product(a, edges[1])
    c = product(b, edges[2])
    loop = product(c, edges[3])
    return a, b, c, loop


def tangent_jacobian(values: tuple[np.ndarray, ...]) -> np.ndarray:
    result = np.zeros((12, 12), dtype=np.float64)
    result[0:3, 0:3] = np.eye(3, dtype=np.float64)
    for row in range(1, 4):
        transform = rotation(inverse(values[row - 1]))
        result[3 * row : 3 * row + 3, 3 * (row - 1) : 3 * row] = -transform
        result[3 * row : 3 * row + 3, 3 * row : 3 * row + 3] = transform
    return result


def numerical_jacobian(values: tuple[np.ndarray, ...]) -> np.ndarray:
    unperturbed = links_from_tree(values)
    result = np.zeros((12, 12), dtype=np.float64)
    for coordinate_index in range(4):
        for axis in range(3):
            displacement = np.zeros(3, dtype=np.float64)
            displacement[axis] = FD_STEP
            forward = list(values)
            backward = list(values)
            forward[coordinate_index] = product(rotor(displacement), values[coordinate_index])
            backward[coordinate_index] = product(rotor(-displacement), values[coordinate_index])
            forward_edges = links_from_tree(tuple(forward))
            backward_edges = links_from_tree(tuple(backward))
            for edge_index in range(4):
                positive = logarithm(product(forward_edges[edge_index], inverse(unperturbed[edge_index])))
                negative = logarithm(product(backward_edges[edge_index], inverse(unperturbed[edge_index])))
                result[3 * edge_index : 3 * edge_index + 3, 3 * coordinate_index + axis] = (
                    positive - negative
                ) / (2.0 * FD_STEP)
    return result


def dense_hamiltonian(cutoff: int, coupling: float) -> np.ndarray:
    labels = np.arange(cutoff + 1, dtype=np.float64)
    matrix = np.diag(labels * (labels + 2.0) + 2.0 * coupling)
    for label in range(cutoff):
        matrix[label, label + 1] = -coupling
        matrix[label + 1, label] = -coupling
    return matrix


def spectrum(cutoff: int, coupling: float) -> tuple[np.ndarray, np.ndarray]:
    return np.linalg.eigh(dense_hamiltonian(cutoff, coupling))


def direct_character_gram(order: int, maximum_n: int) -> np.ndarray:
    k = np.arange(1, order + 1, dtype=np.float64)
    angles = math.pi * k / (order + 1)
    weights = 2.0 * np.sin(angles) ** 2 / (order + 1)
    characters = np.array(
        [
            np.sin((label + 1) * angles) / np.sin(angles)
            for label in range(maximum_n + 1)
        ]
    )
    return np.einsum("ik,k,jk->ij", characters, weights, characters)


def add(
    checks: list[dict[str, Any]],
    name: str,
    condition: bool,
    value: Any,
    requirement: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(condition),
            "value": value,
            "criterion": requirement,
        }
    )


def recompute_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tail_passed = 0
    square_tail_passed = 0
    ritz_applicable = 0
    ritz_passed = 0
    monotonic = True
    maximum_residual = 0.0
    minimum_tail_margin = math.inf
    minimum_square_margin = math.inf
    minimum_ritz_margin = math.inf

    for coupling in COUPLINGS:
        reference_values, reference_vectors = spectrum(REFERENCE_CUTOFF, coupling)
        reference_matrix = dense_hamiltonian(REFERENCE_CUTOFF, coupling)
        maximum_residual = max(
            maximum_residual,
            float(
                np.max(
                    np.abs(
                        reference_matrix @ reference_vectors
                        - reference_vectors * reference_values
                    )
                )
            ),
        )
        upper_values, _ = spectrum(UPPER_CUTOFF, coupling)
        finite_spectra = {cutoff: spectrum(cutoff, coupling)[0] for cutoff in CUTOFFS}
        for level in LEVELS:
            ordered = [float(finite_spectra[c][level]) for c in CUTOFFS]
            ordered.append(float(reference_values[level]))
            monotonic = monotonic and all(
                right <= left + INEQUALITY_TOL
                for left, right in zip(ordered, ordered[1:])
            )
            energy = float(reference_values[level])
            upper = float(upper_values[level])
            for cutoff in CUTOFFS:
                ritz = float(finite_spectra[cutoff][level])
                tail = float(np.linalg.norm(reference_vectors[cutoff + 1 :, level]) ** 2)
                kappa = (cutoff + 1.0) * (cutoff + 3.0) / 4.0
                square_kappa = 4.0 * kappa
                tail_bound = energy / kappa
                square_bound = energy / square_kappa
                tail_margin = tail_bound - tail
                square_margin = square_bound - tail
                minimum_tail_margin = min(minimum_tail_margin, tail_margin)
                minimum_square_margin = min(minimum_square_margin, square_margin)
                if tail_margin >= -INEQUALITY_TOL:
                    tail_passed += 1
                if square_margin >= -INEQUALITY_TOL:
                    square_tail_passed += 1
                eta = upper / kappa
                error = ritz - energy
                error_bound: float | None = None
                if eta < 1.0:
                    ritz_applicable += 1
                    error_bound = (
                        upper * eta
                        + 4.0 * coupling * (2.0 * math.sqrt(eta) + eta)
                    ) / (1.0 - eta)
                    ritz_margin = error_bound - error
                    minimum_ritz_margin = min(minimum_ritz_margin, ritz_margin)
                    if error >= -INEQUALITY_TOL and ritz_margin >= -INEQUALITY_TOL:
                        ritz_passed += 1
                rows.append(
                    {
                        "coupling_x": coupling,
                        "cutoff": cutoff,
                        "level": level,
                        "reference_energy": energy,
                        "ritz_energy": ritz,
                        "tail_norm_sq": tail,
                        "tail_bound_general": tail_bound,
                        "tail_bound_square": square_bound,
                        "ritz_upper_R": upper,
                        "eta": eta,
                        "ritz_error": error,
                        "ritz_error_bound": error_bound,
                    }
                )
    count = len(COUPLINGS) * len(CUTOFFS) * len(LEVELS)
    summary = {
        "row_count": len(rows),
        "expected_row_count": count,
        "tail_passed": tail_passed,
        "square_tail_passed": square_tail_passed,
        "ritz_applicable": ritz_applicable,
        "ritz_passed": ritz_passed,
        "monotonic": monotonic,
        "maximum_eigensystem_residual": maximum_residual,
        "minimum_tail_margin": minimum_tail_margin,
        "minimum_square_tail_margin": minimum_square_margin,
        "minimum_ritz_margin": minimum_ritz_margin,
    }
    return rows, summary


def row_key(row: dict[str, Any]) -> tuple[float, int, int]:
    return float(row["coupling_x"]), int(row["cutoff"]), int(row["level"])


def run(output: Path, replace: bool) -> dict[str, Any]:
    for required in (PROTOCOL, PRIMARY_SOURCE, PRIMARY_RECEIPT):
        if not required.is_file():
            raise FileNotFoundError(required)
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    checks: list[dict[str, Any]] = []
    primary = load_record(PRIMARY_RECEIPT)
    protocol_hash = digest(PROTOCOL)
    primary_source_hash = digest(PRIMARY_SOURCE)
    add(
        checks,
        "primary_protocol_binding",
        primary.get("inputs", {}).get("protocol", {}).get("sha256") == protocol_hash,
        primary.get("inputs", {}).get("protocol", {}).get("sha256"),
        "primary protocol SHA-256 equals current protocol",
    )
    add(
        checks,
        "primary_source_binding",
        primary.get("inputs", {}).get("primary_source", {}).get("sha256")
        == primary_source_hash,
        primary.get("inputs", {}).get("primary_source", {}).get("sha256"),
        "primary source SHA-256 equals current primary source",
    )
    add(
        checks,
        "primary_finite_status",
        primary.get("finite_graph_status") == "PASS",
        primary.get("finite_graph_status"),
        "primary finite_graph_status is PASS",
    )
    add(
        checks,
        "primary_clay_boundary",
        primary.get("continuum_hypotheses_present") is False
        and primary.get("clay_verdict") == "NULL",
        {
            "continuum_hypotheses_present": primary.get("continuum_hypotheses_present"),
            "clay_verdict": primary.get("clay_verdict"),
        },
        "absent continuum hypotheses force clay_verdict NULL",
    )

    values = tuple(rotor(np.asarray(row, dtype=np.float64)) for row in COORDINATE_VECTORS)
    edges = links_from_tree(values)
    recovered = tree_from_links(edges)
    reconstruction_error = max(
        float(np.linalg.norm(logarithm(product(actual, inverse(expected)))))
        for actual, expected in zip(recovered, values)
    )
    analytic = tangent_jacobian(values)
    numerical = numerical_jacobian(values)
    analytic_det = float(np.linalg.det(analytic))
    numerical_det = float(np.linalg.det(numerical))
    jacobian_error = float(np.max(np.abs(analytic - numerical)))
    add(
        checks,
        "independent_tree_reconstruction",
        reconstruction_error <= ALGEBRA_TOL,
        reconstruction_error,
        f"max coordinate error <= {ALGEBRA_TOL}",
    )
    add(
        checks,
        "independent_analytic_jacobian",
        abs(abs(analytic_det) - 1.0) <= ALGEBRA_TOL,
        analytic_det,
        f"||det J|-1| <= {ALGEBRA_TOL}",
    )
    add(
        checks,
        "independent_finite_jacobian",
        abs(abs(numerical_det) - 1.0) <= JACOBIAN_TOL
        and jacobian_error <= JACOBIAN_TOL,
        {"determinant": numerical_det, "max_entry_error": jacobian_error},
        f"determinant and entry errors <= {JACOBIAN_TOL}",
    )

    r_tc = [[1], [1], [1]]
    m_t = [sum(row) for row in r_tc]
    graph_constant = 1 + max(
        sum(m_t[tree] * r_tc[tree][chord] for tree in range(3))
        for chord in range(1)
    )
    add(
        checks,
        "independent_graph_constant",
        graph_constant == 4 and graph_constant <= 13,
        graph_constant,
        "C_(Gamma,T)=4 and obeys the coarse bound 13",
    )

    gram = direct_character_gram(64, 15)
    gram_error = float(np.max(np.abs(gram - np.eye(16))))
    add(
        checks,
        "independent_haar_orthogonality",
        gram_error <= ALGEBRA_TOL,
        gram_error,
        f"max Gram error <= {ALGEBRA_TOL}",
    )

    potential = np.diag(np.full(REFERENCE_CUTOFF + 1, 2.0))
    potential += np.diag(np.full(REFERENCE_CUTOFF, -1.0), 1)
    potential += np.diag(np.full(REFERENCE_CUTOFF, -1.0), -1)
    potential_spectrum = np.linalg.eigvalsh(potential)
    add(
        checks,
        "independent_wilson_bounds",
        potential_spectrum[0] >= -ALGEBRA_TOL
        and potential_spectrum[-1] <= 4.0 + ALGEBRA_TOL,
        {"minimum": float(potential_spectrum[0]), "maximum": float(potential_spectrum[-1])},
        "0 <= V_C <= 4 I",
    )

    rows, summary = recompute_rows()
    expected_count = len(COUPLINGS) * len(CUTOFFS) * len(LEVELS)
    add(
        checks,
        "independent_schedule_coverage",
        summary["row_count"] == expected_count,
        summary["row_count"],
        f"row count = {expected_count}",
    )
    add(
        checks,
        "independent_eigensystem_residual",
        summary["maximum_eigensystem_residual"] <= EIGEN_TOL,
        summary["maximum_eigensystem_residual"],
        f"max residual <= {EIGEN_TOL}",
    )
    add(
        checks,
        "independent_tail_bounds",
        summary["tail_passed"] == expected_count
        and summary["square_tail_passed"] == expected_count,
        {
            "general": summary["tail_passed"],
            "square": summary["square_tail_passed"],
            "attempted": expected_count,
            "minimum_general_margin": summary["minimum_tail_margin"],
            "minimum_square_margin": summary["minimum_square_tail_margin"],
        },
        "all general and square finite-reference tail bounds pass",
    )
    add(
        checks,
        "independent_ritz_bounds",
        summary["ritz_applicable"] > 0
        and summary["ritz_passed"] == summary["ritz_applicable"],
        {
            "passed": summary["ritz_passed"],
            "applicable": summary["ritz_applicable"],
            "minimum_margin": summary["minimum_ritz_margin"],
        },
        "all applicable noncommuting Ritz bounds pass",
    )
    add(
        checks,
        "independent_ritz_monotonicity",
        summary["monotonic"],
        summary["monotonic"],
        "nested Ritz energies are nonincreasing",
    )

    primary_rows = primary.get("square_spectrum", {}).get("rows", [])
    primary_map = {row_key(row): row for row in primary_rows}
    independent_map = {row_key(row): row for row in rows}
    identical_keys = primary_map.keys() == independent_map.keys()
    energy_difference = math.inf
    ritz_difference = math.inf
    tail_difference = math.inf
    bound_difference = math.inf
    applicability_matches = False
    if identical_keys and independent_map:
        energy_difference = max(
            abs(
                float(primary_map[key]["reference_energy"])
                - float(independent_map[key]["reference_energy"])
            )
            for key in independent_map
        )
        ritz_difference = max(
            abs(
                float(primary_map[key]["ritz_energy"])
                - float(independent_map[key]["ritz_energy"])
            )
            for key in independent_map
        )
        tail_difference = max(
            abs(
                float(primary_map[key]["tail_norm_sq"])
                - float(independent_map[key]["tail_norm_sq"])
            )
            for key in independent_map
        )
        bound_difference = max(
            abs(
                float(primary_map[key]["tail_bound_general"])
                - float(independent_map[key]["tail_bound_general"])
            )
            for key in independent_map
        )
        applicability_matches = all(
            (primary_map[key]["ritz_error_bound"] is None)
            == (independent_map[key]["ritz_error_bound"] is None)
            for key in independent_map
        )
    add(
        checks,
        "primary_independent_spectral_agreement",
        identical_keys
        and energy_difference <= CROSSCHECK_TOL
        and ritz_difference <= CROSSCHECK_TOL
        and tail_difference <= CROSSCHECK_TOL
        and bound_difference <= CROSSCHECK_TOL
        and applicability_matches,
        {
            "identical_keys": identical_keys,
            "max_reference_energy_difference": energy_difference,
            "max_ritz_energy_difference": ritz_difference,
            "max_tail_difference": tail_difference,
            "max_bound_difference": bound_difference,
            "applicability_matches": applicability_matches,
        },
        f"independent dense and primary tridiagonal rows agree <= {CROSSCHECK_TOL}",
    )

    firing_k = np.array([[0.0, 0.0], [0.0, 4.0]])
    firing_v = np.array([[1.0, -1.0], [-1.0, 1.0]])
    firing_energy = float(np.linalg.eigvalsh(firing_k + firing_v)[0])
    exact_energy = 3.0 - math.sqrt(5.0)
    eta = exact_energy / 4.0
    actual_error = 1.0 - exact_energy
    incomplete = exact_energy * eta / (1.0 - eta)
    complete = (
        exact_energy * eta + 2.0 * (2.0 * math.sqrt(eta) + eta)
    ) / (1.0 - eta)
    violation = actual_error - incomplete
    add(
        checks,
        "independent_firing_spectrum",
        abs(firing_energy - exact_energy) <= ALGEBRA_TOL,
        {"computed": firing_energy, "exact": exact_energy},
        f"energy error <= {ALGEBRA_TOL}",
    )
    add(
        checks,
        "independent_omitted_term_fires",
        violation > 1.0e-3 and actual_error <= complete + INEQUALITY_TOL,
        {"violation_margin": violation, "actual_error": actual_error, "full_bound": complete},
        "incomplete estimate fails and complete YMCF15 estimate passes",
    )

    passed = all(item["passed"] for item in checks)
    finite_status = "PASS" if passed else "FAIL"
    record: dict[str, Any] = {
        "schema": "cassi.yang_mills_finite_graph_cutoff_form.independent.v1",
        "status": finite_status,
        "finite_graph_status": finite_status,
        "continuum_hypotheses_present": False,
        "clay_verdict": "NULL",
        "inputs": {
            "protocol": {"path": relative(PROTOCOL), "sha256": protocol_hash},
            "independent_source": {"path": relative(SOURCE), "sha256": digest(SOURCE)},
            "primary_source": {"path": relative(PRIMARY_SOURCE), "sha256": primary_source_hash},
            "primary_receipt": {"path": relative(PRIMARY_RECEIPT), "sha256": digest(PRIMARY_RECEIPT)},
        },
        "tree_coordinates": {
            "reconstruction_error": reconstruction_error,
            "analytic_jacobian_determinant": analytic_det,
            "finite_difference_jacobian_determinant": numerical_det,
            "analytic_vs_finite_max_error": jacobian_error,
            "graph_form_constant": graph_constant,
        },
        "haar_character_control": {
            "nodes": 64,
            "maximum_doubled_spin": 15,
            "maximum_gram_error": gram_error,
        },
        "square_spectrum": {"rows": rows, **summary},
        "crosscheck": {
            "maximum_reference_energy_difference": energy_difference,
            "maximum_ritz_energy_difference": ritz_difference,
            "maximum_tail_difference": tail_difference,
            "maximum_bound_difference": bound_difference,
            "applicability_matches": applicability_matches,
        },
        "noncommuting_firing_control": {
            "exact_ground_energy": exact_energy,
            "computed_ground_energy": firing_energy,
            "actual_ritz_error": actual_error,
            "incomplete_bound": incomplete,
            "incomplete_bound_violation_margin": violation,
            "full_bound": complete,
        },
        "checks": checks,
        "checks_passed": sum(item["passed"] for item in checks),
        "checks_total": len(checks),
        "claim_boundary": (
            "The independent checks cover a fixed finite graph only. Uniform "
            "volume/spacing estimates and a continuum construction are absent, so "
            "the Clay verdict is NULL even when finite_graph_status is PASS."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    if not passed:
        failed = [item["name"] for item in checks if not item["passed"]]
        raise RuntimeError(f"independent finite-graph verification failed: {failed}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    arguments = parser.parse_args()
    result = run(arguments.output, arguments.replace)
    spectrum_summary = result["square_spectrum"]
    print(
        f"status={result['finite_graph_status']} clay={result['clay_verdict']} "
        f"checks={result['checks_passed']}/{result['checks_total']}"
    )
    print(
        f"rows={spectrum_summary['row_count']} "
        f"tails={spectrum_summary['tail_passed']}/{spectrum_summary['expected_row_count']} "
        f"ritz={spectrum_summary['ritz_passed']}/{spectrum_summary['ritz_applicable']} "
        f"cross_energy={result['crosscheck']['maximum_reference_energy_difference']:.3e}"
    )


if __name__ == "__main__":
    main()
