#!/usr/bin/env python3
"""Frozen Wave-5 source-only passive receiver-transfer probe.

Run from the CassiTheory repository root::

    python field-experience/source_only_passive_transfer_probe.py

Protocol: field-experience/source-only-passive-transfer-pre-registration.md
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from counterflow_resonant_addressing_probe import (
    DT,
    FLOOR,
    MATCH_THRESHOLD,
    N,
    ROOT,
    TARGET,
    build_context,
    build_solver,
    initialize_arm,
    normalized,
    signed_periodic_delta,
    weighted_mean,
)
from counterflow_amplitude_phase_kick_probe import (
    FLOOR_MARGIN,
    KICK_ALPHA_CAP,
    KICK_BISECT_ITERS,
    KICK_L2,
    NORM_TOL,
    RHO_TOL,
    amplitude_current,
    amplitude_fields,
    amplitude_phasor,
    kick_norm,
)

# Frozen Wave-5 execution values.
HORIZON = 260
PULSE_STEP = 100
ANALYSIS_K_MIN = 20
ANALYSIS_K_MAX = 120
COMPACT_RADIUS = 6.0
T_CENTER = (12.0, 12.0, 24.0)
D_CENTER = (24.0, 24.0, 24.0)
A_CENTER = (12.0, 29.0, 24.0)
DIRECTION_D = (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0)
F1_THRESHOLD = 0.010
F2_THRESHOLD = 0.005
F3_THRESHOLD = 0.005

SOURCE_ARMS = (
    "source_plus",
    "source_minus",
    "source_shuffled_plus",
    "source_shuffled_minus",
)
DIRECT_ARMS = (
    "direct_diagonal_plus",
    "direct_diagonal_minus",
    "direct_axial_plus",
    "direct_axial_minus",
    "direct_diagonal_shuffled_plus",
    "direct_diagonal_shuffled_minus",
    "direct_axial_shuffled_plus",
    "direct_axial_shuffled_minus",
)
ARM_ORDER = (
    "baseline",
    "source_plus",
    "source_minus",
    "direct_diagonal_plus",
    "direct_diagonal_minus",
    "direct_axial_plus",
    "direct_axial_minus",
    "source_shuffled_plus",
    "source_shuffled_minus",
    "direct_diagonal_shuffled_plus",
    "direct_diagonal_shuffled_minus",
    "direct_axial_shuffled_plus",
    "direct_axial_shuffled_minus",
)


class ProtocolInvalid(RuntimeError):
    """Raised when an execution-time frozen quality condition fails."""


def compact_bump(
    X: torch.Tensor,
    Y: torch.Tensor,
    Z: torch.Tensor,
    center: tuple[float, float, float],
    radius: float = COMPACT_RADIUS,
) -> torch.Tensor:
    """Return the frozen compact periodic C-infinity bump b_C."""
    dx = signed_periodic_delta(X, center[0])
    dy = signed_periodic_delta(Y, center[1])
    dz = signed_periodic_delta(Z, center[2])
    radius_sq = dx * dx + dy * dy + dz * dz
    inside = radius_sq < radius * radius
    q_sq = radius_sq / (radius * radius)
    # Avoid evaluating the singular denominator outside the support while
    # preserving the exact strict-support definition at |delta_N| = radius.
    denominator = torch.where(inside, 1.0 - q_sq, torch.ones_like(q_sq))
    values = torch.exp(1.0 - 1.0 / denominator)
    return torch.where(inside, values, torch.zeros_like(values))


def build_compact_context(solver: Any) -> dict[str, Any]:
    """Extend the canonical context with frozen compact masks and weights."""
    context = build_context(solver)
    X, Y, Z = context["X"], context["Y"], context["Z"]
    masks = {
        "T": compact_bump(X, Y, Z, T_CENTER),
        "D": compact_bump(X, Y, Z, D_CENTER),
        "A": compact_bump(X, Y, Z, A_CENTER),
    }
    context["compact_masks"] = masks
    context["chi_T"] = normalized(masks["T"])
    context["chi_D"] = normalized(masks["D"])
    context["chi_A"] = normalized(masks["A"])
    return context


def support_audit(context: dict[str, Any]) -> dict[str, Any]:
    """Audit exact compact support and source/receiver disjointness."""
    masks = context["compact_masks"]
    support = {name: mask > 0.0 for name, mask in masks.items()}
    overlaps: dict[str, Any] = {}
    for left, right in (("T", "D"), ("T", "A"), ("D", "A")):
        product = masks[left] * masks[right]
        overlaps[f"{left}_{right}"] = {
            "max_product": float(product.max()),
            "overlap_cells": int((support[left] & support[right]).sum()),
            "disjoint": bool(torch.all(product == 0.0)),
        }
    return {
        "radius": COMPACT_RADIUS,
        "centers": {"T": T_CENTER, "D": D_CENTER, "A": A_CENTER},
        "support_cells": {name: int(value.sum()) for name, value in support.items()},
        "max_values": {name: float(mask.max()) for name, mask in masks.items()},
        "overlaps": overlaps,
        "source_receiver_disjoint": bool(
            overlaps["T_D"]["disjoint"] and overlaps["T_A"]["disjoint"]
        ),
    }

def synchronized_no_op_identity(device: torch.device) -> float:
    """Compare the actual read-only trace wrapper with direct canonical RK2."""
    direct = build_solver(device)
    wrapped = build_solver(device)
    direct_context = build_context(direct)
    wrapped_context = build_compact_context(wrapped)
    u0, ey0, ei0 = initialize_arm(direct, direct_context, +1, False)
    u1, ey1, ei1 = initialize_arm(wrapped, wrapped_context, +1, False)
    ey_wrapped = torch.fft.ifftn(ey1).real
    ei_wrapped = torch.fft.ifftn(ei1).real
    for step in range(100):
        state_snapshot(wrapped, ey_wrapped, ei_wrapped, wrapped_context, step)
        u0, ey0, ei0 = direct.rk2_step(u0, ey0, ei0, DT)
        u1, ey1, ei1 = wrapped.rk2_step(u1, ey1, ei1, DT)
        ey_wrapped = torch.fft.ifftn(ey1).real
        ei_wrapped = torch.fft.ifftn(ei1).real
        if device.type == "cuda":
            torch.cuda.synchronize(device)
    state_snapshot(wrapped, ey_wrapped, ei_wrapped, wrapped_context, 100)
    delta = [torch.max(torch.abs(ey0 - ey1)), torch.max(torch.abs(ei0 - ei1))]
    delta.extend(torch.max(torch.abs(left - right)) for left, right in zip(u0, u1))
    return max(float(value) for value in delta)


def receiver_metrics(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    context: dict[str, Any],
) -> dict[str, float]:
    """Measure frozen amplitude phase-current projections at D and A."""
    Jx, Jy, Jz = amplitude_current(solver, ey, ei)
    current_sq = Jx * Jx + Jy * Jy + Jz * Jz
    chi_D = context["chi_D"]
    chi_A = context["chi_A"]
    return {
        "j_D": weighted_mean(Jx * DIRECTION_D[0] + Jy * DIRECTION_D[1], chi_D),
        "j_A": weighted_mean(Jy, chi_A),
        "j_D_rms": float(torch.sqrt((current_sq * chi_D).sum())),
        "j_A_rms": float(torch.sqrt((current_sq * chi_A).sum())),
        "j_D_x": weighted_mean(Jx, chi_D),
        "j_D_y": weighted_mean(Jy, chi_D),
        "j_A_x": weighted_mean(Jx, chi_A),
        "j_A_y": weighted_mean(Jy, chi_A),
        "j_D_z": weighted_mean(Jz, chi_D),
        "j_A_z": weighted_mean(Jz, chi_A),
    }


def state_snapshot(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    context: dict[str, Any],
    step: int,
) -> dict[str, float | int | bool]:
    """Record one full receiver/current and field-integrity sample."""
    values: dict[str, float | int | bool] = receiver_metrics(solver, ey, ei, context)
    values.update(
        {
            "step": step,
            "t": step * DT,
            "ey_min": float(ey.min()),
            "ei_min": float(ei.min()),
            "floor_ey": int((ey <= FLOOR + 1.0e-12).sum()),
            "floor_ei": int((ei <= FLOOR + 1.0e-12).sum()),
            "mass": float((ey + ei).sum()),
            "rho_finite": bool(torch.isfinite(ey).all() and torch.isfinite(ei).all()),
        }
    )
    return values


def compact_kick(
    ey_hat: torch.Tensor,
    ei_hat: torch.Tensor,
    mask: torch.Tensor,
    sign: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float | bool]]:
    """Apply one frozen compact-profile SO(2) amplitude-space rotation."""
    if sign not in (-1, 1):
        raise ValueError(f"kick sign must be +/-1, got {sign}")

    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    A, B = amplitude_fields(ey, ei)
    rho = ey + ei
    max_norm = float(kick_norm(A, B, mask, KICK_ALPHA_CAP))
    if max_norm + NORM_TOL < KICK_L2:
        raise ProtocolInvalid(
            f"compact kick capacity {max_norm:.12g} is below {KICK_L2:.12g}"
        )

    lo, hi = 0.0, KICK_ALPHA_CAP
    for _ in range(KICK_BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        if float(kick_norm(A, B, mask, mid)) < KICK_L2:
            lo = mid
        else:
            hi = mid
    beta = 0.5 * (lo + hi)
    alpha = sign * beta * mask

    theta = torch.atan2(B, A)
    floor_angle = torch.asin(torch.sqrt((FLOOR + FLOOR_MARGIN) / rho))
    theta_after = theta + alpha
    angle_margin = torch.minimum(
        theta_after - floor_angle,
        math.pi / 2.0 - floor_angle - theta_after,
    )
    safety = bool(torch.all(angle_margin >= 0.0))
    if not safety:
        raise ProtocolInvalid("compact kick violates the frozen positivity wedge")

    Ap = torch.cos(alpha) * A - torch.sin(alpha) * B
    Bp = torch.sin(alpha) * A + torch.cos(alpha) * B
    ey_post = Ap * Ap
    ei_post = Bp * Bp
    rho_post = ey_post + ei_post
    actual_norm = float(torch.sqrt(((Ap - A) ** 2 + (Bp - B) ** 2).sum()))
    rho_error = float(torch.max(torch.abs(rho_post - rho)))
    mass_rel_error = float(torch.abs(rho_post.sum() - rho.sum()) / rho.sum())
    finite_after = bool(torch.isfinite(ey_post).all() and torch.isfinite(ei_post).all())
    return torch.fft.fftn(ey_post), torch.fft.fftn(ei_post), {
        "beta": beta,
        "capacity": beta <= KICK_ALPHA_CAP + NORM_TOL,
        "kick_l2": actual_norm,
        "norm_error": abs(actual_norm - KICK_L2),
        "alpha_abs_max": float(alpha.abs().max()),
        "rho_error_max": rho_error,
        "mass_rel_error": mass_rel_error,
        "safety": safety,
        "angle_margin_min": float(angle_margin.min()),
        "ey_min_after": float(ey_post.min()),
        "ei_min_after": float(ei_post.min()),
        "floor_after": bool(
            (ey_post <= FLOOR + 1.0e-12).any()
            or (ei_post <= FLOOR + 1.0e-12).any()
        ),
        "finite_after": finite_after,
    }


def target_phase_match(
    ey: torch.Tensor,
    ei: torch.Tensor,
    context: dict[str, Any],
    theta_t0: float,
) -> float:
    """Return the frozen target phase-match M at the pulse step."""
    z_target = amplitude_phasor(ey, ei, context["target_weight"])
    if abs(z_target) <= 1.0e-14:
        return float("nan")
    phase_ratio = (z_target / abs(z_target)) * complex(
        math.cos(-theta_t0), math.sin(-theta_t0)
    )
    return float(phase_ratio.real)


def run_arm(
    tag: str,
    device: torch.device,
    spatial_shuffled: bool,
    pulse_mask_name: str | None,
    pulse_sign: int,
    outdir: Path,
) -> dict[str, Any]:
    """Run one fresh solver arm and emit its complete per-arm receipt."""
    solver = build_solver(device)
    context = build_compact_context(solver)
    u_hat, ey_hat, ei_hat = initialize_arm(solver, context, +1, spatial_shuffled)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    initial = state_snapshot(solver, ey, ei, context, 0)
    z0 = amplitude_phasor(ey, ei, context["target_weight"])
    if abs(z0) <= 1.0e-14:
        raise ProtocolInvalid(f"{tag}: initial target amplitude phasor is zero")
    theta_t0 = math.atan2(z0.imag, z0.real)

    pulse: dict[str, Any] | None = None
    trace: list[dict[str, float | int | bool]] = []
    min_ey_observed = float(initial["ey_min"])
    min_ei_observed = float(initial["ei_min"])
    finite_seen = bool(initial["rho_finite"])
    floor_seen = bool(initial["floor_ey"] or initial["floor_ei"])
    started = time.time()

    for step in range(HORIZON + 1):
        if step == PULSE_STEP and pulse_mask_name is not None:
            if pulse_sign not in (-1, 1):
                raise ValueError(f"{tag}: active arm has invalid pulse sign")
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            match = target_phase_match(ey, ei, context, theta_t0)
            source_arm = pulse_mask_name == "T"
            if source_arm and (not math.isfinite(match) or match < MATCH_THRESHOLD):
                raise ProtocolInvalid(
                    f"{tag}: target phase match {match!r} is below {MATCH_THRESHOLD:.12g}"
                )
            ey_hat, ei_hat, kick_receipt = compact_kick(
                ey_hat,
                ei_hat,
                context["compact_masks"][pulse_mask_name],
                pulse_sign,
            )
            pulse = {
                "step": step,
                "t": step * DT,
                "mask": pulse_mask_name,
                "sign": pulse_sign,
                "target_phase_match": match if source_arm else None,
                **kick_receipt,
            }
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real

        sample = state_snapshot(solver, ey, ei, context, step)
        trace.append(sample)
        min_ey_observed = min(min_ey_observed, float(sample["ey_min"]))
        min_ei_observed = min(min_ei_observed, float(sample["ei_min"]))
        finite_seen = finite_seen and bool(sample["rho_finite"])
        floor_seen = floor_seen or bool(sample["floor_ey"] or sample["floor_ei"])

        if step < HORIZON:
            u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real

    if pulse_mask_name is not None and pulse is None:
        raise ProtocolInvalid(f"{tag}: active pulse was not applied")
    summary = {
        "n_pulses": int(pulse is not None),
        "trace_length": len(trace),
        "trace_steps": [int(trace[0]["step"]), int(trace[-1]["step"])],
        "initial": initial,
        "final": trace[-1],
        "theta_T0": theta_t0,
        "min_ey_observed": min_ey_observed,
        "min_ei_observed": min_ei_observed,
        "finite_seen": finite_seen,
        "floor_seen": floor_seen,
        "initial_j_D_rms": float(initial["j_D_rms"]),
        "initial_j_A_rms": float(initial["j_A_rms"]),
        "elapsed_s": time.time() - started,
    }
    result: dict[str, Any] = {
        "tag": tag,
        "spatial_shuffled": spatial_shuffled,
        "pulse_mask": pulse_mask_name,
        "pulse_sign": pulse_sign,
        "pulse": pulse,
        "receiver_trace": trace,
        "summary": summary,
    }
    with (outdir / f"run_{tag}.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(
        f"[{tag}] pulse={pulse_mask_name or 'none'} trace={len(trace)} "
        f"jD0={float(initial['j_D_rms']):.5f} "
        f"jA0={float(initial['j_A_rms']):.5f} "
        f"{summary['elapsed_s']:.1f}s",
        flush=True,
    )
    return result


def delayed_gain_values(
    plus_values: list[float],
    minus_values: list[float],
    scale: float,
) -> float:
    """Compute G from indexed plus/minus receiver values."""
    if len(plus_values) <= PULSE_STEP + ANALYSIS_K_MAX:
        raise ProtocolInvalid("receiver trace is shorter than the frozen lag window")
    if len(minus_values) != len(plus_values):
        raise ProtocolInvalid("plus/minus receiver traces have different lengths")
    if not math.isfinite(scale) or scale <= 0.0:
        raise ProtocolInvalid("receiver-current normalization scale is not positive")
    antisymmetric = np.asarray(
        [
            (float(plus_values[PULSE_STEP + k]) - float(minus_values[PULSE_STEP + k]))
            / 2.0
            for k in range(ANALYSIS_K_MIN, ANALYSIS_K_MAX + 1)
        ],
        dtype=np.float64,
    )
    return float(np.sqrt(np.mean((antisymmetric / scale) ** 2)))


def synthetic_trace_checks() -> dict[str, Any]:
    """Exercise the delayed-gain implementation on frozen synthetic traces."""
    equal_plus = [0.25] * (HORIZON + 1)
    equal_minus = [0.25] * (HORIZON + 1)
    unit_plus = [1.0] * (HORIZON + 1)
    unit_minus = [-1.0] * (HORIZON + 1)
    equal_gain = delayed_gain_values(equal_plus, equal_minus, 1.0)
    unit_gain = delayed_gain_values(unit_plus, unit_minus, 1.0)
    return {
        "equal_trace_gain": equal_gain,
        "unit_antisymmetric_gain": unit_gain,
        "passes": abs(equal_gain) <= 1.0e-15 and abs(unit_gain - 1.0) <= 1.0e-15,
    }


def antisymmetric_pair(
    runs: dict[str, dict[str, Any]],
    pair_name: str,
    plus_name: str,
    minus_name: str,
) -> dict[str, Any]:
    """Form full post-pulse antisymmetric traces and the frozen gain window."""
    plus_trace = runs[plus_name]["receiver_trace"]
    minus_trace = runs[minus_name]["receiver_trace"]
    if len(plus_trace) != HORIZON + 1 or len(minus_trace) != HORIZON + 1:
        raise ProtocolInvalid(f"{pair_name}: incomplete per-step trace")
    if [row["step"] for row in plus_trace] != [row["step"] for row in minus_trace]:
        raise ProtocolInvalid(f"{pair_name}: plus/minus step indices differ")

    full: list[dict[str, float | int]] = []
    for k in range(0, HORIZON - PULSE_STEP + 1):
        step = PULSE_STEP + k
        full.append(
            {
                "k": k,
                "step": step,
                "t": step * DT,
                "S_D": 0.5 * (float(plus_trace[step]["j_D"]) - float(minus_trace[step]["j_D"])),
                "S_A": 0.5 * (float(plus_trace[step]["j_A"]) - float(minus_trace[step]["j_A"])),
            }
        )
    window = [
        row for row in full if ANALYSIS_K_MIN <= int(row["k"]) <= ANALYSIS_K_MAX
    ]
    if len(window) != ANALYSIS_K_MAX - ANALYSIS_K_MIN + 1:
        raise ProtocolInvalid(f"{pair_name}: lag-window trace is absent")

    j_D_scale = float(runs[plus_name]["summary"]["initial_j_D_rms"])
    j_A_scale = float(runs[plus_name]["summary"]["initial_j_A_rms"])
    gains = {
        "G_D": delayed_gain_values(
            [float(row["j_D"]) for row in plus_trace],
            [float(row["j_D"]) for row in minus_trace],
            j_D_scale,
        ),
        "G_A": delayed_gain_values(
            [float(row["j_A"]) for row in plus_trace],
            [float(row["j_A"]) for row in minus_trace],
            j_A_scale,
        ),
    }
    return {
        "plus_arm": plus_name,
        "minus_arm": minus_name,
        "initial_scales": {"J_D_rms_0": j_D_scale, "J_A_rms_0": j_A_scale},
        "antisymmetric_trace": full,
        "analysis_window": window,
        "gains": gains,
    }


def form_pair_analyses(runs: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        "source": antisymmetric_pair(runs, "source", "source_plus", "source_minus"),
        "direct_diagonal": antisymmetric_pair(
            runs, "direct_diagonal", "direct_diagonal_plus", "direct_diagonal_minus"
        ),
        "direct_axial": antisymmetric_pair(
            runs, "direct_axial", "direct_axial_plus", "direct_axial_minus"
        ),
        "source_shuffled": antisymmetric_pair(
            runs, "source_shuffled", "source_shuffled_plus", "source_shuffled_minus"
        ),
        "direct_diagonal_shuffled": antisymmetric_pair(
            runs,
            "direct_diagonal_shuffled",
            "direct_diagonal_shuffled_plus",
            "direct_diagonal_shuffled_minus",
        ),
        "direct_axial_shuffled": antisymmetric_pair(
            runs,
            "direct_axial_shuffled",
            "direct_axial_shuffled_plus",
            "direct_axial_shuffled_minus",
        ),
    }


def transfer_metrics(pairs: dict[str, dict[str, Any]]) -> dict[str, float]:
    """Compute standard/shuffled transfer fractions and diagonal excesses."""
    G_D_source = float(pairs["source"]["gains"]["G_D"])
    G_A_source = float(pairs["source"]["gains"]["G_A"])
    G_D_direct = float(pairs["direct_diagonal"]["gains"]["G_D"])
    G_A_direct = float(pairs["direct_axial"]["gains"]["G_A"])
    G_D_source_shuf = float(pairs["source_shuffled"]["gains"]["G_D"])
    G_A_source_shuf = float(pairs["source_shuffled"]["gains"]["G_A"])
    G_D_direct_shuf = float(pairs["direct_diagonal_shuffled"]["gains"]["G_D"])
    G_A_direct_shuf = float(pairs["direct_axial_shuffled"]["gains"]["G_A"])
    for name, value in {
        "G_D_direct": G_D_direct,
        "G_A_direct": G_A_direct,
        "G_D_direct_shuffled": G_D_direct_shuf,
        "G_A_direct_shuffled": G_A_direct_shuf,
    }.items():
        if value <= 1.0e-12:
            raise ProtocolInvalid(f"{name} is at or below the frozen calibration floor")
    F_D = G_D_source / G_D_direct
    F_A = G_A_source / G_A_direct
    F_D_shuf = G_D_source_shuf / G_D_direct_shuf
    F_A_shuf = G_A_source_shuf / G_A_direct_shuf
    return {
        "G_D_source": G_D_source,
        "G_A_source": G_A_source,
        "G_D_direct": G_D_direct,
        "G_A_direct": G_A_direct,
        "G_D_source_shuffled": G_D_source_shuf,
        "G_A_source_shuffled": G_A_source_shuf,
        "G_D_direct_shuffled": G_D_direct_shuf,
        "G_A_direct_shuffled": G_A_direct_shuf,
        "F_D": F_D,
        "F_A": F_A,
        "F_D_shuffled": F_D_shuf,
        "F_A_shuffled": F_A_shuf,
        "E": F_D - F_A,
        "E_shuffled": F_D_shuf - F_A_shuf,
        "E_minus_E_shuffled": (F_D - F_A) - (F_D_shuf - F_A_shuf),
    }


def quality_receipt(
    identity_delta: float,
    support: dict[str, Any],
    synthetic: dict[str, Any],
    runs: dict[str, dict[str, Any]],
    transfers: dict[str, float],
) -> dict[str, Any]:
    """Apply every frozen Wave-5 execution and measurement quality gate."""
    all_runs = [runs[name] for name in ARM_ORDER]
    all_samples = [sample for run in all_runs for sample in run["receiver_trace"]]
    pulses = [run["pulse"] for run in all_runs if run["pulse"] is not None]
    source_matches = {
        name: runs[name]["pulse"]["target_phase_match"] for name in SOURCE_ARMS
    }
    source_match_ok = all(
        math.isfinite(float(value)) and float(value) >= MATCH_THRESHOLD
        for value in source_matches.values()
    )
    capacities = all(bool(pulse["capacity"]) for pulse in pulses)
    norm_error = max((float(pulse["norm_error"]) for pulse in pulses), default=float("inf"))
    rho_error = max((float(pulse["rho_error_max"]) for pulse in pulses), default=float("inf"))
    mass_error = max((float(pulse["mass_rel_error"]) for pulse in pulses), default=float("inf"))
    wedge_margin = min(
        (float(pulse["angle_margin_min"]) for pulse in pulses),
        default=-float("inf"),
    )
    quality = {
        "synthetic_trace_checks": synthetic,
        "identity_exact": identity_delta == 0.0,
        "identity_delta": identity_delta,
        "support_disjoint": bool(support["source_receiver_disjoint"]),
        "support_audit": support,
        "source_phase_match": source_matches,
        "source_phase_match_ok": source_match_ok,
        "finite": all(bool(run["summary"]["finite_seen"]) for run in all_runs)
        and all(bool(sample["rho_finite"]) for sample in all_samples)
        and all(bool(pulse["finite_after"]) for pulse in pulses),
        "no_floor_hits": all(not bool(run["summary"]["floor_seen"]) for run in all_runs)
        and all(int(sample["floor_ey"]) == 0 and int(sample["floor_ei"]) == 0 for sample in all_samples)
        and all(not bool(pulse["floor_after"]) for pulse in pulses),
        "n_active_pulses": len(pulses),
        "one_pulse_per_active_arm": len(pulses) == len(SOURCE_ARMS) + len(DIRECT_ARMS),
        "capacity": capacities,
        "beta_max": max((float(pulse["beta"]) for pulse in pulses), default=float("inf")),
        "kick_norm_error_max": norm_error,
        "kick_norm_match": norm_error <= NORM_TOL,
        "rho_error_max": rho_error,
        "rho_invariant": rho_error <= RHO_TOL,
        "mass_rel_error_max": mass_error,
        "mass_invariant": mass_error <= RHO_TOL,
        "minimum_angle_margin": wedge_margin,
        "safety_wedge": wedge_margin >= 0.0 and all(bool(pulse["safety"]) for pulse in pulses),
        "all_lag_windows_present": all(
            len(runs[name]["receiver_trace"]) == HORIZON + 1 for name in ARM_ORDER
        ),
        "direct_calibrations_positive": bool(
            transfers["G_D_direct"] > 1.0e-12
            and transfers["G_A_direct"] > 1.0e-12
            and transfers["G_D_direct_shuffled"] > 1.0e-12
            and transfers["G_A_direct_shuffled"] > 1.0e-12
        ),
    }
    quality["valid"] = bool(
        quality["synthetic_trace_checks"]["passes"]
        and quality["identity_exact"]
        and quality["support_disjoint"]
        and quality["source_phase_match_ok"]
        and quality["finite"]
        and quality["no_floor_hits"]
        and quality["one_pulse_per_active_arm"]
        and quality["capacity"]
        and quality["kick_norm_match"]
        and quality["rho_invariant"]
        and quality["mass_invariant"]
        and quality["safety_wedge"]
        and quality["all_lag_windows_present"]
        and quality["direct_calibrations_positive"]
    )
    return quality


def classify(
    quality: dict[str, Any],
    transfers: dict[str, float],
) -> dict[str, Any]:
    """Apply frozen F1-F3 labels and terminal decision tree."""
    if not quality["valid"]:
        return {
            "verdict": "INVALID",
            "features": {
                "F1": "DOES NOT EMERGE",
                "F2": "DOES NOT EMERGE",
                "F3": "DOES NOT EMERGE",
            },
        }
    f1 = transfers["F_D"] >= F1_THRESHOLD
    f2 = transfers["E"] >= F2_THRESHOLD
    f3 = transfers["E_minus_E_shuffled"] >= F3_THRESHOLD
    if f1 and f2 and f3:
        verdict = "SUPPORTS"
    elif f1 and f2 and not f3:
        verdict = "HOLD"
    elif not f1 or not f2:
        verdict = "CONTRADICTS"
    else:
        verdict = "INCONCLUSIVE"
    return {
        "verdict": verdict,
        "features": {
            "F1": "EMERGES" if f1 else "DOES NOT EMERGE",
            "F2": "EMERGES" if f2 else "DOES NOT EMERGE",
            "F3": "EMERGES" if f3 else "DOES NOT EMERGE",
        },
        "thresholds": {"F1": F1_THRESHOLD, "F2": F2_THRESHOLD, "F3": F3_THRESHOLD},
    }


def output_directory(argument: str | None) -> Path:
    if argument is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return ROOT / "runs" / f"{run_id}_source_only_passive_transfer"
    outdir = Path(argument)
    if not outdir.is_absolute():
        outdir = ROOT / outdir
    outdir = outdir.resolve()
    runs_root = (ROOT / "runs").resolve()
    try:
        outdir.relative_to(runs_root)
    except ValueError as exc:
        raise ValueError("--output-dir must be under CassiTheory/runs") from exc
    return outdir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None, help="optional output directory below runs/")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    outdir = output_directory(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=False)
    print(
        f"Device: {device} N={N} dt={DT} t_end={HORIZON * DT:.3f} "
        f"pulse_step={PULSE_STEP}",
        flush=True,
    )

    identity_delta = synchronized_no_op_identity(device)
    print(f"No-op canonical identity max|delta|={identity_delta:.1e}", flush=True)

    audit_solver = build_solver(device)
    audit_context = build_compact_context(audit_solver)
    support = support_audit(audit_context)
    synthetic = synthetic_trace_checks()

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_arm("baseline", device, False, None, 0, outdir)
    runs["source_plus"] = run_arm("source_plus", device, False, "T", +1, outdir)
    runs["source_minus"] = run_arm("source_minus", device, False, "T", -1, outdir)
    runs["direct_diagonal_plus"] = run_arm(
        "direct_diagonal_plus", device, False, "D", +1, outdir
    )
    runs["direct_diagonal_minus"] = run_arm(
        "direct_diagonal_minus", device, False, "D", -1, outdir
    )
    runs["direct_axial_plus"] = run_arm("direct_axial_plus", device, False, "A", +1, outdir)
    runs["direct_axial_minus"] = run_arm("direct_axial_minus", device, False, "A", -1, outdir)
    runs["source_shuffled_plus"] = run_arm(
        "source_shuffled_plus", device, True, "T", +1, outdir
    )
    runs["source_shuffled_minus"] = run_arm(
        "source_shuffled_minus", device, True, "T", -1, outdir
    )
    runs["direct_diagonal_shuffled_plus"] = run_arm(
        "direct_diagonal_shuffled_plus", device, True, "D", +1, outdir
    )
    runs["direct_diagonal_shuffled_minus"] = run_arm(
        "direct_diagonal_shuffled_minus", device, True, "D", -1, outdir
    )
    runs["direct_axial_shuffled_plus"] = run_arm(
        "direct_axial_shuffled_plus", device, True, "A", +1, outdir
    )
    runs["direct_axial_shuffled_minus"] = run_arm(
        "direct_axial_shuffled_minus", device, True, "A", -1, outdir
    )

    pairs = {
        "source": antisymmetric_pair(runs, "source", "source_plus", "source_minus"),
        "direct_diagonal": antisymmetric_pair(
            runs, "direct_diagonal", "direct_diagonal_plus", "direct_diagonal_minus"
        ),
        "direct_axial": antisymmetric_pair(
            runs, "direct_axial", "direct_axial_plus", "direct_axial_minus"
        ),
        "source_shuffled": antisymmetric_pair(
            runs, "source_shuffled", "source_shuffled_plus", "source_shuffled_minus"
        ),
        "direct_diagonal_shuffled": antisymmetric_pair(
            runs,
            "direct_diagonal_shuffled",
            "direct_diagonal_shuffled_plus",
            "direct_diagonal_shuffled_minus",
        ),
        "direct_axial_shuffled": antisymmetric_pair(
            runs,
            "direct_axial_shuffled",
            "direct_axial_shuffled_plus",
            "direct_axial_shuffled_minus",
        ),
    }
    transfers = transfer_metrics(pairs)
    quality = quality_receipt(identity_delta, support, synthetic, runs, transfers)
    verdict = classify(quality, transfers)
    receipt = {
        "protocol": "field-experience/source-only-passive-transfer-pre-registration.md",
        "script": "field-experience/source_only_passive_transfer_probe.py",
        "config": {
            "N": N,
            "dt": DT,
            "horizon_steps": HORIZON,
            "t_end": HORIZON * DT,
            "pulse_step": PULSE_STEP,
            "compact_radius": COMPACT_RADIUS,
            "target_center_T": T_CENTER,
            "diagonal_center_D": D_CENTER,
            "axial_center_A": A_CENTER,
            "kick_l2": KICK_L2,
            "kick_alpha_cap": KICK_ALPHA_CAP,
            "kick_bisect_iters": KICK_BISECT_ITERS,
            "floor": FLOOR,
            "floor_margin": FLOOR_MARGIN,
            "analysis_k": [ANALYSIS_K_MIN, ANALYSIS_K_MAX],
            "match_threshold": MATCH_THRESHOLD,
        },
        "arm_order": list(ARM_ORDER),
        "support": support,
        "quality": quality,
        "transfers": transfers,
        "pairs": pairs,
        "verdict": verdict,
        "run_files": {name: f"run_{name}.json" for name in ARM_ORDER},
    }
    with (outdir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)

    print(
        f"Quality={'PASS' if quality['valid'] else 'INVALID'} "
        f"G_D(source/direct)={transfers['G_D_source']:.6g}/{transfers['G_D_direct']:.6g} "
        f"G_A(source/direct)={transfers['G_A_source']:.6g}/{transfers['G_A_direct']:.6g} "
        f"F1={verdict['features']['F1']} F2={verdict['features']['F2']} "
        f"F3={verdict['features']['F3']} verdict={verdict['verdict']}",
        flush=True,
    )
    print(f"Results: {outdir / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
