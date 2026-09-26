#!/usr/bin/env python3
"""Primary frozen nonlinear composition-to-density transfer receipt.

This program uses the unmodified ``TwoFluid3DGPU`` source on CPU, retaining
full three-dimensional fields while recording the invariant planar profiles.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import platform
import re
from pathlib import Path

import numpy as np
import sympy as sp
import torch

ROOT = Path(__file__).resolve().parents[1]
HEADING = "### 23.2 Nonlinear transfer calculation: pre-execution criteria"
PROTOCOL_SHA = "280f63358968c9bc8d7852e9b1a5482e130150141b4932e62f525ac68ff62c9a"
SOLVER_SHA = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
VERDICT = "SUPPORTS—nonlinear composition-to-density transfer in the base solver"
PHI = (1.0 + math.sqrt(5.0)) / 2.0

L = 2.0 * math.pi
D = 0.03
NU = 0.02
LAM = 0.2
RHO0 = 2.0
R = 0.2
AMPLITUDE = 0.8
CHI = 0.4
CHI_YANG = CHI / PHI
GAMMA = (1.0 + PHI) * LAM
T_FINAL = 20.0

CASES = (
    ("forward", 1.0, CHI),
    ("reverse", -1.0, CHI),
    ("balanced", 0.0, CHI),
    ("disabled", 1.0, 0.0),
)
SCHEDULE = (
    ("forward_n16_dt002", "forward", 16, 0.02),
    ("forward_n16_dt001", "forward", 16, 0.01),
    ("forward_n16_dt0005", "forward", 16, 0.005),
    ("forward_n32_dt001", "forward", 32, 0.01),
    ("reverse_n16_dt001", "reverse", 16, 0.01),
    ("balanced_n16_dt001", "balanced", 16, 0.01),
    ("disabled_n16_dt001", "disabled", 16, 0.01),
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n")


def protocol(note: Path) -> str:
    text = note.read_text(encoding="utf-8").replace("\r\n", "\n")
    if text.count(HEADING) != 1:
        raise ValueError("Frozen transfer heading must occur exactly once")
    rest = text.split(HEADING, 1)[1]
    end = re.search(r"\n#{1,3} ", rest)
    return (HEADING + (rest[: end.start()] if end else rest)).rstrip() + "\n"


def _residual(value: object) -> float:
    return float(abs(complex(sp.N(value, 40))))


def exact_identities() -> list[dict]:
    """Qualify source transformations and the complete periodic budgets."""
    rho, eps, chi, lam, diffusion, mean, velocity = sp.symbols(
        "rho epsilon chi lambda D rho_bar u", real=True
    )
    phi = (1 + sp.sqrt(5)) / 2
    c = 1 / (1 + phi)
    gamma = (1 + phi) * lam
    ey = (phi * rho + eps) / (1 + phi)
    ei = (rho - eps) / (1 + phi)
    x = sp.symbols("x", real=True)
    f, e, potential = (sp.Function(name)(x) for name in ("rho", "epsilon", "Phi"))
    fx, ex, px = (sp.diff(value, x) for value in (f, e, potential))
    density_flux = diffusion * fx - chi / phi * e * px - velocity * f
    imbalance_flux = diffusion * ex - chi * (f - c * e) * px - velocity * e
    density_rhs = diffusion * sp.diff(f, x, 2) - chi / phi * sp.diff(e * px, x) - velocity * fx
    imbalance_rhs = diffusion * sp.diff(e, x, 2) - gamma * e - chi * sp.diff((f - c * e) * px, x) - velocity * ex
    density_energy_flux = diffusion * (f - mean) * fx - chi / phi * (f - mean) * e * px - velocity * (f - mean)**2 / 2
    imbalance_energy_flux = diffusion * e * ex - chi * e * (f - c * e) * px - velocity * e**2 / 2
    a, amplitude, sigma = sp.symbols("r A sigma", real=True)
    witness_rho = mean + a * sp.cos(x)
    witness_eps = sigma * amplitude * sp.cos(2 * x)
    witness_phi = -a * sp.cos(x)
    wrx, wex, wpx = (sp.diff(value, x) for value in (witness_rho, witness_eps, witness_phi))
    density_integrand = -diffusion * wrx**2 + chi / phi * witness_eps * wrx * wpx
    imbalance_integrand = -diffusion * wex**2 - gamma * witness_eps**2 + chi * (witness_rho - c * witness_eps) * wex * wpx
    checks = {
        "population_sum": ey + ei - rho,
        "population_imbalance": ey - phi * ei - eps,
        "density_flux_transformation": chi / phi * ey - chi * ei - chi / phi * eps,
        "imbalance_flux_transformation": chi / phi * ey + phi * chi * ei - chi * (rho - c * eps),
        "conversion_sum": -lam * eps + lam * eps,
        "conversion_imbalance_rate": -lam * eps - phi * lam * eps + gamma * eps,
        "density_mean_divergence": density_rhs - sp.diff(density_flux, x),
        "imbalance_mean_divergence": imbalance_rhs + gamma * e - sp.diff(imbalance_flux, x),
        "density_budget_product_rule": (f - mean) * density_rhs - sp.diff(density_energy_flux, x) + diffusion * fx**2 - chi / phi * e * fx * px,
        "imbalance_budget_product_rule": e * imbalance_rhs - sp.diff(imbalance_energy_flux, x) + diffusion * ex**2 + gamma * e**2 - chi * (f - c * e) * ex * px,
        "density_trigonometric_budget": sp.integrate(sp.expand_trig(density_integrand), (x, 0, 2 * sp.pi)) / (2 * sp.pi) + diffusion * a**2 / 2 - chi * sigma * amplitude * a**2 / (4 * phi),
        "imbalance_trigonometric_budget": sp.integrate(sp.expand_trig(imbalance_integrand), (x, 0, 2 * sp.pi)) / (2 * sp.pi) + (2 * diffusion + gamma / 2) * sigma**2 * amplitude**2 + chi * sigma * amplitude * a**2 / 2,
    }
    records = []
    for name, value in checks.items():
        residual = sp.simplify(value)
        records.append({"name": name, "residual": _residual(residual),
                        "passed": bool(residual == 0)})
    return records


def load_solver(path: Path):
    spec = importlib.util.spec_from_file_location("chemotactic_transfer_canonical", path)
    if spec is None or spec.loader is None:
        raise ValueError("Unable to load canonical source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def initial_fields(n: int, sigma: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    x = 2.0 * np.pi * np.arange(n, dtype=np.float64) / n
    rho_line = RHO0 + R * np.cos(x)
    eps_line = sigma * AMPLITUDE * np.cos(2.0 * x)
    rho = np.broadcast_to(rho_line, (n, n, n)).copy()
    eps = np.broadcast_to(eps_line, (n, n, n)).copy()
    ey = (PHI * rho + eps) / (1.0 + PHI)
    ei = (rho - eps) / (1.0 + PHI)
    return ey, ei, eps


def state_from_fields(ey: np.ndarray, ei: np.ndarray):
    shape = ey.shape
    zero = torch.zeros(shape, dtype=torch.complex128, device="cpu")
    return [zero.clone(), zero.clone(), zero.clone()], torch.fft.fftn(torch.as_tensor(ey, dtype=torch.float64)), torch.fft.fftn(torch.as_tensor(ei, dtype=torch.float64))


def native_one_dimensional_rhs(
    ey: np.ndarray, ei: np.ndarray, n: int, chi: float
) -> tuple[np.ndarray, np.ndarray]:
    labels = np.fft.fftfreq(n, d=1.0 / n).astype(np.float32)
    k1 = (2.0 * np.pi * (labels * np.float32(1.0 / L))).astype(np.float64)
    mask = (np.abs(k1) < (2.0 / 3.0) * np.max(np.abs(k1))).astype(np.float64)
    yh = np.fft.fft(ey.astype(np.float64)).astype(np.complex128)
    ih = np.fft.fft(ei.astype(np.float64)).astype(np.complex128)
    rh = yh + ih
    rh = rh.copy()
    rh[0] = 0.0
    denom = k1 * k1
    denom = denom.copy()
    denom[0] = 1.0
    phi_h = -rh / denom
    gradphi = np.fft.ifft(1j * k1 * phi_h).real
    eps = ey - PHI * ei
    conv = -LAM * eps
    rhs_yh = -D * k1 * k1 * yh + np.fft.fft(conv)
    rhs_ih = -D * k1 * k1 * ih - np.fft.fft(conv)
    if chi != 0.0:
        rhs_yh = rhs_yh - 1j * k1 * np.fft.fft(CHI_YANG * ey * gradphi)
        rhs_ih = rhs_ih + 1j * k1 * np.fft.fft(chi * ei * gradphi)
    return np.fft.ifft(rhs_yh * mask).real, np.fft.ifft(rhs_ih * mask).real


def _norm_error(actual: np.ndarray, reference: np.ndarray) -> float:
    den = max(1.0, float(np.max(np.abs(reference))))
    return float(np.max(np.abs(actual - reference)) / den)


def make_solver(module, n: int, chi: float):
    return module.TwoFluid3DGPU(
        N=n, L=L, nu=NU, D=D, lam=LAM, chi=chi, chi_yang=CHI_YANG,
        mode="cosmos", device="cpu",
    )


def witness(module, out: Path, files: dict, case: str, sigma: float, chi: float) -> dict:
    n = 16
    solver = make_solver(module, n, chi)
    ey, ei, eps = initial_fields(n, sigma)
    u_hat, ey_hat, ei_hat = state_from_fields(ey, ei)
    rhs_u, rhs_y, rhs_i = solver.rhs(u_hat, ey_hat, ei_hat)
    ey_dot = torch.fft.ifftn(rhs_y).real.numpy()
    ei_dot = torch.fft.ifftn(rhs_i).real.numpy()
    u_dot = np.stack([torch.fft.ifftn(item).real.numpy() for item in rhs_u]).astype(np.float64)
    yref, iref = native_one_dimensional_rhs(ey[0, 0, :], ei[0, 0, :], n, chi)
    source_error = max(_norm_error(ey_dot, yref), _norm_error(ei_dot, iref))
    rho = ey + ei
    eps_dot = ey_dot - PHI * ei_dot
    rho_dot = ey_dot + ei_dot
    rho_budget = float(np.mean((rho - np.mean(rho)) * rho_dot))
    eps_budget = float(np.mean(eps * eps_dot))
    expected_rho_budget = -D * R * R / 2.0 + chi * sigma * AMPLITUDE * R * R / (4.0 * PHI)
    expected_eps_budget = -(2.0 * D + GAMMA / 2.0) * sigma * sigma * AMPLITUDE * AMPLITUDE - chi * sigma * AMPLITUDE * R * R / 2.0
    budget_error = max(abs(rho_budget - expected_rho_budget), abs(eps_budget - expected_eps_budget))
    mean_rho_rate = abs(float(np.mean(rho_dot)))
    mean_epsilon_rate_residual = abs(float(np.mean(eps_dot)) + GAMMA * float(np.mean(eps)))
    velocity_rate = float(np.max(np.abs(u_dot)))
    name = f"witness_{case}.npz"
    arrays = {
        "ey": ey.astype(np.float64), "ei": ei.astype(np.float64),
        "ey_dot": ey_dot.astype(np.float64), "ei_dot": ei_dot.astype(np.float64),
        "u_dot": u_dot.astype(np.float64),
        "k1": solver.kx[0, 0, :].detach().cpu().numpy().astype(np.float64),
        "mask": solver.dealias[0, 0, :].detach().cpu().numpy().astype(np.float64),
    }
    np.savez_compressed(out / name, **arrays)
    files[name] = digest((out / name).read_bytes())
    if not all(np.all(np.isfinite(value)) for value in arrays.values()):
        raise FloatingPointError(f"Nonfinite witness retained in {name}")
    passed = bool(
        source_error <= 1e-10 and budget_error <= 1e-8
        and mean_rho_rate <= 1e-12 and mean_epsilon_rate_residual <= 1e-12
        and velocity_rate <= 1e-12
        and (rho_budget > 0.0 if case == "forward" else rho_budget < 0.0)
    )
    return {
        "id": case, "array": name,
        "rho_budget": rho_budget, "epsilon_budget": eps_budget,
        "rho_budget_expected": float(expected_rho_budget), "epsilon_budget_expected": float(expected_eps_budget),
        "source_error": float(source_error), "budget_error": float(budget_error),
        "mean_rho_rate": float(mean_rho_rate), "mean_epsilon_rate_residual": float(mean_epsilon_rate_residual),
        "velocity_rate": float(velocity_rate), "passed": passed,
    }




def trajectory(module, out: Path, files: dict, ident: str, case: str, n: int, dt: float, sigma: float, chi: float):
    solver = make_solver(module, n, chi)
    ey, ei, _ = initial_fields(n, sigma)
    u_hat, ey_hat, ei_hat = state_from_fields(ey, ei)
    steps = int(round(T_FINAL / dt))
    times = np.arange(steps + 1, dtype=np.float64) * dt
    times[-1] = T_FINAL
    ey_profiles = np.empty((steps + 1, n), dtype=np.float64)
    ei_profiles = np.empty((steps + 1, n), dtype=np.float64)
    rho_mean = np.empty(steps + 1, dtype=np.float64)
    epsilon_mean = np.empty(steps + 1, dtype=np.float64)
    velocity_max = np.empty(steps + 1, dtype=np.float64)
    transverse_error = np.empty(steps + 1, dtype=np.float64)
    minima = np.empty((steps + 1, 2), dtype=np.float64)

    def retain(index: int):
        ey_full = torch.fft.ifftn(ey_hat).real.numpy()
        ei_full = torch.fft.ifftn(ei_hat).real.numpy()
        profile_y = ey_full[0, 0, :]
        profile_i = ei_full[0, 0, :]
        ey_profiles[index] = profile_y
        ei_profiles[index] = profile_i
        rho_mean[index] = float(np.mean(ey_full + ei_full))
        epsilon_mean[index] = float(np.mean(ey_full - PHI * ei_full))
        velocity_max[index] = max(float(torch.fft.ifftn(component).real.abs().max()) for component in u_hat)
        transverse_error[index] = max(float(np.max(np.abs(ey_full - profile_y))),
                                      float(np.max(np.abs(ei_full - profile_i))))
        minima[index] = (float(ey_full.min()), float(ei_full.min()))

    retain(0)
    for step in range(1, steps + 1):
        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
        retain(step)
    name = f"trajectory_{ident}.npz"
    arrays = {
        "times": times, "k1": solver.kx[0, 0, :].detach().cpu().numpy().astype(np.float64),
        "mask": solver.dealias[0, 0, :].detach().cpu().numpy().astype(np.float64),
        "ey": ey_profiles, "ei": ei_profiles, "rho_mean": rho_mean,
        "epsilon_mean": epsilon_mean, "velocity_max": velocity_max,
        "transverse_error": transverse_error, "minima": minima,
    }
    np.savez_compressed(out / name, **arrays)
    files[name] = digest((out / name).read_bytes())
    if not all(np.all(np.isfinite(value)) for value in arrays.values()):
        raise FloatingPointError(f"Nonfinite trajectory retained in {name}")
    expected_eps = epsilon_mean[0] * np.exp(-GAMMA * times)
    mass_error = float(np.max(np.abs(rho_mean - rho_mean[0])))
    mean_epsilon_error = float(np.max(np.abs(epsilon_mean - expected_eps)))
    minimum_component = float(np.min(minima))
    maximum_velocity = float(np.max(velocity_max))
    max_transverse = float(np.max(transverse_error))
    rho0_profile = ey_profiles[0] + ei_profiles[0]
    v0 = float(np.mean((rho0_profile - np.mean(rho0_profile)) ** 2))
    if v0 <= 0.0:
        raise ValueError(f"Nonpositive initial density variance in {name}")
    rho_profiles = ey_profiles + ei_profiles
    variances = np.mean((rho_profiles - rho_profiles.mean(axis=1)[:, None])**2, axis=1)
    variance_ratio = variances / v0
    max_ratio_index = int(np.argmax(variance_ratio))
    row = {
        "id": ident, "case": case, "N": int(n), "dt": float(dt), "array": name,
        "mass_error": mass_error, "mean_epsilon_error": mean_epsilon_error,
        "minimum_component": minimum_component, "maximum_velocity": maximum_velocity,
        "transverse_error": max_transverse, "maximum_variance_ratio": float(variance_ratio[max_ratio_index]),
        "maximum_variance_time": float(times[max_ratio_index]), "endpoint_variance_ratio": float(variance_ratio[-1]),
        "endpoint_classification": "above_initial_at_endpoint" if variance_ratio[-1] > 1.0 else "at_or_below_initial_at_endpoint",
        "passed": bool(minimum_component > 0.0 and mass_error <= 1e-11 and mean_epsilon_error <= 1e-11
                       and maximum_velocity <= 1e-10 and max_transverse <= 1e-10),
    }
    meta = {"ey": ey_profiles, "ei": ei_profiles, "times": times, "variance": variances}
    return row, meta


def qualification(meta: dict) -> dict:
    c = meta["forward_n16_dt002"]
    m = meta["forward_n16_dt001"]
    f = meta["forward_n16_dt0005"]
    n32 = meta["forward_n32_dt001"]
    rev = meta["reverse_n16_dt001"]
    cm = np.concatenate([c["ey"][-1] - m["ey"][-1], c["ei"][-1] - m["ei"][-1]])
    mf = np.concatenate([m["ey"][-1] - f["ey"][-1], m["ei"][-1] - f["ei"][-1]])
    coarse_medium = float(np.max(np.abs(cm)))
    medium_fine = float(np.max(np.abs(mf)))
    ratio = coarse_medium / medium_fine if medium_fine > 0 else None
    common_y = n32["ey"][-1][::2]
    common_i = n32["ei"][-1][::2]
    spatial = _norm_error(
        np.concatenate([m["ey"][-1], m["ei"][-1]]),
        np.concatenate([common_y, common_i]),
    )
    i01 = int(round(0.1 / 0.01))
    forward_early = float(m["variance"][i01] - m["variance"][0])
    forward_minus_reverse = float(m["variance"][i01] - rev["variance"][i01])
    return {
        "endpoint_difference_coarse_medium": coarse_medium,
        "endpoint_difference_medium_fine": medium_fine,
        "endpoint_difference_ratio": ratio,
        "spatial_endpoint_error": float(spatial),
        "forward_early_gain": forward_early,
        "forward_minus_reverse_early": forward_minus_reverse,
        "passed": bool(ratio is not None and 3.5 <= ratio <= 4.5 and medium_fine > 1e-12 and spatial <= 5e-4
                        and forward_early > 1e-5 and forward_minus_reverse > 1e-5),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--note", type=Path, default=ROOT / "computations/matter-formation-continuum-report.md")
    parser.add_argument("--solver", type=Path, default=ROOT / "two-fluid/cassi_two_fluid_3d_gpu.py")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result = {
        "schema": "matter-formation-chemotactic-transfer-v1", "verdict": "INCONCLUSIVE",
        "passed": False, "provenance": {},
        "config": {"L": L, "D": D, "nu": NU, "lam": LAM, "rho0": RHO0, "r": R,
                   "amplitude": AMPLITUDE, "chi_yang": CHI_YANG, "T": T_FINAL},
        "identities": [], "rows": [], "trajectories": [], "qualification": {}, "files": {},
    }
    try:
        # Capture live sources before validating prerequisites or doing science.
        own_source = Path(__file__).read_bytes()
        (args.output_dir / "source_primary.py").write_bytes(own_source)
        result["files"]["source_primary.py"] = digest(own_source)
        source = args.solver.read_bytes()
        note_section = protocol(args.note)
        for name, data in (("frozen_protocol.txt", note_section.encode()), ("source_solver.py", source), ("source_primary.py", own_source)):
            (args.output_dir / name).write_bytes(data)
            result["files"][name] = digest(data)
        result["provenance"] = {
            "protocol_sha256": PROTOCOL_SHA, "solver_canonical_sha256": SOLVER_SHA,
            "solver_raw_sha256": digest(source), "primary_canonical_sha256": digest(canonical(own_source)),
            "primary_raw_sha256": digest(own_source), "python": platform.python_version(),
            "numpy": np.__version__, "torch": torch.__version__,
        }
        if digest(note_section.encode()) != PROTOCOL_SHA:
            raise ValueError("Frozen transfer section hash mismatch")
        if digest(canonical(source)) != SOLVER_SHA:
            raise ValueError("Canonical solver source hash mismatch")
        module = load_solver(args.solver)
        torch.set_num_threads(1)
        result["identities"] = exact_identities()
        for case, sigma, chi in CASES:
            result["rows"].append(witness(module, args.output_dir, result["files"], case, sigma, chi))
        metas = {}
        for ident, case, n, dt in SCHEDULE:
            sigma, chi = next((s, c) for name, s, c in CASES if name == case)
            row, meta = trajectory(module, args.output_dir, result["files"], ident, case, n, dt, sigma, chi)
            result["trajectories"].append(row)
            metas[ident] = meta
        result["qualification"] = qualification(metas)
        result["passed"] = bool(
            len(result["identities"]) == 12 and len(result["rows"]) == 4 and len(result["trajectories"]) == 7
            and all(item["passed"] for item in result["identities"] + result["rows"] + result["trajectories"])
            and result["qualification"].get("passed", False)
        )
        if result["passed"]:
            result["verdict"] = VERDICT
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    (args.output_dir / "results.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(result["verdict"])
    print(json.dumps({"identities": len(result["identities"]), "rows": len(result["rows"]),
                      "trajectories": len(result["trajectories"]), "qualification": result.get("qualification"),
                      "error": result.get("error")}, allow_nan=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
