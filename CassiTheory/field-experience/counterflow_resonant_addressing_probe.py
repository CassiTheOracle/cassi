#!/usr/bin/env python3
"""Frozen Wave-1 counterflow resonant-addressing probe.

Run from the CassiTheory repository root:
    python field-experience/counterflow_resonant_addressing_probe.py

Protocol: field-experience/counterflow-resonant-addressing-pre-registration.md

The canonical solver is imported unchanged. This script owns the finite
checkerboard seed, shared paired-flow proxy, pulse injection, and read-only
density-plane diagnostics. The diagnostic
J_d = E_Y grad(E_I) - E_I grad(E_Y) = (E_Y^2 + E_I^2) grad(theta_d)
and is stored under historical `j*` receipt keys; it is distinct in units
from the amplitude current J_Psi and does not imply transport without a
constitutive law.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
TWO_FLUID = ROOT / "two-fluid"
sys.path.insert(0, str(TWO_FLUID))

from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI, PHI_INV


# Frozen protocol parameters: see the pre-registration.
N = 48
L = 2.0 * math.pi
DT = 0.001
STEPS = 4000
REPORT_EVERY = 50
LAM = 0.05
DIFFUSION = 2.0e-4
VISCOSITY = 5.0e-4
BUBBLE_SIGMA = 3.0
BUBBLE_AMP = 0.20
AXIAL_PHASE_AMP = 0.50
FLOW_SPEED = 0.12
PULSE_INTERVAL = 20
PULSE_LAG = 10
PULSE_L2 = 1.0
MATCH_THRESHOLD = math.cos(math.pi / 6.0)
PSI_REF = math.pi / 4.0
PSI_WRONG = -math.pi / 4.0
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260818
BLOCK_SIZE = 20
FLOOR = 1.0e-3

# Centers are stated in physical (x, y, z) coordinate order. Tensor order is
# (z, y, x), matching the canonical solver's k_z, k_y, k_x layout.
BUBBLES: dict[str, tuple[float, float, float, float, int]] = {
    "target": (12.0, 12.0, 24.0, +math.pi / 4.0, +1),
    "right_upper": (12.0, 36.0, 24.0, +math.pi / 4.0, +1),
    "diagonal": (24.0, 24.0, 24.0, 0.0, 0),
    "left_lower": (36.0, 12.0, 24.0, -math.pi / 4.0, -1),
    "left_upper": (36.0, 36.0, 24.0, -math.pi / 4.0, -1),
}
TARGET = "target"
DIAGONAL = "diagonal"
RIGHT_SITES = ("target", "right_upper")
LEFT_SITES = ("left_lower", "left_upper")


def build_solver(device: torch.device) -> ExpandingTwoFluid3DGPU:
    """Build a fresh canonical solver with the frozen five-channel setting."""
    solver = ExpandingTwoFluid3DGPU(
        N=N,
        L=L,
        nu=VISCOSITY,
        D=DIFFUSION,
        lam=LAM,
        chi=0.0,
        hubble_mode="conversion",
        cs2=0.0,
        qi_gate=True,
        qi_memory=False,
        phi_inv2=PHI_INV ** 2,
        device=device,
    )
    solver.gate_model = "five"
    return solver


def signed_periodic_delta(coord: torch.Tensor, center: float) -> torch.Tensor:
    """Shortest signed periodic displacement in cells."""
    return (coord - center + N / 2.0) % N - N / 2.0


def gaussian_mask(
    X: torch.Tensor,
    Y: torch.Tensor,
    Z: torch.Tensor,
    center: tuple[float, float, float],
) -> torch.Tensor:
    dx = signed_periodic_delta(X, center[0])
    dy = signed_periodic_delta(Y, center[1])
    dz = signed_periodic_delta(Z, center[2])
    return torch.exp(-(dx * dx + dy * dy + dz * dz) / (2.0 * BUBBLE_SIGMA ** 2))


def normalized(weight: torch.Tensor) -> torch.Tensor:
    return weight / weight.sum().clamp_min(1.0e-30)


def build_context(solver: ExpandingTwoFluid3DGPU) -> dict[str, Any]:
    """Precompute periodic geometry and all read-only local windows."""
    axis = torch.arange(N, dtype=torch.float64, device=solver.device)
    Z, Y, X = torch.meshgrid(axis, axis, axis, indexing="ij")
    masks: dict[str, torch.Tensor] = {}
    for name, (cx, cy, cz, _, _) in BUBBLES.items():
        masks[name] = gaussian_mask(X, Y, Z, (cx, cy, cz))

    target_weight = normalized(masks[TARGET])
    diagonal_weight = normalized(masks[DIAGONAL])
    edge_weight = normalized(masks[TARGET] + masks[DIAGONAL])
    right_weight = normalized(sum((masks[name] for name in RIGHT_SITES)))
    left_weight = normalized(sum((masks[name] for name in LEFT_SITES)))

    # The diffuse reservoir keeps every pulse exactly zero-sum in both rho and
    # epsilon. It excludes the target support smoothly rather than introducing
    # a second local source site.
    outside = (1.0 - masks[TARGET]).clamp_min(0.0)
    reservoir_weight = normalized(outside)
    pulse_shape = target_weight - reservoir_weight

    return {
        "X": X,
        "Y": Y,
        "Z": Z,
        "masks": masks,
        "target_weight": target_weight,
        "diagonal_weight": diagonal_weight,
        "edge_weight": edge_weight,
        "right_weight": right_weight,
        "left_weight": left_weight,
        "pulse_shape": pulse_shape,
    }


def phase_labels(spatial_shuffled: bool) -> dict[str, float]:
    labels = {name: row[3] for name, row in BUBBLES.items()}
    if spatial_shuffled:
        labels["diagonal"], labels["left_lower"] = (
            labels["left_lower"],
            labels["diagonal"],
        )
    return labels


def initialize_arm(
    solver: ExpandingTwoFluid3DGPU,
    context: dict[str, Any],
    flow_sign: int,
    spatial_shuffled: bool,
) -> tuple[list[torch.Tensor], torch.Tensor, torch.Tensor]:
    """Create the frozen finite checkerboard and projected paired-flow proxy.

    The bubble angles are seeded parameters in the real $(\rho,\varepsilon)$
    plane; they do not introduce an independently evolved compact phase.
    """
    X, Y, Z = context["X"], context["Y"], context["Z"]
    rho0 = 1.0 + PHI_INV
    rho = torch.full((N, N, N), rho0, dtype=torch.float64, device=solver.device)
    eps = torch.zeros_like(rho)
    labels = phase_labels(spatial_shuffled)

    for name, (cx, cy, cz, _, side) in BUBBLES.items():
        g = context["masks"][name]
        dz = signed_periodic_delta(Z, cz)
        phase = labels[name] + flow_sign * side * AXIAL_PHASE_AMP * torch.sin(
            2.0 * math.pi * dz / N
        )
        rho = rho + BUBBLE_AMP * g * torch.cos(phase)
        eps = eps + BUBBLE_AMP * g * torch.sin(phase)

    ey = (PHI * rho + eps) / (1.0 + PHI)
    ei = (rho - eps) / (1.0 + PHI)

    ux = torch.zeros_like(rho)
    uy = torch.zeros_like(rho)
    uz = flow_sign * FLOW_SPEED * torch.sin(2.0 * math.pi * X / N)
    u_hat = solver._project([
        torch.fft.fftn(ux),
        torch.fft.fftn(uy),
        torch.fft.fftn(uz),
    ])
    return u_hat, torch.fft.fftn(ey), torch.fft.fftn(ei)


def weighted_mean(field: torch.Tensor, weight: torch.Tensor) -> float:
    return float((field * weight).sum())


def phasor(ey: torch.Tensor, ei: torch.Tensor, weight: torch.Tensor) -> complex:
    rho = ey + ei
    eps = ey - PHI * ei
    value = ((rho - (1.0 + PHI_INV)) * weight).sum() + 1j * (eps * weight).sum()
    return complex(value.item())


def current_vector(
    solver: ExpandingTwoFluid3DGPU,
    ey: torch.Tensor,
    ei: torch.Tensor,
) -> list[torch.Tensor]:
    ey_hat = torch.fft.fftn(ey)
    ei_hat = torch.fft.fftn(ei)
    grad_ey = solver._grad(ey_hat)
    grad_ei = solver._grad(ei_hat)
    return [ey * grad_ei[d] - ei * grad_ey[d] for d in range(3)]


def phase_current_metrics(
    solver: ExpandingTwoFluid3DGPU,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
) -> dict[str, float]:
    r"""Read the density-plane diagnostic $J_d$, shared flow, and coherence.

    The returned `j*` fields are historical receipt labels for projections or
    norms of $J_d$. They are not amplitude-current $J_\Psi$ readouts and carry
    no transport interpretation without a constitutive law.
    """
    Jx, Jy, Jz = current_vector(solver, ey, ei)
    edge_weight = context["edge_weight"]
    target_weight = context["target_weight"]
    diagonal_weight = context["diagonal_weight"]
    j_edge = weighted_mean((Jx + Jy) / math.sqrt(2.0), edge_weight)
    j_rms = float(torch.sqrt(((Jx * Jx + Jy * Jy + Jz * Jz) * edge_weight).sum()))

    s_target = phasor(ey, ei, target_weight)
    s_diagonal = phasor(ey, ei, diagonal_weight)
    phase_target = math.atan2(s_target.imag, s_target.real)
    phase_diagonal = math.atan2(s_diagonal.imag, s_diagonal.real)
    relation = math.atan2(
        math.sin(phase_diagonal - phase_target),
        math.cos(phase_diagonal - phase_target),
    )
    seed_relation = -math.pi / 4.0
    relation_order = math.cos(relation - seed_relation)

    _, q = solver.compute_q_field(ey, ei)
    u_z = torch.fft.ifftn(u_hat[2]).real
    return {
        "j_edge": j_edge,
        "j_rms_edge": j_rms,
        "jz_target": weighted_mean(Jz, target_weight),
        "jz_right": weighted_mean(Jz, context["right_weight"]),
        "jz_left": weighted_mean(Jz, context["left_weight"]),
        "u_z_right": weighted_mean(u_z, context["right_weight"]),
        "u_z_left": weighted_mean(u_z, context["left_weight"]),
        "phase_target": phase_target,
        "phase_diagonal": phase_diagonal,
        "phasor_target_abs": abs(s_target),
        "phasor_diagonal_abs": abs(s_diagonal),
        "phase_relation": relation,
        "relation_order": relation_order,
        "q_target": weighted_mean(q, target_weight),
        "q_diagonal": weighted_mean(q, diagonal_weight),
    }


def field_snapshot(
    solver: ExpandingTwoFluid3DGPU,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
    step: int,
) -> dict[str, float]:
    d = phase_current_metrics(solver, ey, ei, u_hat, context)
    d.update({
        "step": step,
        "t": step * DT,
        "ey_min": float(ey.min()),
        "ei_min": float(ei.min()),
        "floor_ey": int((ey <= FLOOR + 1.0e-12).sum()),
        "floor_ei": int((ei <= FLOOR + 1.0e-12).sum()),
        "mass": float((ey + ei).sum()),
        "eps_total": float((ey - PHI * ei).sum()),
        "H": float(solver.H),
        "a": float(solver.a),
        "finite": bool(torch.isfinite(ey).all() and torch.isfinite(ei).all()),
    })
    return d


def phase_match(ey: torch.Tensor, ei: torch.Tensor, context: dict[str, Any]) -> float:
    s = phasor(ey, ei, context["target_weight"])
    if abs(s) <= 1.0e-14:
        return float("nan")
    return float((s / abs(s) * complex(math.cos(-PSI_REF), math.sin(-PSI_REF))).real)


def build_pulse(context: dict[str, Any], phase: float) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
    """Build one exactly normed, globally balanced real-doublet redistribution pulse."""
    shape = context["pulse_shape"]
    drho = shape * math.cos(phase)
    deps = shape * math.sin(phase)
    dey = (PHI * drho + deps) / (1.0 + PHI)
    dei = (drho - deps) / (1.0 + PHI)
    norm_pre = torch.sqrt((dey * dey + dei * dei).sum())
    scale = PULSE_L2 / norm_pre.clamp_min(1.0e-30)
    dey = dey * scale
    dei = dei * scale
    drho = drho * scale
    deps = deps * scale
    stats = {
        "l2": float(torch.sqrt((dey * dey + dei * dei).sum())),
        "rho_total": float(drho.sum()),
        "eps_total": float(deps.sum()),
        "ey_total": float(dey.sum()),
        "ei_total": float(dei.sum()),
        "peak_ey": float(dey.abs().max()),
        "peak_ei": float(dei.abs().max()),
    }
    return dey, dei, stats


def apply_pulse(
    ey_hat: torch.Tensor,
    ei_hat: torch.Tensor,
    dey: torch.Tensor,
    dei: torch.Tensor,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    ey_new = ey + dey
    ei_new = ei + dei
    return torch.fft.fftn(ey_new), torch.fft.fftn(ei_new), {
        "ey_min_after": float(ey_new.min()),
        "ei_min_after": float(ei_new.min()),
        "finite_after": bool(torch.isfinite(ey_new).all() and torch.isfinite(ei_new).all()),
    }


def no_op_identity(device: torch.device) -> float:
    """Verify that the wrapper's no-pulse path is bit-identical to RK2 alone."""
    direct = build_solver(device)
    wrapped = build_solver(device)
    direct_context = build_context(direct)
    wrapped_context = build_context(wrapped)
    u0, ey0, ei0 = initialize_arm(direct, direct_context, +1, False)
    u1, ey1, ei1 = initialize_arm(wrapped, wrapped_context, +1, False)
    for _ in range(100):
        u0, ey0, ei0 = direct.rk2_step(u0, ey0, ei0, DT)
        # This call is intentionally the wrapper's inactive intervention path.
        u1, ey1, ei1 = wrapped.rk2_step(u1, ey1, ei1, DT)
    values = [torch.max(torch.abs(ey0 - ey1)), torch.max(torch.abs(ei0 - ei1))]
    values.extend(torch.max(torch.abs(a - b)) for a, b in zip(u0, u1))
    return max(float(v) for v in values)


def event_blocks(values: list[float]) -> list[float]:
    return [float(np.mean(values[i:i + BLOCK_SIZE])) for i in range(0, len(values), BLOCK_SIZE)]


def paired_bootstrap(a: list[float], b: list[float]) -> dict[str, float | int | None]:
    n = min(len(a), len(b))
    if n == 0:
        return {"mean": None, "lo": None, "hi": None, "n_blocks": 0}
    delta = np.asarray(a[:n], dtype=np.float64) - np.asarray(b[:n], dtype=np.float64)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    indices = rng.integers(0, n, size=(BOOTSTRAP_SAMPLES, n))
    samples = delta[indices].mean(axis=1)
    return {
        "mean": float(delta.mean()),
        "lo": float(np.quantile(samples, 0.025)),
        "hi": float(np.quantile(samples, 0.975)),
        "n_blocks": n,
    }


def contrast_passes(d: dict[str, float | int | None]) -> bool:
    mean = d["mean"]
    lo = d["lo"]
    return bool(
        mean is not None
        and lo is not None
        and math.isfinite(float(mean))
        and float(mean) >= 0.05
        and float(lo) > 0.0
    )


def run_arm(
    tag: str,
    device: torch.device,
    flow_sign: int,
    spatial_shuffled: bool,
    pulse_mode: str,
    replay_schedule: list[int] | None,
    outdir: Path,
) -> dict[str, Any]:
    """Run one fresh-solver arm and emit its complete machine receipt."""
    solver = build_solver(device)
    context = build_context(solver)
    u_hat, ey_hat, ei_hat = initialize_arm(solver, context, flow_sign, spatial_shuffled)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    initial = field_snapshot(solver, ey0, ei0, u_hat, context, step=0)
    j_scale = initial["j_rms_edge"]

    if j_scale <= 1.0e-14:
        raise RuntimeError(f"{tag}: initial edge-current scale is zero")
    if pulse_mode == "replay" and replay_schedule is None:
        raise ValueError(f"{tag}: replay arm needs the matched schedule")

    pulse_phase = PSI_REF if pulse_mode != "wrong" else PSI_WRONG
    dey, dei, pulse_template = build_pulse(context, pulse_phase)
    schedule = set(replay_schedule or [])
    matched_schedule: list[int] = []
    pending: dict[int, dict[str, float]] = {}
    events: list[dict[str, float | int]] = []
    pulses: list[dict[str, float | int | bool]] = []
    history: list[dict[str, float]] = [initial]
    t0 = time.time()

    for step in range(STEPS):
        if step in pending:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            post = phase_current_metrics(solver, ey, ei, u_hat, context)["j_edge"]
            event = pending.pop(step)
            event["post_j_edge"] = post
            event["response"] = (post - event["pre_j_edge"]) / j_scale
            events.append(event)

        emit = False
        match: float | None = None
        if step > 0 and step % PULSE_INTERVAL == 0:
            if pulse_mode == "matched":
                ey = torch.fft.ifftn(ey_hat).real
                ei = torch.fft.ifftn(ei_hat).real
                match = phase_match(ey, ei, context)
                emit = bool(math.isfinite(match) and match >= MATCH_THRESHOLD)
                if emit:
                    matched_schedule.append(step)
            elif pulse_mode in ("replay", "wrong"):
                emit = step in schedule

        if emit:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            pre = phase_current_metrics(solver, ey, ei, u_hat, context)["j_edge"]
            ey_hat, ei_hat, injection = apply_pulse(ey_hat, ei_hat, dey, dei)
            record: dict[str, float | int | bool | None] = {
                "step": step,
                "t": step * DT,
                "match": match,
                "pre_j_edge": pre,
                **pulse_template,
                **injection,
            }
            pulses.append(record)
            pending[step + PULSE_LAG] = {
                "step": step,
                "t": step * DT,
                "pre_j_edge": pre,
            }

        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)

        if step % REPORT_EVERY == 0 or step == STEPS - 1:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            history.append(field_snapshot(solver, ey, ei, u_hat, context, step=step + 1))

    if pending:
        raise RuntimeError(f"{tag}: {len(pending)} event responses did not fit within horizon")

    responses = [float(e["response"]) for e in events]
    response_mean = float(np.mean(responses)) if responses else None
    summary = {
        "n_pulses": len(pulses),
        "n_responses": len(events),
        "response_mean": response_mean,
        "response_blocks": event_blocks(responses),
        "response_min": float(np.min(responses)) if responses else None,
        "response_max": float(np.max(responses)) if responses else None,
        "initial_j_scale": j_scale,
        "initial": initial,
        "final": history[-1],
        "elapsed_s": time.time() - t0,
    }
    result: dict[str, Any] = {
        "tag": tag,
        "flow_sign": flow_sign,
        "spatial_shuffled": spatial_shuffled,
        "pulse_mode": pulse_mode,
        "matched_schedule": matched_schedule if pulse_mode == "matched" else sorted(schedule),
        "pulse_template": pulse_template,
        "pulses": pulses,
        "events": events,
        "history": history,
        "summary": summary,
    }
    with (outdir / f"run_{tag}.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    response_text = f"{response_mean:+.5f}" if response_mean is not None else "n/a"
    print(
        f"[{tag}] pulses={summary['n_pulses']} response={response_text} "
        f"j0={j_scale:.5f} final_min={summary['final']['ey_min']:.4f}/"
        f"{summary['final']['ei_min']:.4f} {summary['elapsed_s']:.1f}s",
        flush=True,
    )
    return result


def quality_checks(identity_delta: float, runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = runs["baseline"]["summary"]["initial"]
    matched = runs["matched"]
    all_records = [record for run in runs.values() for record in run["history"]]
    all_pulses = [pulse for run in runs.values() for pulse in run["pulses"]]

    floor_hits = any(record["floor_ey"] > 0 or record["floor_ei"] > 0 for record in all_records)
    nonfinite = any(not record["finite"] for record in all_records) or any(
        not pulse["finite_after"] for pulse in all_pulses
    )
    balanced = all(
        abs(float(pulse["rho_total"])) <= 1.0e-12
        and abs(float(pulse["eps_total"])) <= 1.0e-12
        for pulse in all_pulses
    )
    norms = [float(pulse["l2"]) for pulse in all_pulses]
    norm_span = max(norms) - min(norms) if norms else None
    directional_seed = (
        baseline["u_z_right"] > 0.0
        and baseline["u_z_left"] < 0.0
        and baseline["jz_right"] * baseline["jz_left"] < 0.0
    )
    checks = {
        "identity_exact": identity_delta == 0.0,
        "identity_delta": identity_delta,
        "finite": not nonfinite,
        "no_floor_hits": not floor_hits,
        "balanced_pulses": balanced,
        "pulse_norm_span": norm_span,
        "pulse_norm_match": norm_span is not None and norm_span <= 1.0e-12,
        "enough_matched_events": len(matched["matched_schedule"]) >= 30,
        "directional_seed": directional_seed,
        "baseline_u_z_right": baseline["u_z_right"],
        "baseline_u_z_left": baseline["u_z_left"],
        "baseline_jz_right": baseline["jz_right"],
        "baseline_jz_left": baseline["jz_left"],
    }
    checks["valid"] = bool(
        checks["identity_exact"]
        and checks["finite"]
        and checks["no_floor_hits"]
        and checks["balanced_pulses"]
        and checks["pulse_norm_match"]
        and checks["enough_matched_events"]
        and checks["directional_seed"]
    )
    return checks


def classify(quality: dict[str, Any], contrasts: dict[str, dict[str, float | int]], runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not quality["valid"]:
        return {"verdict": "INVALID", "phase": False, "space": False, "counterflow": False}

    phase = contrast_passes(contrasts["phase"])
    space = contrast_passes(contrasts["space"])
    counterflow = contrast_passes(contrasts["counterflow_reversed"]) and contrast_passes(
        contrasts["counterflow_zero"]
    )
    # The density-plane diagnostic must reverse sign between the signed
    # counterflow arms before any flow-dependence statement is permitted.
    positive_jz = runs["matched"]["summary"]["initial"]["jz_right"]
    reversed_jz = runs["counterflow_reversed"]["summary"]["initial"]["jz_right"]
    counterflow = bool(counterflow and positive_jz * reversed_jz < 0.0)

    n_pass = int(phase) + int(space) + int(counterflow)
    if n_pass == 0:
        verdict = "NULL"
    elif n_pass == 3:
        verdict = "PHASE-SELECTIVE CHECKERBOARD COUNTERFLOW SUPPORT"
    else:
        verdict = "PARTIAL"
    return {"verdict": verdict, "phase": phase, "space": space, "counterflow": counterflow}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="optional explicit output directory under the repository runs/ tree",
    )
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}  N={N} dt={DT} t_end={STEPS * DT} pulses=50/time", flush=True)
    identity_delta = no_op_identity(device)
    print(f"No-op canonical identity max|delta|={identity_delta:.1e}", flush=True)

    if args.output_dir is None:
        rid = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = ROOT / "runs" / f"{rid}_counterflow_resonant_addressing"
    else:
        outdir = Path(args.output_dir)
        if not outdir.is_absolute():
            outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=False)

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_arm("baseline", device, +1, False, "none", None, outdir)
    runs["matched"] = run_arm("matched", device, +1, False, "matched", None, outdir)
    schedule = runs["matched"]["matched_schedule"]
    runs["phase_wrong"] = run_arm("phase_wrong", device, +1, False, "wrong", schedule, outdir)
    runs["spatial_shuffled"] = run_arm("spatial_shuffled", device, +1, True, "replay", schedule, outdir)
    runs["counterflow_reversed"] = run_arm("counterflow_reversed", device, -1, False, "replay", schedule, outdir)
    runs["counterflow_zero"] = run_arm("counterflow_zero", device, 0, False, "replay", schedule, outdir)

    quality = quality_checks(identity_delta, runs)
    blocks = {name: run["summary"]["response_blocks"] for name, run in runs.items()}
    contrasts = {
        "phase": paired_bootstrap(blocks["matched"], blocks["phase_wrong"]),
        "space": paired_bootstrap(blocks["matched"], blocks["spatial_shuffled"]),
        "counterflow_reversed": paired_bootstrap(blocks["matched"], blocks["counterflow_reversed"]),
        "counterflow_zero": paired_bootstrap(blocks["matched"], blocks["counterflow_zero"]),
    }
    verdict = classify(quality, contrasts, runs)
    output = {
        "protocol": "field-experience/counterflow-resonant-addressing-pre-registration.md",
        "script": "field-experience/counterflow_resonant_addressing_probe.py",
        "config": {
            "N": N,
            "L": L,
            "dt": DT,
            "steps": STEPS,
            "t_end": STEPS * DT,
            "lambda": LAM,
            "D": DIFFUSION,
            "nu": VISCOSITY,
            "flow_speed": FLOW_SPEED,
            "pulse_interval": PULSE_INTERVAL,
            "pulse_lag": PULSE_LAG,
            "pulse_l2": PULSE_L2,
            "match_threshold": MATCH_THRESHOLD,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
        },
        "quality": quality,
        "contrasts": contrasts,
        "verdict": verdict,
        "summaries": {name: run["summary"] for name, run in runs.items()},
        "run_files": {name: f"run_{name}.json" for name in runs},
    }
    with (outdir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(output, handle, indent=2, allow_nan=False)

    print(json.dumps({"quality": quality, "contrasts": contrasts, "verdict": verdict}, indent=2), flush=True)
    print(f"Results: {outdir}", flush=True)


if __name__ == "__main__":
    main()
