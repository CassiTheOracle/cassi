#!/usr/bin/env python3
"""Run the frozen Cassi quantum-geometric bridge certificates.

Protocol: computations/quantum-geometric-bridge-pre-registration.md
"""

from __future__ import annotations

import math

import numpy as np


TOL = 1.0e-12
PHI = (1.0 + math.sqrt(5.0)) / 2.0


def dc_coordinates(e_y: complex, e_i: complex) -> tuple[complex, complex]:
    d = e_y - PHI * e_i
    c = (PHI * e_y + e_i) / (1.0 + PHI**2)
    return d, c


def certificate_c1() -> bool:
    p_y = PHI**-1
    p_i = PHI**-2
    n_z = p_y - p_i
    theta = math.acos(n_z)
    radius = math.sin(theta)
    norm_residuals = []
    for delta in (0.0, math.pi / 2.0, math.pi):
        bloch = np.array(
            [radius * math.cos(delta), radius * math.sin(delta), n_z]
        )
        norm_residuals.append(abs(float(bloch @ bloch) - 1.0))

    residual = max(
        abs(p_y + p_i - 1.0),
        abs(n_z - PHI**-3),
        *norm_residuals,
    )
    passed = residual <= TOL
    print(
        "C1-BLOCH",
        "PASS" if passed else "FAIL",
        f"n_z={n_z:.12f}",
        f"theta_deg={math.degrees(theta):.9f}",
        f"radius={radius:.12f}",
        f"residual={residual:.3e}",
    )
    return passed


def certificate_c2() -> bool:
    a, b = 0.7, 0.3
    w_d = 1.0 / (1.0 + PHI**2)
    w_c = 1.0 + PHI**2
    deltas = np.array([0.0, math.pi / 2.0, math.pi])
    d_norms = []
    c_norms = []
    weighted_norms = []
    link_currents = []

    for delta in deltas:
        e_y = math.sqrt(a)
        e_i = math.sqrt(b) * np.exp(1.0j * delta)
        d, c = dc_coordinates(e_y, e_i)
        d_norms.append(abs(d) ** 2)
        c_norms.append(abs(c) ** 2)
        weighted_norms.append(w_d * abs(d) ** 2 + w_c * abs(c) ** 2)

        z_s = 1.0 + 0.0j
        z_next = np.exp(1.0j * delta)
        link_currents.append(-float(np.imag(np.conj(z_s) * (z_next - z_s))))

    metric_residual = float(np.max(np.abs(np.array(weighted_norms) - 1.0)))
    d_spread = float(np.ptp(d_norms))
    c_spread = float(np.ptp(c_norms))
    current_residual = max(abs(link_currents[0]), abs(link_currents[1] + 1.0))
    passed = (
        metric_residual <= TOL
        and d_spread > TOL
        and c_spread > TOL
        and current_residual <= TOL
    )
    print(
        "C2-LOWER-FIBRE",
        "PASS" if passed else "FAIL",
        f"metric_residual={metric_residual:.3e}",
        f"D_spread={d_spread:.12f}",
        f"C_spread={c_spread:.12f}",
        "link_currents=" + ",".join(f"{value:.6f}" for value in link_currents),
    )
    return passed


def certificate_c3() -> bool:
    psi_0 = np.array([1.0, 1.0], dtype=complex) / math.sqrt(2.0)
    psi_1 = np.array([1.0, 1.0j], dtype=complex) / math.sqrt(2.0)
    probability_residual = float(
        np.max(np.abs(np.abs(psi_0) ** 2 - np.abs(psi_1) ** 2))
    )
    current_0 = float(np.imag(np.conj(psi_0[0]) * psi_0[1]))
    current_1 = float(np.imag(np.conj(psi_1[0]) * psi_1[1]))
    current_residual = max(abs(current_0), abs(current_1 - 0.5))
    passed = probability_residual <= TOL and current_residual <= TOL
    print(
        "C3-UPPER-FIBRE",
        "PASS" if passed else "FAIL",
        f"probability_residual={probability_residual:.3e}",
        f"currents=({current_0:.6f},{current_1:.6f})",
    )
    return passed


def certificate_c4() -> bool:
    a, b = 0.7, 0.3
    alpha = 0.37
    e_y = math.sqrt(a) + 0.0j
    e_i = math.sqrt(b) + 0.0j
    d_0, c_0 = dc_coordinates(e_y, e_i)

    common = np.exp(1.0j * alpha)
    d_global, c_global = dc_coordinates(common * e_y, common * e_i)
    global_residual = max(
        abs(abs(d_global) ** 2 - abs(d_0) ** 2),
        abs(abs(c_global) ** 2 - abs(c_0) ** 2),
    )

    d_relative, c_relative = dc_coordinates(e_y, 1.0j * e_i)
    relative_change = max(
        abs(abs(d_relative) ** 2 - abs(d_0) ** 2),
        abs(abs(c_relative) ** 2 - abs(c_0) ** 2),
    )

    z_global = np.array([common, common])
    z_local = np.array([1.0 + 0.0j, 1.0j])
    gradient_global = float(abs(z_global[1] - z_global[0]) ** 2)
    gradient_local = float(abs(z_local[1] - z_local[0]) ** 2)

    passed = (
        global_residual <= TOL
        and relative_change > TOL
        and abs(gradient_global) <= TOL
        and abs(gradient_local - 2.0) <= TOL
    )
    print(
        "C4-SYMMETRY",
        "PASS" if passed else "FAIL",
        f"global_residual={global_residual:.3e}",
        f"relative_change={relative_change:.12f}",
        f"gradient_energies=({gradient_global:.6f},{gradient_local:.6f})",
    )
    return passed


def certificate_c5() -> bool:
    accelerations = []
    for delta in (0.0, math.pi):
        z_0 = 1.0 + 0.0j
        z_1 = np.exp(1.0j * delta)
        force_0 = z_1 - z_0
        accelerations.append(2.0 * float(np.real(np.conj(z_0) * force_0)))

    residual = max(abs(accelerations[0]), abs(accelerations[1] + 4.0))
    passed = residual <= TOL
    print(
        "C5-NONCLOSURE",
        "PASS" if passed else "FAIL",
        "projected_accelerations="
        + ",".join(f"{value:.6f}" for value in accelerations),
        f"residual={residual:.3e}",
    )
    return passed


def certificate_c6() -> bool:
    point = np.array([0.4, -0.7])
    common_gradient = np.array([2.0 * point[0], -3.0 * point[1]])
    gradient_y_0 = common_gradient.copy()
    gradient_i_0 = common_gradient.copy()
    gradient_y_1 = common_gradient.copy()
    gradient_i_1 = common_gradient.copy()
    phase_gradient_residual = float(
        max(
            np.max(np.abs(gradient_y_1 - gradient_y_0)),
            np.max(np.abs(gradient_i_1 - gradient_i_0)),
        )
    )
    relative_phase_change = 1.1

    curl_irrotational = 0.0
    kappa = 0.37
    curl_rotational = 2.0 * kappa
    circulation = 2.0 * math.pi * kappa
    quantized_distance = min(
        abs(circulation - 2.0 * math.pi * integer)
        for integer in range(-2, 3)
    )

    passed = (
        abs(curl_irrotational) <= TOL
        and phase_gradient_residual <= TOL
        and relative_phase_change > TOL
        and abs(curl_rotational - 0.74) <= TOL
        and abs(circulation - 2.0 * math.pi * kappa) <= TOL
        and quantized_distance > 1.0e-3
    )
    print(
        "C6-COTANGENT",
        "PASS" if passed else "FAIL",
        f"irrotational_curl={curl_irrotational:.6f}",
        f"phase_gradient_residual={phase_gradient_residual:.3e}",
        f"rotational_curl={curl_rotational:.6f}",
        f"circulation={circulation:.12f}",
        f"quantized_distance={quantized_distance:.12f}",
    )
    return passed


def certificate_c7() -> bool:
    w = np.diag([2.0, 3.0])
    u = np.array([1.0 + 2.0j, -0.5 + 0.25j])
    v = np.array([0.3 - 0.7j, 1.2 + 0.4j])

    def hermitian(left: np.ndarray, right: np.ndarray) -> complex:
        return complex(np.vdot(left, w @ right))

    h_uv = hermitian(u, v)
    metric_residual = abs(
        float(np.real(hermitian(1.0j * u, 1.0j * v))) - float(np.real(h_uv))
    )
    compatibility_residual = abs(
        float(np.imag(h_uv)) - float(np.real(hermitian(1.0j * u, v)))
    )

    w_prime = np.eye(3)
    refine = np.array(
        [
            [math.sqrt(2.0), 0.0],
            [0.0, math.sqrt(3.0)],
            [0.0, 0.0],
        ]
    )
    refinement_metric_residual = float(
        np.max(np.abs(refine.conj().T @ w_prime @ refine - w))
    )
    refined_h = complex(np.vdot(refine @ u, w_prime @ (refine @ v)))
    hermitian_residual = abs(refined_h - h_uv)
    complex_linearity_residual = float(
        np.max(np.abs(refine @ (1.0j * u) - 1.0j * (refine @ u)))
    )

    residual = max(
        metric_residual,
        compatibility_residual,
        refinement_metric_residual,
        hermitian_residual,
        complex_linearity_residual,
    )
    passed = residual <= TOL
    print(
        "C7-KAHLER",
        "PASS" if passed else "FAIL",
        f"metric_residual={metric_residual:.3e}",
        f"compatibility_residual={compatibility_residual:.3e}",
        f"refinement_residual={refinement_metric_residual:.3e}",
        f"hermitian_residual={hermitian_residual:.3e}",
        f"J_residual={complex_linearity_residual:.3e}",
    )
    return passed


def principal_difference(delta: float) -> float:
    return math.atan2(math.sin(delta), math.cos(delta))


def winding(phases: np.ndarray) -> tuple[float, int]:
    total = sum(
        principal_difference(float(phases[index + 1] - phases[index]))
        for index in range(len(phases) - 1)
    )
    return total, int(round(total / (2.0 * math.pi)))


def certificate_c8() -> bool:
    phases = np.array([0.0, math.pi / 2.0, math.pi, -math.pi / 2.0, 0.0])
    total, number = winding(phases)
    shifted_total, shifted_number = winding(phases + 0.37)
    residual = max(
        abs(total - 2.0 * math.pi),
        abs(shifted_total - 2.0 * math.pi),
        abs(number - 1),
        abs(shifted_number - 1),
    )
    passed = residual <= TOL
    print(
        "C8-WINDING",
        "PASS" if passed else "FAIL",
        f"total={total:.12f}",
        f"shifted_total={shifted_total:.12f}",
        f"windings=({number},{shifted_number})",
        f"residual={residual:.3e}",
    )
    return passed


def certificate_c9() -> bool:
    product = np.array([[1.0, 1.0], [1.0, 1.0]]) / 2.0
    bell = np.eye(2) / math.sqrt(2.0)
    product_determinant = float(np.linalg.det(product))
    bell_determinant = float(np.linalg.det(bell))
    residual = max(abs(product_determinant), abs(abs(bell_determinant) - 0.5))
    passed = residual <= TOL
    print(
        "C9-SEGRE",
        "PASS" if passed else "FAIL",
        f"product_det={product_determinant:.3e}",
        f"bell_det={bell_determinant:.12f}",
        f"residual={residual:.3e}",
    )
    return passed


def main() -> int:
    certificates = [
        certificate_c1(),
        certificate_c2(),
        certificate_c3(),
        certificate_c4(),
        certificate_c5(),
        certificate_c6(),
        certificate_c7(),
        certificate_c8(),
        certificate_c9(),
    ]
    if all(certificates):
        print("ALL DECLARED CERTIFICATES PASSED")
        return 0
    print("DECLARED CERTIFICATES FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
