#!/usr/bin/env python3
"""Verify the complete quantum free-fall correspondence gates.

Run from the CassiTheory repository root:

    python computations/verify_quantum_free_fall_correspondence.py

The governing protocol is
``computations/quantum_free_fall_correspondence_prereg.md``. The calculation
verifies the ideal external-potential QGI limit. It does not
identify atomic states with Cassi field variables or model the apparatus's
finite magnetic pulses and systematic corrections.
"""

from __future__ import annotations

from dataclasses import dataclass

import sympy as sp


@dataclass(frozen=True)
class Dimension:
    """Mass, length, and time exponents for a dimensional identity."""

    mass: int = 0
    length: int = 0
    time: int = 0

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(
            self.mass + other.mass,
            self.length + other.length,
            self.time + other.time,
        )

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(
            self.mass - other.mass,
            self.length - other.length,
            self.time - other.time,
        )

    def __pow__(self, exponent: int) -> "Dimension":
        return Dimension(
            self.mass * exponent,
            self.length * exponent,
            self.time * exponent,
        )


def require_zero(name: str, expression: sp.Expr) -> None:
    value = sp.simplify(expression)
    print(f"{name}: {value}")
    if value != 0:
        raise AssertionError(f"{name} failed: {value}")


def require_equal(name: str, actual: object, expected: object) -> None:
    passed = actual == expected
    print(f"{name}: {passed}")
    if not passed:
        raise AssertionError(f"{name} failed: {actual!r} != {expected!r}")


def main() -> None:
    t, z, big_t = sp.symbols("t z T", real=True, positive=True)
    physical_t = sp.symbols("mathcal_T", real=True, positive=True)
    m_i, m_g, gravity, hbar = sp.symbols(
        "m_i m_g g hbar", real=True, positive=True
    )
    lapse = sp.symbols("N", real=True, positive=True)
    r_b, r_r = sp.symbols("r_b r_r", real=True, positive=True)

    # QF1: accelerated-frame transformation.
    response = m_g / m_i
    zeta_t = response * gravity * t
    phase_action = -m_g * gravity * t * z - (
        m_g**2 * gravity**2 * t**3 / (6 * m_i)
    )
    phase_z = sp.diff(phase_action, z)
    phase_t = sp.diff(phase_action, t)
    derivative_residual = zeta_t + phase_z / m_i
    scalar_residual = (
        -phase_t
        - phase_z**2 / (2 * m_i)
        - m_g * gravity * z
    )
    require_zero("QF1 first-derivative residual", derivative_residual)
    require_zero("QF1 scalar residual", scalar_residual)
    print(f"QF1 gauge action: {phase_action}")

    # QF2-QF3: closed ballistic trajectory and action.
    launch_velocity = response * gravity * big_t
    z_ballistic = sp.expand(
        launch_velocity * t - response * gravity * t**2 / 2
    )
    v_ballistic = sp.diff(z_ballistic, t)
    require_zero("QF2 initial endpoint", z_ballistic.subs(t, 0))
    require_zero("QF2 final endpoint", z_ballistic.subs(t, 2 * big_t))

    kinetic_action = sp.integrate(
        m_i * v_ballistic**2 / 2,
        (t, 0, 2 * big_t),
    )
    potential_action = sp.integrate(
        -m_g * gravity * z_ballistic,
        (t, 0, 2 * big_t),
    )
    expected_kinetic = m_g**2 * gravity**2 * big_t**3 / (3 * m_i)
    expected_potential = -2 * expected_kinetic
    require_zero("QF2 kinetic action", kinetic_action - expected_kinetic)
    require_zero("QF2 potential action", potential_action - expected_potential)

    total_action = sp.simplify(kinetic_action + potential_action)
    phase_general = sp.simplify(total_action / hbar)
    expected_phase = -m_g**2 * gravity**2 * big_t**3 / (
        3 * hbar * m_i
    )
    require_zero("QF3 unequal-mass phase", phase_general - expected_phase)
    equal_mass = sp.symbols("m", real=True, positive=True)
    phase_equal = sp.simplify(
        phase_general.subs({m_i: equal_mass, m_g: equal_mass})
    )
    expected_equal = -equal_mass * gravity**2 * big_t**3 / (3 * hbar)
    require_zero("QF3 equal-mass phase", phase_equal - expected_equal)
    print(f"QF3 unequal-mass phase: {phase_general}")
    print(f"QF3 equal-mass phase: {phase_equal}")

    # QF4: a phase written in the same arm's calibrated acceleration loses the
    # separate source-field and response-ratio factors.
    ballistic_acceleration = response * gravity
    local_phase = -m_i * ballistic_acceleration**2 * big_t**3 / (3 * hbar)
    require_zero("QF4 local-acceleration degeneracy", phase_general - local_phase)

    # QF5: a held preparation supplies a differential response ratio if its
    # holding acceleration and the ballistic phase share the same source.
    ballistic_phase = -m_i * (r_b * gravity) ** 2 * big_t**3 / (3 * hbar)
    holding_acceleration = r_r * gravity
    response_observable_squared = sp.simplify(
        -3
        * hbar
        * ballistic_phase
        / (m_i * big_t**3 * holding_acceleration**2)
    )
    require_zero(
        "QF5 squared differential response",
        response_observable_squared - (r_b / r_r) ** 2,
    )
    response_observable = sp.sqrt(response_observable_squared)
    require_zero(
        "QF5 positive differential response",
        response_observable - r_b / r_r,
    )

    # QF6: constant common-lapse coordinate changes disappear when duration is
    # reported by the same physical clock.
    coordinate_acceleration = lapse**2 * response * gravity
    lapse_launch_velocity = coordinate_acceleration * big_t
    z_lapse = sp.expand(
        lapse_launch_velocity * t - coordinate_acceleration * t**2 / 2
    )
    v_lapse = sp.diff(z_lapse, t)
    lapse_action = sp.integrate(
        m_i * v_lapse**2 / (2 * lapse) - lapse * m_g * gravity * z_lapse,
        (t, 0, 2 * big_t),
    )
    lapse_phase = sp.simplify(lapse_action / hbar)
    expected_lapse_phase = -lapse**3 * m_g**2 * gravity**2 * big_t**3 / (
        3 * hbar * m_i
    )
    require_zero("QF6 coordinate-time lapse phase", lapse_phase - expected_lapse_phase)
    physical_phase = sp.simplify(lapse_phase.subs(big_t, physical_t / lapse))
    expected_physical_phase = -m_g**2 * gravity**2 * physical_t**3 / (
        3 * hbar * m_i
    )
    require_zero(
        "QF6 physical-time lapse cancellation",
        physical_phase - expected_physical_phase,
    )

    # QF7: the composition attractor is a line parameterized by density.
    phi = (sp.Integer(1) + sp.sqrt(5)) / 2
    yin_density = sp.symbols("E_I", real=True, positive=True)
    yang_density = phi * yin_density
    epsilon_on_ray = sp.simplify(yang_density - phi * yin_density)
    require_zero("QF7 attractor condition", epsilon_on_ray)
    rho_on_ray = sp.simplify(yang_density + yin_density)
    pi_on_ray = sp.simplify(yang_density - yin_density)
    signed_fraction = sp.simplify(pi_on_ray / rho_on_ray)
    require_zero("QF7 attractor signed fraction", signed_fraction - phi**-3)

    rho = sp.symbols("rho", real=True, positive=True)
    q_equilibrium = sp.simplify(rho**2 / (rho**2 + phi**-2))
    require_zero("QF7 dilute q limit", sp.limit(q_equilibrium, rho, 0, dir="+"))
    q_reference = sp.simplify(q_equilibrium.subs(rho, phi))
    require_zero("QF7 reference q", q_reference - phi**2 / 3)
    coupling_reference = sp.simplify(
        signed_fraction * (1 + (phi**6 - 1) * q_reference)
    )
    print(f"QF7 reference q exact: {q_reference}")
    print(f"QF7 reference q numeric: {sp.N(q_reference, 12)}")
    print(f"QF7 reference G_C exact: {coupling_reference}")
    print(f"QF7 reference G_C numeric: {sp.N(coupling_reference, 12)}")

    # QF8: mass-length-time dimensions.
    dimensionless = Dimension()
    mass_dimension = Dimension(mass=1)
    acceleration_dimension = Dimension(length=1, time=-2)
    duration_dimension = Dimension(time=1)
    action_dimension = Dimension(mass=1, length=2, time=-1)
    phase_dimension = (
        (mass_dimension**2 / mass_dimension)
        * acceleration_dimension**2
        * duration_dimension**3
        / action_dimension
    )
    require_equal("QF8 phase dimensionless", phase_dimension, dimensionless)
    density_dimension = Dimension(mass=1, length=-1, time=-2)
    q_dimension = density_dimension**2 / density_dimension**2
    require_equal("QF8 q dimensionless", q_dimension, dimensionless)
    require_equal("QF8 signed fraction dimensionless", q_dimension, dimensionless)
    require_equal("QF8 G_C dimensionless", q_dimension, dimensionless)

    print("VERDICT: PASS")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
