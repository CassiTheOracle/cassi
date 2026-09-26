#!/usr/bin/env python3
"""Finite-cylinder radial vortex-core minimization and transverse carrier spectrum.

Run from the repository root, for example::

    python computations/matter_formation_vortex_core.py --output runs/20260908_matter_formation_vortex_core/primary

The program solves the declared five-field radial variational problem on the
fixed continuation schedule for both caps.  It reports a conditional
stationary-core and transverse-spectrum calculation only; it does not classify
full matter formation, carrier production, or a finite loop.
"""
from __future__ import annotations

import argparse
import json
import math
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy.optimize as optimize
import scipy.sparse as sparse
import scipy.sparse.linalg as spla
import scipy.special as special
import torch


SCHEMA = "matter-formation-vortex-core-v1"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
RHO0 = 1.2
A = 0.83
D = 1.25
V = 0.9
G = 0.71
LAMBDA_RHO = 1.0
LAMBDA_PHI = 1.0
LAMBDA_H = 1.0
K_CX = 1.0
ETA_C = 1.0
M_WINDING = 1
C0 = PHI ** -3
J0 = 4.0 * A * RHO0 * D * V * V * (1.0 - C0 * C0) / (A * RHO0 + 4.0 * D * V * V)
A_RHO = (M_WINDING * M_WINDING * A * (4.0 * D * V * V) ** 2 * (1.0 - C0 * C0) / (4.0 * LAMBDA_RHO * (A * RHO0 + 4.0 * D * V * V) ** 2))


def _torch_single_thread() -> None:
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)


def finite_float(value: Any) -> bool:
    try:
        return bool(np.isfinite(float(value)))
    except (TypeError, ValueError):
        return False


def strict_value(value: Any) -> Any:
    """Convert NumPy scalars recursively, replacing nonfinite values by null."""
    if isinstance(value, dict):
        return {str(k): strict_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [strict_value(v) for v in value]
    if isinstance(value, np.ndarray):
        return strict_value(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    return value


def quadrature_grid(R: float, N: int) -> dict[str, np.ndarray]:
    """Uniform nodal grid with fixed two-point Gauss integration per element."""
    r = np.linspace(0.0, R, N + 1, dtype=np.float64)
    dr = R / N
    xi = np.array([-1.0 / math.sqrt(3.0), 1.0 / math.sqrt(3.0)], dtype=np.float64)
    t = (xi + 1.0) / 2.0
    qr = r[:-1, None] + dr * t[None, :]
    qw = 2.0 * math.pi * qr * (dr / 2.0)
    return {"r": r, "dr": np.array(dr), "t": t, "quadrature_r": qr, "quadrature_weight": qw}


def basis_values(r: np.ndarray, winding: bool) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return w_p,w_q,w'_p,w'_q at radii, with exact regular factors."""
    w1 = r / np.sqrt(1.0 + r * r)
    dw1 = (1.0 + r * r) ** (-1.5)
    one = np.ones_like(r)
    if winding:
        return w1, one, dw1, np.zeros_like(r)
    return one, w1, np.zeros_like(r), dw1


def gauge_basis(r: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Return (w1,w3,w1',w3') for smooth gauge coefficients."""
    w1 = r / np.sqrt(1.0 + r * r)
    dw1 = (1.0 + r * r) ** (-1.5)
    w3 = r * r / (1.0 + r * r)
    dw3 = 2.0 * r / (1.0 + r * r) ** 2
    return w1, w3, dw1, dw3


def vacuum_fields(epsilon: int) -> np.ndarray:
    p_inf = math.sqrt(RHO0 * (1.0 + C0) / 2.0)
    q_inf = math.sqrt(RHO0 * (1.0 - C0) / 2.0)
    b1_inf = A * RHO0 * math.sqrt(1.0 - C0 * C0) / (A * RHO0 + 4.0 * D * V * V)
    b3_inf = epsilon + C0
    return np.array([p_inf, q_inf, V, b1_inf, b3_inf], dtype=np.float64)


def radial_density(
    p: Any,
    q: Any,
    u: Any,
    b1: Any,
    b3: Any,
    dp: Any,
    dq: Any,
    du: Any,
    db1: Any,
    db3: Any,
    r: Any,
    h: Any,
    epsilon: int,
    xp: Any,
) -> tuple[Any, dict[str, Any], Any, Any, Any]:
    """Shared NumPy/Torch radial density and its algebraic h data.

    The returned density is the full E in the working notebook.  Component
    densities are returned without the cylindrical Jacobian; the caller
    integrates them with the same two-point Gauss weights.
    """
    n_y = (1 + epsilon) / 2.0
    n_i = (1 - epsilon) / 2.0
    rho = p * p + q * q
    delta = ((1.0 - PHI) * rho + (1.0 + PHI) * (u / V) * (p * p - q * q)) / 2.0
    h_quad = A * rho / 4.0 + D * u * u + D / (G * G * r * r) * ((b3 - epsilon) ** 2 + b1 * b1)
    l_quad = A / 2.0 * (p * dq - q * dp) + D / (G * G * r * r) * ((b3 - epsilon) * db1 - b1 * db3)
    if not bool(xp.all(xp.isfinite(h_quad) & (h_quad > 0.0))):
        raise ValueError("algebraic h coefficient H must be finite and positive")
    e_h = -l_quad / h_quad if h is None else h
    if xp is torch:
        e_h = e_h.detach()
    hr_y = dp - e_h * q / 2.0
    hr_i = dq + e_h * p / 2.0
    ec_psi_r = A / 2.0 * (hr_y * hr_y + hr_i * hr_i)
    ec_phi_r = D / 2.0 * (du * du + e_h * e_h * u * u)
    ec_psi_ang = A / (8.0 * r * r) * (
        ((2.0 * n_y - b3) * p - b1 * q) ** 2
        + ((2.0 * n_i + b3) * q - b1 * p) ** 2
    )
    ec_phi_ang = D * b1 * b1 * u * u / (2.0 * r * r)
    ec_gauge = D / (2.0 * G * G * r * r) * (
        (db1 + e_h * (b3 - epsilon)) ** 2 + (db3 - e_h * b1) ** 2
    )
    ec_density = LAMBDA_RHO * (rho - RHO0) ** 2 / 4.0
    ec_composition = LAMBDA_PHI * delta * delta / 2.0
    ec_higgs = LAMBDA_H * (u * u - V * V) ** 2 / 4.0
    components = {
        "psi_radial": ec_psi_r,
        "phi_radial": ec_phi_r,
        "psi_angular": ec_psi_ang,
        "phi_angular": ec_phi_ang,
        "gauge": ec_gauge,
        "density_potential": ec_density,
        "composition_potential": ec_composition,
        "higgs_potential": ec_higgs,
    }
    total = sum(components.values())
    return total, components, e_h, h_quad, l_quad


def h_stationarity_data(
    p: np.ndarray,
    q: np.ndarray,
    u: np.ndarray,
    b1: np.ndarray,
    b3: np.ndarray,
    dp: np.ndarray,
    dq: np.ndarray,
    du: np.ndarray,
    db1: np.ndarray,
    db3: np.ndarray,
    r: np.ndarray,
    epsilon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Evaluate h, H, and dE/dh = H*h+L for finite quadrature points."""
    rho = p * p + q * q
    H = A * rho / 4.0 + D * u * u + D / (G * G * r * r) * ((b3 - epsilon) ** 2 + b1 * b1)
    L = A / 2.0 * (p * dq - q * dp) + D / (G * G * r * r) * ((b3 - epsilon) * db1 - b1 * db3)
    h = -L / H
    return h, H, H * h + L


class RadialModel:
    def __init__(self, R: float, N: int, epsilon: int) -> None:
        grid = quadrature_grid(R, N)
        self.R = R
        self.N = N
        self.epsilon = epsilon
        self.r = grid["r"]
        self.dr = float(grid["dr"])
        self.t = grid["t"]
        self.qr = grid["quadrature_r"]
        self.qweight = grid["quadrature_weight"]
        winding = epsilon == 1
        wp, wq, dwp, dwq = basis_values(self.qr, winding)
        w1, w3, dw1, dw3 = gauge_basis(self.qr)
        self.basis = np.stack((wp, wq, np.ones_like(wp), w1, w3), axis=-1)
        self.dbasis = np.stack((dwp, dwq, np.zeros_like(wp), dw1, dw3), axis=-1)
        self.nodal_basis = np.stack((*basis_values(self.r, winding)[:2], np.ones_like(self.r), *gauge_basis(self.r)[:2]), axis=-1)
        self.outer = vacuum_fields(epsilon) / self.nodal_basis[-1]
        self.mass = self._lumped_masses()

    def _lumped_masses(self) -> np.ndarray:
        masses = np.zeros(self.N + 1, dtype=np.float64)
        for e in range(self.N):
            masses[e] += float(np.sum(self.qweight[e] * (1.0 - self.t)))
            masses[e + 1] += float(np.sum(self.qweight[e] * self.t))
        return masses

    def nodal_physical(self, y: np.ndarray) -> np.ndarray:
        return y * self.nodal_basis

    def initial_y(self) -> np.ndarray:
        r = self.r
        bulk = vacuum_fields(self.epsilon)
        winding_bulk = bulk[0] if self.epsilon == 1 else bulk[1]
        winding_phys = winding_bulk * np.tanh(r) / math.tanh(self.R)
        nonwinding_phys = np.sqrt(RHO0 - winding_phys * winding_phys)
        physical = np.empty((self.N + 1, 5), dtype=np.float64)
        if self.epsilon == 1:
            physical[:, 0] = winding_phys
            physical[:, 1] = nonwinding_phys
        else:
            physical[:, 0] = nonwinding_phys
            physical[:, 1] = winding_phys
        physical[:, 2] = V
        physical[:, 3] = bulk[3] * self.nodal_basis[:, 3] / self.nodal_basis[-1, 3]
        physical[:, 4] = bulk[4] * self.nodal_basis[:, 4] / self.nodal_basis[-1, 4]
        y = np.empty_like(physical)
        y[1:] = physical[1:] / self.nodal_basis[1:]
        # Analytic finite limits at the origin.
        y[0, 0 if self.epsilon == 1 else 1] = winding_bulk / math.tanh(self.R)
        y[0, 1 if self.epsilon == 1 else 0] = math.sqrt(RHO0)
        y[0, 2] = V
        y[0, 3] = bulk[3] / self.nodal_basis[-1, 3]
        y[0, 4] = bulk[4] / self.nodal_basis[-1, 4]
        return y

    def continuation_y(self, previous: dict[str, Any]) -> np.ndarray:
        physical_old = np.asarray(previous["physical_fields"], dtype=np.float64)
        r_old = np.asarray(previous["r"], dtype=np.float64)
        physical = np.empty((self.N + 1, 5), dtype=np.float64)
        bulk = vacuum_fields(self.epsilon)
        for j in range(5):
            physical[:, j] = np.interp(self.r, r_old, physical_old[:, j])
            physical[self.r > r_old[-1], j] = bulk[j]
        y = np.empty_like(physical)
        y[1:] = physical[1:] / self.nodal_basis[1:]
        y[0] = np.asarray(previous["y"], dtype=np.float64)[0]
        y[-1] = self.outer
        return y

    def _numpy_fields(self, y: np.ndarray) -> tuple[np.ndarray, ...]:
        yq = (1.0 - self.t[None, :, None]) * y[:-1, None, :] + self.t[None, :, None] * y[1:, None, :]
        dy = (y[1:] - y[:-1]) / self.dr
        fq = yq * self.basis
        dfq = dy[:, None, :] * self.basis + yq * self.dbasis
        return tuple(fq[..., j] for j in range(5)) + tuple(dfq[..., j] for j in range(5))

    def evaluate_numpy(self, y: np.ndarray) -> dict[str, Any]:
        p, q, u, b1, b3, dp, dq, du, db1, db3 = self._numpy_fields(y)
        total, components, h, H, L = radial_density(p, q, u, b1, b3, dp, dq, du, db1, db3, self.qr, None, self.epsilon, np)
        # radial_density computes the eliminated h internally; h is the third return.
        component_integrals = {name: float(np.sum(self.qweight * value)) for name, value in components.items()}
        return {
            "total": float(np.sum(self.qweight * total)),
            "components": component_integrals,
            "physical_fields": self.nodal_physical(y),
            "quadrature_fields": np.stack((p, q, u, b1, b3), axis=-1),
            "quadrature_derivatives": np.stack((dp, dq, du, db1, db3), axis=-1),
            "h": h,
            "H": H,
            "L": L,
        }

    def torch_energy(self, y: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor], torch.Tensor, torch.Tensor, torch.Tensor]:
        t = torch.as_tensor(self.t, dtype=torch.float64)
        basis = torch.as_tensor(self.basis, dtype=torch.float64)
        dbasis = torch.as_tensor(self.dbasis, dtype=torch.float64)
        qr = torch.as_tensor(self.qr, dtype=torch.float64)
        yq = (1.0 - t[None, :, None]) * y[:-1, None, :] + t[None, :, None] * y[1:, None, :]
        dy = (y[1:] - y[:-1]) / self.dr
        fq = yq * basis
        dfq = dy[:, None, :] * basis + yq * dbasis
        p, q, u, b1, b3 = (fq[..., j] for j in range(5))
        dp, dq, du, db1, db3 = (dfq[..., j] for j in range(5))
        total, components, h, H, L = radial_density(p, q, u, b1, b3, dp, dq, du, db1, db3, qr, None, self.epsilon, torch)
        weight = torch.as_tensor(self.qweight, dtype=torch.float64)
        return torch.sum(weight * total), components, h, H, L


def optimize_case(model: RadialModel, y0: np.ndarray) -> tuple[np.ndarray, optimize.OptimizeResult, dict[str, Any]]:
    sqrt_mass = np.sqrt(model.mass[: model.N, None])
    boundary = torch.as_tensor(model.outer, dtype=torch.float64)

    def unpack(z: np.ndarray) -> torch.Tensor:
        free = torch.as_tensor(z.reshape(model.N, 5), dtype=torch.float64) / torch.as_tensor(sqrt_mass, dtype=torch.float64)
        return torch.cat((free, boundary[None, :]), dim=0)

    def objective(z: np.ndarray) -> tuple[float, np.ndarray]:
        z_tensor = torch.as_tensor(z, dtype=torch.float64).requires_grad_(True)
        y_tensor = unpack(z_tensor)
        energy, _, _, _, _ = model.torch_energy(y_tensor)
        grad_z = torch.autograd.grad(energy, z_tensor)[0]
        return float(energy.detach().cpu().item()), grad_z.detach().cpu().numpy().astype(np.float64, copy=False)

    z0 = (y0[:-1] * sqrt_mass).reshape(-1)
    result = optimize.minimize(
        objective,
        z0,
        method="L-BFGS-B",
        jac=True,
        bounds=None,
        options={
            "maxiter": 8000,
            "maxfun": 16000,
            "maxls": 40,
            "maxcor": 30,
            "ftol": 5e-15,
            "gtol": 1e-9,
        },
    )
    y = np.empty_like(y0)
    y[:-1] = result.x.reshape(model.N, 5) / sqrt_mass
    y[-1] = model.outer
    eval_data = model.evaluate_numpy(y)
    # Reconstruct y-gradient separately from the mass-scaled optimizer gradient.
    yt = torch.as_tensor(y, dtype=torch.float64).requires_grad_(True)
    energy, _, _, _, _ = model.torch_energy(yt)
    gy = torch.autograd.grad(energy, yt)[0].detach().cpu().numpy()
    gy_free = gy[:-1]
    rms = math.sqrt(float(np.sum(gy_free * gy_free / model.mass[: model.N, None]) / (5.0 * np.sum(model.mass[: model.N]))))
    max_scaled = float(np.max(np.abs(gy_free) / model.mass[: model.N, None]))
    eval_data["gradient_y"] = gy
    eval_data["gradient_rms"] = rms
    eval_data["gradient_max_abs_over_mass"] = max_scaled
    eval_data["z_gradient_norm"] = float(np.linalg.norm(result.jac)) if result.jac is not None else None
    return y, result, eval_data


def assemble_carrier(
    model: RadialModel,
    physical_fields: np.ndarray,
    quadrature_fields: np.ndarray,
) -> dict[str, Any]:
    """Assemble radial FE matrices and solve physical/control spectra."""
    N = model.N
    rows: list[int] = []
    cols: list[int] = []
    av: list[float] = []
    mv: list[float] = []
    zpv: list[float] = []
    for e in range(N):
        local = np.zeros((2, 2), dtype=np.float64)
        mass_local = np.zeros((2, 2), dtype=np.float64)
        zero_local = np.zeros((2, 2), dtype=np.float64)
        for k in range(2):
            shape = np.array([1.0 - model.t[k], model.t[k]], dtype=np.float64)
            dshape = np.array([-1.0 / model.dr, 1.0 / model.dr], dtype=np.float64)
            w = model.qweight[e, k]
            rho = quadrature_fields[e, k, 0] ** 2 + quadrature_fields[e, k, 1] ** 2
            potential = -ETA_C * (RHO0 - rho)
            mass_local += w * np.outer(shape, shape)
            local += w * (K_CX / 2.0 * np.outer(dshape, dshape) + potential * np.outer(shape, shape))
            zero_local += w * (K_CX / 2.0 * np.outer(dshape, dshape))
        for i in range(2):
            for j in range(2):
                ii, jj = e + i, e + j
                if ii < N and jj < N:
                    rows.append(ii)
                    cols.append(jj)
                    av.append(local[i, j])
                    mv.append(mass_local[i, j])
                    zpv.append(zero_local[i, j])
    A_mat = sparse.coo_matrix((av, (rows, cols)), shape=(N, N)).tocsr()
    M_mat = sparse.coo_matrix((mv, (rows, cols)), shape=(N, N)).tocsr()
    Z_mat = sparse.coo_matrix((zpv, (rows, cols)), shape=(N, N)).tocsr()
    potential_samples = -ETA_C * (RHO0 - (quadrature_fields[..., 0] ** 2 + quadrature_fields[..., 1] ** 2))
    sigma = float(np.min(potential_samples) - 1.0)

    def spectrum(matrix: sparse.csr_matrix, shift: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        values, vectors = spla.eigsh(matrix, M=M_mat, k=3, sigma=shift, which="LM", tol=1e-10)
        order = np.argsort(values)
        values = np.asarray(values[order], dtype=np.float64)
        vectors = np.asarray(vectors[:, order], dtype=np.float64)
        residuals = np.empty(3, dtype=np.float64)
        for j in range(3):
            av = matrix @ vectors[:, j]
            mv = values[j] * (M_mat @ vectors[:, j])
            residuals[j] = np.linalg.norm(av - mv) / max(1.0, np.linalg.norm(av), np.linalg.norm(mv))
        gram = vectors.T @ (M_mat @ vectors)
        return values, vectors, residuals, gram

    eig, vec, residuals, gram = spectrum(A_mat, sigma)
    control_eig, control_vec, control_residuals, control_gram = spectrum(Z_mat, -1.0)
    bessel_first = float(special.jn_zeros(0, 1)[0])
    bessel_first_eigenvalue = K_CX / 2.0 * (bessel_first / model.R) ** 2
    return {
        "carrier_eigenvalues": eig,
        "carrier_eigenvectors": vec,
        "carrier_residual_norms": residuals,
        "carrier_m_gram": gram,
        "carrier_m_orthonormality_max_abs_error": float(np.max(np.abs(gram - np.eye(3)))),
        "zero_attraction_eigenvalues": control_eig,
        "zero_attraction_eigenvectors": control_vec,
        "zero_attraction_residual_norms": control_residuals,
        "zero_attraction_m_gram": control_gram,
        "zero_attraction_m_orthonormality_max_abs_error": float(np.max(np.abs(control_gram - np.eye(3)))),
        "carrier_potential_min": float(np.min(potential_samples)),
        "carrier_shift_sigma": sigma,
        "bessel_first_zero": bessel_first,
        "bessel_first_eigenvalue": bessel_first_eigenvalue,
    }


def source_tail(model: RadialModel, eval_data: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    qr = model.qr.reshape(-1)
    fields = eval_data["quadrature_fields"].reshape(-1, 5)
    source = qr * qr * (RHO0 - (fields[:, 0] ** 2 + fields[:, 1] ** 2))
    mask = (qr >= 16.0) & (qr <= 24.0)
    radii = qr[mask]
    values = source[mask]
    if values.size:
        rel = np.abs(values - A_RHO) / abs(A_RHO)
        metrics = {
            "tail_expected_A_rho": A_RHO,
            "tail_mean_relative_deviation": float(np.mean(rel)),
            "tail_max_relative_deviation": float(np.max(rel)),
            "tail_sample_count": int(values.size),
            "tail_finest_grid": bool(model.R == 64.0 and model.N == 1024),
        }
    else:
        metrics = {
            "tail_expected_A_rho": A_RHO,
            "tail_mean_relative_deviation": None,
            "tail_max_relative_deviation": None,
            "tail_sample_count": 0,
            "tail_finest_grid": bool(model.R == 64.0 and model.N == 1024),
        }
    return radii, values, metrics


def run_case(output: Path, epsilon: int, R: float, N: int, previous: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    model = RadialModel(R, N, epsilon)
    y0 = model.initial_y() if previous is None else model.continuation_y(previous)
    status = "exception"
    result: optimize.OptimizeResult | None = None
    eval_data: dict[str, Any] | None = None
    exception_text: str | None = None
    optimizer_started = time.perf_counter()
    try:
        y, result, eval_data = optimize_case(model, y0)
        status = "optimized"
    except Exception as exc:  # Preserve an explicit failed row and its current initialized fields.
        y = y0
        exception_text = f"{type(exc).__name__}: {exc}"
        eval_data = model.evaluate_numpy(y)
    optimizer_elapsed = time.perf_counter() - optimizer_started
    assert eval_data is not None
    tail_r, tail_values, tail_metrics = source_tail(model, eval_data)
    h, H, h_residual = h_stationarity_data(
        eval_data["quadrature_fields"][..., 0],
        eval_data["quadrature_fields"][..., 1],
        eval_data["quadrature_fields"][..., 2],
        eval_data["quadrature_fields"][..., 3],
        eval_data["quadrature_fields"][..., 4],
        eval_data["quadrature_derivatives"][..., 0],
        eval_data["quadrature_derivatives"][..., 1],
        eval_data["quadrature_derivatives"][..., 2],
        eval_data["quadrature_derivatives"][..., 3],
        eval_data["quadrature_derivatives"][..., 4],
        model.qr,
        epsilon,
    )
    eval_data["h"] = h
    eval_data["H"] = H
    eval_data["h_stationary_residual"] = h_residual
    try:
        carrier = assemble_carrier(model, eval_data["physical_fields"], eval_data["quadrature_fields"])
    except Exception as exc:
        carrier = {
            "carrier_exception": f"{type(exc).__name__}: {exc}",
            "carrier_eigenvalues": np.full(3, np.nan),
            "carrier_eigenvectors": np.full((N, 3), np.nan),
            "carrier_residual_norms": np.full(3, np.nan),
            "carrier_m_gram": np.full((3, 3), np.nan),
            "zero_attraction_eigenvalues": np.full(3, np.nan),
            "zero_attraction_eigenvectors": np.full((N, 3), np.nan),
            "zero_attraction_residual_norms": np.full(3, np.nan),
            "zero_attraction_m_gram": np.full((3, 3), np.nan),
            "carrier_m_orthonormality_max_abs_error": np.nan,
            "zero_attraction_m_orthonormality_max_abs_error": np.nan,
            "carrier_potential_min": np.nan,
            "carrier_shift_sigma": np.nan,
            "bessel_first_zero": float(special.jn_zeros(0, 1)[0]),
            "bessel_first_eigenvalue": float(K_CX / 2.0 * (special.jn_zeros(0, 1)[0] / R) ** 2),
        }
    carrier_vectors = np.zeros((N + 1, 3), dtype=np.float64)
    carrier_vectors[:N] = carrier["carrier_eigenvectors"]
    control_vectors = np.zeros((N + 1, 3), dtype=np.float64)
    control_vectors[:N] = carrier["zero_attraction_eigenvectors"]
    stem = f"cap_{'plus' if epsilon == 1 else 'minus'}_N{N}_R{int(R)}"
    npz_path = output / f"{stem}.npz"
    np.savez_compressed(
        npz_path,
        r=model.r,
        y=y,
        physical_fields=eval_data["physical_fields"],
        quadrature_r=model.qr,
        quadrature_fields=eval_data["quadrature_fields"],
        quadrature_derivatives=eval_data["quadrature_derivatives"],
        h=h,
        energy=np.array(eval_data["total"]),
        energy_component_names=np.array([
            "fundamental_radial",
            "adjoint_radial",
            "fundamental_angular",
            "adjoint_angular",
            "magnetic",
            "potential",
        ]),
        energy_component_values=np.array([
            eval_data["components"]["psi_radial"],
            eval_data["components"]["phi_radial"],
            eval_data["components"]["psi_angular"],
            eval_data["components"]["phi_angular"],
            eval_data["components"]["gauge"],
            eval_data["components"]["density_potential"] + eval_data["components"]["composition_potential"] + eval_data["components"]["higgs_potential"],
        ], dtype=np.float64),
        gradient_y=eval_data.get("gradient_y", np.full_like(y, np.nan)),
        carrier_eigenvalues=carrier["carrier_eigenvalues"],
        carrier_eigenvectors=carrier_vectors,
        control_eigenvalues=carrier["zero_attraction_eigenvalues"],
        control_eigenvectors=control_vectors,
        optimizer_elapsed_seconds=np.array(optimizer_elapsed),
        carrier_residual_norms=carrier["carrier_residual_norms"],
        carrier_m_gram=carrier["carrier_m_gram"],
        control_residual_norms=carrier["zero_attraction_residual_norms"],
        control_m_gram=carrier["zero_attraction_m_gram"],
        source_tail_r=tail_r,
        source_tail_values=tail_values,
        h_stationary_residual=h_residual,
    )
    optimizer_info: dict[str, Any] = {
        "success": bool(result.success) if result is not None else False,
        "status": int(result.status) if result is not None else -1,
        "message": str(result.message) if result is not None else exception_text,
        "nit": int(result.nit) if result is not None else 0,
        "nfev": int(result.nfev) if result is not None else 0,
        "elapsed_seconds": optimizer_elapsed,
    }
    H_positive = bool(np.all(H > 0.0))
    h_relative = np.abs(h_residual) / np.maximum(1.0, np.abs(eval_data["L"]))
    h_stationarity_max = float(np.max(h_relative))
    h_rms = math.sqrt(float(np.sum(model.qweight * h_residual * h_residual) / np.sum(model.qweight)))
    # Stationarity qualification is separate from the optimizer's status.
    stationary = bool(
        status == "optimized"
        and eval_data.get("gradient_rms", math.inf) <= 1.0e-6
        and eval_data.get("gradient_max_abs_over_mass", math.inf) <= 1.0e-4
        and H_positive
        and h_stationarity_max <= 1.0e-10
    )
    component_values = {
        "fundamental_radial": eval_data["components"]["psi_radial"],
        "adjoint_radial": eval_data["components"]["phi_radial"],
        "fundamental_angular": eval_data["components"]["psi_angular"],
        "adjoint_angular": eval_data["components"]["phi_angular"],
        "magnetic": eval_data["components"]["gauge"],
        "potential": eval_data["components"]["density_potential"] + eval_data["components"]["composition_potential"] + eval_data["components"]["higgs_potential"],
    }
    carrier_summary = {
        "carrier_potential_min": carrier["carrier_potential_min"],
        "carrier_shift_sigma": carrier["carrier_shift_sigma"],
        "bessel_first_zero": carrier["bessel_first_zero"],
        "bessel_first_eigenvalue": carrier["bessel_first_eigenvalue"],
    }
    rho_nodes = eval_data["physical_fields"][:, 0] ** 2 + eval_data["physical_fields"][:, 1] ** 2
    rho_quadrature = eval_data["quadrature_fields"][..., 0] ** 2 + eval_data["quadrature_fields"][..., 1] ** 2
    row = {
        "cap": "plus" if epsilon == 1 else "minus",
        "epsilon": epsilon,
        "R": R,
        "N": N,
        "npz": npz_path.name,
        "status": status,
        "exception": exception_text,
        "carrier_exception": carrier.get("carrier_exception"),
        "energy": eval_data["total"],
        "energy_components": component_values,
        "renormalized_energy": eval_data["total"] - math.pi * J0 / 4.0 * math.log(R),
        "gradient_rms": eval_data.get("gradient_rms"),
        "gradient_max": eval_data.get("gradient_max_abs_over_mass"),
        "h_stationarity_max": h_stationarity_max,
        "minimum_rho": float(np.min(rho_nodes)),
        "minimum_u": float(np.min(eval_data["physical_fields"][:, 2])),
        "rho_origin": float(rho_nodes[0]),
        "carrier_eigenvalues": carrier["carrier_eigenvalues"],
        "carrier_control_eigenvalues": carrier["zero_attraction_eigenvalues"],
        "carrier_residual": float(np.max(carrier["carrier_residual_norms"])),
        "carrier_orthogonality_error": carrier["carrier_m_orthonormality_max_abs_error"],
        "stationary": stationary,
        "tail": {
            "mean_coefficient": float(np.mean(tail_values)) if tail_values.size else None,
            "max_relative_error": tail_metrics["tail_max_relative_deviation"],
        },
        "optimizer": optimizer_info,
        "h_stationarity_rms": h_rms,
        "H_minimum": float(np.min(H)),
        "carrier_summary": carrier_summary,
        "numerical_qualification": bool(
            stationary
            and np.all(np.isfinite(carrier["carrier_eigenvalues"]))
            and np.all(np.isfinite(carrier["zero_attraction_eigenvalues"]))
            and np.max(carrier["carrier_residual_norms"]) < 1e-8
            and carrier["carrier_m_orthonormality_max_abs_error"] < 1e-8
            and np.max(carrier["zero_attraction_residual_norms"]) < 1e-8
            and carrier["zero_attraction_m_orthonormality_max_abs_error"] < 1e-8
        ),
    }
    return row, {"r": model.r, "y": y, "physical_fields": eval_data["physical_fields"]}


def run(output: Path) -> int:
    _torch_single_thread()
    output.mkdir(parents=True, exist_ok=False)
    rows: list[dict[str, Any]] = []
    for epsilon in (1, -1):
        previous: dict[str, Any] | None = None
        for R, N in ((32.0, 256), (32.0, 512), (64.0, 512), (64.0, 1024)):
            row, previous = run_case(output, epsilon, R, N, previous)
            rows.append(row)
            row_path = output / Path(row["npz"]).with_suffix(".json")
            with row_path.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(strict_value(row), handle, indent=2, sort_keys=True, allow_nan=False)
                handle.write("\n")
            print(json.dumps(strict_value(row), sort_keys=True, allow_nan=False), flush=True)
    summary = {
        "schema": SCHEMA,
        "source": "computations/matter_formation_vortex_core.py",
        "platform": platform.platform(),
        "parameters": {
            "rho0": RHO0,
            "a": A,
            "d": D,
            "v": V,
            "g": G,
            "lambda_rho": LAMBDA_RHO,
            "lambda_phi": LAMBDA_PHI,
            "lambda_H": LAMBDA_H,
            "K_Cx": K_CX,
            "eta_C": ETA_C,
            "phi": PHI,
            "c0": C0,
            "m": M_WINDING,
            "J0": J0,
            "A_rho": A_RHO,
        },
        "fixed_schedule": [[32, 256], [32, 512], [64, 512], [64, 1024]],
        "rows": rows,
        "all_rows_numerically_qualified": bool(rows) and all(bool(row["numerical_qualification"]) for row in rows),
        "complete_physical_matter_formation": False,
        "scope_caveats": [
            "The carrier eigenpairs are transverse states on a straight finite cylinder, not a finite loop or a production event.",
            "The witness parameters are supplied source units without physical calibration.",
            "A stationary row requires the declared gradient and algebraic-h residual metrics; optimizer success alone is insufficient.",
        ],
    }
    with (output / "summary.json").open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(strict_value(summary), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return 0 if summary["all_rows_numerically_qualified"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new output directory; an existing directory is refused")
    args = parser.parse_args()
    return run(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
