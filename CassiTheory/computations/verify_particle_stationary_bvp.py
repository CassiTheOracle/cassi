#!/usr/bin/env python3
"""Independently verify the preregistered stationary fixed-charge campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "runs" / "20260901_particle_stationary_bvp" / "results.json"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6
Q_C = 4.0
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
    "q_C": Q_C,
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
FIELD_KEYS = ("x", "psi_real", "psi_imag", "h", "a", "c")
COMPONENT_KEYS = (
    "psi_gradient",
    "rho_potential",
    "composition_potential",
    "curvature",
    "h_gradient",
    "h_potential",
    "carrier_gradient",
    "carrier_quadratic",
    "carrier_quartic",
)
SOURCE_PATHS = {
    "authority_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
    "authority_core_support": ROOT / "foundations" / "core-trapped-charge-support.md",
    "authority_magnetic_boundary": ROOT
    / "foundations"
    / "nonabelian-magnetic-core-boundary.md",
    "preregistration": ROOT
    / "computations"
    / "particle-stationary-bvp-pre-registration.md",
    "primary_program": ROOT / "computations" / "particle_stationary_bvp.py",
    "independent_verifier": Path(__file__).resolve(),
}
HASH_KEYS = (*SOURCE_PATHS.keys(), "artifacts")
TOP_LEVEL_KEYS = {
    "schema_version",
    "coefficients",
    "environment",
    "hashes",
    "preflight",
    "arm_inventory",
    "run_order",
    "arms",
    "h_selection",
    "gates",
    "pairwise_ordering_margins",
    "verdict",
}
ARM_KEYS = {
    "family",
    "basin",
    "R",
    "N",
    "dx",
    "artifact",
    "artifact_sha256",
    "completed",
    "error",
    "optimizer",
    "diagnostics",
    "gates",
}
OPTIMIZER_KEYS = {
    "adam_history",
    "lbfgs_history",
    "lbfgs_iterations",
    "lbfgs_closure_calls",
    "lbfgs_function_evaluations",
    "wall_seconds",
}
ADAM_ROW_KEYS = {
    "step",
    "objective",
    "physical_energy",
    "gauge_fixing_energy",
    "raw_gradient_rms",
    "raw_gradient_max",
}
LBFGS_ROW_KEYS = {
    "closure",
    "objective",
    "physical_energy",
    "gauge_fixing_energy",
    "raw_gradient_rms",
    "raw_gradient_max",
}
SIGMA = np.array(
    (
        ((0.0, 1.0), (1.0, 0.0)),
        ((0.0, -1.0j), (1.0j, 0.0)),
        ((1.0, 0.0), (0.0, -1.0)),
    ),
    dtype=np.complex128,
)
ROTATIONS = np.array(
    (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ),
    dtype=np.float64,
)


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def mismatch(
    out: list[dict[str, Any]],
    path: str,
    expected: Any,
    actual: Any,
    kind: str = "mismatch",
    tolerance: float | None = None,
) -> None:
    row = {
        "kind": kind,
        "path": path,
        "expected": json_safe(expected),
        "actual": json_safe(actual),
    }
    if tolerance is not None:
        row["tolerance"] = tolerance
    out.append(row)


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def finite_number(value: Any) -> bool:
    return is_number(value) and math.isfinite(float(value))


def close(actual: Any, expected: float) -> bool:
    if not finite_number(actual) or not math.isfinite(expected):
        return False
    return abs(float(actual) - expected) <= ABS_TOL + REL_TOL * abs(expected)


def compare_float(
    out: list[dict[str, Any]], path: str, actual: Any, expected: float
) -> None:
    tolerance = ABS_TOL + REL_TOL * abs(expected)
    if not close(actual, expected):
        mismatch(out, path, expected, actual, "tolerance", tolerance)


def compare_tree(
    out: list[dict[str, Any]], path: str, actual: Any, expected: Any
) -> None:
    if isinstance(expected, float):
        compare_float(out, path, actual, expected)
        return
    if isinstance(expected, bool):
        if not isinstance(actual, bool) or actual is not expected:
            mismatch(out, path, expected, actual, "exact")
        return
    if isinstance(expected, int):
        if not isinstance(actual, int) or isinstance(actual, bool) or actual != expected:
            mismatch(out, path, expected, actual, "exact")
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatch(out, path, expected, actual, "schema")
            return
        if set(actual) != set(expected):
            mismatch(out, f"{path}.keys", sorted(expected), sorted(actual), "exact")
        for key, value in expected.items():
            if key in actual:
                compare_tree(out, f"{path}.{key}", actual[key], value)
        return
    if isinstance(expected, list):
        if not isinstance(actual, list):
            mismatch(out, path, expected, actual, "schema")
            return
        if len(actual) != len(expected):
            mismatch(out, f"{path}.length", len(expected), len(actual), "exact")
        for index, value in enumerate(expected[: len(actual)]):
            compare_tree(out, f"{path}[{index}]", actual[index], value)
        return
    if actual != expected:
        mismatch(out, path, expected, actual, "exact")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shell_mask(n: int, width: int = 1) -> np.ndarray:
    indices = np.arange(n)
    ii, jj, kk = np.meshgrid(indices, indices, indices, indexing="ij")
    return (
        (ii < width)
        | (ii >= n - width)
        | (jj < width)
        | (jj >= n - width)
        | (kk < width)
        | (kk >= n - width)
    )


def gradient(field: np.ndarray, dx: float) -> tuple[np.ndarray, ...]:
    return tuple(
        np.gradient(field, dx, dx, dx, axis=(0, 1, 2), edge_order=2)
    )


def project_scalar(field: np.ndarray) -> np.ndarray:
    return sum(np.rot90(field, k, axes=(0, 1)) for k in range(4)) / 4.0


def project_vector(field: np.ndarray) -> np.ndarray:
    projected = np.zeros_like(field)
    for k, rotation in enumerate(ROTATIONS):
        rotated = np.rot90(field, k, axes=(0, 1))
        projected += np.einsum("ij,...ja->...ia", rotation, rotated)
    return projected / 4.0


def numpy_energy(
    psi: np.ndarray,
    h: np.ndarray,
    a: np.ndarray,
    c: np.ndarray,
    x: np.ndarray,
) -> tuple[dict[str, float], float, dict[str, np.ndarray]]:
    dx = float(x[1] - x[0])
    dv = dx**3
    dpsi = np.stack(gradient(psi, dx), axis=-2)
    gauge_psi = np.einsum(
        "...ia,abc,...c->...ib", a.astype(np.complex128), SIGMA / 2.0, psi
    )
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = np.sum(np.abs(psi) ** 2, axis=-1)
    spin = np.einsum("...b,abc,...c->...a", psi.conj(), SIGMA, psi).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * np.sum(h * spin, axis=-1)
    )

    da = gradient(a, dx)
    curvature = np.stack(
        tuple(
            np.stack(
                tuple(
                    da[i][..., j, :]
                    - da[j][..., i, :]
                    + np.cross(a[..., i, :], a[..., j, :])
                    for j in range(3)
                ),
                axis=-2,
            )
            for i in range(3)
        ),
        axis=-3,
    )
    dh = np.stack(gradient(h, dx), axis=-2)
    covariant_h = dh + np.cross(a, np.broadcast_to(h[..., None, :], a.shape))
    dc = np.stack(gradient(c, dx), axis=-1)
    divergence = sum(da[i][..., i, :] for i in range(3))

    components = {
        "psi_gradient": 0.5 * float(np.sum(np.abs(covariant_psi) ** 2) * dv),
        "rho_potential": float(np.sum((rho - 1.0) ** 2) * dv),
        "composition_potential": 2.0 * float(np.sum(delta_phi**2) * dv),
        "curvature": 0.25 * float(np.sum(curvature**2) * dv),
        "h_gradient": 0.5 * float(np.sum(covariant_h**2) * dv),
        "h_potential": float(np.sum((np.sum(h**2, axis=-1) - 1.0) ** 2) * dv),
        "carrier_gradient": 0.5 * float(np.sum(dc**2) * dv),
        "carrier_quadratic": float(
            np.sum((0.75 - 1.50 * (1.0 - rho)) * c**2) * dv
        ),
        "carrier_quartic": 0.5 * float(np.sum(c**4) * dv),
    }
    gauge_fixing = 0.5 * float(np.sum(divergence**2) * dv)
    return components, gauge_fixing, {
        "rho": rho,
        "curvature": curvature,
        "divergence": divergence,
    }


def torch_project_scalar(field: torch.Tensor) -> torch.Tensor:
    return sum(torch.rot90(field, k, dims=(0, 1)) for k in range(4)) / 4.0


def torch_project_vector(field: torch.Tensor) -> torch.Tensor:
    rotations = torch.tensor(ROTATIONS, dtype=torch.float64)
    projected = torch.zeros_like(field)
    for k, rotation in enumerate(rotations):
        rotated = torch.rot90(field, k, dims=(0, 1))
        projected = projected + torch.einsum("ij,...ja->...ia", rotation, rotated)
    return projected / 4.0


def torch_physical_energy(
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    h: torch.Tensor,
    a: torch.Tensor,
    c: torch.Tensor,
    dx: float,
) -> torch.Tensor:
    psi = torch.complex(psi_real, psi_imag)
    sigma = torch.tensor(SIGMA, dtype=torch.complex128)
    dpsi = torch.stack(
        torch.gradient(
            psi, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-2,
    )
    gauge_psi = torch.einsum(
        "...ia,abc,...c->...ib", a.to(torch.complex128), sigma / 2.0, psi
    )
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = torch.sum(torch.abs(psi) ** 2, dim=-1)
    spin = torch.einsum("...b,abc,...c->...a", psi.conj(), sigma, psi).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * torch.sum(h * spin, dim=-1)
    )

    da = torch.gradient(
        a, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
    )
    curvature = torch.stack(
        tuple(
            torch.stack(
                tuple(
                    da[i][..., j, :]
                    - da[j][..., i, :]
                    + torch.cross(a[..., i, :], a[..., j, :], dim=-1)
                    for j in range(3)
                ),
                dim=-2,
            )
            for i in range(3)
        ),
        dim=-3,
    )
    dh = torch.stack(
        torch.gradient(
            h, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-2,
    )
    covariant_h = dh + torch.cross(a, h[..., None, :].expand_as(a), dim=-1)
    dc = torch.stack(
        torch.gradient(
            c, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-1,
    )
    dv = dx**3
    values = (
        0.5 * torch.sum(torch.abs(covariant_psi) ** 2) * dv,
        torch.sum((rho - 1.0) ** 2) * dv,
        2.0 * torch.sum(delta_phi**2) * dv,
        0.25 * torch.sum(curvature**2) * dv,
        0.5 * torch.sum(covariant_h**2) * dv,
        torch.sum((torch.sum(h**2, dim=-1) - 1.0) ** 2) * dv,
        0.5 * torch.sum(dc**2) * dv,
        torch.sum((0.75 - 1.50 * (1.0 - rho)) * c**2) * dv,
        0.5 * torch.sum(c**4) * dv,
    )
    return torch.stack(values).sum()


def physical_gradient_rms(
    psi: np.ndarray,
    h: np.ndarray,
    a: np.ndarray,
    c: np.ndarray,
    x: np.ndarray,
) -> float:
    dx = float(x[1] - x[0])
    dv = dx**3
    n = len(x)
    mask_np = (~shell_mask(n)).astype(np.float64)
    mask = torch.tensor(mask_np, dtype=torch.float64)
    psi_real = torch.tensor(psi.real, dtype=torch.float64, requires_grad=True)
    psi_imag = torch.tensor(psi.imag, dtype=torch.float64, requires_grad=True)
    h_t = torch.tensor(h, dtype=torch.float64, requires_grad=True)
    a_t = torch.tensor(a, dtype=torch.float64, requires_grad=True)
    c_t = torch.tensor(c, dtype=torch.float64, requires_grad=True)
    physical = torch_physical_energy(psi_real, psi_imag, h_t, a_t, c_t, dx)
    gradients = torch.autograd.grad(
        physical, (psi_real, psi_imag, h_t, a_t, c_t)
    )
    mask_component = mask[..., None]
    mask_connection = mask[..., None, None]
    projected = [
        torch_project_scalar(mask_component * gradients[0] / dv),
        torch_project_scalar(mask_component * gradients[1] / dv),
        torch_project_scalar(mask_component * gradients[2] / dv),
        torch_project_vector(mask_connection * gradients[3] / dv),
    ]
    carrier_gradient = gradients[4] / dv
    inner = torch.sum(c_t * carrier_gradient) * dv
    norm = torch.sum(c_t**2) * dv
    carrier_tangent = mask * (carrier_gradient - c_t * inner / norm)
    projected.append(torch_project_scalar(carrier_tangent))
    squared = torch.stack(tuple(torch.sum(value**2) for value in projected)).sum()
    active = int(np.sum(mask_np)) * 17
    return float(torch.sqrt(squared / active).detach())


def virial_diagnostics(
    psi: np.ndarray,
    h: np.ndarray,
    a: np.ndarray,
    c: np.ndarray,
    x: np.ndarray,
    components: Mapping[str, float],
) -> tuple[float, float, dict[str, float]]:
    dx = float(x[1] - x[0])
    dv = dx**3
    r_box = max(abs(float(x[0])), abs(float(x[-1])))
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    chi = (
        (1.0 - (X / r_box) ** 2) ** 2
        * (1.0 - (Y / r_box) ** 2) ** 2
        * (1.0 - (Z / r_box) ** 2) ** 2
    )
    v = chi[..., None] * np.stack((X, Y, Z), axis=-1)
    dpsi = gradient(psi, dx)
    dh = gradient(h, dx)
    da = gradient(a, dx)
    dv_field = gradient(v, dx)
    dot_psi = -sum(v[..., j, None] * dpsi[j] for j in range(3))
    dot_h = -sum(v[..., j, None] * dh[j] for j in range(3))
    advected_a = sum(v[..., j, None, None] * da[j] for j in range(3))
    one_form = np.stack(
        tuple(np.einsum("...j,...ja->...a", dv_field[i], a) for i in range(3)),
        axis=-2,
    )
    dot_a = -advected_a - one_form
    dlog_c = gradient(np.log(c + 1.0e-12), dx)
    divergence_v = sum(dv_field[i][..., i] for i in range(3))
    transport_c = sum(v[..., j] * dlog_c[j] for j in range(3))
    s_c = -transport_c - 0.5 * divergence_v
    shell = shell_mask(len(x))
    mask = (~shell).astype(np.float64)
    psi_inf = np.array((PHI**-0.5, PHI**-1.0), dtype=np.float64)
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    perturbed: dict[int, dict[str, float]] = {}
    for sign in (-1, 1):
        t = sign * 1.0e-4
        psi_t = project_scalar(psi + t * dot_psi)
        psi_t[shell] = psi_inf
        h_t = project_scalar(h + t * dot_h)
        h_t[shell] = h_inf
        a_t = project_vector(a + t * dot_a) * mask[..., None, None]
        positive = mask * c * np.exp(t * s_c)
        c_t = math.sqrt(Q_C) * positive / math.sqrt(float(np.sum(positive**2) * dv))
        perturbed[sign], _, _ = numpy_energy(psi_t, h_t, a_t, c_t, x)
    directional = {
        name: (perturbed[1][name] - perturbed[-1][name]) / 2.0e-4
        for name in COMPONENT_KEYS
    }
    numerator = abs(sum(directional.values()))
    denominator = max(1.0e-12, sum(abs(value) for value in directional.values()))
    cutoff = numerator / denominator
    formal = (
        components["psi_gradient"]
        + components["h_gradient"]
        - components["curvature"]
        + 3.0
        * (
            components["rho_potential"]
            + components["composition_potential"]
            + components["h_potential"]
        )
        - 2.0 * components["carrier_gradient"]
        - 3.0 * components["carrier_quartic"]
    )
    return cutoff, formal, directional


def take_face(array: np.ndarray, axis: int, index: int) -> np.ndarray:
    selection: list[Any] = [slice(None)] * array.ndim
    selection[axis] = index
    return array[tuple(selection)]


def outer_magnetic_number(
    h: np.ndarray, a: np.ndarray, curvature: np.ndarray, dx: float
) -> float:
    n = h.shape[0]
    weights_1d = np.ones(n, dtype=np.float64)
    weights_1d[0] = weights_1d[-1] = 0.5
    weights = weights_1d[:, None] * weights_1d[None, :]
    flux = 0.0
    for normal, tangent_j, tangent_k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
        remaining = [axis for axis in range(3) if axis != normal]
        for index, sign in ((n - 1, 1.0), (0, -1.0)):
            h_face = take_face(h, normal, index)
            h_hat = h_face / np.linalg.norm(h_face, axis=-1, keepdims=True)
            dh_face = np.gradient(
                h_hat, dx, dx, axis=(0, 1), edge_order=2
            )
            a_face = take_face(a, normal, index)
            d_j = dh_face[remaining.index(tangent_j)] + np.cross(
                a_face[..., tangent_j, :], h_hat
            )
            d_k = dh_face[remaining.index(tangent_k)] + np.cross(
                a_face[..., tangent_k, :], h_hat
            )
            f_jk = take_face(curvature[..., tangent_j, tangent_k, :], normal, index)
            residual = np.sum(h_hat * f_jk, axis=-1) - np.sum(
                h_hat * np.cross(d_j, d_k), axis=-1
            )
            flux += sign * dx**2 * float(np.sum(weights * residual))
    return flux / (4.0 * math.pi)


def boundary_residual(
    psi: np.ndarray, h: np.ndarray, a: np.ndarray, c: np.ndarray
) -> float:
    shell = shell_mask(psi.shape[0])
    psi_inf = np.array((PHI**-0.5, PHI**-1.0), dtype=np.float64)
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    return max(
        float(np.max(np.abs(psi.real[shell] - psi_inf))),
        float(np.max(np.abs(psi.imag[shell]))),
        float(np.max(np.abs(h[shell] - h_inf))),
        float(np.max(np.abs(a[shell]))),
        float(np.max(np.abs(c[shell]))),
    )


def recompute_diagnostics(fields: Mapping[str, np.ndarray]) -> dict[str, Any]:
    x = fields["x"]
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h = fields["h"]
    a = fields["a"]
    c = fields["c"]
    dx = float(x[1] - x[0])
    dv = dx**3
    components, gauge_fixing, aux = numpy_energy(psi, h, a, c, x)
    physical_energy = sum(components.values())
    charge = float(np.sum(c**2) * dv)
    depletion = np.maximum(1.0 - aux["rho"], 0.0)
    depletion_weight = float(np.sum(depletion) * dv)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    if depletion_weight < 1.0e-12:
        core_length = 0.0
    else:
        core_length = 2.0 * math.sqrt(
            float(np.sum(Z**2 * depletion) * dv) / depletion_weight
        )
    carrier_radius = math.sqrt(
        float(np.sum((X**2 + Y**2 + Z**2) * c**2) * dv) / charge
    )
    omega_c = (
        components["carrier_gradient"]
        + components["carrier_quadratic"]
        + 2.0 * components["carrier_quartic"]
    ) / charge
    physical_rms = physical_gradient_rms(psi, h, a, c, x)
    cutoff, formal, directional = virial_diagnostics(
        psi, h, a, c, x, components
    )
    independent_curvature = np.stack(
        (
            aux["curvature"][..., 0, 1, :],
            aux["curvature"][..., 0, 2, :],
            aux["curvature"][..., 1, 2, :],
        ),
        axis=-2,
    )
    shell1 = shell_mask(len(x))
    shell2 = shell_mask(len(x), width=2)
    outer_flux_rms = float(
        np.sqrt(np.mean(independent_curvature[shell1] ** 2))
    )
    gauge_divergence_rms = float(np.sqrt(np.mean(aux["divergence"] ** 2)))
    return {
        "physical_energy": physical_energy,
        "charge": charge,
        "charge_relative_error": abs(charge - Q_C) / Q_C,
        "omega_c": omega_c,
        "core_length": core_length,
        "carrier_radius": carrier_radius,
        "physical_gradient_rms": physical_rms,
        "cutoff_virial": cutoff,
        "formal_virial": formal,
        "cutoff_directional_components": directional,
        "outer_flux_rms": outer_flux_rms,
        "outer_magnetic_number": outer_magnetic_number(
            h, a, aux["curvature"], dx
        ),
        "gauge_divergence_rms": gauge_divergence_rms,
        "gauge_fixing_energy": gauge_fixing,
        "gauge_fixing_fraction": gauge_fixing / max(abs(physical_energy), 1.0e-12),
        "outer_carrier_fraction": float(
            np.sum(c[shell2] ** 2) / np.sum(c**2)
        ),
        "max_density_depletion": float(np.max(depletion)),
        "boundary_residual": boundary_residual(psi, h, a, c),
        "energy_components": components,
    }


def q1_q4(completed: bool, values: Mapping[str, Any] | None) -> dict[str, bool]:
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


def all_quality(arm: Mapping[str, Any] | None) -> bool:
    return arm is not None and all(arm["gates"].values())


def localized(arm: Mapping[str, Any]) -> bool:
    values = arm.get("diagnostics")
    return bool(
        all_quality(arm)
        and values is not None
        and values["outer_carrier_fraction"] <= 1.0e-3
        and values["carrier_radius"] < arm["R"] / 2.0
        and values["omega_c"] < 0.73
        and values["max_density_depletion"] >= 0.10
    )


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-12)


def comparison_metrics(
    primary: Mapping[str, Any], other: Mapping[str, Any]
) -> dict[str, Any]:
    p = primary["diagnostics"]
    o = other["diagnostics"]
    assert p is not None and o is not None
    localized_radius = (
        p["outer_carrier_fraction"] <= 0.01
        and o["outer_carrier_fraction"] <= 0.01
    )
    radius_difference = (
        relative_difference(p["carrier_radius"], o["carrier_radius"])
        if localized_radius
        else relative_difference(
            p["carrier_radius"] / primary["R"],
            o["carrier_radius"] / other["R"],
        )
    )
    metrics = {
        "energy_relative_difference": relative_difference(
            p["physical_energy"], o["physical_energy"]
        ),
        "core_length_absolute_difference": abs(
            p["core_length"] - o["core_length"]
        ),
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


def validate_numeric_history_row(
    row: Any,
    expected_keys: set[str],
    ordinal_key: str,
    expected_ordinal: int,
    path: str,
    out: list[dict[str, Any]],
) -> None:
    if not isinstance(row, dict):
        mismatch(out, path, "object", row, "schema")
        return
    if set(row) != expected_keys:
        mismatch(out, f"{path}.keys", sorted(expected_keys), sorted(row), "exact")
    ordinal = row.get(ordinal_key)
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal != expected_ordinal:
        mismatch(out, f"{path}.{ordinal_key}", expected_ordinal, ordinal, "exact")
    for name in expected_keys - {ordinal_key}:
        value = row.get(name)
        if not finite_number(value):
            mismatch(out, f"{path}.{name}", "finite number", value, "schema")


def validate_optimizer(
    optimizer: Any,
    completed: bool,
    path: str,
    out: list[dict[str, Any]],
) -> None:
    if not isinstance(optimizer, dict):
        mismatch(out, path, "optimizer object", optimizer, "schema")
        return
    if set(optimizer) != OPTIMIZER_KEYS:
        mismatch(out, f"{path}.keys", sorted(OPTIMIZER_KEYS), sorted(optimizer), "exact")
    adam = optimizer.get("adam_history")
    lbfgs = optimizer.get("lbfgs_history")
    if not isinstance(adam, list):
        mismatch(out, f"{path}.adam_history", "list", adam, "schema")
        adam = []
    if not isinstance(lbfgs, list):
        mismatch(out, f"{path}.lbfgs_history", "list", lbfgs, "schema")
        lbfgs = []
    expected_steps = list(range(0, 800, 20)) + [799]
    for index, row in enumerate(adam):
        expected_step = expected_steps[index] if index < len(expected_steps) else -1
        validate_numeric_history_row(
            row,
            ADAM_ROW_KEYS,
            "step",
            expected_step,
            f"{path}.adam_history[{index}]",
            out,
        )
    for index, row in enumerate(lbfgs):
        validate_numeric_history_row(
            row,
            LBFGS_ROW_KEYS,
            "closure",
            index + 1,
            f"{path}.lbfgs_history[{index}]",
            out,
        )
    counts: dict[str, int] = {}
    for name in (
        "lbfgs_iterations",
        "lbfgs_closure_calls",
        "lbfgs_function_evaluations",
    ):
        value = optimizer.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            mismatch(out, f"{path}.{name}", "nonnegative integer", value, "schema")
        else:
            counts[name] = value
    wall_seconds = optimizer.get("wall_seconds")
    if not finite_number(wall_seconds) or float(wall_seconds) < 0.0:
        mismatch(out, f"{path}.wall_seconds", "finite nonnegative number", wall_seconds, "schema")
    if completed:
        if len(adam) != len(expected_steps):
            mismatch(out, f"{path}.adam_history.length", len(expected_steps), len(adam), "exact")
        iterations = counts.get("lbfgs_iterations")
        closures = counts.get("lbfgs_closure_calls")
        evaluations = counts.get("lbfgs_function_evaluations")
        if iterations is not None and iterations > 120:
            mismatch(out, f"{path}.lbfgs_iterations", "<= 120", iterations, "bound")
        if closures is not None and closures > 150:
            mismatch(out, f"{path}.lbfgs_closure_calls", "<= 150", closures, "bound")
        if evaluations is not None and evaluations > 150:
            mismatch(out, f"{path}.lbfgs_function_evaluations", "<= 150", evaluations, "bound")
        if closures is not None and len(lbfgs) != closures:
            mismatch(out, f"{path}.lbfgs_history.length", closures, len(lbfgs), "exact")
        if closures is not None and evaluations is not None and closures != evaluations:
            mismatch(out, f"{path}.closure_evaluation_relation", closures, evaluations, "exact")


def validate_preflight(
    preflight: Any,
    hashes: Mapping[str, Any],
    out: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    if not isinstance(preflight, dict):
        mismatch(out, "preflight", "object", preflight, "schema")
        return False, {}
    expected_keys = {"G1", "G2", "G3", "G4", "pass"}
    if set(preflight) != expected_keys:
        mismatch(out, "preflight.keys", sorted(expected_keys), sorted(preflight), "exact")
    recomputed: dict[str, Any] = {}
    g1 = preflight.get("G1")
    if isinstance(g1, dict) and finite_number(g1.get("vacuum_energy_abs")):
        g1_pass = float(g1["vacuum_energy_abs"]) < 1.0e-12
        recomputed["G1"] = {"vacuum_energy_abs": float(g1["vacuum_energy_abs"]), "pass": g1_pass}
        compare_tree(out, "preflight.G1.pass", g1.get("pass"), g1_pass)
    else:
        mismatch(out, "preflight.G1", "finite vacuum receipt", g1, "schema")
        recomputed["G1"] = {"pass": False}

    expected_blocks = (
        "psi_real[0]",
        "psi_real[1]",
        "psi_imag[0]",
        "psi_imag[1]",
        "h[0]",
        "h[1]",
        "h[2]",
        "a[0,0]",
        "a[1,1]",
        "a[2,2]",
        "a[0,2]",
        "w",
    )
    g2 = preflight.get("G2")
    recomputed_checks: list[dict[str, Any]] = []
    if not isinstance(g2, dict) or not isinstance(g2.get("checks"), list):
        mismatch(out, "preflight.G2", "checks list", g2, "schema")
    else:
        checks = g2["checks"]
        if len(checks) != len(expected_blocks):
            mismatch(out, "preflight.G2.checks.length", len(expected_blocks), len(checks), "exact")
        for index, block in enumerate(expected_blocks):
            path = f"preflight.G2.checks[{index}]"
            if index >= len(checks) or not isinstance(checks[index], dict):
                mismatch(out, path, "check object", None if index >= len(checks) else checks[index], "schema")
                recomputed_checks.append({"r": index, "block": block, "pass": False})
                continue
            row = checks[index]
            compare_tree(out, f"{path}.r", row.get("r"), index)
            compare_tree(out, f"{path}.block", row.get("block"), block)
            automatic = row.get("autograd")
            finite_difference = row.get("finite_difference")
            if finite_number(automatic) and finite_number(finite_difference):
                relative_error = abs(float(automatic) - float(finite_difference)) / max(
                    1.0e-8, abs(float(automatic)), abs(float(finite_difference))
                )
                row_pass = relative_error <= 5.0e-5
                compare_float(out, f"{path}.relative_error", row.get("relative_error"), relative_error)
                compare_tree(out, f"{path}.pass", row.get("pass"), row_pass)
                recomputed_checks.append(
                    {
                        "r": index,
                        "block": block,
                        "autograd": float(automatic),
                        "finite_difference": float(finite_difference),
                        "relative_error": relative_error,
                        "pass": row_pass,
                    }
                )
            else:
                mismatch(out, path, "finite derivative values", row, "schema")
                recomputed_checks.append({"r": index, "block": block, "pass": False})
    g2_pass = len(recomputed_checks) == 12 and all(
        bool(row.get("pass")) for row in recomputed_checks
    )
    recomputed["G2"] = {"checks": recomputed_checks, "pass": g2_pass}
    if isinstance(g2, dict):
        compare_tree(out, "preflight.G2.pass", g2.get("pass"), g2_pass)

    g3 = preflight.get("G3")
    if isinstance(g3, dict) and finite_number(g3.get("charge_relative_error")):
        g3_value = float(g3["charge_relative_error"])
        g3_pass = g3_value < 5.0e-12
        recomputed["G3"] = {"charge_relative_error": g3_value, "pass": g3_pass}
        compare_tree(out, "preflight.G3.pass", g3.get("pass"), g3_pass)
    else:
        mismatch(out, "preflight.G3", "finite charge receipt", g3, "schema")
        recomputed["G3"] = {"pass": False}

    required_keys = list(SOURCE_PATHS)
    g4_pass = all(
        isinstance(hashes.get(key), str) and len(hashes[key]) == 64
        for key in required_keys
    )
    recomputed["G4"] = {"required_keys": required_keys, "pass": g4_pass}
    g4 = preflight.get("G4")
    if isinstance(g4, dict):
        compare_tree(out, "preflight.G4.required_keys", g4.get("required_keys"), required_keys)
        compare_tree(out, "preflight.G4.pass", g4.get("pass"), g4_pass)
    else:
        mismatch(out, "preflight.G4", "object", g4, "schema")
    overall = all(bool(recomputed[name].get("pass")) for name in ("G1", "G2", "G3", "G4"))
    recomputed["pass"] = overall
    compare_tree(out, "preflight.pass", preflight.get("pass"), overall)
    return overall, recomputed


def load_npz(
    path: Path,
    family: str,
    out: list[dict[str, Any]],
) -> dict[str, np.ndarray] | None:
    try:
        with np.load(path, allow_pickle=False) as archive:
            files = set(archive.files)
            if files != set(FIELD_KEYS):
                mismatch(out, f"{path}.keys", sorted(FIELD_KEYS), sorted(files), "exact")
            if not set(FIELD_KEYS).issubset(files):
                return None
            fields = {name: archive[name] for name in FIELD_KEYS}
    except Exception as exc:
        mismatch(out, str(path), "readable NPZ", repr(exc), "artifact_read")
        return None
    R, n = GRIDS[family]
    expected_shapes = {
        "x": (n,),
        "psi_real": (n, n, n, 2),
        "psi_imag": (n, n, n, 2),
        "h": (n, n, n, 3),
        "a": (n, n, n, 3, 3),
        "c": (n, n, n),
    }
    valid = True
    for name, expected_shape in expected_shapes.items():
        array = fields[name]
        if array.dtype != np.float64:
            mismatch(out, f"{path}:{name}.dtype", "float64", str(array.dtype), "schema")
            valid = False
        if array.shape != expected_shape:
            mismatch(out, f"{path}:{name}.shape", expected_shape, array.shape, "schema")
            valid = False
        if not array.flags.c_contiguous:
            mismatch(out, f"{path}:{name}.order", "C-contiguous", "non-C", "schema")
            valid = False
        if not np.isfinite(array).all():
            mismatch(out, f"{path}:{name}", "all finite", "nonfinite values", "nonfinite")
            valid = False
    if not valid:
        return None
    expected_x = np.linspace(-R, R, n, dtype=np.float64)
    if not np.allclose(fields["x"], expected_x, rtol=0.0, atol=1.0e-14):
        mismatch(out, f"{path}:x", expected_x.tolist(), fields["x"].tolist(), "grid")
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    c4_residual = max(
        float(np.max(np.abs(project_scalar(psi) - psi))),
        float(np.max(np.abs(project_scalar(fields["h"]) - fields["h"]))),
        float(np.max(np.abs(project_vector(fields["a"]) - fields["a"]))),
        float(np.max(np.abs(project_scalar(fields["c"]) - fields["c"]))),
    )
    if c4_residual > 1.0e-10:
        mismatch(out, f"{path}:C4_residual", "<= 1e-10", c4_residual, "symmetry")
    interior = ~shell_mask(n)
    if not np.all(fields["c"][interior] > 0.0):
        mismatch(out, f"{path}:c.interior", "strictly positive", float(np.min(fields["c"][interior])), "constraint")
    return fields


def verify_arm(
    key: str,
    row: Any,
    receipt_dir: Path,
    artifact_hashes: Mapping[str, Any],
    out: list[dict[str, Any]],
) -> dict[str, Any] | None:
    path = f"arms.{key}"
    if not isinstance(row, dict):
        mismatch(out, path, "object", row, "schema")
        return None
    if set(row) != ARM_KEYS:
        mismatch(out, f"{path}.keys", sorted(ARM_KEYS), sorted(row), "exact")
    if ":" not in key:
        mismatch(out, path, "family:basin key", key, "schema")
        return None
    family, basin = key.split(":", 1)
    if family not in GRIDS or basin not in BASINS:
        mismatch(out, path, "known family and basin", key, "schema")
        return None
    compare_tree(out, f"{path}.family", row.get("family"), family)
    compare_tree(out, f"{path}.basin", row.get("basin"), basin)
    R, n = GRIDS[family]
    compare_float(out, f"{path}.R", row.get("R"), R)
    compare_tree(out, f"{path}.N", row.get("N"), n)
    compare_float(out, f"{path}.dx", row.get("dx"), 2.0 * R / (n - 1))
    completed = row.get("completed") is True
    if not isinstance(row.get("completed"), bool):
        mismatch(out, f"{path}.completed", "boolean", row.get("completed"), "schema")
    validate_optimizer(row.get("optimizer"), completed, f"{path}.optimizer", out)
    if not completed:
        compare_tree(out, f"{path}.artifact", row.get("artifact"), None)
        compare_tree(out, f"{path}.artifact_sha256", row.get("artifact_sha256"), None)
        compare_tree(out, f"{path}.diagnostics", row.get("diagnostics"), None)
        expected_gates = q1_q4(False, None)
        compare_tree(out, f"{path}.gates", row.get("gates"), expected_gates)
        if not isinstance(row.get("error"), str) or not row["error"]:
            mismatch(out, f"{path}.error", "nonempty string", row.get("error"), "schema")
        return {
            "family": family,
            "basin": basin,
            "R": R,
            "N": n,
            "completed": False,
            "diagnostics": None,
            "gates": expected_gates,
        }

    compare_tree(out, f"{path}.error", row.get("error"), None)
    artifact_name = f"fields_{family}_{basin}.npz"
    compare_tree(out, f"{path}.artifact", row.get("artifact"), artifact_name)
    artifact_path = receipt_dir / artifact_name
    if not artifact_path.is_file():
        mismatch(out, f"{path}.artifact", "existing file", str(artifact_path), "missing")
        return None
    artifact_digest = sha256(artifact_path)
    compare_tree(out, f"{path}.artifact_sha256", row.get("artifact_sha256"), artifact_digest)
    compare_tree(out, f"hashes.artifacts.{artifact_name}", artifact_hashes.get(artifact_name), artifact_digest)
    fields = load_npz(artifact_path, family, out)
    if fields is None:
        return None
    try:
        diagnostics = recompute_diagnostics(fields)
    except Exception as exc:
        mismatch(out, f"{path}.diagnostics", "independently recomputable", repr(exc), "recompute")
        return None
    reported = row.get("diagnostics")
    if not isinstance(reported, dict):
        mismatch(out, f"{path}.diagnostics", "object", reported, "schema")
    else:
        expected_diagnostic_keys = set(diagnostics) | {
            "objective_raw_gradient_rms",
            "objective_raw_gradient_max",
        }
        if set(reported) != expected_diagnostic_keys:
            mismatch(
                out,
                f"{path}.diagnostics.keys",
                sorted(expected_diagnostic_keys),
                sorted(reported),
                "exact",
            )
        for name, expected in diagnostics.items():
            if name in reported:
                compare_tree(out, f"{path}.diagnostics.{name}", reported[name], expected)
        for name in ("objective_raw_gradient_rms", "objective_raw_gradient_max"):
            value = reported.get(name)
            if not finite_number(value) or float(value) < 0.0:
                mismatch(out, f"{path}.diagnostics.{name}", "finite nonnegative receipt value", value, "schema")
    gates = q1_q4(True, diagnostics)
    compare_tree(out, f"{path}.gates", row.get("gates"), gates)
    return {
        "family": family,
        "basin": basin,
        "R": R,
        "N": n,
        "completed": True,
        "diagnostics": diagnostics,
        "gates": gates,
    }


def evaluate_campaign(
    arms: Mapping[str, Mapping[str, Any]], selected: str | None, preflight_pass: bool
) -> tuple[dict[str, Any], dict[str, float], str]:
    structural_domain: dict[str, Any] = {}
    for basin in STRUCTURAL:
        primary = arms.get(f"P:{basin}")
        domain = arms.get(f"D:{basin}")
        if all_quality(primary) and all_quality(domain):
            assert primary is not None and domain is not None
            structural_domain[basin] = comparison_metrics(primary, domain)
        else:
            structural_domain[basin] = {"pass": False, "reason": "Q1-Q4 failure"}

    p_control = arms.get("P:delocalized")
    d_control = arms.get("D:delocalized")
    if not (all_quality(p_control) and all_quality(d_control)):
        control: dict[str, Any] = {
            "mode": "invalid",
            "pass": False,
            "reason": "Q1-Q4 failure",
        }
    else:
        assert p_control is not None and d_control is not None
        localized_p = localized(p_control)
        localized_d = localized(d_control)
        if localized_p and localized_d:
            control = {"mode": "localized", **comparison_metrics(p_control, d_control)}
        elif not localized_p and not localized_d:
            p_values = p_control["diagnostics"]
            d_values = d_control["diagnostics"]
            assert p_values is not None and d_values is not None
            radius_difference = relative_difference(
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
                "pass": radius_difference <= 0.10
                and quartic_ok
                and energy_target <= 0.25,
            }
        else:
            control = {
                "mode": "localization_mismatch",
                "localized_P": localized_p,
                "localized_D": localized_d,
                "pass": False,
            }

    if selected is None or f"H:{selected}" not in arms:
        resolution: dict[str, Any] = {"pass": False, "reason": "no H arm"}
    else:
        primary = arms.get(f"P:{selected}")
        high = arms.get(f"H:{selected}")
        if all_quality(primary) and all_quality(high):
            assert primary is not None and high is not None
            resolution = comparison_metrics(primary, high)
        else:
            resolution = {"pass": False, "reason": "Q1-Q4 failure"}

    quality_all = (
        all(bool(values.get("pass")) for values in structural_domain.values())
        and bool(control.get("pass"))
        and bool(resolution.get("pass"))
    )
    gates = {
        "structural_domain": structural_domain,
        "delocalized_control": control,
        "resolution": resolution,
        "quality_all": quality_all,
    }

    uncertainties: dict[str, float] = {}
    for basin in BASINS:
        p_values = arms.get(f"P:{basin}", {}).get("diagnostics")
        d_values = arms.get(f"D:{basin}", {}).get("diagnostics")
        uncertainties[basin] = (
            math.inf
            if p_values is None or d_values is None
            else abs(p_values["physical_energy"] - d_values["physical_energy"])
        )
    if selected is not None:
        p_values = arms.get(f"P:{selected}", {}).get("diagnostics")
        h_values = arms.get(f"H:{selected}", {}).get("diagnostics")
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

    if not preflight_pass:
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
                if all(
                    margins[f"{basin}<{other}"] > 0.0
                    for other in BASINS
                    if other != basin
                )
            ),
            None,
        )
        if winner is not None:
            verdict = "EMERGES—LOCALIZED FIXED-CHARGE STATIONARY BASIN"
        elif not localized_structural or all(
            margins[f"delocalized<{basin}"] > 0.0
            for basin in localized_structural
        ):
            verdict = "DOES NOT EMERGE—LOCALIZED FIXED-CHARGE STATIONARY BASIN"
        else:
            verdict = "INCONCLUSIVE—BASIN ORDERING"
    return gates, margins, verdict


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", nargs="?", default=str(DEFAULT_RECEIPT))
    receipt_path = Path(parser.parse_args(argv).receipt).resolve()
    verification_path = receipt_path.parent / "verification.json"
    mismatches: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema_version": "particle_stationary_bvp_verification.v1",
        "receipt": str(receipt_path),
        "pass": False,
        "mismatches": mismatches,
    }
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception as exc:
        mismatch(mismatches, "results.json", "readable JSON object", repr(exc), "receipt_read")
        write_report(verification_path, report)
        print("particle stationary BVP: FAIL (receipt unreadable)")
        return 1
    if not isinstance(receipt, dict):
        mismatch(mismatches, "results", "object", type(receipt).__name__, "schema")
        write_report(verification_path, report)
        print("particle stationary BVP: FAIL (receipt schema)")
        return 1
    if set(receipt) != TOP_LEVEL_KEYS:
        mismatch(mismatches, "results.keys", sorted(TOP_LEVEL_KEYS), sorted(receipt), "exact")
    compare_tree(mismatches, "schema_version", receipt.get("schema_version"), 1)
    compare_tree(mismatches, "coefficients", receipt.get("coefficients"), COEFFICIENTS)
    environment = receipt.get("environment")
    if not isinstance(environment, dict):
        mismatch(mismatches, "environment", "object", environment, "schema")
    else:
        required_environment = {
            "python",
            "platform",
            "torch",
            "hip",
            "device",
            "device_name",
            "cuda_visible_devices",
            "dtype",
            "deterministic_algorithms",
        }
        if set(environment) != required_environment:
            mismatch(mismatches, "environment.keys", sorted(required_environment), sorted(environment), "exact")
        compare_tree(mismatches, "environment.cuda_visible_devices", environment.get("cuda_visible_devices"), "0")
        compare_tree(mismatches, "environment.device_name", environment.get("device_name"), "AMD Radeon RX 7900 XTX")
        compare_tree(mismatches, "environment.dtype", environment.get("dtype"), "float64")
        compare_tree(mismatches, "environment.deterministic_algorithms", environment.get("deterministic_algorithms"), True)
        for name in ("python", "platform", "torch", "device", "device_name"):
            if not isinstance(environment.get(name), str) or not environment[name]:
                mismatch(mismatches, f"environment.{name}", "nonempty string", environment.get(name), "schema")
        if environment.get("hip") is not None and not isinstance(environment.get("hip"), str):
            mismatch(mismatches, "environment.hip", "string or null", environment.get("hip"), "schema")

    hashes = receipt.get("hashes")
    if not isinstance(hashes, dict):
        mismatch(mismatches, "hashes", "object", hashes, "schema")
        hashes = {}
    if set(hashes) != set(HASH_KEYS):
        mismatch(mismatches, "hashes.keys", sorted(HASH_KEYS), sorted(hashes), "exact")
    actual_hashes: dict[str, Any] = {}
    for name, path in SOURCE_PATHS.items():
        actual = sha256(path) if path.is_file() else None
        actual_hashes[name] = actual
        compare_tree(mismatches, f"hashes.{name}", hashes.get(name), actual)
    artifact_hashes = hashes.get("artifacts")
    if not isinstance(artifact_hashes, dict):
        mismatch(mismatches, "hashes.artifacts", "object", artifact_hashes, "schema")
        artifact_hashes = {}
    actual_hashes["artifacts"] = {
        str(name): sha256(receipt_path.parent / str(name))
        if (receipt_path.parent / str(name)).is_file()
        else None
        for name in artifact_hashes
    }
    for name, actual in actual_hashes["artifacts"].items():
        compare_tree(mismatches, f"hashes.artifacts.{name}", artifact_hashes.get(name), actual)
    report["hashes"] = actual_hashes

    preflight_pass, preflight = validate_preflight(
        receipt.get("preflight"), hashes, mismatches
    )
    report["preflight"] = preflight
    expected_inventory = {
        "P": list(BASINS),
        "D": list(BASINS),
        "H": "lowest-energy structural P basin passing Q1-Q4",
    }
    compare_tree(mismatches, "arm_inventory", receipt.get("arm_inventory"), expected_inventory)

    rows = receipt.get("arms")
    if not isinstance(rows, dict):
        mismatch(mismatches, "arms", "object", rows, "schema")
        rows = {}
    recomputed_arms: dict[str, dict[str, Any]] = {}
    for key, row in rows.items():
        arm = verify_arm(str(key), row, receipt_path.parent, artifact_hashes, mismatches)
        if arm is not None:
            recomputed_arms[str(key)] = arm

    h_eligible = [
        basin
        for basin in STRUCTURAL
        if all_quality(recomputed_arms.get(f"P:{basin}"))
    ]
    if h_eligible:
        minimum_energy = min(
            recomputed_arms[f"P:{basin}"]["diagnostics"]["physical_energy"]
            for basin in h_eligible
        )
        selected = next(
            basin
            for basin in STRUCTURAL
            if basin in h_eligible
            and recomputed_arms[f"P:{basin}"]["diagnostics"]["physical_energy"]
            <= minimum_energy + 1.0e-10
        )
    else:
        selected = None
    h_selection = {"basin": selected, "eligible": h_eligible}
    compare_tree(mismatches, "h_selection", receipt.get("h_selection"), h_selection)

    if preflight_pass:
        expected_order = [f"P:{basin}" for basin in BASINS]
        if selected is not None:
            expected_order.append(f"H:{selected}")
        expected_order.extend(f"D:{basin}" for basin in BASINS)
    else:
        expected_order = []
    compare_tree(mismatches, "run_order", receipt.get("run_order"), expected_order)
    if set(rows) != set(expected_order):
        mismatch(mismatches, "arms.keys", sorted(expected_order), sorted(rows), "exact")
    expected_artifacts = {
        row["artifact"]
        for row in rows.values()
        if isinstance(row, dict)
        and row.get("completed") is True
        and isinstance(row.get("artifact"), str)
    }
    if set(artifact_hashes) != expected_artifacts:
        mismatch(mismatches, "hashes.artifacts.keys", sorted(expected_artifacts), sorted(artifact_hashes), "exact")

    if preflight_pass:
        gates, margins, verdict = evaluate_campaign(
            recomputed_arms, selected, preflight_pass
        )
    else:
        gates = {}
        margins = {}
        verdict = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    compare_tree(mismatches, "gates", receipt.get("gates"), gates)
    compare_tree(
        mismatches,
        "pairwise_ordering_margins",
        receipt.get("pairwise_ordering_margins"),
        margins,
    )
    compare_tree(mismatches, "verdict", receipt.get("verdict"), verdict)
    report.update(
        {
            "arms": recomputed_arms,
            "h_selection": h_selection,
            "gates": gates,
            "pairwise_ordering_margins": margins,
            "verdict": verdict,
            "receipt_verdict": receipt.get("verdict"),
        }
    )
    report["pass"] = not mismatches
    write_report(verification_path, report)
    print(
        f"particle stationary BVP: {'PASS' if report['pass'] else 'FAIL'} "
        f"({verdict}; {len(mismatches)} mismatch(es))"
    )
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
