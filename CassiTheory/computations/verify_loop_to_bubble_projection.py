"""Verify the frozen loop-to-bubble projection identities."""

from __future__ import annotations

import cmath
import itertools
import math

import numpy as np


PHI = (1.0 + math.sqrt(5.0)) / 2.0
NX = 7
NCHI = 12
U = 0.31
D_X = 0.17
R = 1.7
V = 0.8
D_ELL = 0.13
EXCHANGE = 0.6
LAM = 0.04
OMEGA = V / R
D_LOOP = D_ELL / R**2
AXES = np.array((3.0, 2.0, 1.25))
TOL = 1.0e-11


def derivative(values: np.ndarray, axis: int, spacing: float) -> np.ndarray:
    return (np.roll(values, -1, axis=axis) - np.roll(values, 1, axis=axis)) / (
        2.0 * spacing
    )


def laplacian(values: np.ndarray, axis: int, spacing: float) -> np.ndarray:
    return (
        np.roll(values, -1, axis=axis)
        - 2.0 * values
        + np.roll(values, 1, axis=axis)
    ) / spacing**2


def bounded_q(e_y: np.ndarray | float, e_i: np.ndarray | float) -> np.ndarray | float:
    rho = e_y + e_i
    epsilon = e_y - PHI * e_i
    return rho**2 / (rho**2 + PHI**-2 + epsilon**2)


def multiset_residual(actual: np.ndarray, expected: np.ndarray) -> float:
    return min(
        max(abs(actual[index] - candidate[index]) for index in range(len(actual)))
        for candidate in itertools.permutations(expected)
    )


def coherence_data(
    psi_y: np.ndarray, psi_i: np.ndarray
) -> tuple[float, float, complex, np.ndarray, np.ndarray]:
    e_y = float(np.mean(np.abs(psi_y) ** 2, axis=-1).sum())
    e_i = float(np.mean(np.abs(psi_i) ** 2, axis=-1).sum())
    cross = complex(np.mean(np.conjugate(psi_y) * psi_i, axis=-1).sum())
    rho = e_y + e_i
    vector = np.array(
        (2.0 * cross.real / rho, 2.0 * cross.imag / rho, (e_y - e_i) / rho)
    )
    gram = np.array(((e_y, cross.conjugate()), (cross, e_i)), dtype=complex)
    return e_y, e_i, cross, vector, gram


def generator(kappa: float, exchange: float) -> np.ndarray:
    return np.array(
        (
            (-exchange - kappa, exchange, PHI * kappa, 0.0),
            (exchange, -exchange - kappa, 0.0, PHI * kappa),
            (kappa, 0.0, -exchange - PHI * kappa, exchange),
            (0.0, kappa, exchange, -exchange - PHI * kappa),
        )
    )


def mode_generator(
    mode: int, kappa: float, exchange: float, omega: float, loop_diffusion: float
) -> np.ndarray:
    conversion = kappa * np.array(((-1.0, PHI), (1.0, -PHI)))
    direction = np.array(
        (
            (-exchange - 1j * mode * omega, exchange),
            (exchange, -exchange + 1j * mode * omega),
        )
    )
    return (
        np.kron(conversion, np.eye(2))
        + np.kron(np.eye(2), direction)
        - loop_diffusion * mode**2 * np.eye(4)
    )


def closed_spectrum(
    mode: int, kappa: float, exchange: float, omega: float, loop_diffusion: float
) -> np.ndarray:
    root = cmath.sqrt(exchange**2 - mode**2 * omega**2)
    return np.array(
        [
            -loop_diffusion * mode**2 + conversion - exchange + sign * root
            for conversion in (0.0, -kappa * (1.0 + PHI))
            for sign in (1.0, -1.0)
        ]
    )


def verify() -> int:
    failures: list[str] = []

    # LB1: use the same periodic difference operators before and after projection.
    x = 2.0 * math.pi * np.arange(NX) / NX
    chi = 2.0 * math.pi * np.arange(NCHI) / NCHI
    populations = np.empty((2, 2, NX, NCHI))
    for carrier in range(2):
        for direction_index in range(2):
            direction_sign = 1.0 if direction_index == 0 else -1.0
            populations[carrier, direction_index] = (
                1.05
                + 0.27 * carrier
                + 0.09 * direction_sign
                + 0.11 * np.cos(x[:, None] + (carrier + 1) * chi[None, :])
                + 0.07
                * np.sin(2.0 * x[:, None] - direction_sign * chi[None, :])
            )

    densities = populations.mean(axis=3).sum(axis=1)
    kappa_x = LAM * (1.0 - bounded_q(densities[0], densities[1]))
    dx = 2.0 * math.pi / NX
    dchi = 2.0 * math.pi / NCHI
    signs = np.array((1.0, -1.0))[None, :, None, None]
    microscopic = (
        -U * derivative(populations, axis=2, spacing=dx)
        + D_X * laplacian(populations, axis=2, spacing=dx)
        - signs * OMEGA * derivative(populations, axis=3, spacing=dchi)
        + D_LOOP * laplacian(populations, axis=3, spacing=dchi)
        + EXCHANGE * (populations[:, ::-1] - populations)
    )
    microscopic[0] += kappa_x[None, :, None] * (
        -populations[0] + PHI * populations[1]
    )
    microscopic[1] += kappa_x[None, :, None] * (
        populations[0] - PHI * populations[1]
    )
    projected_rhs = microscopic.mean(axis=3).sum(axis=1)
    epsilon = densities[0] - PHI * densities[1]
    canonical_rhs = np.stack(
        (
            -U * derivative(densities[0], axis=0, spacing=dx)
            + D_X * laplacian(densities[0], axis=0, spacing=dx)
            - kappa_x * epsilon,
            -U * derivative(densities[1], axis=0, spacing=dx)
            + D_X * laplacian(densities[1], axis=0, spacing=dx)
            + kappa_x * epsilon,
        )
    )
    lb1 = float(np.max(np.abs(projected_rhs - canonical_rhs)))
    print(f"LB1 zero-mode closure: residual={lb1:.3e}")
    if lb1 > TOL:
        failures.append("LB1")

    # LB2: local reaction/exchange generator.
    kappa = float(LAM * (1.0 - bounded_q(1.1, 0.7)))
    local = generator(kappa, EXCHANGE)
    off_diagonal = local.copy()
    np.fill_diagonal(off_diagonal, 0.0)
    fixed = np.array((PHI, PHI, 1.0, 1.0))
    lb2 = max(
        float(np.max(np.abs(local.sum(axis=0)))),
        float(np.max(np.abs(local @ fixed))),
        abs((fixed[0] + fixed[1]) / (fixed[2] + fixed[3]) - PHI),
    )
    positivity_ok = bool(np.min(off_diagonal) >= -TOL)
    print(
        "LB2 conservation/positivity/fixed composition: "
        f"residual={lb2:.3e}, positivity={'PASS' if positivity_ok else 'FAIL'}"
    )
    if lb2 > TOL or not positivity_ok:
        failures.append("LB2")

    # LB3: proportional vectors reach the shell; nonproportional vectors do not.
    phase_grid = 2.0 * math.pi * np.arange(NCHI) / NCHI
    psi_y = np.stack(
        (
            (1.0 + 0.08 * np.cos(phase_grid)) * np.exp(1j * phase_grid),
            (0.73 + 0.05 * np.sin(phase_grid)) * np.exp(-2j * phase_grid),
        )
    )
    proportionality = 0.71 * cmath.exp(0.43j)
    shell_i = proportionality * psi_y
    e_y, e_i, cross, shell_vector, shell_gram = coherence_data(psi_y, shell_i)
    shell_residual = max(
        abs(abs(cross) ** 2 - e_y * e_i),
        abs(float(shell_vector @ shell_vector) - 1.0),
        abs(float((AXES * shell_vector / AXES) @ (AXES * shell_vector / AXES)) - 1.0),
        abs(float(np.min(np.linalg.eigvalsh(shell_gram)))),
    )

    interior_i = np.stack(
        (
            0.69 * np.exp(2j * phase_grid + 0.2j),
            0.52 * np.exp(3j * phase_grid - 0.4j),
        )
    )
    int_y, int_i, int_cross, interior_vector, interior_gram = coherence_data(
        psi_y, interior_i
    )
    cauchy_slack = int_y * int_i - abs(int_cross) ** 2
    bubble_slack = 1.0 - float(interior_vector @ interior_vector)
    psd_min = float(np.min(np.linalg.eigvalsh(interior_gram)))
    inequalities_ok = cauchy_slack > TOL and bubble_slack > TOL and psd_min > -TOL
    lb3 = shell_residual
    print(
        "LB3 coherence matrix/affine bubble: "
        f"shell_residual={lb3:.3e}, interior_slack={bubble_slack:.6f}, "
        f"inequalities={'PASS' if inequalities_ok else 'FAIL'}"
    )
    if lb3 > TOL or not inequalities_ok:
        failures.append("LB3")

    # LB4: alternating equal phases cancel in even pairs and leave 1/K for odd K.
    alternating_residual = 0.0
    for layer_count in range(2, 10):
        zeta = sum(
            cmath.exp(1j * (0.37 + layer * math.pi))
            for layer in range(layer_count)
        ) / layer_count
        expected = 0.0 if layer_count % 2 == 0 else 1.0 / layer_count
        alternating_residual = max(alternating_residual, abs(abs(zeta) - expected))
    print(f"LB4 alternating-phase cancellation: residual={alternating_residual:.3e}")
    if alternating_residual > TOL:
        failures.append("LB4")

    # LB5: compare numerical 4x4 eigenvalues to the closed spectrum.
    spectrum_residual = 0.0
    for mode in range(-6, 7):
        numerical = np.linalg.eigvals(
            mode_generator(mode, kappa, EXCHANGE, OMEGA, D_LOOP)
        )
        expected = closed_spectrum(mode, kappa, EXCHANGE, OMEGA, D_LOOP)
        spectrum_residual = max(
            spectrum_residual, multiset_residual(numerical, expected)
        )

    high_omega_exchange = 0.2
    high_omega = 0.9
    high_omega_diffusion = 0.07
    for mode in range(-3, 4):
        numerical = np.linalg.eigvals(
            mode_generator(
                mode, kappa, high_omega_exchange, high_omega, high_omega_diffusion
            )
        )
        expected = closed_spectrum(
            mode, kappa, high_omega_exchange, high_omega, high_omega_diffusion
        )
        spectrum_residual = max(
            spectrum_residual, multiset_residual(numerical, expected)
        )

    zero_expected = np.array(
        (0.0, -2.0 * EXCHANGE, -kappa * (1.0 + PHI), -2.0 * EXCHANGE - kappa * (1.0 + PHI))
    )
    zero_residual = multiset_residual(
        np.linalg.eigvals(mode_generator(0, kappa, EXCHANGE, OMEGA, D_LOOP)),
        zero_expected,
    )
    closed_gap = min(
        kappa * (1.0 + PHI),
        2.0 * EXCHANGE,
        D_LOOP
        + EXCHANGE
        - cmath.sqrt(EXCHANGE**2 - OMEGA**2).real,
    )
    enumerated_decays: list[float] = []
    for mode in range(-64, 65):
        for eigenvalue in np.linalg.eigvals(
            mode_generator(mode, kappa, EXCHANGE, OMEGA, D_LOOP)
        ):
            if abs(eigenvalue) > TOL:
                enumerated_decays.append(float(-eigenvalue.real))
    numerical_gap = min(enumerated_decays)
    gap_residual = abs(numerical_gap - closed_gap)

    ballistic = np.linalg.eigvals(mode_generator(1, kappa, 0.0, OMEGA, 0.0))
    ballistic_gap = min(abs(float(value.real)) for value in ballistic)
    lb5 = max(spectrum_residual, zero_residual, gap_residual, ballistic_gap)
    print(
        "LB5 internal spectrum/gap: "
        f"spectrum_residual={spectrum_residual:.3e}, gap={closed_gap:.12f}, "
        f"gap_residual={gap_residual:.3e}, ballistic_gap={ballistic_gap:.3e}"
    )
    if lb5 > TOL:
        failures.append("LB5")

    # LB6: populations remain fixed while a relative phase winding erases c.
    constant_y = np.array(
        (
            np.full(NCHI, 1.1, dtype=complex),
            np.full(NCHI, 0.8, dtype=complex),
        )
    )
    constant_i = np.array(
        (
            np.full(NCHI, 0.7, dtype=complex),
            np.full(NCHI, 0.6, dtype=complex),
        )
    )
    coherent_i = constant_i * cmath.exp(0.37j)
    winding_i = constant_i * np.exp(1j * (0.37 + phase_grid))[None, :]
    ay, ai, ac, av, _ = coherence_data(constant_y, coherent_i)
    by, bi, bc, bv, _ = coherence_data(constant_y, winding_i)
    density_residual = max(abs(ay - by), abs(ai - bi))
    coherence_separation = abs(ac - bc)
    bubble_separation = float(np.linalg.norm(AXES * (av - bv)))
    print(
        "LB6 projection non-injectivity: "
        f"density_residual={density_residual:.3e}, "
        f"coherence_separation={coherence_separation:.6f}, "
        f"bubble_separation={bubble_separation:.6f}"
    )
    if (
        density_residual > TOL
        or coherence_separation <= 1.0e-3
        or bubble_separation <= 1.0e-3
    ):
        failures.append("LB6")

    # LB7: coherence scales the fivefold transverse orbit and preserves ratios.
    latitude = PHI**-3
    transverse_radius = math.sqrt(1.0 - latitude**2)
    reference_vertices = np.array(
        [
            (
                transverse_radius * math.cos(2.0 * math.pi * index / 5.0),
                transverse_radius * math.sin(2.0 * math.pi * index / 5.0),
            )
            for index in range(5)
        ]
    )
    fivefold_residual = 0.0
    for coherence in (1.0, 0.75, 0.25):
        vertices = coherence * reference_vertices
        radii = np.linalg.norm(vertices, axis=1)
        side = float(np.linalg.norm(vertices[0] - vertices[1]))
        diagonal = float(np.linalg.norm(vertices[0] - vertices[2]))
        fivefold_residual = max(
            fivefold_residual,
            float(np.max(np.abs(radii - coherence * transverse_radius))),
            abs(side - coherence * np.linalg.norm(reference_vertices[0] - reference_vertices[1])),
            abs(diagonal / side - PHI),
        )
    collapsed = np.zeros_like(reference_vertices)
    fivefold_residual = max(
        fivefold_residual, float(np.max(np.linalg.norm(collapsed - collapsed[0], axis=1)))
    )
    print(f"LB7 fivefold visibility: residual={fivefold_residual:.3e}")
    if fivefold_residual > TOL:
        failures.append("LB7")

    if failures:
        print(f"FAIL: {', '.join(failures)}")
        return 1
    print("PASS: LB1-LB7 loop-to-bubble projection identities verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
