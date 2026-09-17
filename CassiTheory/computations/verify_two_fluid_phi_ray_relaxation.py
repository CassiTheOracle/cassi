#!/usr/bin/env python3
"""Measure the phi ray and the conversion rate in the canonical two-fluid solver.

The preregistered schedule is
`computations/two-fluid-phi-ray-relaxation-prereg.md`. This probe loads the
canonical solver `two-fluid/cassi_two_fluid_3d_gpu.py` from disk, accepts it
only at the SHA-256 recorded below, and evolves the sixteen declared states of
the schedule: five compositions in the ungated base mode, the same five in the
q-gated static-box mode, a frozen-conversion control in each mode, a step
refinement, a resolution check, one long gated horizon and one sensitivity
control with an unprojected velocity.

The statistics are the volume ratio R = <E_Y>/<E_I>, the fitted mean-imbalance
decay rate against (1+phi)*lambda, the total-density conservation residual, the
per-step closure residual of the predicted mean law, and the gate sub-question
readings (the openness-weighted ratio and the quartile local ratios). The
probe scripts nothing: the solver supplies rhs, rk2_step, _project and
compute_q_field.

Run from the repository root:

    timeout 10800 python computations/verify_two_fluid_phi_ray_relaxation.py
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


ROOT = Path(__file__).resolve().parents[1]
SOLVER = ROOT / "two-fluid" / "cassi_two_fluid_3d_gpu.py"
PROTOCOL = ROOT / "computations" / "two-fluid-phi-ray-relaxation-prereg.md"
FOUNDATION_ONE = ROOT / "foundations" / "cassi-first-principles.md"
FOUNDATION_TWO = ROOT / "foundations" / "physical-becoming-hierarchy.md"
SCRIPT = Path(__file__).resolve()
DEFAULT_OUTPUT = ROOT / "runs" / "two_fluid_phi_ray_relaxation" / "verification.json"
SCHEMA = "cassi.two-fluid.phi-ray-relaxation.verification.v1"
PROTOCOL_REVISION = "P1"
PROBE_REVISION = "P1a"

SOLVER_SHA256 = "368e5539e3e1ae9205c543ed413350c8c3aa83c395809012fa44891d0aa6468c"

L = 2.0 * math.pi
PHI = (1.0 + math.sqrt(5.0)) / 2.0
LAM = 0.1
NU = 0.001
DIFFUSIVITY = 0.0
MOBILITY = 0.0
AMPLITUDE = 0.1
VELOCITY_AMPLITUDE = 0.05
BAND = 4
SEED_EY = 20260916
SEED_EI = 20260917
SEED_U = 20260918
DT = 0.002
T_END = 30.0
T_LONG = 240.0
STEPS = 15000
STEPS_LONG = 120000
STEPS_REFINED = 30000
SAMPLE_FIT = 25
SAMPLE_RECORD = 125
CHECKPOINT_FRACTIONS = (0.0, 0.125, 0.25, 0.5, 0.75, 1.0)

PREDICTED_RATE = (1.0 + PHI) * LAM
RAY_OPENNESS = PHI ** -2 / ((1.0 + 1.0 / PHI) ** 2 + PHI ** -2)
RAY_SIDE_RATE = PREDICTED_RATE * RAY_OPENNESS

RATIO_TOL = 1.0e-3
RATE_TOL = 1.0e-4
SUM_TOL = 1.0e-11
CLOSURE_TOL = 1.0e-6
REFINE_TOL = 1.0e-5
SOLENOIDAL_TOL = 1.0e-12
CONSTRUCTION_STATE_TOL = 1.0e-12
STEP_FLOOR = 1.0e-3
GATE_SPREAD_TOL = 1.0e-6
RATE_FLOOR = 0.1 * PREDICTED_RATE
CONTROL_RATIO_TOL = 1.0e-3
WEIGHT_IDENTITY_TOL = 1.0e-14
RAY_EPS_FLOOR = 1.0e-12

MODE_UNGATED = "ungated_base"
MODE_GATED = "gated_static_box"

STATE_RATIOS = {
    "ray": PHI,
    "mild_inv": 1.0,
    "inv": 1.0 / PHI,
    "deep_inv": PHI ** -2,
    "yang": PHI ** 2,
}

DECLARED_RUNS: tuple[dict[str, Any], ...] = (
    {"run": "A1", "mode": MODE_UNGATED, "state": "ray", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "A2", "mode": MODE_UNGATED, "state": "mild_inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "A3", "mode": MODE_UNGATED, "state": "inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "A4", "mode": MODE_UNGATED, "state": "deep_inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "A5", "mode": MODE_UNGATED, "state": "yang", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "B1", "mode": MODE_GATED, "state": "ray", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "B2", "mode": MODE_GATED, "state": "mild_inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "B3", "mode": MODE_GATED, "state": "inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "B4", "mode": MODE_GATED, "state": "deep_inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "B5", "mode": MODE_GATED, "state": "yang", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "C1", "mode": MODE_UNGATED, "state": "yang", "lam": 0.0, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "C2", "mode": MODE_GATED, "state": "inv", "lam": 0.0, "N": 32, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "R1", "mode": MODE_UNGATED, "state": "inv", "lam": LAM, "N": 32, "dt": 0.001, "steps": STEPS_REFINED, "projected": True},
    {"run": "R2", "mode": MODE_GATED, "state": "inv", "lam": LAM, "N": 64, "dt": DT, "steps": STEPS, "projected": True},
    {"run": "L1", "mode": MODE_GATED, "state": "inv", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS_LONG, "projected": True},
    {"run": "M1", "mode": MODE_UNGATED, "state": "yang", "lam": LAM, "N": 32, "dt": DT, "steps": STEPS, "projected": False},
)
DECLARED_RUN_COUNT = len(DECLARED_RUNS)
DECISIVE_RUNS = tuple(spec["run"] for spec in DECLARED_RUNS if spec["run"] != "M1")
FROZEN_CONTROL_RUNS = ("C1", "C2")
T30_GATED_RUNS = ("B1", "B2", "B3", "B4", "B5", "C2")
T30_GATED_DECISIVE = ("B1", "B2", "B3", "B4", "B5")


def load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else ("nan" if math.isnan(value) else "inf")
    return value


def finite_scan(value: Any) -> int:
    if isinstance(value, dict):
        return sum(finite_scan(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return sum(finite_scan(item) for item in value)
    if isinstance(value, float) and not math.isfinite(value):
        return 1
    return 0


def band_limited_field(tf: Any, solver: Any, seed: int) -> Any:
    """Zero-mean, unit-variance real field on the declared integer-mode band."""
    generator = torch.Generator(device=solver.device)
    generator.manual_seed(seed)
    white = torch.randn((solver.N,) * 3, generator=generator, device=solver.device, dtype=torch.float64)
    indices = torch.fft.fftfreq(solver.N, d=1.0 / solver.N, device=solver.device)
    keep = (
        (indices.abs() <= BAND).unsqueeze(1).unsqueeze(2)
        & (indices.abs() <= BAND).unsqueeze(0).unsqueeze(2)
        & (indices.abs() <= BAND).unsqueeze(0).unsqueeze(1)
    ).to(torch.float64)
    field = torch.fft.ifftn(torch.fft.fftn(white) * keep).real
    field = field - field.mean()
    return field / field.std()


def declared_means(ratio: float) -> tuple[float, float]:
    ey_mean = (1.0 + 1.0 / PHI) * ratio / (1.0 + ratio)
    return ey_mean, ey_mean / ratio


def build_state(tf: Any, solver: Any, spec: dict[str, Any]) -> dict[str, Any]:
    ratio = STATE_RATIOS[spec["state"]]
    ey_mean, ei_mean = declared_means(ratio)
    field_y = band_limited_field(tf, solver, SEED_EY)
    field_i = band_limited_field(tf, solver, SEED_EI)
    ey = ey_mean + AMPLITUDE * field_y
    ei = ei_mean + AMPLITUDE * field_i
    ey = ey * (ey_mean / ey.mean())
    ei = ei * (ei_mean / ei.mean())
    u_hat = []
    for component in range(3):
        component_field = VELOCITY_AMPLITUDE * band_limited_field(tf, solver, SEED_U + component)
        u_hat.append(torch.fft.fftn(component_field))
    if spec["projected"]:
        u_hat = solver._project(u_hat)
    return {
        "u_hat": u_hat,
        "ey_hat": torch.fft.fftn(ey),
        "ei_hat": torch.fft.fftn(ei),
        "ratio": ratio,
        "ey_mean": ey_mean,
        "ei_mean": ei_mean,
        "field_min_ey": float(ey.min()),
        "field_min_ei": float(ei.min()),
    }


def divergence_residual(solver: Any, u_hat: list[Any]) -> Any:
    divergence = solver.kx * u_hat[0] + solver.ky * u_hat[1] + solver.kz * u_hat[2]
    magnitude = torch.sqrt(solver.k2)
    scale = max(float((magnitude * u_hat[d].abs()).max()) for d in range(3))
    return divergence.abs().max() / (scale + 1e-300)


def fit_rate(times: list[float], values: list[float]) -> dict[str, Any]:
    count = len(times)
    mean_t = sum(times) / count
    mean_v = sum(values) / count
    numerator = sum((t - mean_t) * (v - mean_v) for t, v in zip(times, values))
    denominator = sum((t - mean_t) ** 2 for t in times)
    slope = numerator / denominator
    intercept = mean_v - slope * mean_t
    residual = max(abs(v - (intercept + slope * t)) for t, v in zip(times, values))
    return {"slope": slope, "intercept": intercept, "samples": count, "max_residual": residual}


def quartile_ratios(ey: Any, ei: Any, weight: Any) -> list[float]:
    flat_weight = weight.reshape(-1)
    order = torch.argsort(flat_weight)
    count = flat_weight.numel() // 4
    flat_ey = ey.reshape(-1)
    flat_ei = ei.reshape(-1)
    ratios = []
    for index in range(4):
        selection = order[index * count:(index + 1) * count] if index < 3 else order[3 * count:]
        ratios.append(float(flat_ey[selection].mean() / flat_ei[selection].mean()))
    return ratios


def diagnostic_openness(tf: Any, ey: Any, ei: Any) -> Any:
    floor = PHI ** -2
    total = (ey + ei) ** 2
    imbalance = (ey - PHI * ei) ** 2
    return (floor + imbalance) / (total + floor + imbalance + 1e-30)


def run_one(tf: Any, spec: dict[str, Any], device: Any) -> dict[str, Any]:
    started = time.time()
    gated = spec["mode"] == MODE_GATED
    if gated:
        solver = tf.ExpandingTwoFluid3DGPU(
            N=spec["N"], L=L, nu=NU, D=DIFFUSIVITY, lam=spec["lam"], chi=MOBILITY,
            H0=0.0, a0=1.0, hubble_mode="friedmann", hyper_nu=0.0, cs2=0.0,
            qi_gate=True, phi_inv2=PHI ** -2, qi_memory=False, wu_xing=False,
            mode="cosmos", device=device,
        )
        solver.gate_model = "single"
    else:
        solver = tf.TwoFluid3DGPU(
            N=spec["N"], L=L, nu=NU, D=DIFFUSIVITY, lam=spec["lam"], chi=MOBILITY,
            mode="cosmos", device=device,
        )
    actual = {
        "N": int(solver.N),
        "nu": float(solver.nu),
        "D": float(solver.D),
        "lam": float(solver.lam),
        "chi": float(solver.chi),
        "qi_gate": bool(getattr(solver, "qi_gate", False)),
        "hubble_mode": getattr(solver, "hubble_mode", None),
        "H0": float(getattr(solver, "H0", 0.0)),
        "a0_initial": float(getattr(solver, "a", torch.tensor(1.0, device=device))),
        "gate_model": getattr(solver, "gate_model", None),
        "phi_inv2": float(getattr(solver, "phi_inv2", 0.0)),
        "cs2": float(getattr(solver, "cs2", 0.0)),
        "hyper_nu": float(getattr(solver, "hyper_nu", 0.0)),
        "qi_memory": bool(getattr(solver, "qi_memory", False)),
        "wu_xing": bool(getattr(solver, "wu_xing", False)),
    }
    expected = {
        "N": spec["N"],
        "nu": NU,
        "D": DIFFUSIVITY,
        "lam": spec["lam"],
        "chi": MOBILITY,
        "qi_gate": gated,
        "hubble_mode": "friedmann" if gated else None,
        "H0": 0.0,
        "a0_initial": 1.0,
        "gate_model": "single" if gated else None,
        "phi_inv2": PHI ** -2 if gated else 0.0,
        "cs2": 0.0,
        "hyper_nu": 0.0,
        "qi_memory": False,
        "wu_xing": False,
    }
    mismatches = {
        key: {"actual": actual[key], "declared": expected[key]}
        for key in expected
        if not isinstance(actual[key], type(expected[key])) or actual[key] != expected[key]
    }

    state = build_state(tf, solver, spec)
    u_hat = state["u_hat"]
    ey_hat = state["ey_hat"]
    ei_hat = state["ei_hat"]
    dt = spec["dt"]
    steps = spec["steps"]
    lam = spec["lam"]
    rate = (1.0 + PHI) * lam

    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    rho = ey + ei
    eps = ey - PHI * ei
    rho_zero = float(rho.mean())
    eps_zero = float(eps.mean())
    initial_u = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
    initial = {
        "ey_mean": float(ey.mean()),
        "ei_mean": float(ei.mean()),
        "rho_mean": rho_zero,
        "eps_zero": eps_zero,
        "ratio_zero": float(ey.mean() / ei.mean()),
        "ratio_declared": state["ratio"],
        "field_min_ey": state["field_min_ey"],
        "field_min_ei": state["field_min_ei"],
        "solenoidal_residual": float(divergence_residual(solver, u_hat)),
        "u_rms": float(math.sqrt(sum(float((initial_u[d] ** 2).mean()) for d in range(3)))),
    }

    if gated and lam != 0.0:
        _, weight = solver.compute_q_field(ey, ei)
    else:
        weight = None
    previous_eps = torch.tensor(eps_zero, device=device, dtype=torch.float64)
    previous_weighted = (weight * eps).mean() if weight is not None else previous_eps
    initial_ey_mean = float(ey.mean())
    initial_ei_mean = float(ei.mean())
    ray_control = abs(eps_zero) <= RAY_EPS_FLOOR * rho_zero

    closure_max = torch.zeros((), device=device, dtype=torch.float64)
    sum_residual_max = torch.zeros((), device=device, dtype=torch.float64)
    channel_identity_max = torch.zeros((), device=device, dtype=torch.float64)
    divergence_max = torch.tensor(initial["solenoidal_residual"], device=device, dtype=torch.float64)
    field_min = torch.tensor(min(initial["field_min_ey"], initial["field_min_ei"]), device=device, dtype=torch.float64)
    integral_eps = torch.zeros((), device=device, dtype=torch.float64)
    band_fraction_min = torch.ones((), device=device, dtype=torch.float64)

    if abs(eps_zero) > 0.0:
        fit_times: list[float] = [0.0]
        fit_log_mean: list[float] = [math.log(abs(eps_zero))]
        fit_log_rms: list[float] = [0.5 * math.log(float((eps ** 2).mean()))]
    else:
        fit_times, fit_log_mean, fit_log_rms = [], [], []
    sign_stable = True
    checkpoint_steps = {int(round(fraction * steps)): fraction for fraction in CHECKPOINT_FRACTIONS}
    series: list[dict[str, Any]] = []
    checkpoints: list[dict[str, Any]] = []
    sample_sign = 0.0 if eps_zero == 0.0 else math.copysign(1.0, eps_zero)

    def reading(step: int) -> dict[str, Any]:
        ey_physical = torch.fft.ifftn(ey_hat).real
        ei_physical = torch.fft.ifftn(ei_hat).real
        eps_physical = ey_physical - PHI * ei_physical
        rho_physical = ey_physical + ei_physical
        if gated:
            _, weight_now = solver.compute_q_field(ey_physical, ei_physical)
        else:
            weight_now = None
        eps_hat = ey_hat - PHI * ei_hat
        total_imbalance = float((eps_hat.abs() ** 2).sum())
        retained = float(((eps_hat.abs() * solver.dealias) ** 2).sum())
        u_physical = [torch.fft.ifftn(u_hat[d]).real for d in range(3)]
        entry: dict[str, Any] = {
            "step": step,
            "t": step * dt,
            "ratio": float(ey_physical.mean() / ei_physical.mean()),
            "eps_mean": float(eps_physical.mean()),
            "rho_mean": float(rho_physical.mean()),
            "rms_imbalance": float(torch.sqrt((eps_physical ** 2).mean()) / rho_zero),
            "retained_band_fraction": retained / (total_imbalance + 1e-300),
            "u_max": max(float(u_physical[d].abs().max()) for d in range(3)),
            "field_min": float(min(ey_physical.min(), ei_physical.min())),
        }
        if weight_now is not None:
            entry["openness_mean"] = float(weight_now.mean())
            entry["openness_min"] = float(weight_now.min())
            entry["openness_max"] = float(weight_now.max())
            entry["weighted_ratio"] = float((weight_now * ey_physical).mean() / (weight_now * ei_physical).mean())
            entry["weighted_imbalance"] = float((weight_now * eps_physical).mean())
            entry["xi"] = float((weight_now * eps_physical).mean() / (eps_physical.mean() + 1e-300))
            entry["quartiles"] = quartile_ratios(ey_physical, ei_physical, weight_now)
        else:
            entry["openness_mean"] = 1.0
            entry["openness_min"] = 1.0
            entry["openness_max"] = 1.0
            entry["weighted_ratio"] = entry["ratio"]
            entry["weighted_imbalance"] = entry["eps_mean"]
            entry["xi"] = 1.0
            entry["quartiles"] = None
        diagnostic = diagnostic_openness(tf, ey_physical, ei_physical)
        entry["diagnostic_openness_mean"] = float(diagnostic.mean())
        entry["diagnostic_openness_min"] = float(diagnostic.min())
        entry["diagnostic_openness_max"] = float(diagnostic.max())
        entry["diagnostic_quartiles"] = quartile_ratios(ey_physical, ei_physical, diagnostic)
        return entry

    first = reading(0)
    checkpoints.append(first)
    series.append({key: first[key] for key in ("t", "ratio", "eps_mean", "openness_mean", "weighted_ratio")})

    with torch.no_grad():
        for step in range(1, steps + 1):
            u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, dt)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            eps = ey - PHI * ei
            eps_mean = eps.mean()
            if gated and lam != 0.0:
                _, weight = solver.compute_q_field(ey, ei)
                weighted = (weight * eps).mean()
            else:
                weighted = eps_mean
            delta_eps = eps_mean - previous_eps
            trapezoidal = 0.5 * (previous_weighted + weighted)
            closure = abs(delta_eps + rate * trapezoidal * dt) / (
                rho_zero * 1e-3 + abs(delta_eps) + rate * abs(trapezoidal) * dt
            )
            closure_max = torch.maximum(closure_max, closure)
            integral_eps = integral_eps + 0.5 * (previous_eps + eps_mean) * dt
            sum_residual_max = torch.maximum(
                sum_residual_max, abs(ey.mean() + ei.mean() - rho_zero) / rho_zero
            )
            channel_identity_max = torch.maximum(
                channel_identity_max,
                abs(ey.mean() - initial_ey_mean + lam * integral_eps) / rho_zero,
            )
            divergence_max = torch.maximum(divergence_max, divergence_residual(solver, u_hat))
            field_min = torch.minimum(field_min, torch.minimum(ey.min(), ei.min()))
            eps_hat_now = ey_hat - PHI * ei_hat
            total_now = (eps_hat_now.abs() ** 2).sum()
            retained_now = ((eps_hat_now.abs() * solver.dealias) ** 2).sum()
            band_fraction_min = torch.minimum(band_fraction_min, retained_now / (total_now + 1e-300))
            if eps_zero != 0.0 and float(eps_mean) * sample_sign <= 0.0:
                sign_stable = False
            previous_eps = eps_mean
            previous_weighted = weighted
            if step % SAMPLE_FIT == 0 or step == steps:
                magnitude = abs(float(eps_mean))
                if magnitude > 0.0:
                    fit_times.append(step * dt)
                    fit_log_mean.append(math.log(magnitude))
                    fit_log_rms.append(0.5 * math.log(float((eps ** 2).mean())))
            if step in checkpoint_steps or step == steps:
                checkpoints.append(reading(step))
            if step % SAMPLE_RECORD == 0 or step == steps:
                ey_physical = torch.fft.ifftn(ey_hat).real
                ei_physical = torch.fft.ifftn(ei_hat).real
                eps_physical = ey_physical - PHI * ei_physical
                if gated and lam != 0.0:
                    _, weight_now = solver.compute_q_field(ey_physical, ei_physical)
                    weighted_ratio = float(
                        (weight_now * ey_physical).mean() / (weight_now * ei_physical).mean()
                    )
                    openness_mean = float(weight_now.mean())
                else:
                    weighted_ratio = float(ey_physical.mean() / ei_physical.mean())
                    openness_mean = 1.0
                series.append({
                    "t": step * dt,
                    "ratio": float(ey_physical.mean() / ei_physical.mean()),
                    "eps_mean": float(eps_physical.mean()),
                    "openness_mean": openness_mean,
                    "weighted_ratio": weighted_ratio,
                })

    final = checkpoints[-1]
    ratio_t = float(final["ratio"])
    ratio_zero = float(initial["ratio_zero"])
    samples = len(fit_times)
    fit = (
        fit_rate(fit_times, fit_log_mean)
        if samples >= 2 and sign_stable and not ray_control
        else None
    )
    fit_rms = fit_rate(fit_times, fit_log_rms) if samples >= 2 else None
    r_fit = -fit["slope"] if fit else None
    r_fit_rms = -fit_rms["slope"] if fit_rms else None
    if ray_control:
        fit_suppressed = "ray_control"
    elif not sign_stable:
        fit_suppressed = "sign_unstable"
    elif samples < 2:
        fit_suppressed = "too_few_samples"
    else:
        fit_suppressed = None
    statistics = {
        "r_fit": r_fit,
        "r_fit_log_slope": fit["slope"] if fit else None,
        "r_fit_max_residual": fit["max_residual"] if fit else None,
        "r_fit_samples": samples,
        "r_fit_suppressed": fit_suppressed,
        "r_fit_rms": r_fit_rms,
        "r_fit_rms_samples": fit_rms["samples"] if fit_rms else 0,
        "sign_stable": sign_stable,
        "ratio_zero": ratio_zero,
        "ratio_t": ratio_t,
        "ratio_zero_deviation": ratio_zero / PHI - 1.0,
        "ratio_t_deviation": ratio_t / PHI - 1.0,
        "sum_residual": float(sum_residual_max),
        "closure_max": float(closure_max),
        "integral_eps": float(integral_eps),
        "channel_identity_max": float(channel_identity_max),
        "channel_delta_ey": float(ey.mean() - initial_ey_mean),
        "channel_delta_ei": float(ei.mean() - initial_ei_mean),
        "divergence_max": float(divergence_max),
        "field_min": float(field_min),
        "retained_band_fraction_min": float(band_fraction_min),
        "predicted_rate": rate,
        "rate_ratio": (r_fit / rate) if (r_fit is not None and rate > 0.0) else None,
    }

    is_ray_control = ray_control
    if is_ray_control:
        rate_class = "rate_not_defined"
    elif lam == 0.0:
        rate_class = "rate_not_applicable"
    elif fit is None or not sign_stable:
        rate_class = "rate_unfittable"
    else:
        comparison = r_fit / PREDICTED_RATE
        if abs(comparison - 1.0) <= RATE_TOL:
            rate_class = "rate_matches"
        elif comparison > 1.0:
            rate_class = "rate_above"
        elif gated and r_fit >= RATE_FLOOR:
            rate_class = "rate_below_gated"
        else:
            rate_class = "rate_below_unexplained"

    deviation = ratio_t / PHI - 1.0
    movement = abs(ratio_t - PHI) - abs(ratio_zero - PHI)
    if lam == 0.0:
        ratio_class = "ratio_not_applicable"
    elif abs(deviation) <= RATIO_TOL:
        ratio_class = "ray"
    elif movement >= 0.0:
        ratio_class = "departing"
    elif abs(ratio_t - ratio_zero) <= 0.1 * abs(ratio_zero - PHI):
        ratio_class = "other_ratio"
    else:
        ratio_class = "approaching"

    closure_class = "closure_holds" if statistics["closure_max"] <= CLOSURE_TOL else "closure_fails"
    conservation_class = (
        "exact" if statistics["sum_residual"] <= SUM_TOL else "floor_limited_or_violated"
    )
    frozen_class = (
        "frozen" if abs(ratio_t / ratio_zero - 1.0) <= CONTROL_RATIO_TOL else "composition_moved"
    )
    weight_identity = (
        abs(final["weighted_ratio"] - final["ratio"]) / max(abs(final["ratio"]), 1e-300)
        if not gated
        else None
    )
    record = {
        "run": spec["run"],
        "mode": spec["mode"],
        "state": spec["state"],
        "lambda": lam,
        "N": spec["N"],
        "dt": dt,
        "steps": steps,
        "T": steps * dt,
        "projected_velocity": spec["projected"],
        "decisive": spec["run"] != "M1",
        "configuration_mismatches": mismatches,
        "actual_configuration": actual,
        "initial": initial,
        "statistics": statistics,
        "classes": {
            "ratio": ratio_class,
            "rate": rate_class,
            "closure": closure_class,
            "conservation": conservation_class,
            "frozen": frozen_class,
            "weight_identity": weight_identity,
        },
        "checkpoints": checkpoints,
        "series": series,
        "wall_time_seconds": time.time() - started,
    }
    print(
        f"[done] {spec['run']:>2} {spec['mode']:<17} {spec['state']:<9} N={spec['N']} "
        f"T={steps * dt:6.1f} R0={ratio_zero:.6f} RT={ratio_t:.6f} "
        f"r={statistics['r_fit'] if statistics['r_fit'] is not None else float('nan'):.6e} "
        f"sum={statistics['sum_residual']:.2e} closure={statistics['closure_max']:.2e} "
        f"{ratio_class}/{rate_class}/{closure_class}",
        flush=True,
    )
    return record


def classify_records(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    floors = {
        "ungated_base": records["C1"]["statistics"]["sum_residual"],
        "gated_static_box": records["C2"]["statistics"]["sum_residual"],
    }
    for record in records.values():
        measured = record["statistics"]["sum_residual"]
        floor = floors[record["mode"]]
        if measured <= SUM_TOL:
            record["classes"]["conservation"] = "exact"
        elif measured <= max(10.0 * SUM_TOL, 3.0 * floor):
            record["classes"]["conservation"] = "floor_limited"
        else:
            record["classes"]["conservation"] = "violated"
    long_record = records["L1"]
    final = long_record["checkpoints"][-1]
    gated_records = [records[tag] for tag in ("B1", "B2", "B3", "B4", "B5", "L1")]
    spreads = [
        row["openness_max"] - row["openness_min"]
        for record in gated_records
        for row in record["checkpoints"]
    ]
    maximum_spread = max(spreads)
    long_ratio_class = long_record["classes"]["ratio"]
    quartiles = final["quartiles"]
    l1_floor_clear = long_record["statistics"]["field_min"] > STEP_FLOOR
    if maximum_spread <= GATE_SPREAD_TOL:
        subquestion = "gate_uniform"
    elif not l1_floor_clear:
        subquestion = "gate_unresolved"
    elif long_ratio_class != "ray":
        subquestion = "gate_unresolved"
    elif quartiles is None:
        subquestion = "gate_unresolved"
    else:
        worst = max(abs(value / PHI - 1.0) for value in quartiles)
        subquestion = "gate_differentiates" if worst > RATIO_TOL else "gate_does_not_differentiate"
    weighted_deviation = final["weighted_ratio"] / PHI - 1.0
    return {
        "class": subquestion,
        "evaluated_run": "L1",
        "evaluated_checkpoint": final["t"],
        "openness_spread_max": maximum_spread,
        "openness_mean_at_checkpoint": final["openness_mean"],
        "quartile_ratios": quartiles,
        "quartile_worst_deviation": (
            max(abs(value / PHI - 1.0) for value in quartiles) if quartiles else None
        ),
        "weighted_ratio": final["weighted_ratio"],
        "weighted_ratio_deviation": weighted_deviation,
        "volume_ratio": final["ratio"],
        "volume_ratio_deviation": final["ratio"] / PHI - 1.0,
        "long_horizon_ratio_class": long_ratio_class,
        "l1_floor_flag_clear": l1_floor_clear,
        "b3_final_checkpoint": records["B3"]["checkpoints"][-1],
    }


def run_probe() -> dict[str, Any]:
    tf = load_module("cassi_two_fluid_3d_gpu", SOLVER)
    digest = sha256(SOLVER)
    if not torch.cuda.is_available():
        raise SystemExit("ROCm Torch CUDA device is required")
    device = torch.device("cuda")
    started = time.time()
    records: dict[str, dict[str, Any]] = {}
    for spec in DECLARED_RUNS:
        print(
            f"[run] {spec['run']:>2} mode={spec['mode']} state={spec['state']} "
            f"lambda={spec['lam']} N={spec['N']} steps={spec['steps']} projected={spec['projected']}",
            flush=True,
        )
        records[spec["run"]] = run_one(tf, spec, device)
    elapsed = time.time() - started
    subquestion = classify_records(records)

    checks: dict[str, Any] = {}

    def check(name: str, passed: bool, detail: Any) -> None:
        checks[name] = {"passed": bool(passed), "detail": detail}

    check("declared_run_count", len(records) == DECLARED_RUN_COUNT, len(records))
    mismatched = {
        run: record["configuration_mismatches"]
        for run, record in records.items()
        if record["configuration_mismatches"]
    }
    check("configuration_match", not mismatched, mismatched)
    check(
        "source_binding",
        digest == SOLVER_SHA256,
        {"measured": digest, "declared": SOLVER_SHA256},
    )
    nonfinite = {run: finite_scan(record) for run, record in records.items()}
    check("finite_values", sum(nonfinite.values()) == 0, nonfinite)
    coverage = {
        run: {
            "series": len(record["series"]),
            "fitted_samples": record["statistics"]["r_fit_samples"],
            "checkpoints": len(record["checkpoints"]),
            "t": record["T"],
        }
        for run, record in records.items()
    }
    expected_samples = {
        spec["run"]: {
            "series": spec["steps"] // SAMPLE_RECORD + 1,
            "fitted_samples": spec["steps"] // SAMPLE_FIT + 1,
        }
        for spec in DECLARED_RUNS
    }
    coverage_ok = all(
        row["checkpoints"] == len(CHECKPOINT_FRACTIONS)
        and row["series"] == expected_samples[run]["series"]
        and row["fitted_samples"] == expected_samples[run]["fitted_samples"]
        for run, row in coverage.items()
    )
    check("sampling_coverage", coverage_ok, {"measured": coverage, "declared": expected_samples})
    construction = {
        run: {
            "min_ey": record["initial"]["field_min_ey"],
            "min_ei": record["initial"]["field_min_ei"],
        }
        for run, record in records.items()
    }
    construction_margin = {
        run: min(row["min_ey"], row["min_ei"]) / STEP_FLOOR
        for run, row in construction.items()
    }
    check(
        "construction_positive_above_step_floor",
        all(margin > 1.0 for margin in construction_margin.values()),
        {
            "minima": construction,
            "margin_over_step_floor": construction_margin,
            "bound": STEP_FLOOR,
        },
    )
    declared_state = {
        run: {
            "ratio_zero": record["initial"]["ratio_zero"],
            "ratio_declared": record["initial"]["ratio_declared"],
            "ratio_relative": record["initial"]["ratio_zero"] / record["initial"]["ratio_declared"] - 1.0,
            "rho_mean_relative": record["initial"]["rho_mean"] / (1.0 + 1.0 / PHI) - 1.0,
        }
        for run, record in records.items()
    }
    check(
        "construction_declared_state",
        all(
            abs(row["ratio_relative"]) <= CONSTRUCTION_STATE_TOL
            and abs(row["rho_mean_relative"]) <= CONSTRUCTION_STATE_TOL
            for row in declared_state.values()
        ),
        {"measured": declared_state, "bound": CONSTRUCTION_STATE_TOL},
    )
    solenoidal = {
        run: record["initial"]["solenoidal_residual"]
        for run, record in records.items()
        if record["projected_velocity"]
    }
    check(
        "solenoidal",
        all(value <= SOLENOIDAL_TOL for value in solenoidal.values()),
        {"max": max(solenoidal.values()), "bound": SOLENOIDAL_TOL},
    )
    floors = {
        run: records[run]["statistics"]["field_min"]
        for run in T30_GATED_RUNS
    }
    l1_floor = {
        "field_min": records["L1"]["statistics"]["field_min"],
        "flag_clear": records["L1"]["statistics"]["field_min"] > STEP_FLOOR,
    }
    check(
        "step_floor_inactive",
        all(floors[run] > STEP_FLOOR for run in T30_GATED_RUNS),
        {"t30_gated_field_min": floors, "L1_flag": l1_floor, "bound": STEP_FLOOR},
    )
    refined = records["R1"]["statistics"]
    coarse = records["A3"]["statistics"]
    refinement = {
        "rate_relative_difference": abs(refined["r_fit"] / coarse["r_fit"] - 1.0),
        "ratio_relative_difference": abs(refined["ratio_t"] / coarse["ratio_t"] - 1.0),
    }
    check(
        "refinement_agreement",
        max(refinement.values()) <= REFINE_TOL,
        {"measured": refinement, "bound": REFINE_TOL},
    )
    weight_identities = {
        run: record["classes"]["weight_identity"]
        for run, record in records.items()
        if record["classes"]["weight_identity"] is not None
    }
    check(
        "mode_a_weight_identity",
        all(value <= WEIGHT_IDENTITY_TOL for value in weight_identities.values()),
        {"max": max(weight_identities.values()), "bound": WEIGHT_IDENTITY_TOL},
    )

    integrity = all(entry["passed"] for entry in checks.values())
    frozen_controls = {
        run: records[run]["classes"]["frozen"] for run in FROZEN_CONTROL_RUNS
    }
    mutation = {
        "conservation_class": records["M1"]["classes"]["conservation"],
        "closure_class": records["M1"]["classes"]["closure"],
        "sum_residual": records["M1"]["statistics"]["sum_residual"],
        "closure_max": records["M1"]["statistics"]["closure_max"],
        "fired": (
            records["M1"]["classes"]["conservation"] == "violated"
            or records["M1"]["classes"]["closure"] == "closure_fails"
        ),
    }
    contradictory: dict[str, Any] = {}
    l1_decisive = l1_floor["flag_clear"]
    for run in DECISIVE_RUNS:
        record = records[run]
        classes = record["classes"]
        if run == "L1" and not l1_decisive:
            continue
        if classes["ratio"] in ("other_ratio", "departing"):
            contradictory.setdefault("ratio", []).append(run)
        if record["mode"] == MODE_UNGATED and classes["rate"] in (
            "rate_above",
            "rate_below_gated",
            "rate_below_unexplained",
        ):
            contradictory.setdefault("rate_ungated", []).append(run)
        if record["mode"] == MODE_GATED and classes["rate"] in ("rate_above", "rate_below_unexplained"):
            contradictory.setdefault("rate_gated", []).append(run)
        if classes["closure"] == "closure_fails":
            contradictory.setdefault("closure", []).append(run)
        if classes["conservation"] == "violated":
            contradictory.setdefault("conservation", []).append(run)
    for run, value in frozen_controls.items():
        if value != "frozen":
            contradictory.setdefault("frozen_control", []).append(run)

    supports_conditions = {
        "mode_a_ray_and_rate": all(
            records[run]["classes"]["ratio"] == "ray"
            and records[run]["classes"]["rate"] == "rate_matches"
            for run in ("A2", "A3", "A4", "A5")
        ),
        "mode_a_ray_control": records["A1"]["classes"]["ratio"] == "ray",
        "gated_approach": all(
            records[run]["classes"]["ratio"] in ("ray", "approaching")
            and records[run]["classes"]["closure"] == "closure_holds"
            and records[run]["classes"]["rate"] in ("rate_not_defined", "rate_matches", "rate_below_gated")
            for run in T30_GATED_DECISIVE
        ),
        "gated_long_horizon_ray": l1_decisive
        and records["L1"]["classes"]["ratio"] == "ray"
        and records["L1"]["classes"]["closure"] == "closure_holds",
        "conservation": all(
            records[run]["classes"]["conservation"] in ("exact", "floor_limited")
            for run in DECISIVE_RUNS
        ),
        "subquestion_classified": subquestion["class"] != "gate_unresolved",
    }
    if not integrity:
        verdict = None
    elif contradictory:
        verdict = "CONTRADICTS"
    elif all(supports_conditions.values()):
        verdict = "SUPPORTS"
    else:
        verdict = "INCONCLUSIVE"
    if verdict is not None and verdict not in ("SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"):
        raise RuntimeError(f"undeclared verdict {verdict}")

    receipt = {
        "schema": SCHEMA,
        "protocol_revision": PROTOCOL_REVISION,
        "probe_revision": PROBE_REVISION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if integrity else "FAIL",
        "verdict": verdict,
        "verdict_scope": "phi ray and conversion rate of the canonical two-fluid solver at the declared settings",
        "scope": {
            "grid": [spec["N"] for spec in DECLARED_RUNS],
            "N_primary": 32,
            "N_resolution": 64,
            "L": L,
            "lambda": LAM,
            "nu": NU,
            "D": DIFFUSIVITY,
            "chi": MOBILITY,
            "dt": DT,
            "T": T_END,
            "T_long": T_LONG,
            "steps": STEPS,
            "steps_long": STEPS_LONG,
            "steps_refined": STEPS_REFINED,
            "band": BAND,
            "amplitude": AMPLITUDE,
            "velocity_amplitude": VELOCITY_AMPLITUDE,
            "seeds": {"ey": SEED_EY, "ei": SEED_EI, "u": SEED_U},
            "states": STATE_RATIOS,
            "runs": [spec["run"] for spec in DECLARED_RUNS],
        },
        "predictions": {
            "phi": PHI,
            "predicted_rate": PREDICTED_RATE,
            "ray_openness": RAY_OPENNESS,
            "ray_side_rate": RAY_SIDE_RATE,
        },
        "decision_parameters": {
            "ratio_tolerance": RATIO_TOL,
            "rate_tolerance": RATE_TOL,
            "sum_tolerance": SUM_TOL,
            "closure_tolerance": CLOSURE_TOL,
            "refinement_tolerance": REFINE_TOL,
            "solenoidal_tolerance": SOLENOIDAL_TOL,
            "construction_state_tolerance": CONSTRUCTION_STATE_TOL,
            "step_floor": STEP_FLOOR,
            "gate_spread_tolerance": GATE_SPREAD_TOL,
            "rate_floor": RATE_FLOOR,
            "control_ratio_tolerance": CONTROL_RATIO_TOL,
            "ray_eps_floor": RAY_EPS_FLOOR,
        },
        "checks": checks,
        "frozen_controls": frozen_controls,
        "mutation_control": mutation,
        "subquestion": subquestion,
        "aggregate": {
            "contradictory_conditions": contradictory,
            "supports_conditions": supports_conditions,
            "verdict_domain": ["SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"],
        },
        "wall_time_seconds": elapsed,
        "source_hashes": {
            "two-fluid/cassi_two_fluid_3d_gpu.py": digest,
            "computations/verify_two_fluid_phi_ray_relaxation.py": sha256(SCRIPT),
            "computations/two-fluid-phi-ray-relaxation-prereg.md": sha256(PROTOCOL),
            "foundations/cassi-first-principles.md": sha256(FOUNDATION_ONE),
            "foundations/physical-becoming-hierarchy.md": sha256(FOUNDATION_TWO),
        },
        "runs": [records[spec["run"]] for spec in DECLARED_RUNS],
    }
    return sanitize(receipt)


def run_smoke() -> None:
    tf = load_module("cassi_two_fluid_3d_gpu", SOLVER)
    digest = sha256(SOLVER)
    if digest != SOLVER_SHA256:
        raise SystemExit(f"smoke FAILED: solver digest {digest}")
    if not torch.cuda.is_available():
        raise SystemExit("smoke FAILED: ROCm Torch CUDA device is required")
    device = torch.device("cuda")
    for mode, lam in ((MODE_UNGATED, LAM), (MODE_GATED, LAM), (MODE_UNGATED, 0.0)):
        spec = {
            "run": "smoke",
            "mode": mode,
            "state": "inv",
            "lam": lam,
            "N": 8,
            "dt": DT,
            "steps": 200,
            "projected": True,
        }
        record = run_one(tf, spec, device)
        statistics = record["statistics"]
        if not math.isfinite(statistics["ratio_t"]) or not math.isfinite(statistics["sum_residual"]):
            raise SystemExit(f"smoke FAILED: nonfinite reading in {mode}")
        print(
            f"smoke: mode={mode} lam={lam} RT={statistics['ratio_t']:.9f} "
            f"sum={statistics['sum_residual']:.3e} closure={statistics['closure_max']:.3e} "
            f"checks={record['classes']['weight_identity']}"
        )
    print("smoke: PASS")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--smoke", action="store_true")
    arguments = parser.parse_args()
    if arguments.smoke:
        run_smoke()
        return 0

    receipt = run_probe()
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    failed = [name for name, entry in receipt["checks"].items() if not entry["passed"]]
    print(f"status={receipt['status']} verdict={receipt['verdict']}")
    print(f"checks: {len(receipt['checks']) - len(failed)}/{len(receipt['checks'])} passed")
    for name in failed:
        print(f"FAILED {name}: {receipt['checks'][name]['detail']}")
    print(f"wall_time_seconds={receipt['wall_time_seconds']:.2f}")
    for record in receipt["runs"]:
        statistics = record["statistics"]
        classes = record["classes"]
        print(
            f"{record['run']:>2} {record['mode']:<17} {record['state']:<9} "
            f"R0={statistics['ratio_zero']:.6f} RT={statistics['ratio_t']:.9f} "
            f"rate={statistics['r_fit'] if statistics['r_fit'] is not None else float('nan'):.8e} "
            f"sum={statistics['sum_residual']:.2e} closure={statistics['closure_max']:.2e} "
            f"{classes['ratio']}/{classes['rate']}/{classes['closure']}/{classes['conservation']}"
        )
    subquestion = receipt["subquestion"]
    print(
        f"subquestion={subquestion['class']} quartet={subquestion['quartile_ratios']} "
        f"weighted={subquestion['weighted_ratio']:.9f} spread={subquestion['openness_spread_max']:.3e}"
    )
    print(f"mutation_control={receipt['mutation_control']}")
    print(f"receipt: {arguments.output}")
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
