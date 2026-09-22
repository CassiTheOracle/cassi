#!/usr/bin/env python
"""The material transport of the coherence modulus of a tube.

Verifies, on the exact Arnold-Beltrami-Childress flow (an unsteady viscous
Navier-Stokes solution, Beltrami so that omega = u, with curved vortex lines and a
time-independent vorticity direction), that

  * the vorticity flux through a material surface element is conserved up to
    viscosity: dGamma/dt = nu integral Delta omega . N dA, so the tube radius
    a with a^2 = Gamma / (pi |omega|) obeys D_tau log a = -ell/2;
  * the enstrophy identity turns that into
    D_tau log(kappa a) = D_tau log kappa - (1/4) D_tau log e
                         + (1/2) nu omega.Delta omega / |omega|^2;
  * the integrated form closes along a material trajectory;
  * the viscous term is capped by Delta|omega| at a local maximum of |omega|.

Usage:
    python computations/verify_navier_stokes_tube_modulus_transport.py

Exit status is 0 only when every check passes.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

NU = 0.05
STEP = 1.0e-3
HORIZON = 1.0
PATCH_SCALE = 1.0e-4
QUADRATURE_ORDER = 3
ENSTROPHY_TOLERANCE = 1.0e-10
FLUX_TOLERANCE = 1.0e-3
RADIUS_TOLERANCE = 1.0e-3
INTEGRAL_TOLERANCE = 1.0e-3
CAP_TOLERANCE = 1.0e-9
SPACE_STEP = 1.0e-5


def trig(x: np.ndarray) -> tuple[float, ...]:
    return (
        math.sin(x[0]),
        math.cos(x[0]),
        math.sin(x[1]),
        math.cos(x[1]),
        math.sin(x[2]),
        math.cos(x[2]),
    )


def amplitude(time: float) -> float:
    return math.exp(-NU * time)


def velocity(x: np.ndarray, time: float) -> np.ndarray:
    sx, cx, sy, cy, sz, cz = trig(x)
    return amplitude(time) * np.array([sz + cy, sx + cz, sy + cx])


def velocity_gradient(x: np.ndarray, time: float) -> np.ndarray:
    sx, cx, sy, cy, sz, cz = trig(x)
    return amplitude(time) * np.array(
        [
            [0.0, -sy, cz],
            [cx, 0.0, -sz],
            [-sx, cy, 0.0],
        ]
    )


def velocity_hessian(x: np.ndarray, time: float) -> np.ndarray:
    """d_k grad u_ij of the ABC velocity, up to the amplitude."""
    sx, cx, sy, cy, sz, cz = trig(x)
    hessian = np.zeros((3, 3, 3))
    hessian[0, 1, 0] = -sx
    hessian[0, 2, 0] = -cx
    hessian[1, 0, 1] = -cy
    hessian[1, 2, 1] = -sy
    hessian[2, 0, 2] = -sz
    hessian[2, 1, 2] = -cz
    return amplitude(time) * hessian


def direction_gradient(x: np.ndarray, time: float) -> np.ndarray:
    """grad xi for the ABC flow, where xi = omega/|omega| = u/|u|."""
    speed = velocity(x, time)
    magnitude = float(np.linalg.norm(speed))
    gradient = velocity_gradient(x, time)
    return gradient / magnitude - np.outer(speed, (gradient @ speed)) / magnitude**3


def vorticity(x: np.ndarray, time: float) -> np.ndarray:
    """The ABC flow is Beltrami: omega = u."""
    return velocity(x, time)


def vorticity_gradient(x: np.ndarray, time: float) -> np.ndarray:
    """Beltrami: grad omega = grad u."""
    return velocity_gradient(x, time)


def frame(x: np.ndarray, time: float) -> dict[str, Any]:
    """Vorticity frame, strains and the local enstrophy terms."""
    omega = vorticity(x, time)
    gradient = vorticity_gradient(x, time)
    magnitude = float(np.linalg.norm(omega))
    direction = omega / magnitude
    gradient_magnitude = (gradient @ omega) / magnitude
    gradient_direction = (
        gradient / magnitude - np.outer(omega, gradient_magnitude) / magnitude**2
    )
    curvature_vector = gradient_direction @ direction
    curvature = float(np.linalg.norm(curvature_vector))
    normal = curvature_vector / max(curvature, 1e-300)
    binormal = np.cross(direction, normal)
    strain = 0.5 * (gradient + gradient.T)
    stretch = float(direction @ strain @ direction)
    transverse = float(normal @ strain @ normal)
    binormal_strain = float(binormal @ strain @ binormal)
    laplacian = -omega
    production = float(omega @ laplacian)
    gradient_square = float(np.sum(gradient**2))
    laplacian_magnitude = (
        production + gradient_square - float(gradient_magnitude @ gradient_magnitude)
    ) / magnitude
    return {
        "omega": omega,
        "direction": direction,
        "magnitude": magnitude,
        "curvature": curvature,
        "normal": normal,
        "binormal": binormal,
        "stretch": stretch,
        "transverse": transverse,
        "binormal_strain": binormal_strain,
        "production": production,
        "laplacian_magnitude": laplacian_magnitude,
        "frame_trace": stretch + transverse + binormal_strain,
        "viscous": NU * production / magnitude**2,
        "magnitude_rate": -NU
        + float(velocity(x, time) @ gradient_magnitude) / magnitude,
    }


def curvature_transport(x: np.ndarray, time: float) -> float:
    """D_tau log kappa from the material transport of the curvature.

    With t = xi, D_tau t = (grad u)t - ell t + V and kappa n = (t.grad)t,

        D_tau kappa = n.[(At.grad)t + (t.grad)(At)] - 2 ell kappa
                      + n.[(V.grad)t + (t.grad)V],

    where the last bracket is the viscous direction transport of the vorticity
    equation.  This flow is Beltrami with Delta omega = -omega, so V vanishes.
    """
    current = frame(x, time)
    tangent = current["direction"]
    normal = current["normal"]
    stretch = current["stretch"]
    curvature = current["curvature"]
    matrix = velocity_gradient(x, time)
    second = velocity_hessian(x, time)
    direction_derivative = direction_gradient(x, time)
    transported = matrix @ tangent
    # (t.grad)(A t)
    total = np.einsum("k,kij,j->i", tangent, second, tangent) + matrix @ (
        direction_derivative @ tangent
    )
    # (A t . grad) t
    total = total + transported @ direction_derivative
    # the field commutator: D_tau(grad xi) = grad(D_tau xi) - (grad u) grad xi
    total = total - (matrix.T @ tangent) @ direction_derivative
    total = total - 2.0 * stretch * curvature * normal
    return float(normal @ total) / curvature


def curvature_material_rate(x: np.ndarray, time: float) -> float:
    """D_tau log kappa: the vorticity direction is time independent here."""
    speed = velocity(x, time)
    total = 0.0
    for axis in range(3):
        offset = np.zeros(3)
        offset[axis] = SPACE_STEP
        plus = math.log(frame(x + offset, time)["curvature"])
        minus = math.log(frame(x - offset, time)["curvature"])
        total += speed[axis] * (plus - minus) / (2.0 * SPACE_STEP)
    return total


def advance(
    x: np.ndarray, patch: np.ndarray, time: float, step: float
) -> tuple[np.ndarray, np.ndarray]:
    def point_rhs(state, t):
        return velocity(state, t)

    def patch_rhs(state, t):
        gradient = velocity_gradient(state, t)
        return np.array([gradient @ vector for vector in patch])

    k1 = point_rhs(x, time)
    p1 = patch_rhs(x, time)
    k2 = point_rhs(x + 0.5 * step * k1, time + 0.5 * step)
    p2 = patch_rhs(x + 0.5 * step * k1, time + 0.5 * step)
    k3 = point_rhs(x + 0.5 * step * k2, time + 0.5 * step)
    p3 = patch_rhs(x + 0.5 * step * k2, time + 0.5 * step)
    k4 = point_rhs(x + step * k3, time + step)
    p4 = patch_rhs(x + step * k3, time + step)
    new_x = x + (step / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
    new_patch = patch + (step / 6.0) * (p1 + 2.0 * p2 + 2.0 * p3 + p4)
    return new_x, new_patch


def patch_integrals(
    x: np.ndarray, patch: np.ndarray, time: float
) -> tuple[float, float, float]:
    """Vorticity and Laplacian-vorticity flux through the material parallelogram.

    Returns (area, integral omega.N dA, integral Delta omega.N dA) by tensor
    Gauss-Legendre quadrature; the flow is Beltrami, so Delta omega = -omega.
    """
    normal_vector = np.cross(patch[0], patch[1])
    area = float(np.linalg.norm(normal_vector))
    normal = normal_vector / area
    nodes, weights = np.polynomial.legendre.leggauss(QUADRATURE_ORDER)
    nodes = 0.5 * (nodes + 1.0)
    weights = 0.5 * weights
    total = 0.0
    for i, u in enumerate(nodes):
        for j, v in enumerate(nodes):
            point = x + u * patch[0] + v * patch[1]
            total += weights[i] * weights[j] * float(vorticity(point, time) @ normal)
    return area, total * area, -total * area


def run_trajectory(start: np.ndarray, step: float) -> dict[str, np.ndarray]:
    time = 0.0
    x = np.array(start, dtype=float)
    initial = frame(x, time)
    direction = initial["direction"]
    normal = np.cross(direction, np.array([0.0, 0.0, 1.0]))
    if float(np.linalg.norm(normal)) < 1.0e-8:
        normal = np.cross(direction, np.array([0.0, 1.0, 0.0]))
    normal = normal / float(np.linalg.norm(normal))
    binormal = np.cross(direction, normal)
    patch = PATCH_SCALE * np.array([normal, binormal])
    records: dict[str, list[Any]] = {key: [] for key in (
        "time", "magnitude", "curvature", "area", "flux", "stretch", "viscous",
        "laplacian_magnitude", "transverse_plus_binormal", "frame_trace",
        "magnitude_rate", "curvature_rate", "curvature_rate_fd", "flux_rate_exact",
    )}
    steps = int(round(HORIZON / step))
    for index in range(steps + 1):
        current = frame(x, time)
        area, flux, laplacian_flux = patch_integrals(x, patch, time)
        records["time"].append(time)
        records["magnitude"].append(current["magnitude"])
        records["curvature"].append(current["curvature"])
        records["area"].append(area)
        records["flux"].append(flux)
        records["stretch"].append(current["stretch"])
        records["viscous"].append(current["viscous"])
        records["laplacian_magnitude"].append(current["laplacian_magnitude"])
        records["transverse_plus_binormal"].append(
            current["transverse"] + current["binormal_strain"]
        )
        records["frame_trace"].append(current["frame_trace"])
        records["magnitude_rate"].append(current["magnitude_rate"])
        records["curvature_rate"].append(curvature_transport(x, time))
        records["curvature_rate_fd"].append(curvature_material_rate(x, time))
        records["flux_rate_exact"].append(
            NU * laplacian_flux / max(abs(flux), 1e-300)
        )
        if index < steps:
            x, patch = advance(x, patch, time, step)
            time = (index + 1) * step
    return {key: np.asarray(value) for key, value in records.items()}


def trapezoid(values: np.ndarray, time: np.ndarray) -> np.ndarray:
    increments = 0.5 * (values[1:] + values[:-1]) * np.diff(time)
    return np.concatenate([[0.0], np.cumsum(increments)])


def main() -> int:
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    print("The material transport of the coherence modulus")
    print("=" * 78)
    data = run_trajectory(np.array([1.1, 0.7, 0.4]), STEP)
    time = data["time"]
    coarse = run_trajectory(np.array([1.1, 0.7, 0.4]), 2.0 * STEP)

    # V1 the vorticity frame closes: the transverse trace is minus the axial stretch
    frame_residual = np.maximum(
        np.abs(data["frame_trace"]), np.abs(data["transverse_plus_binormal"] + data["stretch"])
    )
    worst = float(np.max(frame_residual))
    record(
        "V1 the vorticity frame closes, n.Sn + b.Sb = -ell",
        worst <= 1.0e-12,
        f"worst |n.Sn + b.Sb + xi.Sxi| = {worst:.2e} and worst |tr S| = "
        f"{float(np.max(np.abs(data['frame_trace']))):.2e} over {len(time)} samples",
    )

    # V2 the enstrophy identity along the trajectory, with analytic rates
    residual = data["magnitude_rate"] - data["stretch"] - data["viscous"]
    worst = float(np.max(np.abs(residual)))
    record(
        "V2 the enstrophy identity holds along the trajectory",
        worst <= ENSTROPHY_TOLERANCE,
        f"worst |D log|omega| - ell - nu omega.Delta omega/|omega|^2| = {worst:.2e}",
    )

    # V3 the flux-transport lemma on the exact solution, in integrated form
    flux_residual = np.log(data["flux"] / data["flux"][0]) - trapezoid(
        data["flux_rate_exact"], time
    )
    coarse_residual = np.log(coarse["flux"] / coarse["flux"][0]) - trapezoid(
        coarse["flux_rate_exact"], coarse["time"]
    )
    worst = float(np.max(np.abs(flux_residual)))
    coarse_worst = float(np.max(np.abs(coarse_residual)))
    record(
        "V3 the vorticity flux through the material element is conserved up to viscosity",
        worst <= FLUX_TOLERANCE and coarse_worst >= worst,
        f"worst |Delta log Gamma - integral nu integral Delta omega.N dA / Gamma| = "
        f"{worst:.2e} at step {STEP:g} against {coarse_worst:.2e} "
        f"at step {2.0 * STEP:g}; the flux decays at the viscous rate "
        f"nu(omega.Delta omega)/|omega|^2 = {float(np.mean(data['viscous'])):.6f}",
    )

    # V4 the tube radius from the flux obeys D_tau log a = -ell/2
    radius = np.sqrt(data["flux"] / (math.pi * data["magnitude"]))
    coarse_radius = np.sqrt(coarse["flux"] / (math.pi * coarse["magnitude"]))
    radius_residual = np.log(radius / radius[0]) + 0.5 * trapezoid(data["stretch"], time)
    coarse_radius_residual = np.log(coarse_radius / coarse_radius[0]) + 0.5 * trapezoid(
        coarse["stretch"], coarse["time"]
    )
    worst = float(np.max(np.abs(radius_residual)))
    coarse_worst = float(np.max(np.abs(coarse_radius_residual)))
    record(
        "V4 the flux-based tube radius falls at half the axial stretching",
        worst <= RADIUS_TOLERANCE and coarse_worst >= worst,
        f"worst |Delta log a + integral ell/2| = {worst:.2e} at step {STEP:g} against "
        f"{float(np.max(np.abs(coarse_radius_residual))):.2e} at step {2.0 * STEP:g}; "
        f"the flux moves {math.log(data['flux'][-1] / data['flux'][0]):+.6f} against "
        f"{-0.5 * math.log(data['magnitude'][-1] / data['magnitude'][0]):+.6f} from the "
        f"magnitude over the same window",
    )

    # V5 the integrated form of the modulus identity
    margin = data["curvature"] * radius

    def modulus_residual(recorded: dict[str, np.ndarray], steps: np.ndarray) -> np.ndarray:
        local_radius = np.sqrt(recorded["flux"] / (math.pi * recorded["magnitude"]))
        local_margin = recorded["curvature"] * local_radius
        integrated = (
            trapezoid(recorded["curvature_rate"], steps)
            - 0.5 * np.log(recorded["magnitude"] / recorded["magnitude"][0])
            + 0.5 * trapezoid(recorded["viscous"], steps)
        )
        return np.log(local_margin / local_margin[0]) - integrated

    residual = modulus_residual(data, time)
    coarse_residual = modulus_residual(coarse, coarse["time"])
    worst = float(np.max(np.abs(residual)))
    coarse_worst = float(np.max(np.abs(coarse_residual)))
    record(
        "V5 the integrated modulus identity closes along the trajectory",
        worst <= INTEGRAL_TOLERANCE and coarse_worst >= worst,
        f"worst residual {worst:.2e} at step {STEP:g} against {coarse_worst:.2e} at step "
        f"{2.0 * STEP:g} over {len(time)} samples, from the closed-form curvature rate; log margin moves "
        f"{math.log(margin[-1] / margin[0]):+.6f}, the enstrophy endpoint contributes "
        f"{-0.5 * math.log(data['magnitude'][-1] / data['magnitude'][0]):+.6f}, the "
        f"bending integral {trapezoid(data['curvature_rate'], time)[-1]:+.6f}, the "
        f"viscous integral {0.5 * trapezoid(data['viscous'], time)[-1]:+.6f}",
    )

    # V6 the viscous term against its cap where |omega| is locally maximal along n
    local_maximum = data["laplacian_magnitude"] < 0.0
    cap = 0.5 * NU * data["laplacian_magnitude"] / data["magnitude"]
    excess = 0.5 * data["viscous"] - cap
    worst = float(np.max(excess[local_maximum])) if bool(np.any(local_maximum)) else 0.0
    record(
        "V6 the viscous term stays under the cap where |omega| is locally maximal",
        worst <= CAP_TOLERANCE,
        f"{int(np.sum(local_maximum))} of {len(time)} samples at a local maximum along "
        f"the normal, worst excess {worst:.2e}",
    )

    print("=" * 78)
    # V7 the closed-form material transport of the vortex-line curvature
    curvature_residual = data["curvature_rate"] - data["curvature_rate_fd"]
    worst = float(np.max(np.abs(curvature_residual)))
    record(
        "V7 the curvature transport closes against its finite differences",
        worst <= 1.0e-8,
        f"worst |n.[(At.grad)t + (t.grad)(At) - ((grad u)^T t.grad)t] - 2 ell kappa "
        f"over kappa - D log kappa| = {worst:.2e} over {len(time)} samples; the viscous "
        f"direction transport V = nu[Delta omega - xi(omega.Delta omega)/|omega|]/|omega| "
        f"vanishes identically here, the flow being Beltrami with Delta omega = -omega",
    )

    failed = [item for item in checks if not item["passed"]]
    for item in checks:
        print(f"  [{'PASS' if item['passed'] else 'FAIL'}] {item['name']}: {item['detail']}")
    print(f"checks: {len(checks)}  failures: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
