#!/usr/bin/env python3
"""Independent NumPy verifier for the nonlinear composition-to-density receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTE = ROOT / "computations" / "matter-formation-continuum-report.md"
DEFAULT_SOLVER = ROOT / "two-fluid" / "cassi_two_fluid_3d_gpu.py"
PRIMARY_SOURCE = "source_primary.py"
SOLVER_SOURCE = "source_solver.py"
PROTOCOL_SOURCE = "frozen_protocol.txt"
PROTOCOL_SHA256 = "280f63358968c9bc8d7852e9b1a5482e130150141b4932e62f525ac68ff62c9a"
SOLVER_CANONICAL_SHA256 = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
SCHEMA = "matter-formation-chemotactic-transfer-verification-v1"
VERDICT = "SUPPORTS—nonlinear composition-to-density transfer in the base solver"
INCONCLUSIVE = "INCONCLUSIVE"
HEADING = "### 23.2 Nonlinear transfer calculation: pre-execution criteria\n"
PHI = (1.0 + math.sqrt(5.0)) / 2.0
L = 2.0 * math.pi
D = 0.03
NU = 0.02
LAM = 0.2
RHO0 = 2.0
R = 0.2
AMPLITUDE = 0.8
CHI_YANG = 0.4 / PHI
T_FINAL = 20.0
GAMMA = (1.0 + PHI) * LAM
CASES = (("forward", 1.0, 0.4), ("reverse", -1.0, 0.4), ("balanced", 0.0, 0.4), ("disabled", 1.0, 0.0))
TRAJECTORIES = (
    ("forward_n16_dt002", "forward", 16, 0.02),
    ("forward_n16_dt001", "forward", 16, 0.01),
    ("forward_n16_dt0005", "forward", 16, 0.005),
    ("forward_n32_dt001", "forward", 32, 0.01),
    ("reverse_n16_dt001", "reverse", 16, 0.01),
    ("balanced_n16_dt001", "balanced", 16, 0.01),
    ("disabled_n16_dt001", "disabled", 16, 0.01),
)
CASE_MAP = {name: (sigma, chi) for name, sigma, chi in CASES}
TRAJ_MAP = {name: (case, n, dt) for name, case, n, dt in TRAJECTORIES}


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def raw_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return safe(value.item())
    if isinstance(value, np.ndarray):
        return [safe(v) for v in value.tolist()]
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    return value


def finite(value: Any) -> bool:
    try:
        return not isinstance(value, bool) and math.isfinite(float(value))
    except (TypeError, ValueError, OverflowError):
        return False


def close(a: Any, b: Any, tol: float = 1.0e-12) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= tol * max(1.0, abs(float(a)), abs(float(b)))


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(safe(payload), ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def protocol_section(note: Path) -> bytes:
    text = canonical_bytes(note).decode("utf-8")
    if text.count(HEADING) != 1:
        raise ValueError("frozen section heading is not unique")
    start = text.index(HEADING)
    tail = text[start + len(HEADING) :]
    boundary = re.search(r"\n(?=#{1,3} )", tail)
    end = start + len(HEADING) + (boundary.start() if boundary else len(tail))
    return (text[start:end].rstrip() + "\n").encode("utf-8")


def expected_k1_mask(n: int) -> tuple[np.ndarray, np.ndarray]:
    labels = np.fft.fftfreq(n, d=1.0 / n).astype(np.float32)
    k1 = (2.0 * np.pi * (labels * np.float32(1.0 / L))).astype(np.float64)
    cutoff = (2.0 / 3.0) * float(np.max(np.abs(k1)))
    mask = (np.abs(k1) < cutoff).astype(np.float64)
    return k1, mask


def finite_array(value: np.ndarray) -> bool:
    return value.dtype == np.dtype("float64") and bool(np.all(np.isfinite(value)))


def load_npz(path: Path, required: set[str], shapes: dict[str, tuple[int, ...]]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != required:
            raise ValueError(f"{path.name}: exact NPZ key set mismatch")
        arrays = {name: np.asarray(archive[name]) for name in archive.files}
    for name, value in arrays.items():
        if not finite_array(value):
            raise ValueError(f"{path.name}:{name}: requires finite float64")
        if value.shape != shapes[name]:
            raise ValueError(f"{path.name}:{name}: shape {value.shape}, expected {shapes[name]}")
    return arrays


def rhs_1d(ey: np.ndarray, ei: np.ndarray, k1: np.ndarray, mask: np.ndarray, chi: float) -> tuple[np.ndarray, np.ndarray]:
    """Population RHS reconstructed without importing either solver."""
    yh = np.fft.fft(np.asarray(ey, dtype=np.float64)).astype(np.complex128)
    ih = np.fft.fft(np.asarray(ei, dtype=np.float64)).astype(np.complex128)
    rh = np.fft.fft(np.asarray(ey + ei, dtype=np.float64)).astype(np.complex128)
    rh[0] = 0.0 + 0.0j
    denom = np.asarray(k1 * k1, dtype=np.float64).copy()
    denom[0] = 1.0
    phi_h = -rh / denom
    gradphi = np.fft.ifft((1j * k1.astype(np.complex128)) * phi_h).real
    conv = -LAM * (ey - PHI * ei)
    rhs_yh = -D * (k1 * k1) * yh + np.fft.fft(conv)
    rhs_ih = -D * (k1 * k1) * ih - np.fft.fft(conv)
    if chi != 0.0:
        rhs_yh = rhs_yh - 1j * k1 * np.fft.fft(CHI_YANG * ey * gradphi)
        rhs_ih = rhs_ih + 1j * k1 * np.fft.fft(chi * ei * gradphi)
    rhs_yh *= mask
    rhs_ih *= mask
    return np.fft.ifft(rhs_yh).real, np.fft.ifft(rhs_ih).real


def rk2_step(yh: np.ndarray, ih: np.ndarray, dt: float, k1: np.ndarray, mask: np.ndarray, chi: float) -> tuple[np.ndarray, np.ndarray]:
    ey = np.fft.ifft(yh).real
    ei = np.fft.ifft(ih).real
    ky, ki = rhs_1d(ey, ei, k1, mask, chi)
    y2 = yh + dt * np.fft.fft(ky)
    i2 = ih + dt * np.fft.fft(ki)
    ky2, ki2 = rhs_1d(np.fft.ifft(y2).real, np.fft.ifft(i2).real, k1, mask, chi)
    return yh + 0.5 * dt * (np.fft.fft(ky) + np.fft.fft(ky2)), ih + 0.5 * dt * (np.fft.fft(ki) + np.fft.fft(ki2))


def initial_profiles(n: int, sigma: float) -> tuple[np.ndarray, np.ndarray]:
    x = 2.0 * math.pi * np.arange(n, dtype=np.float64) / float(n)
    rho = RHO0 + R * np.cos(x)
    eps = sigma * AMPLITUDE * np.cos(2.0 * x)
    return (PHI * rho + eps) / (1.0 + PHI), (rho - eps) / (1.0 + PHI)


def exact_identities() -> list[dict[str, Any]]:
    """Reconstruct the general periodic budgets and exact witness integrals."""
    p = (1 + sp.sqrt(5)) / 2
    rho, eps, lam, d, chi, rho_bar, speed = sp.symbols(
        "rho eps lam D chi rho_bar u", real=True
    )
    ey = (p * rho + eps) / (1 + p)
    ei = (rho - eps) / (1 + p)
    conv = -lam * eps
    c = 1 / (1 + p)
    gamma = (1 + p) * lam
    x = sp.symbols("x", real=True)
    density, imbalance, potential = (sp.Function(name)(x) for name in ("r", "e", "P"))
    grad = lambda expression: sp.diff(expression, x)
    density_current = speed * density - d * grad(density) + chi / p * imbalance * grad(potential)
    imbalance_current = speed * imbalance - d * grad(imbalance) + chi * (density - c * imbalance) * grad(potential)
    density_rate = -grad(density_current)
    imbalance_rate = -grad(imbalance_current) - gamma * imbalance
    density_energy_current = (
        speed * (density - rho_bar) ** 2 / 2
        - d * (density - rho_bar) * grad(density)
        + chi / p * (density - rho_bar) * imbalance * grad(potential)
    )
    imbalance_energy_current = (
        speed * imbalance ** 2 / 2 - d * imbalance * grad(imbalance)
        + chi * imbalance * (density - c * imbalance) * grad(potential)
    )
    rr, aa, sigma = sp.symbols("r0 A sigma", real=True)
    rho_x = rho_bar + rr * sp.cos(x)
    eps_x = sigma * aa * sp.cos(2 * x)
    phi_x = -rr * sp.cos(x)
    mean = lambda expression: sp.integrate(expression, (x, 0, 2 * sp.pi)) / (2 * sp.pi)
    rho_budget = mean(-d * grad(rho_x) ** 2 + chi / p * eps_x * grad(rho_x) * grad(phi_x))
    eps_budget = mean(-d * grad(eps_x) ** 2 - gamma * eps_x ** 2 + chi * (rho_x - c * eps_x) * grad(eps_x) * grad(phi_x))
    exprs = [
        ("population_sum_reconstruction", ey + ei - rho),
        ("population_imbalance_reconstruction", ey - p * ei - eps),
        ("density_flux_transformation", -ey / p + ei + eps / p),
        ("imbalance_flux_transformation", ey / p + p * ei - (rho - c * eps)),
        ("conversion_sum", conv - conv),
        ("conversion_imbalance_rate", conv - p * (-conv) + gamma * eps),
        ("mean_density_divergence", density_rate + speed * grad(density) - d * grad(grad(density)) + chi / p * grad(imbalance * grad(potential))),
        ("mean_imbalance_divergence", imbalance_rate + gamma * imbalance + speed * grad(imbalance) - d * grad(grad(imbalance)) + chi * grad((density - c * imbalance) * grad(potential))),
        ("density_budget_product_rule", (density - rho_bar) * density_rate + grad(density_energy_current) + d * grad(density) ** 2 - chi / p * imbalance * grad(density) * grad(potential)),
        ("imbalance_budget_product_rule", imbalance * imbalance_rate + grad(imbalance_energy_current) + d * grad(imbalance) ** 2 + gamma * imbalance ** 2 - chi * (density - c * imbalance) * grad(imbalance) * grad(potential)),
        ("density_trigonometric_budget_integral", rho_budget - (-d * rr ** 2 / 2 + chi * sigma * aa * rr ** 2 / (4 * p))),
        ("imbalance_trigonometric_budget_integral", eps_budget - (-(2 * d + gamma / 2) * sigma ** 2 * aa ** 2 - chi * sigma * aa * rr ** 2 / 2)),
    ]
    out = []
    for name, expression in exprs:
        reduced = sp.simplify(expression)
        residual = 0.0 if reduced == 0 else float(abs(complex(sp.N(reduced, 40))))
        out.append({"name": name, "residual": residual, "passed": bool(reduced == 0)})
    return out


def expected_config() -> dict[str, float]:
    return {"L": L, "D": D, "nu": NU, "lam": LAM, "rho0": RHO0, "r": R, "amplitude": AMPLITUDE, "chi_yang": CHI_YANG, "T": T_FINAL}


def preflight(primary_dir: Path, note: Path, solver: Path) -> dict[str, Any]:
    if not primary_dir.is_dir():
        raise ValueError("primary directory is missing")
    receipt_path = primary_dir / "results.json"
    receipt = strict_json(receipt_path)
    if receipt.get("schema") != "matter-formation-chemotactic-transfer-v1":
        raise ValueError("primary schema mismatch")
    for key in ("provenance", "config", "identities", "rows", "trajectories", "qualification", "files"):
        if key not in receipt:
            raise ValueError(f"primary receipt missing {key}")
    provenance = receipt["provenance"]
    files = receipt["files"]
    if not isinstance(provenance, dict) or not isinstance(files, dict):
        raise ValueError("primary provenance/files must be objects")
    section = protocol_section(note)
    if hashlib.sha256(section).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("live frozen protocol hash mismatch")
    if not solver.is_file() or canonical_sha256(solver) != SOLVER_CANONICAL_SHA256:
        raise ValueError("live canonical solver hash mismatch")
    solver_raw = raw_sha256(solver)
    if provenance.get("protocol_sha256") != PROTOCOL_SHA256 or provenance.get("solver_canonical_sha256") != SOLVER_CANONICAL_SHA256 or provenance.get("solver_raw_sha256") != solver_raw:
        raise ValueError("primary provenance source identity mismatch")
    expected = [PROTOCOL_SOURCE, PRIMARY_SOURCE, SOLVER_SOURCE]
    expected += [f"witness_{case}.npz" for case, _, _ in CASES]
    expected += [f"trajectory_{tid}.npz" for tid, _, _, _ in TRAJECTORIES]
    for name in expected:
        if Path(name).name != name or name not in files:
            raise ValueError(f"missing file identity {name}")
        path = primary_dir / name
        if not path.is_file() or raw_sha256(path) != files[name]:
            raise ValueError(f"missing or hash-mismatched {name}")
    if (primary_dir / PROTOCOL_SOURCE).read_bytes() != section:
        raise ValueError("frozen protocol snapshot mismatch")
    if canonical_sha256(primary_dir / SOLVER_SOURCE) != SOLVER_CANONICAL_SHA256 or raw_sha256(primary_dir / SOLVER_SOURCE) != solver_raw:
        raise ValueError("solver snapshot identity mismatch")
    primary_snapshot = primary_dir / PRIMARY_SOURCE
    primary_canonical = canonical_sha256(primary_snapshot)
    primary_raw = raw_sha256(primary_snapshot)
    if provenance.get("primary_canonical_sha256") != primary_canonical or provenance.get("primary_raw_sha256") != primary_raw:
        raise ValueError("primary snapshot provenance mismatch")
    config = receipt["config"]
    if not isinstance(config, dict) or any(not close(config.get(key), value, 1.0e-14) for key, value in expected_config().items()):
        raise ValueError("primary config mismatch")
    if not isinstance(receipt["rows"], list) or len(receipt["rows"]) != len(CASES):
        raise ValueError("primary witness row set mismatch")
    for row, (case, _, _) in zip(receipt["rows"], CASES):
        if not isinstance(row, dict) or row.get("id") != case or row.get("array") != f"witness_{case}.npz":
            raise ValueError(f"primary witness metadata mismatch: {case}")
    if not isinstance(receipt["trajectories"], list) or len(receipt["trajectories"]) != len(TRAJECTORIES):
        raise ValueError("primary trajectory row set mismatch")
    for row, (tid, case, n, dt) in zip(receipt["trajectories"], TRAJECTORIES):
        if not isinstance(row, dict) or row.get("id") != tid or row.get("case") != case or row.get("N") != n or not close(row.get("dt"), dt, 1.0e-14) or row.get("array") != f"trajectory_{tid}.npz":
            raise ValueError(f"primary trajectory metadata mismatch: {tid}")
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for case, _, _ in CASES:
        arrays[f"witness_{case}.npz"] = load_npz(
            primary_dir / f"witness_{case}.npz",
            {"ey", "ei", "ey_dot", "ei_dot", "u_dot", "k1", "mask"},
            {"ey": (16, 16, 16), "ei": (16, 16, 16), "ey_dot": (16, 16, 16), "ei_dot": (16, 16, 16), "u_dot": (3, 16, 16, 16), "k1": (16,), "mask": (16,)},
        )
    for tid, _, n, dt in TRAJECTORIES:
        steps = int(round(T_FINAL / dt))
        arrays[f"trajectory_{tid}.npz"] = load_npz(
            primary_dir / f"trajectory_{tid}.npz",
            {"times", "k1", "mask", "ey", "ei", "rho_mean", "epsilon_mean", "velocity_max", "transverse_error", "minima"},
            {"times": (steps + 1,), "k1": (n,), "mask": (n,), "ey": (steps + 1, n), "ei": (steps + 1, n), "rho_mean": (steps + 1,), "epsilon_mean": (steps + 1,), "velocity_max": (steps + 1,), "transverse_error": (steps + 1,), "minima": (steps + 1, 2)},
        )
    return {"receipt": receipt, "provenance": provenance, "files": files, "arrays": arrays, "solver_raw": solver_raw, "primary_canonical": primary_canonical, "primary_raw": primary_raw}


def witness_rows(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    failures: list[str] = []
    for case, sigma, chi in CASES:
        a = data["arrays"][f"witness_{case}.npz"]
        k1, mask = expected_k1_mask(16)
        symbol_error = max(float(np.max(np.abs(a["k1"] - k1))), float(np.max(np.abs(a["mask"] - mask))))
        ey = a["ey"][0, 0, :]
        ei = a["ei"][0, 0, :]
        expected_ey, expected_ei = initial_profiles(16, sigma)
        initial_error = max(float(np.max(np.abs(a["ey"] - expected_ey))),
                            float(np.max(np.abs(a["ei"] - expected_ei))))
        rhs_y, rhs_i = rhs_1d(ey, ei, k1, mask, chi)
        expected_y = np.broadcast_to(rhs_y, a["ey_dot"].shape)
        expected_i = np.broadcast_to(rhs_i, a["ei_dot"].shape)
        source_error = max(
            float(np.max(np.abs(a["ey_dot"] - expected_y))) / max(1.0, float(np.max(np.abs(expected_y)))),
            float(np.max(np.abs(a["ei_dot"] - expected_i))) / max(1.0, float(np.max(np.abs(expected_i)))),
        )
        rho = a["ey"] + a["ei"]
        eps = a["ey"] - PHI * a["ei"]
        rho_dot = a["ey_dot"] + a["ei_dot"]
        eps_dot = a["ey_dot"] - PHI * a["ei_dot"]
        rho_mean = float(np.mean(rho))
        rho_budget = float(np.mean((rho - rho_mean) * rho_dot))
        eps_budget = float(np.mean(eps * eps_dot))
        rho_expected = -D * R * R / 2.0 + chi * sigma * AMPLITUDE * R * R / (4.0 * PHI)
        eps_expected = -(2.0 * D + GAMMA / 2.0) * sigma * sigma * AMPLITUDE * AMPLITUDE - chi * sigma * AMPLITUDE * R * R / 2.0
        budget_error = max(abs(rho_budget - rho_expected), abs(eps_budget - eps_expected))
        mean_rho_rate = float(abs(np.mean(rho_dot)))
        mean_epsilon_rate_residual = float(abs(np.mean(eps_dot) + GAMMA * np.mean(eps)))
        velocity_rate = float(np.max(np.abs(a["u_dot"])))
        passed = bool(initial_error <= 1.0e-10 and symbol_error <= 1.0e-12 and source_error <= 1.0e-10 and budget_error <= 1.0e-8 and mean_rho_rate <= 1.0e-12 and mean_epsilon_rate_residual <= 1.0e-12 and velocity_rate <= 1.0e-12 and ((case == "forward" and rho_budget > 0.0) or (case != "forward" and rho_budget < 0.0)))
        row = {"id": case, "array": f"witness_{case}.npz", "rho_budget": rho_budget, "epsilon_budget": eps_budget, "rho_budget_expected": rho_expected, "epsilon_budget_expected": eps_expected, "source_error": source_error, "budget_error": budget_error, "mean_rho_rate": mean_rho_rate, "mean_epsilon_rate_residual": mean_epsilon_rate_residual, "velocity_rate": velocity_rate, "passed": passed}
        rows.append(row)
        if not passed:
            failures.append(f"witness:{case}")
    return rows, failures


def trajectory_reconstruction(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]], list[str]]:
    summaries: list[dict[str, Any]] = []
    reconstructed: dict[str, dict[str, np.ndarray]] = {}
    failures: list[str] = []
    for tid, case, n, dt in TRAJECTORIES:
        sigma, chi = CASE_MAP[case]
        a = data["arrays"][f"trajectory_{tid}.npz"]
        k1, mask = expected_k1_mask(n)
        times = np.arange(int(round(T_FINAL / dt)) + 1, dtype=np.float64) * dt
        ey0, ei0 = initial_profiles(n, sigma)
        yh = np.fft.fft(ey0).astype(np.complex128)
        ih = np.fft.fft(ei0).astype(np.complex128)
        ey = np.empty_like(a["ey"])
        ei = np.empty_like(a["ei"])
        ey[0], ei[0] = ey0, ei0
        for j in range(1, len(times)):
            yh, ih = rk2_step(yh, ih, dt, k1, mask, chi)
            ey[j], ei[j] = np.fft.ifft(yh).real, np.fft.ifft(ih).real
        profile_error = max(
            float(np.max(np.abs(ey - a["ey"]))) / max(1.0, float(np.max(np.abs(a["ey"])))),
            float(np.max(np.abs(ei - a["ei"]))) / max(1.0, float(np.max(np.abs(a["ei"])))),
        )
        rho = ey + ei
        eps = ey - PHI * ei
        rho_mean = np.mean(rho, axis=1)
        eps_mean = np.mean(eps, axis=1)
        minima = np.column_stack((np.min(ey, axis=1), np.min(ei, axis=1)))
        independent_velocity = np.zeros(len(times), dtype=np.float64)
        independent_transverse = np.zeros(len(times), dtype=np.float64)
        mass_error = float(np.max(np.abs(rho_mean - RHO0)))
        mean_eps_error = float(np.max(np.abs(eps_mean - eps_mean[0] * np.exp(-GAMMA * times))))
        diag_error = max(
            float(np.max(np.abs(rho_mean - a["rho_mean"]))),
            float(np.max(np.abs(eps_mean - a["epsilon_mean"]))),
            float(np.max(np.abs(minima - a["minima"]))),
            float(np.max(np.abs(independent_velocity - a["velocity_max"]))),
            float(np.max(np.abs(independent_transverse - a["transverse_error"]))),
        )
        variance = np.mean((rho - rho_mean[:, None]) ** 2, axis=1)
        v0 = float(variance[0])
        ratio = variance / max(v0, np.finfo(float).tiny)
        imax = int(np.argmax(ratio))
        minimum_component = float(np.min(minima))
        maximum_velocity = float(np.max(a["velocity_max"]))
        transverse_error = float(np.max(a["transverse_error"]))
        endpoint_ratio = float(ratio[-1])
        passed = bool(profile_error <= 1.0e-9 and close(float(a["times"][0]), 0.0, 1.0e-14) and close(float(a["times"][-1]), T_FINAL, 1.0e-14) and np.max(np.abs(a["times"] - times)) <= 1.0e-12 and mass_error <= 1.0e-11 and mean_eps_error <= 1.0e-11 and minimum_component > 0.0 and maximum_velocity <= 1.0e-10 and transverse_error <= 1.0e-10 and diag_error <= 1.0e-10 and np.max(np.abs(a["k1"] - k1)) <= 1.0e-12 and np.max(np.abs(a["mask"] - mask)) <= 1.0e-12)
        summary = {"id": tid, "case": case, "N": n, "dt": dt, "array": f"trajectory_{tid}.npz", "mass_error": mass_error, "mean_epsilon_error": mean_eps_error, "minimum_component": minimum_component, "maximum_velocity": maximum_velocity, "transverse_error": transverse_error, "maximum_variance_ratio": float(np.max(ratio)), "maximum_variance_time": float(times[imax]), "endpoint_variance_ratio": endpoint_ratio, "endpoint_classification": "above_initial_at_endpoint" if endpoint_ratio > 1.0 else "at_or_below_initial_at_endpoint", "passed": passed}
        summaries.append(summary)
        reconstructed[tid] = {"times": times, "ey": ey, "ei": ei, "rho": rho, "variance": variance}
        if not passed:
            failures.append(f"trajectory:{tid}")
    return summaries, reconstructed, failures


def qualification(reconstructed: dict[str, dict[str, np.ndarray]]) -> tuple[dict[str, Any], list[str]]:
    c = reconstructed["forward_n16_dt002"]
    m = reconstructed["forward_n16_dt001"]
    f = reconstructed["forward_n16_dt0005"]
    n16 = reconstructed["forward_n16_dt001"]
    n32 = reconstructed["forward_n32_dt001"]
    coarse_medium = float(np.max(np.abs(np.concatenate((c["ey"][-1] - m["ey"][-1], c["ei"][-1] - m["ei"][-1])))))
    medium_fine = float(np.max(np.abs(np.concatenate((m["ey"][-1] - f["ey"][-1], m["ei"][-1] - f["ei"][-1])))))
    ratio = coarse_medium / medium_fine if medium_fine > 0.0 else 0.0
    common_y, common_i = n32["ey"][-1][::2], n32["ei"][-1][::2]
    common = np.concatenate((n16["ey"][-1] - common_y, n16["ei"][-1] - common_i))
    denominator = max(1.0, float(np.max(np.abs(np.concatenate((common_y, common_i))))))
    spatial = float(np.max(np.abs(common))) / denominator
    reverse = reconstructed["reverse_n16_dt001"]
    early_index = int(round(0.1 / 0.01))
    early_gain = float(m["variance"][early_index] - m["variance"][0])
    forward_reverse = float(m["variance"][early_index] - reverse["variance"][early_index])
    result = {"endpoint_difference_coarse_medium": coarse_medium, "endpoint_difference_medium_fine": medium_fine, "endpoint_difference_ratio": ratio, "spatial_endpoint_error": spatial, "forward_early_gain": early_gain, "forward_minus_reverse_early": forward_reverse, "passed": bool(3.5 <= ratio <= 4.5 and medium_fine > 1.0e-12 and spatial <= 5.0e-4 and early_gain > 1.0e-5 and forward_reverse > 1.0e-5)}
    return result, [] if result["passed"] else ["qualification"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently verify nonlinear chemotactic transfer receipt")
    parser.add_argument("--primary-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--note", default=str(DEFAULT_NOTE))
    parser.add_argument("--solver", default=str(DEFAULT_SOLVER))
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    primary_dir = Path(args.primary_dir).resolve()
    base: dict[str, Any] = {"schema": SCHEMA, "verdict": INCONCLUSIVE, "passed": False, "provenance": {}, "config": expected_config(), "identities": [], "rows": [], "trajectories": [], "qualification": {}, "files": {}}
    if output_dir.exists():
        print("output directory must be absent before invocation", file=sys.stderr)
        return 1
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
        snapshot = output_dir / "source_verifier.py"
        snapshot.write_bytes(Path(__file__).read_bytes())
        data = preflight(primary_dir, Path(args.note).resolve(), Path(args.solver).resolve())
        identities = exact_identities()
        rows, row_failures = witness_rows(data)
        trajectories, reconstructed, trajectory_failures = trajectory_reconstruction(data)
        qualification_result, qualification_failures = qualification(reconstructed)
        failures = [f"identity:{item['name']}" for item in identities if not item["passed"]] + row_failures + trajectory_failures + qualification_failures
        primary_receipt = primary_dir / "results.json"
        provenance = {"protocol_sha256": PROTOCOL_SHA256, "solver_canonical_sha256": SOLVER_CANONICAL_SHA256, "solver_raw_sha256": data["solver_raw"], "primary_canonical_sha256": data["primary_canonical"], "primary_raw_sha256": data["primary_raw"], "verifier_canonical_sha256": canonical_sha256(Path(__file__)), "verifier_raw_sha256": raw_sha256(Path(__file__)), "primary_receipt_raw_sha256": raw_sha256(primary_receipt), "python": sys.version.split()[0], "numpy": np.__version__, "torch": data["provenance"].get("torch")}
        files = dict(data["files"])
        files["source_verifier.py"] = raw_sha256(snapshot)
        result = {**base, "provenance": provenance, "identities": identities, "rows": rows, "trajectories": trajectories, "qualification": qualification_result, "files": files}
        result["passed"] = not failures
        result["verdict"] = VERDICT if result["passed"] else INCONCLUSIVE
        if failures:
            result["error"] = "; ".join(failures)
        write_json(output_dir / "results.json", result)
        return 0 if result["passed"] else 1
    except Exception as exc:
        base["error"] = str(exc)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            if not (output_dir / "source_verifier.py").exists():
                (output_dir / "source_verifier.py").write_bytes(Path(__file__).read_bytes())
            base["files"] = {"source_verifier.py": raw_sha256(output_dir / "source_verifier.py")}
            write_json(output_dir / "results.json", base)
        except Exception as write_exc:
            print(f"{exc}; unable to write failure receipt: {write_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
