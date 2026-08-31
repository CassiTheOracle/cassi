#!/usr/bin/env python3
"""Run the preregistered V4 high-precision toroidal survival campaign."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch

_V3_PATH = Path(__file__).with_name("toroidal_coherence_survival_v3_probe.py")
_V3_SPEC = importlib.util.spec_from_file_location("toroidal_coherence_survival_v3_probe", _V3_PATH)
if _V3_SPEC is None or _V3_SPEC.loader is None:
    raise ImportError(f"cannot load {_V3_PATH}")
v3 = importlib.util.module_from_spec(_V3_SPEC)
_V3_SPEC.loader.exec_module(v3)

ROOT = v3.ROOT
PHI = v3.PHI
DIAGNOSTIC = "sector_normalized_phase_v4_complex128"
CONSTANTS = {
    **v3.CONSTANTS,
    "reference_n": 64,
    "dt": 0.0025,
    "state_dtype": "complex128",
}
ARMS = [
    {"id": "A", "name": "primary_closed", "seed": "closed", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "B", "name": "gravity_off", "seed": "closed", "n": 64, "dt": 0.0025, "g": 0.0},
    {"id": "C", "name": "untwisted", "seed": "untwisted", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "D", "name": "open_loop", "seed": "open", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "E", "name": "scrambled_phase", "seed": "scrambled", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "F", "name": "sphere", "seed": "sphere", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "G", "name": "perturbed", "seed": "perturbed", "n": 64, "dt": 0.0025, "g": 1.0},
    {"id": "H", "name": "low_resolution", "seed": "closed", "n": 48, "dt": 0.0025, "g": 1.0},
    {"id": "I", "name": "high_resolution", "seed": "closed", "n": 80, "dt": 0.0025, "g": 1.0},
    {"id": "J", "name": "half_dt", "seed": "closed", "n": 64, "dt": 0.00125, "g": 1.0},
]


def make_grid(n: int, device: torch.device) -> dict[str, Any]:
    box = CONSTANTS["box_size"]
    dx = box / n
    axis = (torch.arange(n, device=device, dtype=torch.float64) - n / 2) * dx
    x, y, z = torch.meshgrid(axis, axis, axis, indexing="ij")
    r_perp = torch.sqrt(x * x + y * y)
    chi = torch.atan2(y, x)
    k_axis = 2.0 * math.pi * torch.fft.fftfreq(n, d=dx, device=device, dtype=torch.float64)
    kx, ky, kz = torch.meshgrid(k_axis, k_axis, k_axis, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    sector = torch.floor((chi + math.pi) * CONSTANTS["winding_sectors"] / (2.0 * math.pi)).to(torch.int64)
    sector.clamp_(0, CONSTANTS["winding_sectors"] - 1)
    return {
        "n": n,
        "dx": dx,
        "dv": dx**3,
        "x": x,
        "y": y,
        "z": z,
        "r_perp": r_perp,
        "chi": chi,
        "k2": k2,
        "kx": kx,
        "ky": ky,
        "kz": kz,
        "sector": sector.reshape(-1),
    }


def filtered_noise(n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal((n, n, n))
    dx = CONSTANTS["box_size"] / n
    k = 2.0 * math.pi * np.fft.fftfreq(n, d=dx)
    kx, ky, kz = np.meshgrid(k, k, k, indexing="ij")
    kmag = np.sqrt(kx * kx + ky * ky + kz * kz)
    cutoff = math.pi / CONSTANTS["sigma"]
    return np.fft.ifftn(np.fft.fftn(noise) * np.exp(-((kmag / cutoff) ** 4))).real.astype(np.float64)


def normalize_components(
    amp_y: torch.Tensor,
    amp_i: torch.Tensor,
    phase_y: torch.Tensor,
    phase_i: torch.Tensor,
    grid: dict[str, Any],
    total_mass: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    ratio = CONSTANTS["component_ratio"]
    target_y = total_mass * ratio / (1.0 + ratio)
    target_i = total_mass / (1.0 + ratio)
    norm_y = torch.sum(amp_y * amp_y) * grid["dv"]
    norm_i = torch.sum(amp_i * amp_i) * grid["dv"]
    amp_y = amp_y * torch.sqrt(torch.tensor(target_y, device=amp_y.device, dtype=amp_y.dtype) / norm_y)
    amp_i = amp_i * torch.sqrt(torch.tensor(target_i, device=amp_i.device, dtype=amp_i.dtype) / norm_i)
    return torch.polar(amp_y, phase_y).to(torch.complex128), torch.polar(amp_i, phase_i).to(torch.complex128)


def sector_statistics(field: torch.Tensor, grid: dict[str, Any], declared_winding: int) -> dict[str, float]:
    sectors = CONSTANTS["winding_sectors"]
    flat = field.reshape(-1)
    indices = grid["sector"]
    real = torch.zeros(sectors, device=field.device, dtype=flat.real.dtype).scatter_add_(0, indices, flat.real)
    imag = torch.zeros(sectors, device=field.device, dtype=flat.real.dtype).scatter_add_(0, indices, flat.imag)
    amplitude = torch.zeros(sectors, device=field.device, dtype=flat.real.dtype).scatter_add_(0, indices, torch.abs(flat))
    values = torch.complex(real, imag)
    safe_amplitude = torch.clamp(amplitude, min=torch.finfo(amplitude.dtype).tiny)
    phasors = values / safe_amplitude
    increments = torch.angle(torch.roll(phasors, shifts=-1) * torch.conj(phasors))
    centers = (torch.arange(sectors, device=field.device, dtype=amplitude.dtype) + 0.5) * (2.0 * math.pi / sectors)
    demodulator = torch.exp(torch.complex(torch.zeros_like(centers), -declared_winding * centers))
    value_magnitudes = torch.abs(values)
    return {
        "winding": v3.base.scalar(torch.sum(increments) / (2.0 * math.pi)),
        "phase_coherence": v3.base.scalar(torch.min(torch.abs(phasors))),
        "sector_support": v3.base.scalar(torch.min(amplitude) / torch.clamp(torch.mean(amplitude), min=1e-300)),
        "demodulated_coherence": v3.base.scalar(torch.abs(torch.sum(values * demodulator)) / torch.clamp(torch.sum(amplitude), min=1e-300)),
        "legacy_sector_ratio": v3.base.scalar(torch.min(value_magnitudes) / torch.clamp(torch.mean(value_magnitudes), min=1e-300)),
    }

def legacy_winding(field: torch.Tensor, grid: dict[str, Any]) -> tuple[float, float]:
    stats = sector_statistics(field, grid, 0)
    return stats["winding"], stats["legacy_sector_ratio"]

def evolve_arm(
    arm: dict[str, Any],
    total_mass: float,
    device: torch.device,
    run_dir: Path,
) -> dict[str, Any]:
    grid = make_grid(arm["n"], device)
    psi_y, psi_i = v3.base.make_seed(arm["seed"], grid, total_mass)
    g = arm["g"]
    dt = arm["dt"]
    steps = round(CONSTANTS["t_end"] / dt)
    report_steps = round(CONSTANTS["report_cadence"] / dt)
    kinetic_phase = torch.exp(-0.5j * grid["k2"] * dt)
    phi_field = v3.base.solve_phi(psi_y, psi_i, grid) if g != 0.0 else None
    initial_max_density = v3.base.scalar(torch.max(torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2))
    metrics: list[dict[str, Any]] = []
    fields_y: list[np.ndarray] = []
    fields_i: list[np.ndarray] = []
    times: list[float] = []
    initial_center: list[float] | None = None
    status = "complete"
    stop_reason: str | None = None

    def capture(step: int) -> None:
        nonlocal initial_center
        time_value = step * dt
        row = v3.diagnose(psi_y, psi_i, grid, g, time_value, phi_field, initial_center)
        if initial_center is None:
            initial_center = row["center"]
            row["center_displacement"] = 0.0
        metrics.append(row)
        times.append(time_value)
        fields_y.append(psi_y.detach().cpu().numpy().copy())
        fields_i.append(psi_i.detach().cpu().numpy().copy())

    capture(0)
    for step in range(1, steps + 1):
        if g != 0.0:
            phase = torch.exp(-0.5j * dt * g * phi_field)
            psi_y *= phase
            psi_i *= phase
        psi_y = torch.fft.ifftn(torch.fft.fftn(psi_y) * kinetic_phase)
        psi_i = torch.fft.ifftn(torch.fft.fftn(psi_i) * kinetic_phase)
        if g != 0.0:
            phi_field = v3.base.solve_phi(psi_y, psi_i, grid)
            phase = torch.exp(-0.5j * dt * g * phi_field)
            psi_y *= phase
            psi_i *= phase
        density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
        if not bool(torch.isfinite(density).all().item()):
            status, stop_reason = "stopped", "nonfinite field"
            break
        if v3.base.scalar(torch.max(density)) > 1.0e8 * initial_max_density:
            status, stop_reason = "stopped", "density ceiling"
            break
        if step % report_steps == 0:
            capture(step)

    receipt_path = run_dir / f"fields_{arm['id']}.npz"
    np.savez_compressed(
        receipt_path,
        times=np.asarray(times, dtype=np.float64),
        psi_y=np.stack(fields_y),
        psi_i=np.stack(fields_i),
    )
    return {
        "config": arm,
        "status": status,
        "stop_reason": stop_reason,
        "metrics": metrics,
        "fields_file": receipt_path.name,
        "fields_sha256": v3.base.sha256_file(receipt_path),
    }




setattr(v3, "CONSTANTS", CONSTANTS)
setattr(v3, "ARMS", ARMS)
setattr(v3, "sector_statistics", sector_statistics)
v3.base.CONSTANTS = CONSTANTS
v3.base.ARMS = ARMS
v3.base.make_grid = make_grid
v3.base.filtered_noise = filtered_noise
v3.base.normalize_components = normalize_components
v3.base.winding = legacy_winding
v3.base.evolve_arm = evolve_arm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="fresh receipt directory")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    args = parser.parse_args()

    if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()):
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("requested CUDA/ROCm device is unavailable")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_coherence_survival_v4"
    run_dir.mkdir(parents=True, exist_ok=False)

    source_names = (
        "toroidal-coherence-survival-pre-registration.md",
        "toroidal-coherence-survival-v2-pre-registration.md",
        "toroidal-coherence-survival-v3-pre-registration.md",
        "toroidal-coherence-survival-v4-pre-registration.md",
        "toroidal_coherence_survival_v2_probe.py",
        "toroidal_coherence_survival_v3_probe.py",
        "toroidal_coherence_survival_v4_probe.py",
        "verify_toroidal_coherence_survival_v2.py",
        "verify_toroidal_coherence_survival_v3.py",
        "verify_toroidal_coherence_survival_v4.py",
    )
    source_paths = tuple(ROOT / "field-experience" / name for name in source_names)
    sources = {str(path.relative_to(ROOT)).replace("\\", "/"): v3.base.sha256_file(path) for path in source_paths}

    reference_grid = make_grid(CONSTANTS["reference_n"], device)
    unit_y, unit_i = v3.base.make_seed("closed", reference_grid, 1.0)
    reference_phi = v3.base.solve_phi(unit_y, unit_i, reference_grid)
    k1, w1, _ = v3.base.energy_terms(unit_y, unit_i, reference_grid, 1.0, reference_phi)
    virial_mass = -2.0 * k1 / w1
    if w1 >= 0.0 or not math.isfinite(virial_mass) or not 0.1 <= virial_mass <= 1.0e6:
        raise RuntimeError(f"invalid virial calibration: K1={k1}, W1={w1}, M={virial_mass}")

    def initial(seed: str) -> dict[str, Any]:
        psi_y, psi_i = v3.base.make_seed(seed, reference_grid, virial_mass)
        phi_field = v3.base.solve_phi(psi_y, psi_i, reference_grid)
        return v3.diagnose(psi_y, psi_i, reference_grid, 1.0, 0.0, phi_field, None)

    preflight = {
        "diagnostic": DIAGNOSTIC,
        "precision": "float64/complex128",
        "closure_error": v3.base.analytic_closure_error(),
        "k1": k1,
        "w1": w1,
        "virial_mass": virial_mass,
        "closed_initial": initial("closed"),
        "untwisted_initial": initial("untwisted"),
        "scrambled_initial": initial("scrambled"),
    }
    preflight_gates = v3.initialization_gates(preflight)
    if not all(preflight_gates.values()):
        result = {
            "probe": "toroidal_coherence_survival_v4",
            "diagnostic": DIAGNOSTIC,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "constants": CONSTANTS,
            "arms_spec": ARMS,
            "sources": sources,
            "device": str(device),
            "dtype": "complex128/float64",
            "preflight": preflight,
            "gates": preflight_gates,
            "verdict": "INCONCLUSIVE—INVALID INITIALIZATION",
        }
        with (run_dir / "results.json").open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps({"run_dir": str(run_dir), "verdict": result["verdict"], "gates": preflight_gates}, indent=2))
        return

    arm_results: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        print(f"running arm {arm['id']} ({arm['name']})", flush=True)
        arm_results[arm["id"]] = v3.base.evolve_arm(arm, virial_mass, device, run_dir)
        if arm_results[arm["id"]]["status"] != "complete":
            print(f"arm {arm['id']} stopped: {arm_results[arm['id']]['stop_reason']}", flush=True)

    gates, verdict, failure_labels, perturbation_verdict = v3.evaluate_gates(arm_results, preflight)
    results = {
        "probe": "toroidal_coherence_survival_v4",
        "diagnostic": DIAGNOSTIC,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "constants": CONSTANTS,
        "arms_spec": ARMS,
        "arms": arm_results,
        "sources": sources,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
        "dtype": "complex128/float64",
        "preflight": preflight,
        "gates": gates,
        "verdict": verdict,
        "failure_labels": failure_labels,
        "perturbation_verdict": perturbation_verdict,
    }
    results_path = run_dir / "results.json"
    with results_path.open("x", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict, "failure_labels": failure_labels, "perturbation_verdict": perturbation_verdict, "gates": gates}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
