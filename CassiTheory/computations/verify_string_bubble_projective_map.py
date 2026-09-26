"""Verify the frozen string-to-bubble projective-map identities."""

from __future__ import annotations

import cmath
import math


PHI = (1.0 + math.sqrt(5.0)) / 2.0
AXES = (3.0, 2.0, 1.25)
THETA_PHI = math.acos(PHI**-3)
TOL = 1.0e-12


def max_abs(values: tuple[float, ...]) -> float:
    return max(abs(value) for value in values)


def bloch(theta: float, delta: float, gamma: float = 0.0) -> tuple[float, float, float]:
    z_y = cmath.exp(1j * gamma) * math.cos(theta / 2.0)
    z_i = cmath.exp(1j * (gamma + delta)) * math.sin(theta / 2.0)
    density = abs(z_y) ** 2 + abs(z_i) ** 2
    cross = z_y.conjugate() * z_i
    return (
        2.0 * cross.real / density,
        2.0 * cross.imag / density,
        (abs(z_y) ** 2 - abs(z_i) ** 2) / density,
    )


def shell_map(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(axis * value for axis, value in zip(AXES, vector, strict=True))


def affine_rotate(
    vector: tuple[float, float, float], delta: float
) -> tuple[float, float, float]:
    normalized = tuple(value / axis for value, axis in zip(vector, AXES, strict=True))
    cosine = math.cos(delta)
    sine = math.sin(delta)
    rotated = (
        cosine * normalized[0] - sine * normalized[1],
        sine * normalized[0] + cosine * normalized[1],
        normalized[2],
    )
    return shell_map(rotated)


def distance_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def cross_2d(a: tuple[float, float], b: tuple[float, float]) -> float:
    return a[0] * b[1] - a[1] * b[0]


def line_parameter(
    p0: tuple[float, float],
    p1: tuple[float, float],
    q0: tuple[float, float],
    q1: tuple[float, float],
) -> float:
    r = (p1[0] - p0[0], p1[1] - p0[1])
    s = (q1[0] - q0[0], q1[1] - q0[1])
    displacement = (q0[0] - p0[0], q0[1] - p0[1])
    return cross_2d(displacement, s) / cross_2d(r, s)


def diagonal_fractions(vertices: list[tuple[float, float]]) -> tuple[float, float, float]:
    star_edges = ((0, 2), (2, 4), (4, 1), (1, 3), (3, 0))
    first = star_edges[0]
    parameters = sorted(
        line_parameter(
            vertices[first[0]],
            vertices[first[1]],
            vertices[edge[0]],
            vertices[edge[1]],
        )
        for edge in (star_edges[2], star_edges[3])
    )
    return (parameters[0], parameters[1] - parameters[0], 1.0 - parameters[1])


def qi(rho: float, theta: float) -> float:
    deviation = (PHI**2 * math.cos(theta) - PHI**-1) / 2.0
    return 1.0 / (1.0 + deviation**2 + PHI**-2 / rho**2)


def meridional_rate(rho: float, lam: float, theta: float) -> tuple[float, float]:
    epsilon = rho * (PHI**2 * math.cos(theta) - PHI**-1) / 2.0
    kappa = lam * (1.0 - qi(rho, theta))
    s_dot = -2.0 * kappa * epsilon / rho
    direct = -s_dot / math.sin(theta)
    formula = kappa * (PHI**2 * math.cos(theta) - PHI**-1) / math.sin(theta)
    return direct, formula


def verify() -> int:
    failures: list[str] = []

    sphere_residual = 0.0
    shell_residual = 0.0
    phase_residual = 0.0
    orbit_residual = 0.0
    for theta_index in range(21):
        theta = math.pi * theta_index / 20.0
        meridian = shell_map((math.sin(theta), 0.0, math.cos(theta)))
        for delta_index in range(17):
            delta = 2.0 * math.pi * delta_index / 17.0
            vector = bloch(theta, delta)
            phased = bloch(theta, delta, gamma=0.37)
            point = shell_map(vector)
            direct = shell_map(
                (
                    math.sin(theta) * math.cos(delta),
                    math.sin(theta) * math.sin(delta),
                    math.cos(theta),
                )
            )
            orbit = affine_rotate(meridian, delta)
            sphere_residual = max(
                sphere_residual,
                abs(sum(component**2 for component in vector) - 1.0),
            )
            shell_residual = max(
                shell_residual,
                abs(sum((value / axis) ** 2 for value, axis in zip(point, AXES, strict=True)) - 1.0),
            )
            phase_residual = max(
                phase_residual,
                max_abs(tuple(a - b for a, b in zip(vector, phased, strict=True))),
            )
            orbit_residual = max(
                orbit_residual,
                max_abs(tuple(a - b for a, b in zip(orbit, direct, strict=True))),
            )

    sb1 = max(sphere_residual, shell_residual, phase_residual)
    print(f"SB1 projective shell map: residual={sb1:.3e}")
    if sb1 > TOL:
        failures.append("SB1")

    print(f"SB2 string orbit: residual={orbit_residual:.3e}")
    if orbit_residual > TOL:
        failures.append("SB2")

    radius = math.sin(THETA_PHI)
    normalized_vertices = [
        (radius * math.cos(2.0 * math.pi * index / 5.0), radius * math.sin(2.0 * math.pi * index / 5.0))
        for index in range(5)
    ]
    affine_vertices = [(AXES[0] * x, AXES[1] * y) for x, y in normalized_vertices]
    chord_ratio = distance_2d(normalized_vertices[0], normalized_vertices[2]) / distance_2d(
        normalized_vertices[0], normalized_vertices[1]
    )
    expected_fractions = (PHI**-2, PHI**-3, PHI**-2)
    normalized_fractions = diagonal_fractions(normalized_vertices)
    affine_fractions = diagonal_fractions(affine_vertices)
    sb3 = max(
        abs(chord_ratio - PHI),
        max_abs(tuple(a - b for a, b in zip(normalized_fractions, expected_fractions, strict=True))),
        max_abs(tuple(a - b for a, b in zip(affine_fractions, expected_fractions, strict=True))),
    )
    print(
        "SB3 fivefold orbit: "
        f"chord_ratio={chord_ratio:.12f}, fractions={normalized_fractions}, residual={sb3:.3e}"
    )
    if sb3 > TOL:
        failures.append("SB3")

    rho = 1.7
    lam = 0.02
    rate_residual = 0.0
    direction_ok = True
    for theta in (THETA_PHI - 0.4, THETA_PHI - 0.2, THETA_PHI + 0.2, THETA_PHI + 0.4):
        direct, formula = meridional_rate(rho, lam, theta)
        rate_residual = max(rate_residual, abs(direct - formula))
        direction_ok &= formula > 0.0 if theta < THETA_PHI else formula < 0.0
    equilibrium_rate = abs(meridional_rate(rho, lam, THETA_PHI)[1])
    sb4 = max(rate_residual, equilibrium_rate)
    print(
        "SB4 canonical meridional drift: "
        f"residual={sb4:.3e}, direction={'PASS' if direction_ok else 'FAIL'}"
    )
    if sb4 > TOL or not direction_ok:
        failures.append("SB4")

    loop_phase = math.pi * (1.0 - PHI**-3)
    connection_delta = (1.0 - math.cos(THETA_PHI)) / 2.0
    step_phase = connection_delta * (2.0 * math.pi / 5.0)
    sb5 = abs(5.0 * step_phase - loop_phase)
    print(
        "SB5 projective connection: "
        f"loop={loop_phase:.12f}, step={step_phase:.12f}, residual={sb5:.3e}"
    )
    if sb5 > TOL:
        failures.append("SB5")

    if failures:
        print(f"FAIL: {', '.join(failures)}")
        return 1
    print("PASS: SB1-SB5 string-bubble projective-map identities verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(verify())
