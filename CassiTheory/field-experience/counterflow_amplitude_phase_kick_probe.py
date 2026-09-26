#!/usr/bin/env python3
"""Frozen Wave-2 amplitude-phase synchronization probe.

Run from the CassiTheory repository root:
    python field-experience/counterflow_amplitude_phase_kick_probe.py

Protocol: field-experience/counterflow-amplitude-phase-kick-pre-registration.md
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
    BLOCK_SIZE,
    BOOTSTRAP_SAMPLES,
    BOOTSTRAP_SEED,
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
    build_context,
    build_solver,
    current_vector,
    initialize_arm,
    paired_bootstrap,
    weighted_mean,
)

KICK_L2 = 0.45
KICK_ALPHA_CAP = 0.05
KICK_BISECT_ITERS = 48
FLOOR_MARGIN = 1.0e-5
RHO_TOL = 1.0e-12
NORM_TOL = 1.0e-12

MATCHED_CARRIER = (+1, +1, -1, -1)
QUADRATURE_CARRIER = (+1, -1, -1, +1)


class ProtocolInvalid(RuntimeError):
    """Raised when a frozen Wave-2 quality condition fails during execution."""


def amplitude_fields(ey: torch.Tensor, ei: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    return torch.sqrt(ey), torch.sqrt(ei)


def amplitude_phasor(ey: torch.Tensor, ei: torch.Tensor, weight: torch.Tensor) -> complex:
    A, B = amplitude_fields(ey, ei)
    value = (A * weight).sum() + 1j * (B * weight).sum()
    return complex(value.item())


def amplitude_current(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
) -> list[torch.Tensor]:
    A, B = amplitude_fields(ey, ei)
    grad_A = solver._grad(torch.fft.fftn(A))
    grad_B = solver._grad(torch.fft.fftn(B))
    return [A * grad_B[d] - B * grad_A[d] for d in range(3)]


def amplitude_metrics(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
) -> dict[str, float]:
    Jx, Jy, Jz = amplitude_current(solver, ey, ei)
    D_x, D_y, D_z = current_vector(solver, ey, ei)
    target_weight = context["target_weight"]
    diagonal_weight = context["diagonal_weight"]
    edge_weight = context["edge_weight"]

    s_target = amplitude_phasor(ey, ei, target_weight)
    s_diagonal = amplitude_phasor(ey, ei, diagonal_weight)
    phase_target = math.atan2(s_target.imag, s_target.real)
    phase_diagonal = math.atan2(s_diagonal.imag, s_diagonal.real)
    phase_relation = math.atan2(
        math.sin(phase_diagonal - phase_target),
        math.cos(phase_diagonal - phase_target),
    )

    _, q = solver.compute_q_field(ey, ei)
    u_z = torch.fft.ifftn(u_hat[2]).real
    amp_squared = Jx * Jx + Jy * Jy + Jz * Jz
    return {
        "jpsi_edge": weighted_mean((Jx + Jy) / math.sqrt(2.0), edge_weight),
        "jpsi_rms_edge": float(torch.sqrt((amp_squared * edge_weight).sum())),
        "jd_edge": weighted_mean((D_x + D_y) / math.sqrt(2.0), edge_weight),
        "jpsi_z_target": weighted_mean(Jz, target_weight),
        "jpsi_z_right": weighted_mean(Jz, context["right_weight"]),
        "jpsi_z_left": weighted_mean(Jz, context["left_weight"]),
        "u_z_right": weighted_mean(u_z, context["right_weight"]),
        "u_z_left": weighted_mean(u_z, context["left_weight"]),
        "phase_target": phase_target,
        "phase_diagonal": phase_diagonal,
        "phase_relation": phase_relation,
        "phasor_target_abs": abs(s_target),
        "phasor_diagonal_abs": abs(s_diagonal),
        "q_target": weighted_mean(q, target_weight),
        "q_diagonal": weighted_mean(q, diagonal_weight),
    }


def snapshot(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    u_hat: list[torch.Tensor],
    context: dict[str, Any],
    step: int,
) -> dict[str, float | int | bool]:
    d: dict[str, float | int | bool] = amplitude_metrics(solver, ey, ei, u_hat, context)
    d.update({
        "step": step,
        "t": step * DT,
        "ey_min": float(ey.min()),
        "ei_min": float(ei.min()),
        "floor_ey": int((ey <= FLOOR + 1.0e-12).sum()),
        "floor_ei": int((ei <= FLOOR + 1.0e-12).sum()),
        "mass": float((ey + ei).sum()),
        "eps_total": float((ey - ((1.0 + math.sqrt(5.0)) / 2.0) * ei).sum()),
        "H": float(solver.H),
        "a": float(solver.a),
        "finite": bool(torch.isfinite(ey).all() and torch.isfinite(ei).all()),
    })
    return d


def local_phase_match(
    ey: torch.Tensor,
    ei: torch.Tensor,
    context: dict[str, Any],
    theta_ref: float,
) -> float:
    z = amplitude_phasor(ey, ei, context["target_weight"])
    if abs(z) <= 1.0e-14:
        return float("nan")
    return float((z / abs(z) * complex(math.cos(-theta_ref), math.sin(-theta_ref))).real)


def kick_norm(A: torch.Tensor, B: torch.Tensor, mask: torch.Tensor, beta: float) -> torch.Tensor:
    alpha = beta * mask
    Ap = torch.cos(alpha) * A - torch.sin(alpha) * B
    Bp = torch.sin(alpha) * A + torch.cos(alpha) * B
    return torch.sqrt(((Ap - A) ** 2 + (Bp - B) ** 2).sum())


def amplitude_kick(
    ey_hat: torch.Tensor,
    ei_hat: torch.Tensor,
    context: dict[str, Any],
    carrier_sign: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float | bool]]:
    """Apply one fixed-norm local SO(2) amplitude rotation before one RK2 step."""
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    A, B = amplitude_fields(ey, ei)
    mask = context["masks"][TARGET]

    max_norm = float(kick_norm(A, B, mask, KICK_ALPHA_CAP))
    if max_norm + NORM_TOL < KICK_L2:
        raise ProtocolInvalid(
            f"kick capacity {max_norm:.12g} is below frozen target {KICK_L2:.12g}"
        )

    lo, hi = 0.0, KICK_ALPHA_CAP
    for _ in range(KICK_BISECT_ITERS):
        mid = 0.5 * (lo + hi)
        if float(kick_norm(A, B, mask, mid)) < KICK_L2:
            lo = mid
        else:
            hi = mid
    beta = 0.5 * (lo + hi)
    alpha = carrier_sign * beta * mask

    rho = ey + ei
    theta = torch.atan2(B, A)
    floor_angle = torch.asin(torch.sqrt((FLOOR + FLOOR_MARGIN) / rho))
    theta_after = theta + alpha
    safety = bool(
        torch.all(theta_after >= floor_angle)
        and torch.all(theta_after <= math.pi / 2.0 - floor_angle)
    )
    if not safety:
        raise ProtocolInvalid("fixed amplitude rotation violates the pre-registered positivity wedge")

    Ap = torch.cos(alpha) * A - torch.sin(alpha) * B
    Bp = torch.sin(alpha) * A + torch.cos(alpha) * B
    ey_post = Ap * Ap
    ei_post = Bp * Bp
    rho_error = float(torch.max(torch.abs((ey_post + ei_post) - rho)))
    mass_rel_error = float(torch.abs((ey_post + ei_post).sum() - rho.sum()) / rho.sum())
    actual_norm = float(torch.sqrt(((Ap - A) ** 2 + (Bp - B) ** 2).sum()))
    angle_margin = torch.minimum(theta_after - floor_angle, math.pi / 2.0 - floor_angle - theta_after)

    return torch.fft.fftn(ey_post), torch.fft.fftn(ei_post), {
        "kick_l2": actual_norm,
        "beta": beta,
        "alpha_abs_max": float(alpha.abs().max()),
        "rho_error_max": rho_error,
        "mass_rel_error": mass_rel_error,
        "safety": safety,
        "angle_margin_min": float(angle_margin.min()),
        "ey_min_after": float(ey_post.min()),
        "ei_min_after": float(ei_post.min()),
        "finite_after": bool(torch.isfinite(ey_post).all() and torch.isfinite(ei_post).all()),
    }


def no_op_identity(device: torch.device) -> float:
    """Compare an inactive wrapper loop with direct canonical RK2."""
    direct = build_solver(device)
    wrapped = build_solver(device)
    direct_context = build_context(direct)
    wrapped_context = build_context(wrapped)
    u0, ey0, ei0 = initialize_arm(direct, direct_context, +1, False)
    u1, ey1, ei1 = initialize_arm(wrapped, wrapped_context, +1, False)
    for _ in range(100):
        u0, ey0, ei0 = direct.rk2_step(u0, ey0, ei0, DT)
        u1, ey1, ei1 = wrapped.rk2_step(u1, ey1, ei1, DT)
    delta = [torch.max(torch.abs(ey0 - ey1)), torch.max(torch.abs(ei0 - ei1))]
    delta.extend(torch.max(torch.abs(x - y)) for x, y in zip(u0, u1))
    return max(float(x) for x in delta)


def event_blocks(values: list[float]) -> list[float]:
    return [float(np.mean(values[i:i + BLOCK_SIZE])) for i in range(0, len(values), BLOCK_SIZE)]


def contrast_passes(contrast: dict[str, float | int | None]) -> bool:
    mean = contrast["mean"]
    lo = contrast["lo"]
    return bool(mean is not None and lo is not None and float(mean) >= 0.05 and float(lo) > 0.0)


def run_arm(
    tag: str,
    device: torch.device,
    flow_sign: int,
    spatial_shuffled: bool,
    carrier: tuple[int, int, int, int] | None,
    replay_schedule: list[int] | None,
    outdir: Path,
) -> dict[str, Any]:
    solver = build_solver(device)
    context = build_context(solver)
    u_hat, ey_hat, ei_hat = initialize_arm(solver, context, flow_sign, spatial_shuffled)
    ey0 = torch.fft.ifftn(ey_hat).real
    ei0 = torch.fft.ifftn(ei_hat).real
    initial = snapshot(solver, ey0, ei0, u_hat, context, 0)
    j_scale = float(initial["jpsi_rms_edge"])
    if j_scale <= 1.0e-14:
        raise ProtocolInvalid(f"{tag}: initial amplitude-current scale is zero")

    theta_ref = math.atan2(
        amplitude_phasor(ey0, ei0, context["target_weight"]).imag,
        amplitude_phasor(ey0, ei0, context["target_weight"]).real,
    )
    schedule = set(replay_schedule or [])
    event_index = {step: index for index, step in enumerate(replay_schedule or [])}
    matched_schedule: list[int] = []
    events: list[dict[str, float | int]] = []
    kicks: list[dict[str, float | int | bool]] = []
    pending: dict[int, dict[str, float | int]] = {}
    history: list[dict[str, float | int | bool]] = [initial]
    min_ey_observed = float(initial["ey_min"])
    min_ei_observed = float(initial["ei_min"])
    floor_seen = bool(initial["floor_ey"] or initial["floor_ei"])
    finite_seen = bool(initial["finite"])
    started = time.time()

    for step in range(STEPS):
        if step in pending:
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            post = amplitude_metrics(solver, ey, ei, u_hat, context)["jpsi_edge"]
            event = pending.pop(step)
            event["post_jpsi_edge"] = post
            event["response"] = (post - float(event["pre_jpsi_edge"])) / j_scale
            events.append(event)

        kick_index: int | None = None
        match: float | None = None
        if step > 0 and step % PULSE_INTERVAL == 0:
            if tag == "matched":
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
                raise ProtocolInvalid(f"{tag}: active event has no carrier")
            sign = carrier[kick_index % len(carrier)]
            ey = torch.fft.ifftn(ey_hat).real
            ei = torch.fft.ifftn(ei_hat).real
            pre = amplitude_metrics(solver, ey, ei, u_hat, context)["jpsi_edge"]
            ey_hat, ei_hat, receipt = amplitude_kick(ey_hat, ei_hat, context, sign)
            kicks.append({
                "step": step,
                "t": step * DT,
                "event_index": kick_index,
                "carrier_sign": sign,
                "match": match,
                "pre_jpsi_edge": pre,
                **receipt,
            })
            pending[step + PULSE_LAG] = {
                "step": step,
                "t": step * DT,
                "event_index": kick_index,
                "pre_jpsi_edge": pre,
            }

        u_hat, ey_hat, ei_hat = solver.rk2_step(u_hat, ey_hat, ei_hat, DT)
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        min_ey_observed = min(min_ey_observed, float(ey.min()))
        min_ei_observed = min(min_ei_observed, float(ei.min()))
        floor_seen = floor_seen or bool((ey <= FLOOR + 1.0e-12).any()) or bool((ei <= FLOOR + 1.0e-12).any())
        finite_seen = finite_seen and bool(torch.isfinite(ey).all() and torch.isfinite(ei).all())
        if step % REPORT_EVERY == 0 or step == STEPS - 1:
            history.append(snapshot(solver, ey, ei, u_hat, context, step + 1))

    if pending:
        raise ProtocolInvalid(f"{tag}: response lag exceeds frozen horizon")

    responses = [float(event["response"]) for event in events]
    response_mean = float(np.mean(responses)) if responses else None
    summary = {
        "n_kicks": len(kicks),
        "n_responses": len(events),
        "response_mean": response_mean,
        "response_blocks": event_blocks(responses),
        "initial_jpsi_scale": j_scale,
        "theta_ref": theta_ref,
        "initial": initial,
        "final": history[-1],
        "min_ey_observed": min_ey_observed,
        "min_ei_observed": min_ei_observed,
        "floor_seen": floor_seen,
        "finite_seen": finite_seen,
        "elapsed_s": time.time() - started,
    }
    result: dict[str, Any] = {
        "tag": tag,
        "flow_sign": flow_sign,
        "spatial_shuffled": spatial_shuffled,
        "carrier": carrier,
        "matched_schedule": matched_schedule if tag == "matched" else sorted(schedule),
        "kicks": kicks,
        "events": events,
        "history": history,
        "summary": summary,
    }
    with (outdir / f"run_{tag}.json").open("w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    response_text = f"{response_mean:+.5f}" if response_mean is not None else "n/a"
    print(
        f"[{tag}] kicks={len(kicks)} response={response_text} "
        f"j0={j_scale:.5f} min={summary['final']['ey_min']:.4f}/"
        f"{summary['final']['ei_min']:.4f} {summary['elapsed_s']:.1f}s",
        flush=True,
    )
    return result


def quality_checks(identity: float, runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    baseline = runs["baseline"]["summary"]["initial"]
    all_history = [sample for run in runs.values() for sample in run["history"]]
    all_kicks = [kick for run in runs.values() for kick in run["kicks"]]
    matched_n = len(runs["matched"]["matched_schedule"])
    expected = matched_n

    finite = all(bool(run["summary"]["finite_seen"]) for run in runs.values()) and all(
        bool(sample["finite"]) for sample in all_history
    ) and all(bool(kick["finite_after"]) for kick in all_kicks)
    no_floor = all(not bool(run["summary"]["floor_seen"]) for run in runs.values()) and all(
        sample["floor_ey"] == 0 and sample["floor_ei"] == 0 for sample in all_history
    )
    replay_counts = all(
        len(runs[name]["kicks"]) == expected
        for name in ("carrier_quadrature", "spatial_shuffled", "counterflow_reversed", "counterflow_zero")
    )
    norm_error = max((abs(float(kick["kick_l2"]) - KICK_L2) for kick in all_kicks), default=float("inf"))
    rho_error = max((float(kick["rho_error_max"]) for kick in all_kicks), default=float("inf"))
    mass_error = max((float(kick["mass_rel_error"]) for kick in all_kicks), default=float("inf"))
    margin = min((float(kick["angle_margin_min"]) for kick in all_kicks), default=-float("inf"))
    directional_seed = bool(
        baseline["u_z_right"] > 0.0
        and baseline["u_z_left"] < 0.0
        and baseline["jpsi_z_right"] * baseline["jpsi_z_left"] < 0.0
    )
    checks = {
        "identity_exact": identity == 0.0,
        "identity_delta": identity,
        "finite": finite,
        "no_floor_hits": no_floor,
        "replay_counts": replay_counts,
        "enough_matched_events": matched_n >= 30,
        "kick_norm_error_max": norm_error,
        "kick_norm_match": norm_error <= NORM_TOL,
        "rho_error_max": rho_error,
        "rho_invariant": rho_error <= RHO_TOL,
        "mass_rel_error_max": mass_error,
        "mass_invariant": mass_error <= RHO_TOL,
        "minimum_angle_margin": margin,
        "safety_wedge": margin >= 0.0 and all(bool(kick["safety"]) for kick in all_kicks),
        "directional_seed": directional_seed,
        "baseline_u_z_right": baseline["u_z_right"],
        "baseline_u_z_left": baseline["u_z_left"],
        "baseline_jpsi_z_right": baseline["jpsi_z_right"],
        "baseline_jpsi_z_left": baseline["jpsi_z_left"],
    }
    checks["valid"] = bool(
        checks["identity_exact"]
        and checks["finite"]
        and checks["no_floor_hits"]
        and checks["replay_counts"]
        and checks["enough_matched_events"]
        and checks["kick_norm_match"]
        and checks["rho_invariant"]
        and checks["mass_invariant"]
        and checks["safety_wedge"]
        and checks["directional_seed"]
    )
    return checks


def classify(quality: dict[str, Any], contrasts: dict[str, dict[str, float | int | None]], runs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not quality["valid"]:
        return {"verdict": "INVALID", "phase": False, "space": False, "counterflow": False}
    phase = contrast_passes(contrasts["phase"])
    space = contrast_passes(contrasts["space"])
    counterflow = contrast_passes(contrasts["counterflow_reversed"]) and contrast_passes(
        contrasts["counterflow_zero"]
    )
    j_positive = runs["matched"]["summary"]["initial"]["jpsi_z_right"]
    j_reversed = runs["counterflow_reversed"]["summary"]["initial"]["jpsi_z_right"]
    counterflow = bool(counterflow and j_positive * j_reversed < 0.0)
    count = int(phase) + int(space) + int(counterflow)
    verdict = "NULL" if count == 0 else "PARTIAL" if count < 3 else "PHASE-SELECTIVE CHECKERBOARD COUNTERFLOW SUPPORT"
    return {"verdict": verdict, "phase": phase, "space": space, "counterflow": counterflow}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=None, help="optional output directory below runs/")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device} N={N} dt={DT} t_end={STEPS * DT} kicks=50/time", flush=True)
    identity = no_op_identity(device)
    print(f"No-op canonical identity max|delta|={identity:.1e}", flush=True)

    if args.output_dir is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        outdir = ROOT / "runs" / f"{run_id}_counterflow_amplitude_phase_kick"
    else:
        outdir = Path(args.output_dir)
        if not outdir.is_absolute():
            outdir = ROOT / outdir
    outdir.mkdir(parents=True, exist_ok=False)

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_arm("baseline", device, +1, False, None, None, outdir)
    runs["matched"] = run_arm("matched", device, +1, False, MATCHED_CARRIER, None, outdir)
    schedule = runs["matched"]["matched_schedule"]
    runs["carrier_quadrature"] = run_arm(
        "carrier_quadrature", device, +1, False, QUADRATURE_CARRIER, schedule, outdir
    )
    runs["spatial_shuffled"] = run_arm(
        "spatial_shuffled", device, +1, True, MATCHED_CARRIER, schedule, outdir
    )
    runs["counterflow_reversed"] = run_arm(
        "counterflow_reversed", device, -1, False, MATCHED_CARRIER, schedule, outdir
    )
    runs["counterflow_zero"] = run_arm(
        "counterflow_zero", device, 0, False, MATCHED_CARRIER, schedule, outdir
    )

    quality = quality_checks(identity, runs)
    blocks = {name: run["summary"]["response_blocks"] for name, run in runs.items()}
    contrasts = {
        "phase": paired_bootstrap(blocks["matched"], blocks["carrier_quadrature"]),
        "space": paired_bootstrap(blocks["matched"], blocks["spatial_shuffled"]),
        "counterflow_reversed": paired_bootstrap(blocks["matched"], blocks["counterflow_reversed"]),
        "counterflow_zero": paired_bootstrap(blocks["matched"], blocks["counterflow_zero"]),
    }
    verdict = classify(quality, contrasts, runs)
    receipt = {
        "protocol": "field-experience/counterflow-amplitude-phase-kick-pre-registration.md",
        "script": "field-experience/counterflow_amplitude_phase_kick_probe.py",
        "config": {
            "N": N,
            "dt": DT,
            "steps": STEPS,
            "t_end": STEPS * DT,
            "kick_l2": KICK_L2,
            "kick_alpha_cap": KICK_ALPHA_CAP,
            "kick_bisect_iters": KICK_BISECT_ITERS,
            "pulse_interval": PULSE_INTERVAL,
            "pulse_lag": PULSE_LAG,
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
