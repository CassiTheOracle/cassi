#!/usr/bin/env python3
"""Run the preregistered V3 toroidal coherence survival campaign."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch

_BASE_PATH = Path(__file__).with_name("toroidal_coherence_survival_v2_probe.py")
_BASE_SPEC = importlib.util.spec_from_file_location("toroidal_coherence_survival_v2_probe", _BASE_PATH)
if _BASE_SPEC is None or _BASE_SPEC.loader is None:
    raise ImportError(f"cannot load {_BASE_PATH}")
base = importlib.util.module_from_spec(_BASE_SPEC)
_BASE_SPEC.loader.exec_module(base)

PHI = base.PHI
CONSTANTS = base.CONSTANTS
ARMS = base.ARMS
ROOT = base.ROOT
V1_PREREG = ROOT / "field-experience" / "toroidal-coherence-survival-pre-registration.md"
V2_PREREG = ROOT / "field-experience" / "toroidal-coherence-survival-v2-pre-registration.md"
V3_PREREG = ROOT / "field-experience" / "toroidal-coherence-survival-v3-pre-registration.md"
V2_PRIMARY = ROOT / "field-experience" / "toroidal_coherence_survival_v2_probe.py"
V2_VERIFIER = ROOT / "field-experience" / "verify_toroidal_coherence_survival_v2.py"
V3_VERIFIER = ROOT / "field-experience" / "verify_toroidal_coherence_survival_v3.py"
DIAGNOSTIC = "sector_normalized_phase_v3"

_original_diagnose = base.diagnose
_original_survival = base.survival
_original_evaluate_gates = base.evaluate_gates


def sector_statistics(field: torch.Tensor, grid: dict[str, Any], declared_winding: int) -> dict[str, float]:
    sectors = CONSTANTS["winding_sectors"]
    flat = field.reshape(-1)
    indices = grid["sector"]
    real = torch.zeros(sectors, device=field.device).scatter_add_(0, indices, flat.real)
    imag = torch.zeros(sectors, device=field.device).scatter_add_(0, indices, flat.imag)
    amplitude = torch.zeros(sectors, device=field.device).scatter_add_(0, indices, torch.abs(flat))
    values = torch.complex(real, imag)
    safe_amplitude = torch.clamp(amplitude, min=torch.finfo(amplitude.dtype).tiny)
    phasors = values / safe_amplitude
    increments = torch.angle(torch.roll(phasors, shifts=-1) * torch.conj(phasors))
    centers = (torch.arange(sectors, device=field.device, dtype=amplitude.dtype) + 0.5) * (2.0 * math.pi / sectors)
    demodulator = torch.exp(torch.complex(torch.zeros_like(centers), -declared_winding * centers))
    value_magnitudes = torch.abs(values)
    return {
        "winding": base.scalar(torch.sum(increments) / (2.0 * math.pi)),
        "phase_coherence": base.scalar(torch.min(torch.abs(phasors))),
        "sector_support": base.scalar(torch.min(amplitude) / torch.clamp(torch.mean(amplitude), min=1e-30)),
        "demodulated_coherence": base.scalar(torch.abs(torch.sum(values * demodulator)) / torch.clamp(torch.sum(amplitude), min=1e-30)),
        "legacy_sector_ratio": base.scalar(torch.min(value_magnitudes) / torch.clamp(torch.mean(value_magnitudes), min=1e-30)),
    }


def diagnose(
    psi_y: torch.Tensor,
    psi_i: torch.Tensor,
    grid: dict[str, Any],
    g: float,
    time_value: float,
    phi_field: torch.Tensor | None,
    initial_center: list[float] | None,
) -> dict[str, Any]:
    row = _original_diagnose(psi_y, psi_i, grid, g, time_value, phi_field, initial_center)
    stats_y = sector_statistics(psi_y, grid, CONSTANTS["yang_winding"])
    stats_i = sector_statistics(psi_i, grid, CONSTANTS["yin_winding"])
    row.update(
        winding_y=stats_y["winding"],
        winding_i=stats_i["winding"],
        coherence_y=stats_y["phase_coherence"],
        coherence_i=stats_i["phase_coherence"],
        phase_coherence_y=stats_y["phase_coherence"],
        phase_coherence_i=stats_i["phase_coherence"],
        sector_support_y=stats_y["sector_support"],
        sector_support_i=stats_i["sector_support"],
        demodulated_coherence_y=stats_y["demodulated_coherence"],
        demodulated_coherence_i=stats_i["demodulated_coherence"],
        legacy_sector_ratio_y=stats_y["legacy_sector_ratio"],
        legacy_sector_ratio_i=stats_i["legacy_sector_ratio"],
    )
    return row


def survival(metrics: list[dict[str, Any]]) -> dict[str, bool]:
    gates = _original_survival(metrics)
    gates["S1_winding"] = all(
        abs(row["winding_y"] - 2.0) <= 0.25
        and abs(row["winding_i"] + 3.0) <= 0.25
        and row["phase_coherence_y"] >= 0.50
        and row["phase_coherence_i"] >= 0.50
        and row["demodulated_coherence_y"] >= 0.50
        and row["demodulated_coherence_i"] >= 0.50
        and row["sector_support_y"] >= 0.05
        and row["sector_support_i"] >= 0.05
        for row in metrics
    )
    return gates


def initialization_gates(preflight: dict[str, Any]) -> dict[str, bool]:
    closed = preflight["closed_initial"]
    untwisted = preflight["untwisted_initial"]
    scrambled = preflight["scrambled_initial"]
    return {
        "G1": preflight["closure_error"] <= 1e-12,
        "G2": (
            abs(closed["winding_y"] - 2.0) <= 0.05
            and abs(closed["winding_i"] + 3.0) <= 0.05
            and closed["phase_coherence_y"] >= 0.95
            and closed["phase_coherence_i"] >= 0.95
            and closed["demodulated_coherence_y"] >= 0.95
            and closed["demodulated_coherence_i"] >= 0.95
            and closed["sector_support_y"] >= 0.05
            and closed["sector_support_i"] >= 0.05
            and scrambled["demodulated_coherence_y"] <= 0.50
            and scrambled["demodulated_coherence_i"] <= 0.50
        ),
        "G3": closed["helix_order"] >= 0.80 and closed["opposition"] >= 0.80 and untwisted["helix_order"] <= 0.20,
        "G4": (
            abs(closed["component_ratio"] - PHI) / PHI <= 1e-5
            and abs(closed["virial"]) / (2.0 * closed["kinetic"] + abs(closed["potential"])) <= 1e-5
        ),
    }


def evaluate_gates(
    arms: dict[str, dict[str, Any]], preflight: dict[str, Any]
) -> tuple[dict[str, Any], str, list[str], str]:
    gates, _, labels, _ = _original_evaluate_gates(arms, preflight)
    gates.update(initialization_gates(preflight))
    primary = survival(arms["A"]["metrics"])
    gates.update(primary)
    perturb = survival(arms["G"]["metrics"])
    perturb_compare, perturb_differences = base.compare_end(arms["A"]["metrics"][-1], arms["G"]["metrics"][-1], 0.15)
    gates["P1"] = {
        "pass": all(perturb.values()) and perturb_compare,
        "survival": perturb,
        "differences": perturb_differences,
    }
    geometry_ok = all(gates[name] for name in ("G1", "G2", "G3", "G4"))
    quality_ok = gates["Q1"] and all(gates[name]["pass"] for name in ("Q2", "Q3", "Q4", "Q5"))
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


setattr(base, "diagnose", diagnose)
setattr(base, "survival", survival)


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
    run_dir = args.output or ROOT / "runs" / f"{stamp}_toroidal_coherence_survival_v3"
    run_dir.mkdir(parents=True, exist_ok=False)

    source_paths = (Path(__file__).resolve(), V1_PREREG, V2_PREREG, V3_PREREG, V2_PRIMARY, V2_VERIFIER, V3_VERIFIER)
    sources = {str(path.relative_to(ROOT)).replace("\\", "/"): base.sha256_file(path) for path in source_paths}

    reference_grid = base.make_grid(CONSTANTS["reference_n"], device)
    unit_y, unit_i = base.make_seed("closed", reference_grid, 1.0)
    reference_phi = base.solve_phi(unit_y, unit_i, reference_grid)
    k1, w1, _ = base.energy_terms(unit_y, unit_i, reference_grid, 1.0, reference_phi)
    virial_mass = -2.0 * k1 / w1
    if w1 >= 0.0 or not math.isfinite(virial_mass) or not 0.1 <= virial_mass <= 1.0e6:
        raise RuntimeError(f"invalid virial calibration: K1={k1}, W1={w1}, M={virial_mass}")

    def initial(seed: str) -> dict[str, Any]:
        psi_y, psi_i = base.make_seed(seed, reference_grid, virial_mass)
        phi_field = base.solve_phi(psi_y, psi_i, reference_grid)
        return diagnose(psi_y, psi_i, reference_grid, 1.0, 0.0, phi_field, None)

    preflight = {
        "diagnostic": DIAGNOSTIC,
        "closure_error": base.analytic_closure_error(),
        "k1": k1,
        "w1": w1,
        "virial_mass": virial_mass,
        "closed_initial": initial("closed"),
        "untwisted_initial": initial("untwisted"),
        "scrambled_initial": initial("scrambled"),
    }
    preflight_gates = initialization_gates(preflight)
    if not all(preflight_gates.values()):
        result = {
            "probe": "toroidal_coherence_survival_v3",
            "diagnostic": DIAGNOSTIC,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "constants": CONSTANTS,
            "sources": sources,
            "device": str(device),
            "dtype": "complex64/float32",
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
        arm_results[arm["id"]] = base.evolve_arm(arm, virial_mass, device, run_dir)
        if arm_results[arm["id"]]["status"] != "complete":
            print(f"arm {arm['id']} stopped: {arm_results[arm['id']]['stop_reason']}", flush=True)

    gates, verdict, failure_labels, perturbation_verdict = evaluate_gates(arm_results, preflight)
    results = {
        "probe": "toroidal_coherence_survival_v3",
        "diagnostic": DIAGNOSTIC,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "constants": CONSTANTS,
        "arms": arm_results,
        "sources": sources,
        "device": str(device),
        "device_name": torch.cuda.get_device_name(0) if device.type == "cuda" else "CPU",
        "torch_version": torch.__version__,
        "dtype": "complex64/float32",
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
