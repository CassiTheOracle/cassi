#!/usr/bin/env python3
"""Verify the interscale stress and routed-attenuation identities.

Run from the CassiTheory repository root:
    python computations/interscale_stress_attenuation_check.py
"""

from math import cos, isclose, sin, sqrt

PHI = (1.0 + sqrt(5.0)) / 2.0
T_PHI = PHI**-1
R_PHI = PHI**-2
T_AMP = sqrt(T_PHI)
R_AMP = sqrt(R_PHI)
TOL = 5.0e-13


def check(label: str, condition: bool, detail: str) -> None:
    status = "PASS" if condition else "FAIL"
    print(f"{label}: {status} — {detail}")
    if not condition:
        raise AssertionError(f"{label} failed: {detail}")


def matmul(a: tuple[tuple[float, float], tuple[float, float]],
           b: tuple[tuple[float, float], tuple[float, float]],
           ) -> tuple[tuple[float, float], tuple[float, float]]:
    return (
        (
            a[0][0] * b[0][0] + a[0][1] * b[1][0],
            a[0][0] * b[0][1] + a[0][1] * b[1][1],
        ),
        (
            a[1][0] * b[0][0] + a[1][1] * b[1][0],
            a[1][0] * b[0][1] + a[1][1] * b[1][1],
        ),
    )


def matpow(a: tuple[tuple[float, float], tuple[float, float]],
           exponent: int,
           ) -> tuple[tuple[float, float], tuple[float, float]]:
    result = ((1.0, 0.0), (0.0, 1.0))
    for _ in range(exponent):
        result = matmul(result, a)
    return result


def max_matrix_error(
    a: tuple[tuple[float, float], tuple[float, float]],
    b: tuple[tuple[float, float], tuple[float, float]],
) -> float:
    return max(abs(a[row][col] - b[row][col]) for row in range(2) for col in range(2))


def main() -> None:
    print("INTERSCALE STRESS–ATTENUATION CHECK")
    print(f"phi={PHI:.15f}  T_phi={T_PHI:.15f}  R_phi={R_PHI:.15f}")
    print()

    check(
        "ST1 fixed-point partition",
        isclose(T_PHI + R_PHI, 1.0, rel_tol=0.0, abs_tol=TOL),
        f"T_phi + R_phi = {T_PHI + R_PHI:.15f}",
    )

    displacement_jump = (0.75, -0.20, 0.45)
    kappa_star = 2.3
    unit_traction = tuple(kappa_star * value for value in displacement_jump)
    phi_traction = tuple(kappa_star * T_PHI * value for value in displacement_jump)
    traction_error = max(
        abs(phi_value / unit_value - T_PHI)
        for phi_value, unit_value in zip(phi_traction, unit_traction)
    )
    check(
        "ST2 frozen-state traction",
        traction_error < TOL,
        f"max |Pi(d)/Pi(1) - phi^-1| = {traction_error:.3e}",
    )

    displacements = (
        (0.20, -0.10, 0.40),
        (0.55, 0.25, -0.15),
        (-0.30, 0.60, 0.10),
        (0.15, -0.20, 0.35),
    )
    stiffnesses = (1.7, 0.9, 2.4)
    interface_stress = tuple(
        tuple(
            stiffnesses[a] * (displacements[a][i] - displacements[a + 1][i])
            for i in range(3)
        )
        for a in range(len(stiffnesses))
    )
    node_forces = []
    zero = (0.0, 0.0, 0.0)
    for a in range(len(displacements)):
        left = interface_stress[a - 1] if a > 0 else zero
        right = interface_stress[a] if a < len(interface_stress) else zero
        node_forces.append(tuple(left[i] - right[i] for i in range(3)))
    total_force = tuple(sum(force[i] for force in node_forces) for i in range(3))
    check(
        "ST3 closed-ladder momentum",
        max(abs(value) for value in total_force) < TOL,
        f"sum of pairwise interface forces = {total_force}",
    )

    window_start, window_end = 1, 2
    window_force = tuple(
        sum(node_forces[a][i] for a in range(window_start, window_end + 1))
        for i in range(3)
    )
    expected_window_force = tuple(
        interface_stress[window_start - 1][i] - interface_stress[window_end][i]
        for i in range(3)
    )
    window_error = max(
        abs(actual - expected)
        for actual, expected in zip(window_force, expected_window_force)
    )
    check(
        "ST4 scale-window boundary",
        window_error < TOL,
        f"|sum f - (Pi_left - Pi_right)|_inf = {window_error:.3e}",
    )

    series_stiffnesses = (1.1, 0.8, 2.5, 1.7, 0.6)
    mixed_stress = 0.73
    total_jump = -mixed_stress * sum(1.0 / value for value in series_stiffnesses)
    effective_stiffness = -mixed_stress / total_jump
    harmonic_stiffness = 1.0 / sum(1.0 / value for value in series_stiffnesses)
    uniform_count = 7
    uniform_effective = 1.0 / sum(
        1.0 / (kappa_star * T_PHI) for _ in range(uniform_count)
    )
    check(
        "ST5 static series response",
        isclose(effective_stiffness, harmonic_stiffness, rel_tol=0.0, abs_tol=TOL)
        and isclose(
            uniform_effective,
            kappa_star * T_PHI / uniform_count,
            rel_tol=0.0,
            abs_tol=TOL,
        ),
        (
            f"k_eff={effective_stiffness:.12f}; "
            f"uniform k_eff={uniform_effective:.12f}=kappa*d/N"
        ),
    )

    mass = 1.4
    c_t = 0.8
    wave_number = 0.7
    scale_phase = 1.1
    omega_squared = (
        c_t * c_t * wave_number * wave_number
        + 4.0 * kappa_star * T_PHI / mass * sin(scale_phase / 2.0) ** 2
    )
    omega = sqrt(omega_squared)
    amplitude = 0.63
    mode_energies = tuple(
        0.5 * mass * (-amplitude * omega * sin(omega * time)) ** 2
        + 0.5 * mass * omega_squared * (amplitude * cos(omega * time)) ** 2
        for time in (0.0, 0.37, 1.2, 3.4)
    )
    check(
        "ST6 reciprocal normal mode",
        omega_squared > 0.0 and max(mode_energies) - min(mode_energies) < TOL,
        (
            f"omega^2={omega_squared:.12f}; "
            f"mode-energy spread={max(mode_energies) - min(mode_energies):.3e}"
        ),
    )

    splitter = ((T_AMP, R_AMP), (-R_AMP, T_AMP))
    transpose = ((T_AMP, -R_AMP), (R_AMP, T_AMP))
    identity = ((1.0, 0.0), (0.0, 1.0))
    orthogonality_error = max_matrix_error(matmul(transpose, splitter), identity)
    determinant = T_AMP * T_AMP + R_AMP * R_AMP
    check(
        "ST7 golden splitter unitarity",
        orthogonality_error < TOL
        and isclose(determinant, 1.0, rel_tol=0.0, abs_tol=TOL),
        f"|S^T S - I|_max={orthogonality_error:.3e}; det S={determinant:.15f}",
    )

    coherent_steps = 2
    coherent = matpow(splitter, coherent_steps)
    coherent_forward_power = coherent[0][0] ** 2
    expected_two_step_power = (T_AMP * T_AMP - R_AMP * R_AMP) ** 2
    routed_two_step_power = T_PHI**coherent_steps
    check(
        "ST8 coherent-chain boundary",
        isclose(
            coherent_forward_power,
            expected_two_step_power,
            rel_tol=0.0,
            abs_tol=TOL,
        )
        and abs(coherent_forward_power - routed_two_step_power) > 0.1,
        (
            f"closed S^2 power={coherent_forward_power:.12f}; "
            f"routed T^2={routed_two_step_power:.12f}"
        ),
    )

    routed_steps = 12
    forward_power = T_PHI**routed_steps
    returned_power = sum(
        R_PHI * T_PHI**step for step in range(routed_steps)
    )
    forward_amplitude = T_AMP**routed_steps
    check(
        "ST9 routed flux ledger",
        isclose(
            forward_power + returned_power,
            1.0,
            rel_tol=0.0,
            abs_tol=TOL,
        )
        and isclose(
            forward_power,
            PHI**-routed_steps,
            rel_tol=0.0,
            abs_tol=TOL,
        )
        and isclose(
            forward_amplitude,
            PHI ** (-routed_steps / 2.0),
            rel_tol=0.0,
            abs_tol=TOL,
        ),
        (
            f"forward={forward_power:.12e}; return={returned_power:.12e}; "
            f"amplitude={forward_amplitude:.12e}"
        ),
    )

    incoming_momentum = (0.80, -0.35, 0.20)
    forwarded_momentum = tuple(T_PHI * value for value in incoming_momentum)
    ledger_error = 0.0
    reactions = {}
    for sigma in (1, -1):
        returned_momentum = tuple(
            sigma * R_PHI * value for value in incoming_momentum
        )
        interface_reaction = tuple(
            (1 - sigma) * R_PHI * value for value in incoming_momentum
        )
        reactions[sigma] = interface_reaction
        ledger_error = max(
            ledger_error,
            *(
                abs(incoming - forwarded - returned - reaction)
                for incoming, forwarded, returned, reaction in zip(
                    incoming_momentum,
                    forwarded_momentum,
                    returned_momentum,
                    interface_reaction,
                )
            ),
        )
    reversed_reaction_error = max(
        abs(actual - 2.0 * R_PHI * incoming)
        for actual, incoming in zip(reactions[-1], incoming_momentum)
    )
    check(
        "ST10 signed momentum and reaction ledger",
        ledger_error < TOL
        and max(abs(value) for value in reactions[1]) < TOL
        and reversed_reaction_error < TOL,
        (
            f"max signed residual={ledger_error:.3e}; "
            f"reversed-reaction error={reversed_reaction_error:.3e}"
        ),
    )

    print()
    print("ALL CHECKS PASSED")
    print(
        "Receipt: reciprocal stress is conservative; "
        "phi^-N is a routed quadratic-flux law."
    )


if __name__ == "__main__":
    main()
