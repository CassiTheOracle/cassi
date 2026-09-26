#!/usr/bin/env python3
"""Frozen Wave-6 source-only field-space timing probe.

Run from the CassiTheory repository root::

    python field-experience/source_only_fieldspace_timing_probe.py

Protocol: field-experience/source-only-fieldspace-timing-pre-registration.md
"""

from __future__ import annotations

import argparse
import json
import math
import time
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np
import torch

from counterflow_resonant_addressing_probe import (
    DT,
    FLOOR,
    MATCH_THRESHOLD,
    N,
    PHI,
    ROOT,
    initialize_arm,
    build_solver,
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
)
from source_only_passive_transfer_probe import (
    A_CENTER,
    COMPACT_RADIUS,
    D_CENTER,
    HORIZON,
    PULSE_STEP,
    T_CENTER,
    build_compact_context,
    compact_kick,
    support_audit,
    target_phase_match,
)


# Frozen Wave-6 analysis values.
PAIR_K_MAX = 160
TIMING_K_MIN = 1
TIMING_K_MAX = 120
LATE_K_MIN = 20
LATE_K_MAX = 120
Q_FLOOR = 1.0e-12
SOURCE_MASK_KEY = "T"

ARM_ORDER = (
    "baseline",
    "source_plus",
    "source_minus",
    "source_shuffled_plus",
    "source_shuffled_minus",
)
SOURCE_ARMS = ARM_ORDER[1:]
PAIR_ORDER = ("source", "source_shuffled")


class ProtocolInvalid(RuntimeError):
    """Raised when an execution-time frozen quality condition fails."""


def _finite_float(value: float | int | np.floating[Any]) -> float:
    """Convert a scalar to a JSON-safe finite Python float."""
    result = float(value)
    if not math.isfinite(result):
        raise ProtocolInvalid(f"non-finite scalar in receipt: {value!r}")
    return result


def q_from_amplitude_pair(
    A_plus: torch.Tensor,
    B_plus: torch.Tensor,
    A_minus: torch.Tensor,
    B_minus: torch.Tensor,
    weight: torch.Tensor,
) -> tuple[float, float, float]:
    """Return q_R and its local amplitude-space component norms.

    The pair is formed pointwise before applying the normalized local weight;
    this is intentionally not a projection or a difference of weighted means.
    """
    delta_A = 0.5 * (A_plus - A_minus)
    delta_B = 0.5 * (B_plus - B_minus)
    delta_A_sq = (weight * delta_A * delta_A).sum()
    delta_B_sq = (weight * delta_B * delta_B).sum()
    total = torch.clamp_min(delta_A_sq + delta_B_sq, 0.0)
    q_value = torch.sqrt(total) / KICK_L2
    return (
        _finite_float(q_value),
        _finite_float(torch.sqrt(torch.clamp_min(delta_A_sq, 0.0))),
        _finite_float(torch.sqrt(torch.clamp_min(delta_B_sq, 0.0))),
    )


def amplitude_pair_snapshot(
    plus: tuple[torch.Tensor, torch.Tensor],
    minus: tuple[torch.Tensor, torch.Tensor],
    context: dict[str, Any],
    k: int,
    step: int,
) -> dict[str, float | int]:
    """Form one exact field-space snapshot from matched plus/minus fields."""
    A_plus, B_plus = amplitude_fields(*plus)
    A_minus, B_minus = amplitude_fields(*minus)
    q_D, dA_D, dB_D = q_from_amplitude_pair(
        A_plus, B_plus, A_minus, B_minus, context["chi_D"]
    )
    q_A, dA_A, dB_A = q_from_amplitude_pair(
        A_plus, B_plus, A_minus, B_minus, context["chi_A"]
    )
    return {
        "k": int(k),
        "step": int(step),
        "t": _finite_float(step * DT),
        "q_D": q_D,
        "q_A": q_A,
        "delta_A_l2_D": dA_D,
        "delta_B_l2_D": dB_D,
        "delta_A_l2_A": dA_A,
        "delta_B_l2_A": dB_A,
    }


def field_space_current_telemetry(
    solver: Any,
    ey: torch.Tensor,
    ei: torch.Tensor,
    context: dict[str, Any],
) -> dict[str, float]:
    """Record the old FFT-gradient current only as k=0 telemetry."""
    Jx, Jy, _Jz = amplitude_current(solver, ey, ei)
    return {
        "j_D_0": _finite_float(
            weighted_mean((Jx + Jy) / math.sqrt(2.0), context["chi_D"])
        ),
        "j_A_0": _finite_float(weighted_mean(Jy, context["chi_A"])),
    }


def field_snapshot(
    solver: Any,
    u_hat: list[torch.Tensor],
    ey: torch.Tensor,
    ei: torch.Tensor,
    step: int,
) -> dict[str, float | int | bool]:
    """Record scalar field and invariant receipts without changing the solver."""
    rho = ey + ei
    eps = ey - PHI * ei
    u_finite = all(bool(torch.isfinite(component).all()) for component in u_hat)
    return {
        "step": int(step),
        "t": _finite_float(step * DT),
        "ey_min": _finite_float(ey.min()),
        "ei_min": _finite_float(ei.min()),
        "rho_min": _finite_float(rho.min()),
        "rho_max": _finite_float(rho.max()),
        "floor_ey": int((ey <= FLOOR + 1.0e-12).sum()),
        "floor_ei": int((ei <= FLOOR + 1.0e-12).sum()),
        "mass": _finite_float(rho.sum()),
        "eps_total": _finite_float(eps.sum()),
        "H": _finite_float(solver.H),
        "a": _finite_float(solver.a),
        "field_finite": bool(torch.isfinite(ey).all() and torch.isfinite(ei).all()),
        "flow_finite": u_finite,
    }


def _new_arm_state(
    tag: str,
    device: torch.device,
    spatial_shuffled: bool,
    pulse_sign: int,
) -> dict[str, Any]:
    """Build one fresh solver/state, preserving canonical Wave-5 initialization."""
    solver = build_solver(device)
    context = build_compact_context(solver)
    u_hat, ey_hat, ei_hat = initialize_arm(solver, context, +1, spatial_shuffled)
    ey = torch.fft.ifftn(ey_hat).real
    ei = torch.fft.ifftn(ei_hat).real
    z0 = amplitude_phasor(ey, ei, context["target_weight"])
    if abs(z0) <= 1.0e-14:
        raise ProtocolInvalid(f"{tag}: initial target amplitude phasor is zero")
    return {
        "tag": tag,
        "solver": solver,
        "context": context,
        "u_hat": u_hat,
        "ey_hat": ey_hat,
        "ei_hat": ei_hat,
        "spatial_shuffled": bool(spatial_shuffled),
        "pulse_mask_name": SOURCE_MASK_KEY,
        "pulse_sign": int(pulse_sign),
        "theta_t0": math.atan2(z0.imag, z0.real),
        "pulse": None,
    }


def _advance_state_to_snapshot(
    state: dict[str, Any],
    step: int,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float | int | bool]]:
    """Apply the frozen source pulse at step 100, then read one field snapshot."""
    context = state["context"]
    if (
        step == PULSE_STEP
        and state["pulse_mask_name"] is not None
        and state["pulse"] is None
    ):
        ey_before = torch.fft.ifftn(state["ey_hat"]).real
        ei_before = torch.fft.ifftn(state["ei_hat"]).real
        match = target_phase_match(ey_before, ei_before, context, state["theta_t0"])
        if not math.isfinite(match) or match < MATCH_THRESHOLD:
            raise ProtocolInvalid(
                f"{state['tag']}: target phase match {match!r} is below "
                f"{MATCH_THRESHOLD:.12g}"
            )
        state["ey_hat"], state["ei_hat"], kick_receipt = compact_kick(
            state["ey_hat"],
            state["ei_hat"],
            context["compact_masks"][str(state["pulse_mask_name"])],
            state["pulse_sign"],
        )
        state["pulse"] = {
            "step": PULSE_STEP,
            "t": _finite_float(PULSE_STEP * DT),
            "mask": str(state["pulse_mask_name"]),
            "sign": int(state["pulse_sign"]),
            "target_phase_match": _finite_float(match),
            **kick_receipt,
        }

    ey = torch.fft.ifftn(state["ey_hat"]).real
    ei = torch.fft.ifftn(state["ei_hat"]).real
    snapshot = field_snapshot(state["solver"], state["u_hat"], ey, ei, step)
    return ey, ei, snapshot


def field_space_trace_wrapper(
    states: list[dict[str, Any]],
    end_step: int,
    snapshot_callback: Callable[
        [int, dict[str, tuple[torch.Tensor, torch.Tensor, dict[str, Any]]]], None
    ]
    | None = None,
) -> dict[str, list[dict[str, float | int | bool]]]:
    """Run the actual read-only field-space trace path for independent states.

    Each state retains a separate fresh solver. The wrapper reads fields after
    any step-local pulse, emits scalar receipts, gives the callback matched
    field tensors, and only then performs the canonical RK2 step. Source pairs
    therefore form q_R from pointwise amplitude fields, never from a current.
    """
    if end_step < 0:
        raise ValueError("trace end step must be non-negative")
    traces: dict[str, list[dict[str, float | int | bool]]] = {
        str(state["tag"]): [] for state in states
    }
    for step in range(end_step + 1):
        current: dict[str, tuple[torch.Tensor, torch.Tensor, dict[str, Any]]] = {}
        for state in states:
            ey, ei, receipt = _advance_state_to_snapshot(state, step)
            traces[str(state["tag"])].append(receipt)
            current[str(state["tag"])] = (ey, ei, receipt)
        if snapshot_callback is not None:
            snapshot_callback(step, current)
        if step < end_step:
            for state in states:
                state["u_hat"], state["ey_hat"], state["ei_hat"] = state[
                    "solver"
                ].rk2_step(state["u_hat"], state["ey_hat"], state["ei_hat"], DT)
    return traces


def _max_state_delta(
    left: dict[str, Any],
    right_u: list[torch.Tensor],
    right_ey: torch.Tensor,
    right_ei: torch.Tensor,
) -> float:
    values = [
        torch.max(torch.abs(left["ey_hat"] - right_ey)),
        torch.max(torch.abs(left["ei_hat"] - right_ei)),
    ]
    values.extend(torch.max(torch.abs(a - b)) for a, b in zip(left["u_hat"], right_u))
    return max(_finite_float(value) for value in values)


def field_space_no_op_identity(device: torch.device) -> dict[str, Any]:
    """Compare the complete read-only pair wrapper with direct canonical RK2."""
    direct_solver = build_solver(device)
    direct_context = build_compact_context(direct_solver)
    direct_u, direct_ey, direct_ei = initialize_arm(
        direct_solver, direct_context, +1, False
    )
    wrapped_plus = _new_arm_state("identity_plus", device, False, +1)
    wrapped_minus = _new_arm_state("identity_minus", device, False, -1)
    wrapped_plus["pulse_mask_name"] = None
    wrapped_minus["pulse_mask_name"] = None
    identity_pair: list[dict[str, float | int]] = []

    def on_snapshot(
        step: int,
        current: dict[str, tuple[torch.Tensor, torch.Tensor, dict[str, Any]]],
    ) -> None:
        identity_pair.append(
            amplitude_pair_snapshot(
                current["identity_plus"][:2],
                current["identity_minus"][:2],
                wrapped_plus["context"],
                step,
                step,
            )
        )

    wrapper_traces = field_space_trace_wrapper(
        [wrapped_plus, wrapped_minus], 100, on_snapshot
    )
    for _ in range(100):
        direct_u, direct_ey, direct_ei = direct_solver.rk2_step(
            direct_u, direct_ey, direct_ei, DT
        )
    if device.type == "cuda":
        torch.cuda.synchronize(device)
    delta = _max_state_delta(wrapped_plus, direct_u, direct_ey, direct_ei)
    identity_q_max = max(
        max(float(row["q_D"]), float(row["q_A"])) for row in identity_pair
    )
    return {
        "wrapper": "field_space_trace_wrapper + amplitude_pair_snapshot",
        "direct_sequence": "100 canonical rk2_step calls",
        "steps": 100,
        "trace_length": len(wrapper_traces["identity_plus"]),
        "pair_trace_length": len(identity_pair),
        "identity_pair_q_max": identity_q_max,
        "max_abs_delta": delta,
        "identity_exact": bool(delta == 0.0 and identity_q_max <= 1.0e-15),
    }


def synthetic_fieldspace_checks(context: dict[str, Any]) -> dict[str, Any]:
    """Check q=0 for equal pairs and q=1 for a unit antisymmetric pair."""
    chi_D = context["chi_D"]
    chi_A = context["chi_A"]
    equal_A = torch.zeros_like(chi_D)
    equal_B = torch.zeros_like(chi_D)
    unit_A_plus = torch.full_like(chi_D, KICK_L2)
    unit_A_minus = torch.full_like(chi_D, -KICK_L2)
    equal_D = q_from_amplitude_pair(equal_A, equal_B, equal_A, equal_B, chi_D)[0]
    equal_A_value = q_from_amplitude_pair(
        equal_A, equal_B, equal_A, equal_B, chi_A
    )[0]
    unit_D = q_from_amplitude_pair(
        unit_A_plus, equal_B, unit_A_minus, equal_B, chi_D
    )[0]
    unit_A_value = q_from_amplitude_pair(
        unit_A_plus, equal_B, unit_A_minus, equal_B, chi_A
    )[0]
    passes = bool(
        equal_D <= 1.0e-15
        and equal_A_value <= 1.0e-15
        and abs(unit_D - 1.0) <= 1.0e-12
        and abs(unit_A_value - 1.0) <= 1.0e-12
    )
    return {
        "equal_pair_q_D": equal_D,
        "equal_pair_q_A": equal_A_value,
        "unit_antisymmetric_q_D": unit_D,
        "unit_antisymmetric_q_A": unit_A_value,
        "normalization": KICK_L2,
        "passes": passes,
    }


def _arm_summary(
    tag: str,
    state: dict[str, Any],
    trace: list[dict[str, float | int | bool]],
    elapsed_s: float,
) -> dict[str, Any]:
    if len(trace) != HORIZON + 1:
        raise ProtocolInvalid(f"{tag}: trace length {len(trace)} != {HORIZON + 1}")
    if [row["step"] for row in trace] != list(range(HORIZON + 1)):
        raise ProtocolInvalid(f"{tag}: trace step indices are not complete")
    finite_seen = all(bool(row["field_finite"] and row["flow_finite"]) for row in trace)
    floor_seen = any(bool(row["floor_ey"] or row["floor_ei"]) for row in trace)
    return {
        "trace_length": len(trace),
        "trace_steps": [0, HORIZON],
        "initial": trace[0],
        "final": trace[-1],
        "min_ey_observed": min(float(row["ey_min"]) for row in trace),
        "min_ei_observed": min(float(row["ei_min"]) for row in trace),
        "finite_seen": finite_seen,
        "floor_seen": floor_seen,
        "initial_mass": float(trace[0]["mass"]),
        "final_mass": float(trace[-1]["mass"]),
        "pulse": state["pulse"],
        "elapsed_s": _finite_float(elapsed_s),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)


def run_baseline(device: torch.device, outdir: Path) -> dict[str, Any]:
    """Run the fresh no-pulse baseline through step 260."""
    state = _new_arm_state("baseline", device, False, 0)
    state["pulse_mask_name"] = None
    started = time.time()
    traces = field_space_trace_wrapper([state], HORIZON)
    trace = traces["baseline"]
    result = {
        "tag": "baseline",
        "spatial_shuffled": False,
        "pulse_mask": None,
        "pulse_sign": 0,
        "field_trace": trace,
        "summary": _arm_summary("baseline", state, trace, time.time() - started),
    }
    _write_json(outdir / "run_baseline.json", result)
    return result


def run_source_pair(
    pair_name: str,
    device: torch.device,
    spatial_shuffled: bool,
    outdir: Path,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Run a fresh +/- source pair and form q_R from every matched field step."""
    plus_name = f"{pair_name}_plus"
    minus_name = f"{pair_name}_minus"
    plus = _new_arm_state(plus_name, device, spatial_shuffled, +1)
    minus = _new_arm_state(minus_name, device, spatial_shuffled, -1)
    pair_snapshots: list[dict[str, float | int]] = []
    telemetry_at_pulse: dict[str, dict[str, float]] = {}

    def on_snapshot(
        step: int,
        current: dict[str, tuple[torch.Tensor, torch.Tensor, dict[str, Any]]],
    ) -> None:
        if step == PULSE_STEP:
            telemetry_at_pulse[plus_name] = field_space_current_telemetry(
                plus["solver"],
                current[plus_name][0],
                current[plus_name][1],
                plus["context"],
            )
            telemetry_at_pulse[minus_name] = field_space_current_telemetry(
                minus["solver"],
                current[minus_name][0],
                current[minus_name][1],
                minus["context"],
            )
        if PULSE_STEP <= step <= PULSE_STEP + PAIR_K_MAX:
            pair_snapshots.append(
                amplitude_pair_snapshot(
                    current[plus_name][:2],
                    current[minus_name][:2],
                    plus["context"],
                    step - PULSE_STEP,
                    step,
                )
            )

    started = time.time()
    traces = field_space_trace_wrapper([plus, minus], HORIZON, on_snapshot)
    elapsed = time.time() - started
    if len(pair_snapshots) != PAIR_K_MAX + 1:
        raise ProtocolInvalid(
            f"{pair_name}: field-space pair trace has {len(pair_snapshots)} samples"
        )
    if [int(row["k"]) for row in pair_snapshots] != list(range(PAIR_K_MAX + 1)):
        raise ProtocolInvalid(f"{pair_name}: pair k indices are incomplete")

    plus_trace = traces[plus_name]
    minus_trace = traces[minus_name]
    runs: dict[str, dict[str, Any]] = {}
    for state, trace, tag in ((plus, plus_trace, plus_name), (minus, minus_trace, minus_name)):
        result = {
            "tag": tag,
            "spatial_shuffled": bool(spatial_shuffled),
            "pulse_mask": str(state["pulse_mask_name"]),
            "pulse_sign": int(state["pulse_sign"]),
            "field_trace": trace,
            "summary": _arm_summary(tag, state, trace, elapsed),
        }
        runs[tag] = result
        _write_json(outdir / f"run_{tag}.json", result)

    if plus_name not in telemetry_at_pulse or minus_name not in telemetry_at_pulse:
        raise ProtocolInvalid(f"{pair_name}: missing pulse-snapshot current telemetry")
    telemetry_plus = telemetry_at_pulse[plus_name]
    telemetry_minus = telemetry_at_pulse[minus_name]
    telemetry = {
        "j_D_plus_0": telemetry_plus["j_D_0"],
        "j_D_minus_0": telemetry_minus["j_D_0"],
        "j_A_plus_0": telemetry_plus["j_A_0"],
        "j_A_minus_0": telemetry_minus["j_A_0"],
        "S_D_0": _finite_float(
            0.5 * (telemetry_plus["j_D_0"] - telemetry_minus["j_D_0"])
        ),
        "S_A_0": _finite_float(
            0.5 * (telemetry_plus["j_A_0"] - telemetry_minus["j_A_0"])
        ),
        "classifying": False,
        "method": "Wave-5 amplitude_current FFT-gradient diagnostic",
    }
    pair_result: dict[str, Any] = {
        "pair": pair_name,
        "plus_arm": plus_name,
        "minus_arm": minus_name,
        "spatial_shuffled": bool(spatial_shuffled),
        "normalization": KICK_L2,
        "pair_snapshot_steps": [PULSE_STEP, PULSE_STEP + PAIR_K_MAX],
        "amplitude_pair_trace": pair_snapshots,
        "current_telemetry": telemetry,
    }
    _write_json(outdir / f"pair_{pair_name}.json", pair_result)
    return runs, pair_result


def timing_metrics(q_values: list[float]) -> dict[str, Any]:
    """Compute the preregistered W, k50, iota, p, and Q_late metrics."""
    if len(q_values) != PAIR_K_MAX + 1:
        raise ProtocolInvalid(f"timing trace length {len(q_values)} != {PAIR_K_MAX + 1}")
    if any(not math.isfinite(float(value)) for value in q_values):
        raise ProtocolInvalid("non-finite q value in timing trace")

    q_sq = np.asarray([float(value) ** 2 for value in q_values], dtype=np.float64)
    analysis = q_sq[TIMING_K_MIN : TIMING_K_MAX + 1]
    W = float(analysis.sum())
    ranges = {
        "W": [TIMING_K_MIN, TIMING_K_MAX],
        "k50": [TIMING_K_MIN, TIMING_K_MAX],
        "iota": [1, 1],
        "p": [LATE_K_MIN, LATE_K_MAX],
        "Q_late": [LATE_K_MIN, LATE_K_MAX],
    }
    if not math.isfinite(W) or W <= 0.0:
        return {
            "W": 0.0 if W == 0.0 else None,
            "k50": None,
            "iota": None,
            "p": None,
            "Q_late": None,
            "defined": False,
            "detectable": False,
            "undefined_reason": "W_nonpositive",
            "ranges": ranges,
        }

    cumulative = np.cumsum(analysis)
    k50_candidates = np.flatnonzero(cumulative >= 0.5 * W)
    k50 = int(TIMING_K_MIN + int(k50_candidates[0])) if len(k50_candidates) else None
    iota = float(q_sq[1] / W)
    p = float(q_sq[LATE_K_MIN : LATE_K_MAX + 1].sum() / W)
    Q_late = float(math.sqrt(float(q_sq[LATE_K_MIN : LATE_K_MAX + 1].mean())))
    return {
        "W": _finite_float(W),
        "k50": k50,
        "iota": _finite_float(iota),
        "p": _finite_float(p),
        "Q_late": _finite_float(Q_late),
        "defined": bool(k50 is not None),
        "detectable": bool(Q_late >= Q_FLOOR and W > 0.0),
        "undefined_reason": None if k50 is not None else "k50_not_reached",
        "ranges": ranges,
    }


def delayed_condition(diagonal: dict[str, Any], axial: dict[str, Any]) -> bool | None:
    """Return strict D, or None when either label setting has undefined timing."""
    if not bool(diagonal["defined"]) or not bool(axial["defined"]):
        return None
    values = (diagonal["k50"], axial["k50"], diagonal["p"], axial["p"])
    if any(value is None for value in values):
        return None
    return bool(
        int(diagonal["k50"]) > int(axial["k50"])
        and float(diagonal["p"]) > float(axial["p"])
    )


def attach_pair_timing(pair: dict[str, Any]) -> dict[str, Any]:
    q_D = [float(row["q_D"]) for row in pair["amplitude_pair_trace"]]
    q_A = [float(row["q_A"]) for row in pair["amplitude_pair_trace"]]
    timing = {"D": timing_metrics(q_D), "A": timing_metrics(q_A)}
    timing["delayed_condition"] = delayed_condition(timing["D"], timing["A"])
    timing["q_snapshot_gate"] = {
        "q_D_0": q_D[0],
        "q_A_0": q_A[0],
        "passes": bool(q_D[0] <= Q_FLOOR and q_A[0] <= Q_FLOOR),
    }
    pair["timing"] = timing
    return pair


def quality_receipt(
    identity: dict[str, Any],
    synthetic: dict[str, Any],
    support: dict[str, Any],
    runs: dict[str, dict[str, Any]],
    pairs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Apply every frozen Wave-6 execution and measurement quality gate."""
    all_runs = [runs[name] for name in ARM_ORDER]
    all_samples = [sample for run in all_runs for sample in run["field_trace"]]
    pulses = [runs[name]["summary"]["pulse"] for name in SOURCE_ARMS]
    source_matches = {
        name: runs[name]["summary"]["pulse"]["target_phase_match"] for name in SOURCE_ARMS
    }
    source_match_ok = all(
        value is not None and math.isfinite(float(value)) and float(value) >= MATCH_THRESHOLD
        for value in source_matches.values()
    )
    q0 = {name: pairs[name]["timing"]["q_snapshot_gate"] for name in PAIR_ORDER}
    q0_ok = all(bool(value["passes"]) for value in q0.values())
    all_pair_traces = all(
        len(pair["amplitude_pair_trace"]) == PAIR_K_MAX + 1 for pair in pairs.values()
    )
    finite = (
        all(bool(run["summary"]["finite_seen"]) for run in all_runs)
        and all(bool(sample["field_finite"] and sample["flow_finite"]) for sample in all_samples)
        and all(bool(pulse["finite_after"]) for pulse in pulses)
        and all(
            all(math.isfinite(float(row["q_D"])) and math.isfinite(float(row["q_A"])) for row in pair["amplitude_pair_trace"])
            for pair in pairs.values()
        )
    )
    no_floor_hits = (
        all(not bool(run["summary"]["floor_seen"]) for run in all_runs)
        and all(int(sample["floor_ey"]) == 0 and int(sample["floor_ei"]) == 0 for sample in all_samples)
        and all(not bool(pulse["floor_after"]) for pulse in pulses)
    )
    capacities = all(bool(pulse["capacity"]) for pulse in pulses)
    norm_error = max(float(pulse["norm_error"]) for pulse in pulses)
    rho_error = max(float(pulse["rho_error_max"]) for pulse in pulses)
    mass_error = max(float(pulse["mass_rel_error"]) for pulse in pulses)
    wedge_margin = min(float(pulse["angle_margin_min"]) for pulse in pulses)
    quality: dict[str, Any] = {
        "synthetic_fieldspace_checks": synthetic,
        "identity_exact": bool(identity["identity_exact"]),
        "identity_delta": float(identity["max_abs_delta"]),
        "identity_receipt": identity,
        "support_disjoint": bool(support["source_receiver_disjoint"]),
        "support_audit": support,
        "source_phase_match": source_matches,
        "source_phase_match_ok": source_match_ok,
        "pulse_snapshot_q": q0,
        "pulse_snapshot_q_ok": q0_ok,
        "finite": finite,
        "no_floor_hits": no_floor_hits,
        "n_active_pulses": len(pulses),
        "one_pulse_per_source_arm": len(pulses) == len(SOURCE_ARMS),
        "capacity": capacities,
        "beta_max": max(float(pulse["beta"]) for pulse in pulses),
        "kick_norm_error_max": norm_error,
        "kick_norm_match": norm_error <= NORM_TOL,
        "rho_error_max": rho_error,
        "rho_invariant": rho_error <= RHO_TOL,
        "mass_rel_error_max": mass_error,
        "mass_invariant": mass_error <= RHO_TOL,
        "minimum_angle_margin": wedge_margin,
        "safety_wedge": wedge_margin >= 0.0 and all(bool(pulse["safety"]) for pulse in pulses),
        "all_261_sample_traces": all(len(run["field_trace"]) == HORIZON + 1 for run in all_runs),
        "all_161_pair_traces": all_pair_traces,
    }
    quality["valid"] = bool(
        quality["synthetic_fieldspace_checks"]["passes"]
        and quality["identity_exact"]
        and quality["support_disjoint"]
        and quality["source_phase_match_ok"]
        and quality["pulse_snapshot_q_ok"]
        and quality["finite"]
        and quality["no_floor_hits"]
        and quality["one_pulse_per_source_arm"]
        and quality["capacity"]
        and quality["kick_norm_match"]
        and quality["rho_invariant"]
        and quality["mass_invariant"]
        and quality["safety_wedge"]
        and quality["all_261_sample_traces"]
        and quality["all_161_pair_traces"]
    )
    return quality


def classify(quality: dict[str, Any], pairs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Apply frozen F1/F2/F3 labels and the Wave-6 terminal decision tree."""
    if not bool(quality["valid"]):
        return {
            "verdict": "INVALID",
            "features": {"F1": "DOES NOT EMERGE", "F2": "DOES NOT EMERGE", "F3": "DOES NOT EMERGE"},
            "reason": "quality_gate_failure",
        }

    standard = pairs["source"]["timing"]
    shuffled = pairs["source_shuffled"]["timing"]
    f1 = bool(
        standard["D"]["W"] is not None
        and standard["D"]["W"] > 0.0
        and standard["D"]["Q_late"] is not None
        and standard["D"]["Q_late"] >= Q_FLOOR
    )
    delayed_standard = standard["delayed_condition"]
    delayed_shuffled = shuffled["delayed_condition"]
    f2 = bool(delayed_standard is True)
    f3 = bool(delayed_standard is True and delayed_shuffled is False)

    immediate_global = False
    k_D, k_A = standard["D"]["k50"], standard["A"]["k50"]
    iota_D, iota_A = standard["D"]["iota"], standard["A"]["iota"]
    if all(value is not None for value in (k_D, k_A, iota_D, iota_A)):
        immediate_global = bool(int(k_D) <= int(k_A) and float(iota_D) >= float(iota_A))

    if not f1 or immediate_global:
        verdict = "CONTRADICTS"
        reason = "f1_absent" if not f1 else "immediate_global_timing_branch"
    elif f1 and f2 and delayed_shuffled is None:
        verdict = "INCONCLUSIVE"
        reason = "undefined_shuffled_timing"
    elif f1 and f2 and f3:
        verdict = "SUPPORTS"
        reason = "all_frozen_features_emerge"
    elif f1 and f2 and not f3:
        verdict = "HOLD"
        reason = "f1_f2_emerge_but_f3_does_not"
    else:
        verdict = "INCONCLUSIVE"
        reason = "other_valid_tree_outcome"
    return {
        "verdict": verdict,
        "features": {
            "F1": "EMERGES" if f1 else "DOES NOT EMERGE",
            "F2": "EMERGES" if f2 else "DOES NOT EMERGE",
            "F3": "EMERGES" if f3 else "DOES NOT EMERGE",
        },
        "conditions": {
            "standard_delayed": delayed_standard,
            "shuffled_delayed": delayed_shuffled,
            "immediate_global_branch": immediate_global,
        },
        "thresholds": {"Q_late_floor": Q_FLOOR, "normalization": KICK_L2},
        "reason": reason,
    }


def output_directory(argument: str | None) -> Path:
    if argument is None:
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        return ROOT / "runs" / f"{run_id}_source_only_fieldspace_timing"
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
    parser.add_argument("--output-dir", default=None, help="optional output directory below CassiTheory/runs")
    args = parser.parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    outdir = output_directory(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=False)
    print(
        f"Device: {device} N={N} dt={DT} t_end={HORIZON * DT:.3f} pulse_step={PULSE_STEP} q_k=0..{PAIR_K_MAX}",
        flush=True,
    )

    identity = field_space_no_op_identity(device)
    print(f"No-op field-space wrapper max|delta|={identity['max_abs_delta']:.1e}", flush=True)

    audit_solver = build_solver(device)
    audit_context = build_compact_context(audit_solver)
    support = support_audit(audit_context)
    synthetic = synthetic_fieldspace_checks(audit_context)

    runs: dict[str, dict[str, Any]] = {}
    runs["baseline"] = run_baseline(device, outdir)
    source_runs, source_pair = run_source_pair("source", device, False, outdir)
    shuffled_runs, shuffled_pair = run_source_pair("source_shuffled", device, True, outdir)
    runs.update(source_runs)
    runs.update(shuffled_runs)
    pairs = {"source": source_pair, "source_shuffled": shuffled_pair}
    for pair in pairs.values():
        attach_pair_timing(pair)
        _write_json(outdir / f"pair_{pair['pair']}.json", pair)

    quality = quality_receipt(identity, synthetic, support, runs, pairs)
    verdict = classify(quality, pairs)
    receipt: dict[str, Any] = {
        "protocol": "field-experience/source-only-fieldspace-timing-pre-registration.md",
        "script": "field-experience/source_only_fieldspace_timing_probe.py",
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
            "analysis_q_k": [0, PAIR_K_MAX],
            "timing_W_k": [TIMING_K_MIN, TIMING_K_MAX],
            "timing_k50_k": [TIMING_K_MIN, TIMING_K_MAX],
            "timing_iota_k": [1, 1],
            "timing_p_k": [LATE_K_MIN, LATE_K_MAX],
            "timing_Q_late_k": [LATE_K_MIN, LATE_K_MAX],
            "q_normalization": KICK_L2,
            "q_floor": Q_FLOOR,
        },
        "arm_order": list(ARM_ORDER),
        "pair_order": list(PAIR_ORDER),
        "support": support,
        "synthetic_fieldspace_checks": synthetic,
        "identity": identity,
        "quality": quality,
        "pairs": pairs,
        "timing": {name: pair["timing"] for name, pair in pairs.items()},
        "verdict": verdict,
        "run_files": {name: f"run_{name}.json" for name in ARM_ORDER},
        "pair_files": {name: f"pair_{name}.json" for name in PAIR_ORDER},
    }
    _write_json(outdir / "results.json", receipt)

    standard = pairs["source"]["timing"]
    shuffled = pairs["source_shuffled"]["timing"]
    print(
        f"Quality={'PASS' if quality['valid'] else 'INVALID'} "
        f"W_D/W_A={standard['D']['W']!s}/{standard['A']['W']!s} "
        f"k50_D/k50_A={standard['D']['k50']!s}/{standard['A']['k50']!s} "
        f"q0_D/q0_A={standard['q_snapshot_gate']['q_D_0']:.3g}/{standard['q_snapshot_gate']['q_A_0']:.3g} "
        f"S_D0/S_A0={pairs['source']['current_telemetry']['S_D_0']:.3g}/{pairs['source']['current_telemetry']['S_A_0']:.3g} "
        f"F1={verdict['features']['F1']} F2={verdict['features']['F2']} F3={verdict['features']['F3']} "
        f"verdict={verdict['verdict']} shuf_timing={shuffled['delayed_condition']!s}",
        flush=True,
    )
    print(f"Results: {outdir / 'results.json'}", flush=True)


if __name__ == "__main__":
    main()
