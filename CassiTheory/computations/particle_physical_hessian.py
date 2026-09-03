#!/usr/bin/env python3
"""Compute the frozen PA42 finite-grid physical Hessian spectrum.

Run from the CassiTheory repository root:

    python computations/particle_physical_hessian.py
"""

from __future__ import annotations

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

import particle_stationary_bvp as stationary


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz"
RUN_DIR = ROOT / "runs/20260902_particle_physical_hessian"
RESULTS_PATH = RUN_DIR / "results.json"
MODES_PATH = RUN_DIR / "eigenmodes.npz"
MANIFEST_PATH = ROOT / "computations/particle_physical_hessian_manifest.json"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"

ARTIFACT_SHA256 = "99766cddb04107bb0c103c8f96254df651094054578867d37662ee7bff7e2550"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
OMEGA_C = 0.9619135625713447
FROZEN_BACKGROUND = {
    "physical_energy": 3.8542001269281165,
    "physical_gradient_rms": 1.936974511462461e-4,
    "cutoff_virial": 1.8910101999779969e-3,
    "omega_c": OMEGA_C,
    "charge": 4.0,
}

N = 17
M = N - 2
DX = 0.5
DV = DX**3
NS = 855
NV = 2535
N_ALPHA = 559
N_GAUGE = 3 * N_ALPHA
N_NONCARRIER = 7 * NS + 3 * NV
N_BASE = N_NONCARRIER + (NS - 1) + NS
N_PHYS = N_BASE - N_GAUGE
FIELD_COMPONENTS = 18
STEPS = (2.0e-4, 1.0e-4, 5.0e-5)
PAULI = 0.5 * np.asarray(
    (
        ((0.0, 1.0), (1.0, 0.0)),
        ((0.0, -1.0j), (1.0j, 0.0)),
        ((1.0, 0.0), (0.0, -1.0)),
    ),
    dtype=np.complex128,
)
ROTATION = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))


class HessianFailure(RuntimeError):
    """Raised when a frozen Hessian gate fails."""


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


def tensor_float(value: torch.Tensor) -> float:
    return float(value.detach().cpu())



def rotate_site(site: tuple[int, int, int]) -> tuple[int, int, int]:
    i, j, k = site
    return j, N - 1 - i, k


def orbit_partition(sites: list[tuple[int, int, int]]) -> list[list[tuple[int, int, int]]]:
    remaining = set(sites)
    result: list[list[tuple[int, int, int]]] = []
    while remaining:
        first = min(remaining)
        orbit: list[tuple[int, int, int]] = []
        site = first
        for _ in range(4):
            if site not in orbit:
                orbit.append(site)
            site = rotate_site(site)
        for site in orbit:
            remaining.remove(site)
        result.append(orbit)
    return result


def flat_index(site: tuple[int, int, int]) -> int:
    i, j, k = site
    return (i * N + j) * N + k


def interior_index(site: tuple[int, int, int]) -> int:
    i, j, k = site
    return ((i - 1) * M + (j - 1)) * M + (k - 1)


def source_derivative_matrix() -> np.ndarray:
    matrix = np.empty((N, N), dtype=np.float64)
    for column in range(N):
        field = np.zeros(N, dtype=np.float64)
        field[column] = 1.0
        matrix[:, column] = np.gradient(field, DX, edge_order=2)
    return matrix


def scalar_c4_project(field: np.ndarray) -> np.ndarray:
    return sum(np.rot90(field, k, axes=(0, 1)) for k in range(4)) / 4.0


def vector_c4_project(field: np.ndarray) -> np.ndarray:
    result = np.zeros_like(field)
    for k in range(4):
        rotated = np.rot90(field, k, axes=(0, 1))
        result += np.einsum("ij,...jc->...ic", np.linalg.matrix_power(ROTATION, k), rotated)
    return result / 4.0


def projection_residual(field: np.ndarray, projected: np.ndarray) -> float:
    return float(np.max(np.abs(field - projected)) / max(float(np.max(np.abs(field))), 1.0))


def boundary_max(field: np.ndarray) -> float:
    shell = np.zeros((N, N, N), dtype=bool)
    shell[[0, -1], :, :] = True
    shell[:, [0, -1], :] = True
    shell[:, :, [0, -1]] = True
    return float(np.max(np.abs(field[shell])))


def configure_torch() -> torch.device:
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cuda"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise HessianFailure("ROCm/CUDA PyTorch device is required by the frozen campaign")
    return torch.device("cuda:0")


def verify_manifest() -> tuple[dict[str, Any], str]:
    if not MANIFEST_PATH.is_file():
        raise HessianFailure(f"missing frozen manifest: {MANIFEST_PATH}")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest.get("sha256", {})
    if not isinstance(expected, dict) or not expected:
        raise HessianFailure("manifest has no sha256 mapping")
    mismatches: dict[str, dict[str, str]] = {}
    for relative, frozen_hash in expected.items():
        path = ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != frozen_hash:
            mismatches[relative] = {"expected": frozen_hash, "actual": actual}
    if mismatches:
        raise HessianFailure(f"source manifest mismatch: {mismatches}")
    return manifest, sha256_file(MANIFEST_PATH)


@dataclass
class BasisData:
    scalar_sparse: sparse.csr_matrix
    vector_sparse: sparse.csr_matrix
    scalar_index: np.ndarray
    scalar_weight: np.ndarray
    vector_index: np.ndarray
    vector_matrix: np.ndarray
    interior_orbits: list[list[tuple[int, int, int]]]


def build_bases() -> BasisData:
    interior_sites = [
        (i, j, k)
        for i in range(1, N - 1)
        for j in range(1, N - 1)
        for k in range(1, N - 1)
    ]
    orbits = orbit_partition(interior_sites)
    if len(orbits) != NS:
        raise HessianFailure(f"scalar C4 dimension {len(orbits)} != {NS}")

    scalar_rows: list[int] = []
    scalar_cols: list[int] = []
    scalar_values: list[float] = []
    scalar_index = np.zeros(N**3, dtype=np.int64)
    scalar_weight = np.zeros(N**3, dtype=np.float64)
    for column, orbit in enumerate(orbits):
        value = 1.0 / math.sqrt(len(orbit))
        for site in orbit:
            row = flat_index(site)
            scalar_rows.append(row)
            scalar_cols.append(column)
            scalar_values.append(value)
            scalar_index[row] = column
            scalar_weight[row] = value
    scalar_sparse = sparse.coo_matrix(
        (scalar_values, (scalar_rows, scalar_cols)), shape=(N**3, NS)
    ).tocsr()

    vector_rows: list[int] = []
    vector_cols: list[int] = []
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
            vector_cols.append(column)
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
                    if entry != 0.0:
                        vector_rows.append(component * M**3 + interior_index(site))
                        vector_cols.append(column)
                        vector_values.append(float(entry))
            column += 1
    if column != NV:
        raise HessianFailure(f"vector C4 dimension {column} != {NV}")
    vector_sparse = sparse.coo_matrix(
        (vector_values, (vector_rows, vector_cols)), shape=(3 * M**3, NV)
    ).tocsr()
    scalar_orth = np.max(np.abs((scalar_sparse.T @ scalar_sparse).toarray() - np.eye(NS)))
    vector_orth = np.max(np.abs((vector_sparse.T @ vector_sparse).toarray() - np.eye(NV)))
    if scalar_orth > 1.0e-12 or vector_orth > 1.0e-12:
        raise HessianFailure(f"nonorthogonal C4 bases: scalar={scalar_orth}, vector={vector_orth}")
    return BasisData(
        scalar_sparse=scalar_sparse,
        vector_sparse=vector_sparse,
        scalar_index=scalar_index,
        scalar_weight=scalar_weight,
        vector_index=vector_index,
        vector_matrix=vector_matrix,
        interior_orbits=orbits,
    )


def boundary_gauge_basis(bases: BasisData) -> tuple[np.ndarray, dict[str, Any]]:
    derivative = source_derivative_matrix()
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
            i in (0, N - 1) or j in (0, N - 1) or k in (0, N - 1)
            for i in range(N)
            for j in range(N)
            for k in range(N)
        ],
        dtype=bool,
    )
    boundary_matrix = (gradient @ bases.scalar_sparse)[np.tile(shell, 3), :].toarray()
    _, singular, right = svd(boundary_matrix, full_matrices=True, lapack_driver="gesdd")
    ranks = {
        f"relative_{threshold:.0e}": int(np.count_nonzero(singular > threshold * singular[0]))
        for threshold in (1.0e-10, 1.0e-11, 1.0e-12)
    }
    rank = ranks["relative_1e-11"]
    null = right[rank:, :].T.copy()
    orth = float(np.max(np.abs(null.T @ null - np.eye(null.shape[1]))))
    residual = float(np.linalg.norm(boundary_matrix @ null, ord=2))
    diagnostics = {
        "matrix_shape": list(boundary_matrix.shape),
        "ranks": ranks,
        "rank": rank,
        "null_dimension": int(null.shape[1]),
        "sigma_max": float(singular[0]),
        "sigma_last_retained": float(singular[rank - 1]),
        "sigma_first_null": float(singular[rank]),
        "null_orthogonality_max": orth,
        "null_residual_2": residual,
    }
    if rank != 296 or null.shape[1] != N_ALPHA or any(value != 296 for value in ranks.values()):
        raise HessianFailure(f"boundary gauge rank contract failed: {diagnostics}")
    if orth > 1.0e-11 or residual > 1.0e-11:
        raise HessianFailure(f"boundary gauge null contract failed: {diagnostics}")
    return null, diagnostics


def carrier_tangent_basis(c_values: np.ndarray, bases: BasisData) -> tuple[np.ndarray, np.ndarray, dict[str, float]]:
    reduced = np.asarray(bases.scalar_sparse.T @ c_values.reshape(-1), dtype=np.float64)
    unit = reduced / np.linalg.norm(reduced)
    sign = 1.0 if unit[0] >= 0.0 else -1.0
    reflector_vector = unit.copy()
    reflector_vector[0] += sign
    reflector_vector /= np.linalg.norm(reflector_vector)
    reflector = np.eye(NS) - 2.0 * np.outer(reflector_vector, reflector_vector)
    tangent = reflector[:, 1:].copy()
    orth = float(np.max(np.abs(tangent.T @ tangent - np.eye(NS - 1))))
    residual = float(np.max(np.abs(reduced @ tangent)))
    diagnostics = {
        "orthogonality_max": orth,
        "charge_normal_residual": residual,
        "reduced_carrier_norm": float(np.linalg.norm(reduced)),
    }
    if orth > 1.0e-11 or residual > 1.0e-11:
        raise HessianFailure(f"carrier tangent contract failed: {diagnostics}")
    return tangent, reduced, diagnostics


def coupled_gauge_matrix(
    fields: dict[str, np.ndarray], bases: BasisData, alpha_null: np.ndarray
) -> tuple[np.ndarray, dict[str, Any]]:
    alpha_fields = np.asarray(bases.scalar_sparse @ alpha_null).reshape(N, N, N, N_ALPHA)
    alpha_derivatives = np.gradient(alpha_fields, DX, axis=(0, 1, 2), edge_order=2)
    gauge = np.zeros((N_NONCARRIER, N_GAUGE), dtype=np.float64)
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h = fields["h"]
    a = fields["a"]
    interior = (slice(1, -1), slice(1, -1), slice(1, -1))

    sample: dict[str, float] = {}
    for input_color in range(3):
        columns = slice(input_color * N_ALPHA, (input_color + 1) * N_ALPHA)
        transformed_psi = np.einsum("ab,...b->...a", PAULI[input_color], psi)
        delta_psi = 1.0j * transformed_psi[..., None] * alpha_fields[..., None, :]
        for component in range(2):
            real = delta_psi[..., component, :].real.reshape(N**3, N_ALPHA)
            imag = delta_psi[..., component, :].imag.reshape(N**3, N_ALPHA)
            gauge[component * NS : (component + 1) * NS, columns] = bases.scalar_sparse.T @ real
            offset = (2 + component) * NS
            gauge[offset : offset + NS, columns] = bases.scalar_sparse.T @ imag

        delta_h = (
            np.cross(h, np.eye(3, dtype=np.float64)[input_color])[..., :, None]
            * alpha_fields[..., None, :]
        )
        for component in range(3):
            values = delta_h[..., component, :].reshape(N**3, N_ALPHA)
            offset = (4 + component) * NS
            gauge[offset : offset + NS, columns] = bases.scalar_sparse.T @ values

        for output_color in range(3):
            spatial_values: list[np.ndarray] = []
            for spatial_component in range(3):
                commutator = np.cross(
                    a[..., spatial_component, :], np.eye(3, dtype=np.float64)[input_color]
                )[..., output_color, None]
                delta_a = commutator * alpha_fields
                if output_color == input_color:
                    delta_a = delta_a + alpha_derivatives[spatial_component]
                spatial_values.append(delta_a[interior].reshape(M**3, N_ALPHA))
            stacked = np.concatenate(spatial_values, axis=0)
            offset = 7 * NS + output_color * NV
            gauge[offset : offset + NV, columns] = bases.vector_sparse.T @ stacked

        if input_color == 0:
            alpha = alpha_fields[..., 0]
            delta_psi_sample = 1.0j * transformed_psi * alpha[..., None]
            delta_h_sample = np.cross(h, np.eye(3)[0]) * alpha[..., None]
            delta_a_sample = np.zeros_like(a)
            for spatial_component in range(3):
                delta_a_sample[..., spatial_component, :] = (
                    np.cross(a[..., spatial_component, :], np.eye(3)[0]) * alpha[..., None]
                )
                delta_a_sample[..., spatial_component, 0] += alpha_derivatives[spatial_component][..., 0]
            sample = {
                "delta_psi_norm": float(np.linalg.norm(delta_psi_sample)),
                "delta_h_norm": float(np.linalg.norm(delta_h_sample)),
                "delta_a_norm": float(np.linalg.norm(delta_a_sample)),
                "alpha_shell_max": boundary_max(alpha),
                "delta_a_shell_max": boundary_max(delta_a_sample),
            }

    gram = gauge.T @ gauge
    eigenvalues = eigvalsh(gram, driver="evr")
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
        raise HessianFailure(f"coupled gauge rank contract failed: {diagnostics}")
    if sample["delta_a_shell_max"] > 1.0e-12:
        raise HessianFailure(f"boundary-preserving gauge generator failed: {diagnostics}")
    return gauge, diagnostics


class PhysicalSpace:
    def __init__(
        self,
        fields_np: dict[str, np.ndarray],
        bases: BasisData,
        carrier_tangent: np.ndarray,
        gauge_noncarrier: np.ndarray,
        device: torch.device,
    ) -> None:
        constraint = np.zeros((N_GAUGE, N_BASE), dtype=np.float64)
        constraint[:, :N_NONCARRIER] = gauge_noncarrier.T
        _, _, pivots = qr(constraint, mode="economic", pivoting=True, check_finite=False)
        self.pivots = np.asarray(pivots, dtype=np.int64)
        self.pivot = self.pivots[:N_GAUGE]
        self.free = self.pivots[N_GAUGE:]
        constraint_pivot = constraint[:, self.pivot]
        constraint_free = constraint[:, self.free]
        self.transform = np.linalg.solve(constraint_pivot, -constraint_free)
        parameterization_residual = float(
            np.max(np.abs(constraint_pivot @ self.transform + constraint_free))
        )
        pivot_condition = float(np.linalg.cond(constraint_pivot))
        transform_norm = float(np.linalg.norm(self.transform, ord=2))
        if pivot_condition > 1.0e3 or parameterization_residual > 1.0e-10:
            raise HessianFailure(
                f"gauge quotient parameterization failed: condition={pivot_condition}, "
                f"residual={parameterization_residual}"
            )
        metric_core = np.eye(N_GAUGE) + self.transform @ self.transform.T
        self.metric_cholesky = cho_factor(metric_core, lower=True, check_finite=False)
        inverse_probe = np.random.default_rng(99017).normal(size=N_PHYS)
        inverse_residual = np.linalg.norm(
            self.metric(self.metric_inverse(inverse_probe)) - inverse_probe
        ) / np.linalg.norm(inverse_probe)
        if inverse_residual > 1.0e-10:
            raise HessianFailure(f"Woodbury metric inverse residual {inverse_residual}")

        self.constraint = constraint
        self.gauge_noncarrier = gauge_noncarrier
        self.bases = bases
        self.device = device
        self.transform_t = torch.as_tensor(self.transform, dtype=torch.float64, device=device)
        self.pivot_t = torch.as_tensor(self.pivot, dtype=torch.long, device=device)
        self.free_t = torch.as_tensor(self.free, dtype=torch.long, device=device)
        self.scalar_index_t = torch.as_tensor(bases.scalar_index, dtype=torch.long, device=device)
        self.scalar_weight_t = torch.as_tensor(bases.scalar_weight, dtype=torch.float64, device=device)
        self.vector_index_t = torch.as_tensor(bases.vector_index, dtype=torch.long, device=device)
        self.vector_matrix_t = torch.as_tensor(bases.vector_matrix, dtype=torch.float64, device=device)
        self.carrier_tangent_t = torch.as_tensor(carrier_tangent, dtype=torch.float64, device=device)
        self.background = {
            name: torch.as_tensor(value, dtype=torch.float64, device=device)
            for name, value in fields_np.items()
        }
        self.grid = stationary.make_grid("P", device)
        self.diagnostics = {
            "constraint_shape": list(constraint.shape),
            "pivot_condition_2": pivot_condition,
            "transform_shape": list(self.transform.shape),
            "transform_norm_2": transform_norm,
            "parameterization_residual_max": parameterization_residual,
            "metric_inverse_probe_relative": float(inverse_residual),
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
            raise HessianFailure("cannot metric-normalize quotient vector")
        return vector / norm

    def base_from_quotient_np(self, vector: np.ndarray) -> np.ndarray:
        base = np.empty(N_BASE, dtype=np.float64)
        base[self.free] = vector
        base[self.pivot] = self.transform @ vector
        return base

    def base_from_quotient_torch(self, vector: torch.Tensor) -> torch.Tensor:
        base = torch.zeros(N_BASE, dtype=torch.float64, device=self.device)
        base = base.index_copy(0, self.free_t, vector)
        base = base.index_copy(0, self.pivot_t, self.transform_t @ vector)
        return base

    def quotient_covector_torch(self, base_covector: torch.Tensor) -> torch.Tensor:
        return base_covector[self.free_t] + self.transform_t.T @ base_covector[self.pivot_t]

    def scalar_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        values = self.scalar_weight_t * coefficients[self.scalar_index_t]
        return values.reshape(N, N, N)

    def vector_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        gathered = coefficients[self.vector_index_t, :]
        values = torch.einsum("nis,nsc->nic", self.vector_matrix_t, gathered)
        return values.reshape(N, N, N, 3, 3)

    def fields_from_base(self, base: torch.Tensor) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        scalar = base[: 7 * NS].reshape(7, NS)
        delta_scalars = torch.stack([self.scalar_field(scalar[index]) for index in range(7)], dim=-1)
        gauge_coefficients = base[7 * NS : N_NONCARRIER].reshape(3, NV).T
        delta_a = self.vector_field(gauge_coefficients)
        carrier_real_coeff = self.carrier_tangent_t @ base[N_NONCARRIER : N_NONCARRIER + NS - 1]
        carrier_imag_coeff = base[N_NONCARRIER + NS - 1 :]
        delta_carrier_real = self.scalar_field(carrier_real_coeff)
        carrier_imag = self.scalar_field(carrier_imag_coeff)
        fields = {
            "psi_real": self.background["psi_real"] + delta_scalars[..., 0:2],
            "psi_imag": self.background["psi_imag"] + delta_scalars[..., 2:4],
            "h": self.background["h"] + delta_scalars[..., 4:7],
            "a": self.background["a"] + delta_a,
            "c": self.background["c"] + delta_carrier_real,
        }
        return fields, carrier_imag

    def lagrangian_from_base(self, base: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        fields, carrier_imag = self.fields_from_base(base)
        components, _, aux = stationary.energy_components(fields, self.grid)
        noncarrier = torch.stack(
            tuple(value for name, value in components.items() if not name.startswith("carrier_"))
        ).sum()
        carrier_real = fields["c"]
        carrier_modulus2 = carrier_real**2 + carrier_imag**2
        derivative_real = stationary.derivatives(carrier_real, self.grid)
        derivative_imag = stationary.derivatives(carrier_imag, self.grid)
        carrier_gradient = (
            0.5
            * stationary.COEFFICIENTS["k_Cx"]
            * sum(
                torch.sum(real_derivative**2 + imag_derivative**2)
                for real_derivative, imag_derivative in zip(derivative_real, derivative_imag)
            )
            * self.grid.dv
        )
        trap = stationary.COEFFICIENTS["e_C"] - stationary.COEFFICIENTS["h_C"] * (
            1.0 - aux["rho"]
        )
        carrier_quadratic = torch.sum(trap * carrier_modulus2) * self.grid.dv
        carrier_quartic = (
            0.5
            * stationary.COEFFICIENTS["u_C"]
            * torch.sum(carrier_modulus2**2)
            * self.grid.dv
        )
        physical = noncarrier + carrier_gradient + carrier_quadratic + carrier_quartic
        charge = torch.sum(carrier_modulus2) * self.grid.dv
        return physical - OMEGA_C * charge, physical, charge

    def lagrangian(self, quotient: np.ndarray) -> float:
        vector = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        base = self.base_from_quotient_torch(vector)
        value, _, _ = self.lagrangian_from_base(base)
        return tensor_float(value)

    def gradient(self, quotient: np.ndarray) -> np.ndarray:
        vector = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        base = self.base_from_quotient_torch(vector).detach().requires_grad_(True)
        value, _, _ = self.lagrangian_from_base(base)
        base_gradient = torch.autograd.grad(value, base)[0]
        quotient_gradient = self.quotient_covector_torch(base_gradient) / self.grid.dv
        return quotient_gradient.detach().cpu().numpy()

    def hvp(self, quotient: np.ndarray) -> np.ndarray:
        direction = torch.as_tensor(quotient, dtype=torch.float64, device=self.device)
        base_direction = self.base_from_quotient_torch(direction)
        base = torch.zeros(N_BASE, dtype=torch.float64, device=self.device, requires_grad=True)
        value, _, _ = self.lagrangian_from_base(base)
        first = torch.autograd.grad(value, base, create_graph=True)[0]
        directional = torch.dot(first, base_direction)
        second = torch.autograd.grad(directional, base)[0]
        projected = self.quotient_covector_torch(second) / self.grid.dv
        return projected.detach().cpu().numpy()

    def base_mode(self, quotient: np.ndarray) -> np.ndarray:
        return self.base_from_quotient_np(quotient)

    def mode_fields(self, quotient: np.ndarray) -> dict[str, np.ndarray]:
        base = torch.as_tensor(self.base_from_quotient_np(quotient), dtype=torch.float64, device=self.device)
        zero_background = {name: value.clone() for name, value in self.background.items()}
        fields, carrier_imag = self.fields_from_base(base)
        return {
            "psi_real": (fields["psi_real"] - zero_background["psi_real"]).detach().cpu().numpy(),
            "psi_imag": (fields["psi_imag"] - zero_background["psi_imag"]).detach().cpu().numpy(),
            "h": (fields["h"] - zero_background["h"]).detach().cpu().numpy(),
            "a": (fields["a"] - zero_background["a"]).detach().cpu().numpy(),
            "chi_real": (fields["c"] - zero_background["c"]).detach().cpu().numpy(),
            "chi_imag": carrier_imag.detach().cpu().numpy(),
        }


def load_background(device: torch.device) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if sha256_file(ARTIFACT) != ARTIFACT_SHA256:
        raise HessianFailure("selected NPZ hash mismatch")
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
            raise HessianFailure(f"artifact keys {archive.files} != {sorted(expected_shapes)}")
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
            raise HessianFailure(f"artifact schema failure for {name}: {schema[name]}")
        if not np.all(np.isfinite(value)):
            raise HessianFailure(f"nonfinite artifact array {name}")
    if np.max(np.abs(arrays["x"] - np.linspace(-4.0, 4.0, N))) > 1.0e-14:
        raise HessianFailure("artifact coordinate grid mismatch")

    fields_np = {name: arrays[name] for name in ("psi_real", "psi_imag", "h", "a", "c")}
    shell_residuals = {
        "psi_real": boundary_max(
            arrays["psi_real"] - np.asarray((PHI**-0.5, PHI**-1.0), dtype=np.float64)
        ),
        "psi_imag": boundary_max(arrays["psi_imag"]),
        "h": boundary_max(arrays["h"] - np.asarray((0.0, 0.0, 1.0), dtype=np.float64)),
        "a": boundary_max(arrays["a"]),
        "c": boundary_max(arrays["c"]),
    }
    c4_residuals = {
        "psi_real": projection_residual(arrays["psi_real"], scalar_c4_project(arrays["psi_real"])),
        "psi_imag": projection_residual(arrays["psi_imag"], scalar_c4_project(arrays["psi_imag"])),
        "h": projection_residual(arrays["h"], scalar_c4_project(arrays["h"])),
        "a": projection_residual(arrays["a"], vector_c4_project(arrays["a"])),
        "c": projection_residual(arrays["c"], scalar_c4_project(arrays["c"])),
    }
    if max(shell_residuals.values()) > 1.0e-12 or max(c4_residuals.values()) > 5.0e-12:
        raise HessianFailure(
            f"background boundary/C4 contract failed: shell={shell_residuals}, C4={c4_residuals}"
        )

    grid = stationary.make_grid("P", device)
    fields_t = {
        name: torch.as_tensor(value, dtype=torch.float64, device=device) for name, value in fields_np.items()
    }
    components, _, _ = stationary.energy_components(fields_t, grid)
    physical_energy = tensor_float(torch.stack(tuple(components.values())).sum())
    charge = tensor_float(torch.sum(fields_t["c"] ** 2) * grid.dv)
    omega = tensor_float(
        (
            components["carrier_gradient"]
            + components["carrier_quadratic"]
            + 2.0 * components["carrier_quartic"]
        )
        / charge
    )
    physical_gradient = stationary.physical_gradient_rms(fields_t, grid)
    cutoff, _, _ = stationary.virial_diagnostics(fields_t, grid, components)
    measured = {
        "physical_energy": physical_energy,
        "physical_gradient_rms": physical_gradient,
        "cutoff_virial": cutoff,
        "omega_c": omega,
        "charge": charge,
    }
    comparisons: dict[str, Any] = {}
    for name, target in FROZEN_BACKGROUND.items():
        error = abs(measured[name] - target)
        tolerance = 1.0e-11 + 1.0e-9 * abs(target)
        comparisons[name] = {"measured": measured[name], "frozen": target, "error": error, "tolerance": tolerance}
        if error > tolerance:
            raise HessianFailure(f"frozen background scalar mismatch: {name}: {comparisons[name]}")
    if abs(charge - 4.0) / 4.0 > 1.0e-12:
        raise HessianFailure(f"charge mismatch: {charge}")
    diagnostics = {
        "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": ARTIFACT_SHA256,
        "schema": schema,
        "shell_residuals": shell_residuals,
        "c4_residuals": c4_residuals,
        "scalars": comparisons,
    }
    return fields_np, diagnostics


def directional_preflight(space: PhysicalSpace, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    passes = True
    for index in range(3):
        direction = space.normalize(rng.normal(size=N_PHYS))
        exact = space.hvp(direction)
        exact_curvature = float(direction @ exact)
        step_rows: list[dict[str, float]] = []
        for step in STEPS:
            plus_gradient = space.gradient(step * direction)
            minus_gradient = space.gradient(-step * direction)
            finite_hvp = (plus_gradient - minus_gradient) / (2.0 * step)
            vector_relative = float(
                np.linalg.norm(finite_hvp - exact) / max(np.linalg.norm(exact), 1.0)
            )
            energy_curvature = (
                space.lagrangian(step * direction)
                - 2.0 * space.lagrangian(np.zeros(N_PHYS))
                + space.lagrangian(-step * direction)
            ) / (step**2 * DV)
            curvature_error = abs(energy_curvature - exact_curvature)
            curvature_tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
            step_rows.append(
                {
                    "step": step,
                    "vector_relative_error": vector_relative,
                    "energy_curvature": energy_curvature,
                    "exact_curvature": exact_curvature,
                    "curvature_error": curvature_error,
                    "curvature_tolerance": curvature_tolerance,
                }
            )
        smallest = step_rows[-1]
        step_agreement = abs(step_rows[-1]["energy_curvature"] - step_rows[-2]["energy_curvature"])
        step_tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
        passed = (
            smallest["vector_relative_error"] <= 5.0e-5
            and smallest["curvature_error"] <= smallest["curvature_tolerance"]
            and step_agreement <= step_tolerance
        )
        passes = passes and passed
        rows.append(
            {
                "direction": index,
                "metric_norm": float(direction @ space.metric(direction)),
                "exact_curvature": exact_curvature,
                "steps": step_rows,
                "two_smallest_energy_curvature_difference": step_agreement,
                "step_agreement_tolerance": step_tolerance,
                "pass": passed,
            }
        )
    return {"seed": seed, "directions": rows, "pass": passes}


def operator_preflight(space: PhysicalSpace, carrier_reduced: np.ndarray) -> dict[str, Any]:
    zero = np.zeros(N_PHYS, dtype=np.float64)
    quotient_gradient = space.gradient(zero)
    gradient_rms = math.sqrt(
        float(quotient_gradient @ space.metric_inverse(quotient_gradient)) / N_PHYS
    )
    rng = np.random.default_rng(57721)
    symmetry_rows: list[dict[str, float]] = []
    symmetry_pass = True
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
        symmetry_pass = symmetry_pass and relative <= 1.0e-9

    phase_base = np.zeros(N_BASE, dtype=np.float64)
    phase_coefficients = carrier_reduced / np.linalg.norm(carrier_reduced)
    phase_base[N_NONCARRIER + NS - 1 :] = phase_coefficients
    phase = phase_base[space.free]
    reproduction = np.linalg.norm(space.base_from_quotient_np(phase) - phase_base)
    phase = space.normalize(phase)
    phase_hvp = space.hvp(phase)
    phase_rayleigh = float(phase @ phase_hvp)
    phase_residual = float(np.linalg.norm(phase_hvp))
    passed = (
        gradient_rms <= 3.0e-4
        and symmetry_pass
        and abs(phase_rayleigh) <= 1.0e-10
        and reproduction <= 1.0e-11
    )
    return {
        "augmented_gradient_rms": gradient_rms,
        "augmented_gradient_limit": 3.0e-4,
        "operator_symmetry": symmetry_rows,
        "operator_symmetry_pass": symmetry_pass,
        "phase_generator_reproduction": float(reproduction),
        "phase_rayleigh": phase_rayleigh,
        "phase_hessian_residual": phase_residual,
        "phase_rayleigh_limit": 1.0e-10,
        "phase_quotient_vector": phase,
        "pass": passed,
    }


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
    numerator = float(np.sum(left * right))
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return abs(numerator) / denominator if denominator > 0.0 else 0.0


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
    derivatives = np.gradient(background, DX, axis=(0, 1, 2), edge_order=2)
    coordinates = np.linspace(-4.0, 4.0, N)
    x, y, _ = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    axial = -(x[..., None] * derivatives[1] - y[..., None] * derivatives[0])
    a_slice = slice(7, 16)
    axial_a = axial[..., a_slice].reshape(N, N, N, 3, 3)
    background_a = fields["a"]
    spatial_generator = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    axial_a += np.einsum("ij,...jc->...ic", spatial_generator, background_a)
    axial[..., a_slice] = axial_a.reshape(N, N, N, 9)
    phase = np.zeros_like(background)
    phase[..., -1] = fields["c"]
    charge_normal = np.zeros_like(background)
    charge_normal[..., -2] = fields["c"]
    return {
        "translation_x": -derivatives[0],
        "translation_y": -derivatives[1],
        "translation_z": -derivatives[2],
        "axial_rotation": axial,
        "global_u1": phase,
        "charge_normal": charge_normal,
    }


def mode_diagnostics(
    space: PhysicalSpace,
    quotient: np.ndarray,
    base: np.ndarray,
    mode: dict[str, np.ndarray],
    probes: dict[str, np.ndarray],
) -> dict[str, Any]:
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
    high_fraction = high_fft / total_fft
    group_norms = {
        "psi": float(np.sum(mode["psi_real"] ** 2) + np.sum(mode["psi_imag"] ** 2)),
        "h": float(np.sum(mode["h"] ** 2)),
        "a": float(np.sum(mode["a"] ** 2)),
        "chi_real": float(np.sum(mode["chi_real"] ** 2)),
        "chi_imag": float(np.sum(mode["chi_imag"] ** 2)),
    }
    total_norm = sum(group_norms.values())
    component_fractions = {name: value / total_norm for name, value in group_norms.items()}
    shell = boundary_max(stacked)
    carrier_background = space.background["c"].detach().cpu().numpy()
    charge_tangent_relative = abs(float(np.sum(carrier_background * mode["chi_real"]))) / max(
        float(np.linalg.norm(carrier_background) * np.linalg.norm(mode["chi_real"])), 1.0
    )
    gauge_residual = float(np.linalg.norm(space.constraint @ base) / max(np.linalg.norm(base), 1.0))
    metric_norm = float(quotient @ space.metric(quotient))
    overlaps = {name: normalized_overlap(stacked, probe) for name, probe in probes.items()}
    return {
        "participation": participation,
        "high_frequency_fraction": high_fraction,
        "spatially_resolved": participation >= 16.0 and high_fraction <= 0.20,
        "component_fractions": component_fractions,
        "shell_max": shell,
        "charge_tangent_relative": charge_tangent_relative,
        "gauge_orthogonality_relative": gauge_residual,
        "metric_norm": metric_norm,
        "overlaps": overlaps,
    }


def run_spectrum(
    space: PhysicalSpace,
    fields_np: dict[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    operator = LinearOperator(
        shape=(N_PHYS, N_PHYS), dtype=np.float64, matvec=space.hvp, rmatvec=space.hvp
    )
    metric = LinearOperator(
        shape=(N_PHYS, N_PHYS), dtype=np.float64, matvec=space.metric, rmatvec=space.metric
    )
    metric_inverse = LinearOperator(
        shape=(N_PHYS, N_PHYS),
        dtype=np.float64,
        matvec=space.metric_inverse,
        rmatvec=space.metric_inverse,
    )
    rng = np.random.default_rng(424242)
    initial = space.normalize(rng.normal(size=N_PHYS))
    started = time.perf_counter()
    try:
        eigenvalues, eigenvectors = eigsh(
            operator,
            k=12,
            M=metric,
            Minv=metric_inverse,
            which="SA",
            ncv=48,
            tol=1.0e-9,
            maxiter=2000,
            v0=initial,
            return_eigenvectors=True,
        )
    except ArpackNoConvergence as exc:
        raise HessianFailure(
            f"primary ARPACK did not converge: {len(exc.eigenvalues)} partial eigenvalues"
        ) from exc
    elapsed = time.perf_counter() - started
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)
    metric_gram = eigenvectors.T @ np.column_stack(
        [space.metric(eigenvectors[:, index]) for index in range(eigenvectors.shape[1])]
    )
    orthogonality = float(np.max(np.abs(metric_gram - np.eye(12))))
    if orthogonality > 1.0e-8:
        raise HessianFailure(f"primary metric orthogonality residual {orthogonality}")

    probes = symmetry_probes(fields_np)
    zero_lagrangian = space.lagrangian(np.zeros(N_PHYS, dtype=np.float64))
    modes: list[dict[str, Any]] = []
    base_vectors = np.empty((N_BASE, 12), dtype=np.float64)
    mode_arrays: dict[str, list[np.ndarray]] = {
        "psi_real": [],
        "psi_imag": [],
        "h": [],
        "a": [],
        "chi_real": [],
        "chi_imag": [],
    }
    residual_norms: list[float] = []
    for index in range(12):
        vector = eigenvectors[:, index]
        k_vector = space.hvp(vector)
        m_vector = space.metric(vector)
        exact_curvature = float(vector @ k_vector)
        directional_curvature: float | None = None
        if index < 6:
            step = STEPS[-1]
            directional_curvature = (
                space.lagrangian(step * vector)
                - 2.0 * zero_lagrangian
                + space.lagrangian(-step * vector)
            ) / (step**2 * DV)
        residual_vector = k_vector - eigenvalues[index] * m_vector
        residual_absolute = float(np.linalg.norm(residual_vector))
        residual_relative = residual_absolute / max(
            abs(float(eigenvalues[index])) * float(np.linalg.norm(m_vector)), 1.0
        )
        if residual_relative > 1.0e-6:
            raise HessianFailure(f"primary eigenpair {index} residual {residual_relative}")
        base = space.base_mode(vector)
        mode = space.mode_fields(vector)
        base_vectors[:, index] = base
        for name in mode_arrays:
            mode_arrays[name].append(mode[name])
        diagnostic = mode_diagnostics(space, vector, base, mode, probes)
        if (
            diagnostic["shell_max"] > 1.0e-12
            or diagnostic["charge_tangent_relative"] > 1.0e-11
            or diagnostic["gauge_orthogonality_relative"] > 1.0e-10
            or abs(diagnostic["metric_norm"] - 1.0) > 1.0e-10
        ):
            raise HessianFailure(f"primary mode {index} constraint failure: {diagnostic}")
        diagnostic.update(
            {
                "index": index,
                "eigenvalue": float(eigenvalues[index]),
                "residual_absolute": residual_absolute,
                "residual_relative": residual_relative,
                "exact_directional_curvature": exact_curvature,
                "smallest_step_directional_curvature": directional_curvature,
            }
        )
        modes.append(diagnostic)
        residual_norms.append(residual_absolute)

    saved = {
        "eigenvalues": eigenvalues,
        "quotient_vectors": eigenvectors,
        "base_vectors": base_vectors,
        "pivot_indices": space.pivot,
        "free_indices": space.free,
    }
    saved.update({name: np.stack(values, axis=0) for name, values in mode_arrays.items()})
    spectrum = {
        "settings": {
            "k": 12,
            "which": "SA",
            "ncv": 48,
            "tolerance": 1.0e-9,
            "maxiter": 2000,
            "seed": 424242,
        },
        "wall_seconds": elapsed,
        "eigenvalues": [float(value) for value in eigenvalues],
        "max_absolute_residual": max(residual_norms),
        "metric_orthogonality_max": orthogonality,
        "modes": modes,
        "finite": bool(np.all(np.isfinite(eigenvalues)) and np.all(np.isfinite(eigenvectors))),
    }
    return spectrum, saved


def main() -> int:
    started = time.perf_counter()
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    manifest, manifest_hash = verify_manifest()
    if not PREFLIGHT_PATH.is_file():
        raise HessianFailure("independent preflight receipt is missing")
    independent_preflight = json.loads(PREFLIGHT_PATH.read_text(encoding="utf-8"))
    if not independent_preflight.get("pass", False):
        raise HessianFailure("independent preflight did not pass")
    if independent_preflight.get("manifest_sha256") != manifest_hash:
        raise HessianFailure("independent preflight used a different manifest")

    device = configure_torch()
    fields_np, background = load_background(device)
    bases = build_bases()
    alpha_null, boundary_gauge = boundary_gauge_basis(bases)
    carrier_tangent, carrier_reduced, carrier = carrier_tangent_basis(fields_np["c"], bases)
    gauge, coupled_gauge = coupled_gauge_matrix(fields_np, bases, alpha_null)
    space = PhysicalSpace(fields_np, bases, carrier_tangent, gauge, device)
    operator_checks = operator_preflight(space, carrier_reduced)
    directional = directional_preflight(space, 271828)
    if not operator_checks["pass"] or not directional["pass"]:
        raise HessianFailure(
            f"primary Hessian preflight failed: operator={operator_checks}, directional={directional}"
        )

    phase_vector = operator_checks.pop("phase_quotient_vector")
    spectrum, saved = run_spectrum(space, fields_np)
    saved["global_u1_quotient_vector"] = phase_vector
    np.savez_compressed(MODES_PATH, **saved)
    results = {
        "schema": "cassi.particle-physical-hessian.results.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": {
            "python": sys.version,
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
            "torch": torch.__version__,
            "device": str(device),
            "device_name": torch.cuda.get_device_name(device),
            "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES"),
            "PYTORCH_HIP_ALLOC_CONF": os.environ.get("PYTORCH_HIP_ALLOC_CONF"),
            "HSA_ENABLE_SDMA": os.environ.get("HSA_ENABLE_SDMA"),
        },
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
        "boundary_gauge": boundary_gauge,
        "carrier_tangent": carrier,
        "coupled_gauge": coupled_gauge,
        "quotient": space.diagnostics,
        "operator_preflight": operator_checks,
        "directional_preflight": directional,
        "spectrum": spectrum,
        "primary_status": "PENDING—INDEPENDENT VERIFICATION",
        "domain_resolution_verdict": "INCONCLUSIVE—NO Q2 DOMAIN/RESOLUTION BACKGROUNDS",
        "wall_seconds": time.perf_counter() - started,
        "artifacts": {
            "eigenmodes": str(MODES_PATH.relative_to(ROOT)).replace("\\", "/"),
            "eigenmodes_sha256": sha256_file(MODES_PATH),
        },
    }
    write_json(RESULTS_PATH, results)
    print(json.dumps({
        "primary_status": results["primary_status"],
        "eigenvalues": spectrum["eigenvalues"],
        "max_residual": spectrum["max_absolute_residual"],
        "wall_seconds": results["wall_seconds"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HessianFailure as exc:
        write_json(
            RESULTS_PATH,
            {
                "schema": "cassi.particle-physical-hessian.results.v1",
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "primary_status": "INCONCLUSIVE—IMPLEMENTATION OR HESSIAN PREFLIGHT",
                "error": str(exc),
            },
        )
        print(f"HESSIAN FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
