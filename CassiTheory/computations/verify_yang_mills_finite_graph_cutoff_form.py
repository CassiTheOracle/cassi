"""Verify the fixed-finite-graph Yang--Mills character-cutoff form lemma.

The analytic proof and frozen deterministic schedule are in
computations/yang-mills-finite-graph-cutoff-form-prereg.md.  The numerical
controls falsify the stated identities and bounds; they do not prove a
continuum Yang--Mills construction or a mass gap.

Run from the CassiTheory root:

    python computations/verify_yang_mills_finite_graph_cutoff_form.py
    python computations/verify_yang_mills_finite_graph_cutoff_form.py --replace
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import eigh_tridiagonal


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "yang-mills-finite-graph-cutoff-form-prereg.md"
OUTPUT = ROOT / "runs" / "yang_mills_finite_graph_cutoff_form" / "verification.json"

REFERENCE_CUTOFF = 64
RITZ_UPPER_CUTOFF = 2
COUPLINGS = (1.0 / 64.0, 1.0 / 16.0, 1.0 / 4.0, 1.0, 4.0, 16.0)
RITZ_CUTOFFS = (1, 2, 4, 8, 16, 32, 48)
LEVELS = (0, 1)
COORDINATE_VECTORS = (
    (0.23, -0.17, 0.31),
    (-0.29, 0.37, 0.11),
    (0.19, 0.41, -0.27),
    (-0.33, 0.14, 0.26),
)
FINITE_DIFFERENCE_STEP = 1.0e-6
ALGEBRA_TOL = 1.0e-12
EIGEN_TOL = 1.0e-10
JACOBIAN_TOL = 1.0e-6
INEQUALITY_TOL = 1.0e-11


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def qmul(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    lw, lx, ly, lz = left
    rw, rx, ry, rz = right
    return np.array(
        [
            lw * rw - lx * rx - ly * ry - lz * rz,
            lw * rx + lx * rw + ly * rz - lz * ry,
            lw * ry - lx * rz + ly * rw + lz * rx,
            lw * rz + lx * ry - ly * rx + lz * rw,
        ],
        dtype=np.float64,
    )


def qinv(value: np.ndarray) -> np.ndarray:
    norm_sq = float(value @ value)
    return np.array(
        [value[0], -value[1], -value[2], -value[3]], dtype=np.float64
    ) / norm_sq


def qexp(vector: np.ndarray) -> np.ndarray:
    theta = float(np.linalg.norm(vector))
    if theta < 1.0e-14:
        theta_sq = theta * theta
        scalar = 1.0 - theta_sq / 2.0
        scale = 1.0 - theta_sq / 6.0
        value = np.concatenate(([scalar], scale * vector))
        return value / np.linalg.norm(value)
    return np.concatenate(([math.cos(theta)], math.sin(theta) * vector / theta))


def qlog(value: np.ndarray) -> np.ndarray:
    unit = value / np.linalg.norm(value)
    if unit[0] < 0.0:
        unit = -unit
    vector = unit[1:]
    sine = float(np.linalg.norm(vector))
    if sine < 1.0e-14:
        return vector.copy()
    angle = math.atan2(sine, float(unit[0]))
    return angle * vector / sine


def qdistance(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.linalg.norm(qlog(qmul(left, qinv(right)))))


def adjoint(value: np.ndarray) -> np.ndarray:
    inverse = qinv(value)
    matrix = np.empty((3, 3), dtype=np.float64)
    for column in range(3):
        pure = np.zeros(4, dtype=np.float64)
        pure[column + 1] = 1.0
        matrix[:, column] = qmul(qmul(value, pure), inverse)[1:]
    return matrix


def reconstruct_links(coordinates: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    g1, g2, g3, h = coordinates
    return (
        g1.copy(),
        qmul(qinv(g1), g2),
        qmul(qinv(g2), g3),
        qmul(qinv(g3), h),
    )


def gauge_fix_links(links: tuple[np.ndarray, ...]) -> tuple[np.ndarray, ...]:
    u0, u1, u2, u3 = links
    g1 = u0.copy()
    g2 = qmul(g1, u1)
    g3 = qmul(g2, u2)
    h = qmul(g3, u3)
    return g1, g2, g3, h


def analytic_coordinate_jacobian(
    coordinates: tuple[np.ndarray, ...],
) -> np.ndarray:
    g1, g2, g3, _h = coordinates
    identity = np.eye(3, dtype=np.float64)
    zero = np.zeros((3, 3), dtype=np.float64)
    a1 = adjoint(qinv(g1))
    a2 = adjoint(qinv(g2))
    a3 = adjoint(qinv(g3))
    return np.block(
        [
            [identity, zero, zero, zero],
            [-a1, a1, zero, zero],
            [zero, -a2, a2, zero],
            [zero, zero, -a3, a3],
        ]
    )


def finite_difference_coordinate_jacobian(
    coordinates: tuple[np.ndarray, ...], step: float
) -> np.ndarray:
    base_links = reconstruct_links(coordinates)
    jacobian = np.empty((12, 12), dtype=np.float64)
    for variable in range(4):
        for generator in range(3):
            tangent = np.zeros(3, dtype=np.float64)
            tangent[generator] = step
            plus = list(coordinates)
            minus = list(coordinates)
            plus[variable] = qmul(qexp(tangent), plus[variable])
            minus[variable] = qmul(qexp(-tangent), minus[variable])
            plus_links = reconstruct_links(tuple(plus))
            minus_links = reconstruct_links(tuple(minus))
            column = 3 * variable + generator
            for link in range(4):
                plus_delta = qlog(qmul(plus_links[link], qinv(base_links[link])))
                minus_delta = qlog(qmul(minus_links[link], qinv(base_links[link])))
                jacobian[3 * link : 3 * link + 3, column] = (
                    plus_delta - minus_delta
                ) / (2.0 * step)
    return jacobian


def character_gram(nodes: int, maximum_n: int) -> np.ndarray:
    indices = np.arange(1, nodes + 1, dtype=np.float64)
    theta = indices * math.pi / (nodes + 1)
    x = np.cos(theta)
    weights = 2.0 * np.sin(theta) ** 2 / (nodes + 1)
    characters = np.empty((maximum_n + 1, nodes), dtype=np.float64)
    characters[0] = 1.0
    if maximum_n >= 1:
        characters[1] = 2.0 * x
    for n in range(2, maximum_n + 1):
        characters[n] = 2.0 * x * characters[n - 1] - characters[n - 2]
    return (characters * weights) @ characters.T


def tridiagonal_spectrum(cutoff: int, coupling: float) -> tuple[np.ndarray, np.ndarray]:
    n = np.arange(cutoff + 1, dtype=np.float64)
    diagonal = n * (n + 2.0) + 2.0 * coupling
    off_diagonal = -coupling * np.ones(cutoff, dtype=np.float64)
    return eigh_tridiagonal(diagonal, off_diagonal)


def dense_square_hamiltonian(cutoff: int, coupling: float) -> np.ndarray:
    n = np.arange(cutoff + 1, dtype=np.float64)
    hamiltonian = np.diag(n * (n + 2.0) + 2.0 * coupling)
    if cutoff:
        off = -coupling * np.ones(cutoff, dtype=np.float64)
        hamiltonian += np.diag(off, 1) + np.diag(off, -1)
    return hamiltonian


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    value: Any,
    criterion: str,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "value": value,
            "criterion": criterion,
        }
    )


def run(output: Path, replace: bool) -> dict[str, Any]:
    if not PROTOCOL.is_file():
        raise FileNotFoundError(PROTOCOL)
    if output.exists() and not replace:
        raise FileExistsError(f"refusing to overwrite existing receipt: {output}")

    checks: list[dict[str, Any]] = []

    coordinates = tuple(qexp(np.asarray(row, dtype=np.float64)) for row in COORDINATE_VECTORS)
    links = reconstruct_links(coordinates)
    recovered = gauge_fix_links(links)
    reconstruction_error = max(
        qdistance(expected, actual) for expected, actual in zip(coordinates, recovered)
    )
    link_norm_error = max(abs(float(link @ link) - 1.0) for link in links)
    add_check(
        checks,
        "square_tree_reconstruction",
        reconstruction_error <= ALGEBRA_TOL,
        reconstruction_error,
        f"max SU(2) coordinate error <= {ALGEBRA_TOL}",
    )
    add_check(
        checks,
        "square_link_unit_norms",
        link_norm_error <= ALGEBRA_TOL,
        link_norm_error,
        f"max quaternion norm error <= {ALGEBRA_TOL}",
    )

    analytic_jacobian = analytic_coordinate_jacobian(coordinates)
    finite_jacobian = finite_difference_coordinate_jacobian(
        coordinates, FINITE_DIFFERENCE_STEP
    )
    analytic_det = float(np.linalg.det(analytic_jacobian))
    finite_det = float(np.linalg.det(finite_jacobian))
    jacobian_difference = float(np.max(np.abs(analytic_jacobian - finite_jacobian)))
    add_check(
        checks,
        "analytic_haar_jacobian",
        abs(abs(analytic_det) - 1.0) <= ALGEBRA_TOL,
        analytic_det,
        f"||det J|-1| <= {ALGEBRA_TOL}",
    )
    add_check(
        checks,
        "finite_difference_haar_jacobian",
        abs(abs(finite_det) - 1.0) <= JACOBIAN_TOL,
        finite_det,
        f"||det J_fd|-1| <= {JACOBIAN_TOL}",
    )
    add_check(
        checks,
        "analytic_vs_finite_difference_jacobian",
        jacobian_difference <= JACOBIAN_TOL,
        jacobian_difference,
        f"max entry error <= {JACOBIAN_TOL}",
    )

    incidence = np.ones((3, 1), dtype=np.int64)
    multiplicity = np.sum(incidence, axis=1)
    graph_constant = 1 + int(
        np.max(np.sum(multiplicity[:, None] * incidence, axis=0))
    )
    coarse_constant = 1 + 4 * 1 * (4 - 1)
    add_check(
        checks,
        "square_graph_form_constant",
        graph_constant == 4,
        graph_constant,
        "C_(Gamma,T) = 4",
    )
    add_check(
        checks,
        "graph_constant_coarse_bound",
        graph_constant <= coarse_constant,
        {"exact": graph_constant, "coarse": coarse_constant},
        "C_(Gamma,T) <= 1 + 4 r (|V|-1)",
    )

    doubled_spins = np.arange(17, dtype=np.float64)
    four_link_electric = doubled_spins * (doubled_spins + 2.0)
    four_casimirs = 4.0 * (doubled_spins / 2.0) * (
        doubled_spins / 2.0 + 1.0
    )
    electric_identity_error = float(np.max(np.abs(four_link_electric - four_casimirs)))
    add_check(
        checks,
        "four_link_electric_character_identity",
        electric_identity_error <= ALGEBRA_TOL,
        electric_identity_error,
        f"max eigenvalue identity error <= {ALGEBRA_TOL}",
    )

    gram = character_gram(64, 15)
    gram_error = float(np.max(np.abs(gram - np.eye(16))))
    add_check(
        checks,
        "su2_character_haar_orthogonality",
        gram_error <= ALGEBRA_TOL,
        gram_error,
        f"max Gram error <= {ALGEBRA_TOL}",
    )

    potential_dimension = REFERENCE_CUTOFF + 1
    potential = 2.0 * np.eye(potential_dimension)
    potential -= np.eye(potential_dimension, k=1)
    potential -= np.eye(potential_dimension, k=-1)
    potential_eigenvalues = np.linalg.eigvalsh(potential)
    potential_minimum = float(potential_eigenvalues[0])
    potential_maximum = float(potential_eigenvalues[-1])
    add_check(
        checks,
        "finite_wilson_potential_bounds",
        potential_minimum >= -ALGEBRA_TOL
        and potential_maximum <= 4.0 + ALGEBRA_TOL,
        {"minimum": potential_minimum, "maximum": potential_maximum},
        "0 <= V_C <= 4 I",
    )

    spectral_rows: list[dict[str, Any]] = []
    tail_attempted = 0
    tail_passed = 0
    square_tail_passed = 0
    ritz_attempted = 0
    ritz_applicable = 0
    ritz_passed = 0
    minimum_tail_margin = math.inf
    minimum_square_tail_margin = math.inf
    minimum_ritz_margin = math.inf
    maximum_residual = 0.0
    monotonicity_violations: list[dict[str, Any]] = []

    for coupling in COUPLINGS:
        reference_values, reference_vectors = tridiagonal_spectrum(
            REFERENCE_CUTOFF, coupling
        )
        reference_matrix = dense_square_hamiltonian(REFERENCE_CUTOFF, coupling)
        residual = reference_matrix @ reference_vectors - reference_vectors * reference_values
        maximum_residual = max(maximum_residual, float(np.max(np.abs(residual))))

        upper_values, _ = tridiagonal_spectrum(RITZ_UPPER_CUTOFF, coupling)
        cutoff_spectra = {
            cutoff: tridiagonal_spectrum(cutoff, coupling)[0]
            for cutoff in RITZ_CUTOFFS
        }

        for level in LEVELS:
            monotone_values = [
                float(cutoff_spectra[cutoff][level]) for cutoff in RITZ_CUTOFFS
            ] + [float(reference_values[level])]
            for left_cutoff, right_cutoff, left_value, right_value in zip(
                (*RITZ_CUTOFFS, REFERENCE_CUTOFF),
                (*RITZ_CUTOFFS[1:], REFERENCE_CUTOFF, REFERENCE_CUTOFF),
                monotone_values,
                monotone_values[1:] + [monotone_values[-1]],
            ):
                if right_value > left_value + INEQUALITY_TOL:
                    monotonicity_violations.append(
                        {
                            "coupling": coupling,
                            "level": level,
                            "left_cutoff": left_cutoff,
                            "right_cutoff": right_cutoff,
                            "left_energy": left_value,
                            "right_energy": right_value,
                        }
                    )

            exact_energy = float(reference_values[level])
            ritz_upper = float(upper_values[level])
            for cutoff in RITZ_CUTOFFS:
                ritz_energy = float(cutoff_spectra[cutoff][level])
                tail_norm_sq = float(
                    np.sum(reference_vectors[cutoff + 1 :, level] ** 2)
                )
                kappa_general = (cutoff + 1.0) * (cutoff + 3.0) / 4.0
                kappa_square = (cutoff + 1.0) * (cutoff + 3.0)
                tail_bound = exact_energy / kappa_general
                square_tail_bound = exact_energy / kappa_square
                tail_margin = tail_bound - tail_norm_sq
                square_tail_margin = square_tail_bound - tail_norm_sq
                minimum_tail_margin = min(minimum_tail_margin, tail_margin)
                minimum_square_tail_margin = min(
                    minimum_square_tail_margin, square_tail_margin
                )
                tail_attempted += 1
                if tail_margin >= -INEQUALITY_TOL:
                    tail_passed += 1
                if square_tail_margin >= -INEQUALITY_TOL:
                    square_tail_passed += 1

                eta = ritz_upper / kappa_general
                ritz_error = ritz_energy - exact_energy
                ritz_attempted += 1
                ritz_error_bound: float | None = None
                if eta < 1.0:
                    ritz_applicable += 1
                    ritz_error_bound = (
                        ritz_upper * eta
                        + coupling * 4.0 * (2.0 * math.sqrt(eta) + eta)
                    ) / (1.0 - eta)
                    ritz_margin = ritz_error_bound - ritz_error
                    minimum_ritz_margin = min(minimum_ritz_margin, ritz_margin)
                    if (
                        ritz_error >= -INEQUALITY_TOL
                        and ritz_margin >= -INEQUALITY_TOL
                    ):
                        ritz_passed += 1

                spectral_rows.append(
                    {
                        "coupling_x": coupling,
                        "cutoff": cutoff,
                        "level": level,
                        "reference_energy": exact_energy,
                        "ritz_energy": ritz_energy,
                        "tail_norm_sq": tail_norm_sq,
                        "kappa_general": kappa_general,
                        "tail_bound_general": tail_bound,
                        "kappa_square": kappa_square,
                        "tail_bound_square": square_tail_bound,
                        "ritz_upper_cutoff": RITZ_UPPER_CUTOFF,
                        "ritz_upper_R": ritz_upper,
                        "eta": eta,
                        "ritz_error": ritz_error,
                        "ritz_error_bound": ritz_error_bound,
                    }
                )

    expected_inequalities = len(COUPLINGS) * len(RITZ_CUTOFFS) * len(LEVELS)
    add_check(
        checks,
        "reference_eigensystem_residual",
        maximum_residual <= EIGEN_TOL,
        maximum_residual,
        f"max residual <= {EIGEN_TOL}",
    )
    add_check(
        checks,
        "tail_attempt_count",
        tail_attempted == expected_inequalities,
        tail_attempted,
        f"attempted = {expected_inequalities}",
    )
    add_check(
        checks,
        "general_tail_inequalities",
        tail_passed == tail_attempted,
        {
            "passed": tail_passed,
            "attempted": tail_attempted,
            "minimum_margin": minimum_tail_margin,
        },
        "every YMCF12 finite-reference row passes",
    )
    add_check(
        checks,
        "square_tail_inequalities",
        square_tail_passed == tail_attempted,
        {
            "passed": square_tail_passed,
            "attempted": tail_attempted,
            "minimum_margin": minimum_square_tail_margin,
        },
        "every square-strengthened tail row passes",
    )
    add_check(
        checks,
        "ritz_attempt_count",
        ritz_attempted == expected_inequalities,
        ritz_attempted,
        f"attempted = {expected_inequalities}",
    )
    add_check(
        checks,
        "ritz_applicability_visible",
        0 < ritz_applicable <= ritz_attempted,
        {"applicable": ritz_applicable, "attempted": ritz_attempted},
        "at least one YMCF15 row is applicable and the count is explicit",
    )
    add_check(
        checks,
        "ritz_error_inequalities",
        ritz_passed == ritz_applicable,
        {
            "passed": ritz_passed,
            "applicable": ritz_applicable,
            "minimum_margin": minimum_ritz_margin,
        },
        "every applicable YMCF15 finite-reference row passes",
    )
    add_check(
        checks,
        "ritz_monotonicity",
        not monotonicity_violations,
        {"violations": monotonicity_violations},
        "nested Ritz energies are nonincreasing",
    )

    firing_k = np.diag([0.0, 4.0])
    firing_v = np.array([[1.0, -1.0], [-1.0, 1.0]], dtype=np.float64)
    firing_h = firing_k + firing_v
    firing_eigenvalues = np.linalg.eigvalsh(firing_h)
    firing_energy = float(firing_eigenvalues[0])
    firing_exact = 3.0 - math.sqrt(5.0)
    firing_eta = firing_exact / 4.0
    firing_actual_error = 1.0 - firing_exact
    firing_naive_bound = firing_exact * firing_eta / (1.0 - firing_eta)
    firing_full_bound = (
        firing_exact * firing_eta
        + 2.0 * (2.0 * math.sqrt(firing_eta) + firing_eta)
    ) / (1.0 - firing_eta)
    firing_violation_margin = firing_actual_error - firing_naive_bound
    commutator_norm = float(np.linalg.norm(firing_k @ firing_v - firing_v @ firing_k))
    firing_potential_eigenvalues = np.linalg.eigvalsh(firing_v)
    add_check(
        checks,
        "noncommuting_firing_exact_spectrum",
        abs(firing_energy - firing_exact) <= ALGEBRA_TOL,
        {"computed": firing_energy, "exact": firing_exact},
        f"ground-energy error <= {ALGEBRA_TOL}",
    )
    add_check(
        checks,
        "noncommuting_firing_hypotheses",
        firing_potential_eigenvalues[0] >= -ALGEBRA_TOL
        and abs(float(firing_potential_eigenvalues[-1]) - 2.0) <= ALGEBRA_TOL
        and commutator_norm > 1.0,
        {
            "potential_eigenvalues": firing_potential_eigenvalues.tolist(),
            "commutator_frobenius_norm": commutator_norm,
        },
        "V is positive with norm 2 and [K,V] is nonzero",
    )
    add_check(
        checks,
        "omitted_potential_term_fires",
        firing_violation_margin > 1.0e-3,
        firing_violation_margin,
        "actual Ritz error exceeds the incomplete bound by > 1e-3",
    )
    add_check(
        checks,
        "full_noncommuting_bound_passes",
        firing_actual_error <= firing_full_bound + INEQUALITY_TOL,
        {
            "actual_error": firing_actual_error,
            "full_bound": firing_full_bound,
        },
        "YMCF15 includes enough potential correction",
    )

    all_passed = all(row["passed"] for row in checks)
    finite_graph_status = "PASS" if all_passed else "FAIL"
    record: dict[str, Any] = {
        "schema": "cassi.yang_mills_finite_graph_cutoff_form.v1",
        "status": finite_graph_status,
        "finite_graph_status": finite_graph_status,
        "continuum_hypotheses_present": False,
        "clay_verdict": "NULL",
        "inputs": {
            "protocol": {
                "path": display_path(PROTOCOL),
                "sha256": sha256(PROTOCOL),
            },
            "primary_source": {
                "path": display_path(SOURCE),
                "sha256": sha256(SOURCE),
            },
        },
        "schedule": {
            "reference_cutoff": REFERENCE_CUTOFF,
            "ritz_upper_cutoff": RITZ_UPPER_CUTOFF,
            "couplings_x": list(COUPLINGS),
            "ritz_cutoffs": list(RITZ_CUTOFFS),
            "levels": list(LEVELS),
            "finite_difference_step": FINITE_DIFFERENCE_STEP,
        },
        "tree_coordinates": {
            "reconstruction_error": reconstruction_error,
            "analytic_jacobian_determinant": analytic_det,
            "finite_difference_jacobian_determinant": finite_det,
            "analytic_vs_finite_max_error": jacobian_difference,
            "graph_form_constant": graph_constant,
            "coarse_graph_bound": coarse_constant,
        },
        "haar_character_control": {
            "nodes": 64,
            "maximum_doubled_spin": 15,
            "maximum_gram_error": gram_error,
        },
        "square_spectrum": {
            "potential_minimum": potential_minimum,
            "potential_maximum": potential_maximum,
            "maximum_eigensystem_residual": maximum_residual,
            "rows": spectral_rows,
            "tail_attempted": tail_attempted,
            "tail_passed": tail_passed,
            "square_tail_passed": square_tail_passed,
            "ritz_attempted": ritz_attempted,
            "ritz_applicable": ritz_applicable,
            "ritz_passed": ritz_passed,
        },
        "noncommuting_firing_control": {
            "exact_ground_energy": firing_exact,
            "computed_ground_energy": firing_energy,
            "eta": firing_eta,
            "actual_ritz_error": firing_actual_error,
            "incomplete_bound": firing_naive_bound,
            "incomplete_bound_violation_margin": firing_violation_margin,
            "full_bound": firing_full_bound,
        },
        "checks": checks,
        "checks_passed": sum(row["passed"] for row in checks),
        "checks_total": len(checks),
        "claim_boundary": (
            "The analytic and deterministic checks concern one fixed finite graph at "
            "fixed coupling. Spatial-volume-uniform and lattice-spacing-uniform "
            "estimates and a continuum Yang--Mills construction are absent; the Clay "
            "verdict is therefore NULL."
        ),
    }

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output)
    if not all_passed:
        failed = [row["name"] for row in checks if not row["passed"]]
        raise RuntimeError(f"finite-graph cutoff-form verification failed: {failed}")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    record = run(args.output, args.replace)
    spectrum = record["square_spectrum"]
    print(
        f"status={record['finite_graph_status']} clay={record['clay_verdict']} "
        f"checks={record['checks_passed']}/{record['checks_total']}"
    )
    print(
        f"tails={spectrum['tail_passed']}/{spectrum['tail_attempted']} "
        f"ritz={spectrum['ritz_passed']}/{spectrum['ritz_applicable']} "
        f"jacobian={record['tree_coordinates']['finite_difference_jacobian_determinant']:.12g}"
    )


if __name__ == "__main__":
    main()
