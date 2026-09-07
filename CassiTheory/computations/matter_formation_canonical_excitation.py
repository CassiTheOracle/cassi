#!/usr/bin/env python3
"""Primary CPU receipt producer for the frozen canonical excitation campaign."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "computations" / "matter-formation-continuum-report.md"
DEFAULT_SOLVER = ROOT / "two-fluid" / "cassi_two_fluid_3d_gpu.py"
SCHEMA = "matter-formation-canonical-excitation-v1"
PROTOCOL_SHA256 = "4c3d0eb3fd1739b8f01cdf0dabcddcc983755ebe41197d89300accc86aa6e98b"
SOLVER_CANONICAL_SHA256 = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
N = 16
L = 2.0 * math.pi
RHO0 = 2.0
LAMBDA = 0.2
D = 0.03
NU = 0.02
U = np.array([0.2, -0.1, 0.05], dtype=np.float64)
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
CASES = (
    {"id": "base_matched", "class": "Base", "chi": 0.4, "chi_yang": 0.4 / PHI, "lam": 0.2, "D": 0.03, "nu": 0.02},
    {"id": "base_attraction", "class": "Base", "chi": 0.4, "chi_yang": 0.0, "lam": 0.2, "D": 0.03, "nu": 0.02},
    {"id": "base_repulsion", "class": "Base", "chi": 0.4, "chi_yang": 0.4, "lam": 0.2, "D": 0.03, "nu": 0.02},
    {"id": "base_guard", "class": "Base", "chi": 0.0, "chi_yang": 0.4, "lam": 0.2, "D": 0.03, "nu": 0.02},
    {"id": "base_jordan", "class": "Base", "chi": 0.4, "chi_yang": (0.4 + (1.0 + PHI) ** 2 * LAMBDA / RHO0) / PHI, "lam": 0.2, "D": 0.03, "nu": 0.02},
    {"id": "expanding_gated", "class": "Expanding", "chi": 0.4, "chi_yang": 0.4 / PHI, "lam": 0.2, "D": 0.03, "nu": 0.02, "hyper_nu": 0.0004, "cs2": 0.7, "qi_gate": True},
    {"id": "expanding_ungated", "class": "Expanding", "chi": 0.4, "chi_yang": 0.4 / PHI, "lam": 0.2, "D": 0.03, "nu": 0.02, "hyper_nu": 0.0, "cs2": 0.7, "qi_gate": False},
    {"id": "expanding_transport", "class": "Expanding", "chi": 0.4, "chi_yang": 0.4 / PHI, "lam": 0.0, "D": 0.0, "nu": 0.0, "hyper_nu": 0.0, "cs2": 0.7, "qi_gate": True},
)
WAVEVECTORS = ((1, 0, 0), (1, 1, 0), (1, 1, 1), (0, 0, 0), (6, 0, 0))
AMPLITUDES = np.array([1.0e-3, 5.0e-4], dtype=np.float64)


class ContractError(RuntimeError):
    pass


def raw_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def canonical_sha256(data: bytes) -> str:
    return raw_sha256(canonical_bytes(data))


def protocol_bytes(report_bytes: bytes) -> bytes:
    text = canonical_bytes(report_bytes).decode("utf-8")
    matches = list(re.finditer(r"^### 21\.3 Canonical excitation calculation: pre-execution criteria\s*$", text, re.MULTILINE))
    if len(matches) != 1:
        raise ContractError("canonical protocol heading is not unique")
    start = matches[0].start()
    tail = text[matches[0].end():]
    nxt = re.search(r"^#{1,3}\s+", tail, re.MULTILINE)
    section = text[start:] if nxt is None else text[start:start + matches[0].end() - matches[0].start() + nxt.start()]
    return (section.rstrip() + "\n").encode("utf-8")


def finite_array(a: Any, label: str) -> np.ndarray:
    out = np.asarray(a)
    if not np.all(np.isfinite(out)):
        raise ContractError(f"nonfinite array: {label}")
    return out


def scalar_float(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ContractError(f"nonfinite scalar: {label}")
    return result


def jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [jsonable(v) for v in value.tolist()]
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, complex):
        return {"real": scalar_float(value.real, "complex.real"), "imag": scalar_float(value.imag, "complex.imag")}
    return value


def load_solver(path: Path):
    spec = importlib.util.spec_from_file_location("canonical_two_fluid_source", path)
    if spec is None or spec.loader is None:
        raise ContractError("cannot load canonical solver")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def transverse_basis(kvec: np.ndarray) -> np.ndarray:
    khat = kvec / np.linalg.norm(kvec)
    axes = np.eye(3, dtype=np.float64)
    axis = axes[int(np.argmin(np.abs(khat)))]
    b1 = np.cross(khat, axis)
    b1 /= np.linalg.norm(b1)
    b2 = np.cross(khat, b1)
    b2 /= np.linalg.norm(b2)
    return np.column_stack((b1, b2))


def phase_cos(k: tuple[int, int, int]) -> np.ndarray:
    x = np.arange(N, dtype=np.float64)[None, None, :]
    y = np.arange(N, dtype=np.float64)[None, :, None]
    z = np.arange(N, dtype=np.float64)[:, None, None]
    nx, ny, nz = k
    return np.cos(2.0 * math.pi * (nx * x + ny * y + nz * z) / N)


def coordinate_extract(components: list[Any], ey: Any, ei: Any, idx: tuple[int, int, int], basis: np.ndarray, zero: bool) -> np.ndarray:
    def coeff(arr: Any) -> complex:
        if zero:
            return complex((arr[0, 0, 0] / (N ** 3)).detach().cpu().numpy())
        return complex((2.0 * arr[idx] / (N ** 3)).detach().cpu().numpy())
    rho = coeff(ey) + coeff(ei)
    eps = coeff(ey) - PHI * coeff(ei)
    if zero:
        return np.array([rho, eps, coeff(components[0]), coeff(components[1]), coeff(components[2])], dtype=np.complex128)
    vel = np.array([coeff(c) for c in components], dtype=np.complex128)
    return np.array([rho, eps, np.dot(basis[:, 0], vel), np.dot(basis[:, 1], vel)], dtype=np.complex128)


def make_solver(module: Any, case: dict[str, Any]):
    common = dict(N=N, L=L, nu=case["nu"], D=case["D"], lam=case["lam"], chi=case["chi"], chi_yang=case["chi_yang"], device="cpu")
    if case["class"] == "Base":
        return module.TwoFluid3DGPU(**common)
    return module.ExpandingTwoFluid3DGPU(
        **common, H0=0.0, a0=1.0, hubble_mode="friedmann", h_smooth=1.0,
        max_H=4.0, qi_memory=False, wu_xing=False, hyper_nu=case["hyper_nu"],
        cs2=case["cs2"], qi_gate=case["qi_gate"], phi_inv2=0.382,
    )


def expected_matrix(case: dict[str, Any], source_k: np.ndarray, mask: float, zero: bool) -> np.ndarray:
    n = 5 if zero else 4
    out = np.zeros((n, n), dtype=np.complex128)
    if mask == 0.0:
        return out
    K = float(np.dot(source_k, source_k))
    omega = float(np.dot(source_k, U))
    D_case = case["D"]
    nu_case = case["nu"]
    if case["class"] == "Base":
        gamma = (1.0 + PHI) * case["lam"]
        b = float(case["chi"] != 0.0)
        s = b * RHO0 / (1.0 + PHI) * (case["chi"] - PHI * case["chi_yang"])
        B = b * PHI * RHO0 / (1.0 + PHI) * (case["chi"] + case["chi_yang"])
        if zero:
            out[1, 1] = -gamma
        else:
            out[0, 0] = -D_case * K + s
            out[1, 0] = -B
            out[1, 1] = -D_case * K - gamma
            out[2, 2] = -nu_case * K
            out[3, 3] = -nu_case * K
    else:
        g0 = 0.382 / (RHO0 * RHO0 + 0.382) if case["qi_gate"] else 1.0
        gamma = (1.0 + PHI) * case["lam"] * g0
        h = case["hyper_nu"] * K * K
        if zero:
            out[1, 1] = -gamma
        else:
            out[0, 0] = -D_case * K - h
            out[1, 1] = -D_case * K - h - gamma
            out[2, 2] = -nu_case * K - h
            out[3, 3] = -nu_case * K - h
    if not zero:
        out += -1j * omega * np.eye(4, dtype=np.complex128)
    return out


def jacobian_case(module: Any, case: dict[str, Any], k: tuple[int, int, int], outdir: Path) -> dict[str, Any]:
    solver = make_solver(module, case)
    idx = (k[2] % N, k[1] % N, k[0] % N)
    zero = k == (0, 0, 0)
    source_k = np.array([float(solver.kx[idx]), float(solver.ky[idx]), float(solver.kz[idx])], dtype=np.float64)
    mask = float(solver.dealias[idx])
    basis = np.eye(3, dtype=np.float64) if zero else transverse_basis(source_k)
    n = 5 if zero else 4
    responses = np.zeros((2, 2, n, n), dtype=np.complex128)
    ey0 = PHI * RHO0 / (1.0 + PHI)
    ei0 = RHO0 / (1.0 + PHI)
    cosine = phase_cos(k)
    import torch
    for ai, amp in enumerate(AMPLITUDES):
        for si, sign in enumerate((1.0, -1.0)):
            for j in range(n):
                drho = amp if j == 0 else 0.0
                deps = amp if j == 1 else 0.0
                dey = (PHI * drho + deps) / (1.0 + PHI)
                dei = (drho - deps) / (1.0 + PHI)
                ey = torch.full((N, N, N), ey0, dtype=torch.float64) + sign * dey * torch.from_numpy(cosine)
                ei = torch.full((N, N, N), ei0, dtype=torch.float64) + sign * dei * torch.from_numpy(cosine)
                velocity = []
                for d in range(3):
                    perturb = amp * basis[d, j - 2] if j >= 2 else 0.0
                    velocity.append(torch.fft.fftn(torch.full((N, N, N), U[d], dtype=torch.float64) + sign * perturb * torch.from_numpy(cosine)))
                rhs_u, rhs_ey, rhs_ei = solver.rhs(velocity, torch.fft.fftn(ey), torch.fft.fftn(ei))
                responses[ai, si, :, j] = coordinate_extract(rhs_u, rhs_ey, rhs_ei, idx, basis, zero)
    jac = np.empty((2, n, n), dtype=np.complex128)
    for ai, amp in enumerate(AMPLITUDES):
        jac[ai] = (responses[ai, 0] - responses[ai, 1]) / (2.0 * amp)
    richardson = (4.0 * jac[1] - jac[0]) / 3.0
    expected = expected_matrix(case, source_k, mask, zero)
    denom = max(1.0, float(np.max(np.abs(expected))))
    fine_residual = float(np.max(np.abs(jac[1] - expected)) / denom)
    rich_residual = float(np.max(np.abs(richardson - expected)) / denom)
    if not all(np.all(np.isfinite(x)) for x in (source_k, basis, responses, jac, richardson, expected)):
        raise ContractError(f"nonfinite Jacobian evidence {case['id']} {k}")
    ident = f"{case['id']}_k{k[0]}_{k[1]}_{k[2]}"
    filename = f"jacobian_{ident}.npz"
    np.savez(outdir / filename, wavevector=source_k, basis=basis, mask=np.array(mask), amplitudes=AMPLITUDES, responses=responses, jacobians=jac, richardson=richardson, expected=expected)
    return {"id": ident, "case": case["id"], "k": list(k), "array": filename, "fine_residual": fine_residual, "richardson_residual": rich_residual, "passed": bool(fine_residual <= 5.0e-6 and rich_residual <= 1.0e-8)}
def trajectory(module: Any, case: dict[str, Any], dt: float, outdir: Path) -> dict[str, Any]:
    k = (1, 1, 0)
    solver_probe = make_solver(module, case)
    idx = (0, 1, 1)
    source_k = np.array([float(solver_probe.kx[idx]), float(solver_probe.ky[idx]), float(solver_probe.kz[idx])], dtype=np.float64)
    basis = transverse_basis(source_k)
    A = expected_matrix(case, source_k, 1.0, False)
    X0 = 1.0e-4 * np.array([1.0, 0.7, 0.3, -0.2], dtype=np.complex128)
    nsteps = int(round(10.0 / dt))
    expected_continuous = expm(10.0 * A) @ X0
    expected_discrete = np.linalg.matrix_power(np.eye(4, dtype=np.complex128) + dt * A + 0.5 * dt * dt * (A @ A), nsteps) @ X0
    times = np.arange(nsteps + 1, dtype=np.float64) * dt
    coordinates = np.zeros((2, nsteps + 1, 4), dtype=np.complex128)
    minima = np.zeros((2, nsteps + 1, 2), dtype=np.float64)
    rho_mean = np.zeros((2, nsteps + 1), dtype=np.float64)
    scale_factor = np.zeros((2, nsteps + 1), dtype=np.float64)
    hubble = np.zeros((2, nsteps + 1), dtype=np.float64)
    ey0 = PHI * RHO0 / (1.0 + PHI)
    ei0 = RHO0 / (1.0 + PHI)
    cosine = phase_cos(k)
    import torch
    for si, sign in enumerate((1.0, -1.0)):
        solver = make_solver(module, case)
        ey = torch.full((N, N, N), ey0, dtype=torch.float64) + sign * ((PHI * X0[0].real + X0[1].real) / (1.0 + PHI)) * torch.from_numpy(cosine)
        ei = torch.full((N, N, N), ei0, dtype=torch.float64) + sign * ((X0[0].real - X0[1].real) / (1.0 + PHI)) * torch.from_numpy(cosine)
        u = [torch.fft.fftn(torch.full((N, N, N), U[d], dtype=torch.float64) + sign * (X0[2].real * basis[d, 0] + X0[3].real * basis[d, 1]) * torch.from_numpy(cosine)) for d in range(3)]
        ey_hat, ei_hat = torch.fft.fftn(ey), torch.fft.fftn(ei)
        def store(ti: int, uu: list[Any], eyy: Any, eii: Any) -> None:
            coordinates[si, ti] = coordinate_extract(uu, eyy, eii, idx, basis, False)
            ey_phys = torch.fft.ifftn(eyy).real
            ei_phys = torch.fft.ifftn(eii).real
            minima[si, ti] = [float(ey_phys.min()), float(ei_phys.min())]
            rho_mean[si, ti] = float((ey_phys + ei_phys).mean())
            scale_factor[si, ti] = float(solver.a)
            hubble[si, ti] = float(solver.H)
        store(0, u, ey_hat, ei_hat)
        for ti in range(1, nsteps + 1):
            u, ey_hat, ei_hat = solver.rk2_step(u, ey_hat, ei_hat, dt)
            store(ti, u, ey_hat, ei_hat)
    odd = (coordinates[0, -1] - coordinates[1, -1]) / 2.0
    norm = float(np.max(np.abs(X0)))
    endpoint_cont = float(np.max(np.abs(odd - expected_continuous)) / norm)
    endpoint_disc = float(np.max(np.abs(odd - expected_discrete)) / norm)
    mean_drift = float(np.max(np.abs(rho_mean - RHO0)) / RHO0)
    scale_err = float(np.max(np.abs(scale_factor - 1.0)))
    max_h = float(np.max(np.abs(hubble)))
    min_field = float(np.min(minima))
    filename = {0.04: "trajectory_dt004.npz", 0.02: "trajectory_dt002.npz", 0.01: "trajectory_dt001.npz"}[dt]
    for arr, name in ((coordinates, "coordinates"), (minima, "minima"), (rho_mean, "rho_mean"), (scale_factor, "scale_factor"), (hubble, "hubble")):
        finite_array(arr, name)
    np.savez(outdir / filename, dt=np.array(dt), times=times, coordinates=coordinates, minima=minima, rho_mean=rho_mean, scale_factor=scale_factor, hubble=hubble, expected_continuous=expected_continuous, expected_discrete=expected_discrete)
    return {"dt": dt, "array": filename, "endpoint_continuous_error": endpoint_cont, "endpoint_discrete_error": endpoint_disc, "minima": min_field, "maximum_mean_relative_drift": mean_drift, "maximum_scale_error": scale_err, "maximum_hubble": max_h, "passed": bool(endpoint_disc <= 2.0e-4 and min_field > 0.1 and mean_drift <= 1.0e-10 and scale_err <= 1.0e-12 and max_h <= 1.0e-12)}






def algebra_certificates(module: Any) -> dict[str, Any]:
    T = np.array([[1.0, 1.0], [1.0, -PHI]])
    Ti = np.array([[PHI, 1.0], [1.0, -1.0]]) / (1.0 + PHI)
    records: list[dict[str, Any]] = []
    def rec(name: str, residual: float, passed: bool = True) -> None:
        records.append({"name": name, "residual": scalar_float(residual, name), "passed": bool(passed)})
    rec("population_transform", np.max(np.abs(T @ Ti - np.eye(2))))
    kvec = np.array([1.0, 2.0, 3.0], dtype=np.float64)
    K = float(kvec @ kvec)
    omega = float(kvec @ U)
    base = CASES[0]
    A = expected_matrix(base, kvec, 1.0, False)
    gamma = (1.0 + PHI) * base["lam"]
    eig = np.array([-D * K - 1j * omega, -D * K - gamma - 1j * omega, -NU * K - 1j * omega, -NU * K - 1j * omega])
    rec("base_characteristic_polynomial", np.max(np.abs(np.poly(A) - np.poly(eig))))
    rec("matched_mobility", abs(A[0, 0] + 1j * omega + D * K) + abs(A[1, 0] + (PHI * RHO0 / (1.0 + PHI)) * (0.4 + 0.4 / PHI)))
    jordan = expected_matrix(CASES[4], kvec, 1.0, False)
    jordan_lambda = -D * K - gamma - 1j * omega
    jordan_nil = jordan[:2, :2] - jordan_lambda * np.eye(2)
    rec("jordan_nilpotent", np.max(np.abs(jordan_nil @ jordan_nil)), passed=abs(jordan_nil[1, 0]) > 0.0)
    J = np.eye(4)
    J[0, 1] = 1.0
    transformed = J @ A @ np.linalg.inv(J)
    rec("similarity", np.max(np.abs(transformed @ J - J @ A)))
    lift = np.vstack((np.eye(4), np.array([[1.0, 2.0, 0.0, 0.0]])))
    A5 = np.zeros((5, 5), dtype=np.complex128)
    A5[:4, :4] = A
    A5[4, :4] = np.array([1.0, 2.0, 0.0, 0.0]) @ A
    rec("injective_lift", np.max(np.abs(A5 @ lift - lift @ A)))
    rec("density_closure", np.max(np.abs(A[0, 1:])))
    rec("imbalance_closure_failure", 0.0, passed=abs(A[1, 0]) > 0.0)
    records[-1]["coupling_magnitude"] = float(abs(A[1, 0]))
    P = np.eye(3) - np.outer(kvec, kvec) / K
    rec("projector_identity", np.max(np.abs(P @ P - P)) + np.max(np.abs(P @ kvec)))
    ex = expected_matrix(CASES[5], kvec, 1.0, False)
    ex_diag = np.diag([-CASES[5]["D"] * K - CASES[5]["hyper_nu"] * K * K - 1j * omega, -CASES[5]["D"] * K - CASES[5]["hyper_nu"] * K * K - (1.0 + PHI) * CASES[5]["lam"] * 0.382 / (RHO0 * RHO0 + 0.382) - 1j * omega, -CASES[5]["nu"] * K - CASES[5]["hyper_nu"] * K * K - 1j * omega, -CASES[5]["nu"] * K - CASES[5]["hyper_nu"] * K * K - 1j * omega])
    rec("expanding_spectrum", np.max(np.abs(ex - ex_diag)))
    identity_pass = all(r["passed"] and r["residual"] <= 1.0e-12 for r in records)
    return {"records": records, "passed": identity_pass}

def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def failure(outdir: Path, error: str) -> int:
    if outdir.exists() and (outdir / "results.json").exists():
        return 1
    outdir.mkdir(parents=True, exist_ok=True)
    write_json(outdir / "results.json", {"schema": SCHEMA, "verdict": "INCONCLUSIVE", "passed": False, "provenance": {}, "rows": [], "trajectories": [], "algebra": {}, "files": {}, "error": str(error)})
    return 1


def run(args: argparse.Namespace) -> int:
    outdir = Path(args.output_dir).resolve()
    if outdir.exists():
        raise ContractError("output directory must be absent before invocation")
    solver_path = Path(args.solver).resolve() if args.solver else DEFAULT_SOLVER
    report_path = Path(args.note).resolve() if args.note else REPORT
    if not report_path.is_file():
        raise ContractError("missing continuum report")
    if not solver_path.is_file():
        raise ContractError("missing canonical solver")
    report_raw = report_path.read_bytes()
    protocol = protocol_bytes(report_raw)
    if canonical_sha256(protocol) != PROTOCOL_SHA256:
        raise ContractError("frozen protocol hash mismatch")
    solver_raw = solver_path.read_bytes()
    solver_canon = canonical_sha256(solver_raw)
    if solver_canon != SOLVER_CANONICAL_SHA256:
        raise ContractError("canonical solver hash mismatch")
    outdir.mkdir(parents=True)
    (outdir / "source_solver.py").write_bytes(solver_raw)
    (outdir / "source_primary.py").write_bytes(Path(__file__).read_bytes())
    (outdir / "frozen_protocol.txt").write_bytes(protocol)
    module = load_solver(solver_path)
    import torch
    torch.set_num_threads(1)
    rows: list[dict[str, Any]] = []
    trajectories: list[dict[str, Any]] = []
    for case in CASES:
        for k in WAVEVECTORS:
            rows.append(jacobian_case(module, case, k, outdir))
    expanding = next(c for c in CASES if c["id"] == "expanding_gated")
    for dt in (0.04, 0.02, 0.01):
        trajectories.append(trajectory(module, expanding, dt, outdir))
    algebra = algebra_certificates(module)
    cont = [r["endpoint_continuous_error"] for r in trajectories]
    ratios = [cont[i] / cont[i + 1] if cont[i + 1] > 0 else math.inf for i in range(2)]
    ratio_pass = all(3.5 <= x <= 4.5 for x in ratios)
    algebra["trajectory_continuous_ratios"] = {"ratios": ratios, "passed": ratio_pass}
    all_pass = all(r["passed"] for r in rows) and all(r["passed"] for r in trajectories) and algebra["passed"] and algebra["trajectory_continuous_ratios"]["passed"]
    files: dict[str, str] = {}
    for path in sorted(outdir.iterdir()):
        if path.name != "results.json":
            files[path.name] = raw_sha256(path.read_bytes())
    primary_raw = Path(__file__).read_bytes()
    provenance = {"protocol_sha256": PROTOCOL_SHA256, "solver_canonical_sha256": solver_canon, "solver_raw_sha256": raw_sha256(solver_raw), "primary_canonical_sha256": canonical_sha256(primary_raw), "primary_raw_sha256": raw_sha256(primary_raw), "python": platform.python_version(), "numpy": np.__version__, "torch": torch.__version__, "scipy": __import__("scipy").__version__}
    config = {"N": N, "L": L, "rho0": RHO0, "lambda": LAMBDA, "D": D, "nu": NU, "U": U.tolist(), "phi": PHI, "amplitudes": AMPLITUDES.tolist(), "cases": jsonable(CASES), "wavevectors": [list(k) for k in WAVEVECTORS], "solver_defaults": {"device": "cpu", "dtype": "float64", "complex_dtype": "complex128", "torch_threads": 1, "hubble_mode": "friedmann", "H0": 0.0, "a0": 1.0, "h_smooth": 1.0, "max_H": 4.0, "qi_memory": False, "wu_xing": False, "gate_model": "single", "phi_inv2": 0.382}, "trajectory": {"T": 10.0, "dt": [0.04, 0.02, 0.01], "X0": [1.0e-4, 0.7e-4, 0.3e-4, -0.2e-4]}}
    verdict = "SUPPORTS—homogeneous canonical excitation and regular-observable boundaries" if all_pass else "INCONCLUSIVE"
    receipt = {"schema": SCHEMA, "verdict": verdict, "passed": all_pass, "provenance": provenance, "config": config, "rows": rows, "trajectories": trajectories, "algebra": algebra, "files": files}
    write_json(outdir / "results.json", receipt)
    print(verdict)
    print(json.dumps({"jacobian_rows": len(rows), "max_fine_residual": max(r["fine_residual"] for r in rows),
                      "max_richardson_residual": max(r["richardson_residual"] for r in rows),
                      "trajectories": len(trajectories), "continuous_error_ratios": ratios}, allow_nan=False))
    return 0 if all_pass else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Primary canonical density-velocity excitation campaign")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--note")
    parser.add_argument("--solver")
    args = parser.parse_args()
    outdir = Path(args.output_dir).resolve()
    preexisting = outdir.exists()
    try:
        return run(args)
    except Exception as exc:
        if preexisting:
            return 1
        return failure(outdir, str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
