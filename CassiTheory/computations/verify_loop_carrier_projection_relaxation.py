"""Execute the frozen loop-carrier projection relaxation schedule.

Protocol: computations/loop-carrier-projection-relaxation-prereg.md (sections 1-6).
Invocation: timeout 1200 python computations/verify_loop_carrier_projection_relaxation.py
Receipt: runs/loop_carrier_projection_relaxation/verification.json

The script takes no command-line arguments. Every threshold, horizon rule, step rule,
initial profile, seed and arm below is a copy of the protocol, and the frozen discrete
operators and rate constants are imported from the module the protocol binds by digest.

The thirteen closure arms of protocol section 3.1 are the spent protocol's own closure
arms, re-declared by this protocol with the same names, profiles, seeds, mode content,
step sizes and horizons, so every construction function below that they use is the spent
probe's construction unchanged; the three relaxation arms of section 3.2 add the effective
gate field (LR-A0), the peak witness (LR-W), the relaxation statistic (LR2), the arm
bracket (LR3) and the scale-stable identity (LR4).
"""

from __future__ import annotations

import cmath
import hashlib
import json
import math
import os
import platform
import sys
import time
from dataclasses import dataclass

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

BOUND_MODULE = "computations/verify_loop_to_bubble_projection.py"
BOUND_DIGEST = "d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1"
PROTOCOL_PATH = "computations/loop-carrier-projection-relaxation-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_projection_relaxation.py"
RECEIPT_PATH = "runs/loop_carrier_projection_relaxation/verification.json"
INVOCATION = "timeout 1200 python computations/verify_loop_carrier_projection_relaxation.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-projection-relaxation.v1"
BOUND_SECONDS = 1200.0
DECLARED_EXECUTIONS = 16
EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4


def digest_of(relative_path: str) -> str:
    with open(os.path.join(ROOT, relative_path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def bind_frozen_module():
    """Protocol section 4 gate 1: accept the operator module only at its frozen digest."""
    observed = digest_of(BOUND_MODULE)
    if observed != BOUND_DIGEST:
        raise SystemExit(
            "source binding failed for {0}\n  expected {1}\n  observed {2}\n"
            "The probe reads the frozen operators rather than reimplementing them and "
            "fails closed if that file changes.".format(BOUND_MODULE, BOUND_DIGEST, observed)
        )
    import verify_loop_to_bubble_projection as frozen

    expected_constants = {
        "PHI": (1.0 + math.sqrt(5.0)) / 2.0,
        "NX": 7,
        "NCHI": 12,
        "U": 0.31,
        "D_X": 0.17,
        "R": 1.7,
        "V": 0.8,
        "D_ELL": 0.13,
        "EXCHANGE": 0.6,
        "LAM": 0.04,
        "TOL": 1.0e-11,
    }
    for name, value in expected_constants.items():
        if getattr(frozen, name) != value:
            raise SystemExit(
                "bound module disagrees with the protocol table at {0}: {1} != {2}".format(
                    name, getattr(frozen, name), value
                )
            )
    return frozen


frozen = bind_frozen_module()

PHI = frozen.PHI
U = frozen.U
D_X = frozen.D_X
EXCHANGE = frozen.EXCHANGE
LAM = frozen.LAM
OMEGA = frozen.OMEGA
D_LOOP = frozen.D_LOOP

# Protocol section 1.2 item 2: exterior grid stays at the frozen N_x, loop grid at 24.
N_X = frozen.NX
N_CHI = 24
N_CHI_TRUNCATED = frozen.NCHI
LOOP_AXIS = 3
EXTERIOR_AXIS = 2
EXTERIOR_DX = 2.0 * math.pi / N_X
SIGNS = np.array((1.0, -1.0))[None, :, None, None]

# Protocol section 2.1: exterior modulation and the composition of each declared profile.
MODULATION = 0.20
PROFILES = {
    "off_ray": (0.90, 1.40),
    "on_ray": (1.10, 1.10 / PHI),
    "open_gate": (0.35, 0.35 / PHI),
    "closed_gate": (5.00, 5.00 / PHI),
}

# Protocol section 3.1: declared seed amplitude.
MODE_AMPLITUDE = 0.25

# Protocol section 2.2: the three declared frozen rules.
STEP_CANDIDATES = (0.05, 0.02, 0.01)
STEP_SAFETY = 40.0
HORIZON_CAP = 1000.0
CONVERGENCE_PRODUCT = 10.0
SHORT_FRACTION = 100.0

# Protocol section 4: integrity thresholds and the declared control parameters.
BUDGET = 1.0e-6
STRUCTURAL_SCALE = 1.0e-4
REFINEMENT_FACTOR = 4.0
WITNESS_FLOOR = 1.0e-4
ANNIHILATION_TOLERANCE = 1.0e-14
IDEMPOTENCE_TOLERANCE = 1.0e-15
MATCHED_START_TOLERANCE = 1.0e-15
SPECTRUM_TOLERANCE = 1.0e-9
NULL_FLOOR = 1.0e-11
IDENTITY_TOLERANCE = 1.0e-12
D0_FLOOR = 1.0e-6
C_MIN_FLOOR = 1.0e-6
C_MAX_CEIL = 1.0
GATE_COVARIANCE_FACTOR = 0.5
GATE_SCALE_REFERENCE = 1.0
GATE_SCALE_HALVED = 0.5
VELOCITY_SPLIT = 0.05
ZERO_EXCHANGE = 0.0

# Protocol section 2.2: the relaxation statistic (LR2) and its two clauses (LR-R1, LR-R2).
FIT_WINDOW_START = 0.5
FIT_FLOOR = 1.0e-12
FIT_MIN_SAMPLES = 50
BRACKET_LOW = 0.9
BRACKET_HIGH = 1.1
SCALED_RATIO_LOW = 0.45
SCALED_RATIO_HIGH = 0.55

# Protocol section 1.2 item 6: the declared seeds. (LR-A3) applies the direction imbalance
# beta = 0.05 to every J-carrying arm; the seed invariance is checked at the initial state.
SEED_IMBALANCE = 0.05
SEED_INVARIANCE_TOLERANCE = 1.0e-15

# Protocol section 6: declared step budget.
STEP_CAP_PER_EXECUTION = 50000
STEP_BUDGET_TOTAL = 290000

# Protocol section 1.3: the thirteen closure arms carry the spent protocol's own step counts,
# summed by section 6 to 132334; the three relaxation arms carry 50000 each.
CLOSURE_STEPS = 132334

# Frozen comparison table of the protocol's own arm tables (sections 3.1 and 3.2),
# transcribed here so the derived schedule can be checked against them. Columns: index,
# name, profile, loop content, rate change, horizon label, grid label.
EXPECTED_ARMS = (
    (1, "off_ray", "off_ray", "uniform", "-", "convergence", "7x24"),
    (2, "off_ray_refined", "off_ray", "uniform", "-", "convergence", "7x24 dt/2"),
    (3, "on_ray", "on_ray", "uniform", "-", "convergence", "7x24"),
    (4, "on_ray_refined", "on_ray", "uniform", "-", "convergence", "7x24 dt/2"),
    (5, "open_gate", "open_gate", "uniform", "-", "convergence", "7x24"),
    (6, "closed_gate", "closed_gate", "uniform", "-", "convergence", "7x24"),
    (7, "loop_truncated", "on_ray", "uniform", "-", "convergence", "7x12"),
    (8, "mode1_short", "on_ray", "mode 1", "-", "short", "7x24"),
    (9, "mode1_long", "on_ray", "mode 1", "-", "mode", "7x24"),
    (10, "mode2_long", "on_ray", "mode 2", "-", "mode", "7x24"),
    (11, "uniform_short", "on_ray", "uniform", "-", "short", "7x24"),
    (12, "null", "on_ray", "uniform", "-", "short", "7x24"),
    (13, "persistent_current", "on_ray", "mode 1", "r = 0", "mode_zero_exchange", "7x24"),
    (14, "relax_reference", "on_ray", "mode 1,2", "s = 1", "relaxation", "7x24"),
    (15, "relax_scaled", "on_ray", "mode 1,2", "s = 1/2", "relaxation", "7x24"),
    (16, "relax_split", "on_ray", "mode 1", "u split", "relaxation", "7x24"),
)

# Frozen readings of the derived schedule. The thirteen closure arms take the spent
# receipt's own figures for the same constructions; the three relaxation arms take the
# declared consequences of section 2.4. Lambda_max is frozen where the spent receipt or the
# step rule of section 2.4 fixes it; for the relaxation arms the step rule's outcome is
# checked instead, since section 2.4 declares dt = 0.02 without quoting lambda_max.
# Columns: index, dt, horizon, steps, lambda_max, mode set.
EXPECTED_SPEC = (
    (1, 0.05, 332.745257, 6655, 0.345366227, ()),
    (2, 0.025, 332.745257, 13310, 0.345366227, ()),
    (3, 0.05, 1000.0, 20000, 0.345366227, ()),
    (4, 0.025, 1000.0, 40000, 0.345366227, ()),
    (5, 0.05, 210.946802, 4219, 0.345366227, ()),
    (6, 0.05, 1000.0, 20000, 0.345366227, ()),
    (7, 0.05, 1000.0, 20000, 0.345366227, ()),
    (8, 0.02, 0.366617, 19, 1.033131228, (1,)),
    (9, 0.02, 36.661721, 1834, 1.033131228, (1,)),
    (10, 0.02, 36.661721, 1834, 0.795860689, (2,)),
    (11, 0.05, 0.366617, 8, 0.345366227, ()),
    (12, 0.05, 0.366617, 8, 0.345366227, ()),
    (13, 0.05, 222.307692, 4447, 0.060912592, (1,)),
    (14, 0.02, 1000.0, 50000, None, (1, 2)),
    (15, 0.02, 1000.0, 50000, None, (1, 2)),
    (16, 0.02, 1000.0, 50000, None, (1,)),
)

# Protocol section 2.4: the declared consequences of the step rule for the three relaxation
# arms. The step rule must select 0.02 and must not have been free to select 0.05.
RELAXATION_ARMS = ("relax_reference", "relax_scaled", "relax_split")


@dataclass(frozen=True)
class Arm:
    index: int
    name: str
    profile: str
    modes: tuple
    alpha: float
    horizon_key: str
    n_chi: int
    refined: bool
    exchange: float
    velocity_split: float
    gate_covariance: float
    role: str
    refinement_partner: str
    counterpart: str
    carries_j: bool
    seed_imbalance: float = 0.0
    composition_split: bool = False
    gate_scale: float = 1.0


# Protocol sections 3.1 and 3.2: the sixteen declared arms. The trailing fields carry the
# declared seeds of section 1.2 item 6 and the declared gate scale s of (LR-A0): the
# direction imbalance beta = 0.05 on the J-carrying arms, the composition asymmetry on the
# two covariance arms, the halved scale on the scaled arm and the plain gate on the split arm.
ARM_TABLE = (
    Arm(1, "off_ray", "off_ray", (), 0.0, "convergence", N_CHI, False, EXCHANGE, 0.0, 0.0,
        "contract", "off_ray_refined", "", False),
    Arm(2, "off_ray_refined", "off_ray", (), 0.0, "convergence", N_CHI, True, EXCHANGE, 0.0,
        0.0, "contract", "", "", False),
    Arm(3, "on_ray", "on_ray", (), 0.0, "convergence", N_CHI, False, EXCHANGE, 0.0, 0.0,
        "contract", "on_ray_refined", "", False),
    Arm(4, "on_ray_refined", "on_ray", (), 0.0, "convergence", N_CHI, True, EXCHANGE, 0.0,
        0.0, "contract", "", "", False),
    Arm(5, "open_gate", "open_gate", (), 0.0, "convergence", N_CHI, False, EXCHANGE, 0.0, 0.0,
        "contract", "", "", False),
    Arm(6, "closed_gate", "closed_gate", (), 0.0, "convergence", N_CHI, False, EXCHANGE, 0.0,
        0.0, "contract", "", "", False),
    Arm(7, "loop_truncated", "on_ray", (), 0.0, "convergence", N_CHI_TRUNCATED, False,
        EXCHANGE, 0.0, 0.0, "contract", "", "on_ray", False),
    Arm(8, "mode1_short", "on_ray", (1,), MODE_AMPLITUDE, "short", N_CHI, False, EXCHANGE,
        0.0, 0.0, "mode", "", "uniform_short", False),
    Arm(9, "mode1_long", "on_ray", (1,), MODE_AMPLITUDE, "mode", N_CHI, False, EXCHANGE,
        0.0, 0.0, "mode", "", "uniform_short", True, SEED_IMBALANCE),
    Arm(10, "mode2_long", "on_ray", (2,), MODE_AMPLITUDE, "mode", N_CHI, False, EXCHANGE,
        0.0, 0.0, "mode", "", "uniform_short", True, SEED_IMBALANCE),
    Arm(11, "uniform_short", "on_ray", (), 0.0, "short", N_CHI, False, EXCHANGE, 0.0, 0.0,
        "contract", "", "", False),
    Arm(12, "null", "on_ray", (), 0.0, "short", N_CHI, False, EXCHANGE, 0.0, 0.0,
        "contract", "", "uniform_short", False),
    Arm(13, "persistent_current", "on_ray", (1,), MODE_AMPLITUDE, "mode_zero_exchange",
        N_CHI, False, ZERO_EXCHANGE, 0.0, 0.0, "persistence", "", "", True, SEED_IMBALANCE),
    Arm(14, "relax_reference", "on_ray", (1, 2), MODE_AMPLITUDE, "relaxation", N_CHI, False,
        EXCHANGE, 0.0, GATE_COVARIANCE_FACTOR, "relaxation", "", "", False, 0.0, True,
        GATE_SCALE_REFERENCE),
    Arm(15, "relax_scaled", "on_ray", (1, 2), MODE_AMPLITUDE, "relaxation", N_CHI, False,
        EXCHANGE, 0.0, GATE_COVARIANCE_FACTOR, "relaxation", "", "", False, 0.0, True,
        GATE_SCALE_HALVED),
    Arm(16, "relax_split", "on_ray", (1,), MODE_AMPLITUDE, "relaxation", N_CHI, False,
        EXCHANGE, VELOCITY_SPLIT, 0.0, "relaxation", "", "", False),
)

CONTRACT_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "contract")
MODE_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "mode")
J_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.carries_j)
CLOSURE_ARMS = tuple(
    arm.name for arm in ARM_TABLE if arm.role in ("contract", "mode", "persistence")
)
COVARIANCE_ARMS = ("relax_reference", "relax_scaled")
REFINEMENT_PAIRS = (
    ("off_ray", "off_ray_refined"),
    ("on_ray", "on_ray_refined"),
)


def loop_grid(n_chi: int) -> np.ndarray:
    return 2.0 * math.pi * np.arange(n_chi, dtype=np.float64) / n_chi


def loop_dx(n_chi: int) -> float:
    return 2.0 * math.pi / n_chi


def exterior_densities(profile: str) -> tuple:
    """Protocol section 2.1: E_a(x) = B_a (1 + 0.20 cos x) on the periodic exterior grid."""
    base_y, base_i = PROFILES[profile]
    modulation = 1.0 + MODULATION * np.cos(loop_grid(N_X))
    return base_y * modulation, base_i * modulation


def seed_factors(arm: Arm) -> tuple:
    """Per-carrier loop factors of protocol sections 3.1 and 6A.

    Both carriers share the declared mode factor 1 + alpha cos(m chi). Two declared seeds
    modify that: the composition asymmetry of (A2) gives the Yin carrier the opposite phase
    factor, and the orientation imbalance (A1) is applied by the caller through the sign axis.
    """
    grid = loop_grid(arm.n_chi)
    factor_y = np.ones(arm.n_chi)
    factor_i = np.ones(arm.n_chi)
    for mode in arm.modes:
        carrier_phase = arm.alpha * np.cos(mode * grid)
        factor_y = factor_y * (1.0 + carrier_phase)
        factor_i = factor_i * (
            1.0 + (-carrier_phase if arm.composition_split else carrier_phase)
        )
    return factor_y, factor_i


def initial_carrier(arm: Arm) -> np.ndarray:
    """Protocol sections 3.1 and 6A: the declared seed of one arm.

    f_{a,s}(x, chi) = (E_a/2) [1 + alpha cos(m chi)] (1 + s beta), with the Yin carrier
    taking the opposite phase factor in the composition-asymmetric arm. Identity (A1) makes
    the two orientations sum to the unmodulated total and identity (A2) makes each carrier
    mean one, so the projection reproduces E_a in both cases.
    """
    e_y, e_i = exterior_densities(arm.profile)
    factor_y, factor_i = seed_factors(arm)
    imbalance = np.array(
        (1.0 + arm.seed_imbalance, 1.0 - arm.seed_imbalance), dtype=np.float64
    )
    state = np.empty((2, 2, N_X, arm.n_chi), dtype=np.float64)
    state[0] = (e_y / 2.0)[None, :, None] * factor_y[None, None, :] * imbalance[:, None, None]
    state[1] = (e_i / 2.0)[None, :, None] * factor_i[None, None, :] * imbalance[:, None, None]
    return state


def canonical_initial(profile: str) -> np.ndarray:
    e_y, e_i = exterior_densities(profile)
    return np.stack((e_y, e_i)).astype(np.float64)


def projection(state: np.ndarray) -> np.ndarray:
    """(LB1): E_a(x) = sum_s <f_{a,s}>_chi on the equal-weight loop grid."""
    return state.mean(axis=LOOP_AXIS).sum(axis=1)


def lift(e: np.ndarray, n_chi: int) -> np.ndarray:
    """Re-embed a projection as a chi-uniform carrier state, for gate 3."""
    state = np.empty((2, 2, N_X, n_chi), dtype=np.float64)
    for label in range(2):
        state[label] = (e[label] / 2.0)[None, :, None] * np.ones((1, n_chi))
    return state


def gate_rate(e_y: np.ndarray, e_i: np.ndarray) -> np.ndarray:
    """(LB4)-(LB5): kappa = lambda [1 - q] with q the frozen bounded composition."""
    return LAM * (1.0 - frozen.bounded_q(e_y, e_i))


def gate_profile(state: np.ndarray, arm: Arm) -> np.ndarray:
    """Protocol sections 1.2 item 3 and 1.2 item 5: kappa^eff from the projected densities.

    The result is chi resolved, shape (N_x, N_chi), so it multiplies a carrier component of
    shape (orientation, N_x, N_chi); for a closure arm every loop cell carries one value.
    """
    return effective_gate_field(arm, gate_rate(*channel_densities(state)))


def channel_densities(state: np.ndarray) -> tuple:
    e = projection(state)
    return e[0], e[1]


def effective_gate_field(arm: Arm, rate: np.ndarray) -> np.ndarray:
    """(LR-A0): kappa^eff = s kappa [1 + 0.5 cos chi], with s the arm's declared scale.

    Every closure arm carries s = 1 and no loop variation, so kappa^eff = kappa there; the
    two covariance arms carry the loop-varying factor and the declared scale, and the split
    arm carries kappa^eff = kappa.
    """
    if arm.gate_covariance:
        return arm.gate_scale * rate[:, None] * (
            1.0 + arm.gate_covariance * np.cos(loop_grid(arm.n_chi))
        )[None, :]
    return arm.gate_scale * rate[:, None] * np.ones((1, arm.n_chi))


def slow_rate(mode: int, exchange: float) -> float:
    """(LB38): g_m = d m^2 + r - Re sqrt(r^2 - m^2 Omega^2)."""
    return D_LOOP * mode**2 + exchange - cmath.sqrt(exchange**2 - mode**2 * OMEGA**2).real


def internal_gap(kappa: np.ndarray, exchange: float) -> float:
    """(LB39): min[kappa (1+phi), 2r, d + r - Re sqrt(r^2 - Omega^2)]."""
    return float(
        min(
            float(np.min(kappa)) * (1.0 + PHI),
            2.0 * exchange,
            slow_rate(1, exchange),
        )
    )


def mode_spectrum(mode: int, kappa: float, exchange: float) -> np.ndarray:
    """(LB36) through the frozen generator, so the binding covers the spectrum too."""
    return frozen.closed_spectrum(mode, kappa, exchange, OMEGA, D_LOOP)


def arm_lambda_max(arm: Arm, kappa: np.ndarray) -> float:
    """Protocol section 2.4 (LR-S1): largest |Re Lambda| over the arm's mode content.

    The peak is taken on the arm's own effective field, so the loop-varying factor and the
    declared scale of (LR-A0) enter the step rule exactly as they enter the arm.
    """
    if not arm.modes:
        return max(abs(U) / EXTERIOR_DX, D_X / EXTERIOR_DX**2)
    peak = float(np.max(effective_gate_field(arm, kappa)))
    return float(
        max(
            abs(value.real)
            for mode in arm.modes
            for value in mode_spectrum(mode, peak, arm.exchange)
        )
    )


def step_size(lambda_max: float) -> float:
    """(LR-S1): dt = max{dt in {0.05, 0.02, 0.01} : dt <= 1/(40 lambda_max)}."""
    limit = 1.0 / (STEP_SAFETY * lambda_max)
    for candidate in STEP_CANDIDATES:
        if candidate <= limit:
            return candidate
    raise ValueError("no frozen step size satisfies the safety factor at {0}".format(lambda_max))


def arm_horizon(arm: Arm, kappa: np.ndarray) -> float:
    """(LR-S2), with the internal gap taken on the arm's own effective field.

    A convergence or relaxation arm takes T = min(10/g, 1000) with g its internal gap
    (LB39); the mode arms take their own declared counterparts, as section 3.1 re-declares.
    """
    if arm.horizon_key in ("convergence", "relaxation"):
        gap = internal_gap(np.ravel(effective_gate_field(arm, kappa)), arm.exchange)
        return min(CONVERGENCE_PRODUCT / gap, HORIZON_CAP)
    if arm.horizon_key == "mode":
        return min(CONVERGENCE_PRODUCT / slow_rate(1, EXCHANGE), HORIZON_CAP)
    if arm.horizon_key == "short":
        return min(CONVERGENCE_PRODUCT / slow_rate(1, EXCHANGE), HORIZON_CAP) / SHORT_FRACTION
    if arm.horizon_key == "mode_zero_exchange":
        return min(CONVERGENCE_PRODUCT / slow_rate(1, ZERO_EXCHANGE), HORIZON_CAP)
    raise ValueError("undeclared horizon key {0}".format(arm.horizon_key))


def carrier_rhs(state: np.ndarray, kappa: np.ndarray, arm: Arm) -> np.ndarray:
    """(LB6) with the frozen operators: exterior and loop transport, exchange, conversion."""
    dchi = loop_dx(state.shape[LOOP_AXIS])
    if arm.velocity_split:
        velocity = np.array(
            (U - arm.velocity_split, U + arm.velocity_split), dtype=np.float64
        )[None, :, None, None]
    else:
        velocity = U
    out = (
        -velocity * frozen.derivative(state, EXTERIOR_AXIS, EXTERIOR_DX)
        + D_X * frozen.laplacian(state, EXTERIOR_AXIS, EXTERIOR_DX)
        - SIGNS * OMEGA * frozen.derivative(state, LOOP_AXIS, dchi)
        + D_LOOP * frozen.laplacian(state, LOOP_AXIS, dchi)
        + arm.exchange * (state[:, ::-1] - state)
    )
    out[0] += kappa * (-state[0] + PHI * state[1])
    out[1] += kappa * (state[0] - PHI * state[1])
    return out


def canonical_rhs(e: np.ndarray, kappa: np.ndarray) -> np.ndarray:
    """(LB7): the canonical pair driven by the projected gate."""
    epsilon = e[0] - PHI * e[1]
    return np.stack(
        (
            -U * frozen.derivative(e[0], 0, EXTERIOR_DX)
            + D_X * frozen.laplacian(e[0], 0, EXTERIOR_DX)
            - kappa * epsilon,
            -U * frozen.derivative(e[1], 0, EXTERIOR_DX)
            + D_X * frozen.laplacian(e[1], 0, EXTERIOR_DX)
            + kappa * epsilon,
        )
    )


def rk4_step(state: np.ndarray, dt: float, rhs) -> np.ndarray:
    """Classical RK4 in float64, the integrator both arms share (protocol section 1.2)."""
    k1 = rhs(state)
    k2 = rhs(state + 0.5 * dt * k1)
    k3 = rhs(state + 0.5 * dt * k2)
    k4 = rhs(state + dt * k3)
    return state + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)


def carrier_step(state: np.ndarray, dt: float, arm: Arm) -> np.ndarray:
    return rk4_step(state, dt, lambda s: carrier_rhs(s, gate_profile(s, arm), arm))


def canonical_step(e: np.ndarray, dt: float) -> np.ndarray:
    return rk4_step(
        e,
        dt,
        lambda current: canonical_rhs(current, gate_rate(current[0], current[1])),
    )


def relative_residual(value: np.ndarray, reference: np.ndarray) -> float:
    """max|value - reference| against max(1, max|reference|)."""
    return float(
        np.max(np.abs(value - reference)) / max(1.0, float(np.max(np.abs(reference))))
    )


def loop_mode_energies(state: np.ndarray, modes: tuple) -> dict:
    """Per-mode energy of the loop content, used for the spectrum re-check and the slope."""
    deviation = state - state.mean(axis=LOOP_AXIS, keepdims=True)
    spectra = np.fft.rfft(deviation, axis=LOOP_AXIS)
    energies = {}
    for mode in modes:
        energies[mode] = float(np.sum(np.abs(spectra[..., mode]) ** 2))
    return energies


def current_averages(state: np.ndarray) -> tuple:
    """<H>_chi(x) from (LB40)-(LB44), in its domain mean and its max-abs reduction."""
    h = (state[:, 0].sum(axis=0) - state[:, 1].sum(axis=0)).mean(axis=1)
    return float(np.mean(h)), float(np.max(np.abs(h)))


def covariance_parts(state: np.ndarray, arm: Arm) -> tuple:
    """The two sides of (LB14) at one state, with Z(chi) = sum_s [f_Ys - phi f_Is].

    The left side is <kappa^eff Z>_chi and the right side is <kappa^eff>_chi eps +
    (kappa^eff - <kappa^eff>_chi) Z, both evaluated on the arm's own effective field, so the
    identity is read on the field the arm actually evolves.
    """
    e = projection(state)
    epsilon = e[0] - PHI * e[1]
    z = state[0, 0] + state[0, 1] - PHI * (state[1, 0] + state[1, 1])
    kappa = effective_gate_field(arm, gate_rate(e[0], e[1]))
    mean_kappa = kappa.mean(axis=1)
    left = float(np.mean(kappa * z))
    right = float(
        np.mean(
            mean_kappa[:, None] * epsilon[:, None] + (kappa - mean_kappa[:, None]) * z
        )
    )
    return left, right


def identity_residual(state: np.ndarray, arm: Arm) -> float:
    """(LR4): the absolute residual of the discrete form of (LB14) at one accepted state.

    The protocol measures this residual against the declared t0 operand scale D_0 rather
    than against the state's own decaying operand, so the reading cannot improve as the arm
    relaxes the very content the identity is read on.
    """
    left, right = covariance_parts(state, arm)
    return abs(left - right)


def spectrum_check(arm: Arm, kappa: float) -> float:
    """Gate 9: the frozen generator against the closed form of (LB36) at the arm's kappa."""
    residual = 0.0
    for mode in arm.modes:
        generator = frozen.mode_generator(mode, kappa, arm.exchange, OMEGA, D_LOOP)
        numeric = np.linalg.eigvals(generator)
        residual = max(
            residual,
            frozen.multiset_residual(numeric, mode_spectrum(mode, kappa, arm.exchange)),
        )
    return float(residual)


@dataclass
class ArmSpec:
    arm: Arm
    dt: float
    horizon: float
    steps: int
    lambda_max: float
    kappa_mean: float
    kappa_min: float
    kappa_max: float
    gap: float
    gap_at_mean_gate: float
    c_minus: float
    c_plus: float
    ell: float
    operand_scale: float
    operand_raw: float


def arm_bracket(arm: Arm, kappa: np.ndarray) -> tuple:
    """(LR3): the arm's conversion bracket on its own effective field."""
    field = effective_gate_field(arm, kappa)
    c_minus = float(np.min(field)) * (1.0 + PHI)
    c_plus = float(np.max(field)) * (1.0 + PHI)
    ell = min(c_minus, 2.0 * arm.exchange, slow_rate(1, arm.exchange))
    return c_minus, c_plus, ell


def operand_scale(arm: Arm, kappa: np.ndarray, state: np.ndarray) -> tuple:
    """(LR4): D_0 = max(1, <kappa^eff>_chi(0) max_chi|Z(0)|), read before execution."""
    field = effective_gate_field(arm, kappa)
    z = state[0, 0] + state[0, 1] - PHI * (state[1, 0] + state[1, 1])
    raw = float(np.max(field.mean(axis=1) * np.max(np.abs(z), axis=1)))
    return max(1.0, raw), raw


def build_spec(arm: Arm) -> ArmSpec:
    initial = canonical_initial(arm.profile)
    kappa = gate_rate(initial[0], initial[1])
    lambda_max = arm_lambda_max(arm, kappa)
    dt = step_size(lambda_max)
    if arm.refined:
        dt = dt / 2.0
    horizon = arm_horizon(arm, kappa)
    c_minus, c_plus, ell = arm_bracket(arm, kappa)
    scale, raw = operand_scale(arm, kappa, initial_carrier(arm))
    return ArmSpec(
        arm=arm,
        dt=dt,
        horizon=horizon,
        steps=int(math.ceil(horizon / dt)),
        lambda_max=lambda_max,
        kappa_mean=float(np.mean(kappa)),
        kappa_min=float(np.min(kappa)),
        kappa_max=float(np.max(kappa)),
        gap=internal_gap(kappa, arm.exchange),
        gap_at_mean_gate=internal_gap(np.array((float(np.mean(kappa)),)), arm.exchange),
        c_minus=c_minus,
        c_plus=c_plus,
        ell=ell,
        operand_scale=scale,
        operand_raw=raw,
    )


@dataclass
class ArmTrace:
    spec: ArmSpec
    times: np.ndarray
    rho: np.ndarray
    proj: np.ndarray
    annihilation: np.ndarray
    idempotence: np.ndarray
    min_state: np.ndarray
    min_projection: np.ndarray
    q_min: np.ndarray
    q_max: np.ndarray
    gate_spread: np.ndarray
    mode_energy: np.ndarray
    per_mode_energy: dict
    current_mean: np.ndarray
    current_max: np.ndarray
    local_error: np.ndarray
    rho_growth: float
    covariance_residual: np.ndarray
    identity_residual: np.ndarray
    matched_start: float


def state_readings(state: np.ndarray, e: np.ndarray, arm: Arm) -> dict:
    """Every per-state reading of sections 2.1, 3.1 and the gates, at one accepted state."""
    n_chi = state.shape[LOOP_AXIS]
    e_loop = projection(state)
    scale = max(1.0, float(np.max(np.abs(e))))
    dchi = loop_dx(n_chi)
    magnitude = max(float(np.max(np.abs(state))), 1.0)
    q = frozen.bounded_q(e_loop[0], e_loop[1])
    local_gate = gate_profile(state, arm)
    mean_current, max_current = current_averages(state)
    readings = {
        "rho": float(np.max(np.abs(e_loop - e)) / scale),
        "projection": e_loop,
        "annihilation": max(
            float(np.max(np.abs(frozen.derivative(state, LOOP_AXIS, dchi).sum(axis=LOOP_AXIS))))
            / magnitude,
            float(
                np.max(np.abs(frozen.laplacian(state, LOOP_AXIS, dchi).sum(axis=LOOP_AXIS)))
            )
            / magnitude,
        ),
        "idempotence": relative_residual(projection(lift(e_loop, n_chi)), e_loop),
        "min_state": float(np.min(state)),
        "min_projection": float(np.min(e_loop)),
        "q_min": float(np.min(q)),
        "q_max": float(np.max(q)),
        "gate_spread": float(
            np.max(np.abs(local_gate - gate_rate(e_loop[0], e_loop[1])[:, None]))
        ),
        "mode_energy": float(
            np.sum((state - state.mean(axis=LOOP_AXIS, keepdims=True)) ** 2)
        ),
        "per_mode_energy": loop_mode_energies(state, arm.modes),
        "current_mean": mean_current,
        "current_max": max_current,
    }
    if arm.role == "relaxation":
        readings["identity_residual"] = identity_residual(state, arm)
    return readings


def run_arm(spec: ArmSpec) -> ArmTrace:
    arm = spec.arm
    n_chi = arm.n_chi
    state = initial_carrier(arm)
    e = canonical_initial(arm.profile)
    matched_start = float(np.max(np.abs(projection(state) - e)))

    times, rho, proj = [], [], []
    annihilation, idempotence = [], []
    min_state, min_projection, q_min, q_max, gate_spread = [], [], [], [], []
    mode_energy, per_mode = [], {mode: [] for mode in arm.modes}
    current_mean, current_max, local_error, covariance_residual = [], [], [], []
    identity_trace = []

    for index in range(spec.steps + 1):
        readings = state_readings(state, e, arm)
        times.append(index * spec.dt)
        rho.append(readings["rho"])
        proj.append(readings["projection"])
        annihilation.append(readings["annihilation"])
        idempotence.append(readings["idempotence"])
        min_state.append(readings["min_state"])
        min_projection.append(readings["min_projection"])
        q_min.append(readings["q_min"])
        q_max.append(readings["q_max"])
        gate_spread.append(readings["gate_spread"])
        mode_energy.append(readings["mode_energy"])
        for mode, value in readings["per_mode_energy"].items():
            per_mode[mode].append(value)
        current_mean.append(readings["current_mean"])
        current_max.append(readings["current_max"])
        if "covariance_identity" in readings:
            covariance_residual.append(readings["covariance_identity"])
        if "identity_residual" in readings:
            identity_trace.append(readings["identity_residual"])

        if index == spec.steps:
            break
        previous_projection = projection(state) if arm.name in CLOSURE_ARMS else None
        state = carrier_step(state, spec.dt, arm)
        e = canonical_step(e, spec.dt)
        if previous_projection is not None:
            advanced = canonical_step(previous_projection, spec.dt)
            local_error.append(relative_residual(advanced, projection(state)))

    growth = float(np.max(np.abs(np.diff(np.array(rho))))) if len(rho) > 1 else 0.0
    return ArmTrace(
        spec=spec,
        times=np.array(times),
        rho=np.array(rho),
        proj=np.array(proj),
        annihilation=np.array(annihilation),
        idempotence=np.array(idempotence),
        min_state=np.array(min_state),
        min_projection=np.array(min_projection),
        q_min=np.array(q_min),
        q_max=np.array(q_max),
        gate_spread=np.array(gate_spread),
        mode_energy=np.array(mode_energy),
        per_mode_energy={k: np.array(v) for k, v in per_mode.items()},
        current_mean=np.array(current_mean),
        current_max=np.array(current_max),
        local_error=np.array(local_error),
        rho_growth=growth,
        covariance_residual=np.array(covariance_residual),
        identity_residual=np.array(identity_trace),
        matched_start=matched_start,
    )


def matched_indices(left: ArmTrace, right: ArmTrace) -> list:
    """States of both traces at equal model time, for the mode-versus-uniform pairing."""
    pairs = []
    for index, time in enumerate(left.times):
        ratio = time / right.spec.dt
        nearest = int(round(ratio))
        if 0 <= nearest < len(right.times) and abs(right.times[nearest] - time) <= 1.0e-9:
            pairs.append((index, nearest))
    return pairs


def paired_delta(left: ArmTrace, right: ArmTrace) -> dict:
    """Relative difference of two projected trajectories on the states they share in time."""
    pairs = matched_indices(left, right)
    values = []
    for first, second in pairs:
        scale = max(1.0, float(np.max(np.abs(right.proj[second]))))
        values.append(
            float(np.max(np.abs(left.proj[first] - right.proj[second])) / scale)
        )
    return {
        "counterpart": right.spec.arm.name,
        "matched_states": len(pairs),
        "delta_max": max(values) if values else None,
        "delta_final": values[-1] if values else None,
    }


def slope_of(values: np.ndarray, times: np.ndarray) -> tuple:
    """Least squares log-slope on the second half of a trace."""
    count = len(values)
    start = count // 2
    window = [
        (times[index], values[index])
        for index in range(start, count)
        if values[index] > 0.0 and math.isfinite(values[index])
    ]
    if len(window) < 5:
        return float("nan"), len(window)
    x = np.array([entry[0] for entry in window])
    y = np.log(np.array([entry[1] for entry in window]))
    slope = float(np.polyfit(x, y, 1)[0])
    return slope, len(window)


def relaxation_fit(trace: ArmTrace) -> dict:
    """(LR2): nu_fit = -slope of ln rho_k on W = {t_k >= T/2, rho_k > 1e-12}.

    The window and the floor are declared in section 2.2 before execution; a window that
    holds fewer than 50 samples is read as no_fit and the arm's rate clause fails there.
    """
    start = FIT_WINDOW_START * trace.spec.horizon
    window = [
        (float(trace.times[index]), float(trace.rho[index]))
        for index in range(len(trace.times))
        if trace.times[index] >= start and trace.rho[index] > FIT_FLOOR
    ]
    reading = {
        "window_start": start,
        "fit_floor": FIT_FLOOR,
        "declared_min_samples": FIT_MIN_SAMPLES,
        "window_samples": len(window),
        "no_fit": bool(len(window) < FIT_MIN_SAMPLES),
        "nu_fit": None,
        "window_first_time": window[0][0] if window else None,
        "window_last_time": window[-1][0] if window else None,
        "window_first_rho": window[0][1] if window else None,
        "window_last_rho": window[-1][1] if window else None,
    }
    if not reading["no_fit"]:
        x = np.array([entry[0] for entry in window])
        y = np.log(np.array([entry[1] for entry in window]))
        reading["nu_fit"] = -float(np.polyfit(x, y, 1)[0])
        reading["nu_fit_over_ell"] = reading["nu_fit"] / trace.spec.ell
    return reading


def relaxation_reading(trace: ArmTrace) -> dict:
    """The peak witness, the bracket, the fitted rate and the clauses of one relaxation arm."""
    spec = trace.spec
    arm = spec.arm
    rho_max = float(np.max(trace.rho))
    peak_index = int(np.argmax(trace.rho))
    fit = relaxation_fit(trace)
    identity_max = (
        float(np.max(trace.identity_residual)) if len(trace.identity_residual) else None
    )
    clauses = ["LR-W"]
    if arm.name in COVARIANCE_ARMS:
        clauses.extend(["LR4", "LR-R1"])
    if arm.gate_scale != GATE_SCALE_REFERENCE:
        clauses.append("LR-R2")
    rate_clause = None
    if "LR-R1" in clauses:
        rate_clause = bool(
            not fit["no_fit"]
            and fit["nu_fit"] is not None
            and BRACKET_LOW * spec.c_minus <= fit["nu_fit"] <= BRACKET_HIGH * spec.c_plus
        )
    return {
        "arm": arm.name,
        "gate_scale": arm.gate_scale,
        "declared_clauses": clauses,
        "rho_max": rho_max,
        "rho_final": float(trace.rho[-1]),
        "rho_peak_time": float(trace.times[peak_index]),
        "witness_floor": WITNESS_FLOOR,
        "witness_fired": bool(rho_max > WITNESS_FLOOR),
        "c_minus": spec.c_minus,
        "c_plus": spec.c_plus,
        "ell": spec.ell,
        "c_minus_floor": C_MIN_FLOOR,
        "c_plus_ceiling": C_MAX_CEIL,
        "operand_scale": spec.operand_scale,
        "operand_raw": spec.operand_raw,
        "identity_residual_max": identity_max,
        "identity_bound": IDENTITY_TOLERANCE * spec.operand_scale,
        "identity_met": (
            None if identity_max is None else bool(identity_max <= IDENTITY_TOLERANCE * spec.operand_scale)
        ),
        "fit": fit,
        "rate_clause": rate_clause,
    }


def arm_row(trace: ArmTrace) -> dict:
    spec = trace.spec
    arm = spec.arm
    return {
        "index": arm.index,
        "name": arm.name,
        "profile": arm.profile,
        "loop_content": (
            "uniform" if not arm.modes else "mode " + ",".join(str(m) for m in arm.modes)
        ),
        "role": arm.role,
        "n_chi": arm.n_chi,
        "alpha": arm.alpha,
        "exchange": arm.exchange,
        "velocity_split": arm.velocity_split,
        "gate_covariance": arm.gate_covariance,
        "dt": spec.dt,
        "horizon": spec.horizon,
        "steps": spec.steps,
        "final_time": float(trace.times[-1]),
        "lambda_max": spec.lambda_max,
        "kappa_initial_min": spec.kappa_min,
        "kappa_initial_mean": spec.kappa_mean,
        "kappa_initial_max": spec.kappa_max,
        "internal_gap": spec.gap,
        "internal_gap_at_mean_gate": spec.gap_at_mean_gate,
        "rho_max": float(np.max(trace.rho)),
        "rho_final": float(trace.rho[-1]),
        "rho_growth_max": trace.rho_growth,
        "annihilation_max": float(np.max(trace.annihilation)),
        "idempotence_max": float(np.max(trace.idempotence)),
        "min_state": float(np.min(trace.min_state)),
        "min_projection": float(np.min(trace.min_projection)),
        "q_min": float(np.min(trace.q_min)),
        "q_max": float(np.max(trace.q_max)),
        "gate_spread_max": float(np.max(trace.gate_spread)),
        "matched_start": trace.matched_start,
        "local_error_max": float(np.max(trace.local_error)) if len(trace.local_error) else None,
        "current_mean_initial": float(trace.current_mean[0]),
        "current_mean_final": float(trace.current_mean[-1]),
        "current_max_initial": float(trace.current_max[0]),
        "current_max_final": float(trace.current_max[-1]),
        "gate_scale": spec.arm.gate_scale,
        "rho_peak_time": float(trace.times[int(np.argmax(trace.rho))]),
        "c_minus": spec.c_minus,
        "c_plus": spec.c_plus,
        "ell": spec.ell,
        "operand_scale": spec.operand_scale,
        "operand_raw": spec.operand_raw,
        "identity_residual_max": (
            float(np.max(trace.identity_residual)) if len(trace.identity_residual) else None
        ),
    }


def mode_reading(trace: ArmTrace, uniform: ArmTrace) -> dict:
    arm = trace.spec.arm
    pairing = paired_delta(trace, uniform)
    per_mode = {}
    for mode in arm.modes:
        series = trace.per_mode_energy[mode]
        initial = series[0]
        ratio = series / initial if initial > 0.0 else series * float("nan")
        slope, window = slope_of(ratio, trace.times)
        target = slow_rate(mode, arm.exchange)
        per_mode[mode] = {
            "g_m": target,
            "energy_ratio_final": float(ratio[-1]),
            "slope": slope,
            "slope_window": window,
            "slope_relative_error": (
                abs(slope + 2.0 * target) / (2.0 * target) if math.isfinite(slope) else None
            ),
            "g_m_times_horizon": target * trace.spec.horizon,
        }
    total = trace.mode_energy / trace.mode_energy[0]
    total_slope, total_window = slope_of(total, trace.times)
    return {
        "arm": arm.name,
        "counterpart": pairing["counterpart"],
        "matched_states": pairing["matched_states"],
        "delta_max": pairing["delta_max"],
        "delta_final": pairing["delta_final"],
        "per_mode": per_mode,
        "total_energy_ratio_final": float(total[-1]),
        "total_slope": total_slope,
        "total_slope_window": total_window,
        "final_mean_at_zero": (
            abs(trace.current_mean[-1] / trace.current_mean[0])
            if trace.current_mean[0] != 0.0
            else None
        ),
        "final_max_at_zero": (
            abs(trace.current_max[-1] / trace.current_max[0])
            if trace.current_max[0] != 0.0
            else None
        ),
    }


def static_check(specs: list) -> dict:
    """Cross-check the derived schedule against the frozen tables before any execution."""
    failures = []

    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        failures.append("arm table has {0} rows".format(len(ARM_TABLE)))
    for arm, expected in zip(ARM_TABLE, EXPECTED_ARMS):
        index, name, profile, content, change, horizon, grid = expected
        if (arm.index, arm.name, arm.profile) != (index, name, profile):
            failures.append("arm {0}: name or profile drift".format(index))
        if arm.horizon_key != horizon:
            failures.append("arm {0}: horizon key drift".format(index))
        if (arm.n_chi == N_CHI_TRUNCATED) != (grid == "7x12"):
            failures.append("arm {0}: resolution drift".format(index))
        if arm.refined != grid.endswith("dt/2"):
            failures.append("arm {0}: refinement drift".format(index))
        if (arm.gate_covariance != 0.0) != change.startswith("s ="):
            failures.append("arm {0}: gate modification drift".format(index))
        if (arm.velocity_split != 0.0) != change.startswith("u"):
            failures.append("arm {0}: velocity modification drift".format(index))
        if (arm.exchange != EXCHANGE) != change.startswith("r ="):
            failures.append("arm {0}: exchange modification drift".format(index))
        if (arm.modes != ()) != (content != "uniform"):
            failures.append("arm {0}: loop content drift".format(index))
        declared_scale = GATE_SCALE_REFERENCE
        if change == "s = 1/2":
            declared_scale = GATE_SCALE_HALVED
        if arm.gate_scale != declared_scale:
            failures.append("arm {0}: gate scale drift".format(index))
    for spec, expected in zip(specs, EXPECTED_SPEC):
        index, dt, horizon, steps, lambda_max, modes = expected
        if spec.arm.index != index:
            failures.append("spec {0}: index drift".format(index))
        if abs(spec.dt - dt) > 0.0:
            failures.append("arm {0}: dt {1} != frozen {2}".format(index, spec.dt, dt))
        if abs(spec.horizon - horizon) > 1.0e-6:
            failures.append(
                "arm {0}: horizon {1} != frozen {2}".format(index, spec.horizon, horizon)
            )
        if spec.steps != steps:
            failures.append("arm {0}: steps {1} != frozen {2}".format(index, spec.steps, steps))
        if lambda_max is not None and abs(spec.lambda_max - lambda_max) > 1.0e-6:
            failures.append(
                "arm {0}: lambda_max {1} != frozen {2}".format(index, spec.lambda_max, lambda_max)
            )
        if tuple(spec.arm.modes) != tuple(modes):
            failures.append("arm {0}: mode set drift".format(index))
        if spec.arm.name in RELAXATION_ARMS:
            limit = 1.0 / (STEP_SAFETY * spec.lambda_max)
            if not dt <= limit < 0.05:
                failures.append(
                    "arm {0}: the step rule's declared outcome does not hold; "
                    "1/(40 lambda_max) = {1}".format(index, limit)
                )

    thresholds = {
        "BUDGET": BUDGET,
        "STRUCTURAL_SCALE": STRUCTURAL_SCALE,
        "REFINEMENT_FACTOR": REFINEMENT_FACTOR,
        "WITNESS_FLOOR": WITNESS_FLOOR,
        "ANNIHILATION_TOLERANCE": ANNIHILATION_TOLERANCE,
        "IDEMPOTENCE_TOLERANCE": IDEMPOTENCE_TOLERANCE,
        "MATCHED_START_TOLERANCE": MATCHED_START_TOLERANCE,
        "SPECTRUM_TOLERANCE": SPECTRUM_TOLERANCE,
        "NULL_FLOOR": NULL_FLOOR,
        "IDENTITY_TOLERANCE": IDENTITY_TOLERANCE,
        "D0_FLOOR": D0_FLOOR,
        "C_MIN_FLOOR": C_MIN_FLOOR,
        "C_MAX_CEIL": C_MAX_CEIL,
        "FIT_WINDOW_START": FIT_WINDOW_START,
        "FIT_FLOOR": FIT_FLOOR,
        "FIT_MIN_SAMPLES": FIT_MIN_SAMPLES,
        "BRACKET_LOW": BRACKET_LOW,
        "BRACKET_HIGH": BRACKET_HIGH,
        "SCALED_RATIO_LOW": SCALED_RATIO_LOW,
        "SCALED_RATIO_HIGH": SCALED_RATIO_HIGH,
        "STEP_SAFETY": STEP_SAFETY,
        "HORIZON_CAP": HORIZON_CAP,
        "CONVERGENCE_PRODUCT": CONVERGENCE_PRODUCT,
        "SHORT_FRACTION": SHORT_FRACTION,
        "MODULATION": MODULATION,
        "MODE_AMPLITUDE": MODE_AMPLITUDE,
        "GATE_COVARIANCE_FACTOR": GATE_COVARIANCE_FACTOR,
        "GATE_SCALE_REFERENCE": GATE_SCALE_REFERENCE,
        "GATE_SCALE_HALVED": GATE_SCALE_HALVED,
        "VELOCITY_SPLIT": VELOCITY_SPLIT,
        "SEED_IMBALANCE": SEED_IMBALANCE,
        "SEED_INVARIANCE_TOLERANCE": SEED_INVARIANCE_TOLERANCE,
    }
    frozen_thresholds = {
        "BUDGET": 1.0e-6,
        "STRUCTURAL_SCALE": 1.0e-4,
        "REFINEMENT_FACTOR": 4.0,
        "WITNESS_FLOOR": 1.0e-4,
        "ANNIHILATION_TOLERANCE": 1.0e-14,
        "IDEMPOTENCE_TOLERANCE": 1.0e-15,
        "MATCHED_START_TOLERANCE": 1.0e-15,
        "SPECTRUM_TOLERANCE": 1.0e-9,
        "NULL_FLOOR": 1.0e-11,
        "IDENTITY_TOLERANCE": 1.0e-12,
        "D0_FLOOR": 1.0e-6,
        "C_MIN_FLOOR": 1.0e-6,
        "C_MAX_CEIL": 1.0,
        "FIT_WINDOW_START": 0.5,
        "FIT_FLOOR": 1.0e-12,
        "FIT_MIN_SAMPLES": 50,
        "BRACKET_LOW": 0.9,
        "BRACKET_HIGH": 1.1,
        "SCALED_RATIO_LOW": 0.45,
        "SCALED_RATIO_HIGH": 0.55,
        "STEP_SAFETY": 40.0,
        "HORIZON_CAP": 1000.0,
        "CONVERGENCE_PRODUCT": 10.0,
        "SHORT_FRACTION": 100.0,
        "MODULATION": 0.20,
        "MODE_AMPLITUDE": 0.25,
        "GATE_COVARIANCE_FACTOR": 0.5,
        "GATE_SCALE_REFERENCE": 1.0,
        "GATE_SCALE_HALVED": 0.5,
        "VELOCITY_SPLIT": 0.05,
        "SEED_IMBALANCE": 0.05,
        "SEED_INVARIANCE_TOLERANCE": 1.0e-15,
    }
    for name, frozen_value in frozen_thresholds.items():
        if thresholds[name] != frozen_value:
            failures.append(
                "threshold {0} is {1}, frozen value is {2}".format(
                    name, thresholds[name], frozen_value
                )
            )

    # Protocol section 6: the declared step budget and the closure figure of section 1.3.
    schedule_constants = {
        "STEP_CAP_PER_EXECUTION": STEP_CAP_PER_EXECUTION,
        "STEP_BUDGET_TOTAL": STEP_BUDGET_TOTAL,
        "CLOSURE_STEPS": CLOSURE_STEPS,
    }
    frozen_schedule_constants = {
        "STEP_CAP_PER_EXECUTION": 50000,
        "STEP_BUDGET_TOTAL": 290000,
        "CLOSURE_STEPS": 132334,
    }
    for name, frozen_value in frozen_schedule_constants.items():
        if schedule_constants[name] != frozen_value:
            failures.append(
                "schedule constant {0} is {1}, declared value is {2}".format(
                    name, schedule_constants[name], frozen_value
                )
            )

    imbalanced = tuple(arm.name for arm in ARM_TABLE if arm.seed_imbalance != 0.0)
    if imbalanced != J_ARMS:
        failures.append(
            "the direction imbalance is declared on {0}, the J-carrying arms are {1}".format(
                list(imbalanced), list(J_ARMS)
            )
        )
    split = tuple(arm.name for arm in ARM_TABLE if arm.composition_split)
    if split != COVARIANCE_ARMS:
        failures.append(
            "the composition asymmetry is declared on {0}, the covariance arms are {1}".format(
                list(split), list(COVARIANCE_ARMS)
            )
        )
    for coarse, refined in REFINEMENT_PAIRS:
        partner = next((arm.refinement_partner for arm in ARM_TABLE if arm.name == coarse), "")
        if partner != refined:
            failures.append(
                "the declared refinement pair {0}/{1} is not in the arm table".format(
                    coarse, refined
                )
            )

    steps_total = int(sum(spec.steps for spec in specs))
    steps_max = int(max(spec.steps for spec in specs))
    steps_closure = int(sum(spec.steps for spec in specs if spec.arm.name in CLOSURE_ARMS))
    if steps_max > STEP_CAP_PER_EXECUTION:
        failures.append(
            "arm {0} needs {1} steps, cap is {2}".format(
                max(specs, key=lambda item: item.steps).arm.name, steps_max,
                STEP_CAP_PER_EXECUTION,
            )
        )
    if steps_total > STEP_BUDGET_TOTAL:
        failures.append(
            "the schedule needs {0} steps, budget is {1}".format(steps_total, STEP_BUDGET_TOTAL)
        )
    if steps_closure != CLOSURE_STEPS:
        failures.append(
            "the thirteen closure arms need {0} steps, section 1.3 declares {1}".format(
                steps_closure, CLOSURE_STEPS
            )
        )

    sample = initial_carrier(
        Arm(0, "seed_sample", "on_ray", (1,), MODE_AMPLITUDE, "mode", N_CHI, False,
            EXCHANGE, 0.0, 0.0, "mode", "", "", False)
    )
    if sample.dtype != np.float64:
        failures.append("carrier state dtype is {0}".format(sample.dtype))
    canonical = canonical_initial("on_ray")
    if canonical.dtype != np.float64:
        failures.append("canonical state dtype is {0}".format(canonical.dtype))
    if frozen.derivative(sample, LOOP_AXIS, loop_dx(N_CHI)).dtype != np.float64:
        failures.append("loop derivative is not float64")
    if not np.array(1.0).dtype == np.dtype("float64"):
        failures.append("numpy default float is not float64")

    # Reachability of the decision tree of section 5, checked on the pure function: a dead
    # instrument must force status=FAIL with no verdict at all, and each live reading must
    # reach the label the tree declares for it.
    dead = aggregate_verdicts(
        closure_features={"G1": False, "G2": False, "G3": False},
        relaxation_features={"H1": False, "H2": False, "H3": False},
        arms=[{"name": "on_ray", "class": "within_budget"}],
        controls_ok=False,
    )
    if dead["status"] != "FAIL" or dead["closure_verdict"] is not None or (
        dead["relaxation_verdict"] is not None
    ):
        failures.append("a dead instrument does not force status=FAIL with no verdict")
    unrealized = aggregate_verdicts(
        closure_features={"G1": False, "G2": True, "G3": True},
        relaxation_features={"H1": True, "H2": True, "H3": True},
        arms=[{"name": "on_ray", "class": "within_budget"}],
        controls_ok=True,
    )
    if unrealized["status"] != "PASS" or unrealized["closure_verdict"] != "INCONCLUSIVE":
        failures.append("a live instrument with an unrealized closure does not read INCONCLUSIVE")
    realized = aggregate_verdicts(
        closure_features={"G1": True, "G2": True, "G3": True},
        relaxation_features={"H1": True, "H2": True, "H3": True},
        arms=[{"name": "on_ray", "class": "within_budget"}],
        controls_ok=True,
    )
    if realized["closure_verdict"] != "EMERGES" or realized["relaxation_verdict"] != "EMERGES":
        failures.append("a fully emergent schedule does not read EMERGES")
    structural = aggregate_verdicts(
        closure_features={"G1": False, "G2": True, "G3": True},
        relaxation_features={"H1": True, "H2": False, "H3": True},
        arms=[{"name": "on_ray", "class": "structural_disagreement"}],
        controls_ok=True,
    )
    if structural["closure_verdict"] != "CONTRADICTS" or (
        structural["relaxation_verdict"] != "CONTRADICTS"
    ):
        failures.append("a structural disagreement does not read CONTRADICTS")

    return {
        "failures": failures,
        "arms": len(ARM_TABLE),
        "closure_arms": list(CLOSURE_ARMS),
        "mode_arms": list(MODE_ARMS),
        "j_arms": list(J_ARMS),
        "covariance_arms": list(COVARIANCE_ARMS),
        "relaxation_arms": list(RELAXATION_ARMS),
        "refinement_pairs": [list(pair) for pair in REFINEMENT_PAIRS],
        "steps_total": steps_total,
        "closure_steps": steps_closure,
        "steps_per_execution_max": steps_max,
        "declared_steps_per_execution_cap": STEP_CAP_PER_EXECUTION,
        "declared_steps_total_budget": STEP_BUDGET_TOTAL,
        "thresholds": thresholds,
        "schedule_constants": schedule_constants,
        "seed_imbalance": SEED_IMBALANCE,
        "imbalanced_arms": list(imbalanced),
        "composition_split_arms": list(split),
    }


def initial_state_report() -> dict:
    """The declared seed of every arm, and the readings the gate table needs at t = 0."""
    report = {}
    for arm in ARM_TABLE:
        state = initial_carrier(arm)
        scale = max(1.0, float(np.max(np.abs(state))))
        h = (state[:, 0].sum(axis=0) - state[:, 1].sum(axis=0)).mean(axis=1)
        z = state[0, 0] + state[0, 1] - PHI * (state[1, 0] + state[1, 1])
        e = canonical_initial(arm.profile)
        residual = float(np.max(np.abs(projection(state) - e))) / max(
            1.0, float(np.max(np.abs(e)))
        )
        d0, raw = operand_scale(arm, gate_rate(e[0], e[1]), state)
        report[arm.name] = {
            "seed_imbalance": arm.seed_imbalance,
            "composition_split": bool(arm.composition_split),
            "gate_scale": arm.gate_scale,
            "seed_projection_residual": residual,
            "current_mean": float(np.mean(h)),
            "current_mean_relative": abs(float(np.mean(h))) / scale,
            "current_max_relative": float(np.max(np.abs(h))) / scale,
            "z_relative": float(np.max(np.abs(z))) / scale,
            "operand_scale": d0,
            "operand_raw": raw,
        }
    return report


def pre_execution_checks(states: dict, specs: list) -> tuple:
    """Protocol section 4 gate 10 and gate 11, read before any execution.

    Returns (failed, notes, readings). Gate 11 holds for the two covariance arms: their
    operand scale, their bracket floor c_- and their bracket ceiling c_+ must be resolved
    before the schedule runs, because the rate clause of an arm whose bracket is unresolved
    cannot be met. A failed reading is status=FAIL before any arm executes.
    """
    by_name = {spec.arm.name: spec for spec in specs}
    notes = []
    readings = {
        "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
        "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
        "steps_budget_total": STEP_BUDGET_TOTAL,
        "seeds": states,
    }
    readings["seed_projection_residual_max"] = max(
        entry["seed_projection_residual"] for entry in states.values()
    )
    rows = []
    for name in COVARIANCE_ARMS:
        spec = by_name[name]
        rows.append(
            {
                "arm": name,
                "gate_scale": spec.arm.gate_scale,
                "operand_scale": spec.operand_scale,
                "operand_scale_floor": D0_FLOOR,
                "c_minus": spec.c_minus,
                "c_minus_floor": C_MIN_FLOOR,
                "c_plus": spec.c_plus,
                "c_plus_ceiling": C_MAX_CEIL,
                "ell": spec.ell,
                "passed": bool(
                    spec.operand_scale >= D0_FLOOR
                    and spec.c_minus >= C_MIN_FLOOR
                    and spec.c_plus <= C_MAX_CEIL
                ),
            }
        )
    readings["bracket_reachability"] = rows
    failed = [row for row in rows if not row["passed"]]

    notes.append(
        {
            "id": "LR-N1",
            "readings": {
                "seed_imbalance": SEED_IMBALANCE,
                "imbalanced_arms": list(J_ARMS),
                "composition_split_arms": list(COVARIANCE_ARMS),
                "gate_scale": {arm.name: arm.gate_scale for arm in ARM_TABLE},
                "seed_projection_residual_max": readings["seed_projection_residual_max"],
            },
            "statement": (
                "Section 1.2 item 6's declared seeds are applied: (LR-A1) mode content to "
                "every mode-carrying arm, (LR-A2) composition asymmetry to the two "
                "covariance arms and (LR-A3) the direction imbalance to the J-carrying "
                "arms, each re-checked at the seed states before execution."
            ),
        }
    )
    notes.append(
        {
            "id": "LR-N2",
            "readings": {
                "steps_total": int(sum(spec.steps for spec in specs)),
                "closure_steps": int(
                    sum(spec.steps for spec in specs if spec.arm.name in CLOSURE_ARMS)
                ),
                "relaxation_steps": int(
                    sum(spec.steps for spec in specs if spec.arm.name in RELAXATION_ARMS)
                ),
                "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
                "steps_budget_total": STEP_BUDGET_TOTAL,
            },
            "statement": (
                "Section 6's schedule is the declared consequence of (LR-S1) and (LR-S2): "
                "the thirteen closure arms take the spent receipt's own step counts and the "
                "three relaxation arms take 50000 steps each, at the declared total of "
                "282334 against the 290000 cap."
            ),
        }
    )
    notes.append(
        {
            "id": "LR-N3",
            "readings": {"bracket_reachability": rows},
            "statement": (
                "Section 4 gate 11's reachability readings are taken before execution on the "
                "arms' own effective fields (LR-A0); the fixed operand scale of (LR4) is "
                "D_0 = max(1, <kappa^eff>_chi(0) max_chi |Z(0)|), so the identity's bound is "
                "an absolute bound on the arm's own declared scale."
            ),
        }
    )
    return failed, notes, readings


def control_readings(traces: dict, relaxations: dict, gate11: dict) -> list:
    """Section 4: each required control, with its required and its measured readings.

    Section 6A: a control whose verdict is only produced by the run carries the reading that
    makes it reachable, taken before execution; 'decided' states whether its verdict is
    settled at that reading or by the run.
    """
    brackets = {row["arm"]: row for row in gate11.get("bracket_reachability", [])}
    reference = relaxations["relax_reference"]
    scaled = relaxations["relax_scaled"]
    split = relaxations["relax_split"]
    null = traces["null"]
    uniform_short = traces["uniform_short"]
    null_delta = paired_delta(null, uniform_short)

    def rate_clause(reading):
        fit = reading["fit"]
        low = BRACKET_LOW * reading["c_minus"]
        high = BRACKET_HIGH * reading["c_plus"]
        return {
            "bracket_low": low,
            "bracket_high": high,
            "nu_fit": fit["nu_fit"],
            "nu_fit_over_ell": fit.get("nu_fit_over_ell"),
            "window_samples": fit["window_samples"],
            "no_fit": fit["no_fit"],
            "met": bool(
                not fit["no_fit"]
                and fit["nu_fit"] is not None
                and low <= fit["nu_fit"] <= high
            ),
        }

    reference_rate = rate_clause(reference)
    scaled_rate = rate_clause(scaled)
    ratio = None
    if scaled_rate["nu_fit"] is not None and reference_rate["nu_fit"] not in (None, 0.0):
        ratio = scaled_rate["nu_fit"] / reference_rate["nu_fit"]

    return [
        {
            "name": "null pair",
            "arms": ["uniform_short", "null"],
            "requirement": "rho_max <= 1e-11 and delta = 0 exactly",
            "measured": {
                "null_floor": NULL_FLOOR,
                "rho_max_uniform_short": float(np.max(uniform_short.rho)),
                "rho_max_null": float(np.max(null.rho)),
                "delta_max": null_delta["delta_max"],
                "delta_final": null_delta["delta_final"],
                "matched_states": null_delta["matched_states"],
            },
            "fired": bool(
                float(np.max(uniform_short.rho)) <= NULL_FLOOR
                and float(np.max(null.rho)) <= NULL_FLOOR
                and null_delta["delta_max"] == 0.0
            ),
            "decided": (
                "by the run: the two arms carry the same state on the same arithmetic, so the "
                "pair reads the floor and an exactly zero difference as soon as both run"
            ),
            "reachability": (
                "not a t0 reading. The spent protocol read this control at the terminal state "
                "only, where the attracting fixed ratio of the conversion law had already "
                "damped every difference; the successor reads the peak rho_max on every arm, "
                "which is the quantity the witness needs"
            ),
        },
        {
            "name": "relax_reference",
            "arms": ["relax_reference"],
            "requirement": (
                "rho_max > 1e-4 (LR-W); (LR4) at every accepted state; nu_fit inside (LR-R1) "
                "for its own bracket"
            ),
            "measured": {
                "rho_max": reference["rho_max"],
                "rho_final": reference["rho_final"],
                "rho_peak_time": reference["rho_peak_time"],
                "witness_floor": WITNESS_FLOOR,
                "identity_residual_max": reference["identity_residual_max"],
                "identity_bound": reference["identity_bound"],
                "identity_met": reference["identity_met"],
                "c_minus": reference["c_minus"],
                "c_plus": reference["c_plus"],
                "rate": reference_rate,
            },
            "fired": bool(
                reference["witness_fired"]
                and reference["identity_met"] is True
                and reference_rate["met"]
            ),
            "decided": "by the run: the peak witness and the fitted tail",
            "reachability": (
                "t0 readings, by gate 11: operand scale D_0 = {0} against the floor {1}, "
                "c_- = {2}, c_+ = {3}, so the identity's operand and the rate bracket are both "
                "resolved before the schedule starts".format(
                    brackets.get("relax_reference", {}).get("operand_scale"),
                    D0_FLOOR,
                    reference["c_minus"],
                    reference["c_plus"],
                )
            ),
        },
        {
            "name": "relax_scaled",
            "arms": ["relax_scaled"],
            "requirement": (
                "rho_max > 1e-4; (LR4) at every accepted state; nu_fit inside its own bracket; "
                "the ratio clause (LR-R2)"
            ),
            "measured": {
                "rho_max": scaled["rho_max"],
                "rho_final": scaled["rho_final"],
                "rho_peak_time": scaled["rho_peak_time"],
                "witness_floor": WITNESS_FLOOR,
                "identity_residual_max": scaled["identity_residual_max"],
                "identity_bound": scaled["identity_bound"],
                "identity_met": scaled["identity_met"],
                "c_minus": scaled["c_minus"],
                "c_plus": scaled["c_plus"],
                "rate": scaled_rate,
                "ratio_nu_scaled_over_nu_reference": ratio,
                "ratio_low": SCALED_RATIO_LOW,
                "ratio_high": SCALED_RATIO_HIGH,
            },
            "fired": bool(
                scaled["witness_fired"]
                and scaled["identity_met"] is True
                and scaled_rate["met"]
                and ratio is not None
                and SCALED_RATIO_LOW <= ratio <= SCALED_RATIO_HIGH
            ),
            "decided": "by the run: the peak witness, the fitted tail and the ratio to arm 14",
            "reachability": (
                "t0 readings, by gate 11: operand scale D_0 = {0} against the floor {1}, "
                "c_- = {2}, c_+ = {3}, on the halved gate s = {4} of (LR-A0)".format(
                    brackets.get("relax_scaled", {}).get("operand_scale"),
                    D0_FLOOR,
                    scaled["c_minus"],
                    scaled["c_plus"],
                    scaled["gate_scale"],
                )
            ),
        },
        {
            "name": "relax_split",
            "arms": ["relax_split"],
            "requirement": "rho_max > 1e-4 (LR-W)",
            "measured": {
                "rho_max": split["rho_max"],
                "rho_final": split["rho_final"],
                "rho_peak_time": split["rho_peak_time"],
                "witness_floor": WITNESS_FLOOR,
                "nu_fit_recorded_not_gated": split["fit"]["nu_fit"],
                "window_samples": split["fit"]["window_samples"],
                "velocity_split": VELOCITY_SPLIT,
            },
            "fired": bool(split["witness_fired"]),
            "decided": "by the run: the peak witness only",
            "reachability": (
                "declared construction, not a t0 reading: u_+ = u - {0} and u_- = u + {0}, so "
                "the two orientation blocks advect at different speeds from the first step; "
                "the rate is recorded and gates nothing because this protocol derives no rate "
                "for the orientation-imbalance channel".format(VELOCITY_SPLIT)
            ),
        },
    ]


def aggregate_verdicts(closure_features: dict, relaxation_features: dict, arms: list,
                       controls_ok: bool) -> dict:
    """Section 5: the two aggregate verdicts, and status=FAIL when a required control is silent."""
    if not controls_ok:
        return {"status": "FAIL", "closure_verdict": None, "relaxation_verdict": None}
    if not closure_features.get("G3", False) or not relaxation_features.get("H1", False):
        return {"status": "FAIL", "closure_verdict": None, "relaxation_verdict": None}

    structural = any(row["class"] == "structural_disagreement" for row in arms)
    if closure_features.get("G1", False) and closure_features.get("G2", False):
        closure = "EMERGES"
    elif structural:
        closure = "CONTRADICTS"
    else:
        closure = "INCONCLUSIVE"

    if not relaxation_features.get("H2", False):
        relaxation = "CONTRADICTS"
    elif relaxation_features.get("H3", False):
        relaxation = "EMERGES"
    else:
        relaxation = "INCONCLUSIVE"
    return {"status": "PASS", "closure_verdict": closure, "relaxation_verdict": relaxation}


def class_of(trace: ArmTrace, partner: ArmTrace) -> str:
    """Section 5.1: the per-arm class of a refinement-pair member, tested in the declared order."""
    rho_max = float(np.max(trace.rho))
    if rho_max <= BUDGET:
        return "within_budget"
    if partner is None:
        return "above_budget_no_partner"
    partner_rho = float(np.max(partner.rho))
    if partner_rho <= 0.0:
        ratio = float("inf")
    else:
        ratio = rho_max / partner_rho
    if not 1.0 / REFINEMENT_FACTOR <= ratio <= REFINEMENT_FACTOR:
        return "step_dependent"
    if rho_max > STRUCTURAL_SCALE:
        return "structural_disagreement"
    return "above_budget_below_structural"


def spectrum_gate_rows(specs: list, traces: dict) -> list:
    """Gate 9: the frozen generator against the closed form, on every mode-carrying closure arm."""
    rows = []
    for spec in specs:
        arm = spec.arm
        if arm.role not in ("contract", "mode", "persistence") or not arm.modes:
            continue
        trace = traces[arm.name]
        residual = spectrum_check(arm, trace.spec.kappa_mean)
        rows.append(
            {
                "arm": arm.name,
                "kappa": trace.spec.kappa_mean,
                "exchange": arm.exchange,
                "modes": list(arm.modes),
                "multiset_residual": residual,
                "passed": bool(residual <= SPECTRUM_TOLERANCE),
            }
        )
    return rows

def run_schedule() -> tuple:
    """Every declared arm, one execution each, in the order of the section 6 table."""
    specs = [build_spec(arm) for arm in ARM_TABLE]
    traces = {}
    for spec in specs:
        print(
            "arm {0}/{1} {2}: dt={3} horizon={4} steps={5}".format(
                spec.arm.index, len(specs), spec.arm.name, spec.dt, spec.horizon, spec.steps
            ),
            flush=True,
        )
        trace = run_arm(spec)
        traces[spec.arm.name] = trace
        print(
            "arm {0} {1}: rho_max={2:.3e}".format(
                spec.arm.index, spec.arm.name, float(np.max(trace.rho))
            ),
            flush=True,
        )
    return specs, traces


def schedule_declaration(specs: list, gate11: dict) -> dict:
    """Section 8: the declared schedule, thresholds, rules and seeds, shared by both receipts."""
    return {
        "arm_table": [
            {
                "index": spec.arm.index,
                "name": spec.arm.name,
                "profile": spec.arm.profile,
                "modes": list(spec.arm.modes),
                "alpha": spec.arm.alpha,
                "horizon_key": spec.arm.horizon_key,
                "n_chi": spec.arm.n_chi,
                "refined": spec.arm.refined,
                "exchange": spec.arm.exchange,
                "velocity_split": spec.arm.velocity_split,
                "gate_covariance": spec.arm.gate_covariance,
                "gate_scale": spec.arm.gate_scale,
                "role": spec.arm.role,
                "dt": spec.dt,
                "horizon": spec.horizon,
                "steps": spec.steps,
                "seed_imbalance": spec.arm.seed_imbalance,
                "composition_split": bool(spec.arm.composition_split),
                "kappa_initial_mean": spec.kappa_mean,
                "c_minus": spec.c_minus,
                "c_plus": spec.c_plus,
                "ell": spec.ell,
                "operand_scale": spec.operand_scale,
            }
            for spec in specs
        ],
        "profiles": {name: list(value) for name, value in PROFILES.items()},
        "modulation": MODULATION,
        "mode_amplitude": MODE_AMPLITUDE,
        "gate_scale_reference": GATE_SCALE_REFERENCE,
        "gate_scale_halved": GATE_SCALE_HALVED,
        "gate_covariance_factor": GATE_COVARIANCE_FACTOR,
        "velocity_split": VELOCITY_SPLIT,
        "thresholds": {
            "budget": BUDGET,
            "structural_scale": STRUCTURAL_SCALE,
            "refinement_factor": REFINEMENT_FACTOR,
            "witness_floor": WITNESS_FLOOR,
            "annihilation_tolerance": ANNIHILATION_TOLERANCE,
            "idempotence_tolerance": IDEMPOTENCE_TOLERANCE,
            "matched_start_tolerance": MATCHED_START_TOLERANCE,
            "spectrum_tolerance": SPECTRUM_TOLERANCE,
            "null_floor": NULL_FLOOR,
            "identity_tolerance": IDENTITY_TOLERANCE,
            "d0_floor": D0_FLOOR,
            "c_minus_floor": C_MIN_FLOOR,
            "c_plus_ceiling": C_MAX_CEIL,
            "fit_window_start": FIT_WINDOW_START,
            "fit_floor": FIT_FLOOR,
            "fit_min_samples": FIT_MIN_SAMPLES,
            "bracket_low": BRACKET_LOW,
            "bracket_high": BRACKET_HIGH,
            "scaled_ratio_low": SCALED_RATIO_LOW,
            "scaled_ratio_high": SCALED_RATIO_HIGH,
        },
        "rules": {
            "step_candidates": list(STEP_CANDIDATES),
            "step_safety": STEP_SAFETY,
            "horizon_cap": HORIZON_CAP,
            "convergence_product": CONVERGENCE_PRODUCT,
            "short_fraction": SHORT_FRACTION,
            "seed_imbalance": SEED_IMBALANCE,
            "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
        },
        "executions": DECLARED_EXECUTIONS,
        "steps_total": int(sum(spec.steps for spec in specs)),
        "steps_closure": int(
            sum(spec.steps for spec in specs if spec.arm.name in CLOSURE_ARMS)
        ),
        "steps_relaxation": int(
            sum(spec.steps for spec in specs if spec.arm.name in RELAXATION_ARMS)
        ),
        "steps_per_execution_max": int(max(spec.steps for spec in specs)),
        "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
        "steps_budget_total": STEP_BUDGET_TOTAL,
        "closure_steps_declared": CLOSURE_STEPS,
        "seeds": gate11.get("seeds", {}),
        "seed_declaration": {
            "mode_content": {
                "amplitude": MODE_AMPLITUDE,
                "arms": {
                    spec.arm.name: list(spec.arm.modes) for spec in specs if spec.arm.modes
                },
                "identity": "mean_chi(1 + alpha cos(m chi)) = 1, so the projection is "
                "unchanged at the declared mode amplitudes",
            },
            "composition_asymmetry": {
                "arms": list(COVARIANCE_ARMS),
                "identity": "each carrier's loop mean is exactly one and "
                "Z(chi) = eps + alpha rho cos(m chi) no longer vanishes",
            },
            "direction_imbalance": {
                "value": SEED_IMBALANCE,
                "arms": list(J_ARMS),
                "identity": "sum_s (1 + s beta) = 2, so the projection reproduces E_a",
            },
            "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
        },
        "refinement_pairs": [list(pair) for pair in REFINEMENT_PAIRS],
        "observational_note": (
            "loops are read as their frozen equal-weight grid average; the carrier state "
            "layout is f[carrier, orientation, x, chi]; rho is read as the peak over the "
            "whole trace of max|P f - E| / max(1,max|E|); the rate is the least-squares slope "
            "of ln rho on W = {t >= T/2, rho > 1e-12}; J is the domain mean of <H>_chi over "
            "the periodic exterior grid, and the mode pair Delta is read on the states the "
            "two traces share in model time"
        ),
    }


def receipt_head(specs: list, started: float, gate11: dict, executions: int) -> dict:
    """The framing of both receipts: digests, invocation and the declared schedule."""
    return {
        "schema": RECEIPT_SCHEMA,
        "protocol": {"path": PROTOCOL_PATH, "sha256": digest_of(PROTOCOL_PATH)},
        "probe": {"path": PROBE_PATH, "sha256": digest_of(PROBE_PATH)},
        "binding": {
            "path": BOUND_MODULE,
            "expected_sha256": BOUND_DIGEST,
            "observed_sha256": digest_of(BOUND_MODULE),
        },
        "frozen_sources": {
            "protocol": {"path": PROTOCOL_PATH, "sha256": digest_of(PROTOCOL_PATH)},
            "bound_module": {"path": BOUND_MODULE, "sha256": digest_of(BOUND_MODULE)},
            "probe": {"path": PROBE_PATH, "sha256": digest_of(PROBE_PATH)},
            "bound_digest_expected": BOUND_DIGEST,
        },
        "invocation": {
            "command": INVOCATION,
            "bound_seconds": BOUND_SECONDS,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
            "runtime_seconds": time.time() - started,
            "pid": os.getpid(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "device": "cpu",
            "processes": 1,
            "concurrent_runs": False,
            "executions": executions,
        },
        "declared": schedule_declaration(specs, gate11),
        "pre_execution": {
            "bracket_reachability": gate11.get("bracket_reachability", []),
            "seed_projection_residual_max": gate11.get("seed_projection_residual_max"),
            "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
        },
    }


def assemble_receipt(specs: list, traces: dict, started: float, notes: list,
                     gate11: dict) -> dict:
    """Section 8: the receipt of one completed schedule, with both verdicts."""
    rows = [arm_row(traces[spec.arm.name]) for spec in specs]
    pair_partner = {}
    for coarse, refined in REFINEMENT_PAIRS:
        pair_partner[coarse] = refined
        pair_partner[refined] = coarse
    uniform_short = traces["uniform_short"]
    mode_readings = {name: mode_reading(traces[name], uniform_short) for name in MODE_ARMS}
    relaxations = {name: relaxation_reading(traces[name]) for name in RELAXATION_ARMS}

    for row in rows:
        name = row["name"]
        arm = traces[name].spec.arm
        partner_name = pair_partner.get(name, "")
        row["pair_partner"] = partner_name or None
        row["pair_rho_ratio"] = None
        row["pair_class"] = (
            class_of(traces[name], traces[partner_name]) if partner_name else None
        )
        if partner_name:
            partner_rho = float(np.max(traces[partner_name].rho))
            row["pair_rho_ratio"] = (
                None if partner_rho <= 0.0 else row["rho_max"] / partner_rho
            )
        if arm.counterpart:
            row["counterpart_reading"] = paired_delta(traces[name], traces[arm.counterpart])
        if name in mode_readings:
            row["mode_reading"] = mode_readings[name]
        if name in relaxations:
            row["relaxation_reading"] = relaxations[name]

    closure_rows = [row for row in rows if row["role"] in ("contract", "mode", "persistence")]
    covariance_rows = [row for row in rows if row["name"] in COVARIANCE_ARMS]

    gates = []
    binding_ok = digest_of(BOUND_MODULE) == BOUND_DIGEST
    gates.append(
        {"gate": 1, "name": "source binding", "measured": digest_of(BOUND_MODULE),
         "bound": BOUND_DIGEST, "passed": bool(binding_ok)}
    )
    gate_2 = max(row["annihilation_max"] for row in rows)
    gates.append(
        {"gate": 2, "name": "discrete annihilation", "measured": gate_2,
         "bound": ANNIHILATION_TOLERANCE, "passed": bool(gate_2 <= ANNIHILATION_TOLERANCE)}
    )
    gate_3 = max(row["idempotence_max"] for row in rows)
    gates.append(
        {"gate": 3, "name": "projection idempotence", "measured": gate_3,
         "bound": IDEMPOTENCE_TOLERANCE, "passed": bool(gate_3 <= IDEMPOTENCE_TOLERANCE)}
    )
    closure_transport = [
        {"arm": row["name"], "velocity_split": row["velocity_split"]} for row in closure_rows
    ]
    split_recorded = [
        {"arm": row["name"], "velocity_split": row["velocity_split"]} for row in rows
        if row["name"] in RELAXATION_ARMS and row["velocity_split"] != 0.0
    ]
    gates.append(
        {"gate": 4, "name": "shared exterior transport",
         "measured": {"closure_arms": closure_transport, "recorded_violations": split_recorded},
         "bound": "u and D_x identical in all four channels and chi independent in every "
                  "closure arm; the split arm records its violation instead of failing",
         "passed": bool(all(entry["velocity_split"] == 0.0 for entry in closure_transport))}
    )
    gate_5 = max(row["gate_spread_max"] for row in closure_rows)
    gates.append(
        {"gate": 5, "name": "common gate",
         "measured": {
             "closure_max_spread": gate_5,
             "recorded_violations": [
                 {"arm": row["name"], "gate_spread_max": row["gate_spread_max"]}
                 for row in covariance_rows
             ],
             "covariance_factor": GATE_COVARIANCE_FACTOR,
         },
         "bound": "max_chi |kappa^eff - <kappa^eff>_chi| = 0 in every closure arm; arms 14 "
                  "and 15 record their violation instead of failing",
         "passed": bool(gate_5 == 0.0)}
    )
    gate_6 = max(row["matched_start"] for row in rows)
    gates.append(
        {"gate": 6, "name": "matched start", "measured": gate_6,
         "bound": MATCHED_START_TOLERANCE, "passed": bool(gate_6 <= MATCHED_START_TOLERANCE)}
    )
    finite = all(
        math.isfinite(value)
        for row in rows
        for key, value in row.items()
        if isinstance(value, float)
    )
    positive = all(
        row["min_state"] >= 0.0 and row["min_projection"] >= 0.0 and 0.0 <= row["q_min"]
        and row["q_max"] < 1.0
        for row in rows
    )
    gates.append(
        {
            "gate": 7,
            "name": "finite and nonnegative",
            "measured": {"finite": finite, "positive": positive},
            "bound": "every recorded scalar finite, every f >= 0, 0 <= q < 1",
            "passed": bool(finite and positive),
        }
    )
    statistics_carried = {
        "closure arm": (
            "rho_max", "rho_final", "rho_peak_time", "annihilation_max", "idempotence_max",
            "matched_start", "current_mean_initial", "current_mean_final", "q_min", "q_max",
        ),
        "relaxation arm": (
            "rho_max", "rho_final", "rho_peak_time", "identity_residual_max", "c_minus",
            "c_plus", "ell", "operand_scale",
        ),
    }
    missing_statistics = []
    for row in rows:
        keys = statistics_carried["relaxation arm"] if row["name"] in RELAXATION_ARMS else (
            statistics_carried["closure arm"]
        )
        for key in keys:
            if key not in row or row[key] is None:
                missing_statistics.append({"arm": row["name"], "statistic": key})
    steps_total = int(sum(spec.steps for spec in specs))
    shape_measured = {
        "executions": len(rows),
        "steps_total": steps_total,
        "steps_budget_total": STEP_BUDGET_TOTAL,
        "steps_per_execution_max": int(max(spec.steps for spec in specs)),
        "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
        "steps_match_the_rules": bool(
            all(
                spec.steps == expected[3]
                for spec, expected in zip(specs, EXPECTED_SPEC)
            )
        ),
        "missing_statistics": missing_statistics,
    }
    gates.append(
        {"gate": 8, "name": "declared shape", "measured": shape_measured,
         "bound": "sixteen executions, every declared statistic recorded, the recorded total "
                  "at or below the declared cap and the per-arm counts the rules' figures",
         "passed": bool(
             len(rows) == DECLARED_EXECUTIONS
             and not missing_statistics
             and steps_total <= STEP_BUDGET_TOTAL
             and shape_measured["steps_match_the_rules"]
         )}
    )
    spectrum_rows = spectrum_gate_rows(specs, traces)
    gates.append(
        {"gate": 9, "name": "spectrum re-check", "measured": spectrum_rows,
         "bound": SPECTRUM_TOLERANCE,
         "passed": bool(spectrum_rows) and bool(
             all(entry["passed"] for entry in spectrum_rows)
         )}
    )
    null_row = next(row for row in rows if row["name"] == "null")
    null_pair_delta = paired_delta(traces["null"], uniform_short)
    gate_10 = {
        "rho_max_null": null_row["rho_max"],
        "rho_max_uniform_short": next(
            row["rho_max"] for row in rows if row["name"] == "uniform_short"
        ),
        "null_floor": NULL_FLOOR,
        "delta_max": null_pair_delta["delta_max"],
    }
    gates.append(
        {"gate": 10, "name": "witness floor", "measured": gate_10,
         "bound": "the null pair reads rho_max <= 1e-11 and delta = 0 exactly",
         "passed": bool(
             gate_10["rho_max_null"] <= NULL_FLOOR
             and gate_10["rho_max_uniform_short"] <= NULL_FLOOR
             and gate_10["delta_max"] == 0.0
         )}
    )
    bracket_rows = gate11.get("bracket_reachability", [])
    gates.append(
        {"gate": 11, "name": "bracket and identity reachability",
         "measured": bracket_rows,
         "bound": "for arms 14 and 15, read before execution: D_0 >= 1e-6, c_- >= 1e-6, "
                  "c_+ <= 1",
         "passed": bool(bracket_rows) and bool(
             all(entry["passed"] for entry in bracket_rows)
         )}
    )
    gates.append(
        {"gate": 12, "name": "process declaration",
         "measured": {"processes": 1, "executions": len(rows), "pid": os.getpid(),
                      "device": "cpu", "concurrent": False},
         "bound": "one process, sixteen executions, the device and no concurrent runs",
         "passed": bool(len(rows) == DECLARED_EXECUTIONS)}
    )

    controls = control_readings(traces, relaxations, gate11)
    controls_ok = all(entry["fired"] for entry in controls)

    g1 = all(row["rho_max"] <= BUDGET for row in closure_rows)
    pair_agreement = {}
    for coarse, refined in REFINEMENT_PAIRS:
        coarse_rho = float(np.max(traces[coarse].rho))
        refined_rho = float(np.max(traces[refined].rho))
        ratio = None if refined_rho <= 0.0 else coarse_rho / refined_rho
        pair_agreement[coarse + "/" + refined] = {
            "coarse_rho_max": coarse_rho,
            "refined_rho_max": refined_rho,
            "ratio": ratio,
            "agrees_within_factor": bool(
                ratio is not None and 1.0 / REFINEMENT_FACTOR <= ratio <= REFINEMENT_FACTOR
            ),
        }
    g2 = all(entry["agrees_within_factor"] for entry in pair_agreement.values())
    g3 = bool(
        gates[9]["passed"]
        and all(entry["identity_met"] is True for entry in relaxations.values()
                if entry["arm"] in COVARIANCE_ARMS)
        and all(entry["passed"] for entry in bracket_rows)
    )
    h1 = all(entry["witness_fired"] for entry in relaxations.values())
    h2 = all(
        entry["rate_clause"] is True
        for entry in relaxations.values()
        if entry["arm"] in COVARIANCE_ARMS
    )
    ratio_scaled = controls[2]["measured"]["ratio_nu_scaled_over_nu_reference"]
    h3 = bool(
        ratio_scaled is not None
        and SCALED_RATIO_LOW <= ratio_scaled <= SCALED_RATIO_HIGH
    )

    verdicts = aggregate_verdicts(
        closure_features={"G1": g1, "G2": g2, "G3": g3},
        relaxation_features={"H1": h1, "H2": h2, "H3": h3},
        arms=[{"name": row["name"], "class": row["pair_class"]} for row in rows],
        controls_ok=controls_ok,
    )
    gates_ok = all(entry["passed"] for entry in gates)
    if not gates_ok or verdicts["status"] != "PASS":
        verdicts = {"status": "FAIL", "closure_verdict": None, "relaxation_verdict": None}
    status = verdicts["status"]

    receipt = receipt_head(specs, started, gate11, len(rows))
    receipt.update(
        {
            "gates": gates,
            "controls": controls,
            "arms": rows,
            "mode_readings": mode_readings,
            "closure": {
                "features": {"G1": g1, "G2": g2, "G3": g3},
                "classes": {
                    row["name"]: row["pair_class"]
                    for row in rows
                    if row["pair_class"] is not None
                },
                "refinement_agreement": pair_agreement,
                "budget": BUDGET,
                "structural_scale": STRUCTURAL_SCALE,
                "refinement_factor": REFINEMENT_FACTOR,
                "verdict": verdicts["closure_verdict"],
            },
            "relaxation": {
                "features": {"H1": h1, "H2": h2, "H3": h3},
                "arms": {name: relaxations[name] for name in RELAXATION_ARMS},
                "brackets": {
                    name: {
                        "c_minus": relaxations[name]["c_minus"],
                        "c_plus": relaxations[name]["c_plus"],
                        "ell": relaxations[name]["ell"],
                        "operand_scale": relaxations[name]["operand_scale"],
                        "bracket_low": BRACKET_LOW,
                        "bracket_high": BRACKET_HIGH,
                    }
                    for name in COVARIANCE_ARMS
                },
                "nu_fit_ratio_scaled_over_reference": ratio_scaled,
                "ratio_band": [SCALED_RATIO_LOW, SCALED_RATIO_HIGH],
                "rate_observation_not_gated": {
                    name: relaxations[name]["fit"].get("nu_fit_over_ell")
                    for name in RELAXATION_ARMS
                },
                "witness_floor": WITNESS_FLOOR,
                "verdict": verdicts["relaxation_verdict"],
            },
            "status": status,
            "verdict_scope": (
                "both features measured and both verdicts issued" if status == "PASS"
                else "no verdict is issued for this status"
            ),
            "protocol_notes": notes,
        }
    )
    return receipt


def pre_execution_receipt(specs: list, started: float, notes: list, gate11: dict,
                          failed: list) -> dict:
    """Gate 11's failure path: status=FAIL with no verdict before any arm executes."""
    receipt = receipt_head(specs, started, gate11, 0)
    receipt.update(
        {
            "gates": [
                {
                    "gate": 11,
                    "name": "bracket and identity reachability",
                    "measured": gate11.get("bracket_reachability", []),
                    "bound": "for arms 14 and 15, read before execution: D_0 >= 1e-6, "
                             "c_- >= 1e-6, c_+ <= 1",
                    "passed": False,
                    "failed_readings": failed,
                }
            ],
            "controls": [],
            "arms": [],
            "mode_readings": {},
            "closure": {
                "features": {"G1": None, "G2": None, "G3": False},
                "classes": {},
                "verdict": None,
            },
            "relaxation": {
                "features": {"H1": None, "H2": None, "H3": None},
                "arms": {},
                "verdict": None,
            },
            "status": "FAIL",
            "verdict_scope": "no verdict is issued for this status",
            "protocol_notes": notes,
            "pre_execution": {
                "executions": 0,
                "failed_readings": failed,
                "statement": (
                    "a rate clause whose bracket is unresolved cannot be met, so the probe "
                    "stopped before executing any arm"
                ),
            },
        }
    )
    return receipt


def sanitize(value):
    """Strip numpy scalars and refuse a non-finite number before the receipt is written."""
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, np.ndarray):
        raise TypeError("array reached the receipt; record a scalar instead")
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def write_receipt(receipt: dict) -> str:
    path = os.path.join(ROOT, RECEIPT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sanitize(receipt), handle, indent=2, sort_keys=False, allow_nan=False)
        handle.write("\n")
    return path


def main() -> int:
    if len(sys.argv) > 1:
        print(
            "the protocol declares no command-line parameter; received {0}".format(sys.argv[1:]),
            flush=True,
        )
        return EXIT_ARGUMENTS

    specs = [build_spec(arm) for arm in ARM_TABLE]
    report = static_check(specs)
    if report["failures"]:
        for failure in report["failures"]:
            print("static check: {0}".format(failure), flush=True)
        return EXIT_STATIC_CHECK
    print(
        "static check: {0} arms, {1} steps total ({2} closure, {3} relaxation), {4} steps in "
        "the longest execution".format(
            report["arms"], report["steps_total"], report["closure_steps"],
            report["steps_total"] - report["closure_steps"], report["steps_per_execution_max"],
        ),
        flush=True,
    )

    started = time.time()
    states = initial_state_report()
    failed, notes, readings = pre_execution_checks(states, specs)
    print(
        "gate 11 readings: seed projection residual max {0}, brackets {1}".format(
            readings["seed_projection_residual_max"],
            [
                (row["arm"], row["operand_scale"], row["c_minus"], row["c_plus"],
                 row["passed"])
                for row in readings["bracket_reachability"]
            ],
        ),
        flush=True,
    )
    for note in notes:
        print("protocol note {0}: {1}".format(note["id"], note["statement"]), flush=True)
    if failed:
        for row in failed:
            print(
                "gate 11 reading failed for {0}: D_0 = {1} (floor {2}), c_- = {3} (floor "
                "{4}), c_+ = {5} (ceiling {6})".format(
                    row["arm"], row["operand_scale"], row["operand_scale_floor"],
                    row["c_minus"], row["c_minus_floor"], row["c_plus"],
                    row["c_plus_ceiling"],
                ),
                flush=True,
            )
        receipt = pre_execution_receipt(specs, started, notes, readings, failed)
        path = write_receipt(receipt)
        print(
            "receipt {0}\nstatus FAIL, no verdict: gate 11 is unresolved, so the one "
            "declared invocation would be spent on a criterion that cannot be met.".format(path),
            flush=True,
        )
        return EXIT_PRE_EXECUTION_BLOCK

    specs, traces = run_schedule()
    receipt = assemble_receipt(specs, traces, started, notes, readings)
    path = write_receipt(receipt)
    print(
        "receipt {0}\nstatus {1} closure {2} relaxation {3}".format(
            path, receipt["status"], receipt["closure"]["verdict"],
            receipt["relaxation"]["verdict"],
        ),
        flush=True,
    )
    return EXIT_PASS if receipt["status"] == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
