#!/usr/bin/env python3
"""Run the preregistered fixed-charge stationary particle campaign."""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260901_particle_stationary_bvp"
RESULTS_PATH = RUN_DIR / "results.json"
PREREG = ROOT / "computations" / "particle-stationary-bvp-pre-registration.md"
VERIFIER = ROOT / "computations" / "verify_particle_stationary_bvp.py"

PHI = (1.0 + math.sqrt(5.0)) / 2.0
COEFFICIENTS = {
    "phi": PHI,
    "alpha_s": 1.0,
    "u_rho": 4.0,
    "u_phi": 4.0,
    "gamma_x": 1.0,
    "gamma_s": 1.0,
    "u_H": 4.0,
    "k_Cx": 1.0,
    "k_Cs": 1.0,
    "e_C": 0.75,
    "h_C": 1.50,
    "u_C": 1.0,
    "q_C": 4.0,
    "L_s": 1.0,
    "xi_gf": 1.0,
}
BASINS = (
    "separated_core",
    "merged_core",
    "closed_loop",
    "carrier_lump",
    "delocalized",
    "split_multicore",
)
STRUCTURAL = tuple(basin for basin in BASINS if basin != "delocalized")
GRIDS = {"P": (4.0, 17), "D": (5.0, 21), "H": (4.0, 21)}
ETA = 1.0e-4


@dataclass
class Grid:
    family: str
    R: float
    N: int
    dx: float
    dv: float
    x: torch.Tensor
    X: torch.Tensor
    Y: torch.Tensor
    Z: torch.Tensor
    mask: torch.Tensor
    shell1: torch.Tensor
    shell2: torch.Tensor
    rotations: tuple[torch.Tensor, ...]
    sigma: torch.Tensor
    generators: torch.Tensor
    psi_inf: torch.Tensor
    h_inf: torch.Tensor


class ArmFailure(RuntimeError):
    def __init__(self, message: str, optimizer: dict[str, Any]):
        super().__init__(message)
        self.optimizer = optimizer


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def make_grid(
    family: str,
    device: torch.device,
    R: float | None = None,
    N: int | None = None,
) -> Grid:
    if R is None or N is None:
        R, N = GRIDS[family]
    x = torch.linspace(-R, R, N, device=device, dtype=torch.float64)
    X, Y, Z = torch.meshgrid(x, x, x, indexing="ij")
    mask = torch.zeros((N, N, N), device=device, dtype=torch.float64)
    mask[1:-1, 1:-1, 1:-1] = 1.0
    indices = torch.arange(N, device=device)
    ii, jj, kk = torch.meshgrid(indices, indices, indices, indexing="ij")
    shell1 = (
        (ii == 0)
        | (ii == N - 1)
        | (jj == 0)
        | (jj == N - 1)
        | (kk == 0)
        | (kk == N - 1)
    )
    shell2 = (
        (ii <= 1)
        | (ii >= N - 2)
        | (jj <= 1)
        | (jj >= N - 2)
        | (kk <= 1)
        | (kk >= N - 2)
    )
    rotations = tuple(
        torch.tensor(matrix, device=device, dtype=torch.float64)
        for matrix in (
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
            ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
            ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        )
    )
    sigma = torch.tensor(
        (
            ((0.0, 1.0), (1.0, 0.0)),
            ((0.0, -1.0j), (1.0j, 0.0)),
            ((1.0, 0.0), (0.0, -1.0)),
        ),
        device=device,
        dtype=torch.complex128,
    )
    psi_inf = torch.tensor(
        (PHI ** -0.5, PHI**-1.0), device=device, dtype=torch.float64
    )
    h_inf = torch.tensor((0.0, 0.0, 1.0), device=device, dtype=torch.float64)
    dx = 2.0 * R / (N - 1)
    return Grid(
        family=family,
        R=R,
        N=N,
        dx=dx,
        dv=dx**3,
        x=x,
        X=X,
        Y=Y,
        Z=Z,
        mask=mask,
        shell1=shell1,
        shell2=shell2,
        rotations=rotations,
        sigma=sigma,
        generators=sigma / 2.0,
        psi_inf=psi_inf,
        h_inf=h_inf,
    )


def derivatives(field: torch.Tensor, grid: Grid) -> tuple[torch.Tensor, ...]:
    return torch.gradient(
        field,
        spacing=(grid.dx, grid.dx, grid.dx),
        dim=(0, 1, 2),
        edge_order=2,
    )


def project_scalar(field: torch.Tensor) -> torch.Tensor:
    projected = torch.zeros_like(field)
    for k in range(4):
        projected = projected + torch.rot90(field, k, dims=(0, 1))
    return projected / 4.0

def project_vector(
    field: torch.Tensor, rotations: tuple[torch.Tensor, ...]
) -> torch.Tensor:
    projected = torch.zeros_like(field)
    for k, rotation in enumerate(rotations):
        rotated = torch.rot90(field, k, dims=(0, 1))
        projected = projected + torch.einsum(
            "ij,...ja->...ia", rotation, rotated
        )
    return projected / 4.0


def gaussian(grid: Grid, center: tuple[float, float, float], width: float) -> torch.Tensor:
    x0, y0, z0 = center
    radius2 = (grid.X - x0) ** 2 + (grid.Y - y0) ** 2 + (grid.Z - z0) ** 2
    return torch.exp(-radius2 / (2.0 * width**2))


def inverse_softplus(profile: torch.Tensor) -> torch.Tensor:
    return torch.log(torch.expm1(profile + ETA))


def seed_arrays(basin: str, grid: Grid) -> dict[str, torch.Tensor]:
    shape = (grid.N, grid.N, grid.N)
    psi = grid.psi_inf.expand(*shape, 2).clone().to(torch.complex128)
    h = grid.h_inf.expand(*shape, 3).clone()
    a = torch.zeros((*shape, 3, 3), device=grid.x.device, dtype=torch.float64)

    if basin == "separated_core":
        d = 1.50
        width = 0.70
        g_plus = gaussian(grid, (0.0, 0.0, d), width)
        g_minus = gaussian(grid, (0.0, 0.0, -d), width)
        r_perp2 = grid.X**2 + grid.Y**2
        interval_distance = torch.clamp(torch.abs(grid.Z) - d, min=0.0)
        g_interval = torch.exp(
            -(r_perp2 + interval_distance**2) / (2.0 * width**2)
        )
        amplitude = (1.0 - g_plus) * (1.0 - g_minus)
        theta = 0.80 * (g_plus - g_minus)
        n = torch.stack(
            (torch.sin(theta), torch.zeros_like(theta), torch.cos(theta)), dim=-1
        )
        h = amplitude[..., None] * n
        dn = derivatives(n, grid)
        a = torch.stack(tuple(-torch.cross(n, dn_i, dim=-1) for dn_i in dn), dim=-2)
        psi = (1.0 - g_interval)[..., None] * psi
        profile = g_interval
    elif basin == "merged_core":
        g = gaussian(grid, (0.0, 0.0, 0.0), 0.85)
        h = torch.stack(
            (torch.zeros_like(g), torch.zeros_like(g), 1.0 - g), dim=-1
        )
        psi = (1.0 - g)[..., None] * psi
        profile = gaussian(grid, (0.0, 0.0, 0.0), 0.80)
    elif basin == "closed_loop":
        r_perp = torch.sqrt(grid.X**2 + grid.Y**2)
        torus = torch.exp(
            -((r_perp - 1.50) ** 2 + grid.Z**2) / (2.0 * 0.55**2)
        )
        h = torch.stack(
            (torch.zeros_like(torus), torch.zeros_like(torus), 1.0 - torus),
            dim=-1,
        )
        psi = (1.0 - torus)[..., None] * psi
        e_phi = torch.stack(
            (-grid.Y, grid.X, torch.zeros_like(grid.X)), dim=-1
        ) / torch.sqrt(r_perp**2 + ETA**2)[..., None]
        a[..., :, 2] = 0.80 * torus[..., None] * e_phi
        profile = torus
    elif basin == "carrier_lump":
        profile = gaussian(grid, (0.0, 0.0, 0.0), 0.90)
    elif basin == "delocalized":
        profile = torch.ones(shape, device=grid.x.device, dtype=torch.float64)
    elif basin == "split_multicore":
        centers = (
            (1.35, 0.0, 0.0),
            (-1.35, 0.0, 0.0),
            (0.0, 1.35, 0.0),
            (0.0, -1.35, 0.0),
        )
        gaussians = [gaussian(grid, center, 0.60) for center in centers]
        amplitude = torch.ones(shape, device=grid.x.device, dtype=torch.float64)
        for value in gaussians:
            amplitude = amplitude * (1.0 - value)
        psi = amplitude[..., None] * psi
        profile = torch.stack(tuple(gaussians), dim=0).sum(dim=0)
    else:
        raise ValueError(f"Unknown basin: {basin}")

    return {
        "psi_real": psi.real,
        "psi_imag": psi.imag,
        "h": h,
        "a": a,
        "w": inverse_softplus(profile),
    }


def raw_parameters(basin: str, grid: Grid) -> dict[str, torch.nn.Parameter]:
    return {
        name: torch.nn.Parameter(value.clone())
        for name, value in seed_arrays(basin, grid).items()
    }


def physical_fields(
    raw: Mapping[str, torch.Tensor],
    grid: Grid,
    charge: float = COEFFICIENTS["q_C"],
) -> dict[str, torch.Tensor]:
    mask_scalar = grid.mask
    mask_component = mask_scalar[..., None]
    mask_connection = mask_scalar[..., None, None]

    psi_real = mask_component * project_scalar(raw["psi_real"]) + (
        1.0 - mask_component
    ) * grid.psi_inf
    psi_imag = mask_component * project_scalar(raw["psi_imag"])
    h = mask_component * project_scalar(raw["h"]) + (1.0 - mask_component) * grid.h_inf
    a = mask_connection * project_vector(raw["a"], grid.rotations)

    if charge == 0.0:
        c = torch.zeros_like(mask_scalar)
    else:
        positive = mask_scalar * F.softplus(project_scalar(raw["w"]))
        normalization = torch.sqrt(torch.sum(positive**2) * grid.dv)
        c = math.sqrt(charge) * positive / normalization

    return {
        "psi_real": psi_real,
        "psi_imag": psi_imag,
        "h": h,
        "a": a,
        "c": c,
    }


def energy_components(
    fields: dict[str, torch.Tensor], grid: Grid
) -> tuple[dict[str, torch.Tensor], torch.Tensor, dict[str, torch.Tensor]]:
    psi = torch.complex(fields["psi_real"], fields["psi_imag"])
    h = fields["h"]
    a = fields["a"]
    c = fields["c"]

    dpsi = torch.stack(derivatives(psi, grid), dim=-2)
    gauge_psi = torch.einsum(
        "...ia,abc,...c->...ib", a.to(grid.generators.dtype), grid.generators, psi
    )
    covariant_psi = dpsi - 1.0j * gauge_psi

    rho = torch.sum(torch.abs(psi) ** 2, dim=-1)
    spin = torch.einsum(
        "...b,abc,...c->...a", psi.conj(), grid.sigma, psi
    ).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * torch.sum(h * spin, dim=-1)
    )

    da = derivatives(a, grid)
    f_rows = []
    for i in range(3):
        row = []
        for j in range(3):
            row.append(
                da[i][..., j, :]
                - da[j][..., i, :]
                + torch.cross(a[..., i, :], a[..., j, :], dim=-1)
            )
        f_rows.append(torch.stack(row, dim=-2))
    curvature = torch.stack(f_rows, dim=-3)

    dh = torch.stack(derivatives(h, grid), dim=-2)
    covariant_h = dh + torch.cross(a, h[..., None, :].expand_as(a), dim=-1)
    dc = torch.stack(derivatives(c, grid), dim=-1)
    divergence = torch.stack(tuple(da[i][..., i, :] for i in range(3)), dim=0).sum(dim=0)

    components = {
        "psi_gradient": 0.5 * torch.sum(torch.abs(covariant_psi) ** 2) * grid.dv,
        "rho_potential": COEFFICIENTS["u_rho"]
        / 4.0
        * torch.sum((rho - 1.0) ** 2)
        * grid.dv,
        "composition_potential": COEFFICIENTS["u_phi"]
        / 2.0
        * torch.sum(delta_phi**2)
        * grid.dv,
        "curvature": COEFFICIENTS["gamma_x"]
        / 4.0
        * torch.sum(curvature**2)
        * grid.dv,
        "h_gradient": COEFFICIENTS["gamma_x"]
        / 2.0
        * torch.sum(covariant_h**2)
        * grid.dv,
        "h_potential": COEFFICIENTS["u_H"]
        / 4.0
        * torch.sum((torch.sum(h**2, dim=-1) - 1.0) ** 2)
        * grid.dv,
        "carrier_gradient": COEFFICIENTS["k_Cx"]
        / 2.0
        * torch.sum(dc**2)
        * grid.dv,
        "carrier_quadratic": torch.sum(
            (
                COEFFICIENTS["e_C"]
                - COEFFICIENTS["h_C"] * (1.0 - rho)
            )
            * c**2
        )
        * grid.dv,
        "carrier_quartic": COEFFICIENTS["u_C"]
        / 2.0
        * torch.sum(c**4)
        * grid.dv,
    }
    gauge_fixing = COEFFICIENTS["xi_gf"] / 2.0 * torch.sum(divergence**2) * grid.dv
    return components, gauge_fixing, {
        "rho": rho,
        "curvature": curvature,
        "divergence": divergence,
    }


def objective(
    raw: Mapping[str, torch.Tensor],
    grid: Grid,
    charge: float = COEFFICIENTS["q_C"],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
    fields = physical_fields(raw, grid, charge)
    components, gauge_fixing, _ = energy_components(fields, grid)
    physical = torch.stack(tuple(components.values())).sum()
    return physical + gauge_fixing, physical, gauge_fixing, fields


def tensor_float(value: torch.Tensor) -> float:
    return float(value.detach().cpu())


def optimizer_gradient_summary(parameters: Sequence[torch.Tensor]) -> tuple[float, float]:
    squares = torch.zeros((), device=parameters[0].device, dtype=torch.float64)
    count = 0
    maximum = torch.zeros((), device=parameters[0].device, dtype=torch.float64)
    for parameter in parameters:
        if parameter.grad is None:
            continue
        gradient = parameter.grad
        squares = squares + torch.sum(gradient**2)
        count += gradient.numel()
        maximum = torch.maximum(maximum, torch.max(torch.abs(gradient)))
    return tensor_float(torch.sqrt(squares / max(count, 1))), tensor_float(maximum)


def finite_parameters(parameters: Sequence[torch.Tensor]) -> bool:
    return all(bool(torch.isfinite(parameter).all()) for parameter in parameters)


def finite_gradients(parameters: Sequence[torch.Tensor]) -> bool:
    return all(
        parameter.grad is not None and bool(torch.isfinite(parameter.grad).all())
        for parameter in parameters
    )


def optimize_arm(
    raw: dict[str, torch.nn.Parameter], grid: Grid
) -> dict[str, Any]:
    parameters = list(raw.values())
    history: dict[str, Any] = {
        "adam_history": [],
        "lbfgs_history": [],
        "lbfgs_iterations": 0,
        "lbfgs_closure_calls": 0,
        "lbfgs_function_evaluations": 0,
    }
    adam = torch.optim.Adam(parameters, lr=0.020)
    started = time.perf_counter()

    for step in range(800):
        if step == 400:
            adam.param_groups[0]["lr"] = 0.005
        adam.zero_grad(set_to_none=True)
        loss, physical, gauge_fixing, _ = objective(raw, grid)
        if not bool(torch.isfinite(loss)):
            history["wall_seconds"] = time.perf_counter() - started
            raise ArmFailure(f"nonfinite Adam objective at step {step}", history)
        loss.backward()
        if not finite_gradients(parameters):
            history["wall_seconds"] = time.perf_counter() - started
            raise ArmFailure(f"nonfinite Adam gradient at step {step}", history)
        adam.step()
        if not finite_parameters(parameters):
            history["wall_seconds"] = time.perf_counter() - started
            raise ArmFailure(f"nonfinite Adam field at step {step}", history)
        if step % 20 == 0 or step == 799:
            raw_rms, raw_max = optimizer_gradient_summary(parameters)
            history["adam_history"].append(
                {
                    "step": step,
                    "objective": tensor_float(loss),
                    "physical_energy": tensor_float(physical),
                    "gauge_fixing_energy": tensor_float(gauge_fixing),
                    "raw_gradient_rms": raw_rms,
                    "raw_gradient_max": raw_max,
                }
            )

    lbfgs = torch.optim.LBFGS(
        parameters,
        max_iter=120,
        max_eval=150,
        history_size=20,
        tolerance_grad=1.0e-10,
        tolerance_change=1.0e-12,
        line_search_fn="strong_wolfe",
    )
    closure_calls = 0

    def closure() -> torch.Tensor:
        nonlocal closure_calls
        closure_calls += 1
        lbfgs.zero_grad(set_to_none=True)
        loss, physical, gauge_fixing, _ = objective(raw, grid)
        if not bool(torch.isfinite(loss)):
            raise ArmFailure("nonfinite L-BFGS objective", history)
        loss.backward()
        if not finite_gradients(parameters):
            raise ArmFailure("nonfinite L-BFGS gradient", history)
        raw_rms, raw_max = optimizer_gradient_summary(parameters)
        history["lbfgs_history"].append(
            {
                "closure": closure_calls,
                "objective": tensor_float(loss),
                "physical_energy": tensor_float(physical),
                "gauge_fixing_energy": tensor_float(gauge_fixing),
                "raw_gradient_rms": raw_rms,
                "raw_gradient_max": raw_max,
            }
        )
        return loss

    try:
        lbfgs.step(closure)
    except ArmFailure:
        state = lbfgs.state.get(parameters[0], {})
        history["lbfgs_iterations"] = int(state.get("n_iter", 0))
        history["lbfgs_closure_calls"] = closure_calls
        history["lbfgs_function_evaluations"] = int(state.get("func_evals", 0))
        history["wall_seconds"] = time.perf_counter() - started
        raise
    state = lbfgs.state.get(parameters[0], {})
    history["lbfgs_iterations"] = int(state.get("n_iter", 0))
    history["lbfgs_closure_calls"] = closure_calls
    history["lbfgs_function_evaluations"] = int(state.get("func_evals", 0))
    if not finite_parameters(parameters):
        history["wall_seconds"] = time.perf_counter() - started
        raise ArmFailure("nonfinite field after L-BFGS", history)
    history["wall_seconds"] = time.perf_counter() - started
    return history


def physical_gradient_rms(fields: dict[str, torch.Tensor], grid: Grid) -> float:
    psi_real = fields["psi_real"].detach().clone().requires_grad_(True)
    psi_imag = fields["psi_imag"].detach().clone().requires_grad_(True)
    h = fields["h"].detach().clone().requires_grad_(True)
    a = fields["a"].detach().clone().requires_grad_(True)
    c = fields["c"].detach().clone().requires_grad_(True)
    leaves = {"psi_real": psi_real, "psi_imag": psi_imag, "h": h, "a": a, "c": c}
    components, _, _ = energy_components(leaves, grid)
    physical = torch.stack(tuple(components.values())).sum()
    gradients = torch.autograd.grad(physical, (psi_real, psi_imag, h, a, c))
    mask_component = grid.mask[..., None]
    mask_connection = grid.mask[..., None, None]
    projected = [
        project_scalar(mask_component * gradients[0] / grid.dv),
        project_scalar(mask_component * gradients[1] / grid.dv),
        project_scalar(mask_component * gradients[2] / grid.dv),
        project_vector(mask_connection * gradients[3] / grid.dv, grid.rotations),
    ]
    carrier_gradient = gradients[4] / grid.dv
    inner = torch.sum(c * carrier_gradient) * grid.dv
    norm = torch.sum(c**2) * grid.dv
    carrier_tangent = grid.mask * (carrier_gradient - c * inner / norm)
    projected.append(project_scalar(carrier_tangent))
    squared = torch.stack(tuple(torch.sum(value**2) for value in projected)).sum()
    active = int(torch.sum(grid.mask).item()) * 17
    return tensor_float(torch.sqrt(squared / active))


def virial_diagnostics(
    fields: dict[str, torch.Tensor], grid: Grid, components: dict[str, torch.Tensor]
) -> tuple[float, float, dict[str, float]]:
    psi = torch.complex(fields["psi_real"], fields["psi_imag"])
    h = fields["h"]
    a = fields["a"]
    c = fields["c"]
    chi = (
        (1.0 - (grid.X / grid.R) ** 2) ** 2
        * (1.0 - (grid.Y / grid.R) ** 2) ** 2
        * (1.0 - (grid.Z / grid.R) ** 2) ** 2
    )
    v = chi[..., None] * torch.stack((grid.X, grid.Y, grid.Z), dim=-1)
    dpsi = derivatives(psi, grid)
    dh = derivatives(h, grid)
    da = derivatives(a, grid)
    dv = derivatives(v, grid)
    dot_psi = -torch.stack(
        tuple(v[..., j, None] * dpsi[j] for j in range(3)), dim=0
    ).sum(dim=0)
    dot_h = -torch.stack(
        tuple(v[..., j, None] * dh[j] for j in range(3)), dim=0
    ).sum(dim=0)
    advected_a = torch.stack(
        tuple(v[..., j, None, None] * da[j] for j in range(3)), dim=0
    ).sum(dim=0)
    one_form = torch.stack(
        tuple(
            torch.einsum("...j,...ja->...a", dv[i], a)
            for i in range(3)
        ),
        dim=-2,
    )
    dot_a = -advected_a - one_form
    log_c = torch.log(c + 1.0e-12)
    dlog_c = derivatives(log_c, grid)
    divergence_v = torch.stack(tuple(dv[i][..., i] for i in range(3)), dim=0).sum(dim=0)
    transport_c = torch.stack(
        tuple(v[..., j] * dlog_c[j] for j in range(3)), dim=0
    ).sum(dim=0)
    s_c = -transport_c - 0.5 * divergence_v

    perturbed_components: dict[int, dict[str, torch.Tensor]] = {}
    for sign in (-1, 1):
        t = sign * 1.0e-4
        psi_t = project_scalar(psi + t * dot_psi)
        psi_t = grid.mask[..., None] * psi_t + (1.0 - grid.mask[..., None]) * grid.psi_inf
        h_t = project_scalar(h + t * dot_h)
        h_t = grid.mask[..., None] * h_t + (1.0 - grid.mask[..., None]) * grid.h_inf
        a_t = project_vector(a + t * dot_a, grid.rotations) * grid.mask[..., None, None]
        positive = grid.mask * c * torch.exp(t * s_c)
        c_t = math.sqrt(COEFFICIENTS["q_C"]) * positive / torch.sqrt(
            torch.sum(positive**2) * grid.dv
        )
        trial = {
            "psi_real": psi_t.real,
            "psi_imag": psi_t.imag,
            "h": h_t,
            "a": a_t,
            "c": c_t,
        }
        perturbed_components[sign], _, _ = energy_components(trial, grid)

    directional: dict[str, float] = {}
    for name in components:
        value = (perturbed_components[1][name] - perturbed_components[-1][name]) / 2.0e-4
        directional[name] = tensor_float(value)
    numerator = abs(sum(directional.values()))
    denominator = max(1.0e-12, sum(abs(value) for value in directional.values()))
    cutoff = numerator / denominator
    formal = (
        tensor_float(components["psi_gradient"])
        + tensor_float(components["h_gradient"])
        - tensor_float(components["curvature"])
        + 3.0
        * (
            tensor_float(components["rho_potential"])
            + tensor_float(components["composition_potential"])
            + tensor_float(components["h_potential"])
        )
        - 2.0 * tensor_float(components["carrier_gradient"])
        - 3.0 * tensor_float(components["carrier_quartic"])
    )
    return cutoff, formal, directional


def face(array: torch.Tensor, axis: int, index: int) -> torch.Tensor:
    selection: list[Any] = [slice(None)] * array.ndim
    selection[axis] = index
    return array[tuple(selection)]

def outer_magnetic_number(
    fields: dict[str, torch.Tensor], curvature: torch.Tensor, grid: Grid
) -> float:
    h = fields["h"]
    a = fields["a"]
    weights_1d = torch.ones(grid.N, device=grid.x.device, dtype=torch.float64)
    weights_1d[0] = 0.5
    weights_1d[-1] = 0.5
    weights = weights_1d[:, None] * weights_1d[None, :]
    flux = torch.zeros((), device=grid.x.device, dtype=torch.float64)
    cyclic = ((0, 1, 2), (1, 2, 0), (2, 0, 1))

    for normal, tangent_j, tangent_k in cyclic:
        remaining = [axis for axis in range(3) if axis != normal]
        for index, sign in ((grid.N - 1, 1.0), (0, -1.0)):
            h_face = face(h, normal, index)
            h_hat = h_face / torch.linalg.vector_norm(h_face, dim=-1, keepdim=True)
            dh_face = torch.gradient(
                h_hat,
                spacing=(grid.dx, grid.dx),
                dim=(0, 1),
                edge_order=2,
            )
            a_face = face(a, normal, index)
            d_j = dh_face[remaining.index(tangent_j)] + torch.cross(
                a_face[..., tangent_j, :], h_hat, dim=-1
            )
            d_k = dh_face[remaining.index(tangent_k)] + torch.cross(
                a_face[..., tangent_k, :], h_hat, dim=-1
            )
            f_jk = face(curvature[..., tangent_j, tangent_k, :], normal, index)
            residual = torch.sum(h_hat * f_jk, dim=-1) - torch.sum(
                h_hat * torch.cross(d_j, d_k, dim=-1), dim=-1
            )
            flux = flux + sign * grid.dx**2 * torch.sum(weights * residual)
    return tensor_float(flux / (4.0 * math.pi))


def boundary_residual(fields: dict[str, torch.Tensor], grid: Grid) -> float:
    shell = grid.shell1
    residuals = (
        torch.max(torch.abs(fields["psi_real"][shell] - grid.psi_inf)),
        torch.max(torch.abs(fields["psi_imag"][shell])),
        torch.max(torch.abs(fields["h"][shell] - grid.h_inf)),
        torch.max(torch.abs(fields["a"][shell])),
        torch.max(torch.abs(fields["c"][shell])),
    )
    return max(tensor_float(value) for value in residuals)


def objective_gradient_diagnostic(
    raw: dict[str, torch.nn.Parameter], grid: Grid
) -> tuple[float, float]:
    parameters = list(raw.values())
    for parameter in parameters:
        parameter.grad = None
    loss, _, _, _ = objective(raw, grid)
    loss.backward()
    return optimizer_gradient_summary(parameters)


def diagnostics(
    raw: dict[str, torch.nn.Parameter], grid: Grid
) -> tuple[dict[str, Any], dict[str, torch.Tensor]]:
    fields = {name: value.detach() for name, value in physical_fields(raw, grid).items()}
    components_t, gauge_fixing_t, aux = energy_components(fields, grid)
    components = {name: tensor_float(value) for name, value in components_t.items()}
    physical_energy = sum(components.values())
    charge = tensor_float(torch.sum(fields["c"] ** 2) * grid.dv)
    rho = aux["rho"]
    depletion = torch.clamp(1.0 - rho, min=0.0)
    depletion_weight = tensor_float(torch.sum(depletion) * grid.dv)
    if depletion_weight < 1.0e-12:
        core_length = 0.0
    else:
        core_length = 2.0 * math.sqrt(
            tensor_float(torch.sum(grid.Z**2 * depletion) * grid.dv) / depletion_weight
        )
    radius2 = grid.X**2 + grid.Y**2 + grid.Z**2
    carrier_radius = math.sqrt(
        tensor_float(torch.sum(radius2 * fields["c"] ** 2) * grid.dv) / charge
    )
    omega = (
        components["carrier_gradient"]
        + components["carrier_quadratic"]
        + 2.0 * components["carrier_quartic"]
    ) / charge
    physical_rms = physical_gradient_rms(fields, grid)
    cutoff, formal, directional = virial_diagnostics(fields, grid, components_t)
    independent_curvature = torch.stack(
        (
            aux["curvature"][..., 0, 1, :],
            aux["curvature"][..., 0, 2, :],
            aux["curvature"][..., 1, 2, :],
        ),
        dim=-2,
    )
    outer_flux_rms = tensor_float(
        torch.sqrt(torch.mean(independent_curvature[grid.shell1] ** 2))
    )
    gauge_divergence_rms = tensor_float(torch.sqrt(torch.mean(aux["divergence"] ** 2)))
    gauge_fixing = tensor_float(gauge_fixing_t)
    outer_fraction = tensor_float(
        torch.sum(fields["c"][grid.shell2] ** 2) / torch.sum(fields["c"] ** 2)
    )
    raw_rms, raw_max = objective_gradient_diagnostic(raw, grid)
    result = {
        "physical_energy": physical_energy,
        "charge": charge,
        "charge_relative_error": abs(charge - COEFFICIENTS["q_C"])
        / COEFFICIENTS["q_C"],
        "omega_c": omega,
        "core_length": core_length,
        "carrier_radius": carrier_radius,
        "physical_gradient_rms": physical_rms,
        "cutoff_virial": cutoff,
        "formal_virial": formal,
        "cutoff_directional_components": directional,
        "outer_flux_rms": outer_flux_rms,
        "outer_magnetic_number": outer_magnetic_number(fields, aux["curvature"], grid),
        "gauge_divergence_rms": gauge_divergence_rms,
        "gauge_fixing_energy": gauge_fixing,
        "gauge_fixing_fraction": gauge_fixing / max(abs(physical_energy), 1.0e-12),
        "outer_carrier_fraction": outer_fraction,
        "max_density_depletion": tensor_float(torch.max(depletion)),
        "boundary_residual": boundary_residual(fields, grid),
        "objective_raw_gradient_rms": raw_rms,
        "objective_raw_gradient_max": raw_max,
        "energy_components": components,
    }
    return result, fields


def save_fields(path: Path, fields: dict[str, torch.Tensor], grid: Grid) -> None:
    arrays = {
        "x": np.ascontiguousarray(grid.x.detach().cpu().numpy(), dtype=np.float64),
        "psi_real": np.ascontiguousarray(
            fields["psi_real"].detach().cpu().numpy(), dtype=np.float64
        ),
        "psi_imag": np.ascontiguousarray(
            fields["psi_imag"].detach().cpu().numpy(), dtype=np.float64
        ),
        "h": np.ascontiguousarray(fields["h"].detach().cpu().numpy(), dtype=np.float64),
        "a": np.ascontiguousarray(fields["a"].detach().cpu().numpy(), dtype=np.float64),
        "c": np.ascontiguousarray(fields["c"].detach().cpu().numpy(), dtype=np.float64),
    }
    np.savez_compressed(path, **arrays)


def q1_q4(completed: bool, values: dict[str, Any] | None) -> dict[str, bool]:
    if not completed or values is None:
        return {"Q1": False, "Q2": False, "Q3": False, "Q4": False}
    return {
        "Q1": values["charge_relative_error"] <= 5.0e-12
        and values["boundary_residual"] <= 1.0e-12,
        "Q2": values["physical_gradient_rms"] <= 3.0e-4
        and values["cutoff_virial"] <= 0.08,
        "Q3": values["gauge_divergence_rms"] <= 0.02
        and values["gauge_fixing_fraction"] <= 0.01,
        "Q4": values["outer_flux_rms"] <= 0.05
        and abs(values["outer_magnetic_number"]) <= 1.0e-10,
    }


def run_arm(family: str, basin: str, device: torch.device) -> dict[str, Any]:
    grid = make_grid(family, device)
    raw = raw_parameters(basin, grid)
    optimizer = optimize_arm(raw, grid)
    values, fields = diagnostics(raw, grid)
    artifact_name = f"fields_{family}_{basin}.npz"
    artifact_path = RUN_DIR / artifact_name
    save_fields(artifact_path, fields, grid)
    artifact_digest = sha256(artifact_path)
    return {
        "family": family,
        "basin": basin,
        "R": grid.R,
        "N": grid.N,
        "dx": grid.dx,
        "artifact": artifact_name,
        "artifact_sha256": artifact_digest,
        "completed": True,
        "error": None,
        "optimizer": optimizer,
        "diagnostics": values,
        "gates": q1_q4(True, values),
    }


def failed_arm(
    family: str, basin: str, message: str, optimizer: dict[str, Any]
) -> dict[str, Any]:
    R, N = GRIDS[family]
    return {
        "family": family,
        "basin": basin,
        "R": R,
        "N": N,
        "dx": 2.0 * R / (N - 1),
        "artifact": None,
        "artifact_sha256": None,
        "completed": False,
        "error": message,
        "optimizer": optimizer,
        "diagnostics": None,
        "gates": q1_q4(False, None),
    }


def all_q1_q4(arm: dict[str, Any]) -> bool:
    return all(arm["gates"].values())


def reldiff(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-12)


def localized(arm: dict[str, Any]) -> bool:
    if not all_q1_q4(arm) or arm["diagnostics"] is None:
        return False
    values = arm["diagnostics"]
    return (
        values["outer_carrier_fraction"] <= 1.0e-3
        and values["carrier_radius"] < arm["R"] / 2.0
        and values["omega_c"] < 0.73
        and values["max_density_depletion"] >= 0.10
    )


def comparison_metrics(primary: dict[str, Any], other: dict[str, Any]) -> dict[str, Any]:
    p = primary["diagnostics"]
    o = other["diagnostics"]
    assert p is not None and o is not None
    localized_radius = (
        p["outer_carrier_fraction"] <= 0.01
        and o["outer_carrier_fraction"] <= 0.01
    )
    radius_difference = (
        reldiff(p["carrier_radius"], o["carrier_radius"])
        if localized_radius
        else reldiff(
            p["carrier_radius"] / primary["R"],
            o["carrier_radius"] / other["R"],
        )
    )
    metrics = {
        "energy_relative_difference": reldiff(
            p["physical_energy"], o["physical_energy"]
        ),
        "core_length_absolute_difference": abs(p["core_length"] - o["core_length"]),
        "omega_absolute_difference": abs(p["omega_c"] - o["omega_c"]),
        "radius_difference": radius_difference,
        "radius_branch": "absolute" if localized_radius else "normalized",
    }
    metrics["pass"] = (
        metrics["energy_relative_difference"] <= 0.05
        and metrics["core_length_absolute_difference"] <= 0.75
        and metrics["omega_absolute_difference"] <= 0.10
        and metrics["radius_difference"] <= 0.10
    )
    return metrics


def evaluate_campaign(receipt: dict[str, Any]) -> None:
    arms = receipt["arms"]
    structural_domain: dict[str, Any] = {}
    for basin in STRUCTURAL:
        primary = arms[f"P:{basin}"]
        domain = arms[f"D:{basin}"]
        if all_q1_q4(primary) and all_q1_q4(domain):
            metrics = comparison_metrics(primary, domain)
        else:
            metrics = {"pass": False, "reason": "Q1-Q4 failure"}
        structural_domain[basin] = metrics

    p_control = arms["P:delocalized"]
    d_control = arms["D:delocalized"]
    control_localized_p = localized(p_control)
    control_localized_d = localized(d_control)
    if not (all_q1_q4(p_control) and all_q1_q4(d_control)):
        control = {"mode": "invalid", "pass": False, "reason": "Q1-Q4 failure"}
    elif control_localized_p and control_localized_d:
        control = {
            "mode": "localized",
            **comparison_metrics(p_control, d_control),
        }
    elif not control_localized_p and not control_localized_d:
        p_values = p_control["diagnostics"]
        d_values = d_control["diagnostics"]
        assert p_values is not None and d_values is not None
        radius_difference = reldiff(
            p_values["carrier_radius"] / p_control["R"],
            d_values["carrier_radius"] / d_control["R"],
        )
        quartic_ok = (
            d_values["energy_components"]["carrier_quartic"]
            <= p_values["energy_components"]["carrier_quartic"] + 1.0e-6
        )
        energy_target = abs(
            d_values["physical_energy"]
            - COEFFICIENTS["e_C"] * COEFFICIENTS["q_C"]
        ) / (COEFFICIENTS["e_C"] * COEFFICIENTS["q_C"])
        control = {
            "mode": "dilution",
            "radius_difference": radius_difference,
            "quartic_nonincrease": quartic_ok,
            "energy_target_relative_difference": energy_target,
            "pass": radius_difference <= 0.10 and quartic_ok and energy_target <= 0.25,
        }
    else:
        control = {
            "mode": "localization_mismatch",
            "localized_P": control_localized_p,
            "localized_D": control_localized_d,
            "pass": False,
        }

    selected = receipt["h_selection"]["basin"]
    if selected is None or f"H:{selected}" not in arms:
        resolution = {"pass": False, "reason": "no H arm"}
    else:
        primary = arms[f"P:{selected}"]
        high = arms[f"H:{selected}"]
        if all_q1_q4(primary) and all_q1_q4(high):
            resolution = comparison_metrics(primary, high)
        else:
            resolution = {"pass": False, "reason": "Q1-Q4 failure"}

    quality_all = (
        all(bool(values.get("pass")) for values in structural_domain.values())
        and bool(control.get("pass"))
        and bool(resolution.get("pass"))
    )
    receipt["gates"] = {
        "structural_domain": structural_domain,
        "delocalized_control": control,
        "resolution": resolution,
        "quality_all": quality_all,
    }

    uncertainties: dict[str, float] = {}
    for basin in BASINS:
        p_values = arms[f"P:{basin}"]["diagnostics"]
        d_values = arms[f"D:{basin}"]["diagnostics"]
        if p_values is None or d_values is None:
            uncertainties[basin] = math.inf
        else:
            uncertainties[basin] = abs(
                p_values["physical_energy"] - d_values["physical_energy"]
            )
    if selected is not None and f"H:{selected}" in arms:
        p_values = arms[f"P:{selected}"]["diagnostics"]
        h_values = arms[f"H:{selected}"]["diagnostics"]
        if p_values is not None and h_values is not None:
            uncertainties[selected] = max(
                uncertainties[selected],
                abs(p_values["physical_energy"] - h_values["physical_energy"]),
            )

    margins: dict[str, float] = {}
    if quality_all:
        for left in BASINS:
            left_values = arms[f"P:{left}"]["diagnostics"]
            assert left_values is not None
            for right in BASINS:
                if left == right:
                    continue
                right_values = arms[f"P:{right}"]["diagnostics"]
                assert right_values is not None
                margins[f"{left}<{right}"] = (
                    right_values["physical_energy"]
                    - left_values["physical_energy"]
                    - 0.01
                    - 2.0 * (uncertainties[left] + uncertainties[right])
                )
    receipt["pairwise_ordering_margins"] = margins

    if not receipt["preflight"]["pass"]:
        verdict = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    elif not quality_all:
        verdict = "INCONCLUSIVE—NUMERICAL QUALITY"
    else:
        localized_structural = [
            basin for basin in STRUCTURAL if localized(arms[f"P:{basin}"])
        ]
        winner = next(
            (
                basin
                for basin in localized_structural
                if all(margins[f"{basin}<{other}"] > 0.0 for other in BASINS if other != basin)
            ),
            None,
        )
        if winner is not None:
            verdict = "EMERGES—LOCALIZED FIXED-CHARGE STATIONARY BASIN"
        elif not localized_structural or all(
            margins[f"delocalized<{basin}"] > 0.0 for basin in localized_structural
        ):
            verdict = "DOES NOT EMERGE—LOCALIZED FIXED-CHARGE STATIONARY BASIN"
        else:
            verdict = "INCONCLUSIVE—BASIN ORDERING"
    receipt["verdict"] = verdict


def preflight(device: torch.device, hashes: dict[str, Any]) -> dict[str, Any]:
    grid = make_grid("P", device)
    vacuum_seed = seed_arrays("carrier_lump", grid)
    vacuum_raw = {
        "psi_real": grid.psi_inf.expand(grid.N, grid.N, grid.N, 2).clone(),
        "psi_imag": torch.zeros(
            (grid.N, grid.N, grid.N, 2), device=device, dtype=torch.float64
        ),
        "h": grid.h_inf.expand(grid.N, grid.N, grid.N, 3).clone(),
        "a": torch.zeros(
            (grid.N, grid.N, grid.N, 3, 3), device=device, dtype=torch.float64
        ),
        "w": vacuum_seed["w"],
    }
    _, vacuum_energy, _, _ = objective(vacuum_raw, grid, charge=0.0)
    g1_value = abs(tensor_float(vacuum_energy))

    test_grid = make_grid("G2", device, R=2.0, N=7)
    idx = torch.arange(7, device=device)
    ii, jj, kk = torch.meshgrid(idx, idx, idx, indexing="ij")

    block_specs = (
        ("psi_real", (0,)),
        ("psi_real", (1,)),
        ("psi_imag", (0,)),
        ("psi_imag", (1,)),
        ("h", (0,)),
        ("h", (1,)),
        ("h", (2,)),
        ("a", (0, 0)),
        ("a", (1, 1)),
        ("a", (2, 2)),
        ("a", (0, 2)),
        ("w", ()),
    )
    checks = []
    for r, (name, components) in enumerate(block_specs):
        raw = raw_parameters("merged_core", test_grid)
        direction = test_grid.mask * torch.cos(
            (r + 1) * (ii + 1).to(torch.float64)
            + 2.0 * (jj + 1).to(torch.float64)
            + 3.0 * (kk + 1).to(torch.float64)
        )
        direction = direction / torch.linalg.vector_norm(direction)
        selection = (slice(None), slice(None), slice(None), *components)
        with torch.no_grad():
            raw[name][selection] += 0.03 * direction
        loss, _, _, _ = objective(raw, test_grid)
        loss.backward()
        gradient = raw[name].grad
        assert gradient is not None
        automatic = tensor_float(torch.sum(gradient[selection] * direction))
        with torch.no_grad():
            raw[name][selection] += 1.0e-5 * direction
        plus = tensor_float(objective(raw, test_grid)[0])
        with torch.no_grad():
            raw[name][selection] -= 2.0e-5 * direction
        minus = tensor_float(objective(raw, test_grid)[0])
        finite_difference = (plus - minus) / 2.0e-5
        relative_error = abs(automatic - finite_difference) / max(
            1.0e-8, abs(automatic), abs(finite_difference)
        )
        checks.append(
            {
                "r": r,
                "block": name + ("[" + ",".join(map(str, components)) + "]" if components else ""),
                "autograd": automatic,
                "finite_difference": finite_difference,
                "relative_error": relative_error,
                "pass": relative_error <= 5.0e-5,
            }
        )

    charge_fields = physical_fields(raw_parameters("merged_core", test_grid), test_grid)
    charge_value = tensor_float(torch.sum(charge_fields["c"] ** 2) * test_grid.dv)
    g3_value = abs(charge_value - COEFFICIENTS["q_C"]) / COEFFICIENTS["q_C"]
    required_hashes = (
        "authority_action",
        "authority_core_support",
        "authority_magnetic_boundary",
        "preregistration",
        "primary_program",
        "independent_verifier",
    )
    result: dict[str, Any] = {
        "G1": {"vacuum_energy_abs": g1_value, "pass": g1_value < 1.0e-12},
        "G2": {"checks": checks, "pass": all(check["pass"] for check in checks)},
        "G3": {"charge_relative_error": g3_value, "pass": g3_value < 5.0e-12},
        "G4": {
            "required_keys": list(required_hashes),
            "pass": all(key in hashes and len(hashes[key]) == 64 for key in required_hashes),
        },
    }
    result["pass"] = all(result[key]["pass"] for key in ("G1", "G2", "G3", "G4"))
    return result


def source_hashes() -> dict[str, Any]:
    paths = {
        "authority_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
        "authority_core_support": ROOT / "foundations" / "core-trapped-charge-support.md",
        "authority_magnetic_boundary": ROOT
        / "foundations"
        / "nonabelian-magnetic-core-boundary.md",
        "preregistration": PREREG,
        "primary_program": Path(__file__).resolve(),
        "independent_verifier": VERIFIER,
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing frozen source: " + ", ".join(missing))
    return {**{name: sha256(path) for name, path in paths.items()}, "artifacts": {}}


def environment_receipt(device: torch.device) -> dict[str, Any]:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "hip": torch.version.hip,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "dtype": "float64",
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
    }


def run() -> dict[str, Any]:
    if RESULTS_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite frozen receipt: {RESULTS_PATH}")
    if not torch.cuda.is_available():
        raise RuntimeError("ROCm device exposed as cuda:0 is unavailable")
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    device = torch.device("cuda:0")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    hashes = source_hashes()
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "coefficients": COEFFICIENTS,
        "environment": environment_receipt(device),
        "hashes": hashes,
        "preflight": {},
        "arm_inventory": {
            "P": list(BASINS),
            "D": list(BASINS),
            "H": "lowest-energy structural P basin passing Q1-Q4",
        },
        "run_order": [],
        "arms": {},
        "h_selection": {"basin": None, "eligible": []},
        "gates": {},
        "pairwise_ordering_margins": {},
        "verdict": None,
    }
    receipt["preflight"] = preflight(device, hashes)
    if not receipt["preflight"]["pass"]:
        receipt["verdict"] = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
        write_json(RESULTS_PATH, receipt)
        return receipt
    write_json(RESULTS_PATH, receipt)

    def execute(family: str, basin: str) -> None:
        key = f"{family}:{basin}"
        print(f"RUN {key}", flush=True)
        try:
            arm = run_arm(family, basin, device)
        except ArmFailure as failure:
            arm = failed_arm(family, basin, str(failure), failure.optimizer)
        receipt["arms"][key] = arm
        receipt["run_order"].append(key)
        if arm["artifact"] is not None:
            receipt["hashes"]["artifacts"][arm["artifact"]] = arm["artifact_sha256"]
        write_json(RESULTS_PATH, receipt)
        if arm["diagnostics"] is None:
            print(f"FAIL {key}: {arm['error']}", flush=True)
        else:
            print(
                f"DONE {key} E={arm['diagnostics']['physical_energy']:.9g} "
                f"grad={arm['diagnostics']['physical_gradient_rms']:.3g}",
                flush=True,
            )

    for basin in BASINS:
        execute("P", basin)

    eligible = [
        basin for basin in STRUCTURAL if all_q1_q4(receipt["arms"][f"P:{basin}"])
    ]
    if eligible:
        minimum_energy = min(
            receipt["arms"][f"P:{basin}"]["diagnostics"]["physical_energy"]
            for basin in eligible
        )
        selected = next(
            basin
            for basin in STRUCTURAL
            if basin in eligible
            and receipt["arms"][f"P:{basin}"]["diagnostics"]["physical_energy"]
            <= minimum_energy + 1.0e-10
        )
    else:
        selected = None
    receipt["h_selection"] = {"basin": selected, "eligible": eligible}
    write_json(RESULTS_PATH, receipt)
    if selected is not None:
        execute("H", selected)

    for basin in BASINS:
        execute("D", basin)

    evaluate_campaign(receipt)
    write_json(RESULTS_PATH, receipt)
    return receipt


def main() -> None:
    receipt = run()
    print(json.dumps({"verdict": receipt["verdict"], "results": str(RESULTS_PATH)}))
    raise SystemExit(0 if receipt["preflight"].get("pass") else 2)


if __name__ == "__main__":
    main()
