#!/usr/bin/env python3
"""Independently verify the QCD cosmological matter-completion receipt.

This program intentionally does not import the primary implementation. It uses
a logarithmic-time, rescaled leptogenesis system, event-bounded annihilation,
and a real-space finite-difference nonradial evolution.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
from scipy import integrate, special


ROOT = Path(__file__).resolve().parents[1]
PRIMARY_DIR = (
    ROOT / "runs" / "20260910_qcd_cosmological_matter_completion" / "primary"
)
OUTPUT_DIR = (
    ROOT / "runs" / "20260910_qcd_cosmological_matter_completion" / "verification"
)
RESULTS = PRIMARY_DIR / "results.json"
FIELDS = PRIMARY_DIR / "nonradial_fields.npz"
SCHEMA = "cassi.qcd-cosmological-matter-completion.verification.v1"
PI = math.pi


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def relative_difference(left: float, right: float, floor: float = 1.0e-300) -> float:
    return abs(left - right) / max(abs(left), abs(right), floor)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, np.generic):
        return json_ready(value.item())
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite verification value: {value}")
    return value


def decode_complex(rows: list[list[dict[str, float]]]) -> np.ndarray:
    return np.array(
        [
            [complex(item["real"], item["imag"]) for item in row]
            for row in rows
        ],
        dtype=np.complex128,
    )


def pmns() -> np.ndarray:
    s12, s23, s13 = map(math.sqrt, (0.304, 0.573, 0.02219))
    c12, c23, c13 = map(math.sqrt, (0.696, 0.427, 0.97781))
    phase = np.exp(1j * math.radians(195.0))
    return np.array(
        [
            [c12 * c13, s12 * c13, s13 / phase],
            [
                -s12 * c23 - c12 * s23 * s13 * phase,
                c12 * c23 - s12 * s23 * s13 * phase,
                s23 * c13,
            ],
            [
                s12 * s23 - c12 * c23 * s13 * phase,
                -c12 * s23 - s12 * c23 * s13 * phase,
                c23 * c13,
            ],
        ],
        dtype=np.complex128,
    )


def independent_leptogenesis(receipt: dict[str, Any]) -> dict[str, Any]:
    constants = receipt["constants"]
    recorded = receipt["leptogenesis"]["primary"]
    mass_1 = float(recorded["mass_1_gev"])
    ratio = float(constants["heavy_mass_ratio"])
    mass_2 = ratio * mass_1
    v_higgs = float(constants["v_higgs_gev"])
    masses_ev = np.asarray(constants["light_masses_ev"], dtype=np.float64)
    masses_gev = masses_ev * 1.0e-9
    z_row = constants["casas_ibarra_z"]
    z_value = complex(z_row["real"], z_row["imag"])
    rotation = np.array(
        [
            [0.0, 0.0],
            [np.cos(z_value), -np.sin(z_value)],
            [np.sin(z_value), np.cos(z_value)],
        ],
        dtype=np.complex128,
    )
    yukawa = (
        pmns()
        @ np.diag(np.sqrt(masses_gev))
        @ rotation
        @ np.diag(np.sqrt([mass_1, mass_2]))
        / v_higgs
    )
    recorded_yukawa = decode_complex(recorded["yukawa"])
    h_matrix = yukawa.conj().T @ yukawa
    effective_mass_ev = h_matrix[0, 0].real * v_higgs**2 / mass_1 * 1.0e9
    decay_parameter = effective_mass_ev / float(constants["m_star_ev"])
    hierarchy = ratio**2
    loop = math.sqrt(hierarchy) * (
        1.0 / (1.0 - hierarchy)
        + 1.0
        - (1.0 + hierarchy) * math.log((1.0 + hierarchy) / hierarchy)
    )
    epsilon = float(
        (h_matrix[0, 1] ** 2).imag
        * loop
        / (8.0 * PI * h_matrix[0, 0].real)
    )

    reconstructed = (
        v_higgs**2
        * yukawa
        @ np.diag([1.0 / mass_1, 1.0 / mass_2])
        @ yukawa.T
    )
    reconstructed_masses = np.sort(np.linalg.svd(reconstructed, compute_uv=False)) * 1.0e9
    mass_error = float(
        np.max(np.abs(reconstructed_masses[1:] - masses_ev[1:]) / masses_ev[1:])
    )

    x_initial = 1.0e-3
    x_final = 50.0
    initial_heavy = 0.5 * x_initial**2 * special.kv(2, x_initial)

    def log_rhs(log_x: float, state: np.ndarray) -> np.ndarray:
        x_value = math.exp(log_x)
        k1 = special.kv(1, x_value)
        k2 = special.kv(2, x_value)
        equilibrium = 0.5 * x_value**2 * k2
        decay = decay_parameter * x_value * k1 / k2
        washout = 0.25 * decay_parameter * x_value**3 * k1
        departure = decay * (state[0] - equilibrium)
        # state[1] is N_(B-L) / epsilon, keeping both variables O(1).
        return x_value * np.array(
            [-departure, -departure - washout * state[1]], dtype=np.float64
        )

    solution = integrate.solve_ivp(
        log_rhs,
        (math.log(x_initial), math.log(x_final)),
        np.array([initial_heavy, 0.0]),
        method="BDF",
        rtol=2.0e-11,
        atol=2.0e-13,
        max_step=0.01,
    )
    if not solution.success:
        raise RuntimeError(f"independent leptogenesis solve failed: {solution.message}")
    b_minus_l = epsilon * float(solution.y[1, -1])
    eta_b = 0.96e-2 * abs(b_minus_l)
    davidson_ibarra_bound = (
        3.0 * mass_1 * masses_ev[-1] * 1.0e-9 / (16.0 * PI * v_higgs**2)
    )
    return {
        "mass_1_gev": mass_1,
        "mass_2_gev": mass_2,
        "yukawa_max_absolute_difference": float(
            np.max(np.abs(yukawa - recorded_yukawa))
        ),
        "effective_mass_ev": float(effective_mass_ev),
        "decay_parameter": float(decay_parameter),
        "epsilon_1": epsilon,
        "davidson_ibarra_bound": davidson_ibarra_bound,
        "davidson_ibarra_pass": abs(epsilon) <= davidson_ibarra_bound,
        "reconstructed_masses_ev": reconstructed_masses,
        "mass_reconstruction_relative_error": mass_error,
        "final_b_minus_l": b_minus_l,
        "eta_b": eta_b,
        "primary_eta_b": float(recorded["eta_b"]),
        "eta_b_relative_difference": relative_difference(
            eta_b, float(recorded["eta_b"])
        ),
        "solver_method": "BDF in log(M1/T), rescaled B-L",
        "solver_success": bool(solution.success),
        "function_evaluations": int(solution.nfev),
    }


def gstar(temperature: float) -> float:
    return float(
        np.interp(
            temperature,
            np.array([0.001, 0.010, 0.100, 0.1565]),
            np.array([10.75, 10.75, 17.25, 61.75]),
        )
    )


def equilibrium_yield(temperature: float, mass: float) -> float:
    argument = mass / temperature
    bessel = (
        0.0
        if argument >= 745.0
        else float(math.exp(-argument) * special.kve(2, argument))
    )
    density = 4.0 * mass**2 * temperature * bessel / (2.0 * PI**2)
    entropy = 2.0 * PI**2 / 45.0 * gstar(temperature) * temperature**3
    return density / entropy


def independent_chemistry(
    receipt: dict[str, Any], cross_section_mb: float
) -> dict[str, Any]:
    constants = receipt["constants"]
    eta_b = float(receipt["leptogenesis"]["primary"]["eta_b"])
    net = eta_b / 7.04
    mass = float(constants["nucleon_mean_mass_gev"])
    critical_temperature = float(constants["qcd_crossover_temperature_gev"])
    planck = float(constants["planck_mass_gev"])
    equilibrium_initial = equilibrium_yield(critical_temperature, mass)
    anti_initial = (
        -net + math.hypot(net, 2.0 * equilibrium_initial)
    ) / 2.0
    w_final = math.log(critical_temperature / 0.001)

    def rhs(log_scale: float, state: np.ndarray) -> np.ndarray:
        temperature = critical_temperature * math.exp(-log_scale)
        freedom = gstar(temperature)
        entropy = 2.0 * PI**2 / 45.0 * freedom * temperature**3
        hubble = 1.66 * math.sqrt(freedom) * temperature**2 / planck
        equilibrium = equilibrium_yield(temperature, mass)
        anti = max(float(state[0]), 0.0)
        coefficient = entropy * (cross_section_mb / 0.389379) / hubble
        return np.array(
            [-coefficient * (anti * (anti + net) - equilibrium**2)],
            dtype=np.float64,
        )

    def threshold(_log_scale: float, state: np.ndarray) -> float:
        anti = float(state[0])
        return anti / (2.0 * anti + net) - 1.0e-8

    threshold_event: Any = threshold
    threshold_event.terminal = True
    threshold_event.direction = -1
    solution = integrate.solve_ivp(
        rhs,
        (0.0, w_final),
        np.array([anti_initial]),
        method="Radau",
        events=threshold_event,
        rtol=1.0e-9,
        atol=1.0e-20,
        max_step=0.01,
    )
    if not solution.success:
        raise RuntimeError(f"independent chemistry solve failed: {solution.message}")
    event_reached = bool(solution.t_events[0].size)
    event_w = float(solution.t_events[0][0]) if event_reached else float(solution.t[-1])
    anti = float(solution.y_events[0][0, 0]) if event_reached else float(solution.y[0, -1])
    fraction = anti / (2.0 * anti + net)
    event_temperature = critical_temperature * math.exp(-event_w)
    equilibrium_at_event = equilibrium_yield(event_temperature, mass)
    equilibrium_root = (
        -net + math.hypot(net, 2.0 * equilibrium_at_event)
    ) / 2.0
    derivative_at_event = float(rhs(event_w, np.array([anti]))[0])
    # Below the event temperature the equilibrium root decreases monotonically;
    # a negative derivative therefore makes the event fraction an upper bound.
    monotone_upper_bound = bool(
        event_reached and anti >= equilibrium_root and derivative_at_event <= 0.0
    )
    return {
        "cross_section_mb": cross_section_mb,
        "event_reached": event_reached,
        "event_temperature_mev": 1000.0 * event_temperature,
        "antibaryon_fraction_at_event": fraction,
        "equilibrium_antibaryon_yield_at_event": equilibrium_root,
        "antibaryon_yield_at_event": anti,
        "derivative_at_event": derivative_at_event,
        "final_fraction_upper_bound": fraction if monotone_upper_bound else 1.0,
        "monotone_upper_bound": monotone_upper_bound,
        "solver_method": "Radau event bound in log scale factor",
        "function_evaluations": int(solution.nfev),
    }


def nonzero_rms(pair: np.ndarray) -> float:
    values = []
    for field in pair:
        centered = field - float(np.mean(field))
        values.append(float(np.mean(centered * centered)))
    return math.sqrt(0.5 * sum(values))


def finite_difference_rhs(pair: np.ndarray, diffusion: float) -> np.ndarray:
    laplacians = []
    for field in pair:
        laplacian = -6.0 * field
        for axis in range(3):
            laplacian = laplacian + np.roll(field, 1, axis=axis)
            laplacian = laplacian + np.roll(field, -1, axis=axis)
        laplacians.append(laplacian)
    reaction = -(pair[0] * pair[1] - 1.0)
    return np.stack(
        (
            diffusion * laplacians[0] + reaction,
            diffusion * laplacians[1] + reaction,
        ),
        axis=0,
    )


def independent_nonradial(
    receipt: dict[str, Any], arrays: dict[str, np.ndarray]
) -> dict[str, Any]:
    initial = np.stack(
        (arrays["initial_baryon"], arrays["initial_antibaryon"]), axis=0
    )
    recorded_final = np.stack(
        (arrays["final_baryon"], arrays["final_antibaryon"]), axis=0
    )
    recorded = receipt["nonradial"]
    initial_rms = nonzero_rms(initial)
    recorded_rms = nonzero_rms(recorded_final)
    initial_net = float(np.mean(initial[0] - initial[1]))
    recorded_net = float(np.mean(recorded_final[0] - recorded_final[1]))

    time_step = 0.0025
    steps = 8000
    pair = initial.copy()
    minimum = float(np.min(pair))
    for _ in range(steps):
        first = finite_difference_rhs(pair, 0.2)
        trial = pair + time_step * first
        second = finite_difference_rhs(trial, 0.2)
        pair += 0.5 * time_step * (first + second)
        minimum = min(minimum, float(np.min(pair)))
    independent_rms = nonzero_rms(pair)
    independent_net = float(np.mean(pair[0] - pair[1]))
    independent_pair_mean = float(np.mean(pair[0] + pair[1]))
    recorded_pair_mean = float(np.mean(recorded_final[0] + recorded_final[1]))
    return {
        "method": "periodic second-order finite differences with Heun time stepping",
        "time_step": time_step,
        "steps": steps,
        "initial_nonzero_mode_rms": initial_rms,
        "recorded_final_nonzero_mode_rms_recomputed": recorded_rms,
        "recorded_metric_relative_difference": relative_difference(
            recorded_rms, float(recorded["final_nonzero_mode_rms"])
        ),
        "independent_final_nonzero_mode_rms": independent_rms,
        "independent_rms_ratio": independent_rms / initial_rms,
        "recorded_to_independent_final_rms_relative_difference": relative_difference(
            recorded_rms, independent_rms
        ),
        "minimum_density": minimum,
        "initial_net_mean": initial_net,
        "recorded_final_net_mean": recorded_net,
        "independent_final_net_mean": independent_net,
        "independent_net_conservation_absolute_error": abs(
            independent_net - initial_net
        ),
        "recorded_final_pair_mean": recorded_pair_mean,
        "independent_final_pair_mean": independent_pair_mean,
        "final_pair_mean_relative_difference": relative_difference(
            recorded_pair_mean, independent_pair_mean
        ),
    }


def main() -> int:
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"refusing to overwrite verification: {OUTPUT_DIR}")
    started = time.time()
    receipt = json.loads(RESULTS.read_text(encoding="utf-8"))
    if receipt.get("schema") != "cassi.qcd-cosmological-matter-completion.primary.v1":
        raise ValueError("unexpected primary schema")

    source_rows = []
    source_hash_pass = True
    for row in receipt["sources"]:
        path = ROOT / row["path"]
        actual = digest(path) if path.is_file() else None
        passed = actual == row["sha256"]
        source_hash_pass &= passed
        source_rows.append(
            {
                "path": row["path"],
                "recorded_sha256": row["sha256"],
                "actual_sha256": actual,
                "pass": passed,
            }
        )

    with np.load(FIELDS, allow_pickle=False) as loaded:
        arrays = {key: loaded[key] for key in loaded.files}
    leptogenesis = independent_leptogenesis(receipt)
    chemistry = [
        independent_chemistry(receipt, value) for value in (40.0, 50.0, 60.0)
    ]
    nonradial = independent_nonradial(receipt, arrays)

    expected_gates = {
        "PCM1": "PASS EMPIRICAL",
        "PCM2": "PASS CALIBRATED",
        "PCM2_no_fit_mapped_seesaw_scale": "CONTRADICTS",
        "PCM3": "SUPPORTS",
        "PCM4": "SUPPORTS",
        "PCM5": "PASS EMPIRICAL",
        "conditional_empirical_matter_history": "SUPPORTS",
        "complete_physical_Cassi_matter_formation": "FAIL",
    }
    checks = {
        "source_hashes": source_hash_pass,
        "primary_execution_valid": bool(receipt["execution_valid"]),
        "yukawa_reconstruction": leptogenesis[
            "yukawa_max_absolute_difference"
        ]
        < 1.0e-14,
        "light_mass_reconstruction": leptogenesis[
            "mass_reconstruction_relative_error"
        ]
        < 1.0e-10,
        "davidson_ibarra_bound": bool(leptogenesis["davidson_ibarra_pass"]),
        "leptogenesis_agreement": leptogenesis["eta_b_relative_difference"]
        < 5.0e-4,
        "chemistry_event_bounds": all(
            row["event_reached"]
            and row["monotone_upper_bound"]
            and row["final_fraction_upper_bound"] < 1.0e-6
            for row in chemistry
        ),
        "recorded_nonradial_metric": nonradial[
            "recorded_metric_relative_difference"
        ]
        < 1.0e-12,
        "independent_nonradial_positivity": nonradial["minimum_density"] > 0.0,
        "independent_nonradial_decay": nonradial["independent_rms_ratio"]
        <= 0.10,
        "independent_nonradial_conservation": nonradial[
            "independent_net_conservation_absolute_error"
        ]
        < 2.0e-13,
        "independent_nonradial_pair_mean": nonradial[
            "final_pair_mean_relative_difference"
        ]
        < 1.0e-3,
        "gate_reconstruction": receipt["gates"] == expected_gates,
        "lattice_mass_pull": receipt["evidence"]["lattice_nucleon"][
            "mass_pull_sigma"
        ]
        <= 1.0,
        "qcd_asymptotic_freedom": receipt["evidence"]["microscopic_action"][
            "qcd_beta_0"
        ]
        > 0.0,
        "cassi_origin_remains_unselected": not any(
            value
            for key, value in receipt["evidence"]["registered_cassi_origin"].items()
            if key.startswith("selects_")
        ),
    }
    verification_pass = all(checks.values())
    output = {
        "schema": SCHEMA,
        "primary_results_sha256": digest(RESULTS),
        "primary_fields_sha256": digest(FIELDS),
        "environment": {
            "python": sys.version,
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": __import__("scipy").__version__,
        },
        "sources": source_rows,
        "leptogenesis": leptogenesis,
        "chemistry": chemistry,
        "nonradial": nonradial,
        "expected_gates": expected_gates,
        "checks": checks,
        "verification_pass": verification_pass,
        "elapsed_seconds": time.time() - started,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)
    target = OUTPUT_DIR / "verification.json"
    target.write_text(
        json.dumps(json_ready(output), indent=2, ensure_ascii=False, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )
    print("QCD COSMOLOGICAL MATTER COMPLETION INDEPENDENT VERIFICATION")
    for name, passed in checks.items():
        print(f"{name}={'PASS' if passed else 'FAIL'}")
    print(f"ETA_B_INDEPENDENT={leptogenesis['eta_b']:.12e}")
    print(f"NONRADIAL_RMS_RATIO_INDEPENDENT={nonradial['independent_rms_ratio']:.9e}")
    print(f"VERIFICATION={'PASS' if verification_pass else 'FAIL'}")
    print(f"RESULTS={target.relative_to(ROOT).as_posix()}")
    return 0 if verification_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
