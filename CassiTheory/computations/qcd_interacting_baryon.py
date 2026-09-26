#!/usr/bin/env python3
"""Run the preregistered interacting chiral-chromodielectric baryon calculation.

Run from the CassiTheory repository root:
    python computations/qcd_interacting_baryon.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy import integrate, optimize, sparse
from scipy.sparse import linalg as spla


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-interacting-baryon-prereg.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_interacting_baryon"
    / "primary"
    / "recovery3"
)
SCHEMA = "cassi.qcd-interacting-baryon.primary.v1"

HBARC = 197.3269804
NC = 3
F_PI = 93.0
M_PI = 139.6
M_SIGMA = 1200.0
G_COUPLING = 23.0
M_CHI = 1700.0
GAMMA = 0.2
ETA = 0.12
CHIRAL_LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)

RMAX_PRIMARY = 10.0
N_PRIMARY = 320
DELTA_PRIMARY = 2.0
DE_SEED = 260910
NORMALIZED_BOUNDS = [(0.0, 1.0)] * 4
PHYSICAL_LOW = np.array([0.0, 0.15, 1.0, 0.15], dtype=np.float64)
PHYSICAL_HIGH = np.array([1.0, 2.50, 510.0, 2.50], dtype=np.float64)
FD_STEP = 0.002
PENALTY_BASE = 1.0e7
TAIL_RADIUS = 8.0

GRID_SEQUENCE = (240, 320, 480, 640)
BOX_SEQUENCE = ((8.0, 256), (10.0, 320), (12.0, 384))
REGULATOR_SEQUENCE = (8.0, 4.0, 2.0, 1.0, 0.5)
DILATION_SEQUENCE = (0.50, 0.70, 0.85, 0.95, 1.00, 1.05, 1.15, 1.40, 2.00)
AFFINE_SEQUENCE = (-0.20, -0.10, 0.0, 0.10, 0.20)
FORMATION_STARTS = (
    (0.00, 0.30, 15.0, 0.30),
    (0.25, 0.50, 25.0, 0.50),
    (0.50, 0.70, 40.0, 0.70),
    (0.75, 0.90, 60.0, 0.90),
    (1.00, 1.10, 80.0, 1.10),
    (0.20, 1.40, 120.0, 0.60),
    (0.40, 0.60, 160.0, 1.40),
    (0.60, 1.80, 220.0, 1.00),
    (0.80, 1.00, 280.0, 1.80),
    (1.00, 2.10, 340.0, 1.30),
    (0.35, 1.60, 420.0, 2.10),
    (0.65, 2.30, 480.0, 2.30),
)


@dataclass(frozen=True)
class Case:
    n: int = N_PRIMARY
    rmax: float = RMAX_PRIMARY
    delta: float = DELTA_PRIMARY
    coupling_mode: str = "chromodielectric"
    nc: int = NC


@dataclass
class Spectrum:
    radial: np.ndarray
    eigenvalues: np.ndarray
    vector: np.ndarray | None
    upper: np.ndarray | None
    lower: np.ndarray | None
    candidate_energy: float | None
    nodes: int | None
    rms: float | None
    tail_probability: float | None
    same_sign_gap: float | None
    normalization_error: float | None
    hermiticity_error: float
    kinetic_one: float | None
    interaction_one: float | None
    wilson_one: float | None


@dataclass
class EnergyResult:
    z: np.ndarray
    case: Case
    spectrum: Spectrum
    chiral_gradient: float
    chiral_potential: float
    chi_gradient: float
    chi_potential: float
    field_tail_bound: float
    total: float
    penalized: bool


_CACHE: dict[tuple[Any, ...], EnergyResult] = {}
_EVALUATIONS = 0


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


def physical_to_normalized(z: np.ndarray) -> np.ndarray:
    return (np.asarray(z, dtype=np.float64) - PHYSICAL_LOW) / (
        PHYSICAL_HIGH - PHYSICAL_LOW
    )


def normalized_to_physical(x: np.ndarray) -> np.ndarray:
    return PHYSICAL_LOW + np.asarray(x, dtype=np.float64) * (
        PHYSICAL_HIGH - PHYSICAL_LOW
    )


def chiral_profile(
    a: float, radius: float, r: np.ndarray | float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    radial = np.asarray(r, dtype=np.float64)
    denominator = radial**4 + radius**4
    cos_f = (radial**4 - radius**4) / denominator
    sin_f = 2.0 * radius**2 * radial**2 / denominator
    f_prime = -4.0 * radius**2 * radial / denominator
    scalar = 1.0 - a + a * cos_f
    pion = -a * sin_f
    scalar_prime = -a * sin_f * f_prime
    pion_prime = -a * cos_f * f_prime
    return scalar, pion, scalar_prime, pion_prime


def chi_profile(
    amplitude: float, radius: float, r: np.ndarray | float
) -> tuple[np.ndarray, np.ndarray]:
    radial = np.asarray(r, dtype=np.float64)
    value = amplitude * np.exp(-((radial / radius) ** 2))
    derivative = -2.0 * radial * value / radius**2
    return value, derivative


def chiral_potential(scalar: np.ndarray, pion: np.ndarray) -> np.ndarray:
    radial_delta = scalar * scalar + pion * pion - 1.0
    return (
        0.5
        * M_PI**2
        * F_PI**2
        * ((scalar - 1.0) ** 2 + pion * pion)
        + 0.25 * CHIRAL_LAMBDA * F_PI**4 * radial_delta**2
    )


def chi_potential(chi: np.ndarray | float) -> np.ndarray:
    value = np.asarray(chi, dtype=np.float64)
    scaled = value / (GAMMA * M_CHI)
    cubic = 8.0 * ETA**4 / GAMMA**2 - 2.0
    quartic = 1.0 - 6.0 * ETA**4 / GAMMA**2
    return 0.5 * M_CHI**2 * value**2 * (
        1.0 + cubic * scaled + quartic * scaled**2
    )


def chi_potential_derivative(chi: float) -> float:
    scaled = chi / (GAMMA * M_CHI)
    cubic = 8.0 * ETA**4 / GAMMA**2 - 2.0
    quartic = 1.0 - 6.0 * ETA**4 / GAMMA**2
    return M_CHI**2 * chi * (
        1.0 + 1.5 * cubic * scaled + 2.0 * quartic * scaled**2
    )


def derivative_matrix(n: int, dr: float) -> sparse.csr_matrix:
    matrix = sparse.lil_matrix((n, n), dtype=np.float64)
    matrix[0, 0] = -0.5 / dr
    matrix[0, 1] = 0.5 / dr
    for index in range(1, n - 1):
        matrix[index, index - 1] = -0.5 / dr
        matrix[index, index + 1] = 0.5 / dr
    matrix[n - 1, n - 2] = -0.5 / dr
    return matrix.tocsr()


def count_nodes(radial: np.ndarray, amplitude: np.ndarray, probability: np.ndarray) -> int:
    cumulative = np.cumsum(probability)
    cutoff = int(np.searchsorted(cumulative, 0.999, side="left"))
    cutoff = max(2, min(cutoff, radial.size - 1))
    peak = float(np.max(np.abs(amplitude[: cutoff + 1])))
    if peak == 0.0:
        return radial.size
    mask = np.abs(amplitude[: cutoff + 1]) > 1.0e-3 * peak
    signs = np.sign(amplitude[: cutoff + 1][mask])
    if signs.size < 2:
        return 0
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0))


def radial_spectrum(z: np.ndarray, case: Case) -> Spectrum:
    a, chiral_radius, chi_amplitude, chi_radius = [float(item) for item in z]
    dr = case.rmax / case.n
    radial = (np.arange(case.n, dtype=np.float64) + 0.5) * dr
    weight_sqrt = radial * math.sqrt(dr)
    weight_inverse = 1.0 / weight_sqrt

    derivative = derivative_matrix(case.n, dr)
    left_scale = sparse.diags(weight_sqrt, format="csr")
    right_scale = sparse.diags(weight_inverse, format="csr")
    derivative_tilde = left_scale @ derivative @ right_scale
    wilson = 0.5 * HBARC * dr * (derivative_tilde.T @ derivative_tilde)

    scalar, pion, _, _ = chiral_profile(a, chiral_radius, radial)
    chi, _ = chi_profile(chi_amplitude, chi_radius, radial)
    if case.coupling_mode == "chromodielectric":
        denominator = np.sqrt(chi * chi + case.delta * case.delta)
        scalar_mass = G_COUPLING * F_PI * scalar / denominator
        pseudoscalar_mass = G_COUPLING * F_PI * pion / denominator
    elif case.coupling_mode == "constant":
        scalar_mass = 500.0 * scalar
        pseudoscalar_mass = 500.0 * pion
    else:
        raise ValueError(f"unknown coupling mode {case.coupling_mode}")

    scalar_matrix = sparse.diags(scalar_mass, format="csr")
    pion_matrix = sparse.diags(pseudoscalar_mass, format="csr")
    derivative_block = HBARC * derivative_tilde
    mass = scalar_matrix + wilson
    offdiag = derivative_block - pion_matrix
    hamiltonian = sparse.bmat(
        [[mass, offdiag.T], [offdiag, -mass]],
        format="csc",
        dtype=np.float64,
    )
    kinetic_matrix = sparse.bmat(
        [
            [None, derivative_block.T],
            [derivative_block, None],
        ],
        format="csr",
        dtype=np.float64,
    )
    interaction_matrix = sparse.bmat(
        [
            [scalar_matrix, -pion_matrix],
            [-pion_matrix, -scalar_matrix],
        ],
        format="csr",
        dtype=np.float64,
    )
    wilson_matrix = sparse.bmat(
        [[wilson, None], [None, -wilson]],
        format="csr",
        dtype=np.float64,
    )

    asymmetry = hamiltonian - hamiltonian.T
    hermiticity_error = (
        float(np.max(np.abs(asymmetry.data))) if asymmetry.nnz else 0.0
    )
    start = np.linspace(1.0, 2.0, 2 * case.n, dtype=np.float64)
    start /= np.linalg.norm(start)
    eigenvalues, eigenvectors = spla.eigsh(
        hamiltonian,
        k=12,
        sigma=0.0,
        which="LM",
        tol=2.0e-11,
        maxiter=12000,
        v0=start,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)

    states: list[dict[str, Any]] = []
    for column, energy in enumerate(eigenvalues):
        vector = eigenvectors[:, column].copy()
        upper = vector[: case.n] * weight_inverse
        lower = vector[case.n :] * weight_inverse
        if upper[0] < 0.0:
            vector *= -1.0
            upper *= -1.0
            lower *= -1.0
        raw_norm = float(np.dot(vector, vector))
        probability = vector[: case.n] ** 2 + vector[case.n :] ** 2
        probability /= float(np.sum(probability))
        states.append(
            {
                "energy": float(energy),
                "vector": vector,
                "upper": upper,
                "lower": lower,
                "nodes": count_nodes(radial, upper, probability),
                "rms": math.sqrt(float(np.dot(probability, radial**2))),
                "tail": float(np.sum(probability[radial >= TAIL_RADIUS])),
                "normalization_error": abs(raw_norm - 1.0),
            }
        )

    candidates = [
        state
        for state in states
        if state["energy"] > 0.0 and state["nodes"] == 0
    ]
    candidate = min(candidates, key=lambda state: state["energy"]) if candidates else None
    if candidate is None:
        return Spectrum(
            radial=radial,
            eigenvalues=eigenvalues,
            vector=None,
            upper=None,
            lower=None,
            candidate_energy=None,
            nodes=None,
            rms=None,
            tail_probability=None,
            same_sign_gap=None,
            normalization_error=None,
            hermiticity_error=hermiticity_error,
            kinetic_one=None,
            interaction_one=None,
            wilson_one=None,
        )

    alternatives = [
        state["energy"] - candidate["energy"]
        for state in states
        if state["energy"] > candidate["energy"] + 1.0e-9
    ]
    same_sign_gap = min(alternatives) if alternatives else None
    vector = candidate["vector"]
    kinetic_one = float(vector @ (kinetic_matrix @ vector))
    interaction_one = float(vector @ (interaction_matrix @ vector))
    wilson_one = float(vector @ (wilson_matrix @ vector))
    return Spectrum(
        radial=radial,
        eigenvalues=eigenvalues,
        vector=vector,
        upper=candidate["upper"],
        lower=candidate["lower"],
        candidate_energy=candidate["energy"],
        nodes=candidate["nodes"],
        rms=candidate["rms"],
        tail_probability=candidate["tail"],
        same_sign_gap=same_sign_gap,
        normalization_error=candidate["normalization_error"],
        hermiticity_error=hermiticity_error,
        kinetic_one=kinetic_one,
        interaction_one=interaction_one,
        wilson_one=wilson_one,
    )


def field_energy_parts(z: np.ndarray, case: Case) -> tuple[float, float, float, float]:
    a, chiral_radius, chi_amplitude, chi_radius = [float(item) for item in z]
    radial = np.linspace(0.0, case.rmax, 2 * case.n + 1, dtype=np.float64)
    scalar, pion, scalar_prime, pion_prime = chiral_profile(
        a, chiral_radius, radial
    )
    chi, chi_prime = chi_profile(chi_amplitude, chi_radius, radial)
    angular = np.zeros_like(radial)
    angular[1:] = 2.0 * pion[1:] ** 2 / radial[1:] ** 2

    chiral_gradient_density = F_PI**2 / (2.0 * HBARC) * (
        scalar_prime**2 + pion_prime**2 + angular
    )
    chiral_potential_density = chiral_potential(scalar, pion) / HBARC**3
    chi_gradient_density = chi_prime**2 / (2.0 * HBARC)
    chi_potential_density = chi_potential(chi) / HBARC**3
    measure = 4.0 * math.pi * radial**2
    return (
        float(integrate.simpson(measure * chiral_gradient_density, x=radial)),
        float(integrate.simpson(measure * chiral_potential_density, x=radial)),
        float(integrate.simpson(measure * chi_gradient_density, x=radial)),
        float(integrate.simpson(measure * chi_potential_density, x=radial)),
    )


def field_tail_energy(z: np.ndarray, rmax: float) -> float:
    a, chiral_radius, chi_amplitude, chi_radius = [float(item) for item in z]

    def integrand(radius: float) -> float:
        scalar, pion, scalar_prime, pion_prime = chiral_profile(
            a, chiral_radius, radius
        )
        chi, chi_prime = chi_profile(chi_amplitude, chi_radius, radius)
        angular = 0.0 if radius == 0.0 else 2.0 * float(pion) ** 2 / radius**2
        density = (
            F_PI**2
            / (2.0 * HBARC)
            * (
                float(scalar_prime) ** 2
                + float(pion_prime) ** 2
                + angular
            )
            + float(chiral_potential(scalar, pion)) / HBARC**3
            + float(chi_prime) ** 2 / (2.0 * HBARC)
            + float(chi_potential(chi)) / HBARC**3
        )
        return 4.0 * math.pi * radius**2 * density

    value, _ = integrate.quad(
        integrand,
        rmax,
        np.inf,
        epsabs=1.0e-10,
        epsrel=1.0e-9,
        limit=800,
    )
    return float(value)


def energy_result(z: np.ndarray, case: Case) -> EnergyResult:
    global _EVALUATIONS
    physical = np.asarray(z, dtype=np.float64)
    key = (
        *(round(float(item), 10) for item in physical),
        case.n,
        round(case.rmax, 10),
        round(case.delta, 10),
        case.coupling_mode,
        case.nc,
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    _EVALUATIONS += 1
    chiral_gradient, chiral_potential_energy, chi_gradient, chi_potential_energy = (
        field_energy_parts(physical, case)
    )
    spectrum = radial_spectrum(physical, case)
    field_total = (
        chiral_gradient
        + chiral_potential_energy
        + chi_gradient
        + chi_potential_energy
    )
    penalized = spectrum.candidate_energy is None
    if spectrum.candidate_energy is None:
        total = PENALTY_BASE + 1.0e3 * float(np.sum(physical))
    else:
        total = case.nc * spectrum.candidate_energy + field_total
        if not math.isfinite(total):
            penalized = True
            total = PENALTY_BASE + 1.0e3 * float(np.sum(physical))
    result = EnergyResult(
        z=physical.copy(),
        case=case,
        spectrum=spectrum,
        chiral_gradient=chiral_gradient,
        chiral_potential=chiral_potential_energy,
        chi_gradient=chi_gradient,
        chi_potential=chi_potential_energy,
        field_tail_bound=float("nan"),
        total=float(total),
        penalized=penalized,
    )
    _CACHE[key] = result
    return result


def objective_x(x: np.ndarray, case: Case) -> float:
    clipped = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    return energy_result(normalized_to_physical(clipped), case).total


def state_overlap(left: Spectrum, right: Spectrum) -> float:
    if (
        left.upper is None
        or left.lower is None
        or right.upper is None
        or right.lower is None
    ):
        return 0.0
    lower_bound = max(float(left.radial[0]), float(right.radial[0]))
    upper_bound = min(float(left.radial[-1]), float(right.radial[-1]))
    count = max(left.radial.size, right.radial.size) * 4
    radial = np.linspace(lower_bound, upper_bound, count, dtype=np.float64)
    left_upper = np.interp(radial, left.radial, left.upper)
    left_lower = np.interp(radial, left.radial, left.lower)
    right_upper = np.interp(radial, right.radial, right.upper)
    right_lower = np.interp(radial, right.radial, right.lower)
    left_norm = math.sqrt(
        float(
            integrate.simpson(
                radial**2 * (left_upper**2 + left_lower**2), x=radial
            )
        )
    )
    right_norm = math.sqrt(
        float(
            integrate.simpson(
                radial**2 * (right_upper**2 + right_lower**2), x=radial
            )
        )
    )
    overlap = integrate.simpson(
        radial**2
        * (left_upper * right_upper + left_lower * right_lower),
        x=radial,
    )
    return float(abs(overlap) / (left_norm * right_norm))


def public_spectrum(spectrum: Spectrum) -> dict[str, Any]:
    return {
        "eigenvalues_mev": spectrum.eigenvalues,
        "candidate_energy_mev": spectrum.candidate_energy,
        "nodes_upper": spectrum.nodes,
        "rms_fm": spectrum.rms,
        "tail_probability_r_ge_8fm": spectrum.tail_probability,
        "same_sign_gap_mev": spectrum.same_sign_gap,
        "normalization_error": spectrum.normalization_error,
        "hermiticity_error_mev": spectrum.hermiticity_error,
        "kinetic_one_quark_mev": spectrum.kinetic_one,
        "interaction_one_quark_mev": spectrum.interaction_one,
        "wilson_one_quark_mev": spectrum.wilson_one,
    }


def public_energy(result: EnergyResult, include_tail: bool = True) -> dict[str, Any]:
    tail = field_tail_energy(result.z, result.case.rmax) if include_tail else None
    return {
        "z": result.z,
        "normalized_z": physical_to_normalized(result.z),
        "case": {
            "n": result.case.n,
            "rmax_fm": result.case.rmax,
            "delta_mev": result.case.delta,
            "coupling_mode": result.case.coupling_mode,
            "n_c": result.case.nc,
        },
        "spectrum": public_spectrum(result.spectrum),
        "energies_mev": {
            "chiral_gradient": result.chiral_gradient,
            "chiral_potential": result.chiral_potential,
            "chi_gradient": result.chi_gradient,
            "chi_potential": result.chi_potential,
            "field_total": (
                result.chiral_gradient
                + result.chiral_potential
                + result.chi_gradient
                + result.chi_potential
            ),
            "quark_levels": (
                None
                if result.spectrum.candidate_energy is None
                else result.case.nc * result.spectrum.candidate_energy
            ),
            "total": result.total,
            "field_tail_beyond_box": tail,
        },
        "penalized": result.penalized,
    }


def run_powell(
    start_x: np.ndarray,
    case: Case,
    *,
    record_path: bool = False,
) -> tuple[optimize.OptimizeResult, list[float]]:
    history = [objective_x(start_x, case)]

    def callback(current: np.ndarray) -> None:
        if record_path:
            history.append(objective_x(current, case))

    result = optimize.minimize(
        lambda x: objective_x(x, case),
        np.asarray(start_x, dtype=np.float64),
        method="Powell",
        bounds=NORMALIZED_BOUNDS,
        callback=callback,
        options={
            "xtol": 1.0e-6,
            "ftol": 1.0e-8,
            "maxiter": 240,
            "disp": False,
        },
    )
    if not record_path:
        history.append(float(result.fun))
    elif not history or abs(history[-1] - float(result.fun)) > 1.0e-12:
        history.append(float(result.fun))
    return result, history


def optimize_primary(case: Case) -> dict[str, Any]:
    start_time = time.perf_counter()
    differential = optimize.differential_evolution(
        lambda x: objective_x(x, case),
        bounds=NORMALIZED_BOUNDS,
        seed=DE_SEED,
        popsize=10,
        maxiter=70,
        mutation=(0.5, 1.0),
        recombination=0.7,
        tol=1.0e-7,
        workers=1,
        updating="immediate",
        polish=False,
        disp=False,
    )
    polished, history = run_powell(np.asarray(differential.x), case)
    endpoint = energy_result(normalized_to_physical(polished.x), case)
    return {
        "differential": differential,
        "polished": polished,
        "history": history,
        "endpoint": endpoint,
        "elapsed_seconds": time.perf_counter() - start_time,
    }


def optimization_record(result: optimize.OptimizeResult) -> dict[str, Any]:
    return {
        "x": np.asarray(result.x, dtype=np.float64),
        "fun_mev": float(result.fun),
        "success": bool(result.success),
        "message": str(result.message),
        "nit": int(result.nit),
        "nfev": int(result.nfev),
    }


def finite_difference_diagnostics(
    endpoint: EnergyResult,
) -> dict[str, Any]:
    x0 = physical_to_normalized(endpoint.z)
    e0 = endpoint.total
    h = FD_STEP
    free: list[int] = []
    active_lower: list[int] = []
    active_upper: list[int] = []
    for index, coordinate in enumerate(x0):
        if coordinate <= 1.5 * h:
            active_lower.append(index)
        elif coordinate >= 1.0 - 1.5 * h:
            active_upper.append(index)
        else:
            free.append(index)

    point_cache: dict[tuple[float, ...], EnergyResult] = {}
    overlap_rows: list[dict[str, Any]] = []

    def evaluated(x: np.ndarray) -> EnergyResult:
        key = tuple(round(float(item), 12) for item in x)
        if key not in point_cache:
            row = energy_result(normalized_to_physical(x), endpoint.case)
            point_cache[key] = row
            overlap_rows.append(
                {
                    "x": x.copy(),
                    "energy_mev": row.total,
                    "overlap": state_overlap(endpoint.spectrum, row.spectrum),
                    "nodes": row.spectrum.nodes,
                    "penalized": row.penalized,
                }
            )
        return point_cache[key]

    gradient = np.full(4, np.nan, dtype=np.float64)
    for index in range(4):
        plus = x0.copy()
        minus = x0.copy()
        if index in active_lower:
            plus[index] += h
            gradient[index] = (evaluated(plus).total - e0) / h
        elif index in active_upper:
            minus[index] -= h
            gradient[index] = (e0 - evaluated(minus).total) / h
        else:
            plus[index] += h
            minus[index] -= h
            gradient[index] = (
                evaluated(plus).total - evaluated(minus).total
            ) / (2.0 * h)

    hessian = np.zeros((len(free), len(free)), dtype=np.float64)
    for row_index, left in enumerate(free):
        plus = x0.copy()
        minus = x0.copy()
        plus[left] += h
        minus[left] -= h
        hessian[row_index, row_index] = (
            evaluated(plus).total - 2.0 * e0 + evaluated(minus).total
        ) / h**2
        for column_index in range(row_index + 1, len(free)):
            right = free[column_index]
            pp = x0.copy()
            pm = x0.copy()
            mp = x0.copy()
            mm = x0.copy()
            pp[left] += h
            pp[right] += h
            pm[left] += h
            pm[right] -= h
            mp[left] -= h
            mp[right] += h
            mm[left] -= h
            mm[right] -= h
            value = (
                evaluated(pp).total
                - evaluated(pm).total
                - evaluated(mp).total
                + evaluated(mm).total
            ) / (4.0 * h**2)
            hessian[row_index, column_index] = value
            hessian[column_index, row_index] = value

    eigenvalues = (
        np.linalg.eigvalsh(hessian) if hessian.size else np.array([], dtype=np.float64)
    )
    free_gradient_max = (
        float(np.max(np.abs(gradient[free]))) if free else 0.0
    )
    kkt_lower = all(float(gradient[index]) >= -1.0 for index in active_lower)
    kkt_upper = all(float(gradient[index]) <= 1.0 for index in active_upper)
    valid_overlaps = [
        float(row["overlap"])
        for row in overlap_rows
        if not row["penalized"] and row["nodes"] == endpoint.spectrum.nodes
    ]
    branch_minimum = min(valid_overlaps) if valid_overlaps else 0.0
    all_stencils_valid = len(valid_overlaps) == len(overlap_rows)
    return {
        "normalized_endpoint": x0,
        "step": h,
        "free_indices": free,
        "active_lower_indices": active_lower,
        "active_upper_indices": active_upper,
        "gradient_mev_per_normalized_coordinate": gradient,
        "free_gradient_max_abs": free_gradient_max,
        "kkt_lower_pass": kkt_lower,
        "kkt_upper_pass": kkt_upper,
        "projected_hessian_mev": hessian,
        "projected_hessian_eigenvalues_mev": eigenvalues,
        "projected_hessian_minimum_mev": (
            float(eigenvalues[0]) if eigenvalues.size else None
        ),
        "branch_minimum_overlap": branch_minimum,
        "all_stencils_valid": all_stencils_valid,
        "stencils": overlap_rows,
    }


def optimized_case(
    case: Case,
    primary_x: np.ndarray,
    primary: EnergyResult | None = None,
) -> dict[str, Any]:
    if (
        primary is not None
        and case == primary.case
        and np.max(np.abs(primary_x - physical_to_normalized(primary.z))) < 1.0e-12
    ):
        return {
            "optimizer": {
                "x": primary_x,
                "fun_mev": primary.total,
                "success": True,
                "message": "primary endpoint reused",
                "nit": 0,
                "nfev": 0,
            },
            "result_private": primary,
        }
    optimized, _ = run_powell(primary_x, case)
    row = energy_result(normalized_to_physical(optimized.x), case)
    return {
        "optimizer": optimization_record(optimized),
        "result_private": row,
    }


def sequence_with_overlaps(
    cases: list[Case],
    primary_x: np.ndarray,
    primary: EnergyResult,
) -> list[dict[str, Any]]:
    rows = [optimized_case(case, primary_x, primary) for case in cases]
    for index, row in enumerate(rows):
        result = row["result_private"]
        row["result"] = public_energy(result)
        row["overlap_with_primary"] = state_overlap(primary.spectrum, result.spectrum)
        row["overlap_with_previous"] = (
            None
            if index == 0
            else state_overlap(
                rows[index - 1]["result_private"].spectrum,
                result.spectrum,
            )
        )
    for row in rows:
        del row["result_private"]
    return rows


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def sequence_pair_metrics(
    rows: list[dict[str, Any]], left_index: int, right_index: int
) -> dict[str, Any]:
    left = rows[left_index]["result"]
    right = rows[right_index]["result"]
    left_spectrum = left["spectrum"]
    right_spectrum = right["spectrum"]
    return {
        "energy_relative_difference": relative_difference(
            float(left["energies_mev"]["total"]),
            float(right["energies_mev"]["total"]),
        ),
        "level_relative_difference": relative_difference(
            float(left_spectrum["candidate_energy_mev"]),
            float(right_spectrum["candidate_energy_mev"]),
        ),
        "rms_relative_difference": relative_difference(
            float(left_spectrum["rms_fm"]),
            float(right_spectrum["rms_fm"]),
        ),
        "state_overlap": float(rows[right_index]["overlap_with_previous"]),
    }


def dilation_diagnostics(endpoint: EnergyResult) -> dict[str, Any]:
    spectrum = endpoint.spectrum
    if (
        spectrum.kinetic_one is None
        or spectrum.interaction_one is None
        or spectrum.wilson_one is None
    ):
        raise RuntimeError("endpoint has no selected state for dilation diagnostics")
    gradient = endpoint.chiral_gradient + endpoint.chi_gradient
    potential = endpoint.chiral_potential + endpoint.chi_potential
    kinetic_three = NC * spectrum.kinetic_one
    interaction_three = NC * spectrum.interaction_one
    virial = -kinetic_three + gradient + 3.0 * potential
    virial_scale = abs(kinetic_three) + gradient + 3.0 * abs(potential)
    direct_rows: list[dict[str, Any]] = []
    for scale in DILATION_SEQUENCE:
        z = endpoint.z.copy()
        z[1] *= scale
        z[3] *= scale
        row = energy_result(z, endpoint.case)
        direct_rows.append(
            {
                "lambda": scale,
                "z": z,
                "total_mev": row.total,
                "difference_from_endpoint_mev": row.total - endpoint.total,
                "spectrum": public_spectrum(row.spectrum),
            }
        )
    return {
        "kinetic_three_quark_mev": kinetic_three,
        "interaction_three_quark_mev": interaction_three,
        "wilson_three_quark_mev": NC * spectrum.wilson_one,
        "field_gradient_mev": gradient,
        "field_potential_mev": potential,
        "virial_residual_mev": virial,
        "virial_relative_residual": abs(virial) / max(virial_scale, 1.0e-300),
        "rows": direct_rows,
    }


def affine_diagnostics(endpoint: EnergyResult) -> dict[str, Any]:
    spectrum = endpoint.spectrum
    if spectrum.kinetic_one is None or spectrum.interaction_one is None:
        raise RuntimeError("endpoint has no selected state for affine diagnostics")
    gradient = endpoint.chiral_gradient + endpoint.chi_gradient
    potential = endpoint.chiral_potential + endpoint.chi_potential
    curvature = 2.0 * NC * spectrum.kinetic_one + 8.0 * gradient
    rows: list[dict[str, float]] = []
    for deformation in AFFINE_SEQUENCE:
        kinetic_factor = (
            2.0 * math.exp(deformation) + math.exp(-2.0 * deformation)
        ) / 3.0
        gradient_factor = (
            2.0 * math.exp(2.0 * deformation) + math.exp(-4.0 * deformation)
        ) / 3.0
        energy = (
            NC * spectrum.kinetic_one * kinetic_factor
            + NC * spectrum.interaction_one
            + gradient * gradient_factor
            + potential
        )
        rows.append(
            {
                "d": deformation,
                "kinetic_factor": kinetic_factor,
                "gradient_factor": gradient_factor,
                "trial_energy_mev": energy,
            }
        )
    baseline = next(row["trial_energy_mev"] for row in rows if row["d"] == 0.0)
    for row in rows:
        row["difference_from_d0_mev"] = row["trial_energy_mev"] - baseline
    return {
        "kinetic_one_quark_mev": spectrum.kinetic_one,
        "interaction_one_quark_mev": spectrum.interaction_one,
        "field_gradient_mev": gradient,
        "field_potential_mev": potential,
        "analytic_second_derivative_mev": curvature,
        "rows": rows,
    }


def formation_diagnostics(endpoint: EnergyResult) -> dict[str, Any]:
    endpoint_x = physical_to_normalized(endpoint.z)
    rows: list[dict[str, Any]] = []
    for start_index, start in enumerate(FORMATION_STARTS, start=1):
        start_z = np.asarray(start, dtype=np.float64)
        start_x = physical_to_normalized(start_z)
        optimized, history = run_powell(
            start_x,
            endpoint.case,
            record_path=True,
        )
        result = energy_result(normalized_to_physical(optimized.x), endpoint.case)
        overlap = state_overlap(endpoint.spectrum, result.spectrum)
        distance = float(np.linalg.norm(np.asarray(optimized.x) - endpoint_x))
        energy_difference = abs(result.total - endpoint.total)
        nonincreasing = all(
            history[index + 1] <= history[index] + 1.0e-5
            for index in range(len(history) - 1)
        )
        in_basin = bool(
            optimized.success
            and not result.penalized
            and energy_difference <= 2.0
            and distance <= 0.05
            and overlap >= 0.98
            and result.spectrum.tail_probability is not None
            and result.spectrum.tail_probability < 1.0e-4
            and nonincreasing
        )
        rows.append(
            {
                "start_index": start_index,
                "start_z": start_z,
                "start_normalized": start_x,
                "optimizer": optimization_record(optimized),
                "accepted_energy_history_mev": history,
                "history_nonincreasing": nonincreasing,
                "result": public_energy(result),
                "endpoint_energy_difference_mev": energy_difference,
                "normalized_endpoint_distance": distance,
                "endpoint_state_overlap": overlap,
                "in_endpoint_basin": in_basin,
            }
        )
    basin_rows = [row for row in rows if row["in_endpoint_basin"]]
    low_seed = any(
        float(row["start_z"][2]) <= 25.0 for row in basin_rows
    )
    high_seed = any(
        float(row["start_z"][2]) >= 340.0 for row in basin_rows
    )
    return {
        "rows": rows,
        "basin_count": len(basin_rows),
        "low_chi_seed_in_basin": low_seed,
        "high_chi_seed_in_basin": high_seed,
    }


def raw_energy_payload(z: np.ndarray, case: Case) -> dict[str, Any]:
    result = energy_result(z, case)
    field_total = (
        result.chiral_gradient
        + result.chiral_potential
        + result.chi_gradient
        + result.chi_potential
    )
    raw_total = (
        None
        if result.spectrum.candidate_energy is None
        else case.nc * result.spectrum.candidate_energy + field_total
    )
    payload = public_energy(result)
    payload["raw_unpenalized_total_mev"] = raw_total
    return payload


def negative_controls(endpoint: EnergyResult) -> dict[str, Any]:
    vacuum_z = endpoint.z.copy()
    vacuum_z[0] = 0.0
    vacuum_z[2] = 0.0
    vacuum_rows: list[dict[str, Any]] = []
    for delta in (8.0, 2.0, 0.5):
        for rmax, n in BOX_SEQUENCE:
            case = Case(n=n, rmax=rmax, delta=delta)
            vacuum_rows.append(
                {
                    "delta_mev": delta,
                    "rmax_fm": rmax,
                    "result": raw_energy_payload(vacuum_z, case),
                }
            )
    constant_case = Case(
        n=endpoint.case.n,
        rmax=endpoint.case.rmax,
        delta=endpoint.case.delta,
        coupling_mode="constant",
        nc=NC,
    )
    constant_result = raw_energy_payload(endpoint.z, constant_case)
    single_colour_case = Case(
        n=endpoint.case.n,
        rmax=endpoint.case.rmax,
        delta=endpoint.case.delta,
        coupling_mode=endpoint.case.coupling_mode,
        nc=1,
    )
    single_colour_result = raw_energy_payload(endpoint.z, single_colour_case)
    return {
        "vacuum_field": vacuum_rows,
        "no_confining_coupling": constant_result,
        "single_colour_fixed_fields": single_colour_result,
        "three_minus_one_colour_level_contribution_mev": (
            None
            if endpoint.spectrum.candidate_energy is None
            else 2.0 * endpoint.spectrum.candidate_energy
        ),
    }


def algebra_controls() -> dict[str, Any]:
    local = GAMMA * M_CHI
    potential_zero = float(chi_potential(0.0))
    derivative_zero = chi_potential_derivative(0.0)
    second_zero = M_CHI**2
    potential_local = float(chi_potential(local))
    derivative_local = chi_potential_derivative(local)
    target_local = (ETA * M_CHI) ** 4
    cubic_factor = 8.0 * ETA**4 / GAMMA**2 - 2.0
    quartic_factor = 1.0 - 6.0 * ETA**4 / GAMMA**2
    return {
        "global_phase_baryon_current_identity": True,
        "u_zero_mev4": potential_zero,
        "u_prime_zero_mev3": derivative_zero,
        "u_second_zero_mev2": second_zero,
        "u_second_zero_target_mev2": M_CHI**2,
        "local_coordinate_mev": local,
        "u_local_mev4": potential_local,
        "u_local_target_mev4": target_local,
        "u_local_relative_error": relative_difference(potential_local, target_local),
        "u_prime_local_mev3": derivative_local,
        "u_prime_local_scaled_abs": abs(derivative_local)
        / max(M_CHI**3, 1.0e-300),
        "cubic_factor": cubic_factor,
        "quartic_factor": quartic_factor,
        "cubic_negative": cubic_factor < 0.0,
        "quartic_positive": quartic_factor > 0.0,
    }


def decision_payload(
    primary_optimization: dict[str, Any],
    endpoint: EnergyResult,
    stationarity: dict[str, Any],
    grid_rows: list[dict[str, Any]],
    box_rows: list[dict[str, Any]],
    regulator_rows: list[dict[str, Any]],
    regulator_extrapolation: dict[str, Any],
    dilation: dict[str, Any],
    affine: dict[str, Any],
    formation: dict[str, Any],
    algebra: dict[str, Any],
) -> dict[str, Any]:
    spectrum = endpoint.spectrum
    endpoint_x = physical_to_normalized(endpoint.z)
    optimizer_pass = bool(
        primary_optimization["differential"].success
        and primary_optimization["polished"].success
    )
    state_pass = bool(
        spectrum.candidate_energy is not None
        and 0.0 < spectrum.candidate_energy < 2500.0
        and spectrum.nodes == 0
        and spectrum.same_sign_gap is not None
        and spectrum.same_sign_gap > 5.0
        and spectrum.tail_probability is not None
        and spectrum.tail_probability < 1.0e-4
        and spectrum.normalization_error is not None
        and spectrum.normalization_error < 1.0e-10
    )
    algebra_pass = bool(
        algebra["global_phase_baryon_current_identity"]
        and algebra["u_zero_mev4"] == 0.0
        and algebra["u_prime_zero_mev3"] == 0.0
        and algebra["u_second_zero_mev2"] == algebra["u_second_zero_target_mev2"]
        and algebra["u_local_relative_error"] < 1.0e-12
        and algebra["u_prime_local_scaled_abs"] < 1.0e-12
        and algebra["cubic_negative"]
        and algebra["quartic_positive"]
        and spectrum.hermiticity_error < 1.0e-10
    )
    non_a_interior = bool(np.all(endpoint_x[1:] > 0.02) and np.all(endpoint_x[1:] < 0.98))
    hessian_minimum = stationarity["projected_hessian_minimum_mev"]
    stationarity_pass = bool(
        optimizer_pass
        and non_a_interior
        and stationarity["free_gradient_max_abs"] < 1.0
        and stationarity["kkt_lower_pass"]
        and stationarity["kkt_upper_pass"]
        and hessian_minimum is not None
        and hessian_minimum > 5.0
        and stationarity["all_stencils_valid"]
        and stationarity["branch_minimum_overlap"] >= 0.98
    )

    grid_metrics = sequence_pair_metrics(grid_rows, -2, -1)
    box_metrics = sequence_pair_metrics(box_rows, -2, -1)
    regulator_metrics = sequence_pair_metrics(regulator_rows, -2, -1)
    sequence_optimizers_pass = all(
        bool(row["optimizer"]["success"])
        for row in grid_rows + box_rows + regulator_rows
    )
    field_tail_pass = bool(
        math.isfinite(endpoint.field_tail_bound)
        and endpoint.field_tail_bound < 1.0e-4
    )
    icb3_pass = bool(
        sequence_optimizers_pass
        and field_tail_pass
        and grid_metrics["energy_relative_difference"] < 0.005
        and grid_metrics["level_relative_difference"] < 0.005
        and grid_metrics["rms_relative_difference"] < 0.01
        and grid_metrics["state_overlap"] > 0.995
        and box_metrics["energy_relative_difference"] < 0.002
        and box_metrics["level_relative_difference"] < 0.002
        and box_metrics["rms_relative_difference"] < 0.005
        and box_metrics["state_overlap"] > 0.995
        and regulator_metrics["energy_relative_difference"] < 0.01
        and regulator_metrics["level_relative_difference"] < 0.01
        and regulator_metrics["rms_relative_difference"] < 0.01
        and regulator_metrics["state_overlap"] > 0.995
        and regulator_extrapolation["quadratic_intercept_finite"]
        and regulator_extrapolation["intercept_relative_difference"] < 0.02
    )

    dilation_by_scale = {
        round(float(row["lambda"]), 8): row for row in dilation["rows"]
    }
    local_dilation_pass = bool(
        dilation_by_scale[0.95]["difference_from_endpoint_mev"] >= 0.05
        and dilation_by_scale[1.05]["difference_from_endpoint_mev"] >= 0.05
    )
    endpoint_dilation_pass = bool(
        dilation_by_scale[0.50]["difference_from_endpoint_mev"] >= 10.0
        and dilation_by_scale[2.00]["difference_from_endpoint_mev"] >= 10.0
    )
    affine_nonzero = [row for row in affine["rows"] if row["d"] != 0.0]
    affine_pass = bool(
        affine["kinetic_one_quark_mev"] > 0.0
        and affine["field_gradient_mev"] > 0.0
        and affine["analytic_second_derivative_mev"] > 10.0
        and all(row["difference_from_d0_mev"] > 0.0 for row in affine_nonzero)
    )
    icb4_pass = bool(
        dilation["virial_relative_residual"] < 0.02
        and local_dilation_pass
        and endpoint_dilation_pass
        and affine_pass
    )
    icb5_supports = bool(
        formation["basin_count"] >= 8
        and formation["low_chi_seed_in_basin"]
        and formation["high_chi_seed_in_basin"]
    )
    gates = {
        "ICB1": "PASS" if algebra_pass else "FAIL",
        "ICB2": "PASS" if state_pass and stationarity_pass else "FAIL",
        "ICB3": "PASS" if icb3_pass else "FAIL",
        "ICB4": "PASS" if icb4_pass else "FAIL",
        "ICB5": "SUPPORTS" if icb5_supports else "CONTRADICTS",
        "ICB6": "FAIL",
    }
    reduced_support = bool(
        gates["ICB1"] == "PASS"
        and gates["ICB2"] == "PASS"
        and gates["ICB3"] == "PASS"
        and gates["ICB4"] == "PASS"
        and gates["ICB5"] == "SUPPORTS"
    )
    return {
        "gates": gates,
        "overall_reduced_verdict": (
            "INTERACTING_REDUCED_FORMATION_SUPPORTS"
            if reduced_support
            else "INTERACTING_REDUCED_FORMATION_CONTRADICTS"
        ),
        "complete_physical_matter_formation": False,
        "criteria": {
            "optimizer_pass": optimizer_pass,
            "state_pass": state_pass,
            "algebra_pass": algebra_pass,
            "non_a_coordinates_interior": non_a_interior,
            "stationarity_pass": stationarity_pass,
            "grid_pair": grid_metrics,
            "box_pair": box_metrics,
            "regulator_pair": regulator_metrics,
            "sequence_optimizers_pass": sequence_optimizers_pass,
            "field_tail_pass": field_tail_pass,
            "regulator_extrapolation_pass": (
                regulator_extrapolation["quadratic_intercept_finite"]
                and regulator_extrapolation["intercept_relative_difference"] < 0.02
            ),
            "virial_pass": dilation["virial_relative_residual"] < 0.02,
            "local_dilation_pass": local_dilation_pass,
            "endpoint_dilation_pass": endpoint_dilation_pass,
            "affine_pass": affine_pass,
            "formation_basin_pass": icb5_supports,
        },
    }


def regulator_fit(rows: list[dict[str, Any]]) -> dict[str, Any]:
    final = rows[-3:]
    deltas = np.asarray(
        [float(row["result"]["case"]["delta_mev"]) for row in final],
        dtype=np.float64,
    )
    energies = np.asarray(
        [float(row["result"]["energies_mev"]["total"]) for row in final],
        dtype=np.float64,
    )
    quadratic_coefficients = np.polyfit(deltas**2, energies, 1)
    linear_coefficients = np.polyfit(deltas, energies, 1)
    quadratic_intercept = float(quadratic_coefficients[1])
    linear_intercept = float(linear_coefficients[1])
    return {
        "deltas_mev": deltas,
        "energies_mev": energies,
        "quadratic_in_delta_coefficients": quadratic_coefficients,
        "linear_in_delta_coefficients": linear_coefficients,
        "quadratic_intercept_mev": quadratic_intercept,
        "linear_intercept_mev": linear_intercept,
        "quadratic_intercept_finite": math.isfinite(quadratic_intercept),
        "intercept_relative_difference": relative_difference(
            quadratic_intercept, linear_intercept
        ),
    }


def save_endpoint_arrays(path: Path, endpoint: EnergyResult) -> None:
    spectrum = endpoint.spectrum
    if (
        spectrum.vector is None
        or spectrum.upper is None
        or spectrum.lower is None
    ):
        raise RuntimeError("cannot save endpoint arrays without a selected state")
    a, chiral_radius, chi_amplitude, chi_radius = endpoint.z
    scalar, pion, scalar_prime, pion_prime = chiral_profile(
        float(a), float(chiral_radius), spectrum.radial
    )
    chi, chi_prime = chi_profile(
        float(chi_amplitude), float(chi_radius), spectrum.radial
    )
    np.savez_compressed(
        path,
        radial_fm=spectrum.radial,
        eigenvalues_mev=spectrum.eigenvalues,
        weighted_eigenvector=spectrum.vector,
        upper_radial=spectrum.upper,
        lower_radial=spectrum.lower,
        scalar_over_fpi=scalar,
        pion_over_fpi=pion,
        scalar_prime_per_fm=scalar_prime,
        pion_prime_per_fm=pion_prime,
        chi_mev=chi,
        chi_prime_mev_per_fm=chi_prime,
        z=endpoint.z,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="fresh output directory",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sources = output / "sources"
    sources.mkdir()
    shutil.copy2(PROTOCOL, sources / PROTOCOL.name)
    shutil.copy2(SELF, sources / SELF.name)

    started = time.time()
    primary_case = Case()
    print("Running primary differential-evolution and Powell solve", flush=True)
    primary_optimization = optimize_primary(primary_case)
    endpoint: EnergyResult = primary_optimization["endpoint"]
    primary_x = physical_to_normalized(endpoint.z)
    if endpoint.spectrum.candidate_energy is None:
        raise RuntimeError("primary optimizer returned no positive nodeless state")

    print("Reconstructing stationarity and convergence sequences", flush=True)
    stationarity = finite_difference_diagnostics(endpoint)
    grid_rows = sequence_with_overlaps(
        [Case(n=n) for n in GRID_SEQUENCE],
        primary_x,
        endpoint,
    )
    box_rows = sequence_with_overlaps(
        [Case(n=n, rmax=rmax) for rmax, n in BOX_SEQUENCE],
        primary_x,
        endpoint,
    )
    regulator_rows = sequence_with_overlaps(
        [Case(delta=delta) for delta in REGULATOR_SEQUENCE],
        primary_x,
        endpoint,
    )
    regulator_extrapolation = regulator_fit(regulator_rows)

    print("Evaluating stability, formation basin and controls", flush=True)
    dilation = dilation_diagnostics(endpoint)
    affine = affine_diagnostics(endpoint)
    formation = formation_diagnostics(endpoint)
    controls = negative_controls(endpoint)
    algebra = algebra_controls()
    decisions = decision_payload(
        primary_optimization,
        endpoint,
        stationarity,
        grid_rows,
        box_rows,
        regulator_rows,
        regulator_extrapolation,
        dilation,
        affine,
        formation,
        algebra,
    )

    arrays_path = output / "endpoint_arrays.npz"
    save_endpoint_arrays(arrays_path, endpoint)
    source_manifest = {
        "protocol": source_record(PROTOCOL),
        "primary": source_record(SELF),
        "snapshots": {
            PROTOCOL.name: source_record(sources / PROTOCOL.name),
            SELF.name: source_record(sources / SELF.name),
        },
    }
    receipt = {
        "schema": SCHEMA,
        "protocol_status": "Preregistered—September 2026",
        "started_unix": started,
        "finished_unix": time.time(),
        "source_manifest": source_manifest,
        "constants": {
            "hbar_c_mev_fm": HBARC,
            "n_c": NC,
            "f_pi_mev": F_PI,
            "m_pi_mev": M_PI,
            "m_sigma_mev": M_SIGMA,
            "g_mev": G_COUPLING,
            "m_chi_mev": M_CHI,
            "gamma": GAMMA,
            "eta": ETA,
            "chiral_lambda": CHIRAL_LAMBDA,
        },
        "primary_optimizer": {
            "differential_evolution": optimization_record(
                primary_optimization["differential"]
            ),
            "powell": optimization_record(primary_optimization["polished"]),
            "powell_energy_history_mev": primary_optimization["history"],
            "elapsed_seconds": primary_optimization["elapsed_seconds"],
        },
        "primary_endpoint": public_energy(endpoint),
        "algebra_controls": algebra,
        "stationarity": stationarity,
        "grid_sequence": grid_rows,
        "box_sequence": box_rows,
        "regulator_sequence": regulator_rows,
        "regulator_extrapolation": regulator_extrapolation,
        "dilation": dilation,
        "affine_shape": affine,
        "formation": formation,
        "negative_controls": controls,
        "decisions": decisions,
        "execution": {
            "energy_evaluations": _EVALUATIONS,
            "wall_seconds": time.time() - started,
        },
        "artifacts": {
            "endpoint_arrays": {
                "path": arrays_path.relative_to(ROOT).as_posix(),
                "sha256": sha256_file(arrays_path),
                "bytes": arrays_path.stat().st_size,
            }
        },
    }
    results_path = output / "results.json"
    write_json(results_path, receipt)
    print(
        " ".join(
            [
                f"ICB1={decisions['gates']['ICB1']}",
                f"ICB2={decisions['gates']['ICB2']}",
                f"ICB3={decisions['gates']['ICB3']}",
                f"ICB4={decisions['gates']['ICB4']}",
                f"ICB5={decisions['gates']['ICB5']}",
                f"ICB6={decisions['gates']['ICB6']}",
            ]
        )
    )
    print(decisions["overall_reduced_verdict"])
    print("complete_physical_matter_formation=false")
    print(f"wrote {results_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
