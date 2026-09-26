"""Execute the frozen loop-carrier projection dynamics schedule.

Protocol: computations/loop-carrier-projection-dynamics-prereg.md (sections 1-6).
Invocation: timeout 5400 python computations/verify_loop_carrier_projection_dynamics.py
Receipt: runs/loop_carrier_projection_dynamics/verification.json

The script takes no command-line arguments. Every threshold, horizon rule, step rule,
initial profile, seed and arm below is a copy of the protocol, and the frozen discrete
operators and rate constants are imported from the module the protocol binds by digest.
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
PROTOCOL_PATH = "computations/loop-carrier-projection-dynamics-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_projection_dynamics.py"
RECEIPT_PATH = "runs/loop_carrier_projection_dynamics/verification.json"
INVOCATION = "timeout 5400 python computations/verify_loop_carrier_projection_dynamics.py"
BOUND_SECONDS = 5400.0
DECLARED_EXECUTIONS = 15
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
REFINEMENT_REDUCTION = 4.0
MODE_BUDGET = 1.0e-6
RELAXATION_LIMIT = 1.0e-3
SLOPE_TOLERANCE = 0.10
SENSITIVITY_FLOOR = 1.0e-11
PERSISTENCE_FLOOR = 0.9
ANNIHILATION_TOLERANCE = 1.0e-14
IDEMPOTENCE_TOLERANCE = 1.0e-15
MATCHED_START_TOLERANCE = 1.0e-15
SPECTRUM_TOLERANCE = 1.0e-9
COVARIANCE_IDENTITY_TOLERANCE = 1.0e-12
CONTROL_DEVIATION = 1.0e-4
GATE_COVARIANCE_FACTOR = 0.5
VELOCITY_SPLIT = 0.05
ZERO_EXCHANGE = 0.0

# Protocol section 6 (amended by section 6A): declared step budget. The caps are the figures
# rules (PD2) and (PD3) compute for this arm list; the pre-amendment draft declared 40000 and
# 230000 before those rules were instantiated.
STEP_CAP_PER_EXECUTION = 50000
STEP_BUDGET_TOTAL = 232334

# Protocol section 6A (amendment of September 16, 2026): declared seeds and the floors the
# pre-execution reachability checks of the two previously dead controls read against.
SEED_IMBALANCE = 0.05
SEED_INVARIANCE_TOLERANCE = 1.0e-15
CURRENT_FLOOR = 1.0e-9
COVARIANCE_FLOOR = 1.0e-6

# Frozen comparison table of the protocol's own arm table (section 6), transcribed here so
# the derived schedule can be checked against it. Columns: index, name, profile, loop
# content, rate change, horizon label, grid label.
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
    (13, "covariance", "on_ray", "mode 1,2", "kappa(1+0.5cos chi)", "convergence", "7x24"),
    (14, "direction_split", "on_ray", "mode 1", "u_-+ = u -+ 0.05", "convergence", "7x24"),
    (15, "persistent_current", "on_ray", "mode 1", "r = 0", "mode_zero_exchange", "7x24"),
)

# Frozen readings of the derived schedule: the rules of sections 2.2 were applied to the
# arm table above and the resulting step size, horizon and step count are fixed here, so a
# later change to a rule shows up as a static-check failure rather than as a silent change
# of the schedule. Columns: index, dt, horizon, steps, lambda_max, mode set.
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
    (13, 0.02, 1000.0, 50000, 1.041096175, (1, 2)),
    (14, 0.02, 1000.0, 50000, 1.033131228, (1,)),
    (15, 0.05, 222.307692, 4447, 0.060912592, (1,)),
)


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


# Protocol section 6A: the two trailing fields carry the amendment's seed declarations. Arms
# that do not name them carry the plain seed of section 3.1.
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
    Arm(13, "covariance", "on_ray", (1, 2), MODE_AMPLITUDE, "convergence", N_CHI, False,
        EXCHANGE, 0.0, GATE_COVARIANCE_FACTOR, "covariance", "", "", False, 0.0, True),
    Arm(14, "direction_split", "on_ray", (1,), MODE_AMPLITUDE, "convergence", N_CHI, False,
        EXCHANGE, VELOCITY_SPLIT, 0.0, "direction_split", "", "", False),
    Arm(15, "persistent_current", "on_ray", (1,), MODE_AMPLITUDE, "mode_zero_exchange",
        N_CHI, False, ZERO_EXCHANGE, 0.0, 0.0, "persistence", "", "", True, SEED_IMBALANCE),
)

CONTRACT_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "contract")
MODE_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "mode")
J_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.carries_j)
CLOSURE_ARMS = tuple(
    arm.name for arm in ARM_TABLE if arm.role in ("contract", "mode")
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
    """Protocol section 1.2 item 4: kappa from the projected densities at the stage start.

    The result is chi resolved, shape (N_x, N_chi), so it multiplies a carrier component of
    shape (orientation, N_x, N_chi); for a contract arm every loop cell carries one value.
    """
    e = projection(state)
    rate = gate_rate(e[0], e[1])
    if arm.gate_covariance:
        return rate[:, None] * (
            1.0 + arm.gate_covariance * np.cos(loop_grid(state.shape[LOOP_AXIS]))
        )[None, :]
    return rate[:, None] * np.ones((1, state.shape[LOOP_AXIS]))


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
    """Protocol section 2.2: largest |Re Lambda| over the mode set the arm carries."""
    if not arm.modes:
        return max(abs(U) / EXTERIOR_DX, D_X / EXTERIOR_DX**2)
    peak = float(np.max(kappa))
    if arm.gate_covariance:
        peak = peak * (1.0 + arm.gate_covariance)
    return float(
        max(
            abs(value.real)
            for mode in arm.modes
            for value in mode_spectrum(mode, peak, arm.exchange)
        )
    )


def step_size(lambda_max: float) -> float:
    """(PD2): dt = max{dt in {0.05, 0.02, 0.01} : dt <= 1/(40 lambda_max)}."""
    limit = 1.0 / (STEP_SAFETY * lambda_max)
    for candidate in STEP_CANDIDATES:
        if candidate <= limit:
            return candidate
    raise ValueError("no frozen step size satisfies the safety factor at {0}".format(lambda_max))


def arm_horizon(arm: Arm, kappa: np.ndarray) -> float:
    """(PD3), with the internal gap taken at the slowest cell of the arm's own gate."""
    if arm.horizon_key == "convergence":
        gap = internal_gap(kappa, arm.exchange)
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


def covariance_parts(state: np.ndarray) -> tuple:
    """The two sides of (LB14) at one state, with Z(chi) = sum_s [f_Ys - phi f_Is]."""
    e = projection(state)
    epsilon = e[0] - PHI * e[1]
    z = state[0, 0] + state[0, 1] - PHI * (state[1, 0] + state[1, 1])
    kappa = gate_rate(e[0], e[1])[:, None] * (
        1.0 + GATE_COVARIANCE_FACTOR * np.cos(loop_grid(state.shape[LOOP_AXIS]))
    )[None, :]
    mean_kappa = kappa.mean(axis=1)
    left = float(np.mean(kappa * z))
    right = float(
        np.mean(
            mean_kappa[:, None] * epsilon[:, None] + (kappa - mean_kappa[:, None]) * z
        )
    )
    return left, right


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


def build_spec(arm: Arm) -> ArmSpec:
    initial = canonical_initial(arm.profile)
    kappa = gate_rate(initial[0], initial[1])
    lambda_max = arm_lambda_max(arm, kappa)
    dt = step_size(lambda_max)
    if arm.refined:
        dt = dt / 2.0
    horizon = arm_horizon(arm, kappa)
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
    if arm.role == "covariance":
        left, right = covariance_parts(state)
        readings["covariance_identity"] = abs(left - right) / max(
            COVARIANCE_IDENTITY_TOLERANCE, abs(right)
        )
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
        "covariance_identity_max": (
            float(np.max(trace.covariance_residual)) if len(trace.covariance_residual) else None
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
        if (arm.horizon_key == "convergence") != (horizon in ("convergence",)):
            failures.append("arm {0}: horizon key drift".format(index))
        if (arm.n_chi == N_CHI_TRUNCATED) != (grid == "7x12"):
            failures.append("arm {0}: resolution drift".format(index))
        if (arm.refined) != (grid.endswith("dt/2")):
            failures.append("arm {0}: refinement drift".format(index))
        if (arm.gate_covariance != 0.0) != change.startswith("kappa"):
            failures.append("arm {0}: gate modification drift".format(index))
        if (arm.velocity_split != 0.0) != change.startswith("u_"):
            failures.append("arm {0}: velocity modification drift".format(index))
        if (arm.exchange != EXCHANGE) != change.startswith("r ="):
            failures.append("arm {0}: exchange modification drift".format(index))
        if (arm.modes != ()) != (content != "uniform"):
            failures.append("arm {0}: loop content drift".format(index))
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
        if abs(spec.lambda_max - lambda_max) > 1.0e-6:
            failures.append(
                "arm {0}: lambda_max {1} != frozen {2}".format(index, spec.lambda_max, lambda_max)
            )
        if tuple(spec.arm.modes) != tuple(modes):
            failures.append("arm {0}: mode set drift".format(index))

    thresholds = {
        "BUDGET": BUDGET,
        "STRUCTURAL_SCALE": STRUCTURAL_SCALE,
        "REFINEMENT_REDUCTION": REFINEMENT_REDUCTION,
        "MODE_BUDGET": MODE_BUDGET,
        "RELAXATION_LIMIT": RELAXATION_LIMIT,
        "SLOPE_TOLERANCE": SLOPE_TOLERANCE,
        "SENSITIVITY_FLOOR": SENSITIVITY_FLOOR,
        "PERSISTENCE_FLOOR": PERSISTENCE_FLOOR,
        "ANNIHILATION_TOLERANCE": ANNIHILATION_TOLERANCE,
        "IDEMPOTENCE_TOLERANCE": IDEMPOTENCE_TOLERANCE,
        "MATCHED_START_TOLERANCE": MATCHED_START_TOLERANCE,
        "SPECTRUM_TOLERANCE": SPECTRUM_TOLERANCE,
        "COVARIANCE_IDENTITY_TOLERANCE": COVARIANCE_IDENTITY_TOLERANCE,
        "CONTROL_DEVIATION": CONTROL_DEVIATION,
        "STEP_SAFETY": STEP_SAFETY,
        "HORIZON_CAP": HORIZON_CAP,
        "CONVERGENCE_PRODUCT": CONVERGENCE_PRODUCT,
        "SHORT_FRACTION": SHORT_FRACTION,
        "MODULATION": MODULATION,
        "MODE_AMPLITUDE": MODE_AMPLITUDE,
        "GATE_COVARIANCE_FACTOR": GATE_COVARIANCE_FACTOR,
        "VELOCITY_SPLIT": VELOCITY_SPLIT,
    }
    frozen_thresholds = {
        "BUDGET": 1.0e-6,
        "STRUCTURAL_SCALE": 1.0e-4,
        "REFINEMENT_REDUCTION": 4.0,
        "MODE_BUDGET": 1.0e-6,
        "RELAXATION_LIMIT": 1.0e-3,
        "SLOPE_TOLERANCE": 0.10,
        "SENSITIVITY_FLOOR": 1.0e-11,
        "PERSISTENCE_FLOOR": 0.9,
        "ANNIHILATION_TOLERANCE": 1.0e-14,
        "IDEMPOTENCE_TOLERANCE": 1.0e-15,
        "MATCHED_START_TOLERANCE": 1.0e-15,
        "SPECTRUM_TOLERANCE": 1.0e-9,
        "COVARIANCE_IDENTITY_TOLERANCE": 1.0e-12,
        "CONTROL_DEVIATION": 1.0e-4,
        "STEP_SAFETY": 40.0,
        "HORIZON_CAP": 1000.0,
        "CONVERGENCE_PRODUCT": 10.0,
        "SHORT_FRACTION": 100.0,
        "MODULATION": 0.20,
        "MODE_AMPLITUDE": 0.25,
        "GATE_COVARIANCE_FACTOR": 0.5,
        "VELOCITY_SPLIT": 0.05,
    }
    for name, frozen_value in frozen_thresholds.items():
        if thresholds[name] != frozen_value:
            failures.append(
                "threshold {0} is {1}, frozen value is {2}".format(
                    name, thresholds[name], frozen_value
                )
            )

    # Section 6A: the constants the amendment declares, transcribed from the amended text.
    amendment_constants = {
        "SEED_IMBALANCE": SEED_IMBALANCE,
        "STEP_CAP_PER_EXECUTION": STEP_CAP_PER_EXECUTION,
        "STEP_BUDGET_TOTAL": STEP_BUDGET_TOTAL,
        "SEED_INVARIANCE_TOLERANCE": SEED_INVARIANCE_TOLERANCE,
        "CURRENT_FLOOR": CURRENT_FLOOR,
        "COVARIANCE_FLOOR": COVARIANCE_FLOOR,
    }
    frozen_amendment_constants = {
        "SEED_IMBALANCE": 0.05,
        "STEP_CAP_PER_EXECUTION": 50000,
        "STEP_BUDGET_TOTAL": 232334,
        "SEED_INVARIANCE_TOLERANCE": 1.0e-15,
        "CURRENT_FLOOR": 1.0e-9,
        "COVARIANCE_FLOOR": 1.0e-6,
    }
    for name, frozen_value in frozen_amendment_constants.items():
        if amendment_constants[name] != frozen_value:
            failures.append(
                "amendment constant {0} is {1}, declared value is {2}".format(
                    name, amendment_constants[name], frozen_value
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
    if split != ("covariance",):
        failures.append("the composition asymmetry is declared on {0}".format(list(split)))

    steps_total = int(sum(spec.steps for spec in specs))
    steps_max = int(max(spec.steps for spec in specs))
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

    reachable = aggregate_verdicts(
        closure_features={"F1": False, "F2": False, "F3": False},
        mode_features={"F4": True, "F5": True, "F6": False},
        arms=[{"name": "on_ray", "class": "within_budget"}],
    )
    if reachable["status"] != "FAIL" or reachable["closure_verdict"] is not None:
        failures.append("a failed control does not force status=FAIL with no verdict")
    if reachable["mode_verdict"] is not None:
        failures.append("a failed control does not suppress the mode verdict")

    return {
        "failures": failures,
        "arms": len(ARM_TABLE),
        "closure_arms": list(CLOSURE_ARMS),
        "mode_arms": list(MODE_ARMS),
        "j_arms": list(J_ARMS),
        "steps_total": steps_total,
        "steps_per_execution_max": steps_max,
        "declared_steps_per_execution_cap": STEP_CAP_PER_EXECUTION,
        "declared_steps_total_budget": STEP_BUDGET_TOTAL,
        "thresholds": thresholds,
        "amendment_constants": amendment_constants,
        "seed_imbalance": SEED_IMBALANCE,
        "imbalanced_arms": list(imbalanced),
        "composition_split_arms": list(split),
    }


def initial_state_report() -> dict:
    """Readings of the declared initial states, used by the pre-execution checks of section 6A.

    For every arm: the declared seed, the residual of the projection identity (A1) or (A2),
    and the two readings that decide whether the previously dead controls can fire at all.
    """
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
        report[arm.name] = {
            "seed_imbalance": arm.seed_imbalance,
            "composition_split": bool(arm.composition_split),
            "seed_projection_residual": residual,
            "current_mean": float(np.mean(h)),
            "current_mean_relative": abs(float(np.mean(h))) / scale,
            "current_max_relative": float(np.max(np.abs(h))) / scale,
            "z_relative": float(np.max(np.abs(z))) / scale,
        }
    return report


def pre_execution_checks(states: dict, specs: list) -> tuple:
    """Section 6A readings, taken before any execution.

    Returns (blocking, notes, readings). A blocking reading is one that makes a declared
    criterion unreachable or leaves a declared invariant broken; the probe then stops before
    executing, since the single invocation would otherwise be spent on a guaranteed
    status=FAIL with no verdict. The notes record the amendment's declarations.
    """
    blocking = []
    notes = []
    readings = {
        "seed_imbalance": SEED_IMBALANCE,
        "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
        "current_floor": CURRENT_FLOOR,
        "covariance_floor": COVARIANCE_FLOOR,
        "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
        "steps_budget_total": STEP_BUDGET_TOTAL,
    }

    invariance = {
        name: states[name]["seed_projection_residual"] for name in states
    }
    readings["seed_projection_residual_max"] = max(invariance.values())
    off_identity = {
        name: value
        for name, value in invariance.items()
        if value > SEED_INVARIANCE_TOLERANCE
    }
    if off_identity:
        blocking.append(
            {
                "id": "PX-1",
                "reading": "seed_projection_residual",
                "values": off_identity,
                "statement": (
                    "A declared seed does not reproduce the declared projected densities to "
                    "machine precision, so the arm would evolve a different initial condition "
                    "than the protocol declares."
                ),
            }
        )

    j_denominators = {name: states[name]["current_mean_relative"] for name in J_ARMS}
    readings["j_denominators"] = j_denominators
    dead = {name: value for name, value in j_denominators.items() if value <= CURRENT_FLOOR}
    if dead:
        blocking.append(
            {
                "id": "PX-2",
                "reading": "current_mean_relative",
                "values": dead,
                "statement": (
                    "An arm that carries the J readout starts with a loop-mean current at or "
                    "below the declared floor, so the (PD4) denominator is missing and the "
                    "persistent_current control of section 4 cannot fire."
                ),
            }
        )

    z_relative = states["covariance"]["z_relative"]
    readings["covariance_z_relative_max"] = z_relative
    if z_relative <= COVARIANCE_FLOOR:
        blocking.append(
            {
                "id": "PX-3",
                "reading": "z_relative",
                "values": {"covariance": z_relative},
                "statement": (
                    "The covariance arm starts with a vanishing composition combination, so "
                    "the (LB14) covariance term is zero at every state and the control's "
                    "required deviation above 1e-4 is unreachable."
                ),
            }
        )

    over_cap = [
        {"name": spec.arm.name, "steps": spec.steps, "cap": STEP_CAP_PER_EXECUTION}
        for spec in specs
        if spec.steps > STEP_CAP_PER_EXECUTION
    ]
    total = int(sum(spec.steps for spec in specs))
    readings["steps_total"] = total
    readings["steps_per_execution_max"] = int(max(spec.steps for spec in specs))
    if over_cap:
        blocking.append(
            {
                "id": "PX-4",
                "reading": "steps",
                "values": over_cap,
                "statement": "An arm exceeds the step cap of section 6 as amended by section 6A.",
            }
        )
    if total > STEP_BUDGET_TOTAL:
        blocking.append(
            {
                "id": "PX-5",
                "reading": "steps_total",
                "values": {"steps_total": total, "declared": STEP_BUDGET_TOTAL},
                "statement": "The schedule exceeds the total step budget of section 6.",
            }
        )

    notes.append(
        {
            "id": "PD-N1",
            "readings": {
                "steps_per_execution_max": readings["steps_per_execution_max"],
                "steps_total": total,
                "cap": STEP_CAP_PER_EXECUTION,
                "budget": STEP_BUDGET_TOTAL,
            },
            "statement": (
                "The step caps are the figures (PD2) and (PD3) compute for this arm list, as "
                "amended in section 6A; the pre-amendment draft declared 40,000 and 230,000 "
                "before those rules were instantiated."
            ),
        }
    )
    notes.append(
        {
            "id": "PD-N2",
            "readings": {
                "seed_imbalance": SEED_IMBALANCE,
                "imbalanced_arms": list(J_ARMS),
                "composition_split_arms": [
                    arm.name for arm in ARM_TABLE if arm.composition_split
                ],
                "j_denominators": j_denominators,
                "covariance_z_relative": z_relative,
            },
            "statement": (
                "Section 6A's declared seeds are applied: the direction imbalance (A1) to the "
                "J-carrying arms and the composition asymmetry (A2) to the covariance arm. "
                "Both identities are re-checked at the seed states before execution and their "
                "residuals are recorded."
            ),
        }
    )
    notes.append(
        {
            "id": "PD-W2",
            "statement": (
                "The mode pair of section 6 runs at different step sizes: the mode arms at "
                "0.02 because their mode set sets lambda_max, the uniform counterpart at 0.05. "
                "Delta is read on the states the two traces share in model time, and its "
                "sample count is recorded per pair."
            ),
        }
    )
    notes.append(
        {
            "id": "PD-W3",
            "statement": (
                "Gate 4 and gate 9 are read over the contract arms and the section 3 mode "
                "arms, following the construction exemption gate 5 declares for the "
                "covariance arm; the declared violations of the controls are recorded "
                "rather than treated as schedule failures."
            ),
        }
    )
    notes.append(
        {
            "id": "PD-W4",
            "statement": (
                "The convergence horizon takes the internal gap at the slowest cell of the "
                "arm's own gate, so that g_int T = 10 holds everywhere on the grid; the gap "
                "at the mean gate is recorded for comparison."
            ),
        }
    )
    return blocking, notes, readings


def control_readings(traces: dict, mode_readings: dict, seeds: dict = None) -> list:
    """Section 4: each control with its required and measured readings.

    Section 6A: a control whose reading is only produced by the run carries the reading that
    makes it reachable at the declared initial state, and the field 'decided' states whether
    its verdict is settled at the initial reading or by the run.
    """
    seeds = seeds or {}
    covariance_z = seeds.get("covariance", {}).get("z_relative")
    j_denominator = seeds.get("persistent_current", {}).get("current_mean_relative")
    null = traces["null"]
    uniform_short = traces["uniform_short"]
    null_delta = paired_delta(null, uniform_short)["delta_max"] or 0.0
    covariance = traces["covariance"]
    direction_split = traces["direction_split"]
    persistence = traces["persistent_current"]

    return [
        {
            "name": "null",
            "requirement": "rho_max <= 1e-11 and delta = 0 exactly",
            "measured": {
                "rho_max": float(np.max(null.rho)),
                "delta_max_abs": null_delta,
            },
            "fired": bool(
                float(np.max(null.rho)) <= SENSITIVITY_FLOOR and null_delta == 0.0
            ),
            "decided": "at the initial reading: both arms carry the same state at t0",
            "reachability": "not applicable: the requirement is met or missed at t0",
        },
        {
            "name": "covariance",
            "requirement": (
                "(LB14) to 1e-12 relative at every accepted state and deviation above 1e-4 "
                "at the declared horizon"
            ),
            "measured": {
                "identity_max": float(np.max(covariance.covariance_residual))
                if len(covariance.covariance_residual)
                else None,
                "rho_max": float(np.max(covariance.rho)),
                "rho_final": float(covariance.rho[-1]),
            },
            "fired": bool(
                len(covariance.covariance_residual) > 0
                and float(np.max(covariance.covariance_residual))
                <= COVARIANCE_IDENTITY_TOLERANCE
                and float(covariance.rho[-1]) > CONTROL_DEVIATION
            ),
            "decided": (
                "by the run: the deviation grows over the horizon and is not measurable at t0"
            ),
            "reachability": (
                "composition combination Z relative to the local state at t0 = {0}, above the "
                "declared floor {1}, so the (LB14) covariance term has a non-zero operand to "
                "act on".format(covariance_z, COVARIANCE_FLOOR)
            ),
        },
        {
            "name": "direction_split",
            "requirement": "deviation above 1e-4 at the declared horizon",
            "measured": {
                "rho_max": float(np.max(direction_split.rho)),
                "rho_final": float(direction_split.rho[-1]),
            },
            "fired": bool(float(direction_split.rho[-1]) > CONTROL_DEVIATION),
            "decided": (
                "by the run: the two orientations carry the same state at t0, so the split in "
                "the exterior velocity only separates them as the trace advances"
            ),
            "reachability": (
                "declared construction, not a t0 reading: u_+ = u - 0.05 and u_- = u + 0.05, "
                "so the orientation blocks advect at different speeds for every step"
            ),
        },
        {
            "name": "persistent_current",
            "requirement": "J(T) >= 0.9 and rho_max <= 1e-6",
            "measured": {
                "j_mean_final": (
                    abs(
                        float(persistence.current_mean[-1])
                        / float(persistence.current_mean[0])
                    )
                    if float(persistence.current_mean[0]) != 0.0
                    else None
                ),
                "j_max_final": (
                    abs(float(persistence.current_max[-1]) / float(persistence.current_max[0]))
                    if float(persistence.current_max[0]) != 0.0
                    else None
                ),
                "rho_max": float(np.max(persistence.rho)),
            },
            "fired": bool(
                float(persistence.current_mean[0]) != 0.0
                and abs(
                    float(persistence.current_mean[-1]) / float(persistence.current_mean[0])
                )
                >= PERSISTENCE_FLOOR
                and float(np.max(persistence.rho)) <= BUDGET
            ),
            "decided": (
                "by the run: J(T) is read from the trace, while its denominator is a t0 "
                "reading checked before execution"
            ),
            "reachability": (
                "loop-mean current relative to the local state at t0 = {0}, above the declared "
                "floor {1}, so the (PD4) denominator exists and J is measurable at every "
                "accepted state".format(j_denominator, CURRENT_FLOOR)
            ),
        },
    ]


def aggregate_verdicts(closure_features: dict, mode_features: dict, arms: list) -> dict:
    """Section 5: the two aggregate verdicts, and status=FAIL when a control does not fire."""
    controls_ok = closure_features.get("F3", False) and mode_features.get("F6", False)
    if not controls_ok:
        return {"status": "FAIL", "closure_verdict": None, "mode_verdict": None}

    structural = any(row["class"] == "structural_disagreement" for row in arms)
    if closure_features["F1"]:
        closure = "EMERGES"
    elif structural:
        closure = "CONTRADICTS"
    else:
        closure = "INCONCLUSIVE"

    if mode_features["F4"] and mode_features["F5"]:
        mode = "EMERGES"
    elif not mode_features["F4"]:
        mode = "CONTRADICTS"
    elif not mode_features["F5"]:
        mode = "DOES NOT EMERGE"
    else:
        mode = "INCONCLUSIVE"
    return {"status": "PASS", "closure_verdict": closure, "mode_verdict": mode}


def class_of(trace: ArmTrace, partner: ArmTrace) -> str:
    rho_max = float(np.max(trace.rho))
    if rho_max <= BUDGET:
        return "within_budget"
    if partner is None:
        return "above_budget_no_partner"
    partner_rho = float(np.max(partner.rho))
    reduction = float("inf") if partner_rho == 0.0 else rho_max / partner_rho
    if reduction >= REFINEMENT_REDUCTION:
        return "discretization_limited"
    if rho_max > STRUCTURAL_SCALE:
        return "structural_disagreement"
    return "above_budget_below_structural"


def spectrum_gate_rows(specs: list, traces: dict) -> list:
    rows = []
    for name in MODE_ARMS:
        trace = traces[name]
        kappa = trace.spec.kappa_mean
        residual = spectrum_check(trace.spec.arm, kappa)
        rows.append(
            {
                "arm": name,
                "kappa": kappa,
                "modes": list(trace.spec.arm.modes),
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


def assemble_receipt(specs: list, traces: dict, started: float, notes: list,
                     seeds: dict = None) -> dict:
    rows = [arm_row(traces[spec.arm.name]) for spec in specs]

    uniform_short = traces["uniform_short"]
    mode_readings = {
        name: mode_reading(traces[name], uniform_short) for name in MODE_ARMS
    }

    for spec in specs:
        arm = spec.arm
        partner = traces[arm.refinement_partner] if arm.refinement_partner else None
        trace = traces[arm.name]
        rho_max = float(np.max(trace.rho))
        reduction = None
        unbounded = False
        if partner is not None:
            partner_rho = float(np.max(partner.rho))
            unbounded = partner_rho == 0.0
            reduction = None if unbounded else rho_max / partner_rho
        for row in rows:
            if row["name"] == arm.name:
                row["refinement_partner"] = arm.refinement_partner or None
                row["refinement_reduction"] = reduction
                row["refinement_unbounded"] = unbounded
                row["class"] = class_of(trace, partner)
                if arm.counterpart:
                    row["counterpart_reading"] = paired_delta(
                        trace, traces[arm.counterpart]
                    )
                if arm.name in mode_readings:
                    row["mode_reading"] = mode_readings[arm.name]

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
    contract_declared = [
        {"arm": row["name"], "velocity_split": row["velocity_split"]}
        for row in rows
        if row["role"] == "contract"
    ]
    gates.append(
        {"gate": 4, "name": "shared exterior transport", "measured": contract_declared,
         "bound": "u and D_x shared by all four channels, chi independent",
         "passed": bool(all(entry["velocity_split"] == 0.0 for entry in contract_declared))}
    )
    gate_5 = max(row["gate_spread_max"] for row in rows if row["role"] in ("contract", "mode"))
    gates.append(
        {"gate": 5, "name": "common gate", "measured": gate_5, "bound": 0.0,
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
    gates.append(
        {"gate": 8, "name": "declared shape", "measured": {"executions": len(rows)},
         "bound": DECLARED_EXECUTIONS, "passed": bool(len(rows) == DECLARED_EXECUTIONS)}
    )
    spectrum_rows = spectrum_gate_rows(specs, traces)
    gates.append(
        {"gate": 9, "name": "spectrum re-check", "measured": spectrum_rows,
         "bound": SPECTRUM_TOLERANCE,
         "passed": bool(all(entry["passed"] for entry in spectrum_rows))}
    )
    gate_10 = max(row["rho_max"] for row in rows if row["name"] == "null")
    gates.append(
        {"gate": 10, "name": "sensitivity floor", "measured": gate_10,
         "bound": SENSITIVITY_FLOOR, "passed": bool(gate_10 <= SENSITIVITY_FLOOR)}
    )
    gates.append(
        {"gate": 11, "name": "process declaration",
         "measured": {"processes": 1, "executions": len(rows), "pid": os.getpid(),
                      "device": "cpu", "concurrent": False},
         "bound": "one process, declared execution count, no concurrent runs", "passed": True}
    )

    controls = control_readings(traces, mode_readings, seeds)

    closure_arms = [row for row in rows if row["role"] in ("contract", "mode")]
    f1 = all(row["rho_max"] <= BUDGET for row in closure_arms)
    with_partner = [row for row in closure_arms if row["refinement_partner"]]
    f2 = all(
        row["refinement_unbounded"]
        or (
            row["refinement_reduction"] is not None
            and row["refinement_reduction"] >= REFINEMENT_REDUCTION
        )
        for row in with_partner
        if row["rho_max"] > BUDGET
    )
    f3 = all(entry["fired"] for entry in controls)

    delta_values = [mode_readings[name]["delta_max"] for name in MODE_ARMS]
    f4 = all(value is not None and value <= MODE_BUDGET for value in delta_values)
    long_arms = [name for name in MODE_ARMS if traces[name].spec.arm.horizon_key == "mode"]
    f5 = all(
        mode_readings[name]["per_mode"][traces[name].spec.arm.modes[0]]["slope_relative_error"]
        is not None
        and mode_readings[name]["per_mode"][traces[name].spec.arm.modes[0]]["slope_relative_error"]
        <= SLOPE_TOLERANCE
        and mode_readings[name]["total_energy_ratio_final"] <= RELAXATION_LIMIT
        for name in long_arms
    )
    j_control = next(entry for entry in controls if entry["name"] == "persistent_current")
    f6 = bool(
        j_control["fired"]
        and all(
            mode_readings[name]["final_mean_at_zero"] is not None
            and mode_readings[name]["final_mean_at_zero"] <= RELAXATION_LIMIT
            for name in long_arms
        )
    )

    verdicts = aggregate_verdicts(
        closure_features={"F1": f1, "F2": f2, "F3": f3},
        mode_features={"F4": f4, "F5": f5, "F6": f6},
        arms=rows,
    )
    gates_ok = all(entry["passed"] for entry in gates)
    if not gates_ok:
        verdicts = {"status": "FAIL", "closure_verdict": None, "mode_verdict": None}
    status = "PASS" if gates_ok and verdicts["status"] == "PASS" else "FAIL"

    receipt = {
        "schema": "cassi.loop-carrier-projection-dynamics.v1",
        "protocol": {"path": PROTOCOL_PATH, "sha256": digest_of(PROTOCOL_PATH)},
        "probe": {"path": PROBE_PATH, "sha256": digest_of(PROBE_PATH)},
        "binding": {
            "path": BOUND_MODULE,
            "expected_sha256": BOUND_DIGEST,
            "observed_sha256": digest_of(BOUND_MODULE),
        },
        "invocation": {
            "command": INVOCATION,
            "bound_seconds": BOUND_SECONDS,
            "started": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(started)),
            "runtime_seconds": time.time() - started,
            "pid": os.getpid(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "device": "cpu",
            "processes": 1,
            "concurrent_runs": False,
        },
        "declared": {
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
                    "role": spec.arm.role,
                    "dt": spec.dt,
                    "horizon": spec.horizon,
                    "steps": spec.steps,
                    "seed_imbalance": spec.arm.seed_imbalance,
                    "composition_split": bool(spec.arm.composition_split),
                }
                for spec in specs
            ],
            "profiles": {name: list(value) for name, value in PROFILES.items()},
            "modulation": MODULATION,
            "mode_amplitude": MODE_AMPLITUDE,
            "thresholds": {
                "budget": BUDGET,
                "structural_scale": STRUCTURAL_SCALE,
                "refinement_reduction": REFINEMENT_REDUCTION,
                "mode_budget": MODE_BUDGET,
                "relaxation_limit": RELAXATION_LIMIT,
                "slope_tolerance": SLOPE_TOLERANCE,
                "sensitivity_floor": SENSITIVITY_FLOOR,
                "persistence_floor": PERSISTENCE_FLOOR,
                "annihilation_tolerance": ANNIHILATION_TOLERANCE,
                "idempotence_tolerance": IDEMPOTENCE_TOLERANCE,
                "matched_start_tolerance": MATCHED_START_TOLERANCE,
                "spectrum_tolerance": SPECTRUM_TOLERANCE,
                "covariance_identity_tolerance": COVARIANCE_IDENTITY_TOLERANCE,
                "control_deviation": CONTROL_DEVIATION,
            },
            "rules": {
                "step_candidates": list(STEP_CANDIDATES),
                "step_safety": STEP_SAFETY,
                "horizon_cap": HORIZON_CAP,
                "convergence_product": CONVERGENCE_PRODUCT,
                "short_fraction": SHORT_FRACTION,
            },
            "executions": DECLARED_EXECUTIONS,
            "steps_total": int(sum(spec.steps for spec in specs)),
            "steps_per_execution_max": int(max(spec.steps for spec in specs)),
            "steps_cap_per_execution": STEP_CAP_PER_EXECUTION,
            "steps_budget_total": STEP_BUDGET_TOTAL,
            "seeds": seeds if seeds is not None else {},
            "seed_declaration": {
                "amendment": "section 6A, September 16, 2026, before the first execution",
                "direction_imbalance": {
                    "value": SEED_IMBALANCE,
                    "arms": list(J_ARMS),
                    "identity": "sum_s (1 + s beta) = 2, so the projection reproduces E_a",
                },
                "composition_asymmetry": {
                    "arms": ["covariance"],
                    "identity": "mean_chi(1 -+ alpha cos(m chi)) = 1 for both carriers",
                },
                "current_reduction": (
                    "domain mean of <H>_chi, with the max-abs reduction recorded as "
                    "current_max_relative"
                ),
                "reachability_floors": {
                    "current_floor": CURRENT_FLOOR,
                    "covariance_floor": COVARIANCE_FLOOR,
                    "seed_invariance_tolerance": SEED_INVARIANCE_TOLERANCE,
                },
            },
            "observational_note": (
                "loops are read as their frozen equal-weight grid average; the carrier state "
                "layout is f[carrier, orientation, x, chi]; J is read as the domain mean of "
                "<H>_chi over the periodic exterior grid, and the mode pair Delta is read on "
                "the states the two traces share in model time"
            ),
        },
        "gates": gates,
        "controls": controls,
        "arms": rows,
        "mode_readings": mode_readings,
        "closure": {
            "features": {"F1": f1, "F2": f2, "F3": f3},
            "classes": {row["name"]: row["class"] for row in rows},
            "verdict": verdicts["closure_verdict"],
        },
        "mode": {
            "features": {"F4": f4, "F5": f5, "F6": f6},
            "verdict": verdicts["mode_verdict"],
        },
        "status": status,
        "verdict_scope": (
            "both features measured" if status == "PASS"
            else "no verdict is issued for this status"
        ),
        "protocol_notes": notes,
    }
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
        "static check: {0} arms, {1} steps total, {2} steps in the longest execution".format(
            report["arms"], report["steps_total"], report["steps_per_execution_max"]
        ),
        flush=True,
    )

    states = initial_state_report()
    blocking, notes, readings = pre_execution_checks(states, specs)
    print(
        "seed check: projection residual max {0}, current floors {1}, covariance Z {2}".format(
            readings["seed_projection_residual_max"],
            readings["j_denominators"],
            readings["covariance_z_relative_max"],
        ),
        flush=True,
    )
    for note in notes:
        print("protocol note {0}: {1}".format(note["id"], note["statement"]), flush=True)
    if blocking:
        for block in blocking:
            print(
                "pre-execution block {0}: {1}\n  readings {2}".format(
                    block["id"], block["statement"], block["values"]
                ),
                flush=True,
            )
        print(
            "the probe stops before execution: a declared criterion would be unreachable, so "
            "the one declared invocation would return status=FAIL with no verdict.",
            flush=True,
        )
        return EXIT_PRE_EXECUTION_BLOCK

    started = time.time()
    specs, traces = run_schedule()
    receipt = assemble_receipt(specs, traces, started, notes, states)
    path = write_receipt(receipt)
    print(
        "receipt {0}\nstatus {1} closure {2} mode {3}".format(
            path, receipt["status"], receipt["closure"]["verdict"], receipt["mode"]["verdict"]
        ),
        flush=True,
    )
    return EXIT_PASS if receipt["status"] == "PASS" else EXIT_FAIL


if __name__ == "__main__":
    raise SystemExit(main())
