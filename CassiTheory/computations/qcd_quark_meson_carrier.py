#!/usr/bin/env python3
"""Run the frozen regular quark–meson carrier calculation.

Run from the CassiTheory root:
    python computations/qcd_quark_meson_carrier.py \
      --output-dir runs/20260910_qcd_quark_meson_carrier/primary
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy
from scipy import integrate, optimize, sparse
from scipy.sparse import linalg as spla


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-quark-meson-carrier-prereg.md"
SCHEMA = "cassi.qcd-quark-meson-carrier.primary.v1"
DEFAULT_OUTPUT = ROOT / "runs" / "20260910_qcd_quark_meson_carrier" / "primary"

HBARC = 197.3269804  # MeV fm
NC = 3
F_PI = 93.0  # MeV
M_PI = 139.6  # MeV
M_SIGMA = 1200.0  # MeV
M_Q = 500.0  # MeV
LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)
V_SQ = F_PI**2 - M_PI**2 / LAMBDA
H_BREAK = F_PI * M_PI**2
R_MAX = 12.0  # fm
SCAN_N = 1200
GRID_SEQUENCE = (600, 1200, 2400)
R_SCAN = np.round(np.arange(0.10, 2.5000001, 0.05), 12)
A_SCAN = np.round(np.arange(0.0, 1.0000001, 0.05), 12)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(data),
        "bytes": len(data),
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
    text = json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False)
    path.write_text(text + "\n", encoding="utf-8")


def profile(a: float, radius: float, r: np.ndarray | float) -> tuple[Any, Any, Any, Any]:
    rr = np.asarray(r, dtype=np.float64)
    den = rr**4 + radius**4
    cos_f = (rr**4 - radius**4) / den
    sin_f = 2.0 * radius**2 * rr**2 / den
    f_prime = -4.0 * radius**2 * rr / den
    s = 1.0 - a + a * cos_f
    p = -a * sin_f
    s_prime = -a * sin_f * f_prime
    p_prime = -a * cos_f * f_prime
    return s, p, s_prime, p_prime


def stable_potential_difference(s: Any, p: Any) -> Any:
    radial_delta = s * s + p * p - 1.0
    return (
        0.5 * M_PI**2 * F_PI**2 * ((s - 1.0) ** 2 + p * p)
        + 0.25 * LAMBDA * F_PI**4 * radial_delta**2
    )


def meson_integrand(r: float, a: float, radius: float) -> float:
    s, p, s_prime, p_prime = profile(a, radius, r)
    angular = 0.0 if r == 0.0 else 2.0 * float(p) ** 2 / r**2
    gradient = F_PI**2 / (2.0 * HBARC) * (
        float(s_prime) ** 2 + float(p_prime) ** 2 + angular
    )
    potential = float(stable_potential_difference(s, p)) / HBARC**3
    return 4.0 * math.pi * r**2 * (gradient + potential)


_MESON_CACHE: dict[tuple[float, float], tuple[float, float]] = {}


def meson_energy(a: float, radius: float) -> tuple[float, float]:
    key = (round(float(a), 12), round(float(radius), 10))
    if key in _MESON_CACHE:
        return _MESON_CACHE[key]
    value, error = integrate.quad(
        meson_integrand,
        0.0,
        np.inf,
        args=(float(a), float(radius)),
        epsabs=1.0e-7,
        epsrel=2.0e-11,
        limit=600,
    )
    result = (float(value), float(error))
    _MESON_CACHE[key] = result
    return result


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
    cutoff_index = int(np.searchsorted(cumulative, 0.999, side="left"))
    cutoff_index = max(2, min(cutoff_index, radial.size - 1))
    peak = float(np.max(np.abs(amplitude[: cutoff_index + 1])))
    if peak == 0.0:
        return radial.size
    mask = np.abs(amplitude[: cutoff_index + 1]) > 1.0e-3 * peak
    signs = np.sign(amplitude[: cutoff_index + 1][mask])
    if signs.size < 2:
        return 0
    return int(np.count_nonzero(signs[1:] * signs[:-1] < 0.0))


def radial_spectrum(a: float, radius: float, n: int = SCAN_N) -> dict[str, Any]:
    dr = R_MAX / n
    radial = (np.arange(n, dtype=np.float64) + 0.5) * dr
    weight_sqrt = radial * math.sqrt(dr)
    weight_inverse = 1.0 / weight_sqrt

    derivative = derivative_matrix(n, dr)
    left_scale = sparse.diags(weight_sqrt, format="csr")
    right_scale = sparse.diags(weight_inverse, format="csr")
    derivative_tilde = left_scale @ derivative @ right_scale
    wilson_tilde = 0.5 * HBARC * dr * (derivative_tilde.T @ derivative_tilde)

    s, p, _, _ = profile(a, radius, radial)
    scalar = M_Q * s
    pseudoscalar = M_Q * p
    offdiag = HBARC * derivative_tilde - sparse.diags(pseudoscalar, format="csr")
    mass = sparse.diags(scalar, format="csr") + wilson_tilde
    hamiltonian = sparse.bmat(
        [[mass, offdiag.T], [offdiag, -mass]], format="csc", dtype=np.float64
    )

    asymmetry_matrix = hamiltonian - hamiltonian.T
    symmetry_error = (
        float(np.max(np.abs(asymmetry_matrix.data)))
        if asymmetry_matrix.nnz
        else 0.0
    )
    eigenvalues, eigenvectors = spla.eigsh(
        hamiltonian,
        k=12,
        sigma=1.0e-8,
        which="LM",
        tol=2.0e-11,
        maxiter=10000,
    )
    order = np.argsort(eigenvalues)
    eigenvalues = np.asarray(eigenvalues[order], dtype=np.float64)
    eigenvectors = np.asarray(eigenvectors[:, order], dtype=np.float64)

    states: list[dict[str, Any]] = []
    for column, energy in enumerate(eigenvalues):
        vector = eigenvectors[:, column].copy()
        h = vector[:n] * weight_inverse
        j = vector[n:] * weight_inverse
        if h[0] < 0.0:
            vector *= -1.0
            h *= -1.0
            j *= -1.0
        probability = vector[:n] ** 2 + vector[n:] ** 2
        norm = float(np.sum(probability))
        probability /= norm
        rms = math.sqrt(float(np.dot(probability, radial**2)))
        tail = float(np.sum(probability[radial >= 8.0]))
        nodes = count_nodes(radial, h, probability)
        states.append(
            {
                "energy_mev": float(energy),
                "nodes_h": nodes,
                "rms_fm": rms,
                "tail_probability_r_ge_8fm": tail,
                "vector": vector,
                "h": h,
                "j": j,
                "probability": probability,
            }
        )

    candidates = [
        state
        for state in states
        if -M_Q < state["energy_mev"] < M_Q and state["nodes_h"] == 0
    ]
    candidate = (
        min(candidates, key=lambda item: abs(item["energy_mev"]))
        if candidates
        else None
    )
    same_sign_gap = None
    if candidate is not None:
        candidate_sign = 1.0 if candidate["energy_mev"] >= 0.0 else -1.0
        alternatives = [
            abs(state["energy_mev"] - candidate["energy_mev"])
            for state in states
            if state is not candidate
            and candidate_sign * state["energy_mev"] > 0.0
        ]
        same_sign_gap = min(alternatives) if alternatives else None

    return {
        "a": float(a),
        "radius_fm": float(radius),
        "n": int(n),
        "dr_fm": float(dr),
        "radial": radial,
        "eigenvalues": eigenvalues,
        "states": states,
        "candidate": candidate,
        "same_sign_gap_mev": same_sign_gap,
        "symmetry_error": symmetry_error,
    }


_SPECTRUM_CACHE: dict[tuple[float, float, int], dict[str, Any]] = {}


def cached_spectrum(a: float, radius: float, n: int = SCAN_N) -> dict[str, Any]:
    key = (round(float(a), 12), round(float(radius), 9), int(n))
    if key not in _SPECTRUM_CACHE:
        _SPECTRUM_CACHE[key] = radial_spectrum(float(a), float(radius), int(n))
    return _SPECTRUM_CACHE[key]


def total_energy(a: float, radius: float, n: int = SCAN_N) -> dict[str, Any]:
    spectrum = cached_spectrum(a, radius, n)
    meson, meson_error = meson_energy(a, radius)
    candidate = spectrum["candidate"]
    level = float(candidate["energy_mev"]) if candidate is not None else M_Q
    return {
        "a": float(a),
        "radius_fm": float(radius),
        "level_mev": level,
        "bound_state": candidate is not None,
        "meson_mev": meson,
        "meson_quadrature_error_mev": meson_error,
        "total_mev": 3.0 * level + meson,
        "candidate": candidate,
        "spectrum": spectrum,
    }


def public_energy_row(result: dict[str, Any]) -> dict[str, Any]:
    candidate = result["candidate"]
    spectrum = result["spectrum"]
    return {
        "a": result["a"],
        "radius_fm": result["radius_fm"],
        "level_mev": result["level_mev"],
        "bound_state": result["bound_state"],
        "meson_mev": result["meson_mev"],
        "meson_quadrature_error_mev": result["meson_quadrature_error_mev"],
        "total_mev": result["total_mev"],
        "rms_fm": None if candidate is None else candidate["rms_fm"],
        "nodes_h": None if candidate is None else candidate["nodes_h"],
        "tail_probability_r_ge_8fm": (
            None if candidate is None else candidate["tail_probability_r_ge_8fm"]
        ),
        "same_sign_gap_mev": spectrum["same_sign_gap_mev"],
        "symmetry_error": spectrum["symmetry_error"],
        "eigenvalues_mev": spectrum["eigenvalues"],
    }


def scan_radii(a: float, n: int = SCAN_N) -> tuple[list[dict[str, Any]], list[float]]:
    private_rows = [total_energy(a, float(radius), n) for radius in R_SCAN]
    overlaps: list[float] = []
    previous: np.ndarray | None = None
    for row in private_rows:
        candidate = row["candidate"]
        if candidate is None:
            previous = None
            continue
        vector = candidate["vector"]
        if previous is not None:
            overlaps.append(float(abs(np.dot(previous, vector))))
        previous = vector
    return private_rows, overlaps


def refine_radius(a: float, sampled: list[dict[str, Any]], n: int = SCAN_N) -> dict[str, Any]:
    index = int(np.argmin([row["total_mev"] for row in sampled]))
    if index == 0 or index == len(sampled) - 1:
        chosen = sampled[index]
        return {
            "qualified_interior": False,
            "sample_index": index,
            "bracket_fm": None,
            "optimizer_success": False,
            "result": chosen,
        }
    lower = float(R_SCAN[index - 1])
    upper = float(R_SCAN[index + 1])
    minimization = optimize.minimize_scalar(
        lambda radius: total_energy(a, float(radius), n)["total_mev"],
        method="bounded",
        bounds=(lower, upper),
        options={"xatol": 1.0e-6, "maxiter": 120},
    )
    refined = total_energy(a, float(minimization.x), n)
    return {
        "qualified_interior": True,
        "sample_index": index,
        "bracket_fm": [lower, upper],
        "optimizer_success": bool(minimization.success),
        "optimizer_message": str(minimization.message),
        "result": refined,
    }


def branch_overlaps(rows: list[dict[str, Any]]) -> list[float]:
    overlaps: list[float] = []
    previous: np.ndarray | None = None
    for row in rows:
        candidate = row["candidate"]
        if candidate is None:
            previous = None
            continue
        vector = candidate["vector"]
        if previous is not None:
            overlaps.append(float(abs(np.dot(previous, vector))))
        previous = vector
    return overlaps


def vacuum_checks() -> dict[str, Any]:
    vacuum_radial = F_PI**2
    first_sigma = LAMBDA * (vacuum_radial - V_SQ) * F_PI - H_BREAK
    first_pion = 0.0
    pion_hessian = LAMBDA * (vacuum_radial - V_SQ)
    sigma_hessian = LAMBDA * (3.0 * F_PI**2 - V_SQ)
    zero_s, zero_p, zero_sp, zero_pp = profile(0.5, 1.0, 0.0)
    zero_gradient_density = F_PI**2 / (2.0 * HBARC) * (
        float(zero_sp) ** 2 + float(zero_pp) ** 2
    )
    zero_potential_density = float(stable_potential_difference(zero_s, zero_p)) / HBARC**3
    derivative_scale = max(abs(H_BREAK), 1.0)
    first_derivative_dimensionless = max(abs(first_sigma), abs(first_pion)) / derivative_scale
    return {
        "first_derivatives_mev3": [float(first_sigma), float(first_pion)],
        "first_derivative_max_abs_mev3": float(max(abs(first_sigma), abs(first_pion))),
        "first_derivative_scale_mev3": float(derivative_scale),
        "first_derivative_dimensionless_max_abs": float(first_derivative_dimensionless),
        "pion_hessian_mev2": float(pion_hessian),
        "sigma_hessian_mev2": float(sigma_hessian),
        "pion_mass_relative_error": float(abs(math.sqrt(pion_hessian) - M_PI) / M_PI),
        "sigma_mass_relative_error": float(
            abs(math.sqrt(sigma_hessian) - M_SIGMA) / M_SIGMA
        ),
        "chiral_zero": {
            "a": 0.5,
            "radius_fm": 1.0,
            "r_fm": 0.0,
            "s": float(zero_s),
            "p": float(zero_p),
            "gradient_energy_density_mev_per_fm3": zero_gradient_density,
            "potential_energy_density_mev_per_fm3": zero_potential_density,
            "total_energy_density_mev_per_fm3": zero_gradient_density
            + zero_potential_density,
            "finite": bool(
                math.isfinite(zero_gradient_density + zero_potential_density)
            ),
        },
    }


def pauli_matrices() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    sx = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    sy = np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
    sz = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    return sx, sy, sz


def current_control() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    sx, sy, sz = pauli_matrices()
    identity2 = np.eye(2, dtype=np.complex128)
    zero2 = np.zeros((2, 2), dtype=np.complex128)
    beta = np.block([[identity2, zero2], [zero2, -identity2]])
    alpha_x = np.block([[zero2, sx], [sx, zero2]])
    gamma5 = np.block([[zero2, identity2], [identity2, zero2]])
    tau3 = sz
    identity_iso = identity2
    beta8 = np.kron(beta, identity_iso)
    alpha8 = np.kron(alpha_x, identity_iso)
    pion8 = 1j * np.kron(beta @ gamma5, tau3)
    internal = 8
    sites = 3
    spacing = 0.4
    hopping_forward = -1j * HBARC * alpha8 / (2.0 * spacing) - HBARC * beta8 / (
        2.0 * spacing
    )
    hopping_backward = hopping_forward.conj().T
    wilson_onsite = HBARC * beta8 / spacing

    raw = np.arange(1, 49, dtype=np.float64)
    psi = raw[:24] + 1j * raw[24:]
    psi = psi.reshape(sites, internal)
    psi /= np.linalg.norm(psi)

    def make_hamiltonian(zero_middle: bool) -> np.ndarray:
        hamiltonian = np.zeros(
            (sites * internal, sites * internal), dtype=np.complex128
        )
        for site in range(sites):
            if site == 1 and zero_middle:
                scalar, pion = 0.0, 0.0
            else:
                scalar, pion = M_Q, 0.0
            onsite = wilson_onsite + scalar * beta8 + pion * pion8
            sl = slice(site * internal, (site + 1) * internal)
            hamiltonian[sl, sl] += onsite
            next_site = (site + 1) % sites
            sr = slice(next_site * internal, (next_site + 1) * internal)
            hamiltonian[sl, sr] += hopping_forward
            hamiltonian[sr, sl] += hopping_backward
        return hamiltonian

    def evaluate(hamiltonian: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        dot_density = np.zeros(sites, dtype=np.float64)
        currents = np.zeros((sites, sites), dtype=np.float64)
        for x in range(sites):
            slx = slice(x * internal, (x + 1) * internal)
            for y in range(sites):
                sly = slice(y * internal, (y + 1) * internal)
                block = hamiltonian[slx, sly]
                contribution = np.vdot(psi[x], block @ psi[y])
                dot_density[x] += 2.0 * contribution.imag
                if x != y:
                    currents[x, y] = -2.0 * contribution.imag
        residual = dot_density + np.sum(currents, axis=1)
        antisymmetry = currents + currents.T
        return (
            dot_density,
            currents,
            float(np.max(np.abs(residual))),
            float(np.max(np.abs(antisymmetry))),
        )

    zero_hamiltonian = make_hamiltonian(True)
    vacuum_hamiltonian = make_hamiltonian(False)
    zero_dot, zero_currents, zero_residual, zero_antisymmetry = evaluate(zero_hamiltonian)
    vacuum_dot, vacuum_currents, vacuum_residual, vacuum_antisymmetry = evaluate(
        vacuum_hamiltonian
    )
    hermiticity = max(
        float(np.max(np.abs(zero_hamiltonian - zero_hamiltonian.conj().T))),
        float(np.max(np.abs(vacuum_hamiltonian - vacuum_hamiltonian.conj().T))),
    )
    result = {
        "sites": sites,
        "internal_dimension": internal,
        "spacing_fm": spacing,
        "hamiltonian_hermiticity_error": hermiticity,
        "zero_middle": {
            "density_derivative": zero_dot,
            "bond_currents": zero_currents,
            "continuity_residual_max_abs": zero_residual,
            "bond_antisymmetry_max_abs": zero_antisymmetry,
        },
        "vacuum_middle": {
            "density_derivative": vacuum_dot,
            "bond_currents": vacuum_currents,
            "continuity_residual_max_abs": vacuum_residual,
            "bond_antisymmetry_max_abs": vacuum_antisymmetry,
        },
        "zero_vs_vacuum_density_derivative_max_abs": float(
            np.max(np.abs(zero_dot - vacuum_dot))
        ),
    }
    arrays = {
        "current_spinor": psi,
        "current_zero_hamiltonian": zero_hamiltonian,
        "current_vacuum_hamiltonian": vacuum_hamiltonian,
        "current_zero_currents": zero_currents,
        "current_vacuum_currents": vacuum_currents,
    }
    return result, arrays


def cosmology_ledger() -> dict[str, Any]:
    zeta3 = float(scipy.special.zeta(3.0, 1.0))
    temperature = 156.5
    eta_b = 6.0e-10
    photon_density = 2.0 * zeta3 / math.pi**2 * (temperature / HBARC) ** 3
    baryon_density = eta_b * photon_density
    spacing = baryon_density ** (-1.0 / 3.0)
    volume = 5.0**3
    baryons_per_box = baryon_density * volume
    boxes_per_baryon = 1.0 / baryons_per_box

    planck_mass_gev = 1.220890e19
    hbar_gev_s = 6.582119569e-25
    strong_time_s = 2.0e-15 / 299792458.0
    hubble_rows: list[dict[str, Any]] = []
    for temp_mev in (155.0, 158.0):
        for g_star in (17.25, 61.75):
            temp_gev = temp_mev / 1000.0
            hubble_gev = 1.66 * math.sqrt(g_star) * temp_gev**2 / planck_mass_gev
            hubble_per_s = hubble_gev / hbar_gev_s
            hubble_time_s = 1.0 / hubble_per_s
            hubble_rows.append(
                {
                    "temperature_mev": temp_mev,
                    "g_star": g_star,
                    "hubble_per_s": hubble_per_s,
                    "hubble_time_s": hubble_time_s,
                    "hubble_to_2fm_over_c_ratio": hubble_time_s / strong_time_s,
                }
            )
    return {
        "temperature_mev": temperature,
        "eta_b": eta_b,
        "zeta_3": zeta3,
        "photon_density_fm_minus3": photon_density,
        "net_baryon_density_fm_minus3": baryon_density,
        "mean_net_baryon_spacing_fm": spacing,
        "five_fm_box_volume_fm3": volume,
        "expected_net_baryons_per_five_fm_box": baryons_per_box,
        "five_fm_boxes_per_net_baryon": boxes_per_baryon,
        "two_fm_over_c_s": strong_time_s,
        "hubble_rows": hubble_rows,
        "minimum_hubble_to_strong_time_ratio": min(
            row["hubble_to_2fm_over_c_ratio"] for row in hubble_rows
        ),
        "interpretation": (
            "The fixed B=1 sector represents inherited asymmetry; an exactly "
            "neutral closed state remains net neutral under the selected action."
        ),
    }


def main(output_dir: Path) -> int:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence in {output_dir}")
    output_dir.mkdir(parents=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir()
    shutil.copy2(PROTOCOL, source_dir / PROTOCOL.name)
    shutil.copy2(SELF, source_dir / SELF.name)

    protocol_identity = identity(PROTOCOL)
    source_identity = identity(SELF)
    constants = {
        "n_c": NC,
        "f_pi_mev": F_PI,
        "m_pi_mev": M_PI,
        "m_sigma_mev": M_SIGMA,
        "m_q_mev": M_Q,
        "lambda": LAMBDA,
        "v_sq_mev2": V_SQ,
        "h_break_mev3": H_BREAK,
        "hbar_c_mev_fm": HBARC,
        "r_max_fm": R_MAX,
        "scan_n": SCAN_N,
        "grid_sequence": GRID_SEQUENCE,
        "r_scan_fm": R_SCAN,
        "a_scan": A_SCAN,
    }

    vacuum = vacuum_checks()
    current, current_arrays = current_control()
    cosmology = cosmology_ledger()

    endpoint_private, endpoint_overlaps = scan_radii(1.0)
    endpoint_refinement = refine_radius(1.0, endpoint_private)
    selected_private = endpoint_refinement["result"]
    selected_radius = float(selected_private["radius_fm"])

    convergence_private = [
        total_energy(1.0, selected_radius, n) for n in GRID_SEQUENCE
    ]
    convergence_rows = [public_energy_row(row) for row in convergence_private]
    selected_private = convergence_private[1]
    selected = public_energy_row(selected_private)

    fixed_amplitude_private = [
        total_energy(float(a), selected_radius, SCAN_N) for a in A_SCAN
    ]
    amplitude_overlaps = branch_overlaps(fixed_amplitude_private)

    envelope_private: list[dict[str, Any]] = []
    envelope_sample_rows: list[list[dict[str, Any]]] = []
    for a in A_SCAN:
        sampled, _ = scan_radii(float(a), SCAN_N)
        refined = refine_radius(float(a), sampled, SCAN_N)
        envelope_private.append(refined)
        envelope_sample_rows.append(sampled)

    delta_a = 0.01
    delta_r = 0.01
    e_1_0 = total_energy(1.0, selected_radius, SCAN_N)["total_mev"]
    e_a1 = total_energy(1.0 - delta_a, selected_radius, SCAN_N)["total_mev"]
    e_a2 = total_energy(1.0 - 2.0 * delta_a, selected_radius, SCAN_N)["total_mev"]
    e_rp = total_energy(1.0, selected_radius + delta_r, SCAN_N)["total_mev"]
    e_rm = total_energy(1.0, selected_radius - delta_r, SCAN_N)["total_mev"]
    e_arp = total_energy(1.0 - delta_a, selected_radius + delta_r, SCAN_N)[
        "total_mev"
    ]
    e_arm = total_energy(1.0 - delta_a, selected_radius - delta_r, SCAN_N)[
        "total_mev"
    ]
    endpoint_derivatives = {
        "delta_a": delta_a,
        "delta_r_fm": delta_r,
        "backward_first_a_mev": (3.0 * e_1_0 - 4.0 * e_a1 + e_a2)
        / (2.0 * delta_a),
        "backward_second_a_mev": (e_1_0 - 2.0 * e_a1 + e_a2) / delta_a**2,
        "centered_second_r_mev_per_fm2": (e_rp - 2.0 * e_1_0 + e_rm)
        / delta_r**2,
        "backward_centered_cross_mev_per_fm": (
            (e_rp - e_arp) - (e_rm - e_arm)
        )
        / (2.0 * delta_a * delta_r),
        "sample_energies_mev": {
            "e_1_0": e_1_0,
            "e_a1": e_a1,
            "e_a2": e_a2,
            "e_rp": e_rp,
            "e_rm": e_rm,
            "e_arp": e_arp,
            "e_arm": e_arm,
        },
    }

    envelope_rows = []
    for item in envelope_private:
        row = public_energy_row(item["result"])
        row.update(
            {
                "qualified_interior": item["qualified_interior"],
                "optimizer_success": item["optimizer_success"],
                "bracket_fm": item["bracket_fm"],
            }
        )
        envelope_rows.append(row)
    envelope_barrier = max(row["total_mev"] - 3.0 * M_Q for row in envelope_rows)

    overlap_values = endpoint_overlaps + amplitude_overlaps
    min_overlap = min(overlap_values) if overlap_values else 1.0
    selected_candidate = selected_private["candidate"]
    selected_gap = selected_private["spectrum"]["same_sign_gap_mev"]
    symmetry_error = max(
        row["spectrum"]["symmetry_error"]
        for row in endpoint_private + fixed_amplitude_private + convergence_private
    )
    finest_level_difference = (
        abs(convergence_rows[-1]["level_mev"] - convergence_rows[-2]["level_mev"])
        if convergence_rows[-1]["bound_state"] and convergence_rows[-2]["bound_state"]
        else None
    )
    finest_level_relative = (
        finest_level_difference / max(abs(convergence_rows[-1]["level_mev"]), 1.0)
        if finest_level_difference is not None
        else None
    )
    endpoint_total_relative = abs(
        convergence_rows[-1]["total_mev"] - convergence_rows[-2]["total_mev"]
    ) / max(abs(convergence_rows[-1]["total_mev"]), 1.0)

    qmc1_pass = all(
        [
            vacuum["first_derivative_dimensionless_max_abs"] < 1.0e-10,
            vacuum["pion_mass_relative_error"] < 1.0e-8,
            vacuum["sigma_mass_relative_error"] < 1.0e-8,
            vacuum["chiral_zero"]["finite"],
            symmetry_error < 1.0e-10,
            current["hamiltonian_hermiticity_error"] < 1.0e-12,
            current["zero_middle"]["continuity_residual_max_abs"] < 1.0e-12,
            current["zero_middle"]["bond_antisymmetry_max_abs"] < 1.0e-12,
            current["zero_vs_vacuum_density_derivative_max_abs"] < 1.0e-12,
        ]
    )
    qmc2_primary_inputs = {
        "qmc1_pass": qmc1_pass,
        "endpoint_bound_state": selected_candidate is not None,
        "endpoint_nodeless": (
            selected_candidate is not None and selected_candidate["nodes_h"] == 0
        ),
        "minimum_adjacent_branch_overlap": min_overlap,
        "endpoint_same_sign_gap_mev": selected_gap,
        "finest_two_level_relative_difference": finest_level_relative,
        "all_finite": bool(
            all(
                math.isfinite(row["total_mev"])
                and math.isfinite(row["level_mev"])
                for row in convergence_rows + envelope_rows
            )
        ),
        "independent_agreement_pending": True,
    }
    qmc2_local = bool(
        qmc1_pass
        and selected_candidate is not None
        and selected_candidate["nodes_h"] == 0
        and min_overlap > 0.70
        and selected_gap is not None
        and selected_gap > 1.0
        and finest_level_relative is not None
        and finest_level_relative <= 0.02
        and qmc2_primary_inputs["all_finite"]
    )
    binding_margin = 3.0 * M_Q - selected["total_mev"]
    qmc3_local = bool(
        qmc2_local
        and endpoint_refinement["qualified_interior"]
        and endpoint_refinement["optimizer_success"]
        and binding_margin >= 5.0
        and endpoint_derivatives["centered_second_r_mev_per_fm2"] > 0.0
        and selected["rms_fm"] is not None
        and 0.2 <= selected["rms_fm"] <= 1.5
        and endpoint_total_relative <= 0.05
    )
    qmc5_pass = bool(
        cosmology["expected_net_baryons_per_five_fm_box"] < 1.0e-6
        and cosmology["five_fm_boxes_per_net_baryon"] > 1.0e6
        and cosmology["minimum_hubble_to_strong_time_ratio"] > 1.0e12
    )

    arrays: dict[str, np.ndarray] = dict(current_arrays)
    arrays["r_scan_fm"] = R_SCAN
    arrays["a_scan"] = A_SCAN
    arrays["endpoint_scan_total_mev"] = np.array(
        [row["total_mev"] for row in endpoint_private]
    )
    arrays["endpoint_scan_level_mev"] = np.array(
        [row["level_mev"] for row in endpoint_private]
    )
    arrays["endpoint_scan_meson_mev"] = np.array(
        [row["meson_mev"] for row in endpoint_private]
    )
    arrays["envelope_radius_fm"] = np.array(
        [row["radius_fm"] for row in envelope_rows]
    )
    arrays["envelope_total_mev"] = np.array(
        [row["total_mev"] for row in envelope_rows]
    )
    arrays["fixed_radius_level_mev"] = np.array(
        [row["level_mev"] for row in fixed_amplitude_private]
    )
    for result in convergence_private:
        n = result["spectrum"]["n"]
        arrays[f"radial_n{n}"] = result["spectrum"]["radial"]
        if result["candidate"] is not None:
            arrays[f"h_n{n}"] = result["candidate"]["h"]
            arrays[f"j_n{n}"] = result["candidate"]["j"]
            arrays[f"probability_n{n}"] = result["candidate"]["probability"]
            arrays[f"vector_n{n}"] = result["candidate"]["vector"]
    array_path = output_dir / "arrays.npz"
    np.savez_compressed(array_path, **arrays)
    array_identity = {
        "path": array_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(array_path.read_bytes()),
        "bytes": array_path.stat().st_size,
    }

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "completed": True,
        "scientific_execution_started": True,
        "protocol": protocol_identity,
        "sources": {
            "primary": source_identity,
            "snapshots": {
                "protocol": {
                    "path": (source_dir / PROTOCOL.name).relative_to(ROOT).as_posix(),
                    "sha256": sha256_bytes((source_dir / PROTOCOL.name).read_bytes()),
                    "bytes": (source_dir / PROTOCOL.name).stat().st_size,
                },
                "primary": {
                    "path": (source_dir / SELF.name).relative_to(ROOT).as_posix(),
                    "sha256": sha256_bytes((source_dir / SELF.name).read_bytes()),
                    "bytes": (source_dir / SELF.name).stat().st_size,
                },
            },
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
            "cpu_count": os.cpu_count(),
        },
        "constants": constants,
        "vacuum_and_zero": vacuum,
        "current_control": current,
        "cosmological_initial_conditions": cosmology,
        "endpoint_radius_scan": {
            "rows": [public_energy_row(row) for row in endpoint_private],
            "adjacent_bound_branch_overlaps": endpoint_overlaps,
        },
        "endpoint_refinement": {
            "qualified_interior": endpoint_refinement["qualified_interior"],
            "sample_index": endpoint_refinement["sample_index"],
            "bracket_fm": endpoint_refinement["bracket_fm"],
            "optimizer_success": endpoint_refinement["optimizer_success"],
            "selected": selected,
        },
        "grid_convergence": {
            "rows": convergence_rows,
            "finest_two_level_difference_mev": finest_level_difference,
            "finest_two_level_relative_difference": finest_level_relative,
            "finest_two_total_relative_difference": endpoint_total_relative,
        },
        "fixed_radius_amplitude_scan": {
            "radius_fm": selected_radius,
            "rows": [public_energy_row(row) for row in fixed_amplitude_private],
            "adjacent_bound_branch_overlaps": amplitude_overlaps,
        },
        "formation_envelope": {
            "rows": envelope_rows,
            "barrier_above_three_quark_threshold_mev": envelope_barrier,
        },
        "endpoint_derivatives": endpoint_derivatives,
        "measurements": {
            "selected_radius_fm": selected_radius,
            "selected_level_mev": selected["level_mev"],
            "selected_meson_mev": selected["meson_mev"],
            "selected_total_mev": selected["total_mev"],
            "three_quark_threshold_mev": 3.0 * M_Q,
            "binding_margin_mev": binding_margin,
            "selected_baryon_rms_radius_fm": selected["rms_fm"],
            "selected_same_sign_gap_mev": selected_gap,
            "minimum_adjacent_branch_overlap": min_overlap,
            "maximum_hamiltonian_symmetry_error": symmetry_error,
        },
        "gate_inputs": {
            "QMC1": {"passed": qmc1_pass},
            "QMC2": qmc2_primary_inputs,
            "QMC3": {
                "local_criteria_passed": qmc3_local,
                "binding_margin_mev": binding_margin,
                "qualified_interior": endpoint_refinement["qualified_interior"],
                "radial_curvature_mev_per_fm2": endpoint_derivatives[
                    "centered_second_r_mev_per_fm2"
                ],
                "rms_fm": selected["rms_fm"],
                "endpoint_total_relative_difference": endpoint_total_relative,
                "independent_agreement_pending": True,
            },
            "QMC4": {
                "local_criteria_passed": bool(qmc3_local and envelope_barrier <= 155.0),
                "barrier_mev": envelope_barrier,
                "threshold_mev": 155.0,
                "independent_agreement_pending": True,
            },
            "QMC5": {"passed": qmc5_pass},
            "QMC6": {
                "requirements": {
                    "cassi_action_and_parameter_selection": False,
                    "renormalized_interacting_vacuum_or_thermal_state": False,
                    "current_spin_statistics": True,
                    "continuum_nonradial_persistence_and_formation_rate": False,
                    "confinement_and_observable_nucleon_map": False,
                    "baryogenesis_without_fitted_outcome": False,
                },
                "passed": False,
            },
        },
        "primary_verdicts": {
            "QMC1": "PASS" if qmc1_pass else "FAIL",
            "QMC2": "INCONCLUSIVE",
            "QMC3": "INCONCLUSIVE",
            "QMC4": "INCONCLUSIVE",
            "QMC5": "PASS" if qmc5_pass else "FAIL",
            "QMC6": "FAIL",
        },
        "complete_physical_matter_formation": False,
        "artifacts": {"arrays": array_identity},
        "failure": None,
    }
    result_path = output_dir / "results.json"
    write_json(result_path, payload)
    print(
        json.dumps(
            {
                "result": result_path.relative_to(ROOT).as_posix(),
                "selected_radius_fm": selected_radius,
                "selected_level_mev": selected["level_mev"],
                "selected_total_mev": selected["total_mev"],
                "binding_margin_mev": binding_margin,
                "barrier_mev": envelope_barrier,
                "primary_verdicts": payload["primary_verdicts"],
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    try:
        raise SystemExit(main(arguments.output_dir))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
