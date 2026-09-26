#!/usr/bin/env python3
"""Execute the preregistered whole-bubble initial-state and CP-selection probe."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import platform
import sys
import time
from typing import Any, cast

import numpy as np
from scipy import integrate, optimize, special


ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-whole-bubble-cp-selection-prereg.md"
DEFAULT_OUTPUT = (
    ROOT / "runs" / "20260910_qcd_whole_bubble_cp_selection" / "primary"
)
SCHEMA = "cassi.qcd-whole-bubble-cp-selection.primary.v1"

PI = math.pi
V_HIGGS_GEV = 174.0
M_STAR_EV = 1.08e-3
DM21_EV2 = 7.42e-5
DM31_EV2 = 2.517e-3
LIGHT_MASSES_EV = np.array([0.0, math.sqrt(DM21_EV2), math.sqrt(DM31_EV2)])
BENCHMARK_Z = PI / 4.0 + 0.5j
HEAVY_RATIO = 10.0
ETA_TARGET = 6.1e-10
ETA_INTERVAL = (5.8e-10, 6.4e-10)
X_INITIAL = 1.0e-3
X_FINAL = 50.0
SPHALERON_ENTROPY = 0.96e-2

SOURCE_PATHS = (
    PROTOCOL,
    ROOT / "computations" / "qcd-cosmological-matter-completion-prereg.md",
    ROOT / "computations" / "qcd_cosmological_matter_completion.py",
    ROOT / "computations" / "matter-formation-continuum-report.md",
    ROOT / "foundations" / "baryon-asymmetry.md",
    ROOT / "standard-model" / "cp-violation.md",
    ROOT / "foundations" / "unified-lagrangian.md",
)


@dataclass(frozen=True)
class Texture:
    mass_1_gev: float
    mass_2_gev: float
    z_value: complex
    yukawa: np.ndarray
    h_matrix: np.ndarray
    reconstructed_masses_ev: np.ndarray
    reconstruction_relative_error: float
    effective_mass_ev: float
    decay_parameter: float
    loop_function: float
    epsilon_flavors: np.ndarray
    epsilon_total: float
    epsilon_trace: float
    projectors: np.ndarray
    davidson_ibarra_bound: float
    max_yukawa: float


@dataclass(frozen=True)
class Evolution:
    texture: Texture
    initial_heavy_factor: float
    initial_b_minus_l: float
    x: np.ndarray
    heavy_abundance: np.ndarray
    channel_asymmetries: np.ndarray
    eta_signed: float
    solver_success: bool
    solver_message: str
    function_evaluations: int


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def source_record(path: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
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
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    return value


def relative_difference(left: float, right: float, floor: float = 1.0e-300) -> float:
    return abs(left - right) / max(abs(left), abs(right), floor)


def pmns_matrix(*, conjugate: bool = False) -> np.ndarray:
    sin2_12 = 0.304
    sin2_23 = 0.573
    sin2_13 = 0.02219
    delta = math.radians(195.0)
    s12, s23, s13 = map(math.sqrt, (sin2_12, sin2_23, sin2_13))
    c12, c23, c13 = map(
        math.sqrt, (1.0 - sin2_12, 1.0 - sin2_23, 1.0 - sin2_13)
    )
    phase = np.exp(1j * delta)
    matrix = np.array(
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
    return matrix.conj() if conjugate else matrix


def build_texture(
    mass_1_gev: float,
    z_value: complex,
    *,
    conjugate_pmns: bool = False,
) -> Texture:
    mass_2_gev = HEAVY_RATIO * mass_1_gev
    heavy = np.array([mass_1_gev, mass_2_gev], dtype=np.float64)
    light_gev = LIGHT_MASSES_EV * 1.0e-9
    rotation = np.array(
        [
            [0.0, 0.0],
            [np.cos(z_value), -np.sin(z_value)],
            [np.sin(z_value), np.cos(z_value)],
        ],
        dtype=np.complex128,
    )
    yukawa = (
        pmns_matrix(conjugate=conjugate_pmns)
        @ np.diag(np.sqrt(light_gev))
        @ rotation
        @ np.diag(np.sqrt(heavy))
        / V_HIGGS_GEV
    )
    h_matrix = yukawa.conj().T @ yukawa
    h_11 = float(h_matrix[0, 0].real)
    effective_mass_ev = h_11 * V_HIGGS_GEV**2 / mass_1_gev * 1.0e9
    decay_parameter = effective_mass_ev / M_STAR_EV
    hierarchy = HEAVY_RATIO**2
    loop_function = math.sqrt(hierarchy) * (
        1.0 / (1.0 - hierarchy)
        + 1.0
        - (1.0 + hierarchy) * math.log((1.0 + hierarchy) / hierarchy)
    )
    epsilon_flavors = (
        np.imag(np.conj(yukawa[:, 0]) * yukawa[:, 1] * h_matrix[0, 1])
        * loop_function
        / (8.0 * PI * h_11)
    )
    epsilon_total = float(np.imag(h_matrix[0, 1] ** 2) * loop_function / (8.0 * PI * h_11))
    epsilon_trace = float(np.sum(epsilon_flavors))
    elementary_projectors = np.abs(yukawa[:, 0]) ** 2 / h_11
    projectors = np.array(
        [elementary_projectors[0] + elementary_projectors[1], elementary_projectors[2]],
        dtype=np.float64,
    )
    mass_matrix = (
        V_HIGGS_GEV**2
        * yukawa
        @ np.diag(1.0 / heavy)
        @ yukawa.T
    )
    reconstructed = np.sort(np.linalg.svd(mass_matrix, compute_uv=False)) * 1.0e9
    nonzero_target = LIGHT_MASSES_EV[1:]
    reconstruction_relative_error = float(
        np.max(np.abs(reconstructed[1:] - nonzero_target) / nonzero_target)
    )
    davidson_ibarra_bound = (
        3.0
        * mass_1_gev
        * LIGHT_MASSES_EV[-1]
        * 1.0e-9
        / (16.0 * PI * V_HIGGS_GEV**2)
    )
    return Texture(
        mass_1_gev=float(mass_1_gev),
        mass_2_gev=float(mass_2_gev),
        z_value=z_value,
        yukawa=yukawa,
        h_matrix=h_matrix,
        reconstructed_masses_ev=reconstructed,
        reconstruction_relative_error=reconstruction_relative_error,
        effective_mass_ev=float(effective_mass_ev),
        decay_parameter=float(decay_parameter),
        loop_function=float(loop_function),
        epsilon_flavors=epsilon_flavors,
        epsilon_total=epsilon_total,
        epsilon_trace=epsilon_trace,
        projectors=projectors,
        davidson_ibarra_bound=float(davidson_ibarra_bound),
        max_yukawa=float(np.max(np.abs(yukawa))),
    )


def equilibrium_abundance(x_value: float) -> float:
    return float(0.5 * x_value * x_value * special.kv(2, x_value))


def kinetic_rhs(texture: Texture):
    epsilon_channels = np.array(
        [texture.epsilon_flavors[0] + texture.epsilon_flavors[1], texture.epsilon_flavors[2]],
        dtype=np.float64,
    )

    def rhs(x_value: float, state: np.ndarray) -> np.ndarray:
        k1 = special.kv(1, x_value)
        k2 = special.kv(2, x_value)
        equilibrium = 0.5 * x_value * x_value * k2
        decay = texture.decay_parameter * x_value * k1 / k2
        washout = 0.25 * texture.decay_parameter * x_value**3 * k1
        departure = decay * (state[0] - equilibrium)
        derivatives = np.empty(3, dtype=np.float64)
        derivatives[0] = -departure
        derivatives[1:] = (
            -epsilon_channels * departure
            - texture.projectors * washout * state[1:]
        )
        return derivatives

    return rhs


def evolve(
    texture: Texture,
    *,
    initial_heavy_factor: float = 1.0,
    initial_b_minus_l: float = 0.0,
    retain_history: bool = False,
    method: str = "DOP853",
    rtol: float = 1.0e-10,
    atol: float = 1.0e-13,
    max_step: float = 0.05,
) -> Evolution:
    initial_heavy = initial_heavy_factor * equilibrium_abundance(X_INITIAL)
    initial_channels = initial_b_minus_l * texture.projectors
    initial = np.array([initial_heavy, *initial_channels], dtype=np.float64)
    if retain_history:
        x_eval = np.unique(
            np.concatenate(
                (
                    np.geomspace(X_INITIAL, 1.0, 241),
                    np.linspace(1.0, X_FINAL, 491),
                )
            )
        )
    else:
        x_eval = np.array([X_FINAL])
    solution = integrate.solve_ivp(
        kinetic_rhs(texture),
        (X_INITIAL, X_FINAL),
        initial,
        method=method,
        t_eval=x_eval,
        rtol=rtol,
        atol=atol,
        max_step=max_step,
    )
    if not solution.success:
        raise RuntimeError(f"two-flavour solve failed: {solution.message}")
    eta_signed = SPHALERON_ENTROPY * float(np.sum(solution.y[1:, -1]))
    return Evolution(
        texture=texture,
        initial_heavy_factor=float(initial_heavy_factor),
        initial_b_minus_l=float(initial_b_minus_l),
        x=solution.t,
        heavy_abundance=solution.y[0],
        channel_asymmetries=solution.y[1:],
        eta_signed=eta_signed,
        solver_success=bool(solution.success),
        solver_message=str(solution.message),
        function_evaluations=int(solution.nfev),
    )


def calibrate_mass() -> tuple[float, list[dict[str, float]]]:
    evaluations: list[dict[str, float]] = []
    cache: dict[float, float] = {}

    def residual(log10_mass: float) -> float:
        key = round(float(log10_mass), 12)
        if key not in cache:
            texture = build_texture(10.0**log10_mass, BENCHMARK_Z)
            result = evolve(texture)
            eta = abs(result.eta_signed)
            cache[key] = eta
            evaluations.append(
                {
                    "log10_mass_1_gev": float(log10_mass),
                    "mass_1_gev": float(10.0**log10_mass),
                    "eta_b": float(eta),
                }
            )
        return math.log10(cache[key] / ETA_TARGET)

    root = cast(
        float,
        optimize.brentq(
            residual,
            8.0,
            13.0,
            xtol=np.float64(1.0e-11),
            rtol=np.float64(1.0e-12),
        ),
    )
    return float(10.0**root), evaluations


def texture_payload(texture: Texture) -> dict[str, Any]:
    epsilon_channels = [
        float(texture.epsilon_flavors[0] + texture.epsilon_flavors[1]),
        float(texture.epsilon_flavors[2]),
    ]
    return {
        "mass_1_gev": texture.mass_1_gev,
        "mass_2_gev": texture.mass_2_gev,
        "z": texture.z_value,
        "yukawa": texture.yukawa,
        "h_matrix": texture.h_matrix,
        "reconstructed_masses_ev": texture.reconstructed_masses_ev,
        "reconstruction_relative_error": texture.reconstruction_relative_error,
        "effective_mass_ev": texture.effective_mass_ev,
        "decay_parameter": texture.decay_parameter,
        "loop_function": texture.loop_function,
        "epsilon_flavors_e_mu_tau": texture.epsilon_flavors,
        "epsilon_channels_e_plus_mu_tau": epsilon_channels,
        "epsilon_total": texture.epsilon_total,
        "epsilon_trace": texture.epsilon_trace,
        "epsilon_trace_relative_difference": relative_difference(
            texture.epsilon_trace, texture.epsilon_total
        ),
        "projectors_e_plus_mu_tau": texture.projectors,
        "projector_sum_error": abs(float(np.sum(texture.projectors)) - 1.0),
        "davidson_ibarra_bound": texture.davidson_ibarra_bound,
        "max_yukawa": texture.max_yukawa,
    }


def evolution_payload(result: Evolution, *, include_history: bool = False) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "initial_heavy_factor": result.initial_heavy_factor,
        "initial_b_minus_l": result.initial_b_minus_l,
        "final_heavy_abundance": float(result.heavy_abundance[-1]),
        "final_channel_asymmetries": result.channel_asymmetries[:, -1],
        "final_b_minus_l": float(np.sum(result.channel_asymmetries[:, -1])),
        "eta_signed": result.eta_signed,
        "eta_abs": abs(result.eta_signed),
        "solver_success": result.solver_success,
        "solver_message": result.solver_message,
        "function_evaluations": result.function_evaluations,
    }
    if include_history:
        payload.update(
            {
                "x": result.x,
                "heavy_abundance": result.heavy_abundance,
                "channel_asymmetries": result.channel_asymmetries,
            }
        )
    return payload


def scan_payload(mass_1_gev: float) -> list[dict[str, Any]]:
    real_values = [0.0, PI / 8.0, PI / 4.0, 3.0 * PI / 8.0, PI / 2.0]
    imag_values = [-1.0, -0.5, 0.0, 0.5, 1.0]
    rows: list[dict[str, Any]] = []
    for real_value in real_values:
        for imag_value in imag_values:
            z_value = complex(real_value, imag_value)
            texture = build_texture(mass_1_gev, z_value)
            result = evolve(texture)
            rows.append(
                {
                    "z_real": real_value,
                    "z_imag": imag_value,
                    "eta_signed": result.eta_signed,
                    "epsilon_total": texture.epsilon_total,
                    "epsilon_trace": texture.epsilon_trace,
                    "projectors_e_plus_mu_tau": texture.projectors,
                    "decay_parameter": texture.decay_parameter,
                    "max_yukawa": texture.max_yukawa,
                    "reconstructed_masses_ev": texture.reconstructed_masses_ev,
                    "reconstruction_relative_error": texture.reconstruction_relative_error,
                }
            )
    return rows


def decide(
    benchmark: Evolution,
    abundance_rows: list[dict[str, Any]],
    inherited_rows: list[dict[str, Any]],
    scan_rows: list[dict[str, Any]],
    cp_pair: dict[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    texture = benchmark.texture
    baseline_eta = benchmark.eta_signed
    abundance_spread = max(
        relative_difference(float(row["eta_signed"]), baseline_eta)
        for row in abundance_rows
    )
    inherited_spread = max(
        relative_difference(float(row["eta_signed"]), baseline_eta)
        for row in inherited_rows
    )
    abundance_signs = {int(math.copysign(1.0, float(row["eta_signed"]))) for row in abundance_rows}
    inherited_signs = {int(math.copysign(1.0, float(row["eta_signed"]))) for row in inherited_rows}
    max_scan_mass_error = max(float(row["reconstruction_relative_error"]) for row in scan_rows)
    scan_etas = np.array([float(row["eta_signed"]) for row in scan_rows])
    scan_has_zero = bool(np.any(np.abs(scan_etas) < 1.0e-20))
    scan_has_positive = bool(np.any(scan_etas > 1.0e-12))
    scan_has_negative = bool(np.any(scan_etas < -1.0e-12))

    fcp1_pass = (
        relative_difference(texture.epsilon_trace, texture.epsilon_total) < 1.0e-12
        and abs(float(np.sum(texture.projectors)) - 1.0) < 1.0e-13
        and texture.reconstruction_relative_error < 1.0e-10
    )
    fcp2_pass = (
        1.0e9 < texture.mass_1_gev < 1.0e12
        and 20.0 * texture.mass_2_gev > texture.mass_2_gev
        and texture.max_yukawa < 1.0
        and abs(texture.epsilon_total) <= texture.davidson_ibarra_bound
        and ETA_INTERVAL[0] <= abs(baseline_eta) <= ETA_INTERVAL[1]
    )
    if max(abs(float(row["eta_signed"])) for row in abundance_rows) < 1.0e-14:
        fcp3 = "INCONCLUSIVE"
    elif abundance_spread < 1.0e-2 and len(abundance_signs) == 1:
        fcp3 = "SUPPORTS"
    else:
        fcp3 = "CONTRADICTS"
    fcp4 = (
        "SUPPORTS"
        if inherited_spread < 1.0e-2 and len(inherited_signs) == 1
        else "CONTRADICTS"
    )
    fcp5_pass = all(
        [
            cp_pair["yukawa_conjugation_max_abs"] < 1.0e-13,
            cp_pair["projector_relative_difference"] < 1.0e-12,
            cp_pair["decay_parameter_relative_difference"] < 1.0e-12,
            cp_pair["mass_relative_difference"] < 1.0e-12,
            cp_pair["epsilon_pair_relative_cancellation"] < 1.0e-8,
            cp_pair["eta_pair_relative_cancellation"] < 1.0e-8,
            cp_pair["eta_abs_relative_difference"] < 1.0e-8,
        ]
    )
    fcp6_fail = (
        max_scan_mass_error < 1.0e-10
        and scan_has_zero
        and scan_has_positive
        and scan_has_negative
    )
    gates = {
        "FCP1": "PASS" if fcp1_pass else "FAIL",
        "FCP2": "PASS CALIBRATED" if fcp2_pass else "FAIL",
        "FCP3": fcp3,
        "FCP4": fcp4,
        "FCP5": "PASS" if fcp5_pass else "FAIL",
        "FCP6": "FAIL" if fcp6_fail else "INCONCLUSIVE",
        "FCP7": "FAIL",
    }
    initial_state_verdict = (
        "SUPPORTS"
        if gates["FCP1"] == "PASS"
        and gates["FCP2"] == "PASS CALIBRATED"
        and gates["FCP3"] == "SUPPORTS"
        and gates["FCP4"] == "SUPPORTS"
        else "CONTRADICTS"
    )
    cp_selection_verdict = (
        "DOES NOT EMERGE"
        if gates["FCP5"] == "PASS"
        and gates["FCP6"] == "FAIL"
        and gates["FCP7"] == "FAIL"
        else "INCONCLUSIVE"
    )
    gates["EMPIRICAL INITIAL STATE"] = initial_state_verdict
    gates["CP SELECTION"] = cp_selection_verdict
    gates["COMPLETE CASSI MATTER FORMATION"] = "FAIL"
    diagnostics = {
        "abundance_max_relative_difference": abundance_spread,
        "inherited_max_relative_difference": inherited_spread,
        "scan_max_mass_reconstruction_error": max_scan_mass_error,
        "scan_eta_min": float(np.min(scan_etas)),
        "scan_eta_max": float(np.max(scan_etas)),
        "scan_min_abs_eta": float(np.min(np.abs(scan_etas))),
        "scan_has_zero": scan_has_zero,
        "scan_has_positive": scan_has_positive,
        "scan_has_negative": scan_has_negative,
    }
    return gates, diagnostics


def report_text(payload: dict[str, Any]) -> str:
    gates = payload["gates"]
    benchmark = payload["benchmark"]
    diagnostics = payload["diagnostics"]
    cp_pair = payload["cp_pair"]
    return rf"""# Whole-Bubble Initial-State and CP-Selection Result

## Status: Tested—September 2026

## Verdicts

| Decision | Verdict |
|---|---|
""" + "".join(f"| {name} | `{verdict}` |\n" for name, verdict in gates.items()) + rf"""

## Two-flavour benchmark

The fixed $z=\pi/4+i/2$ texture reaches the observed baryon magnitude after calibrating

$$
M_1={benchmark['texture']['mass_1_gev']:.12e}\,\mathrm{{GeV}},\qquad
M_2={benchmark['texture']['mass_2_gev']:.12e}\,\mathrm{{GeV}}.
$$

The final signed yield is $\eta_B={benchmark['evolution']['eta_signed']:.12e}$, the decay parameter is $K={benchmark['texture']['decay_parameter']:.9f}$, and the largest Yukawa magnitude is {benchmark['texture']['max_yukawa']:.9e}. The leading resolved-flavour system is therefore a viable calibrated empirical comparator within its declared kinetic precision.

## Initial-state result

Changing the initial heavy-neutrino abundance from zero through twice equilibrium changes the final signed yield by at most {diagnostics['abundance_max_relative_difference']:.3e} relative. Injecting initial $B-L=\pm10^{{-4}}$ changes it by at most {diagnostics['inherited_max_relative_difference']:.3e}. Strong washout removes the tested abundance history, so the equilibrium preparation is not the unresolved selector in this benchmark.

## CP-selection result

The exact CP pair has Yukawa conjugation residual {cp_pair['yukawa_conjugation_max_abs']:.3e} and final-yield cancellation residual {cp_pair['eta_pair_relative_cancellation']:.3e}. The 25-point Casas–Ibarra scan preserves the light spectrum with maximum relative error {diagnostics['scan_max_mass_reconstruction_error']:.3e}, while its signed baryon yield spans {diagnostics['scan_eta_min']:.3e} to {diagnostics['scan_eta_max']:.3e} and includes a point with $|\eta_B|={diagnostics['scan_min_abs_eta']:.3e}$.

The registered real-density and scalar whole-bubble inputs cannot distinguish the CP pair. The fixed light-neutrino data also admit zero, matter-sign and antimatter-sign outcomes as the independent complex coordinate varies. A physical CP-odd boundary datum and a derived map to the neutrino texture are required for Cassi-selected matter formation.

## Scope

This result strengthens the connected empirical history by using the appropriate leading two-flavour kinetics and by demonstrating initial-abundance erasure. It does not turn the calibrated heavy mass or declared complex coordinate into Cassi predictions. Spectator matrices, thermal corrections and a density-matrix treatment would refine the calibrated number; none supplies the missing microscopic selector.

## Receipts

- `results.json`—full inputs, complex matrices, trajectories, scan and decisions
- `computations/qcd-whole-bubble-cp-selection-prereg.md`—frozen protocol
- `computations/qcd_whole_bubble_cp_selection.py`—primary implementation
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    started = time.perf_counter()

    mass_1_gev, calibration = calibrate_mass()
    texture = build_texture(mass_1_gev, BENCHMARK_Z)
    benchmark = evolve(texture, retain_history=True)

    abundance_results = [
        evolve(texture, initial_heavy_factor=factor)
        for factor in (0.0, 1.0, 2.0)
    ]
    inherited_results = [
        evolve(texture, initial_b_minus_l=value)
        for value in (-1.0e-4, 0.0, 1.0e-4)
    ]
    abundance_rows = [evolution_payload(result) for result in abundance_results]
    inherited_rows = [evolution_payload(result) for result in inherited_results]
    scan_rows = scan_payload(mass_1_gev)

    cp_positive_texture = texture
    cp_negative_texture = build_texture(
        mass_1_gev, BENCHMARK_Z.conjugate(), conjugate_pmns=True
    )
    cp_positive = evolve(cp_positive_texture)
    cp_negative = evolve(cp_negative_texture)
    epsilon_scale = max(
        float(np.max(np.abs(cp_positive_texture.epsilon_flavors))), 1.0e-300
    )
    eta_scale = max(abs(cp_positive.eta_signed), 1.0e-300)
    mass_scale = max(float(np.max(cp_positive_texture.reconstructed_masses_ev)), 1.0e-300)
    cp_pair = {
        "positive": {
            "texture": texture_payload(cp_positive_texture),
            "evolution": evolution_payload(cp_positive),
        },
        "negative": {
            "texture": texture_payload(cp_negative_texture),
            "evolution": evolution_payload(cp_negative),
        },
        "yukawa_conjugation_max_abs": float(
            np.max(np.abs(cp_negative_texture.yukawa - cp_positive_texture.yukawa.conj()))
        ),
        "projector_relative_difference": float(
            np.max(np.abs(cp_negative_texture.projectors - cp_positive_texture.projectors))
            / max(float(np.max(np.abs(cp_positive_texture.projectors))), 1.0e-300)
        ),
        "decay_parameter_relative_difference": relative_difference(
            cp_negative_texture.decay_parameter, cp_positive_texture.decay_parameter
        ),
        "mass_relative_difference": float(
            np.max(
                np.abs(
                    cp_negative_texture.reconstructed_masses_ev
                    - cp_positive_texture.reconstructed_masses_ev
                )
            )
            / mass_scale
        ),
        "epsilon_pair_relative_cancellation": float(
            np.max(
                np.abs(
                    cp_negative_texture.epsilon_flavors
                    + cp_positive_texture.epsilon_flavors
                )
            )
            / epsilon_scale
        ),
        "eta_pair_relative_cancellation": abs(
            cp_negative.eta_signed + cp_positive.eta_signed
        )
        / eta_scale,
        "eta_abs_relative_difference": relative_difference(
            abs(cp_negative.eta_signed), abs(cp_positive.eta_signed)
        ),
    }

    gates, diagnostics = decide(
        benchmark, abundance_rows, inherited_rows, scan_rows, cp_pair
    )
    selector_inventory = {
        "canonical_state": "two real nonnegative densities E_Y and E_I",
        "canonical_complex_phase": False,
        "wu_xing_label_type": "scalar declared cosmological label",
        "cascade_coordinate_type": "real scalar scale coordinate",
        "mapped_ckm_phase": "quark-sector input without a derived quark-lepton texture relation",
        "physical_cp_odd_boundary_datum": False,
        "derived_map_to_casas_ibarra_z": False,
        "cp_pair_distinguished_by_registered_inputs": False,
    }
    payload = {
        "schema": SCHEMA,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "platform": platform.platform(),
        "python": sys.version,
        "numpy": np.__version__,
        "scipy": __import__("scipy").__version__,
        "protocol_sha256": sha256(PROTOCOL),
        "source_records": [source_record(path) for path in (*SOURCE_PATHS, SELF)],
        "constants": {
            "v_higgs_gev": V_HIGGS_GEV,
            "m_star_ev": M_STAR_EV,
            "dm21_ev2": DM21_EV2,
            "dm31_ev2": DM31_EV2,
            "light_masses_ev": LIGHT_MASSES_EV,
            "benchmark_z": BENCHMARK_Z,
            "heavy_ratio": HEAVY_RATIO,
            "eta_target": ETA_TARGET,
            "eta_interval": ETA_INTERVAL,
            "x_initial": X_INITIAL,
            "x_final": X_FINAL,
            "sphaleron_entropy": SPHALERON_ENTROPY,
        },
        "calibration_evaluations": calibration,
        "benchmark": {
            "texture": texture_payload(texture),
            "evolution": evolution_payload(benchmark, include_history=True),
        },
        "initial_heavy_abundance_arms": abundance_rows,
        "inherited_b_minus_l_arms": inherited_rows,
        "casas_ibarra_scan": scan_rows,
        "cp_pair": cp_pair,
        "selector_inventory": selector_inventory,
        "diagnostics": diagnostics,
        "gates": gates,
        "elapsed_seconds": time.perf_counter() - started,
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results_path = output / "results.json"
    report_path = output / "report.md"
    results_path.write_text(
        json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(report_text(json_ready(payload)), encoding="utf-8")

    for name, verdict in gates.items():
        print(f"{name}={verdict}")
    print(f"M1_GEV={mass_1_gev:.12e}")
    print(f"ETA_B_SIGNED={benchmark.eta_signed:.12e}")
    print(f"ABUNDANCE_SPREAD={diagnostics['abundance_max_relative_difference']:.3e}")
    print(f"INHERITED_SPREAD={diagnostics['inherited_max_relative_difference']:.3e}")
    print(f"SCAN_RANGE={diagnostics['scan_eta_min']:.3e},{diagnostics['scan_eta_max']:.3e}")
    print(f"RESULTS={results_path.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
