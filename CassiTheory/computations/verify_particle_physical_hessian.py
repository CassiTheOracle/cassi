#!/usr/bin/env python3
"""Independently verify the frozen PA42 finite-grid physical Hessian campaign.

Run from the CassiTheory repository root:

    python computations/verify_particle_physical_hessian.py --preflight
    python computations/verify_particle_physical_hessian.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy import sparse
from scipy.linalg import cho_factor, cho_solve, eigvalsh, qr, svd
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigsh


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz"
RUN_DIR = ROOT / "runs/20260902_particle_physical_hessian"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
MODES_PATH = RUN_DIR / "eigenmodes.npz"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations/particle_physical_hessian_manifest.json"

ARTIFACT_SHA256 = "99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
OMEGA_C = 0.9619135625713447
COEFFICIENTS = {
    "u_rho": 4.0,
    "u_phi": 4.0,
    "gamma_x": 1.0,
    "u_H": 4.0,
    "k_Cx": 1.0,
    "e_C": 0.75,
    "h_C": 1.50,
    "u_C": 1.0,
    "q_C": 4.0,
    "xi_gf": 1.0,
}
FROZEN_BACKGROUND = {
    "physical_energy": 3.8542001269281165,
    "physical_gradient_rms": 1.936974511462461e-4,
    "cutoff_virial": 1.8910101999779969e-3,
    "omega_c": OMEGA_C,
    "charge": 4.0,
}

N = 17
M = 15
DX = 0.5
DV = DX**3
NS = 855
NV = 2535
N_ALPHA = 559
N_GAUGE = 1677
N_NONCARRIER = 13590
N_BASE = 15299
N_PHYS = 13622
FIELD_COMPONENTS = 18
STEPS = (2.0e-4, 1.0e-4, 5.0e-5)
ROTATION = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
PAULI_GENERATORS = 0.5 * np.asarray(
    (
        ((0.0, 1.0), (1.0, 0.0)),
        ((0.0, -1.0j), (1.0j, 0.0)),
        ((1.0, 0.0), (0.0, -1.0)),
    ),
    dtype=np.complex128,
)


class VerificationFailure(RuntimeError):
    """Raised when a frozen independent-verification gate fails."""


def sha256_file(path: Path) -> str:
    if path.suffix.lower() in {".json", ".md", ".py"}:
        canonical = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(canonical).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def scalar(value: torch.Tensor) -> float:
    return float(value.detach().cpu())


def verify_manifest() -> tuple[dict[str, Any], str]:
    if not MANIFEST_PATH.is_file():
        raise VerificationFailure(f"missing frozen manifest: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest.get("sha256")
    if not isinstance(expected, dict) or not expected:
        raise VerificationFailure("manifest has no sha256 mapping")
    mismatches: dict[str, dict[str, str]] = {}
    for relative, frozen_hash in expected.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != frozen_hash:
            mismatches[relative] = {"expected": frozen_hash, "actual": actual}
    if mismatches:
        raise VerificationFailure(f"source manifest mismatch: {mismatches}")
    return manifest, sha256_file(MANIFEST_PATH)


def configure_torch() -> torch.device:
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cuda"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise VerificationFailure("ROCm/CUDA PyTorch device is required by the frozen campaign")
    return torch.device("cuda:0")


@dataclass
class Grid:
    x: torch.Tensor
    X: torch.Tensor
    Y: torch.Tensor
    Z: torch.Tensor
    mask: torch.Tensor
    rotations: tuple[torch.Tensor, ...]
    sigma: torch.Tensor
    generators: torch.Tensor
    psi_inf: torch.Tensor
    h_inf: torch.Tensor
    dx: float = DX
    dv: float = DV
    R: float = 4.0


def make_grid(device: torch.device) -> Grid:
    x = torch.linspace(-4.0, 4.0, N, device=device, dtype=torch.float64)
    X, Y, Z = torch.meshgrid(x, x, x, indexing="ij")
    mask = torch.zeros((N, N, N), device=device, dtype=torch.float64)
    mask[1:-1, 1:-1, 1:-1] = 1.0
    rotations = tuple(
        torch.as_tensor(np.linalg.matrix_power(ROTATION, turn), device=device, dtype=torch.float64)
        for turn in range(4)
    )
    sigma = torch.as_tensor(2.0 * PAULI_GENERATORS, device=device, dtype=torch.complex128)
    return Grid(
        x=x,
        X=X,
        Y=Y,
        Z=Z,
        mask=mask,
        rotations=rotations,
        sigma=sigma,
        generators=sigma / 2.0,
        psi_inf=torch.as_tensor((PHI**-0.5, PHI**-1.0), device=device),
        h_inf=torch.as_tensor((0.0, 0.0, 1.0), device=device),
    )


def derivatives(field: torch.Tensor, grid: Grid) -> tuple[torch.Tensor, ...]:
    return torch.gradient(
        field,
        spacing=(grid.dx, grid.dx, grid.dx),
        dim=(0, 1, 2),
        edge_order=2,
    )


def project_scalar(field: torch.Tensor) -> torch.Tensor:
    return sum(torch.rot90(field, turn, dims=(0, 1)) for turn in range(4)) / 4.0


def project_vector(field: torch.Tensor, rotations: tuple[torch.Tensor, ...]) -> torch.Tensor:
    projected = torch.zeros_like(field)
    for turn, rotation in enumerate(rotations):
        projected = projected + torch.einsum(
            "ij,...ja->...ia", rotation, torch.rot90(field, turn, dims=(0, 1))
        )
    return projected / 4.0


def energy_components(
    fields: dict[str, torch.Tensor], chi_imag: torch.Tensor, grid: Grid
) -> tuple[dict[str, torch.Tensor], torch.Tensor, dict[str, torch.Tensor]]:
    psi = torch.complex(fields["psi_real"], fields["psi_imag"])
    h = fields["h"]
    a = fields["a"]
    chi_real = fields["c"]

    dpsi = torch.stack(derivatives(psi, grid), dim=-2)
    gauge_psi = torch.einsum(
        "...ia,abc,...c->...ib", a.to(grid.generators.dtype), grid.generators, psi
    )
    covariant_psi = dpsi - 1.0j * gauge_psi

    rho = torch.sum(torch.abs(psi) ** 2, dim=-1)
    spin = torch.einsum("...b,abc,...c->...a", psi.conj(), grid.sigma, psi).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * torch.sum(h * spin, dim=-1)
    )

    da = derivatives(a, grid)
    curvature_rows: list[torch.Tensor] = []
    for i in range(3):
        row: list[torch.Tensor] = []
        for j in range(3):
            row.append(
                da[i][..., j, :]
                - da[j][..., i, :]
                + torch.cross(a[..., i, :], a[..., j, :], dim=-1)
            )
        curvature_rows.append(torch.stack(row, dim=-2))
    curvature = torch.stack(curvature_rows, dim=-3)

    dh = torch.stack(derivatives(h, grid), dim=-2)
    covariant_h = dh + torch.cross(a, h[..., None, :].expand_as(a), dim=-1)
    dchi_real = derivatives(chi_real, grid)
    dchi_imag = derivatives(chi_imag, grid)
    divergence = sum(da[index][..., index, :] for index in range(3))
    chi_modulus2 = chi_real**2 + chi_imag**2
    carrier_gradient_norm = sum(
        torch.sum(real_derivative**2 + imag_derivative**2)
        for real_derivative, imag_derivative in zip(dchi_real, dchi_imag)
    )

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
        * carrier_gradient_norm
        * grid.dv,
        "carrier_quadratic": torch.sum(
            (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - rho))
            * chi_modulus2
        )
        * grid.dv,
        "carrier_quartic": COEFFICIENTS["u_C"]
        / 2.0
        * torch.sum(chi_modulus2**2)
        * grid.dv,
    }
    gauge_fixing = COEFFICIENTS["xi_gf"] / 2.0 * torch.sum(divergence**2) * grid.dv
    return components, gauge_fixing, {"rho": rho, "curvature": curvature, "divergence": divergence}


def physical_gradient_rms(fields: dict[str, torch.Tensor], grid: Grid) -> float:
    leaves = {
        name: value.detach().clone().requires_grad_(True) for name, value in fields.items()
    }
    chi_imag = torch.zeros_like(leaves["c"])
    components, _, _ = energy_components(leaves, chi_imag, grid)
    physical = torch.stack(tuple(components.values())).sum()
    order = ("psi_real", "psi_imag", "h", "a", "c")
    gradients = torch.autograd.grad(physical, tuple(leaves[name] for name in order))
    projected = [
        project_scalar(grid.mask[..., None] * gradients[0] / grid.dv),
        project_scalar(grid.mask[..., None] * gradients[1] / grid.dv),
        project_scalar(grid.mask[..., None] * gradients[2] / grid.dv),
        project_vector(grid.mask[..., None, None] * gradients[3] / grid.dv, grid.rotations),
    ]
    carrier_gradient = gradients[4] / grid.dv
    inner = torch.sum(leaves["c"] * carrier_gradient) * grid.dv
    norm = torch.sum(leaves["c"] ** 2) * grid.dv
    carrier_tangent = grid.mask * (carrier_gradient - leaves["c"] * inner / norm)
    projected.append(project_scalar(carrier_tangent))
    squared = sum(torch.sum(value**2) for value in projected)
    return scalar(torch.sqrt(squared / (M**3 * 17)))


def cutoff_virial(
    fields: dict[str, torch.Tensor], grid: Grid, components: dict[str, torch.Tensor]
) -> tuple[float, float, dict[str, float]]:
    psi = torch.complex(fields["psi_real"], fields["psi_imag"])
    h = fields["h"]
    a = fields["a"]
    c = fields["c"]
    cutoff = (
        (1.0 - (grid.X / grid.R) ** 2) ** 2
        * (1.0 - (grid.Y / grid.R) ** 2) ** 2
        * (1.0 - (grid.Z / grid.R) ** 2) ** 2
    )
    vector = cutoff[..., None] * torch.stack((grid.X, grid.Y, grid.Z), dim=-1)
    dpsi = derivatives(psi, grid)
    dh = derivatives(h, grid)
    da = derivatives(a, grid)
    dvector = derivatives(vector, grid)
    dot_psi = -sum(vector[..., axis, None] * dpsi[axis] for axis in range(3))
    dot_h = -sum(vector[..., axis, None] * dh[axis] for axis in range(3))
    advected_a = sum(vector[..., axis, None, None] * da[axis] for axis in range(3))
    one_form = torch.stack(
        tuple(torch.einsum("...j,...ja->...a", dvector[i], a) for i in range(3)),
        dim=-2,
    )
    dot_a = -advected_a - one_form
    dlog_c = derivatives(torch.log(c + 1.0e-12), grid)
    divergence_v = sum(dvector[i][..., i] for i in range(3))
    transport_c = sum(vector[..., axis] * dlog_c[axis] for axis in range(3))
    scale_c = -transport_c - 0.5 * divergence_v

    perturbed: dict[int, dict[str, torch.Tensor]] = {}
    for sign in (-1, 1):
        step = sign * 1.0e-4
        psi_trial = project_scalar(psi + step * dot_psi)
        psi_trial = grid.mask[..., None] * psi_trial + (1.0 - grid.mask[..., None]) * grid.psi_inf
        h_trial = project_scalar(h + step * dot_h)
        h_trial = grid.mask[..., None] * h_trial + (1.0 - grid.mask[..., None]) * grid.h_inf
        a_trial = (
            project_vector(a + step * dot_a, grid.rotations) * grid.mask[..., None, None]
        )
        positive = grid.mask * c * torch.exp(step * scale_c)
        c_trial = math.sqrt(COEFFICIENTS["q_C"]) * positive / torch.sqrt(
            torch.sum(positive**2) * grid.dv
        )
        trial = {
            "psi_real": psi_trial.real,
            "psi_imag": psi_trial.imag,
            "h": h_trial,
            "a": a_trial,
            "c": c_trial,
        }
        perturbed[sign], _, _ = energy_components(trial, torch.zeros_like(c_trial), grid)

    directional = {
        name: scalar((perturbed[1][name] - perturbed[-1][name]) / 2.0e-4)
        for name in components
    }
    numerator = abs(sum(directional.values()))
    denominator = max(1.0e-12, sum(abs(value) for value in directional.values()))
    formal = (
        scalar(components["psi_gradient"])
        + scalar(components["h_gradient"])
        - scalar(components["curvature"])
        + 3.0
        * (
            scalar(components["rho_potential"])
            + scalar(components["composition_potential"])
            + scalar(components["h_potential"])
        )
        - 2.0 * scalar(components["carrier_gradient"])
        - 3.0 * scalar(components["carrier_quartic"])
    )
    return numerator / denominator, formal, directional


def rotate_site(site: tuple[int, int, int]) -> tuple[int, int, int]:
    i, j, k = site
    return j, N - 1 - i, k


def orbit_partition(sites: list[tuple[int, int, int]]) -> list[list[tuple[int, int, int]]]:
    unseen = set(sites)
    orbits: list[list[tuple[int, int, int]]] = []
    while unseen:
        seed = min(unseen)
        orbit: list[tuple[int, int, int]] = []
        site = seed
        for _ in range(4):
            if site not in orbit:
                orbit.append(site)
            site = rotate_site(site)
        unseen.difference_update(orbit)
        orbits.append(orbit)
    return orbits


def flat_index(site: tuple[int, int, int]) -> int:
    i, j, k = site
    return (i * N + j) * N + k


def interior_index(site: tuple[int, int, int]) -> int:
    i, j, k = site
    return ((i - 1) * M + (j - 1)) * M + (k - 1)


@dataclass
class BasisData:
    scalar: sparse.csr_matrix
    vector: sparse.csr_matrix
    scalar_index: np.ndarray
    scalar_weight: np.ndarray
    vector_index: np.ndarray
    vector_matrix: np.ndarray


def build_bases() -> tuple[BasisData, dict[str, Any]]:
    sites = [(i, j, k) for i in range(1, 16) for j in range(1, 16) for k in range(1, 16)]
    orbits = orbit_partition(sites)
    if len(orbits) != NS:
        raise VerificationFailure(f"independent scalar C4 dimension {len(orbits)} != {NS}")

    scalar_rows: list[int] = []
    scalar_columns: list[int] = []
    scalar_values: list[float] = []
    scalar_index = np.zeros(N**3, dtype=np.int64)
    scalar_weight = np.zeros(N**3, dtype=np.float64)
    for column, orbit in enumerate(orbits):
        weight = 1.0 / math.sqrt(len(orbit))
        for site in orbit:
            row = flat_index(site)
            scalar_rows.append(row)
            scalar_columns.append(column)
            scalar_values.append(weight)
            scalar_index[row] = column
            scalar_weight[row] = weight
    scalar_basis = sparse.coo_matrix(
        (scalar_values, (scalar_rows, scalar_columns)), shape=(N**3, NS)
    ).tocsr()

    vector_rows: list[int] = []
    vector_columns: list[int] = []
    vector_values: list[float] = []
    vector_index = np.zeros((N**3, 3), dtype=np.int64)
    vector_matrix = np.zeros((N**3, 3, 3), dtype=np.float64)
    column = 0
    for orbit in orbits:
        if len(orbit) == 1:
            site = orbit[0]
            row = flat_index(site)
            vector_index[row, :] = column
            vector_matrix[row, 2, 0] = 1.0
            vector_rows.append(2 * M**3 + interior_index(site))
            vector_columns.append(column)
            vector_values.append(1.0)
            column += 1
            continue
        ordered = [orbit[0]]
        for _ in range(3):
            ordered.append(rotate_site(ordered[-1]))
        for seed in range(3):
            for turn, site in enumerate(ordered):
                value = np.linalg.matrix_power(ROTATION, -turn)[:, seed] / 2.0
                row = flat_index(site)
                vector_index[row, seed] = column
                vector_matrix[row, :, seed] = value
                for component, entry in enumerate(value):
                    if entry:
                        vector_rows.append(component * M**3 + interior_index(site))
                        vector_columns.append(column)
                        vector_values.append(float(entry))
            column += 1
    if column != NV:
        raise VerificationFailure(f"independent vector C4 dimension {column} != {NV}")
    vector_basis = sparse.coo_matrix(
        (vector_values, (vector_rows, vector_columns)), shape=(3 * M**3, NV)
    ).tocsr()
    scalar_orthogonality = float(
        np.max(np.abs((scalar_basis.T @ scalar_basis).toarray() - np.eye(NS)))
    )
    vector_orthogonality = float(
        np.max(np.abs((vector_basis.T @ vector_basis).toarray() - np.eye(NV)))
    )
    if scalar_orthogonality > 1.0e-12 or vector_orthogonality > 1.0e-12:
        raise VerificationFailure(
            f"independent C4 bases are not orthonormal: {scalar_orthogonality}, "
            f"{vector_orthogonality}"
        )
    return (
        BasisData(
            scalar=scalar_basis,
            vector=vector_basis,
            scalar_index=scalar_index,
            scalar_weight=scalar_weight,
            vector_index=vector_index,
            vector_matrix=vector_matrix,
        ),
        {
            "scalar_dimension": NS,
            "vector_dimension": NV,
            "scalar_orthogonality_max": scalar_orthogonality,
            "vector_orthogonality_max": vector_orthogonality,
            "axis_orbits": sum(len(orbit) == 1 for orbit in orbits),
            "four_site_orbits": sum(len(orbit) == 4 for orbit in orbits),
        },
    )


def derivative_matrix() -> np.ndarray:
    matrix = np.empty((N, N), dtype=np.float64)
    for column in range(N):
        impulse = np.zeros(N, dtype=np.float64)
        impulse[column] = 1.0
        matrix[:, column] = np.gradient(impulse, DX, edge_order=2)
    return matrix


def boundary_gauge_basis(bases: BasisData) -> tuple[np.ndarray, dict[str, Any]]:
    derivative = derivative_matrix()
    identity = sparse.eye(N, format="csr")
    gradient = sparse.vstack(
        (
            sparse.kron(sparse.kron(derivative, identity), identity),
            sparse.kron(sparse.kron(identity, derivative), identity),
            sparse.kron(sparse.kron(identity, identity), derivative),
        ),
        format="csr",
    )
    shell = np.asarray(
        [
            i in (0, 16) or j in (0, 16) or k in (0, 16)
            for i in range(N)
            for j in range(N)
            for k in range(N)
        ],
        dtype=bool,
    )
    boundary = (gradient @ bases.scalar)[np.tile(shell, 3), :].toarray()
    _, singular, right = svd(boundary, full_matrices=True, lapack_driver="gesdd")
    ranks = {
        f"relative_{threshold:.0e}": int(np.count_nonzero(singular > threshold * singular[0]))
        for threshold in (1.0e-10, 1.0e-11, 1.0e-12)
    }
    rank = ranks["relative_1e-11"]
    null = right[rank:].T.copy()
    orthogonality = float(np.max(np.abs(null.T @ null - np.eye(null.shape[1]))))
    residual = float(np.linalg.norm(boundary @ null, ord=2))
    diagnostics = {
        "matrix_shape": list(boundary.shape),
        "ranks": ranks,
        "rank": rank,
        "null_dimension": int(null.shape[1]),
        "sigma_max": float(singular[0]),
        "sigma_last_retained": float(singular[rank - 1]),
        "sigma_first_null": float(singular[rank]),
        "null_orthogonality_max": orthogonality,
        "null_residual_2": residual,
    }
    if rank != 296 or null.shape[1] != N_ALPHA or any(value != 296 for value in ranks.values()):
        raise VerificationFailure(f"independent boundary-gauge rank failure: {diagnostics}")
    if orthogonality > 1.0e-11 or residual > 1.0e-11:
        raise VerificationFailure(f"independent boundary-gauge null failure: {diagnostics}")
    return null, diagnostics


def carrier_tangent_basis(
    carrier: np.ndarray, bases: BasisData
) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    reduced = np.asarray(bases.scalar.T @ carrier.reshape(-1), dtype=np.float64)
    unit = reduced / np.linalg.norm(reduced)
    sign = 1.0 if unit[0] >= 0.0 else -1.0
    householder = unit.copy()
    householder[0] += sign
    householder /= np.linalg.norm(householder)
    tangent = (np.eye(NS) - 2.0 * np.outer(householder, householder))[:, 1:]
    orthogonality = float(np.max(np.abs(tangent.T @ tangent - np.eye(NS - 1))))
    residual = float(np.max(np.abs(reduced @ tangent)))
    diagnostics = {
        "orthogonality_max": orthogonality,
        "charge_normal_residual": residual,
        "reduced_carrier_norm": float(np.linalg.norm(reduced)),
    }
    if orthogonality > 1.0e-11 or residual > 1.0e-11:
        raise VerificationFailure(f"independent carrier tangent failure: {diagnostics}")
    return tangent, reduced, diagnostics


def boundary_max(field: np.ndarray) -> float:
    shell = np.zeros((N, N, N), dtype=bool)
    shell[[0, -1], :, :] = True
    shell[:, [0, -1], :] = True
    shell[:, :, [0, -1]] = True
    return float(np.max(np.abs(field[shell])))


def scalar_c4(field: np.ndarray) -> np.ndarray:
    return sum(np.rot90(field, turn, axes=(0, 1)) for turn in range(4)) / 4.0


def vector_c4(field: np.ndarray) -> np.ndarray:
    projected = np.zeros_like(field)
    for turn in range(4):
        projected += np.einsum(
            "ij,...ja->...ia",
            np.linalg.matrix_power(ROTATION, turn),
            np.rot90(field, turn, axes=(0, 1)),
        )
    return projected / 4.0


def projection_residual(field: np.ndarray, projected: np.ndarray) -> float:
    return float(np.max(np.abs(field - projected)) / max(float(np.max(np.abs(field))), 1.0))


def coupled_gauge_matrix(
    fields: dict[str, np.ndarray], bases: BasisData, alpha_null: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    alpha_fields = np.asarray(bases.scalar @ alpha_null).reshape(N, N, N, N_ALPHA)
    alpha_derivatives = np.gradient(alpha_fields, DX, axis=(0, 1, 2), edge_order=2)
    gauge = np.zeros((N_NONCARRIER, N_GAUGE), dtype=np.float64)
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h = fields["h"]
    a = fields["a"]
    interior = (slice(1, -1), slice(1, -1), slice(1, -1))
    sample: dict[str, float] = {}

    for input_color in range(3):
        columns = slice(input_color * N_ALPHA, (input_color + 1) * N_ALPHA)
        transformed_psi = np.einsum("ab,...b->...a", PAULI_GENERATORS[input_color], psi)
        delta_psi = 1.0j * transformed_psi[..., None] * alpha_fields[..., None, :]
        for component in range(2):
            real = delta_psi[..., component, :].real.reshape(N**3, N_ALPHA)
            imag = delta_psi[..., component, :].imag.reshape(N**3, N_ALPHA)
            gauge[component * NS : (component + 1) * NS, columns] = bases.scalar.T @ real
            offset = (2 + component) * NS
            gauge[offset : offset + NS, columns] = bases.scalar.T @ imag

        delta_h = (
            np.cross(h, np.eye(3, dtype=np.float64)[input_color])[..., :, None]
            * alpha_fields[..., None, :]
        )
        for component in range(3):
            values = delta_h[..., component, :].reshape(N**3, N_ALPHA)
            offset = (4 + component) * NS
            gauge[offset : offset + NS, columns] = bases.scalar.T @ values

        for output_color in range(3):
            spatial: list[np.ndarray] = []
            for spatial_component in range(3):
                commutator = np.cross(
                    a[..., spatial_component, :], np.eye(3, dtype=np.float64)[input_color]
                )[..., output_color, None]
                delta_a = commutator * alpha_fields
                if output_color == input_color:
                    delta_a = delta_a + alpha_derivatives[spatial_component]
                spatial.append(delta_a[interior].reshape(M**3, N_ALPHA))
            offset = 7 * NS + output_color * NV
            gauge[offset : offset + NV, columns] = bases.vector.T @ np.concatenate(spatial, axis=0)

        if input_color == 0:
            alpha = alpha_fields[..., 0]
            delta_a_sample = np.zeros_like(a)
            for spatial_component in range(3):
                delta_a_sample[..., spatial_component, :] = (
                    np.cross(a[..., spatial_component, :], np.eye(3)[0]) * alpha[..., None]
                )
                delta_a_sample[..., spatial_component, 0] += alpha_derivatives[spatial_component][..., 0]
            sample = {
                "delta_psi_norm": float(np.linalg.norm(1.0j * transformed_psi * alpha[..., None])),
                "delta_h_norm": float(
                    np.linalg.norm(np.cross(h, np.eye(3)[0]) * alpha[..., None])
                ),
                "delta_a_norm": float(np.linalg.norm(delta_a_sample)),
                "alpha_shell_max": boundary_max(alpha),
                "delta_a_shell_max": boundary_max(delta_a_sample),
            }

    eigenvalues = eigvalsh(gauge.T @ gauge, driver="evr")
    singular = np.sqrt(np.maximum(eigenvalues, 0.0))
    sigma_max = float(singular[-1])
    ranks = {
        f"relative_{threshold:.0e}": int(np.count_nonzero(singular > threshold * sigma_max))
        for threshold in (1.0e-10, 1.0e-11, 1.0e-12)
    }
    diagnostics = {
        "nonzero_shape": list(gauge.shape),
        "embedded_shape": [N_BASE, N_GAUGE],
        "ranks": ranks,
        "rank": ranks["relative_1e-11"],
        "sigma_min": float(singular[0]),
        "sigma_max": sigma_max,
        "condition": sigma_max / float(singular[0]),
        "sample_generator": sample,
    }
    if any(value != N_GAUGE for value in ranks.values()) or singular[0] <= 1.0e-6:
        raise VerificationFailure(f"independent coupled-gauge rank failure: {diagnostics}")
    if sample["delta_a_shell_max"] > 1.0e-12:
        raise VerificationFailure(f"independent gauge shell failure: {diagnostics}")
    return gauge, diagnostics


class IndependentSpace:
    def __init__(
        self,
        fields: dict[str, np.ndarray],
        bases: BasisData,
        carrier_tangent: np.ndarray,
        gauge_noncarrier: np.ndarray,
        device: torch.device,
    ) -> None:
        constraint = np.zeros((N_GAUGE, N_BASE), dtype=np.float64)
        constraint[:, :N_NONCARRIER] = gauge_noncarrier.T
        _, _, pivots = qr(constraint, mode="economic", pivoting=True, check_finite=False)
        self.pivot = np.asarray(pivots[:N_GAUGE], dtype=np.int64)
        self.free = np.asarray(pivots[N_GAUGE:], dtype=np.int64)
        pivot_block = constraint[:, self.pivot]
        free_block = constraint[:, self.free]
        self.transform = np.linalg.solve(pivot_block, -free_block)
        parameterization_residual = float(
            np.max(np.abs(pivot_block @ self.transform + free_block))
        )
        pivot_condition = float(np.linalg.cond(pivot_block))
        transform_norm = float(np.linalg.norm(self.transform, ord=2))
        if pivot_condition > 1.0e3 or parameterization_residual > 1.0e-10:
            raise VerificationFailure(
                f"independent quotient parameterization failure: condition={pivot_condition}, "
                f"residual={parameterization_residual}"
            )
        metric_core = np.eye(N_GAUGE) + self.transform @ self.transform.T
        self.metric_cholesky = cho_factor(metric_core, lower=True, check_finite=False)
        probe = np.random.default_rng(88031).normal(size=N_PHYS)
        inverse_residual = float(
            np.linalg.norm(self.metric(self.metric_inverse(probe)) - probe) / np.linalg.norm(probe)
        )
        if inverse_residual > 1.0e-10:
            raise VerificationFailure(f"independent metric inverse residual {inverse_residual}")

        self.constraint = constraint
        self.device = device
        self.grid = make_grid(device)
        self.background = {
            name: torch.as_tensor(value, dtype=torch.float64, device=device)
            for name, value in fields.items()
        }
        self.scalar_index_t = torch.as_tensor(bases.scalar_index, dtype=torch.long, device=device)
        self.scalar_weight_t = torch.as_tensor(
            bases.scalar_weight, dtype=torch.float64, device=device
        )
        self.vector_index_t = torch.as_tensor(bases.vector_index, dtype=torch.long, device=device)
        self.vector_matrix_t = torch.as_tensor(
            bases.vector_matrix, dtype=torch.float64, device=device
        )
        self.carrier_tangent_t = torch.as_tensor(
            carrier_tangent, dtype=torch.float64, device=device
        )
        self.pivot_t = torch.as_tensor(self.pivot, dtype=torch.long, device=device)
        self.free_t = torch.as_tensor(self.free, dtype=torch.long, device=device)
        self.transform_t = torch.as_tensor(self.transform, dtype=torch.float64, device=device)
        self.diagnostics = {
            "constraint_shape": list(constraint.shape),
            "pivot_condition_2": pivot_condition,
            "transform_shape": list(self.transform.shape),
            "transform_norm_2": transform_norm,
            "parameterization_residual_max": parameterization_residual,
            "metric_inverse_probe_relative": inverse_residual,
            "base_dimension": N_BASE,
            "physical_dimension": N_PHYS,
        }

    def metric(self, vector: np.ndarray) -> np.ndarray:
        return vector + self.transform.T @ (self.transform @ vector)

    def metric_inverse(self, vector: np.ndarray) -> np.ndarray:
        middle = cho_solve(
            self.metric_cholesky, self.transform @ vector, check_finite=False
        )
        return vector - self.transform.T @ middle

    def normalize(self, vector: np.ndarray) -> np.ndarray:
        norm = math.sqrt(float(vector @ self.metric(vector)))
        if not math.isfinite(norm) or norm == 0.0:
            raise VerificationFailure("cannot metric-normalize independent quotient vector")
        return vector / norm

    def base_from_quotient_np(self, vector: np.ndarray) -> np.ndarray:
        base = np.empty(N_BASE, dtype=np.float64)
        base[self.free] = vector
        base[self.pivot] = self.transform @ vector
        return base

    def base_from_quotient_torch(self, vector: torch.Tensor) -> torch.Tensor:
        base = torch.zeros(N_BASE, dtype=torch.float64, device=self.device)
        base = base.index_copy(0, self.free_t, vector)
        return base.index_copy(0, self.pivot_t, self.transform_t @ vector)

    def quotient_covector(self, base_covector: torch.Tensor) -> torch.Tensor:
        return (
            base_covector[self.free_t]
            + self.transform_t.T @ base_covector[self.pivot_t]
        )

    def scalar_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        return (self.scalar_weight_t * coefficients[self.scalar_index_t]).reshape(N, N, N)

    def vector_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        gathered = coefficients[self.vector_index_t, :]
        return torch.einsum("nis,nsc->nic", self.vector_matrix_t, gathered).reshape(
            N, N, N, 3, 3
        )

    def fields_from_base(self, base: torch.Tensor) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        scalar_coefficients = base[: 7 * NS].reshape(7, NS)
        scalar_changes = torch.stack(
            tuple(self.scalar_field(scalar_coefficients[index]) for index in range(7)),
            dim=-1,
        )
        gauge_coefficients = base[7 * NS : N_NONCARRIER].reshape(3, NV).T
        carrier_real_coefficients = self.carrier_tangent_t @ base[
            N_NONCARRIER : N_NONCARRIER + NS - 1
        ]
        carrier_imag_coefficients = base[N_NONCARRIER + NS - 1 :]
        fields = {
            "psi_real": self.background["psi_real"] + scalar_changes[..., 0:2],
            "psi_imag": self.background["psi_imag"] + scalar_changes[..., 2:4],
            "h": self.background["h"] + scalar_changes[..., 4:7],
            "a": self.background["a"] + self.vector_field(gauge_coefficients),
            "c": self.background["c"] + self.scalar_field(carrier_real_coefficients),
        }
        return fields, self.scalar_field(carrier_imag_coefficients)

    def lagrangian_from_base(
        self, base: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        fields, chi_imag = self.fields_from_base(base)
        components, _, _ = energy_components(fields, chi_imag, self.grid)
        physical = torch.stack(tuple(components.values())).sum()
        charge = torch.sum(fields["c"] ** 2 + chi_imag**2) * self.grid.dv
        return physical - OMEGA_C * charge, physical, charge

    def lagrangian(self, quotient: np.ndarray) -> float:
        vector = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        value, _, _ = self.lagrangian_from_base(self.base_from_quotient_torch(vector))
        return scalar(value)

    def gradient(self, quotient: np.ndarray) -> np.ndarray:
        vector = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        base = self.base_from_quotient_torch(vector).detach().requires_grad_(True)
        value, _, _ = self.lagrangian_from_base(base)
        base_gradient = torch.autograd.grad(value, base)[0]
        return (self.quotient_covector(base_gradient) / DV).detach().cpu().numpy()

    def hvp(self, quotient: np.ndarray) -> np.ndarray:
        direction = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        base_direction = self.base_from_quotient_torch(direction)
        base = torch.zeros(N_BASE, dtype=torch.float64, device=self.device, requires_grad=True)
        value, _, _ = self.lagrangian_from_base(base)
        first = torch.autograd.grad(value, base, create_graph=True)[0]
        second = torch.autograd.grad(torch.dot(first, base_direction), base)[0]
        return (self.quotient_covector(second) / DV).detach().cpu().numpy()

    def mode_fields(self, quotient: np.ndarray) -> dict[str, np.ndarray]:
        base = torch.as_tensor(
            self.base_from_quotient_np(quotient), dtype=torch.float64, device=self.device
        )
        fields, chi_imag = self.fields_from_base(base)
        return {
            "psi_real": (fields["psi_real"] - self.background["psi_real"]).detach().cpu().numpy(),
            "psi_imag": (fields["psi_imag"] - self.background["psi_imag"]).detach().cpu().numpy(),
            "h": (fields["h"] - self.background["h"]).detach().cpu().numpy(),
            "a": (fields["a"] - self.background["a"]).detach().cpu().numpy(),
            "chi_real": (fields["c"] - self.background["c"]).detach().cpu().numpy(),
            "chi_imag": chi_imag.detach().cpu().numpy(),
        }


def load_background(
    device: torch.device, grid: Grid
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if sha256_file(ARTIFACT) != ARTIFACT_SHA256:
        raise VerificationFailure("independent selected-artifact hash mismatch")
    expected_shapes = {
        "x": (N,),
        "psi_real": (N, N, N, 2),
        "psi_imag": (N, N, N, 2),
        "h": (N, N, N, 3),
        "a": (N, N, N, 3, 3),
        "c": (N, N, N),
    }
    with np.load(ARTIFACT, allow_pickle=False) as archive:
        if set(archive.files) != set(expected_shapes):
            raise VerificationFailure(
                f"independent artifact keys {sorted(archive.files)} != {sorted(expected_shapes)}"
            )
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    schema: dict[str, Any] = {}
    for name, shape in expected_shapes.items():
        value = arrays[name]
        schema[name] = {
            "shape": list(value.shape),
            "dtype": str(value.dtype),
            "c_contiguous": bool(value.flags.c_contiguous),
            "finite": bool(np.all(np.isfinite(value))),
        }
        if value.shape != shape or value.dtype != np.float64 or not value.flags.c_contiguous:
            raise VerificationFailure(f"independent artifact schema failure for {name}: {schema[name]}")
        if not np.all(np.isfinite(value)):
            raise VerificationFailure(f"independent nonfinite artifact array {name}")
    if np.max(np.abs(arrays["x"] - np.linspace(-4.0, 4.0, N))) > 1.0e-14:
        raise VerificationFailure("independent artifact coordinate mismatch")

    fields_np = {name: arrays[name] for name in ("psi_real", "psi_imag", "h", "a", "c")}
    shell_residuals = {
        "psi_real": boundary_max(
            fields_np["psi_real"] - np.asarray((PHI**-0.5, PHI**-1.0))
        ),
        "psi_imag": boundary_max(fields_np["psi_imag"]),
        "h": boundary_max(fields_np["h"] - np.asarray((0.0, 0.0, 1.0))),
        "a": boundary_max(fields_np["a"]),
        "c": boundary_max(fields_np["c"]),
    }
    c4_residuals = {
        "psi_real": projection_residual(fields_np["psi_real"], scalar_c4(fields_np["psi_real"])),
        "psi_imag": projection_residual(fields_np["psi_imag"], scalar_c4(fields_np["psi_imag"])),
        "h": projection_residual(fields_np["h"], scalar_c4(fields_np["h"])),
        "a": projection_residual(fields_np["a"], vector_c4(fields_np["a"])),
        "c": projection_residual(fields_np["c"], scalar_c4(fields_np["c"])),
    }
    if max(shell_residuals.values()) > 1.0e-12 or max(c4_residuals.values()) > 5.0e-12:
        raise VerificationFailure(
            f"independent boundary/C4 failure: shell={shell_residuals}, C4={c4_residuals}"
        )

    fields_t = {
        name: torch.as_tensor(value, dtype=torch.float64, device=device)
        for name, value in fields_np.items()
    }
    components, gauge_fixing, _ = energy_components(
        fields_t, torch.zeros_like(fields_t["c"]), grid
    )
    physical_energy = scalar(torch.stack(tuple(components.values())).sum())
    charge = scalar(torch.sum(fields_t["c"] ** 2) * grid.dv)
    omega = scalar(
        (
            components["carrier_gradient"]
            + components["carrier_quadratic"]
            + 2.0 * components["carrier_quartic"]
        )
        / charge
    )
    gradient_rms = physical_gradient_rms(fields_t, grid)
    virial, formal_virial, directional = cutoff_virial(fields_t, grid, components)
    measured = {
        "physical_energy": physical_energy,
        "physical_gradient_rms": gradient_rms,
        "cutoff_virial": virial,
        "omega_c": omega,
        "charge": charge,
    }
    comparisons: dict[str, Any] = {}
    for name, frozen in FROZEN_BACKGROUND.items():
        error = abs(measured[name] - frozen)
        tolerance = 1.0e-11 + 1.0e-9 * abs(frozen)
        comparisons[name] = {
            "measured": measured[name],
            "frozen": frozen,
            "absolute_error": error,
            "tolerance": tolerance,
            "pass": error <= tolerance,
        }
        if error > tolerance:
            raise VerificationFailure(
                f"independent frozen-background mismatch for {name}: {comparisons[name]}"
            )
    if abs(charge - 4.0) / 4.0 > 1.0e-12:
        raise VerificationFailure(f"independent charge mismatch: {charge}")
    return fields_np, {
        "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": ARTIFACT_SHA256,
        "schema": schema,
        "shell_residuals": shell_residuals,
        "c4_residuals": c4_residuals,
        "scalars": comparisons,
        "gauge_fixing_diagnostic": scalar(gauge_fixing),
        "formal_virial_diagnostic": formal_virial,
        "virial_directional_terms": directional,
        "coefficient_point": COEFFICIENTS,
    }


def directional_check(
    space: IndependentSpace, direction: np.ndarray
) -> dict[str, Any]:
    direction = space.normalize(direction)
    exact = space.hvp(direction)
    exact_curvature = float(direction @ exact)
    zero_lagrangian = space.lagrangian(np.zeros(N_PHYS, dtype=np.float64))
    steps: list[dict[str, float]] = []
    for step in STEPS:
        finite_hvp = (
            space.gradient(step * direction) - space.gradient(-step * direction)
        ) / (2.0 * step)
        vector_error = float(
            np.linalg.norm(finite_hvp - exact) / max(np.linalg.norm(exact), 1.0)
        )
        energy_curvature = (
            space.lagrangian(step * direction)
            - 2.0 * zero_lagrangian
            + space.lagrangian(-step * direction)
        ) / (step**2 * DV)
        curvature_error = abs(energy_curvature - exact_curvature)
        curvature_tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
        steps.append(
            {
                "step": step,
                "vector_relative_error": vector_error,
                "energy_curvature": energy_curvature,
                "exact_curvature": exact_curvature,
                "curvature_error": curvature_error,
                "curvature_tolerance": curvature_tolerance,
            }
        )
    step_agreement = abs(steps[-1]["energy_curvature"] - steps[-2]["energy_curvature"])
    step_tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
    passed = (
        steps[-1]["vector_relative_error"] <= 5.0e-5
        and steps[-1]["curvature_error"] <= steps[-1]["curvature_tolerance"]
        and step_agreement <= step_tolerance
    )
    return {
        "metric_norm": float(direction @ space.metric(direction)),
        "exact_curvature": exact_curvature,
        "steps": steps,
        "two_smallest_energy_curvature_difference": step_agreement,
        "step_agreement_tolerance": step_tolerance,
        "pass": passed,
    }


def directional_preflight(space: IndependentSpace) -> dict[str, Any]:
    rng = np.random.default_rng(161803)
    rows = []
    for index in range(3):
        row = directional_check(space, rng.normal(size=N_PHYS))
        row["direction"] = index
        rows.append(row)
    return {"seed": 161803, "directions": rows, "pass": all(row["pass"] for row in rows)}


def operator_preflight(
    space: IndependentSpace, carrier_reduced: np.ndarray
) -> tuple[dict[str, Any], np.ndarray]:
    zero = np.zeros(N_PHYS, dtype=np.float64)
    gradient = space.gradient(zero)
    augmented_gradient_rms = math.sqrt(
        float(gradient @ space.metric_inverse(gradient)) / N_PHYS
    )
    rng = np.random.default_rng(61927)
    symmetry_rows: list[dict[str, float]] = []
    for index in range(4):
        left = space.normalize(rng.normal(size=N_PHYS))
        right = space.normalize(rng.normal(size=N_PHYS))
        h_left = space.hvp(left)
        h_right = space.hvp(right)
        left_right = float(left @ h_right)
        right_left = float(right @ h_left)
        relative = abs(left_right - right_left) / max(abs(left_right), abs(right_left), 1.0)
        symmetry_rows.append(
            {
                "pair": index,
                "left_K_right": left_right,
                "right_K_left": right_left,
                "relative_error": relative,
            }
        )
    symmetry_pass = all(row["relative_error"] <= 1.0e-9 for row in symmetry_rows)

    phase_base = np.zeros(N_BASE, dtype=np.float64)
    phase_base[N_NONCARRIER + NS - 1 :] = carrier_reduced / np.linalg.norm(carrier_reduced)
    phase = phase_base[space.free]
    reproduction = float(np.linalg.norm(space.base_from_quotient_np(phase) - phase_base))
    phase = space.normalize(phase)
    phase_hvp = space.hvp(phase)
    phase_rayleigh = float(phase @ phase_hvp)
    passed = (
        augmented_gradient_rms <= 3.0e-4
        and symmetry_pass
        and abs(phase_rayleigh) <= 1.0e-10
        and reproduction <= 1.0e-11
    )
    return (
        {
            "augmented_gradient_rms": augmented_gradient_rms,
            "augmented_gradient_limit": 3.0e-4,
            "operator_symmetry": symmetry_rows,
            "operator_symmetry_pass": symmetry_pass,
            "phase_generator_reproduction": reproduction,
            "phase_rayleigh": phase_rayleigh,
            "phase_hessian_residual": float(np.linalg.norm(phase_hvp)),
            "phase_rayleigh_limit": 1.0e-10,
            "static_gauss_rank": 0,
            "pass": passed,
        },
        phase,
    )


def build_campaign_state(
    device: torch.device,
) -> tuple[
    dict[str, np.ndarray],
    IndependentSpace,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    np.ndarray,
]:
    grid = make_grid(device)
    fields, background = load_background(device, grid)
    bases, basis_diagnostics = build_bases()
    alpha_null, boundary_gauge = boundary_gauge_basis(bases)
    carrier_tangent, carrier_reduced, carrier = carrier_tangent_basis(fields["c"], bases)
    gauge, coupled_gauge = coupled_gauge_matrix(fields, bases, alpha_null)
    space = IndependentSpace(fields, bases, carrier_tangent, gauge, device)
    return (
        fields,
        space,
        background,
        basis_diagnostics,
        boundary_gauge,
        carrier,
        coupled_gauge,
        carrier_reduced,
    )


def environment_receipt(device: torch.device) -> dict[str, Any]:
    return {
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "torch": torch.__version__,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "PYTORCH_HIP_ALLOC_CONF": os.environ.get("PYTORCH_HIP_ALLOC_CONF"),
        "HSA_ENABLE_SDMA": os.environ.get("HSA_ENABLE_SDMA"),
    }


def run_preflight() -> int:
    started = time.perf_counter()
    manifest, manifest_hash = verify_manifest()
    device = configure_torch()
    (
        _,
        space,
        background,
        bases,
        boundary_gauge,
        carrier,
        coupled_gauge,
        carrier_reduced,
    ) = build_campaign_state(device)
    operator, _ = operator_preflight(space, carrier_reduced)
    directional = directional_preflight(space)
    h1 = all(row["pass"] for row in background["scalars"].values())
    h2 = (
        bases["scalar_dimension"] == NS
        and bases["vector_dimension"] == NV
        and boundary_gauge["rank"] == 296
        and boundary_gauge["null_dimension"] == N_ALPHA
        and coupled_gauge["rank"] == N_GAUGE
        and space.diagnostics["physical_dimension"] == N_PHYS
        and space.diagnostics["pivot_condition_2"] <= 1.0e3
        and space.diagnostics["parameterization_residual_max"] <= 1.0e-10
    )
    h3 = bool(operator["pass"] and directional["pass"])
    receipt = {
        "schema": "cassi.particle-physical-hessian.preflight.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": environment_receipt(device),
        "background": background,
        "basis": bases,
        "boundary_gauge": boundary_gauge,
        "carrier_tangent": carrier,
        "coupled_gauge": coupled_gauge,
        "quotient": space.diagnostics,
        "operator": operator,
        "directional": directional,
        "gates": {"H1": h1, "H2": h2, "H3": h3},
        "pass": bool(h1 and h2 and h3),
        "wall_seconds": time.perf_counter() - started,
    }
    write_json(PREFLIGHT_PATH, receipt)
    print(
        json.dumps(
            {
                "pass": receipt["pass"],
                "gates": receipt["gates"],
                "augmented_gradient_rms": operator["augmented_gradient_rms"],
                "phase_rayleigh": operator["phase_rayleigh"],
                "wall_seconds": receipt["wall_seconds"],
            },
            indent=2,
        )
    )
    if not receipt["pass"]:
        raise VerificationFailure(f"independent preflight gates failed: {receipt['gates']}")
    return 0


def full_component_stack(mode: dict[str, np.ndarray]) -> np.ndarray:
    return np.concatenate(
        (
            mode["psi_real"],
            mode["psi_imag"],
            mode["h"],
            mode["a"].reshape(N, N, N, 9),
            mode["chi_real"][..., None],
            mode["chi_imag"][..., None],
        ),
        axis=-1,
    )


def normalized_overlap(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return abs(float(np.sum(left * right))) / denominator if denominator else 0.0


def symmetry_probes(fields: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    background = np.concatenate(
        (
            fields["psi_real"],
            fields["psi_imag"],
            fields["h"],
            fields["a"].reshape(N, N, N, 9),
            fields["c"][..., None],
            np.zeros((N, N, N, 1), dtype=np.float64),
        ),
        axis=-1,
    )
    gradients = np.gradient(background, DX, axis=(0, 1, 2), edge_order=2)
    coordinates = np.linspace(-4.0, 4.0, N)
    x, y, _ = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    axial = -(x[..., None] * gradients[1] - y[..., None] * gradients[0])
    axial_a = axial[..., 7:16].reshape(N, N, N, 3, 3)
    generator = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    axial_a += np.einsum("ij,...ja->...ia", generator, fields["a"])
    axial[..., 7:16] = axial_a.reshape(N, N, N, 9)
    global_phase = np.zeros_like(background)
    global_phase[..., -1] = fields["c"]
    charge_normal = np.zeros_like(background)
    charge_normal[..., -2] = fields["c"]
    return {
        "translation_x": -gradients[0],
        "translation_y": -gradients[1],
        "translation_z": -gradients[2],
        "axial_rotation": axial,
        "global_u1": global_phase,
        "charge_normal": charge_normal,
    }


def mode_diagnostics(
    space: IndependentSpace,
    quotient: np.ndarray,
    mode: dict[str, np.ndarray],
    probes: dict[str, np.ndarray],
) -> dict[str, Any]:
    base = space.base_from_quotient_np(quotient)
    stacked = full_component_stack(mode)
    node_power = np.sum(stacked**2, axis=-1)
    participation = float(np.sum(node_power) ** 2 / np.sum(node_power**2))
    frequencies = np.fft.fftfreq(N, d=DX)
    high_axis = np.abs(frequencies) >= 0.75 * (1.0 / (2.0 * DX))
    high_mask = high_axis[:, None, None] | high_axis[None, :, None] | high_axis[None, None, :]
    total_fft = 0.0
    high_fft = 0.0
    for component in range(FIELD_COMPONENTS):
        spectrum = np.fft.fftn(stacked[..., component])
        power = np.abs(spectrum) ** 2
        total_fft += float(np.sum(power))
        high_fft += float(np.sum(power[high_mask]))
    group_norms = {
        "psi": float(np.sum(mode["psi_real"] ** 2) + np.sum(mode["psi_imag"] ** 2)),
        "h": float(np.sum(mode["h"] ** 2)),
        "a": float(np.sum(mode["a"] ** 2)),
        "chi_real": float(np.sum(mode["chi_real"] ** 2)),
        "chi_imag": float(np.sum(mode["chi_imag"] ** 2)),
    }
    total_norm = sum(group_norms.values())
    carrier = space.background["c"].detach().cpu().numpy()
    charge_tangent = abs(float(np.sum(carrier * mode["chi_real"]))) / max(
        float(np.linalg.norm(carrier) * np.linalg.norm(mode["chi_real"])), 1.0
    )
    return {
        "participation": participation,
        "high_frequency_fraction": high_fft / total_fft,
        "spatially_resolved": participation >= 16.0 and high_fft / total_fft <= 0.20,
        "component_fractions": {name: value / total_norm for name, value in group_norms.items()},
        "shell_max": boundary_max(stacked),
        "charge_tangent_relative": charge_tangent,
        "gauge_orthogonality_relative": float(
            np.linalg.norm(space.constraint @ base) / max(np.linalg.norm(base), 1.0)
        ),
        "metric_norm": float(quotient @ space.metric(quotient)),
        "overlaps": {name: normalized_overlap(stacked, probe) for name, probe in probes.items()},
    }


def independent_eigensolve(
    space: IndependentSpace, fields: dict[str, np.ndarray]
) -> tuple[dict[str, Any], np.ndarray, list[dict[str, Any]]]:
    operator = LinearOperator((N_PHYS, N_PHYS), matvec=space.hvp, rmatvec=space.hvp, dtype=np.float64)
    metric = LinearOperator(
        (N_PHYS, N_PHYS), matvec=space.metric, rmatvec=space.metric, dtype=np.float64
    )
    metric_inverse = LinearOperator(
        (N_PHYS, N_PHYS),
        matvec=space.metric_inverse,
        rmatvec=space.metric_inverse,
        dtype=np.float64,
    )
    initial = space.normalize(np.random.default_rng(314159).normal(size=N_PHYS))
    started = time.perf_counter()
    try:
        values, vectors = eigsh(
            operator,
            k=6,
            M=metric,
            Minv=metric_inverse,
            which="SA",
            ncv=32,
            tol=1.0e-9,
            maxiter=2000,
            v0=initial,
            return_eigenvectors=True,
        )
    except ArpackNoConvergence as exc:
        raise VerificationFailure(
            f"independent ARPACK did not converge: {len(exc.eigenvalues)} partial eigenvalues"
        ) from exc
    order = np.argsort(values)
    values = np.asarray(values[order], dtype=np.float64)
    vectors = np.asarray(vectors[:, order], dtype=np.float64)
    gram = vectors.T @ np.column_stack([space.metric(vectors[:, index]) for index in range(6)])
    orthogonality = float(np.max(np.abs(gram - np.eye(6))))
    if orthogonality > 1.0e-8:
        raise VerificationFailure(f"independent metric orthogonality residual {orthogonality}")

    probes = symmetry_probes(fields)
    zero_lagrangian = space.lagrangian(np.zeros(N_PHYS, dtype=np.float64))
    modes: list[dict[str, Any]] = []
    for index in range(6):
        vector = vectors[:, index]
        k_vector = space.hvp(vector)
        m_vector = space.metric(vector)
        residual_vector = k_vector - values[index] * m_vector
        residual_absolute = float(np.linalg.norm(residual_vector))
        residual_relative = residual_absolute / max(
            abs(float(values[index])) * float(np.linalg.norm(m_vector)), 1.0
        )
        if residual_relative > 1.0e-6:
            raise VerificationFailure(
                f"independent eigenpair {index} residual {residual_relative}"
            )
        step = STEPS[-1]
        energy_curvature = (
            space.lagrangian(step * vector)
            - 2.0 * zero_lagrangian
            + space.lagrangian(-step * vector)
        ) / (step**2 * DV)
        diagnostic = mode_diagnostics(space, vector, space.mode_fields(vector), probes)
        diagnostic.update(
            {
                "index": index,
                "eigenvalue": float(values[index]),
                "residual_absolute": residual_absolute,
                "residual_relative": residual_relative,
                "exact_directional_curvature": float(vector @ k_vector),
                "smallest_step_directional_curvature": energy_curvature,
            }
        )
        modes.append(diagnostic)
    return (
        {
            "settings": {
                "k": 6,
                "which": "SA",
                "ncv": 32,
                "tolerance": 1.0e-9,
                "maxiter": 2000,
                "seed": 314159,
            },
            "wall_seconds": time.perf_counter() - started,
            "eigenvalues": [float(value) for value in values],
            "max_absolute_residual": max(mode["residual_absolute"] for mode in modes),
            "metric_orthogonality_max": orthogonality,
            "finite": bool(np.all(np.isfinite(values)) and np.all(np.isfinite(vectors))),
            "modes": modes,
        },
        vectors,
        modes,
    )


def mode_contract(mode: dict[str, Any]) -> bool:
    return bool(
        mode["shell_max"] <= 1.0e-12
        and mode["charge_tangent_relative"] <= 1.0e-11
        and mode["gauge_orthogonality_relative"] <= 1.0e-10
        and abs(mode["metric_norm"] - 1.0) <= 1.0e-10
    )


def collect_fd_disagreements(
    primary: dict[str, Any], preflight: dict[str, Any], independent_modes: list[dict[str, Any]],
    primary_lowest_check: dict[str, Any],
) -> list[float]:
    disagreements: list[float] = []
    for source in (primary["directional_preflight"], preflight["directional"]):
        for row in source["directions"]:
            disagreements.append(float(row["steps"][-1]["curvature_error"]))
            disagreements.append(float(row["two_smallest_energy_curvature_difference"]))
    for mode in primary["spectrum"]["modes"][:6]:
        disagreements.append(
            abs(
                float(mode["smallest_step_directional_curvature"])
                - float(mode["exact_directional_curvature"])
            )
        )
    for mode in independent_modes:
        disagreements.append(
            abs(
                float(mode["smallest_step_directional_curvature"])
                - float(mode["exact_directional_curvature"])
            )
        )
    disagreements.append(float(primary_lowest_check["steps"][-1]["curvature_error"]))
    disagreements.append(
        float(primary_lowest_check["two_smallest_energy_curvature_difference"])
    )
    return disagreements


def run_final_verification() -> int:
    started = time.perf_counter()
    manifest, manifest_hash = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise VerificationFailure("independent preflight receipt is missing")
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    if not preflight.get("pass") or preflight.get("manifest_sha256") != manifest_hash:
        raise VerificationFailure("independent preflight receipt does not match the frozen manifest")
    if not RESULTS_PATH.is_file() or not MODES_PATH.is_file():
        raise VerificationFailure("primary Hessian results or modes are missing")
    primary = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    if primary.get("manifest_sha256") != manifest_hash:
        raise VerificationFailure("primary Hessian result used a different manifest")
    if primary.get("primary_status") != "PENDING—INDEPENDENT VERIFICATION":
        raise VerificationFailure(f"unexpected primary status: {primary.get('primary_status')}")
    modes_hash = sha256_file(MODES_PATH)
    if primary.get("artifacts", {}).get("eigenmodes_sha256") != modes_hash:
        raise VerificationFailure("primary eigenmode archive hash mismatch")

    device = configure_torch()
    (
        fields,
        space,
        background,
        bases,
        boundary_gauge,
        carrier,
        coupled_gauge,
        carrier_reduced,
    ) = build_campaign_state(device)
    operator, phase = operator_preflight(space, carrier_reduced)
    directional = directional_preflight(space)
    if not operator["pass"] or not directional["pass"]:
        raise VerificationFailure("independent final-pass Hessian preflight failed")

    with np.load(MODES_PATH, allow_pickle=False) as archive:
        required = {
            "eigenvalues",
            "quotient_vectors",
            "base_vectors",
            "pivot_indices",
            "free_indices",
            "global_u1_quotient_vector",
            "psi_real",
            "psi_imag",
            "h",
            "a",
            "chi_real",
            "chi_imag",
        }
        if set(archive.files) != required:
            raise VerificationFailure(
                f"primary eigenmode keys {sorted(archive.files)} != {sorted(required)}"
            )
        saved = {name: np.asarray(archive[name]) for name in archive.files}
    expected_shapes = {
        "eigenvalues": (12,),
        "quotient_vectors": (N_PHYS, 12),
        "base_vectors": (N_BASE, 12),
        "pivot_indices": (N_GAUGE,),
        "free_indices": (N_PHYS,),
        "global_u1_quotient_vector": (N_PHYS,),
        "psi_real": (12, N, N, N, 2),
        "psi_imag": (12, N, N, N, 2),
        "h": (12, N, N, N, 3),
        "a": (12, N, N, N, 3, 3),
        "chi_real": (12, N, N, N),
        "chi_imag": (12, N, N, N),
    }
    for name, shape in expected_shapes.items():
        if saved[name].shape != shape or not np.all(np.isfinite(saved[name])):
            raise VerificationFailure(
                f"primary eigenmode schema failure for {name}: {saved[name].shape}"
            )
    if not np.array_equal(saved["pivot_indices"], space.pivot) or not np.array_equal(
        saved["free_indices"], space.free
    ):
        raise VerificationFailure("primary and independent quotient coordinates differ")
    if np.linalg.norm(saved["global_u1_quotient_vector"] - phase) > 1.0e-10:
        raise VerificationFailure("primary and independent global phase generators differ")

    primary_values = np.asarray(primary["spectrum"]["eigenvalues"], dtype=np.float64)
    primary_all_modes = primary["spectrum"]["modes"]
    if primary_values.shape != (12,) or len(primary_all_modes) != 12:
        raise VerificationFailure("primary JSON spectrum does not contain twelve modes")
    if not np.allclose(primary_values, saved["eigenvalues"], rtol=0.0, atol=0.0):
        raise VerificationFailure("primary JSON and NPZ eigenvalues differ")
    reconstruction_max = 0.0
    for index in range(6):
        expected_mode = space.mode_fields(saved["quotient_vectors"][:, index])
        for name in ("psi_real", "psi_imag", "h", "a", "chi_real", "chi_imag"):
            reconstruction_max = max(
                reconstruction_max,
                float(np.max(np.abs(expected_mode[name] - saved[name][index]))),
            )
    if reconstruction_max > 1.0e-10:
        raise VerificationFailure(f"primary full-grid mode reconstruction residual {reconstruction_max}")

    independent, _, independent_modes = independent_eigensolve(space, fields)
    comparisons: list[dict[str, Any]] = []
    for index, independent_value in enumerate(independent["eigenvalues"]):
        primary_value = float(primary_values[index])
        difference = abs(primary_value - independent_value)
        tolerance = 5.0e-6 + 5.0e-4 * abs(independent_value)
        comparisons.append(
            {
                "index": index,
                "primary": primary_value,
                "independent": independent_value,
                "absolute_difference": difference,
                "tolerance": tolerance,
                "pass": difference <= tolerance,
            }
        )

    primary_lowest_check = directional_check(space, saved["quotient_vectors"][:, 0])
    primary_modes = primary_all_modes[:6]
    primary_contracts = [mode_contract(mode) for mode in primary_all_modes]
    independent_contracts = [mode_contract(mode) for mode in independent_modes]
    primary_residuals_pass = all(
        float(mode["residual_relative"]) <= 1.0e-6 for mode in primary_all_modes
    )
    independent_residuals_pass = all(
        float(mode["residual_relative"]) <= 1.0e-6 for mode in independent_modes
    )
    h4 = bool(
        primary["spectrum"]["finite"]
        and independent["finite"]
        and primary["spectrum"]["metric_orthogonality_max"] <= 1.0e-8
        and independent["metric_orthogonality_max"] <= 1.0e-8
        and primary_residuals_pass
        and independent_residuals_pass
        and all(row["pass"] for row in comparisons)
        and all(primary_contracts)
        and all(independent_contracts)
        and primary_lowest_check["pass"]
    )

    eigenvalue_difference = max(row["absolute_difference"] for row in comparisons)
    fd_disagreements = collect_fd_disagreements(
        primary, preflight, independent_modes, primary_lowest_check
    )
    augmented_gradient_rms = max(
        float(primary["operator_preflight"]["augmented_gradient_rms"]),
        float(operator["augmented_gradient_rms"]),
    )
    uncertainty = max(
        10.0 * max(float(mode["residual_absolute"]) for mode in primary_modes),
        10.0 * independent["max_absolute_residual"],
        10.0 * eigenvalue_difference,
        10.0 * max(fd_disagreements),
        10.0 * augmented_gradient_rms,
        1.0e-6,
    )
    classifications: list[dict[str, Any]] = []
    for index in range(6):
        primary_value = float(primary_values[index])
        independent_value = float(independent["eigenvalues"][index])
        primary_curvature = float(primary_modes[index]["smallest_step_directional_curvature"])
        independent_curvature = float(
            independent_modes[index]["smallest_step_directional_curvature"]
        )
        if (
            primary_value + uncertainty < 0.0
            and independent_value + uncertainty < 0.0
            and primary_curvature + uncertainty < 0.0
            and independent_curvature + uncertainty < 0.0
        ):
            classification = "negative"
        elif (
            primary_value - uncertainty > 0.0
            and independent_value - uncertainty > 0.0
            and primary_curvature - uncertainty > 0.0
            and independent_curvature - uncertainty > 0.0
        ):
            classification = "positive"
        else:
            classification = "near-zero"
        u1_overlap = min(
            float(primary_modes[index]["overlaps"]["global_u1"]),
            float(independent_modes[index]["overlaps"]["global_u1"]),
        )
        classifications.append(
            {
                "index": index,
                "classification": classification,
                "primary_eigenvalue": primary_value,
                "independent_eigenvalue": independent_value,
                "primary_smallest_step_curvature": primary_curvature,
                "independent_smallest_step_curvature": independent_curvature,
                "global_u1_overlap_min": u1_overlap,
                "primary_spatially_resolved": bool(primary_modes[index]["spatially_resolved"]),
                "independent_spatially_resolved": bool(
                    independent_modes[index]["spatially_resolved"]
                ),
            }
        )

    negative = [row for row in classifications if row["classification"] == "negative"]
    near_zero = [row for row in classifications if row["classification"] == "near-zero"]
    positive = [row for row in classifications if row["classification"] == "positive"]
    h5 = not negative
    h6 = bool(
        h5
        and len(near_zero) == 1
        and near_zero[0]["global_u1_overlap_min"] >= 0.90
        and len(positive) == 5
    )
    classified_nonpositive = negative + near_zero
    h7 = all(
        row["primary_spatially_resolved"] and row["independent_spatially_resolved"]
        for row in classified_nonpositive
    )
    h1 = bool(preflight["gates"]["H1"])
    h2 = bool(preflight["gates"]["H2"])
    h3 = bool(preflight["gates"]["H3"] and operator["pass"] and directional["pass"])
    gates = {"H1": h1, "H2": h2, "H3": h3, "H4": h4, "H5": h5, "H6": h6, "H7": h7}
    if not h1:
        verdict = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    elif not h2:
        verdict = "INCONCLUSIVE—GAUGE QUOTIENT"
    elif not h3:
        verdict = "INCONCLUSIVE—HESSIAN PREFLIGHT"
    elif not h4:
        verdict = "INCONCLUSIVE—EIGENSOLVER OR VERIFICATION"
    elif not h5:
        verdict = "FAIL—NEGATIVE PHYSICAL MODE"
    elif not h6:
        verdict = "INCONCLUSIVE—UNRESOLVED PHYSICAL ZERO MODE"
    else:
        verdict = "PASS—NONNEGATIVE C4 FINITE-GRID PA42 HESSIAN"
    if negative and not h7:
        spatial_verdict = "INCONCLUSIVE—GRID-SCALE NEGATIVE MODE"
    elif classified_nonpositive and not h7:
        spatial_verdict = "INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE"
    else:
        spatial_verdict = "PASS—CLASSIFIED MODES SPATIALLY RESOLVED"

    receipt = {
        "schema": "cassi.particle-physical-hessian.verification.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": environment_receipt(device),
        "preflight_sha256": sha256_file(PREFLIGHT_PATH),
        "primary_results_sha256": sha256_file(RESULTS_PATH),
        "eigenmodes_sha256": modes_hash,
        "background": background,
        "basis": bases,
        "boundary_gauge": boundary_gauge,
        "carrier_tangent": carrier,
        "coupled_gauge": coupled_gauge,
        "quotient": space.diagnostics,
        "operator": operator,
        "directional": directional,
        "independent_spectrum": independent,
        "primary_eigenvalue_comparison": comparisons,
        "primary_lowest_mode_directional_check": primary_lowest_check,
        "primary_mode_archive_reconstruction_max": reconstruction_max,
        "primary_mode_contracts": primary_contracts,
        "independent_mode_contracts": independent_contracts,
        "uncertainty": {
            "epsilon_lambda": uncertainty,
            "primary_max_absolute_residual": max(
                float(mode["residual_absolute"]) for mode in primary_modes
            ),
            "independent_max_absolute_residual": independent["max_absolute_residual"],
            "max_eigenvalue_difference": eigenvalue_difference,
            "max_fd_curvature_disagreement": max(fd_disagreements),
            "augmented_gradient_rms": augmented_gradient_rms,
        },
        "classifications": classifications,
        "gates": gates,
        "verdict": verdict,
        "spatial_verdict": spatial_verdict,
        "domain_resolution_verdict": "INCONCLUSIVE—NO Q2 DOMAIN/RESOLUTION BACKGROUNDS",
        "wall_seconds": time.perf_counter() - started,
    }
    write_json(VERIFICATION_PATH, receipt)
    print(
        json.dumps(
            {
                "verdict": verdict,
                "spatial_verdict": spatial_verdict,
                "domain_resolution_verdict": receipt["domain_resolution_verdict"],
                "gates": gates,
                "epsilon_lambda": uncertainty,
                "primary_eigenvalues": primary_values[:6].tolist(),
                "independent_eigenvalues": independent["eigenvalues"],
                "wall_seconds": receipt["wall_seconds"],
            },
            indent=2,
        )
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="run the frozen independent preflight without evaluating a spectrum",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    return run_preflight() if args.preflight else run_final_verification()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationFailure as exc:
        target = PREFLIGHT_PATH if "--preflight" in sys.argv else VERIFICATION_PATH
        write_json(
            target,
            {
                "schema": "cassi.particle-physical-hessian.failure.v1",
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pass": False,
                "error": str(exc),
            },
        )
        print(f"HESSIAN VERIFICATION FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
