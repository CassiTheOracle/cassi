"""Does an asymmetric gate write, or only shake? The loop-carrier composition attractor
under a split gate, read by a multi-horizon offset fit.

One protocol, one invocation. The executor is frozen with `computations/loop-carrier-
attractor-write-prereg.md` in the same commit and refuses to run unless the protocol
body's digest, its own digest, and the digests of every imported module and receipt agree
with the ten rows of section 0.

The statistic is the composition coordinate A(t) = mean_x q(E_Y, E_I) of the projection,
read as the difference between a split arm's own trajectory and its unsplit anchor's, at
five declared horizons of one run. Each arm is fitted twice: with the successor receipt's
relaxation rate held (fit H), and with the rate free (fit F). A branch is issued only where
the two agree, because a held rate wrong by a few percent makes a pure transient look like
an offset -- section 1.3 states that fragility, section 5.5 exhibits it as a witness, and
the self-check re-derives both.

    python computations/verify_loop_carrier_attractor_write.py --self-check
    timeout 600 python computations/verify_loop_carrier_attractor_write.py
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

# The two spent executors, imported for their constructions. Their module levels only
# define constants and functions; neither reads a file and neither imports a probe until
# called, so importing them constructs no arm and evaluates no pipeline.
import verify_loop_carrier_projection_split as split  # noqa: E402
import verify_loop_carrier_gate_load as gate_load  # noqa: E402

# Frozen sources, all by digest: the two operator layers, this protocol's two imported
# executors, the predecessor protocol body, and the three receipts whose readings are read
# rather than typed. Section 0 declares all ten rows and the self-check mirrors them.
BOUND_MODULE = "computations/verify_loop_to_bubble_projection.py"
BOUND_DIGEST = "d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1"
BASE_PROBE = "computations/verify_loop_carrier_projection_relaxation.py"
BASE_PROBE_DIGEST = "28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622"
SPLIT_EXECUTOR = "computations/verify_loop_carrier_projection_split.py"
SPLIT_EXECUTOR_DIGEST = "246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a"
GATE_LOAD_EXECUTOR = "computations/verify_loop_carrier_gate_load.py"
GATE_LOAD_EXECUTOR_DIGEST = "be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac"
BASE_RECEIPT = "runs/loop_carrier_projection_relaxation/verification.json"
BASE_RECEIPT_DIGEST = "3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1"
SPLIT_RECEIPT = "runs/loop_carrier_projection_split/verification.json"
SPLIT_RECEIPT_DIGEST = "559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc"
GATE_LOAD_PROTOCOL = "computations/loop-carrier-gate-load-prereg.md"
GATE_LOAD_PROTOCOL_DIGEST = "c0d2fe37b8b4ee7673b1ec1a7c658f2bedb4eae6ad360516057d5ee9cdc843fa"
GATE_LOAD_RECEIPT = "runs/loop_carrier_gate_load/verification.json"
GATE_LOAD_RECEIPT_DIGEST = "471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1"

PROTOCOL_PATH = "computations/loop-carrier-attractor-write-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_attractor_write.py"
RECEIPT_PATH = "runs/loop_carrier_attractor_write/verification.json"
INVOCATION = "timeout 600 python computations/verify_loop_carrier_attractor_write.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-attractor-write.v1"
BOUND_SECONDS = 600.0

# Section 0 of the protocol declares both hashes: this file's, and the digest of the frozen
# body (everything from "## 1." to just before "## 8."). The two are cross-bound without a
# fix point, because section 0 sits outside the body range. Filled by the freeze pass.
FROZEN_BODY_DIGEST = "151ab43fbaf2cd8580679bca98d51a40cbac7adf275a799b0f06249aedb9c636"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.3: the declared thresholds.
READABLE_FLOOR_Q = 1.0e-12
SILENCE_FLOOR_Q = 1.0e-14
PERSIST_SHARE = 0.5
TRANS_SHARE = 0.1
RESIDUAL_BAND = 0.25
CLOCK_TOLERANCE = 2.0
NU_REFERENCE = 0.01119569724312185
NU_TOLERANCE = 2.0
TAIL_FRACTION = 1.0e-2
MIN_SPAN = 1.0
HORIZON_COUNT = 5
RATE_SCAN_FACTOR = 4.0
RATE_SCAN_POINTS = 4001
RATE_REFINEMENT_WIDTHS = (2.0e-3, 2.0e-4, 2.0e-5, 2.0e-6)
RATE_REFINEMENT_STEPS = 20
MIN_READABLE = 4
MIN_PERSIST = 2
FIT_BAND = 2.0
EXPONENT_LOW = 0.9
EXPONENT_HIGH = 1.1
JUMP_FACTOR = 3.0
MONOTONE_TOLERANCE = 1.5
ACTION_FLOOR_LIVE = 1.0e-3
ACTION_CEIL_SILENT = 1.0e-15
ANCHOR_RAY_TOL = 5.0e-3
LOAD_TOL = 1.0e-12
LOAD_ABS_FLOOR = 1.0e-15
STEP_SAFETY = 40.0
SECONDS_PER_STEP_ASSUMED = 8.36e-4
SECONDS_PER_STEP_MEASURED = 6.025e-4
PROJECTED_SECONDS = 190.0
PER_EXECUTION_CAP = 50000
TOTAL_STEP_CAP = 300000
DECLARED_EXECUTIONS = 12

# Section 1.1: everything the predecessor chain fixes and this protocol carries unchanged.
PROFILE = "on_ray"
STEP_CANDIDATES = (0.05, 0.02, 0.01)
DECLARED_DT = 0.02
SHORT_DT = 0.02
SHORT_HORIZON = 2.0
SHORT_STEPS = 100
REPLICATION_DT = 0.02
REPLICATION_HORIZON = 36.66172105812361
REPLICATION_STEPS = 1834
LONG_HORIZON = 450.0
LONG_STEPS = 22500
# Section 1.5: the declared offset law of the design probe, used by gate 6's magnitude check.
PROBE_OFFSET_COEFFICIENT = 3.378913644274e-4
PROBE_OFFSET_EXPONENT = 1.005101810107

# Section 1.2 and 2.3: the declared horizons, on one trajectory.
HORIZONS = (30.0, 90.0, 180.0, 300.0, 450.0)
SAMPLE = tuple(int(round(h / DECLARED_DT)) for h in HORIZONS)

# Section 3: the declared sweep family and the declared split sizes.
DECADES = (1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1)
LARGEST_SPLIT = 1.0
SWEEP_LEVELS = DECADES + (LARGEST_SPLIT,)
SWEEP_ORDER = ("decade_1", "decade_2", "decade_3", "decade_4", "decade_5", "decade_6",
               "supersplit_load")
LARGEST_LOAD = gate_load.LARGEST_LOAD
ANCHOR_ARM = "loadmax_anchor"
LARGEST_SPLIT_ARM = "supersplit_load"
RAY_ANCHOR_ARM = "ray_anchor"
RAY_SILENCE_ARM = "ray_supersplit"
CLOCK_ARM = ANCHOR_ARM
STEP_NOISE_ARM = "ray_short"
REPLICATION_ARM = "successor_replication"

# Section 5: the oracle readings, read from the three digest-bound receipts and declared
# here as literals so that a receipt cannot drift silently under the oracle.
ORACLE_RAY_RHO = 5.329147248815693e-16
ORACLE_REPLICATION_RHO = 2.622443969747147e-15
ORACLE_REPLICATION_FINAL = 2.219140084394095e-15
ORACLE_REPLICATION_LAMBDA = 1.0331312281605476
ORACLE_RAY_LOAD = 3.646114292316331e-1
ORACLE_CLOCK = 0.01119569724312185

# Section 5.5: the synthetic branch witnesses, declared as the measured table so that the
# self-check fails if the rule stops reaching a branch.
WITNESS_OFFSET = -3.3329e-10
WITNESS_AMPLITUDE = -1.1149e-10
WITNESS_RATIOS = (0.5, 0.9, 1.0, 1.0161, 1.024, 1.1, 1.5, 2.0)
WITNESS_LABELS = {
    "transient": ("TRANS", "TRANS", "TRANS", "TRANS", "TRANS", "TRANS", "TRANS",
                  "UNRESOLVED"),
    "shift": ("PERSIST",) * 8,
    "overshoot": ("PERSIST",) * 8,
}

VERDICT_LABELS = ("WRITES", "PERTURBS_ONLY", "INCONCLUSIVE")


def digest_of(relative_path: str) -> str:
    with open(os.path.join(ROOT, relative_path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def load_json(relative_path: str) -> dict:
    with open(os.path.join(ROOT, relative_path), encoding="utf-8") as handle:
        return json.load(handle)


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
    return tuple(float(item.strip().strip("$=")) for item in protocol_row(key).split(","))


BINDING_SOURCES = (
    ("frozen_body_sha256", None),
    ("executor_sha256", None),
    ("bound_module_sha256", BOUND_MODULE),
    ("base_probe_sha256", BASE_PROBE),
    ("split_executor_sha256", SPLIT_EXECUTOR),
    ("gate_load_executor_sha256", GATE_LOAD_EXECUTOR),
    ("base_receipt_sha256", BASE_RECEIPT),
    ("split_receipt_sha256", SPLIT_RECEIPT),
    ("gate_load_protocol_body_sha256", GATE_LOAD_PROTOCOL),
    ("gate_load_receipt_sha256", GATE_LOAD_RECEIPT),
)


def check_binding(expect_body: str = None, expect_executor: str = None) -> dict:
    """Refuse to run on any hash mismatch, before any arm is constructed."""
    problems = []
    declared, observed = {}, {}
    for key, path in BINDING_SOURCES:
        declared[key] = protocol_row(key)
        if key == "frozen_body_sha256":
            observed[key] = protocol_body_digest()
        elif key == "executor_sha256":
            observed[key] = digest_of(PROBE_PATH)
        elif key == "gate_load_protocol_body_sha256":
            # The bound artifact is that protocol's body, not its whole file: section 0 and
            # the post-execution record of a frozen protocol are meant to move.
            observed[key] = gate_load.protocol_body_digest()
        else:
            observed[key] = digest_of(path)
    if declared["frozen_body_sha256"] != FROZEN_BODY_DIGEST:
        problems.append(
            "the protocol body digest and this executor's constant disagree: {0} vs {1}".format(
                declared["frozen_body_sha256"], FROZEN_BODY_DIGEST))
    for key in sorted(declared):
        if declared[key] != observed[key]:
            problems.append(
                "binding mismatch on {0}: the protocol declares {1}, the tree holds {2}".format(
                    key, declared[key], observed[key]))
    if expect_body is not None and observed["frozen_body_sha256"] != expect_body:
        problems.append("disturbed binding on frozen_body_sha256: expected {0}, observed "
                        "{1}".format(expect_body, observed["frozen_body_sha256"]))
    if expect_executor is not None and observed["executor_sha256"] != expect_executor:
        problems.append("disturbed binding on executor_sha256: expected {0}, observed "
                        "{1}".format(expect_executor, observed["executor_sha256"]))
    if problems:
        for problem in problems:
            print("REFUSING TO RUN: {0}".format(problem))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"declared": declared, "observed": observed}


def load_modules():
    """Import the successor probe through the spent executors' own loader.

    The loader converts the successor probe's binding refusal into this protocol's, so a
    disturbed operator module stops the run before any arm exists.
    """
    try:
        return gate_load.load_modules()
    except SystemExit:
        print("REFUSING TO RUN: the successor probe's own binding of the frozen operators "
              "failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)


class ArmSpec(gate_load.LoadSpec):
    """One declared arm of section 3, on this protocol's own long schedule."""

    def __init__(self, index: int, name: str, role: str, load_c: float, delta_g: float,
                 schedule_key: str = "long", twin: str = ""):
        gate_load.LoadSpec.__init__(self, index, name, role, load_c, delta_g,
                                    schedule_key, twin)

    def declared_schedule(self) -> tuple:
        if self.schedule_key == "short":
            return SHORT_DT, SHORT_HORIZON, SHORT_STEPS
        if self.schedule_key == "replication":
            return REPLICATION_DT, REPLICATION_HORIZON, REPLICATION_STEPS
        return DECLARED_DT, LONG_HORIZON, LONG_STEPS


def build_arm_table() -> tuple:
    arms = [
        ArmSpec(1, "ray_short", "oracle", 0.0, 0.0, "short"),
        ArmSpec(2, "ray_anchor", "anchor", 0.0, 0.0),
        ArmSpec(3, "ray_supersplit", "silence", 0.0, LARGEST_SPLIT, "long", "ray_anchor"),
        ArmSpec(4, "successor_replication", "oracle", 0.0, 0.0, "replication"),
        ArmSpec(5, "loadmax_anchor", "anchor", LARGEST_LOAD, 0.0),
    ]
    index = 6
    for position, level in enumerate(DECADES):
        arms.append(ArmSpec(index, "decade_{0}".format(position + 1), "sweep",
                            LARGEST_LOAD, level, "long", "loadmax_anchor"))
        index += 1
    arms.append(ArmSpec(index, "supersplit_load", "canfail", LARGEST_LOAD, LARGEST_SPLIT,
                        "long", "loadmax_anchor"))
    return tuple(arms)


ARM_TABLE = build_arm_table()
TWIN_NAMES = tuple(sorted({arm.twin for arm in ARM_TABLE if arm.twin}))


def coordinate_of(projection: np.ndarray, base) -> float:
    """Section 1.2: A = mean_x q(E_Y, E_I) on the projection, the rate's own coordinate."""
    return float(np.mean(np.asarray(base.frozen.bounded_q(projection[0], projection[1]))))


def ray_distance_of(projection: np.ndarray, base) -> float:
    """Section 5.7: how far the projection's EPSILON is from the ray, relative to rho."""
    rho = projection[0] + projection[1]
    epsilon = projection[0] - base.PHI * projection[1]
    return float(np.max(np.abs(epsilon)) / max(1.0, float(np.max(np.abs(rho)))))


def action_of(load_c: float, delta_g: float, base) -> dict:
    """Section 5.1 and 5.2: the split's action on A over one declared step, seeded state.

    The numerator is the change of A that adding the split makes to a single declared step;
    the denominator is that same step's own drift at zero split, so the reading is the
    fraction of the step the gate accounts for. On the ray the bracket is identically zero
    and both terms vanish, so the reading is an identity rather than a small number.
    """
    spec = ArmSpec(0, "action", "action", load_c, delta_g)
    zero = ArmSpec(0, "action", "action", load_c, 0.0)
    state = gate_load.loaded_seed(spec, base)
    start = coordinate_of(base.projection(state), base)
    without = split.split_step(state, DECLARED_DT, zero, base)
    with_split = split.split_step(state, DECLARED_DT, spec, base)
    plain = coordinate_of(base.projection(without), base)
    split_value = coordinate_of(base.projection(with_split), base)
    drift = abs(plain - start)
    absolute = abs(split_value - plain)
    return {
        "declared_load": load_c,
        "delta_g": delta_g,
        "absolute": absolute,
        "drift": drift,
        "relative": (absolute / drift if drift > 0.0 else 0.0),
    }


def fit_held(readings) -> dict:
    """Fit H: the declared statistic, the successor receipt's rate held.

    The model D(T) = D_inf + (D_0 - D_inf) exp(-nu T) is linear in (D_inf, D_0), so the two
    parameters are one least-squares solve and no iteration.
    """
    times = np.array(HORIZONS, dtype=np.float64)
    values = np.asarray(readings, dtype=np.float64)
    x = np.exp(-NU_REFERENCE * times)
    design = np.stack((1.0 - x, x), axis=1)
    solution, *_ = np.linalg.lstsq(design, values, rcond=None)
    model = design @ solution
    scale = max(float(np.max(np.abs(values))), 1e-300)
    return {
        "offset": float(solution[0]),
        "amplitude": float(solution[1]),
        "residual": float(np.max(np.abs(model - values))) / scale,
        "rate": NU_REFERENCE,
        "rate_held": True,
    }


def fit_free(readings) -> dict:
    """Fit F: the same model with the rate free, on a declared deterministic search.

    The rate is scanned on a declared log grid in [nu/4, 4nu], each rate solved in closed
    form for the two amplitudes, then refined by declared relative widths. No optimiser, no
    seed, no tolerance on an iteration: the same readings give the same answer every time.
    """
    times = np.array(HORIZONS, dtype=np.float64)
    values = np.asarray(readings, dtype=np.float64)
    low = NU_REFERENCE / RATE_SCAN_FACTOR
    high = NU_REFERENCE * RATE_SCAN_FACTOR
    grid = np.exp(np.linspace(np.log(low), np.log(high), RATE_SCAN_POINTS))
    best = None
    for rate in grid:
        x = np.exp(-rate * times)
        design = np.stack((1.0 - x, x), axis=1)
        solution, *_ = np.linalg.lstsq(design, values, rcond=None)
        rss = float(np.sum((design @ solution - values) ** 2))
        if best is None or rss < best[0]:
            best = (rss, float(rate), float(solution[0]), float(solution[1]))
    rss, rate, offset, amplitude = best
    for width in RATE_REFINEMENT_WIDTHS:
        for step in range(-RATE_REFINEMENT_STEPS, RATE_REFINEMENT_STEPS + 1):
            trial = rate * (1.0 + width * step / RATE_REFINEMENT_STEPS)
            if trial <= 0.0:
                continue
            x = np.exp(-trial * times)
            design = np.stack((1.0 - x, x), axis=1)
            solution, *_ = np.linalg.lstsq(design, values, rcond=None)
            candidate = float(np.sum((design @ solution - values) ** 2))
            if candidate < rss:
                rss, rate, offset, amplitude = candidate, float(trial), \
                    float(solution[0]), float(solution[1])
    x = np.exp(-rate * times)
    design = np.stack((1.0 - x, x), axis=1)
    model = design @ np.array([offset, amplitude])
    scale = max(float(np.max(np.abs(values))), 1e-300)
    margin = 1.0 + 2.0 * RATE_REFINEMENT_WIDTHS[-1]
    return {
        "rate": rate,
        "offset": offset,
        "amplitude": amplitude,
        "residual": float(np.max(np.abs(model - values))) / scale,
        "rate_held": False,
        "rate_at_edge": bool(rate <= low * margin or rate >= high / margin),
    }


def classify(readings) -> dict:
    """Section 2.1: the branch, from the two fits and the terminal reading."""
    values = np.asarray(readings, dtype=np.float64)
    peak = float(np.max(np.abs(values)))
    terminal = float(values[-1])
    held = fit_held(values)
    free = fit_free(values)
    reading = {
        "peak": peak,
        "terminal": terminal,
        "held": held,
        "free": free,
        "share_held": (abs(held["offset"]) / abs(terminal) if terminal != 0.0 else None),
        "share_free": (abs(free["offset"]) / abs(terminal) if terminal != 0.0 else None),
        "rate_ratio": free["rate"] / NU_REFERENCE,
        "terminal_ratio": (float(values[-2] / values[-3]) if values[-3] != 0.0 else None),
        "transient_prediction": float(np.exp(-NU_REFERENCE * (HORIZONS[-1] - HORIZONS[-2]))),
    }
    if peak < READABLE_FLOOR_Q:
        reading["branch"] = "BELOW_FLOOR"
        reading["reason"] = "the peak reading is below the readable floor"
        return reading
    persists = (abs(held["offset"]) >= PERSIST_SHARE * abs(terminal)
                and abs(free["offset"]) >= PERSIST_SHARE * abs(terminal)
                and held["residual"] <= RESIDUAL_BAND
                and free["residual"] <= RESIDUAL_BAND)
    decays = (abs(free["offset"]) <= TRANS_SHARE * abs(terminal)
              and free["residual"] <= RESIDUAL_BAND
              and 1.0 / CLOCK_TOLERANCE <= reading["rate_ratio"] <= CLOCK_TOLERANCE)
    if persists:
        reading["branch"] = "PERSIST"
        reading["reason"] = ("both fits leave an offset of at least {0} of the terminal "
                             "reading".format(PERSIST_SHARE))
    elif decays:
        reading["branch"] = "TRANS"
        reading["reason"] = ("the free fit leaves no offset and decays at {0} times the "
                             "declared clock, inside the rate band".format(
                                 round(reading["rate_ratio"], 4)))
    else:
        reading["branch"] = "UNRESOLVED"
        reading["reason"] = ("the held offset is {0} of the terminal reading, the free "
                             "offset {1}, the free rate {2} times the declared clock, and "
                             "the residuals {3} and {4}".format(
                                 _round(reading["share_held"]), _round(reading["share_free"]),
                                 round(reading["rate_ratio"], 4),
                                 round(held["residual"], 4), round(free["residual"], 4)))
    return reading


def _round(value):
    return None if value is None else round(value, 4)


def run_arm(spec: ArmSpec, base, anchor_series) -> dict:
    """One declared arm: its own schedule, its coordinate series, and its separation."""
    state = gate_load.loaded_seed(spec, base)
    dt, horizon, steps = spec.declared_schedule()
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])
    lambda_max = float(base.arm_lambda_max(split.proxy_arm(spec, base), kappa))
    conformant = bool(dt <= 1.0 / (STEP_SAFETY * lambda_max) and dt in STEP_CANDIDATES)
    comparison = gate_load.load_comparison(spec, gate_load.load_of(state, base))

    sampled = SAMPLE if steps + 1 > SAMPLE[-1] else ()
    canonical = base.canonical_initial(PROFILE)
    series = np.empty(steps + 1)
    rho, minimum, minimum_projection, q_low, q_high = [], [], [], [], []
    annihilation, idempotence = [], []
    for index in range(steps + 1):
        current = base.projection(state)
        value = coordinate_of(current, base)
        series[index] = value
        rho.append(gate_load.rho_of(current, canonical))
        minimum.append(float(np.min(state)))
        minimum_projection.append(float(np.min(current)))
        composition = base.frozen.bounded_q(current[0], current[1])
        q_low.append(float(np.min(composition)))
        q_high.append(float(np.max(composition)))
        annihilation.append(gate_load.annihilation_of(state, base))
        idempotence.append(base.relative_residual(
            base.projection(base.lift(current, state.shape[base.LOOP_AXIS])), current))
        if index == steps:
            break
        state = split.split_step(state, dt, spec, base)
        canonical = base.canonical_step(canonical, dt)

    self_twin = anchor_series is None
    reading = {
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
            "samples": list(sampled),
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
        "ray_distance": (None if self_twin else
                         ray_distance_of(base.projection(state), base)),
        "coordinate": {"initial": float(series[0]), "final": float(series[-1]),
                       "at_horizons": ([float(series[index]) for index in sampled]
                                       if sampled else None)},
        "delta": None,
        "branch": None,
        "self_twin": self_twin,
        "steps_recorded": int(steps + 1),
    }
    if not self_twin and sampled:
        difference = series - anchor_series
        readings = [float(difference[index]) for index in sampled]
        peak_index = int(np.argmax(np.abs(difference)))
        reading["delta"] = {
            "at_horizons": readings,
            "horizons": list(HORIZONS),
            "peak": float(np.max(np.abs(difference))),
            "peak_time": float(peak_index * dt),
        }
        reading["branch"] = classify(readings)
    reading["_coordinate_series"] = series
    reading["_rho_series"] = rho if spec.name == CLOCK_ARM else None
    return reading


def clock_of(rho_series, dt, start_index, end_index) -> dict:
    """Section 1.4 and gate 7: the anchor's own rho decay rate over the declared window."""
    window = np.asarray(rho_series[start_index:end_index + 1], dtype=np.float64)
    times = np.arange(start_index, end_index + 1, dtype=np.float64) * dt
    positive = window > 0.0
    if int(np.sum(positive)) < 2:
        return {"window": [start_index * dt, end_index * dt], "rate": None,
                "ratio": None, "passed": False,
                "reason": "fewer than two positive samples"}
    rate = float(-np.polyfit(times[positive], np.log(window[positive]), 1)[0])
    return {
        "window": [float(start_index * dt), float(end_index * dt)],
        "samples": int(np.sum(positive)),
        "rate": rate,
        "reference": NU_REFERENCE,
        "ratio": rate / NU_REFERENCE,
        "tolerance": NU_TOLERANCE,
        "passed": bool(1.0 / NU_TOLERANCE <= rate / NU_REFERENCE <= NU_TOLERANCE),
    }


def read_clock() -> dict:
    """Section 1.4: the declared rate, read from the digest-bound successor receipt."""
    receipt = load_json(BASE_RECEIPT)
    value = float(receipt["relaxation"]["arms"]["relax_reference"]["fit"]["nu_fit"])
    return {
        "source_path": BASE_RECEIPT,
        "source_sha256": digest_of(BASE_RECEIPT),
        "source_field": "relaxation.arms.relax_reference.fit.nu_fit",
        "declared": ORACLE_CLOCK,
        "read": value,
        "equal_to_declared": bool(value == ORACLE_CLOCK),
    }


def read_oracle() -> dict:
    """Section 5: the oracle readings, read from the three digest-bound receipts."""
    reading = gate_load.read_oracle()
    gate_receipt = load_json(GATE_LOAD_RECEIPT)
    return {
        "ray_rho": float(reading["ray_rho"]),
        "replication_rho": float(reading["replication_rho"]),
        "replication_final": float(reading["replication_final"]),
        "replication_lambda": float(reading["replication_lambda"]),
        "ray_load": float(gate_receipt["arms"]["loadLmax_reference"]["load"]["measured"]),
        "clock": float(load_json(BASE_RECEIPT)["relaxation"]["arms"]["relax_reference"]
                       ["fit"]["nu_fit"]),
    }


def law_of(levels, readings) -> dict:
    """Section 2.2: the log-space fit, the label and the instrument over the given arms."""
    fit = gate_load.fit_law(tuple(levels), tuple(readings))
    label = gate_load.label_split_law(tuple(levels), tuple(readings))
    instrument = None
    if fit["exponent"] and fit["coefficient"]:
        instrument = float((READABLE_FLOOR_Q / fit["coefficient"]) ** (1.0 / fit["exponent"]))
    return {
        "levels": [float(level) for level in levels],
        "readings": [float(value) for value in readings],
        "fit": fit,
        "label": label["label"],
        "reasons": label["reasons"],
        "jumps": label["jumps"],
        "instrument": instrument,
    }


def corroboration_of(arms, levels) -> dict:
    """Section 2.2: the same fit on the free offsets and on the terminal readings."""
    free = [abs(arms[name]["branch"]["free"]["offset"]) for name in SWEEP_ORDER
            if name in arms and arms[name]["branch"] is not None]
    terminal = [abs(arms[name]["branch"]["terminal"]) for name in SWEEP_ORDER
                if name in arms and arms[name]["branch"] is not None]
    return {
        "free_offsets": law_of(levels, free),
        "terminal_readings": law_of(levels, terminal),
    }


def verdict_of(branches: dict, persisting: list, decaying: list,
               largest_branch: str) -> str:
    """Section 2.4's two sufficient conditions, each on declared counts alone."""
    if largest_branch == "PERSIST" and len(persisting) >= MIN_PERSIST:
        return "WRITES"
    if largest_branch == "TRANS" and not persisting and len(decaying) >= MIN_READABLE:
        return "PERTURBS_ONLY"
    return "INCONCLUSIVE"


def decide(arms: dict) -> dict:
    """Section 2.4: the branch counts, the law and the write verdict."""
    branches = {name: arms[name]["branch"]["branch"] for name in SWEEP_ORDER}
    persisting = [name for name in SWEEP_ORDER if branches[name] == "PERSIST"]
    decaying = [name for name in SWEEP_ORDER if branches[name] == "TRANS"]
    measured = [name for name in SWEEP_ORDER
                if branches[name] not in ("BELOW_FLOOR",)]
    levels = [arms[name]["declared"]["delta_g"] for name in SWEEP_ORDER]
    law = None
    if len(persisting) >= MIN_READABLE:
        law = law_of([arms[name]["declared"]["delta_g"] for name in persisting],
                     [abs(arms[name]["branch"]["held"]["offset"]) for name in persisting])
    verdict = verdict_of(branches, persisting, decaying, branches[LARGEST_SPLIT_ARM])
    return {
        "branches": branches,
        "persisting": persisting,
        "decaying": decaying,
        "measured": measured,
        "largest_split": LARGEST_SPLIT_ARM,
        "largest_split_branch": branches[LARGEST_SPLIT_ARM],
        "law": law,
        "law_issued": bool(law is not None),
        "law_arm_count": len(persisting),
        "corroboration": corroboration_of(arms, levels),
        "verdict": verdict,
    }


def gate_rows(arms: dict, action: dict, comparison_ok: bool, budget: dict,
              clock: dict, clock_read: dict, oracle: dict) -> list:
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
    shape_ok = (budget["executions"] == DECLARED_EXECUTIONS
                and budget["steps_max"] <= PER_EXECUTION_CAP
                and budget["steps_total"] <= TOTAL_STEP_CAP)
    tail = float(np.exp(-NU_REFERENCE * HORIZONS[-1]))
    span = float(NU_REFERENCE * (HORIZONS[-1] - HORIZONS[0]))
    declared_threshold = float(np.log(1.0 / TAIL_FRACTION) / NU_REFERENCE)
    distinct = len({round(float(np.exp(-NU_REFERENCE * h)), 15) for h in HORIZONS})
    declared_levels = [arm for arm in ARM_TABLE
                       if arm.name in SWEEP_ORDER and arm.delta_g in SWEEP_LEVELS]
    adequacy = (len(HORIZONS) == HORIZON_COUNT and distinct == len(HORIZONS)
                and span >= MIN_SPAN and tail <= TAIL_FRACTION
                and HORIZONS[-1] >= declared_threshold
                and len(declared_levels) >= MIN_READABLE
                and min(PROBE_OFFSET_COEFFICIENT * arm.delta_g ** PROBE_OFFSET_EXPONENT
                        for arm in declared_levels) >= READABLE_FLOOR_Q)
    silence = max(abs(value) for value in
                  arms[RAY_SILENCE_ARM]["delta"]["at_horizons"])
    firer = arms[LARGEST_SPLIT_ARM]["delta"]["peak"]
    anchor = arms[ANCHOR_ARM]
    replication_arm = arms[REPLICATION_ARM]
    rows = [
        {"id": 1, "name": "binding", "reading": "ten rows declared against observed, all "
         "exact", "bound": "exact", "passed": True},
        {"id": 2, "name": "structure", "reading": "minimum state and projection, the "
         "composition bounds, and the annihilation and idempotence maxima over every "
         "recorded state", "bound": "nonnegative states, 0 <= q < 1",
         "passed": bool(structural)},
        {"id": 3, "name": "anchor load", "reading": {
            "measured": anchor["load"]["measured"], "receipt": oracle["ray_load"],
            "declared_literal": anchor["load"]["predicted"]},
         "bound": "relative {0} against the section 67 receipt and the declared literal "
         "{1}".format(LOAD_TOL, LOAD_ABS_FLOOR),
         "passed": bool(comparison_ok
                        and abs(anchor["load"]["measured"] - oracle["ray_load"])
                        <= LOAD_TOL * oracle["ray_load"])},
        {"id": 4, "name": "action live", "reading": action["live"]["relative"],
         "bound": ">= {0}".format(ACTION_FLOOR_LIVE),
         "passed": bool(action["live"]["relative"] >= ACTION_FLOOR_LIVE)},
        {"id": 5, "name": "action silent", "reading": action["silent"]["relative"],
         "bound": "<= {0}".format(ACTION_CEIL_SILENT),
         "passed": bool(action["silent"]["relative"] <= ACTION_CEIL_SILENT)},
        {"id": 6, "name": "horizon adequacy", "reading": {
            "horizons": list(HORIZONS), "distinct": distinct, "span_nats": span,
            "tail": tail, "declared_threshold": declared_threshold,
            "declared_levels": len(declared_levels),
            "smallest_declared_magnitude": min(
                PROBE_OFFSET_COEFFICIENT * arm.delta_g ** PROBE_OFFSET_EXPONENT
                for arm in declared_levels)},
         "bound": "count {0}, distinct, span >= {1}, tail <= {2}, T_max >= {3}".format(
             HORIZON_COUNT, MIN_SPAN, TAIL_FRACTION, round(declared_threshold, 3)),
         "passed": bool(adequacy)},
        {"id": 7, "name": "clock", "reading": {
            "fitted": clock["rate"], "reference": clock["reference"],
            "ratio": clock["ratio"], "window": clock["window"],
            "receipt_read": clock_read["read"], "receipt_equal": clock_read["equal_to_declared"]},
         "bound": "factor {0} of the declared rate, read from the receipt".format(
             NU_TOLERANCE),
         "passed": bool(clock["passed"] and clock_read["equal_to_declared"])},
        {"id": 8, "name": "schedule conformance", "reading": "dt against the rule on every "
         "arm's own loaded projection", "bound": "dt <= 1/(40 lambda_max), declared set",
         "passed": bool(conformant)},
        {"id": 9, "name": "declared shape", "reading": budget, "bound": "{0} executions, "
         "{1} per execution, {2} total".format(DECLARED_EXECUTIONS, PER_EXECUTION_CAP,
                                               TOTAL_STEP_CAP),
         "passed": bool(shape_ok)},
        {"id": 10, "name": "silence on the ray", "reading": silence,
         "bound": "<= {0} at every horizon".format(SILENCE_FLOOR_Q),
         "passed": bool(silence <= SILENCE_FLOOR_Q)},
        {"id": 11, "name": "can-fail at the largest split", "reading": firer,
         "bound": ">= {0}".format(READABLE_FLOOR_Q), "passed": bool(firer >= READABLE_FLOOR_Q)},
        {"id": 12, "name": "anchor at the ray", "reading": anchor["ray_distance"],
         "bound": "<= {0} at T_max".format(ANCHOR_RAY_TOL),
         "passed": bool(anchor["ray_distance"] is not None
                        and anchor["ray_distance"] <= ANCHOR_RAY_TOL)},
        {"id": 13, "name": "cross-protocol oracle", "reading": arms[STEP_NOISE_ARM]["rho"]["max"],
         "bound": "bit-identical to {0}".format(ORACLE_RAY_RHO),
         "passed": bool(arms[STEP_NOISE_ARM]["rho"]["max"] == ORACLE_RAY_RHO)},
        {"id": 14, "name": "cross-executor oracle",
         "reading": [replication_arm["rho"]["max"], replication_arm["rho"]["final"],
                     replication_arm["schedule"]["lambda_max"]],
         "bound": "bit-identical to {0}, {1}, {2}".format(ORACLE_REPLICATION_RHO,
                                                          ORACLE_REPLICATION_FINAL,
                                                          ORACLE_REPLICATION_LAMBDA),
         "passed": bool(replication_arm["rho"]["max"] == ORACLE_REPLICATION_RHO
                        and replication_arm["rho"]["final"] == ORACLE_REPLICATION_FINAL
                        and replication_arm["schedule"]["lambda_max"]
                        == ORACLE_REPLICATION_LAMBDA)},
        {"id": 15, "name": "single invocation", "reading": "receipt absent at start, one "
         "process, pid recorded", "bound": "structural", "passed": True},
    ]
    return rows


def features_of(gates: list, decision: dict) -> dict:
    """Section 4.2: the six features, each readable off a gate or off the decision."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    return {
        "F1": passed[11],
        "F2": passed[10],
        "F3": bool(passed[13] and passed[14]),
        "F4": passed[7],
        "F5": passed[12],
        "F6": bool(decision["largest_split_branch"] in ("PERSIST", "TRANS")),
        "largest_split_branch": decision["largest_split_branch"],
        "verdict_candidate": decision["verdict"],
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
    observed = {}
    for key, source in (("protocol", PROTOCOL_PATH), ("probe", PROBE_PATH),
                        ("bound_module", BOUND_MODULE), ("base_probe", BASE_PROBE),
                        ("split_executor", SPLIT_EXECUTOR),
                        ("gate_load_executor", GATE_LOAD_EXECUTOR),
                        ("base_receipt", BASE_RECEIPT), ("split_receipt", SPLIT_RECEIPT),
                        ("gate_load_protocol", GATE_LOAD_PROTOCOL),
                        ("gate_load_receipt", GATE_LOAD_RECEIPT)):
        if key == "protocol":
            observed[key] = protocol_body_digest()
        elif key == "gate_load_protocol":
            observed[key] = gate_load.protocol_body_digest()
        else:
            observed[key] = digest_of(source)
    mismatches = [key for key, value in observed.items()
                  if sources.get(key, {}).get("sha256") != value]
    return {
        "present": True,
        "consistent": not mismatches,
        "mismatched_sources": mismatches,
        "schema": receipt.get("schema"),
        "status": receipt.get("status"),
        "runtime_seconds": receipt.get("runtime_seconds"),
        "verdicts": receipt.get("verdicts"),
    }


def execute() -> int:
    started = time.time()
    binding = check_binding()
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        print("REFUSING TO RUN: {0} already exists; the stopping rule allows no second "
              "invocation on a recorded result".format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    base = load_modules()
    clock_read = read_clock()
    oracle = read_oracle()
    if not clock_read["equal_to_declared"]:
        print("REFUSING TO RUN: the successor receipt holds {0} for the relaxation rate "
              "where this protocol declares {1}".format(clock_read["read"],
                                                        clock_read["declared"]))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)

    action = {
        "live": action_of(LARGEST_LOAD, LARGEST_SPLIT, base),
        "silent": action_of(0.0, LARGEST_SPLIT, base),
    }
    reduction = gate_load.reduction_residual(
        ArmSpec(0, "reduction", "reduction", 0.0, 0.0), base)

    arms, traces = {}, {}
    for spec in ARM_TABLE:
        anchor_series = traces.get(spec.twin) if spec.twin else None
        reading = run_arm(spec, base, anchor_series)
        series = reading.pop("_coordinate_series")
        rho_series = reading.pop("_rho_series")
        if spec.name in TWIN_NAMES:
            traces[spec.name] = series
        arms[spec.name] = reading
        if spec.name == CLOCK_ARM:
            clock = clock_of(rho_series, reading["schedule"]["dt"], SAMPLE[0], SAMPLE[-1])
        if reading["branch"] is not None:
            print("{0:<22} branch {1:<11} Dinf {2:>12.4e} free {3:>12.4e} peak {4:.6e} "
                  "share {5}".format(
                      spec.name, reading["branch"]["branch"],
                      reading["branch"]["held"]["offset"],
                      reading["branch"]["free"]["offset"], reading["branch"]["peak"],
                      _round(reading["branch"]["share_held"])))
        else:
            print("{0:<22} {1:<11} rho_max {2:.6e} steps {3}".format(
                spec.name, reading["role"], reading["rho"]["max"],
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
        "seconds_per_step_assumed": SECONDS_PER_STEP_ASSUMED,
        "seconds_per_step_measured": SECONDS_PER_STEP_MEASURED,
    }
    decision = decide(arms)
    gates = gate_rows(arms, action, comparison_ok, budget, clock, clock_read, oracle)
    features = features_of(gates, decision)
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
            "gate_load_executor": {"path": GATE_LOAD_EXECUTOR,
                                   "sha256": binding["observed"]["gate_load_executor_sha256"]},
            "base_receipt": {"path": BASE_RECEIPT,
                             "sha256": binding["observed"]["base_receipt_sha256"]},
            "split_receipt": {"path": SPLIT_RECEIPT,
                              "sha256": binding["observed"]["split_receipt_sha256"]},
            "gate_load_protocol": {"path": GATE_LOAD_PROTOCOL,
                                   "sha256": binding["observed"][
                                       "gate_load_protocol_body_sha256"]},
            "gate_load_receipt": {"path": GATE_LOAD_RECEIPT,
                                  "sha256": binding["observed"]["gate_load_receipt_sha256"]},
        },
        "binding": binding,
        "thresholds": {
            "readable_floor_q": READABLE_FLOOR_Q,
            "silence_floor_q": SILENCE_FLOOR_Q,
            "persist_share": PERSIST_SHARE,
            "trans_share": TRANS_SHARE,
            "residual_band": RESIDUAL_BAND,
            "clock_tolerance": CLOCK_TOLERANCE,
            "nu_reference": NU_REFERENCE,
            "nu_tolerance": NU_TOLERANCE,
            "tail_fraction": TAIL_FRACTION,
            "min_span": MIN_SPAN,
            "horizon_count": HORIZON_COUNT,
            "horizons": list(HORIZONS),
            "rate_scan_factor": RATE_SCAN_FACTOR,
            "rate_scan_points": RATE_SCAN_POINTS,
            "rate_refinement_widths": list(RATE_REFINEMENT_WIDTHS),
            "rate_refinement_steps": RATE_REFINEMENT_STEPS,
            "min_readable": MIN_READABLE,
            "min_persist": MIN_PERSIST,
            "fit_band": FIT_BAND,
            "exponent_low": EXPONENT_LOW,
            "exponent_high": EXPONENT_HIGH,
            "jump_factor": JUMP_FACTOR,
            "monotone_tolerance": MONOTONE_TOLERANCE,
            "action_floor_live": ACTION_FLOOR_LIVE,
            "action_ceiling_silent": ACTION_CEIL_SILENT,
            "anchor_ray_tolerance": ANCHOR_RAY_TOL,
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
        "reduction": {"residual": reduction, "bound": 0.0},
        "clock": {"measured": clock, "declared": clock_read},
        "oracle": oracle,
        "fits": {
            "law_held": decision["law"],
            "corroboration": decision["corroboration"],
        },
        "decision": {
            "branches": decision["branches"],
            "persisting": decision["persisting"],
            "decaying": decision["decaying"],
            "measured": decision["measured"],
            "largest_split": decision["largest_split"],
            "largest_split_branch": decision["largest_split_branch"],
            "law_issued": decision["law_issued"],
            "law_arm_count": decision["law_arm_count"],
        },
        "instrument": (decision["law"]["instrument"] if decision["law"] else None),
        "gates": gates,
        "features": features,
        "budget": budget,
        "verdicts": {
            "write": decision["verdict"] if passed else None,
            "law": (decision["law"]["label"] if (passed and decision["law"]) else None),
            "instrument": (decision["law"]["instrument"] if (passed and decision["law"])
                           else None),
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
    print("write: {0}".format(receipt["verdicts"]["write"]))
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
    if isinstance(value, np.bool_):
        return bool(value)
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
        "READABLE_FLOOR_Q": (declared_number("READABLE_FLOOR_Q"), READABLE_FLOOR_Q),
        "SILENCE_FLOOR_Q": (declared_number("SILENCE_FLOOR_Q"), SILENCE_FLOOR_Q),
        "PERSIST_SHARE": (declared_number("PERSIST_SHARE"), PERSIST_SHARE),
        "TRANS_SHARE": (declared_number("TRANS_SHARE"), TRANS_SHARE),
        "RESIDUAL_BAND": (declared_number("RESIDUAL_BAND"), RESIDUAL_BAND),
        "CLOCK_TOLERANCE": (declared_number("CLOCK_TOLERANCE"), CLOCK_TOLERANCE),
        "NU_REFERENCE": (declared_number("NU_REFERENCE"), NU_REFERENCE),
        "NU_TOLERANCE": (declared_number("NU_TOLERANCE"), NU_TOLERANCE),
        "TAIL_FRACTION": (declared_number("TAIL_FRACTION"), TAIL_FRACTION),
        "MIN_SPAN": (declared_number("MIN_SPAN"), MIN_SPAN),
        "RATE_SCAN_FACTOR": (declared_number("RATE_SCAN_FACTOR"), RATE_SCAN_FACTOR),
        "RATE_SCAN_POINTS": (declared_number("RATE_SCAN_POINTS"), float(RATE_SCAN_POINTS)),
        "RATE_REFINEMENT_STEPS": (declared_number("RATE_REFINEMENT_STEPS"),
                                  float(RATE_REFINEMENT_STEPS)),
        "MIN_READABLE": (declared_number("MIN_READABLE"), float(MIN_READABLE)),
        "MIN_PERSIST": (declared_number("MIN_PERSIST"), float(MIN_PERSIST)),
        "FIT_BAND": (declared_number("FIT_BAND"), FIT_BAND),
        "EXPONENT_LOW": (declared_number("EXPONENT_LOW"), EXPONENT_LOW),
        "EXPONENT_HIGH": (declared_number("EXPONENT_HIGH"), EXPONENT_HIGH),
        "JUMP_FACTOR": (declared_number("JUMP_FACTOR"), JUMP_FACTOR),
        "MONOTONE_TOL": (declared_number("MONOTONE_TOL"), MONOTONE_TOLERANCE),
        "ACTION_FLOOR_LIVE": (declared_number("ACTION_FLOOR_LIVE"), ACTION_FLOOR_LIVE),
        "ACTION_CEIL_SILENT": (declared_number("ACTION_CEIL_SILENT"), ACTION_CEIL_SILENT),
        "ANCHOR_RAY_TOL": (declared_number("ANCHOR_RAY_TOL"), ANCHOR_RAY_TOL),
        "LOAD_TOL": (declared_number("LOAD_TOL"), LOAD_TOL),
        "LOAD_ABS_FLOOR": (declared_number("LOAD_ABS_FLOOR"), LOAD_ABS_FLOOR),
        "STEP_SAFETY": (declared_number("STEP_SAFETY"), STEP_SAFETY),
        "DECLARED_DT": (declared_number("DECLARED_DT"), DECLARED_DT),
        "PROBE_OFFSET_COEFFICIENT": (declared_number("PROBE_OFFSET_COEFFICIENT"),
                                     PROBE_OFFSET_COEFFICIENT),
        "PROBE_OFFSET_EXPONENT": (declared_number("PROBE_OFFSET_EXPONENT"),
                                  PROBE_OFFSET_EXPONENT),
        "BOUND_SECONDS": (declared_number("BOUND_SECONDS"), BOUND_SECONDS),
        "PROJECTED_SECONDS": (declared_number("PROJECTED_SECONDS"), PROJECTED_SECONDS),
        "SECONDS_PER_STEP_ASSUMED": (declared_number("SECONDS_PER_STEP_ASSUMED"),
                                     SECONDS_PER_STEP_ASSUMED),
        "SECONDS_PER_STEP_MEASURED": (declared_number("SECONDS_PER_STEP_MEASURED"),
                                      SECONDS_PER_STEP_MEASURED),
        "DECLARED_EXECUTIONS": (declared_number("DECLARED_EXECUTIONS"),
                                float(DECLARED_EXECUTIONS)),
        "PER_EXECUTION_CAP": (declared_number("PER_EXECUTION_CAP"), float(PER_EXECUTION_CAP)),
        "TOTAL_STEP_CAP": (declared_number("TOTAL_STEP_CAP"), float(TOTAL_STEP_CAP)),
    }
    for key, (row, constant) in sorted(declared.items()):
        if row != constant:
            problems.append("the protocol declares {0} = {1}, this executor holds {2}".format(
                key, row, constant))
    for key, constant in (("HORIZONS", HORIZONS), ("DECADES", DECADES),
                          ("SWEEP_LEVELS", SWEEP_LEVELS)):
        row = declared_tuple(key)
        if row != constant:
            problems.append("the protocol declares {0} = {1}, this executor holds {2}".format(
                key, row, constant))
        else:
            print("  {0:<28} {1}".format(key, row))
    if int(declared_number("HORIZON_COUNT")) != len(HORIZONS):
        problems.append("the protocol declares {0} horizons and this executor holds "
                        "{1}".format(declared_number("HORIZON_COUNT"), len(HORIZONS)))
    widths = declared_tuple("RATE_REFINEMENT_WIDTHS")
    if widths != RATE_REFINEMENT_WIDTHS:
        problems.append("the protocol declares refinement widths {0}, this executor holds "
                        "{1}".format(widths, RATE_REFINEMENT_WIDTHS))
    if declared_number("DECLARED_DT") != DECLARED_DT:
        problems.append("the declared step {0} disagrees with {1}".format(
            declared_number("DECLARED_DT"), DECLARED_DT))

    print("self-check: the imported chain's own thresholds and the horizon arithmetic")
    if not gate_load.READABLE_FLOOR < READABLE_FLOOR_Q:
        problems.append("the imported log-space fit filters readings above {0}, which is "
                        "not below this protocol's readable floor {1}".format(
                            gate_load.READABLE_FLOOR, READABLE_FLOOR_Q))
    for name in ("FIT_BAND", "EXPONENT_LOW",
                 "EXPONENT_HIGH", "JUMP_FACTOR", "MONOTONE_TOLERANCE", "MIN_READABLE",
                 "STEP_SAFETY"):
        theirs = getattr(gate_load, name)
        ours = {"FIT_BAND": FIT_BAND, "EXPONENT_LOW": EXPONENT_LOW,
                "EXPONENT_HIGH": EXPONENT_HIGH, "JUMP_FACTOR": JUMP_FACTOR,
                "MONOTONE_TOLERANCE": MONOTONE_TOLERANCE, "MIN_READABLE": MIN_READABLE,
                "STEP_SAFETY": STEP_SAFETY}[name]
        if float(theirs) != float(ours):
            problems.append("the imported fit's {0} is {1} against this protocol's "
                            "{2}".format(name, theirs, ours))
    tail = float(np.exp(-NU_REFERENCE * HORIZONS[-1]))
    span = float(NU_REFERENCE * (HORIZONS[-1] - HORIZONS[0]))
    threshold = float(np.log(1.0 / TAIL_FRACTION) / NU_REFERENCE)
    distinct = len({round(float(np.exp(-NU_REFERENCE * h)), 15) for h in HORIZONS})
    print("  1/nu {0:.6f}, span {1:.6f} nats, tail {2:.9f}, declared threshold {3:.6f}".format(
        1.0 / NU_REFERENCE, span, tail, threshold))
    if span < MIN_SPAN:
        problems.append("the horizon set spans {0} relaxation times against the declared "
                        "minimum {1}".format(span, MIN_SPAN))
    if tail > TAIL_FRACTION:
        problems.append("the horizon set's tail is {0}, above the declared fraction "
                        "{1}".format(tail, TAIL_FRACTION))
    if HORIZONS[-1] < threshold:
        problems.append("the last horizon {0} is below the declared threshold {1}".format(
            HORIZONS[-1], threshold))
    if distinct != len(HORIZONS):
        problems.append("the declared horizons do not give distinct exponential weights")

    print("self-check: the declared arm table")
    names = [arm.name for arm in ARM_TABLE]
    declared_steps = sum(arm.declared_schedule()[2] for arm in ARM_TABLE)
    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        problems.append("{0} arms in the table against {1} declared".format(
            len(ARM_TABLE), DECLARED_EXECUTIONS))
    if [arm.index for arm in ARM_TABLE] != list(range(1, DECLARED_EXECUTIONS + 1)):
        problems.append("the arm indices are not 1..{0}".format(DECLARED_EXECUTIONS))
    if len(set(names)) != len(names):
        problems.append("the arm names are not unique")
    print("  arms {0}, steps {1} (cap {2}), largest {3} (cap {4})".format(
        len(ARM_TABLE), declared_steps, TOTAL_STEP_CAP,
        max(arm.declared_schedule()[2] for arm in ARM_TABLE), PER_EXECUTION_CAP))
    if declared_steps > TOTAL_STEP_CAP:
        problems.append("the declared schedule totals {0} steps against the cap {1}".format(
            declared_steps, TOTAL_STEP_CAP))
    if max(arm.declared_schedule()[2] for arm in ARM_TABLE) > PER_EXECUTION_CAP:
        problems.append("an arm exceeds the per-execution cap")
    seen = set()
    for arm in ARM_TABLE:
        if arm.twin:
            if arm.twin not in seen:
                problems.append("{0}'s twin {1} does not precede it".format(
                    arm.name, arm.twin))
            else:
                twin = [item for item in ARM_TABLE if item.name == arm.twin][0]
                if twin.role not in ("anchor",) or twin.load_c != arm.load_c:
                    problems.append("{0}'s twin {1} is not an anchor on the same load".format(
                        arm.name, arm.twin))
                if twin.declared_schedule() != arm.declared_schedule():
                    problems.append("{0} and its twin {1} disagree on the schedule".format(
                        arm.name, arm.twin))
        elif arm.role not in ("anchor", "oracle"):
            problems.append("{0} declares no twin and is not an anchor or an oracle".format(
                arm.name))
        seen.add(arm.name)
    for arm in ARM_TABLE:
        if arm.name in SWEEP_ORDER or arm.role == "silence":
            if arm.declared_schedule()[2] + 1 <= SAMPLE[-1]:
                problems.append("{0} is read at the declared horizons but runs only {1} "
                                "steps".format(arm.name, arm.declared_schedule()[2]))
    sweep = [arm for arm in ARM_TABLE if arm.name in SWEEP_ORDER]
    if [arm.name for arm in sweep] != list(SWEEP_ORDER):
        problems.append("the sweep family is not the declared order {0}".format(SWEEP_ORDER))
    if [arm.delta_g for arm in sweep] != list(SWEEP_LEVELS):
        problems.append("the sweep arms do not carry the declared split sizes")
    if len({arm.delta_g for arm in sweep}) != len(sweep):
        problems.append("the sweep arms do not carry distinct split sizes")

    print("self-check: the label vocabulary is reachable in every branch")
    linear = tuple(3.0e-4 * level for level in DECADES)
    cliff = list(linear)
    cliff[-1] = cliff[-1] * 1.0e4
    bent = []
    value = 1.0e-9
    for position in range(len(DECADES)):
        if position:
            value *= 3.0 if position % 2 else 20.0
        bent.append(value)
    short = tuple(3.0e-4 * level for level in DECADES[:2])
    preview = (
        ("PROPORTIONAL", law_of(DECADES, linear)),
        ("CLIFF", law_of(DECADES, tuple(cliff))),
        ("NONLINEAR", law_of(DECADES, tuple(bent))),
        ("INCONCLUSIVE", law_of(DECADES[:2], short)),
    )
    for wanted, reading in preview:
        if reading["label"] != wanted:
            problems.append("the law rule labels its {0} preview as {1}".format(
                wanted, reading["label"]))
        else:
            print("  law {0:<14} reached (exponent {1})".format(
                wanted, reading["fit"]["exponent"]))

    print("self-check: the branch rule is reachable in every branch, on synthetic readings")
    for structure, expected in WITNESS_LABELS.items():
        for ratio, wanted in zip(WITNESS_RATIOS, expected):
            rate = NU_REFERENCE * ratio
            times = np.array(HORIZONS)
            if structure == "transient":
                values = WITNESS_AMPLITUDE * np.exp(-rate * times)
            elif structure == "shift":
                values = WITNESS_OFFSET * (1.0 - np.exp(-rate * times))
            else:
                values = (WITNESS_OFFSET * (1.0 - np.exp(-rate * times))
                          + WITNESS_AMPLITUDE * np.exp(-rate * times))
            reading = classify([float(value) for value in values])
            if reading["branch"] != wanted:
                problems.append("the branch rule labels a synthetic {0} at rate ratio {1} "
                                "as {2} where the declared table says {3}".format(
                                    structure, ratio, reading["branch"], wanted))
    print("  {0} structures x {1} rate ratios all reached their declared branches".format(
        len(WITNESS_LABELS), len(WITNESS_RATIOS)))

    print("self-check: the fragility the conjunction exists for")
    rate = NU_REFERENCE * 1.024
    values = WITNESS_AMPLITUDE * np.exp(-rate * np.array(HORIZONS))
    reading = classify([float(value) for value in values])
    share = abs(reading["held"]["offset"]) / abs(reading["terminal"])
    print("  a pure transient 2.4% off the declared clock: held share {0:.4f} (inside the "
          "persist band), free share {1:.4f}, rate ratio {2:.4f}, branch {3}".format(
              share, abs(reading["free"]["offset"]) / abs(reading["terminal"]),
              reading["rate_ratio"], reading["branch"]))
    if not share >= PERSIST_SHARE:
        problems.append("the fragility witness no longer exercises the held fit: its share "
                        "is {0}".format(share))
    if reading["branch"] != "TRANS":
        problems.append("the conjoint rule no longer rescues the fragility witness: it "
                        "returns {0}".format(reading["branch"]))

    print("self-check: the verdict vocabulary is reachable in every branch")
    previews = (
        ("WRITES", {"largest": "PERSIST", "persist": 6, "trans": 0}),
        ("PERTURBS_ONLY", {"largest": "TRANS", "persist": 0, "trans": 6}),
        ("INCONCLUSIVE", {"largest": "UNRESOLVED", "persist": 0, "trans": 6}),
        ("INCONCLUSIVE", {"largest": "PERSIST", "persist": 1, "trans": 5}),
        ("INCONCLUSIVE", {"largest": "TRANS", "persist": 0, "trans": 3}),
        ("INCONCLUSIVE", {"largest": "BELOW_FLOOR", "persist": 0, "trans": 0}),
    )
    for wanted, counts in previews:
        branches = {"largest": counts["largest"]}
        persisting = ["p{0}".format(index) for index in range(counts["persist"])]
        decaying = ["d{0}".format(index) for index in range(counts["trans"])]
        got = verdict_of(branches, persisting, decaying, counts["largest"])
        if got != wanted:
            problems.append("the verdict rule returns {0} where the declared table says "
                            "{1} for {2}".format(got, wanted, counts))
        else:
            print("  verdict {0:<13} reached ({1})".format(wanted, counts))

    print("self-check: the decision rule reads every gate and every feature")
    rows = [{"id": index, "name": "synthetic", "passed": True} for index in range(1, 16)]
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
    print("  15 gates and 6 features each carry the status")

    print("self-check: the seeded-state action, the reduction and the anchor load")
    live = action_of(LARGEST_LOAD, LARGEST_SPLIT, base)
    silent = action_of(0.0, LARGEST_SPLIT, base)
    print("  action live   {0:.12e} (absolute {1:.12e} of the step's own drift {2:.12e})".format(
        live["relative"], live["absolute"], live["drift"]))
    print("  action silent {0:.12e}".format(silent["relative"]))
    if live["relative"] < ACTION_FLOOR_LIVE:
        problems.append("the split's action at the largest load is {0}, below the floor "
                        "{1}".format(live["relative"], ACTION_FLOOR_LIVE))
    if silent["relative"] > ACTION_CEIL_SILENT:
        problems.append("the split's action on the ray seed is {0}, above the ceiling "
                        "{1}".format(silent["relative"], ACTION_CEIL_SILENT))
    residual = gate_load.reduction_residual(
        ArmSpec(0, "reduction", "reduction", 0.0, 0.0), base)
    print("  zero-split reduction residual {0!r}".format(residual))
    if residual != 0.0:
        problems.append("the split right-hand side does not reduce to the successor's own "
                        "at zero split: {0}".format(residual))
    anchor_spec = ArmSpec(0, "anchor", "anchor", LARGEST_LOAD, 0.0)
    state = gate_load.loaded_seed(anchor_spec, base)
    measured = gate_load.load_of(state, base)
    comparison = gate_load.load_comparison(anchor_spec, measured)
    receipt_load = float(load_json(GATE_LOAD_RECEIPT)["arms"]["loadLmax_reference"]["load"]
                         ["measured"])
    print("  anchor load {0:.12e}, section 67 receipt {1:.12e}, declared literal "
          "{2:.12e}".format(measured, receipt_load, ORACLE_RAY_LOAD))
    if not comparison["passed"]:
        problems.append("the anchor's measured load {0} disagrees with the declared "
                        "{1}".format(measured, comparison["predicted"]))
    if abs(measured - receipt_load) > LOAD_TOL * receipt_load:
        problems.append("the anchor's measured load {0} disagrees with section 67's receipt "
                        "{1}".format(measured, receipt_load))
    if receipt_load != ORACLE_RAY_LOAD:
        problems.append("the declared oracle load {0} is not section 67's receipt value "
                        "{1}".format(ORACLE_RAY_LOAD, receipt_load))

    print("self-check: the clock and the oracle literals against the bound receipts")
    clock_read = read_clock()
    print("  clock read from {0}: {1!r} against the declared {2!r}".format(
        clock_read["source_path"], clock_read["read"], clock_read["declared"]))
    if not clock_read["equal_to_declared"]:
        problems.append("the successor receipt's relaxation rate {0} is not the declared "
                        "{1}".format(clock_read["read"], clock_read["declared"]))
    oracle = read_oracle()
    print("  ray {0!r}, replication {1!r}, terminal {2!r}, lambda {3!r}, load {4!r}, "
          "clock {5!r}".format(
              oracle["ray_rho"], oracle["replication_rho"], oracle["replication_final"],
              oracle["replication_lambda"], oracle["ray_load"], oracle["clock"]))
    for key, declared_value in (("ray_rho", ORACLE_RAY_RHO),
                                ("replication_rho", ORACLE_REPLICATION_RHO),
                                ("replication_final", ORACLE_REPLICATION_FINAL),
                                ("replication_lambda", ORACLE_REPLICATION_LAMBDA),
                                ("ray_load", ORACLE_RAY_LOAD),
                                ("clock", ORACLE_CLOCK)):
        if oracle[key] != declared_value:
            problems.append("the declared oracle literal {0} is {1} against the receipts' "
                            "{2}".format(key, declared_value, oracle[key]))
    ray_silence = float(load_json(GATE_LOAD_RECEIPT)["arms"]["ray_short"]["rho"]["max"])
    if ray_silence != ORACLE_RAY_RHO:
        problems.append("section 67's own ray_short residual {0} is not the declared "
                        "{1}".format(ray_silence, ORACLE_RAY_RHO))

    print("self-check: the identity reading of the ray, one step at every declared split")
    for level in (LARGEST_SPLIT, DECADES[-1]):
        quiet = action_of(0.0, level, base)
        print("  ray seed, delta_g {0:>8.4g}: action {1!r}".format(level, quiet["relative"]))
        if quiet["relative"] != 0.0:
            problems.append("the split's action on the ray seed at delta_g {0} is {1}, not "
                            "the exact zero the bracket's vanishing implies".format(
                                level, quiet["relative"]))

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
    projection_assumed = SECONDS_PER_STEP_ASSUMED * declared_steps
    print("  {0} arms, {1} steps, projected {2:.1f} s at the assumed rate and {3:.1f} s at "
          "the measured one, against the bound {4} s".format(
              len(ARM_TABLE), declared_steps, projection_assumed,
              SECONDS_PER_STEP_MEASURED * declared_steps, BOUND_SECONDS))
    if abs(projection_assumed - PROJECTED_SECONDS) > 0.01 * PROJECTED_SECONDS:
        problems.append("the declared projection {0} s is not the assumed rate times the "
                        "declared steps ({1:.1f} s)".format(PROJECTED_SECONDS,
                                                            projection_assumed))
    if PROJECTED_SECONDS > BOUND_SECONDS:
        problems.append("the declared projection exceeds the bound")

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
