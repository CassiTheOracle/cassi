"""Does the loop carrier hold one composition coordinate or several?

The spent bodies read the carrier's write and its retention on one conserved scalar: the
exterior mean of the composition. Two writes into one conserved quantity have nowhere else
to go, so a coexistence test taken on that scalar can only ever return "it adds". This
protocol reads the carrier's composition where the declaration itself resolves it -- the
per-orientation, per-loop-sample composition profile

    c_{s,k}(t) = mean_x bounded_q( F_{Y,s}(x, chi_k), F_{I,s}(x, chi_k) ),  s in {+1, -1},
    k = 0..23,

and writes two gate directions into it, both at the largest declared magnitude:

    A: kappa_Y = kappa_I = rate (1 + delta cos chi)              the established write
    B: kappa_{Y,s} = rate (1 + delta s cos chi), kappa_I = ...    orientation-antisymmetric

A lies on the even group e_k = (c_{+k} + c_{-k})/2 and B on the odd group
o_k = (c_{+k} - c_{-k})/2 of that profile. The two directions are read *before* any
integration on the loaded seed (one declared step each, no write as the control), and the
pre-flight passes only if each direction is readable on its own group, neither leaks into
the other's group above the readable floor, the two displaced directions are distinguishable
on the declared coordinates, and the null moves neither coordinate. If the two directions
are not distinguishable, that is the finding: the conserved level has one writable
coordinate on this realization, and multi-item storage has to come from placement rather
than from the carrier. No re-tuning of the observable, no hand-built basis.

Three verdicts come out of one invocation, all on declared readings:

    coexistence    at T3 = 1350: `COEXIST_ADDITIVE`, `COEXIST_NONADDITIVE`, `INTERFERE`,
                   `RESERVED_ONE_RETAINED` or `RESERVED_NOT_DISTINGUISHABLE`
    erasure        at T2 = 900:  `ERASES_ONE`, `RESIDUAL`, `MOVES_BOTH`, `RESERVED_NO_B`
    composition    the joint arm read on the retained scalar A, reported and not gated

    python computations/verify_loop_carrier_composition_coexistence.py --self-check
    python computations/verify_loop_carrier_composition_coexistence.py --design-probe
    python computations/verify_loop_carrier_composition_coexistence.py --freeze
    timeout 900 python computations/verify_loop_carrier_composition_coexistence.py
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

# The spent chain is imported as a library: the split executor's right-hand side is the
# established write this protocol's direction A must reduce to, the gate-load executor
# supplies the loaded seed and the step rule, the predecessor supplies the two release fits
# and the scalar coordinate, and the successor supplies the receipt the replication reads.
import verify_loop_carrier_attractor_write as prior  # noqa: E402
import verify_loop_carrier_attractor_write_successor as successor  # noqa: E402
import verify_loop_carrier_gate_load as gate_load  # noqa: E402
import verify_loop_carrier_projection_split as split  # noqa: E402

# Section 0: the bound sources, all by digest.
BOUND_MODULE = prior.BOUND_MODULE
BASE_PROBE = prior.BASE_PROBE
SPLIT_EXECUTOR = prior.SPLIT_EXECUTOR
GATE_LOAD_EXECUTOR = prior.GATE_LOAD_EXECUTOR
GATE_LOAD_PROTOCOL = prior.GATE_LOAD_PROTOCOL
BASE_RECEIPT = prior.BASE_RECEIPT
SPLIT_RECEIPT = prior.SPLIT_RECEIPT
GATE_LOAD_RECEIPT = prior.GATE_LOAD_RECEIPT
PRIOR_EXECUTOR = prior.PROBE_PATH
PRIOR_RECEIPT = prior.RECEIPT_PATH
SUCCESSOR_PROTOCOL = successor.PROTOCOL_PATH
SUCCESSOR_EXECUTOR = successor.PROBE_PATH
SUCCESSOR_RECEIPT = successor.RECEIPT_PATH

PROTOCOL_PATH = "computations/loop-carrier-composition-coexistence-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_composition_coexistence.py"
RECEIPT_PATH = "runs/loop_carrier_composition_coexistence/verification.json"
INVOCATION = ("timeout 900 python "
              "computations/verify_loop_carrier_composition_coexistence.py")
RECEIPT_SCHEMA = "cassi.loop-carrier-composition-coexistence.v1"
BOUND_SECONDS = 900.0

# Section 0 declares both hashes: this file's, and the digest of the frozen body (everything
# from "## 1." to just before "## 8."). The two are cross-bound without a fix point, because
# section 0 sits outside the body range. Filled by the freeze pass.
FROZEN_BODY_DIGEST = "09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.3: the declared thresholds. Everything the spent chain fixed is carried
# unchanged; the four that this protocol adds are the group reading's floor and silence
# floor, the cross-group action bound and the direction cosines' bound.
READABLE_FLOOR_Q = prior.READABLE_FLOOR_Q
SILENCE_FLOOR_Q = prior.SILENCE_FLOOR_Q
PERSIST_SHARE = prior.PERSIST_SHARE
TRANS_SHARE = prior.TRANS_SHARE
RESIDUAL_BAND = prior.RESIDUAL_BAND
CLOCK_TOLERANCE = prior.CLOCK_TOLERANCE
NU_REFERENCE = prior.NU_REFERENCE
NU_TOLERANCE = prior.NU_TOLERANCE
TAIL_FRACTION = prior.TAIL_FRACTION
MIN_SPAN = prior.MIN_SPAN
HORIZON_COUNT = prior.HORIZON_COUNT
MIN_READABLE = prior.MIN_READABLE
MIN_PERSIST = prior.MIN_PERSIST
ACTION_FLOOR_LIVE = prior.ACTION_FLOOR_LIVE
ACTION_CEIL_SILENT = prior.ACTION_CEIL_SILENT
ANCHOR_RAY_TOL = prior.ANCHOR_RAY_TOL
LOAD_TOL = prior.LOAD_TOL
LOAD_ABS_FLOOR = prior.LOAD_ABS_FLOOR
STEP_SAFETY = prior.STEP_SAFETY
STEP_CANDIDATES = prior.STEP_CANDIDATES
DECLARED_DT = prior.DECLARED_DT
PROFILE = prior.PROFILE
HORIZONS = prior.HORIZONS
LARGEST_SPLIT = prior.LARGEST_SPLIT
LARGEST_LOAD = prior.LARGEST_LOAD
# New here, fixed against the design probe's own readings before the freeze.
READABLE_LEVEL = 1.0e-12
SILENCE_LEVEL = 1.0e-14
CROSS_CEIL = 1.0e-3
DISTINCTNESS_CEIL = 0.5
NULL_CEIL = 0.0
RAY_READABLE_FLOOR = 1.0e-6
RETENTION_SHARE = 0.5
RELEASE_SHARE = 0.05
ADDITIVE_BAND = prior.RESIDUAL_BAND
REPLICATION_TOL = 1.0e-15
PROBE_TOL = 1.0e-12
# Section 1.5: the successor receipt's replication readings, declared before the run.
REPLICATION_LOAD_REFERENCE_AT_T1 = 0.8923960494310218
REPLICATION_WRITE_A_AT_T1 = 0.8918036475597466
REPLICATION_RAY_WRITE_AT_T1 = 0.8923974885141087
REPLICATION_WRITE_A_RAY_DISTANCE = 0.0013261506410605264
REPLICATION_RAY_WRITE_RAY_DISTANCE = 4.615955614456139e-15
ORACLE_SCALAR_ACTION_LIVE = 0.05339073136188713
ORACLE_SCALAR_ACTION_SILENT = 0.0
ORACLE_SCALAR_ACTION_DRIFT = 6.248434071254305e-05
ORACLE_RAY_RHO = successor.ORACLE_RAY_RHO
# Section 1.5: the design probe's group readings, in the declared order of PROBE_READINGS,
# declared before the run; gate 6 checks the run reproduces them.
PROBE_READINGS = (3.5782503187010394e-03, 0.0000000000000000e+00, 8.0544689706744455e-05,
                  2.9373740229761033e-16, 3.6690824708873952e-03, 4.3795864823950710e-10,
                  3.6684648139275978e-03, 4.3790254439566828e-10, 3.5854949127067321e-03,
                  0.0000000000000000e+00, 3.6690824768987312e-03, 0.0000000000000000e+00)

# Section 3: the declared schedules. Three phases of the same length: the first write, the
# second write, and the release, so the drive is held for two relaxation-scale spans and
# then removed for a third.
PHASE_UNITS = 450.0
PHASE_STEPS = 22500
TOTAL_UNITS = 1350.0
TOTAL_STEPS = 67500
T1_INDEX = PHASE_STEPS
T2_INDEX = 2 * PHASE_STEPS
T3_INDEX = TOTAL_STEPS
RELEASE_SAMPLE = tuple(T2_INDEX + int(round(h / DECLARED_DT)) for h in HORIZONS)
SAMPLES = ((("initial", 0), ("t1", T1_INDEX), ("t2", T2_INDEX))
           + tuple(("r{0}".format(position + 1), index)
                   for position, index in enumerate(RELEASE_SAMPLE))
           + (("t3", T3_INDEX),))
READ_KEYS = ("t1", "t2", "t3")
RELEASE_KEYS = tuple("r{0}".format(position + 1) for position in range(len(HORIZONS)))
N_CHI = 24

NO_WRITE = (0.0, 0.0)
DIRECTION_A = (1.0, 0.0)
DIRECTION_B = (0.0, 1.0)
JOINT = (1.0, 1.0)
ERASE = (-1.0, 1.0)

PER_EXECUTION_CAP = 100000
TOTAL_STEP_CAP = 600000
DECLARED_EXECUTIONS = 8
SECONDS_PER_STEP_MEASURED = 6.665e-4
SECONDS_PER_STEP_ASSUMED = prior.SECONDS_PER_STEP_ASSUMED
PROJECTED_SECONDS_MEASURED = 315.0
PROJECTED_SECONDS_ASSUMED = 396.0

GROUPS = ("even", "odd")
COEXISTENCE_VERDICTS = ("COEXIST_ADDITIVE", "COEXIST_NONADDITIVE", "INTERFERE",
                        "RESERVED_ONE_RETAINED", "RESERVED_NOT_DISTINGUISHABLE")
ERASURE_VERDICTS = ("ERASES_ONE", "RESIDUAL", "MOVES_BOTH", "RESERVED_NO_B")
GROUP_LABELS = ("SILENT", "RETAINED", "DECAYED", "UNRESOLVED")

PROBE_READING_ORDER = ("write_A:even:t1", "write_A:odd:t1", "write_B:even:t1",
                       "write_B:odd:t1", "joint_AB:even:t2", "joint_AB:odd:t2",
                       "erase_A:even:t2", "erase_A:odd:t2", "write_A:even:t3",
                       "write_B:odd:t3", "joint_AB:even:t3", "joint_AB:odd:t3")


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
    """Section 0's binding of the frozen text: everything from "## 1." to "## 8."."""
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


def declared_literal_tuple(key: str) -> tuple:
    row = protocol_row(key).strip().strip("$")
    return tuple(float(item.strip().strip("$=")) for item in row.split(","))


BINDING_SOURCES = (
    ("frozen_body_sha256", None),
    ("executor_sha256", None),
    ("prior_body_sha256", None),
    ("prior_executor_sha256", PRIOR_EXECUTOR),
    ("bound_module_sha256", BOUND_MODULE),
    ("base_probe_sha256", BASE_PROBE),
    ("split_executor_sha256", SPLIT_EXECUTOR),
    ("gate_load_executor_sha256", GATE_LOAD_EXECUTOR),
    ("base_receipt_sha256", BASE_RECEIPT),
    ("split_receipt_sha256", SPLIT_RECEIPT),
    ("gate_load_protocol_body_sha256", None),
    ("gate_load_receipt_sha256", GATE_LOAD_RECEIPT),
    ("prior_receipt_sha256", PRIOR_RECEIPT),
    ("successor_protocol_body_sha256", None),
    ("successor_executor_sha256", SUCCESSOR_EXECUTOR),
    ("successor_receipt_sha256", SUCCESSOR_RECEIPT),
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
        elif key == "prior_body_sha256":
            observed[key] = prior.protocol_body_digest()
        elif key == "gate_load_protocol_body_sha256":
            observed[key] = gate_load.protocol_body_digest()
        elif key == "successor_protocol_body_sha256":
            observed[key] = successor.protocol_body_digest()
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
    # The successor's own sixteen rows are the strongest available statement that the chain
    # family is intact, and it costs one call: its refusal is a refusal here.
    try:
        successor.check_binding()
    except SystemExit:
        problems.append("the successor's own binding of the chain failed")
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
    """Import the successor probe through the spent executors' own loader."""
    try:
        return gate_load.load_modules()
    except SystemExit:
        print("REFUSING TO RUN: the successor probe's own binding of the frozen operators "
              "failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)


class CoexistenceSpec(gate_load.LoadSpec):
    """One declared arm: a load, a seed, and a three-phase write plan.

    The plan is a tuple of three `(even, odd)` coefficient pairs, one per phase, applied to
    the declared modulation

        m_s(chi) = delta (even + s odd) cos chi,   kappa_{Y,s} = rate (1 + m_s),
                                                   kappa_{I,s} = rate (1 - m_s).

    Direction A is `(1, 0)`, direction B is `(0, 1)`, the joint is `(1, 1)` and the
    counter-write is `(-1, 1)`: on the two orientations that is `0` and `-2` against the
    joint's `2` and `0`, so the change from the joint to the erase phase is `-2` on the even
    coefficient and `0` on the odd one.
    """

    def __init__(self, index: int, name: str, role: str, load_c: float, plan: tuple,
                 baseline: str, schedule_key: str = "phases"):
        gate_load.LoadSpec.__init__(self, index, name, role, load_c, LARGEST_SPLIT,
                                    schedule_key, "")
        self.plan = tuple(plan)
        self.baseline = baseline

    def declared_schedule(self) -> tuple:
        if self.schedule_key == "short":
            return prior.SHORT_DT, prior.SHORT_HORIZON, prior.SHORT_STEPS
        return DECLARED_DT, TOTAL_UNITS, TOTAL_STEPS

    def coefficients(self, index: int) -> tuple:
        if self.schedule_key == "short":
            return self.plan[0]
        return self.plan[min(index // PHASE_STEPS, len(self.plan) - 1)]


def build_arm_table() -> tuple:
    """Section 3: the declared arms. One per direction, one joint, one counter-write, one
    ray pair predicted silent, one loaded reference, and the spent short-horizon oracle."""
    arms = [
        CoexistenceSpec(1, "ray_anchor", "baseline", 0.0,
                        (NO_WRITE, NO_WRITE, NO_WRITE), "itself"),
        CoexistenceSpec(2, "load_reference", "baseline", LARGEST_LOAD,
                        (NO_WRITE, NO_WRITE, NO_WRITE), "itself"),
        CoexistenceSpec(3, "ray_write", "ray", 0.0,
                        (DIRECTION_A, DIRECTION_A, NO_WRITE), "ray_anchor"),
        CoexistenceSpec(4, "write_A", "single", LARGEST_LOAD,
                        (DIRECTION_A, DIRECTION_A, NO_WRITE), "load_reference"),
        CoexistenceSpec(5, "write_B", "single", LARGEST_LOAD,
                        (DIRECTION_B, DIRECTION_B, NO_WRITE), "load_reference"),
        CoexistenceSpec(6, "joint_AB", "joint", LARGEST_LOAD,
                        (JOINT, JOINT, NO_WRITE), "load_reference"),
        CoexistenceSpec(7, "erase_A", "erase", LARGEST_LOAD,
                        (JOINT, ERASE, NO_WRITE), "load_reference"),
        CoexistenceSpec(8, "step_short", "oracle", 0.0,
                        (NO_WRITE, NO_WRITE, NO_WRITE), "itself", "short"),
    ]
    return tuple(arms)


ARM_TABLE = build_arm_table()

# The two zero-displacement baselines, and the arms each family is read against.
BASELINE_NAMES = ("ray_anchor", "load_reference")
LOADED_ARMS = ("load_reference", "write_A", "write_B", "joint_AB", "erase_A")


def write_rhs(state: np.ndarray, rate: np.ndarray, coefficients: tuple, base,
              delta: float) -> np.ndarray:
    """The successor's (LB6) right-hand side with the declared two-channel modulation.

    Term for term the split executor's right-hand side; at `coefficients = (c, 0)` the gate
    line is `kappa (1 +- delta c cos chi)`, which is the split executor's own line and is
    checked bit-identical against it. The orientation-signed branch is new: it puts the
    declared sign on the carrier's orientation index, so the two orientations' gates are
    offset by `2 delta odd cos chi`.
    """
    dchi = base.loop_dx(state.shape[base.LOOP_AXIS])
    out = (
        -base.U * base.frozen.derivative(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        + base.D_X * base.frozen.laplacian(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        - base.SIGNS * base.OMEGA * base.frozen.derivative(state, base.LOOP_AXIS, dchi)
        + base.D_LOOP * base.frozen.laplacian(state, base.LOOP_AXIS, dchi)
        + base.EXCHANGE * (state[:, ::-1] - state)
    )
    cosine = np.cos(base.loop_grid(state.shape[base.LOOP_AXIS]))[None, :]
    even, odd = coefficients
    if odd == 0.0:
        modulation = delta * even * cosine
        kappa_y = rate * (1.0 + modulation)
        kappa_i = rate * (1.0 - modulation)
    else:
        sign = np.array((1.0, -1.0))[:, None, None]
        modulation = delta * (even + sign * odd) * cosine[None, :, :]
        kappa_y = rate[None, :, :] * (1.0 + modulation)
        kappa_i = rate[None, :, :] * (1.0 - modulation)
    out[0] += kappa_y * (-state[0] + base.PHI * state[1])
    out[1] += kappa_i * (state[0] - base.PHI * state[1])
    return out


def write_step(state: np.ndarray, dt: float, coefficients: tuple, base,
               delta: float) -> np.ndarray:
    return base.rk4_step(state, dt, lambda current: write_rhs(
        current, split.gate_rate_of(current, base), coefficients, base, delta))


def composition_profile(state: np.ndarray, base) -> np.ndarray:
    """The declared reading domain: c_{s,k}, the per-orientation, per-loop-sample mean."""
    composition = base.frozen.bounded_q(state[0], state[1])
    return composition.mean(axis=base.EXTERIOR_AXIS)


def group_of(profile: np.ndarray) -> tuple:
    """The field's own partition of the reading domain: even and odd in the orientation."""
    return 0.5 * (profile[0] + profile[1]), 0.5 * (profile[0] - profile[1])


def vector_norm(vector: np.ndarray) -> float:
    """The declared norm of a coordinate block: the Euclidean norm over its coordinates."""
    return float(np.sqrt(np.sum(np.square(np.asarray(vector, dtype=np.float64)))))


def cosine_of(first: np.ndarray, second: np.ndarray) -> float:
    denominator = vector_norm(first) * vector_norm(second)
    if denominator == 0.0:
        return None
    return float(np.sum(np.asarray(first) * np.asarray(second)) / denominator)


def direction_cosine(first: np.ndarray, second: np.ndarray) -> float:
    """Cosine over the two groups' coordinates as one declared 48-vector."""
    left = np.concatenate([np.asarray(first[0]).ravel(), np.asarray(first[1]).ravel()])
    right = np.concatenate([np.asarray(second[0]).ravel(), np.asarray(second[1]).ravel()])
    return cosine_of(left, right)


def action_preflight(base) -> dict:
    """Section 1.5: the four readings and the null, on the seeded state, before integration.

    Displacement of one declared step with direction D against the same step with no write,
    in the declared 48 coordinates, as the fraction of that step's own profile change.
    """
    spec = CoexistenceSpec(0, "preflight", "preflight", LARGEST_LOAD,
                           (NO_WRITE, NO_WRITE, NO_WRITE), "itself")
    state = gate_load.loaded_seed(spec, base)
    seed = composition_profile(state, base)
    plain = composition_profile(write_step(state, DECLARED_DT, NO_WRITE, base,
                                           LARGEST_SPLIT), base)
    drift = vector_norm(plain - seed)
    readings = {}
    vectors = {}
    for label, coefficients in (("A", DIRECTION_A), ("B", DIRECTION_B),
                                ("null", NO_WRITE)):
        stepped = composition_profile(write_step(state, DECLARED_DT, coefficients, base,
                                                 LARGEST_SPLIT), base)
        difference = group_of(stepped - plain)
        vectors[label] = difference
        readings[label] = {
            "even_norm": vector_norm(difference[0]),
            "odd_norm": vector_norm(difference[1]),
            "absolute": vector_norm(np.concatenate([difference[0], difference[1]])),
        }
    for label in readings:
        absolute = readings[label]["absolute"]
        readings[label]["relative"] = (absolute / drift if drift > 0.0 else 0.0)
        readings[label]["even_relative"] = (
            readings[label]["even_norm"] / drift if drift > 0.0 else 0.0)
        readings[label]["odd_relative"] = (
            readings[label]["odd_norm"] / drift if drift > 0.0 else 0.0)
    cosine = direction_cosine(vectors["A"], vectors["B"])
    scalar = {
        "live": prior.action_of(LARGEST_LOAD, LARGEST_SPLIT, base),
        "silent": prior.action_of(0.0, LARGEST_SPLIT, base),
    }
    return {
        "drift": drift,
        "seed_profile_sum": float(np.sum(seed)),
        "readings": readings,
        "direction_cosine": cosine,
        "scalar": scalar,
        "checks": {
            "live_A": readings["A"]["even_relative"] >= ACTION_FLOOR_LIVE,
            "live_B": readings["B"]["odd_relative"] >= ACTION_FLOOR_LIVE,
            "cross_A": readings["A"]["odd_relative"] <= CROSS_CEIL,
            "cross_B": readings["B"]["even_relative"] <= CROSS_CEIL,
            "distinct": bool(cosine is not None and abs(cosine) <= DISTINCTNESS_CEIL),
            "null_zero": readings["null"]["absolute"] <= NULL_CEIL,
        },
    }


def arm_record(spec, base) -> dict:
    """One declared arm: its schedule, its coordinate series, its structure, its profiles."""
    state = gate_load.loaded_seed(spec, base)
    dt, horizon, steps = spec.declared_schedule()
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])
    lambda_max = float(base.arm_lambda_max(split.proxy_arm(spec, base), kappa))
    conformant = bool(dt <= 1.0 / (STEP_SAFETY * lambda_max) and dt in STEP_CANDIDATES)
    comparison = gate_load.load_comparison(spec, gate_load.load_of(state, base))
    canonical = base.canonical_initial(PROFILE)
    wanted = {}
    for key, index in SAMPLES:
        if index <= steps:
            wanted.setdefault(index, []).append(key)
    series = np.empty(steps + 1)
    profiles = {}
    ray_distances = {}
    rho, minima, projections, low, high = [], [], [], [], []
    annihilation, idempotence = [], []
    for index in range(steps + 1):
        current = base.projection(state)
        series[index] = prior.coordinate_of(current, base)
        rho.append(gate_load.rho_of(current, canonical))
        minima.append(float(np.min(state)))
        projections.append(float(np.min(current)))
        composition = base.frozen.bounded_q(current[0], current[1])
        low.append(float(np.min(composition)))
        high.append(float(np.max(composition)))
        annihilation.append(gate_load.annihilation_of(state, base))
        idempotence.append(base.relative_residual(
            base.projection(base.lift(current, state.shape[base.LOOP_AXIS])), current))
        if index in wanted:
            groups = group_of(composition_profile(state, base))
            for label in wanted[index]:
                profiles[label] = groups
                ray_distances[label] = prior.ray_distance_of(current, base)
        if index == steps:
            break
        coefficients = spec.coefficients(index)
        state = base.rk4_step(state, dt, lambda current: write_rhs(
            current, split.gate_rate_of(current, base), coefficients, base,
            LARGEST_SPLIT))
        canonical = base.canonical_step(canonical, dt)
    return {
        "index": spec.index,
        "name": spec.name,
        "role": spec.role,
        "declared": {
            "load_transfer": spec.load_c,
            "delta": LARGEST_SPLIT,
            "baseline": spec.baseline,
            "schedule_key": spec.schedule_key,
            "plan": [list(pair) for pair in spec.plan],
        },
        "load": comparison,
        "schedule": {
            "dt": dt,
            "horizon": horizon,
            "steps": steps,
            "lambda_max": lambda_max,
            "rule_conformant": conformant,
            "samples": [index for _, index in SAMPLES if index <= steps],
        },
        "rho": {"max": float(np.max(rho)), "final": float(rho[-1]),
                "peak_time": float(int(np.argmax(rho)) * dt),
                "release_window": [float(value) for value in
                                   rho[RELEASE_SAMPLE[0]:RELEASE_SAMPLE[-1] + 1]]},
        "structure": {
            "min_state": float(np.min(minima)),
            "min_projection": float(np.min(projections)),
            "q_min": float(np.min(low)),
            "q_max": float(np.max(high)),
            "annihilation_max": float(np.max(annihilation)),
            "idempotence_max": float(np.max(idempotence)),
        },
        "ray_distance": prior.ray_distance_of(base.projection(state), base),
        "ray_distance_at": ray_distances,
        "coordinate": {
            "initial": float(series[0]),
            "final": float(series[-1]),
            "at_reads": {key: float(series[index]) for key, index in
                         (("t1", T1_INDEX), ("t2", T2_INDEX), ("t3", T3_INDEX))
                         if index <= steps},
            "at_release_samples": ([float(series[index]) for index in RELEASE_SAMPLE]
                                   if steps >= RELEASE_SAMPLE[-1] else None),
        },
        "profiles": {key: [block.tolist() for block in value]
                     for key, value in sorted(profiles.items())},
        "steps_recorded": int(steps + 1),
    }


def displacement_of(arms: dict, name: str, key: str):
    """The arm's group displacement against its own declared baseline, at one read time.

    A baseline arm is its own reference, so its displacement is the declared exact zero;
    an arm whose schedule stops before a read time has no reading there.
    """
    baseline = arms[name]["declared"]["baseline"]
    own = arms[name]["profiles"].get(key)
    if own is None:
        return None
    if baseline == "itself":
        reference = own
    else:
        reference = arms[baseline]["profiles"].get(key)
        if reference is None:
            return None
    return tuple(np.asarray(own[position]) - np.asarray(reference[position])
                 for position in range(2))


def displacement_record(arms: dict, name: str) -> dict:
    """Every declared displacement reading of one arm: both groups at the three read times,
    the release window's norms, and the two established fits per group."""
    record = {"baseline": arms[name]["declared"]["baseline"], "groups": {}, "release": None,
              "fits": None}
    for key in READ_KEYS:
        difference = displacement_of(arms, name, key)
        if difference is None:
            continue
        even, odd = difference
        record["groups"][key] = {
            "even": even.tolist(),
            "odd": odd.tolist(),
            "even_norm": vector_norm(even),
            "odd_norm": vector_norm(odd),
            "norm": vector_norm(np.concatenate([even, odd])),
        }
    if arms[name]["coordinate"]["at_release_samples"] is None:
        return record
    record["release"] = {"horizons": list(HORIZONS), "even_norms": [], "odd_norms": []}
    for key in ("r{0}".format(position + 1) for position in range(len(HORIZONS))):
        difference = displacement_of(arms, name, key)
        if difference is None:
            return record
        record["release"]["even_norms"].append(vector_norm(difference[0]))
        record["release"]["odd_norms"].append(vector_norm(difference[1]))
    record["fits"] = {}
    for group, series in (("even", record["release"]["even_norms"]),
                          ("odd", record["release"]["odd_norms"])):
        record["fits"][group] = group_fit(series)
    return record


def group_fit(values) -> dict:
    """Section 4.2: the two established fits on one group's release-window norms."""
    held = prior.fit_held(values)
    free = prior.fit_free(values)
    peak = float(np.max(values))
    terminal = float(values[-1])
    share_held = (abs(held["offset"]) / abs(terminal) if terminal != 0.0 else None)
    share_free = (abs(free["offset"]) / abs(terminal) if terminal != 0.0 else None)
    ratio = free["rate"] / NU_REFERENCE
    if peak <= SILENCE_LEVEL:
        label = "SILENT"
        reason = "the peak reading is at or below the declared silence level"
    elif (share_held is not None and share_held >= RETENTION_SHARE
          and held["residual"] <= RESIDUAL_BAND):
        label = "RETAINED"
        reason = "the held fit leaves at least {0} of the terminal reading".format(
            RETENTION_SHARE)
    elif (share_free is not None and share_free <= RELEASE_SHARE
          and free["residual"] <= RESIDUAL_BAND
          and 1.0 / CLOCK_TOLERANCE <= ratio <= CLOCK_TOLERANCE):
        label = "DECAYED"
        reason = ("the free fit leaves no offset and decays at {0} times the declared "
                  "clock".format(round(ratio, 4)))
    else:
        label = "UNRESOLVED"
        reason = ("the held share is {0}, the free share {1}, the rate ratio {2} and the "
                  "residuals {3} and {4}".format(
                      _rounded(share_held), _rounded(share_free), round(ratio, 4),
                      round(held["residual"], 4), round(free["residual"], 4)))
    return {"label": label, "reason": reason, "peak": peak, "terminal": terminal,
            "share_held": share_held, "share_free": share_free, "rate_ratio": ratio,
            "held": held, "free": free}


def _rounded(value):
    return None if value is None else round(value, 4)


def matches(first: tuple, second: tuple, band: float = ADDITIVE_BAND) -> dict:
    """Section 4.2: two displacements are the same when their magnitudes agree within the
    declared band and their directions agree within the same band."""
    left = np.concatenate([np.asarray(first[0]), np.asarray(first[1])])
    right = np.concatenate([np.asarray(second[0]), np.asarray(second[1])])
    norm_left, norm_right = vector_norm(left), vector_norm(right)
    scale = max(norm_left, norm_right)
    gap = (abs(norm_left - norm_right) / scale) if scale > 0.0 else 1.0
    cosine = cosine_of(left, right)
    return {"norm_first": norm_left, "norm_second": norm_right, "relative_gap": gap,
            "cosine": cosine, "bound": band,
            "passed": bool(scale > 0.0 and gap <= band and cosine is not None
                           and cosine >= 1.0 - band)}


def decide(arms: dict, displacements: dict, preflight: dict) -> dict:
    """Section 4.3: the coexistence and erasure verdicts, and the reported composition."""
    def groups(name, key):
        return tuple(np.asarray(block) for block in (displacements[name]["groups"][key]["even"],
                                                     displacements[name]["groups"][key]["odd"]))

    single = {label: displacements[name]["groups"] for label, name in
              (("A", "write_A"), ("B", "write_B"))}
    joint = displacements["joint_AB"]["groups"]
    erase = displacements["erase_A"]["groups"]
    retained_A = single["A"]["t3"]["even_norm"] >= READABLE_LEVEL
    retained_B = single["B"]["t3"]["odd_norm"] >= READABLE_LEVEL
    cross_A = single["A"]["t3"]["odd_norm"]
    cross_B = single["B"]["t3"]["even_norm"]
    additive = {"even": matches(groups("joint_AB", "t3"), groups("write_A", "t3")),
                "odd": matches(groups("joint_AB", "t3"), groups("write_B", "t3"))}
    joint_readable = (joint["t3"]["even_norm"] >= READABLE_LEVEL
                      and joint["t3"]["odd_norm"] >= READABLE_LEVEL)
    if not preflight["passed"]:
        coexistence = "RESERVED_NOT_DISTINGUISHABLE"
    elif not (retained_A and retained_B):
        coexistence = "RESERVED_ONE_RETAINED"
    elif additive["even"]["passed"] and additive["odd"]["passed"]:
        coexistence = "COEXIST_ADDITIVE"
    elif not joint_readable:
        coexistence = "INTERFERE"
    else:
        coexistence = "COEXIST_NONADDITIVE"
    b_readable = single["B"]["t2"]["odd_norm"] >= READABLE_LEVEL
    erased = matches(groups("erase_A", "t2"), groups("write_B", "t2"))
    residual = matches(groups("erase_A", "t2"), groups("joint_AB", "t2"))
    if not b_readable:
        erasure = "RESERVED_NO_B"
    elif erased["passed"] and not residual["passed"]:
        erasure = "ERASES_ONE"
    elif residual["passed"]:
        erasure = "RESIDUAL"
    else:
        erasure = "MOVES_BOTH"
    reference_scalar = arms["load_reference"]["coordinate"]["at_reads"]["t3"]
    scalar = {
        "reference": reference_scalar,
        "write_A": arms["write_A"]["coordinate"]["at_reads"]["t3"],
        "write_B": arms["write_B"]["coordinate"]["at_reads"]["t3"],
        "joint_AB": arms["joint_AB"]["coordinate"]["at_reads"]["t3"],
        "erase_A": arms["erase_A"]["coordinate"]["at_reads"]["t3"],
        "sum_of_singles": (arms["write_A"]["coordinate"]["at_reads"]["t3"]
                           + arms["write_B"]["coordinate"]["at_reads"]["t3"]
                           - reference_scalar),
    }
    return {
        "coexistence": coexistence,
        "erasure": erasure,
        "retained": {"A": retained_A, "B": retained_B,
                     "A_even_t3": single["A"]["t3"]["even_norm"],
                     "B_odd_t3": single["B"]["t3"]["odd_norm"]},
        "cross_at_t3": {"A_on_odd": cross_A, "B_on_even": cross_B},
        "additive": additive,
        "erase_match": {"against_B": erased, "against_joint": residual},
        "joint_readable": bool(joint_readable),
        "scalar": scalar,
    }


def gate_rows(arms: dict, displacements: dict, decision: dict, preflight: dict,
              comparison_ok: bool, budget: dict, clock: dict, clock_read: dict,
              replication: dict, probe_check: dict) -> list:
    """Section 4.1: every gate with its reading, its bound and its verdict. The
    branch-selecting readings of section 4.2 are not gates."""
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
    baseline_zero = all(
        all(value["norm"] == 0.0 for value in displacements[name]["groups"].values())
        for name in BASELINE_NAMES)
    ray_readings = [abs(value) for key in READ_KEYS
                    for value in (displacements["ray_write"]["groups"][key]["even_norm"],
                                  displacements["ray_write"]["groups"][key]["odd_norm"])]
    ray_silence = max(ray_readings)
    anchor = {name: arms[name]["ray_distance_at"]["t1"] for name in LOADED_ARMS}
    can_fail = displacements["write_A"]["groups"]["t1"]["even_norm"]
    clock_ok = bool(clock["passed"] and clock_read["equal_to_declared"])
    short_ok = bool(arms["step_short"]["rho"]["max"] == ORACLE_RAY_RHO)
    rows = [
        {"id": 1, "name": "binding", "reading": "sixteen rows declared against observed, "
         "all exact, and the successor's own rows agree", "bound": "exact", "passed": True},
        {"id": 2, "name": "structure", "reading": "minimum state and projection, the "
         "composition bounds, and the annihilation and idempotence maxima over every "
         "recorded state", "bound": "nonnegative states, 0 <= q < 1",
         "passed": bool(structural)},
        {"id": 3, "name": "loads and shape", "reading": {
            "declared_executions": budget["executions"],
            "steps_total": budget["steps_total"], "steps_max": budget["steps_max"],
            "loads": {name: arms[name]["load"]["measured"] for name in LOADED_ARMS}},
         "bound": "every declared load within {0} relative ({1} absolute at zero), {2} "
                  "executions, {3} per execution, {4} total".format(
                      LOAD_TOL, LOAD_ABS_FLOOR, DECLARED_EXECUTIONS, PER_EXECUTION_CAP,
                      TOTAL_STEP_CAP),
         "passed": bool(comparison_ok and shape_ok)},
        {"id": 4, "name": "schedule conformance", "reading": "dt against the rule on every "
         "arm's own loaded projection", "bound": "dt <= 1/(40 lambda_max), declared set",
         "passed": bool(conformant)},
        {"id": 5, "name": "replication of the established constructions",
         "reading": replication, "bound": "the three scalars and the two ray distances "
         "within {0} of the successor receipt's values".format(REPLICATION_TOL),
         "passed": bool(replication["passed"])},
        {"id": 6, "name": "design probe reproduction", "reading": probe_check,
         "bound": "every declared probe reading within {0} relative".format(PROBE_TOL),
         "passed": bool(probe_check["passed"])},
        {"id": 7, "name": "baselines hold the zero displacement",
         "reading": {name: displacements[name]["groups"]["t3"]["norm"]
                     for name in BASELINE_NAMES},
         "bound": "exactly zero: the baseline is its own reference", "passed":
         bool(baseline_zero)},
        {"id": 8, "name": "silence on the ray pair",
         "reading": {"ray_write_at_load": ray_silence,
                     "displacement": {key: displacements["ray_write"]["groups"][key]["norm"]
                                      for key in READ_KEYS}},
         "bound": "<= {0} at every read time; the ray's bracket vanishes identically".format(
             SILENCE_LEVEL),
         "passed": bool(ray_silence <= SILENCE_LEVEL)},
        {"id": 9, "name": "anchor readable on every arm charged an offset",
         "reading": anchor, "bound": ">= {0} at the first read time".format(
             RAY_READABLE_FLOOR),
         "passed": bool(all(value is not None and value >= RAY_READABLE_FLOOR
                            for value in anchor.values()))},
        {"id": 10, "name": "can-fail at the largest declared magnitude",
         "reading": {"write_A_even_t1": can_fail, "write_A_odd_t1":
                     displacements["write_A"]["groups"]["t1"]["odd_norm"]},
         "bound": ">= {0} on the direction's own group".format(READABLE_LEVEL),
         "passed": bool(can_fail >= READABLE_LEVEL)},
        {"id": 11, "name": "the null moves neither coordinate",
         "reading": preflight["readings"]["null"], "bound": "exactly {0}".format(NULL_CEIL),
         "passed": bool(preflight["checks"]["null_zero"])},
        {"id": 12, "name": "the declared clock, read from the successor receipt",
         "reading": {"fitted": clock["rate"], "reference": clock["reference"],
                     "ratio": clock["ratio"], "window": clock["window"],
                     "receipt_read": clock_read["read"]},
         "bound": "factor {0} of the declared rate, read live from the receipt".format(
             NU_TOLERANCE), "passed": clock_ok},
        {"id": 13, "name": "cross-protocol oracle on the short arm",
         "reading": arms["step_short"]["rho"]["max"],
         "bound": "bit-identical to the successor's own short-horizon residual {0}".format(
             ORACLE_RAY_RHO), "passed": short_ok},
        {"id": 14, "name": "single invocation", "reading": "receipt absent at start, one "
         "process, pid recorded", "bound": "structural", "passed": True},
    ]
    return rows


def features_of(gates: list, decision: dict, preflight: dict) -> dict:
    """Section 4.2: every branch-selecting reading, reported and deliberately outside the
    status conjunction. A reserved branch is a finding, not a failure."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    return {
        "F1_can_fail_fired": passed[10],
        "F2_ray_silent": passed[8],
        "F3_anchor_readable": passed[9],
        "F4_preflight_live_A": bool(preflight["checks"]["live_A"]),
        "F5_preflight_live_B": bool(preflight["checks"]["live_B"]),
        "F6_preflight_cross_A": bool(preflight["checks"]["cross_A"]),
        "F7_preflight_cross_B": bool(preflight["checks"]["cross_B"]),
        "F8_preflight_distinct": bool(preflight["checks"]["distinct"]),
        "F9_retained_A": bool(decision["retained"]["A"]),
        "F10_retained_B": bool(decision["retained"]["B"]),
        "F11_joint_readable": bool(decision["joint_readable"]),
        "F12_additive_even": bool(decision["additive"]["even"]["passed"]),
        "F13_additive_odd": bool(decision["additive"]["odd"]["passed"]),
        "F14_erase_matches_B": bool(decision["erase_match"]["against_B"]["passed"]),
        "F15_erase_matches_joint": bool(decision["erase_match"]["against_joint"]["passed"]),
        "coexistence": decision["coexistence"],
        "erasure": decision["erasure"],
    }


def status_of(gates: list, features: dict) -> str:
    """The status conjunction reads the gates only: the branch-selecting features of section
    4.2 select a branch, and a reserved branch is a recorded finding."""
    every_gate = all(row["passed"] for row in gates)
    return "PASS" if every_gate else "FAIL"


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
                        ("prior_body", PRIOR_EXECUTOR), ("prior_executor", PRIOR_EXECUTOR),
                        ("bound_module", BOUND_MODULE), ("base_probe", BASE_PROBE),
                        ("split_executor", SPLIT_EXECUTOR),
                        ("gate_load_executor", GATE_LOAD_EXECUTOR),
                        ("base_receipt", BASE_RECEIPT), ("split_receipt", SPLIT_RECEIPT),
                        ("gate_load_protocol", GATE_LOAD_PROTOCOL),
                        ("gate_load_receipt", GATE_LOAD_RECEIPT),
                        ("prior_receipt", PRIOR_RECEIPT),
                        ("successor_protocol", SUCCESSOR_PROTOCOL),
                        ("successor_executor", SUCCESSOR_EXECUTOR),
                        ("successor_receipt", SUCCESSOR_RECEIPT)):
        if key == "protocol":
            observed[key] = protocol_body_digest()
        elif key == "prior_body":
            observed[key] = prior.protocol_body_digest()
        elif key == "gate_load_protocol":
            observed[key] = gate_load.protocol_body_digest()
        elif key == "successor_protocol":
            observed[key] = successor.protocol_body_digest()
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
        "executed_probe_sha256": sources.get("probe", {}).get("sha256"),
    }


def read_clock() -> dict:
    return prior.read_clock()


def successor_oracle() -> dict:
    """Section 1.5: the successor receipt's own readings this protocol replicates."""
    receipt = load_json(SUCCESSOR_RECEIPT)
    arms = receipt["arms"]
    return {
        "coordinate": {
            "loadmax_anchor_at_horizons": list(
                arms["loadmax_anchor"]["coordinate"]["at_horizons"]),
            "supersplit_load_final": float(
                arms["supersplit_load"]["coordinate"]["final"]),
            "ray_supersplit_final": float(arms["ray_supersplit"]["coordinate"]["final"]),
        },
        "ray_distance": {
            "supersplit_load_final": float(arms["supersplit_load"]["ray_distance"]),
            "ray_supersplit_final": float(arms["ray_supersplit"]["ray_distance"]),
        },
        "action": receipt["action"],
        "short_rho": float(arms["ray_short"]["rho"]["max"]),
    }


def replication_of(arms: dict, oracle: dict) -> dict:
    """Section 4.1 gate 5: my own constructions against the successor's recorded readings."""
    measured = {
        "load_reference_at_t1": arms["load_reference"]["coordinate"]["at_reads"]["t1"],
        "write_A_at_t1": arms["write_A"]["coordinate"]["at_reads"]["t1"],
        "ray_write_at_t1": arms["ray_write"]["coordinate"]["at_reads"]["t1"],
        "write_A_ray_distance": arms["write_A"]["ray_distance_at"]["t1"],
        "ray_write_ray_distance": arms["ray_write"]["ray_distance_at"]["t1"],
    }
    declared = {
        "load_reference_at_t1": REPLICATION_LOAD_REFERENCE_AT_T1,
        "write_A_at_t1": REPLICATION_WRITE_A_AT_T1,
        "ray_write_at_t1": REPLICATION_RAY_WRITE_AT_T1,
        "write_A_ray_distance": REPLICATION_WRITE_A_RAY_DISTANCE,
        "ray_write_ray_distance": REPLICATION_RAY_WRITE_RAY_DISTANCE,
    }
    mismatches = [key for key in sorted(declared)
                  if abs(measured[key] - declared[key]) > REPLICATION_TOL]
    receiver = {
        "loadmax_anchor_at_horizons_last":
            oracle["coordinate"]["loadmax_anchor_at_horizons"][-1],
        "supersplit_load_final": oracle["coordinate"]["supersplit_load_final"],
        "ray_supersplit_final": oracle["coordinate"]["ray_supersplit_final"],
        "supersplit_load_ray_distance": oracle["ray_distance"]["supersplit_load_final"],
        "ray_supersplit_ray_distance": oracle["ray_distance"]["ray_supersplit_final"],
    }
    return {"measured": measured, "declared": declared, "receipt": receiver,
            "mismatches": mismatches, "passed": not mismatches}


def probe_replication(displacements: dict) -> dict:
    """Gate 6: the run reproduces the design probe's declared group readings."""
    observed = {}
    for label in PROBE_READING_ORDER:
        name, group, key = label.split(":")
        observed[label] = displacements[name]["groups"][key]["{0}_norm".format(group)]
    if not PROBE_READINGS:
        return {"checked": [], "mismatches": [], "passed": True,
                "note": "the protocol declares no probe readings"}
    declared = dict(zip(PROBE_READING_ORDER, PROBE_READINGS))
    mismatches = []
    for label in PROBE_READING_ORDER:
        reference = declared[label]
        scale = max(abs(reference), 1e-300)
        if abs(observed[label] - reference) > PROBE_TOL * scale:
            mismatches.append("{0}: run {1}, probe {2}".format(label, observed[label],
                                                               reference))
    return {"checked": list(PROBE_READING_ORDER), "observed": observed,
            "declared": declared, "mismatches": mismatches, "passed": not mismatches}


def build():
    """Run every declared arm once, in order, and return the readings both verdicts read."""
    base = load_modules()
    preflight = action_preflight(base)
    preflight["passed"] = bool(all(preflight["checks"].values()))
    arms = {}
    for spec in ARM_TABLE:
        reading = arm_record(spec, base)
        arms[spec.name] = reading
        print("{0:<16} {1:<9} steps {2:>6} q_max {3:.9f} ray {4:.6e}".format(
            spec.name, reading["role"], reading["schedule"]["steps"],
            reading["structure"]["q_max"], reading["ray_distance"]))
    return {"base": base, "arms": arms, "preflight": preflight}


def finish(built) -> dict:
    """The displacements, the clock, the decision, the gates and the status."""
    arms = built["arms"]
    displacements = {name: displacement_record(arms, name) for name in arms}
    clock = prior.clock_of(arms["load_reference"]["rho"]["release_window"], DECLARED_DT, 0,
                           len(RELEASE_SAMPLE) - 1)
    clock["window"] = [float(RELEASE_SAMPLE[0] * DECLARED_DT),
                       float(RELEASE_SAMPLE[-1] * DECLARED_DT)]
    decision = decide(arms, displacements, built["preflight"])
    oracle = successor_oracle()
    replication = replication_of(arms, oracle)
    probe_check = probe_replication(displacements)
    comparison_ok = all(arm["load"]["passed"] for arm in arms.values())
    budget = {
        "executions": len(arms),
        "steps_total": int(sum(arm["schedule"]["steps"] for arm in arms.values())),
        "steps_max": int(max(arm["schedule"]["steps"] for arm in arms.values())),
        "per_execution_cap": PER_EXECUTION_CAP,
        "total_cap": TOTAL_STEP_CAP,
        "declared_executions": DECLARED_EXECUTIONS,
        "projected_seconds_measured": PROJECTED_SECONDS_MEASURED,
        "projected_seconds_assumed": PROJECTED_SECONDS_ASSUMED,
        "seconds_per_step_measured": SECONDS_PER_STEP_MEASURED,
        "seconds_per_step_assumed": SECONDS_PER_STEP_ASSUMED,
    }
    gates = gate_rows(arms, displacements, decision, built["preflight"], comparison_ok,
                      budget, clock, read_clock(), replication, probe_check)
    features = features_of(gates, decision, built["preflight"])
    status = status_of(gates, features)
    return {"displacements": displacements, "clock": clock, "decision": decision,
            "replication": replication, "probe_check": probe_check, "budget": budget,
            "gates": gates, "features": features, "status": status,
            "oracle": oracle, "comparison_ok": comparison_ok}


def execute() -> int:
    started = time.time()
    binding = check_binding()
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        print("REFUSING TO RUN: {0} already exists; the stopping rule allows no second "
              "invocation on a recorded result".format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    clock_read = read_clock()
    if not clock_read["equal_to_declared"]:
        print("REFUSING TO RUN: the successor receipt holds {0} for the relaxation rate "
              "where this protocol declares {1}".format(clock_read["read"],
                                                        clock_read["declared"]))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    oracle = successor_oracle()
    for key, declared_value in (("short_rho", ORACLE_RAY_RHO),
                                ("action_live", ORACLE_SCALAR_ACTION_LIVE),
                                ("action_silent", ORACLE_SCALAR_ACTION_SILENT),
                                ("action_drift", ORACLE_SCALAR_ACTION_DRIFT)):
        observed = {"short_rho": oracle["short_rho"],
                    "action_live": oracle["action"]["live"]["relative"],
                    "action_silent": oracle["action"]["silent"]["relative"],
                    "action_drift": oracle["action"]["live"]["drift"]}[key]
        if abs(observed - declared_value) > REPLICATION_TOL:
            print("REFUSING TO RUN: the successor receipt holds {0} for {1} where this "
                  "protocol declares {2}".format(observed, key, declared_value))
            raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    built = build()
    result = finish(built)
    arms = built["arms"]
    decision = result["decision"]
    passed = result["status"] == "PASS"
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": result["status"],
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
            "prior_body": {"path": PRIOR_EXECUTOR,
                           "sha256": binding["observed"]["prior_body_sha256"]},
            "prior_executor": {"path": PRIOR_EXECUTOR,
                               "sha256": binding["observed"]["prior_executor_sha256"]},
            "bound_module": {"path": BOUND_MODULE,
                             "sha256": binding["observed"]["bound_module_sha256"]},
            "base_probe": {"path": BASE_PROBE,
                           "sha256": binding["observed"]["base_probe_sha256"]},
            "split_executor": {"path": SPLIT_EXECUTOR,
                               "sha256": binding["observed"]["split_executor_sha256"]},
            "gate_load_executor": {"path": GATE_LOAD_EXECUTOR,
                                   "sha256": binding["observed"][
                                       "gate_load_executor_sha256"]},
            "base_receipt": {"path": BASE_RECEIPT,
                             "sha256": binding["observed"]["base_receipt_sha256"]},
            "split_receipt": {"path": SPLIT_RECEIPT,
                              "sha256": binding["observed"]["split_receipt_sha256"]},
            "gate_load_protocol": {"path": GATE_LOAD_PROTOCOL,
                                   "sha256": binding["observed"][
                                       "gate_load_protocol_body_sha256"]},
            "gate_load_receipt": {"path": GATE_LOAD_RECEIPT,
                                  "sha256": binding["observed"][
                                      "gate_load_receipt_sha256"]},
            "prior_receipt": {"path": PRIOR_RECEIPT,
                              "sha256": binding["observed"]["prior_receipt_sha256"]},
            "successor_protocol": {"path": SUCCESSOR_PROTOCOL,
                                   "sha256": binding["observed"][
                                       "successor_protocol_body_sha256"]},
            "successor_executor": {"path": SUCCESSOR_EXECUTOR,
                                   "sha256": binding["observed"][
                                       "successor_executor_sha256"]},
            "successor_receipt": {"path": SUCCESSOR_RECEIPT,
                                  "sha256": binding["observed"][
                                      "successor_receipt_sha256"]},
        },
        "binding": binding,
        "thresholds": {
            "readable_floor_q": READABLE_FLOOR_Q,
            "silence_floor_q": SILENCE_FLOOR_Q,
            "readable_level": READABLE_LEVEL,
            "silence_level": SILENCE_LEVEL,
            "cross_ceiling": CROSS_CEIL,
            "distinctness_ceiling": DISTINCTNESS_CEIL,
            "null_ceiling": NULL_CEIL,
            "ray_readable_floor": RAY_READABLE_FLOOR,
            "retention_share": RETENTION_SHARE,
            "release_share": RELEASE_SHARE,
            "additive_band": ADDITIVE_BAND,
            "residual_band": RESIDUAL_BAND,
            "clock_tolerance": CLOCK_TOLERANCE,
            "nu_reference": NU_REFERENCE,
            "nu_tolerance": NU_TOLERANCE,
            "action_floor_live": ACTION_FLOOR_LIVE,
            "action_ceiling_silent": ACTION_CEIL_SILENT,
            "anchor_ray_tolerance": ANCHOR_RAY_TOL,
            "load_tolerance": LOAD_TOL,
            "load_absolute_floor": LOAD_ABS_FLOOR,
            "step_safety": STEP_SAFETY,
            "step_candidates": list(STEP_CANDIDATES),
            "declared_dt": DECLARED_DT,
            "phase_units": PHASE_UNITS,
            "phase_steps": PHASE_STEPS,
            "horizons": list(HORIZONS),
            "release_sample": list(RELEASE_SAMPLE),
            "replication_tolerance": REPLICATION_TOL,
            "probe_tolerance": PROBE_TOL,
            "replication_load_reference_at_t1": REPLICATION_LOAD_REFERENCE_AT_T1,
            "replication_write_a_at_t1": REPLICATION_WRITE_A_AT_T1,
            "replication_ray_write_at_t1": REPLICATION_RAY_WRITE_AT_T1,
            "replication_write_a_ray_distance": REPLICATION_WRITE_A_RAY_DISTANCE,
            "replication_ray_write_ray_distance": REPLICATION_RAY_WRITE_RAY_DISTANCE,
            "oracle_scalar_action_live": ORACLE_SCALAR_ACTION_LIVE,
            "oracle_scalar_action_silent": ORACLE_SCALAR_ACTION_SILENT,
            "oracle_scalar_action_drift": ORACLE_SCALAR_ACTION_DRIFT,
            "oracle_ray_rho": ORACLE_RAY_RHO,
        },
        "arm_table": [
            {"index": arm.index, "name": arm.name, "role": arm.role,
             "load_transfer": arm.load_c, "delta": LARGEST_SPLIT,
             "baseline": arm.baseline, "schedule_key": arm.schedule_key,
             "plan": [list(pair) for pair in arm.plan],
             "schedule": list(arm.declared_schedule())}
            for arm in ARM_TABLE
        ],
        "arms": arms,
        "displacements": result["displacements"],
        "preflight": built["preflight"],
        "clock": {"measured": result["clock"], "declared": read_clock()},
        "replication": result["replication"],
        "probe_check": result["probe_check"],
        "decision": decision,
        "gates": result["gates"],
        "features": result["features"],
        "budget": result["budget"],
        "verdicts": {
            "coexistence": decision["coexistence"] if passed else None,
            "erasure": decision["erasure"] if passed else None,
            "composition_reported_not_gated": decision["scalar"],
        },
        "runtime_seconds": time.time() - started,
    }
    receipt["invocation"]["runtime_seconds"] = receipt["runtime_seconds"]
    path = os.path.join(ROOT, RECEIPT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(sanitize(receipt), handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(result["status"])
    print("coexistence: {0}".format(receipt["verdicts"]["coexistence"]))
    print("erasure: {0}".format(receipt["verdicts"]["erasure"]))
    print("runtime_seconds: {0}".format(receipt["runtime_seconds"]))
    return EXIT_PASS if passed else EXIT_FAIL


def sanitize(value):
    """Strip numpy scalars and refuse a non-finite number before the receipt is written."""
    if isinstance(value, dict):
        return {key: sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, np.ndarray):
        return sanitize(value.tolist())
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
    """Static, derivation and pre-flight checks. Writes nothing; safe to run again."""
    problems = []
    print("self-check: binding")
    check_binding()
    print("self-check: protocol rows against this executor's constants")
    rows = (
        ("readable_level", READABLE_LEVEL), ("silence_level", SILENCE_LEVEL),
        ("cross_ceiling", CROSS_CEIL), ("distinctness_ceiling", DISTINCTNESS_CEIL),
        ("null_ceiling", NULL_CEIL), ("ray_readable_floor", RAY_READABLE_FLOOR),
        ("retention_share", RETENTION_SHARE), ("release_share", RELEASE_SHARE),
        ("additive_band", ADDITIVE_BAND), ("residual_band", RESIDUAL_BAND),
        ("clock_tolerance", CLOCK_TOLERANCE), ("nu_reference", NU_REFERENCE),
        ("nu_tolerance", NU_TOLERANCE), ("action_floor_live", ACTION_FLOOR_LIVE),
        ("action_ceiling_silent", ACTION_CEIL_SILENT), ("load_tolerance", LOAD_TOL),
        ("load_absolute_floor", LOAD_ABS_FLOOR), ("step_safety", STEP_SAFETY),
        ("declared_dt", DECLARED_DT), ("bound_seconds", BOUND_SECONDS),
        ("phase_units", PHASE_UNITS), ("phase_steps", float(PHASE_STEPS)),
        ("total_units", TOTAL_UNITS), ("total_steps", float(TOTAL_STEPS)),
        ("declared_executions", float(DECLARED_EXECUTIONS)),
        ("per_execution_cap", float(PER_EXECUTION_CAP)),
        ("total_step_cap", float(TOTAL_STEP_CAP)),
        ("replication_tolerance", REPLICATION_TOL), ("probe_tolerance", PROBE_TOL),
        ("replication_load_reference_at_t1", REPLICATION_LOAD_REFERENCE_AT_T1),
        ("replication_write_a_at_t1", REPLICATION_WRITE_A_AT_T1),
        ("replication_ray_write_at_t1", REPLICATION_RAY_WRITE_AT_T1),
        ("replication_write_a_ray_distance", REPLICATION_WRITE_A_RAY_DISTANCE),
        ("replication_ray_write_ray_distance", REPLICATION_RAY_WRITE_RAY_DISTANCE),
        ("oracle_scalar_action_live", ORACLE_SCALAR_ACTION_LIVE),
        ("oracle_scalar_action_silent", ORACLE_SCALAR_ACTION_SILENT),
        ("oracle_scalar_action_drift", ORACLE_SCALAR_ACTION_DRIFT),
        ("oracle_ray_rho", ORACLE_RAY_RHO),
        ("projected_seconds_measured", PROJECTED_SECONDS_MEASURED),
        ("projected_seconds_assumed", PROJECTED_SECONDS_ASSUMED),
        ("seconds_per_step_measured", SECONDS_PER_STEP_MEASURED),
        ("seconds_per_step_assumed", SECONDS_PER_STEP_ASSUMED),
    )
    for key, value in rows:
        declared = declared_number(key)
        if declared != value:
            problems.append("the protocol declares {0} = {1}, this executor holds {2}".format(
                key, declared, value))
    if declared_literal_tuple("horizons") != tuple(HORIZONS):
        problems.append("the protocol's horizons are not the executor's")
    if declared_literal_tuple("release_sample") != tuple(float(value)
                                                         for value in RELEASE_SAMPLE):
        problems.append("the protocol's release sample is not the executor's")
    if PROBE_READINGS and declared_literal_tuple("probe_readings") != tuple(PROBE_READINGS):
        problems.append("the protocol's probe readings are not the executor's")
    print("self-check: the imported chain's own thresholds and the horizon arithmetic")
    if prior.READABLE_FLOOR_Q != READABLE_FLOOR_Q:
        problems.append("the imported fits filter readings above the declared floor")
    if prior.NU_REFERENCE != NU_REFERENCE:
        problems.append("the imported fits hold a different rate")
    if ADDITIVE_BAND != prior.RESIDUAL_BAND:
        problems.append("the matching band is not the spent residual band")
    if tuple(prior.STEP_CANDIDATES) != tuple(STEP_CANDIDATES):
        problems.append("the step candidates differ from the spent set")
    span = float(NU_REFERENCE * (HORIZONS[-1] - HORIZONS[0]))
    if span < MIN_SPAN:
        problems.append("the release window spans {0} relaxation times".format(span))
    if float(np.exp(-NU_REFERENCE * HORIZONS[-1])) > TAIL_FRACTION:
        problems.append("the release window's tail is above the declared fraction")
    if PHASE_UNITS < 5.0 / NU_REFERENCE:
        problems.append("the phase is shorter than the declared five relaxation times")
    print("self-check: the declared schedules and the sample arithmetic")
    if RELEASE_SAMPLE[0] != T2_INDEX + int(round(HORIZONS[0] / DECLARED_DT)):
        problems.append("the release sample is not offset by the second write phase")
    if [value * DECLARED_DT for value in
            [index - T2_INDEX for index in RELEASE_SAMPLE]] != list(HORIZONS):
        problems.append("the release sample times are not the declared horizons")
    if T3_INDEX != RELEASE_SAMPLE[-1]:
        problems.append("the third read time is not the last release sample")
    if PHASE_STEPS * DECLARED_DT != PHASE_UNITS:
        problems.append("the phase steps and units disagree")
    print("self-check: the declared arm table")
    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        problems.append("{0} arms in the table against {1} declared".format(
            len(ARM_TABLE), DECLARED_EXECUTIONS))
    if [arm.index for arm in ARM_TABLE] != list(range(1, DECLARED_EXECUTIONS + 1)):
        problems.append("the arm indices are not 1..{0}".format(DECLARED_EXECUTIONS))
    if len({arm.name for arm in ARM_TABLE}) != len(ARM_TABLE):
        problems.append("the arm names are not unique")
    total = sum(arm.declared_schedule()[2] for arm in ARM_TABLE)
    if total > TOTAL_STEP_CAP:
        problems.append("the declared schedule totals {0} steps against the cap {1}".format(
            total, TOTAL_STEP_CAP))
    if max(arm.declared_schedule()[2] for arm in ARM_TABLE) > PER_EXECUTION_CAP:
        problems.append("an arm exceeds the per-execution cap")
    names = {arm.name for arm in ARM_TABLE}
    for arm in ARM_TABLE:
        if arm.baseline not in names and arm.baseline != "itself":
            problems.append("{0}'s baseline {1} is not in the table".format(
                arm.name, arm.baseline))
        if arm.baseline == "itself" and arm.name not in BASELINE_NAMES and arm.role != "oracle":
            problems.append("{0} is its own baseline but is not a declared baseline".format(
                arm.name))
        if arm.role == "oracle":
            # The oracle arm exists for its residual reading against the successor receipt;
            # it must not quietly consume a displacement baseline. Its schedule stops before
            # every read time, so it declares no group reading at all.
            if arm.baseline != "itself":
                problems.append("{0} is the oracle arm but is not its own baseline".format(
                    arm.name))
            if any(0 < index <= arm.declared_schedule()[2] for _, index in SAMPLES):
                problems.append("{0} is the oracle arm but reaches a declared read "
                                "time".format(arm.name))
        if arm.name in LOADED_ARMS:
            if arm.load_c != LARGEST_LOAD:
                problems.append("{0} is a loaded arm without the largest load".format(
                    arm.name))
        elif arm.load_c != 0.0:
            problems.append("{0} is not a loaded arm but carries a load".format(arm.name))
    for arm in ARM_TABLE:
        if arm.name in ("write_A", "write_B", "joint_AB", "erase_A") \
                and arm.baseline != "load_reference":
            problems.append("{0} does not read against the loaded reference".format(arm.name))
    if [arm for arm in ARM_TABLE if arm.name == "ray_write"][0].baseline != "ray_anchor":
        problems.append("the ray write does not read against the ray anchor")
    for arm in ARM_TABLE:
        if arm.schedule_key == "phases" and len(arm.plan) != 3:
            problems.append("{0} does not carry a three-phase plan".format(arm.name))
    print("self-check: the phase arithmetic of the erase arm")
    erase = [arm for arm in ARM_TABLE if arm.name == "erase_A"][0]
    joint = [arm for arm in ARM_TABLE if arm.name == "joint_AB"][0]
    for position, (left, right) in enumerate(zip(erase.plan, joint.plan)):
        delta_even = left[0] - right[0]
        delta_odd = left[1] - right[1]
        if position == 1 and (delta_even != -2.0 or delta_odd != 0.0):
            problems.append("the counter-write changes the even coefficient by {0} and the "
                            "odd by {1} against the declared -2 and 0".format(delta_even,
                                                                             delta_odd))
        if position != 1 and (delta_even != 0.0 or delta_odd != 0.0):
            problems.append("the erase arm differs from the joint outside the second phase")
    print("self-check: direction A reduces to the spent right-hand side, exactly")
    base = load_modules()
    spec = CoexistenceSpec(0, "reduction", "reduction", LARGEST_LOAD,
                           (DIRECTION_A, DIRECTION_A, NO_WRITE), "itself")
    state = gate_load.loaded_seed(spec, base)
    rate = split.gate_rate_of(state, base)
    mine = write_rhs(state, rate, DIRECTION_A, base, LARGEST_SPLIT)
    theirs = split.split_rhs(state, rate, split.SplitSpec(0, "reference", "reference",
                                                          LARGEST_SPLIT, 0.0, 0.0, -1), base)
    if not np.array_equal(mine, theirs):
        problems.append("direction A is not the spent split executor's own right-hand side")
    zero = write_rhs(state, rate, NO_WRITE, base, LARGEST_SPLIT)
    reference = split.split_rhs(state, rate, split.SplitSpec(0, "reference", "reference",
                                                             0.0, 0.0, 0.0, -1), base)
    if not np.array_equal(zero, reference):
        problems.append("the no-write right-hand side is not the spent executor's own")
    if not np.all(np.isfinite(mine)):
        problems.append("the right-hand side is not finite on the seeded state")
    print("self-check: the pre-flight, in both directions, on the seeded state")
    preflight = action_preflight(base)
    preflight["passed"] = bool(all(preflight["checks"].values()))
    for label in ("A", "B", "null"):
        reading = preflight["readings"][label]
        print("  {0:<4} even {1:.6e} odd {2:.6e} relative {3:.6e} (cross {4:.6e})".format(
            label, reading["even_norm"], reading["odd_norm"], reading["relative"],
            reading["odd_relative"] if label != "B" else reading["even_relative"]))
    print("  direction cosine {0}".format(preflight["direction_cosine"]))
    print("  scalar action live {0} silent {1} drift {2}".format(
        preflight["scalar"]["live"]["relative"], preflight["scalar"]["silent"]["relative"],
        preflight["scalar"]["live"]["drift"]))
    if abs(preflight["scalar"]["live"]["relative"] - ORACLE_SCALAR_ACTION_LIVE) \
            > REPLICATION_TOL:
        problems.append("the scalar action does not reproduce the successor receipt")
    if preflight["scalar"]["silent"]["relative"] != ORACLE_SCALAR_ACTION_SILENT:
        problems.append("the scalar action on the ray seed is not the exact zero")
    if preflight["checks"]["null_zero"] is False:
        problems.append("the null displaces the declared coordinates")
    print("self-check: the label vocabulary is reachable in every branch")
    times = np.array(HORIZONS, dtype=np.float64)
    written = READABLE_LEVEL * 1.0e3
    previews = (
        ("RETAINED", [written] * len(HORIZONS)),
        ("DECAYED", list(written * np.exp(-NU_REFERENCE * times))),
        # A fall faster than any rate the free scan can express: the held fit's rate leaves
        # a residual above the declared band, and the free fit is pinned at its ceiling, so
        # neither established fit describes the series. That is the branch's meaning.
        ("UNRESOLVED", list(written * np.exp(-8.0 * NU_REFERENCE * times))),
        ("SILENT", [SILENCE_LEVEL / 10.0] * len(HORIZONS)),
    )
    for wanted, values in previews:
        observed = group_fit([float(value) for value in values])["label"]
        if observed != wanted:
            problems.append("the group fit labels its {0} preview as {1}".format(wanted,
                                                                                 observed))
    print("self-check: the verdict vocabulary is reachable in every branch")
    for label in ("ERASES_ONE", "RESIDUAL", "MOVES_BOTH"):
        if label not in ERASURE_VERDICTS:
            problems.append("the erasure verdict {0} is not declared".format(label))
    blocking = ("COEXIST_ADDITIVE", "COEXIST_NONADDITIVE", "INTERFERE")
    for label in COEXISTENCE_VERDICTS:
        if label not in blocking + ("RESERVED_ONE_RETAINED", "RESERVED_NOT_DISTINGUISHABLE"):
            problems.append("the coexistence verdict {0} is unreachable in the rule".format(
                label))
    print("self-check: the decision rule reads every gate")
    sample_gates = [{"id": index, "name": "gate {0}".format(index), "reading": "sample",
                     "bound": "sample", "passed": True} for index in range(1, 15)]
    if status_of(sample_gates, {"F1_can_fail_fired": True}) != "PASS":
        problems.append("the status rule does not return PASS on an all-true gate set")
    for row in sample_gates:
        mutated = [dict(item) for item in sample_gates]
        mutated[row["id"] - 1]["passed"] = False
        if status_of(mutated, {"F1_can_fail_fired": True}) != "FAIL":
            problems.append("gate {0} does not carry the status".format(row["id"]))
    if status_of(sample_gates, {"F1_can_fail_fired": False}) != "PASS":
        problems.append("a false branch-selecting feature still fails the status")
    print("self-check: the clock and the oracle literals against the bound receipt")
    clock_read = read_clock()
    if not clock_read["equal_to_declared"]:
        problems.append("the successor receipt's relaxation rate is not the declared one")
    oracle = successor_oracle()
    if oracle["short_rho"] != ORACLE_RAY_RHO:
        problems.append("the declared short-horizon residual is not the receipt's")
    if oracle["coordinate"]["supersplit_load_final"] != REPLICATION_WRITE_A_AT_T1:
        problems.append("the declared write-A replication literal is not the receipt's")
    if oracle["coordinate"]["ray_supersplit_final"] != REPLICATION_RAY_WRITE_AT_T1:
        problems.append("the declared ray-write replication literal is not the receipt's")
    if oracle["coordinate"]["loadmax_anchor_at_horizons"][-1] \
            != REPLICATION_LOAD_REFERENCE_AT_T1:
        problems.append("the declared loaded-reference literal is not the receipt's")
    if oracle["ray_distance"]["supersplit_load_final"] != REPLICATION_WRITE_A_RAY_DISTANCE:
        problems.append("the declared write-A ray distance is not the receipt's")
    if oracle["ray_distance"]["ray_supersplit_final"] != REPLICATION_RAY_WRITE_RAY_DISTANCE:
        problems.append("the declared ray-write ray distance is not the receipt's")
    print("self-check: the receipt")
    status = receipt_status()
    if status["present"]:
        print("  {0} present, schema {1}, status {2}, binding {3} {4}".format(
            RECEIPT_PATH, status["schema"], status["status"],
            "consistent" if status["consistent"] else "INCONSISTENT",
            status["mismatched_sources"]))
        if status["schema"] != RECEIPT_SCHEMA:
            problems.append("the receipt's schema is not this protocol's")
    else:
        print("  {0} absent".format(RECEIPT_PATH))
    print("self-check: derived budget")
    print("  {0} arms, {1} steps, projected {2} s at the assumed rate and {3} s at the "
          "measured one, against the bound {4}".format(len(ARM_TABLE), total,
                                                      PROJECTED_SECONDS_ASSUMED,
                                                      PROJECTED_SECONDS_MEASURED,
                                                      BOUND_SECONDS))
    if PROBLEMS := problems:
        print("SELF-CHECK FAILED")
        for problem in PROBLEMS:
            print("  {0}".format(problem))
        return EXIT_STATIC_CHECK
    print("SELF-CHECK PASSED")
    return EXIT_PASS


def design_probe() -> int:
    """Section 1.5: the readings the declared floors, bands and bounds are chosen against.

    Runs every declared arm once and writes nothing. This is design work, not an
    invocation: the run is expected to reproduce it, because it is the same construction on
    the same seed, and gate 6 checks that it does.
    """
    built = build()
    result = finish(built)
    preflight = built["preflight"]
    displacements = result["displacements"]
    print()
    print("design probe: the pre-flight, both directions, on the seeded state")
    print("  drift {0:.12e}".format(preflight["drift"]))
    for label in ("A", "B", "null"):
        reading = preflight["readings"][label]
        print("  {0:<5} even {1:>13.6e} odd {2:>13.6e} even/drift {3:>12.4e} odd/drift "
              "{4:>12.4e}".format(label, reading["even_norm"], reading["odd_norm"],
                                  reading["even_relative"], reading["odd_relative"]))
    print("  direction cosine {0}".format(preflight["direction_cosine"]))
    print("  checks {0}".format(preflight["checks"]))
    print("  scalar action live {0} silent {1} drift {2}".format(
        preflight["scalar"]["live"]["relative"], preflight["scalar"]["silent"]["relative"],
        preflight["scalar"]["live"]["drift"]))
    print()
    print("design probe: the group displacements, both groups, every read time")
    for name in [arm.name for arm in ARM_TABLE]:
        record = displacements[name]
        fits = record["fits"]
        labels = "none" if fits is None else "{0}/{1}".format(fits["even"]["label"],
                                                             fits["odd"]["label"])
        print("  {0:<16} baseline {1:<15} fits {2}".format(name, record["baseline"], labels))
        for key in READ_KEYS:
            groups = record["groups"].get(key)
            if groups is None:
                print("      {0:<3} no reading: the arm's schedule stops before it".format(key))
                continue
            print("      {0:<3} even {1:>13.6e} odd {2:>13.6e} norm {3:>13.6e}".format(
                key, groups["even_norm"], groups["odd_norm"], groups["norm"]))
        release = record["release"]
        if release is None:
            print("      release none: the arm has no release window")
            continue
        for group in GROUPS:
            series = release["{0}_norms".format(group)]
            print("      release {0:<4} {1}".format(
                group, ["{0:.6e}".format(value) for value in series]))
    print()
    print("design probe: the coexistence and erasure readings")
    for key, value in result["decision"]["additive"].items():
        print("  additive {0:<5} gap {1:.6f} cosine {2} passed {3}".format(
            key, value["relative_gap"], value["cosine"], value["passed"]))
    for key, value in result["decision"]["erase_match"].items():
        print("  erase vs {0:<13} gap {1:.6f} cosine {2} passed {3}".format(
            key, value["relative_gap"], value["cosine"], value["passed"]))
    print("  retained {0}".format(result["decision"]["retained"]))
    print("  cross at T3 {0}".format(result["decision"]["cross_at_t3"]))
    print("  scalar at T3 {0}".format(result["decision"]["scalar"]))
    print("  verdicts: coexistence {0}, erasure {1}".format(
        result["decision"]["coexistence"], result["decision"]["erasure"]))
    print()
    print("design probe: the gates and the status")
    for row in result["gates"]:
        print("  gate {0:>2} {1:<46} {2}".format(row["id"], row["name"],
                                                 "pass" if row["passed"] else "FAIL"))
    print("  status {0}".format(result["status"]))
    print("  replication mismatches {0}".format(result["replication"]["mismatches"]))
    print("  budget {0} arms, {1} steps, largest {2}".format(
        result["budget"]["executions"], result["budget"]["steps_total"],
        result["budget"]["steps_max"]))
    print("  probe_readings = ({0})".format(", ".join(
        "{0:.16e}".format(displacements[label.split(":")[0]]["groups"][
            label.split(":")[2]]["{0}_norm".format(label.split(":")[1])])
        for label in PROBE_READING_ORDER)))
    return EXIT_PASS


def freeze() -> int:
    """Print the two digests and the section-0 rows the freeze pass pastes in."""
    print("frozen_body_sha256 = {0}".format(protocol_body_digest()))
    print("executor_sha256    = {0}".format(digest_of(PROBE_PATH)))
    print("prior_body         = {0}".format(prior.protocol_body_digest()))
    print("successor_body     = {0}".format(successor.protocol_body_digest()))
    print("gate_load_body     = {0}".format(gate_load.protocol_body_digest()))
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--design-probe", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument("--expect-frozen-body", default=None)
    parser.add_argument("--expect-executor", default=None)
    arguments = parser.parse_args(argv)
    if arguments.self_check:
        return self_check()
    if arguments.design_probe:
        return design_probe()
    if arguments.freeze:
        return freeze()
    if arguments.expect_frozen_body or arguments.expect_executor:
        check_binding(expect_body=arguments.expect_frozen_body,
                      expect_executor=arguments.expect_executor)
        print("REFUSING TO RUN: the expectation flags are for the self-check only")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
