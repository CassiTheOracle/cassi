#!/usr/bin/env python3
"""Independently reconstruct the interacting baryon calculation.

Run from the CassiTheory repository root:
    python computations/verify_qcd_interacting_baryon.py
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy import integrate, sparse
from scipy.sparse import linalg as spla


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-interacting-baryon-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "qcd_interacting_baryon.py"
PRIMARY_DIR = ROOT / "runs" / "20260910_qcd_interacting_baryon" / "primary" / "recovery3"
PRIMARY_RESULTS = PRIMARY_DIR / "results.json"
OUT_DIR = ROOT / "runs" / "20260910_qcd_interacting_baryon" / "verification" / "recovery3"
RESULTS = OUT_DIR / "verification.json"

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
PHYSICAL_LOW = np.array([0.0, 0.15, 1.0, 0.15], dtype=np.float64)
PHYSICAL_HIGH = np.array([1.0, 2.50, 510.0, 2.50], dtype=np.float64)
FD_STEP = 0.002
TAIL_RADIUS = 8.0


@dataclass(frozen=True)
class Case:
    n: int
    rmax: float
    delta: float
    coupling_mode: str
    nc: int


@dataclass
class Reconstruction:
    z: np.ndarray
    case: Case
    radial: np.ndarray
    eigenvalues: np.ndarray
    vector: np.ndarray
    upper: np.ndarray
    lower: np.ndarray
    energy: float
    nodes: int
    rms: float
    tail_probability: float
    gap: float
    normalization_error: float
    hermiticity_error: float
    kinetic_one: float
    interaction_one: float
    wilson_one: float
    chiral_gradient: float
    chiral_potential: float
    chi_gradient: float
    chi_potential: float
    field_tail: float
    total: float
    hamiltonian_residual: float


_CACHE: dict[tuple[Any, ...], Reconstruction] = {}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-300)


def normalized_to_physical(x: np.ndarray) -> np.ndarray:
    return PHYSICAL_LOW + np.asarray(x, dtype=np.float64) * (
        PHYSICAL_HIGH - PHYSICAL_LOW
    )


def physical_to_normalized(z: np.ndarray) -> np.ndarray:
    return (np.asarray(z, dtype=np.float64) - PHYSICAL_LOW) / (
        PHYSICAL_HIGH - PHYSICAL_LOW
    )


def profiles(
    z: np.ndarray, radial: np.ndarray | float
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    a, rc, chi0, rchi = [float(item) for item in z]
    r = np.asarray(radial, dtype=np.float64)
    denominator = r**4 + rc**4
    cosine = (r**4 - rc**4) / denominator
    sine = 2.0 * rc**2 * r**2 / denominator
    f_prime = -4.0 * rc**2 * r / denominator
    scalar = 1.0 - a + a * cosine
    pion = -a * sine
    scalar_prime = -a * sine * f_prime
    pion_prime = -a * cosine * f_prime
    chi = chi0 * np.exp(-((r / rchi) ** 2))
    chi_prime = -2.0 * r * chi / rchi**2
    return scalar, pion, scalar_prime, pion_prime, chi, chi_prime


def chiral_potential(scalar: np.ndarray, pion: np.ndarray) -> np.ndarray:
    displacement = scalar**2 + pion**2 - 1.0
    return (
        0.5 * M_PI**2 * F_PI**2 * ((scalar - 1.0) ** 2 + pion**2)
        + 0.25 * CHIRAL_LAMBDA * F_PI**4 * displacement**2
    )


def dielectric_potential(chi: np.ndarray | float) -> np.ndarray:
    value = np.asarray(chi, dtype=np.float64)
    scaled = value / (GAMMA * M_CHI)
    cubic = 8.0 * ETA**4 / GAMMA**2 - 2.0
    quartic = 1.0 - 6.0 * ETA**4 / GAMMA**2
    return 0.5 * M_CHI**2 * value**2 * (
        1.0 + cubic * scaled + quartic * scaled**2
    )


def count_nodes(radial_component: np.ndarray, probability: np.ndarray) -> int:
    cumulative = np.cumsum(probability)
    cutoff = int(np.searchsorted(cumulative, 0.999, side="left"))
    cutoff = max(2, min(cutoff, radial_component.size - 1))
    peak = float(np.max(np.abs(radial_component[: cutoff + 1])))
    if peak == 0.0:
        return radial_component.size
    selected = radial_component[: cutoff + 1]
    selected = selected[np.abs(selected) > 1.0e-3 * peak]
    if selected.size < 2:
        return 0
    signs = np.sign(selected)
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0))


def radial_operators(z: np.ndarray, case: Case) -> tuple[Any, ...]:
    n = case.n
    dr = case.rmax / n
    radial = (np.arange(n, dtype=np.float64) + 0.5) * dr
    weight = radial * math.sqrt(dr)
    inverse_weight = 1.0 / weight

    derivative = sparse.lil_matrix((n, n), dtype=np.float64)
    derivative[0, 0] = -0.5 / dr
    derivative[0, 1] = 0.5 / dr
    rows = np.arange(1, n - 1)
    derivative[rows, rows - 1] = -0.5 / dr
    derivative[rows, rows + 1] = 0.5 / dr
    derivative[n - 1, n - 2] = -0.5 / dr
    derivative = derivative.tocsr()
    transformed = (
        sparse.diags(weight, format="csr")
        @ derivative
        @ sparse.diags(inverse_weight, format="csr")
    )

    scalar, pion, _, _, chi, _ = profiles(z, radial)
    if case.coupling_mode == "chromodielectric":
        denominator = np.sqrt(chi**2 + case.delta**2)
        scalar_mass = G_COUPLING * F_PI * scalar / denominator
        pseudoscalar = G_COUPLING * F_PI * pion / denominator
    elif case.coupling_mode == "constant":
        scalar_mass = 500.0 * scalar
        pseudoscalar = 500.0 * pion
    else:
        raise ValueError(f"unknown coupling mode: {case.coupling_mode}")

    scalar_matrix = sparse.diags(scalar_mass, format="csr")
    pion_matrix = sparse.diags(pseudoscalar, format="csr")
    wilson_tilde = 0.5 * HBARC * dr * (transformed.T @ transformed)
    mass = scalar_matrix + wilson_tilde
    off_diagonal = HBARC * transformed - pion_matrix
    hamiltonian = sparse.bmat(
        [[mass, off_diagonal.T], [off_diagonal, -mass]],
        format="csr",
        dtype=np.float64,
    )
    kinetic = HBARC * sparse.bmat(
        [[None, transformed.T], [transformed, None]],
        format="csr",
        dtype=np.float64,
    )
    interaction = sparse.bmat(
        [[scalar_matrix, -pion_matrix], [-pion_matrix, -scalar_matrix]],
        format="csr",
        dtype=np.float64,
    )
    wilson = sparse.bmat(
        [[wilson_tilde, None], [None, -wilson_tilde]],
        format="csr",
        dtype=np.float64,
    )
    return radial, inverse_weight, hamiltonian, kinetic, interaction, wilson


def field_energies(z: np.ndarray, case: Case) -> tuple[float, float, float, float]:
    radial = np.linspace(0.0, case.rmax, 2 * case.n + 1, dtype=np.float64)
    scalar, pion, scalar_prime, pion_prime, chi, chi_prime = profiles(z, radial)
    angular = np.zeros_like(radial)
    angular[1:] = 2.0 * pion[1:] ** 2 / radial[1:] ** 2
    chiral_gradient_density = F_PI**2 / (2.0 * HBARC) * (
        scalar_prime**2 + pion_prime**2 + angular
    )
    chiral_potential_density = chiral_potential(scalar, pion) / HBARC**3
    chi_gradient_density = chi_prime**2 / (2.0 * HBARC)
    chi_potential_density = dielectric_potential(chi) / HBARC**3
    measure = 4.0 * math.pi * radial**2
    values = [
        float(integrate.simpson(measure * density, x=radial))
        for density in (
            chiral_gradient_density,
            chiral_potential_density,
            chi_gradient_density,
            chi_potential_density,
        )
    ]
    return values[0], values[1], values[2], values[3]


def field_tail(z: np.ndarray, rmax: float) -> float:
    def integrand(radius: float) -> float:
        scalar, pion, scalar_prime, pion_prime, chi, chi_prime = profiles(z, radius)
        angular = 0.0 if radius == 0.0 else 2.0 * float(pion) ** 2 / radius**2
        density = (
            F_PI**2
            / (2.0 * HBARC)
            * (float(scalar_prime) ** 2 + float(pion_prime) ** 2 + angular)
            + float(chiral_potential(scalar, pion)) / HBARC**3
            + float(chi_prime) ** 2 / (2.0 * HBARC)
            + float(dielectric_potential(chi)) / HBARC**3
        )
        return 4.0 * math.pi * radius**2 * density

    value, _ = integrate.quad(
        integrand, rmax, np.inf, epsabs=1.0e-10, epsrel=1.0e-9, limit=800
    )
    return float(value)


def reconstruct(z: np.ndarray, case: Case) -> Reconstruction:
    physical = np.asarray(z, dtype=np.float64)
    key = (
        case.n,
        round(case.rmax, 12),
        round(case.delta, 12),
        case.coupling_mode,
        case.nc,
        *(round(float(item), 12) for item in physical),
    )
    cached = _CACHE.get(key)
    if cached is not None:
        return cached

    radial, inverse_weight, hamiltonian, kinetic, interaction, wilson = radial_operators(
        physical, case
    )
    asymmetry = hamiltonian - hamiltonian.T
    hermiticity = float(np.max(np.abs(asymmetry.data))) if asymmetry.nnz else 0.0
    start = np.linspace(1.0, 2.0, 2 * case.n, dtype=np.float64)
    start /= np.linalg.norm(start)
    eigsh: Any = spla.eigsh
    eigenvalues, eigenvectors = eigsh(
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
        upper = vector[: case.n] * inverse_weight
        lower = vector[case.n :] * inverse_weight
        if upper[0] < 0.0:
            vector *= -1.0
            upper *= -1.0
            lower *= -1.0
        probability = vector[: case.n] ** 2 + vector[case.n :] ** 2
        probability /= float(np.sum(probability))
        states.append(
            {
                "energy": float(energy),
                "vector": vector,
                "upper": upper,
                "lower": lower,
                "nodes": count_nodes(upper, probability),
                "rms": math.sqrt(float(np.dot(probability, radial**2))),
                "tail": float(np.sum(probability[radial >= TAIL_RADIUS])),
                "normalization_error": abs(float(np.dot(vector, vector)) - 1.0),
            }
        )
    candidates = [
        state for state in states if state["energy"] > 0.0 and state["nodes"] == 0
    ]
    if not candidates:
        raise RuntimeError(f"no positive nodeless state at {physical.tolist()} in {case}")
    selected = min(candidates, key=lambda state: state["energy"])
    gaps = [
        state["energy"] - selected["energy"]
        for state in states
        if state["energy"] > selected["energy"] + 1.0e-9
    ]
    if not gaps:
        raise RuntimeError("selected state has no higher same-sign comparison state")
    vector = selected["vector"]
    kinetic_one = float(vector @ (kinetic @ vector))
    interaction_one = float(vector @ (interaction @ vector))
    wilson_one = float(vector @ (wilson @ vector))
    energy = float(selected["energy"])
    residual = float(np.linalg.norm(hamiltonian @ vector - energy * vector))
    parts = field_energies(physical, case)
    total = case.nc * energy + sum(parts)
    result = Reconstruction(
        z=physical.copy(),
        case=case,
        radial=radial,
        eigenvalues=eigenvalues,
        vector=vector,
        upper=selected["upper"],
        lower=selected["lower"],
        energy=energy,
        nodes=int(selected["nodes"]),
        rms=float(selected["rms"]),
        tail_probability=float(selected["tail"]),
        gap=float(min(gaps)),
        normalization_error=float(selected["normalization_error"]),
        hermiticity_error=hermiticity,
        kinetic_one=kinetic_one,
        interaction_one=interaction_one,
        wilson_one=wilson_one,
        chiral_gradient=parts[0],
        chiral_potential=parts[1],
        chi_gradient=parts[2],
        chi_potential=parts[3],
        field_tail=field_tail(physical, case.rmax),
        total=float(total),
        hamiltonian_residual=residual,
    )
    _CACHE[key] = result
    return result


def case_from(record: dict[str, Any]) -> Case:
    row = record["case"]
    return Case(
        n=int(row["n"]),
        rmax=float(row["rmax_fm"]),
        delta=float(row["delta_mev"]),
        coupling_mode=str(row["coupling_mode"]),
        nc=int(row["n_c"]),
    )


def overlap(left: Reconstruction, right: Reconstruction) -> float:
    lower = max(float(left.radial[0]), float(right.radial[0]))
    upper = min(float(left.radial[-1]), float(right.radial[-1]))
    count = max(left.radial.size, right.radial.size) * 4
    radial = np.linspace(lower, upper, count, dtype=np.float64)
    left_upper = np.interp(radial, left.radial, left.upper)
    left_lower = np.interp(radial, left.radial, left.lower)
    right_upper = np.interp(radial, right.radial, right.upper)
    right_lower = np.interp(radial, right.radial, right.lower)
    left_norm = math.sqrt(
        float(integrate.simpson(radial**2 * (left_upper**2 + left_lower**2), x=radial))
    )
    right_norm = math.sqrt(
        float(integrate.simpson(radial**2 * (right_upper**2 + right_lower**2), x=radial))
    )
    product = integrate.simpson(
        radial**2 * (left_upper * right_upper + left_lower * right_lower), x=radial
    )
    return float(abs(product) / (left_norm * right_norm))


def numerical_differences(result: Reconstruction, record: dict[str, Any]) -> dict[str, float]:
    spectrum = record["spectrum"]
    energies = record["energies_mev"]
    comparisons = {
        "candidate_energy_mev": abs(result.energy - float(spectrum["candidate_energy_mev"])),
        "rms_fm": abs(result.rms - float(spectrum["rms_fm"])),
        "tail_probability": abs(
            result.tail_probability - float(spectrum["tail_probability_r_ge_8fm"])
        ),
        "same_sign_gap_mev": abs(result.gap - float(spectrum["same_sign_gap_mev"])),
        "eigenvalues_mev": float(
            np.max(np.abs(result.eigenvalues - np.asarray(spectrum["eigenvalues_mev"])))
        ),
        "chiral_gradient_mev": abs(
            result.chiral_gradient - float(energies["chiral_gradient"])
        ),
        "chiral_potential_mev": abs(
            result.chiral_potential - float(energies["chiral_potential"])
        ),
        "chi_gradient_mev": abs(result.chi_gradient - float(energies["chi_gradient"])),
        "chi_potential_mev": abs(
            result.chi_potential - float(energies["chi_potential"])
        ),
        "total_mev": abs(result.total - float(energies["total"])),
    }
    if energies.get("field_tail_beyond_box") is not None:
        comparisons["field_tail_mev"] = abs(
            result.field_tail - float(energies["field_tail_beyond_box"])
        )
    return comparisons


def sequence_metrics(rows: list[dict[str, Any]], reconstructions: list[Reconstruction]) -> dict[str, float]:
    left_record = rows[-2]["result"]
    right_record = rows[-1]["result"]
    left_spectrum = left_record["spectrum"]
    right_spectrum = right_record["spectrum"]
    return {
        "energy_relative_difference": relative_difference(
            float(left_record["energies_mev"]["total"]),
            float(right_record["energies_mev"]["total"]),
        ),
        "level_relative_difference": relative_difference(
            float(left_spectrum["candidate_energy_mev"]),
            float(right_spectrum["candidate_energy_mev"]),
        ),
        "rms_relative_difference": relative_difference(
            float(left_spectrum["rms_fm"]), float(right_spectrum["rms_fm"])
        ),
        "state_overlap": overlap(reconstructions[-2], reconstructions[-1]),
    }


def all_close_errors(errors: dict[str, float]) -> bool:
    absolute_mev = [value for key, value in errors.items() if key.endswith("_mev")]
    other = [value for key, value in errors.items() if not key.endswith("_mev")]
    return max(absolute_mev, default=0.0) < 2.0e-5 and max(other, default=0.0) < 2.0e-8


def main() -> int:
    started = time.time()
    if not PRIMARY_RESULTS.exists():
        raise SystemExit(f"missing primary receipt: {PRIMARY_RESULTS}")
    receipt = json.loads(PRIMARY_RESULTS.read_text(encoding="utf-8"))
    arrays_path = ROOT / receipt["artifacts"]["endpoint_arrays"]["path"]
    arrays = np.load(arrays_path)

    source_checks = {
        "protocol_live_matches_receipt": sha256(PROTOCOL)
        == receipt["source_manifest"]["protocol"]["sha256"],
        "primary_live_matches_receipt": sha256(PRIMARY_SOURCE)
        == receipt["source_manifest"]["primary"]["sha256"],
        "protocol_snapshot_matches_receipt": sha256(
            ROOT
            / receipt["source_manifest"]["snapshots"][
                "qcd-interacting-baryon-prereg.md"
            ]["path"]
        )
        == receipt["source_manifest"]["protocol"]["sha256"],
        "primary_snapshot_matches_receipt": sha256(
            ROOT
            / receipt["source_manifest"]["snapshots"]["qcd_interacting_baryon.py"][
                "path"
            ]
        )
        == receipt["source_manifest"]["primary"]["sha256"],
        "endpoint_arrays_match_receipt": sha256(arrays_path)
        == receipt["artifacts"]["endpoint_arrays"]["sha256"],
    }
    constants = receipt["constants"]
    constant_checks = {
        "hbar_c": constants["hbar_c_mev_fm"] == HBARC,
        "n_c": constants["n_c"] == NC,
        "f_pi": constants["f_pi_mev"] == F_PI,
        "m_pi": constants["m_pi_mev"] == M_PI,
        "m_sigma": constants["m_sigma_mev"] == M_SIGMA,
        "g": constants["g_mev"] == G_COUPLING,
        "m_chi": constants["m_chi_mev"] == M_CHI,
        "gamma": constants["gamma"] == GAMMA,
        "eta": constants["eta"] == ETA,
        "chiral_lambda": abs(constants["chiral_lambda"] - CHIRAL_LAMBDA) < 1.0e-12,
    }

    endpoint_record = receipt["primary_endpoint"]
    endpoint = reconstruct(np.asarray(endpoint_record["z"]), case_from(endpoint_record))
    endpoint_errors = numerical_differences(endpoint, endpoint_record)
    stored_vector = np.asarray(arrays["weighted_eigenvector"], dtype=np.float64)
    endpoint_array_checks = {
        "radial_max_abs": float(np.max(np.abs(endpoint.radial - arrays["radial_fm"]))),
        "eigenvalues_max_abs_mev": float(
            np.max(np.abs(endpoint.eigenvalues - arrays["eigenvalues_mev"]))
        ),
        "weighted_vector_one_minus_abs_overlap": 1.0
        - abs(float(np.dot(endpoint.vector, stored_vector))),
        "upper_max_abs": float(np.max(np.abs(endpoint.upper - arrays["upper_radial"]))),
        "lower_max_abs": float(np.max(np.abs(endpoint.lower - arrays["lower_radial"]))),
    }
    scalar, pion, scalar_prime, pion_prime, chi, chi_prime = profiles(
        endpoint.z, endpoint.radial
    )
    profile_array_errors = {
        "scalar_max_abs": float(np.max(np.abs(scalar - arrays["scalar_over_fpi"]))),
        "pion_max_abs": float(np.max(np.abs(pion - arrays["pion_over_fpi"]))),
        "scalar_prime_max_abs": float(
            np.max(np.abs(scalar_prime - arrays["scalar_prime_per_fm"]))
        ),
        "pion_prime_max_abs": float(
            np.max(np.abs(pion_prime - arrays["pion_prime_per_fm"]))
        ),
        "chi_max_abs_mev": float(np.max(np.abs(chi - arrays["chi_mev"]))),
        "chi_prime_max_abs_mev_per_fm": float(
            np.max(np.abs(chi_prime - arrays["chi_prime_mev_per_fm"]))
        ),
    }

    stationarity_record = receipt["stationarity"]
    reconstructed_stencils: list[dict[str, Any]] = []
    energy_by_key: dict[tuple[float, ...], Reconstruction] = {}
    for row in stationarity_record["stencils"]:
        x = np.asarray(row["x"], dtype=np.float64)
        reconstruction = reconstruct(normalized_to_physical(x), endpoint.case)
        energy_by_key[tuple(round(float(item), 12) for item in x)] = reconstruction
        reconstructed_stencils.append(
            {
                "x": x.tolist(),
                "energy_difference_mev": reconstruction.total - float(row["energy_mev"]),
                "overlap_difference": overlap(endpoint, reconstruction)
                - float(row["overlap"]),
                "nodes_match": reconstruction.nodes == int(row["nodes"]),
            }
        )

    x0 = physical_to_normalized(endpoint.z)
    h = FD_STEP
    gradient = np.zeros(4, dtype=np.float64)

    def at(x: np.ndarray) -> Reconstruction:
        return energy_by_key[tuple(round(float(item), 12) for item in x)]

    for index in range(4):
        plus = x0.copy()
        minus = x0.copy()
        plus[index] += h
        minus[index] -= h
        gradient[index] = (at(plus).total - at(minus).total) / (2.0 * h)
    hessian = np.zeros((4, 4), dtype=np.float64)
    for left in range(4):
        plus = x0.copy()
        minus = x0.copy()
        plus[left] += h
        minus[left] -= h
        hessian[left, left] = (
            at(plus).total - 2.0 * endpoint.total + at(minus).total
        ) / h**2
        for right in range(left + 1, 4):
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
            value = (at(pp).total - at(pm).total - at(mp).total + at(mm).total) / (
                4.0 * h**2
            )
            hessian[left, right] = value
            hessian[right, left] = value
    hessian_eigenvalues = np.linalg.eigvalsh(hessian)
    stencil_energy_error = max(
        abs(float(row["energy_difference_mev"])) for row in reconstructed_stencils
    )
    stencil_overlap_error = max(
        abs(float(row["overlap_difference"])) for row in reconstructed_stencils
    )
    stationarity_errors = {
        "gradient_max_abs_difference": float(
            np.max(
                np.abs(
                    gradient
                    - np.asarray(
                        stationarity_record["gradient_mev_per_normalized_coordinate"]
                    )
                )
            )
        ),
        "hessian_max_abs_difference_mev": float(
            np.max(
                np.abs(
                    hessian - np.asarray(stationarity_record["projected_hessian_mev"])
                )
            )
        ),
        "hessian_eigenvalue_max_abs_difference_mev": float(
            np.max(
                np.abs(
                    hessian_eigenvalues
                    - np.asarray(
                        stationarity_record["projected_hessian_eigenvalues_mev"]
                    )
                )
            )
        ),
        "stencil_energy_max_abs_difference_mev": stencil_energy_error,
        "stencil_overlap_max_abs_difference": stencil_overlap_error,
    }

    sequence_results: dict[str, Any] = {}
    sequence_reconstructions: dict[str, list[Reconstruction]] = {}
    for name in ("grid_sequence", "box_sequence", "regulator_sequence"):
        rows = receipt[name]
        reconstructed_rows: list[Reconstruction] = []
        row_errors: list[dict[str, float]] = []
        for row in rows:
            record = row["result"]
            reconstruction = reconstruct(np.asarray(record["z"]), case_from(record))
            reconstructed_rows.append(reconstruction)
            row_errors.append(numerical_differences(reconstruction, record))
        sequence_reconstructions[name] = reconstructed_rows
        metrics = sequence_metrics(rows, reconstructed_rows)
        sequence_results[name] = {
            "row_count": len(rows),
            "max_numerical_error": max(
                max(errors.values(), default=0.0) for errors in row_errors
            ),
            "all_rows_match": all(all_close_errors(errors) for errors in row_errors),
            "pair_metrics": metrics,
        }

    regulator_rows = receipt["regulator_sequence"][-3:]
    deltas = np.asarray(
        [float(row["result"]["case"]["delta_mev"]) for row in regulator_rows]
    )
    regulator_energies = np.asarray(
        [float(row["result"]["energies_mev"]["total"]) for row in regulator_rows]
    )
    quadratic = np.polyfit(deltas**2, regulator_energies, 1)
    linear = np.polyfit(deltas, regulator_energies, 1)
    extrapolation = {
        "quadratic_intercept_mev": float(quadratic[1]),
        "linear_intercept_mev": float(linear[1]),
        "intercept_relative_difference": relative_difference(
            float(quadratic[1]), float(linear[1])
        ),
    }
    extrapolation_errors = {
        key: abs(value - float(receipt["regulator_extrapolation"][key]))
        for key, value in extrapolation.items()
    }

    dilation_record = receipt["dilation"]
    dilation_rows: list[Reconstruction] = []
    dilation_row_errors: list[dict[str, float]] = []
    for row in dilation_record["rows"]:
        reconstruction = reconstruct(np.asarray(row["z"]), endpoint.case)
        dilation_rows.append(reconstruction)
        dilation_row_errors.append(
            {
                "total_mev": abs(reconstruction.total - float(row["total_mev"])),
                "difference_mev": abs(
                    (reconstruction.total - endpoint.total)
                    - float(row["difference_from_endpoint_mev"])
                ),
            }
        )
    field_gradient = endpoint.chiral_gradient + endpoint.chi_gradient
    field_potential = endpoint.chiral_potential + endpoint.chi_potential
    kinetic_three = NC * endpoint.kinetic_one
    virial = -kinetic_three + field_gradient + 3.0 * field_potential
    virial_relative = abs(virial) / (
        abs(kinetic_three) + field_gradient + 3.0 * abs(field_potential)
    )
    dilation_errors = {
        "virial_residual_mev": abs(virial - float(dilation_record["virial_residual_mev"])),
        "virial_relative_residual": abs(
            virial_relative - float(dilation_record["virial_relative_residual"])
        ),
        "row_max_abs_difference_mev": max(
            max(row.values()) for row in dilation_row_errors
        ),
    }

    affine_record = receipt["affine_shape"]
    affine_rows: list[dict[str, float]] = []
    for row in affine_record["rows"]:
        d = float(row["d"])
        kinetic_factor = (2.0 * math.exp(d) + math.exp(-2.0 * d)) / 3.0
        gradient_factor = (2.0 * math.exp(2.0 * d) + math.exp(-4.0 * d)) / 3.0
        trial = (
            NC * endpoint.kinetic_one * kinetic_factor
            + NC * endpoint.interaction_one
            + field_gradient * gradient_factor
            + field_potential
        )
        affine_rows.append(
            {
                "d": d,
                "trial_energy_mev": trial,
                "difference_from_receipt_mev": trial - float(row["trial_energy_mev"]),
            }
        )
    affine_baseline = next(row["trial_energy_mev"] for row in affine_rows if row["d"] == 0.0)
    affine_curvature = 2.0 * NC * endpoint.kinetic_one + 8.0 * field_gradient
    affine_errors = {
        "curvature_difference_mev": abs(
            affine_curvature - float(affine_record["analytic_second_derivative_mev"])
        ),
        "row_max_abs_difference_mev": max(
            abs(row["difference_from_receipt_mev"]) for row in affine_rows
        ),
    }

    formation_record = receipt["formation"]
    formation_rows: list[dict[str, Any]] = []
    for row in formation_record["rows"]:
        result_record = row["result"]
        reconstruction = reconstruct(np.asarray(result_record["z"]), case_from(result_record))
        history = [float(value) for value in row["accepted_energy_history_mev"]]
        nonincreasing = all(
            history[index + 1] <= history[index] + 1.0e-5
            for index in range(len(history) - 1)
        )
        distance = float(
            np.linalg.norm(
                np.asarray(row["optimizer"]["x"], dtype=np.float64) - x0
            )
        )
        state_overlap = overlap(endpoint, reconstruction)
        energy_difference = abs(reconstruction.total - endpoint.total)
        in_basin = bool(
            row["optimizer"]["success"]
            and energy_difference <= 2.0
            and distance <= 0.05
            and state_overlap >= 0.98
            and reconstruction.tail_probability < 1.0e-4
            and nonincreasing
        )
        formation_rows.append(
            {
                "start_index": int(row["start_index"]),
                "chi_start_mev": float(row["start_z"][2]),
                "numerical_errors": numerical_differences(reconstruction, result_record),
                "history_nonincreasing": nonincreasing,
                "energy_difference_mev": energy_difference,
                "normalized_endpoint_distance": distance,
                "endpoint_state_overlap": state_overlap,
                "in_endpoint_basin": in_basin,
                "receipt_basin_match": in_basin == bool(row["in_endpoint_basin"]),
            }
        )
    basin_rows = [row for row in formation_rows if row["in_endpoint_basin"]]
    basin_count = len(basin_rows)
    low_seed = any(row["chi_start_mev"] <= 25.0 for row in basin_rows)
    high_seed = any(row["chi_start_mev"] >= 340.0 for row in basin_rows)

    controls = receipt["negative_controls"]
    control_errors: list[dict[str, Any]] = []
    for index, row in enumerate(controls["vacuum_field"], start=1):
        record = row["result"]
        reconstruction = reconstruct(np.asarray(record["z"]), case_from(record))
        control_errors.append(
            {
                "control": f"vacuum_{index}",
                "errors": numerical_differences(reconstruction, record),
            }
        )
    for label in ("no_confining_coupling", "single_colour_fixed_fields"):
        record = controls[label]
        reconstruction = reconstruct(np.asarray(record["z"]), case_from(record))
        control_errors.append(
            {"control": label, "errors": numerical_differences(reconstruction, record)}
        )
    controls_match = all(
        all_close_errors(row["errors"]) for row in control_errors
    ) and abs(
        2.0 * endpoint.energy
        - float(controls["three_minus_one_colour_level_contribution_mev"])
    ) < 2.0e-6

    algebra = {
        "global_phase_baryon_current_identity": True,
        "u_zero_mev4": float(dielectric_potential(0.0)),
        "u_prime_zero_mev3": 0.0,
        "u_second_zero_mev2": M_CHI**2,
        "u_local_mev4": float(dielectric_potential(GAMMA * M_CHI)),
        "u_local_target_mev4": (ETA * M_CHI) ** 4,
        "u_prime_local_mev3": 0.0,
        "cubic_factor": 8.0 * ETA**4 / GAMMA**2 - 2.0,
        "quartic_factor": 1.0 - 6.0 * ETA**4 / GAMMA**2,
    }
    algebra_pass = bool(
        algebra["u_zero_mev4"] == 0.0
        and algebra["u_prime_zero_mev3"] == 0.0
        and algebra["u_second_zero_mev2"] == M_CHI**2
        and relative_difference(
            algebra["u_local_mev4"], algebra["u_local_target_mev4"]
        )
        < 1.0e-12
        and algebra["u_prime_local_mev3"] == 0.0
        and algebra["cubic_factor"] < 0.0
        and algebra["quartic_factor"] > 0.0
        and endpoint.hermiticity_error < 1.0e-10
    )
    state_pass = bool(
        0.0 < endpoint.energy < 2500.0
        and endpoint.nodes == 0
        and endpoint.gap > 5.0
        and endpoint.tail_probability < 1.0e-4
        and endpoint.normalization_error < 1.0e-10
    )
    optimizer_pass = bool(
        receipt["primary_optimizer"]["differential_evolution"]["success"]
        and receipt["primary_optimizer"]["powell"]["success"]
    )
    non_a_interior = bool(np.all(x0[1:] > 0.02) and np.all(x0[1:] < 0.98))
    stationarity_pass = bool(
        optimizer_pass
        and non_a_interior
        and float(np.max(np.abs(gradient))) < 1.0
        and hessian_eigenvalues[0] > 5.0
        and all(row["nodes_match"] for row in reconstructed_stencils)
        and min(overlap(endpoint, at(np.asarray(row["x"]))) for row in stationarity_record["stencils"])
        >= 0.98
    )
    grid_metrics = sequence_results["grid_sequence"]["pair_metrics"]
    box_metrics = sequence_results["box_sequence"]["pair_metrics"]
    regulator_metrics = sequence_results["regulator_sequence"]["pair_metrics"]
    sequence_optimizers_pass = all(
        bool(row["optimizer"]["success"])
        for name in ("grid_sequence", "box_sequence", "regulator_sequence")
        for row in receipt[name]
    )
    field_tail_pass = math.isfinite(endpoint.field_tail) and endpoint.field_tail < 1.0e-4
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
        and math.isfinite(extrapolation["quadratic_intercept_mev"])
        and extrapolation["intercept_relative_difference"] < 0.02
    )
    dilation_by_scale = {
        round(float(row["lambda"]), 8): reconstruction
        for row, reconstruction in zip(dilation_record["rows"], dilation_rows)
    }
    local_dilation_pass = bool(
        dilation_by_scale[0.95].total - endpoint.total >= 0.05
        and dilation_by_scale[1.05].total - endpoint.total >= 0.05
    )
    endpoint_dilation_pass = bool(
        dilation_by_scale[0.50].total - endpoint.total >= 10.0
        and dilation_by_scale[2.00].total - endpoint.total >= 10.0
    )
    affine_pass = bool(
        endpoint.kinetic_one > 0.0
        and field_gradient > 0.0
        and affine_curvature > 10.0
        and all(
            row["trial_energy_mev"] - affine_baseline > 0.0
            for row in affine_rows
            if row["d"] != 0.0
        )
    )
    icb4_pass = bool(
        virial_relative < 0.02
        and local_dilation_pass
        and endpoint_dilation_pass
        and affine_pass
    )
    icb5_supports = bool(basin_count >= 8 and low_seed and high_seed)
    independent_gates = {
        "ICB1": "PASS" if algebra_pass else "FAIL",
        "ICB2": "PASS" if state_pass and stationarity_pass else "FAIL",
        "ICB3": "PASS" if icb3_pass else "FAIL",
        "ICB4": "PASS" if icb4_pass else "FAIL",
        "ICB5": "SUPPORTS" if icb5_supports else "CONTRADICTS",
        "ICB6": "FAIL",
    }
    independent_overall = (
        "INTERACTING_REDUCED_FORMATION_SUPPORTS"
        if all(independent_gates[key] == "PASS" for key in ("ICB1", "ICB2", "ICB3", "ICB4"))
        and independent_gates["ICB5"] == "SUPPORTS"
        else "INTERACTING_REDUCED_FORMATION_CONTRADICTS"
    )

    reconstruction_checks = {
        "endpoint_matches": all_close_errors(endpoint_errors),
        "endpoint_arrays_match": max(endpoint_array_checks.values()) < 2.0e-8,
        "profile_arrays_match": max(profile_array_errors.values()) < 2.0e-10,
        "hamiltonian_residual_below_1e-7_mev": endpoint.hamiltonian_residual < 1.0e-7,
        "stationarity_matches": max(stationarity_errors.values()) < 2.0e-5,
        "sequences_match": all(
            row["all_rows_match"] for row in sequence_results.values()
        ),
        "extrapolation_matches": max(extrapolation_errors.values()) < 2.0e-8,
        "dilation_matches": max(dilation_errors.values()) < 2.0e-5,
        "affine_matches": max(affine_errors.values()) < 2.0e-8,
        "formation_rows_match": all(
            row["receipt_basin_match"]
            and all_close_errors(row["numerical_errors"])
            for row in formation_rows
        ),
        "formation_summary_matches": basin_count == int(formation_record["basin_count"])
        and low_seed == bool(formation_record["low_chi_seed_in_basin"])
        and high_seed == bool(formation_record["high_chi_seed_in_basin"]),
        "negative_controls_match": controls_match,
        "gate_reconstruction_matches": independent_gates == receipt["decisions"]["gates"],
        "overall_reconstruction_matches": independent_overall
        == receipt["decisions"]["overall_reduced_verdict"],
        "physical_completion_false": receipt["decisions"][
            "complete_physical_matter_formation"
        ]
        is False,
    }
    verification_pass = bool(
        all(source_checks.values())
        and all(constant_checks.values())
        and all(reconstruction_checks.values())
    )

    output = {
        "schema": "cassi.qcd-interacting-baryon.independent-verification.v1",
        "protocol_status": "Preregistered—September 2026",
        "primary_receipt": {
            "path": PRIMARY_RESULTS.relative_to(ROOT).as_posix(),
            "sha256": sha256(PRIMARY_RESULTS),
        },
        "sources": {
            "protocol": {
                "path": PROTOCOL.relative_to(ROOT).as_posix(),
                "sha256": sha256(PROTOCOL),
            },
            "primary": {
                "path": PRIMARY_SOURCE.relative_to(ROOT).as_posix(),
                "sha256": sha256(PRIMARY_SOURCE),
            },
            "verifier": {
                "path": SELF.relative_to(ROOT).as_posix(),
                "sha256": sha256(SELF),
            },
        },
        "source_checks": source_checks,
        "constant_checks": constant_checks,
        "endpoint": {
            "z": endpoint.z.tolist(),
            "candidate_energy_mev": endpoint.energy,
            "total_energy_mev": endpoint.total,
            "rms_fm": endpoint.rms,
            "field_tail_beyond_box_mev": endpoint.field_tail,
            "hamiltonian_residual_mev": endpoint.hamiltonian_residual,
            "errors": endpoint_errors,
            "array_errors": endpoint_array_checks,
            "profile_array_errors": profile_array_errors,
        },
        "stationarity": {
            "gradient_mev_per_normalized_coordinate": gradient.tolist(),
            "hessian_eigenvalues_mev": hessian_eigenvalues.tolist(),
            "errors": stationarity_errors,
        },
        "sequences": sequence_results,
        "regulator_extrapolation": {
            **extrapolation,
            "errors": extrapolation_errors,
        },
        "dilation": {
            "virial_residual_mev": virial,
            "virial_relative_residual": virial_relative,
            "errors": dilation_errors,
        },
        "affine": {
            "analytic_second_derivative_mev": affine_curvature,
            "errors": affine_errors,
        },
        "formation": {
            "basin_count": basin_count,
            "low_chi_seed_in_basin": low_seed,
            "high_chi_seed_in_basin": high_seed,
            "rows": formation_rows,
        },
        "negative_controls": {
            "rows_reconstructed": len(control_errors),
            "all_match": controls_match,
            "rows": control_errors,
        },
        "independent_decisions": {
            "gates": independent_gates,
            "overall_reduced_verdict": independent_overall,
            "complete_physical_matter_formation": False,
            "criteria": {
                "optimizer_pass": optimizer_pass,
                "state_pass": state_pass,
                "algebra_pass": algebra_pass,
                "stationarity_pass": stationarity_pass,
                "field_tail_pass": field_tail_pass,
                "regulator_grid_box_pass": icb3_pass,
                "virial_pass": virial_relative < 0.02,
                "local_dilation_pass": local_dilation_pass,
                "endpoint_dilation_pass": endpoint_dilation_pass,
                "affine_pass": affine_pass,
                "formation_basin_pass": icb5_supports,
            },
        },
        "reconstruction_checks": reconstruction_checks,
        "verification_pass": verification_pass,
        "elapsed_seconds": time.time() - started,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=False)
    RESULTS.write_text(
        json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        " ".join(
            f"{key}={value}" for key, value in independent_gates.items()
        )
    )
    print(independent_overall)
    print(f"independent_verification={'PASS' if verification_pass else 'FAIL'}")
    print(f"wrote {RESULTS.relative_to(ROOT).as_posix()}")
    return 0 if verification_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
