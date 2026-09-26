#!/usr/bin/env python3
"""Probe for computations/loop-carrier-projection-split-prereg.md.

The successor protocol (computations/loop-carrier-projection-relaxation-prereg.md) settles
the closure and the conversion rate under two assumptions the projection theorem is
conditional on: that both carriers see one common projected gate, and that both carriers
are advected by one shared exterior velocity. This probe splits each assumption alone,
over six declared levels, and reads the same closure statistic the successor reads.

Nothing here is a transcription of the successor's machinery: the frozen discrete operators
are bound by digest, and the projection, the integrator, the reference solver, the gate and
the declared arm seeds are imported from the successor probe, itself bound by digest, so
the statistic is the successor's own code. The only new arithmetic is the split itself,
which reduces to the successor's right-hand side exactly at zero split (checked by
`--self-check` before any invocation).

Usage:
    python computations/verify_loop_carrier_projection_split.py --self-check
    timeout 600 python computations/verify_loop_carrier_projection_split.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Frozen sources, all by digest. The bound module is the discrete operator layer; the base
# probe is the successor's executed probe, whose declarations this protocol re-uses; the
# successor receipt is the predecessor's immutable reading, from which the two bit-identity
# oracles of section 4.2 are read rather than typed.
BOUND_MODULE = "computations/verify_loop_to_bubble_projection.py"
BOUND_DIGEST = "d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1"
BASE_PROBE = "computations/verify_loop_carrier_projection_relaxation.py"
BASE_PROBE_DIGEST = "28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622"
BASE_RECEIPT = "runs/loop_carrier_projection_relaxation/verification.json"
BASE_RECEIPT_DIGEST = "3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1"

PROTOCOL_PATH = "computations/loop-carrier-projection-split-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_projection_split.py"
RECEIPT_PATH = "runs/loop_carrier_projection_split/verification.json"
INVOCATION = "timeout 600 python computations/verify_loop_carrier_projection_split.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-projection-split.v1"
BOUND_SECONDS = 600.0

# Section 0 of the protocol declares both hashes: this file's, and the digest of the frozen
# body (everything from "## 1." to just before "## 8."). The two are cross-bound without a
# fix point, because section 0 sits outside the body range. Filled by the freeze pass.
FROZEN_BODY_DIGEST = "f7a7d9ea67bf160ca860fa49d4891a7ff5aa6de0854b97796d1570c9002c1029"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.1: the closure statistic, carried from the successor unchanged.
BUDGET = 1.0e-6
REFERENCE_FLOOR = 1.0e-14
STRUCTURAL_SCALE = 1.0e-4
ANNIHILATION_TOLERANCE = 1.0e-14
IDEMPOTENCE_TOLERANCE = 1.0e-15
MATCHED_START_TOLERANCE = 1.0e-15
NULL_FLOOR = 1.0e-11

# Section 2.2: the split statistic and its declared reading rules.
SPLIT_LEVELS = (1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1)
SUPERSPLIT_LEVEL = 1.0
ORIENTATION_COMPARABILITY = 0.05
LEVEL_RATIO = 10.0
READABLE_FLOOR = 1.0e-13
FIT_BAND = 2.0
EXPONENT_LOW = 0.9
EXPONENT_HIGH = 1.1
JUMP_FACTOR = 3.0
MONOTONE_TOLERANCE = 1.5
MIN_READABLE = 4
SATURATION_CAP = 0.25
OPERAND_FLOOR_GATE = 0.05
OPERAND_FLOOR_TRANSPORT = 0.10

# Section 2.4: the step rule is the successor's, the sweep schedule is declared as literals.
STEP_CANDIDATES = (0.05, 0.02, 0.01)
STEP_SAFETY = 40.0
SPLIT_DT = 0.02
SPLIT_HORIZON = 2.0
SPLIT_STEPS = 100
REPLICATION_DT = 0.02
REPLICATION_HORIZON = 36.66172105812361
REPLICATION_STEPS = 1834
SHORT_DT = 0.05
SHORT_HORIZON = 0.3666172105812361
SHORT_STEPS = 8

# Section 6: budget.
STEP_CAP_PER_EXECUTION = 50000
STEP_BUDGET_TOTAL = 6000
DECLARED_EXECUTIONS = 19
PROJECTED_SECONDS = 5.0

PROFILE = "on_ray"
MODES = (1,)
ALPHA = 0.25
SEED_IMBALANCE = 0.05

# The canonical pair is (carrier, exterior), so its exterior axis is 1, while the carrier
# state is (carrier, orientation, exterior, loop) with exterior axis 2.
CANONICAL_EXTERIOR_AXIS = 1

# Section 4.2: the bit-identity oracles, read from the successor's digest-bound receipt and
# declared here as literals so that the receipt itself is checked against this protocol.
ORACLE_REPLICATION_RHO = 2.622443969747147e-15
ORACLE_NULL_RHO = 8.505827589859918e-17
ORACLE_LAMBDA_MAX = 1.0331312281605476

VERDICT_LABELS = ("PROPORTIONAL", "NONLINEAR", "CLIFF", "INCONCLUSIVE")
CLASS_LABELS = ("BRACKETED", "ABOVE_ALL_LEVELS", "BELOW_ALL_LEVELS", "MIXED")

# Section 5's self-check preview: one declared synthetic coefficient per law shape.
LINEAR_PREVIEW = (1.0e-2,)


def digest_of(relative_path: str) -> str:
    with open(os.path.join(ROOT, relative_path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def protocol_text() -> str:
    with open(os.path.join(ROOT, PROTOCOL_PATH), encoding="utf-8") as handle:
        return handle.read()


def protocol_body_digest() -> str:
    """Section 0's binding of the frozen text: everything from "## 1." to "## 8.".

    Both ends are matched at the start of a line, because section 0 names both headings in
    prose and an unanchored search would find that prose first.
    """
    text = protocol_text()
    start = re.search(BODY_START, text).start()
    end = re.search(BODY_END, text).start()
    return hashlib.sha256(text[start:end].encode("utf-8")).hexdigest()


def protocol_row(key: str) -> str:
    """Read one `| `key` | value |` row of the protocol's declared tables."""
    pattern = re.compile(r"\|\s*`" + re.escape(key) + r"`\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(protocol_text())
    if match is None:
        raise KeyError("the protocol declares no row for {0}".format(key))
    return match.group(1).strip().strip("`")


def declared_number(key: str) -> float:
    return float(protocol_row(key).replace(",", "").split()[0].strip("$="))


def declared_tuple(key: str) -> tuple:
    return tuple(
        float(token)
        for token in re.findall(r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?", protocol_row(key))
    )


def check_binding(expect_body: str = None, expect_probe: str = None) -> dict:
    """Refuse to run on any hash mismatch, before any arm is constructed."""
    problems = []
    declared = {
        "frozen_body_sha256": protocol_row("frozen_body_sha256"),
        "executor_sha256": protocol_row("executor_sha256"),
        "bound_module_sha256": protocol_row("bound_module_sha256"),
        "base_probe_sha256": protocol_row("base_probe_sha256"),
        "base_receipt_sha256": protocol_row("base_receipt_sha256"),
    }
    observed = {
        "frozen_body_sha256": protocol_body_digest(),
        "executor_sha256": digest_of(PROBE_PATH),
        "bound_module_sha256": digest_of(BOUND_MODULE),
        "base_probe_sha256": digest_of(BASE_PROBE),
        "base_receipt_sha256": digest_of(BASE_RECEIPT),
    }
    if declared["frozen_body_sha256"] != FROZEN_BODY_DIGEST:
        problems.append(
            "the protocol body digest and this executor's constant disagree: {0} vs {1}".format(
                declared["frozen_body_sha256"], FROZEN_BODY_DIGEST
            )
        )
    for key in declared:
        if declared[key] != observed[key]:
            problems.append(
                "binding mismatch on {0}: the protocol declares {1}, the tree holds {2}".format(
                    key, declared[key], observed[key]
                )
            )
    if expect_body is not None and observed["frozen_body_sha256"] != expect_body:
        problems.append(
            "disturbed binding on frozen_body_sha256: expected {0}, observed {1}".format(
                expect_body, observed["frozen_body_sha256"]
            )
        )
    if expect_probe is not None and observed["executor_sha256"] != expect_probe:
        problems.append(
            "disturbed binding on executor_sha256: expected {0}, observed {1}".format(
                expect_probe, observed["executor_sha256"]
            )
        )
    if problems:
        for problem in problems:
            print("REFUSING TO RUN: {0}".format(problem))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"declared": declared, "observed": observed}


def load_base():
    """Import the successor probe, converting its own binding refusal into this one's."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import verify_loop_carrier_projection_relaxation as base
    except SystemExit:
        print("REFUSING TO RUN: the successor probe's binding of the frozen operators failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return base


class SplitSpec:
    """One declared arm of section 3."""

    def __init__(
        self,
        index: int,
        name: str,
        family: str,
        delta_g: float,
        delta_u: float,
        orientation_split: float,
        levels_index: int,
        modes: tuple = MODES,
        alpha: float = ALPHA,
        seed_imbalance: float = SEED_IMBALANCE,
        carries_j: bool = True,
        horizon_key: str = "split",
    ):
        self.index = index
        self.name = name
        self.family = family
        self.delta_g = delta_g
        self.delta_u = delta_u
        self.orientation_split = orientation_split
        self.levels_index = levels_index
        self.modes = modes
        self.alpha = alpha
        self.seed_imbalance = seed_imbalance
        self.carries_j = carries_j
        self.horizon_key = horizon_key
        self.dt = 0.0
        self.steps = 0
        self.horizon = 0.0

    @property
    def is_supersplit(self) -> bool:
        return self.family in ("supersplit_gate", "supersplit_transport")

    def declared_schedule(self) -> tuple:
        """Section 2.4: the sweep is uniform; the two supersplits take the rule's output."""
        if self.horizon_key == "replication":
            return REPLICATION_DT, REPLICATION_HORIZON, REPLICATION_STEPS
        if self.horizon_key == "short":
            return SHORT_DT, SHORT_HORIZON, SHORT_STEPS
        return SPLIT_DT, SPLIT_HORIZON, SPLIT_STEPS


def build_arm_table() -> tuple:
    arms = [
        SplitSpec(1, "common_reference", "reference", 0.0, 0.0, 0.0, -1),
        SplitSpec(2, "successor_replication", "reference", 0.0, 0.0, 0.0, -1,
                  horizon_key="replication"),
        SplitSpec(3, "uniform_short", "reference", 0.0, 0.0, 0.0, -1, modes=(),
                  alpha=0.0, seed_imbalance=0.0, carries_j=False, horizon_key="short"),
        SplitSpec(4, "null", "reference", 0.0, 0.0, 0.0, -1, modes=(), alpha=0.0,
                  seed_imbalance=0.0, carries_j=False, horizon_key="short"),
    ]
    index = 5
    for position, level in enumerate(SPLIT_LEVELS):
        arms.append(SplitSpec(index, "gate_split_{0}".format(position + 1), "gate", level,
                              0.0, 0.0, position))
        index += 1
    arms.append(SplitSpec(index, "supersplit_gate", "supersplit_gate", SUPERSPLIT_LEVEL,
                          0.0, 0.0, -1))
    index += 1
    for position, level in enumerate(SPLIT_LEVELS):
        arms.append(SplitSpec(index, "transport_split_{0}".format(position + 1), "transport",
                              0.0, level, 0.0, position))
        index += 1
    arms.append(SplitSpec(index, "supersplit_transport", "supersplit_transport", 0.0,
                          SUPERSPLIT_LEVEL, 0.0, -1))
    index += 1
    arms.append(SplitSpec(index, "orientation_split_005", "comparability", 0.0, 0.0,
                          ORIENTATION_COMPARABILITY, -1))
    return tuple(arms)


ARM_TABLE = build_arm_table()
GATE_LEVELS = tuple(arm for arm in ARM_TABLE if arm.family == "gate")
TRANSPORT_LEVELS = tuple(arm for arm in ARM_TABLE if arm.family == "transport")


def proxy_arm(spec: SplitSpec, base):
    """The `base.Arm` that carries the arm's seed and its effective gate for the step rule."""
    return base.Arm(
        spec.index, spec.name, PROFILE, spec.modes, spec.alpha, "mode", base.N_CHI, False,
        base.EXCHANGE, 0.0, spec.delta_g, "mode", "", "", spec.carries_j,
        spec.seed_imbalance,
    )


def initial_state(spec: SplitSpec, base) -> np.ndarray:
    return base.initial_carrier(proxy_arm(spec, base))


def gate_rate_of(state: np.ndarray, base) -> np.ndarray:
    """The gate rate of the state's own projection, as a column to broadcast over the loop."""
    e = base.projection(state)
    return base.gate_rate(e[0], e[1])[:, None]


def split_rhs(state: np.ndarray, rate: np.ndarray, spec: SplitSpec, base) -> np.ndarray:
    """The successor's (LB6) right-hand side with the two declared splits applied.

    Transport: every carrier keeps the successor's shared operators except its exterior
    velocity, which becomes U (1 +- delta_u) for delta_u on the two carriers. Gate: the
    conversion field becomes kappa (1 +- delta_g cos chi), the sign following the carrier,
    so the two carriers' gates are offset by the declared relative amount. At zero split
    this is the successor's right-hand side term for term.
    """
    dchi = base.loop_dx(state.shape[base.LOOP_AXIS])
    if spec.orientation_split:
        velocity = np.array(
            (base.U - spec.orientation_split, base.U + spec.orientation_split),
            dtype=np.float64,
        )[None, :, None, None]
    else:
        velocity = np.array(
            (base.U * (1.0 + spec.delta_u), base.U * (1.0 - spec.delta_u)),
            dtype=np.float64,
        )[:, None, None, None]
    out = (
        -velocity * base.frozen.derivative(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        + base.D_X * base.frozen.laplacian(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        - base.SIGNS * base.OMEGA * base.frozen.derivative(state, base.LOOP_AXIS, dchi)
        + base.D_LOOP * base.frozen.laplacian(state, base.LOOP_AXIS, dchi)
        + base.EXCHANGE * (state[:, ::-1] - state)
    )
    cosine = np.cos(base.loop_grid(state.shape[base.LOOP_AXIS]))[None, :]
    kappa_y = rate * (1.0 + spec.delta_g * cosine)
    kappa_i = rate * (1.0 - spec.delta_g * cosine)
    out[0] += kappa_y * (-state[0] + base.PHI * state[1])
    out[1] += kappa_i * (state[0] - base.PHI * state[1])
    return out


def split_step(state: np.ndarray, dt: float, spec: SplitSpec, base) -> np.ndarray:
    return base.rk4_step(state, dt, lambda current: split_rhs(
        current, gate_rate_of(current, base), spec, base
    ))


def state_reading(state: np.ndarray, e: np.ndarray, spec: SplitSpec, base) -> dict:
    e_loop = base.projection(state)
    scale = max(1.0, float(np.max(np.abs(e))))
    magnitude = max(float(np.max(np.abs(state))), 1.0)
    dchi = base.loop_dx(state.shape[base.LOOP_AXIS])
    rate = base.gate_rate(e_loop[0], e_loop[1])[:, None]
    cosine = np.cos(base.loop_grid(state.shape[base.LOOP_AXIS]))[None, :]
    gate_field = rate * (1.0 + spec.delta_g * cosine)
    return {
        "rho": float(np.max(np.abs(e_loop - e)) / scale),
        "annihilation": max(
            float(np.max(np.abs(
                base.frozen.derivative(state, base.LOOP_AXIS, dchi).sum(
                    axis=base.LOOP_AXIS)
            ))) / magnitude,
            float(np.max(np.abs(
                base.frozen.laplacian(state, base.LOOP_AXIS, dchi).sum(
                    axis=base.LOOP_AXIS)
            ))) / magnitude,
        ),
        "idempotence": base.relative_residual(
            base.projection(base.lift(e_loop, state.shape[base.LOOP_AXIS])), e_loop
        ),
        "min_state": float(np.min(state)),
        "min_projection": float(np.min(e_loop)),
        "q_min": float(np.min(base.frozen.bounded_q(e_loop[0], e_loop[1]))),
        "q_max": float(np.max(base.frozen.bounded_q(e_loop[0], e_loop[1]))),
        "gate_field_peak": float(np.max(gate_field)),
        "loop_content": float(
            np.max(np.abs(state - state.mean(axis=base.LOOP_AXIS, keepdims=True)))
        ),
    }


def split_operands(spec: SplitSpec, base, state: np.ndarray) -> dict:
    """Section 4.3: the t=0 operands each split axis acts on, read before any integration.

    The gate axis acts on loop content correlated with cos chi, and the transport axis on
    the exterior gradient of the projected densities. Both are read on the initial state.
    """
    grid = base.loop_grid(state.shape[base.LOOP_AXIS])
    deviation = state - state.mean(axis=base.LOOP_AXIS, keepdims=True)
    local_mean = state.mean(axis=base.LOOP_AXIS)
    correlated = (deviation * np.cos(grid)[None, None, None, :]).mean(axis=base.LOOP_AXIS)
    safe = np.where(np.abs(local_mean) > 1.0e-300, local_mean, 1.0)
    e = base.canonical_initial(PROFILE)
    gradient = np.abs(base.frozen.derivative(e, CANONICAL_EXTERIOR_AXIS, base.EXTERIOR_DX))
    return {
        "gate_operand": float(np.max(np.abs(correlated / safe))),
        "transport_operand": float(np.max(gradient)),
        "orientation_operand": float(np.max(gradient)),
    }


def run_arm(spec: SplitSpec, base) -> dict:
    state = initial_state(spec, base)
    reference = base.canonical_initial(PROFILE)
    matched_start = float(np.max(np.abs(base.projection(state) - reference)))
    operands = split_operands(spec, base, state)

    dt, horizon, steps = spec.declared_schedule()
    if spec.is_supersplit:
        lam_max = base.arm_lambda_max(proxy_arm(spec, base), base.gate_rate(
            *base.exterior_densities(PROFILE)))
        dt = base.step_size(lam_max)
        steps = int(round(horizon / dt))
    else:
        lam_max = base.arm_lambda_max(
            proxy_arm(spec, base), base.gate_rate(*base.exterior_densities(PROFILE))
        )
    conformant = dt <= 1.0 / (STEP_SAFETY * lam_max) and dt in STEP_CANDIDATES

    times, rho, annihilation, idempotence = [], [], [], []
    min_state, min_projection, q_min, q_max, loop_content = [], [], [], [], []
    current = state
    for index in range(steps + 1):
        reading = state_reading(current, reference, spec, base)
        times.append(index * dt)
        rho.append(reading["rho"])
        annihilation.append(reading["annihilation"])
        idempotence.append(reading["idempotence"])
        min_state.append(reading["min_state"])
        min_projection.append(reading["min_projection"])
        q_min.append(reading["q_min"])
        q_max.append(reading["q_max"])
        loop_content.append(reading["loop_content"])
        if index == steps:
            break
        current = split_step(current, dt, spec, base)
        reference = base.canonical_step(reference, dt)

    rho = np.array(rho)
    return {
        "index": spec.index,
        "name": spec.name,
        "family": spec.family,
        "declared": {
            "delta_g": spec.delta_g,
            "delta_u": spec.delta_u,
            "orientation_split": spec.orientation_split,
            "modes": list(spec.modes),
            "alpha": spec.alpha,
            "seed_imbalance": spec.seed_imbalance,
            "levels_index": spec.levels_index,
        },
        "schedule": {
            "dt": dt,
            "horizon": horizon,
            "steps": steps,
            "lambda_max": lam_max,
            "rule_conformant": bool(conformant),
        },
        "operands": operands,
        "matched_start": matched_start,
        "rho_max": float(np.max(rho)),
        "rho_final": float(rho[-1]),
        "rho_max_time": float(times[int(np.argmax(rho))]),
        "steps_recorded": int(steps + 1),
        "annihilation_max": float(np.max(annihilation)),
        "idempotence_max": float(np.max(idempotence)),
        "min_state": float(np.min(min_state)),
        "min_projection": float(np.min(min_projection)),
        "q_min": float(np.min(q_min)),
        "q_max": float(np.max(q_max)),
        "loop_content_initial": float(loop_content[0]),
        "loop_content_final": float(loop_content[-1]),
        "class": "within_budget" if float(np.max(rho)) <= BUDGET else "above_budget",
        "saturated": bool(float(np.max(rho)) > SATURATION_CAP),
    }


def fit_law(levels: tuple, readings: tuple) -> dict:
    pairs = [(level, value) for level, value in zip(levels, readings)
             if value > READABLE_FLOOR]
    if len(pairs) < 2:
        return {
            "readable": len(pairs),
            "coefficient": None,
            "exponent": None,
            "ratios": [],
            "fitted_levels": [pair[0] for pair in pairs],
        }
    x = np.array([pair[0] for pair in pairs], dtype=np.float64)
    y = np.array([pair[1] for pair in pairs], dtype=np.float64)
    coefficient = float(np.sum(x * y) / np.sum(x * x))
    exponent = float(np.polyfit(np.log(x), np.log(y), 1)[0])
    ratios = [float(value / (coefficient * level)) for level, value in pairs]
    return {
        "readable": len(pairs),
        "coefficient": coefficient,
        "exponent": exponent,
        "ratios": ratios,
        "fitted_levels": [pair[0] for pair in pairs],
    }


def law_label(levels: tuple, readings: tuple) -> dict:
    """Section 5.2, on the declared levels and readings alone."""
    fit = fit_law(levels, readings)
    readable = [(level, value) for level, value in zip(levels, readings)
                if value > READABLE_FLOOR]
    reasons = []
    if fit["readable"] < MIN_READABLE:
        reasons.append(
            "only {0} of {1} levels are readable above {2}".format(
                fit["readable"], len(levels), READABLE_FLOOR
            )
        )
        return {"label": "INCONCLUSIVE", "fit": fit, "reasons": reasons}
    values = [pair[1] for pair in readable]
    monotone = all(
        values[index + 1] * MONOTONE_TOLERANCE >= values[index]
        for index in range(len(values) - 1)
    )
    jumps = [
        float(values[index + 1] / values[index])
        for index in range(len(values) - 1)
    ]
    implied_jump = LEVEL_RATIO ** fit["exponent"]
    cliff = any(jump >= JUMP_FACTOR * implied_jump for jump in jumps)
    in_band = all(1.0 / FIT_BAND <= ratio <= FIT_BAND for ratio in fit["ratios"])
    exponent_in_band = EXPONENT_LOW <= fit["exponent"] <= EXPONENT_HIGH
    if not monotone:
        reasons.append("the response is not monotone over the readable levels")
        label = "INCONCLUSIVE"
    elif in_band and exponent_in_band:
        reasons.append(
            "every readable level is within the factor {0} of the fitted line and the "
            "fitted exponent is {1}".format(FIT_BAND, fit["exponent"])
        )
        label = "PROPORTIONAL"
    elif cliff:
        reasons.append(
            "an adjacent pair grows by at least {0} x the growth the fitted exponent {1} "
            "implies".format(JUMP_FACTOR, fit["exponent"])
        )
        label = "CLIFF"
    else:
        reasons.append(
            "monotone but off the fitted line: exponent {0}, ratios {1}".format(
                fit["exponent"], fit["ratios"]
            )
        )
        label = "NONLINEAR"
    return {"label": label, "fit": fit, "reasons": reasons, "jumps": jumps,
            "monotone": monotone}


def class_of_levels(readings: tuple) -> dict:
    within = [index for index, value in enumerate(readings) if value <= BUDGET]
    above = [index for index, value in enumerate(readings) if value > BUDGET]
    if within and above:
        label = "BRACKETED"
    elif above and not within:
        label = "ABOVE_ALL_LEVELS"
    elif within and not above:
        label = "BELOW_ALL_LEVELS"
    else:
        label = "MIXED"
    return {"label": label, "within": within, "above": above,
            "smallest_above": (min(above) if above else None)}


def combined_class(gate: dict, transport: dict) -> str:
    if gate["label"] == transport["label"] == "BRACKETED":
        return "BRACKETED"
    if gate["label"] == transport["label"] == "ABOVE_ALL_LEVELS":
        return "ABOVE_ALL_LEVELS"
    if gate["label"] == transport["label"] == "BELOW_ALL_LEVELS":
        return "BELOW_ALL_LEVELS"
    return "MIXED"


def decide(gate_readings: tuple, transport_readings: tuple) -> dict:
    gate = law_label(SPLIT_LEVELS, gate_readings)
    transport = law_label(SPLIT_LEVELS, transport_readings)
    gate_class = class_of_levels(gate_readings)
    transport_class = class_of_levels(transport_readings)
    crossing = {}
    for name, fit in (("gate", gate["fit"]), ("transport", transport["fit"])):
        coefficient = fit["coefficient"]
        crossing[name] = (
            None if not coefficient else float(BUDGET / coefficient)
        )
    return {
        "gate_label": gate["label"],
        "transport_label": transport["label"],
        "gate": gate,
        "transport": transport,
        "gate_class": gate_class,
        "transport_class": transport_class,
        "class_verdict": combined_class(gate_class, transport_class),
        "crossing": crossing,
    }


def gate_rows(arms: dict, oracle: dict, operands: dict, budget: dict) -> list:
    """Section 4.1: every gate with its reading and its declared bound."""
    reference = arms["common_reference"]
    replication = arms["successor_replication"]
    null_a = arms["uniform_short"]
    null_b = arms["null"]
    supersplit_gate = arms["supersplit_gate"]
    supersplit_transport = arms["supersplit_transport"]
    worst_annihilation = max(arm["annihilation_max"] for arm in arms.values())
    worst_idempotence = max(arm["idempotence_max"] for arm in arms.values())
    worst_matched_start = max(arm["matched_start"] for arm in arms.values())
    min_state = min(arm["min_state"] for arm in arms.values())
    min_projection = min(arm["min_projection"] for arm in arms.values())
    q_min = min(arm["q_min"] for arm in arms.values())
    q_max = max(arm["q_max"] for arm in arms.values())
    rows = [
        {
            "index": 1,
            "name": "source binding",
            "measured": "frozen_body_and_executor_and_sources",
            "bound": "exact",
            "passed": True,
            "detail": {
                "frozen_body": protocol_body_digest(),
                "executor": digest_of(PROBE_PATH),
                "bound_module": digest_of(BOUND_MODULE),
                "base_probe": digest_of(BASE_PROBE),
                "base_receipt": digest_of(BASE_RECEIPT),
            },
        },
        {
            "index": 2,
            "name": "discrete annihilation",
            "measured": float(worst_annihilation),
            "bound": ANNIHILATION_TOLERANCE,
            "passed": bool(worst_annihilation <= ANNIHILATION_TOLERANCE),
        },
        {
            "index": 3,
            "name": "projection idempotence",
            "measured": float(worst_idempotence),
            "bound": IDEMPOTENCE_TOLERANCE,
            "passed": bool(worst_idempotence <= IDEMPOTENCE_TOLERANCE),
        },
        {
            "index": 4,
            "name": "matched start",
            "measured": float(worst_matched_start),
            "bound": MATCHED_START_TOLERANCE,
            "passed": bool(worst_matched_start <= MATCHED_START_TOLERANCE),
        },
        {
            "index": 5,
            "name": "finite and nonnegative",
            "measured": {"min_state": float(min_state),
                         "min_projection": float(min_projection),
                         "q_min": float(q_min), "q_max": float(q_max)},
            "bound": "every scalar finite, f >= 0, 0 <= q < 1",
            "passed": bool(
                min_state >= 0.0 and min_projection >= 0.0 and 0.0 <= q_min
                and q_max < 1.0 and np.isfinite(worst_annihilation)
            ),
        },
        {
            "index": 6,
            "name": "schedule conformance",
            "measured": {
                "non_conformant_arms": [arm["name"] for arm in arms.values()
                                        if not arm["schedule"]["rule_conformant"]],
                "step_sizes": sorted({arm["schedule"]["dt"] for arm in arms.values()}),
            },
            "bound": "dt <= 1/(40 lambda_max), dt in {0.05, 0.02, 0.01}",
            "passed": bool(all(arm["schedule"]["rule_conformant"]
                               for arm in arms.values())),
        },
        {
            "index": 7,
            "name": "declared shape",
            "measured": budget,
            "bound": {"executions": DECLARED_EXECUTIONS,
                      "steps_per_execution": STEP_CAP_PER_EXECUTION,
                      "steps_total": STEP_BUDGET_TOTAL},
            "passed": bool(
                budget["executions"] == DECLARED_EXECUTIONS
                and budget["steps_total"] <= STEP_BUDGET_TOTAL
                and budget["steps_max"] <= STEP_CAP_PER_EXECUTION
            ),
        },
        {
            "index": 8,
            "name": "reference at the floor",
            "measured": float(reference["rho_max"]),
            "bound": REFERENCE_FLOOR,
            "passed": bool(reference["rho_max"] <= REFERENCE_FLOOR),
        },
        {
            "index": 9,
            "name": "witness floor, null pair",
            "measured": {"uniform_short": float(null_a["rho_max"]),
                         "null": float(null_b["rho_max"]),
                         "delta": float(abs(null_a["rho_max"] - null_b["rho_max"]))
                         if null_a["rho_max"] != null_b["rho_max"] else 0.0},
            "bound": NULL_FLOOR,
            "passed": bool(
                null_a["rho_max"] <= NULL_FLOOR and null_b["rho_max"] <= NULL_FLOOR
                and null_a["rho_max"] == null_b["rho_max"]
            ),
        },
        {
            "index": 10,
            "name": "cross-executor oracle",
            "measured": {"successor_replication": float(replication["rho_max"]),
                         "successor_receipt": oracle["replication"],
                         "uniform_short": float(null_a["rho_max"]),
                         "successor_receipt_null": oracle["null"]},
            "bound": "bit-identical to the successor receipt's reading",
            "passed": bool(
                replication["rho_max"] == oracle["replication"]
                and null_a["rho_max"] == oracle["null"]
            ),
        },
        {
            "index": 11,
            "name": "can-fail control",
            "measured": {"supersplit_gate": float(supersplit_gate["rho_max"]),
                         "supersplit_transport": float(supersplit_transport["rho_max"])},
            "bound": STRUCTURAL_SCALE,
            "passed": bool(
                supersplit_gate["rho_max"] > STRUCTURAL_SCALE
                and supersplit_transport["rho_max"] > STRUCTURAL_SCALE
            ),
        },
        {
            "index": 12,
            "name": "split reachability, read before execution",
            "measured": operands,
            "bound": {"gate_operand": OPERAND_FLOOR_GATE,
                      "transport_operand": OPERAND_FLOOR_TRANSPORT},
            "passed": bool(
                operands["gate_operand"] >= OPERAND_FLOOR_GATE
                and operands["transport_operand"] >= OPERAND_FLOOR_TRANSPORT
            ),
        },
        {
            "index": 13,
            "name": "process declaration",
            "measured": {"executions": budget["executions"], "processes": 1},
            "bound": "one process, no concurrent run",
            "passed": True,
        },
    ]
    return rows


def read_oracle() -> dict:
    """Section 4.2: the two bit-identity oracles, read from the successor's receipt.

    The receipt is digest-bound, and its two readings are checked against the literals this
    protocol declares, so an oracle cannot drift silently with the receipt.
    """
    with open(os.path.join(ROOT, BASE_RECEIPT), encoding="utf-8") as handle:
        receipt = json.load(handle)
    arms = {arm["name"]: arm for arm in receipt["arms"]}
    replication = float(arms["mode1_long"]["rho_max"])
    null = float(arms["uniform_short"]["rho_max"])
    null_second = float(arms["null"]["rho_max"])
    if replication != ORACLE_REPLICATION_RHO or null != ORACLE_NULL_RHO:
        print("REFUSING TO RUN: the successor receipt holds {0} and {1} where this protocol "
              "declares {2} and {3}".format(replication, null, ORACLE_REPLICATION_RHO,
                                            ORACLE_NULL_RHO))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    if null != null_second:
        print("REFUSING TO RUN: the successor's null pair does not agree with itself")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"replication": replication, "null": null,
            "lambda_max": float(arms["mode1_long"]["lambda_max"])}


def execute() -> int:
    started = time.time()
    binding = check_binding()
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        print("REFUSING TO RUN: {0} already exists; the stopping rule allows no second "
              "invocation on a recorded result".format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    base = load_base()
    oracle = read_oracle()

    arms = {}
    for spec in ARM_TABLE:
        arm = run_arm(spec, base)
        arms[spec.name] = arm
        print("{0:<26} rho_max {1:.12e} class {2:>13} dt {3} steps {4}".format(
            spec.name, arm["rho_max"], arm["class"], arm["schedule"]["dt"],
            arm["schedule"]["steps"],
        ))

    budget = {
        "executions": len(arms),
        "steps_total": int(sum(arm["schedule"]["steps"] for arm in arms.values())),
        "steps_max": int(max(arm["schedule"]["steps"] for arm in arms.values())),
        "per_execution_cap": STEP_CAP_PER_EXECUTION,
        "total_cap": STEP_BUDGET_TOTAL,
        "declared_executions": DECLARED_EXECUTIONS,
    }
    gate_readings = tuple(arms[arm.name]["rho_max"] for arm in GATE_LEVELS)
    transport_readings = tuple(arms[arm.name]["rho_max"] for arm in TRANSPORT_LEVELS)
    operands = arms["common_reference"]["operands"]
    rows = gate_rows(arms, oracle, operands, budget)
    decision = decide(gate_readings, transport_readings)
    features = {
        "D1": bool(rows[7]["passed"]),
        "D2": bool(rows[8]["passed"]),
        "D3": bool(rows[10]["passed"]),
        "D4": bool(rows[11]["passed"]),
        "D5": bool(rows[9]["passed"]),
        "D6": bool(decision["gate_label"] != "INCONCLUSIVE"
                   and decision["transport_label"] != "INCONCLUSIVE"),
    }
    passed = all(row["passed"] for row in rows)
    status = "PASS" if passed else "FAIL"
    verdicts = {
        "degradation_gate": decision["gate_label"] if passed else None,
        "degradation_transport": decision["transport_label"] if passed else None,
        "class": decision["class_verdict"] if passed else None,
    }
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "invocation": {
            "command": INVOCATION,
            "bound_seconds": BOUND_SECONDS,
            "runtime_seconds": time.time() - started,
        },
        "frozen_sources": {
            "protocol": {"path": PROTOCOL_PATH,
                         "sha256": binding["observed"]["frozen_body_sha256"]},
            "probe": {"path": PROBE_PATH,
                      "sha256": binding["observed"]["executor_sha256"]},
            "bound_module": {"path": BOUND_MODULE,
                             "sha256": binding["observed"]["bound_module_sha256"]},
            "base_probe": {"path": BASE_PROBE,
                           "sha256": binding["observed"]["base_probe_sha256"]},
            "base_receipt": {"path": BASE_RECEIPT,
                             "sha256": binding["observed"]["base_receipt_sha256"]},
        },
        "binding": binding,
        "gates": rows,
        "features": features,
        "arms": arms,
        "sweep": {
            "gate": {
                "levels": list(SPLIT_LEVELS),
                "readings": list(gate_readings),
                "classes": [arms[arm.name]["class"] for arm in GATE_LEVELS],
                "fit": decision["gate"]["fit"],
                "reasons": decision["gate"]["reasons"],
                "crossing": decision["crossing"]["gate"],
                "boundary": decision["gate_class"],
            },
            "transport": {
                "levels": list(SPLIT_LEVELS),
                "readings": list(transport_readings),
                "classes": [arms[arm.name]["class"] for arm in TRANSPORT_LEVELS],
                "fit": decision["transport"]["fit"],
                "reasons": decision["transport"]["reasons"],
                "crossing": decision["crossing"]["transport"],
                "boundary": decision["transport_class"],
            },
            "comparability": {
                "arm": "orientation_split_005",
                "delta": ORIENTATION_COMPARABILITY,
                "readings": {"orientation_split_005":
                             arms["orientation_split_005"]["rho_max"]},
            },
        },
        "controls": {
            "reference": arms["common_reference"]["rho_max"],
            "oracle": oracle,
            "supersplit_gate": arms["supersplit_gate"]["rho_max"],
            "supersplit_transport": arms["supersplit_transport"]["rho_max"],
            "null_pair": [arms["uniform_short"]["rho_max"], arms["null"]["rho_max"]],
        },
        "budget": budget,
        "verdicts": verdicts,
        "runtime_seconds": time.time() - started,
    }
    receipt["invocation"]["runtime_seconds"] = receipt["runtime_seconds"]

    path = os.path.join(ROOT, RECEIPT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(status)
    for name in ("degradation_gate", "degradation_transport", "class"):
        print("{0}: {1}".format(name, verdicts[name]))
    print("runtime_seconds: {0}".format(receipt["runtime_seconds"]))
    return EXIT_PASS if passed else EXIT_FAIL


def self_check() -> int:
    """Static and derivation checks; no arm is integrated and no receipt is written."""
    problems = []
    print("self-check: binding")
    check_binding()
    base = load_base()

    print("self-check: the arm table against section 3")
    names = [arm.name for arm in ARM_TABLE]
    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        problems.append("the arm table holds {0} arms, the protocol declares {1}".format(
            len(ARM_TABLE), DECLARED_EXECUTIONS))
    if len(set(names)) != len(names):
        problems.append("duplicate arm names in the table")
    for name in names:
        if name not in protocol_text():
            problems.append("the protocol's section 3 does not name the arm {0}".format(name))
    if len(GATE_LEVELS) != len(SPLIT_LEVELS) or len(TRANSPORT_LEVELS) != len(SPLIT_LEVELS):
        problems.append("the two axes do not carry one arm per declared level")
    for arm in GATE_LEVELS + TRANSPORT_LEVELS:
        if arm.delta_g and arm.delta_u:
            problems.append("{0} splits both axes at once".format(arm.name))
    if not any(arm.family == "supersplit_gate" for arm in ARM_TABLE):
        problems.append("the gate can-fail control is missing")
    if not any(arm.family == "supersplit_transport" for arm in ARM_TABLE):
        problems.append("the transport can-fail control is missing")
    print("self-check: the declared constants against the protocol and the successor")
    declared_checks = (
        ("budget", BUDGET),
        ("reference_floor", REFERENCE_FLOOR),
        ("structural_scale", STRUCTURAL_SCALE),
        ("annihilation_tolerance", ANNIHILATION_TOLERANCE),
        ("idempotence_tolerance", IDEMPOTENCE_TOLERANCE),
        ("matched_start_tolerance", MATCHED_START_TOLERANCE),
        ("null_floor", NULL_FLOOR),
        ("readable_floor", READABLE_FLOOR),
        ("fit_band", FIT_BAND),
        ("exponent_low", EXPONENT_LOW),
        ("exponent_high", EXPONENT_HIGH),
        ("jump_factor", JUMP_FACTOR),
        ("monotone_tolerance", MONOTONE_TOLERANCE),
        ("min_readable", MIN_READABLE),
        ("saturation_cap", SATURATION_CAP),
        ("operand_floor_gate", OPERAND_FLOOR_GATE),
        ("operand_floor_transport", OPERAND_FLOOR_TRANSPORT),
        ("split_dt", SPLIT_DT),
        ("split_horizon", SPLIT_HORIZON),
        ("split_steps", SPLIT_STEPS),
        ("replication_dt", REPLICATION_DT),
        ("replication_horizon", REPLICATION_HORIZON),
        ("replication_steps", REPLICATION_STEPS),
        ("short_dt", SHORT_DT),
        ("short_horizon", SHORT_HORIZON),
        ("short_steps", SHORT_STEPS),
        ("step_safety", STEP_SAFETY),
        ("step_cap_per_execution", STEP_CAP_PER_EXECUTION),
        ("step_budget_total", STEP_BUDGET_TOTAL),
        ("declared_executions", DECLARED_EXECUTIONS),
        ("bound_seconds", BOUND_SECONDS),
    )
    for key, value in declared_checks:
        try:
            declared = declared_number(key)
        except (KeyError, ValueError) as error:
            problems.append("the protocol's constant table misses {0}: {1}".format(key, error))
            continue
        if abs(declared - float(value)) > 0.0:
            problems.append("constant {0}: protocol {1} vs executor {2}".format(
                key, declared, value))
    if declared_tuple("split_levels") != SPLIT_LEVELS:
        problems.append("the protocol's split levels are not the executor's")
    for label, mine, successor in (
        ("budget", BUDGET, base.BUDGET),
        ("null_floor", NULL_FLOOR, base.NULL_FLOOR),
        ("structural_scale", STRUCTURAL_SCALE, base.STRUCTURAL_SCALE),
        ("step_safety", STEP_SAFETY, base.STEP_SAFETY),
        ("annihilation_tolerance", ANNIHILATION_TOLERANCE, base.ANNIHILATION_TOLERANCE),
        ("idempotence_tolerance", IDEMPOTENCE_TOLERANCE, base.IDEMPOTENCE_TOLERANCE),
        ("matched_start_tolerance", MATCHED_START_TOLERANCE, base.MATCHED_START_TOLERANCE),
    ):
        if float(mine) != float(successor):
            problems.append(
                "the carried threshold {0} is {1}, the successor's is {2}".format(
                    label, mine, successor)
            )
    if tuple(base.STEP_CANDIDATES) != STEP_CANDIDATES:
        problems.append("the step candidates differ from the successor's")

    print("self-check: the step rule on the declared arms, without integrating")
    zero = [arm for arm in ARM_TABLE if arm.name == "common_reference"][0]
    reference_kappa = base.gate_rate(*base.exterior_densities(PROFILE))
    reference_lambda = base.arm_lambda_max(proxy_arm(zero, base), reference_kappa)
    if reference_lambda != ORACLE_LAMBDA_MAX:
        problems.append(
            "the reference arm's step-rule input is {0}, the successor recorded {1}".format(
                reference_lambda, ORACLE_LAMBDA_MAX)
        )
    for arm in ARM_TABLE:
        lam_max = base.arm_lambda_max(proxy_arm(arm, base), reference_kappa)
        dt, horizon, steps = arm.declared_schedule()
        if arm.is_supersplit:
            if not (base.step_size(lam_max) <= 1.0 / (STEP_SAFETY * lam_max)):
                problems.append("the rule's own step fails the safety factor on {0}".format(
                    arm.name))
            continue
        if dt > 1.0 / (STEP_SAFETY * lam_max):
            problems.append(
                "the declared step {0} on {1} violates the safety factor at lambda "
                "{2}".format(dt, arm.name, lam_max)
            )
        if dt != base.step_size(lam_max):
            problems.append(
                "the rule would take a different step on {0}: {1} against the declared "
                "{2}".format(arm.name, base.step_size(lam_max), dt)
            )
        if abs(horizon - SPLIT_HORIZON) > 0.0 and arm.horizon_key == "split":
            problems.append("{0} does not carry the declared horizon".format(arm.name))
        if arm.horizon_key == "split" and steps != SPLIT_STEPS:
            problems.append("{0} does not carry the declared step count".format(arm.name))

    print("self-check: the split reduces to the successor's right-hand side")
    state = initial_state(zero, base)
    rate = gate_rate_of(state, base)
    mine = split_rhs(state, rate, zero, base)
    theirs = base.carrier_rhs(state, rate, proxy_arm(zero, base))
    if not np.array_equal(mine, theirs):
        problems.append("the zero-split right-hand side is not the successor's")
    orientation = [arm for arm in ARM_TABLE if arm.name == "orientation_split_005"][0]
    successor_arm = base.Arm(999, "oracle", PROFILE, MODES, ALPHA, "mode", base.N_CHI,
                             False, base.EXCHANGE, ORIENTATION_COMPARABILITY, 0.0, "mode",
                             "", "", True, SEED_IMBALANCE)
    mine_orientation = split_rhs(state, rate, orientation, base)
    theirs_orientation = base.carrier_rhs(state, rate, successor_arm)
    if not np.array_equal(mine_orientation, theirs_orientation):
        problems.append("the orientation split is not the successor's own split geometry")
    if not np.all(np.isfinite(mine)):
        problems.append("the split right-hand side is not finite on the initial state")

    print("self-check: reachability, controls, and the decision tree")
    operands = split_operands(zero, base, state)
    if operands["gate_operand"] < OPERAND_FLOOR_GATE:
        problems.append("the gate operand {0} is below its floor".format(
            operands["gate_operand"]))
    if operands["transport_operand"] < OPERAND_FLOOR_TRANSPORT:
        problems.append("the transport operand {0} is below its floor".format(
            operands["transport_operand"]))
    proportional = tuple(LINEAR_PREVIEW[0] * level for level in SPLIT_LEVELS)
    nonlinear = tuple(LINEAR_PREVIEW[0] * level ** 2 for level in SPLIT_LEVELS)
    cliff = tuple(
        LINEAR_PREVIEW[0] * level for level in SPLIT_LEVELS[:4]
    ) + tuple(
        LINEAR_PREVIEW[0] * SPLIT_LEVELS[3] * 100.0 * (level / SPLIT_LEVELS[4])
        for level in SPLIT_LEVELS[4:]
    )
    tiny = tuple(1.0e-16 for _ in SPLIT_LEVELS)
    labels = {
        "proportional": law_label(SPLIT_LEVELS, proportional)["label"],
        "nonlinear": law_label(SPLIT_LEVELS, nonlinear)["label"],
        "cliff": law_label(SPLIT_LEVELS, cliff)["label"],
        "unreadable": law_label(SPLIT_LEVELS, tiny)["label"],
    }
    if labels["proportional"] != "PROPORTIONAL":
        problems.append("the decision tree cannot read a proportional law: {0}".format(
            labels["proportional"]))
    if labels["nonlinear"] != "NONLINEAR":
        problems.append("the decision tree cannot read a quadratic law: {0}".format(
            labels["nonlinear"]))
    if labels["cliff"] != "CLIFF":
        problems.append("the decision tree cannot read a cliff: {0}".format(labels["cliff"]))
    if labels["unreadable"] != "INCONCLUSIVE":
        problems.append("the decision tree cannot read an unreadable sweep")
    for name, readings, expected in (
        ("bracketed", (1.0e-9, 1.0e-8, 1.0e-7, 1.0e-5, 1.0e-4, 1.0e-3), "BRACKETED"),
        ("above", tuple(1.0e-3 for _ in SPLIT_LEVELS), "ABOVE_ALL_LEVELS"),
        ("below", tuple(1.0e-12 for _ in SPLIT_LEVELS), "BELOW_ALL_LEVELS"),
    ):
        observed = class_of_levels(readings)["label"]
        if observed != expected:
            problems.append(
                "the class boundary reads {0} where the sweep is {1}".format(observed, name))
    for label in VERDICT_LABELS:
        if label not in labels.values():
            problems.append("the verdict {0} is unreachable in the self-check".format(label))

    print("self-check: status=FAIL is reachable")
    fake = {
        "common_reference": {"rho_max": 1.0e-16, "annihilation_max": 1.0e-15,
                             "idempotence_max": 1.0e-16, "matched_start": 1.0e-16,
                             "min_state": 0.1, "min_projection": 0.1, "q_min": 0.0,
                             "q_max": 0.5, "schedule": {"rule_conformant": True,
                                                        "dt": 0.02, "steps": 100},
                             "operands": {"gate_operand": 0.125,
                                          "transport_operand": 0.22,
                                          "orientation_operand": 0.22}},
        "successor_replication": {"rho_max": 1.0e-15, "annihilation_max": 1.0e-15,
                                  "idempotence_max": 1.0e-16, "matched_start": 1.0e-16,
                                  "min_state": 0.1, "min_projection": 0.1, "q_min": 0.0,
                                  "q_max": 0.5, "schedule": {"rule_conformant": True,
                                                             "dt": 0.02, "steps": 100},
                                  "operands": {}},
        "uniform_short": {"rho_max": 8.5e-17, "annihilation_max": 1.0e-15,
                          "idempotence_max": 1.0e-16, "matched_start": 1.0e-16,
                          "min_state": 0.1, "min_projection": 0.1, "q_min": 0.0,
                          "q_max": 0.5, "schedule": {"rule_conformant": True,
                                                     "dt": 0.05, "steps": 8},
                          "operands": {}},
        "null": {"rho_max": 8.5e-17, "annihilation_max": 1.0e-15,
                 "idempotence_max": 1.0e-16, "matched_start": 1.0e-16, "min_state": 0.1,
                 "min_projection": 0.1, "q_min": 0.0, "q_max": 0.5,
                 "schedule": {"rule_conformant": True, "dt": 0.05, "steps": 8},
                 "operands": {}},
        "supersplit_gate": {"rho_max": 1.0e-16, "annihilation_max": 1.0e-15,
                            "idempotence_max": 1.0e-16, "matched_start": 1.0e-16,
                            "min_state": 0.1, "min_projection": 0.1, "q_min": 0.0,
                            "q_max": 0.5, "schedule": {"rule_conformant": True,
                                                       "dt": 0.02, "steps": 100},
                            "operands": {}},
        "supersplit_transport": {"rho_max": 1.0e-1, "annihilation_max": 1.0e-15,
                                 "idempotence_max": 1.0e-16, "matched_start": 1.0e-16,
                                 "min_state": 0.1, "min_projection": 0.1, "q_min": 0.0,
                                 "q_max": 0.5, "schedule": {"rule_conformant": True,
                                                            "dt": 0.02, "steps": 100},
                                 "operands": {}},
    }
    budget = {"executions": DECLARED_EXECUTIONS, "steps_total": 100,
              "steps_max": 100, "per_execution_cap": STEP_CAP_PER_EXECUTION,
              "total_cap": STEP_BUDGET_TOTAL, "declared_executions": DECLARED_EXECUTIONS}
    silent = gate_rows(fake, {"replication": 1.0e-15, "null": 8.5e-17},
                       fake["common_reference"]["operands"], budget)
    if all(row["passed"] for row in silent):
        problems.append("a silent can-fail control still passes every gate")
    if not problems:
        print("self-check: every gate above can fail, so the run can end at status=FAIL")

    print("self-check: the refusal path fires on a disturbed binding")
    for flag, value in (("--expect-frozen-body", "0" * 64),
                        ("--expect-executor", "0" * 64)):
        completed = subprocess.run(
            [sys.executable, os.path.join(HERE, os.path.basename(PROBE_PATH)), flag, value],
            cwd=ROOT, capture_output=True, text=True,
        )
        if completed.returncode != EXIT_PRE_EXECUTION_BLOCK:
            problems.append(
                "{0} exited {1}, not the refusal code {2}".format(
                    flag, completed.returncode, EXIT_PRE_EXECUTION_BLOCK)
            )
        if "disturbed binding on" not in completed.stdout:
            problems.append(
                "{0} did not refuse on the disturbance itself: {1}".format(
                    flag, completed.stdout.strip().splitlines()[-1:] or "")
            )
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        problems.append("the self-check wrote a receipt")

    if problems:
        for problem in problems:
            print("SELF-CHECK FAILURE: {0}".format(problem))
        return EXIT_STATIC_CHECK
    print("SELF-CHECK PASS")
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-check", action="store_true",
                        help="run the static and derivation checks and stop")
    parser.add_argument("--expect-frozen-body", default=None,
                        help="refuse unless the protocol body hashes to this value")
    parser.add_argument("--expect-executor", default=None,
                        help="refuse unless this executor hashes to this value")
    arguments = parser.parse_args(argv)
    if arguments.self_check:
        return self_check()
    if arguments.expect_frozen_body or arguments.expect_executor:
        check_binding(expect_body=arguments.expect_frozen_body,
                      expect_probe=arguments.expect_executor)
        print("REFUSING TO RUN: the expectation flags are for the self-check only")
        return EXIT_PRE_EXECUTION_BLOCK
    return execute()


if __name__ == "__main__":
    sys.exit(main())
