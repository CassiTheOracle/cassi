#!/usr/bin/env python3
"""Compute the frozen localized-carrier PA42 physical Hessian spectrum.

Run from the CassiTheory repository root:

    python computations/particle_localized_physical_hessian.py
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy import sparse
from scipy.sparse.linalg import ArpackNoConvergence, LinearOperator, eigsh, splu

import particle_stationary_bvp as stationary


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz"
SOURCE_RESULTS = ROOT / "runs/20260902_particle_carrier_resolution_recovery/results.json"
SOURCE_VERIFICATION = ROOT / "runs/20260902_particle_carrier_resolution_recovery/verification.json"
RUN_DIR = ROOT / "runs/20260903_particle_localized_physical_hessian"
RESULTS_PATH = RUN_DIR / "results.json"
MODES_PATH = RUN_DIR / "eigenmodes.npz"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
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
M = N - 2
CORE_M = N - 4
R = 4.0
DX = 2.0 / 7.0
DV = DX**3
NS = 4941
NV = 14769
N_ALPHA = 3925
N_GAUGE = 3 * N_ALPHA
N_NONCARRIER = 7 * NS + 3 * NV
N_BASE = N_NONCARRIER + (NS - 1) + NS
N_PHYS = N_BASE - N_GAUGE
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
VERIFIER_SETTINGS = {
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
    "independent_eigensolver": VERIFIER_SETTINGS,
    "source_hashes": SOURCE_HASHES,
    "source_verdict": SOURCE_VERDICT,
}
ROTATION = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)))
PAULI = 0.5 * np.asarray(
    (
        ((0.0, 1.0), (1.0, 0.0)),
        ((0.0, -1.0j), (1.0j, 0.0)),
        ((1.0, 0.0), (0.0, -1.0)),
    ),
    dtype=np.complex128,
)


class HessianFailure(RuntimeError):
    """Raised when a frozen localized-Hessian gate fails."""


def sha256_file(path: Path) -> str:
    if path.suffix.lower() in {".json", ".md", ".py"}:
        return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
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


def tensor_float(value: torch.Tensor) -> float:
    return float(value.detach().cpu())


def verify_manifest(path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise HessianFailure(f"missing frozen manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("schema") != "cassi.particle-localized-physical-hessian.manifest.v1":
        raise HessianFailure("manifest schema mismatch")
    if manifest.get("campaign") != "particle_localized_physical_hessian":
        raise HessianFailure("manifest campaign mismatch")
    if manifest.get("protocol") != EXPECTED_PROTOCOL:
        raise HessianFailure("manifest protocol differs from frozen implementation constants")
    expected = manifest.get("sha256")
    if not isinstance(expected, dict) or not expected:
        raise HessianFailure("manifest has no sha256 mapping")
    mismatches: dict[str, dict[str, str]] = {}
    for relative, frozen_hash in expected.items():
        candidate = ROOT / relative
        actual = sha256_file(candidate) if candidate.is_file() else "MISSING"
        if actual != frozen_hash:
            mismatches[relative] = {"expected": frozen_hash, "actual": actual}
    if mismatches:
        raise HessianFailure(f"source manifest mismatch: {mismatches}")
    return manifest, sha256_file(path)


def configure_torch() -> torch.device:
    torch.set_default_dtype(torch.float64)
    torch.use_deterministic_algorithms(True)
    if hasattr(torch.backends, "cuda"):
        torch.backends.cuda.matmul.allow_tf32 = False
    if hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.allow_tf32 = False
    if not torch.cuda.is_available():
        raise HessianFailure("ROCm/CUDA PyTorch device is required by the frozen campaign")
    stationary.COEFFICIENTS.clear()
    stationary.COEFFICIENTS.update(COEFFICIENTS)
    return torch.device("cuda:0")


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


def sparse_max_abs(matrix: sparse.spmatrix) -> float:
    return float(np.max(np.abs(matrix.data))) if matrix.nnz else 0.0


def clean(matrix: sparse.spmatrix, fmt: str = "csr") -> sparse.spmatrix:
    result = matrix.asformat(fmt)
    result.eliminate_zeros()
    return result


def derivative_1d() -> sparse.csr_matrix:
    matrix = np.empty((N, N), dtype=np.float64)
    for column in range(N):
        field = np.zeros(N, dtype=np.float64)
        field[column] = 1.0
        matrix[:, column] = np.gradient(field, DX, edge_order=2)
    return sparse.csr_matrix(matrix)


def derivative_operators() -> tuple[sparse.csr_matrix, ...]:
    derivative = derivative_1d()
    identity = sparse.eye(N, format="csr")
    return (
        sparse.kron(sparse.kron(derivative, identity), identity, format="csr"),
        sparse.kron(sparse.kron(identity, derivative), identity, format="csr"),
        sparse.kron(sparse.kron(identity, identity), derivative, format="csr"),
    )


def shell_mask() -> np.ndarray:
    shell = np.zeros((N, N, N), dtype=bool)
    shell[[0, -1], :, :] = True
    shell[:, [0, -1], :] = True
    shell[:, :, [0, -1]] = True
    return shell.reshape(-1)


def scalar_c4_project(field: np.ndarray) -> np.ndarray:
    return sum(np.rot90(field, turn, axes=(0, 1)) for turn in range(4)) / 4.0


def vector_c4_project(field: np.ndarray) -> np.ndarray:
    result = np.zeros_like(field)
    for turn in range(4):
        rotated = np.rot90(field, turn, axes=(0, 1))
        result += np.einsum("ij,...jc->...ic", np.linalg.matrix_power(ROTATION, turn), rotated)
    return result / 4.0


def projection_residual(field: np.ndarray, projected: np.ndarray) -> float:
    return float(np.max(np.abs(field - projected)) / max(float(np.max(np.abs(field))), 1.0))


def boundary_max(field: np.ndarray) -> float:
    return float(np.max(np.abs(field.reshape(N**3, -1)[shell_mask()])))


@dataclass
class BasisData:
    scalar: sparse.csr_matrix
    vector: sparse.csr_matrix
    scalar_index: np.ndarray
    scalar_weight: np.ndarray
    vector_index: np.ndarray
    vector_matrix: np.ndarray
    interior_rows: np.ndarray
    diagnostics: dict[str, Any]


def build_bases() -> BasisData:
    sites = [(i, j, k) for i in range(1, N - 1) for j in range(1, N - 1) for k in range(1, N - 1)]
    orbits = orbit_partition(sites)
    if len(orbits) != NS:
        raise HessianFailure(f"scalar C4 dimension {len(orbits)} != {NS}")

    scalar_rows: list[int] = []
    scalar_cols: list[int] = []
    scalar_values: list[float] = []
    scalar_index = np.zeros(N**3, dtype=np.int64)
    scalar_weight = np.zeros(N**3, dtype=np.float64)
    vector_rows: list[int] = []
    vector_cols: list[int] = []
    vector_values: list[float] = []
    vector_index = np.zeros((N**3, 3), dtype=np.int64)
    vector_matrix = np.zeros((N**3, 3, 3), dtype=np.float64)
    vector_column = 0

    for scalar_column, orbit in enumerate(orbits):
        scalar_value = 1.0 / math.sqrt(len(orbit))
        for site in orbit:
            row = flat_index(site)
            scalar_rows.append(row)
            scalar_cols.append(scalar_column)
            scalar_values.append(scalar_value)
            scalar_index[row] = scalar_column
            scalar_weight[row] = scalar_value

        if len(orbit) == 1:
            site = orbit[0]
            row = flat_index(site)
            vector_index[row, :] = vector_column
            vector_matrix[row, 2, 0] = 1.0
            vector_rows.append(2 * M**3 + interior_index(site))
            vector_cols.append(vector_column)
            vector_values.append(1.0)
            vector_column += 1
        else:
            ordered = [orbit[0]]
            for _ in range(3):
                ordered.append(rotate_site(ordered[-1]))
            for seed in range(3):
                for turn, site in enumerate(ordered):
                    value = np.linalg.matrix_power(ROTATION, -turn)[:, seed] / 2.0
                    row = flat_index(site)
                    vector_index[row, seed] = vector_column
                    vector_matrix[row, :, seed] = value
                    for component, entry in enumerate(value):
                        if entry != 0.0:
                            vector_rows.append(component * M**3 + interior_index(site))
                            vector_cols.append(vector_column)
                            vector_values.append(float(entry))
                vector_column += 1

    if vector_column != NV:
        raise HessianFailure(f"vector C4 dimension {vector_column} != {NV}")
    scalar_basis = sparse.coo_matrix(
        (scalar_values, (scalar_rows, scalar_cols)), shape=(N**3, NS)
    ).tocsr()
    vector_basis = sparse.coo_matrix(
        (vector_values, (vector_rows, vector_cols)), shape=(3 * M**3, NV)
    ).tocsr()
    scalar_gram_error = sparse_max_abs(scalar_basis.T @ scalar_basis - sparse.eye(NS))
    vector_gram_error = sparse_max_abs(vector_basis.T @ vector_basis - sparse.eye(NV))
    if scalar_gram_error > 1.0e-12 or vector_gram_error > 1.0e-12:
        raise HessianFailure(
            f"nonorthogonal C4 bases: scalar={scalar_gram_error}, vector={vector_gram_error}"
        )
    interior_rows = np.asarray([flat_index(site) for site in sites], dtype=np.int64)
    return BasisData(
        scalar=scalar_basis,
        vector=vector_basis,
        scalar_index=scalar_index,
        scalar_weight=scalar_weight,
        vector_index=vector_index,
        vector_matrix=vector_matrix,
        interior_rows=interior_rows,
        diagnostics={
            "scalar_dimension": NS,
            "vector_dimension": NV,
            "scalar_orthogonality_max": scalar_gram_error,
            "vector_orthogonality_max": vector_gram_error,
            "scalar_nnz": int(scalar_basis.nnz),
            "vector_nnz": int(vector_basis.nnz),
        },
    )


def extension_choices(index: int) -> tuple[tuple[int, float], ...]:
    if index == 2:
        return ((1, 0.25), (2, 1.0))
    if index == N - 3:
        return ((N - 3, 1.0), (N - 2, 0.25))
    return ((index, 1.0),)


def build_alpha_basis(derivatives: tuple[sparse.csr_matrix, ...]) -> tuple[sparse.csr_matrix, dict[str, Any]]:
    central_sites = [
        (i, j, k)
        for i in range(2, N - 2)
        for j in range(2, N - 2)
        for k in range(2, N - 2)
    ]
    orbits = orbit_partition(central_sites)
    if len(orbits) != N_ALPHA:
        raise HessianFailure(f"allowed alpha dimension {len(orbits)} != {N_ALPHA}")
    rows: list[int] = []
    cols: list[int] = []
    values: list[float] = []
    for column, orbit in enumerate(orbits):
        entries: dict[int, float] = {}
        orbit_weight = 1.0 / math.sqrt(len(orbit))
        for site in orbit:
            choices = [extension_choices(index) for index in site]
            for x_choice, y_choice, z_choice in product(*choices):
                target = (x_choice[0], y_choice[0], z_choice[0])
                weight = orbit_weight * x_choice[1] * y_choice[1] * z_choice[1]
                row = flat_index(target)
                entries[row] = entries.get(row, 0.0) + weight
        norm = math.sqrt(sum(value * value for value in entries.values()))
        for row, value in entries.items():
            rows.append(row)
            cols.append(column)
            values.append(value / norm)
    alpha = sparse.coo_matrix((values, (rows, cols)), shape=(N**3, N_ALPHA)).tocsr()
    orthogonality = sparse_max_abs(alpha.T @ alpha - sparse.eye(N_ALPHA))
    shell = shell_mask()
    shell_value = sparse_max_abs(alpha[shell, :])
    shell_derivatives = [sparse_max_abs(operator[ shell, :] @ alpha) for operator in derivatives]
    if orthogonality > 1.0e-12 or shell_value > 1.0e-12 or max(shell_derivatives) > 1.0e-12:
        raise HessianFailure(
            f"allowed alpha basis failed: orth={orthogonality}, shell={shell_value}, "
            f"derivatives={shell_derivatives}"
        )
    return alpha, {
        "central_side": CORE_M,
        "dimension_per_color": N_ALPHA,
        "orthogonality_max": orthogonality,
        "shell_value_max": shell_value,
        "shell_derivative_max_by_axis": shell_derivatives,
        "nnz": int(alpha.nnz),
    }


def weighted_alpha(alpha: sparse.csr_matrix, weights: np.ndarray) -> sparse.csr_matrix:
    result = alpha.multiply(np.asarray(weights, dtype=np.float64).reshape(-1, 1))
    return clean(result, "csr")


def coupled_gauge_matrix(
    fields: dict[str, np.ndarray],
    bases: BasisData,
    alpha: sparse.csr_matrix,
    derivatives: tuple[sparse.csr_matrix, ...],
) -> tuple[sparse.csc_matrix, dict[str, Any]]:
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h = fields["h"]
    a = fields["a"]
    alpha_derivatives = tuple(clean(operator @ alpha, "csr") for operator in derivatives)
    scalar_blocks: list[list[sparse.spmatrix]] = [[] for _ in range(7)]
    vector_blocks: list[list[sparse.spmatrix]] = [[] for _ in range(3)]

    for input_color in range(3):
        transformed_psi = np.einsum("ab,...b->...a", PAULI[input_color], psi)
        delta_psi = 1.0j * transformed_psi
        scalar_weights = [
            delta_psi[..., 0].real,
            delta_psi[..., 1].real,
            delta_psi[..., 0].imag,
            delta_psi[..., 1].imag,
        ]
        delta_h = np.cross(h, np.eye(3, dtype=np.float64)[input_color])
        scalar_weights.extend(delta_h[..., component] for component in range(3))
        for group, weights in enumerate(scalar_weights):
            block = bases.scalar.T @ weighted_alpha(alpha, np.asarray(weights).reshape(-1))
            scalar_blocks[group].append(clean(block, "csr"))

        for output_color in range(3):
            spatial: list[sparse.spmatrix] = []
            for spatial_component in range(3):
                commutator = np.cross(
                    a[..., spatial_component, :], np.eye(3, dtype=np.float64)[input_color]
                )[..., output_color]
                block = weighted_alpha(alpha, commutator.reshape(-1))
                if output_color == input_color:
                    block = block + alpha_derivatives[spatial_component]
                spatial.append(clean(block[bases.interior_rows, :], "csr"))
            stacked = sparse.vstack(spatial, format="csr")
            vector_blocks[output_color].append(clean(bases.vector.T @ stacked, "csr"))

    gauge = sparse.bmat(scalar_blocks + vector_blocks, format="csc")
    gauge.eliminate_zeros()
    expected_shape = (N_NONCARRIER, N_GAUGE)
    if gauge.shape != expected_shape:
        raise HessianFailure(f"coupled gauge shape {gauge.shape} != {expected_shape}")

    sample_parameter = np.zeros(N_GAUGE, dtype=np.float64)
    sample_parameter[0] = 1.0
    sample = np.asarray(gauge @ sample_parameter).reshape(-1)
    return gauge, {
        "noncarrier_shape": list(gauge.shape),
        "embedded_shape": [N_BASE, N_GAUGE],
        "nnz": int(gauge.nnz),
        "sample_generator_norm": float(np.linalg.norm(sample)),
    }


class GaugeProjector:
    def __init__(self, gauge: sparse.csc_matrix) -> None:
        self.gauge = gauge
        gram = clean(gauge.T @ gauge, "csc")
        gram = clean(0.5 * (gram + gram.T), "csc")
        self.gram = gram
        try:
            self.factor = splu(gram, permc_spec="COLAMD")
        except RuntimeError as exc:
            raise HessianFailure(f"sparse gauge Gram factorization failed: {exc}") from exc

        inverse = LinearOperator(
            (N_GAUGE, N_GAUGE),
            matvec=self.factor.solve,
            rmatvec=lambda vector: self.factor.solve(vector, trans="T"),
            dtype=np.float64,
        )
        try:
            smallest = float(
                eigsh(
                    gram,
                    k=1,
                    sigma=0.0,
                    which="LM",
                    OPinv=inverse,
                    tol=1.0e-9,
                    maxiter=2000,
                    return_eigenvectors=False,
                )[0]
            )
            largest = float(
                eigsh(
                    gram,
                    k=1,
                    which="LA",
                    tol=1.0e-9,
                    maxiter=2000,
                    return_eigenvectors=False,
                )[0]
            )
        except ArpackNoConvergence as exc:
            raise HessianFailure("gauge Gram extremal eigenvalue solve did not converge") from exc
        condition = largest / smallest
        if smallest <= 1.0e-8 or condition >= 1.0e8:
            raise HessianFailure(
                f"gauge Gram conditioning failed: lambda_min={smallest}, condition={condition}"
            )

        rng = np.random.default_rng(99017)
        solve_rows: list[dict[str, float]] = []
        projector_rows: list[dict[str, float]] = []
        for index in range(3):
            rhs = rng.normal(size=N_GAUGE)
            solution = self.factor.solve(rhs)
            solve_residual = float(np.linalg.norm(gram @ solution - rhs) / np.linalg.norm(rhs))
            solve_rows.append({"probe": index, "relative_residual": solve_residual})
            if solve_residual > 1.0e-10:
                raise HessianFailure(f"gauge Gram solve residual {solve_residual}")

            vector = rng.normal(size=N_BASE)
            projected = self.project(vector)
            repeated = self.project(projected)
            idempotence = float(
                np.linalg.norm(repeated - projected) / max(np.linalg.norm(projected), 1.0)
            )
            gauge_residual = self.gauge_residual(projected)
            other = rng.normal(size=N_BASE)
            projected_other = self.project(other)
            left = float(other @ projected)
            right = float(vector @ projected_other)
            symmetry = abs(left - right) / max(abs(left), abs(right), 1.0)
            projector_rows.append(
                {
                    "probe": index,
                    "idempotence_relative": idempotence,
                    "gauge_orthogonality_relative": gauge_residual,
                    "symmetry_relative": symmetry,
                }
            )
            if max(idempotence, gauge_residual, symmetry) > 1.0e-10:
                raise HessianFailure(f"orthogonal projector probe failed: {projector_rows[-1]}")

        self.diagnostics = {
            "gram_shape": list(gram.shape),
            "gram_nnz": int(gram.nnz),
            "gram_lambda_min": smallest,
            "gram_lambda_max": largest,
            "gram_condition_estimate": condition,
            "solve_probes": solve_rows,
            "projector_probes": projector_rows,
            "physical_dimension": N_PHYS,
        }

    def gauge_part(self, vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float64)
        coefficients = self.factor.solve(np.asarray(self.gauge.T @ vector[:N_NONCARRIER]).reshape(-1))
        result = np.zeros(N_BASE, dtype=np.float64)
        result[:N_NONCARRIER] = np.asarray(self.gauge @ coefficients).reshape(-1)
        return result

    def project(self, vector: np.ndarray) -> np.ndarray:
        vector = np.asarray(vector, dtype=np.float64)
        return vector - self.gauge_part(vector)

    def gauge_residual(self, vector: np.ndarray) -> float:
        numerator = np.linalg.norm(self.gauge.T @ np.asarray(vector)[:N_NONCARRIER])
        return float(numerator / max(np.linalg.norm(vector), 1.0))

def torch_sparse_matrix(matrix: sparse.spmatrix, device: torch.device) -> torch.Tensor:
    coordinate = matrix.tocoo()
    indices = torch.as_tensor(
        np.vstack((coordinate.row, coordinate.col)), dtype=torch.long, device=device
    )
    values = torch.as_tensor(coordinate.data, dtype=torch.float64, device=device)
    return torch.sparse_coo_tensor(
        indices,
        values,
        size=coordinate.shape,
        dtype=torch.float64,
        device=device,
        check_invariants=True,
    ).coalesce()




class PhysicalSpace:
    def __init__(
        self,
        fields_np: dict[str, np.ndarray],
        bases: BasisData,
        projector: GaugeProjector,
        device: torch.device,
    ) -> None:
        carrier_reduced = np.asarray(bases.scalar.T @ fields_np["c"].reshape(-1)).reshape(-1)
        unit = carrier_reduced / np.linalg.norm(carrier_reduced)
        sign = 1.0 if unit[0] >= 0.0 else -1.0
        householder = unit.copy()
        householder[0] += sign
        householder /= np.linalg.norm(householder)
        tangent_probe = self.apply_householder_np(
            np.concatenate((np.zeros(1, dtype=np.float64), np.ones(NS - 1))), householder
        )
        tangent_residual = abs(float(carrier_reduced @ tangent_probe)) / max(
            np.linalg.norm(carrier_reduced) * np.linalg.norm(tangent_probe), 1.0
        )
        involution = np.linalg.norm(self.apply_householder_np(unit, householder) - sign * -np.eye(1, NS, 0).reshape(-1))
        if tangent_residual > 1.0e-11 or involution > 1.0e-11:
            raise HessianFailure(
                f"carrier Householder failed: tangent={tangent_residual}, map={involution}"
            )

        self.bases = bases
        self.projector = projector
        self.device = device
        self.carrier_reduced = carrier_reduced
        self.householder = householder
        self.householder_t = torch.as_tensor(householder, dtype=torch.float64, device=device)
        self.scalar_basis_t = torch_sparse_matrix(bases.scalar, device)
        self.vector_basis_t = torch_sparse_matrix(bases.vector, device)
        self.background = {
            name: torch.as_tensor(value, dtype=torch.float64, device=device)
            for name, value in fields_np.items()
        }
        self.grid = stationary.make_grid("X2", device, R=R, N=N)
        self.diagnostics = {
            "carrier_reduced_norm": float(np.linalg.norm(carrier_reduced)),
            "householder_tangent_probe_relative": tangent_residual,
            "householder_unit_map_residual": float(involution),
            "base_dimension": N_BASE,
            "physical_dimension": N_PHYS,
        }

    @staticmethod
    def apply_householder_np(vector: np.ndarray, householder: np.ndarray) -> np.ndarray:
        return vector - 2.0 * householder * float(householder @ vector)

    def apply_householder_torch(self, vector: torch.Tensor) -> torch.Tensor:
        return vector - 2.0 * self.householder_t * torch.dot(self.householder_t, vector)

    def scalar_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        values = torch.sparse.mm(self.scalar_basis_t, coefficients[:, None])[:, 0]
        return values.reshape(N, N, N)

    def vector_field(self, coefficients: torch.Tensor) -> torch.Tensor:
        interior = torch.sparse.mm(self.vector_basis_t, coefficients).reshape(3, M, M, M, 3)
        padded = torch.nn.functional.pad(
            interior, (0, 0, 1, 1, 1, 1, 1, 1, 0, 0), mode="constant", value=0.0
        )
        return padded.permute(1, 2, 3, 0, 4)

    def fields_from_base(self, base: torch.Tensor) -> tuple[dict[str, torch.Tensor], torch.Tensor]:
        scalar = base[: 7 * NS].reshape(7, NS)
        delta_scalars = torch.stack(
            [self.scalar_field(scalar[index]) for index in range(7)], dim=-1
        )
        gauge_coefficients = base[7 * NS : N_NONCARRIER].reshape(3, NV).T
        delta_a = self.vector_field(gauge_coefficients)
        tangent_coordinates = base[N_NONCARRIER : N_NONCARRIER + NS - 1]
        embedded = torch.cat((torch.zeros(1, dtype=torch.float64, device=self.device), tangent_coordinates))
        carrier_real_coeff = self.apply_householder_torch(embedded)
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
            * COEFFICIENTS["k_Cx"]
            * sum(
                torch.sum(real_derivative**2 + imag_derivative**2)
                for real_derivative, imag_derivative in zip(derivative_real, derivative_imag)
            )
            * self.grid.dv
        )
        trap = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - aux["rho"])
        carrier_quadratic = torch.sum(trap * carrier_modulus2) * self.grid.dv
        carrier_quartic = (
            0.5 * COEFFICIENTS["u_C"] * torch.sum(carrier_modulus2**2) * self.grid.dv
        )
        physical = noncarrier + carrier_gradient + carrier_quadratic + carrier_quartic
        charge = torch.sum(carrier_modulus2) * self.grid.dv
        return physical - OMEGA_C * charge, physical, charge

    def lagrangian(self, base: np.ndarray) -> float:
        vector = torch.as_tensor(base, dtype=torch.float64, device=self.device)
        value, _, _ = self.lagrangian_from_base(vector)
        return tensor_float(value)

    def raw_gradient(self, base: np.ndarray) -> np.ndarray:
        vector = torch.as_tensor(base, dtype=torch.float64, device=self.device).detach().requires_grad_(True)
        value, _, _ = self.lagrangian_from_base(vector)
        gradient = torch.autograd.grad(value, vector)[0] / self.grid.dv
        return gradient.detach().cpu().numpy()

    def physical_gradient(self, base: np.ndarray) -> np.ndarray:
        return self.projector.project(self.raw_gradient(base))

    def raw_hvp(self, direction: np.ndarray) -> np.ndarray:
        direction_t = torch.as_tensor(direction, dtype=torch.float64, device=self.device)
        base = torch.zeros(N_BASE, dtype=torch.float64, device=self.device, requires_grad=True)
        value, _, _ = self.lagrangian_from_base(base)
        first = torch.autograd.grad(value, base, create_graph=True)[0]
        second = torch.autograd.grad(torch.dot(first, direction_t), base)[0] / self.grid.dv
        return second.detach().cpu().numpy()

    def physical_hvp(self, direction: np.ndarray) -> np.ndarray:
        projected = self.projector.project(direction)
        return self.projector.project(self.raw_hvp(projected))

    def lifted_hvp(self, direction: np.ndarray) -> np.ndarray:
        projected = self.projector.project(direction)
        gauge = np.asarray(direction, dtype=np.float64) - projected
        return self.projector.project(self.raw_hvp(projected)) + GAUGE_LIFT * gauge

    def normalize_physical(self, vector: np.ndarray) -> np.ndarray:
        projected = self.projector.project(vector)
        norm = np.linalg.norm(projected)
        if not math.isfinite(norm) or norm == 0.0:
            raise HessianFailure("cannot normalize physical direction")
        return projected / norm

    def phase_vector(self) -> np.ndarray:
        base = np.zeros(N_BASE, dtype=np.float64)
        base[N_NONCARRIER + NS - 1 :] = self.carrier_reduced / np.linalg.norm(self.carrier_reduced)
        return self.normalize_physical(base)

    def mode_fields(self, base_np: np.ndarray) -> dict[str, np.ndarray]:
        base = torch.as_tensor(base_np, dtype=torch.float64, device=self.device)
        fields, carrier_imag = self.fields_from_base(base)
        return {
            "psi_real": (fields["psi_real"] - self.background["psi_real"]).detach().cpu().numpy(),
            "psi_imag": (fields["psi_imag"] - self.background["psi_imag"]).detach().cpu().numpy(),
            "h": (fields["h"] - self.background["h"]).detach().cpu().numpy(),
            "a": (fields["a"] - self.background["a"]).detach().cpu().numpy(),
            "chi_real": (fields["c"] - self.background["c"]).detach().cpu().numpy(),
            "chi_imag": carrier_imag.detach().cpu().numpy(),
        }


def load_background(device: torch.device) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    if sha256_file(ARTIFACT) != ARTIFACT_SHA256:
        raise HessianFailure("selected localized NPZ hash mismatch")
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
    if np.max(np.abs(arrays["x"] - np.linspace(-R, R, N))) > 1.0e-14:
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

    grid = stationary.make_grid("X2", device, R=R, N=N)
    fields_t = {
        name: torch.as_tensor(value, dtype=torch.float64, device=device)
        for name, value in fields_np.items()
    }
    components, gauge_fixing, _ = stationary.energy_components(fields_t, grid)
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
    carrier_radius = tensor_float(
        torch.sqrt(
            torch.sum((grid.X**2 + grid.Y**2 + grid.Z**2) * fields_t["c"] ** 2)
            * grid.dv
            / charge
        )
    )
    rho = torch.sum(torch.complex(fields_t["psi_real"], fields_t["psi_imag"]).abs() ** 2, dim=-1)
    depletion = torch.clamp(1.0 - rho, min=0.0)
    depletion_weight = tensor_float(torch.sum(depletion) * grid.dv)
    core_length = (
        0.0
        if depletion_weight < 1.0e-12
        else 2.0
        * math.sqrt(
            tensor_float(torch.sum(grid.Z**2 * depletion) * grid.dv) / depletion_weight
        )
    )
    outer_fraction = tensor_float(
        torch.sum(fields_t["c"][grid.shell2] ** 2) / torch.sum(fields_t["c"] ** 2)
    )
    measured = {
        "physical_energy": physical_energy,
        "physical_gradient_rms": physical_gradient,
        "cutoff_virial": cutoff,
        "omega_c": omega,
        "charge": charge,
        "gauge_fixing_energy": tensor_float(gauge_fixing),
        "carrier_radius": carrier_radius,
        "core_length": core_length,
        "max_density_depletion": tensor_float(1.0 - torch.min(rho)),
        "outer_carrier_fraction": outer_fraction,
        "negative_norm_fraction": tensor_float(
            torch.sum(torch.clamp(-fields_t["c"], min=0.0) ** 2) * grid.dv / charge
        ),
    }
    comparisons: dict[str, Any] = {}
    for name, target in FROZEN_BACKGROUND.items():
        value = measured[name]
        error = abs(value - target)
        tolerance = 1.0e-11 + 1.0e-9 * abs(target)
        comparisons[name] = {
            "measured": value,
            "frozen": target,
            "error": error,
            "tolerance": tolerance,
        }
        if error > tolerance:
            raise HessianFailure(f"frozen background scalar mismatch: {name}: {comparisons[name]}")

    source_results = json.loads(SOURCE_RESULTS.read_text(encoding="utf-8"))
    source_verification = json.loads(SOURCE_VERIFICATION.read_text(encoding="utf-8"))
    if source_results.get("coefficient_vector") != COEFFICIENTS:
        raise HessianFailure("source result coefficient vector mismatch")
    if source_results.get("primary_verdict") != SOURCE_VERDICT:
        raise HessianFailure("source result verdict mismatch")
    if not source_verification.get("pass", False):
        raise HessianFailure("source independent verification did not pass")
    return fields_np, {
        "artifact": str(ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": ARTIFACT_SHA256,
        "schema": schema,
        "shell_residuals": shell_residuals,
        "c4_residuals": c4_residuals,
        "scalars": comparisons,
        "source_verdict": SOURCE_VERDICT,
    }


def directional_preflight(space: PhysicalSpace, seed: int) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    zero = np.zeros(N_BASE, dtype=np.float64)
    zero_lagrangian = space.lagrangian(zero)
    rows: list[dict[str, Any]] = []
    for index in range(3):
        direction = space.normalize_physical(rng.normal(size=N_BASE))
        exact = space.physical_hvp(direction)
        exact_curvature = float(direction @ exact)
        step_rows: list[dict[str, float]] = []
        for step in STEPS:
            finite_hvp = (
                space.physical_gradient(step * direction)
                - space.physical_gradient(-step * direction)
            ) / (2.0 * step)
            vector_relative = float(
                np.linalg.norm(finite_hvp - exact) / max(np.linalg.norm(exact), 1.0)
            )
            energy_curvature = (
                space.lagrangian(step * direction)
                - 2.0 * zero_lagrangian
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
        step_agreement = abs(step_rows[-1]["energy_curvature"] - step_rows[-2]["energy_curvature"])
        step_tolerance = 5.0e-5 + 5.0e-4 * abs(exact_curvature)
        passed = (
            step_rows[-1]["vector_relative_error"] <= 5.0e-5
            and step_rows[-1]["curvature_error"] <= step_rows[-1]["curvature_tolerance"]
            and step_agreement <= step_tolerance
        )
        rows.append(
            {
                "direction": index,
                "norm": float(direction @ direction),
                "physicality_relative": float(
                    np.linalg.norm(direction - space.projector.project(direction))
                    / max(np.linalg.norm(direction), 1.0)
                ),
                "exact_curvature": exact_curvature,
                "steps": step_rows,
                "two_smallest_energy_curvature_difference": step_agreement,
                "step_agreement_tolerance": step_tolerance,
                "pass": passed,
            }
        )
    return {"seed": seed, "directions": rows, "pass": all(row["pass"] for row in rows)}


def operator_preflight(space: PhysicalSpace) -> dict[str, Any]:
    zero = np.zeros(N_BASE, dtype=np.float64)
    gradient = space.physical_gradient(zero)
    gradient_rms = float(np.linalg.norm(gradient) / math.sqrt(N_PHYS))
    rng = np.random.default_rng(57721)
    symmetry_rows: list[dict[str, float]] = []
    for index in range(4):
        left = space.normalize_physical(rng.normal(size=N_BASE))
        right = space.normalize_physical(rng.normal(size=N_BASE))
        h_left = space.physical_hvp(left)
        h_right = space.physical_hvp(right)
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
    phase = space.phase_vector()
    phase_hvp = space.physical_hvp(phase)
    phase_rayleigh = float(phase @ phase_hvp)
    passed = (
        gradient_rms <= 5.0e-6
        and max(row["relative_error"] for row in symmetry_rows) <= 1.0e-9
        and abs(phase_rayleigh) <= 1.0e-10
        and space.projector.gauge_residual(phase) <= 1.0e-10
    )
    return {
        "augmented_gradient_rms": gradient_rms,
        "augmented_gradient_limit": 5.0e-6,
        "operator_symmetry": symmetry_rows,
        "operator_symmetry_pass": max(row["relative_error"] for row in symmetry_rows) <= 1.0e-9,
        "phase_rayleigh": phase_rayleigh,
        "phase_hessian_residual": float(np.linalg.norm(phase_hvp)),
        "phase_gauge_orthogonality_relative": space.projector.gauge_residual(phase),
        "phase_rayleigh_limit": 1.0e-10,
        "phase_vector": phase,
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
    derivatives = np.gradient(background, DX, axis=(0, 1, 2), edge_order=2)
    coordinates = np.linspace(-R, R, N)
    x, y, _ = np.meshgrid(coordinates, coordinates, coordinates, indexing="ij")
    axial = -(x[..., None] * derivatives[1] - y[..., None] * derivatives[0])
    a_slice = slice(7, 16)
    axial_a = axial[..., a_slice].reshape(N, N, N, 3, 3)
    generator = np.asarray(((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0)))
    axial_a += np.einsum("ij,...jc->...ic", generator, fields["a"])
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
    projected = space.projector.project(base)
    physicality = float(np.linalg.norm(base - projected) / max(np.linalg.norm(base), 1.0))
    return {
        "participation": participation,
        "high_frequency_fraction": high_fft / total_fft,
        "spatially_resolved": participation >= 16.0 and high_fft / total_fft <= 0.20,
        "component_fractions": {name: value / total_norm for name, value in group_norms.items()},
        "shell_max": boundary_max(stacked),
        "charge_tangent_relative": charge_tangent,
        "gauge_orthogonality_relative": space.projector.gauge_residual(base),
        "physical_projection_relative": physicality,
        "norm": float(base @ base),
        "overlaps": {name: normalized_overlap(stacked, probe) for name, probe in probes.items()},
    }


def run_spectrum(
    space: PhysicalSpace,
    fields_np: dict[str, np.ndarray],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    operator = LinearOperator(
        (N_BASE, N_BASE), matvec=space.lifted_hvp, rmatvec=space.lifted_hvp, dtype=np.float64
    )
    rng = np.random.default_rng(PRIMARY_SETTINGS["seed"])
    initial = space.normalize_physical(rng.normal(size=N_BASE))
    started = time.perf_counter()
    try:
        eigenvalues, eigenvectors = eigsh(
            operator,
            k=PRIMARY_SETTINGS["k"],
            which=PRIMARY_SETTINGS["which"],
            ncv=PRIMARY_SETTINGS["ncv"],
            tol=PRIMARY_SETTINGS["tolerance"],
            maxiter=PRIMARY_SETTINGS["maxiter"],
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
    gram = eigenvectors.T @ eigenvectors
    orthogonality = float(np.max(np.abs(gram - np.eye(PRIMARY_SETTINGS["k"]))))
    if orthogonality > 1.0e-8:
        raise HessianFailure(f"primary orthogonality residual {orthogonality}")

    probes = symmetry_probes(fields_np)
    zero_lagrangian = space.lagrangian(np.zeros(N_BASE, dtype=np.float64))
    modes: list[dict[str, Any]] = []
    mode_arrays: dict[str, list[np.ndarray]] = {
        "psi_real": [],
        "psi_imag": [],
        "h": [],
        "a": [],
        "chi_real": [],
        "chi_imag": [],
    }
    residuals: list[float] = []
    for index in range(PRIMARY_SETTINGS["k"]):
        vector = eigenvectors[:, index]
        lifted = space.lifted_hvp(vector)
        physical = space.physical_hvp(vector)
        residual = lifted - eigenvalues[index] * vector
        residual_absolute = float(np.linalg.norm(residual))
        residual_relative = residual_absolute / max(abs(float(eigenvalues[index])), 1.0)
        if residual_relative > 1.0e-6:
            raise HessianFailure(f"primary eigenpair {index} residual {residual_relative}")
        mode = space.mode_fields(vector)
        for name in mode_arrays:
            mode_arrays[name].append(mode[name])
        diagnostic = mode_diagnostics(space, vector, mode, probes)
        if (
            diagnostic["shell_max"] > 1.0e-12
            or diagnostic["charge_tangent_relative"] > 1.0e-11
            or diagnostic["gauge_orthogonality_relative"] > 1.0e-10
            or diagnostic["physical_projection_relative"] > 1.0e-10
            or abs(diagnostic["norm"] - 1.0) > 1.0e-10
            or eigenvalues[index] >= GAUGE_LIFT / 2.0
        ):
            raise HessianFailure(f"primary mode {index} physicality failure: {diagnostic}")
        directional_curvature: float | None = None
        if index < VERIFIER_SETTINGS["k"]:
            step = STEPS[-1]
            directional_curvature = (
                space.lagrangian(step * vector)
                - 2.0 * zero_lagrangian
                + space.lagrangian(-step * vector)
            ) / (step**2 * DV)
        diagnostic.update(
            {
                "index": index,
                "eigenvalue": float(eigenvalues[index]),
                "residual_absolute": residual_absolute,
                "residual_relative": residual_relative,
                "lifted_directional_curvature": float(vector @ lifted),
                "physical_directional_curvature": float(vector @ physical),
                "smallest_step_directional_curvature": directional_curvature,
            }
        )
        modes.append(diagnostic)
        residuals.append(residual_absolute)

    saved = {
        "eigenvalues": eigenvalues,
        "base_vectors": eigenvectors,
        "global_u1_base_vector": space.phase_vector(),
    }
    saved.update({name: np.stack(values, axis=0) for name, values in mode_arrays.items()})
    return {
        "settings": PRIMARY_SETTINGS,
        "wall_seconds": elapsed,
        "eigenvalues": [float(value) for value in eigenvalues],
        "max_absolute_residual": max(residuals),
        "orthogonality_max": orthogonality,
        "modes": modes,
        "finite": bool(np.all(np.isfinite(eigenvalues)) and np.all(np.isfinite(eigenvectors))),
    }, saved


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
    derivatives = derivative_operators()
    alpha, alpha_diagnostics = build_alpha_basis(derivatives)
    gauge, gauge_diagnostics = coupled_gauge_matrix(fields_np, bases, alpha, derivatives)
    projector = GaugeProjector(gauge)
    space = PhysicalSpace(fields_np, bases, projector, device)
    operator_checks = operator_preflight(space)
    directional = directional_preflight(space, 271828)
    if not operator_checks["pass"] or not directional["pass"]:
        raise HessianFailure(
            f"primary Hessian preflight failed: operator={operator_checks}, directional={directional}"
        )
    phase_vector = operator_checks.pop("phase_vector")
    spectrum, saved = run_spectrum(space, fields_np)
    saved["global_u1_base_vector"] = phase_vector
    np.savez_compressed(MODES_PATH, **saved)
    results = {
        "schema": "cassi.particle-localized-physical-hessian.results.v1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "campaign": "particle_localized_physical_hessian",
        "manifest": manifest,
        "manifest_sha256": manifest_hash,
        "environment": {
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
        "bases": bases.diagnostics,
        "alpha_basis": alpha_diagnostics,
        "coupled_gauge": gauge_diagnostics,
        "projector": projector.diagnostics,
        "charge_tangent": space.diagnostics,
        "operator_preflight": operator_checks,
        "directional_preflight": directional,
        "spectrum": spectrum,
        "primary_status": "PENDING—INDEPENDENT VERIFICATION",
        "hessian_resolution_verdict": "INCONCLUSIVE—NO LOCALIZED HESSIAN RESOLUTION SEQUENCE",
        "wall_seconds": time.perf_counter() - started,
        "artifacts": {
            "eigenmodes": str(MODES_PATH.relative_to(ROOT)).replace("\\", "/"),
            "eigenmodes_sha256": sha256_file(MODES_PATH),
        },
    }
    write_json(RESULTS_PATH, results)
    print(
        json.dumps(
            {
                "primary_status": results["primary_status"],
                "eigenvalues": spectrum["eigenvalues"],
                "max_residual": spectrum["max_absolute_residual"],
                "wall_seconds": results["wall_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except HessianFailure as exc:
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        write_json(
            RESULTS_PATH,
            {
                "schema": "cassi.particle-localized-physical-hessian.results.v1",
                "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "primary_status": "INCONCLUSIVE—IMPLEMENTATION OR HESSIAN PREFLIGHT",
                "error": str(exc),
            },
        )
        print(f"LOCALIZED HESSIAN FAILURE: {exc}", file=sys.stderr)
        raise SystemExit(1)
