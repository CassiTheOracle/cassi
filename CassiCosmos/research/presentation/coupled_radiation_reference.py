#!/usr/bin/env python3
"""Build the independent supplied-material fixture for CassiRadiationEngine.

The script uses float64 standard-library arithmetic only.  Godot never imports
it; the runtime consumes only the generated, hash-bound JSON data.
"""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "reference" / "coupled_radiation_reference.json"

C_LIGHT = 299_792_458.0
H_PLANCK = 6.626_070_15e-34
K_BOLTZMANN = 1.380_649e-23
A_RADIATION = 7.565_733_250_280_007e-16
M_PROTON = 1.672_621_925_95e-27
PI4_OVER_15 = math.pi**4 / 15.0

FREQUENCY_EDGES_HZ = (
    1.0e8,
    5.0e13,
    1.0e14,
    2.0e14,
    4.0e14,
    8.0e14,
    1.6e15,
    3.2e15,
    1.0e17,
)
ABSORPTION_M_INV = (3.0e-5, 5.0e-5, 8.0e-5, 1.2e-4, 1.8e-4, 2.4e-4, 1.5e-4, 6.0e-5)
TEMPERATURE_MIN_K = 2_500.0
TEMPERATURE_MAX_K = 20_000.0
NUMBER_DENSITY_M3 = 1.0e19
MASS_DENSITY_KG_M3 = NUMBER_DENSITY_M3 * M_PROTON
SPECIFIC_HEAT_J_KG_K = 3.0 * K_BOLTZMANN / M_PROTON
GAMMA = 5.0 / 3.0
CFL = 0.4


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def planck_kernel(x: float) -> float:
    if x <= 1.0e-8:
        return x * x
    if x >= 80.0:
        return 0.0
    return x**3 / math.expm1(x)


def simpson_integral(lo: float, hi: float, intervals: int = 4096) -> float:
    lo = max(0.0, lo)
    hi = min(80.0, hi)
    if hi <= lo:
        return 0.0
    n = intervals if intervals % 2 == 0 else intervals + 1
    h = (hi - lo) / n
    total = planck_kernel(lo) + planck_kernel(hi)
    for index in range(1, n):
        total += (4.0 if index % 2 else 2.0) * planck_kernel(lo + index * h)
    return total * h / 3.0


def lte_group_energy_density(temperature_k: float) -> list[float]:
    values: list[float] = []
    for low_hz, high_hz in zip(FREQUENCY_EDGES_HZ[:-1], FREQUENCY_EDGES_HZ[1:]):
        low_x = H_PLANCK * low_hz / (K_BOLTZMANN * temperature_k)
        high_x = H_PLANCK * high_hz / (K_BOLTZMANN * temperature_k)
        fraction = simpson_integral(low_x, high_x) / PI4_OVER_15
        values.append(A_RADIATION * temperature_k**4 * fraction)
    return values


def temperature_grid() -> list[float]:
    values = {
        TEMPERATURE_MIN_K * (TEMPERATURE_MAX_K / TEMPERATURE_MIN_K) ** (index / 32.0)
        for index in range(33)
    }
    values.update((3_000.0, 4_000.0, 5_000.0, 6_500.0, 8_000.0, 10_000.0, 12_500.0, 15_000.0))
    return sorted(values)


def interpolate_lte(model: dict[str, Any], temperature_k: float) -> list[float]:
    table = model["material"]["lte_table"]
    temperatures = table["temperature_K"]
    flat = table["energy_density_J_m3"]
    group_count = model["spectral_grid"]["group_count"]
    if not temperatures[0] <= temperature_k <= temperatures[-1]:
        raise ValueError(f"temperature {temperature_k} K is outside the LTE table")
    upper = 1
    while upper < len(temperatures) and temperatures[upper] < temperature_k:
        upper += 1
    if upper == len(temperatures):
        upper -= 1
    lower = max(0, upper - 1)
    if temperatures[upper] == temperatures[lower]:
        mix = 0.0
    else:
        mix = (temperature_k - temperatures[lower]) / (temperatures[upper] - temperatures[lower])
    return [
        flat[lower * group_count + group] * (1.0 - mix)
        + flat[upper * group_count + group] * mix
        for group in range(group_count)
    ]


def make_model() -> dict[str, Any]:
    temperatures = temperature_grid()
    lte_flat = [value for temperature in temperatures for value in lte_group_energy_density(temperature)]
    unit_map: dict[str, Any] = {
        "schema_version": "1.0.0",
        "length_m_per_sim": 1.0,
        "time_s_per_physics_sim": 1.0e-3,
        "mass_kg_per_sim": 1.0,
        "temperature_K_per_value": 1.0,
        "energy_J_per_sim": 1.0e6,
        "c_gamma_sim": C_LIGHT * 1.0e-3,
    }
    unit_map["unit_map_sha256"] = digest(unit_map)
    spectral_grid: dict[str, Any] = {
        "schema_version": "1.0.0",
        "frequency_frame": "material_rest_frame",
        "group_count": len(FREQUENCY_EDGES_HZ) - 1,
        "frequency_edges_Hz": list(FREQUENCY_EDGES_HZ),
        "intragroup_reconstruction": "piecewise_constant",
        "angular_closure": "isotropic",
        "outer_frequency_policy": "open_ledger",
    }
    spectral_grid["group_layout_sha256"] = digest(spectral_grid)
    model: dict[str, Any] = {
        "schema_version": "1.0.0",
        "model_id": "controlled_hydrogen_lte_homogeneous_v1",
        "revision": 1,
        "source_kind": "supplied_reference",
        "coupling": "coupled",
        "qualification_scope": [
            "supplied_material_mapping",
            "canonical_extensive_state",
            "ideal_monatomic_eos",
            "accepted_step_affine_thermal_work",
            "implicit_rest_frame_group_exchange",
            "moving_multigroup_isotropic_affine",
            "complete_physical_checkpoint",
        ],
        "unit_map": unit_map,
        "spectral_grid": spectral_grid,
        "material": {
            "canonical_element": "homogeneous_affine_cell",
            "geometry_source": "supplied_uniform",
            "eos": {
                "kind": "ideal_gas_constant_specific_heat",
                "gamma": GAMMA,
                "specific_heat_J_kg_K": SPECIFIC_HEAT_J_KG_K,
                "temperature_min_K": TEMPERATURE_MIN_K,
                "temperature_max_K": TEMPERATURE_MAX_K,
            },
            "transport": {
                "operator_order": "affine_frequency_then_implicit_source",
                "frequency_cfl": CFL,
                "max_frequency_substeps": 4096,
                "source_root_iterations": 40,
                "source_interpolation": "linear_temperature",
            },
            "coefficients": {
                "absorption_m_inv": list(ABSORPTION_M_INV),
                "scattering_m_inv": [0.0] * (len(FREQUENCY_EDGES_HZ) - 1),
                "coefficient_frame": "material_rest_frame",
                "coefficient_hold": "accepted_source_step",
            },
            "lte_table": {
                "temperature_K": temperatures,
                "energy_density_J_m3": lte_flat,
                "layout": "temperature_major_group_minor",
            },
            "initial_state": {
                "mass_density_kg_m3": MASS_DENSITY_KG_M3,
                "volume_m3": 1.0,
                "temperature_K": 6_500.0,
                "expansion_rate_s_inv": 0.0,
                "radiation_energy_density_J_m3": lte_group_energy_density(4_000.0),
            },
        },
    }
    model["model_sha256"] = digest(model)
    return model


def make_state(model: dict[str, Any], *, temperature_k: float, radiation_temperature_k: float | None,
               expansion_rate_s_inv: float = 0.0, planted_group: int | None = None) -> dict[str, Any]:
    material = model["material"]
    volume = float(material["initial_state"]["volume_m3"])
    mass = MASS_DENSITY_KG_M3 * volume
    internal = mass * SPECIFIC_HEAT_J_KG_K * temperature_k
    if planted_group is None:
        radiation_density = (
            [0.0] * model["spectral_grid"]["group_count"]
            if radiation_temperature_k is None
            else lte_group_energy_density(radiation_temperature_k)
        )
    else:
        radiation_density = [0.0] * model["spectral_grid"]["group_count"]
        radiation_density[planted_group] = 1.0
    return {
        "mass_kg": mass,
        "internal_energy_J": internal,
        "volume_m3": volume,
        "expansion_rate_s_inv": expansion_rate_s_inv,
        "radiation_energy_J": [value * volume for value in radiation_density],
        "low_frequency_escape_J": 0.0,
        "high_frequency_escape_J": 0.0,
        "radiation_pressure_work_J": 0.0,
        "material_radiation_transfer_J": 0.0,
    }


def frequency_substeps(model: dict[str, Any], expansion_rate_s_inv: float, dt_s: float) -> int:
    if expansion_rate_s_inv == 0.0 or dt_s == 0.0:
        return 1
    edges = model["spectral_grid"]["frequency_edges_Hz"]
    rate = 0.0
    for group in range(len(edges) - 1):
        width = edges[group + 1] - edges[group]
        rate = max(rate, abs(expansion_rate_s_inv) * edges[group + 1] / width)
    return max(1, math.ceil(dt_s * rate / model["material"]["transport"]["frequency_cfl"]))


def affine_frequency_step(state: dict[str, Any], model: dict[str, Any], dt_s: float,
                          *, affine_enabled: bool, frequency_enabled: bool) -> None:
    expansion = state["expansion_rate_s_inv"]
    if not affine_enabled or expansion == 0.0:
        return
    count = frequency_substeps(model, expansion, dt_s) if frequency_enabled else 1
    if count > model["material"]["transport"]["max_frequency_substeps"]:
        raise ValueError("frequency substep cap exceeded")
    sub_dt = dt_s / count
    edges = model["spectral_grid"]["frequency_edges_Hz"]
    gamma = model["material"]["eos"]["gamma"]
    for _ in range(count):
        old_volume = state["volume_m3"]
        if frequency_enabled:
            old = state["radiation_energy_J"]
            flux = [0.0] * (len(old) + 1)
            for edge in range(len(flux)):
                if edge == 0:
                    source_group = 0 if expansion > 0.0 else None
                elif edge == len(old):
                    source_group = len(old) - 1 if expansion < 0.0 else None
                else:
                    source_group = edge if expansion > 0.0 else edge - 1
                if source_group is not None:
                    width = edges[source_group + 1] - edges[source_group]
                    spectral_density = old[source_group] / (old_volume * width)
                    flux[edge] = -expansion * edges[edge] * spectral_density
            updated = [
                old[group]
                - sub_dt * expansion * old[group]
                - sub_dt * old_volume * (flux[group + 1] - flux[group])
                for group in range(len(old))
            ]
            if min(updated) < -1.0e-14:
                raise ValueError("reference frequency update became negative")
            state["radiation_pressure_work_J"] += -sub_dt * expansion * sum(old)
            state["low_frequency_escape_J"] += max(0.0, -sub_dt * old_volume * flux[0])
            state["high_frequency_escape_J"] += max(0.0, sub_dt * old_volume * flux[-1])
            state["radiation_energy_J"] = [max(0.0, value) for value in updated]
        state["internal_energy_J"] *= math.exp(-3.0 * expansion * (gamma - 1.0) * sub_dt)
        state["volume_m3"] *= math.exp(3.0 * expansion * sub_dt)


def implicit_source_step(state: dict[str, Any], model: dict[str, Any], dt_s: float) -> None:
    if dt_s == 0.0:
        return
    material = model["material"]
    eos = material["eos"]
    opacity = material["coefficients"]["absorption_m_inv"]
    lambdas = [C_LIGHT * value * dt_s for value in opacity]
    if max(lambdas, default=0.0) == 0.0:
        return
    old_groups = state["radiation_energy_J"]
    old_material = state["internal_energy_J"]
    total = old_material + sum(old_groups)
    heat_capacity = state["mass_kg"] * eos["specific_heat_J_kg_K"]
    volume = state["volume_m3"]

    def groups_at(temperature_k: float) -> list[float]:
        equilibrium = interpolate_lte(model, temperature_k)
        return [
            (old_groups[group] + lambdas[group] * volume * equilibrium[group])
            / (1.0 + lambdas[group])
            for group in range(len(old_groups))
        ]

    def residual(temperature_k: float) -> float:
        return heat_capacity * temperature_k + sum(groups_at(temperature_k)) - total

    low = eos["temperature_min_K"]
    high = eos["temperature_max_K"]
    if residual(low) > 0.0 or residual(high) < 0.0:
        raise ValueError("source root lies outside the supplied temperature table")
    for _ in range(80):
        middle = 0.5 * (low + high)
        if residual(middle) > 0.0:
            high = middle
        else:
            low = middle
    groups = groups_at(0.5 * (low + high))
    material_energy = total - sum(groups)
    state["radiation_energy_J"] = groups
    state["internal_energy_J"] = material_energy
    state["material_radiation_transfer_J"] += material_energy - old_material


def run_control(model: dict[str, Any], control: dict[str, Any]) -> dict[str, Any]:
    state = deepcopy(control["initial_state"])
    initial_radiation = sum(state["radiation_energy_J"])
    for _ in range(control["steps"]):
        affine_frequency_step(
            state,
            model,
            control["dt_s"],
            affine_enabled=control["affine_enabled"],
            frequency_enabled=control["frequency_enabled"],
        )
        if control["source_enabled"]:
            implicit_source_step(state, model, control["dt_s"])
    state["temperature_K"] = state["internal_energy_J"] / (
        state["mass_kg"] * model["material"]["eos"]["specific_heat_J_kg_K"]
    )
    state["radiation_energy_sum_J"] = sum(state["radiation_energy_J"])
    state["material_plus_radiation_J"] = state["internal_energy_J"] + state["radiation_energy_sum_J"]
    state["frequency_balance_residual_J"] = (
        state["radiation_energy_sum_J"]
        - initial_radiation
        + state["low_frequency_escape_J"]
        + state["high_frequency_escape_J"]
        - state["radiation_pressure_work_J"]
    )
    return state


def make_controls(model: dict[str, Any]) -> dict[str, Any]:
    controls: dict[str, dict[str, Any]] = {
        "null": {
            "dt_s": 1.0e-5,
            "steps": 8,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": False,
            "initial_state": make_state(model, temperature_k=6_500.0, radiation_temperature_k=4_000.0),
        },
        "affine_expansion": {
            "dt_s": 2.0e-3,
            "steps": 12,
            "affine_enabled": True,
            "frequency_enabled": False,
            "source_enabled": False,
            "initial_state": make_state(
                model, temperature_k=6_500.0, radiation_temperature_k=None, expansion_rate_s_inv=5.0
            ),
        },
        "affine_compression": {
            "dt_s": 2.0e-3,
            "steps": 12,
            "affine_enabled": True,
            "frequency_enabled": False,
            "source_enabled": False,
            "initial_state": make_state(
                model, temperature_k=6_500.0, radiation_temperature_k=None, expansion_rate_s_inv=-5.0
            ),
        },
        "frequency_expansion": {
            "dt_s": 2.0e-3,
            "steps": 8,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": False,
            "initial_state": make_state(
                model, temperature_k=6_500.0, radiation_temperature_k=None,
                expansion_rate_s_inv=20.0, planted_group=6
            ),
        },
        "frequency_compression": {
            "dt_s": 2.0e-3,
            "steps": 8,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": False,
            "initial_state": make_state(
                model, temperature_k=6_500.0, radiation_temperature_k=None,
                expansion_rate_s_inv=-20.0, planted_group=1
            ),
        },
        "hot_matter": {
            "dt_s": 1.0e-5,
            "steps": 6,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": True,
            "initial_state": make_state(model, temperature_k=10_000.0, radiation_temperature_k=4_000.0),
        },
        "cold_matter": {
            "dt_s": 1.0e-5,
            "steps": 6,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": True,
            "initial_state": make_state(model, temperature_k=4_000.0, radiation_temperature_k=10_000.0),
        },
        "exact_lte": {
            "dt_s": 1.0e-5,
            "steps": 6,
            "affine_enabled": True,
            "frequency_enabled": True,
            "source_enabled": True,
            "initial_state": make_state(model, temperature_k=6_500.0, radiation_temperature_k=6_500.0),
        },
    }
    for control in controls.values():
        control["expected"] = run_control(model, control)
    return controls


def main() -> None:
    model = make_model()
    fixture: dict[str, Any] = {
        "schema_version": "1.0.0",
        "producer": Path(__file__).name,
        "reference_arithmetic": "python_float64",
        "model": model,
        "controls": make_controls(model),
    }
    fixture["fixture_payload_sha256"] = digest(fixture)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(fixture, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"WROTE {OUTPUT}")
    print(f"MODEL_SHA256 {model['model_sha256']}")
    print(f"UNIT_MAP_SHA256 {model['unit_map']['unit_map_sha256']}")
    print(f"GROUP_LAYOUT_SHA256 {model['spectral_grid']['group_layout_sha256']}")
    print(f"FIXTURE_PAYLOAD_SHA256 {fixture['fixture_payload_sha256']}")


if __name__ == "__main__":
    main()
