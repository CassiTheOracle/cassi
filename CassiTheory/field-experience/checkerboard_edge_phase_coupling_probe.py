#!/usr/bin/env python3
"""Frozen Wave-4 directed checkerboard-edge phase-coupling probe.

Run from the CassiTheory repository root:
    python field-experience/checkerboard_edge_phase_coupling_probe.py

Protocol: field-experience/checkerboard-edge-phase-coupling-pre-registration.md
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
    BUBBLE_SIGMA,
    BUBBLES,
    DT,
    FLOOR,
    MATCH_THRESHOLD,
    N,
    PULSE_INTERVAL,
    PULSE_LAG,
    REPORT_EVERY,
    ROOT,
    STEPS,
    TARGET,
    DIAGONAL,
    build_context,
    build_solver,
    current_vector,
    initialize_arm,
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
    local_phase_match,
    no_op_identity,
)
from counterflow_carrier_demodulation_probe import (
    BLOCK_SIZE,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SEED,
    MATCHED_CARRIER,
    QUADRATURE_CARRIER,
    carrier_coherence,
    metric_sanity,
    paired_bootstrap,
)

T_COORD = BUBBLES[TARGET][:3]
D_COORD = BUBBLES[DIAGONAL][:3]
V_COORD = (12.0, 24.0, 24.0)
SADDLE_COORD = (18.0, 18.0, 24.0)
AXIAL_SADDLE_COORD = (12.0, 18.0, 24.0)
DELTA_LABEL = BUBBLES[DIAGONAL][3] - BUBBLES[TARGET][3]  # -pi/4
TUBE_SIGMA = BUBBLE_SIGMA
ROUTE_MARGIN = 0.50


class ProtocolInvalid(RuntimeError):
    """Signal that a frozen Wave-4 execution gate has failed."""


def signed_periodic_delta(coord: torch.Tensor, center: float) -> torch.Tensor:
    return (coord - center + N / 2.0) % N - N / 2.0


def center_mask(context: dict[str, Any], center: tuple[float, float, float]) -> torch.Tensor:
    X, Y, Z = context["X"], context["Y"], context["Z"]
    dx = signed_periodic_delta(X, center[0])
    dy = signed_periodic_delta(Y, center[1])
    dz = signed_periodic_delta(Z, center[2])
    return torch.exp(-(dx * dx + dy * dy + dz * dz) / (2.0 * TUBE_SIGMA ** 2))


def normalized(mask: torch.Tensor) -> torch.Tensor:
    return mask / mask.sum().clamp_min(1.0e-30)


def route_spec(route: str) -> tuple[tuple[float, float, float], tuple[float, float, float], float, int]:
    if route == "diagonal":
        length = 12.0 * math.sqrt(2.0)
        return D_COORD, (1.0 / math.sqrt(2.0), 1.0 / math.sqrt(2.0), 0.0), length, 34
    if route == "axial":
        return V_COORD, (0.0, 1.0, 0.0), 12.0, 24
    raise ValueError(f"unknown route {route}")


def tube_profile(context: dict[str, Any], route: str, directed: bool) -> dict[str, Any]:
    """Build one finite-proxy corridor and its directed or flat phase profile."""
    endpoint, direction, length, count = route_spec(route)
    X, Y, Z = context["X"], context["Y"], context["Z"]
    complement = torch.ones_like(X)
    for q in range(count + 1):
        f = q / count
        center = tuple(T_COORD[d] + f * (endpoint[d] - T_COORD[d]) for d in range(3))
        g = center_mask(context, center)
        complement = complement * (1.0 - g)
    tube = (1.0 - complement).clamp(0.0, 1.0)

    dT = [
        signed_periodic_delta(X, T_COORD[0]),
        signed_periodic_delta(Y, T_COORD[1]),
        signed_periodic_delta(Z, T_COORD[2]),
    ]
    longitudinal = (dT[0] * direction[0] + dT[1] * direction[1] + dT[2] * direction[2])
    h = (longitudinal / length).clamp(0.0, 1.0)
    if directed:
        ramp = torch.sin(DELTA_LABEL * (h - 0.5)) / math.sin(DELTA_LABEL / 2.0)
        profile = tube * ramp
    else:
        profile = tube

    endpoint_weight = normalized(center_mask(context, endpoint))
    tube_weight = normalized(tube)
    return {
        "route": route,
        "directed": directed,
        "endpoint": endpoint,
        "direction": direction,
        "length": length,
        "tube": tube,
        "profile": profile,
        "tube_weight": tube_weight,
        "endpoint_weight": endpoint_weight,
        "target_support": weighted_mean(tube, context["target_weight"]),
        "endpoint_support": weighted_mean(tube, endpoint_weight),
        "max_abs_profile": float(profile.abs().max()),
    }


def route_metrics(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
    route: dict[str, Any],
    static_masks: dict[str, torch.Tensor],
) -> dict[str, float]:
    Jx, Jy, Jz = amplitude_current(solver, ey, ei)
    Dx, Dy, Dz = current_vector(solver, ey, ei)
    direction = route["direction"]
    projected = Jx * direction[0] + Jy * direction[1] + Jz * direction[2]
    density_projected = Dx * direction[0] + Dy * direction[1] + Dz * direction[2]
    diagonal_projection = (Jx + Jy) / math.sqrt(2.0)
    diagonal_weight = context["diagonal_weight"]
    target_weight = context["target_weight"]

    z_target = amplitude_phasor(ey, ei, target_weight)
    z_diagonal = amplitude_phasor(ey, ei, diagonal_weight)
    theta_target = math.atan2(z_target.imag, z_target.real)
    theta_diagonal = math.atan2(z_diagonal.imag, z_diagonal.real)
    delta_theta = math.atan2(
        math.sin(theta_diagonal - theta_target),
        math.cos(theta_diagonal - theta_target),
    )
    _, q = solver.compute_q_field(ey, ei)
    u_z = torch.fft.ifftn(u_hat[2]).real
    j_sq = Jx * Jx + Jy * Jy + Jz * Jz

    return {
        "j_receiver": weighted_mean(diagonal_projection, diagonal_weight),
        "j_receiver_rms": float(torch.sqrt((j_sq * diagonal_weight).sum())),
        "jd_receiver": weighted_mean((Dx + Dy) / math.sqrt(2.0), diagonal_weight),
        "j_route": weighted_mean(projected, route["tube_weight"]),
        "jd_route": weighted_mean(density_projected, route["tube_weight"]),
        "jpsi_z_right": weighted_mean(Jz, context["right_weight"]),
        "jpsi_z_left": weighted_mean(Jz, context["left_weight"]),
        "u_z_right": weighted_mean(u_z, context["right_weight"]),
        "u_z_left": weighted_mean(u_z, context["left_weight"]),
        "phase_target": theta_target,
        "phase_diagonal": theta_diagonal,
        "phase_delta_diagonal_target": delta_theta,
        "phasor_target_abs": abs(z_target),
        "phasor_diagonal_abs": abs(z_diagonal),
        "q_target": weighted_mean(q, target_weight),
        "q_diagonal": weighted_mean(q, diagonal_weight),
        "q_saddle": weighted_mean(q, static_masks["saddle_weight"]),
        "q_axial_void": weighted_mean(q, static_masks["void_weight"]),
    }


def snapshot(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
    route: dict[str, Any],
    static_masks: dict[str, torch.Tensor],
    step: int,
) -> dict[str, float | int | bool]:
    d: dict[str, float | int | bool] = route_metrics(solver, ey, ei, u_hat, context, route, static_masks)
    d.update({
        "step": step,
        "t": step * DT,
        "ey_min": float(ey.min()),
        "ei_min": float(ei.min()),
        "floor_ey": int((ey <= FLOOR + 1.0e-12).sum()),
        "floor_ei": int((ei <= FLOOR + 1.0e-12).sum()),
        "mass": float((ey + ei).sum()),
        "finite": bool(torch.isfinite(ey).all() and torch.isfinite(ei).all()),
    })
    return d


def kick_norm_squared(rho: torch.Tensor, profile: torch.Tensor, beta: float) -> torch.Tensor:
    return 4.0 * (rho * torch.sin(beta * profile / 2.0) ** 2).sum()


def edge_kick(
    ey_hat: torch.Tensor,
    ei_hat: torch.Tensor,
    profile: torch.Tensor,
    carrier_sign: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float | bool]]:
    """Apply one norm-matched, positivity-bounded directed edge phase kick."""
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    A, B = amplitude_fields(ey, ei)
    rho = ey + ei

    max_norm = float(torch.sqrt(kick_norm_squared(rho, profile, KICK_ALPHA_CAP)))
    if max_norm + NORM_TOL < KICK_L2:
        raise ProtocolInvalid(f"route capacity {max_norm:.12g} is below frozen kick target")
    lo, hi = 0.0, KICK_ALPHA_CAP
    for _ in range(KICK_BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        if float(torch.sqrt(kick_norm_squared(rho, profile, mid))) < KICK_L2:
            lo = mid
        else:
            hi = mid
    beta = 0.5 * (lo + hi)
    alpha = carrier_sign * beta * profile

    theta = torch.atan2(B, A)
    floor_angle = torch.asin(torch.sqrt((FLOOR + FLOOR_MARGIN) / rho))
    theta_after = theta + alpha
    safety = bool(
        torch.all(theta_after >= floor_angle)
        and torch.all(theta_after <= math.pi / 2.0 - floor_angle)
    )
    if not safety:
        raise ProtocolInvalid("edge kick violates the frozen positivity wedge")

    Ap = torch.cos(alpha) * A - torch.sin(alpha) * B
    Bp = torch.sin(alpha) * A + torch.cos(alpha) * B
    ey_post = Ap * Ap
    ei_post = Bp * Bp
    rho_error = float(torch.max(torch.abs((ey_post + ei_post) - rho)))
    mass_rel_error = float(torch.abs((ey_post + ei_post).sum() - rho.sum()) / rho.sum())
    actual_norm = float(torch.sqrt(((Ap - A) ** 2 + (Bp - B) ** 2).sum()))
    margin = torch.minimum(theta_after - floor_angle, math.pi / 2.0 - floor_angle - theta_after)

    return torch.fft.fftn(ey_post), torch.fft.fftn(ei_post), {
        "kick_l2": actual_norm,
        "beta": beta,
        "alpha_abs_max": float(alpha.abs().max()),
        "rho_error_max": rho_error,
        "mass_rel_error": mass_rel_error,
        "safety": safety,
        "angle_margin_min": float(margin.min()),
        "ey_min_after": float(ey_post.min()),
        "ei_min_after": float(ei_post.min()),
        "finite_after": bool(torch.isfinite(ey_post).all() and torch.isfinite(ei_post).all()),
        "route_energy": float((rho * profile * profile).sum()),
    }


def event_blocks(values: list[float]) -> list[float]:
    return [float(np.mean(values[start:start + BLOCK_SIZE])) for start in range(0, len(values), BLOCK_SIZE)]


def block_coherences(events: list[dict[str, Any]]) -> list[float]:
    result: list[float] = []
    for start in range(0, len(events), BLOCK_SIZE):
        block = events[start:start + BLOCK_SIZE]
        response = np.asarray([float(event["response"]) for event in block], dtype=np.float64)
        carrier = np.asarray(
            [MATCHED_CARRIER[int(event["event_index"]) % len(MATCHED_CARRIER)] for event in block],
            dtype=np.float64,
        )
        result.append(carrier_coherence(response, carrier))
    return result


def run_arm(
    tag: str,
    device: torch.device,
    flow_sign: int,
    route_name: str,
    directed: bool,
    carrier: tuple[int, int, int, int] | None,
    replay_schedule: list[int] | None,
    outdir: Path,
) -> dict[str, Any]:
    solver = build_solver(device)
    context = build_context(solver)
    route = tube_profile(context, route_name, directed)
    static_masks = {
        "saddle_weight": normalized(center_mask(context, SADDLE_COORD)),
        "void_weight": normalized(center_mask(context, V_COORD)),
    }
    u_hat, ey_hat, ei_hat = initialize_arm(solver, context, flow_sign, False)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    initial = snapshot(solver, ey0, ei0, u_hat, context, route, static_masks, 0)
    j_scale = float(initial["j_receiver_rms"])
    if j_scale <= 1.0e-14:
        raise ProtocolInvalid(f"{tag}: receiver current scale is zero")
    z_ref = amplitude_phasor(ey0, ei0, context["target_weight"])
    theta_ref = math.atan2(z_ref.imag, z_ref.real)

    schedule = set(replay_schedule or [])
    event_index = {step: index for index, step in enumerate(replay_schedule or [])}
    matched_schedule: list[int] = []
    events: list[dict[str, float | int]] = []
    kicks: list[dict[str, float | int | bool | None]] = []
    pending: dict[int, dict[str, float | int]] = {}
    history: list[dict[str, float | int | bool]] = [initial]
    min_ey = float(initial["ey_min"])
    min_ei = float(initial["ei_min"])
    floor_seen = bool(initial["floor_ey"] or initial["floor_ei"])
    finite_seen = bool(initial["finite"])
    started = time.time()

    for step in range(STEPS):
        if step in pending:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            post = route_metrics(solver, ey, ei, u_hat, context, route, static_masks)["j_receiver"]
            event = pending.pop(step)
            event["post_j_receiver"] = post
            event["response"] = (post - float(event["pre_j_receiver"])) / j_scale
            events.append(event)

        kick_index: int | None = None
        match: float | None = None
        if step > 0 and step % PULSE_INTERVAL == 0:
            if tag == "diagonal_matched":
                ey = torch.fft.ifftn(ey_hat).real
                ei = torch.fft.ifftn(ei_hat).real
                match = local_phase_match(ey, ei, context, theta_ref)
                if math.isfinite(match) and match >= MATCH_THRESHOLD:
                    matched_schedule.append(step)
                    kick_index = len(matched_schedule) - 1
            elif carrier is not None and step in schedule:
                kick_index = event_index[step]

        if kick_index is not None:
            if carrier is None:
                raise ProtocolInvalid(f"{tag}: active event lacks a carrier")
            sign = carrier[kick_index % len(carrier)]
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            pre = route_metrics(solver, ey, ei, u_hat, context, route, static_masks)["j_receiver"]
            ey_hat, ei_hat, receipt = edge_kick(ey_hat, ei_hat, route["profile"], sign)
            kicks.append({
                "step": step,
                "t": step * DT,
                "event_index": kick_index,
                "carrier_sign": sign,
                "match": match,
                "pre_j_receiver": pre,
                **receipt,
            })
            pending[step + PULSE_LAG] = {
                "step": step,
                "t": step * DT,
                "event_index": kick_index,
                "pre_j_receiver": pre,
            }

        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        min_ey = min(min_ey, float(ey.min()))
        min_ei = min(min_ei, float(ei.min()))
        floor_seen = floor_seen or bool((ey <= FLOOR + 1.0e-12).any()) or bool((ei <= FLOOR + 1.0e-12).any())
        finite_seen = finite_seen and bool(torch.isfinite(ey).all() and torch.isfinite(ei).all())
        if step % REPORT_EVERY == 0 or step == STEPS - 1:
            history.append(snapshot(solver, ey, ei, u_hat, context, route, static_masks, step + 1))

    if pending:
        raise ProtocolInvalid(f"{tag}: response lag exceeds the frozen horizon")
    responses = [float(event["response"]) for event in events]
    response_mean = float(np.mean(responses)) if responses else None
    summary = {
        "n_kicks": len(kicks),
        "n_responses": len(events),
        "response_mean": response_mean,
        "response_blocks": event_blocks(responses),
        "coherence_blocks": block_coherences(events),
        "initial_j_receiver_scale": j_scale,
        "theta_ref": theta_ref,
        "initial": initial,
        "final": history[-1],
        "min_ey_observed": min_ey,
        "min_ei_observed": min_ei,
        "floor_seen": floor_seen,
        "finite_seen": finite_seen,
        "route": {
            "name": route_name,
            "directed": directed,
            "length": route["length"],
            "target_support": route["target_support"],
            "endpoint_support": route["endpoint_support"],
            "max_abs_profile": route["max_abs_profile"],
        },
        "elapsed_s": time.time() - started,
    }
    result: dict[str, Any] = {
        "tag": tag,
        "flow_sign": flow_sign,
        "route": route_name,
        "directed": directed,
        "carrier": carrier,
        "matched_schedule": matched_schedule if tag == "diagonal_matched" else sorted(schedule),
        "kicks": kicks,
        "events": events,
        "history": history,
        "summary": summary,
    }
    with (outdir / f"run_{tag}.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    text = f"{response_mean:+.5f}" if response_mean is not None else "n/a"
    print(
        f"[{tag}] kicks={len(kicks)} receiver={text} "
        f"min={min_ey:.4f}/{min_ei:.4f} {summary['elapsed_s']:.1f}s",
        flush=True,
    )
    return result


def quality_checks(identity: float, runs: dict[str, dict[str, Any]], sanity: dict[str, Any]) -> dict[str, Any]:
    baseline = runs["baseline"]["summary"]["initial"]
    all_kicks = [kick for run in runs.values() for kick in run["kicks"]]
    matched_n = len(runs["diagonal_matched"]["matched_schedule"])
    controls = ("diagonal_quadrature", "axial_matched", "diagonal_flat", "diagonal_reversed_flow", "diagonal_zero_flow")
    replay = all(len(runs[name]["kicks"]) == matched_n for name in controls)
    norm_error = max((abs(float(k["kick_l2"]) - KICK_L2) for k in all_kicks), default=float("inf"))
    rho_error = max((float(k["rho_error_max"]) for k in all_kicks), default=float("inf"))
    mass_error = max((float(k["mass_rel_error"]) for k in all_kicks), default=float("inf"))
    angle_margin = min((float(k["angle_margin_min"]) for k in all_kicks), default=-float("inf"))
    capacity = all(float(k["beta"]) <= KICK_ALPHA_CAP for k in all_kicks)
    route_ok = all(
        run["summary"]["route"]["max_abs_profile"] <= 1.0 + 1.0e-12
        and run["summary"]["route"]["target_support"] >= ROUTE_MARGIN
        and run["summary"]["route"]["endpoint_support"] >= ROUTE_MARGIN
        for run in runs.values()
    )
    checks = {
        "metric_sanity": sanity,
        "identity_exact": identity == 0.0,
        "identity_delta": identity,
        "finite": all(bool(run["summary"]["finite_seen"]) for run in runs.values()) and all(bool(k["finite_after"]) for k in all_kicks),
        "no_floor_hits": all(not bool(run["summary"]["floor_seen"]) for run in runs.values()),
        "replay_counts": replay,
        "enough_matched_events": matched_n >= 30,
        "kick_norm_error_max": norm_error,
        "kick_norm_match": norm_error <= NORM_TOL,
        "rho_error_max": rho_error,
        "rho_invariant": rho_error <= RHO_TOL,
        "mass_rel_error_max": mass_error,
        "mass_invariant": mass_error <= RHO_TOL,
        "minimum_angle_margin": angle_margin,
        "safety_wedge": angle_margin >= 0.0 and all(bool(k["safety"]) for k in all_kicks),
        "capacity": capacity,
        "route_geometry": route_ok,
        "directional_seed": bool(
            baseline["u_z_right"] > 0.0
            and baseline["u_z_left"] < 0.0
            and baseline["jpsi_z_right"] * baseline["jpsi_z_left"] < 0.0
        ),
        "baseline_u_z_right": baseline["u_z_right"],
        "baseline_u_z_left": baseline["u_z_left"],
        "baseline_jpsi_z_right": baseline["jpsi_z_right"],
        "baseline_jpsi_z_left": baseline["jpsi_z_left"],
    }
    checks["valid"] = bool(
        checks["metric_sanity"]["passes"]
        and checks["identity_exact"]
        and checks["finite"]
        and checks["no_floor_hits"]
        and checks["replay_counts"]
        and checks["enough_matched_events"]
        and checks["kick_norm_match"]
        and checks["rho_invariant"]
        and checks["mass_invariant"]
        and checks["safety_wedge"]
        and checks["capacity"]
        and checks["route_geometry"]
        and checks["directional_seed"]
    )
    return checks


def feature_pass(contrast: dict[str, float | int | None]) -> bool:
    mean = contrast["mean"]
    lo = contrast["lo"]
    return bool(mean is not None and lo is not None and float(mean) >= 0.10 and float(lo) > 0.0)


def classify(quality: dict[str, Any], contrasts: dict[str, dict[str, float | int | None]]) -> dict[str, Any]:
    if not quality["valid"]:
        return {"verdict": "INVALID", "features": {"F1": "DOES NOT EMERGE", "F2": "DOES NOT EMERGE", "F3": "DOES NOT EMERGE"}}
    f1 = feature_pass(contrasts["carrier"])
    f2 = feature_pass(contrasts["axial"])
    f3 = feature_pass(contrasts["flat"])
    count = int(f1) + int(f2) + int(f3)
    if count == 3:
        verdict = "SUPPORTS"
    elif f1 and count == 2:
        verdict = "HOLD"
    elif count == 0:
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
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None, help="optional output directory below runs/")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    sanity = metric_sanity()
    print(f"Device: {device} N={N} t_end={STEPS * DT} metric_sanity={sanity}", flush=True)
    identity = no_op_identity(device)
    print(f"No-op canonical identity max|delta|={identity:.1e}", flush=True)

    if args.output_dir is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = ROOT / "runs" / f"{run_id}_checkerboard_edge_phase_coupling"
    else:
        outdir = Path(args.output_dir)
        if not outdir.is_absolute():
            outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=False)

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_arm("baseline", device, +1, "diagonal", True, None, None, outdir)
    runs["diagonal_matched"] = run_arm(
        "diagonal_matched", device, +1, "diagonal", True, MATCHED_CARRIER, None, outdir
    )
    schedule = runs["diagonal_matched"]["matched_schedule"]
    runs["diagonal_quadrature"] = run_arm(
        "diagonal_quadrature", device, +1, "diagonal", True, QUADRATURE_CARRIER, schedule, outdir
    )
    runs["axial_matched"] = run_arm(
        "axial_matched", device, +1, "axial", True, MATCHED_CARRIER, schedule, outdir
    )
    runs["diagonal_flat"] = run_arm(
        "diagonal_flat", device, +1, "diagonal", False, MATCHED_CARRIER, schedule, outdir
    )
    runs["diagonal_reversed_flow"] = run_arm(
        "diagonal_reversed_flow", device, -1, "diagonal", True, MATCHED_CARRIER, schedule, outdir
    )
    runs["diagonal_zero_flow"] = run_arm(
        "diagonal_zero_flow", device, 0, "diagonal", True, MATCHED_CARRIER, schedule, outdir
    )

    quality = quality_checks(identity, runs, sanity)
    blocks = {name: run["summary"]["coherence_blocks"] for name, run in runs.items() if name != "baseline"}
    contrasts = {
        "carrier": paired_bootstrap(blocks["diagonal_matched"], blocks["diagonal_quadrature"]),
        "axial": paired_bootstrap(blocks["diagonal_matched"], blocks["axial_matched"]),
        "flat": paired_bootstrap(blocks["diagonal_matched"], blocks["diagonal_flat"]),
        "reversed_flow": paired_bootstrap(blocks["diagonal_matched"], blocks["diagonal_reversed_flow"]),
        "zero_flow": paired_bootstrap(blocks["diagonal_matched"], blocks["diagonal_zero_flow"]),
    }
    verdict = classify(quality, contrasts)
    receipt = {
        "protocol": "field-experience/checkerboard-edge-phase-coupling-pre-registration.md",
        "script": "field-experience/checkerboard_edge_phase_coupling_probe.py",
        "config": {
            "N": N,
            "dt": DT,
            "steps": STEPS,
            "t_end": STEPS * DT,
            "kick_l2": KICK_L2,
            "kick_alpha_cap": KICK_ALPHA_CAP,
            "tube_sigma": TUBE_SIGMA,
            "diagonal_samples": 34,
            "axial_samples": 24,
            "block_size": BLOCK_SIZE,
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": BOOTSTRAP_SEED,
        },
        "quality": quality,
        "contrasts": contrasts,
        "verdict": verdict,
        "summaries": {name: run["summary"] for name, run in runs.items()},
        "run_files": {name: f"run_{name}.json" for name in runs},
    }
    with (outdir / "results.json").open("w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, allow_nan=False)
    print(json.dumps({"quality": quality, "contrasts": contrasts, "verdict": verdict}, indent=2), flush=True)
    print(f"Results: {outdir}", flush=True)


if __name__ == "__main__":
    main()
