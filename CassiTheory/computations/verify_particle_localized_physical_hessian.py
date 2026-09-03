#!/usr/bin/env python3
"""Independently verify the localized-carrier physical Hessian campaign.

This module does not import the primary Hessian driver, stationary optimizer,
recovery programs, or recovery verifiers. It separately implements the action,
tangent geometry, sparse gauge quotient, HVP, diagnostics, and eigensolve.

Run from the CassiTheory repository root:

    python computations/verify_particle_localized_physical_hessian.py --preflight
    python computations/verify_particle_localized_physical_hessian.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy import sparse
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigsh, splu


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz"
SOURCE_RESULTS = ROOT / "runs/20260902_particle_carrier_resolution_recovery/results.json"
SOURCE_VERIFICATION = ROOT / "runs/20260902_particle_carrier_resolution_recovery/verification.json"
RUN_DIR = ROOT / "runs/20260903_particle_localized_physical_hessian"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
MODES_PATH = RUN_DIR / "eigenmodes.npz"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations/particle_localized_physical_hessian_manifest.json"

ARTIFACT_SHA256 = "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
OMEGA_C = 0.0034164531971490053
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
    "h_C": 2.9598260763447164,
    "u_C": 1.0,
    "q_C": 4.0,
    "L_s": 1.0,
    "xi_gf": 1.0,
}
FROZEN_BACKGROUND = {
    "physical_energy": 1.5251878559994063,
    "physical_gradient_rms": 3.090108443313949e-7,
    "cutoff_virial": 9.092469919592924e-8,
    "omega_c": OMEGA_C,
    "charge": 4.0,
    "gauge_fixing_energy": 5.97271232511152e-11,
    "carrier_radius": 1.6314313026374387,
    "core_length": 2.2977937729044924,
    "outer_carrier_fraction": 1.0708172350337447e-4,
    "max_density_depletion": 0.9856286941942967,
    "negative_norm_fraction": 0.0,
}
SOURCE_HASHES = {
    "manifest": "8d1f18cb18d3635960ec7be1076688bcbd1f1fbc5fda1d86e851c46f8b3ff853",
    "results": "b22a6e4b84aa68d099c2eb9930aa10213a28826b852a74f7e7b6a044a93c66ca",
    "verification": "7a500585beb44430402987ef9b5cb990619462463161e42d03980ef9ba855b3c",
}
SOURCE_VERDICT = "EMERGES—THREE-LEVEL RESOLUTION-CONSISTENT LOCALIZED RETAINED BRANCH"

N = 29
M = 27
INNER = 25
R = 4.0
DX = 2.0 / 7.0
DV = DX**3
NS = 4941
NV = 14769
N_ALPHA = 3925
N_GAUGE = 11775
N_NONCARRIER = 78894
N_BASE = 88775
N_PHYS = 77000
FIELD_COMPONENTS = 18
GAUGE_LIFT = 8.0
STEPS = (2.0e-4, 1.0e-4, 5.0e-5)
PRIMARY_SETTINGS = {
    "k": 8,
    "which": "SA",
    "ncv": 40,
    "tolerance": 1.0e-9,
    "maxiter": 2000,
    "seed": 424242,
}
INDEPENDENT_SETTINGS = {
    "k": 6,
    "which": "SA",
    "ncv": 32,
    "tolerance": 1.0e-9,
    "maxiter": 2000,
    "seed": 314159,
}
EXPECTED_PROTOCOL = {
    "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
    "artifact_sha256": ARTIFACT_SHA256,
    "background": FROZEN_BACKGROUND,
    "coefficients": COEFFICIENTS,
    "grid": {"R": R, "N": N, "dx": DX, "dv": DV},
    "dimensions": {
        "scalar_c4": NS,
        "vector_c4": NV,
        "alpha_per_color": N_ALPHA,
        "gauge": N_GAUGE,
        "base": N_BASE,
        "physical": N_PHYS,
    },
    "gauge_lift": GAUGE_LIFT,
    "finite_difference_steps": list(STEPS),
    "primary_eigensolver": PRIMARY_SETTINGS,
    "independent_eigensolver": INDEPENDENT_SETTINGS,
    "source_hashes": SOURCE_HASHES,
    "source_verdict": SOURCE_VERDICT,
}
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
        data = path.read_bytes().replace(b"\r\n", b"\n")
        return hashlib.sha256(data).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        if value.ndim == 0:
            return value.item()
        raise TypeError(f"nonscalar ndarray at JSON boundary: {value.shape}")
    if isinstance(value, torch.Tensor):
        if value.numel() == 1:
            return value.detach().cpu().item()
        raise TypeError(f"nonscalar tensor at JSON boundary: {tuple(value.shape)}")
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def scalar(value: torch.Tensor) -> float:
    return float(value.detach().cpu())


def verify_manifest(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise VerificationFailure(f"missing frozen manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "cassi.particle-localized-physical-hessian.manifest.v1":
        raise VerificationFailure("manifest schema mismatch")
    if manifest.get("campaign") != "particle_localized_physical_hessian":
        raise VerificationFailure("manifest campaign mismatch")
    if manifest.get("protocol") != EXPECTED_PROTOCOL:
        raise VerificationFailure("manifest protocol differs from independent frozen constants")
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        raise VerificationFailure("manifest SHA-256 mapping is empty")
    mismatches: dict[str, dict[str, str]] = {}
    for relative, expected in hashes.items():
        path_from_root = ROOT / relative
        actual = sha256_file(path_from_root) if path_from_root.is_file() else "MISSING"
        if actual != expected:
            mismatches[relative] = {"expected": expected, "actual": actual}
    if mismatches:
        raise VerificationFailure(f"manifest source mismatch: {mismatches}")
    return manifest, sha256_file(path)


def configure_torch() -> torch.device:
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cuda"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise VerificationFailure("ROCm/CUDA PyTorch device is required")
    return torch.device("cuda:0")


@dataclass
class Grid:
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
    R: float
    N: int
    dx: float
    dv: float


def make_grid(device: torch.device) -> Grid:
    x = torch.linspace(-R, R, N, dtype=torch.float64, device=device)
    X, Y, Z = torch.meshgrid(x, x, x, indexing="ij")
    indices = torch.arange(N, device=device)
    ii, jj, kk = torch.meshgrid(indices, indices, indices, indexing="ij")
    shell1 = (
        (ii == 0) | (ii == N - 1) | (jj == 0) | (jj == N - 1) | (kk == 0) | (kk == N - 1)
    )
    shell2 = (
        (ii <= 1) | (ii >= N - 2) | (jj <= 1) | (jj >= N - 2) | (kk <= 1) | (kk >= N - 2)
    )
    mask = (~shell1).to(torch.float64)
    rotations = tuple(
        torch.tensor(matrix, dtype=torch.float64, device=device)
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
        dtype=torch.complex128,
        device=device,
    )
    return Grid(
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
        psi_inf=torch.tensor((PHI**-0.5, PHI**-1.0), dtype=torch.float64, device=device),
        h_inf=torch.tensor((0.0, 0.0, 1.0), dtype=torch.float64, device=device),
        R=R,
        N=N,
        dx=DX,
        dv=DV,
    )


def derivatives(field: torch.Tensor, grid: Grid) -> tuple[torch.Tensor, ...]:
    return torch.gradient(
        field,
        spacing=(grid.dx, grid.dx, grid.dx),
        dim=(0, 1, 2),
        edge_order=2,
    )


def project_scalar_torch(field: torch.Tensor) -> torch.Tensor:
    return sum(torch.rot90(field, turn, dims=(0, 1)) for turn in range(4)) / 4.0


def project_vector_torch(field: torch.Tensor, rotations: tuple[torch.Tensor, ...]) -> torch.Tensor:
    projected = torch.zeros_like(field)
    for turn, rotation in enumerate(rotations):
        projected += torch.einsum(
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
        "rho_potential": COEFFICIENTS["u_rho"] / 4.0 * torch.sum((rho - 1.0) ** 2) * grid.dv,
        "composition_potential": COEFFICIENTS["u_phi"] / 2.0 * torch.sum(delta_phi**2) * grid.dv,
        "curvature": COEFFICIENTS["gamma_x"] / 4.0 * torch.sum(curvature**2) * grid.dv,
        "h_gradient": COEFFICIENTS["gamma_x"] / 2.0 * torch.sum(covariant_h**2) * grid.dv,
        "h_potential": COEFFICIENTS["u_H"]
        / 4.0
        * torch.sum((torch.sum(h**2, dim=-1) - 1.0) ** 2)
        * grid.dv,
        "carrier_gradient": COEFFICIENTS["k_Cx"] / 2.0 * carrier_gradient_norm * grid.dv,
        "carrier_quadratic": torch.sum(
            (COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - rho)) * chi_modulus2
        )
        * grid.dv,
        "carrier_quartic": COEFFICIENTS["u_C"] / 2.0 * torch.sum(chi_modulus2**2) * grid.dv,
    }
    gauge_fixing = COEFFICIENTS["xi_gf"] / 2.0 * torch.sum(divergence**2) * grid.dv
    return components, gauge_fixing, {"rho": rho, "curvature": curvature, "divergence": divergence}


def physical_gradient_rms(fields: dict[str, torch.Tensor], grid: Grid) -> float:
    leaves = {name: value.detach().clone().requires_grad_(True) for name, value in fields.items()}
    components, _, _ = energy_components(leaves, torch.zeros_like(leaves["c"]), grid)
    physical = torch.stack(tuple(components.values())).sum()
    order = ("psi_real", "psi_imag", "h", "a", "c")
    gradients = torch.autograd.grad(physical, tuple(leaves[name] for name in order))
    projected = [
        project_scalar_torch(grid.mask[..., None] * gradients[0] / grid.dv),
        project_scalar_torch(grid.mask[..., None] * gradients[1] / grid.dv),
        project_scalar_torch(grid.mask[..., None] * gradients[2] / grid.dv),
        project_vector_torch(grid.mask[..., None, None] * gradients[3] / grid.dv, grid.rotations),
    ]
    carrier_gradient = gradients[4] / grid.dv
    inner = torch.sum(leaves["c"] * carrier_gradient) * grid.dv
    norm = torch.sum(leaves["c"] ** 2) * grid.dv
    projected.append(
        project_scalar_torch(grid.mask * (carrier_gradient - leaves["c"] * inner / norm))
    )
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
        tuple(torch.einsum("...j,...ja->...a", dvector[i], a) for i in range(3)), dim=-2
    )
    dot_a = -advected_a - one_form
    dlog_c = derivatives(torch.log(c + 1.0e-12), grid)
    divergence_v = sum(dvector[i][..., i] for i in range(3))
    transport_c = sum(vector[..., axis] * dlog_c[axis] for axis in range(3))
    scale_c = -transport_c - 0.5 * divergence_v

    perturbed: dict[int, dict[str, torch.Tensor]] = {}
    for sign in (-1, 1):
        step = sign * 1.0e-4
        psi_trial = project_scalar_torch(psi + step * dot_psi)
        psi_trial = grid.mask[..., None] * psi_trial + (1.0 - grid.mask[..., None]) * grid.psi_inf
        h_trial = project_scalar_torch(h + step * dot_h)
        h_trial = grid.mask[..., None] * h_trial + (1.0 - grid.mask[..., None]) * grid.h_inf
        a_trial = project_vector_torch(a + step * dot_a, grid.rotations) * grid.mask[..., None, None]
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


def rotate_full(site: tuple[int, int, int]) -> tuple[int, int, int]:
    return site[1], N - 1 - site[0], site[2]


def rotate_inner(site: tuple[int, int, int]) -> tuple[int, int, int]:
    return site[1], INNER - 1 - site[0], site[2]


def collect_orbits(
    sites: list[tuple[int, int, int]], rotate: Any
) -> list[list[tuple[int, int, int]]]:
    unused = set(sites)
    groups: list[list[tuple[int, int, int]]] = []
    while unused:
        seed = min(unused)
        group: list[tuple[int, int, int]] = []
        point = seed
        for _ in range(4):
            if point not in group:
                group.append(point)
            point = rotate(point)
        unused.difference_update(group)
        groups.append(group)
    return groups


def flat_full(site: tuple[int, int, int]) -> int:
    return (site[0] * N + site[1]) * N + site[2]


def flat_interior(site: tuple[int, int, int]) -> int:
    return ((site[0] - 1) * M + (site[1] - 1)) * M + site[2] - 1


def flat_inner(site: tuple[int, int, int]) -> int:
    return (site[0] * INNER + site[1]) * INNER + site[2]


def max_sparse(matrix: sparse.spmatrix) -> float:
    return float(np.max(np.abs(matrix.data))) if matrix.nnz else 0.0


def tidy(matrix: sparse.spmatrix, form: str = "csr") -> sparse.spmatrix:
    output = matrix.asformat(form)
    output.eliminate_zeros()
    return output


def scalar_project_np(field: np.ndarray) -> np.ndarray:
    return sum(np.rot90(field, turn, axes=(0, 1)) for turn in range(4)) / 4.0


def vector_project_np(field: np.ndarray) -> np.ndarray:
    output = np.zeros_like(field)
    for turn in range(4):
        output += np.einsum(
            "ij,...jc->...ic", np.linalg.matrix_power(ROTATION, turn), np.rot90(field, turn, axes=(0, 1))
        )
    return output / 4.0


def projection_error(field: np.ndarray, projected: np.ndarray) -> float:
    return float(np.max(np.abs(field - projected)) / max(float(np.max(np.abs(field))), 1.0))


def shell_numpy() -> np.ndarray:
    indices = np.indices((N, N, N))
    return np.any((indices == 0) | (indices == N - 1), axis=0)


def boundary_max(field: np.ndarray) -> float:
    return float(np.max(np.abs(field[shell_numpy()])))


@dataclass
class IndependentBases:
    scalar: sparse.csr_matrix
    vector: sparse.csr_matrix
    scalar_lookup: np.ndarray
    scalar_scale: np.ndarray
    vector_lookup: np.ndarray
    vector_values: np.ndarray
    interior_rows: np.ndarray
    diagnostics: dict[str, Any]


def build_bases() -> IndependentBases:
    sites = [(i, j, k) for i in range(1, N - 1) for j in range(1, N - 1) for k in range(1, N - 1)]
    groups = collect_orbits(sites, rotate_full)
    if len(groups) != NS:
        raise VerificationFailure(f"independent scalar dimension {len(groups)} != {NS}")
    s_rows: list[int] = []
    s_cols: list[int] = []
    s_data: list[float] = []
    scalar_lookup = np.zeros(N**3, dtype=np.int64)
    scalar_scale = np.zeros(N**3, dtype=np.float64)
    v_rows: list[int] = []
    v_cols: list[int] = []
    v_data: list[float] = []
    vector_lookup = np.zeros((N**3, 3), dtype=np.int64)
    vector_values = np.zeros((N**3, 3, 3), dtype=np.float64)
    v_column = 0
    for s_column, group in enumerate(groups):
        amplitude = len(group) ** -0.5
        for site in group:
            row = flat_full(site)
            s_rows.append(row)
            s_cols.append(s_column)
            s_data.append(amplitude)
            scalar_lookup[row] = s_column
            scalar_scale[row] = amplitude
        if len(group) == 1:
            site = group[0]
            row = flat_full(site)
            vector_lookup[row, :] = v_column
            vector_values[row, 2, 0] = 1.0
            v_rows.append(2 * M**3 + flat_interior(site))
            v_cols.append(v_column)
            v_data.append(1.0)
            v_column += 1
            continue
        ordered = [group[0]]
        for _ in range(3):
            ordered.append(rotate_full(ordered[-1]))
        for seed_axis in range(3):
            for turn, site in enumerate(ordered):
                vector = np.linalg.matrix_power(ROTATION.T, turn)[:, seed_axis] / 2.0
                row = flat_full(site)
                vector_lookup[row, seed_axis] = v_column
                vector_values[row, :, seed_axis] = vector
                for axis, value in enumerate(vector):
                    if value:
                        v_rows.append(axis * M**3 + flat_interior(site))
                        v_cols.append(v_column)
                        v_data.append(float(value))
            v_column += 1
    if v_column != NV:
        raise VerificationFailure(f"independent vector dimension {v_column} != {NV}")
    scalar_basis = sparse.coo_matrix((s_data, (s_rows, s_cols)), shape=(N**3, NS)).tocsr()
    vector_basis = sparse.coo_matrix((v_data, (v_rows, v_cols)), shape=(3 * M**3, NV)).tocsr()
    s_error = max_sparse(scalar_basis.T @ scalar_basis - sparse.eye(NS))
    v_error = max_sparse(vector_basis.T @ vector_basis - sparse.eye(NV))
    if max(s_error, v_error) > 1.0e-12:
        raise VerificationFailure(f"independent C4 basis orthogonality failed: {s_error}, {v_error}")
    return IndependentBases(
        scalar=scalar_basis,
        vector=vector_basis,
        scalar_lookup=scalar_lookup,
        scalar_scale=scalar_scale,
        vector_lookup=vector_lookup,
        vector_values=vector_values,
        interior_rows=np.asarray([flat_full(site) for site in sites], dtype=np.int64),
        diagnostics={
            "scalar_dimension": NS,
            "vector_dimension": NV,
            "scalar_orthogonality_max": s_error,
            "vector_orthogonality_max": v_error,
            "scalar_nnz": int(scalar_basis.nnz),
            "vector_nnz": int(vector_basis.nnz),
        },
    )


def derivative_matrices() -> tuple[sparse.csr_matrix, ...]:
    one = np.column_stack(
        [np.gradient(np.eye(N, dtype=np.float64)[:, column], DX, edge_order=2) for column in range(N)]
    )
    derivative = sparse.csr_matrix(one)
    identity = sparse.eye(N, format="csr")
    return (
        sparse.kron(derivative, sparse.kron(identity, identity), format="csr"),
        sparse.kron(identity, sparse.kron(derivative, identity), format="csr"),
        sparse.kron(identity, sparse.kron(identity, derivative), format="csr"),
    )


def build_alpha_basis(operators: tuple[sparse.csr_matrix, ...]) -> tuple[sparse.csr_matrix, dict[str, Any]]:
    sites = [(i, j, k) for i in range(INNER) for j in range(INNER) for k in range(INNER)]
    groups = collect_orbits(sites, rotate_inner)
    if len(groups) != N_ALPHA:
        raise VerificationFailure(f"independent alpha dimension {len(groups)} != {N_ALPHA}")
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for column, group in enumerate(groups):
        value = len(group) ** -0.5
        for site in group:
            rows.append(flat_inner(site))
            cols.append(column)
            data.append(value)
    central = sparse.coo_matrix((data, (rows, cols)), shape=(INNER**3, N_ALPHA)).tocsr()
    e_rows = list(range(2, N - 2)) + [1, N - 2]
    e_cols = list(range(INNER)) + [0, INNER - 1]
    e_data = [1.0] * INNER + [0.25, 0.25]
    extension_1d = sparse.coo_matrix((e_data, (e_rows, e_cols)), shape=(N, INNER)).tocsr()
    extension_3d = sparse.kron(
        extension_1d, sparse.kron(extension_1d, extension_1d), format="csr"
    )
    alpha = tidy(extension_3d @ central, "csr")
    norms = np.sqrt(np.asarray(alpha.power(2).sum(axis=0)).reshape(-1))
    alpha = tidy(alpha @ sparse.diags(1.0 / norms), "csr")
    orthogonality = max_sparse(alpha.T @ alpha - sparse.eye(N_ALPHA))
    shell = shell_numpy().reshape(-1)
    shell_value = max_sparse(alpha[shell, :])
    derivative_shell = [max_sparse(operator[shell, :] @ alpha) for operator in operators]
    if max(orthogonality, shell_value, *derivative_shell) > 1.0e-12:
        raise VerificationFailure(
            f"independent alpha basis failed: orth={orthogonality}, shell={shell_value}, "
            f"gradient={derivative_shell}"
        )
    return alpha, {
        "central_side": INNER,
        "dimension_per_color": N_ALPHA,
        "orthogonality_max": orthogonality,
        "shell_value_max": shell_value,
        "shell_derivative_max_by_axis": derivative_shell,
        "nnz": int(alpha.nnz),
    }


def left_weight(weights: np.ndarray, alpha: sparse.csr_matrix) -> sparse.csr_matrix:
    output = sparse.diags(np.asarray(weights).reshape(-1)) @ alpha
    return tidy(output, "csr")


def build_gauge_map(
    fields: dict[str, np.ndarray],
    bases: IndependentBases,
    alpha: sparse.csr_matrix,
    operators: tuple[sparse.csr_matrix, ...],
) -> tuple[sparse.csc_matrix, dict[str, Any]]:
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h = fields["h"]
    connection = fields["a"]
    d_alpha = tuple(tidy(operator @ alpha, "csr") for operator in operators)
    output_rows: list[list[sparse.spmatrix]] = [[] for _ in range(10)]
    color_axes = np.eye(3, dtype=np.float64)
    for source_color in range(3):
        spinor = 1.0j * np.einsum("ab,...b->...a", PAULI_GENERATORS[source_color], psi)
        scalar_weights = [
            spinor[..., 0].real,
            spinor[..., 1].real,
            spinor[..., 0].imag,
            spinor[..., 1].imag,
        ]
        adjoint = np.cross(h, color_axes[source_color])
        scalar_weights += [adjoint[..., axis] for axis in range(3)]
        for row_index, weights in enumerate(scalar_weights):
            output_rows[row_index].append(
                tidy(bases.scalar.T @ left_weight(np.asarray(weights), alpha), "csr")
            )
        for target_color in range(3):
            pieces: list[sparse.spmatrix] = []
            for spatial_axis in range(3):
                commutator = np.cross(
                    connection[..., spatial_axis, :], color_axes[source_color]
                )[..., target_color]
                matrix = left_weight(commutator, alpha)
                if target_color == source_color:
                    matrix = matrix + d_alpha[spatial_axis]
                pieces.append(tidy(matrix[bases.interior_rows, :], "csr"))
            output_rows[7 + target_color].append(
                tidy(bases.vector.T @ sparse.vstack(pieces, format="csr"), "csr")
            )
    gauge = sparse.bmat(output_rows, format="csc")
    gauge.eliminate_zeros()
    if gauge.shape != (N_NONCARRIER, N_GAUGE):
        raise VerificationFailure(f"independent gauge-map shape {gauge.shape}")
    return gauge, {
        "noncarrier_shape": list(gauge.shape),
        "embedded_shape": [N_BASE, N_GAUGE],
        "nnz": int(gauge.nnz),
        "sample_generator_norm": float(np.linalg.norm(gauge[:, 0].toarray())),
    }


class IndependentProjector:
    def __init__(self, gauge: sparse.csc_matrix) -> None:
        self.gauge = gauge
        self.gram = tidy((gauge.T @ gauge + (gauge.T @ gauge).T) * 0.5, "csc")
        try:
            self.lu = splu(self.gram, permc_spec="COLAMD")
        except RuntimeError as exc:
            raise VerificationFailure(f"independent sparse Gram factorization failed: {exc}") from exc
        inverse = LinearOperator(
            (N_GAUGE, N_GAUGE),
            matvec=self.lu.solve,
            rmatvec=lambda value: self.lu.solve(value, trans="T"),
            dtype=np.float64,
        )
        try:
            minimum = float(
                eigsh(
                    self.gram,
                    k=1,
                    sigma=0.0,
                    which="LM",
                    OPinv=inverse,
                    tol=1.0e-9,
                    maxiter=2000,
                    return_eigenvectors=False,
                )[0]
            )
            maximum = float(
                eigsh(
                    self.gram,
                    k=1,
                    which="LA",
                    tol=1.0e-9,
                    maxiter=2000,
                    return_eigenvectors=False,
                )[0]
            )
        except ArpackNoConvergence as exc:
            raise VerificationFailure("independent Gram extremal solve did not converge") from exc
        condition = maximum / minimum
        if minimum <= 1.0e-8 or condition >= 1.0e8:
            raise VerificationFailure(
                f"independent Gram conditioning failed: minimum={minimum}, condition={condition}"
            )
        rng = np.random.default_rng(60601)
        solve_rows: list[dict[str, float]] = []
        projection_rows: list[dict[str, float]] = []
        for index in range(3):
            rhs = rng.standard_normal(N_GAUGE)
            solution = self.lu.solve(rhs)
            solve_residual = float(np.linalg.norm(self.gram @ solution - rhs) / np.linalg.norm(rhs))
            solve_rows.append({"probe": index, "relative_residual": solve_residual})
            first = rng.standard_normal(N_BASE)
            second = rng.standard_normal(N_BASE)
            p_first = self.apply(first)
            p_second = self.apply(second)
            repeated = self.apply(p_first)
            idempotence = float(
                np.linalg.norm(repeated - p_first) / max(np.linalg.norm(p_first), 1.0)
            )
            gauge_residual = self.gauge_residual(p_first)
            left = float(second @ p_first)
            right = float(first @ p_second)
            symmetry = abs(left - right) / max(abs(left), abs(right), 1.0)
            projection_rows.append(
                {
                    "probe": index,
                    "idempotence_relative": idempotence,
                    "gauge_orthogonality_relative": gauge_residual,
                    "symmetry_relative": symmetry,
                }
            )
            if solve_residual > 1.0e-10 or max(idempotence, gauge_residual, symmetry) > 1.0e-10:
                raise VerificationFailure(
                    f"independent projector probe failed: {solve_rows[-1]}, {projection_rows[-1]}"
                )
        self.diagnostics = {
            "gram_shape": list(self.gram.shape),
            "gram_nnz": int(self.gram.nnz),
            "gram_lambda_min": minimum,
            "gram_lambda_max": maximum,
            "gram_condition_estimate": condition,
            "solve_probes": solve_rows,
            "projector_probes": projection_rows,
            "physical_dimension": N_PHYS,
        }

    def gauge_component(self, vector: np.ndarray) -> np.ndarray:
        source = np.asarray(vector, dtype=np.float64)
        rhs = np.asarray(self.gauge.T @ source[:N_NONCARRIER]).reshape(-1)
        coefficients = self.lu.solve(rhs)
        result = np.zeros(N_BASE, dtype=np.float64)
        result[:N_NONCARRIER] = np.asarray(self.gauge @ coefficients).reshape(-1)
        return result

    def apply(self, vector: np.ndarray) -> np.ndarray:
        source = np.asarray(vector, dtype=np.float64)
        return source - self.gauge_component(source)

    def gauge_residual(self, vector: np.ndarray) -> float:
        vector = np.asarray(vector, dtype=np.float64)
        residual = np.linalg.norm(self.gauge.T @ vector[:N_NONCARRIER])
        return float(residual / max(np.linalg.norm(vector), 1.0))

def as_torch_sparse(matrix: sparse.spmatrix, device: torch.device) -> torch.Tensor:
    coordinate = matrix.tocoo()
    locations = np.stack((coordinate.row, coordinate.col), axis=0)
    return torch.sparse_coo_tensor(
        torch.tensor(locations, dtype=torch.long, device=device),
        torch.tensor(coordinate.data, dtype=torch.float64, device=device),
        coordinate.shape,
        dtype=torch.float64,
        device=device,
        check_invariants=True,
    ).coalesce()




class IndependentSpace:
    def __init__(
        self,
        fields_np: dict[str, np.ndarray],
        bases: IndependentBases,
        projector: IndependentProjector,
        grid: Grid,
        device: torch.device,
    ) -> None:
        reduced = np.asarray(bases.scalar.T @ fields_np["c"].reshape(-1)).reshape(-1)
        unit = reduced / np.linalg.norm(reduced)
        sign = 1.0 if unit[0] >= 0.0 else -1.0
        reflector = unit.copy()
        reflector[0] += sign
        reflector /= np.linalg.norm(reflector)
        mapped = unit - 2.0 * reflector * float(reflector @ unit)
        expected = np.zeros(NS, dtype=np.float64)
        expected[0] = -sign
        map_residual = float(np.linalg.norm(mapped - expected))
        probe_coordinates = np.linspace(-1.0, 1.0, NS - 1)
        embedded = np.concatenate((np.zeros(1), probe_coordinates))
        tangent = embedded - 2.0 * reflector * float(reflector @ embedded)
        tangent_residual = abs(float(reduced @ tangent)) / max(
            np.linalg.norm(reduced) * np.linalg.norm(tangent), 1.0
        )
        if max(map_residual, tangent_residual) > 1.0e-11:
            raise VerificationFailure(
                f"independent charge tangent failed: map={map_residual}, tangent={tangent_residual}"
            )
        self.bases = bases
        self.projector = projector
        self.grid = grid
        self.device = device
        self.carrier_reduced = reduced
        self.reflector = reflector
        self.reflector_t = torch.tensor(reflector, dtype=torch.float64, device=device)
        self.scalar_basis_t = as_torch_sparse(bases.scalar, device)
        self.vector_basis_t = as_torch_sparse(bases.vector, device)
        self.background = {
            name: torch.tensor(value, dtype=torch.float64, device=device)
            for name, value in fields_np.items()
        }
        self.diagnostics = {
            "carrier_reduced_norm": float(np.linalg.norm(reduced)),
            "householder_tangent_probe_relative": tangent_residual,
            "householder_unit_map_residual": map_residual,
            "base_dimension": N_BASE,
            "physical_dimension": N_PHYS,
        }

    def scalar_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        flat = torch.sparse.mm(self.scalar_basis_t, coefficients.reshape(-1, 1)).squeeze(1)
        return flat.reshape(N, N, N)

    def vector_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        interior = torch.sparse.mm(self.vector_basis_t, coefficients).reshape(3, M, M, M, 3)
        padded = torch.nn.functional.pad(
            interior, (0, 0, 1, 1, 1, 1, 1, 1, 0, 0), value=0.0
        )
        return torch.permute(padded, (1, 2, 3, 0, 4))

    def perturb(self, base: torch.Tensor) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        scalar_coordinates = base[: 7 * NS].reshape(7, NS)
        scalar_fields = torch.stack(
            tuple(self.scalar_field(scalar_coordinates[row]) for row in range(7)), dim=-1
        )
        vector_coordinates = base[7 * NS : N_NONCARRIER].reshape(3, NV).T
        delta_a = self.vector_field(vector_coordinates)
        carrier_coordinates = torch.cat(
            (
                torch.zeros(1, dtype=torch.float64, device=self.device),
                base[N_NONCARRIER : N_NONCARRIER + NS - 1],
            )
        )
        carrier_real_coefficients = carrier_coordinates - 2.0 * self.reflector_t * torch.dot(
            self.reflector_t, carrier_coordinates
        )
        carrier_imag_coefficients = base[N_NONCARRIER + NS - 1 :]
        carrier_real = self.scalar_field(carrier_real_coefficients)
        carrier_imag = self.scalar_field(carrier_imag_coefficients)
        fields = {
            "psi_real": self.background["psi_real"] + scalar_fields[..., :2],
            "psi_imag": self.background["psi_imag"] + scalar_fields[..., 2:4],
            "h": self.background["h"] + scalar_fields[..., 4:7],
            "a": self.background["a"] + delta_a,
            "c": self.background["c"] + carrier_real,
        }
        return fields, carrier_imag

    def augmented(self, base: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        fields, carrier_imag = self.perturb(base)
        components, _, _ = energy_components(fields, carrier_imag, self.grid)
        physical = torch.stack(tuple(components.values())).sum()
        charge = torch.sum(fields["c"] ** 2 + carrier_imag**2) * self.grid.dv
        return physical - OMEGA_C * charge, physical, charge

    def lagrangian(self, base: np.ndarray) -> float:
        coordinates = torch.tensor(base, dtype=torch.float64, device=self.device)
        value, _, _ = self.augmented(coordinates)
        return scalar(value)

    def unprojected_gradient(self, base: np.ndarray) -> np.ndarray:
        coordinates = torch.tensor(base, dtype=torch.float64, device=self.device, requires_grad=True)
        value, _, _ = self.augmented(coordinates)
        gradient = torch.autograd.grad(value, coordinates)[0] / self.grid.dv
        return gradient.detach().cpu().numpy()

    def physical_gradient(self, base: np.ndarray) -> np.ndarray:
        return self.projector.apply(self.unprojected_gradient(base))

    def unprojected_hvp(self, direction: np.ndarray) -> np.ndarray:
        direction_t = torch.tensor(direction, dtype=torch.float64, device=self.device)
        origin = torch.zeros(N_BASE, dtype=torch.float64, device=self.device, requires_grad=True)
        value, _, _ = self.augmented(origin)
        first = torch.autograd.grad(value, origin, create_graph=True)[0]
        second = torch.autograd.grad(torch.dot(first, direction_t), origin)[0] / self.grid.dv
        return second.detach().cpu().numpy()

    def physical_hvp(self, direction: np.ndarray) -> np.ndarray:
        physical = self.projector.apply(direction)
        return self.projector.apply(self.unprojected_hvp(physical))

    def lifted_hvp(self, direction: np.ndarray) -> np.ndarray:
        physical = self.projector.apply(direction)
        gauge = np.asarray(direction) - physical
        return self.projector.apply(self.unprojected_hvp(physical)) + GAUGE_LIFT * gauge

    def normalize(self, vector: np.ndarray) -> np.ndarray:
        physical = self.projector.apply(vector)
        norm = np.linalg.norm(physical)
        if not math.isfinite(norm) or norm == 0.0:
            raise VerificationFailure("independent physical normalization failed")
        return physical / norm

    def phase_vector(self) -> np.ndarray:
        vector = np.zeros(N_BASE, dtype=np.float64)
        vector[N_NONCARRIER + NS - 1 :] = self.carrier_reduced / np.linalg.norm(self.carrier_reduced)
        return self.normalize(vector)

    def mode_fields(self, base: np.ndarray) -> dict[str, np.ndarray]:
        base_t = torch.tensor(base, dtype=torch.float64, device=self.device)
        fields, carrier_imag = self.perturb(base_t)
        return {
            "psi_real": (fields["psi_real"] - self.background["psi_real"]).detach().cpu().numpy(),
            "psi_imag": (fields["psi_imag"] - self.background["psi_imag"]).detach().cpu().numpy(),
            "h": (fields["h"] - self.background["h"]).detach().cpu().numpy(),
            "a": (fields["a"] - self.background["a"]).detach().cpu().numpy(),
            "chi_real": (fields["c"] - self.background["c"]).detach().cpu().numpy(),
            "chi_imag": carrier_imag.detach().cpu().numpy(),
        }


def load_background(device: torch.device, grid: Grid) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    actual_hash = sha256_file(ARTIFACT)
    if actual_hash != ARTIFACT_SHA256:
        raise VerificationFailure(f"localized artifact digest {actual_hash} != {ARTIFACT_SHA256}")
    expected = {
        "x": (N,),
        "psi_real": (N, N, N, 2),
        "psi_imag": (N, N, N, 2),
        "h": (N, N, N, 3),
        "a": (N, N, N, 3, 3),
        "c": (N, N, N),
    }
    with np.load(ARTIFACT, allow_pickle=False) as archive:
        if set(archive.files) != set(expected):
            raise VerificationFailure(f"independent artifact key mismatch: {archive.files}")
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    schema: dict[str, Any] = {}
    for name, shape in expected.items():
        array = arrays[name]
        schema[name] = {
            "shape": list(array.shape),
            "dtype": str(array.dtype),
            "c_contiguous": bool(array.flags.c_contiguous),
            "finite": bool(np.all(np.isfinite(array))),
        }
        if array.shape != shape or array.dtype != np.float64 or not array.flags.c_contiguous:
            raise VerificationFailure(f"independent artifact schema failure: {name}: {schema[name]}")
        if not np.all(np.isfinite(array)):
            raise VerificationFailure(f"independent artifact nonfinite: {name}")
    if np.max(np.abs(arrays["x"] - np.linspace(-R, R, N))) > 1.0e-14:
        raise VerificationFailure("independent artifact coordinate mismatch")

    fields_np = {name: arrays[name] for name in ("psi_real", "psi_imag", "h", "a", "c")}
    shells = {
        "psi_real": boundary_max(arrays["psi_real"] - np.asarray((PHI**-0.5, PHI**-1.0))),
        "psi_imag": boundary_max(arrays["psi_imag"]),
        "h": boundary_max(arrays["h"] - np.asarray((0.0, 0.0, 1.0))),
        "a": boundary_max(arrays["a"]),
        "c": boundary_max(arrays["c"]),
    }
    c4 = {
        "psi_real": projection_error(arrays["psi_real"], scalar_project_np(arrays["psi_real"])),
        "psi_imag": projection_error(arrays["psi_imag"], scalar_project_np(arrays["psi_imag"])),
        "h": projection_error(arrays["h"], scalar_project_np(arrays["h"])),
        "a": projection_error(arrays["a"], vector_project_np(arrays["a"])),
        "c": projection_error(arrays["c"], scalar_project_np(arrays["c"])),
    }
    if max(shells.values()) > 1.0e-12 or max(c4.values()) > 5.0e-12:
        raise VerificationFailure(f"independent shell/C4 failure: shell={shells}, C4={c4}")

    fields_t = {name: torch.tensor(value, dtype=torch.float64, device=device) for name, value in fields_np.items()}
    components, gauge_fixing, aux = energy_components(fields_t, torch.zeros_like(fields_t["c"]), grid)
    energy = scalar(torch.stack(tuple(components.values())).sum())
    charge = scalar(torch.sum(fields_t["c"] ** 2) * grid.dv)
    omega = scalar(
        (components["carrier_gradient"] + components["carrier_quadratic"] + 2.0 * components["carrier_quartic"])
        / charge
    )
    gradient_rms = physical_gradient_rms(fields_t, grid)
    virial, _, _ = cutoff_virial(fields_t, grid, components)
    depletion = torch.clamp(1.0 - aux["rho"], min=0.0)
    depletion_weight = scalar(torch.sum(depletion) * grid.dv)
    core_length = 0.0 if depletion_weight < 1.0e-12 else 2.0 * math.sqrt(
        scalar(torch.sum(grid.Z**2 * depletion) * grid.dv) / depletion_weight
    )
    radius2 = grid.X**2 + grid.Y**2 + grid.Z**2
    measured = {
        "physical_energy": energy,
        "physical_gradient_rms": gradient_rms,
        "cutoff_virial": virial,
        "omega_c": omega,
        "charge": charge,
        "gauge_fixing_energy": scalar(gauge_fixing),
        "carrier_radius": math.sqrt(scalar(torch.sum(radius2 * fields_t["c"] ** 2) * grid.dv) / charge),
        "core_length": core_length,
        "outer_carrier_fraction": scalar(
            torch.sum(fields_t["c"][grid.shell2] ** 2) / torch.sum(fields_t["c"] ** 2)
        ),
        "max_density_depletion": scalar(torch.max(depletion)),
        "negative_norm_fraction": scalar(
            torch.sum(torch.clamp(-fields_t["c"], min=0.0) ** 2) * grid.dv / charge
        ),
    }
    comparisons: dict[str, Any] = {}
    for name, frozen in FROZEN_BACKGROUND.items():
        error = abs(measured[name] - frozen)
        tolerance = 1.0e-11 + 1.0e-9 * abs(frozen)
        comparisons[name] = {
            "measured": measured[name],
            "frozen": frozen,
            "error": error,
            "tolerance": tolerance,
        }
        if error > tolerance:
            raise VerificationFailure(f"independent background scalar mismatch: {name}: {comparisons[name]}")

    source_results = json.loads(SOURCE_RESULTS.read_text(encoding="utf-8"))
    source_verification = json.loads(SOURCE_VERIFICATION.read_text(encoding="utf-8"))
    if source_results.get("coefficient_vector") != COEFFICIENTS:
        raise VerificationFailure("independent source coefficient mismatch")
    if source_results.get("primary_verdict") != SOURCE_VERDICT:
        raise VerificationFailure("independent source verdict mismatch")
    if not source_verification.get("pass", False):
        raise VerificationFailure("independent source verification receipt does not pass")
    return fields_np, {
        "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": actual_hash,
        "schema": schema,
        "shell_residuals": shells,
        "c4_residuals": c4,
        "scalars": comparisons,
        "source_verdict": SOURCE_VERDICT,
    }


def build_state(device: torch.device) -> tuple[
    dict[str, np.ndarray],
    IndependentSpace,
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
]:
    grid = make_grid(device)
    fields, background = load_background(device, grid)
    bases = build_bases()
    operators = derivative_matrices()
    alpha, alpha_diagnostics = build_alpha_basis(operators)
    gauge, gauge_diagnostics = build_gauge_map(fields, bases, alpha, operators)
    projector = IndependentProjector(gauge)
    space = IndependentSpace(fields, bases, projector, grid, device)
    return (
        fields,
        space,
        background,
        bases.diagnostics,
        alpha_diagnostics,
        gauge_diagnostics,
        projector.diagnostics,
    )


def directional_checks(space: IndependentSpace, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    origin = np.zeros(N_BASE, dtype=np.float64)
    baseline = space.lagrangian(origin)
    rows: list[dict[str, Any]] = []
    for index in range(3):
        direction = space.normalize(rng.standard_normal(N_BASE))
        exact = space.physical_hvp(direction)
        exact_curvature = float(direction @ exact)
        ladder: list[dict[str, float]] = []
        for step in STEPS:
            finite = (
                space.physical_gradient(step * direction)
                - space.physical_gradient(-step * direction)
            ) / (2.0 * step)
            energy_curvature = (
                space.lagrangian(step * direction)
                - 2.0 * baseline
                + space.lagrangian(-step * direction)
            ) / (step**2 * DV)
            tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
            ladder.append(
                {
                    "step": step,
                    "vector_relative_error": float(
                        np.linalg.norm(finite - exact) / max(np.linalg.norm(exact), 1.0)
                    ),
                    "energy_curvature": energy_curvature,
                    "exact_curvature": exact_curvature,
                    "curvature_error": abs(energy_curvature - exact_curvature),
                    "curvature_tolerance": tolerance,
                }
            )
        agreement = abs(ladder[-1]["energy_curvature"] - ladder[-2]["energy_curvature"])
        tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
        passed = (
            ladder[-1]["vector_relative_error"] <= 5.0e-5
            and ladder[-1]["curvature_error"] <= ladder[-1]["curvature_tolerance"]
            and agreement <= tolerance
        )
        rows.append(
            {
                "direction": index,
                "norm": float(direction @ direction),
                "physicality_relative": float(
                    np.linalg.norm(direction - space.projector.apply(direction))
                    / max(np.linalg.norm(direction), 1.0)
                ),
                "exact_curvature": exact_curvature,
                "steps": ladder,
                "two_smallest_energy_curvature_difference": agreement,
                "step_agreement_tolerance": tolerance,
                "pass": passed,
            }
        )
    return {"seed": seed, "directions": rows, "pass": all(row["pass"] for row in rows)}


def operator_checks(space: IndependentSpace) -> tuple[dict[str, Any], np.ndarray]:
    origin = np.zeros(N_BASE, dtype=np.float64)
    gradient = space.physical_gradient(origin)
    gradient_rms = float(np.linalg.norm(gradient) / math.sqrt(N_PHYS))
    rng = np.random.default_rng(90917)
    symmetry: list[dict[str, float]] = []
    for index in range(4):
        left = space.normalize(rng.standard_normal(N_BASE))
        right = space.normalize(rng.standard_normal(N_BASE))
        left_h_right = float(left @ space.physical_hvp(right))
        right_h_left = float(right @ space.physical_hvp(left))
        relative = abs(left_h_right - right_h_left) / max(
            abs(left_h_right), abs(right_h_left), 1.0
        )
        symmetry.append(
            {
                "pair": index,
                "left_K_right": left_h_right,
                "right_K_left": right_h_left,
                "relative_error": relative,
            }
        )
    phase = space.phase_vector()
    phase_hvp = space.physical_hvp(phase)
    phase_rayleigh = float(phase @ phase_hvp)
    passed = (
        gradient_rms <= 5.0e-6
        and max(row["relative_error"] for row in symmetry) <= 1.0e-9
        and abs(phase_rayleigh) <= 1.0e-10
        and space.projector.gauge_residual(phase) <= 1.0e-10
    )
    return {
        "augmented_gradient_rms": gradient_rms,
        "augmented_gradient_limit": 5.0e-6,
        "operator_symmetry": symmetry,
        "operator_symmetry_pass": max(row["relative_error"] for row in symmetry) <= 1.0e-9,
        "phase_rayleigh": phase_rayleigh,
        "phase_hessian_residual": float(np.linalg.norm(phase_hvp)),
        "phase_gauge_orthogonality_relative": space.projector.gauge_residual(phase),
        "phase_rayleigh_limit": 1.0e-10,
        "pass": passed,
    }, phase


def environment_receipt(device: torch.device) -> dict[str, Any]:
    return {
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "torch": torch.__version__,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device),
        "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
        "PYTORCH_HIP_ALLOC_CONF": os.environ.get("PYTORCH_HIP_ALLOC_CONF"),
        "HSA_ENABLE_SDMA": os.environ.get("HSA_ENABLE_SDMA"),
    }


def run_preflight(manifest_path: Path, output_path: Path) -> int:
    started = time.perf_counter()
    manifest, manifest_hash = verify_manifest(manifest_path)
    device = configure_torch()
    (
        fields,
        space,
        background,
        bases,
        alpha,
        gauge,
        projector,
    ) = build_state(device)
    operator, phase = operator_checks(space)
    directional = directional_checks(space, 161803)
    passed = operator["pass"] and directional["pass"]
    receipt = {
        "schema": "cassi.particle-localized-physical-hessian.preflight.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": environment_receipt(device),
        "background": background,
        "dimensions": {
            "scalar_c4": NS,
            "vector_c4": NV,
            "boundary_preserving_alpha_per_color": N_ALPHA,
            "gauge_rank": N_GAUGE,
            "noncarrier_base": N_NONCARRIER,
            "base": N_BASE,
            "physical": N_PHYS,
            "full_real_fields": FIELD_COMPONENTS * N**3,
        },
        "bases": bases,
        "alpha_basis": alpha,
        "coupled_gauge": gauge,
        "projector": projector,
        "charge_tangent": space.diagnostics,
        "operator_preflight": operator,
        "directional_preflight": directional,
        "global_u1_norm": float(phase @ phase),
        "pass": passed,
        "wall_seconds": time.perf_counter() - started,
    }
    write_json(output_path, receipt)
    if not passed:
        raise VerificationFailure("independent localized-Hessian preflight failed")
    print(
        json.dumps(
            {
                "pass": passed,
                "manifest_sha256": manifest_hash,
                "physical_dimension": N_PHYS,
                "augmented_gradient_rms": operator["augmented_gradient_rms"],
                "wall_seconds": receipt["wall_seconds"],
            },
            indent=2,
        )
    )
    del fields
    return 0


def full_stack(mode: dict[str, np.ndarray]) -> np.ndarray:
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


def overlap(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return abs(float(np.sum(left * right))) / denominator if denominator else 0.0


def mode_probes(fields: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
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
    coordinates = np.linspace(-R, R, N)
    x, y, _ = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    axial = -(x[..., None] * gradients[1] - y[..., None] * gradients[0])
    connection_slice = slice(7, 16)
    axial_connection = axial[..., connection_slice].reshape(N, N, N, 3, 3)
    generator = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    axial_connection += np.einsum("ij,...jc->...ic", generator, fields["a"])
    axial[..., connection_slice] = axial_connection.reshape(N, N, N, 9)
    phase = np.zeros_like(background)
    phase[..., -1] = fields["c"]
    normal = np.zeros_like(background)
    normal[..., -2] = fields["c"]
    return {
        "translation_x": -gradients[0],
        "translation_y": -gradients[1],
        "translation_z": -gradients[2],
        "axial_rotation": axial,
        "global_u1": phase,
        "charge_normal": normal,
    }


def diagnose_mode(
    space: IndependentSpace,
    base: np.ndarray,
    mode: dict[str, np.ndarray],
    probes: dict[str, np.ndarray],
) -> dict[str, Any]:
    stacked = full_stack(mode)
    node_power = np.sum(stacked**2, axis=-1)
    participation = float(np.sum(node_power) ** 2 / np.sum(node_power**2))
    frequencies = np.fft.fftfreq(N, d=DX)
    high_axis = np.abs(frequencies) >= 0.75 * (1.0 / (2.0 * DX))
    high_mask = high_axis[:, None, None] | high_axis[None, :, None] | high_axis[None, None, :]
    total_power = 0.0
    high_power = 0.0
    for component in range(FIELD_COMPONENTS):
        spectrum = np.fft.fftn(stacked[..., component])
        power = np.abs(spectrum) ** 2
        total_power += float(np.sum(power))
        high_power += float(np.sum(power[high_mask]))
    fractions_raw = {
        "psi": float(np.sum(mode["psi_real"] ** 2) + np.sum(mode["psi_imag"] ** 2)),
        "h": float(np.sum(mode["h"] ** 2)),
        "a": float(np.sum(mode["a"] ** 2)),
        "chi_real": float(np.sum(mode["chi_real"] ** 2)),
        "chi_imag": float(np.sum(mode["chi_imag"] ** 2)),
    }
    total_norm = sum(fractions_raw.values())
    carrier = space.background["c"].detach().cpu().numpy()
    charge_tangent = abs(float(np.sum(carrier * mode["chi_real"]))) / max(
        float(np.linalg.norm(carrier) * np.linalg.norm(mode["chi_real"])), 1.0
    )
    projection_residual = float(
        np.linalg.norm(base - space.projector.apply(base)) / max(np.linalg.norm(base), 1.0)
    )
    high_fraction = high_power / total_power
    return {
        "participation": participation,
        "high_frequency_fraction": high_fraction,
        "spatially_resolved": participation >= 16.0 and high_fraction <= 0.20,
        "component_fractions": {name: value / total_norm for name, value in fractions_raw.items()},
        "shell_max": boundary_max(stacked),
        "charge_tangent_relative": charge_tangent,
        "gauge_orthogonality_relative": space.projector.gauge_residual(base),
        "physical_projection_relative": projection_residual,
        "norm": float(base @ base),
        "overlaps": {name: overlap(stacked, probe) for name, probe in probes.items()},
    }


def smallest_step_curvature(space: IndependentSpace, vector: np.ndarray) -> float:
    step = STEPS[-1]
    zero = np.zeros(N_BASE, dtype=np.float64)
    baseline = space.lagrangian(zero)
    return (
        space.lagrangian(step * vector)
        - 2.0 * baseline
        + space.lagrangian(-step * vector)
    ) / (step**2 * DV)


def independent_eigensolve(
    space: IndependentSpace, fields: dict[str, np.ndarray]
) -> tuple[dict[str, Any], np.ndarray]:
    operator = LinearOperator(
        (N_BASE, N_BASE), matvec=space.lifted_hvp, rmatvec=space.lifted_hvp, dtype=np.float64
    )
    rng = np.random.default_rng(INDEPENDENT_SETTINGS["seed"])
    initial = space.normalize(rng.standard_normal(N_BASE))
    started = time.perf_counter()
    try:
        values, vectors = eigsh(
            operator,
            k=INDEPENDENT_SETTINGS["k"],
            which=INDEPENDENT_SETTINGS["which"],
            ncv=INDEPENDENT_SETTINGS["ncv"],
            tol=INDEPENDENT_SETTINGS["tolerance"],
            maxiter=INDEPENDENT_SETTINGS["maxiter"],
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
    orthogonality = float(np.max(np.abs(vectors.T @ vectors - np.eye(INDEPENDENT_SETTINGS["k"]))))
    probes = mode_probes(fields)
    rows: list[dict[str, Any]] = []
    residuals: list[float] = []
    for index in range(INDEPENDENT_SETTINGS["k"]):
        vector = vectors[:, index]
        lifted = space.lifted_hvp(vector)
        physical = space.physical_hvp(vector)
        residual_absolute = float(np.linalg.norm(lifted - values[index] * vector))
        residual_relative = residual_absolute / max(abs(float(values[index])), 1.0)
        mode = space.mode_fields(vector)
        diagnostics = diagnose_mode(space, vector, mode, probes)
        curvature = smallest_step_curvature(space, vector)
        diagnostics.update(
            {
                "index": index,
                "eigenvalue": float(values[index]),
                "residual_absolute": residual_absolute,
                "residual_relative": residual_relative,
                "lifted_directional_curvature": float(vector @ lifted),
                "physical_directional_curvature": float(vector @ physical),
                "smallest_step_directional_curvature": curvature,
            }
        )
        if (
            residual_relative > 1.0e-6
            or diagnostics["shell_max"] > 1.0e-12
            or diagnostics["charge_tangent_relative"] > 1.0e-11
            or diagnostics["gauge_orthogonality_relative"] > 1.0e-10
            or diagnostics["physical_projection_relative"] > 1.0e-10
            or abs(diagnostics["norm"] - 1.0) > 1.0e-10
            or values[index] >= GAUGE_LIFT / 2.0
        ):
            raise VerificationFailure(f"independent eigenmode {index} contract failed: {diagnostics}")
        rows.append(diagnostics)
        residuals.append(residual_absolute)
    if orthogonality > 1.0e-8:
        raise VerificationFailure(f"independent eigenspace orthogonality {orthogonality}")
    return {
        "settings": INDEPENDENT_SETTINGS,
        "wall_seconds": time.perf_counter() - started,
        "eigenvalues": [float(value) for value in values],
        "max_absolute_residual": max(residuals),
        "orthogonality_max": orthogonality,
        "modes": rows,
        "finite": bool(np.all(np.isfinite(values)) and np.all(np.isfinite(vectors))),
    }, vectors


def verify_primary_archive(
    space: IndependentSpace,
    fields: dict[str, np.ndarray],
    results: dict[str, Any],
) -> tuple[dict[str, Any], np.ndarray]:
    if not MODES_PATH.is_file():
        raise VerificationFailure("primary eigenmode archive is missing")
    if results.get("artifacts", {}).get("eigenmodes_sha256") != sha256_file(MODES_PATH):
        raise VerificationFailure("primary eigenmode archive digest mismatch")
    expected_shapes = {
        "eigenvalues": (PRIMARY_SETTINGS["k"],),
        "base_vectors": (N_BASE, PRIMARY_SETTINGS["k"]),
        "global_u1_base_vector": (N_BASE,),
        "psi_real": (PRIMARY_SETTINGS["k"], N, N, N, 2),
        "psi_imag": (PRIMARY_SETTINGS["k"], N, N, N, 2),
        "h": (PRIMARY_SETTINGS["k"], N, N, N, 3),
        "a": (PRIMARY_SETTINGS["k"], N, N, N, 3, 3),
        "chi_real": (PRIMARY_SETTINGS["k"], N, N, N),
        "chi_imag": (PRIMARY_SETTINGS["k"], N, N, N),
    }
    with np.load(MODES_PATH, allow_pickle=False) as archive:
        if set(archive.files) != set(expected_shapes):
            raise VerificationFailure(f"primary archive keys differ: {archive.files}")
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    for name, shape in expected_shapes.items():
        array = arrays[name]
        if array.shape != shape or array.dtype != np.float64 or not np.all(np.isfinite(array)):
            raise VerificationFailure(
                f"primary archive schema failure for {name}: {array.shape}, {array.dtype}"
            )
    result_values = np.asarray(results["spectrum"]["eigenvalues"], dtype=np.float64)
    if not np.array_equal(arrays["eigenvalues"], result_values):
        raise VerificationFailure("primary result/archive eigenvalues differ")
    independent_phase = space.phase_vector()
    phase_difference = float(
        np.linalg.norm(arrays["global_u1_base_vector"] - independent_phase)
        / max(np.linalg.norm(independent_phase), 1.0)
    )
    if phase_difference > 1.0e-11:
        raise VerificationFailure(f"primary phase-vector difference {phase_difference}")

    probes = mode_probes(fields)
    rows: list[dict[str, Any]] = []
    for index in range(INDEPENDENT_SETTINGS["k"]):
        vector = arrays["base_vectors"][:, index]
        lifted = space.lifted_hvp(vector)
        physical = space.physical_hvp(vector)
        residual_absolute = float(np.linalg.norm(lifted - arrays["eigenvalues"][index] * vector))
        residual_relative = residual_absolute / max(abs(float(arrays["eigenvalues"][index])), 1.0)
        reconstructed = space.mode_fields(vector)
        reconstruction: dict[str, float] = {}
        for name in ("psi_real", "psi_imag", "h", "a", "chi_real", "chi_imag"):
            archived = arrays[name][index]
            difference = float(
                np.linalg.norm(reconstructed[name] - archived) / max(np.linalg.norm(archived), 1.0)
            )
            reconstruction[name] = difference
            if difference > 1.0e-11:
                raise VerificationFailure(
                    f"primary mode {index} archived {name} reconstruction difference {difference}"
                )
        diagnostics = diagnose_mode(space, vector, reconstructed, probes)
        curvature = smallest_step_curvature(space, vector)
        primary_row = results["spectrum"]["modes"][index]
        if residual_relative > 1.0e-6 or max(reconstruction.values()) > 1.0e-11:
            raise VerificationFailure(f"primary mode {index} independent residual failure")
        diagnostics.update(
            {
                "index": index,
                "eigenvalue": float(arrays["eigenvalues"][index]),
                "residual_absolute": residual_absolute,
                "residual_relative": residual_relative,
                "lifted_directional_curvature": float(vector @ lifted),
                "physical_directional_curvature": float(vector @ physical),
                "smallest_step_directional_curvature": curvature,
                "primary_recorded_smallest_step_curvature": primary_row[
                    "smallest_step_directional_curvature"
                ],
                "archive_reconstruction_relative": reconstruction,
            }
        )
        rows.append(diagnostics)
    return {
        "archive_sha256": sha256_file(MODES_PATH),
        "phase_vector_relative_difference": phase_difference,
        "modes": rows,
        "pass": True,
    }, arrays["base_vectors"]


def classify_modes(
    primary: dict[str, Any], independent: dict[str, Any], uncertainty: float
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(INDEPENDENT_SETTINGS["k"]):
        p = primary["modes"][index]
        q = independent["modes"][index]
        eigen_negative = p["eigenvalue"] + uncertainty < 0.0 and q["eigenvalue"] + uncertainty < 0.0
        curvature_negative = (
            p["smallest_step_directional_curvature"] + uncertainty < 0.0
            and q["smallest_step_directional_curvature"] + uncertainty < 0.0
        )
        eigen_positive = p["eigenvalue"] - uncertainty > 0.0 and q["eigenvalue"] - uncertainty > 0.0
        curvature_positive = (
            p["smallest_step_directional_curvature"] - uncertainty > 0.0
            and q["smallest_step_directional_curvature"] - uncertainty > 0.0
        )
        if eigen_negative and curvature_negative:
            classification = "negative"
        elif eigen_positive and curvature_positive:
            classification = "positive"
        else:
            classification = "near-zero"
        rows.append(
            {
                "index": index,
                "primary_eigenvalue": p["eigenvalue"],
                "independent_eigenvalue": q["eigenvalue"],
                "primary_smallest_step_curvature": p["smallest_step_directional_curvature"],
                "independent_smallest_step_curvature": q["smallest_step_directional_curvature"],
                "classification": classification,
                "primary_global_u1_overlap": p["overlaps"]["global_u1"],
                "independent_global_u1_overlap": q["overlaps"]["global_u1"],
                "primary_spatially_resolved": p["spatially_resolved"],
                "independent_spatially_resolved": q["spatially_resolved"],
            }
        )
    return rows


def run_final(manifest_path: Path, output_path: Path) -> int:
    started = time.perf_counter()
    manifest, manifest_hash = verify_manifest(manifest_path)
    if not PREFLIGHT_PATH.is_file():
        raise VerificationFailure("canonical independent preflight receipt is missing")
    preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    if not preflight.get("pass", False) or preflight.get("manifest_sha256") != manifest_hash:
        raise VerificationFailure("canonical independent preflight receipt is inadmissible")
    if not RESULTS_PATH.is_file():
        raise VerificationFailure("primary results receipt is missing")
    results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    if results.get("schema") != "cassi.particle-localized-physical-hessian.results.v1":
        raise VerificationFailure("primary result schema mismatch")
    if results.get("primary_status") != "PENDING—INDEPENDENT VERIFICATION":
        raise VerificationFailure("primary result status is not pending independent verification")
    if results.get("manifest_sha256") != manifest_hash or results.get("manifest") != manifest:
        raise VerificationFailure("primary result used another manifest")

    device = configure_torch()
    (
        fields,
        space,
        background,
        bases,
        alpha,
        gauge,
        projector,
    ) = build_state(device)
    operator, _ = operator_checks(space)
    directional = directional_checks(space, 161803)
    if not operator["pass"] or not directional["pass"]:
        raise VerificationFailure("independent final preflight reconstruction failed")
    primary, _ = verify_primary_archive(space, fields, results)
    independent, _ = independent_eigensolve(space, fields)

    primary_values = np.asarray(results["spectrum"]["eigenvalues"][: INDEPENDENT_SETTINGS["k"]])
    independent_values = np.asarray(independent["eigenvalues"])
    differences = np.abs(primary_values - independent_values)
    tolerances = 5.0e-6 + 5.0e-4 * np.abs(independent_values)
    eigenvalue_comparison_pass = bool(np.all(differences <= tolerances))

    fd_differences: list[float] = []
    for index in range(INDEPENDENT_SETTINGS["k"]):
        p = primary["modes"][index]
        q = independent["modes"][index]
        fd_differences.extend(
            (
                abs(p["smallest_step_directional_curvature"] - p["physical_directional_curvature"]),
                abs(q["smallest_step_directional_curvature"] - q["physical_directional_curvature"]),
                abs(
                    p["smallest_step_directional_curvature"]
                    - p["primary_recorded_smallest_step_curvature"]
                ),
            )
        )
    fd_differences.extend(
        row["steps"][-1]["curvature_error"] for row in directional["directions"]
    )
    primary_residual = max(row["residual_absolute"] for row in primary["modes"])
    independent_residual = independent["max_absolute_residual"]
    paired_difference = float(np.max(differences))
    fd_difference = max(fd_differences)
    gradient_rms = max(
        float(results["operator_preflight"]["augmented_gradient_rms"]),
        float(operator["augmented_gradient_rms"]),
    )
    uncertainty = max(
        10.0 * primary_residual,
        10.0 * independent_residual,
        10.0 * paired_difference,
        10.0 * fd_difference,
        10.0 * gradient_rms,
        1.0e-7,
    )
    classifications = classify_modes(primary, independent, uncertainty)
    negatives = [row for row in classifications if row["classification"] == "negative"]
    near_zero = [row for row in classifications if row["classification"] == "near-zero"]
    positives = [row for row in classifications if row["classification"] == "positive"]
    phase_assigned = (
        len(near_zero) == 1
        and near_zero[0]["primary_global_u1_overlap"] >= 0.90
        and near_zero[0]["independent_global_u1_overlap"] >= 0.90
    )
    spatial_rows = [row for row in classifications if row["classification"] in {"negative", "near-zero"}]
    spatial_pass = all(
        row["primary_spatially_resolved"] and row["independent_spatially_resolved"]
        for row in spatial_rows
    )

    gates = {
        "LH1_background_identity": True,
        "LH2_sparse_physical_quotient": True,
        "LH3_operator_preflight": operator["pass"] and directional["pass"],
        "LH4_paired_eigenspectra": bool(
            eigenvalue_comparison_pass
            and results["spectrum"]["finite"]
            and independent["finite"]
            and primary["pass"]
        ),
        "LH5_no_negative_physical_mode": len(negatives) == 0,
        "LH6_phase_assignment_and_positive_remainder": bool(
            len(negatives) == 0 and phase_assigned and len(positives) == 5
        ),
        "LH7_spatial_resolution": spatial_pass,
    }
    if not gates["LH1_background_identity"]:
        verdict = "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    elif not gates["LH2_sparse_physical_quotient"]:
        verdict = "INCONCLUSIVE—GAUGE QUOTIENT"
    elif not gates["LH3_operator_preflight"]:
        verdict = "INCONCLUSIVE—HESSIAN PREFLIGHT"
    elif not gates["LH4_paired_eigenspectra"]:
        verdict = "INCONCLUSIVE—EIGENSOLVER OR VERIFICATION"
    elif not gates["LH5_no_negative_physical_mode"]:
        verdict = "FAIL—NEGATIVE PHYSICAL MODE ON LOCALIZED BRANCH"
    elif not gates["LH6_phase_assignment_and_positive_remainder"]:
        verdict = "INCONCLUSIVE—UNRESOLVED PHYSICAL ZERO MODE"
    else:
        verdict = "PASS—NONNEGATIVE LOCALIZED C4 FINITE-GRID PA42 HESSIAN"
    spatial_verdict = (
        "PASS—SPATIALLY RESOLVED CLASSIFIED MODES"
        if spatial_pass
        else "INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE"
    )
    infrastructure_pass = all(
        gates[name]
        for name in (
            "LH1_background_identity",
            "LH2_sparse_physical_quotient",
            "LH3_operator_preflight",
            "LH4_paired_eigenspectra",
        )
    )
    campaign_pass = infrastructure_pass and all(
        gates[name]
        for name in (
            "LH5_no_negative_physical_mode",
            "LH6_phase_assignment_and_positive_remainder",
        )
    )
    receipt = {
        "schema": "cassi.particle-localized-physical-hessian.verification.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": environment_receipt(device),
        "background": background,
        "bases": bases,
        "alpha_basis": alpha,
        "coupled_gauge": gauge,
        "projector": projector,
        "charge_tangent": space.diagnostics,
        "operator_preflight": operator,
        "directional_preflight": directional,
        "primary_reconstruction": primary,
        "independent_spectrum": independent,
        "comparison": {
            "primary_eigenvalues": primary_values.tolist(),
            "independent_eigenvalues": independent_values.tolist(),
            "absolute_differences": differences.tolist(),
            "tolerances": tolerances.tolist(),
            "max_absolute_difference": paired_difference,
            "pass": eigenvalue_comparison_pass,
        },
        "uncertainty": {
            "primary_max_absolute_residual": primary_residual,
            "independent_max_absolute_residual": independent_residual,
            "paired_eigenvalue_difference": paired_difference,
            "finite_difference_disagreement": fd_difference,
            "augmented_gradient_rms": gradient_rms,
            "epsilon_lambda": uncertainty,
        },
        "classifications": classifications,
        "counts": {
            "negative": len(negatives),
            "near_zero": len(near_zero),
            "positive": len(positives),
        },
        "gates": gates,
        "verdict": verdict,
        "spatial_verdict": spatial_verdict,
        "hessian_resolution_verdict": "INCONCLUSIVE—NO LOCALIZED HESSIAN RESOLUTION SEQUENCE",
        "infrastructure_pass": infrastructure_pass,
        "pass": campaign_pass,
        "wall_seconds": time.perf_counter() - started,
        "artifact_hashes": {
            "preflight_verification.json": sha256_file(PREFLIGHT_PATH),
            "results.json": sha256_file(RESULTS_PATH),
            "eigenmodes.npz": sha256_file(MODES_PATH),
        },
    }
    write_json(output_path, receipt)
    print(
        json.dumps(
            {
                "infrastructure_pass": infrastructure_pass,
                "pass": campaign_pass,
                "verdict": verdict,
                "spatial_verdict": spatial_verdict,
                "epsilon_lambda": uncertainty,
                "primary_eigenvalues": primary_values.tolist(),
                "independent_eigenvalues": independent_values.tolist(),
                "wall_seconds": receipt["wall_seconds"],
            },
            indent=2,
        )
    )
    return 0 if campaign_pass else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="run the independent preflight only")
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH, help="manifest path")
    parser.add_argument("--output", type=Path, default=None, help="override receipt path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output or (PREFLIGHT_PATH if args.preflight else VERIFICATION_PATH)
    return run_preflight(args.manifest, output) if args.preflight else run_final(args.manifest, output)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except VerificationFailure as exc:
        args = parse_args()
        output = args.output or (PREFLIGHT_PATH if args.preflight else VERIFICATION_PATH)
        write_json(
            output,
            {
                "schema": (
                    "cassi.particle-localized-physical-hessian.preflight.v1"
                    if args.preflight
                    else "cassi.particle-localized-physical-hessian.verification.v1"
                ),
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "pass": False,
                "error": str(exc),
            },
        )
        print(f"LOCALIZED HESSIAN VERIFICATION FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
