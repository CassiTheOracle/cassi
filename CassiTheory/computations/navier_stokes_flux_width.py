#!/usr/bin/env python
"""Material transport of the flux-based tube width on the retained helical families.

Companion to `computations/navier_stokes_curvature_clock.py`,
`computations/navier_stokes_curvature_budget.py` and the note
`turbulence/navier-stokes-tube-curvature-coherence.md`.  Frozen in
`computations/navier-stokes-flux-width-prereg.md`.

The clock and the budget measured the margin kappa a_n with a Hessian proxy for
the tube width, whose own transport carries the normal curvature of |omega|.  The
note replaces the proxy with the flux-based width

    a^2 = Gamma / (pi |omega|),   Gamma = flux of omega through a material patch,

whose transport is closed:  D_tau log a = -ell/2 up to the viscous profile
spread, and D_tau log Gamma = nu int Delta omega . N dA / Gamma exactly.

This producer carries a Lagrangian tracer together with a material patch on the
three retained helical families and measures the material rates of kappa, Gamma,
|omega|, a and the margin kappa a against their closed forms.

Usage:
    python computations/navier_stokes_flux_width.py [--output DIR]

Exit status is 0 only when every check passes.
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
CLOCK_SCRIPT = ROOT / "computations" / "navier_stokes_curvature_clock.py"
BUDGET_SCRIPT = ROOT / "computations" / "navier_stokes_curvature_budget.py"
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
DEPLETION_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
)
PROTOCOL_SCRIPT = ROOT / "computations" / "navier-stokes-flux-width-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs" / "20260922_flux_width"
SCHEMA = "navier-stokes-flux-width-v1"

CUTOFF = 16
GRID_FACTOR = 6
STEPS = 1024
HORIZON = 0.5
NU = 0.1
SAMPLE_STRIDE = 4
CHECKPOINT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
PATCH_SPAN_FACTOR = 6.0
PATCH_SPAN_CONTROL = 9.0
QUADRATURE_ORDER = 3
REFINEMENT_STEPS = 64
REFINEMENT_SPACINGS = (4, 2, 1)
STABILITY_TOLERANCE = 1.0e-6

FRAME_TOLERANCE = 1.0e-2
FLUX_TOLERANCE = 2.0e-2
WIDTH_TOLERANCE = 1.0e-2
SPREAD_FACTOR = 3.0
BOUND_TOLERANCE = 1.0
PATCH_SIZE_TOLERANCE = 1.0e-2
PROBE_TOLERANCE = 1.0e-10
GRADIENT_TOLERANCE = 1.0e-4
CASES = ("helix_wide", "helix_narrow", "helix_tight_pitch")

EPSILON = np.zeros((3, 3, 3))
for _i, _j, _k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
    EPSILON[_i, _j, _k] = 1.0
    EPSILON[_i, _k, _j] = -1.0


def load_module(path: Path):
    import importlib.util

    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def content_digest(body: dict) -> str:
    payload = json.dumps(body, indent=1, sort_keys=True).encode()
    return hashlib.sha256(payload).hexdigest()


def json_safe(value):
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


# --------------------------------------------------------------------------
# Point evaluation of the frame and of the material patch
# --------------------------------------------------------------------------


class FrameProbe:
    """Point evaluation of u and its derivatives up to fourth order.

    The velocity is shell-limited, so every derivative of it is shell-limited and
    may be read at a point exactly (`PointProbe` validates the convention).  The
    multipliers are built on the retained shell only, so a sample costs a
    contraction over `n_shell * 3` coefficients rather than over the full grid.
    """

    def __init__(self, box) -> None:
        import torch

        self.torch = torch
        self.box = box
        indices = torch.nonzero(box.shell, as_tuple=False)
        self.shell = box.shell
        self.count = int(indices.shape[0])
        self.k = box.wave_numbers[box.shell]
        self.weight = torch.where(
            indices[:, 2] == 0,
            torch.ones(self.count, dtype=torch.float64, device=self.k.device),
            torch.full((self.count,), 2.0, dtype=torch.float64, device=self.k.device),
        )
        self.axes = [self.k[:, axis] for axis in range(3)]
        self.multipliers, self.labels = self._multipliers()
        self._flux = None
        self._kinematic = None

    def _multipliers(self):
        """Rows of `(order, k-product, component)` for u, grad, Hessian, third, fourth."""
        torch = self.torch
        rows = []
        labels = []
        for order in range(5):
            for combination in _combinations(order):
                product = torch.ones(
                    self.count, dtype=torch.complex128, device=self.k.device
                )
                for axis in combination:
                    product = product * (1j * self.axes[axis])
                for index in range(3):
                    row = torch.zeros(
                        self.count * 3, dtype=torch.complex128, device=self.k.device
                    )
                    row[index :: 3] = product
                    rows.append(row)
                    labels.append(
                        {"order": order, "axes": list(combination), "component": index}
                    )
        return torch.stack(rows, dim=0), labels

    def row_index(self, order: int, axes, component: int) -> int:
        for row, label in enumerate(self.labels):
            if (
                label["order"] == order
                and tuple(label["axes"]) == tuple(axes)
                and label["component"] == component
            ):
                return row
        raise KeyError((order, tuple(axes), component))

    def flux_rows(self):
        """Rows for omega and Delta omega, in the three component slots."""
        if self._flux is None:
            self._flux = self._build_flux_rows()
        return self._flux

    def _build_flux_rows(self):
        torch = self.torch
        rows = []
        for index in range(3):
            row = torch.zeros(
                self.count * 3, dtype=torch.complex128, device=self.k.device
            )
            for first in range(3):
                for second in range(3):
                    coefficient = float(EPSILON[index, first, second])
                    if coefficient == 0.0:
                        continue
                    row = row + coefficient * self.multipliers[
                        self.row_index(1, (first,), second)
                    ]
            rows.append(row)
        squared = torch.zeros(
            self.count * 3, dtype=torch.complex128, device=self.k.device
        )
        wave_squared = sum(axis * axis for axis in self.axes)
        squared[0::3] = wave_squared
        squared[1::3] = wave_squared
        squared[2::3] = wave_squared
        for index in range(3):
            rows.append(-squared * rows[index])
        return torch.stack(rows, dim=0)

    def evaluate_rows(self, matrix, state, position) -> np.ndarray:
        torch = self.torch
        x = torch.as_tensor(position, dtype=torch.float64, device=self.k.device)
        phase = torch.exp(1j * (self.k @ x))
        weighted = state[self.shell] * self.weight[:, None]
        coefficients = weighted.reshape(-1)
        interleaved = phase.repeat_interleave(3)
        values = matrix @ (coefficients * interleaved)
        return np.asarray(values.real.cpu().numpy(), dtype=float)

    def evaluate(self, state, position) -> np.ndarray:
        return self.evaluate_rows(self.multipliers, state, position)

    def kinematic_rows(self):
        """Rows for u and grad u, so a carried stage costs one contraction."""
        if self._kinematic is None:
            rows = [
                self.multipliers[self.row_index(0, (), component)]
                for component in range(3)
            ]
            for component in range(3):
                for axis in range(3):
                    rows.append(self.multipliers[self.row_index(1, (axis,), component)])
            self._kinematic = self.torch.stack(rows, dim=0)
        return self._kinematic

    def velocity(self, state, position) -> np.ndarray:
        readings = self.evaluate_rows(self.kinematic_rows(), state, position)
        return np.array(readings[0:3], dtype=float)

    def velocity_and_gradient(self, state, position):
        readings = self.evaluate_rows(self.kinematic_rows(), state, position)
        return (
            np.array(readings[0:3], dtype=float),
            np.array(readings[3:12], dtype=float).reshape(3, 3),
        )


def _combinations(order: int):
    if order == 0:
        return [()]
    out = []
    for head in range(3):
        for tail in _combinations(order - 1):
            out.append((head,) + tail)
    return out


def velocity_and_gradient(probe: FrameProbe, state, position):
    """u and grad u at a point, from the first two derivative blocks."""
    return probe.velocity_and_gradient(state, position)


def frame_readings(probe: FrameProbe, state, position, nu) -> dict[str, Any]:
    """Every frame quantity of the margin at one point, closed forms included."""
    values = probe.evaluate(state, position)
    gradient_velocity = np.zeros((3, 3))
    second_velocity = np.zeros((3, 3, 3))
    third_velocity = np.zeros((3, 3, 3, 3))
    fourth_velocity = np.zeros((3, 3, 3, 3, 3))
    for row, label in enumerate(probe.labels):
        order, axes, component = label["order"], label["axes"], label["component"]
        if order == 1:
            gradient_velocity[component, axes[0]] = values[row]
        elif order == 2:
            second_velocity[component, axes[0], axes[1]] = values[row]
        elif order == 3:
            third_velocity[component, axes[0], axes[1], axes[2]] = values[row]
        elif order == 4:
            fourth_velocity[component, axes[0], axes[1], axes[2], axes[3]] = values[row]

    vorticity = np.einsum("ijk,kj->i", EPSILON, gradient_velocity)
    gradient_vorticity = np.einsum("ijk,kja->ia", EPSILON, second_velocity)
    second_vorticity = np.einsum("ijk,kjab->abi", EPSILON, third_velocity)
    third_vorticity = np.einsum("ijk,kjabc->abci", EPSILON, fourth_velocity)
    magnitude = float(np.linalg.norm(vorticity))
    safe = max(magnitude, 1e-300)
    gradient_magnitude = (gradient_vorticity @ vorticity) / safe
    direction = vorticity / safe
    gradient_direction = (
        gradient_vorticity / safe - np.outer(vorticity, gradient_magnitude) / safe**2
    )
    curvature_vector = gradient_direction @ direction
    kappa = float(np.linalg.norm(curvature_vector))
    normal = curvature_vector / max(kappa, 1e-300)
    binormal = np.cross(direction, normal)

    laplacian_vorticity = np.einsum("aai->i", second_vorticity)
    gradient_laplacian_vorticity = np.einsum("abbi->ia", third_vorticity)
    laplacian_velocity = np.einsum("ill->i", second_velocity)
    gradient_laplacian_velocity = np.einsum("illa->ai", third_velocity)
    production = float(vorticity @ laplacian_vorticity)
    laplacian_magnitude = float(
        (
            production
            + float(np.sum(gradient_vorticity**2))
            - float(np.sum(gradient_magnitude**2))
        )
        / safe
    )

    strain = 0.5 * (gradient_velocity + gradient_velocity.T)
    stretch = float(direction @ strain @ direction)
    transverse = float(normal @ strain @ normal)
    binormal_strain = float(binormal @ strain @ binormal)
    bend = float(np.einsum("i,l,ilj,j->", normal, direction, second_velocity, direction))
    bend_rate = bend / kappa if kappa > 0.0 else 0.0

    viscous_vector = (
        nu * (laplacian_vorticity - direction * (production / safe)) / safe
    )
    gradient_production = gradient_vorticity @ laplacian_vorticity + np.einsum(
        "ai,i->a", gradient_laplacian_vorticity, vorticity
    )
    gradient_viscous = (
        nu
        * (
            gradient_laplacian_vorticity
            - gradient_direction * (production / safe)
            - np.outer(direction, gradient_production) / safe
        )
        / safe
        - np.outer(viscous_vector, gradient_magnitude) / safe
    )
    viscous_curvature = float(
        np.einsum("i,a,ia->", normal, viscous_vector, gradient_direction)
        + np.einsum("i,a,ia->", normal, direction, gradient_viscous)
    )

    normal_curvature = float(
        (normal @ (gradient_vorticity @ gradient_vorticity.T) @ normal + np.einsum("a,b,abi,i->", normal, normal, second_vorticity, vorticity)) / safe
        - float(normal @ gradient_magnitude) ** 2 / safe
    )
    width = (
        math.sqrt(abs(magnitude / normal_curvature))
        if normal_curvature != 0.0
        else float("inf")
    )
    hessian_norm = float(np.linalg.norm(second_velocity.reshape(3, 9), ord=2))
    gradient_norm = float(np.linalg.norm(gradient_velocity, ord=2))
    return {
        "magnitude": magnitude,
        "kappa": kappa,
        "direction": direction,
        "normal": normal,
        "binormal": binormal,
        "stretch": stretch,
        "transverse": transverse,
        "binormal_strain": binormal_strain,
        "bend_rate": bend_rate,
        "production": production,
        "laplacian_magnitude": laplacian_magnitude,
        "viscous_curvature": viscous_curvature,
        "curvature_rate_inviscid": bend_rate + transverse - 2.0 * (stretch + transverse + binormal_strain),
        "curvature_rate_closed": bend_rate
        + transverse
        - 2.0 * (stretch + transverse + binormal_strain)
        + viscous_curvature / max(kappa, 1e-300),
        "enstrophy_rate": 2.0 * stretch + 2.0 * nu * production / max(magnitude**2, 1e-300),
        "magnitude_rate_closed": (stretch + transverse + binormal_strain)
        + nu * production / max(magnitude**2, 1e-300),
        "width": float(width),
        "hessian_norm": hessian_norm,
        "gradient_norm": gradient_norm,
        "laplacian_velocity_norm": float(np.linalg.norm(laplacian_velocity)),
        "gradient_laplacian_velocity_norm": float(
            np.linalg.norm(gradient_laplacian_velocity, ord=2)
        ),
    }


def quadrature_nodes(order: int):
    nodes, weights = np.polynomial.legendre.leggauss(order)
    return 0.5 * (nodes + 1.0), 0.5 * weights


def patch_flux(probe: FrameProbe, box, state, position, patch, order: int) -> dict[str, float]:
    """Flux of omega and of Delta omega through a material parallelogram."""
    rows = probe.flux_rows()
    cross = np.cross(patch[0], patch[1])
    area = float(np.linalg.norm(cross))
    normal = cross / max(area, 1e-300)
    direction = _direction_of(probe, state, position)
    nodes, weights = quadrature_nodes(order)
    flux = 0.0
    laplacian_flux = 0.0
    for left, left_weight in zip(nodes, weights):
        for right, right_weight in zip(nodes, weights):
            offset = (left - 0.5) * patch[0] + (right - 0.5) * patch[1]
            readings = probe.evaluate_rows(rows, state, position + offset)
            flux += left_weight * right_weight * float(np.dot(readings[0:3], normal))
            laplacian_flux += (
                left_weight * right_weight * float(np.dot(readings[3:6], normal))
            )
    return {
        "area": area,
        "normal": normal,
        "projection": float(abs(np.dot(normal, direction))),
        "flux": area * flux,
        "laplacian_flux": area * laplacian_flux,
    }


def _direction_of(probe: FrameProbe, state, position) -> np.ndarray:
    readings = probe.evaluate_rows(probe.flux_rows(), state, position)
    vorticity = np.array(readings[0:3], dtype=float)
    return vorticity / max(float(np.linalg.norm(vorticity)), 1e-300)


def sample(probe: FrameProbe, box, state, position, patch, nu, order: int) -> dict[str, Any]:
    frame = frame_readings(probe, state, position, nu)
    flux = patch_flux(probe, box, state, position, patch, order)
    magnitude = frame["magnitude"]
    area = flux["area"]
    patch_magnitude = flux["flux"] / max(area * flux["projection"], 1e-300)
    width = math.sqrt(abs(flux["flux"]) / (math.pi * max(magnitude, 1e-300)))
    spread = 0.5 * nu * (
        flux["laplacian_flux"] / max(abs(flux["flux"]), 1e-300)
        - frame["production"] / max(magnitude**2, 1e-300)
    )
    return {
        "position": [float(value) for value in position],
        "kappa": frame["kappa"],
        "magnitude": magnitude,
        "width": float(width),
        "margin": float(frame["kappa"] * width),
        "flux": float(flux["flux"]),
        "laplacian_flux": float(flux["laplacian_flux"]),
        "patch_area": float(area),
        "patch_projection": float(flux["projection"]),
        "patch_magnitude": float(patch_magnitude),
        "curvature_rate_inviscid": frame["curvature_rate_inviscid"],
        "curvature_rate_closed": frame["curvature_rate_closed"],
        "magnitude_rate_closed": frame["magnitude_rate_closed"],
        "flux_rate_closed": float(
            nu * flux["laplacian_flux"] / max(abs(flux["flux"]), 1e-300)
        ),
        "spread": float(spread),
        "viscous_curvature": frame["viscous_curvature"],
        "hessian_norm": frame["hessian_norm"],
        "gradient_norm": frame["gradient_norm"],
        "laplacian_velocity_norm": frame["laplacian_velocity_norm"],
        "stretch": frame["stretch"],
        "transverse": frame["transverse"],
        "binormal_strain": frame["binormal_strain"],
        "axial": frame["stretch"] + frame["transverse"] + frame["binormal_strain"],
    }


# --------------------------------------------------------------------------
# The carried trajectory
# --------------------------------------------------------------------------


def release(box, probe, state):
    """The core of the field, the frame there, and the core width scale."""
    torch = __import__("torch")

    omega_grid = box.grid(box.curl(state))
    squared = torch.sum(omega_grid * omega_grid, dim=-1)
    size = int(box.grid_size)
    core = np.unravel_index(
        int(torch.argmax(squared).item()), tuple(int(v) for v in squared.shape)
    )
    position = np.array([2.0 * math.pi * float(value) / size for value in core])
    direction = _direction_of(probe, state, position)
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(np.dot(reference, direction))) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    first = np.cross(direction, reference)
    first = first / float(np.linalg.norm(first))
    second = np.cross(direction, first)
    second = second / float(np.linalg.norm(second))
    return position, direction, first, second, frame_readings(probe, state, position, NU)["width"]


def advance(probe, box, state, rhs, dt, position, patch):
    """One coupled RK4 step of the field, the tracer and the material patch.

    The stages follow the retained budget's convention: each carries the field
    stage state and the tracer position advanced by the previous stage.
    """
    second = box.right_hand_side(state + 0.5 * dt * rhs)
    third = box.right_hand_side(state + 0.5 * dt * second)
    fourth = box.right_hand_side(state + dt * third)
    updated = (
        state + (dt / 6.0) * (rhs + 2.0 * second + 2.0 * third + fourth)
    ).masked_fill(~box.shell[..., None], 0.0)

    first_velocity, first_gradient = velocity_and_gradient(probe, state, position)
    second_velocity, second_gradient = velocity_and_gradient(
        probe, state + 0.5 * dt * rhs, position + 0.5 * dt * first_velocity
    )
    third_velocity, third_gradient = velocity_and_gradient(
        probe, state + 0.5 * dt * second, position + 0.5 * dt * second_velocity
    )
    fourth_velocity, fourth_gradient = velocity_and_gradient(
        probe, state + dt * third, position + dt * third_velocity
    )
    new_position = (
        position
        + (dt / 6.0)
        * (first_velocity + 2.0 * second_velocity + 2.0 * third_velocity + fourth_velocity)
    ) % (2.0 * math.pi)
    deformation = first_gradient + 2.0 * second_gradient + 2.0 * third_gradient + fourth_gradient
    new_patch = [vector + (dt / 6.0) * (deformation @ vector) for vector in patch]
    return updated, new_position, new_patch


def integrate_case(clock, budget, long_trajectory, depletion, case, span_factor, order, stride):
    """Carry the tracer and its material patch through one declared family.

    The patch side is the released core's own width scale times `span_factor`, so
    the patch spans the tube rather than sampling one point inside it.
    """
    box = long_trajectory.TorchGalerkinBox(CUTOFF, GRID_FACTOR * CUTOFF + 1)
    probe = FrameProbe(box)
    record_case = next(item for item in depletion.CASES if item["name"] == case)
    state, metadata = depletion.initial_state(record_case, box)
    dt = HORIZON / float(STEPS)
    position, direction, first, second, core_width = release(box, probe, state)
    patch_side = span_factor * core_width
    patch = [patch_side * first, patch_side * second]
    rhs = box.right_hand_side(state)

    samples = []
    checkpoint_steps = {int(round(f * STEPS)) for f in CHECKPOINT_FRACTIONS}

    def record(index: int) -> None:
        row = sample(probe, box, state, position, patch, NU, order)
        row["step"] = int(index)
        row["time"] = float(index * dt)
        row["checkpoint"] = bool(index in checkpoint_steps)
        samples.append(row)

    record(0)
    for index in range(STEPS):
        state, position, patch = advance(probe, box, state, rhs, dt, position, patch)
        rhs = box.right_hand_side(state)
        if (index + 1) % stride == 0 or (index + 1) in checkpoint_steps:
            record(index + 1)

    rates = []
    for earlier, later in zip(samples, samples[1:]):
        span = later["time"] - earlier["time"]
        if span <= 0.0:
            continue
        rates.append(
            {
                "time": earlier["time"],
                "span": span,
                "kappa": math.log(later["kappa"] / earlier["kappa"]) / span,
                "magnitude": math.log(later["magnitude"] / earlier["magnitude"]) / span,
                "flux": math.log(abs(later["flux"]) / abs(earlier["flux"])) / span,
                "width": math.log(later["width"] / earlier["width"]) / span,
                "margin": math.log(later["margin"] / earlier["margin"]) / span,
                "kappa_closed": 0.5 * (earlier["curvature_rate_closed"] + later["curvature_rate_closed"]),
                "kappa_inviscid": 0.5 * (earlier["curvature_rate_inviscid"] + later["curvature_rate_inviscid"]),
                "flux_closed": 0.5 * (earlier["flux_rate_closed"] + later["flux_rate_closed"]),
                "magnitude_closed": 0.5 * (earlier["magnitude_rate_closed"] + later["magnitude_rate_closed"]),
                "width_identity": -0.5 * 0.5 * (
                    _axial(earlier) + _axial(later)
                ),
                "spread": 0.5 * (earlier["spread"] + later["spread"]),
                "bound": 0.5 * (
                    _bound_rate(earlier) + _bound_rate(later)
                ),
                "viscous_curvature": 0.5 * (
                    earlier["viscous_curvature"] + later["viscous_curvature"]
                ),
            }
        )
    return {
        "case": case,
        "family": record_case["family"],
        "span_factor": span_factor,
        "core_width": float(core_width),
        "patch_side": float(patch_side),
        "quadrature_order": order,
        "stride": stride,
        "grid_size": GRID_FACTOR * CUTOFF + 1,
        "nu": NU,
        "horizon": HORIZON,
        "steps": STEPS,
        "initial_position": [float(value) for value in position],
        "initial_state": {
            "normalization_error": float(metadata["normalization_error"]),
            "projection_error": float(metadata["projection_error"]),
            "state_divergence_residual": float(metadata["state_divergence_residual"]),
        },
        "samples": samples,
        "rates": rates,
    }


def _axial(row) -> float:
    return row["axial"]


def integrate_rates(entry: dict[str, Any]) -> dict[str, float]:
    """The integrated material statements over one carried window.

    Each statement compares the change of a carried quantity against the integral
    of its own closed-form rate, which replaces the pointwise finite-difference
    error with the trapezoid error of the integral.
    """
    samples = entry["samples"]

    def trapezoid(key: str) -> float:
        return sum(
            0.5 * (earlier[key] + later[key]) * (later["time"] - earlier["time"])
            for earlier, later in zip(samples, samples[1:])
        )

    def change(key: str) -> float:
        return math.log(abs(samples[-1][key]) / abs(samples[0][key]))

    axial = trapezoid("axial")
    return {
        "horizon": float(samples[-1]["time"] - samples[0]["time"]),
        "curvature": change("kappa") - trapezoid("curvature_rate_closed"),
        "curvature_inviscid": change("kappa") - trapezoid("curvature_rate_inviscid"),
        "flux": change("flux") - trapezoid("flux_rate_closed"),
        "magnitude": change("magnitude") - trapezoid("magnitude_rate_closed"),
        "width": change("width") + 0.5 * axial,
        "spread": trapezoid("spread"),
        "axial": float(axial),
        "kappa_change": change("kappa"),
        "width_change": change("width"),
        "magnitude_change": change("magnitude"),
        "flux_change": change("flux"),
        "margin_change": change("margin"),
    }


def _bound_rate(row) -> float:
    margin = max(row["margin"], 1e-300)
    return (
        row["width"] * row["hessian_norm"] / margin
        + 3.5 * row["gradient_norm"]
        + row["width"] * abs(row["viscous_curvature"]) / margin
    )


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------


def worst_rate(entry, key, closed_key) -> float:
    return max(
        abs(rate[key] - rate[closed_key]) for rate in entry["rates"]
    )


def build_receipt(clock, budget, long_trajectory, depletion) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}: {detail}")

    box = long_trajectory.TorchGalerkinBox(CUTOFF, GRID_FACTOR * CUTOFF + 1)
    probe = FrameProbe(box)
    case = next(item for item in depletion.CASES if item["name"] == CASES[0])
    state, _ = depletion.initial_state(case, box)

    # D0 instrument: the derivative blocks reproduce the spectral grid derivatives.
    size = int(box.grid_size)
    torch = __import__("torch")
    wave = box.wave_numbers
    velocity_grid = box.grid(state)
    gradient_grid = [
        box.grid(1j * wave[..., axis] * state[..., component])
        for component in range(3)
        for axis in range(3)
    ]
    hessian_grid = [
        box.grid(-wave[..., first] * wave[..., second] * state[..., component])
        for component in range(3)
        for first in range(3)
        for second in range(3)
    ]
    worst_gradient = 0.0
    worst_hessian = 0.0
    for _ in range(24):
        index = tuple(int(value) for value in torch.randint(4, size - 4, (3,)))
        point = np.array([2.0 * math.pi * float(value) / size for value in index])
        values = probe.evaluate(state, point)
        for row, label in enumerate(probe.labels):
            if label["order"] == 1:
                expected = float(
                    gradient_grid[
                        3 * label["component"] + label["axes"][0]
                    ][index[0], index[1], index[2]]
                )
                worst_gradient = max(worst_gradient, abs(values[row] - expected))
            elif label["order"] == 2:
                expected = float(
                    hessian_grid[
                        9 * label["component"] + 3 * label["axes"][0] + label["axes"][1]
                    ][index[0], index[1], index[2]]
                )
                worst_hessian = max(worst_hessian, abs(values[row] - expected))
    check(
        "D0 derivative blocks reproduce the spectral grid derivatives",
        max(worst_gradient, worst_hessian) < PROBE_TOLERANCE,
        f"worst first-derivative residual {worst_gradient:.2e} and second-derivative "
        f"residual {worst_hessian:.2e} over 24 grid points "
        f"(requires < {PROBE_TOLERANCE:.0e}); both sides are spectral, so the residual "
        "is round-off alone",
    )

    # D0b cross-validation: the retained frame reader agrees with this one.
    reference_probe = budget.PointProbe(box)
    worst_frame = 0.0
    for _ in range(8):
        index = tuple(int(value) for value in torch.randint(4, size - 4, (3,)))
        point = np.array([2.0 * math.pi * float(value) / size for value in index])
        mine = frame_readings(probe, state, point, NU)
        retained = budget.local_frame(reference_probe, state, point, NU)
        for key in ("kappa", "magnitude", "stretch", "transverse", "binormal_strain", "bend_rate"):
            worst_frame = max(worst_frame, abs(mine[key] - retained[key]))
    check(
        "D0b frame reader agrees with the retained clock reader",
        worst_frame < PROBE_TOLERANCE,
        f"worst residual {worst_frame:.2e} over 8 points and six frame quantities "
        f"(requires < {PROBE_TOLERANCE:.0e}); the retained reader is the reference",
    )

    # D1 probe convention: the point evaluator reproduces the grid values.
    worst_probe = 0.0
    for _ in range(16):
        index = tuple(int(value) for value in torch.randint(0, size, (3,)))
        point = np.array([2.0 * math.pi * float(value) / size for value in index])
        exact = probe.velocity(state, point)
        gridded = np.array(
            [float(velocity_grid[index[0], index[1], index[2], c]) for c in range(3)]
        )
        worst_probe = max(worst_probe, float(np.max(np.abs(exact - gridded))))
    check(
        "D1 point evaluator reproduces the grid velocity",
        worst_probe < PROBE_TOLERANCE,
        f"worst residual {worst_probe:.2e} over 16 grid points "
        f"(requires < {PROBE_TOLERANCE:.0e})",
    )

    # D2 quadrature convergence on the patch flux at the release point.
    position, _, first, second, core_width = release(box, probe, state)
    fluxes = {}
    for order in (2, 3, 4, 5):
        patch = [PATCH_SPAN_FACTOR * core_width * first, PATCH_SPAN_FACTOR * core_width * second]
        fluxes[order] = patch_flux(probe, box, state, position, patch, order)["flux"]
    reference = fluxes[5]
    worst_quadrature = max(
        abs(fluxes[order] - reference) / max(abs(reference), 1e-300)
        for order in (3, 4)
    )
    check(
        "D2 patch quadrature is converged at the declared order",
        worst_quadrature < FLUX_TOLERANCE,
        f"orders 3 and 4 differ from order 5 by {worst_quadrature:.2e} relative "
        f"(requires < {FLUX_TOLERANCE:.0e}); fluxes "
        + ", ".join(f"{order}: {fluxes[order]:+.6e}" for order in (2, 3, 4, 5)),
    )

    # D3 the integrated material statements, which are the exact ones.
    entries = [
        integrate_case(clock, budget, long_trajectory, depletion, name, PATCH_SPAN_FACTOR, QUADRATURE_ORDER, SAMPLE_STRIDE)
        for name in CASES
    ]
    for entry in entries:
        entry["integrated"] = integrate_rates(entry)

    curvature_residual = {
        entry["case"]: abs(entry["integrated"]["curvature"]) for entry in entries
    }
    inviscid_residual = {
        entry["case"]: abs(entry["integrated"]["curvature_inviscid"]) for entry in entries
    }
    check(
        "D3 the material curvature transport closes over the carried window",
        max(curvature_residual.values()) < FRAME_TOLERANCE,
        "worst residual "
        + ", ".join(f"{name}: {value:.2e}" for name, value in curvature_residual.items())
        + f" (requires < {FRAME_TOLERANCE:.0e}); the same residual without the "
        "viscous bracket is "
        + ", ".join(f"{name}: {value:.2e}" for name, value in inviscid_residual.items()),
    )

    flux_residual = {
        entry["case"]: abs(entry["integrated"]["flux"]) for entry in entries
    }
    check(
        "D4 the material flux transport closes (the flux lemma)",
        max(flux_residual.values()) < FLUX_TOLERANCE,
        "worst residual "
        + ", ".join(f"{name}: {value:.2e}" for name, value in flux_residual.items())
        + f" (requires < {FLUX_TOLERANCE:.0e})",
    )

    magnitude_residual = {
        entry["case"]: abs(entry["integrated"]["magnitude"]) for entry in entries
    }
    check(
        "D5 the material enstrophy transport closes",
        max(magnitude_residual.values()) < FLUX_TOLERANCE,
        "worst residual "
        + ", ".join(f"{name}: {value:.2e}" for name, value in magnitude_residual.items())
        + f" (requires < {FLUX_TOLERANCE:.0e})",
    )

    width_residual = {
        entry["case"]: abs(entry["integrated"]["width"]) for entry in entries
    }
    spread_integral = {
        entry["case"]: abs(entry["integrated"]["spread"]) for entry in entries
    }
    spread_removed = {
        entry["case"]: abs(entry["integrated"]["width"] - entry["integrated"]["spread"])
        for entry in entries
    }
    check(
        "D6 the flux width law holds up to the measured viscous profile spread",
        max(spread_removed.values()) < WIDTH_TOLERANCE,
        "worst residual after removing the spread "
        + ", ".join(f"{name}: {value:.2e}" for name, value in spread_removed.items())
        + f" (requires < {WIDTH_TOLERANCE:.0e}); the deviation of log a from the "
        "ideal -ell/2 law is "
        + ", ".join(f"{name}: {value:.2e}" for name, value in width_residual.items())
        + " and the measured spread integral is "
        + ", ".join(f"{name}: {value:.2e}" for name, value in spread_integral.items()),
    )

    bound_ratio = {
        entry["case"]: max(
            abs(rate["margin"]) / max(rate["bound"], 1e-300) for rate in entry["rates"]
        )
        for entry in entries
    }
    check(
        "D7 the weighted critical-norm bound holds on every sample",
        max(bound_ratio.values()) < BOUND_TOLERANCE,
        "worst ratio of the measured margin rate to the bound "
        + ", ".join(f"{name}: {value:.4f}" for name, value in bound_ratio.items())
        + f" (requires < {BOUND_TOLERANCE:.1f}); the bound is an inequality, so the "
        "slack is the reported quantity",
    )

    control = [
        integrate_case(clock, budget, long_trajectory, depletion, CASES[0], PATCH_SPAN_CONTROL, QUADRATURE_ORDER, SAMPLE_STRIDE)
    ]
    for entry in control:
        entry["integrated"] = integrate_rates(entry)
    check(
        "D8 the reading is independent of the declared patch span",
        abs(control[0]["integrated"]["width"] - entries[0]["integrated"]["width"])
        < PATCH_SIZE_TOLERANCE,
        f"width deviation at span {PATCH_SPAN_CONTROL} is "
        f"{control[0]['integrated']['width']:+.4e} against "
        f"{entries[0]['integrated']['width']:+.4e} at span {PATCH_SPAN_FACTOR} "
        f"(requires < {PATCH_SIZE_TOLERANCE:.0e}); the deviation is a property of the "
        "tube, so the two spans must agree",
    )

    refinement = refinement_floor(clock, budget, long_trajectory, depletion)
    check(
        "D9 the spread-removed residual is a floor, not a sampling artifact",
        refinement["worst"] < WIDTH_TOLERANCE
        and refinement["across"] < STABILITY_TOLERANCE,
        "spread-removed residual at sampling spacings "
        + ", ".join(
            f"{every}: {value:.2e}" for every, value in refinement["spacings"].items()
        )
        + f" (requires < {WIDTH_TOLERANCE:.0e} and a spread across spacings below "
        f"{STABILITY_TOLERANCE:.0e}; the measured spread is {refinement['across']:.2e})",
    )

    status = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    shares = {
        entry["case"]: (
            entry["integrated"]["spread"] / entry["integrated"]["width"]
            if entry["integrated"]["width"] != 0.0
            else float("nan")
        )
        for entry in entries
    }
    verdict = (
        "FLUX WIDTH LAW CARRIES THE DECLARED FAMILIES"
        if all(item["passed"] for item in checks)
        else "FLUX WIDTH LAW DOES NOT CARRY THE DECLARED FAMILIES"
    )
    return {
        "schema": SCHEMA,
        "status": status,
        "verdict": verdict,
        "classification": " ".join(
            f"{entry['case']}: core width {entry['core_width']:.4f} and patch side "
            f"{entry['patch_side']:.4f}; log width change "
            f"{entry['integrated']['width_change']:+.4f} against the ideal "
            f"{-0.5 * entry['integrated']['axial']:+.4f}, spread integral "
            f"{entry['integrated']['spread']:+.2e} carrying "
            f"{shares[entry['case']]:.3f} of the deviation, worst bound ratio "
            f"{bound_ratio[entry['case']]:.4f}."
            for entry in entries
        ),
        "scope": {
            "arbitrary_data_regularity": "UNRESOLVED",
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "backend": "torch-rocm",
            "identity": "D_tau log a = -ell/2 with a^2 = Gamma/(pi |omega|) and "
            "D_tau log Gamma = nu int Delta omega . N dA / Gamma; the width law holds "
            "up to the viscous profile spread, the difference between the patch-mean "
            "and core readings of nu Delta omega . omega / |omega|^2",
            "carried_object": "a Lagrangian tracer with a material parallelogram, "
            "whose vectors obey D_tau v = (grad u) v",
            "time_integrability_of_the_flux_width": "MEASURED ON THE DECLARED FAMILIES ONLY",
        },
        "parameters": {
            "horizon": HORIZON,
            "steps": STEPS,
            "sample_stride": SAMPLE_STRIDE,
            "checkpoint_fractions": list(CHECKPOINT_FRACTIONS),
            "patch_span_factor": PATCH_SPAN_FACTOR,
            "patch_span_control": PATCH_SPAN_CONTROL,
            "quadrature_order": QUADRATURE_ORDER,
            "frame_tolerance": FRAME_TOLERANCE,
            "flux_tolerance": FLUX_TOLERANCE,
            "width_tolerance": WIDTH_TOLERANCE,
            "stability_tolerance": STABILITY_TOLERANCE,
            "bound_tolerance": BOUND_TOLERANCE,
            "patch_size_tolerance": PATCH_SIZE_TOLERANCE,
            "probe_tolerance": PROBE_TOLERANCE,
            "gradient_tolerance": GRADIENT_TOLERANCE,
            "cutoff": CUTOFF,
            "grid_factor": GRID_FACTOR,
            "nu": NU,
        },
        "dynamics": entries + control,
        "refinement": refinement,
        "checks": checks,
        "source_hashes": {
            "computations/navier-stokes-flux-width-prereg.md": clock.sha256(PROTOCOL_SCRIPT),
            "computations/navier_stokes_flux_width.py": clock.sha256(Path(__file__).resolve()),
            "computations/navier_stokes_curvature_clock.py": clock.sha256(CLOCK_SCRIPT),
            "computations/navier_stokes_curvature_budget.py": clock.sha256(BUDGET_SCRIPT),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": clock.sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": clock.sha256(
                DEPLETION_SCRIPT
            ),
        },
    }


def refinement_floor(clock, budget, long_trajectory, depletion) -> dict[str, Any]:
    """The width residual on a short window at three sampling spacings."""
    box = long_trajectory.TorchGalerkinBox(CUTOFF, GRID_FACTOR * CUTOFF + 1)
    probe = FrameProbe(box)
    case = next(item for item in depletion.CASES if item["name"] == CASES[0])
    state, _ = depletion.initial_state(case, box)
    dt = HORIZON / float(STEPS)
    position, _, first, second, core_width = release(box, probe, state)
    patch = [PATCH_SPAN_FACTOR * core_width * first, PATCH_SPAN_FACTOR * core_width * second]
    rhs = box.right_hand_side(state)
    for _ in range(224):
        state, position, patch = advance(probe, box, state, rhs, dt, position, patch)
        rhs = box.right_hand_side(state)

    def window(every: int) -> float:
        local_state, local_rhs = state, rhs
        local_position = position.copy()
        local_patch = [vector.copy() for vector in patch]
        rows = [sample(probe, box, local_state, local_position, local_patch, NU, QUADRATURE_ORDER)]
        rows[0]["time"] = 0.0
        for index in range(REFINEMENT_STEPS):
            local_state, local_position, local_patch = advance(
                probe, box, local_state, local_rhs, dt, local_position, local_patch
            )
            local_rhs = box.right_hand_side(local_state)
            if (index + 1) % every == 0:
                row = sample(
                    probe, box, local_state, local_position, local_patch, NU, QUADRATURE_ORDER
                )
                row["time"] = float(index + 1) * dt
                rows.append(row)
        residual = math.log(rows[-1]["width"] / rows[0]["width"]) + 0.5 * sum(
            0.5 * (earlier["axial"] + later["axial"]) * (later["time"] - earlier["time"])
            for earlier, later in zip(rows, rows[1:])
        )
        spread = sum(
            0.5 * (earlier["spread"] + later["spread"]) * (later["time"] - earlier["time"])
            for earlier, later in zip(rows, rows[1:])
        )
        return abs(residual - spread)

    spacings = {every: window(every) for every in REFINEMENT_SPACINGS}
    ordered = [spacings[every] for every in REFINEMENT_SPACINGS]
    return {
        "spacings": {str(every): float(value) for every, value in spacings.items()},
        "worst": float(max(spacings.values())),
        "across": float(max(ordered) - min(ordered)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    arguments = parser.parse_args()
    output = Path(arguments.output) if arguments.output else DEFAULT_OUTPUT
    if not output.is_absolute():
        output = ROOT / output
    if output.exists():
        raise SystemExit(f"refusing to overwrite {output}")
    output.mkdir(parents=True)

    clock = load_module(CLOCK_SCRIPT)
    budget = load_module(BUDGET_SCRIPT)
    long_trajectory = load_module(LONG_TRAJECTORY_SCRIPT)
    depletion = load_module(DEPLETION_SCRIPT)
    receipt = json_safe(build_receipt(clock, budget, long_trajectory, depletion))
    receipt["content_sha256"] = content_digest(receipt)
    payload = json.dumps(receipt, indent=1, sort_keys=True)
    (output / "flux_width.json").write_text(payload)
    (output / "flux_width_receipt.json").write_text(payload)
    for item in receipt["checks"]:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['name']}: {item['detail']}")
    print("=" * 78)
    print(f"status {receipt['status']}  content {receipt['content_sha256'][:16]}")
    print(f"receipt {output / 'flux_width_receipt.json'}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
