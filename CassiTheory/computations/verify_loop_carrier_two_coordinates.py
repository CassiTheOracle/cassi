"""Does the frozen generator's second conserved direction at r = 0 hold a second coordinate?

The spent body `verify_loop_carrier_composition_coexistence.py` read the loop carrier's
composition profile and measured one retained writable coordinate. The audit
`verify_loop_carrier_kernel_dimension.py` then showed that this coordinate is the frozen
generator's own conserved direction at that body's declared point -- dim ker = 1, no gap
entry vanishing -- so the retention is a conservation law and not a capacity, and that the
executor's reduction was transposed: it averaged over the loop axis and indexed the exterior
axis, so the object it stored is the chi-average of the profile the protocol declared.

This body takes the dial the audit exposed. LB39's internal gap is a minimum of three
entries and each vanishing entry is an extra conserved direction; at r = 0, the boundary
LB39 itself names -- "the uniform direction imbalance is conserved" -- the second entry 2r
vanishes, the third becomes d > 0, and the mode-0 kernel is the whole two-dimensional
direction space at the equilibrium ratio. The protocol declares dim ker = 2 there *before*
the run and states the three entry values.

Four things are measured, each with a declared branch: whether the second direction is an
actual retained coordinate of the field's own state (a `present`), whether a declared drive
writes it (b `writable`), whether it survives a release window on which the spent point's
clock would erase it (c `retained`, with the counterfactual measured by a restored control
at r = 0.6 and published as the analytic factor), and whether a counter-write removes it
while the first coordinate stands (d `erased independently`). The reading domain is the one
the spent protocol declared and its executor did not implement -- mean over the exterior
axis, indexed by the loop sample -- and the two declared-shaped probes that exposed the
transposition are rebuilt here and gated, so the transposition cannot recur unnoticed.

The executors of the spent chain are imported as libraries: `verify_loop_carrier_gate_load`
for the loaded seed, the load reading and the chain's loader, `verify_loop_carrier_projection_
split` for the seed and the gate rate, `verify_loop_carrier_attractor_write` for the two
retention fits, the scalar coordinate, the ray distance and the declared clock, and
`verify_loop_carrier_composition_coexistence` for the direction-A gate line this body's
carrier channel must reduce to term for term.

Run once: `timeout 900 python computations/verify_loop_carrier_two_coordinates.py`.
`--static` checks without writing, `--design-probe` prints the readings the declared floors
are chosen against, `--freeze` prints the two section-0 digests.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# The spent chain is imported as a library. `split` and `gate_load` carry the seed family and
# the gate line; `prior` carries the two retention fits, the scalar coordinate, the ray
# distance, the declared clock and the release horizons; `spent` carries the direction-A
# modulation this body's carrier channel reduces to; `audit` carries the closed form's
# spectrum, the kernel structure and the two declared-shaped reading-domain probes.
import verify_loop_carrier_attractor_write as prior  # noqa: E402
import verify_loop_carrier_composition_coexistence as spent  # noqa: E402
import verify_loop_carrier_gate_load as gate_load  # noqa: E402
import verify_loop_carrier_kernel_dimension as audit  # noqa: E402
import verify_loop_carrier_projection_split as split  # noqa: E402

# Section 0: the bound sources. Every row is a file whose bytes this executor reads, hashes
# and refuses on; none is a running process.
BOUND_MODULE = gate_load.BOUND_MODULE
BASE_PROBE = gate_load.BASE_PROBE
SPLIT_EXECUTOR = gate_load.SPLIT_EXECUTOR
GATE_LOAD_EXECUTOR = gate_load.PROBE_PATH
SPENT_EXECUTOR = spent.PROBE_PATH
SPENT_BODY = spent.PROTOCOL_PATH
AUDIT_EXECUTOR = "computations/verify_loop_carrier_kernel_dimension.py"
WRITE_EXECUTOR = "computations/verify_loop_carrier_attractor_write.py"
BASE_RECEIPT = gate_load.BASE_RECEIPT
SPLIT_RECEIPT = gate_load.SPLIT_RECEIPT
GATE_LOAD_RECEIPT = gate_load.RECEIPT_PATH
PRIOR_RECEIPT = prior.RECEIPT_PATH
SPENT_RECEIPT = spent.RECEIPT_PATH

PROTOCOL_PATH = "computations/loop-carrier-two-coordinate-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_two_coordinates.py"
RECEIPT_PATH = "runs/loop_carrier_two_coordinates/verification.json"
INVOCATION = "timeout 1800 python computations/verify_loop_carrier_two_coordinates.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-two-coordinates.v1"
BOUND_SECONDS = 1800.0
# Section 0: the spent body's own frozen range, read through the spent executor's digest
# function rather than pasted as a whole-file hash.
PRIOR_BODY_DIGEST = "09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25"

# Section 0 declares both hashes: this file's, and the digest of the frozen body (everything
# from "## 1." to just before "## 8."). Filled by the freeze pass.
FROZEN_BODY_DIGEST = "FILLED_AT_FREEZE"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.3: the declared thresholds. Everything the spent chain fixed is carried
# unchanged; the ones this protocol adds are the restored-rate band, the anchor oracle
# tolerance and the two domain-probe levels.
READABLE_FLOOR_Q = 1.0e-12
SILENCE_FLOOR_Q = 1.0e-14
ACTION_FLOOR_LIVE = 1.0e-3
CROSS_RATIO_CEILING = 0.05
CROSS_SHARE_CEILING = 0.5
DISTINCTNESS_CEILING = 0.5
NULL_CEILING = 0.0
RETENTION_SHARE = prior.PERSIST_SHARE
RELEASE_SHARE = prior.TRANS_SHARE
PERSIST_SHARE = prior.PERSIST_SHARE
TRANS_SHARE = prior.TRANS_SHARE
CLOCK_TOLERANCE = prior.CLOCK_TOLERANCE
NU_TOLERANCE = prior.NU_TOLERANCE
COUNTERFACTUAL_FACTOR = 4.8e-235
RESTORED_SHARE_CEILING = 1.0e-6
ANCHOR_ORACLE_TOLERANCE = 1.0e-9
DOMAIN_CHI_FLOOR = 1.0e-3
DOMAIN_EXTERIOR_CEILING = 1.0e-15
PROBE_TOL = 1.0e-12
REPLICATION_TOL = 1.0e-15
KERNEL_TOL = 1.0e-10
KERNEL_SPAN_TOL = 1.0e-9
CLOCK_STRIDE = 250
LOAD_TOL = gate_load.LOAD_TOL
LOAD_ABS_FLOOR = gate_load.LOAD_ABS_FLOOR
RAY_READABLE_FLOOR = spent.RAY_READABLE_FLOOR
ANCHOR_RAY_TOL = spent.ANCHOR_RAY_TOL
STEP_SAFETY = split.STEP_SAFETY
STEP_CANDIDATES = split.STEP_CANDIDATES
DECLARED_DT = 0.02
LARGEST_LOAD = spent.LARGEST_LOAD
# Section 1.3: the two channel magnitudes. The carrier channel keeps the spent chain's
# largest declared magnitude. The orientation channel is declared smaller so that the gate
# rate stays positive on both orientations (at unit magnitude it would switch the conversion
# off entirely on one of them, which is a degenerate intervention whose counter-write cannot
# cancel) and so that the counter-write reaches the same regime from the other side.
DELTA_CARRIER = 1.0
DELTA_ORIENTATION = 0.2
MODES = split.MODES
N_CHI = 24

# Section 0: the spent receipt's own equilibrium reading, the exchange-free anchor's oracle.
ORACLE_SPENT_ANCHOR = 0.8923974885141119
ORACLE_SPENT_RAY_ANCHOR = 0.8923974885141087
# Section 5: the §71 audit's kernel labels and the declared point's two exchange values.
EXCHANGE_FREE = 0.0
EXCHANGE_SPENT = 0.6
KERNEL_LABELS_FREE = ("total-density (direction-symmetric, equilibrium ratio)",
                      "uniform direction imbalance (direction-antisymmetric, chi-uniform)")
KERNEL_LABELS_SPENT = ("total-density (direction-symmetric, equilibrium ratio)",)

# Section 1.1.1: the declared parameter point's entries of (LB39) at the equilibrium.
ENTRY_KAPPA = 1.1268281293796237e-2
ENTRY_EXCHANGE = 0.0
ENTRY_LOOP = 4.4982698961937725e-2

# Section 3: the declared schedules. Three phases of the same length -- the first channel,
# the second channel, and the release or the counter-write -- so each charged channel is held
# for at least one relaxation-scale span and the final phase is the shared release window.
PHASE_UNITS = 450.0
PHASE_STEPS = 22500
TOTAL_UNITS = 1350.0
TOTAL_STEPS = 67500
T1_INDEX = PHASE_STEPS
T2_INDEX = 2 * PHASE_STEPS
T3_INDEX = TOTAL_STEPS
HORIZONS = prior.HORIZONS
NU_REFERENCE = prior.NU_REFERENCE
RELEASE_SAMPLE = tuple(T2_INDEX + int(round(h / DECLARED_DT)) for h in HORIZONS)
SAMPLES = (("initial", 0), ("t1", T1_INDEX), ("t2", T2_INDEX)) + tuple(
    ("r{0}".format(position + 1), index)
    for position, index in enumerate(RELEASE_SAMPLE)
) + (("t3", T3_INDEX),)
READ_KEYS = ("t1", "t2", "t3")
RELEASE_KEYS = tuple("r{0}".format(position + 1)
                     for position in range(len(RELEASE_SAMPLE)))

NO_WRITE = (0.0, 0.0)
CARRIER_D = (1.0, 0.0)
ORIENTATION_N = (0.0, 1.0)
JOINT = (1.0, 1.0)
COUNTER_N = (0.0, -1.0)

PER_EXECUTION_CAP = 100000
TOTAL_STEP_CAP = 620000
DECLARED_EXECUTIONS = 9
SECONDS_PER_STEP_MEASURED = 1.07e-3
SECONDS_PER_STEP_ASSUMED = prior.SECONDS_PER_STEP_ASSUMED
PROJECTED_SECONDS_MEASURED = 650.0
PROJECTED_SECONDS_ASSUMED = 508.0

GROUPS = ("even", "odd")
PRESENT_LABELS = ("CONFIRMED_TWO", "MEASURED_ONE", "MEASURED_MORE", "MEASURED_NONE")
WRITABLE_LABELS = ("WRITABLE_BOTH", "UNWRITABLE_ONE", "UNWRITABLE_NONE")
RETAINED_LABELS = ("RETAINED_BOTH", "RETAINED_ONE", "UNRETAINED")
ERASURE_LABELS = ("ERASED_INDEPENDENTLY", "RESIDUAL", "MOVES_BOTH", "RESERVED_NO_CHARGE")

# Section 1.5: the design probe's declared readings, in the order of PROBE_READING_ORDER,
# fixed against the probe's own run before the freeze; gate 7 checks the invocation
# reproduces them.
PROBE_READING_ORDER = (
    "write_D:even:t1", "write_D:odd:t1",
    "write_N:even:t1", "write_N:odd:t1",
    "write_N:even:t2", "write_N:odd:t2",
    "joint_DN:even:t3", "joint_DN:odd:t3",
    "erase_N:even:t3", "erase_N:odd:t3",
    "write_N_restored:odd:t3",
)
PROBE_READINGS = (
    -9.823123357810548e-05,
    3.418118705290213e-06,
    0.0,
    0.0,
    -9.921615330421574e-07,
    -8.957259285831062e-05,
    -9.922648384153021e-05,
    -8.605157735191993e-05,
    -9.913680956297188e-05,
    -8.548400949087709e-05,
    0.0,
)

BINDING_SOURCES = (
    ("bound_module_sha256", BOUND_MODULE,
     "d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1"),
    ("base_probe_sha256", BASE_PROBE,
     "28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622"),
    ("split_executor_sha256", SPLIT_EXECUTOR,
     "246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a"),
    ("gate_load_executor_sha256", GATE_LOAD_EXECUTOR,
     "be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac"),
    ("prior_executor_sha256", SPENT_EXECUTOR,
     "3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1"),
    ("audit_executor_sha256", AUDIT_EXECUTOR,
     "0503f109c8b431768fbe16d37dfe8a82dec18cce2f97dc417d2fb08d1474f07a"),
    ("base_receipt_sha256", BASE_RECEIPT,
     "3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1"),
    ("split_receipt_sha256", SPLIT_RECEIPT,
     "559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc"),
    ("gate_load_receipt_sha256", GATE_LOAD_RECEIPT,
     "471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1"),
    ("prior_receipt_sha256", PRIOR_RECEIPT,
     "5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200"),
    ("coexistence_receipt_sha256", SPENT_RECEIPT,
     "9724143b98cf394eb9948741d3a117c4cc1e4b14fe54ff2ad9e81dfddb8bf60f"),
)


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
    import re

    text = protocol_text()
    start = re.search(BODY_START, text)
    end = re.search(BODY_END, text)
    if start is None or end is None:
        raise SystemExit("the protocol does not carry the section 1 and section 8 headers")
    return hashlib.sha256(text[start.start():end.start()].encode("utf-8")).hexdigest()


def protocol_row(key: str) -> str:
    """Read one `| `key` | value |` row of the protocol's declared tables."""
    import re

    for line in protocol_text().splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) >= 2 and cells[0].strip().strip("`") == key:
            return cells[1].strip().strip("`")
    raise SystemExit("the protocol does not declare a row for {0}".format(key))


def declared_number(key: str) -> float:
    return float(protocol_row(key).replace(",", "").split()[0].strip("$="))


def check_binding(expect_body: str = None, expect_executor: str = None) -> dict:
    """Refuse to run on any digest mismatch, before any arm is constructed."""
    observed = {}
    failures = []
    for key, path, expected in BINDING_SOURCES:
        value = digest_of(path)
        observed[key] = {"path": path, "expected": expected, "observed": value}
        if value != expected:
            failures.append("{0}: {1} != {2}".format(key, value, expected))
    body = protocol_body_digest()
    executor = digest_of(PROBE_PATH)
    prior_body = spent.protocol_body_digest()
    observed["prior_body_sha256"] = {"path": SPENT_BODY, "expected": PRIOR_BODY_DIGEST,
                                     "observed": prior_body}
    if prior_body != PRIOR_BODY_DIGEST:
        failures.append("prior_body_sha256: {0} != {1}".format(prior_body,
                                                               PRIOR_BODY_DIGEST))
    declared_body = FROZEN_BODY_DIGEST
    declared_executor = protocol_row("executor_sha256")
    observed["frozen_body_sha256"] = {"path": PROTOCOL_PATH, "expected": declared_body,
                                      "observed": body}
    observed["executor_sha256"] = {"path": PROBE_PATH, "expected": declared_executor,
                                   "observed": executor}
    if declared_body != "FILLED_AT_FREEZE" and body != declared_body:
        failures.append("frozen_body_sha256: {0} != {1}".format(body, declared_body))
    if declared_executor != "FILLED_AT_FREEZE" and executor != declared_executor:
        failures.append("executor_sha256: {0} != {1}".format(executor, declared_executor))
    if expect_body is not None and body != expect_body:
        failures.append("frozen body: {0} != {1}".format(body, expect_body))
    if expect_executor is not None and executor != expect_executor:
        failures.append("executor: {0} != {1}".format(executor, expect_executor))
    write_row = digest_of(WRITE_EXECUTOR)
    observed["write_executor_sha256"] = {
        "path": WRITE_EXECUTOR, "expected": protocol_row("write_executor_sha256"),
        "observed": write_row}
    if protocol_row("write_executor_sha256") != "PLACEHOLDER_CHECKED_AT_RUNTIME" \
            and protocol_row("write_executor_sha256") != write_row:
        failures.append("write_executor_sha256: {0} != {1}".format(
            write_row, protocol_row("write_executor_sha256")))
    if failures:
        print("REFUSING TO RUN: source binding failed")
        for line in failures:
            print("  " + line)
        print("The probe reads the frozen operators rather than reimplementing them and "
              "fails closed if any bound file changes.")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"declared": {"frozen_body_sha256": declared_body,
                         "executor_sha256": declared_executor},
            "observed": {key: value["observed"] for key, value in observed.items()},
            "rows": observed}


def load_modules():
    """Import the chain's machinery through the spent executors' own loader."""
    try:
        return split.load_base()
    except SystemExit:
        print("REFUSING TO RUN: the spent chain's own binding of the frozen operators "
              "failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)


base = load_modules()


class KernelSpec:
    """One declared arm: a load, an exchange, a seed and a three-phase plan.

    The plan is a tuple of three `(carrier, orientation)` coefficient pairs, one per phase,
    applied to the declared modulation

        m_s(chi) = delta (carrier cos chi + orientation s),
        kappa_{Y,s} = rate (1 + m_s),   kappa_{I,s} = rate (1 - m_s).

    Direction D is `(1, 0)`, direction N is `(0, 1)`, the joint is `(1, 1)` and the counter-N
    phase is `(0, -1)`: on the two orientations that is `-2` against the joint's `+2` on the
    orientation channel and `0` on the carrier one, so the counter phase reverses the new
    coordinate's drive and leaves the first coordinate's drive absent.
    """

    def __init__(self, index: int, name: str, role: str, load_c: float, plan: tuple,
                 baseline: str, exchange: float = 0.0):
        self.index = index
        self.name = name
        self.role = role
        self.load_c = float(load_c)
        self.plan = tuple(plan)
        self.baseline = baseline
        self.exchange = float(exchange)
        self.modes = MODES
        self.alpha = split.ALPHA
        self.delta_g = 0.0
        self.seed_imbalance = split.SEED_IMBALANCE
        self.carries_j = True
        self.horizon_key = "phases"
        self.dt = DECLARED_DT
        self.steps = TOTAL_STEPS
        self.horizon = TOTAL_UNITS
        self.profile = spent.PROFILE

    def coefficients(self, index: int) -> tuple:
        return self.plan[min(index // PHASE_STEPS, len(self.plan) - 1)]

    def declared_schedule(self) -> tuple:
        return DECLARED_DT, TOTAL_UNITS, TOTAL_STEPS

    def peak_factor(self) -> float:
        """The largest modulation factor any phase of the plan applies."""
        return max(1.0 + abs(carrier) + abs(orientation)
                   for carrier, orientation in self.plan)


def build_arm_table() -> tuple:
    """Section 3: the declared arms. One per direction, one joint, one counter-write, one
    restored control at the spent point with its own exchange-matched anchor, one ray pair
    predicted silent, and the two zero-displacement baselines."""
    arms = [
        KernelSpec(1, "ray_anchor", "baseline", 0.0,
                   (NO_WRITE, NO_WRITE, NO_WRITE), "itself"),
        KernelSpec(2, "load_reference", "baseline", LARGEST_LOAD,
                   (NO_WRITE, NO_WRITE, NO_WRITE), "itself"),
        KernelSpec(3, "restored_anchor", "baseline", LARGEST_LOAD,
                   (NO_WRITE, NO_WRITE, NO_WRITE), "itself", EXCHANGE_SPENT),
        KernelSpec(4, "write_D", "single", LARGEST_LOAD,
                   (CARRIER_D, CARRIER_D, NO_WRITE), "load_reference"),
        KernelSpec(5, "write_N", "single", LARGEST_LOAD,
                   (NO_WRITE, ORIENTATION_N, NO_WRITE), "load_reference"),
        KernelSpec(6, "write_N_restored", "control", LARGEST_LOAD,
                   (NO_WRITE, ORIENTATION_N, NO_WRITE), "restored_anchor",
                   EXCHANGE_SPENT),
        KernelSpec(7, "joint_DN", "joint", LARGEST_LOAD,
                   (CARRIER_D, ORIENTATION_N, NO_WRITE), "load_reference"),
        KernelSpec(8, "erase_N", "erase", LARGEST_LOAD,
                   (CARRIER_D, ORIENTATION_N, COUNTER_N), "load_reference"),
        KernelSpec(9, "ray_write_N", "ray", 0.0,
                   (NO_WRITE, ORIENTATION_N, NO_WRITE), "ray_anchor"),
    ]
    return tuple(arms)


ARM_TABLE = build_arm_table()
BASELINE_NAMES = ("ray_anchor", "load_reference", "restored_anchor")
LOADED_ARMS = ("load_reference", "restored_anchor", "write_D", "write_N",
               "write_N_restored", "joint_DN", "erase_N")
EXCHANGE_FREE_ARMS = ("ray_anchor", "load_reference", "write_D", "write_N", "joint_DN",
                      "erase_N", "ray_write_N")


def kernel_rhs(state: np.ndarray, rate: np.ndarray, coefficients: tuple, exchange: float,
               delta_carrier: float = DELTA_CARRIER,
               delta_orientation: float = DELTA_ORIENTATION) -> np.ndarray:
    """(LB6) with the frozen operators and the declared two-channel modulation.

    Term for term the spent executor's right-hand side, with the exchange coefficient
    carried explicitly instead of read from the module, and the orientation channel added:
    at `coefficients = (1, 0)` and the spent exchange and magnitude this is
    `spent.write_rhs` bit for bit.
    """
    dchi = base.loop_dx(state.shape[base.LOOP_AXIS])
    out = (
        -base.U * base.frozen.derivative(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        + base.D_X * base.frozen.laplacian(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        - base.SIGNS * base.OMEGA * base.frozen.derivative(state, base.LOOP_AXIS, dchi)
        + base.D_LOOP * base.frozen.laplacian(state, base.LOOP_AXIS, dchi)
        + exchange * (state[:, ::-1] - state)
    )
    cosine = np.cos(base.loop_grid(state.shape[base.LOOP_AXIS]))[None, :]
    carrier, orientation = coefficients
    if orientation == 0.0:
        modulation = delta_carrier * carrier * cosine
        kappa_y = rate * (1.0 + modulation)
        kappa_i = rate * (1.0 - modulation)
    else:
        sign = np.array((1.0, -1.0))[:, None, None]
        modulation = (delta_carrier * carrier * cosine[None, :, :]
                      + delta_orientation * orientation * sign)
        kappa_y = rate[None, :, :] * (1.0 + modulation)
        kappa_i = rate[None, :, :] * (1.0 - modulation)
    out[0] += kappa_y * (-state[0] + base.PHI * state[1])
    out[1] += kappa_i * (state[0] - base.PHI * state[1])
    return out


def kernel_step(state: np.ndarray, dt: float, coefficients: tuple, exchange: float) -> np.ndarray:
    return base.rk4_step(state, dt, lambda current: kernel_rhs(
        current, split.gate_rate_of(current, base), coefficients, exchange))


def declared_profile(state: np.ndarray) -> np.ndarray:
    """Section 1.2: mean over the exterior axis, indexed by the loop sample.

    The composition of the carriers carries three axes -- orientation, exterior, loop -- so
    the declared reduction is the mean over index 1 and the reading is indexed by the loop
    sample k = 0..23. This is the reduction the spent protocol declared and the spent
    executor did not implement.
    """
    composition = base.frozen.bounded_q(state[0], state[1])
    return composition.mean(axis=1)


def spent_profile(state: np.ndarray) -> np.ndarray:
    """The spent executor's own reduction, carried only to be refused: it averages the loop
    axis and indexes the exterior one."""
    return spent.composition_profile(state, base)


def groups_of(profile: np.ndarray) -> tuple:
    """The field's own partition of the reading domain: even and odd in the orientation."""
    return 0.5 * (profile[0] + profile[1]), 0.5 * (profile[0] - profile[1])


def uniform_of(group: np.ndarray) -> float:
    return float(np.mean(group))


def nonuniform_of(group: np.ndarray) -> float:
    return float(np.sqrt(np.sum(np.square(group - np.mean(group)))))


def scalar_coordinate(state: np.ndarray) -> float:
    """The spent chain's own scalar A, for the identity check."""
    return prior.coordinate_of(base.projection(state), base)


def reading_of(state: np.ndarray) -> dict:
    """Every declared reading of one state: both groups, their uniform content, the
    nonuniform remainders, the scalar identity and the ray distance."""
    profile = declared_profile(state)
    even, odd = groups_of(profile)
    ray = prior.ray_distance_of(base.projection(state), base)
    return {
        "even": float(uniform_of(even)),
        "odd": float(uniform_of(odd)),
        "even_vector": even,
        "odd_vector": odd,
        "even_nonuniform": nonuniform_of(even),
        "odd_nonuniform": nonuniform_of(odd),
        "scalar": scalar_coordinate(state),
        "ray_distance": ray,
        "min_state": float(np.min(state)),
        "max_state": float(np.max(state)),
        "q_min": float(np.min(profile)),
        "q_max": float(np.max(profile)),
    }


def state_vector(reading: dict) -> np.ndarray:
    """The declared 48-vector: the two groups' loop coordinates, in order."""
    return np.concatenate((reading["even_vector"], reading["odd_vector"]))


def action_preflight() -> dict:
    """Section 1.4: the readings on the seeded state, before integration.

    The numerator of each action reading is the single declared step's change of the
    coordinate that adding the direction makes; the denominator is that same step's own
    drift at no write. The loaded state is the largest declared load, so this is the firing
    side of the firing control.
    """
    seed_spec = KernelSpec(0, "preflight", "action", LARGEST_LOAD, (NO_WRITE,) * 3, "itself")
    state = gate_load.loaded_seed(seed_spec, base)
    start = reading_of(state)
    plain = kernel_step(state, DECLARED_DT, NO_WRITE, EXCHANGE_FREE)
    without = reading_of(plain)
    drift = abs(without["even"] - start["even"])
    readings = {}
    vectors = {}
    for label, coefficients in (("D", CARRIER_D), ("N", ORIENTATION_N)):
        stepped = kernel_step(state, DECLARED_DT, coefficients, EXCHANGE_FREE)
        after = reading_of(stepped)
        readings[label] = {
            "even_action": abs(after["even"] - without["even"]),
            "odd_action": abs(after["odd"] - without["odd"]),
        }
        vectors[label] = state_vector(after) - state_vector(without)
    null = reading_of(kernel_step(state, DECLARED_DT, NO_WRITE, EXCHANGE_FREE))
    ray_spec = KernelSpec(0, "preflight_ray", "action", 0.0, (NO_WRITE,) * 3, "itself")
    ray_state = gate_load.loaded_seed(ray_spec, base)
    ray_start = reading_of(ray_state)
    ray_plain = reading_of(kernel_step(ray_state, DECLARED_DT, NO_WRITE, EXCHANGE_FREE))
    ray_stepped = reading_of(kernel_step(ray_state, DECLARED_DT, ORIENTATION_N,
                                        EXCHANGE_FREE))
    denominator = max(drift, np.finfo(np.float64).tiny)
    own_D = max(readings["D"]["even_action"], np.finfo(np.float64).tiny)
    own_N = max(readings["N"]["odd_action"], np.finfo(np.float64).tiny)
    # The cross readings are ratios between the two directions' actions on the same
    # coordinate, because the composition is a nonlinear function of the densities: a drive
    # on one density combination always reaches the other coordinate at second order. What
    # the pre-flight establishes is that each direction acts on its own coordinate at the
    # largest declared magnitude and that the other direction's action there is far smaller.
    cross_ratio = readings["D"]["odd_action"] / own_N
    cross_share = readings["N"]["even_action"] / own_D
    unit_even = np.zeros(2 * N_CHI)
    unit_even[:N_CHI] = 1.0 / math.sqrt(N_CHI)
    unit_odd = np.zeros(2 * N_CHI)
    unit_odd[N_CHI:] = 1.0 / math.sqrt(N_CHI)
    cosines = {}
    for label in ("D", "N"):
        vector = vectors[label]
        cosines[label] = {
            "even": float(np.dot(vector, unit_even) / max(
                spent.vector_norm(vector), 1e-300)),
            "odd": float(np.dot(vector, unit_odd) / max(
                spent.vector_norm(vector), 1e-300)),
        }
    checks = {
        "live_D": bool(readings["D"]["even_action"] / denominator >= ACTION_FLOOR_LIVE),
        "live_N": bool(readings["N"]["odd_action"] / denominator >= ACTION_FLOOR_LIVE),
        "cross_D": bool(cross_ratio <= CROSS_RATIO_CEILING),
        "cross_N": bool(cross_share <= CROSS_SHARE_CEILING),
        "distinct": bool(abs(spent.cosine_of(vectors["D"], vectors["N"]))
                         <= DISTINCTNESS_CEILING),
        "null_zero": bool(null["even"] == without["even"] and null["odd"] == without["odd"]),
        "ray_odd_zero": bool(ray_stepped["odd"] == ray_plain["odd"]),
        "ray_even_zero": bool(ray_stepped["even"] == ray_plain["even"]),
    }
    return {
        "drift": drift,
        "load": float(gate_load.load_of(state, base)),
        "magnitudes": {"delta_carrier": DELTA_CARRIER, "delta_orientation":
                       DELTA_ORIENTATION},
        "readings": {
            "live_D": readings["D"]["even_action"] / denominator,
            "cross_D": cross_ratio,
            "live_N": readings["N"]["odd_action"] / denominator,
            "cross_N": cross_share,
            "distinctness": abs(spent.cosine_of(vectors["D"], vectors["N"])),
            "cosines": cosines,
            "null": {"even": null["even"] - without["even"],
                     "odd": null["odd"] - without["odd"]},
            "ray": {"even": ray_stepped["even"] - ray_plain["even"],
                    "odd": ray_stepped["odd"] - ray_plain["odd"],
                    "drift": ray_plain["even"] - ray_start["even"]},
        },
        "checks": checks,
        "readings_absolute": readings,
    }


def domain_probe() -> dict:
    """Section 1.4.3: the declared-shaped probes of the §71 audit, rebuilt here.

    `loop_only` varies the composition in chi and is constant in x; `exterior_only` does the
    reverse. The declared reader resolves the first and averages the second out; the spent
    reader does the opposite, which is the transposition §71 reported. The third probe is
    constant in chi, where the two readers must agree on every value they both report -- the
    reason the spent chain's own scalar reading was self-consistent.
    """
    seed_spec = KernelSpec(0, "domain", "probe", LARGEST_LOAD, (NO_WRITE,) * 3, "itself")
    state = gate_load.loaded_seed(seed_spec, base)
    shape = state.shape
    loop_axis, exterior_axis = base.LOOP_AXIS, base.EXTERIOR_AXIS
    n_chi, n_x = shape[loop_axis], shape[exterior_axis]
    chi = 2.0 * math.pi * np.arange(n_chi) / n_chi
    x = 2.0 * math.pi * np.arange(n_x) / n_x
    probes = {}
    loop_only = np.empty_like(state)
    loop_only[0] = (1.05 + 0.11 * np.cos(chi))[None, None, :] + 0.0 * state[0]
    loop_only[1] = (1.05 + 0.0 * np.cos(chi))[None, None, :] + 0.0 * state[1]
    probes["loop_only"] = loop_only
    exterior_only = np.empty_like(state)
    exterior_only[0] = (1.05 + 0.11 * np.cos(x))[None, :, None] + 0.0 * state[0]
    exterior_only[1] = (1.05 + 0.0 * np.cos(x))[None, :, None] + 0.0 * state[1]
    probes["exterior_only"] = exterior_only
    uniform = np.empty_like(state)
    uniform[0] = (1.05 + 0.11 * np.cos(x))[None, :, None] + 0.0 * state[0]
    uniform[1] = (1.00 + 0.0 * np.cos(x))[None, :, None] + 0.0 * state[1]
    probes["chi_uniform"] = uniform
    out = {}
    for label, probe in probes.items():
        mine = declared_profile(probe)
        theirs = spent_profile(probe)
        out[label] = {
            "declared_shape": tuple(int(value) for value in mine.shape),
            "spent_shape": tuple(int(value) for value in theirs.shape),
            "declared_row_spread": float(np.max(mine[0]) - np.min(mine[0])),
            "spent_row_spread": float(np.max(theirs[0]) - np.min(theirs[0])),
            "declared_mean": float(np.mean(mine[0])),
            "spent_mean": float(np.mean(theirs[0])),
        }
    out["reader_is_not_the_spent_reader"] = bool(
        not np.array_equal(declared_profile(loop_only), spent_profile(loop_only)))
    out["declared_shapes_24"] = bool(all(entry["declared_shape"][1] == N_CHI
                                        for entry in (out["loop_only"],
                                                      out["exterior_only"],
                                                      out["chi_uniform"])))
    out["chi_uniform_mean_difference"] = abs(out["chi_uniform"]["declared_mean"]
                                             - out["chi_uniform"]["spent_mean"])
    out["chi_uniform_identity"] = bool(
        out["chi_uniform_mean_difference"] <= PROBE_TOL
        and out["chi_uniform"]["spent_row_spread"] > 0.0)
    return out


def kernel_check(exchange: float) -> dict:
    """Section 5: the stored mode-0 generator at one exchange, against the closed spectrum.

    The generator is built by the frozen operator module from the declared equilibrium kappa
    and the arm's own exchange, so both the kernel count and the entry values are read from
    the machinery rather than from this protocol's arithmetic. The null space is taken from
    the singular values and its overlap with the direction-symmetric and
    direction-antisymmetric subspaces is measured, so the two labels of the declared
    prediction are gated instead of asserted.
    """
    kappa = ENTRY_KAPPA / (1.0 + base.PHI)
    generator = base.frozen.mode_generator(0, kappa, exchange, base.OMEGA, base.D_LOOP)
    closed = base.mode_spectrum(0, kappa, exchange)
    numeric = np.linalg.eigvals(generator)
    left, singular, right = np.linalg.svd(generator)
    positions = [position for position in range(len(singular))
                 if singular[position] < KERNEL_TOL]
    basis = right[positions].conj().T
    symmetric = np.array(((1.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 1.0)))
    antisymmetric = np.array(((1.0, -1.0, 0.0, 0.0), (0.0, 0.0, 1.0, -1.0)))
    directions = []
    residuals = []
    for column, position in enumerate(positions):
        vector = basis[:, column]
        structure = audit.kernel_structure(vector, base.PHI)
        scale = max(abs(complex(value)) for value in vector) or 1.0
        ratio = (complex(vector[0]) + complex(vector[1])) / (
            complex(vector[2]) + complex(vector[3]))
        finite = bool(abs(complex(vector[2]) + complex(vector[3])) / scale > 1.0e-12)
        residuals.append(float(structure["epsilon_of_direction_pair"]))
        directions.append({
            "singular_value": float(singular[position]),
            "components": [complex(value) for value in structure["components"]],
            "epsilon_residual": float(structure["epsilon_of_direction_pair"]),
            "direction_asymmetry": float(structure["direction_asymmetry_y"]
                                         + structure["direction_asymmetry_i"]),
            "carrier_ratio": float(ratio.real) if finite else None,
            "carrier_ratio_residual": float(abs(ratio) - base.PHI) if finite else None,
        })
    return {
        "kappa": kappa,
        "exchange": exchange,
        "numeric_spectrum": [complex(value) for value in numeric],
        "closed_spectrum": [complex(value) for value in closed],
        "multiset_residual": float(base.frozen.multiset_residual(numeric, closed)),
        "nullity": len(positions),
        "singular_values": [float(value) for value in singular],
        "symmetric_dimension": int(np.linalg.matrix_rank(symmetric @ basis,
                                                         tol=KERNEL_SPAN_TOL)),
        "antisymmetric_dimension": int(np.linalg.matrix_rank(antisymmetric @ basis,
                                                             tol=KERNEL_SPAN_TOL)),
        "kernel_residual": max(residuals) if residuals else 0.0,
        "directions": directions,
    }


def arm_record(spec: KernelSpec) -> dict:
    """One declared arm: its schedule, its coordinate series, its structure and its plan.

    The clock is read on the loaded anchor's own eps-excursion level, sampled on a declared
    uniform stride so the release-phase fit has its own series; no other arm pays for it.
    """
    state = gate_load.loaded_seed(spec, base)
    load_measured = gate_load.load_of(state, base)
    samples = {}
    wanted = {}
    for key, index in SAMPLES:
        wanted.setdefault(index, []).append(key)
    clock = {"stride": CLOCK_STRIDE, "stride_units": CLOCK_STRIDE * DECLARED_DT,
             "values": [], "steps": []}
    records_clock = spec.name == "load_reference"
    if records_clock:
        clock["values"].append(float(prior.ray_distance_of(base.projection(state), base)))
        clock["steps"].append(0)
    step = 0
    while True:
        for key in wanted.get(step, ()):
            reading = reading_of(state)
            samples[key] = {name: value for name, value in reading.items()
                            if not name.endswith("_vector")}
            samples[key]["index"] = int(step)
        if step >= TOTAL_STEPS:
            break
        state = kernel_step(state, DECLARED_DT, spec.coefficients(step), spec.exchange)
        step += 1
        if records_clock and step % CLOCK_STRIDE == 0:
            clock["values"].append(float(prior.ray_distance_of(base.projection(state), base)))
            clock["steps"].append(int(step))
    return {
        "index": spec.index,
        "name": spec.name,
        "declared": {
            "load_transfer": spec.load_c,
            "plan": [[float(carrier), float(orientation)]
                     for carrier, orientation in spec.plan],
            "exchange": spec.exchange,
            "baseline": spec.baseline,
        },
        "schedule": {"dt": DECLARED_DT, "steps": TOTAL_STEPS, "horizon": TOTAL_UNITS,
                     "phases": len(spec.plan),
                     "rule_conformant": bool(
                         DECLARED_DT <= 1.0 / (STEP_SAFETY * kernel_lambda_max(spec)))},
        "load": gate_load.load_comparison(spec, load_measured),
        "clock": clock,
        "samples": samples,
    }


def kernel_lambda_max(spec: KernelSpec) -> float:
    """The step rule's own lambda_max, on the arm's own exchange and peak gate."""
    kappa = base.gate_rate(*base.projection(gate_load.loaded_seed(spec, base)))
    peak = float(np.max(kappa)) * spec.peak_factor()
    return float(max(abs(value.real) for mode in spec.modes
                     for value in base.mode_spectrum(mode, peak, spec.exchange)))


def baseline_of(arms: dict, name: str) -> dict:
    """The arm's declared baseline: itself for the two zero-displacement anchors."""
    declared = arms[name]["declared"]["baseline"]
    return arms[name] if declared == "itself" else arms[declared]


def displacement_of(arms: dict, name: str, key: str) -> dict:
    """The arm's group displacement against its own declared baseline, at one read time."""
    arm = arms[name]
    baseline = baseline_of(arms, name)
    out = {}
    for group in GROUPS:
        value = arm["samples"][key][group]
        reference = baseline["samples"][key][group]
        out[group] = {"value": value, "reference": reference, "displacement":
                      value - reference, "norm": abs(value - reference)}
    out["scalar"] = {"value": arm["samples"][key]["scalar"],
                     "reference": baseline["samples"][key]["scalar"]}
    out["ray_distance"] = {"value": arm["samples"][key]["ray_distance"],
                           "reference": baseline["samples"][key]["ray_distance"]}
    out["nonuniform"] = {group: {"value": arm["samples"][key][group + "_nonuniform"],
                                 "reference": baseline["samples"][key][
                                     group + "_nonuniform"]}
                         for group in GROUPS}
    return out


def displacement_record(arms: dict, name: str) -> dict:
    """Every declared displacement reading of one arm: both groups at every sample."""
    keys = tuple(key for key, _ in SAMPLES)
    return {"groups": {key: displacement_of(arms, name, key) for key in keys},
            "baseline": arms[name]["declared"]["baseline"]}


def group_fit(arms: dict, name: str, group: str) -> dict:
    """Section 2.6: the two established fits on one coordinate's release-window series."""
    arm = arms[name]
    baseline = baseline_of(arms, name)
    values = [arm["samples"][key][group] - baseline["samples"][key][group]
              for key in RELEASE_KEYS]
    held = prior.fit_held(values)
    free = prior.fit_free(values)
    return {"values": values, "held": held, "free": free}


def decide(arms: dict, displacements: dict, preflight: dict, domain: dict,
           spectrum: dict) -> dict:
    """Section 2.5: the four declared branches, and every reading they consume."""
    joint = "joint_DN"
    joint_odd = abs(displacements[joint]["groups"]["t3"]["odd"]["displacement"])
    joint_even = abs(displacements[joint]["groups"]["t3"]["even"]["displacement"])
    write_d_even = abs(displacements["write_D"]["groups"]["t3"]["even"]["displacement"])
    write_n_odd = abs(displacements["write_N"]["groups"]["t3"]["odd"]["displacement"])
    standing = {"even": bool(max(joint_even, write_d_even) >= READABLE_FLOOR_Q),
                "odd": bool(max(joint_odd, write_n_odd) >= READABLE_FLOOR_Q)}
    measured_standing = int(sum(1 for value in standing.values() if value))
    predicted = spectrum["free"]["nullity"]
    if measured_standing == predicted:
        branch_present = "CONFIRMED_TWO"
    elif measured_standing == 0:
        branch_present = "MEASURED_NONE"
    elif measured_standing < predicted:
        branch_present = "MEASURED_ONE"
    else:
        branch_present = "MEASURED_MORE"

    live = {"even": bool(preflight["checks"]["live_D"]),
            "odd": bool(preflight["checks"]["live_N"])}
    charged = {"even": bool(write_d_even >= READABLE_FLOOR_Q),
               "odd": bool(write_n_odd >= READABLE_FLOOR_Q)}
    writable = int(sum(1 for key in ("even", "odd") if live[key] and charged[key]))
    if writable == 2:
        branch_writable = "WRITABLE_BOTH"
    elif writable == 1:
        branch_writable = "UNWRITABLE_ONE"
    else:
        branch_writable = "UNWRITABLE_NONE"

    retained = {}
    for label, name, group in (("D", "write_D", "even"), ("N", "write_N", "odd")):
        arm = arms[name]
        baseline = baseline_of(arms, name)
        first = arm["samples"][RELEASE_KEYS[0]][group] - baseline["samples"][
            RELEASE_KEYS[0]][group]
        second = arm["samples"][RELEASE_KEYS[1]][group] - baseline["samples"][
            RELEASE_KEYS[1]][group]
        final = arm["samples"]["t3"][group] - baseline["samples"]["t3"][group]
        peak_at_t2 = displacements[name]["groups"]["t2"][group]["displacement"]
        if abs(peak_at_t2) <= 0.0:
            share = None
        else:
            share = abs(final) / abs(peak_at_t2)
        movement = None if abs(second) <= 0.0 else abs(final - second) / abs(second)
        retained[label] = {
            "peak_at_t2": peak_at_t2,
            "final": final,
            "share": share,
            "final_phase_movement": movement,
            "passed": bool(share is not None and share >= RETENTION_SHARE
                           and movement is not None and movement <= RELEASE_SHARE),
        }
    count_retained = int(sum(1 for entry in retained.values() if entry["passed"]))
    if count_retained == 2:
        branch_retained = "RETAINED_BOTH"
    elif count_retained == 1:
        branch_retained = "RETAINED_ONE"
    else:
        branch_retained = "UNRETAINED"

    erase = {}
    for group in GROUPS:
        erase[group] = {
            "at_t2": displacements["erase_N"]["groups"]["t2"][group]["displacement"],
            "at_t3": displacements["erase_N"]["groups"]["t3"][group]["displacement"],
        }
    # The counter-write is read differentially, against the arm that carries the same two
    # writes and no counter phase: the even charge of the first phase moves the odd group
    # too, because the composition is a nonlinear function of the densities, so the
    # counter's own effect is the difference between the two arms rather than the absolute
    # level of either.
    erase_difference = (displacements["erase_N"]["groups"]["t3"]["odd"]["value"]
                        - displacements["joint_DN"]["groups"]["t3"]["odd"]["value"])
    charge = displacements["joint_DN"]["groups"]["t3"]["odd"]["displacement"]
    removed_share = (abs(erase_difference) / abs(charge)) if abs(charge) > 0.0 else None
    erased = bool(removed_share is not None and removed_share >= 1.0 - RELEASE_SHARE)
    even_final = abs(erase["even"]["at_t3"])
    even_scale = abs(erase["even"]["at_t2"])
    first_stands = bool(even_scale > 0.0 and even_final >= RETENTION_SHARE * even_scale)
    if erased and first_stands:
        branch_erasure = "ERASED_INDEPENDENTLY"
    elif not erased and first_stands:
        branch_erasure = "RESIDUAL"
    elif erased and not first_stands:
        branch_erasure = "MOVES_BOTH"
    else:
        branch_erasure = "RESERVED_NO_CHARGE"

    # Section 2.6: the counterfactual, read as the share of the T2 charge standing at T3 on
    # the same channel at the two parameter points. A fitted rate is not used here: on the
    # restored point the surviving level is at the round-off floor, where a rate fit has no
    # meaning, and the contrast between the two shares is the measurement. The charge is
    # read at T2 itself, not at the first release sample, because the restored point's whole
    # charge is gone before that sample.
    restored = group_fit(arms, "write_N_restored", "odd")
    unrestored = group_fit(arms, "write_N", "odd")
    restored_charge = displacements["write_N_restored"]["groups"]["t2"]["odd"]["displacement"]
    restored_final = displacements["write_N_restored"]["groups"]["t3"]["odd"]["displacement"]
    unrestored_charge = displacements["write_N"]["groups"]["t2"]["odd"]["displacement"]
    unrestored_final = displacements["write_N"]["groups"]["t3"]["odd"]["displacement"]
    restored_share = (abs(restored_final) / abs(restored_charge)
                      if abs(restored_charge) > 0.0 else None)
    unrestored_share = (abs(unrestored_final) / abs(unrestored_charge)
                        if abs(unrestored_charge) > 0.0 else None)
    counterfactual = {
        "analytic_factor": COUNTERFACTUAL_FACTOR,
        "restored_share": restored_share,
        "unrestored_share": unrestored_share,
        "restored_charge": restored_charge,
        "restored_final": restored_final,
        "restored_release_values": restored["values"],
        "restored_held_rate": restored["held"]["rate"],
        "passed": bool(restored_share is not None
                       and unrestored_share is not None
                       and restored_share <= RESTORED_SHARE_CEILING
                       and unrestored_share >= RETENTION_SHARE),
    }

    return {
        "present": branch_present,
        "writable": branch_writable,
        "retained": branch_retained,
        "erasure": branch_erasure,
        "predicted_nullity": predicted,
        "measured_standing": measured_standing,
        "standing": standing,
        "charged": charged,
        "live": live,
        "coordinate_retention": retained,
        "erase": dict(erase, counter_effect=erase_difference, removed_share=removed_share,
                      charge=charge, reference_arm="joint_DN"),
        "erased": erased,
        "first_stands": first_stands,
        "counterfactual": counterfactual,
        "domain_ok": bool(domain["declared_shapes_24"]
                          and domain["reader_is_not_the_spent_reader"]
                          and domain["chi_uniform_identity"]
                          and domain["loop_only"]["declared_row_spread"] >= DOMAIN_CHI_FLOOR
                          and domain["exterior_only"]["declared_row_spread"]
                          <= DOMAIN_EXTERIOR_CEILING),
    }


def gate_rows(arms: dict, displacements: dict, decision: dict, preflight: dict,
              domain: dict, spectrum: dict, replication: dict, probe_check: dict,
              clock: dict, clock_read: dict, budget: dict, comparison_ok: bool) -> list:
    """Section 4: every gate with its reading, its bound and its verdict. The
    branch-selecting readings of section 2.5 are not gates."""
    structural = all(
        arm["samples"][key]["min_state"] >= 0.0
        and np.isfinite(arm["samples"][key]["min_state"])
        and np.isfinite(arm["samples"][key]["max_state"])
        and 0.0 <= arm["samples"][key]["q_min"] <= arm["samples"][key]["q_max"] < 1.0
        for arm in arms.values() for key, _ in SAMPLES)
    conformant = all(arm["schedule"]["rule_conformant"] for arm in arms.values())
    shape_ok = (budget["executions"] == DECLARED_EXECUTIONS
                and budget["steps_max"] <= PER_EXECUTION_CAP
                and budget["steps_total"] <= TOTAL_STEP_CAP)
    baseline_zero = all(
        displacements[name]["groups"][key][group]["displacement"] == 0.0
        for name in BASELINE_NAMES for key in READ_KEYS for group in GROUPS)
    ray_readings = [abs(displacements["ray_write_N"]["groups"][key][group]["displacement"])
                    for key in READ_KEYS for group in GROUPS]
    ray_silence = max(ray_readings)
    anchor = {name: arms[name]["samples"]["t1"]["ray_distance"] for name in LOADED_ARMS
              if name != "load_reference"}
    can_fail = abs(displacements["write_N"]["groups"]["t2"]["odd"]["displacement"])
    clock_ok = bool(clock.get("passed") and clock_read.get("equal_to_declared"))
    kernel_ok = bool(spectrum["free"]["nullity"] == 2 and spectrum["spent"]["nullity"] == 1
                     and spectrum["free"]["multiset_residual"] <= REPLICATION_TOL
                     and spectrum["spent"]["multiset_residual"] <= REPLICATION_TOL
                     and spectrum["free"]["symmetric_dimension"] == 1
                     and spectrum["free"]["antisymmetric_dimension"] == 1
                     and spectrum["spent"]["symmetric_dimension"] == 1
                     and spectrum["spent"]["antisymmetric_dimension"] == 0
                     and spectrum["free"]["kernel_residual"] <= KERNEL_SPAN_TOL
                     and spectrum["spent"]["kernel_residual"] <= KERNEL_SPAN_TOL)
    anchor_ok = bool(replication["anchor_scalar"]["difference"] <= ANCHOR_ORACLE_TOLERANCE
                     and replication["ray_scalar"]["difference"] <= ANCHOR_ORACLE_TOLERANCE)
    load_ok = bool(replication["load"]["passed"])
    rows = [
        {"id": 1, "name": "binding", "reading": "every section-0 row declared against "
         "observed, all exact", "bound": "exact", "passed": True},
        {"id": 2, "name": "reading domain", "reading": domain,
         "bound": "the declared reader is the exterior mean over {0} loop samples and is "
                  "not the spent reader; the loop-only probe reads >= {1}, the exterior-only "
                  "probe <= {2}, and on the chi-uniform probe the two readers agree on the "
                  "reported mean within {3}".format(N_CHI, DOMAIN_CHI_FLOOR,
                                                    DOMAIN_EXTERIOR_CEILING, PROBE_TOL),
         "passed": bool(decision["domain_ok"])},
        {"id": 3, "name": "structure", "reading": "minimum and maximum state, and the "
         "composition bounds, over every recorded state",
         "bound": "nonnegative states, 0 <= q < 1", "passed": bool(structural)},
        {"id": 4, "name": "loads and shape", "reading": {
            "declared_executions": budget["executions"],
            "steps_total": budget["steps_total"], "steps_max": budget["steps_max"],
            "loads": {name: arms[name]["load"]["measured"] for name in LOADED_ARMS}},
         "bound": "every declared load within {0} relative ({1} absolute at zero), {2} "
                  "executions, {3} per execution, {4} total".format(
                      LOAD_TOL, LOAD_ABS_FLOOR, DECLARED_EXECUTIONS, PER_EXECUTION_CAP,
                      TOTAL_STEP_CAP),
         "passed": bool(comparison_ok and shape_ok)},
        {"id": 5, "name": "schedule conformance", "reading": {
            arm["name"]: {"exchange": arm["declared"]["exchange"],
                          "lambda_max": kernel_lambda_max(
                              next(spec for spec in ARM_TABLE if spec.name == arm["name"]))}
            for arm in arms.values()},
         "bound": "dt = {0} <= 1/({1} lambda_max) on every arm's own exchange".format(
             DECLARED_DT, STEP_SAFETY),
         "passed": bool(conformant)},
        {"id": 6, "name": "the spectrum and the anchors against the spent chain",
         "reading": {"free_nullity": spectrum["free"]["nullity"],
                     "spent_nullity": spectrum["spent"]["nullity"],
                     "free_residual": spectrum["free"]["multiset_residual"],
                     "spent_residual": spectrum["spent"]["multiset_residual"],
                     "free_directions": spectrum["free"]["directions"],
                     "anchor_scalar_difference": replication["anchor_scalar"]["difference"],
                     "ray_scalar_difference": replication["ray_scalar"]["difference"],
                     "load_relative_error": replication["load"]["relative_error"],
                     "jensen_gap_max": replication["jensen_gap"]["max_difference"],
                     "chi_uniform_mean_difference": domain[
                         "chi_uniform_mean_difference"]},
         "bound": "two null directions at r = 0 and one at r = {0}, the closed spectrum "
                  "reproduced within {1}, the spent receipt's own scalar on both anchors "
                  "within {2}, its recorded load transfer within {3} relative".format(
                      EXCHANGE_SPENT, REPLICATION_TOL, ANCHOR_ORACLE_TOLERANCE, LOAD_TOL),
         "passed": bool(kernel_ok and anchor_ok and load_ok)},
        {"id": 7, "name": "design probe reproduction", "reading": probe_check,
         "bound": "every declared probe reading within {0} relative".format(PROBE_TOL),
         "passed": bool(probe_check["passed"])},
        {"id": 8, "name": "baselines hold the zero displacement",
         "reading": {name: displacements[name]["groups"]["t3"]["even"]["norm"]
                     for name in BASELINE_NAMES},
         "bound": "exactly zero: the baseline is its own reference",
         "passed": bool(baseline_zero)},
        {"id": 9, "name": "silence on the ray pair",
         "reading": {"ray_write_N_at_load": ray_silence,
                     "displacement": {key: displacements["ray_write_N"]["groups"][key][
                         "even"]["norm"] for key in READ_KEYS}},
         "bound": "<= {0} at every read time; the ray's bracket vanishes identically"
                  .format(SILENCE_FLOOR_Q),
         "passed": bool(ray_silence <= SILENCE_FLOOR_Q)},
        {"id": 10, "name": "anchor readable on every arm charged an offset",
         "reading": anchor, "bound": ">= {0} at the first read time".format(
             RAY_READABLE_FLOOR),
         "passed": bool(all(value is not None and value >= RAY_READABLE_FLOOR
                            for value in anchor.values()))},
        {"id": 11, "name": "can-fail at the declared channel magnitudes",
         "reading": {"write_N_odd_t2": can_fail,
                     "write_N_even_t2": abs(displacements["write_N"]["groups"]["t2"][
                         "even"]["displacement"]),
                     "delta_carrier": DELTA_CARRIER,
                     "delta_orientation": DELTA_ORIENTATION},
         "bound": ">= {0} on the new direction's own coordinate".format(READABLE_FLOOR_Q),
         "passed": bool(can_fail >= READABLE_FLOOR_Q)},
        {"id": 12, "name": "the null moves neither coordinate",
         "reading": preflight["readings"]["null"], "bound": "exactly {0}".format(NULL_CEILING),
         "passed": bool(preflight["checks"]["null_zero"])},
        {"id": 13, "name": "the declared clock, read from the receipt",
         "reading": {"fitted": clock.get("rate"), "reference": clock.get("reference"),
                     "ratio": clock.get("ratio"), "window": clock.get("window"),
                     "samples": clock.get("samples"), "reason": clock.get("reason"),
                     "receipt_read": clock_read.get("read")},
         "bound": "factor {0} of the declared rate, read live from the receipt".format(
             NU_TOLERANCE), "passed": clock_ok},
        {"id": 14, "name": "single invocation", "reading": "receipt absent at start, one "
         "process", "bound": "structural", "passed": True},
    ]
    return rows


def features_of(gates: list, decision: dict, preflight: dict, spectrum: dict) -> dict:
    """Section 2.5 and 2.6: every branch-selecting reading, reported and deliberately
    outside the status conjunction. A reserved branch is a finding, not a failure."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    return {
        "F1_can_fail_fired": passed[11],
        "F2_ray_silent": passed[9],
        "F3_anchor_readable": passed[10],
        "F4_preflight_live_D": bool(preflight["checks"]["live_D"]),
        "F5_preflight_live_N": bool(preflight["checks"]["live_N"]),
        "F6_preflight_cross_D": bool(preflight["checks"]["cross_D"]),
        "F7_preflight_cross_N": bool(preflight["checks"]["cross_N"]),
        "F8_preflight_distinct": bool(preflight["checks"]["distinct"]),
        "F9_ray_identity": bool(preflight["checks"]["ray_odd_zero"]
                                and preflight["checks"]["ray_even_zero"]),
        "F10_predicted_nullity": int(decision["predicted_nullity"]),
        "F11_measured_standing": int(decision["measured_standing"]),
        "F12_retained_D": bool(decision["coordinate_retention"]["D"]["passed"]),
        "F13_retained_N": bool(decision["coordinate_retention"]["N"]["passed"]),
        "F14_counterfactual_measured": bool(decision["counterfactual"]["passed"]),
        "F15_erased_odd": bool(decision["erased"]),
        "F16_first_stands": bool(decision["first_stands"]),
        "present": decision["present"],
        "writable": decision["writable"],
        "retained": decision["retained"],
        "erasure": decision["erasure"],
    }


def status_of(gates: list, features: dict) -> str:
    """The status conjunction reads the gates only: the branch-selecting features of
    section 2.5 select a branch, and a reserved branch is a recorded finding."""
    every_gate = all(row["passed"] for row in gates)
    return "PASS" if every_gate else "FAIL"


def receipt_status() -> dict:
    """Idempotent: read the receipt if it exists and verify its own binding by digest."""
    path = os.path.join(ROOT, RECEIPT_PATH)
    if not os.path.exists(path):
        return {"exists": False, "path": RECEIPT_PATH}
    with open(path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    return {"exists": True, "path": RECEIPT_PATH, "digest": digest_of(RECEIPT_PATH),
            "schema": receipt.get("schema"), "status": receipt.get("status"),
            "invocation": receipt.get("invocation")}


def read_clock() -> dict:
    return prior.read_clock()


def replication(arms: dict) -> dict:
    """Section 5: the two anchors against the spent receipt's own recorded scalars.

    The spent chain's `coordinate` field is the composition read on the *loop-averaged*
    projection; this body's exterior-mean reading is a different reduction of the same
    pointwise composition, so the two agree only through the double mean. What is compared
    here is therefore the spent chain's own scalar, which every arm carries beside the two
    declared groups, and the recorded load transfer.
    """
    anchor_scalar = arms["load_reference"]["samples"]["t3"]["scalar"]
    ray_scalar = arms["ray_anchor"]["samples"]["t3"]["scalar"]
    gaps = []
    for arm in arms.values():
        for key, _ in SAMPLES:
            gaps.append(abs(arm["samples"][key]["even"]
                            - arm["samples"][key]["scalar"]))
    load_measured = arms["load_reference"]["load"]
    return {
        "anchor_scalar": {"observed": anchor_scalar, "declared": ORACLE_SPENT_ANCHOR,
                          "difference": abs(anchor_scalar - ORACLE_SPENT_ANCHOR),
                          "source": SPENT_RECEIPT,
                          "source_field": "arms.load_reference.coordinate.final"},
        "ray_scalar": {"observed": ray_scalar, "declared": ORACLE_SPENT_RAY_ANCHOR,
                       "difference": abs(ray_scalar - ORACLE_SPENT_RAY_ANCHOR),
                       "source": SPENT_RECEIPT,
                       "source_field": "arms.ray_anchor.coordinate.final"},
        "load": {"observed": load_measured["measured"],
                 "predicted": load_measured["predicted"],
                 "declared_transfer": load_measured["declared_transfer"],
                 "relative_error": load_measured.get("relative_error"),
                 "tolerance": load_measured["tolerance"],
                 "passed": bool(load_measured["passed"]),
                 "source": SPENT_RECEIPT,
                 "source_field": "arms.load_reference.load.measured"},
        "jensen_gap": {"max_difference": max(gaps), "field": "even_uniform - scalar",
                       "samples": len(gaps)},
    }


def probe_replication(displacements: dict) -> dict:
    """Gate 7: the run reproduces the design probe's declared readings."""
    readings = []
    for path in PROBE_READING_ORDER:
        name, group, key = path.split(":")
        readings.append(displacements[name]["groups"][key][group]["displacement"])
    mismatches = []
    for position, declared in enumerate(PROBE_READINGS):
        observed = readings[position]
        scale = max(abs(declared), 1e-300)
        if abs(observed - declared) / scale > PROBE_TOL:
            mismatches.append({"position": position, "declared": declared,
                               "observed": observed})
    return {"declared": list(PROBE_READINGS), "observed": readings,
            "mismatches": mismatches, "passed": bool(not mismatches)}


def build() -> dict:
    """Run every declared arm once, in order, and return the readings both verdicts read."""
    arms = {}
    for spec in ARM_TABLE:
        arms[spec.name] = arm_record(spec)
    preflight = action_preflight()
    domain = domain_probe()
    return {"arms": arms, "preflight": preflight, "domain": domain}


def assemble(built: dict, binding: dict, started: float) -> dict:
    """Every reading both verdicts read, from the built arms and the binding record.

    Separate from `execute` so the static pass can drive the whole gate, feature and
    receipt path on shaped inputs without paying for the integration; a key this path
    reads that its producers do not carry is then a static failure rather than a lost
    invocation.
    """
    arms, preflight, domain = built["arms"], built["preflight"], built["domain"]
    displacements = {name: displacement_record(arms, name) for name in arms}
    spectrum = {"free": kernel_check(EXCHANGE_FREE),
                "spent": kernel_check(EXCHANGE_SPENT)}
    replication_record = replication(arms)
    comparison_ok = all(arms[name]["load"]["passed"] for name in LOADED_ARMS)
    anchor_clock = arms["load_reference"]["clock"]
    clock = prior.clock_of(anchor_clock["values"], anchor_clock["stride_units"],
                           T1_INDEX // CLOCK_STRIDE, len(anchor_clock["values"]) - 1)
    clock_read = read_clock()
    decision = decide(arms, displacements, preflight, domain, spectrum)
    probe_check = probe_replication(displacements)
    steps_total = TOTAL_STEPS * len(ARM_TABLE)
    budget = {"executions": len(ARM_TABLE), "steps_max": TOTAL_STEPS,
              "steps_total": steps_total,
              "declared_dt": DECLARED_DT, "bound_seconds": BOUND_SECONDS,
              "seconds_per_step_measured": SECONDS_PER_STEP_MEASURED,
              "projected_seconds_measured": PROJECTED_SECONDS_MEASURED,
              "projected_seconds_assumed": PROJECTED_SECONDS_ASSUMED}
    gates = gate_rows(arms, displacements, decision, preflight, domain, spectrum,
                      replication_record, probe_check, clock, clock_read, budget,
                      comparison_ok)
    features = features_of(gates, decision, preflight, spectrum)
    status = status_of(gates, features)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "invocation": INVOCATION,
        "protocol": PROTOCOL_PATH,
        "protocol_body_sha256": protocol_body_digest(),
        "executor": PROBE_PATH,
        "executor_sha256": digest_of(PROBE_PATH),
        "binding": binding,
        "thresholds": {
            "readable_floor_q": READABLE_FLOOR_Q,
            "silence_floor_q": SILENCE_FLOOR_Q,
            "action_floor_live": ACTION_FLOOR_LIVE,
            "cross_ratio_ceiling": CROSS_RATIO_CEILING,
            "cross_share_ceiling": CROSS_SHARE_CEILING,
            "distinctness_ceiling": DISTINCTNESS_CEILING,
            "null_ceiling": NULL_CEILING,
            "retention_share": RETENTION_SHARE,
            "release_share": RELEASE_SHARE,
            "persist_share": PERSIST_SHARE,
            "trans_share": TRANS_SHARE,
            "clock_tolerance": CLOCK_TOLERANCE,
            "nu_tolerance": NU_TOLERANCE,
            "counterfactual_factor": COUNTERFACTUAL_FACTOR,
            "restored_share_ceiling": RESTORED_SHARE_CEILING,
            "anchor_oracle_tolerance": ANCHOR_ORACLE_TOLERANCE,
            "domain_chi_floor": DOMAIN_CHI_FLOOR,
            "domain_exterior_ceiling": DOMAIN_EXTERIOR_CEILING,
            "probe_tol": PROBE_TOL,
            "replication_tol": REPLICATION_TOL,
        },
        "declared_point": {"kappa_entry": ENTRY_KAPPA, "exchange_entry": ENTRY_EXCHANGE,
                           "loop_entry": ENTRY_LOOP, "predicted_nullity": 2,
                           "exchange_free": EXCHANGE_FREE,
                           "exchange_spent": EXCHANGE_SPENT,
                           "delta_carrier": DELTA_CARRIER,
                           "delta_orientation": DELTA_ORIENTATION,
                           "kernel_labels_free": list(KERNEL_LABELS_FREE),
                           "kernel_labels_spent": list(KERNEL_LABELS_SPENT)},
        "arm_table": [{"name": spec.name, "index": spec.index, "role": spec.role,
                       "load_transfer": spec.load_c, "exchange": spec.exchange,
                       "plan": [list(pair) for pair in spec.plan],
                       "baseline": spec.baseline} for spec in ARM_TABLE],
        "arms": arms,
        "displacements": {name: displacements[name] for name in LOADED_ARMS
                          + ("ray_write_N",)},
        "preflight": preflight,
        "domain": domain,
        "spectrum": spectrum,
        "replication": replication_record,
        "clock": clock,
        "clock_read": clock_read,
        "decision": decision,
        "features": features,
        "gates": gates,
        "budget": budget,
        "status": status,
        "runtime_seconds": time.time() - started,
        "frozen_sources": {key: value["path"] for key, value in binding["rows"].items()},
    }
    return {"receipt": receipt, "status": status, "arms": arms,
            "displacements": displacements, "decision": decision, "gates": gates,
            "features": features, "preflight": preflight, "domain": domain,
            "spectrum": spectrum, "clock": clock, "clock_read": clock_read,
            "budget": budget, "replication": replication_record,
            "probe_check": probe_check}


def execute() -> int:
    started = time.time()
    if receipt_status()["exists"]:
        print("REFUSING TO RUN: {0} already exists; this body is invoked once and a second "
              "invocation is permitted only after an invocation that wrote no receipt."
              .format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    binding = check_binding()
    print("bindings: every section-0 row matches")
    outcome = assemble(build(), binding, started)
    receipt, status = outcome["receipt"], outcome["status"]
    spectrum, domain = outcome["spectrum"], outcome["domain"]
    preflight, decision, gates = (outcome["preflight"], outcome["decision"],
                                  outcome["gates"])
    print("status: " + status)
    print("the declared point: entries {0}, {1}, {2}; predicted dim ker = 2"
          .format(ENTRY_KAPPA, ENTRY_EXCHANGE, ENTRY_LOOP))
    print("nullity at r = 0: {0}; at r = {1}: {2}".format(
        spectrum["free"]["nullity"], EXCHANGE_SPENT, spectrum["spent"]["nullity"]))
    print("domain: declared shapes {0}, spent shapes {1}, loop-only spreads {2} / {3}"
          .format(domain["loop_only"]["declared_shape"],
                  domain["loop_only"]["spent_shape"],
                  domain["loop_only"]["declared_row_spread"],
                  domain["loop_only"]["spent_row_spread"]))
    print("preflight: live D {0}, live N {1}, cross D {2}, cross N {3}, distinct {4}, "
          "null {5}".format(preflight["readings"]["live_D"],
                            preflight["readings"]["live_N"],
                            preflight["readings"]["cross_D"],
                            preflight["readings"]["cross_N"],
                            preflight["readings"]["distinctness"],
                            preflight["readings"]["null"]))
    print("branches: present {0} (standing {1} of predicted {2}), writable {3}, retained "
          "{4}, erasure {5}".format(decision["present"], decision["measured_standing"],
                                    decision["predicted_nullity"], decision["writable"],
                                    decision["retained"], decision["erasure"]))
    print("coordinate retention: " + json.dumps(
        {label: {"share": entry["share"], "movement": entry["final_phase_movement"],
                 "passed": entry["passed"]}
         for label, entry in decision["coordinate_retention"].items()}))
    print("counterfactual: analytic {0}, restored share {1}, unrestored share {2}"
          .format(COUNTERFACTUAL_FACTOR, decision["counterfactual"]["restored_share"],
                  decision["counterfactual"]["unrestored_share"]))
    for row in gates:
        print("gate {0:>2} {1:<58} {2}".format(row["id"], row["name"],
                                               "PASS" if row["passed"] else "FAIL"))
    payload = sanitize(receipt)
    target = os.path.join(ROOT, RECEIPT_PATH)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("receipt: {0} ({1})".format(RECEIPT_PATH, digest_of(RECEIPT_PATH)))
    print("runtime: {0:.1f} s".format(receipt["runtime_seconds"]))
    return EXIT_PASS if status == "PASS" else EXIT_FAIL


def sanitize(value):
    """Strip numpy scalars and refuse a non-finite number before the receipt is written."""
    if isinstance(value, np.ndarray):
        return [sanitize(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number):
            raise SystemExit("refusing to write a non-finite reading: {0}".format(number))
        return number
    if isinstance(value, complex) or isinstance(value, np.complexfloating):
        number = complex(value)
        if not (math.isfinite(number.real) and math.isfinite(number.imag)):
            raise SystemExit("refusing to write a non-finite reading: {0}".format(number))
        return {"real": number.real, "imag": number.imag}
    return value


def dry_run() -> list:
    """Section 4: drive the gate, feature and receipt path on shaped inputs.

    The invocation reaches the gate path only after every arm has been integrated, so a key
    that path reads and its producers do not carry costs a whole invocation to discover.
    This pass builds arms and displacements of the declared shape from one seeded state per
    arm and runs the entire assembly on them. The verdicts it produces are not readings and
    are discarded; any exception, or any departure from the declared shape of the gate
    table, the feature record or the receipt payload, is a static failure.
    """
    failures = []
    arms = {}
    for spec in ARM_TABLE:
        state = gate_load.loaded_seed(spec, base)
        reading = reading_of(state)
        samples = {}
        for position, (key, _) in enumerate(SAMPLES):
            decay = math.exp(-0.01 * (position + 1))
            samples[key] = {
                "even": 1.0e-3 * decay, "odd": 5.0e-4 * decay,
                "even_nonuniform": reading["even_nonuniform"],
                "odd_nonuniform": reading["odd_nonuniform"],
                "scalar": reading["scalar"],
                "ray_distance": max(reading["ray_distance"], 1.0e-3),
                "min_state": reading["min_state"], "max_state": reading["max_state"],
                "q_min": reading["q_min"], "q_max": reading["q_max"],
                "index": position + 1,
            }
        arms[spec.name] = {
            "index": spec.index, "name": spec.name,
            "declared": {"load_transfer": spec.load_c,
                         "plan": [[float(carrier), float(orientation)]
                                  for carrier, orientation in spec.plan],
                         "exchange": spec.exchange, "baseline": spec.baseline},
            "schedule": {"dt": DECLARED_DT, "steps": 1, "horizon": DECLARED_DT,
                         "phases": len(spec.plan), "rule_conformant": True},
            "load": gate_load.load_comparison(spec, gate_load.load_of(state, base)),
            "clock": {"stride": CLOCK_STRIDE, "stride_units": CLOCK_STRIDE * DECLARED_DT,
                      "values": [1.0e-3 * math.exp(-0.01 * index)
                                 for index in range(T1_INDEX // CLOCK_STRIDE + 3)],
                      "steps": [index * CLOCK_STRIDE
                                for index in range(T1_INDEX // CLOCK_STRIDE + 3)]},
            "samples": samples,
        }
    built = {"arms": arms, "preflight": action_preflight(), "domain": domain_probe()}
    binding = {"declared": {"frozen_body_sha256": FROZEN_BODY_DIGEST,
                            "executor_sha256": protocol_row("executor_sha256")},
               "observed": {}, "rows": {}}
    try:
        outcome = assemble(built, binding, time.time())
        payload = sanitize(outcome["receipt"])
    except Exception as error:  # noqa: BLE001 - any failure here is a static failure
        failures.append("the gate, feature and receipt path fails on shaped inputs: "
                        "{0}: {1}".format(type(error).__name__, error))
        return failures
    if len(outcome["gates"]) != 14:
        failures.append("the gate table carries {0} rows, not 14".format(
            len(outcome["gates"])))
    expected_features = set(["F{0}_{1}".format(position, name) for position, name in
                             ((1, "can_fail_fired"), (2, "ray_silent"),
                              (3, "anchor_readable"), (4, "preflight_live_D"),
                              (5, "preflight_live_N"), (6, "preflight_cross_D"),
                              (7, "preflight_cross_N"), (8, "preflight_distinct"),
                              (9, "ray_identity"), (10, "predicted_nullity"),
                              (11, "measured_standing"), (12, "retained_D"),
                              (13, "retained_N"), (14, "counterfactual_measured"),
                              (15, "erased_odd"), (16, "first_stands"))])
    expected_features |= {"present", "writable", "retained", "erasure"}
    if set(outcome["features"]) != expected_features:
        failures.append("the feature record carries {0}, not the declared 20".format(
            sorted(outcome["features"])))
    labels = {"present": PRESENT_LABELS, "writable": WRITABLE_LABELS,
              "retained": RETAINED_LABELS, "erasure": ERASURE_LABELS}
    for key, allowed in labels.items():
        if outcome["decision"][key] not in allowed:
            failures.append("branch {0} is {1}, not one of the declared labels".format(
                key, outcome["decision"][key]))
    if payload.get("status") not in ("PASS", "FAIL"):
        failures.append("the receipt payload carries no status")
    if payload.get("schema") != RECEIPT_SCHEMA:
        failures.append("the receipt payload carries the wrong schema")
    return failures


def self_check() -> int:
    """Static, derivation and pre-flight checks. Writes nothing; safe to run again."""
    failures = []
    check_binding()
    state = gate_load.loaded_seed(ARM_TABLE[1], base)
    rate = split.gate_rate_of(state, base)

    # Section 1.3: the carrier channel at the spent point is the spent direction-A line.
    mine = kernel_rhs(state, rate, CARRIER_D, EXCHANGE_SPENT, DELTA_CARRIER, 0.0)
    theirs = spent.write_rhs(state, rate, (1.0, 0.0), base, DELTA_CARRIER)
    if not np.array_equal(mine, theirs):
        failures.append("the carrier channel is not the spent direction-A right-hand side "
                        "term for term; max difference {0}".format(
                            float(np.max(np.abs(mine - theirs)))))
    zero = kernel_rhs(state, rate, NO_WRITE, EXCHANGE_FREE)
    unmodulated = (
        -base.U * base.frozen.derivative(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        + base.D_X * base.frozen.laplacian(state, base.EXTERIOR_AXIS, base.EXTERIOR_DX)
        - base.SIGNS * base.OMEGA * base.frozen.derivative(state, base.LOOP_AXIS,
                                                           base.loop_dx(state.shape[
                                                               base.LOOP_AXIS]))
        + base.D_LOOP * base.frozen.laplacian(state, base.LOOP_AXIS,
                                              base.loop_dx(state.shape[base.LOOP_AXIS]))
    )
    unmodulated[0] += rate * (-state[0] + base.PHI * state[1])
    unmodulated[1] += rate * (state[0] - base.PHI * state[1])
    if not np.array_equal(zero, unmodulated):
        failures.append("the no-write channel is not the bare (LB6) conversion line")

    # Section 1.3: the counter phase reverses the orientation channel relative to N's own
    # phase and applies no carrier channel, so the change against N is -2 and 0.
    before = np.array(ORIENTATION_N)
    counter = np.array(COUNTER_N)
    if not (counter[1] - before[1] == -2.0 and counter[0] - before[0] == 0.0):
        failures.append("the counter phase is not the declared -2 and 0 change against N")

    # Section 1.2: the declared reader is the exterior mean and the profile carries 24
    # loop samples; the spent reader does not.
    profile = declared_profile(state)
    if profile.shape != (2, N_CHI):
        failures.append("the declared profile is not (2, {0}): {1}".format(
            N_CHI, profile.shape))
    if spent_profile(state).shape != (2, base.frozen.NX):
        failures.append("the spent reader does not read {0} coordinates: {1}".format(
            base.frozen.NX, spent_profile(state).shape))

    # Section 2.3 and section 6: every declared threshold agrees with the protocol row, and
    # the step rule holds on every arm.
    declared = {
        "readable_floor_q": READABLE_FLOOR_Q, "silence_floor_q": SILENCE_FLOOR_Q,
        "action_floor_live": ACTION_FLOOR_LIVE,
        "cross_ratio_ceiling": CROSS_RATIO_CEILING,
        "cross_share_ceiling": CROSS_SHARE_CEILING,
        "distinctness_ceiling": DISTINCTNESS_CEILING, "null_ceiling": NULL_CEILING,
        "retention_share": RETENTION_SHARE, "release_share": RELEASE_SHARE,
        "persist_share": PERSIST_SHARE, "trans_share": TRANS_SHARE,
        "clock_tolerance": CLOCK_TOLERANCE, "nu_tolerance": NU_TOLERANCE,
        "counterfactual_factor": COUNTERFACTUAL_FACTOR,
        "restored_share_ceiling": RESTORED_SHARE_CEILING,
        "anchor_oracle_tolerance": ANCHOR_ORACLE_TOLERANCE,
        "domain_chi_floor": DOMAIN_CHI_FLOOR,
        "domain_exterior_ceiling": DOMAIN_EXTERIOR_CEILING, "probe_tol": PROBE_TOL,
        "replication_tol": REPLICATION_TOL,
        "delta_carrier": DELTA_CARRIER, "delta_orientation": DELTA_ORIENTATION,
    }
    for key, value in declared.items():
        try:
            declared_value = declared_number(key)
        except SystemExit as error:
            failures.append(str(error))
            continue
        if declared_value != value:
            failures.append("threshold {0}: executor {1} != protocol {2}".format(
                key, value, declared_value))
    for spec in ARM_TABLE:
        limit = 1.0 / (STEP_SAFETY * kernel_lambda_max(spec))
        if DECLARED_DT > limit:
            failures.append("arm {0}: dt {1} exceeds the rule's {2}".format(
                spec.name, DECLARED_DT, limit))

    # Section 5: the closed form's entries at the declared point, read from the operators.
    entries = audit.entries(ENTRY_KAPPA / (1.0 + base.PHI), base.PHI, EXCHANGE_FREE,
                            base.OMEGA, base.D_LOOP)
    if abs(entries["kappa_entry"] - ENTRY_KAPPA) > 1e-15:
        failures.append("the kappa entry disagrees with the declared value: {0}".format(
            entries["kappa_entry"]))
    if abs(entries["exchange_entry"]) != 0.0:
        failures.append("the exchange entry does not vanish: {0}".format(
            entries["exchange_entry"]))
    if abs(entries["loop_entry"] - ENTRY_LOOP) > 1e-15:
        failures.append("the loop entry disagrees with the declared value: {0}".format(
            entries["loop_entry"]))

    # Section 2.4 and the abstract: the declared prediction, read from the frozen generator
    # at r = 0 and at the spent point. This is a derivation check, not a result: it is the
    # arithmetic the protocol's prediction is written from, and the run gates on it too.
    free = kernel_check(EXCHANGE_FREE)
    spent_point = kernel_check(EXCHANGE_SPENT)
    if free["nullity"] != 2:
        failures.append("dim ker at r = 0 is {0}, not the declared 2".format(
            free["nullity"]))
    if spent_point["nullity"] != 1:
        failures.append("dim ker at r = {0} is {1}, not the spent body's 1".format(
            EXCHANGE_SPENT, spent_point["nullity"]))
    if not (free["symmetric_dimension"] == 1 and free["antisymmetric_dimension"] == 1):
        failures.append("the r = 0 kernel labels are {0} symmetric and {1} antisymmetric, "
                        "not one of each".format(free["symmetric_dimension"],
                                                 free["antisymmetric_dimension"]))
    if not (spent_point["symmetric_dimension"] == 1
            and spent_point["antisymmetric_dimension"] == 0):
        failures.append("the spent point's kernel is not the symmetric direction alone")
    if free["kernel_residual"] > KERNEL_SPAN_TOL:
        failures.append("the r = 0 kernel direction's carrier residual is {0}".format(
            free["kernel_residual"]))

    # Section 1.4.3: the two declared-shaped probes separate the readers.
    domain = domain_probe()
    if not domain["reader_is_not_the_spent_reader"]:
        failures.append("the declared reader is the spent reader on the loop-only probe")
    if not domain["declared_shapes_24"]:
        failures.append("the declared reader does not read {0} loop samples".format(N_CHI))
    if domain["loop_only"]["declared_row_spread"] < DOMAIN_CHI_FLOOR:
        failures.append("the loop-only probe reads {0} < {1} on the declared reader".format(
            domain["loop_only"]["declared_row_spread"], DOMAIN_CHI_FLOOR))
    if domain["exterior_only"]["declared_row_spread"] > DOMAIN_EXTERIOR_CEILING:
        failures.append("the exterior-only probe reads {0} > {1} on the declared reader"
                        .format(domain["exterior_only"]["declared_row_spread"],
                                DOMAIN_EXTERIOR_CEILING))
    if not domain["chi_uniform_identity"]:
        failures.append("the two readers do not agree on the chi-uniform probe: mean "
                        "difference {0}".format(domain["chi_uniform_mean_difference"]))

    # Section 4: the gate, feature and receipt path, driven on shaped inputs. This is the
    # path the invocation reaches only after every arm is integrated, so it is checked here
    # rather than discovered at the end of a paid run.
    failures.extend(dry_run())

    if failures:
        print("STATIC CHECK FAILED")
        for line in failures:
            print("  " + line)
        return EXIT_STATIC_CHECK
    print("static check: bindings, the two gate channels, the declared reader, the "
          "threshold rows, the step rule, the declared point's entries and the gate, "
          "feature and receipt path all agree")
    return EXIT_PASS


def design_probe() -> int:
    """Section 1.5: the readings the declared floors, bands and bounds are chosen against."""
    check_binding()
    preflight = action_preflight()
    print("preflight readings (fractions of the step's drift {0}):".format(
        preflight["drift"]))
    for key, value in sorted(preflight["readings"].items()):
        print("  {0}: {1!r}".format(key, value))
    print("preflight checks: {0}".format(preflight["checks"]))
    print("load: {0}".format(preflight["load"]))
    arms = {spec.name: arm_record(spec) for spec in ARM_TABLE}
    displacements = {name: displacement_record(arms, name) for name in arms}
    for name in ("ray_anchor", "load_reference", "restored_anchor", "write_D", "write_N",
                 "write_N_restored", "joint_DN", "erase_N", "ray_write_N"):
        row = []
        for key in READ_KEYS:
            row.append("{0}:{1:+.6e}/{2:+.6e}".format(
                key, displacements[name]["groups"][key]["even"]["displacement"],
                displacements[name]["groups"][key]["odd"]["displacement"]))
        print("  {0:<18} {1}".format(name, "  ".join(row)))
    print("design-probe readings in PROBE_READING_ORDER:")
    values = []
    for path in PROBE_READING_ORDER:
        name, group, key = path.split(":")
        values.append(displacements[name]["groups"][key][group]["displacement"])
    for path, value in zip(PROBE_READING_ORDER, values):
        print("  {0:<28} {1!r}".format(path, value))
    print("PROBE_READINGS = ({0})".format(
        ",\n".join("    {0!r}".format(value) for value in values)))
    print("retention fits:")
    for label, name, group in (("D", "write_D", "even"), ("N", "write_N", "odd"),
                               ("N_restored", "write_N_restored", "odd")):
        fit = group_fit(arms, name, group)
        print("  {0}: held {1}, free {2}, values {3}".format(
            label, fit["held"]["rate"], fit["free"]["rate"], fit["values"]))
    print("domain probes: {0}".format(json.dumps(domain_probe(), indent=1)))
    free = kernel_check(EXCHANGE_FREE)
    spent_point = kernel_check(EXCHANGE_SPENT)
    print("spectra: r = 0 nullity {0} (symmetric {1}, antisymmetric {2}, residual {3}); "
          "r = {4} nullity {5} (symmetric {6}, antisymmetric {7})".format(
              free["nullity"], free["symmetric_dimension"],
              free["antisymmetric_dimension"], free["kernel_residual"], EXCHANGE_SPENT,
              spent_point["nullity"], spent_point["symmetric_dimension"],
              spent_point["antisymmetric_dimension"]))
    print("declared entries: {0}".format(json.dumps(
        audit.entries(ENTRY_KAPPA / (1.0 + base.PHI), base.PHI, EXCHANGE_FREE, base.OMEGA,
                      base.D_LOOP), indent=1)))
    anchor_clock = arms["load_reference"]["clock"]
    clock = prior.clock_of(anchor_clock["values"], anchor_clock["stride_units"],
                           T1_INDEX // CLOCK_STRIDE, len(anchor_clock["values"]) - 1)
    print("clock on the loaded anchor: {0}".format(json.dumps(clock, indent=1)))
    print("declared rate: {0}".format(NU_REFERENCE))
    print("replication: {0}".format(json.dumps(replication(arms), indent=1)))
    print("decision: {0}".format(json.dumps(decide(arms, displacements, preflight,
                                                   domain_probe(),
                                                   {"free": kernel_check(EXCHANGE_FREE),
                                                    "spent": kernel_check(EXCHANGE_SPENT)}),
                                          indent=1)))
    print("step rule:")
    for spec in ARM_TABLE:
        limit = 1.0 / (STEP_SAFETY * kernel_lambda_max(spec))
        print("  {0:<18} exchange {1} lambda_max {2:.6e} limit {3:.6f} dt {4}".format(
            spec.name, spec.exchange, kernel_lambda_max(spec), limit, DECLARED_DT))
    return EXIT_PASS


def freeze() -> int:
    """Print the two digests and the section-0 rows the freeze pass pastes in."""
    print("| `frozen_body_sha256` | `{0}` | this file, sections 1-7 |".format(
        protocol_body_digest()))
    print("| `executor_sha256` | `{0}` | {1} |".format(digest_of(PROBE_PATH), PROBE_PATH))
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--static", action="store_true",
                        help="run the static and derivation checks and write nothing")
    parser.add_argument("--design-probe", action="store_true",
                        help="print the readings the declared floors are chosen against")
    parser.add_argument("--freeze", action="store_true",
                        help="print the two section-0 digests")
    arguments = parser.parse_args(argv)
    selected = [arguments.static, arguments.design_probe, arguments.freeze]
    if sum(1 for flag in selected if flag) > 1:
        print("choose at most one of --static, --design-probe, --freeze")
        return EXIT_ARGUMENTS
    if arguments.static:
        return self_check()
    if arguments.design_probe:
        return design_probe()
    if arguments.freeze:
        return freeze()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
