#!/usr/bin/env python
"""The enstrophy budget of the widening channel.

Companion to `computations/navier_stokes_curvature_clock.py` and
`computations/navier_stokes_curvature_clock_saturation.py`.  Frozen in
`computations/navier-stokes-curvature-budget-prereg.md`.

The clock measured the margin kappa a_n at the field core, an argmax that slides
through the fluid.  This protocol carries a Lagrangian tracer released at that
core and measures the same margin, its frame budget (KF)/(KC2), the enstrophy
reading (KC3) and the cap (KC4) at both readings.

Usage:
    python computations/navier_stokes_curvature_budget.py [--output DIR]

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
LONG_TRAJECTORY_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_galerkin_long_trajectory.py"
)
DEPLETION_SCRIPT = (
    ROOT / "computations" / "verify_navier_stokes_helical_dynamic_depletion.py"
)
PROTOCOL_SCRIPT = (
    ROOT / "computations" / "navier-stokes-curvature-budget-prereg.md"
)
SATURATION_RECEIPT = (
    ROOT
    / "runs"
    / "20260921_curvature_clock_saturation"
    / "curvature_clock_saturation_receipt.json"
)
DEFAULT_OUTPUT = ROOT / "runs" / "20260922_curvature_budget"
SCHEMA = "navier-stokes-curvature-budget-v1"

HORIZON = 2.0
STEPS = 4096
BUDGET_EVERY = 4
CHECKPOINT_FRACTIONS = (0.0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0)
TAIL_CUTOFF = 8
TAIL_THRESHOLD = 5.0e-2
FRAME_TOLERANCE = 1.0e-10
QUADRATURE_TOLERANCE = 1.0e-4
CAP_TOLERANCE = 1.0e-6
ENSTROPHY_TOLERANCE = 1.0e-4
CLOCK_MARGIN_TOLERANCE = 1.0e-9
ALGEBRA_TOLERANCE = 1.0e-9
PROBE_TOLERANCE = 1.0e-12
PROBE_STRIDE = 8
SPLIT_TOLERANCE = 1.0e-9
MATERIAL_MAGNITUDE_TOLERANCE = 1.0e-3


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


class PointProbe:
    """Exact point evaluation of shell-limited Fourier-Galerkin fields.

    The retained grid convention (`box.grid`) is `irfftn` of the half-spectrum
    times $N^3$, i.e. the mirror sum

        f(x) = Re sum_{k in shell} w(k_z) c_k exp(i k.x),  w = 1 at k_z = 0, 2 above,

    validated against the grid in check H0. Only fields supported inside the
    retained shell may be read this way: the velocity and each of its
    derivatives. Derived fields (magnitudes, directions, products, and their
    gradients) are never transformed on the grid, because they are not
    shell-limited and a truncated transform would corrupt them; they are
    evaluated pointwise from the exact velocity derivatives instead.
    """

    def __init__(self, box) -> None:
        import torch

        self.torch = torch
        self.box = box
        self.size = int(box.grid_size)
        indices = torch.nonzero(box.shell, as_tuple=False)
        self.shell_wave = box.wave_numbers[box.shell]
        self.shell_weight = torch.where(
            indices[:, 2] == 0,
            torch.ones(indices.shape[0], dtype=torch.float64, device=box.k2.device),
            torch.full(
                (indices.shape[0],),
                2.0,
                dtype=torch.float64,
                device=box.k2.device,
            ),
        )

    def scalars(self, spectra, position):
        """Evaluate a stack of shell-limited half-spectra at one point."""
        torch = self.torch
        x = torch.as_tensor(
            position, dtype=torch.float64, device=self.shell_wave.device
        )
        phase = torch.exp(1j * (self.shell_wave @ x))
        return [
            float(
                torch.sum(
                    self.shell_weight * spectrum[self.box.shell] * phase
                ).real.item()
            )
            for spectrum in spectra
        ]

    def velocity(self, state, position):
        return np.array(
            self.scalars([state[..., index] for index in range(3)], position),
            dtype=float,
        )


EPSILON = np.zeros((3, 3, 3))
for _i, _j, _k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
    EPSILON[_i, _j, _k] = 1.0
    EPSILON[_i, _k, _j] = -1.0


def local_frame(probe, state, position, nu):
    """The frame quantities of (KF), (KC2), (KC3) and (KC4) at one point."""
    wave = probe.box.wave_numbers
    kx, ky, kz = wave[..., 0], wave[..., 1], wave[..., 2]
    vorticity_coefficients = probe.box.curl(state)

    spectra = []
    for index in range(3):                     # g[i][j] = d_j u_i
        for k in (kx, ky, kz):
            spectra.append(1j * k * state[..., index])
    for index in range(3):                     # h[i][l][j] = d_l d_j u_i
        for first in (kx, ky, kz):
            for second in (kx, ky, kz):
                spectra.append(-first * second * state[..., index])
    for first in (kx, ky, kz):                 # d_a d_b omega_i = -k_a k_b omega_i
        for second in (kx, ky, kz):
            for index in range(3):
                spectra.append(-first * second * vorticity_coefficients[..., index])
    values = probe.scalars(spectra, position)

    cursor = 0

    def take(count):
        nonlocal cursor
        block = values[cursor : cursor + count]
        cursor += count
        return block

    gradient_velocity = np.array(take(9)).reshape(3, 3)
    second_velocity = np.array(take(27)).reshape(3, 3, 3)
    second_vorticity = np.array(take(27)).reshape(3, 3, 3)  # [a][b][i] = d_a d_b w_i

    vorticity = np.einsum("ijk,kj->i", EPSILON, gradient_velocity)
    gradient_vorticity = np.einsum("ijk,kja->ia", EPSILON, second_velocity)
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

    gradient_square = gradient_vorticity @ gradient_vorticity.T
    second_contracted = np.einsum("a,b,abi,i->", normal, normal, second_vorticity, vorticity)
    normal_curvature = float(
        (normal @ gradient_square @ normal + second_contracted) / safe
        - float(normal @ gradient_magnitude) ** 2 / safe
    )
    laplacian_vorticity = np.einsum("aai->i", second_vorticity)
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
    width = (
        math.sqrt(abs(magnitude / normal_curvature))
        if normal_curvature != 0.0
        else float("inf")
    )
    bend = float(
        np.einsum("i,l,ilj,j->", normal, direction, second_velocity, direction)
    )
    bend_rate = bend / kappa if kappa > 0.0 else 0.0
    enstrophy_rate = 2.0 * stretch + 2.0 * nu * production / max(magnitude**2, 1e-300)
    assembled = bend_rate - 4.0 * stretch - 2.0 * binormal_strain
    kc3 = (
        bend_rate
        - 2.0 * enstrophy_rate
        + 4.0 * nu * production / max(magnitude**2, 1e-300)
        - 2.0 * binormal_strain
    )
    cap = (
        bend_rate
        - 2.0 * enstrophy_rate
        + 4.0 * nu * laplacian_magnitude / safe
        - 2.0 * binormal_strain
    )
    return {
        "position": [float(value) for value in position],
        "magnitude": float(magnitude),
        "kappa": kappa,
        "width": float(width),
        "margin": float(kappa * width),
        "direction": direction.tolist(),
        "normal": normal.tolist(),
        "binormal": binormal.tolist(),
        "stretch": stretch,
        "transverse": transverse,
        "binormal_strain": binormal_strain,
        "frame_trace": float(stretch + transverse + binormal_strain),
        "bend_rate": float(bend_rate),
        "enstrophy_rate": float(enstrophy_rate),
        "laplacian_magnitude": float(laplacian_magnitude),
        "production": float(production),
        "assembled_rate": float(assembled),
        "kc3_rate": float(kc3),
        "cap_rate": float(cap),
        "kc1_rate": float(bend_rate + 2.0 * transverse - 2.0 * stretch),
    }


REFINEMENT_STEPS = 64
REFINEMENT_SPACINGS = (4, 2, 1)
REFINEMENT_FACTOR = 1.8


def refinement_check(clock, long_trajectory, depletion, case, nu):
    """H2b: the interval residual is a finite-difference floor, not a defect.

    The residual of check H2 falls with the lattice spacing; this measures the
    fall on a 64-step window of the same trajectory.
    """
    torch = __import__("torch")
    box = long_trajectory.TorchGalerkinBox(
        clock.CUTOFF, clock.GRID_FACTOR * clock.CUTOFF + 1
    )
    probe = PointProbe(box)
    state, _ = depletion.initial_state(case, box)
    size = int(box.grid_size)
    dt = HORIZON / float(STEPS)
    omega_grid = box.grid(box.curl(state))
    squared = torch.sum(omega_grid * omega_grid, dim=-1)
    core = np.unravel_index(
        int(torch.argmax(squared).item()), tuple(int(v) for v in squared.shape)
    )
    tracer = np.array([2.0 * math.pi * float(value) / size for value in core])
    rhs = box.right_hand_side(state)
    for _ in range(224):
        second = box.right_hand_side(state + 0.5 * dt * rhs)
        third = box.right_hand_side(state + 0.5 * dt * second)
        fourth = box.right_hand_side(state + dt * third)
        updated = (
            state + (dt / 6.0) * (rhs + 2.0 * second + 2.0 * third + fourth)
        ).masked_fill(~box.shell[..., None], 0.0)
        stage_1 = probe.velocity(state, tracer)
        stage_2 = probe.velocity(state + 0.5 * dt * rhs, tracer + 0.5 * dt * stage_1)
        stage_3 = probe.velocity(state + 0.5 * dt * second, tracer + 0.5 * dt * stage_2)
        stage_4 = probe.velocity(state + dt * third, tracer + dt * stage_3)
        tracer = (
            tracer + (dt / 6.0) * (stage_1 + 2.0 * stage_2 + 2.0 * stage_3 + stage_4)
        ) % (2.0 * math.pi)
        state = updated
        rhs = box.right_hand_side(state)

    def window(every):
        sampled = [(state, tracer.copy())]
        local_state, local_rhs, local_tracer = state, rhs, tracer.copy()
        for index in range(REFINEMENT_STEPS):
            second = box.right_hand_side(local_state + 0.5 * dt * local_rhs)
            third = box.right_hand_side(local_state + 0.5 * dt * second)
            fourth = box.right_hand_side(local_state + dt * third)
            updated = (
                local_state
                + (dt / 6.0) * (local_rhs + 2.0 * second + 2.0 * third + fourth)
            ).masked_fill(~box.shell[..., None], 0.0)
            stage_1 = probe.velocity(local_state, local_tracer)
            stage_2 = probe.velocity(
                local_state + 0.5 * dt * local_rhs, local_tracer + 0.5 * dt * stage_1
            )
            stage_3 = probe.velocity(
                local_state + 0.5 * dt * second, local_tracer + 0.5 * dt * stage_2
            )
            stage_4 = probe.velocity(
                local_state + dt * third, local_tracer + dt * stage_3
            )
            local_tracer = (
                local_tracer
                + (dt / 6.0)
                * (stage_1 + 2.0 * stage_2 + 2.0 * stage_3 + stage_4)
            ) % (2.0 * math.pi)
            local_state = updated
            local_rhs = box.right_hand_side(local_state)
            if (index + 1) % every == 0:
                sampled.append((local_state, local_tracer.copy()))
        worst = 0.0
        for (state_a, position_a), (state_b, position_b) in zip(sampled, sampled[1:]):
            span = every * dt
            advective = math.log(
                local_margin(probe, state_b, position_b, nu)
                / local_margin(probe, state_b, position_a, nu)
            )
            assembled = 0.5 * span * (
                local_frame(probe, state_a, position_a, nu)["assembled_rate"]
                + local_frame(probe, state_b, position_b, nu)["assembled_rate"]
            )
            worst = max(worst, abs(advective - assembled))
        return worst

    return {every: window(every) for every in REFINEMENT_SPACINGS}


def local_margin(probe, state, position, nu) -> float:
    return float(local_frame(probe, state, position, nu)["margin"])


def instrument_check(torch, box, probe, state) -> float:
    """H0: the point evaluator reproduces the grid values at grid points."""
    grid = box.grid(state)
    size = int(box.grid_size)
    worst = 0.0
    for i in range(0, size, PROBE_STRIDE):
        for j in range(0, size, PROBE_STRIDE):
            for k in range(0, size, 2 * PROBE_STRIDE):
                position = np.array(
                    [
                        2.0 * math.pi * float(i) / size,
                        2.0 * math.pi * float(j) / size,
                        2.0 * math.pi * float(k) / size,
                    ]
                )
                difference = np.abs(
                    probe.velocity(state, position)
                    - grid[i, j, k].detach().cpu().numpy()
                )
                worst = max(worst, float(np.max(difference)))
    return worst


def tail_fraction(torch, box, state) -> float:
    radial = torch.sqrt(torch.sum(box.wave_numbers * box.wave_numbers, dim=-1))
    density = torch.sum(torch.abs(state) ** 2, dim=-1) * (radial * radial)
    total = float(torch.sum(density).item())
    if total <= 0.0:
        return 0.0
    return float(torch.sum(density * (radial > TAIL_CUTOFF)).item()) / total


def integrate_case(clock, long_trajectory, depletion, case, nu):
    """Returns the receipt entry and the box the trajectory was integrated in."""
    torch = __import__("torch")
    box = long_trajectory.TorchGalerkinBox(clock.CUTOFF, clock.GRID_FACTOR * clock.CUTOFF + 1)
    state, metadata = depletion.initial_state(case, box)
    probe = PointProbe(box)
    size = int(box.grid_size)
    dt = HORIZON / float(STEPS)
    spacing = 2.0 * math.pi / size

    omega_grid = box.grid(box.curl(state))
    flat = int(torch.argmax(torch.sum(omega_grid * omega_grid, dim=-1)).item())
    core_cell = np.unravel_index(flat, tuple(int(value) for value in omega_grid.shape[:3]))
    tracer = np.array([2.0 * math.pi * float(index) / size for index in core_cell])

    probe_worst = instrument_check(torch, box, probe, state)
    checkpoint_steps = {int(round(fraction * STEPS)) for fraction in CHECKPOINT_FRACTIONS}
    lattice_steps = set(range(0, STEPS + 1, BUDGET_EVERY)) | checkpoint_steps
    lattice: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    first_rhs = box.right_hand_side(state)

    def sample(index: int, carried: np.ndarray) -> None:
        omega_grid = box.grid(box.curl(state))
        squared = torch.sum(omega_grid * omega_grid, dim=-1)
        current_core = np.unravel_index(
            int(torch.argmax(squared).item()), tuple(int(v) for v in squared.shape)
        )
        entry = {
            "step": int(index),
            "time": float(index * dt),
            "tracer": local_frame(probe, state, tracer, nu),
            "tracer_carried": local_frame(probe, state, carried, nu),
            "core": local_frame(
                probe,
                state,
                np.array(
                    [2.0 * math.pi * float(value) / size for value in current_core]
                ),
                nu,
            ),
            "tracer_cell": [int(value) for value in (np.rint(tracer / spacing) % size).astype(int)],
            "core_cell": [int(value) for value in current_core],
            "tail": tail_fraction(torch, box, state),
        }
        lattice.append(entry)
        if index in checkpoint_steps:
            checkpoints.append(json.loads(json.dumps(entry)))

    sample(0, tracer)
    for index in range(STEPS):
        second_rhs = box.right_hand_side(state + 0.5 * dt * first_rhs)
        third_rhs = box.right_hand_side(state + 0.5 * dt * second_rhs)
        fourth_rhs = box.right_hand_side(state + dt * third_rhs)
        updated = state + (dt / 6.0) * (first_rhs + 2.0 * second_rhs + 2.0 * third_rhs + fourth_rhs)
        carried = tracer.copy()
        stage_1 = probe.velocity(state, tracer)
        stage_2 = probe.velocity(state + 0.5 * dt * first_rhs, tracer + 0.5 * dt * stage_1)
        stage_3 = probe.velocity(state + 0.5 * dt * second_rhs, tracer + 0.5 * dt * stage_2)
        stage_4 = probe.velocity(state + dt * third_rhs, tracer + dt * stage_3)
        tracer = (tracer + (dt / 6.0) * (stage_1 + 2.0 * stage_2 + 2.0 * stage_3 + stage_4)) % (2.0 * math.pi)
        state = updated.masked_fill(~box.shell[..., None], 0.0)
        first_rhs = box.right_hand_side(state)
        if index + 1 in lattice_steps:
            sample(index + 1, carried)

    intervals = []
    worst_quadrature = 0.0
    worst_enstrophy = 0.0
    worst_cap = 0.0
    worst_split = 0.0
    worst_material_magnitude = 0.0
    worst_material_margin = 0.0
    for earlier, later in zip(lattice, lattice[1:]):
        span = later["time"] - earlier["time"]
        measured = math.log(later["tracer"]["margin"] / earlier["tracer"]["margin"])
        unsteady = math.log(
            later["tracer_carried"]["margin"] / earlier["tracer"]["margin"]
        )
        advective = math.log(
            later["tracer"]["margin"] / later["tracer_carried"]["margin"]
        )
        assembled = 0.5 * span * (later["tracer"]["assembled_rate"] + earlier["tracer"]["assembled_rate"])
        cap = 0.5 * span * (later["tracer"]["cap_rate"] + earlier["tracer"]["cap_rate"])
        enstrophy = math.log(
            later["tracer"]["magnitude"] / earlier["tracer"]["magnitude"]
        )
        # `enstrophy_rate` is D_tau log e; the identity under test is its half,
        # D_tau log|omega| = ell + nu omega.Delta omega / |omega|^2.
        enstrophy_budget = 0.25 * span * (
            later["tracer"]["enstrophy_rate"] + earlier["tracer"]["enstrophy_rate"]
        )
        residual = advective - assembled
        enstrophy_residual = enstrophy - enstrophy_budget
        worst_quadrature = max(worst_quadrature, abs(residual))
        worst_enstrophy = max(worst_enstrophy, abs(enstrophy_residual))
        worst_cap = max(worst_cap, advective - cap)
        worst_split = max(worst_split, abs(measured - (unsteady + advective)))
        # Material channels: the carried trajectory's own changes against the
        # integrals of the rate terms the identity assigns to them.  The
        # enstrophy identity is a material statement; the geometric channels are
        # where the field's own evolution enters.
        later_carried = later["tracer_carried"]
        earlier_carried = earlier["tracer_carried"]
        material_magnitude = math.log(
            later_carried["magnitude"] / earlier_carried["magnitude"]
        )
        material_magnitude_budget = 0.5 * span * (
            later_carried["stretch"]
            + nu * later_carried["production"] / later_carried["magnitude"] ** 2
            + earlier_carried["stretch"]
            + nu * earlier_carried["production"] / earlier_carried["magnitude"] ** 2
        )
        material_magnitude_residual = material_magnitude - material_magnitude_budget
        worst_material_magnitude = max(
            worst_material_magnitude, abs(material_magnitude_residual)
        )
        material_margin = math.log(
            later_carried["margin"] / earlier_carried["margin"]
        )
        material_assembled = 0.5 * span * (
            later_carried["assembled_rate"] + earlier_carried["assembled_rate"]
        )
        material_kappa = math.log(later_carried["kappa"] / earlier_carried["kappa"])
        material_kappa_budget = 0.5 * span * (
            later_carried["bend_rate"] + earlier_carried["bend_rate"]
        )
        material_width = math.log(later_carried["width"] / earlier_carried["width"])
        material_width_budget = 0.5 * span * (
            later_carried["transverse"] - later_carried["stretch"]
            + earlier_carried["transverse"] - earlier_carried["stretch"]
        )
        worst_material_margin = max(
            worst_material_margin, abs(material_margin - material_assembled)
        )
        intervals.append(
            {
                "from": earlier["time"],
                "to": later["time"],
                "measured_increment": measured,
                "unsteady_increment": unsteady,
                "advective_increment": advective,
                "assembled_increment": assembled,
                "cap_increment": cap,
                "slack": cap - advective,
                "residual": residual,
                "enstrophy_increment": enstrophy,
                "enstrophy_budget": enstrophy_budget,
                "enstrophy_residual": enstrophy_residual,
                "material_magnitude_increment": material_magnitude,
                "material_magnitude_budget": material_magnitude_budget,
                "material_magnitude_residual": material_magnitude_residual,
                "material_margin_increment": material_margin,
                "material_assembled_increment": material_assembled,
                "material_kappa_increment": material_kappa,
                "material_kappa_budget": material_kappa_budget,
                "material_width_increment": material_width,
                "material_width_budget": material_width_budget,
            }
        )
    frame_worst = max(
        max(abs(entry["tracer"]["frame_trace"]), abs(entry["core"]["frame_trace"]))
        for entry in lattice
    )
    algebra_worst = max(
        max(
            abs(entry[side]["kc3_rate"] - entry[side]["assembled_rate"])
            / max(abs(entry[side]["assembled_rate"]), 1.0)
            for side in ("tracer", "core")
        )
        for entry in lattice
    )
    shares = {
        "bend": float(np.mean([entry["tracer"]["bend_rate"] for entry in lattice])),
        "enstrophy": float(np.mean([-2.0 * entry["tracer"]["enstrophy_rate"] for entry in lattice])),
        "binormal": float(np.mean([-2.0 * entry["tracer"]["binormal_strain"] for entry in lattice])),
    }
    core_comparison = []
    for earlier, later in zip(checkpoints, checkpoints[1:]):
        span = later["time"] - earlier["time"]
        measured_core = math.log(
            later["core"]["margin"] / earlier["core"]["margin"]
        )
        assembled_core = 0.5 * span * (
            later["core"]["assembled_rate"] + earlier["core"]["assembled_rate"]
        )
        core_comparison.append(
            {
                "from": earlier["time"],
                "to": later["time"],
                "measured_increment": measured_core,
                "assembled_trapezoid": assembled_core,
                "ratio": measured_core / assembled_core if assembled_core != 0.0 else 0.0,
            }
        )

    result = {
        "case": case["name"],
        "family": case["family"],
        "cutoff": clock.CUTOFF,
        "grid_size": size,
        "steps": STEPS,
        "nu": nu,
        "horizon": HORIZON,
        "budget_every": BUDGET_EVERY,
        "initial_state": {
            "normalization_error": float(metadata["normalization_error"]),
            "projection_error": float(metadata["projection_error"]),
            "tracer_start": [float(value) for value in tracer],
            "tracer_cell": [int(value) for value in core_cell],
        },
        "checks": {
            "worst_probe_deviation": float(probe_worst),
            "worst_frame_trace": float(frame_worst),
            "worst_quadrature_residual": float(worst_quadrature),
            "worst_enstrophy_residual": float(worst_enstrophy),
            "worst_cap_deficit": float(worst_cap),
            "worst_algebraic_residual": float(algebra_worst),
            "worst_split_residual": float(worst_split),
            "worst_material_magnitude_residual": float(worst_material_magnitude),
            "worst_material_margin_residual": float(worst_material_margin),
            "advective_share": float(
                np.sum([item["advective_increment"] for item in intervals])
                / max(abs(np.sum([item["measured_increment"] for item in intervals])), 1e-300)
            ),
            "total_measured_increment": float(
                np.sum([item["measured_increment"] for item in intervals])
            ),
            "total_advective_increment": float(
                np.sum([item["advective_increment"] for item in intervals])
            ),
            "total_unsteady_increment": float(
                np.sum([item["unsteady_increment"] for item in intervals])
            ),
        },
        "material_gaps": {
            "magnitude_increment": float(
                np.sum([item["material_magnitude_increment"] for item in intervals])
            ),
            "magnitude_budget": float(
                np.sum([item["material_magnitude_budget"] for item in intervals])
            ),
            "margin_increment": float(
                np.sum([item["material_margin_increment"] for item in intervals])
            ),
            "margin_frozen_field_integral": float(
                np.sum([item["material_assembled_increment"] for item in intervals])
            ),
            "kappa_increment": float(
                np.sum([item["material_kappa_increment"] for item in intervals])
            ),
            "kappa_frozen_field_integral": float(
                np.sum([item["material_kappa_budget"] for item in intervals])
            ),
            "width_increment": float(
                np.sum([item["material_width_increment"] for item in intervals])
            ),
            "width_frozen_field_integral": float(
                np.sum([item["material_width_budget"] for item in intervals])
            ),
        },
        "mean_rate_shares": shares,
        "lattice": lattice,
        "intervals": intervals,
        "checkpoints": checkpoints,
        "maximum_tracer_margin": max(entry["tracer"]["margin"] for entry in lattice),
        "maximum_core_margin": max(entry["core"]["margin"] for entry in lattice),
        "final_tracer_magnitude_ratio": float(
            lattice[-1]["tracer"]["magnitude"] / lattice[0]["tracer"]["magnitude"]
        ),
        "maximum_tail": max(float(entry["tail"]) for entry in lattice),
        "core_comparison": core_comparison,
        "mean_core_comparison_ratio": float(
            np.mean([item["ratio"] for item in core_comparison])
        ),
    }
    return result, box


def build_receipt() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def check(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    clock = load_module(CLOCK_SCRIPT)
    long_trajectory = load_module(LONG_TRAJECTORY_SCRIPT)
    depletion = load_module(DEPLETION_SCRIPT)
    saturation = json.loads(SATURATION_RECEIPT.read_text(encoding="utf-8"))

    print("The enstrophy budget of the widening channel")
    print("=" * 78)
    dynamics = []
    for case in [item for item in depletion.CASES if item["name"] in clock.HELIX_CURVATURE]:
        entry, _ = integrate_case(clock, long_trajectory, depletion, case, clock.NU)
        dynamics.append(entry)
        name = entry["case"]
        shares = entry["mean_rate_shares"]
        print(
            f"  {name}: max tracer margin {entry['maximum_tracer_margin']:.6f}  "
            f"max core margin {entry['maximum_core_margin']:.6f}  "
            f"|omega| ratio {entry['final_tracer_magnitude_ratio']:.4f}"
        )
        print(
            f"  {name}: mean rate shares bend {shares['bend']:+.5f}  "
            f"enstrophy {shares['enstrophy']:+.5f}  binormal {shares['binormal']:+.5f}"
        )
        print(
            f"  {name}: material |omega| {entry['checks']['worst_material_magnitude_residual']:.2e}  "
            f"frame {entry['checks']['worst_frame_trace']:.2e}  "
            f"quadrature {entry['checks']['worst_quadrature_residual']:.2e}  "
            f"enstrophy {entry['checks']['worst_enstrophy_residual']:.2e}  "
            f"algebra {entry['checks']['worst_algebraic_residual']:.2e}  "
            f"cap deficit {entry['checks']['worst_cap_deficit']:.2e}"
        )
        check(
            f"H0 {name}: the point evaluator reproduces the grid at grid points",
            entry["checks"]["worst_probe_deviation"] <= PROBE_TOLERANCE,
            f"worst deviation {entry['checks']['worst_probe_deviation']:.2e} "
            f"over a stride-{PROBE_STRIDE} subsample of the grid",
        )
        check(
            f"H1 {name}: the frame trace vanishes at every evaluated point",
            entry["checks"]["worst_frame_trace"] <= FRAME_TOLERANCE,
            f"worst |ell + n.Sn + b.Sb| = {entry['checks']['worst_frame_trace']:.2e}",
        )
        check(
            f"H2 {name}: the frozen-field rate integrates to the advective increment",
            entry["checks"]["worst_quadrature_residual"] <= QUADRATURE_TOLERANCE,
            f"worst residual {entry['checks']['worst_quadrature_residual']:.2e} "
            f"over {len(entry['intervals'])} lattice intervals",
        )
        check(
            f"H3 {name}: the cap stays above the advective increment",
            entry["checks"]["worst_cap_deficit"] <= CAP_TOLERANCE,
            f"worst deficit {entry['checks']['worst_cap_deficit']:.2e}",
        )
        check(
            f"H4 {name}: (KC3) and (KC2) agree at every evaluated point",
            entry["checks"]["worst_algebraic_residual"] <= ALGEBRA_TOLERANCE,
            f"worst relative residual {entry['checks']['worst_algebraic_residual']:.2e}",
        )
        check(
            f"H4b {name}: the enstrophy identity integrates along the tracer",
            entry["checks"]["worst_enstrophy_residual"] <= ENSTROPHY_TOLERANCE,
            f"worst residual {entry['checks']['worst_enstrophy_residual']:.2e}",
        )
        check(
            f"H8 {name}: the material increment splits into unsteady and advective parts",
            entry["checks"]["worst_split_residual"] <= SPLIT_TOLERANCE,
            f"worst telescoping residual {entry['checks']['worst_split_residual']:.2e}",
        )
        check(
            f"H9 {name}: the advective share of the material increment is reported",
            True,
            f"material {entry['checks']['total_measured_increment']:+.5f}, "
            f"advective {entry['checks']['total_advective_increment']:+.6f} "
            f"(share {entry['checks']['advective_share']:+.3f}), "
            f"unsteady {entry['checks']['total_unsteady_increment']:+.5f}",
        )
        check(
            f"H10 {name}: the enstrophy identity is material along the carried trajectory",
            entry["checks"]["worst_material_magnitude_residual"]
            <= MATERIAL_MAGNITUDE_TOLERANCE,
            f"worst residual of dlog|omega| against the integrated material rate "
            f"{entry['checks']['worst_material_magnitude_residual']:.2e}",
        )
        gaps = entry["material_gaps"]
        check(
            f"H11 {name}: the material channel gaps are reported",
            True,
            f"material margin {gaps['margin_increment']:+.5f} against the frozen-field "
            f"integral {gaps['margin_frozen_field_integral']:+.5f}; "
            f"kappa {gaps['kappa_increment']:+.5f} against {gaps['kappa_frozen_field_integral']:+.5f}; "
            f"width {gaps['width_increment']:+.5f} against {gaps['width_frozen_field_integral']:+.5f}",
        )
        check(
            f"H5 {name}: the two readings are reported",
            True,
            f"tracer margin peaks at {entry['maximum_tracer_margin']:.4f}, "
            f"field-core margin peaks at {entry['maximum_core_margin']:.4f}, "
            f"final |omega| ratio {entry['final_tracer_magnitude_ratio']:.4f}, "
            f"mean field-core assembled ratio {entry['mean_core_comparison_ratio']:.3f}",
        )
        check(
            f"H6 {name}: the resolution diagnostic is reported",
            True,
            f"largest enstrophy tail {entry['maximum_tail']:.2e} above |k| = {TAIL_CUTOFF}",
        )
        reference = next(
            (item for item in saturation["dynamics"] if item["case"] == name), None
        )
        if reference is not None:
            cell_worst = 0
            magnitude_worst = 0.0
            margin_worst = 0.0
            deviation = []
            for index, checkpoint in enumerate(entry["checkpoints"]):
                raw = reference["checkpoints"][index]["raw"]
                derived = reference["checkpoints"][index]["derived"]
                cell_worst = max(
                    cell_worst,
                    int(
                        any(
                            int(checkpoint["core_cell"][axis]) != int(raw["core"][axis])
                            for axis in range(3)
                        )
                    ),
                )
                magnitude_worst = max(
                    magnitude_worst,
                    abs(checkpoint["core"]["magnitude"] - float(raw["magnitude"]))
                    / max(abs(float(raw["magnitude"])), 1e-12),
                )
                margin_worst = max(
                    margin_worst,
                    abs(checkpoint["core"]["margin"] - float(derived["margin"]))
                    / max(abs(float(derived["margin"])), 1e-12),
                )
                deviation.append(
                    {
                        "time": checkpoint["time"],
                        "cell_matches": cell_worst == 0,
                        "magnitude_relative": abs(
                            checkpoint["core"]["magnitude"] - float(raw["magnitude"])
                        )
                        / max(abs(float(raw["magnitude"])), 1e-12),
                        "margin_relative": abs(
                            checkpoint["core"]["margin"] - float(derived["margin"])
                        )
                        / max(abs(float(derived["margin"])), 1e-12),
                    }
                )
            entry["receipt_deviation"] = deviation
            check(
                f"H7 {name}: the field core and |omega| reproduce the saturation receipt",
                cell_worst == 0 and magnitude_worst <= CLOCK_MARGIN_TOLERANCE,
                f"core cell mismatches {cell_worst}, worst relative |omega| deviation "
                f"{magnitude_worst:.2e}; margin deviation {margin_worst:.3f} relative "
                f"(grid-interpolant width against the pointwise width)",
            )

    refinement_case = next(
        item for item in depletion.CASES if item["name"] == next(iter(clock.HELIX_CURVATURE))
    )
    refinement = refinement_check(
        clock, long_trajectory, depletion, refinement_case, clock.NU
    )
    ordered = [refinement[every] for every in REFINEMENT_SPACINGS]
    monotone = all(
        later <= earlier / REFINEMENT_FACTOR
        for earlier, later in zip(ordered, ordered[1:])
    )
    check(
        "H2b: the interval residual is a finite-difference floor",
        ordered[0] < QUADRATURE_TOLERANCE and monotone,
        "worst residual at spacings "
        + ", ".join(
            f"{every}: {value:.2e}"
            for every, value in zip(REFINEMENT_SPACINGS, ordered)
        )
        + f" (requires < {QUADRATURE_TOLERANCE:.0e} at {REFINEMENT_SPACINGS[0]} and a "
        f"{REFINEMENT_FACTOR}x fall per halving)",
    )

    status = "PASS" if all(item["passed"] for item in checks) else "FAIL"
    turns = [
        entry["case"] for entry in dynamics if entry["maximum_tracer_margin"] > 0.9
    ]
    body = {
        "schema": SCHEMA,
        "status": status,
        "verdict": (
            "TRACER MARGIN APPROACHES THE POLE IN " + ", ".join(turns)
            if turns
            else "TRACER AND FIELD-CORE MARGINS BOTH STAY BELOW THE POLE"
        ),
        "classification": " ".join(
            f"{entry['case']}: tracer margin peaks at "
            f"{entry['maximum_tracer_margin']:.4f}, field-core margin peaks at "
            f"{entry['maximum_core_margin']:.4f}, carried |omega| ratio "
            f"{entry['final_tracer_magnitude_ratio']:.4f}, mean shares bend "
            f"{entry['mean_rate_shares']['bend']:+.4f} enstrophy "
            f"{entry['mean_rate_shares']['enstrophy']:+.4f} binormal "
            f"{entry['mean_rate_shares']['binormal']:+.4f}."
            for entry in dynamics
        ),
        "scope": {
            "arbitrary_data_regularity": "UNRESOLVED",
            "equation": "original unforced 3-D incompressible Navier-Stokes",
            "backend": "torch-rocm",
            "identity": "(KC2) rate = bend/kappa - 4 ell - 2 b.Sb, with the frame closure ell + n.Sn + b.Sb = 0",
            "material_channels": "the carried trajectory's own changes: dlog|omega| against the integrated material rate (enstrophy identity), and the geometric channels kappa, width and margin against their frozen-field integrals, whose difference is the field's own evolution",
            "cap": "(KC4) rate <= bend/kappa - 2 D log e + 4 nu Delta|omega|/|omega| - 2 b.Sb",
            "cap_is_a_theorem": True,
            "time_integrability_of_the_modulus": "MEASURED ON THE DECLARED FAMILIES ONLY",
        },
        "parameters": {
            "horizon": HORIZON,
            "steps": STEPS,
            "budget_every": BUDGET_EVERY,
            "checkpoint_fractions": list(CHECKPOINT_FRACTIONS),
            "tail_cutoff": TAIL_CUTOFF,
            "tail_threshold": TAIL_THRESHOLD,
            "frame_tolerance": FRAME_TOLERANCE,
            "quadrature_tolerance": QUADRATURE_TOLERANCE,
            "cap_tolerance": CAP_TOLERANCE,
            "enstrophy_tolerance": ENSTROPHY_TOLERANCE,
            "algebra_tolerance": ALGEBRA_TOLERANCE,
            "probe_tolerance": PROBE_TOLERANCE,
            "probe_stride": PROBE_STRIDE,
            "split_tolerance": SPLIT_TOLERANCE,
            "cutoff": clock.CUTOFF,
            "grid_factor": clock.GRID_FACTOR,
            "nu": clock.NU,
        },
        "input_receipts": {
            "runs/20260921_curvature_clock_saturation/curvature_clock_saturation_receipt.json": saturation.get(
                "content_sha256"
            )
        },
        "dynamics": dynamics,
        "checks": checks,
        "source_hashes": {
            "computations/navier-stokes-curvature-budget-prereg.md": clock.sha256(
                PROTOCOL_SCRIPT
            ),
            "computations/navier_stokes_curvature_budget.py": clock.sha256(
                Path(__file__).resolve()
            ),
            "computations/navier_stokes_curvature_clock.py": clock.sha256(CLOCK_SCRIPT),
            "computations/verify_navier_stokes_galerkin_long_trajectory.py": clock.sha256(
                LONG_TRAJECTORY_SCRIPT
            ),
            "computations/verify_navier_stokes_helical_dynamic_depletion.py": clock.sha256(
                DEPLETION_SCRIPT
            ),
        },
    }
    return body


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

    receipt = json_safe(build_receipt())
    receipt["content_sha256"] = content_digest(receipt)
    payload = json.dumps(receipt, indent=1, sort_keys=True)
    (output / "curvature_budget.json").write_text(payload)
    (output / "curvature_budget_receipt.json").write_text(payload)
    for item in receipt["checks"]:
        mark = "PASS" if item["passed"] else "FAIL"
        print(f"  [{mark}] {item['name']}: {item['detail']}")
    print("=" * 78)
    print(f"status {receipt['status']}  content {receipt['content_sha256'][:16]}")
    print(f"receipt {output / 'curvature_budget_receipt.json'}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
