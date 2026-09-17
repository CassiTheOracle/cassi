"""Protocol executor: how much gate asymmetry the loop-carrier projection tolerates.

Frozen with computations/loop-carrier-gate-load-prereg.md in the same commit. The static
pass and the run are separate: --self-check verifies the binding by digest, the declared
schedule, the label vocabulary, the FAIL reachability and the pre-flight action checks,
writes nothing, and is idempotent, so it can be re-run after an invocation. A bare
invocation runs the twenty-two declared arms once, writes one receipt, and refuses a
second while that receipt exists.

Two imported constructions, both at bound digests, and nothing re-derived:

* the split right-hand side, from the spent protocol's executed executor
  (`verify_loop_carrier_projection_split.split_rhs`), so the gate split here is the same
  construction that produced the spent reading and not a re-derivation of it;
* the carrier law, projection, integrator, canonical companion and seeds, from the
  successor's executed probe (`verify_loop_carrier_projection_relaxation`).

The design remark that makes this protocol possible: the conversion term is kappa_a B with
B = -psi_Y + phi psi_I, B obeys a homogeneous equation when the carriers share a velocity,
and the spent protocol's seed sits on the ray, so B is zero there and a gate split could
multiply only zero. Here the seed family loads B by a declared, measured amount ell through
a pure transfer between the carriers, and the statistic is the separation between a split
arm and its own unsplit twin, read as a peak with the terminal value recorded beside it.

The pre-flight checks the action rather than the operand: on the seeded state, before any
integration, the bracket's rate under the split,
d/dt B|conv = -(kappa_y + phi kappa_i) B with kappa_a = kappa (1 +- delta_g cos chi), must
change by at least ACTION_FLOOR_LIVE of the right-hand side's magnitude at the largest load
and by no more than ACTION_CEIL_SILENT on the ray seed. Both directions are checked here and
again as run-time gates 4 and 5.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# The spent protocol's executor, imported for its split construction. Its module level only
# defines constants and functions; it reads no file and imports no probe until called.
import verify_loop_carrier_projection_split as split  # noqa: E402

# Frozen sources, all by digest. The bound module is the discrete operator layer; the base
# probe is the successor's executed probe; the split executor carries the split right-hand
# side; the two receipts carry the oracle readings of section 5, read rather than typed.
BOUND_MODULE = "computations/verify_loop_to_bubble_projection.py"
BOUND_DIGEST = "d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1"
BASE_PROBE = "computations/verify_loop_carrier_projection_relaxation.py"
BASE_PROBE_DIGEST = "28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622"
BASE_RECEIPT = "runs/loop_carrier_projection_relaxation/verification.json"
BASE_RECEIPT_DIGEST = "3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1"
SPLIT_EXECUTOR = "computations/verify_loop_carrier_projection_split.py"
SPLIT_EXECUTOR_DIGEST = "246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a"
SPLIT_RECEIPT = "runs/loop_carrier_projection_split/verification.json"
SPLIT_RECEIPT_DIGEST = "559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc"

PROTOCOL_PATH = "computations/loop-carrier-gate-load-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_gate_load.py"
RECEIPT_PATH = "runs/loop_carrier_gate_load/verification.json"
INVOCATION = "timeout 600 python computations/verify_loop_carrier_gate_load.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-gate-load.v1"
BOUND_SECONDS = 600.0

# Section 0 of the protocol declares both hashes: this file's, and the digest of the frozen
# body (everything from "## 1." to just before "## 8."). The two are cross-bound without a
# fix point, because section 0 sits outside the body range. Filled by the freeze pass.
FROZEN_BODY_DIGEST = "8f3fae24990b7b74632f08f3f6d4dde4e476e6d81f3ad8a5d903b37659c06268"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.4: the declared thresholds.
CLASS_BOUND = 1.0e-6
SILENCE_FLOOR = 1.0e-14
READABLE_FLOOR = 1.0e-13
MIN_READABLE = 4
FIT_BAND = 2.0
EXPONENT_LOW = 0.9
EXPONENT_HIGH = 1.1
JUMP_FACTOR = 3.0
MONOTONE_TOLERANCE = 1.5
LEVEL_RATIO = 10.0
ACTION_FLOOR_LIVE = 1.0e-3
ACTION_CEIL_SILENT = 1.0e-15
LOAD_TOL = 1.0e-12
LOAD_ABS_FLOOR = 1.0e-15
STEP_SAFETY = 40.0
PER_EXECUTION_CAP = 50000
TOTAL_STEP_CAP = 30000
DECLARED_EXECUTIONS = 22
PROJECTED_SECONDS = 12.0

# Section 1.1: everything the successor fixes and this protocol carries unchanged.
PROFILE = "on_ray"
STEP_CANDIDATES = (0.05, 0.02, 0.01)
SNAP_DT = 0.02
SNAP_HORIZON = 12.0
SNAP_STEPS = 600
SHORT_DT = 0.02
SHORT_HORIZON = 2.0
SHORT_STEPS = 100
REPLICATION_DT = 0.02
REPLICATION_HORIZON = 36.66172105812361
REPLICATION_STEPS = 1834

# Section 3: the declared split sizes and the declared load family.
SUPERSPLIT_LEVEL = 1.0
SWEEP_LEVEL = 1.0e-2
DECADES = (1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1)
LOADS = (
    (2.0e-3, 4.229224947788e-3),
    (5.0e-3, 1.054750439224e-2),
    (1.25e-2, 2.621036695567e-2),
    (3.2e-2, 6.606671655346e-2),
    (8.0e-2, 1.591427818933e-1),
    (2.0e-1, 3.646114292316e-1),
    (0.0, 0.0),
)
PREDICTED_LOAD = dict(LOADS)
LARGEST_LOAD = 2.0e-1

# Section 5: the bit-identity oracle readings, read from the two digest-bound receipts and
# declared here as literals so that a receipt cannot drift silently under the oracle.
ORACLE_RAY_RHO = 5.329147248815693e-16
ORACLE_REPLICATION_RHO = 2.622443969747147e-15
ORACLE_REPLICATION_FINAL = 2.219140084394095e-15
ORACLE_REPLICATION_LAMBDA = 1.0331312281605476

VERDICT_A_LABELS = ("PROPORTIONAL", "CLIFF", "NONLINEAR", "INCONCLUSIVE")
VERDICT_B_LABELS = ("LINEAR_IN_LOAD", "SUPERLINEAR", "SUBLINEAR", "NONLINEAR_IN_LOAD",
                    "INCONCLUSIVE")


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


def check_binding(expect_body: str = None, expect_executor: str = None) -> dict:
    """Refuse to run on any hash mismatch, before any arm is constructed."""
    problems = []
    declared = {
        "frozen_body_sha256": protocol_row("frozen_body_sha256"),
        "executor_sha256": protocol_row("executor_sha256"),
        "bound_module_sha256": protocol_row("bound_module_sha256"),
        "base_probe_sha256": protocol_row("base_probe_sha256"),
        "split_executor_sha256": protocol_row("split_executor_sha256"),
        "base_receipt_sha256": protocol_row("base_receipt_sha256"),
        "split_receipt_sha256": protocol_row("split_receipt_sha256"),
    }
    observed = {
        "frozen_body_sha256": protocol_body_digest(),
        "executor_sha256": digest_of(PROBE_PATH),
        "bound_module_sha256": digest_of(BOUND_MODULE),
        "base_probe_sha256": digest_of(BASE_PROBE),
        "split_executor_sha256": digest_of(SPLIT_EXECUTOR),
        "base_receipt_sha256": digest_of(BASE_RECEIPT),
        "split_receipt_sha256": digest_of(SPLIT_RECEIPT),
    }
    if declared["frozen_body_sha256"] != FROZEN_BODY_DIGEST:
        problems.append(
            "the protocol body digest and this executor's constant disagree: {0} vs {1}".format(
                declared["frozen_body_sha256"], FROZEN_BODY_DIGEST
            )
        )
    for key in sorted(declared):
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
    if expect_executor is not None and observed["executor_sha256"] != expect_executor:
        problems.append(
            "disturbed binding on executor_sha256: expected {0}, observed {1}".format(
                expect_executor, observed["executor_sha256"]
            )
        )
    if problems:
        for problem in problems:
            print("REFUSING TO RUN: {0}".format(problem))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"declared": declared, "observed": observed}


def load_modules():
    """Import the successor probe through the spent executor's own loader.

    The loader converts the successor probe's binding refusal into this protocol's, so a
    disturbed operator module stops the run before any arm exists.
    """
    try:
        return split.load_base()
    except SystemExit:
        print("REFUSING TO RUN: the successor probe's own binding of the frozen operators "
              "failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)


class LoadSpec(split.SplitSpec):
    """One declared arm of section 3, with a declared load and a declared twin."""

    def __init__(self, index: int, name: str, role: str, load_c: float, delta_g: float,
                 schedule_key: str = "snap", twin: str = ""):
        split.SplitSpec.__init__(self, index, name, role, delta_g, 0.0, 0.0, -1)
        self.role = role
        self.load_c = float(load_c)
        self.schedule_key = schedule_key
        self.twin = twin

    def declared_schedule(self) -> tuple:
        if self.schedule_key == "short":
            return SHORT_DT, SHORT_HORIZON, SHORT_STEPS
        if self.schedule_key == "replication":
            return REPLICATION_DT, REPLICATION_HORIZON, REPLICATION_STEPS
        return SNAP_DT, SNAP_HORIZON, SNAP_STEPS


def build_arm_table() -> tuple:
    arms = [
        LoadSpec(1, "ray_short", "reference", 0.0, 0.0, "short"),
        LoadSpec(2, "ray_reference", "reference", 0.0, 0.0),
        LoadSpec(3, "ray_supersplit", "silence", 0.0, SUPERSPLIT_LEVEL, "snap",
                 "ray_reference"),
        LoadSpec(4, "successor_replication", "reference", 0.0, 0.0, "replication"),
    ]
    index = 5
    for position, (load_c, _) in enumerate(LOADS[:-2]):
        arms.append(LoadSpec(index, "loadL{0}_reference".format(position + 1), "reference",
                             load_c, 0.0))
        index += 1
        arms.append(LoadSpec(index, "loadL{0}_arm".format(position + 1), "sweep", load_c,
                             SWEEP_LEVEL, "snap", "loadL{0}_reference".format(position + 1)))
        index += 1
    arms.append(LoadSpec(index, "loadLmax_reference", "reference", LARGEST_LOAD, 0.0))
    index += 1
    for position, level in enumerate(DECADES):
        arms.append(LoadSpec(index, "decade_{0}".format(position + 1), "sweep", LARGEST_LOAD,
                             level, "snap", "loadLmax_reference"))
        index += 1
    arms.append(LoadSpec(index, "supersplit_load", "supersplit", LARGEST_LOAD,
                         SUPERSPLIT_LEVEL, "snap", "loadLmax_reference"))
    return tuple(arms)


ARM_TABLE = build_arm_table()
DECADE_ARMS = tuple(arm for arm in ARM_TABLE if arm.name.startswith("decade_"))
FIT_B_ARMS = tuple(arm for arm in ARM_TABLE
                   if arm.name in ("loadL1_arm", "loadL2_arm", "loadL3_arm", "loadL4_arm",
                                   "loadL5_arm", "decade_5"))
TWIN_NAMES = tuple(sorted({arm.twin for arm in ARM_TABLE if arm.twin}))


def loaded_seed(spec: LoadSpec, base) -> np.ndarray:
    """Section 1.3: the successor seed with the declared transfer between its carriers.

    psi_Y <- psi_Y + (c/2) rho, psi_I <- psi_I - (c/2) rho with rho the seed's own local
    total, so the total is preserved, no new loop mode is introduced, and the bracket
    B = -psi_Y + phi psi_I becomes -(c/2)(1 + phi) rho. At c = 0 nothing is added and the
    state is the spent protocol's seed bit for bit.
    """
    state = split.initial_state(spec, base)
    if spec.load_c == 0.0:
        return state
    total = state[0] + state[1]
    half = spec.load_c / 2.0
    loaded = state.copy()
    loaded[0] = state[0] + half * total
    loaded[1] = state[1] - half * total
    return loaded


def bracket_of(state: np.ndarray, base) -> np.ndarray:
    """B = -psi_Y + phi psi_I elementwise, the channel the conversion term multiplies."""
    return -state[0] + base.PHI * state[1]


def load_of(state: np.ndarray, base) -> float:
    """Section 1.3: ell = max|B| / max|psi| at t0."""
    return float(np.max(np.abs(bracket_of(state, base))) / np.max(np.abs(state)))


def load_comparison(spec: LoadSpec, measured: float) -> dict:
    predicted = PREDICTED_LOAD[spec.load_c]
    if predicted == 0.0:
        return {"declared_transfer": spec.load_c, "predicted": 0.0, "measured": measured,
                "absolute_error": measured, "tolerance": LOAD_ABS_FLOOR,
                "passed": bool(measured <= LOAD_ABS_FLOOR)}
    relative = abs(measured - predicted) / predicted
    return {"declared_transfer": spec.load_c, "predicted": predicted, "measured": measured,
            "relative_error": relative, "tolerance": LOAD_TOL,
            "passed": bool(relative <= LOAD_TOL)}


def rho_of(projection: np.ndarray, canonical: np.ndarray) -> float:
    """The successor's own residual, recorded beside the separation and never gated."""
    return float(
        np.max(np.abs(projection - canonical)) / max(1.0, float(np.max(np.abs(canonical))))
    )


def annihilation_of(state: np.ndarray, base) -> float:
    """The loop-shape integrity reading the spent protocol records, recorded here too."""
    dchi = base.loop_dx(state.shape[base.LOOP_AXIS])
    magnitude = max(float(np.max(np.abs(state))), 1.0)
    return max(
        float(np.max(np.abs(
            base.frozen.derivative(state, base.LOOP_AXIS, dchi).sum(axis=base.LOOP_AXIS)
        ))) / magnitude,
        float(np.max(np.abs(
            base.frozen.laplacian(state, base.LOOP_AXIS, dchi).sum(axis=base.LOOP_AXIS)
        ))) / magnitude,
    )


def bracket_action(state: np.ndarray, spec: LoadSpec, base, delta_g: float) -> dict:
    """Section 5.1 and 5.2: the split's action on the bracket's rate, before integration.

    The conversion channel contributes d/dt B = -(kappa_y + phi kappa_i) B, so the split's
    action is that rate at delta_g minus the same rate at zero. It is nonzero exactly when B
    is nonzero, which is the property the spent protocol's seed lacked.
    """
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])[:, None]
    cosine = np.cos(base.loop_grid(state.shape[base.LOOP_AXIS]))[None, :]
    bracket = bracket_of(state, base)

    def rate(level: float) -> np.ndarray:
        return -(kappa * (1.0 + level * cosine)
                 + base.PHI * kappa * (1.0 - level * cosine)) * bracket

    delta = rate(delta_g) - rate(0.0)
    probe = LoadSpec(0, "action", "action", spec.load_c, delta_g)
    rhs = split.split_rhs(state, kappa, probe, base)
    return {
        "declared_transfer": spec.load_c,
        "delta_g": delta_g,
        "absolute": float(np.max(np.abs(delta))),
        "relative": float(np.max(np.abs(delta)) / float(np.max(np.abs(rhs)))),
        "bracket": float(np.max(np.abs(bracket))),
    }


def reduction_residual(spec: LoadSpec, base) -> float:
    """Section 5.3: the split right-hand side at zero split against the successor's own."""
    state = loaded_seed(spec, base)
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])[:, None]
    zero = LoadSpec(0, "reduction", "reduction", spec.load_c, 0.0)
    left = split.split_rhs(state, kappa, zero, base)
    right = base.carrier_rhs(state, kappa, split.proxy_arm(zero, base))
    return float(np.max(np.abs(left - right)))


def run_arm(spec: LoadSpec, base, twin_trace) -> dict:
    """One declared arm, its own schedule, and its separation against its twin's trace."""
    state = loaded_seed(spec, base)
    dt, horizon, steps = spec.declared_schedule()
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])
    lambda_max = float(base.arm_lambda_max(split.proxy_arm(spec, base), kappa))
    conformant = bool(dt <= 1.0 / (STEP_SAFETY * lambda_max) and dt in STEP_CANDIDATES)
    comparison = load_comparison(spec, load_of(state, base))

    self_twin = twin_trace is None
    scale = 1.0
    if not self_twin:
        scale = max(1.0, max(float(np.max(np.abs(item))) for item in twin_trace))

    canonical = base.canonical_initial(PROFILE)
    trace = [] if self_twin else None
    sigma, rho = [], []
    minimum, minimum_projection, q_low, q_high = [], [], [], []
    annihilation, idempotence = [], []
    for index in range(steps + 1):
        if trace is not None:
            trace.append(state)
        current = base.projection(state)
        rho.append(rho_of(current, canonical))
        if not self_twin:
            sigma.append(float(np.max(np.abs(state - twin_trace[index]))) / scale)
        minimum.append(float(np.min(state)))
        minimum_projection.append(float(np.min(current)))
        composition = base.frozen.bounded_q(current[0], current[1])
        q_low.append(float(np.min(composition)))
        q_high.append(float(np.max(composition)))
        annihilation.append(annihilation_of(state, base))
        idempotence.append(base.relative_residual(
            base.projection(base.lift(current, state.shape[base.LOOP_AXIS])), current))
        if index == steps:
            break
        state = split.split_step(state, dt, spec, base)
        canonical = base.canonical_step(canonical, dt)

    peak = max(sigma) if sigma else 0.0
    terminal = sigma[-1] if sigma else 0.0
    return {
        "index": spec.index,
        "name": spec.name,
        "role": spec.role,
        "declared": {
            "load_transfer": spec.load_c,
            "delta_g": spec.delta_g,
            "schedule_key": spec.schedule_key,
            "twin": spec.twin,
            "modes": list(spec.modes),
            "alpha": spec.alpha,
            "seed_imbalance": spec.seed_imbalance,
        },
        "load": comparison,
        "schedule": {
            "dt": dt,
            "horizon": horizon,
            "steps": steps,
            "lambda_max": lambda_max,
            "rule_conformant": conformant,
        },
        "separation": {
            "peak": float(peak),
            "peak_time": float(int(np.argmax(sigma)) * dt) if sigma else 0.0,
            "terminal": float(terminal),
            "scale": float(scale),
            "peak_terminal_ratio": (float(terminal / peak) if peak > 0.0 else None),
            "readable": bool(peak > READABLE_FLOOR),
            "class": "within_budget" if peak <= CLASS_BOUND else "above_budget",
            "self_twin": self_twin,
        },
        "rho": {"max": float(np.max(rho)), "final": float(rho[-1]),
                "peak_time": float(int(np.argmax(rho)) * dt)},
        "structure": {
            "min_state": float(np.min(minimum)),
            "min_projection": float(np.min(minimum_projection)),
            "q_min": float(np.min(q_low)),
            "q_max": float(np.max(q_high)),
            "annihilation_max": float(np.max(annihilation)),
            "idempotence_max": float(np.max(idempotence)),
        },
        "steps_recorded": int(steps + 1),
        "trace": trace,
    }


def fit_law(levels: tuple, readings: tuple) -> dict:
    """Least squares in log space: exponent, power-law coefficient, per-level residuals."""
    pairs = [(float(level), float(value)) for level, value in zip(levels, readings)
             if value > READABLE_FLOOR]
    if len(pairs) < 2:
        return {"readable": len(pairs), "exponent": None, "coefficient": None,
                "ratios": [], "pairs": pairs}
    x = np.array([pair[0] for pair in pairs], dtype=np.float64)
    y = np.array([pair[1] for pair in pairs], dtype=np.float64)
    exponent = float(np.polyfit(np.log(x), np.log(y), 1)[0])
    coefficient = float(np.exp(np.mean(np.log(y) - exponent * np.log(x))))
    ratios = [float(value / (coefficient * level ** exponent)) for level, value in pairs]
    return {"readable": len(pairs), "exponent": exponent, "coefficient": coefficient,
            "ratios": ratios, "pairs": pairs}


def monotone(values: tuple) -> bool:
    return all(
        values[index + 1] * MONOTONE_TOLERANCE >= values[index]
        for index in range(len(values) - 1)
    )


def label_split_law(levels: tuple, readings: tuple) -> dict:
    """Section 2.5, fit A: on the declared levels and readings alone."""
    fit = fit_law(levels, readings)
    readable = [value for value in readings if value > READABLE_FLOOR]
    reasons = []
    if fit["readable"] < MIN_READABLE:
        reasons.append("only {0} of {1} levels are readable above {2}".format(
            fit["readable"], len(levels), READABLE_FLOOR))
        return {"label": "INCONCLUSIVE", "fit": fit, "reasons": reasons, "jumps": [],
                "monotone": None}
    ordered = monotone(readable)
    jumps = [float(readable[index + 1] / readable[index])
             for index in range(len(readable) - 1)]
    in_band = all(1.0 / FIT_BAND <= ratio <= FIT_BAND for ratio in fit["ratios"])
    implied = LEVEL_RATIO ** fit["exponent"]
    cliff = any(jump >= JUMP_FACTOR * implied for jump in jumps)
    if not ordered:
        reasons.append("the response is not monotone over the readable levels")
        label = "INCONCLUSIVE"
    elif in_band and EXPONENT_LOW <= fit["exponent"] <= EXPONENT_HIGH:
        reasons.append("every readable level is within the factor {0} of the fitted line "
                       "and the fitted exponent is {1}".format(FIT_BAND, fit["exponent"]))
        label = "PROPORTIONAL"
    elif cliff:
        reasons.append("an adjacent pair grows by at least {0} x the growth the fitted "
                       "exponent {1} implies".format(JUMP_FACTOR, fit["exponent"]))
        label = "CLIFF"
    else:
        reasons.append("monotone but off the fitted line: exponent {0}, ratios {1}".format(
            fit["exponent"], fit["ratios"]))
        label = "NONLINEAR"
    return {"label": label, "fit": fit, "reasons": reasons, "jumps": jumps,
            "monotone": ordered, "in_band": in_band}


def label_load_law(levels: tuple, readings: tuple) -> dict:
    """Section 2.5, fit B: the same fit, read for how the authority scales with the load."""
    fit = fit_law(levels, readings)
    readable = [value for value in readings if value > READABLE_FLOOR]
    reasons = []
    if fit["readable"] < MIN_READABLE:
        reasons.append("only {0} of {1} loads are readable above {2}".format(
            fit["readable"], len(levels), READABLE_FLOOR))
        return {"label": "INCONCLUSIVE", "fit": fit, "reasons": reasons, "jumps": [],
                "monotone": None}
    ordered = monotone(readable)
    jumps = [float(readable[index + 1] / readable[index])
             for index in range(len(readable) - 1)]
    in_band = all(1.0 / FIT_BAND <= ratio <= FIT_BAND for ratio in fit["ratios"])
    exponent = fit["exponent"]
    if not ordered:
        reasons.append("the response is not monotone over the readable loads")
        label = "INCONCLUSIVE"
    elif exponent > EXPONENT_HIGH:
        reasons.append("monotone with a load exponent of {0}, above the linear band".format(
            exponent))
        label = "SUPERLINEAR"
    elif exponent < EXPONENT_LOW:
        reasons.append("monotone with a load exponent of {0}, below the linear band".format(
            exponent))
        label = "SUBLINEAR"
    elif in_band:
        reasons.append("every readable load is within the factor {0} of the fitted line and "
                       "the load exponent is {1}".format(FIT_BAND, exponent))
        label = "LINEAR_IN_LOAD"
    else:
        reasons.append("the load exponent is {0} but a readable load lies outside the "
                       "factor {1} of the fitted line".format(exponent, FIT_BAND))
        label = "NONLINEAR_IN_LOAD"
    return {"label": label, "fit": fit, "reasons": reasons, "jumps": jumps,
            "monotone": ordered, "in_band": in_band}


def crossing(fit: dict, bound: float) -> float:
    """The level at which the fitted law reaches the bound, or None if it cannot."""
    if fit["readable"] < 2 or fit["coefficient"] is None:
        return None
    if fit["exponent"] <= 0.0 or fit["coefficient"] <= 0.0:
        return None
    return float((bound / fit["coefficient"]) ** (1.0 / fit["exponent"]))


def decide(decade_readings: tuple, load_levels: tuple, load_readings: tuple) -> dict:
    split_law = label_split_law(DECADES, decade_readings)
    load_law = label_load_law(load_levels, load_readings)
    return {
        "split_law": split_law,
        "load_law": load_law,
        "split_label": split_law["label"],
        "load_label": load_law["label"],
        "instrument": {
            "delta_star": crossing(split_law["fit"], CLASS_BOUND),
            "ell_star": crossing(load_law["fit"], CLASS_BOUND),
            "split_class_membership": [
                "within_budget" if value <= CLASS_BOUND else "above_budget"
                for value in decade_readings
            ],
            "load_class_membership": [
                "within_budget" if value <= CLASS_BOUND else "above_budget"
                for value in load_readings
            ],
        },
    }


def read_oracle() -> dict:
    """Section 5: the oracle readings, read from the two digest-bound receipts.

    Each declared literal is checked against its receipt's own value here, so a receipt that
    drifted without its digest changing is impossible and a receipt that changed at all
    fails the binding first.
    """
    with open(os.path.join(ROOT, SPLIT_RECEIPT), encoding="utf-8") as handle:
        split_receipt = json.load(handle)
    with open(os.path.join(ROOT, BASE_RECEIPT), encoding="utf-8") as handle:
        base_receipt = json.load(handle)
    ray = float(split_receipt["arms"]["common_reference"]["rho_max"])
    replication = [arm for arm in base_receipt["arms"] if arm["name"] == "mode1_long"][0]
    problems = []
    if ray != ORACLE_RAY_RHO:
        problems.append("the split receipt holds {0} for common_reference where this "
                        "protocol declares {1}".format(ray, ORACLE_RAY_RHO))
    if float(replication["rho_max"]) != ORACLE_REPLICATION_RHO:
        problems.append("the successor receipt holds {0} for mode1_long where this protocol "
                        "declares {1}".format(replication["rho_max"], ORACLE_REPLICATION_RHO))
    if float(replication["rho_final"]) != ORACLE_REPLICATION_FINAL:
        problems.append("the successor receipt holds {0} for mode1_long's terminal residual "
                        "where this protocol declares {1}".format(
                            replication["rho_final"], ORACLE_REPLICATION_FINAL))
    if float(replication["lambda_max"]) != ORACLE_REPLICATION_LAMBDA:
        problems.append("the successor receipt holds {0} for mode1_long's lambda_max where "
                        "this protocol declares {1}".format(
                            replication["lambda_max"], ORACLE_REPLICATION_LAMBDA))
    if problems:
        for problem in problems:
            print("REFUSING TO RUN: {0}".format(problem))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {
        "ray_rho": ray,
        "replication_rho": float(replication["rho_max"]),
        "replication_final": float(replication["rho_final"]),
        "replication_lambda": float(replication["lambda_max"]),
    }


def gate_rows(arms: dict, action: dict, comparison_ok: bool, budget: dict) -> list:
    """Section 4.1: every gate with its reading, its bound and its verdict."""
    structural = all(
        arm["structure"]["min_state"] >= 0.0
        and np.isfinite(arm["structure"]["min_state"])
        and np.isfinite(arm["structure"]["min_projection"])
        and 0.0 <= arm["structure"]["q_min"] <= arm["structure"]["q_max"] < 1.0
        and np.isfinite(arm["structure"]["annihilation_max"])
        and np.isfinite(arm["structure"]["idempotence_max"])
        for arm in arms.values()
    )
    conformant = all(arm["schedule"]["rule_conformant"] for arm in arms.values())
    measured = {name: arms[name]["load"]["measured"] for name in
                ("loadL1_reference", "loadL2_reference", "loadL3_reference",
                 "loadL4_reference", "loadL5_reference", "loadLmax_reference",
                 "ray_reference")}
    ordered = [measured[name] for name in
               ("loadL1_reference", "loadL2_reference", "loadL3_reference",
                "loadL4_reference", "loadL5_reference", "loadLmax_reference")]
    monotone_loads = all(ordered[index + 1] > ordered[index]
                         for index in range(len(ordered) - 1))
    shape_ok = (budget["executions"] == DECLARED_EXECUTIONS
                and budget["steps_max"] <= PER_EXECUTION_CAP
                and budget["steps_total"] <= TOTAL_STEP_CAP)
    silence = arms["ray_supersplit"]["separation"]["peak"]
    firer = arms["supersplit_load"]["separation"]["peak"]
    ray_oracle = arms["ray_short"]["rho"]["max"]
    replication_arm = arms["successor_replication"]
    rows = [
        {"id": 1, "name": "binding", "reading": "seven rows declared against observed, all "
         "exact", "bound": "exact", "passed": True},
        {"id": 2, "name": "structure", "reading": "minimum state and projection, the "
         "composition bounds, and the annihilation and idempotence maxima over every "
         "recorded state", "bound": "nonnegative states, 0 <= q < 1", "passed": bool(structural)},
        {"id": 3, "name": "load metric", "reading": {"measured": measured,
         "declared": {name: arms[name]["load"]["predicted"] for name in measured}},
         "bound": "relative {0}, absolute {1} for the bracket-free member".format(
             LOAD_TOL, LOAD_ABS_FLOOR), "passed": bool(comparison_ok)},
        {"id": 4, "name": "action live", "reading": action["live"]["relative"],
         "bound": ">= {0}".format(ACTION_FLOOR_LIVE),
         "passed": bool(action["live"]["relative"] >= ACTION_FLOOR_LIVE)},
        {"id": 5, "name": "action silent", "reading": action["silent"]["relative"],
         "bound": "<= {0}".format(ACTION_CEIL_SILENT),
         "passed": bool(action["silent"]["relative"] <= ACTION_CEIL_SILENT)},
        {"id": 6, "name": "schedule conformance", "reading": "dt against the rule on every "
         "arm's own loaded projection", "bound": "dt <= 1/(40 lambda_max), declared set",
         "passed": bool(conformant)},
        {"id": 7, "name": "declared shape", "reading": budget, "bound": "{0} executions, "
         "{1} per execution, {2} total".format(DECLARED_EXECUTIONS, PER_EXECUTION_CAP,
                                               TOTAL_STEP_CAP),
         "passed": bool(shape_ok)},
        {"id": 8, "name": "silence at zero load", "reading": silence,
         "bound": "<= {0}".format(SILENCE_FLOOR), "passed": bool(silence <= SILENCE_FLOOR)},
        {"id": 9, "name": "can-fail at the largest load", "reading": firer,
         "bound": ">= {0}".format(CLASS_BOUND), "passed": bool(firer >= CLASS_BOUND)},
        {"id": 10, "name": "cross-protocol oracle", "reading": ray_oracle,
         "bound": "bit-identical to {0}".format(ORACLE_RAY_RHO),
         "passed": bool(ray_oracle == ORACLE_RAY_RHO)},
        {"id": 11, "name": "cross-executor oracle",
         "reading": [replication_arm["rho"]["max"], replication_arm["rho"]["final"],
                     replication_arm["schedule"]["lambda_max"]],
         "bound": "bit-identical to {0}, {1}, {2}".format(ORACLE_REPLICATION_RHO,
                                                          ORACLE_REPLICATION_FINAL,
                                                          ORACLE_REPLICATION_LAMBDA),
         "passed": bool(replication_arm["rho"]["max"] == ORACLE_REPLICATION_RHO
                        and replication_arm["rho"]["final"] == ORACLE_REPLICATION_FINAL
                        and replication_arm["schedule"]["lambda_max"]
                        == ORACLE_REPLICATION_LAMBDA)},
        {"id": 12, "name": "load family monotone", "reading": ordered,
         "bound": "strictly increasing in the declared transfer", "passed": bool(monotone_loads)},
        {"id": 13, "name": "single invocation", "reading": "receipt absent at start, one "
         "process, pid recorded", "bound": "structural", "passed": True},
    ]
    return rows


def features_of(gates: list, decision: dict, arms: dict) -> dict:
    """Section 4.2: the six features, each readable off a gate or off the decision."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    largest = max(arms.values(), key=lambda arm: arm["separation"]["peak"])
    return {
        "F1": passed[9],
        "F2": passed[8],
        "F3": bool(passed[10] and passed[11]),
        "F4": bool(decision["split_law"]["fit"]["readable"] >= MIN_READABLE
                   and decision["load_law"]["fit"]["readable"] >= MIN_READABLE),
        "F5": bool(decision["split_label"] != "INCONCLUSIVE"
                   and decision["load_label"] != "INCONCLUSIVE"),
        "F6": bool(largest["separation"]["peak_time"]
                   < largest["schedule"]["horizon"]),
        "largest_separation_arm": largest["name"],
    }


def status_of(gates: list, features: dict) -> str:
    every_gate = all(row["passed"] for row in gates)
    every_feature = all(value for key, value in features.items() if key.startswith("F"))
    return "PASS" if (every_gate and every_feature) else "FAIL"


def receipt_status() -> dict:
    """Idempotent: read the receipt if it exists and verify its own binding by digest."""
    path = os.path.join(ROOT, RECEIPT_PATH)
    if not os.path.exists(path):
        return {"present": False, "consistent": None, "status": None}
    with open(path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    sources = receipt.get("frozen_sources", {})
    observed = {
        "protocol": protocol_body_digest(),
        "probe": digest_of(PROBE_PATH),
        "bound_module": digest_of(BOUND_MODULE),
        "base_probe": digest_of(BASE_PROBE),
        "split_executor": digest_of(SPLIT_EXECUTOR),
        "base_receipt": digest_of(BASE_RECEIPT),
        "split_receipt": digest_of(SPLIT_RECEIPT),
    }
    mismatches = [
        key for key, value in observed.items()
        if sources.get(key, {}).get("sha256") != value
    ]
    return {
        "present": True,
        "consistent": not mismatches,
        "mismatched_sources": mismatches,
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
        "runtime_seconds": receipt.get("runtime_seconds"),
    }


def execute() -> int:
    started = time.time()
    binding = check_binding()
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        print("REFUSING TO RUN: {0} already exists; the stopping rule allows no second "
              "invocation on a recorded result".format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    base = load_modules()
    oracle = read_oracle()

    live_spec = LoadSpec(0, "action", "action", LARGEST_LOAD, SUPERSPLIT_LEVEL)
    silent_spec = LoadSpec(0, "action", "action", 0.0, SUPERSPLIT_LEVEL)
    action = {
        "live": bracket_action(loaded_seed(live_spec, base), live_spec, base,
                              SUPERSPLIT_LEVEL),
        "silent": bracket_action(loaded_seed(silent_spec, base), silent_spec, base,
                                SUPERSPLIT_LEVEL),
    }

    arms = {}
    traces = {}
    for spec in ARM_TABLE:
        twin = traces.get(spec.twin) if spec.twin else None
        reading = run_arm(spec, base, twin)
        trace = reading.pop("trace")
        if spec.name in TWIN_NAMES:
            traces[spec.name] = trace
        arms[spec.name] = reading
        print("{0:<22} load {1:.6e} peak {2:.6e} t {3:>5} term {4:.6e} {5:>13} dt {6} "
              "steps {7}".format(
                  spec.name, reading["load"]["measured"], reading["separation"]["peak"],
                  reading["separation"]["peak_time"], reading["separation"]["terminal"],
                  reading["separation"]["class"], reading["schedule"]["dt"],
                  reading["schedule"]["steps"]))

    comparison_ok = all(arm["load"]["passed"] for arm in arms.values())
    budget = {
        "executions": len(arms),
        "steps_total": int(sum(arm["schedule"]["steps"] for arm in arms.values())),
        "steps_max": int(max(arm["schedule"]["steps"] for arm in arms.values())),
        "per_execution_cap": PER_EXECUTION_CAP,
        "total_cap": TOTAL_STEP_CAP,
        "declared_executions": DECLARED_EXECUTIONS,
        "projected_seconds": PROJECTED_SECONDS,
    }
    decade_readings = tuple(arms[arm.name]["separation"]["peak"] for arm in DECADE_ARMS)
    load_levels = tuple(arms[arm.name]["load"]["measured"] for arm in FIT_B_ARMS)
    load_readings = tuple(arms[arm.name]["separation"]["peak"] for arm in FIT_B_ARMS)
    decision = decide(decade_readings, load_levels, load_readings)
    gates = gate_rows(arms, action, comparison_ok, budget)
    features = features_of(gates, decision, arms)
    status = status_of(gates, features)
    passed = status == "PASS"

    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": status,
        "invocation": {
            "command": INVOCATION,
            "bound_seconds": BOUND_SECONDS,
            "runtime_seconds": time.time() - started,
            "pid": os.getpid(),
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
            "split_executor": {"path": SPLIT_EXECUTOR,
                               "sha256": binding["observed"]["split_executor_sha256"]},
            "base_receipt": {"path": BASE_RECEIPT,
                             "sha256": binding["observed"]["base_receipt_sha256"]},
            "split_receipt": {"path": SPLIT_RECEIPT,
                              "sha256": binding["observed"]["split_receipt_sha256"]},
        },
        "binding": binding,
        "thresholds": {
            "class_bound": CLASS_BOUND,
            "silence_floor": SILENCE_FLOOR,
            "readable_floor": READABLE_FLOOR,
            "min_readable": MIN_READABLE,
            "fit_band": FIT_BAND,
            "exponent_low": EXPONENT_LOW,
            "exponent_high": EXPONENT_HIGH,
            "jump_factor": JUMP_FACTOR,
            "monotone_tolerance": MONOTONE_TOLERANCE,
            "level_ratio": LEVEL_RATIO,
            "action_floor_live": ACTION_FLOOR_LIVE,
            "action_ceiling_silent": ACTION_CEIL_SILENT,
            "load_tolerance": LOAD_TOL,
            "load_absolute_floor": LOAD_ABS_FLOOR,
            "step_safety": STEP_SAFETY,
            "step_candidates": list(STEP_CANDIDATES),
        },
        "arm_table": [
            {"index": arm.index, "name": arm.name, "role": arm.role,
             "load_transfer": arm.load_c, "delta_g": arm.delta_g,
             "schedule_key": arm.schedule_key, "twin": arm.twin,
             "schedule": list(arm.declared_schedule())}
            for arm in ARM_TABLE
        ],
        "arms": arms,
        "action": action,
        "reduction": {
            "residual": reduction_residual(
                LoadSpec(0, "reduction", "reduction", 0.0, 0.0), base),
            "bound": 0.0,
        },
        "oracle": oracle,
        "fits": {
            "split_law": {"levels": list(DECADES), "readings": list(decade_readings),
                          "fit": decision["split_law"]["fit"],
                          "label": decision["split_law"]["label"],
                          "reasons": decision["split_law"]["reasons"],
                          "jumps": decision["split_law"]["jumps"]},
            "load_law": {"levels": list(load_levels), "readings": list(load_readings),
                         "fit": decision["load_law"]["fit"],
                         "label": decision["load_law"]["label"],
                         "reasons": decision["load_law"]["reasons"],
                         "jumps": decision["load_law"]["jumps"]},
        },
        "instrument": decision["instrument"],
        "gates": gates,
        "features": features,
        "budget": budget,
        "verdicts": {
            "split_law": decision["split_label"] if passed else None,
            "load_law": decision["load_label"] if passed else None,
            "instrument": decision["instrument"] if passed else None,
        },
        "runtime_seconds": time.time() - started,
    }
    receipt["invocation"]["runtime_seconds"] = receipt["runtime_seconds"]

    path = os.path.join(ROOT, RECEIPT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sanitize(receipt), handle, indent=2, sort_keys=True)
        handle.write("\n")

    print(status)
    print("split_law: {0}".format(receipt["verdicts"]["split_law"]))
    print("load_law: {0}".format(receipt["verdicts"]["load_law"]))
    print("runtime_seconds: {0}".format(receipt["runtime_seconds"]))
    return EXIT_PASS if passed else EXIT_FAIL


def sanitize(value):
    """Strip numpy scalars and refuse a non-finite number before the receipt is written."""
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float) and not np.isfinite(value):
        raise ValueError("refusing to record a non-finite number")
    return value


def self_check() -> int:
    """Static, derivation and pre-flight checks. Writes nothing; safe to run again.

    Idempotent by construction: the receipt's presence is reported and verified by digest
    rather than asserted absent, so this pass is usable after an invocation.
    """
    problems = []
    print("self-check: binding")
    check_binding()
    base = load_modules()
    print("self-check: protocol rows against this executor's constants")
    declared = {
        "CLASS_BOUND": (declared_number("CLASS_BOUND"), CLASS_BOUND),
        "SILENCE_FLOOR": (declared_number("SILENCE_FLOOR"), SILENCE_FLOOR),
        "READABLE_FLOOR": (declared_number("READABLE_FLOOR"), READABLE_FLOOR),
        "MIN_READABLE": (declared_number("MIN_READABLE"), float(MIN_READABLE)),
        "FIT_BAND": (declared_number("FIT_BAND"), FIT_BAND),
        "EXPONENT_LOW": (declared_number("EXPONENT_LOW"), EXPONENT_LOW),
        "EXPONENT_HIGH": (declared_number("EXPONENT_HIGH"), EXPONENT_HIGH),
        "JUMP_FACTOR": (declared_number("JUMP_FACTOR"), JUMP_FACTOR),
        "MONOTONE_TOL": (declared_number("MONOTONE_TOL"), MONOTONE_TOLERANCE),
        "ACTION_FLOOR_LIVE": (declared_number("ACTION_FLOOR_LIVE"), ACTION_FLOOR_LIVE),
        "ACTION_CEIL_SILENT": (declared_number("ACTION_CEIL_SILENT"), ACTION_CEIL_SILENT),
        "LOAD_TOL": (declared_number("LOAD_TOL"), LOAD_TOL),
        "STEP_SAFETY": (declared_number("STEP_SAFETY"), STEP_SAFETY),
        "BOUND_SECONDS": (declared_number("BOUND_SECONDS"), BOUND_SECONDS),
    }
    for key, (row, constant) in sorted(declared.items()):
        if row != constant:
            problems.append("the protocol declares {0} = {1}, this executor holds {2}".format(
                key, row, constant))
        else:
            print("  {0:<20} {1}".format(key, constant))
    if declared_number("PER_EXECUTION_CAP") != PER_EXECUTION_CAP:
        problems.append("the declared per-execution cap {0} disagrees with {1}".format(
            declared_number("PER_EXECUTION_CAP"), PER_EXECUTION_CAP))
    if declared_number("TOTAL_STEP_CAP") != TOTAL_STEP_CAP:
        problems.append("the declared total cap {0} disagrees with {1}".format(
            declared_number("TOTAL_STEP_CAP"), TOTAL_STEP_CAP))
    if declared_number("DECLARED_EXECUTIONS") != DECLARED_EXECUTIONS:
        problems.append("the declared execution count {0} disagrees with {1}".format(
            declared_number("DECLARED_EXECUTIONS"), DECLARED_EXECUTIONS))

    print("self-check: the declared arm table")
    names = [arm.name for arm in ARM_TABLE]
    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        problems.append("{0} arms in the table against {1} declared".format(
            len(ARM_TABLE), DECLARED_EXECUTIONS))
    if [arm.index for arm in ARM_TABLE] != list(range(1, DECLARED_EXECUTIONS + 1)):
        problems.append("the arm indices are not 1..{0}".format(DECLARED_EXECUTIONS))
    if len(set(names)) != len(names):
        problems.append("the arm names are not unique")
    declared_steps = sum(arm.declared_schedule()[2] for arm in ARM_TABLE)
    print("  arms {0}, steps {1} (cap {2}), largest {3} (cap {4})".format(
        len(ARM_TABLE), declared_steps, TOTAL_STEP_CAP,
        max(arm.declared_schedule()[2] for arm in ARM_TABLE), PER_EXECUTION_CAP))
    if declared_steps > TOTAL_STEP_CAP:
        problems.append("the declared schedule totals {0} steps against the cap {1}".format(
            declared_steps, TOTAL_STEP_CAP))
    seen = set()
    for arm in ARM_TABLE:
        if arm.twin:
            if arm.twin not in seen:
                problems.append("{0}'s twin {1} does not precede it".format(
                    arm.name, arm.twin))
            twin = [item for item in ARM_TABLE if item.name == arm.twin][0]
            if twin.role != "reference" or twin.load_c != arm.load_c:
                problems.append("{0}'s twin {1} is not a reference on the same load".format(
                    arm.name, arm.twin))
            if twin.declared_schedule() != arm.declared_schedule():
                problems.append("{0} and its twin {1} disagree on the schedule".format(
                    arm.name, arm.twin))
        elif arm.role != "reference":
            problems.append("{0} is not a reference and declares no twin".format(arm.name))
        seen.add(arm.name)
    if len(DECADE_ARMS) != len(DECADES) or len(FIT_B_ARMS) != len(DECADES):
        problems.append("fit A reads {0} arms and fit B {1} against {2} levels".format(
            len(DECADE_ARMS), len(FIT_B_ARMS), len(DECADES)))
    if [arm.delta_g for arm in DECADE_ARMS] != list(DECADES):
        problems.append("fit A's arms do not carry the declared decades")
    if [arm.load_c for arm in FIT_B_ARMS][:-1] != [load for load, _ in LOADS[:-2]]:
        problems.append("fit B's arms do not carry the declared loads")

    print("self-check: the label vocabulary is reachable in every branch")
    linear_a = tuple(3.0e-3 * level for level in DECADES)
    cliff_a = list(linear_a)
    cliff_a[-1] = cliff_a[-1] * 1.0e4
    bent_a = []
    value = 1.0e-6
    for position in range(len(DECADES)):
        if position:
            value *= 3.0 if position % 2 else 20.0
        bent_a.append(value)
    short_a = tuple(3.0e-3 * level for level in DECADES[:2])
    preview = (
        ("PROPORTIONAL", label_split_law(DECADES, linear_a)),
        ("CLIFF", label_split_law(DECADES, tuple(cliff_a))),
        ("NONLINEAR", label_split_law(DECADES, tuple(bent_a))),
        ("INCONCLUSIVE", label_split_law(DECADES[:2], short_a)),
    )
    for wanted, reading in preview:
        if reading["label"] != wanted:
            problems.append("the split-law rule labels its {0} preview as {1}".format(
                wanted, reading["label"]))
        else:
            print("  split law {0:<14} reached (exponent {1})".format(
                wanted, reading["fit"]["exponent"]))
    loads = tuple(PREDICTED_LOAD[load_c] for load_c, _ in LOADS[:-1])
    linear_b = tuple(2.0e-4 * level for level in loads)
    super_b = tuple(2.0e-4 * level ** 1.5 for level in loads)
    sub_b = tuple(2.0e-4 * level ** 0.5 for level in loads)
    # The guard branch's witness: monotone in the load, fitted exponent 0.985553567871603
    # inside the linear band, and a per-level residual of 4.291 against the fitted line, so
    # the band fails and the label is neither LINEAR_IN_LOAD nor INCONCLUSIVE. It was found
    # by a search over monotone six-point readings on these six loads, because on these
    # levels a monotone two-regime power law cannot bend far enough to leave the factor 2
    # band while its exponent stays inside the linear band.
    guard_b = (9.884787065419702e-05, 0.005305490093165468, 0.006589809427470069,
               0.008752218716132423, 0.013896417353663672, 0.024627207325248795)
    preview_b = (
        ("LINEAR_IN_LOAD", label_load_law(loads, linear_b)),
        ("SUPERLINEAR", label_load_law(loads, super_b)),
        ("SUBLINEAR", label_load_law(loads, sub_b)),
        ("NONLINEAR_IN_LOAD", label_load_law(loads, guard_b)),
        ("INCONCLUSIVE", label_load_law(loads[:2], linear_b[:2])),
    )
    for wanted, reading in preview_b:
        if reading["label"] != wanted:
            problems.append("the load-law rule labels its {0} preview as {1}".format(
                wanted, reading["label"]))
        else:
            print("  load law  {0:<18} reached (exponent {1})".format(
                wanted, reading["fit"]["exponent"]))

    print("self-check: the decision rule reads every gate and every feature")
    rows = [{"id": index, "name": "synthetic", "passed": True}
            for index in range(1, 14)]
    features = {key: True for key in ("F1", "F2", "F3", "F4", "F5", "F6")}
    if status_of(rows, features) != "PASS":
        problems.append("the decision rule does not return PASS on an all-true set")
    for row in rows:
        mutated = [dict(item) for item in rows]
        mutated[row["id"] - 1]["passed"] = False
        if status_of(mutated, features) != "FAIL":
            problems.append("gate {0} does not carry the status".format(row["id"]))
    for key in features:
        mutated = dict(features)
        mutated[key] = False
        if status_of(rows, mutated) != "FAIL":
            problems.append("feature {0} does not carry the status".format(key))
    print("  13 gates and 6 features each carry the status")

    print("self-check: the load family and the pre-flight action check")
    for load_c, predicted in LOADS:
        spec = LoadSpec(0, "seed", "seed", load_c, 0.0)
        state = loaded_seed(spec, base)
        comparison = load_comparison(spec, load_of(state, base))
        print("  c {0:>8.4g} ell {1:.12e} predicted {2:.12e}".format(
            load_c, comparison["measured"], predicted))
        if not comparison["passed"]:
            problems.append("the load at c = {0} measures {1} against the declared {2}".format(
                load_c, comparison["measured"], predicted))
    ordered = [load_of(loaded_seed(LoadSpec(0, "seed", "seed", load_c, 0.0), base), base)
               for load_c, _ in LOADS[:-1]]
    if not all(ordered[index + 1] > ordered[index] for index in range(len(ordered) - 1)):
        problems.append("the measured loads are not strictly increasing in the transfer")
    live_spec = LoadSpec(0, "action", "action", LARGEST_LOAD, SUPERSPLIT_LEVEL)
    live = bracket_action(loaded_seed(live_spec, base), live_spec, base, SUPERSPLIT_LEVEL)
    silent_spec = LoadSpec(0, "action", "action", 0.0, SUPERSPLIT_LEVEL)
    silent = bracket_action(loaded_seed(silent_spec, base), silent_spec, base,
                            SUPERSPLIT_LEVEL)
    print("  action live   {0:.12e} of the right-hand side".format(live["relative"]))
    print("  action silent {0:.12e} of the right-hand side".format(silent["relative"]))
    if live["relative"] < ACTION_FLOOR_LIVE:
        problems.append("the split's action at the largest load is {0}, below the floor "
                        "{1}".format(live["relative"], ACTION_FLOOR_LIVE))
    if silent["relative"] > ACTION_CEIL_SILENT:
        problems.append("the split's action on the ray seed is {0}, above the ceiling "
                        "{1}".format(silent["relative"], ACTION_CEIL_SILENT))
    residual = reduction_residual(LoadSpec(0, "reduction", "reduction", 0.0, 0.0), base)
    print("  zero-split reduction residual {0!r}".format(residual))
    if residual != 0.0:
        problems.append("the split right-hand side does not reduce to the successor's own "
                        "at zero split: {0}".format(residual))

    print("self-check: the oracle literals against the two bound receipts")
    oracle = read_oracle()
    print("  ray {0!r}, replication {1!r}, terminal {2!r}, lambda {3!r}".format(
        oracle["ray_rho"], oracle["replication_rho"], oracle["replication_final"],
        oracle["replication_lambda"]))

    print("self-check: the receipt")
    recorded = receipt_status()
    if recorded["present"]:
        print("  {0} present, schema {1}, status {2}, binding {3}".format(
            RECEIPT_PATH, recorded["schema"], recorded["status"],
            "consistent" if recorded["consistent"] else
            "INCONSISTENT {0}".format(recorded["mismatched_sources"])))
        if not recorded["consistent"]:
            problems.append("the receipt's recorded sources do not match the tree")
    else:
        print("  {0} absent (an invocation is still available)".format(RECEIPT_PATH))

    print("self-check: derived budget")
    print("  {0} arms, {1} steps, projected {2} s against the bound {3} s; the budget is "
          "{4}".format(len(ARM_TABLE), declared_steps, PROJECTED_SECONDS, BOUND_SECONDS,
                       "declared but not recomputed here"))

    if problems:
        print("SELF-CHECK FAILED")
        for problem in problems:
            print("  {0}".format(problem))
        return EXIT_STATIC_CHECK
    print("SELF-CHECK PASSED")
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--self-check", action="store_true",
                        help="run the static checks, write nothing and stop")
    args = parser.parse_args(argv)
    if args.self_check:
        return self_check()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
