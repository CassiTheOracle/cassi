#!/usr/bin/env python3
"""Run the preregistered V5 diagnostic-precision toroidal campaign."""

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

_V4_PATH = Path(__file__).with_name("toroidal_coherence_survival_v4_probe.py")
_V4_SPEC = importlib.util.spec_from_file_location("toroidal_coherence_survival_v4_probe", _V4_PATH)
if _V4_SPEC is None or _V4_SPEC.loader is None:
    raise ImportError(f"cannot load {_V4_PATH}")
v4 = importlib.util.module_from_spec(_V4_SPEC)
_V4_SPEC.loader.exec_module(v4)

ROOT = v4.ROOT
PHI = v4.PHI
DIAGNOSTIC = "sector_normalized_phase_v5_s4_float64_energy"
CONSTANTS = dict(v4.CONSTANTS)
ARMS = [dict(arm) for arm in v4.ARMS]


def energy_terms(
    psi_y: torch.Tensor,
    psi_i: torch.Tensor,
    grid: dict[str, Any],
    g: float,
    phi_field: torch.Tensor | None = None,
) -> tuple[float, float, float]:
    kinetic = torch.zeros((), device=psi_y.device, dtype=psi_y.real.dtype)
    for field in (psi_y, psi_i):
        laplacian = torch.fft.ifftn(-grid["k2"] * torch.fft.fftn(field))
        kinetic = kinetic - 0.5 * torch.sum(torch.real(torch.conj(field) * laplacian)) * grid["dv"]
    if g == 0.0:
        potential = 0.0
    else:
        phi_field = v4.v3.base.solve_phi(psi_y, psi_i, grid) if phi_field is None else phi_field
        assert phi_field is not None
        density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
        potential = v4.v3.base.scalar(0.5 * g * torch.sum(density * phi_field) * grid["dv"])
    kinetic_value = v4.v3.base.scalar(kinetic)
    return kinetic_value, potential, kinetic_value + potential


def diagnose(
    psi_y: torch.Tensor,
    psi_i: torch.Tensor,
    grid: dict[str, Any],
    g: float,
    time_value: float,
    phi_field: torch.Tensor | None,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    scalar = v4.v3.base.scalar
    rho_y = torch.abs(psi_y) ** 2
    rho_i = torch.abs(psi_i) ** 2
    density = rho_y + rho_i
    mass_y = torch.sum(rho_y) * grid["dv"]
    mass_i = torch.sum(rho_i) * grid["dv"]
    mass = mass_y + mass_i
    kinetic, potential, energy = energy_terms(psi_y, psi_i, grid, g, phi_field)
    r_fit = torch.sum(grid["r_perp"] * density) * grid["dv"] / mass
    d_tor = torch.sqrt((grid["r_perp"] - r_fit) ** 2 + grid["z"] ** 2)
    core_fraction = torch.sum(density[d_tor <= 2.5 * CONSTANTS["sigma"]]) * grid["dv"] / mass
    theta = torch.atan2(grid["z"], grid["r_perp"] - r_fit)
    carrier = torch.exp(1j * (theta - CONSTANTS["spatial_winding"] * grid["chi"]))
    h_y = torch.sum(rho_y * carrier) * grid["dv"] / mass_y
    h_i = torch.sum(rho_i * carrier) * grid["dv"] / mass_i
    abs_y = torch.abs(h_y)
    abs_i = torch.abs(h_i)
    opposition: float | None = None
    opposed_helical_moment = 0.0
    if scalar(abs_y) >= 1e-8 and scalar(abs_i) >= 1e-8:
        opposition = scalar(-torch.real(h_y * torch.conj(h_i)) / (abs_y * abs_i))
        opposed_helical_moment = scalar(-torch.real(h_y * torch.conj(h_i)))
    stats_y = v4.sector_statistics(psi_y, grid, CONSTANTS["yang_winding"])
    stats_i = v4.sector_statistics(psi_i, grid, CONSTANTS["yin_winding"])
    center = v4.v3.base.periodic_center(density, grid)
    return {
        "time": time_value,
        "mass_y": scalar(mass_y),
        "mass_i": scalar(mass_i),
        "mass": scalar(mass),
        "component_ratio": scalar(mass_y / mass_i),
        "kinetic": kinetic,
        "potential": potential,
        "energy": energy,
        "virial": 2.0 * kinetic + potential,
        "r_fit": scalar(r_fit),
        "core_fraction": scalar(core_fraction),
        "winding_y": stats_y["winding"],
        "winding_i": stats_i["winding"],
        "coherence_y": stats_y["phase_coherence"],
        "coherence_i": stats_i["phase_coherence"],
        "phase_coherence_y": stats_y["phase_coherence"],
        "phase_coherence_i": stats_i["phase_coherence"],
        "sector_support_y": stats_y["sector_support"],
        "sector_support_i": stats_i["sector_support"],
        "demodulated_coherence_y": stats_y["demodulated_coherence"],
        "demodulated_coherence_i": stats_i["demodulated_coherence"],
        "legacy_sector_ratio_y": stats_y["legacy_sector_ratio"],
        "legacy_sector_ratio_i": stats_i["legacy_sector_ratio"],
        "helix_y": scalar(abs_y),
        "helix_i": scalar(abs_i),
        "helix_order": scalar(0.5 * (abs_y + abs_i)),
        "opposition": opposition,
        "opposed_helical_moment": opposed_helical_moment,
        "center": center,
        "center_displacement": 0.0 if initial_center is None else v4.v3.base.center_displacement(center, initial_center),
        "max_density": scalar(torch.max(density)),
    }


def compare_converged_end(
    first: dict[str, Any], second: dict[str, Any], limit: float
) -> tuple[bool, dict[str, float]]:
    differences = {
        key: v4.v3.base.relative_difference(first[key], second[key])
        for key in ("r_fit", "core_fraction", "helix_order")
    }
    differences["opposed_helical_moment"] = abs(
        first["opposed_helical_moment"] - second["opposed_helical_moment"]
    )
    return all(value <= limit for value in differences.values()), differences


def evaluate_gates(
    arms: dict[str, dict[str, Any]], preflight: dict[str, Any]
) -> tuple[dict[str, Any], str, list[str], str]:
    gates, _, labels, _ = v4.v3.evaluate_gates(arms, preflight)

    q4_pass, q4_differences = compare_converged_end(
        arms["A"]["metrics"][-1], arms["J"]["metrics"][-1], 0.05
    )
    q4_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["J"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["J"]["metrics"][-1]["winding_i"]),
    )
    gates["Q4"] = {
        "pass": q4_pass and q4_winding <= 0.10,
        "differences": q4_differences,
        "winding_difference": q4_winding,
    }

    q5_pass, q5_differences = compare_converged_end(
        arms["A"]["metrics"][-1], arms["I"]["metrics"][-1], 0.10
    )
    q5_winding = max(
        abs(arms["A"]["metrics"][-1]["winding_y"] - arms["I"]["metrics"][-1]["winding_y"]),
        abs(arms["A"]["metrics"][-1]["winding_i"] - arms["I"]["metrics"][-1]["winding_i"]),
    )
    direction_agreement = v4.v3.survival(arms["A"]["metrics"]) == v4.v3.survival(arms["I"]["metrics"])
    gates["Q5"] = {
        "pass": q5_pass and q5_winding <= 0.10 and direction_agreement,
        "differences": q5_differences,
        "winding_difference": q5_winding,
        "direction_agreement": direction_agreement,
    }

    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))
    quality_ok = gates["Q1"] and all(gates[name]["pass"] for name in ("Q2", "Q3", "Q4", "Q5"))
    primary = v4.v3.survival(arms["A"]["metrics"])
    if not geometry_ok:
        verdict, perturbation_verdict = "INCONCLUSIVE—INVALID INITIALIZATION", "UNSCORED"
    elif not quality_ok:
        verdict, perturbation_verdict = "INCONCLUSIVE—NUMERICAL QUALITY", "UNSCORED"
    elif all(primary.values()):
        verdict = "EMERGES CONDITIONALLY"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    else:
        verdict = "DOES NOT EMERGE"
        perturbation_verdict = "PASS" if gates["P1"]["pass"] else "FAIL"
    return gates, verdict, labels, perturbation_verdict


def evolve_arm(
    arm: dict[str, Any],
    total_mass: float,
    device: torch.device,
    run_dir: Path,
) -> dict[str, Any]:
    grid = v4.make_grid(arm["n"], device)
    psi_y, psi_i = v4.v3.base.make_seed(arm["seed"], grid, total_mass)
    g = arm["g"]
    dt = arm["dt"]
    steps = round(CONSTANTS["t_end"] / dt)
    report_steps = round(CONSTANTS["report_cadence"] / dt)
    cube_root_two = 2.0 ** (1.0 / 3.0)
    w1 = 1.0 / (2.0 - cube_root_two)
    w0 = -cube_root_two / (2.0 - cube_root_two)
    coefficients = (w1, w0, w1)
    kinetic_phases = tuple(torch.exp(-0.5j * grid["k2"] * (coefficient * dt)) for coefficient in coefficients)
    phi_field = v4.v3.base.solve_phi(psi_y, psi_i, grid) if g != 0.0 else None
    initial_max_density = v4.v3.base.scalar(torch.max(torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2))
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
        row = diagnose(psi_y, psi_i, grid, g, time_value, phi_field, initial_center)
        if initial_center is None:
            initial_center = row["center"]
            row["center_displacement"] = 0.0
        metrics.append(row)
        times.append(time_value)
        fields_y.append(psi_y.detach().cpu().numpy().copy())
        fields_i.append(psi_i.detach().cpu().numpy().copy())

    capture(0)
    for step in range(1, steps + 1):
        for coefficient, kinetic_phase in zip(coefficients, kinetic_phases):
            substep = coefficient * dt
            if g != 0.0:
                phase = torch.exp(-0.5j * substep * g * phi_field)
                psi_y = psi_y * phase
                psi_i = psi_i * phase
            psi_y = torch.fft.ifftn(torch.fft.fftn(psi_y) * kinetic_phase)
            psi_i = torch.fft.ifftn(torch.fft.fftn(psi_i) * kinetic_phase)
            if g != 0.0:
                phi_field = v4.v3.base.solve_phi(psi_y, psi_i, grid)
                phase = torch.exp(-0.5j * substep * g * phi_field)
                psi_y = psi_y * phase
                psi_i = psi_i * phase

        density = torch.abs(psi_y) ** 2 + torch.abs(psi_i) ** 2
        if not bool(torch.isfinite(density).all().item()):
            status, stop_reason = "stopped", "nonfinite field"
            break
        if v4.v3.base.scalar(torch.max(density)) > 1.0e8 * initial_max_density:
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
        "fields_sha256": v4.v3.base.sha256_file(receipt_path),
    }


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
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_coherence_survival_v5"
    run_dir.mkdir(parents=True, exist_ok=False)

    source_names = (
        "toroidal-coherence-survival-pre-registration.md",
        *(f"toroidal-coherence-survival-{version}-pre-registration.md" for version in ("v2", "v3", "v4", "v5")),
        *(f"toroidal_coherence_survival_{version}_probe.py" for version in ("v2", "v3", "v4", "v5")),
        *(f"verify_toroidal_coherence_survival_{version}.py" for version in ("v2", "v3", "v4", "v5")),
    )
    source_paths = tuple(ROOT / "field-experience" / name for name in source_names)
    sources = {str(path.relative_to(ROOT)).replace("\\", "/"): v4.v3.base.sha256_file(path) for path in source_paths}

    reference_grid = v4.make_grid(CONSTANTS["reference_n"], device)
    unit_y, unit_i = v4.v3.base.make_seed("closed", reference_grid, 1.0)
    reference_phi = v4.v3.base.solve_phi(unit_y, unit_i, reference_grid)
    k1, w1, _ = energy_terms(unit_y, unit_i, reference_grid, 1.0, reference_phi)
    virial_mass = -2.0 * k1 / w1
    if w1 >= 0.0 or not math.isfinite(virial_mass) or not 0.1 <= virial_mass <= 1.0e6:
        raise RuntimeError(f"invalid virial calibration: K1={k1}, W1={w1}, M={virial_mass}")

    def initial(seed: str) -> dict[str, Any]:
        psi_y, psi_i = v4.v3.base.make_seed(seed, reference_grid, virial_mass)
        phi_field = v4.v3.base.solve_phi(psi_y, psi_i, reference_grid)
        return diagnose(psi_y, psi_i, reference_grid, 1.0, 0.0, phi_field, None)

    preflight = {
        "diagnostic": DIAGNOSTIC,
        "precision": "float64/complex128",
        "integrator": "yoshida_triple_jump_s4",
        "energy_dtype": "float64",
        "convergence_metric": "opposed_helical_moment",
        "closure_error": v4.v3.base.analytic_closure_error(),
        "k1": k1,
        "w1": w1,
        "virial_mass": virial_mass,
        "closed_initial": initial("closed"),
        "untwisted_initial": initial("untwisted"),
        "scrambled_initial": initial("scrambled"),
    }
    preflight_gates = v4.v3.initialization_gates(preflight)
    if not all(preflight_gates.values()):
        result = {
            "probe": "toroidal_coherence_survival_v5",
            "diagnostic": DIAGNOSTIC,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "constants": CONSTANTS,
            "arms_spec": ARMS,
            "sources": sources,
            "device": str(device),
            "dtype": "complex128/float64",
            "integrator": "yoshida_triple_jump_s4",
            "energy_dtype": "float64",
            "convergence_metric": "opposed_helical_moment",
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
        arm_results[arm["id"]] = evolve_arm(arm, virial_mass, device, run_dir)
        if arm_results[arm["id"]]["status"] != "complete":
            print(f"arm {arm['id']} stopped: {arm_results[arm['id']]['stop_reason']}", flush=True)

    gates, verdict, failure_labels, perturbation_verdict = evaluate_gates(arm_results, preflight)
    results = {
        "probe": "toroidal_coherence_survival_v5",
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
        "integrator": "yoshida_triple_jump_s4",
        "energy_dtype": "float64",
        "convergence_metric": "opposed_helical_moment",
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
    print(
        json.dumps(
            {
                "run_dir": str(run_dir),
                "verdict": verdict,
                "failure_labels": failure_labels,
                "perturbation_verdict": perturbation_verdict,
                "gates": gates,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
