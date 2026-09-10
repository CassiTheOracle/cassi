#!/usr/bin/env python3
"""Independently verify the frozen regular quark–meson carrier receipt.

Run from the CassiTheory root:
    python computations/verify_qcd_quark_meson_carrier.py \
      --input runs/20260910_qcd_quark_meson_carrier/amendment-2/primary/results.json \
      --output-dir runs/20260910_qcd_quark_meson_carrier/amendment-2/verification
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np
import scipy
from numpy.polynomial.legendre import leggauss
from scipy import integrate, optimize


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-quark-meson-carrier-prereg.md"
SCHEMA = "cassi.qcd-quark-meson-carrier.verification.v1"
PRIMARY_SCHEMA = "cassi.qcd-quark-meson-carrier.primary.v1"
DEFAULT_INPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "primary"
    / "results.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "20260910_qcd_quark_meson_carrier"
    / "amendment-2"
    / "verification"
)

HBARC = 197.3269804
NC = 3
F_PI = 93.0
M_PI = 139.6
M_SIGMA = 1200.0
M_Q = 500.0
LAMBDA = (M_SIGMA**2 - M_PI**2) / (2.0 * F_PI**2)
V_SQ = F_PI**2 - M_PI**2 / LAMBDA
H_BREAK = F_PI * M_PI**2
SHOOT_R0 = 1.0e-7
SHOOT_RMAX = 20.0
SHOOT_MATCH = 4.0
SHOOT_ENERGIES = np.linspace(-0.999 * M_Q, 0.999 * M_Q, 4001)
GL_N = 512
GL_X, GL_W = leggauss(GL_N)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_identity(path: Path) -> dict[str, Any]:
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
    path.write_text(
        json.dumps(json_ready(payload), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def check(name: str, condition: bool, detail: Any = None) -> dict[str, Any]:
    return {"name": name, "passed": bool(condition), "detail": json_ready(detail)}


def profile_fields(a: float, radius: float, r: np.ndarray | float) -> tuple[Any, Any, Any, Any]:
    coordinate = np.asarray(r, dtype=np.float64)
    denominator = coordinate**4 + radius**4
    cosine = (coordinate**4 - radius**4) / denominator
    sine = 2.0 * radius**2 * coordinate**2 / denominator
    angle_derivative = -4.0 * radius**2 * coordinate / denominator
    scalar = 1.0 - a + a * cosine
    pion = -a * sine
    scalar_derivative = -a * sine * angle_derivative
    pion_derivative = -a * cosine * angle_derivative
    return scalar, pion, scalar_derivative, pion_derivative


def potential_delta(scalar: Any, pion: Any) -> Any:
    norm_delta = scalar * scalar + pion * pion - 1.0
    return (
        0.5
        * M_PI**2
        * F_PI**2
        * ((scalar - 1.0) ** 2 + pion * pion)
        + 0.25 * LAMBDA * F_PI**4 * norm_delta**2
    )


def energy_density_integrand(r: np.ndarray, a: float, radius: float) -> np.ndarray:
    scalar, pion, scalar_d, pion_d = profile_fields(a, radius, r)
    angular = np.where(r > 0.0, 2.0 * pion**2 / r**2, 0.0)
    gradient = F_PI**2 / (2.0 * HBARC) * (scalar_d**2 + pion_d**2 + angular)
    potential = potential_delta(scalar, pion) / HBARC**3
    return 4.0 * math.pi * r**2 * (gradient + potential)


def gauss_interval(function: Callable[[np.ndarray], np.ndarray], left: float, right: float) -> float:
    midpoint = 0.5 * (left + right)
    halfwidth = 0.5 * (right - left)
    points = midpoint + halfwidth * GL_X
    return float(halfwidth * np.dot(GL_W, function(points)))


def analytic_tail_bound(a: float, radius: float, lower: float = SHOOT_RMAX) -> float:
    gradient_bound = 4.0 * math.pi * F_PI**2 / (2.0 * HBARC) * (
        8.0 * a**2 * radius**4 / lower**3
        + (64.0 / 7.0) * a**2 * radius**8 / lower**7
    )
    potential_r4 = 2.0 * M_PI**2 * F_PI**2 * a**2 * radius**4 / lower
    potential_r8_coefficient = (
        2.0 * M_PI**2 * F_PI**2 * a**2
        + 4.0 * LAMBDA * F_PI**4 * a**2 * (1.0 - a) ** 2
    )
    potential_r8 = potential_r8_coefficient * radius**8 / (5.0 * lower**5)
    potential_bound = 4.0 * math.pi / HBARC**3 * (potential_r4 + potential_r8)
    return gradient_bound + potential_bound


def independent_meson_energy(a: float, radius: float) -> dict[str, float]:
    intervals = ((0.0, radius), (radius, 4.0 * radius), (4.0 * radius, SHOOT_RMAX))
    pieces = [
        gauss_interval(lambda r: energy_density_integrand(r, a, radius), left, right)
        for left, right in intervals
    ]

    upper_t = 1.0 / SHOOT_RMAX

    def transformed(t: np.ndarray) -> np.ndarray:
        radial = 1.0 / t
        return energy_density_integrand(radial, a, radius) / t**2

    tail = gauss_interval(transformed, 0.0, upper_t)
    bound = analytic_tail_bound(a, radius, SHOOT_RMAX)
    return {
        "piece_0_r_mev": pieces[0],
        "piece_r_4r_mev": pieces[1],
        "piece_4r_20fm_mev": pieces[2],
        "tail_20fm_infinity_mev": tail,
        "analytic_tail_upper_bound_mev": bound,
        "tail_within_bound": bool(tail >= 0.0 and tail <= bound * (1.0 + 1.0e-12)),
        "total_mev": float(sum(pieces) + tail),
    }


def radial_rhs(r: float, state: np.ndarray, energy: float, a: float, radius: float) -> np.ndarray:
    scalar, pion, _, _ = profile_fields(a, radius, r)
    scalar_potential = M_Q * float(scalar)
    pion_potential = M_Q * float(pion)
    h, j = state
    return np.array(
        [
            (pion_potential * h + (energy + scalar_potential) * j) / HBARC,
            (-pion_potential * j + (scalar_potential - energy) * h) / HBARC
            - 2.0 * j / r,
        ],
        dtype=np.float64,
    )


def shoot(energy: float, a: float, radius: float, detailed: bool = False) -> dict[str, Any]:
    scalar_zero = M_Q * (1.0 - 2.0 * a)
    outward_initial = np.array(
        [1.0, (scalar_zero - energy) * SHOOT_R0 / (3.0 * HBARC)],
        dtype=np.float64,
    )
    kappa = math.sqrt(max(M_Q**2 - energy**2, 0.0)) / HBARC
    inward_initial = np.array(
        [
            1.0,
            -HBARC
            * (kappa + 1.0 / SHOOT_RMAX)
            / max(energy + M_Q, 1.0e-12),
        ],
        dtype=np.float64,
    )
    outward_evaluation = (
        np.linspace(SHOOT_R0, SHOOT_MATCH, 3201) if detailed else None
    )
    inward_evaluation = (
        np.linspace(SHOOT_RMAX, SHOOT_MATCH, 8001) if detailed else None
    )
    tolerances = {
        "rtol": 2.0e-11 if detailed else 2.0e-8,
        "atol": 2.0e-12 if detailed else 2.0e-9,
        "max_step": 0.04 if detailed else 0.12,
    }
    outward = integrate.solve_ivp(
        radial_rhs,
        (SHOOT_R0, SHOOT_MATCH),
        outward_initial,
        args=(energy, a, radius),
        method="DOP853",
        t_eval=outward_evaluation,
        **tolerances,
    )
    inward = integrate.solve_ivp(
        radial_rhs,
        (SHOOT_RMAX, SHOOT_MATCH),
        inward_initial,
        args=(energy, a, radius),
        method="DOP853",
        t_eval=inward_evaluation,
        **tolerances,
    )
    if (
        not outward.success
        or not inward.success
        or not np.all(np.isfinite(outward.y[:, -1]))
        or not np.all(np.isfinite(inward.y[:, -1]))
    ):
        return {
            "success": False,
            "residual": None,
            "message": f"outward={outward.message}; inward={inward.message}",
        }
    outward_match = outward.y[:, -1]
    inward_match = inward.y[:, -1]
    raw_residual = (
        outward_match[0] * inward_match[1]
        - outward_match[1] * inward_match[0]
    )
    residual_scale = max(
        float(np.linalg.norm(outward_match) * np.linalg.norm(inward_match)),
        1.0e-300,
    )
    result: dict[str, Any] = {
        "success": True,
        "residual": float(raw_residual / residual_scale),
        "raw_residual": float(raw_residual),
        "message": f"outward={outward.message}; inward={inward.message}",
    }
    if detailed:
        inward_scale = float(
            np.dot(outward_match, inward_match)
            / max(np.dot(inward_match, inward_match), 1.0e-300)
        )
        radial = np.concatenate((outward.t[:-1], inward.t[::-1]))
        h = np.concatenate((outward.y[0, :-1], inward_scale * inward.y[0, ::-1]))
        j = np.concatenate((outward.y[1, :-1], inward_scale * inward.y[1, ::-1]))
        density = radial**2 * (h**2 + j**2)
        norm = float(integrate.simpson(density, x=radial))
        rms = math.sqrt(
            float(integrate.simpson(radial**2 * density, x=radial)) / norm
        )
        peak = float(np.max(np.abs(h)))
        node_mask = np.abs(h) > max(peak * 1.0e-7, 1.0e-14)
        node_signs = np.sign(h[node_mask])
        nodes = int(np.count_nonzero(node_signs[1:] * node_signs[:-1] < 0.0))
        normalization = math.sqrt(norm)
        normalized_density = density / norm
        tail_mask = radial >= 8.0
        result.update(
            {
                "radial_fm": radial,
                "h_normalized": h / normalization,
                "j_normalized": j / normalization,
                "radial_probability_density": normalized_density,
                "norm_before_normalization": norm,
                "rms_fm": rms,
                "nodes_h": nodes,
                "match_radius_fm": SHOOT_MATCH,
                "match_relative_wronskian": float(raw_residual / residual_scale),
                "tail_probability_r_ge_8fm": float(
                    integrate.simpson(
                        normalized_density[tail_mask], x=radial[tail_mask]
                    )
                ),
            }
        )
    return result


def independent_spectrum(a: float, radius: float) -> dict[str, Any]:
    residuals = np.empty_like(SHOOT_ENERGIES)
    successes = np.zeros(SHOOT_ENERGIES.shape, dtype=bool)
    for index, energy in enumerate(SHOOT_ENERGIES):
        row = shoot(float(energy), a, radius, detailed=False)
        if row["success"] and row["residual"] is not None:
            residuals[index] = row["residual"]
            successes[index] = True
        else:
            residuals[index] = np.nan

    brackets: list[tuple[float, float]] = []
    for index in range(SHOOT_ENERGIES.size - 1):
        if not successes[index] or not successes[index + 1]:
            continue
        left_value = residuals[index]
        right_value = residuals[index + 1]
        if left_value == 0.0:
            brackets.append((float(SHOOT_ENERGIES[index]), float(SHOOT_ENERGIES[index])))
        elif left_value * right_value < 0.0:
            brackets.append(
                (float(SHOOT_ENERGIES[index]), float(SHOOT_ENERGIES[index + 1]))
            )

    roots: list[dict[str, Any]] = []
    for lower, upper in brackets:
        if lower == upper:
            root = lower
        else:
            root = optimize.brentq(
                lambda energy: float(shoot(energy, a, radius, detailed=False)["residual"]),
                lower,
                upper,
                xtol=1.0e-10,
                rtol=1.0e-13,
                maxiter=160,
            )
        if any(abs(root - row["energy_mev"]) < 1.0e-6 for row in roots):
            continue
        detail = shoot(root, a, radius, detailed=True)
        if detail["success"]:
            detail["energy_mev"] = float(root)
            roots.append(detail)

    nodeless = [row for row in roots if row["nodes_h"] == 0]
    selected = min(nodeless, key=lambda row: abs(row["energy_mev"])) if nodeless else None
    return {
        "a": float(a),
        "radius_fm": float(radius),
        "scan_count": int(SHOOT_ENERGIES.size),
        "failed_scan_integrations": int(np.count_nonzero(~successes)),
        "brackets": brackets,
        "roots": roots,
        "selected": selected,
        "scan_energy_mev": SHOOT_ENERGIES,
        "scan_residual": residuals,
    }


def reconstruct_current() -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    sigma_x = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    sigma_z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    identity2 = np.eye(2, dtype=np.complex128)
    zero2 = np.zeros((2, 2), dtype=np.complex128)
    beta = np.block([[identity2, zero2], [zero2, -identity2]])
    alpha = np.block([[zero2, sigma_x], [sigma_x, zero2]])
    gamma5 = np.block([[zero2, identity2], [identity2, zero2]])
    beta8 = np.kron(beta, identity2)
    alpha8 = np.kron(alpha, identity2)
    pion8 = 1j * np.kron(beta @ gamma5, sigma_z)
    spacing = 0.4
    forward = -1j * HBARC * alpha8 / (2.0 * spacing) - HBARC * beta8 / (
        2.0 * spacing
    )
    backward = forward.conj().T
    onsite_wilson = HBARC * beta8 / spacing

    source = np.arange(1, 49, dtype=np.float64)
    spinor = (source[:24] + 1j * source[24:]).reshape(3, 8)
    spinor /= np.linalg.norm(spinor)

    def construct(zero: bool) -> np.ndarray:
        matrix = np.zeros((24, 24), dtype=np.complex128)
        for site in range(3):
            scalar = 0.0 if zero and site == 1 else M_Q
            pion = 0.0
            block = onsite_wilson + scalar * beta8 + pion * pion8
            site_slice = slice(8 * site, 8 * (site + 1))
            matrix[site_slice, site_slice] += block
            adjacent = (site + 1) % 3
            adjacent_slice = slice(8 * adjacent, 8 * (adjacent + 1))
            matrix[site_slice, adjacent_slice] += forward
            matrix[adjacent_slice, site_slice] += backward
        return matrix

    def currents(matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        derivative = np.zeros(3, dtype=np.float64)
        bonds = np.zeros((3, 3), dtype=np.float64)
        for x in range(3):
            xs = slice(8 * x, 8 * (x + 1))
            for y in range(3):
                ys = slice(8 * y, 8 * (y + 1))
                expectation = np.vdot(spinor[x], matrix[xs, ys] @ spinor[y])
                derivative[x] += 2.0 * expectation.imag
                if x != y:
                    bonds[x, y] = -2.0 * expectation.imag
        continuity = derivative + np.sum(bonds, axis=1)
        return (
            derivative,
            bonds,
            float(np.max(np.abs(continuity))),
            float(np.max(np.abs(bonds + bonds.T))),
        )

    zero_h = construct(True)
    vacuum_h = construct(False)
    zero_dot, zero_bonds, zero_continuity, zero_antisymmetry = currents(zero_h)
    vacuum_dot, vacuum_bonds, vacuum_continuity, vacuum_antisymmetry = currents(vacuum_h)
    result = {
        "zero_density_derivative": zero_dot,
        "vacuum_density_derivative": vacuum_dot,
        "zero_continuity_residual": zero_continuity,
        "vacuum_continuity_residual": vacuum_continuity,
        "zero_bond_antisymmetry": zero_antisymmetry,
        "vacuum_bond_antisymmetry": vacuum_antisymmetry,
        "zero_vs_vacuum_density_derivative_max_abs": float(
            np.max(np.abs(zero_dot - vacuum_dot))
        ),
        "hermiticity_error": max(
            float(np.max(np.abs(zero_h - zero_h.conj().T))),
            float(np.max(np.abs(vacuum_h - vacuum_h.conj().T))),
        ),
    }
    arrays = {
        "current_spinor": spinor,
        "current_zero_hamiltonian": zero_h,
        "current_vacuum_hamiltonian": vacuum_h,
        "current_zero_currents": zero_bonds,
        "current_vacuum_currents": vacuum_bonds,
    }
    return result, arrays


def reconstruct_vacuum() -> dict[str, Any]:
    radial = F_PI**2
    first_sigma = LAMBDA * (radial - V_SQ) * F_PI - H_BREAK
    first_pion = 0.0
    derivative_dimensionless = max(abs(first_sigma), abs(first_pion)) / max(
        abs(H_BREAK), 1.0
    )
    pion_hessian = LAMBDA * (radial - V_SQ)
    sigma_hessian = LAMBDA * (3.0 * F_PI**2 - V_SQ)
    scalar_zero, pion_zero, scalar_d, pion_d = profile_fields(0.5, 1.0, 0.0)
    zero_density = (
        F_PI**2 / (2.0 * HBARC) * (float(scalar_d) ** 2 + float(pion_d) ** 2)
        + float(potential_delta(scalar_zero, pion_zero)) / HBARC**3
    )
    return {
        "first_sigma_mev3": float(first_sigma),
        "first_pion_mev3": first_pion,
        "first_derivative_dimensionless_max_abs": float(derivative_dimensionless),
        "pion_mass_relative_error": abs(math.sqrt(pion_hessian) - M_PI) / M_PI,
        "sigma_mass_relative_error": abs(math.sqrt(sigma_hessian) - M_SIGMA) / M_SIGMA,
        "zero_energy_density_mev_per_fm3": zero_density,
        "zero_finite": math.isfinite(zero_density),
    }


def reconstruct_cosmology() -> dict[str, Any]:
    zeta3 = float(scipy.special.zeta(3.0, 1.0))
    density_gamma = 2.0 * zeta3 / math.pi**2 * (156.5 / HBARC) ** 3
    density_b = 6.0e-10 * density_gamma
    spacing = density_b ** (-1.0 / 3.0)
    per_box = density_b * 125.0
    planck = 1.220890e19
    hbar_gev_s = 6.582119569e-25
    strong_time = 2.0e-15 / 299792458.0
    ratios = []
    for temperature_mev in (155.0, 158.0):
        for g_star in (17.25, 61.75):
            h_gev = 1.66 * math.sqrt(g_star) * (temperature_mev / 1000.0) ** 2 / planck
            ratios.append((1.0 / (h_gev / hbar_gev_s)) / strong_time)
    return {
        "photon_density_fm_minus3": density_gamma,
        "net_baryon_density_fm_minus3": density_b,
        "mean_net_baryon_spacing_fm": spacing,
        "expected_net_baryons_per_five_fm_box": per_box,
        "five_fm_boxes_per_net_baryon": 1.0 / per_box,
        "minimum_hubble_to_strong_time_ratio": min(ratios),
    }


def locate_primary_endpoint_row(primary: dict[str, Any], radius: float) -> dict[str, Any]:
    rows = primary["endpoint_radius_scan"]["rows"]
    return min(rows, key=lambda row: abs(float(row["radius_fm"]) - radius))


def verify(input_path: Path, output_dir: Path) -> int:
    input_path = input_path.resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite evidence in {output_dir}")
    output_dir.mkdir(parents=True)
    source_dir = output_dir / "sources"
    source_dir.mkdir()
    shutil.copy2(PROTOCOL, source_dir / PROTOCOL.name)
    shutil.copy2(SELF, source_dir / SELF.name)

    primary = json.loads(input_path.read_text(encoding="utf-8"))
    primary_dir = input_path.parent
    primary_array_path = ROOT / primary["artifacts"]["arrays"]["path"]
    protocol_snapshot_path = ROOT / primary["sources"]["snapshots"]["protocol"]["path"]
    primary_snapshot_path = ROOT / primary["sources"]["snapshots"]["primary"]["path"]

    checks: list[dict[str, Any]] = []
    checks.append(check("primary_schema", primary.get("schema") == PRIMARY_SCHEMA))
    checks.append(check("primary_completed", primary.get("completed") is True))
    checks.append(check("primary_failure_absent", primary.get("failure") is None))
    checks.append(
        check(
            "protocol_live_identity",
            file_identity(PROTOCOL)["sha256"] == primary["protocol"]["sha256"]
            and file_identity(PROTOCOL)["bytes"] == primary["protocol"]["bytes"],
        )
    )
    checks.append(
        check(
            "protocol_snapshot_identity",
            sha256_bytes(protocol_snapshot_path.read_bytes())
            == primary["protocol"]["sha256"],
        )
    )
    checks.append(
        check(
            "primary_snapshot_identity",
            sha256_bytes(primary_snapshot_path.read_bytes())
            == primary["sources"]["primary"]["sha256"],
        )
    )
    checks.append(
        check(
            "primary_array_identity",
            sha256_bytes(primary_array_path.read_bytes())
            == primary["artifacts"]["arrays"]["sha256"]
            and primary_array_path.stat().st_size
            == primary["artifacts"]["arrays"]["bytes"],
        )
    )

    expected_constants = {
        "n_c": NC,
        "f_pi_mev": F_PI,
        "m_pi_mev": M_PI,
        "m_sigma_mev": M_SIGMA,
        "m_q_mev": M_Q,
        "lambda": LAMBDA,
        "v_sq_mev2": V_SQ,
        "h_break_mev3": H_BREAK,
        "hbar_c_mev_fm": HBARC,
    }
    for name, expected in expected_constants.items():
        actual = primary["constants"][name]
        checks.append(
            check(
                f"constant_{name}",
                math.isclose(float(actual), float(expected), rel_tol=1.0e-14, abs_tol=1.0e-14),
                {"expected": expected, "actual": actual},
            )
        )

    vacuum = reconstruct_vacuum()
    current, current_arrays = reconstruct_current()
    cosmology = reconstruct_cosmology()
    primary_arrays = np.load(primary_array_path, allow_pickle=False)
    for name, reconstructed in current_arrays.items():
        actual = primary_arrays[name]
        checks.append(
            check(
                f"array_{name}",
                actual.shape == reconstructed.shape
                and np.max(np.abs(actual - reconstructed)) < 1.0e-13,
                {
                    "shape": list(actual.shape),
                    "max_abs_difference": float(np.max(np.abs(actual - reconstructed))),
                },
            )
        )

    checks.extend(
        [
            check(
                "vacuum_first_derivative",
                vacuum["first_derivative_dimensionless_max_abs"] < 1.0e-10,
                vacuum,
            ),
            check(
                "vacuum_masses",
                vacuum["pion_mass_relative_error"] < 1.0e-8
                and vacuum["sigma_mass_relative_error"] < 1.0e-8,
                vacuum,
            ),
            check("zero_energy_finite", vacuum["zero_finite"], vacuum),
            check(
                "current_hermiticity",
                current["hermiticity_error"] < 1.0e-12,
                current,
            ),
            check(
                "current_continuity",
                current["zero_continuity_residual"] < 1.0e-12
                and current["vacuum_continuity_residual"] < 1.0e-12,
                current,
            ),
            check(
                "current_bond_antisymmetry",
                current["zero_bond_antisymmetry"] < 1.0e-12
                and current["vacuum_bond_antisymmetry"] < 1.0e-12,
                current,
            ),
            check(
                "current_zero_regular",
                current["zero_vs_vacuum_density_derivative_max_abs"] < 1.0e-12,
                current,
            ),
        ]
    )

    selected_radius = float(primary["measurements"]["selected_radius_fm"])
    requested_points = [
        {"name": "endpoint", "a": 1.0, "radius_fm": selected_radius},
        {"name": "radius_0p50", "a": 1.0, "radius_fm": 0.50},
        {"name": "radius_0p55", "a": 1.0, "radius_fm": 0.55},
        {"name": "radius_0p60", "a": 1.0, "radius_fm": 0.60},
        {"name": "zero_amplitude_crossing", "a": 0.50, "radius_fm": selected_radius},
        {"name": "intermediate_amplitude", "a": 0.75, "radius_fm": selected_radius},
    ]
    shooting_rows: list[dict[str, Any]] = []
    shooting_arrays: dict[str, np.ndarray] = {}
    for point in requested_points:
        spectrum = independent_spectrum(point["a"], point["radius_fm"])
        meson = independent_meson_energy(point["a"], point["radius_fm"])
        selected_shooting = spectrum["selected"]
        if point["name"].startswith("radius_"):
            primary_row = locate_primary_endpoint_row(primary, point["radius_fm"])
        elif point["name"] == "endpoint":
            primary_row = primary["endpoint_refinement"]["selected"]
        else:
            primary_row = min(
                primary["fixed_radius_amplitude_scan"]["rows"],
                key=lambda row: abs(float(row["a"]) - point["a"]),
            )
        independent_bound = selected_shooting is not None
        independent_level = (
            float(selected_shooting["energy_mev"]) if independent_bound else M_Q
        )
        independent_total = 3.0 * independent_level + meson["total_mev"]
        primary_level = float(primary_row["level_mev"])
        energy_tolerance = max(0.5, 0.002 * abs(independent_level))
        level_agreement = (
            independent_bound == bool(primary_row["bound_state"])
            and abs(independent_level - primary_level) <= energy_tolerance
        )
        meson_relative = abs(meson["total_mev"] - float(primary_row["meson_mev"])) / max(
            abs(meson["total_mev"]), 1.0
        )
        shooting_row = {
            **point,
            "scan_count": spectrum["scan_count"],
            "failed_scan_integrations": spectrum["failed_scan_integrations"],
            "brackets": spectrum["brackets"],
            "root_energies_mev": [row["energy_mev"] for row in spectrum["roots"]],
            "root_nodes_h": [row["nodes_h"] for row in spectrum["roots"]],
            "independent_bound_state": independent_bound,
            "independent_level_mev": independent_level,
            "independent_rms_fm": (
                None if selected_shooting is None else selected_shooting["rms_fm"]
            ),
            "independent_tail_probability_r_ge_8fm": (
                None
                if selected_shooting is None
                else selected_shooting["tail_probability_r_ge_8fm"]
            ),
            "independent_meson": meson,
            "independent_total_mev": independent_total,
            "primary_level_mev": primary_level,
            "primary_meson_mev": float(primary_row["meson_mev"]),
            "level_tolerance_mev": energy_tolerance,
            "level_absolute_difference_mev": abs(independent_level - primary_level),
            "level_agreement": level_agreement,
            "meson_relative_difference": meson_relative,
            "meson_agreement": meson_relative <= 0.0005,
        }
        shooting_rows.append(shooting_row)
        safe_name = point["name"]
        shooting_arrays[f"{safe_name}_scan_energy_mev"] = spectrum["scan_energy_mev"]
        shooting_arrays[f"{safe_name}_scan_residual"] = spectrum["scan_residual"]
        if selected_shooting is not None:
            shooting_arrays[f"{safe_name}_radial_fm"] = selected_shooting["radial_fm"]
            shooting_arrays[f"{safe_name}_h"] = selected_shooting["h_normalized"]
            shooting_arrays[f"{safe_name}_j"] = selected_shooting["j_normalized"]
            shooting_arrays[f"{safe_name}_probability"] = selected_shooting[
                "radial_probability_density"
            ]

    radius_rows = [
        next(row for row in shooting_rows if row["name"] == name)
        for name in ("radius_0p50", "radius_0p55", "radius_0p60")
    ]
    radius_values = np.array([row["radius_fm"] for row in radius_rows], dtype=np.float64)
    total_values = np.array([row["independent_total_mev"] for row in radius_rows])
    quadratic = np.polyfit(radius_values, total_values, 2)
    independent_radius = float(-quadratic[1] / (2.0 * quadratic[0]))
    radius_qualified = bool(quadratic[0] > 0.0 and 0.50 <= independent_radius <= 0.60)
    radius_difference = abs(independent_radius - selected_radius)
    endpoint_row = shooting_rows[0]

    all_source_and_array_checks = all(row["passed"] for row in checks)
    qmc1_pass = bool(
        all_source_and_array_checks
        and primary["gate_inputs"]["QMC1"]["passed"] is True
    )
    primary_qmc2 = primary["gate_inputs"]["QMC2"]
    qmc2_checks = {
        "qmc1": qmc1_pass,
        "endpoint_bound_state": endpoint_row["independent_bound_state"],
        "endpoint_nodeless": endpoint_row["independent_bound_state"],
        "branch_overlap": primary_qmc2["minimum_adjacent_branch_overlap"] > 0.70,
        "same_sign_gap": primary_qmc2["endpoint_same_sign_gap_mev"] is not None
        and primary_qmc2["endpoint_same_sign_gap_mev"] > 1.0,
        "grid_convergence": primary_qmc2[
            "finest_two_level_relative_difference"
        ]
        is not None
        and primary_qmc2["finest_two_level_relative_difference"] <= 0.02,
        "all_finite": primary_qmc2["all_finite"] is True,
        "shooting_integrations": all(
            row["failed_scan_integrations"] == 0 for row in shooting_rows
        ),
        "primary_independent_levels": all(row["level_agreement"] for row in shooting_rows),
        "primary_independent_mesons": all(row["meson_agreement"] for row in shooting_rows),
        "selected_radius": radius_qualified and radius_difference <= 0.02,
        "endpoint_total": abs(
            endpoint_row["independent_total_mev"]
            - float(primary["measurements"]["selected_total_mev"])
        )
        <= 2.0,
    }
    qmc2_pass = all(qmc2_checks.values())

    primary_qmc3 = primary["gate_inputs"]["QMC3"]
    independent_binding_margin = 3.0 * M_Q - endpoint_row["independent_total_mev"]
    if qmc2_pass and all(
        [
            primary_qmc3["qualified_interior"] is True,
            independent_binding_margin >= 5.0,
            primary_qmc3["radial_curvature_mev_per_fm2"] > 0.0,
            endpoint_row["independent_rms_fm"] is not None,
            0.2 <= endpoint_row["independent_rms_fm"] <= 1.5,
            primary_qmc3["endpoint_total_relative_difference"] <= 0.05,
        ]
    ):
        qmc3_verdict = "SUPPORTS"
    elif (
        radius_qualified
        and endpoint_row["independent_total_mev"] >= 3.0 * M_Q
    ):
        qmc3_verdict = "CONTRADICTS"
    else:
        qmc3_verdict = "INCONCLUSIVE"

    barrier = float(primary["formation_envelope"]["barrier_above_three_quark_threshold_mev"])
    if qmc3_verdict == "SUPPORTS" and barrier <= 155.0:
        qmc4_verdict = "SUPPORTS"
    elif qmc3_verdict == "CONTRADICTS":
        qmc4_verdict = "CONTRADICTS"
    else:
        qmc4_verdict = "INCONCLUSIVE"

    primary_cosmology = primary["cosmological_initial_conditions"]
    cosmology_comparisons = {
        key: abs(float(primary_cosmology[key]) - float(cosmology[key]))
        for key in (
            "photon_density_fm_minus3",
            "net_baryon_density_fm_minus3",
            "mean_net_baryon_spacing_fm",
            "expected_net_baryons_per_five_fm_box",
            "five_fm_boxes_per_net_baryon",
            "minimum_hubble_to_strong_time_ratio",
        )
    }
    qmc5_pass = bool(
        all(
            difference
            <= 1.0e-12
            * max(abs(float(cosmology[key])), 1.0)
            for key, difference in cosmology_comparisons.items()
        )
        and cosmology["expected_net_baryons_per_five_fm_box"] < 1.0e-6
        and cosmology["five_fm_boxes_per_net_baryon"] > 1.0e6
        and cosmology["minimum_hubble_to_strong_time_ratio"] > 1.0e12
    )

    qmc6_requirements = primary["gate_inputs"]["QMC6"]["requirements"]
    qmc6_pass = all(bool(value) for value in qmc6_requirements.values())
    verdicts = {
        "QMC1": "PASS" if qmc1_pass else "FAIL",
        "QMC2": "PASS" if qmc2_pass else "FAIL",
        "QMC3": qmc3_verdict,
        "QMC4": qmc4_verdict,
        "QMC5": "PASS" if qmc5_pass else "FAIL",
        "QMC6": "PASS" if qmc6_pass else "FAIL",
    }

    array_path = output_dir / "verification_arrays.npz"
    np.savez_compressed(array_path, **shooting_arrays)
    array_identity = {
        "path": array_path.relative_to(ROOT).as_posix(),
        "sha256": sha256_bytes(array_path.read_bytes()),
        "bytes": array_path.stat().st_size,
    }
    primary_identity = file_identity(input_path)
    payload = {
        "schema": SCHEMA,
        "completed": True,
        "scientific_execution_started": True,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "executable": sys.executable,
        },
        "sources": {
            "protocol": file_identity(PROTOCOL),
            "independent": file_identity(SELF),
            "primary_receipt": primary_identity,
            "primary_source_snapshot": file_identity(primary_snapshot_path),
            "protocol_snapshot": file_identity(protocol_snapshot_path),
        },
        "checks": checks,
        "vacuum_and_zero": vacuum,
        "current_control": current,
        "cosmological_initial_conditions": cosmology,
        "cosmology_absolute_differences": cosmology_comparisons,
        "shooting_points": shooting_rows,
        "independent_radius_reconstruction": {
            "input_radius_fm": radius_values,
            "input_total_mev": total_values,
            "quadratic_coefficients": quadratic,
            "qualified": radius_qualified,
            "selected_radius_fm": independent_radius,
            "primary_selected_radius_fm": selected_radius,
            "absolute_difference_fm": radius_difference,
        },
        "measurements": {
            "independent_endpoint_level_mev": endpoint_row["independent_level_mev"],
            "independent_endpoint_meson_mev": endpoint_row["independent_meson"][
                "total_mev"
            ],
            "independent_endpoint_total_mev": endpoint_row["independent_total_mev"],
            "independent_binding_margin_mev": independent_binding_margin,
            "independent_endpoint_rms_fm": endpoint_row["independent_rms_fm"],
            "primary_envelope_barrier_mev": barrier,
        },
        "gate_inputs": {
            "QMC1": {"all_checks_passed": qmc1_pass},
            "QMC2": qmc2_checks,
            "QMC3": {
                "qmc2_pass": qmc2_pass,
                "independent_binding_margin_mev": independent_binding_margin,
                "radius_qualified": radius_qualified,
                "radial_curvature_mev_per_fm2": primary_qmc3[
                    "radial_curvature_mev_per_fm2"
                ],
                "independent_rms_fm": endpoint_row["independent_rms_fm"],
            },
            "QMC4": {"qmc3": qmc3_verdict, "barrier_mev": barrier},
            "QMC5": {"passed": qmc5_pass},
            "QMC6": {"requirements": qmc6_requirements, "passed": qmc6_pass},
        },
        "verdicts": verdicts,
        "exact_verdict_agreement": False,
        "complete_physical_matter_formation": qmc6_pass,
        "artifacts": {"arrays": array_identity},
        "failure": None,
    }
    payload["exact_verdict_agreement"] = (
        payload["verdicts"]["QMC1"] == primary["primary_verdicts"]["QMC1"]
        and payload["verdicts"]["QMC5"] == primary["primary_verdicts"]["QMC5"]
        and payload["verdicts"]["QMC6"] == primary["primary_verdicts"]["QMC6"]
    )
    result_path = output_dir / "verification.json"
    write_json(result_path, payload)
    print(
        json.dumps(
            {
                "result": result_path.relative_to(ROOT).as_posix(),
                "independent_endpoint_level_mev": endpoint_row[
                    "independent_level_mev"
                ],
                "independent_selected_radius_fm": independent_radius,
                "independent_binding_margin_mev": independent_binding_margin,
                "qmc2_failed_checks": [
                    name for name, passed in qmc2_checks.items() if not passed
                ],
                "verdicts": verdicts,
                "complete_physical_matter_formation": qmc6_pass,
            },
            indent=2,
            allow_nan=False,
        )
    )
    return 0 if qmc1_pass and qmc5_pass else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()
    if not arguments.input.exists():
        print(f"MissingPrimaryReceipt: {arguments.input}", file=sys.stderr)
        raise SystemExit(2)
    try:
        raise SystemExit(verify(arguments.input, arguments.output_dir))
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        raise
