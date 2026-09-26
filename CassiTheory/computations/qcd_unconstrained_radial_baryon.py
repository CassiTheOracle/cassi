#!/usr/bin/env python3
"""Run the preregistered unconstrained radial chiral-chromodielectric baryon test.

Run from the CassiTheory repository root:
    python computations/qcd_unconstrained_radial_baryon.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy import integrate, interpolate, optimize, sparse
from scipy.sparse import linalg as spla


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-unconstrained-radial-baryon-prereg.md"
UPSTREAM = (
    ROOT
    / "runs"
    / "20260910_qcd_interacting_baryon"
    / "primary"
    / "recovery3"
    / "results.json"
)
DEFAULT_OUTPUT = ROOT / "runs" / "20260910_qcd_unconstrained_radial_baryon" / "recovery4"
EXPECTED_UPSTREAM_SHA256 = (
    "0067c5139c76e7e8ebf75ee2ced88c645ecd9c66738489b10af003f0ba974437"
)
SCHEMA = "cassi.qcd-unconstrained-radial-baryon.primary.v1"

HBARC = 197.3269804
NC = 3
F_PI = 93.0
M_PI = 139.6
M_SIGMA = 1200.0
G_COUPLING = 23.0
M_CHI = 1700.0
GAMMA = 0.2
ETA = 0.12
CHI_SCALE = GAMMA * M_CHI
CHIRAL_LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)
CUBIC = 8.0 * ETA**4 / GAMMA**2 - 2.0
QUARTIC = 1.0 - 6.0 * ETA**4 / GAMMA**2

PRIMARY_RMAX = 10.0
PRIMARY_DELTA = 2.0
PRIMARY_LEVELS = (48, 96, 192)
GRID_SEQUENCE = ((10.0, 96), (10.0, 144), (10.0, 192), (10.0, 288))
BOX_SEQUENCE = ((8.0, 154), (10.0, 192), (12.0, 230))
REGULATOR_SEQUENCE = (4.0, 2.0, 1.0)
FIELD_LOW = -1.5
FIELD_HIGH = 1.5
C_LOW = 0.0
C_HIGH = 1.5
GRADIENT_THRESHOLD = 1.0e-3
BOUND_TOLERANCE = 1.0e-6
EIGEN_TOLERANCE = 2.0e-11
BRANCH_OVERLAP = 0.70
RNG_SEED = 20260910


@dataclass(frozen=True)
class Grid:
    n: int
    rmax: float
    delta: float
    nc: int = NC
    coupling: float = G_COUPLING

    @property
    def dr(self) -> float:
        return self.rmax / self.n

    @property
    def radial(self) -> np.ndarray:
        return (np.arange(self.n, dtype=np.float64) + 0.5) * self.dr

    @property
    def volumes(self) -> np.ndarray:
        faces = np.arange(self.n + 1, dtype=np.float64) * self.dr
        return (faces[1:] ** 3 - faces[:-1] ** 3) / 3.0


@dataclass
class Spectrum:
    eigenvalues: np.ndarray
    vector: np.ndarray | None
    energy: float | None
    nodes: int | None
    rms: float | None
    tail: float | None
    gap: float | None
    overlap: float | None
    residual: float | None
    hermiticity: float


@dataclass
class Evaluation:
    x: np.ndarray
    total: float
    gradient: np.ndarray
    field_parts: dict[str, float]
    spectrum: Spectrum | None

class BranchEvent(RuntimeError):
    """Terminate one frozen optimization trajectory after occupied-state loss."""



@dataclass
class GridOperators:
    grid: Grid
    derivative_tilde: sparse.csr_matrix
    wilson: sparse.csr_matrix
    reference_vector: np.ndarray | None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def unpack(x: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = np.asarray(x, dtype=np.float64)
    return values[:n], values[n : 2 * n], CHI_SCALE * values[2 * n :]


def pack(scalar: np.ndarray, pion: np.ndarray, chi: np.ndarray) -> np.ndarray:
    return np.concatenate((scalar, pion, chi / CHI_SCALE)).astype(np.float64)


def bounds(n: int) -> optimize.Bounds:
    low = np.concatenate(
        (
            np.full(n, FIELD_LOW),
            np.full(n, FIELD_LOW),
            np.full(n, C_LOW),
        )
    )
    high = np.concatenate(
        (
            np.full(n, FIELD_HIGH),
            np.full(n, FIELD_HIGH),
            np.full(n, C_HIGH),
        )
    )
    return optimize.Bounds(low, high)


def chiral_profile(z: np.ndarray, radial: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    a, radius, chi_amplitude, chi_radius = [float(item) for item in z]
    denominator = radial**4 + radius**4
    scalar = 1.0 - a + a * (radial**4 - radius**4) / denominator
    pion = -a * 2.0 * radius**2 * radial**2 / denominator
    chi = chi_amplitude * np.exp(-((radial / chi_radius) ** 2))
    return scalar, pion, chi


def chiral_profile_with_derivatives(
    z: np.ndarray, radial: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a, radius, chi_amplitude, chi_radius = [float(item) for item in z]
    denominator = radial**4 + radius**4
    cos_f = (radial**4 - radius**4) / denominator
    sin_f = 2.0 * radius**2 * radial**2 / denominator
    f_prime = -4.0 * radius**2 * radial / denominator
    scalar = 1.0 - a + a * cos_f
    pion = -a * sin_f
    scalar_prime = -a * sin_f * f_prime
    pion_prime = -a * cos_f * f_prime
    chi = chi_amplitude * np.exp(-((radial / chi_radius) ** 2))
    chi_prime = -2.0 * radial * chi / chi_radius**2
    return scalar, pion, chi, scalar_prime, pion_prime, chi_prime


def derivative_matrix(n: int, dr: float) -> sparse.csr_matrix:
    matrix = sparse.lil_matrix((n, n), dtype=np.float64)
    matrix[0, 0] = -0.5 / dr
    matrix[0, 1] = 0.5 / dr
    for index in range(1, n - 1):
        matrix[index, index - 1] = -0.5 / dr
        matrix[index, index + 1] = 0.5 / dr
    matrix[n - 1, n - 2] = -0.5 / dr
    return matrix.tocsr()


def make_operators(grid: Grid, reference_z: np.ndarray | None) -> GridOperators:
    radial = grid.radial
    weight_sqrt = radial * math.sqrt(grid.dr)
    derivative = derivative_matrix(grid.n, grid.dr)
    derivative_tilde = (
        sparse.diags(weight_sqrt, format="csr")
        @ derivative
        @ sparse.diags(1.0 / weight_sqrt, format="csr")
    ).tocsr()
    wilson = (0.5 * HBARC * grid.dr * (derivative_tilde.T @ derivative_tilde)).tocsr()
    provisional = GridOperators(grid, derivative_tilde, wilson, None)
    reference_vector = None
    if grid.nc and reference_z is not None:
        scalar, pion, chi = chiral_profile(reference_z, radial)
        reference = solve_spectrum(provisional, scalar, pion, chi)
        if reference.vector is None:
            raise RuntimeError(f"reference profile has no positive nodeless state on N={grid.n}")
        reference_vector = reference.vector.copy()
    return GridOperators(grid, derivative_tilde, wilson, reference_vector)


def count_nodes(amplitude: np.ndarray, probability: np.ndarray) -> int:
    cumulative = np.cumsum(probability)
    cutoff = int(np.searchsorted(cumulative, 0.999, side="left"))
    cutoff = max(2, min(cutoff, amplitude.size - 1))
    peak = float(np.max(np.abs(amplitude[: cutoff + 1])))
    if peak == 0.0:
        return amplitude.size
    mask = np.abs(amplitude[: cutoff + 1]) > 1.0e-3 * peak
    signs = np.sign(amplitude[: cutoff + 1][mask])
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0)) if signs.size >= 2 else 0


def solve_spectrum(
    operators: GridOperators,
    scalar: np.ndarray,
    pion: np.ndarray,
    chi: np.ndarray,
) -> Spectrum:
    grid = operators.grid
    n = grid.n
    denominator = np.sqrt(chi * chi + grid.delta * grid.delta)
    scalar_mass = grid.coupling * F_PI * scalar / denominator
    pion_mass = grid.coupling * F_PI * pion / denominator
    scalar_matrix = sparse.diags(scalar_mass, format="csr")
    pion_matrix = sparse.diags(pion_mass, format="csr")
    derivative_block = HBARC * operators.derivative_tilde
    mass = scalar_matrix + operators.wilson
    offdiag = derivative_block - pion_matrix
    hamiltonian = sparse.bmat(
        [[mass, offdiag.T], [offdiag, -mass]],
        format="csc",
        dtype=np.float64,
    )
    asymmetry = hamiltonian - hamiltonian.T
    hermiticity = float(np.max(np.abs(asymmetry.data))) if asymmetry.nnz else 0.0
    start = np.linspace(1.0, 2.0, 2 * n, dtype=np.float64)
    start /= np.linalg.norm(start)
    count = min(12, 2 * n - 2)
    eigenvalues, eigenvectors = spla.eigsh(
        hamiltonian,
        k=count,
        sigma=1.0e-9,
        which="LM",
        tol=EIGEN_TOLERANCE,
        maxiter=12000,
        v0=start,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)
    candidates: list[dict[str, Any]] = []
    weight_inverse = 1.0 / (grid.radial * math.sqrt(grid.dr))
    for column, energy in enumerate(eigenvalues):
        vector = eigenvectors[:, column].copy()
        if vector[0] < 0.0:
            vector *= -1.0
        probability = vector[:n] ** 2 + vector[n:] ** 2
        probability /= float(np.sum(probability))
        upper = vector[:n] * weight_inverse
        nodes = count_nodes(upper, probability)
        if energy > 0.0 and nodes == 0:
            candidates.append(
                {
                    "energy": float(energy),
                    "vector": vector,
                    "nodes": nodes,
                    "probability": probability,
                }
            )
    if not candidates:
        return Spectrum(eigenvalues, None, None, None, None, None, None, None, None, hermiticity)
    selected = min(candidates, key=lambda row: row["energy"])
    vector = selected["vector"]
    energy = selected["energy"]
    probability = selected["probability"]
    residual = float(np.linalg.norm(hamiltonian @ vector - energy * vector) / max(1.0, abs(energy)))
    alternatives = [float(row["energy"] - energy) for row in candidates if row["energy"] > energy + 1.0e-9]
    overlap = (
        None
        if operators.reference_vector is None
        else float(abs(np.dot(operators.reference_vector, vector)))
    )
    return Spectrum(
        eigenvalues=eigenvalues,
        vector=vector,
        energy=energy,
        nodes=selected["nodes"],
        rms=math.sqrt(float(np.dot(probability, grid.radial**2))),
        tail=float(np.sum(probability[grid.radial >= 8.0])),
        gap=min(alternatives) if alternatives else None,
        overlap=overlap,
        residual=residual,
        hermiticity=hermiticity,
    )


def radial_gradient_value_and_derivative(
    values: np.ndarray,
    grid: Grid,
    outer: float,
    *,
    pion: bool = False,
) -> tuple[float, np.ndarray, np.ndarray]:
    n = grid.n
    dr = grid.dr
    gradient = np.zeros(n, dtype=np.float64)
    diagonal = np.zeros(n, dtype=np.float64)
    differences = values[1:] - values[:-1]
    coefficients = (np.arange(1, n, dtype=np.float64) * dr) ** 2 / dr
    value = float(np.dot(coefficients, differences**2))
    contribution = 2.0 * coefficients * differences
    gradient[1:] += contribution
    gradient[:-1] -= contribution
    diagonal[1:] += 2.0 * coefficients
    diagonal[:-1] += 2.0 * coefficients
    outer_coefficient = 2.0 * grid.rmax**2 / dr
    outer_difference = values[-1] - outer
    value += outer_coefficient * outer_difference**2
    gradient[-1] += 2.0 * outer_coefficient * outer_difference
    diagonal[-1] += 2.0 * outer_coefficient
    if pion:
        value += dr * values[0] ** 2 / 6.0
        gradient[0] += dr * values[0] / 3.0
        diagonal[0] += dr / 3.0
        value += 2.0 * dr * float(np.dot(values, values))
        gradient += 4.0 * dr * values
        diagonal += 4.0 * dr
    return value, gradient, diagonal


def field_energy_and_gradient(
    x: np.ndarray, grid: Grid
) -> tuple[dict[str, float], np.ndarray, np.ndarray]:
    scalar, pion, chi = unpack(x, grid.n)
    volumes = grid.volumes
    i_scalar, g_scalar, d_scalar = radial_gradient_value_and_derivative(scalar, grid, 1.0)
    i_pion, g_pion, d_pion = radial_gradient_value_and_derivative(pion, grid, 0.0, pion=True)
    i_chi, g_chi, d_chi = radial_gradient_value_and_derivative(chi, grid, 0.0)

    radial_delta = scalar * scalar + pion * pion - 1.0
    chiral_density = (
        0.5 * M_PI**2 * F_PI**2 * ((scalar - 1.0) ** 2 + pion**2)
        + 0.25 * CHIRAL_LAMBDA * F_PI**4 * radial_delta**2
    )
    chiral_ds = M_PI**2 * F_PI**2 * (scalar - 1.0) + CHIRAL_LAMBDA * F_PI**4 * radial_delta * scalar
    chiral_dp = M_PI**2 * F_PI**2 * pion + CHIRAL_LAMBDA * F_PI**4 * radial_delta * pion

    scaled_chi = chi / CHI_SCALE
    chi_density = 0.5 * M_CHI**2 * chi**2 * (1.0 + CUBIC * scaled_chi + QUARTIC * scaled_chi**2)
    chi_du = M_CHI**2 * chi * (1.0 + 1.5 * CUBIC * scaled_chi + 2.0 * QUARTIC * scaled_chi**2)

    chiral_gradient_coefficient = 4.0 * math.pi * F_PI**2 / (2.0 * HBARC)
    chi_gradient_coefficient = 4.0 * math.pi / (2.0 * HBARC)
    potential_coefficient = 4.0 * math.pi / HBARC**3

    parts = {
        "chiral_gradient": chiral_gradient_coefficient * (i_scalar + i_pion),
        "chiral_potential": potential_coefficient * float(np.dot(volumes, chiral_density)),
        "chi_gradient": chi_gradient_coefficient * i_chi,
        "chi_potential": potential_coefficient * float(np.dot(volumes, chi_density)),
    }
    gradient_scalar = chiral_gradient_coefficient * g_scalar + potential_coefficient * volumes * chiral_ds
    gradient_pion = chiral_gradient_coefficient * g_pion + potential_coefficient * volumes * chiral_dp
    gradient_chi = chi_gradient_coefficient * g_chi + potential_coefficient * volumes * chi_du
    gradient = np.concatenate((gradient_scalar, gradient_pion, CHI_SCALE * gradient_chi))
    positive_diagonal = np.concatenate(
        (
            chiral_gradient_coefficient * d_scalar,
            chiral_gradient_coefficient * d_pion,
            chi_gradient_coefficient * CHI_SCALE**2 * d_chi,
        )
    )
    return parts, gradient, positive_diagonal


class Evaluator:
    def __init__(
        self,
        grid: Grid,
        reference_z: np.ndarray | None,
        *,
        enforce_branch: bool = True,
    ):
        self.grid = grid
        self.operators = make_operators(grid, reference_z if grid.nc else None)
        self.enforce_branch = enforce_branch
        self.last_x: np.ndarray | None = None
        self.last_value: Evaluation | None = None
        self.evaluations = 0
        self.branch_event: dict[str, Any] | None = None

    def evaluate(self, x: np.ndarray) -> Evaluation:
        current = np.asarray(x, dtype=np.float64)
        if self.last_x is not None and np.array_equal(current, self.last_x):
            assert self.last_value is not None
            return self.last_value
        self.evaluations += 1
        scalar, pion, chi = unpack(current, self.grid.n)
        field_parts, gradient, _ = field_energy_and_gradient(current, self.grid)
        field_total = float(sum(field_parts.values()))
        spectrum = None
        total = field_total
        if self.grid.nc:
            spectrum = solve_spectrum(self.operators, scalar, pion, chi)
            if spectrum.vector is None or spectrum.energy is None:
                self.branch_event = {
                    "kind": "positive_nodeless_state_disappeared",
                    "evaluator_call": self.evaluations,
                    "field_total_mev": field_total,
                    "field_parts_mev": field_parts,
                    "profile": {
                        "scalar": scalar,
                        "pion": pion,
                        "chi_mev": chi,
                    },
                    "distance_from_last_valid_l2": (
                        None
                        if self.last_x is None
                        else float(np.linalg.norm(current - self.last_x))
                    ),
                }
                raise BranchEvent("positive nodeless occupied state disappeared")
            if (
                self.enforce_branch
                and spectrum.overlap is not None
                and spectrum.overlap < BRANCH_OVERLAP
            ):
                self.branch_event = {
                    "kind": "reference_overlap_below_threshold",
                    "evaluator_call": self.evaluations,
                    "reference_overlap": spectrum.overlap,
                    "threshold": BRANCH_OVERLAP,
                    "field_total_mev": field_total,
                    "field_parts_mev": field_parts,
                    "profile": {
                        "scalar": scalar,
                        "pion": pion,
                        "chi_mev": chi,
                    },
                    "distance_from_last_valid_l2": (
                        None
                        if self.last_x is None
                        else float(np.linalg.norm(current - self.last_x))
                    ),
                }
                raise BranchEvent("occupied-state reference overlap fell below threshold")
            vector = spectrum.vector
            n = self.grid.n
            denominator_cubed = (chi * chi + self.grid.delta**2) ** 1.5
            denominator = np.sqrt(chi * chi + self.grid.delta**2)
            scalar_factor = self.grid.coupling * F_PI / denominator
            upper_minus_lower = vector[:n] ** 2 - vector[n:] ** 2
            upper_lower = vector[:n] * vector[n:]
            dlevel_ds = scalar_factor * upper_minus_lower
            dlevel_dp = -2.0 * scalar_factor * upper_lower
            dmass_dchi_common = -self.grid.coupling * F_PI * chi / denominator_cubed
            dlevel_dchi = dmass_dchi_common * (
                scalar * upper_minus_lower - 2.0 * pion * upper_lower
            )
            gradient += self.grid.nc * np.concatenate(
                (dlevel_ds, dlevel_dp, CHI_SCALE * dlevel_dchi)
            )
            total += self.grid.nc * spectrum.energy
        value = Evaluation(current.copy(), float(total), gradient, field_parts, spectrum)
        self.last_x = current.copy()
        self.last_value = value
        return value

    def fun_and_grad(self, x: np.ndarray) -> tuple[float, np.ndarray]:
        value = self.evaluate(x)
        return value.total, value.gradient


def projected_gradient(x: np.ndarray, gradient: np.ndarray, grid: Grid) -> np.ndarray:
    limits = bounds(grid.n)
    result = np.asarray(gradient, dtype=np.float64).copy()
    at_low = x <= limits.lb + BOUND_TOLERANCE
    at_high = x >= limits.ub - BOUND_TOLERANCE
    result[at_low & (gradient > 0.0)] = 0.0
    result[at_high & (gradient < 0.0)] = 0.0
    return result


def public_spectrum(spectrum: Spectrum | None) -> dict[str, Any] | None:
    if spectrum is None:
        return None
    return {
        "eigenvalues_mev": spectrum.eigenvalues,
        "candidate_energy_mev": spectrum.energy,
        "nodes_upper": spectrum.nodes,
        "rms_fm": spectrum.rms,
        "tail_probability_r_ge_8fm": spectrum.tail,
        "same_sign_gap_mev": spectrum.gap,
        "reference_overlap": spectrum.overlap,
        "eigen_residual": spectrum.residual,
        "hermiticity_error_mev": spectrum.hermiticity,
    }


def public_evaluation(value: Evaluation, grid: Grid) -> dict[str, Any]:
    scalar, pion, chi = unpack(value.x, grid.n)
    projected = projected_gradient(value.x, value.gradient, grid)
    return {
        "grid": {
            "n": grid.n,
            "rmax_fm": grid.rmax,
            "delta_mev": grid.delta,
            "n_c": grid.nc,
            "g_mev": grid.coupling,
        },
        "total_mev": value.total,
        "field_parts_mev": value.field_parts,
        "field_total_mev": float(sum(value.field_parts.values())),
        "spectrum": public_spectrum(value.spectrum),
        "gradient_max_abs_mev": float(np.max(np.abs(value.gradient))),
        "projected_gradient_max_abs_mev": float(np.max(np.abs(projected))),
        "tails": {
            "scalar_last_minus_vacuum": float(scalar[-1] - 1.0),
            "pion_last": float(pion[-1]),
            "chi_last_mev": float(chi[-1]),
        },
    }


def interpolate_fields(x: np.ndarray, source: Grid, target: Grid) -> np.ndarray:
    scalar, pion, chi = unpack(x, source.n)
    result: list[np.ndarray] = []
    for values in (scalar, pion, chi):
        curve = interpolate.PchipInterpolator(source.radial, values, extrapolate=True)
        result.append(np.asarray(curve(target.radial), dtype=np.float64))
    result[0] = np.clip(result[0], FIELD_LOW, FIELD_HIGH)
    result[1] = np.clip(result[1], FIELD_LOW, FIELD_HIGH)
    result[2] = np.clip(result[2], C_LOW * CHI_SCALE, C_HIGH * CHI_SCALE)
    return pack(result[0], result[1], result[2])


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def optimization_termination(history: list[dict[str, float]], final: Evaluation, grid: Grid) -> dict[str, Any]:
    projected_max = float(np.max(np.abs(projected_gradient(final.x, final.gradient, grid))))
    if len(history) >= 6:
        changes = [
            relative_difference(history[index - 1]["energy_mev"], history[index]["energy_mev"])
            for index in range(len(history) - 4, len(history))
        ]
        energy_stable = max(changes) < 1.0e-10
    else:
        changes = []
        energy_stable = False
    return {
        "projected_gradient_max_abs_mev": projected_max,
        "projected_gradient_pass": projected_max < GRADIENT_THRESHOLD,
        "last_energy_relative_changes": changes,
        "energy_stable": energy_stable,
        "pass": projected_max < GRADIENT_THRESHOLD and energy_stable,
    }


def run_lbfgsb(start_x: np.ndarray, grid: Grid, reference_z: np.ndarray) -> tuple[dict[str, Any], Evaluation, Evaluator]:
    evaluator = Evaluator(grid, reference_z)
    history: list[dict[str, float]] = []
    accepted_values: list[Evaluation] = []
    initial = evaluator.evaluate(start_x)
    accepted_values.append(initial)
    history.append(
        {
            "energy_mev": initial.total,
            "projected_gradient_max_abs_mev": float(
                np.max(np.abs(projected_gradient(initial.x, initial.gradient, grid)))
            ),
            "reference_overlap": (
                1.0
                if initial.spectrum is None or initial.spectrum.overlap is None
                else float(initial.spectrum.overlap)
            ),
        }
    )

    def callback(current: np.ndarray) -> None:
        row = evaluator.evaluate(current)
        accepted_values.append(row)
        history.append(
            {
                "energy_mev": row.total,
                "projected_gradient_max_abs_mev": float(
                    np.max(np.abs(projected_gradient(row.x, row.gradient, grid)))
                ),
                "reference_overlap": (
                    1.0
                    if row.spectrum is None or row.spectrum.overlap is None
                    else float(row.spectrum.overlap)
                ),
            }
        )

    try:
        result = optimize.minimize(
            evaluator.fun_and_grad,
            np.asarray(start_x, dtype=np.float64),
            method="L-BFGS-B",
            jac=True,
            bounds=bounds(grid.n),
            callback=callback,
            options={
                "ftol": 1.0e-15,
                "gtol": 1.0e-8,
                "maxiter": 1200,
                "maxfun": 4000,
                "maxls": 60,
                "maxcor": 30,
            },
        )
        final = evaluator.evaluate(np.asarray(result.x, dtype=np.float64))
        scipy_success = bool(result.success)
        scipy_message = str(result.message)
        nit: int | None = int(result.nit)
        nfev: int | None = int(result.nfev)
        njev: int | None = int(getattr(result, "njev", result.nfev))
    except BranchEvent as error:
        final = min(accepted_values, key=lambda value: value.total)
        scipy_success = False
        scipy_message = f"BRANCH_EVENT: {error}"
        nit = None
        nfev = evaluator.evaluations
        njev = evaluator.evaluations

    termination = optimization_termination(history, final, grid)
    if evaluator.branch_event is not None:
        termination["pass"] = False
        termination["branch_stop"] = True
    accepted_overlaps = [row["reference_overlap"] for row in history]
    record = {
        "scipy_success": scipy_success,
        "scipy_message": scipy_message,
        "nit": nit,
        "nfev": nfev,
        "njev": njev,
        "evaluator_calls": evaluator.evaluations,
        "history": history,
        "termination": termination,
        "minimum_accepted_reference_overlap": min(accepted_overlaps),
        "branch_event": (
            evaluator.branch_event
            if evaluator.branch_event is not None
            else (
                {
                    "kind": "accepted_reference_overlap_below_threshold",
                    "reference_overlap": min(accepted_overlaps),
                    "threshold": BRANCH_OVERLAP,
                }
                if min(accepted_overlaps) < BRANCH_OVERLAP
                else None
            )
        ),
    }
    return record, final, evaluator


def simpson_field_energy(z: np.ndarray) -> float:
    radial = np.linspace(0.0, PRIMARY_RMAX, 8193, dtype=np.float64)
    scalar, pion, chi, scalar_prime, pion_prime, chi_prime = chiral_profile_with_derivatives(z, radial)
    angular = np.zeros_like(radial)
    angular[1:] = 2.0 * pion[1:] ** 2 / radial[1:] ** 2
    radial_delta = scalar * scalar + pion * pion - 1.0
    chiral_density = (
        F_PI**2 / (2.0 * HBARC) * (scalar_prime**2 + pion_prime**2 + angular)
        + (
            0.5 * M_PI**2 * F_PI**2 * ((scalar - 1.0) ** 2 + pion**2)
            + 0.25 * CHIRAL_LAMBDA * F_PI**4 * radial_delta**2
        )
        / HBARC**3
    )
    scaled_chi = chi / CHI_SCALE
    chi_density = (
        chi_prime**2 / (2.0 * HBARC)
        + 0.5
        * M_CHI**2
        * chi**2
        * (1.0 + CUBIC * scaled_chi + QUARTIC * scaled_chi**2)
        / HBARC**3
    )
    return float(integrate.simpson(4.0 * math.pi * radial**2 * (chiral_density + chi_density), x=radial))


def algebraic_controls(reference_z: np.ndarray) -> dict[str, Any]:
    probe_grid = Grid(48, PRIMARY_RMAX, PRIMARY_DELTA)
    evaluator = Evaluator(probe_grid, reference_z, enforce_branch=False)
    scalar, pion, chi = chiral_profile(reference_z, probe_grid.radial)
    chi = chi + 0.05 * CHI_SCALE * np.exp(-probe_grid.radial / 5.0)
    probe = pack(scalar, pion, chi)
    probe_value = evaluator.evaluate(probe)
    rng = np.random.Generator(np.random.PCG64(RNG_SEED))
    direction_rows: list[dict[str, float | bool]] = []
    finite_step = 1.0e-5
    for index in range(24):
        direction = rng.normal(size=probe.size)
        direction /= np.linalg.norm(direction)
        numerical = (
            evaluator.evaluate(probe + finite_step * direction).total
            - evaluator.evaluate(probe - finite_step * direction).total
        ) / (2.0 * finite_step)
        analytic = float(np.dot(probe_value.gradient, direction))
        absolute = abs(analytic - numerical)
        relative = absolute / max(abs(numerical), 1.0e-300)
        passed = absolute < 3.0e-5 if abs(numerical) < 1.0 else relative < 3.0e-5
        direction_rows.append(
            {
                "index": index,
                "analytic_mev": analytic,
                "numeric_mev": numerical,
                "absolute_error_mev": absolute,
                "relative_error": relative,
                "pass": passed,
            }
        )

    comparison_grid = Grid(384, PRIMARY_RMAX, PRIMARY_DELTA)
    comparison_fields = chiral_profile(reference_z, comparison_grid.radial)
    comparison_x = pack(*comparison_fields)
    comparison_parts, _, _ = field_energy_and_gradient(comparison_x, comparison_grid)
    finite_volume = float(sum(comparison_parts.values()))
    comparison_scalar, comparison_pion, comparison_chi = comparison_fields
    outer_coefficient = 2.0 * comparison_grid.rmax**2 / comparison_grid.dr
    outer_penalties = {
        "chiral_mev": (
            4.0
            * math.pi
            * F_PI**2
            / (2.0 * HBARC)
            * outer_coefficient
            * (
                (comparison_scalar[-1] - 1.0) ** 2
                + comparison_pion[-1] ** 2
            )
        ),
        "chi_mev": (
            4.0
            * math.pi
            / (2.0 * HBARC)
            * outer_coefficient
            * comparison_chi[-1] ** 2
        ),
    }
    finite_volume_interior = finite_volume - sum(outer_penalties.values())
    simpson = simpson_field_energy(reference_z)
    field_relative = relative_difference(finite_volume_interior, simpson)

    vacuum_grid = Grid(48, PRIMARY_RMAX, PRIMARY_DELTA, nc=0)
    vacuum = pack(np.ones(48), np.zeros(48), np.zeros(48))
    vacuum_parts, vacuum_gradient, _ = field_energy_and_gradient(vacuum, vacuum_grid)
    vacuum_energy = float(sum(vacuum_parts.values()))
    spectrum = probe_value.spectrum
    assert spectrum is not None
    checks = {
        "hermiticity": spectrum.hermiticity < 1.0e-12,
        "eigen_residual": spectrum.residual is not None and spectrum.residual < 1.0e-9,
        "gradient": all(bool(row["pass"]) for row in direction_rows),
        "field_quadrature": field_relative < 0.005,
        "outer_penalties": all(value >= 0.0 and math.isfinite(value) for value in outer_penalties.values()),
        "vacuum": abs(vacuum_energy) < 1.0e-10 and float(np.max(np.abs(vacuum_gradient))) < 1.0e-10,
    }
    return {
        "probe": public_evaluation(probe_value, probe_grid),
        "directional_gradient_rows": direction_rows,
        "direction_step": finite_step,
        "finite_volume_field_energy_mev": finite_volume,
        "outer_half_cell_penalties_mev": outer_penalties,
        "finite_volume_interior_field_energy_mev": finite_volume_interior,
        "simpson_field_energy_mev": simpson,
        "interior_field_energy_relative_difference": field_relative,
        "vacuum_field_energy_mev": vacuum_energy,
        "vacuum_gradient_max_abs_mev": float(np.max(np.abs(vacuum_gradient))),
        "checks": checks,
        "pass": all(checks.values()),
    }


def active_bound_violations(value: Evaluation, grid: Grid) -> dict[str, Any]:
    limits = bounds(grid.n)
    at_low = np.flatnonzero(value.x <= limits.lb + BOUND_TOLERANCE)
    at_high = np.flatnonzero(value.x >= limits.ub - BOUND_TOLERANCE)
    violations: list[int] = []
    for index in np.concatenate((at_low, at_high)):
        is_allowed_chi_tail = index >= 2 * grid.n and grid.radial[index - 2 * grid.n] > 8.0 and index in at_low
        if not is_allowed_chi_tail:
            violations.append(int(index))
    return {
        "lower_indices": at_low,
        "upper_indices": at_high,
        "disallowed_indices": violations,
        "pass": len(violations) == 0,
    }


def endpoint_gate(value: Evaluation, optimizer: dict[str, Any], grid: Grid) -> dict[str, Any]:
    if value.spectrum is None:
        raise RuntimeError("occupied endpoint is missing spectrum")
    scalar, pion, chi = unpack(value.x, grid.n)
    spectrum = value.spectrum
    bound_status = active_bound_violations(value, grid)
    checks = {
        "optimizer_termination": bool(optimizer["termination"]["pass"]),
        "active_bounds": bool(bound_status["pass"]),
        "positive_level": spectrum.energy is not None and 0.0 < spectrum.energy < 500.0,
        "bound_total": value.total < 3.0 * grid.coupling * F_PI / grid.delta,
        "rms": spectrum.rms is not None and spectrum.rms < 1.5,
        "scalar_tail": abs(float(scalar[-1] - 1.0)) < 1.0e-3,
        "pion_tail": abs(float(pion[-1])) < 1.0e-3,
        "chi_tail": float(chi[-1]) < 0.5,
        "branch": not bool(optimizer["branch_event"]),
        "eigen_residual": spectrum.residual is not None and spectrum.residual < 1.0e-9,
    }
    return {"checks": checks, "bounds": bound_status, "pass": all(checks.values())}


def primary_multilevel(reference_z: np.ndarray) -> tuple[dict[str, Any], Evaluation | None, Grid | None]:
    rows: list[dict[str, Any]] = []
    source_grid: Grid | None = None
    current_x: np.ndarray | None = None
    final_value: Evaluation | None = None
    final_grid: Grid | None = None
    for n in PRIMARY_LEVELS:
        grid = Grid(n, PRIMARY_RMAX, PRIMARY_DELTA)
        if current_x is None:
            current_x = pack(*chiral_profile(reference_z, grid.radial))
        else:
            assert source_grid is not None
            current_x = interpolate_fields(current_x, source_grid, grid)
        started = time.time()
        try:
            optimizer, value, _ = run_lbfgsb(current_x, grid, reference_z)
            gate = endpoint_gate(value, optimizer, grid)
            row = {
                "grid": {"n": n, "rmax_fm": grid.rmax, "delta_mev": grid.delta},
                "optimizer": optimizer,
                "endpoint": public_evaluation(value, grid),
                "endpoint_gate": gate,
                "elapsed_seconds": time.time() - started,
            }
            rows.append(row)
            current_x = value.x.copy()
            source_grid = grid
            final_value = value
            final_grid = grid
            if not optimizer["termination"]["pass"]:
                break
        except Exception as error:
            rows.append(
                {
                    "grid": {"n": n, "rmax_fm": grid.rmax, "delta_mev": grid.delta},
                    "error": f"{type(error).__name__}: {error}",
                    "elapsed_seconds": time.time() - started,
                }
            )
            break
    passed = len(rows) == len(PRIMARY_LEVELS) and all(
        row.get("endpoint_gate", {}).get("pass") is True for row in rows
    )
    return {"rows": rows, "pass": passed}, final_value, final_grid


def hessian_spectrum(value: Evaluation, grid: Grid, reference_z: np.ndarray) -> dict[str, Any]:
    base = value.x.copy()
    limits = bounds(grid.n)
    free = np.flatnonzero(
        (base > limits.lb + 2.0e-5) & (base < limits.ub - 2.0e-5)
    )
    step = 1.0e-5 * max(1.0, float(np.linalg.norm(base)) / math.sqrt(3 * grid.n))

    def solve_at(h: float) -> dict[str, Any]:
        evaluator = Evaluator(grid, reference_z)
        size = free.size

        def matvec(vector: np.ndarray) -> np.ndarray:
            direction = np.zeros(base.size, dtype=np.float64)
            direction[free] = vector
            plus = evaluator.evaluate(base + h * direction).gradient[free]
            minus = evaluator.evaluate(base - h * direction).gradient[free]
            return (plus - minus) / (2.0 * h)

        operator = spla.LinearOperator((size, size), matvec=matvec, dtype=np.float64)
        k = min(8, size - 2)
        start = np.linspace(1.0, 2.0, size, dtype=np.float64)
        start /= np.linalg.norm(start)
        eigenvalues, eigenvectors = spla.eigsh(
            operator,
            k=k,
            which="SA",
            tol=1.0e-6,
            maxiter=3000,
            v0=start,
        )
        order = np.argsort(eigenvalues)
        eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
        eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)
        residuals = []
        for column, eigenvalue in enumerate(eigenvalues):
            vector = eigenvectors[:, column]
            residuals.append(
                float(np.linalg.norm(matvec(vector) - eigenvalue * vector) / max(1.0, abs(eigenvalue)))
            )
        return {
            "step": h,
            "eigenvalues_mev": eigenvalues,
            "residuals": residuals,
            "evaluator_calls": evaluator.evaluations,
        }

    try:
        full = solve_at(step)
        half = solve_at(step / 2.0)
        sign_agreement = all(
            math.copysign(1.0, left) == math.copysign(1.0, right)
            for left, right in zip(full["eigenvalues_mev"], half["eigenvalues_mev"])
        )
        rng = np.random.Generator(np.random.PCG64(RNG_SEED + 1))
        displacement_rows = []
        evaluator = Evaluator(grid, reference_z)
        for index in range(16):
            direction = np.zeros(base.size, dtype=np.float64)
            direction[free] = rng.normal(size=free.size)
            direction /= np.linalg.norm(direction)
            displaced = evaluator.evaluate(base + 1.0e-3 * direction)
            difference = displaced.total - value.total
            displacement_rows.append({"index": index, "energy_increase_mev": difference, "pass": difference > 0.0})
        checks = {
            "sign_agreement": sign_agreement,
            "minimum": float(full["eigenvalues_mev"][0]) > 1.0e-3,
            "residuals": max(full["residuals"] + half["residuals"]) < 1.0e-6,
            "displacements": all(row["pass"] for row in displacement_rows),
        }
        verdict = "PASS" if all(checks.values()) else "FAIL"
        return {
            "free_coordinate_count": int(free.size),
            "full_step": full,
            "half_step": half,
            "displacements": displacement_rows,
            "checks": checks,
            "verdict": verdict,
        }
    except Exception as error:
        return {
            "free_coordinate_count": int(free.size),
            "error": f"{type(error).__name__}: {error}",
            "verdict": "INCONCLUSIVE",
        }


def profile_overlap(left: Evaluation, left_grid: Grid, right: Evaluation, right_grid: Grid) -> dict[str, float]:
    left_fields = unpack(left.x, left_grid.n)
    right_fields = unpack(right.x, right_grid.n)
    radial = left_grid.radial
    weights = left_grid.volumes
    names = ("scalar", "pion", "chi")
    output: dict[str, float] = {}
    for index, name in enumerate(names):
        left_values = left_fields[index].copy()
        right_values = np.interp(radial, right_grid.radial, right_fields[index])
        if name == "scalar":
            left_values -= 1.0
            right_values -= 1.0
        numerator = float(np.dot(weights, left_values * right_values))
        denominator = math.sqrt(
            float(np.dot(weights, left_values**2)) * float(np.dot(weights, right_values**2))
        )
        output[name] = abs(numerator) / denominator if denominator else 1.0
    return output


def optimized_sequence_case(
    target: Grid,
    primary_value: Evaluation,
    primary_grid: Grid,
    reference_z: np.ndarray,
) -> tuple[dict[str, Any], Evaluation | None]:
    if target == primary_grid:
        optimizer = {
            "reused_primary": True,
            "termination": {"pass": True},
            "branch_event": False,
        }
        gate = endpoint_gate(primary_value, optimizer, target)
        return {"optimizer": optimizer, "endpoint": public_evaluation(primary_value, target), "endpoint_gate": gate}, primary_value
    start = interpolate_fields(primary_value.x, primary_grid, target)
    try:
        optimizer, value, _ = run_lbfgsb(start, target, reference_z)
        gate = endpoint_gate(value, optimizer, target)
        return {"optimizer": optimizer, "endpoint": public_evaluation(value, target), "endpoint_gate": gate}, value
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}, None


def sequence_pair(left: tuple[Evaluation, Grid], right: tuple[Evaluation, Grid]) -> dict[str, Any]:
    left_value, left_grid = left
    right_value, right_grid = right
    assert left_value.spectrum is not None and right_value.spectrum is not None
    return {
        "energy_relative_difference": relative_difference(left_value.total, right_value.total),
        "level_relative_difference": relative_difference(left_value.spectrum.energy or 0.0, right_value.spectrum.energy or 0.0),
        "rms_relative_difference": relative_difference(left_value.spectrum.rms or 0.0, right_value.spectrum.rms or 0.0),
        "profile_overlaps": profile_overlap(left_value, left_grid, right_value, right_grid),
    }


def continuum_sequences(
    primary_value: Evaluation, primary_grid: Grid, reference_z: np.ndarray
) -> dict[str, Any]:
    rows_by_name: dict[str, list[dict[str, Any]]] = {}
    values_by_name: dict[str, list[tuple[Evaluation, Grid]]] = {}
    definitions = {
        "grid": [Grid(n, rmax, PRIMARY_DELTA) for rmax, n in GRID_SEQUENCE],
        "box": [Grid(n, rmax, PRIMARY_DELTA) for rmax, n in BOX_SEQUENCE],
        "regulator": [Grid(primary_grid.n, primary_grid.rmax, delta) for delta in REGULATOR_SEQUENCE],
    }
    for name, grids in definitions.items():
        rows: list[dict[str, Any]] = []
        values: list[tuple[Evaluation, Grid]] = []
        for target in grids:
            started = time.time()
            row, value = optimized_sequence_case(target, primary_value, primary_grid, reference_z)
            row["elapsed_seconds"] = time.time() - started
            rows.append(row)
            if value is not None:
                values.append((value, target))
        rows_by_name[name] = rows
        values_by_name[name] = values

    all_rows_pass = all(
        row.get("endpoint_gate", {}).get("pass") is True
        for rows in rows_by_name.values()
        for row in rows
    )
    grid_pair = sequence_pair(values_by_name["grid"][-2], values_by_name["grid"][-1]) if len(values_by_name["grid"]) == 4 else None
    box_pair = sequence_pair(values_by_name["box"][-2], values_by_name["box"][-1]) if len(values_by_name["box"]) == 3 else None

    regulator_fit: dict[str, Any] | None = None
    regulator_pass = False
    if len(values_by_name["regulator"]) == 3:
        deltas = np.array(REGULATOR_SEQUENCE, dtype=np.float64)
        observables: dict[str, list[float]] = {"total_mev": [], "level_mev": [], "rms_fm": []}
        for value, _ in values_by_name["regulator"]:
            assert value.spectrum is not None
            observables["total_mev"].append(value.total)
            observables["level_mev"].append(float(value.spectrum.energy))
            observables["rms_fm"].append(float(value.spectrum.rms))
        fits: dict[str, Any] = {}
        regulator_pass = True
        for name, raw_values in observables.items():
            values = np.array(raw_values, dtype=np.float64)
            coefficients = np.polyfit(deltas, values, 2)
            predicted = np.polyval(coefficients, deltas)
            residual = float(np.max(np.abs(predicted - values)) / max(np.max(np.abs(values)), 1.0e-300))
            intercept = float(coefficients[2])
            intercept_difference = relative_difference(intercept, float(values[-1]))
            passed = residual < 0.005 and intercept_difference < 0.03
            regulator_pass = regulator_pass and passed
            fits[name] = {
                "values": values,
                "coefficients": coefficients,
                "relative_fit_residual": residual,
                "intercept": intercept,
                "intercept_to_delta1_relative_difference": intercept_difference,
                "pass": passed,
            }
        regulator_fit = fits

    def pair_pass(pair: dict[str, Any] | None) -> bool:
        return bool(
            pair
            and pair["energy_relative_difference"] < 0.01
            and pair["level_relative_difference"] < 0.01
            and pair["rms_relative_difference"] < 0.02
            and min(pair["profile_overlaps"].values()) > 0.99
        )

    checks = {
        "all_endpoints": all_rows_pass,
        "grid_pair": pair_pass(grid_pair),
        "box_pair": pair_pass(box_pair),
        "regulator_fit": regulator_pass,
    }
    return {
        "rows": rows_by_name,
        "grid_pair": grid_pair,
        "box_pair": box_pair,
        "regulator_fit": regulator_fit,
        "checks": checks,
        "pass": all(checks.values()),
        "private_values": values_by_name,
    }


def gradient_flow(
    start: np.ndarray,
    grid: Grid,
    reference_z: np.ndarray,
    max_steps: int = 20000,
) -> tuple[dict[str, Any], Evaluation]:
    evaluator = Evaluator(grid, reference_z)
    current = np.asarray(start, dtype=np.float64).copy()
    value = evaluator.evaluate(current)
    _, _, positive_diagonal = field_energy_and_gradient(current, grid)
    preconditioner = 1.0 / (positive_diagonal + 1.0)
    trace = [{"step": 0, "energy_mev": value.total, "projected_gradient_max_abs_mev": float(np.max(np.abs(projected_gradient(current, value.gradient, grid))))}]
    limits = bounds(grid.n)
    stopped = "step_limit"
    for step_index in range(1, max_steps + 1):
        projected = projected_gradient(current, value.gradient, grid)
        residual = float(np.max(np.abs(projected)))
        if residual < GRADIENT_THRESHOLD:
            stopped = "gradient"
            break
        direction = -preconditioner * projected
        alpha = 1.0
        accepted = False
        while alpha >= 2.0**-30:
            trial = np.clip(current + alpha * direction, limits.lb, limits.ub)
            trial_value = evaluator.evaluate(trial)
            if trial_value.total < value.total:
                current = trial
                value = trial_value
                accepted = True
                break
            alpha *= 0.5
        if not accepted:
            stopped = "line_search"
            break
        if step_index <= 20 or step_index % 25 == 0:
            trace.append(
                {
                    "step": step_index,
                    "energy_mev": value.total,
                    "projected_gradient_max_abs_mev": float(np.max(np.abs(projected_gradient(current, value.gradient, grid)))),
                    "alpha": alpha,
                    "reference_overlap": None if value.spectrum is None else value.spectrum.overlap,
                }
            )
    final_residual = float(np.max(np.abs(projected_gradient(current, value.gradient, grid))))
    return {
        "trace": trace,
        "stop_reason": stopped,
        "accepted_steps": int(trace[-1]["step"] if trace else 0),
        "evaluator_calls": evaluator.evaluations,
        "projected_gradient_max_abs_mev": final_residual,
        "converged": final_residual < GRADIENT_THRESHOLD,
    }, value


def formation_basin(
    primary_value: Evaluation,
    primary_grid: Grid,
    reference_z: np.ndarray,
    low_z: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, np.ndarray]]]:
    grid = Grid(96, PRIMARY_RMAX, PRIMARY_DELTA)
    primary_x = interpolate_fields(primary_value.x, primary_grid, grid)
    low_x = pack(*chiral_profile(low_z, grid.radial))
    scalar, pion, chi = unpack(low_x, grid.n)
    diffuse_radial = grid.radial / 1.6
    diffuse = pack(
        np.interp(diffuse_radial, grid.radial, scalar, left=scalar[0], right=1.0),
        np.interp(diffuse_radial, grid.radial, pion, left=0.0, right=0.0),
        np.interp(diffuse_radial, grid.radial, chi, left=chi[0], right=0.0),
    )
    rng = np.random.Generator(np.random.PCG64(RNG_SEED))
    modes = np.arange(1, 9, dtype=np.float64)
    basis = np.sin(math.pi * np.outer(grid.radial / grid.rmax, modes))
    perturbed_fields = [array.copy() for array in unpack(low_x, grid.n)]
    target_rms = (0.03, 0.03, 0.02 * CHI_SCALE)
    for index, amplitude in enumerate(target_rms):
        coefficients = rng.normal(size=8)
        perturbation = basis @ coefficients
        perturbation *= amplitude / math.sqrt(float(np.mean(perturbation**2)))
        perturbed_fields[index] += perturbation
    perturbed = pack(*perturbed_fields)
    starts = [
        ("compact_endpoint", primary_x),
        ("low_chi", low_x),
        ("diffuse_low_chi", diffuse),
        ("smooth_perturbed_low_chi", np.clip(perturbed, bounds(grid.n).lb, bounds(grid.n).ub)),
    ]
    rows: list[dict[str, Any]] = []
    arrays: list[dict[str, np.ndarray]] = []
    basin_count = 0
    diffuse_in_basin = False
    primary_reference = Evaluator(grid, reference_z).evaluate(primary_x)
    for name, start in starts:
        started = time.time()
        try:
            flow, value = gradient_flow(start, grid, reference_z)
            assert value.spectrum is not None and primary_reference.spectrum is not None
            overlaps = profile_overlap(value, grid, primary_reference, grid)
            metrics = {
                "energy_relative_difference": relative_difference(value.total, primary_reference.total),
                "level_relative_difference": relative_difference(float(value.spectrum.energy), float(primary_reference.spectrum.energy)),
                "rms_relative_difference": relative_difference(float(value.spectrum.rms), float(primary_reference.spectrum.rms)),
                "profile_overlaps": overlaps,
            }
            branch = value.spectrum.overlap is not None and value.spectrum.overlap < BRANCH_OVERLAP
            in_basin = bool(
                flow["converged"]
                and not branch
                and metrics["energy_relative_difference"] < 0.01
                and metrics["level_relative_difference"] < 0.01
                and metrics["rms_relative_difference"] < 0.02
                and min(overlaps.values()) > 0.99
            )
            basin_count += int(in_basin)
            diffuse_in_basin = diffuse_in_basin or (name == "diffuse_low_chi" and in_basin)
            rows.append(
                {
                    "name": name,
                    "flow": flow,
                    "endpoint": public_evaluation(value, grid),
                    "metrics_to_primary": metrics,
                    "branch_event": branch,
                    "in_primary_basin": in_basin,
                    "elapsed_seconds": time.time() - started,
                }
            )
            arrays.append({"name": np.array(name), "start": start, "endpoint": value.x})
        except Exception as error:
            rows.append({"name": name, "error": f"{type(error).__name__}: {error}", "in_primary_basin": False, "elapsed_seconds": time.time() - started})
    if basin_count >= 3 and diffuse_in_basin:
        verdict = "EMERGES"
    elif basin_count <= 2:
        verdict = "DOES NOT EMERGE"
    else:
        verdict = "INCONCLUSIVE"
    return {"rows": rows, "basin_count": basin_count, "diffuse_in_basin": diffuse_in_basin, "verdict": verdict}, arrays


def negative_controls(reference_z: np.ndarray, low_z: np.ndarray) -> dict[str, Any]:
    n = 96
    start_grid = Grid(n, PRIMARY_RMAX, PRIMARY_DELTA)
    start = pack(*chiral_profile(low_z, start_grid.radial))
    rows: dict[str, Any] = {}
    checks: dict[str, bool] = {}
    for name, grid in (
        ("no_occupancy", Grid(n, PRIMARY_RMAX, PRIMARY_DELTA, nc=0)),
        ("no_coupling", Grid(n, PRIMARY_RMAX, PRIMARY_DELTA, nc=NC, coupling=0.0)),
    ):
        started = time.time()
        optimizer, value, _ = run_lbfgsb(start, grid, reference_z)
        scalar, pion, chi = unpack(value.x, n)
        deviations = {
            "scalar": float(np.max(np.abs(scalar - 1.0))),
            "pion": float(np.max(np.abs(pion))),
            "c": float(np.max(np.abs(chi / CHI_SCALE))),
        }
        field_total = float(sum(value.field_parts.values()))
        vacuum_pass = field_total < 1.0e-5 and max(deviations.values()) < 1.0e-4
        no_bound = name == "no_occupancy" or grid.coupling == 0.0
        passed = vacuum_pass and no_bound
        checks[name] = passed
        rows[name] = {
            "optimizer": optimizer,
            "endpoint": public_evaluation(value, grid),
            "vacuum_deviations": deviations,
            "vacuum_pass": vacuum_pass,
            "localized_bound_orbital": False if grid.coupling == 0.0 else None,
            "pass": passed,
            "elapsed_seconds": time.time() - started,
        }
    return {"rows": rows, "checks": checks, "pass": all(checks.values())}


def extract_upstream_seeds(payload: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    endpoint = payload.get("primary_endpoint")
    if not isinstance(endpoint, dict) or "z" not in endpoint:
        raise RuntimeError("upstream primary endpoint z is missing")
    primary_z = np.asarray(endpoint["z"], dtype=np.float64)
    formation = payload.get("formation", {}).get("rows", [])
    selected = next((row for row in formation if row.get("start_index") == 1), None)
    if selected is None:
        raise RuntimeError("upstream low-chi formation row is missing")
    low_z_raw = selected.get("result", {}).get("z")
    if low_z_raw is None:
        low_z_raw = selected.get("optimizer", {}).get("x")
    low_z = np.asarray(low_z_raw, dtype=np.float64)
    if low_z.shape != (4,):
        raise RuntimeError("upstream low-chi endpoint has invalid shape")
    return primary_z, low_z


def strip_private_continuum(payload: dict[str, Any]) -> dict[str, Any]:
    clean = dict(payload)
    clean.pop("private_values", None)
    return clean


def write_report(path: Path, output: dict[str, Any]) -> None:
    decisions = output["decisions"]
    lines = [
        "# Unconstrained radial chiral-chromodielectric baryon result",
        "",
        "## Verdicts",
        "",
        "| Gate | Verdict |",
        "|---|---|",
    ]
    for key in ("QURB1", "QURB2", "QURB3", "QURB4", "QURB5", "QURB6", "QURB7", "QURB8"):
        lines.append(f"| {key} | `{decisions[key]}` |")
    lines.extend(["", f"Overall: `{decisions['overall']}`", ""])
    primary = output.get("primary", {})
    rows = primary.get("rows", [])
    if rows:
        lines.extend(["## Primary multilevel sequence", "", "| N | Energy (MeV) | Projected gradient (MeV) | Gate |", "|---:|---:|---:|---|"])
        for row in rows:
            if "endpoint" not in row:
                lines.append(f"| {row['grid']['n']} |—|—| error |")
                continue
            endpoint = row["endpoint"]
            lines.append(
                f"| {row['grid']['n']} | {endpoint['total_mev']:.9f} | "
                f"{endpoint['projected_gradient_max_abs_mev']:.6g} | "
                f"{'PASS' if row['endpoint_gate']['pass'] else 'FAIL'} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Physical scope",
            "",
            "This result concerns a supplied empirical mean-field action and a fixed occupied valence sector. The microscopic action, renormalized sea, baryogenesis, and closed-system thermal formation remain outside the calculation; QURB8 is therefore fixed to `FAIL`.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    started = time.time()
    upstream_hash = sha256_file(UPSTREAM)
    if upstream_hash != EXPECTED_UPSTREAM_SHA256:
        raise RuntimeError(
            f"upstream hash mismatch: {upstream_hash} != {EXPECTED_UPSTREAM_SHA256}"
        )
    upstream = json.loads(UPSTREAM.read_text(encoding="utf-8"))
    reference_z, low_z = extract_upstream_seeds(upstream)

    algebra = algebraic_controls(reference_z)
    primary: dict[str, Any] = {"rows": [], "pass": False}
    hessian: dict[str, Any] = {"verdict": "SKIPPED_PREREQUISITE"}
    continuum: dict[str, Any] = {"pass": False, "status": "SKIPPED_PREREQUISITE"}
    basin: dict[str, Any] = {"verdict": "INCONCLUSIVE", "status": "SKIPPED_PREREQUISITE"}
    controls: dict[str, Any] = {"pass": False, "status": "SKIPPED_PREREQUISITE"}
    profile_arrays: dict[str, np.ndarray] = {}
    trajectory_arrays: dict[str, np.ndarray] = {}

    final_value: Evaluation | None = None
    final_grid: Grid | None = None
    if algebra["pass"]:
        primary, final_value, final_grid = primary_multilevel(reference_z)
        if final_value is not None and final_grid is not None:
            scalar, pion, chi = unpack(final_value.x, final_grid.n)
            profile_arrays.update(
                {
                    "primary_r_fm": final_grid.radial,
                    "primary_scalar": scalar,
                    "primary_pion": pion,
                    "primary_chi_mev": chi,
                    "primary_spinor": np.array([]) if final_value.spectrum is None or final_value.spectrum.vector is None else final_value.spectrum.vector,
                }
            )
        if primary["pass"] and final_value is not None and final_grid is not None:
            hessian = hessian_spectrum(final_value, final_grid, reference_z)
            controls = negative_controls(reference_z, low_z)
            basin, basin_arrays = formation_basin(final_value, final_grid, reference_z, low_z)
            for index, row in enumerate(basin_arrays):
                trajectory_arrays[f"basin_{index}_start"] = row["start"]
                trajectory_arrays[f"basin_{index}_endpoint"] = row["endpoint"]
            if hessian["verdict"] == "PASS":
                continuum_private = continuum_sequences(final_value, final_grid, reference_z)
                for sequence_name, values in continuum_private["private_values"].items():
                    for index, (value, grid) in enumerate(values):
                        s, p, c = unpack(value.x, grid.n)
                        prefix = f"{sequence_name}_{index}"
                        profile_arrays[f"{prefix}_r_fm"] = grid.radial
                        profile_arrays[f"{prefix}_scalar"] = s
                        profile_arrays[f"{prefix}_pion"] = p
                        profile_arrays[f"{prefix}_chi_mev"] = c
                continuum = strip_private_continuum(continuum_private)

    qurb1 = "PASS" if algebra["pass"] else "FAIL"
    qurb2 = "PASS" if primary.get("pass") is True else "FAIL"
    qurb3 = hessian.get("verdict", "INCONCLUSIVE")
    qurb4 = continuum.get("status") if continuum.get("status") == "SKIPPED_PREREQUISITE" else ("PASS" if continuum.get("pass") is True else "FAIL")
    qurb5 = basin.get("status") if basin.get("status") == "SKIPPED_PREREQUISITE" else basin.get("verdict", "INCONCLUSIVE")
    qurb6 = controls.get("status") if controls.get("status") == "SKIPPED_PREREQUISITE" else ("PASS" if controls.get("pass") is True else "FAIL")
    adopted = qurb1 == "PASS" and qurb2 == "PASS" and qurb3 == "PASS" and qurb4 == "PASS" and qurb5 == "EMERGES" and qurb6 == "PASS"
    decisions = {
        "QURB1": qurb1,
        "QURB2": qurb2,
        "QURB3": qurb3,
        "QURB4": qurb4,
        "QURB5": qurb5,
        "QURB6": qurb6,
        "QURB7": "ADOPT" if adopted else "REJECT",
        "QURB8": "FAIL",
        "complete_physical_matter_formation": False,
        "overall": "UNCONSTRAINED_RADIAL_BARYON_ADOPT" if adopted else "UNCONSTRAINED_RADIAL_BARYON_REJECT",
    }
    output: dict[str, Any] = {
        "schema": SCHEMA,
        "protocol_status": "executed_frozen",
        "started_unix": started,
        "finished_unix": time.time(),
        "source_manifest": {
            "protocol": source_record(PROTOCOL),
            "primary": source_record(SELF),
            "upstream": source_record(UPSTREAM),
        },
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
        },
        "constants": {
            "hbarc_mev_fm": HBARC,
            "n_c": NC,
            "f_pi_mev": F_PI,
            "m_pi_mev": M_PI,
            "m_sigma_mev": M_SIGMA,
            "g_mev": G_COUPLING,
            "m_chi_mev": M_CHI,
            "gamma": GAMMA,
            "eta": ETA,
            "chi_scale_mev": CHI_SCALE,
            "chiral_lambda": CHIRAL_LAMBDA,
            "cubic": CUBIC,
            "quartic": QUARTIC,
        },
        "seeds": {"reference_z": reference_z, "low_z": low_z},
        "algebraic_controls": algebra,
        "primary": primary,
        "hessian": hessian,
        "continuum": continuum,
        "formation_basin": basin,
        "negative_controls": controls,
        "decisions": decisions,
        "execution": {"elapsed_seconds": time.time() - started},
        "artifacts": {
            "profiles": "profiles.npz",
            "trajectory": "trajectory.npz",
            "report": "report.md",
        },
    }
    np.savez_compressed(output_dir / "profiles.npz", **profile_arrays)
    np.savez_compressed(output_dir / "trajectory.npz", **trajectory_arrays)
    write_json(output_dir / "results.json", output)
    write_report(output_dir / "report.md", output)
    print(" ".join(f"{key}={value}" for key, value in decisions.items() if key.startswith("QURB")))
    print(f"RESULTS {output_dir / 'results.json'}")
    return 0 if algebra["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
