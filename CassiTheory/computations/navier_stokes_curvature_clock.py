#!/usr/bin/env python
"""Curvature clock of the vorticity-direction coherence margin.

Block K tests the exact kinematic identity of
`turbulence/navier-stokes-tube-curvature-coherence.md`:

    D_t log(kappa a_n) = n.(d_s grad u)t / kappa + 2 n.Sn - 2 ell        (KC1)

on three closed-form incompressible deformations of a material curve whose
curvature and normal-direction width are known in closed form: a parabolic bend
of a straight tube, the tip of a ring in planar strain, and a ring in
axisymmetric strain.

Block D measures the same margin at the vorticity core of the retained helical
vortex-tube families evolved by the retained Fourier-Galerkin integrator.

Usage:
    python computations/navier_stokes_curvature_clock.py [--output DIR] [--quick]

Exit status is 0 only when every check passes.  --quick skips Block D and is a
development loop, not the declared run.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
DEPLETION_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
)
PROTOCOL_SCRIPT = ROOT / "computations" / "navier-stokes-curvature-clock-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs" / "navier_stokes_curvature_clock"
SCHEMA = "navier-stokes-curvature-clock-v1"

# Block K parameters
BEND_BETA = 0.35
STRAIN_ALPHA = 0.30
RING_RADIUS = 1.0
NORMAL_WIDTH = 0.25
SEGMENT_HALF_LENGTH = 0.4
CURVE_SAMPLES = 2001
CENTER_INDEX = CURVE_SAMPLES // 2
CURVE_ANGLE = np.linspace(-math.pi, math.pi, CURVE_SAMPLES)
RING_STEP = 2.0 * math.pi / (CURVE_SAMPLES - 1)
SEGMENT_STEP = 2.0 * SEGMENT_HALF_LENGTH / (CURVE_SAMPLES - 1)
RING_CURVE = np.stack(
    [
        RING_RADIUS * np.cos(CURVE_ANGLE),
        RING_RADIUS * np.sin(CURVE_ANGLE),
        np.zeros(CURVE_SAMPLES),
    ],
    axis=-1,
)
SEGMENT_CURVE = np.stack(
    [
        np.linspace(-SEGMENT_HALF_LENGTH, SEGMENT_HALF_LENGTH, CURVE_SAMPLES),
        np.zeros(CURVE_SAMPLES),
        np.zeros(CURVE_SAMPLES),
    ],
    axis=-1,
)
DERIVATIVE_STEP = 1.0e-5
WIDTH_OFFSET = 1.0e-3
QUADRATURE_ORDER = 8
INTERVAL_TOLERANCE = 1.0e-9
MARGIN_TOLERANCE = 1.0e-9

# Block D parameters (the retained helical-dynamic-depletion schedule)
CUTOFF = 16
GRID_FACTOR = 6
STEPS = 1024
NU = 0.1
T_END = 0.5
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
DYNAMIC_CASES = ("helix_wide", "helix_narrow", "helix_tight_pitch")
HELIX_CURVATURE = {"helix_wide": 0.48, "helix_narrow": 0.48, "helix_tight_pitch": 1.20}
MARGIN_POLE = 1.0
INTEGRITY_TOLERANCE = 1.0e-9
ANCHOR_FACTOR = 2.0
COEFFICIENT_FACTOR = 3.0
COEFFICIENT_CELLS = (1, 2, 4)

TIME_SAMPLES = (0.25, 0.30, 0.35, 0.40, 0.45)


def sha256(path: Path) -> str:
    """Blob-convention digest: line endings normalised, so a CRLF checkout agrees."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Block K: closed-form controls of the kinematic identity
# --------------------------------------------------------------------------


def center_geometry(
    points: np.ndarray, step: float
) -> tuple[np.ndarray, np.ndarray, float]:
    """Tangent, normal and curvature at the material point, fourth-order stencils."""
    index = CENTER_INDEX
    first = (
        points[index - 2]
        - 8.0 * points[index - 1]
        + 8.0 * points[index + 1]
        - points[index + 2]
    ) / (12.0 * step)
    second = (
        -points[index - 2]
        + 16.0 * points[index - 1]
        - 30.0 * points[index]
        + 16.0 * points[index + 1]
        - points[index + 2]
    ) / (12.0 * step * step)
    speed = float(np.linalg.norm(first))
    tangent = first / speed
    curvature_vector = second / speed**2 - first * float(first @ second) / speed**4
    curvature = float(np.linalg.norm(curvature_vector))
    normal = curvature_vector / max(curvature, 1e-300)
    return tangent, normal, curvature


def numeric_gradient(velocity, x: np.ndarray, step: float) -> np.ndarray:
    """grad[i, j] = d_j u_i at x by central differences of the analytic field."""
    gradient = np.zeros((3, 3))
    for j in range(3):
        offset = np.zeros(3)
        offset[j] = step
        gradient[:, j] = (velocity(x + offset) - velocity(x - offset)) / (2.0 * step)
    return gradient


def gradient_directional_derivative(
    velocity, x: np.ndarray, direction: np.ndarray, step: float
) -> np.ndarray:
    """(direction . grad) grad u at x by central differences of the gradient."""
    plus = numeric_gradient(velocity, x + step * direction, step)
    minus = numeric_gradient(velocity, x - step * direction, step)
    return (plus - minus) / (2.0 * step)


def material_width(deform, x0: np.ndarray, normal0: np.ndarray, time: float) -> float:
    """Half-extent along the material normal of a segment pushed forward by the map."""
    plus = deform(x0 + WIDTH_OFFSET * normal0, time)
    minus = deform(x0 - WIDTH_OFFSET * normal0, time)
    return NORMAL_WIDTH * float(np.linalg.norm(plus - minus)) / (2.0 * WIDTH_OFFSET)


def identity_terms(velocity, deform, curve, step, x0, normal0, time) -> dict[str, Any]:
    """Measured margin and the assembled right-hand side of (KC1) at one time."""
    points = deform(curve, time)
    tangent, normal, kappa = center_geometry(points, step)
    x = deform(x0, time)
    gradient = numeric_gradient(velocity, x, DERIVATIVE_STEP)
    strain = 0.5 * (gradient + gradient.T)
    second = gradient_directional_derivative(velocity, x, tangent, DERIVATIVE_STEP)
    stretch = float(tangent @ gradient @ tangent)
    transverse = float(normal @ strain @ normal)
    inhomogeneous = float(normal @ second @ tangent)
    width = material_width(deform, x0, normal0, time)
    return {
        "time": float(time),
        "kappa": kappa,
        "width": width,
        "margin": kappa * width,
        "tangent": tangent.tolist(),
        "normal": normal.tolist(),
        "stretch": stretch,
        "transverse": transverse,
        "inhomogeneous": inhomogeneous,
        "rate": inhomogeneous / kappa + 2.0 * transverse - 2.0 * stretch,
        "term_scale": abs(inhomogeneous) / kappa + 2.0 * abs(transverse) + 2.0 * abs(stretch),
    }


def quadrature_nodes() -> tuple[np.ndarray, np.ndarray]:
    nodes, weights = np.polynomial.legendre.leggauss(QUADRATURE_ORDER)
    return nodes, weights


def control_rows(
    name: str,
    velocity,
    deform,
    curve: np.ndarray,
    curve_step: float,
    x0: np.ndarray,
    normal0: np.ndarray,
    closed_form,
    times,
    parameters: dict[str, Any],
    closed_form_text: str,
) -> dict[str, Any]:
    rows = []
    for time in times:
        row = identity_terms(velocity, deform, curve, curve_step, x0, normal0, time)
        row["closed_form_margin"] = closed_form(time)
        row["margin_ratio"] = row["margin"] / row["closed_form_margin"]
        rows.append(row)

    nodes, weights = quadrature_nodes()
    intervals = []
    for left, right in zip(rows, rows[1:]):
        half = 0.5 * (right["time"] - left["time"])
        middle = 0.5 * (right["time"] + left["time"])
        integral = 0.0
        for node, weight in zip(nodes, weights):
            integral += weight * identity_terms(
                velocity, deform, curve, curve_step, x0, normal0, middle + half * node
            )["rate"]
        predicted = half * integral
        measured = math.log(right["margin"] / left["margin"])
        intervals.append(
            {
                "from": left["time"],
                "to": right["time"],
                "measured_increment": measured,
                "predicted_increment": predicted,
                "residual": measured - predicted,
                "pointwise_predicted": 0.5 * (left["rate"] + right["rate"]),
            }
        )
    return {
        "name": name,
        "parameters": parameters,
        "closed_form": closed_form_text,
        "material_point": x0.tolist(),
        "material_normal": normal0.tolist(),
        "rows": rows,
        "intervals": intervals,
    }


def build_controls() -> list[dict[str, Any]]:
    pole_time = 1.0 / (2.0 * BEND_BETA * NORMAL_WIDTH)
    parabola = control_rows(
        "parabolic_bend",
        lambda x: np.array([0.0, BEND_BETA * x[0] * x[0], 0.0]),
        lambda points, time: np.stack(
            [
                np.asarray(points)[..., 0],
                np.asarray(points)[..., 1]
                + BEND_BETA * np.asarray(points)[..., 0] ** 2 * time,
                np.asarray(points)[..., 2],
            ],
            axis=-1,
        ),
        SEGMENT_CURVE,
        SEGMENT_STEP,
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        lambda time: 2.0 * BEND_BETA * time * NORMAL_WIDTH,
        TIME_SAMPLES,
        {
            "beta": BEND_BETA,
            "normal_width": NORMAL_WIDTH,
            "pole_time": pole_time,
            "initial_curve": "segment along x through the origin",
        },
        "kappa(t) = 2 beta t, a_n constant, pole at t = 1/(2 beta a_n)",
    )
    pole_row = identity_terms(
        lambda x: np.array([0.0, BEND_BETA * x[0] * x[0], 0.0]),
        lambda points, time: np.stack(
            [
                np.asarray(points)[..., 0],
                np.asarray(points)[..., 1]
                + BEND_BETA * np.asarray(points)[..., 0] ** 2 * time,
                np.asarray(points)[..., 2],
            ],
            axis=-1,
        ),
        SEGMENT_CURVE,
        SEGMENT_STEP,
        np.array([0.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        pole_time,
    )
    pole_row["closed_form_margin"] = 2.0 * BEND_BETA * pole_time * NORMAL_WIDTH
    pole_row["margin_ratio"] = pole_row["margin"] / pole_row["closed_form_margin"]
    parabola["pole"] = pole_row
    ellipse = control_rows(
        "ellipse_tip",
        lambda x: np.array([STRAIN_ALPHA * x[0], -STRAIN_ALPHA * x[1], 0.0]),
        lambda points, time: np.stack(
            [
                np.asarray(points)[..., 0] * math.exp(STRAIN_ALPHA * time),
                np.asarray(points)[..., 1] * math.exp(-STRAIN_ALPHA * time),
                np.asarray(points)[..., 2],
            ],
            axis=-1,
        ),
        RING_CURVE,
        RING_STEP,
        np.array([RING_RADIUS, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        lambda time: (math.exp(3.0 * STRAIN_ALPHA * time) / RING_RADIUS)
        * NORMAL_WIDTH
        * math.exp(STRAIN_ALPHA * time),
        TIME_SAMPLES,
        {
            "alpha": STRAIN_ALPHA,
            "ring_radius": RING_RADIUS,
            "normal_width": NORMAL_WIDTH,
            "initial_curve": "circle of radius R in the xy-plane",
        },
        "kappa(t) = exp(3 alpha t)/R, a_n(t) = a_n(0) exp(alpha t)",
    )
    axisymmetric = control_rows(
        "axisymmetric_ring",
        lambda x: np.array(
            [
                0.5 * STRAIN_ALPHA * x[0],
                0.5 * STRAIN_ALPHA * x[1],
                -STRAIN_ALPHA * x[2],
            ]
        ),
        lambda points, time: np.stack(
            [
                np.asarray(points)[..., 0] * math.exp(0.5 * STRAIN_ALPHA * time),
                np.asarray(points)[..., 1] * math.exp(0.5 * STRAIN_ALPHA * time),
                np.asarray(points)[..., 2] * math.exp(-STRAIN_ALPHA * time),
            ],
            axis=-1,
        ),
        RING_CURVE,
        RING_STEP,
        np.array([RING_RADIUS, 0.0, 0.0]),
        np.array([-1.0, 0.0, 0.0]),
        lambda time: (math.exp(-0.5 * STRAIN_ALPHA * time) / RING_RADIUS)
        * NORMAL_WIDTH
        * math.exp(0.5 * STRAIN_ALPHA * time),
        TIME_SAMPLES,
        {
            "alpha": STRAIN_ALPHA,
            "ring_radius": RING_RADIUS,
            "normal_width": NORMAL_WIDTH,
            "initial_curve": "circle of radius R in the xy-plane",
        },
        "kappa(t) = exp(-alpha t/2)/R, a_n(t) = a_n(0) exp(alpha t/2), margin constant",
    )
    return [parabola, ellipse, axisymmetric]


# --------------------------------------------------------------------------
# Block D: the margin on retained Navier-Stokes trajectories
# --------------------------------------------------------------------------


def local_tensors(box, state) -> dict[str, Any]:
    """Raw local tensors and direction samples at the vorticity core."""
    import torch

    wn = box.wave_numbers
    omega_coefficients = box.curl(state)
    omega = box.grid(omega_coefficients)
    gradient_omega = box.grid(1j * omega_coefficients[..., :, None] * wn[..., None, :])
    magnitude = torch.linalg.vector_norm(omega, dim=-1)
    magnitude_coefficients = box.coefficients(magnitude)
    gradient_magnitude = box.grid(1j * magnitude_coefficients[..., None] * wn)
    hessian_magnitude = box.grid(
        -magnitude_coefficients[..., None, None]
        * wn[..., :, None]
        * wn[..., None, :]
    )
    velocity_gradient = box.grid(1j * state[..., :, None] * wn[..., None, :])
    second_velocity = torch.stack(
        [
            box.grid(
                1j
                * wn[..., index, None, None]
                * (1j * state[..., :, None] * wn[..., None, :])
            )
            for index in range(3)
        ],
        dim=-1,
    )

    flat = int(torch.argmax(magnitude).item())
    core = np.unravel_index(flat, tuple(int(size) for size in magnitude.shape))
    size = int(magnitude.shape[0])
    spacing = 2.0 * math.pi / size
    direction_field = omega / magnitude[..., None]
    core_direction = np.asarray(direction_field[core].detach().cpu().numpy(), dtype=float)
    samples = {}
    for cells in COEFFICIENT_CELLS:
        offset = np.rint(
            np.asarray(core, dtype=float) + cells * core_direction
        ).astype(int) % size
        neighbour = np.asarray(
            direction_field[tuple(int(value) for value in offset)]
            .detach()
            .cpu()
            .numpy(),
            dtype=float,
        )
        samples[f"cells_{cells}"] = {
            "cells": int(cells),
            "displacement": float(cells * spacing),
            "core": [int(value) for value in core],
            "target": [int(value) for value in offset],
            "direction": neighbour.tolist(),
        }

    def take(field):
        return np.asarray(field[core].detach().cpu().numpy(), dtype=float).tolist()

    return {
        "core": [int(value) for value in core],
        "grid_size": size,
        "spacing": float(spacing),
        "omega": take(omega),
        "gradient_omega": take(gradient_omega),
        "magnitude": float(magnitude[core].item()),
        "gradient_magnitude": take(gradient_magnitude),
        "hessian_magnitude": take(hessian_magnitude),
        "velocity_gradient": take(velocity_gradient),
        "second_velocity": take(second_velocity),
        "direction_samples": samples,
    }


def core_algebra(raw: dict[str, Any]) -> dict[str, Any]:
    """Derived margin, identity terms and coherence coefficient from raw tensors."""
    omega = np.asarray(raw["omega"], dtype=float)
    gradient_omega = np.asarray(raw["gradient_omega"], dtype=float)
    magnitude = float(raw["magnitude"])
    gradient_magnitude = np.asarray(raw["gradient_magnitude"], dtype=float)
    hessian_magnitude = np.asarray(raw["hessian_magnitude"], dtype=float)
    gradient_u = np.asarray(raw["velocity_gradient"], dtype=float)
    second_u = np.asarray(raw["second_velocity"], dtype=float)

    direction = omega / magnitude
    gradient_direction = (
        gradient_omega / magnitude
        - omega[:, None] * gradient_magnitude[None, :] / (magnitude * magnitude)
    )
    curvature_vector = np.einsum("j,ij->i", direction, gradient_direction)
    kappa = float(np.linalg.norm(curvature_vector))
    normal = curvature_vector / max(kappa, 1e-300)
    curvature_second = float(normal @ hessian_magnitude @ normal)
    width = (
        math.sqrt(abs(magnitude / curvature_second))
        if curvature_second != 0.0
        else float("inf")
    )
    strain = 0.5 * (gradient_u + gradient_u.T)
    stretch = float(direction @ gradient_u @ direction)
    transverse = float(normal @ strain @ normal)
    inhomogeneous = float(np.einsum("i,l,ijl,j->", normal, direction, second_u, direction))
    predicted = inhomogeneous / kappa + 2.0 * transverse - 2.0 * stretch
    coefficients = {}
    for key, sample in raw["direction_samples"].items():
        neighbour = np.asarray(sample["direction"], dtype=float)
        displacement = float(sample["displacement"])
        variation = float(np.linalg.norm(neighbour - direction))
        coefficients[key] = {
            "cells": sample["cells"],
            "displacement": displacement,
            "variation": variation,
            "coefficient": variation / (displacement * kappa) if kappa > 0.0 else float("inf"),
        }
    return {
        "direction": direction.tolist(),
        "normal": normal.tolist(),
        "kappa": kappa,
        "width": width,
        "margin": kappa * width,
        "stretch": stretch,
        "transverse": transverse,
        "inhomogeneous": inhomogeneous,
        "predicted_rate": predicted,
        "coherence_coefficient": coefficients,
    }


def integrate_case(case: dict[str, Any], long_trajectory, depletion) -> dict[str, Any]:
    box = long_trajectory.TorchGalerkinBox(CUTOFF, GRID_FACTOR * CUTOFF + 1)
    state, metadata = depletion.initial_state(case, box)
    dt = T_END / float(STEPS)
    rhs = box.right_hand_side(state)
    checkpoint_steps = {int(round(f * STEPS)) for f in CHECKPOINT_FRACTIONS}
    checkpoints: list[dict[str, Any]] = []
    maximum_divergence = 0.0
    maximum_energy_increment = 0.0
    previous_energy = None

    def record(index: int, state_tensor) -> None:
        observables = box.spectral_observables(state_tensor, rhs)
        raw = local_tensors(box, state_tensor)
        checkpoints.append(
            {
                "step": int(index),
                "time": float(index * dt),
                "raw": raw,
                "derived": core_algebra(raw),
                "observables": {
                    "kinetic_energy": float(observables["energy"]),
                    "enstrophy": float(observables["enstrophy"]),
                    "production": float(observables["production"]),
                    "divergence_residual": float(observables["divergence_residual"]),
                },
            }
        )

    record(0, state)
    previous_energy = checkpoints[0]["observables"]["kinetic_energy"]
    for index in range(STEPS):
        state = long_trajectory.rk4_update(box, state, dt, rhs)
        rhs = box.right_hand_side(state)
        energy = float(box.spectral_observables(state, rhs)["energy"])
        maximum_energy_increment = max(maximum_energy_increment, energy - previous_energy)
        previous_energy = energy
        if index + 1 in checkpoint_steps:
            record(index + 1, state)
    for row in checkpoints:
        maximum_divergence = max(maximum_divergence, row["observables"]["divergence_residual"])
    for earlier, later in zip(checkpoints, checkpoints[1:]):
        span = later["time"] - earlier["time"]
        earlier["measured_rate"] = float(
            math.log(later["derived"]["margin"] / earlier["derived"]["margin"]) / span
        )
        earlier["rate_interval"] = span
    return {
        "case": case["name"],
        "family": case["family"],
        "cutoff": CUTOFF,
        "grid_size": GRID_FACTOR * CUTOFF + 1,
        "steps": STEPS,
        "nu": NU,
        "horizon": T_END,
        "initial_state": {
            "normalization_error": float(metadata["normalization_error"]),
            "projection_error": float(metadata["projection_error"]),
            "state_divergence_residual": float(metadata["state_divergence_residual"]),
            "geometry": metadata["geometry"],
        },
        "maximum_divergence_residual": maximum_divergence,
        "maximum_energy_increment": maximum_energy_increment,
        "helix_curvature": HELIX_CURVATURE[case["name"]],
        "checkpoints": checkpoints,
    }


# --------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------


def build_receipt(quick: bool) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    print("Block K: closed-form controls of the kinematic identity")
    controls = build_controls()
    for control in controls:
        intervals = control["intervals"]
        worst = max(abs(item["residual"]) for item in intervals)
        record(
            f"KC1 {control['name']}: the margin increment matches the identity integral",
            worst <= INTERVAL_TOLERANCE,
            f"worst increment residual {worst:.2e} over {len(intervals)} intervals",
        )
        worst_ratio = max(abs(row["margin_ratio"] - 1.0) for row in control["rows"])
        record(
            f"KC2 {control['name']}: measured margin matches the closed form",
            worst_ratio <= MARGIN_TOLERANCE,
            f"worst relative deviation {worst_ratio:.2e}",
        )
    axisymmetric = next(c for c in controls if c["name"] == "axisymmetric_ring")
    worst_zero = max(abs(item["measured_increment"]) for item in axisymmetric["intervals"])
    record(
        "KC3 axisymmetric ring strain conserves the margin",
        worst_zero <= INTERVAL_TOLERANCE,
        f"largest measured margin increment {worst_zero:.2e} (predicted exactly zero)",
    )
    parabola = next(c for c in controls if c["name"] == "parabolic_bend")
    pole_row = parabola["pole"]
    record(
        "KC4 parabolic bend reaches the pole in finite time",
        abs(pole_row["margin"] - MARGIN_POLE) <= MARGIN_TOLERANCE,
        f"margin {pole_row['margin']:.12f} at the predicted pole time "
        f"{parabola['parameters']['pole_time']:.6f}",
    )

    dynamics = []
    if quick:
        print("Block D skipped (--quick)")
    else:
        print("Block D: retained helical tube families")
        long_trajectory = load_module("navier_stokes_long_trajectory", LONG_TRAJECTORY_SCRIPT)
        depletion = load_module("navier_stokes_helical_dynamic_depletion", DEPLETION_SCRIPT)
        for name in DYNAMIC_CASES:
            case = next(c for c in depletion.CASES if c["name"] == name)
            result = integrate_case(case, long_trajectory, depletion)
            dynamics.append(result)
            margins = [row["derived"]["margin"] for row in result["checkpoints"]]
            record(
                f"D2 {name}: the coherence margin stays inside the pole",
                max(margins) < MARGIN_POLE,
                f"largest margin {max(margins):.6f} over {len(margins)} checkpoints",
            )
            anchor = result["checkpoints"][0]["derived"]["kappa"]
            ratio = anchor / result["helix_curvature"]
            record(
                f"D3 {name}: measured core curvature anchors to the seeded helix",
                ANCHOR_FACTOR ** -1 <= ratio <= ANCHOR_FACTOR,
                f"measured {anchor:.4f} against analytic "
                f"{result['helix_curvature']:.4f} (ratio {ratio:.3f})",
            )
            coefficients = [
                row["derived"]["coherence_coefficient"]["cells_1"]["coefficient"]
                for row in result["checkpoints"]
            ]
            record(
                f"D4 {name}: the one-cell coherence coefficient sits near one",
                max(coefficients) <= COEFFICIENT_FACTOR
                and min(coefficients) >= 1.0 / COEFFICIENT_FACTOR,
                f"coefficient range {min(coefficients):.4f} to {max(coefficients):.4f}",
            )
            record(
                f"D1 {name}: integrity",
                result["maximum_divergence_residual"] <= INTEGRITY_TOLERANCE
                and result["maximum_energy_increment"] <= INTEGRITY_TOLERANCE
                and result["initial_state"]["normalization_error"] <= INTEGRITY_TOLERANCE,
                f"divergence {result['maximum_divergence_residual']:.2e}, "
                f"energy increment {result['maximum_energy_increment']:.2e}, "
                f"normalization {result['initial_state']['normalization_error']:.2e}",
            )
            print(
                f"  margins {name}: "
                + ", ".join(f"{value:.4f}" for value in margins)
            )
            print(
                f"  rates   {name}: "
                + ", ".join(
                    f"{row['measured_rate']:.4f}"
                    for row in result["checkpoints"]
                    if "measured_rate" in row
                )
            )

    status = "PASS" if all(check["passed"] for check in checks) else "FAIL"
    return {
        "schema": SCHEMA,
        "status": status,
        "verdict": status,
        "classification": (
            "CLOCK IDENTITY CONFIRMED / MARGIN BELOW THE POLE OVER THE DECLARED HORIZON"
            if status == "PASS"
            else "FAIL"
        ),
        "scope": {
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "backend": "numpy controls / torch-rocm dynamics",
            "identity": "D_t log(kappa a_n) = n.(d_s grad u)t/kappa + 2 n.Sn - 2 ell",
            "arbitrary_data_regularity": "UNRESOLVED",
            "time_integrability_of_the_modulus": "MEASURED ON THE DECLARED FAMILIES ONLY",
        },
        "parameters": {
            "bend_beta": BEND_BETA,
            "strain_alpha": STRAIN_ALPHA,
            "ring_radius": RING_RADIUS,
            "normal_width": NORMAL_WIDTH,
            "time_samples": list(TIME_SAMPLES),
            "quadrature_order": QUADRATURE_ORDER,
            "interval_tolerance": INTERVAL_TOLERANCE,
            "margin_tolerance": MARGIN_TOLERANCE,
            "cutoff": CUTOFF,
            "steps": STEPS,
            "nu": NU,
            "horizon": T_END,
            "checkpoint_fractions": list(CHECKPOINT_FRACTIONS),
        },
        "controls": controls,
        "dynamics": dynamics,
        "checks": checks,
        "source_hashes": {
            "computations/navier-stokes-curvature-clock-prereg.md": sha256(PROTOCOL_SCRIPT),
            "computations/navier_stokes_curvature_clock.py": sha256(Path(__file__)),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": sha256(
                DEPLETION_SCRIPT
            ),
        },
    }


def json_safe(value):
    """Coerce numpy scalars and arrays to plain JSON types."""
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--quick", action="store_true")
    arguments = parser.parse_args()
    output = Path(arguments.output) if arguments.output else DEFAULT_OUTPUT
    if not output.is_absolute():
        output = ROOT / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    print("=" * 78)
    print("Curvature clock of the vorticity-direction coherence margin")
    print("=" * 78)
    receipt = json_safe(build_receipt(arguments.quick))
    body = {key: value for key, value in receipt.items() if key != "content_sha256"}
    digest = hashlib.sha256(json.dumps(body, indent=1, sort_keys=True).encode()).hexdigest()
    receipt["content_sha256"] = digest
    payload = json.dumps(receipt, indent=1, sort_keys=True)
    (output / "curvature_clock.json").write_text(payload)
    (output / "curvature_clock_receipt.json").write_text(payload)
    print("=" * 78)
    print(f"status {receipt['status']}  content {digest[:16]}")
    print(f"receipt {output / 'curvature_clock_receipt.json'}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
