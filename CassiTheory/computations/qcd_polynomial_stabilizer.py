#!/usr/bin/env python3
"""Run the preregistered regular polynomial chiral-stabilizer calculation.

Run from the CassiTheory repository root:
    python computations/qcd_polynomial_stabilizer.py
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import torch
from scipy.sparse.linalg import LinearOperator, eigsh


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "qcd-polynomial-stabilizer-prereg.md"
OUT_DIR = ROOT / "runs" / "20260910_qcd_polynomial_stabilizer" / "primary_recovery1"
RESULTS = OUT_DIR / "results.json"
FAILED_ATTEMPT = (
    ROOT / "runs" / "20260910_qcd_polynomial_stabilizer" / "primary" / "results.json"
)

F_PI_MEV = 93.0
M_PI_MEV = 138.0
M_SIGMA_MEV = 600.0
E_SKYRME = 4.25
HBARC_MEV_FM = 197.3269804
X_MAX = 18.0
GRID_INTERVALS = (256, 512, 1024)
SEED = 20260910

LAMBDA = (M_SIGMA_MEV**2 - M_PI_MEV**2) / (2.0 * F_PI_MEV**2)
MU2 = (M_PI_MEV / F_PI_MEV) ** 2
VBAR2 = 1.0 - MU2 / LAMBDA
ALPHA = LAMBDA / (4.0 * E_SKYRME**2)
BETA = MU2 / E_SKYRME**2
ENERGY_UNIT_MEV = 4.0 * math.pi * F_PI_MEV / E_SKYRME
LENGTH_UNIT_FM = HBARC_MEV_FM / (E_SKYRME * F_PI_MEV)

DTYPE = torch.float64
torch.set_default_dtype(DTYPE)
torch.manual_seed(SEED)
np.random.seed(SEED)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def initial_fields(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = np.linspace(0.0, X_MAX, n + 1, dtype=np.float64)
    f = np.empty_like(x)
    f[0] = math.pi
    f[1:] = 2.0 * np.arctan(1.0 / x[1:] ** 2)
    s = 1.0 - 0.15 * np.exp(-(x**2))
    s[0] = s[1]
    s[-1] = 1.0
    f[-1] = 0.0
    return x, s, f


def pack_fields(s: np.ndarray, f: np.ndarray) -> np.ndarray:
    n = len(s) - 1
    return np.concatenate((s[1:n], f[1:n])).astype(np.float64, copy=True)


def unpack_torch(z: torch.Tensor, n: int) -> tuple[torch.Tensor, torch.Tensor]:
    count = n - 1
    s_free = z[:count]
    f_free = z[count:]
    s = torch.cat((s_free[:1], s_free, z.new_ones(1)))
    f = torch.cat((z.new_tensor([math.pi]), f_free, z.new_zeros(1)))
    return s, f


def unpack_numpy(z: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray]:
    count = n - 1
    s_free = np.asarray(z[:count], dtype=np.float64)
    f_free = np.asarray(z[count:], dtype=np.float64)
    s = np.concatenate((s_free[:1], s_free, np.ones(1, dtype=np.float64)))
    f = np.concatenate((np.array([math.pi]), f_free, np.zeros(1, dtype=np.float64)))
    return s, f


def energy_torch(z: torch.Tensor, n: int) -> torch.Tensor:
    s, f = unpack_torch(z, n)
    dx = X_MAX / n
    x_mid = (torch.arange(n, dtype=z.dtype, device=z.device) + 0.5) * dx
    s_mid = 0.5 * (s[:-1] + s[1:])
    f_mid = 0.5 * (f[:-1] + f[1:])
    s_x = (s[1:] - s[:-1]) / dx
    f_x = (f[1:] - f[:-1]) / dx
    sin_f = torch.sin(f_mid)
    sin2 = sin_f.square()

    two = 0.5 * x_mid.square() * (s_x.square() + s_mid.square() * f_x.square())
    two = two + s_mid.square() * sin2
    four = s_mid.square() * sin2 * (
        s_x.square() + s_mid.square() * f_x.square()
    )
    four = four + s_mid.pow(4) * sin2.square() / (2.0 * x_mid.square())
    potential = x_mid.square() * (
        ALPHA * ((s_mid.square() - VBAR2).square() - (1.0 - VBAR2) ** 2)
        + BETA * (1.0 - s_mid * torch.cos(f_mid))
    )
    return dx * torch.sum(two + four + potential)


def components_numpy(s: np.ndarray, f: np.ndarray) -> dict[str, Any]:
    n = len(s) - 1
    dx = X_MAX / n
    x_mid = (np.arange(n, dtype=np.float64) + 0.5) * dx
    s_mid = 0.5 * (s[:-1] + s[1:])
    f_mid = 0.5 * (f[:-1] + f[1:])
    s_x = np.diff(s) / dx
    f_x = np.diff(f) / dx
    sin2 = np.sin(f_mid) ** 2

    two_density = 0.5 * (s_x**2 + s_mid**2 * f_x**2) + s_mid**2 * sin2 / x_mid**2
    four_density = (
        s_mid**2 * sin2 * (s_x**2 + s_mid**2 * f_x**2) / x_mid**2
        + s_mid**4 * sin2**2 / (2.0 * x_mid**4)
    )
    potential_density = (
        ALPHA * ((s_mid**2 - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
        + BETA * (1.0 - s_mid * np.cos(f_mid))
    )
    two = float(np.sum(x_mid**2 * two_density) * dx)
    four = float(np.sum(x_mid**2 * four_density) * dx)
    potential = float(np.sum(x_mid**2 * potential_density) * dx)
    total = two + four + potential
    return {
        "two_derivative": two,
        "quartic": four,
        "potential": potential,
        "total_dimensionless": total,
        "total_mev": total * ENERGY_UNIT_MEV,
        "peak_two_density": float(np.max(two_density)),
        "peak_quartic_density": float(np.max(four_density)),
        "peak_potential_density": float(np.max(np.abs(potential_density))),
        "all_finite": bool(
            np.all(np.isfinite(two_density))
            and np.all(np.isfinite(four_density))
            and np.all(np.isfinite(potential_density))
            and np.isfinite(total)
        ),
    }


def optimize_grid(
    n: int,
    initial_s: np.ndarray | None = None,
    initial_f: np.ndarray | None = None,
    label: str = "cold",
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray]:
    x, s_default, f_default = initial_fields(n)
    s0 = s_default if initial_s is None else np.asarray(initial_s, dtype=np.float64).copy()
    f0 = f_default if initial_f is None else np.asarray(initial_f, dtype=np.float64).copy()
    z0 = pack_fields(s0, f0)
    z = torch.tensor(z0, dtype=DTYPE, requires_grad=True)
    optimizer = torch.optim.LBFGS(
        [z],
        lr=1.0,
        max_iter=2000,
        max_eval=2500,
        tolerance_grad=1.0e-10,
        tolerance_change=1.0e-13,
        history_size=100,
        line_search_fn="strong_wolfe",
    )
    trace: dict[str, Any] = {
        "closure_calls": 0,
        "bounds_violated_during_search": False,
        "largest_abs_s_seen": 0.0,
        "f_min_seen": math.inf,
        "f_max_seen": -math.inf,
    }

    def closure() -> torch.Tensor:
        optimizer.zero_grad(set_to_none=True)
        value = energy_torch(z, n)
        if not bool(torch.isfinite(value)):
            raise FloatingPointError(f"nonfinite energy on {label} N={n}")
        value.backward()
        with torch.no_grad():
            s_now, f_now = unpack_torch(z, n)
            s_abs = float(torch.max(torch.abs(s_now)))
            f_min = float(torch.min(f_now))
            f_max = float(torch.max(f_now))
            trace["closure_calls"] += 1
            trace["largest_abs_s_seen"] = max(trace["largest_abs_s_seen"], s_abs)
            trace["f_min_seen"] = min(trace["f_min_seen"], f_min)
            trace["f_max_seen"] = max(trace["f_max_seen"], f_max)
            if s_abs >= 3.0 or f_min <= -math.pi or f_max >= 2.0 * math.pi:
                trace["bounds_violated_during_search"] = True
        return value

    initial_energy = float(energy_torch(z, n).detach())
    optimizer.step(closure)
    final_energy_tensor = energy_torch(z, n)
    gradient = torch.autograd.grad(final_energy_tensor, z)[0]
    final_z = z.detach().cpu().numpy().copy()
    s, f = unpack_numpy(final_z, n)
    parts = components_numpy(s, f)
    state = optimizer.state[z]

    max_grad = float(torch.max(torch.abs(gradient)).detach())
    s_drop = float(np.max(s[:-1] - s[1:]))
    f_rise = float(np.max(f[1:] - f[:-1]))
    result: dict[str, Any] = {
        "label": label,
        "n_intervals": n,
        "dx": X_MAX / n,
        "initial_energy_dimensionless": initial_energy,
        "energy": parts,
        "max_abs_gradient": max_grad,
        "optimizer_n_iter": int(state.get("n_iter", -1)),
        "optimizer_func_evals": int(state.get("func_evals", trace["closure_calls"])),
        "closure_calls": int(trace["closure_calls"]),
        "bounds_violated_during_search": bool(trace["bounds_violated_during_search"]),
        "largest_abs_s_seen": float(trace["largest_abs_s_seen"]),
        "f_min_seen": float(trace["f_min_seen"]),
        "f_max_seen": float(trace["f_max_seen"]),
        "s_min": float(np.min(s)),
        "s_max": float(np.max(s)),
        "f_min": float(np.min(f)),
        "f_max": float(np.max(f)),
        "max_s_monotonicity_violation": max(0.0, s_drop),
        "max_f_monotonicity_violation": max(0.0, f_rise),
        "boundary": {
            "s0_minus_s1": float(s[0] - s[1]),
            "sN_minus_one": float(s[-1] - 1.0),
            "f0_minus_pi": float(f[0] - math.pi),
            "fN": float(f[-1]),
        },
    }
    return result, x, s, f


def hessian_spectra(n: int, s: np.ndarray, f: np.ndarray, count: int) -> dict[str, Any]:
    z_np = pack_fields(s, f)
    size = z_np.size

    def hvp(v: np.ndarray) -> np.ndarray:
        z = torch.tensor(z_np, dtype=DTYPE, requires_grad=True)
        value = energy_torch(z, n)
        grad = torch.autograd.grad(value, z, create_graph=True)[0]
        direction = torch.tensor(np.asarray(v, dtype=np.float64), dtype=DTYPE)
        product = torch.autograd.grad(grad, z, grad_outputs=direction)[0]
        return product.detach().cpu().numpy()

    raw_operator = LinearOperator((size, size), matvec=hvp, rmatvec=hvp, dtype=np.float64)
    raw_values = eigsh(
        raw_operator,
        k=count,
        which="SA",
        tol=1.0e-8,
        maxiter=6000,
        return_eigenvectors=False,
    )
    raw_values = np.sort(np.asarray(raw_values, dtype=np.float64))

    dx = X_MAX / n
    node_weights = np.full(n + 1, dx, dtype=np.float64)
    node_weights[0] = node_weights[-1] = 0.5 * dx
    s_weights = node_weights[1:n].copy()
    s_weights[0] += node_weights[0]
    f_weights = node_weights[1:n] * s[1:n] ** 2
    metric = np.concatenate((s_weights, f_weights))
    if np.any(metric <= 0.0) or not np.all(np.isfinite(metric)):
        raise FloatingPointError(f"invalid Hessian metric on N={n}")
    inverse_sqrt = 1.0 / np.sqrt(metric)

    def generalized_hvp(v: np.ndarray) -> np.ndarray:
        scaled = inverse_sqrt * np.asarray(v, dtype=np.float64)
        return inverse_sqrt * hvp(scaled)

    generalized_operator = LinearOperator(
        (size, size),
        matvec=generalized_hvp,
        rmatvec=generalized_hvp,
        dtype=np.float64,
    )
    generalized_values = eigsh(
        generalized_operator,
        k=count,
        which="SA",
        tol=1.0e-8,
        maxiter=6000,
        return_eigenvectors=False,
    )
    generalized_values = np.sort(np.asarray(generalized_values, dtype=np.float64))
    return {
        "raw_nodal_eigenvalues": raw_values.tolist(),
        "generalized_eigenvalues": generalized_values.tolist(),
        "metric_min": float(np.min(metric)),
        "metric_max": float(np.max(metric)),
        "all_finite": bool(
            np.all(np.isfinite(raw_values)) and np.all(np.isfinite(generalized_values))
        ),
    }


def homotopy_rows(s: np.ndarray, f: np.ndarray) -> list[dict[str, Any]]:
    n = len(s) - 1
    dx = X_MAX / n
    x_mid = (np.arange(n, dtype=np.float64) + 0.5) * dx
    pion = s * np.sin(f)
    sigma = s * np.cos(f)
    rows: list[dict[str, Any]] = []
    for index in range(401):
        u = index / 400.0
        a = (1.0 - u) * pion
        b = (1.0 - u) * sigma + u
        a_mid = 0.5 * (a[:-1] + a[1:])
        b_mid = 0.5 * (b[:-1] + b[1:])
        a_x = np.diff(a) / dx
        b_x = np.diff(b) / dx
        radial_square = a_x**2 + b_x**2
        two_density = 0.5 * radial_square + a_mid**2 / x_mid**2
        four_density = (
            a_mid**2 * radial_square / x_mid**2
            + a_mid**4 / (2.0 * x_mid**4)
        )
        amplitude_square = a_mid**2 + b_mid**2
        potential_density = (
            ALPHA * ((amplitude_square - VBAR2) ** 2 - (1.0 - VBAR2) ** 2)
            + BETA * (1.0 - b_mid)
        )
        total = float(
            np.sum(x_mid**2 * (two_density + four_density + potential_density)) * dx
        )
        row = {
            "u": u,
            "energy_dimensionless": total,
            "energy_mev": total * ENERGY_UNIT_MEV,
            "minimum_nodal_amplitude": float(np.min(np.sqrt(a**2 + b**2))),
            "peak_two_density": float(np.max(two_density)),
            "peak_quartic_density": float(np.max(four_density)),
            "peak_abs_potential_density": float(np.max(np.abs(potential_density))),
            "all_finite": bool(
                np.isfinite(total)
                and np.all(np.isfinite(two_density))
                and np.all(np.isfinite(four_density))
                and np.all(np.isfinite(potential_density))
            ),
        }
        rows.append(row)
    return rows


def summarize_homotopy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    energies = np.array([row["energy_dimensionless"] for row in rows], dtype=np.float64)
    index = int(np.argmax(energies))
    start = float(energies[0])
    maximum = float(energies[index])
    return {
        "soliton_energy_dimensionless": start,
        "maximum_energy_dimensionless": maximum,
        "maximum_energy_mev": maximum * ENERGY_UNIT_MEV,
        "maximum_u": float(rows[index]["u"]),
        "barrier_dimensionless": maximum - start,
        "barrier_fraction": (maximum - start) / start if start != 0.0 else math.inf,
        "endpoint_energy_dimensionless": float(energies[-1]),
        "minimum_amplitude_over_path": float(
            min(row["minimum_nodal_amplitude"] for row in rows)
        ),
        "maximum_peak_two_density": float(max(row["peak_two_density"] for row in rows)),
        "maximum_peak_quartic_density": float(
            max(row["peak_quartic_density"] for row in rows)
        ),
        "maximum_peak_potential_density": float(
            max(row["peak_abs_potential_density"] for row in rows)
        ),
        "all_finite": bool(all(row["all_finite"] for row in rows)),
    }


def relative_change(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), np.finfo(np.float64).tiny)
    return abs(a - b) / scale


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grid_results: dict[int, dict[str, Any]] = {}
    fields: dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}

    for n in GRID_INTERVALS:
        result, x, s, f = optimize_grid(n, label="cold")
        grid_results[n] = result
        fields[n] = (x, s, f)
        print(
            f"N={n}: E={result['energy']['total_dimensionless']:.12g}, "
            f"max|grad|={result['max_abs_gradient']:.3e}, "
            f"s_min={result['s_min']:.6g}"
        )

    x512, s512, f512 = fields[512]
    x1024 = np.linspace(0.0, X_MAX, 1025, dtype=np.float64)
    warm_s = np.interp(x1024, x512, s512)
    warm_f = np.interp(x1024, x512, f512)
    warm_result, _, warm_s_final, warm_f_final = optimize_grid(
        1024, initial_s=warm_s, initial_f=warm_f, label="warm_from_512"
    )

    for n in GRID_INTERVALS:
        _, s, f = fields[n]
        count = 3 if n == 1024 else 6
        if grid_results[n]["max_abs_gradient"] >= 3.0e-7:
            grid_results[n]["hessian"] = {
                "status": "SKIPPED_NONSTATIONARY",
                "error": (
                    "The frozen optimization did not reach the RPS3 stationarity "
                    "threshold; a local-stability spectrum is undefined."
                ),
                "raw_nodal_eigenvalues": [],
                "generalized_eigenvalues": [],
                "all_finite": False,
            }
            print(f"N={n}: Hessian skipped because the field is nonstationary")
            continue
        print(f"N={n}: computing {count} lowest Hessian modes")
        try:
            spectrum = hessian_spectra(n, s, f, count)
            spectrum["status"] = "COMPLETED"
            grid_results[n]["hessian"] = spectrum
        except Exception as exc:
            grid_results[n]["hessian"] = {
                "status": "FAILED_EIGENSOLVE",
                "error": f"{type(exc).__name__}: {exc}",
                "raw_nodal_eigenvalues": [],
                "generalized_eigenvalues": [],
                "all_finite": False,
            }
            print(f"N={n}: Hessian eigensolve failed: {type(exc).__name__}: {exc}")

    homotopies: dict[int, dict[str, Any]] = {}
    for n in GRID_INTERVALS:
        x, s, f = fields[n]
        rows = homotopy_rows(s, f)
        summary = summarize_homotopy(rows)
        rows_path = OUT_DIR / f"homotopy_N{n}.json"
        rows_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        summary["rows_file"] = rows_path.relative_to(ROOT).as_posix()
        summary["rows_sha256"] = sha256(rows_path)
        homotopies[n] = summary
        arrays_path = OUT_DIR / f"fields_N{n}.npz"
        np.savez_compressed(arrays_path, x=x, s=s, f=f)
        grid_results[n]["fields_file"] = arrays_path.relative_to(ROOT).as_posix()
        grid_results[n]["fields_sha256"] = sha256(arrays_path)

    warm_arrays_path = OUT_DIR / "fields_N1024_warm_from_512.npz"
    np.savez_compressed(warm_arrays_path, x=x1024, s=warm_s_final, f=warm_f_final)
    warm_result["fields_file"] = warm_arrays_path.relative_to(ROOT).as_posix()
    warm_result["fields_sha256"] = sha256(warm_arrays_path)

    energy_256 = grid_results[256]["energy"]["total_dimensionless"]
    energy_512 = grid_results[512]["energy"]["total_dimensionless"]
    energy_1024 = grid_results[1024]["energy"]["total_dimensionless"]
    warm_energy = warm_result["energy"]["total_dimensionless"]
    energy_changes = {
        "N256_to_N512": relative_change(energy_256, energy_512),
        "N512_to_N1024": relative_change(energy_512, energy_1024),
        "N1024_cold_to_warm": relative_change(energy_1024, warm_energy),
    }

    hessian_complete = all(
        grid_results[n]["hessian"]["status"] == "COMPLETED"
        and len(grid_results[n]["hessian"]["generalized_eigenvalues"]) > 0
        for n in GRID_INTERVALS
    )
    lowest_hessian = {
        n: (
            float(grid_results[n]["hessian"]["generalized_eigenvalues"][0])
            if grid_results[n]["hessian"]["generalized_eigenvalues"]
            else None
        )
        for n in GRID_INTERVALS
    }
    hessian_changes = {
        "N256_to_N512": (
            relative_change(lowest_hessian[256], lowest_hessian[512])
            if hessian_complete
            else None
        ),
        "N512_to_N1024": (
            relative_change(lowest_hessian[512], lowest_hessian[1024])
            if hessian_complete
            else None
        ),
    }

    path_energy_changes = {
        "N256_to_N512": relative_change(
            homotopies[256]["maximum_energy_dimensionless"],
            homotopies[512]["maximum_energy_dimensionless"],
        ),
        "N512_to_N1024": relative_change(
            homotopies[512]["maximum_energy_dimensionless"],
            homotopies[1024]["maximum_energy_dimensionless"],
        ),
    }
    density_keys = (
        "maximum_peak_two_density",
        "maximum_peak_quartic_density",
        "maximum_peak_potential_density",
    )
    path_density_changes = {
        key: {
            "N256_to_N512": relative_change(homotopies[256][key], homotopies[512][key]),
            "N512_to_N1024": relative_change(homotopies[512][key], homotopies[1024][key]),
        }
        for key in density_keys
    }

    rps3_pass = bool(
        all(grid_results[n]["max_abs_gradient"] < 3.0e-7 for n in GRID_INTERVALS)
        and all(grid_results[n]["s_min"] > 0.02 for n in GRID_INTERVALS)
        and all(
            grid_results[n]["max_s_monotonicity_violation"] <= 1.0e-8
            and grid_results[n]["max_f_monotonicity_violation"] <= 1.0e-8
            and not grid_results[n]["bounds_violated_during_search"]
            and all(abs(value) == 0.0 for value in grid_results[n]["boundary"].values())
            for n in GRID_INTERVALS
        )
        and energy_changes["N256_to_N512"] < 8.0e-3
        and energy_changes["N512_to_N1024"] < 3.0e-3
        and energy_changes["N1024_cold_to_warm"] < 2.0e-5
    )
    all_generalized = [
        value
        for n in GRID_INTERVALS
        for value in grid_results[n]["hessian"]["generalized_eigenvalues"]
    ]
    rps4_pass = bool(
        hessian_complete
        and all(value > 1.0e-5 for value in all_generalized)
        and hessian_changes["N256_to_N512"] < 0.15
        and hessian_changes["N512_to_N1024"] < 0.10
    )
    rps5_primary_pass = bool(
        all(homotopies[n]["all_finite"] for n in GRID_INTERVALS)
        and path_energy_changes["N256_to_N512"] < 8.0e-3
        and path_energy_changes["N512_to_N1024"] < 3.0e-3
        and all(
            changes["N256_to_N512"] < 0.02
            and changes["N512_to_N1024"] < 0.01
            for changes in path_density_changes.values()
        )
        and homotopies[1024]["barrier_fraction"] >= 1.0e-3
    )

    receipt: dict[str, Any] = {
        "protocol": "qcd-polynomial-stabilizer",
        "protocol_status": "Preregistered",
        "attempt": "primary_recovery1",
        "recovery_scope": (
            "Preserve the failed ARPACK receipt and record skipped or failed "
            "Hessian solves without changing frozen physics inputs or decisions."
        ),
        "seed": SEED,
        "constants": {
            "f_pi_mev": F_PI_MEV,
            "m_pi_mev": M_PI_MEV,
            "m_sigma_mev": M_SIGMA_MEV,
            "e": E_SKYRME,
            "hbar_c_mev_fm": HBARC_MEV_FM,
            "lambda": LAMBDA,
            "mu_squared": MU2,
            "vbar_squared": VBAR2,
            "alpha": ALPHA,
            "beta": BETA,
            "energy_unit_mev": ENERGY_UNIT_MEV,
            "length_unit_fm": LENGTH_UNIT_FM,
            "x_max": X_MAX,
        },
        "grids": {str(n): grid_results[n] for n in GRID_INTERVALS},
        "warm_N1024": warm_result,
        "energy_relative_changes": energy_changes,
        "lowest_generalized_hessian": {str(k): v for k, v in lowest_hessian.items()},
        "hessian_relative_changes": hessian_changes,
        "homotopy": {str(n): homotopies[n] for n in GRID_INTERVALS},
        "homotopy_energy_relative_changes": path_energy_changes,
        "homotopy_peak_density_relative_changes": path_density_changes,
        "primary_gate_inputs": {
            "RPS3": "PASS" if rps3_pass else "FAIL",
            "RPS4": "PASS" if rps4_pass else "FAIL",
            "RPS5_without_independent_agreement": (
                "PASS" if rps5_primary_pass else "FAIL"
            ),
        },
        "final_verdicts": {
            "RPS1": "PENDING_INDEPENDENT_VERIFICATION",
            "RPS2": "PENDING_INDEPENDENT_VERIFICATION",
            "RPS3": "PASS" if rps3_pass else "FAIL",
            "RPS4": "PASS" if rps4_pass else "FAIL",
            "RPS5": "PENDING_INDEPENDENT_VERIFICATION",
            "RPS6": "PENDING_INDEPENDENT_VERIFICATION",
            "physical_completion": "FAIL",
        },
        "complete_physical_matter_formation": False,
        "hashes": {
            "protocol_sha256": sha256(PROTOCOL),
            "primary_source_sha256": sha256(Path(__file__).resolve()),
            "failed_attempt_receipt_sha256": sha256(FAILED_ATTEMPT),
        },
    }
    RESULTS.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt["primary_gate_inputs"], indent=2))
    print(f"wrote {RESULTS.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
