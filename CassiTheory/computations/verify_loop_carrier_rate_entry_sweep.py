"""Is the retained coordinate's decay rate the gap entry, all the way through the crossing?

The two-coordinate body declared one vanishing gap entry at `r = 0`, predicted `dim ker = 2`
before its run and measured two retained coordinates with independent injectors. Its retention
reading, however, is a verdict taken *at* the crossing -- and a vanished gap entry *is* a zero
decay rate, so standing still over a declared window cannot separate permanent storage from a
window that happens to be short. This body takes the non-tautological form of the same question.

The dialled coefficient is the exchange `r` of (LB42), whose entry in (LB39) is `2r`. The sweep
declares points on **both sides** of the crossing plus the crossing itself,
`r in {-0.0100, -0.0050, -0.0025, 0.0, 0.0025, 0.0050, 0.0100}` with entries
`2r in {-0.02, -0.01, -0.005, 0, 0.005, 0.01, 0.02}`, seeds every point off equilibrium, and
reports at every point the **fitted decay rate of the declared coordinate against its entry**,
read with one declared estimator over one declared window, published beside the **window's own
clock** -- the same estimator applied to a companion arm whose rate is the conversion entry
`kappa (1 + phi)` of (LB39), independent of `r`. The measurement is a rate that goes to zero
linearly in the entry across the range; a verdict taken where the entry is zero by construction
is not.

**Why the sweep can be exact and still measure something.** The declared seed is the frozen
`on_ray` family in its chi-uniform, exterior-flat restriction,

    f_{a,s}(x, chi) = (E_a / 2) (1 + s beta),   E_Y : E_I = phi : 1,

whose two carriers are in the equilibrium ratio, so `epsilon = e_Y - phi e_I` vanishes *pointwise*
and the conversion term of (LB6) vanishes identically. The loop and exterior transports vanish
because the state is uniform, the gate rate is therefore the same scalar at every cell, and the
whole evolution is the frozen generator's own four-vector `(Y_up, Y_down, I_up, I_down)`. The
frozen generator is a Kronecker sum -- `conversion` on the carrier axis, `direction` on the
orientation axis -- so its spectrum is {0, -2r, -k(1+phi), -k(1+phi)-2r} and the seed's imbalance
lies exactly on `u_0 (x) v_1`: the orientation-antisymmetric, equilibrium-ratio direction, whose
eigenvalue is `-2r` alone. The *state* therefore decays exactly at the entry, at every point.

What the sweep measures is not that identity but the **declared coordinate**: the frozen bounded
composition `q = rho^2 / (rho^2 + phi^-2 + epsilon^2)`, whose odd-in-the-orientation group is a
*nonlinear* function of the imbalance. Its fitted rate is `2r` times a correction of order
`beta^2`, and the sweep asks whether that rate equals the entry across both signs, at every
declared point, with the fit's own readings -- residual, sign constancy, readability -- beside it.
A flat rate, a one-sided collapse, or a rate that tracks the entry only where the entry was
already known is the finding if it occurs, and the four branch labels record which.

**The injector's law, measured rather than inferred.** The two-coordinate body read `RESIDUAL` on
its erasure branch: the reversed orientation channel removed 0.66% of what it wrote, so the
coordinate's drive is not an inverse. This body drives the declared orientation channel from the
same loaded seed at two declared points with a **sign-reversed pair**, reports the response's
even and odd parts (even = invariant under the drive's sign reversal, odd = the part that flips),
and adds the same three-phase reversal the two-coordinate body used, so the fraction a reversed
channel removes is read at this body's own points and reported beside the 0.66%. The law is stated
in one sentence in section 8 whatever it turns out to be: a coordinate whose drive sets only the
*magnitude* of a rate is a monotone store, and every design downstream needs that stated.

**The reading domain is the two-coordinate body's declared one, proved again here.** The reader is
re-implemented in this file as the mean over the exterior axis of the pointwise composition,
indexed by the loop sample; the three declared-shaped probes are rebuilt and both this reader and
the spent one are read through them, and this body's reading must be *bit-equal* to the
two-coordinate body's on all three, so the transposition the spent protocol reported cannot recur
in this body either.

Run once: `timeout 600 python computations/verify_loop_carrier_rate_entry_sweep.py`.
`--static` checks without writing, including a shaped-input pass through the whole gate, feature
and receipt path; `--design-probe` prints the readings the declared floors and bands are chosen
against; `--freeze` prints the two section-0 digests.
"""
import argparse
import hashlib
import json
import math
import os
import re
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# The spent chain is imported as a library, as the two-coordinate body imported it, plus that body
# itself: its declared reader, its kernel check and its domain probes are the instruments this
# sweep re-reads rather than re-derives.
import verify_loop_carrier_attractor_write as prior  # noqa: E402
import verify_loop_carrier_composition_coexistence as spent  # noqa: E402
import verify_loop_carrier_gate_load as gate_load  # noqa: E402
import verify_loop_carrier_projection_split as split  # noqa: E402
import verify_loop_carrier_two_coordinates as two_coord  # noqa: E402

# Section 0: the bound sources. Every row is a file whose bytes this executor reads, hashes and
# refuses on; none is a running process.
BOUND_MODULE = gate_load.BOUND_MODULE
BASE_PROBE = gate_load.BASE_PROBE
SPLIT_EXECUTOR = gate_load.SPLIT_EXECUTOR
GATE_LOAD_EXECUTOR = gate_load.PROBE_PATH
SPENT_EXECUTOR = spent.PROBE_PATH
AUDIT_EXECUTOR = two_coord.AUDIT_EXECUTOR
WRITE_EXECUTOR = two_coord.WRITE_EXECUTOR
TWO_COORD_EXECUTOR = two_coord.PROBE_PATH
TWO_COORD_BODY = two_coord.PROTOCOL_PATH
BASE_RECEIPT = gate_load.BASE_RECEIPT
SPLIT_RECEIPT = gate_load.SPLIT_RECEIPT
GATE_LOAD_RECEIPT = gate_load.RECEIPT_PATH
PRIOR_RECEIPT = prior.RECEIPT_PATH
SPENT_RECEIPT = spent.RECEIPT_PATH
TWO_COORD_RECEIPT = two_coord.RECEIPT_PATH

PROTOCOL_PATH = "computations/loop-carrier-rate-entry-sweep-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_rate_entry_sweep.py"
RECEIPT_PATH = "runs/loop_carrier_rate_entry_sweep/verification.json"
FIRST_INVOCATION_RECEIPT = "runs/loop_carrier_rate_entry_sweep/first-invocation-verification.json"
FIRST_INVOCATION_RECEIPT_SHA256 = (
    "cdfb45468af1ebdcf1bfc21828f78a502d396c9dd484251114814db340dcd6ec")
INVOCATION = "timeout 600 python computations/verify_loop_carrier_rate_entry_sweep.py"
RECEIPT_SCHEMA = "cassi.loop-carrier-rate-entry-sweep.v1"
BOUND_SECONDS = 600.0

# Section 0 declares both hashes: this file's, and the digest of the frozen body (everything from
# "## 1." to just before "## 8."). Filled by the freeze pass.
FROZEN_BODY_DIGEST = "FILLED_AT_FREEZE"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.3: the declared thresholds. Everything the chain fixes is carried unchanged; the ones
# this body adds are the entry band, the crossing ceiling, the flat ceiling, the fit's own quality
# ceiling, the seed-content floor, the injector ceiling, the erase band and the step modes.
READABLE_FLOOR_Q = 1.0e-12
ENTRY_TOL_RELATIVE = 1.0e-2
ENTRY_ZERO_CEILING = 1.0e-6
FLAT_CEILING = 1.0e-4
FIT_RESIDUAL_CEILING = 2.0e-2
FIT_MIN_SAMPLES = 4
CLOCK_TOLERANCE = prior.CLOCK_TOLERANCE
CANFAIL_BAND_RELATIVE = 1.0e-3
CANFAIL_FLOOR = 1.0
RAY_READABLE_FLOOR = spent.RAY_READABLE_FLOOR
SEED_CONTENT_CEILING = 1.0e-12
SEED_EPSILON_CEILING = 1.0e-14
INJECTOR_EVEN_CEILING = 5.0e-2
LOAD_TRANSFER_TOL = 1.0e-13
PROBE_TOL = 1.0e-12
REPLICATION_TOL = 1.0e-15
KERNEL_TOL = 1.0e-10
KERNEL_SPAN_TOL = 1.0e-9
SPECTRUM_MULTISET_TOL = 1.0e-12
DOMAIN_CHI_FLOOR = 1.0e-3
DOMAIN_EXTERIOR_CEILING = 1.0e-15
STEP_SAFETY = split.STEP_SAFETY
STEP_CANDIDATES = split.STEP_CANDIDATES
DECLARED_DT = 0.02
N_CHI = 24
STEP_MODES = (0, 1)

# Section 1.2: the declared seed and its two magnitudes. The seed's densities are the frozen
# `on_ray` profile's own, without any exterior or loop modulation, so the sweep's arms excite only
# the frozen generator's uniform four-vector; the imbalance is applied with the same factor on both
# carriers, which is what puts its antisymmetric content on the declared direction; the load is the
# chain's declared transfer at a magnitude ten times below its largest, chosen so that the window's
# clock stays within one per cent of the conversion entry.
BETA = 0.01
LOAD_C = 0.02
LOADED_ARM_LOAD = gate_load.LARGEST_LOAD
DRIVE_DELTA = two_coord.DELTA_ORIENTATION
DRIVE_PLUS = (0.0, 1.0)
DRIVE_MINUS = (0.0, -1.0)
NO_DRIVE = (0.0, 0.0)

# Section 1.1.1: the declared points, their entries of (LB39), and the schedule every sweep arm
# shares. The entry is `2r` and is read at run time from the frozen closed spectrum rather than
# typed here; the table below is the declaration it is checked against.
EXCHANGE_POINTS = (-0.0100, -0.0050, -0.0025, 0.0, 0.0025, 0.0050, 0.0100)
ENTRY_VALUES = tuple(2.0 * value for value in EXCHANGE_POINTS)
CANFAIL_EXCHANGE = 0.5
CANFAIL_ENTRY = 2.0 * CANFAIL_EXCHANGE
WITNESS_EXCHANGE = 0.25
WITNESS_ENTRY = 2.0 * WITNESS_EXCHANGE
INJECTOR_POINTS = (0.0, -0.0100)
WINDOW_UNITS = 150.0
WINDOW_STEPS = 7500
SAMPLE_STRIDE = 250
SHORT_UNITS = 5.0
SHORT_STEPS = 250
SHORT_STRIDE = 25
PHASE_STEPS = 2500
CHANNEL_PHASE_STEPS = 2500
ENTRY_EXCHANGE = 0.0
EXCHANGE_SPENT = two_coord.EXCHANGE_SPENT
KAPPA_MODE_ZERO = two_coord.ENTRY_KAPPA / (1.0 + two_coord.base.PHI)
CONVERSION_ENTRY_DECLARED = two_coord.ENTRY_KAPPA
CONVERSION_CLOCK_ORACLE = prior.NU_REFERENCE
# Section 5: the two-coordinate receipt's own zero-rate oracle. Its r = 0 retention stood over a
# 450-unit window at this share, which no rate larger than the derived bound can produce.
TWO_COORD_RETAINED_SHARE = 0.9999998175949137
TWO_COORD_CHANNEL_WINDOW = 450.0
TWO_COORD_ERASE_RESIDUAL = 0.0066
PER_EXECUTION_CAP = 10000
TOTAL_STEP_CAP = 250000
DECLARED_EXECUTIONS = 29
SECONDS_PER_STEP_MEASURED = 1.195e-3
PROJECTED_SECONDS_MEASURED = 245.0
PROJECTED_SECONDS_ASSUMED = 170.0

KERNEL_LABELS_FREE = two_coord.KERNEL_LABELS_FREE
KERNEL_LABELS_SPENT = two_coord.KERNEL_LABELS_SPENT

GROUPS = ("even", "odd")
RATE_LABELS = ("LINEAR_BOTH_SIDES", "FLAT", "ONE_SIDE_ONLY", "INCONCLUSIVE")
INJECTOR_LABELS = ("EVEN_IN_SIGN", "SIGN_DEPENDENT", "RESERVED_NO_RESPONSE")

# Section 1.5: the design probe's declared readings, in the order of PROBE_READING_ORDER, fixed
# against the probe's own run before the freeze; gate 7 checks the invocation reproduces them.
PROBE_READING_ORDER = (
    "entry@-0.0100:rate", "entry@-0.0050:rate", "entry@-0.0025:rate", "entry@+0.0000:rate",
    "entry@+0.0025:rate", "entry@+0.0050:rate", "entry@+0.0100:rate",
    "entry@-0.0100:odd_initial", "entry@-0.0025:odd_initial", "entry@+0.0025:odd_initial",
    "entry@+0.0100:odd_initial",
    "clock@-0.0100:rate", "clock@+0.0000:rate", "clock@+0.0100:rate",
    "canfail@+0.5000:rate", "witness@+0.2500:rate",
    "inject@+0.0000:even_part", "inject@+0.0000:odd_part",
    "inject@-0.0100:even_part", "inject@-0.0100:odd_part",
    "inject@+0.0000:erase_fraction", "inject@-0.0100:erase_fraction",
)
PROBE_READINGS = (
    -0.020087210596378125, -0.010005319983069205, -0.005001058250020064,
    2.4880630605367724e-17, 0.005000236194936966, 0.010000265174148837,
    0.02000022063745508,
    0.004390337204869366, 0.004390337204869366, 0.004390337204869366,
    0.004390337204869366,
    0.011282357172592223, 0.011282357172592223, 0.011282357172592223,
    1.0000059865642859, 0.5000075974138588,
    0.0, -0.0014358387617779411,
    0.0, -0.012646830210309101,
    0.7715799746327933, 0.3690299651437342,
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
    ("write_executor_sha256", WRITE_EXECUTOR,
     "740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6"),
    ("two_coordinate_executor_sha256", TWO_COORD_EXECUTOR,
     "671e4a5edbe406f6c1f932d855987d5cc746315b10c13f387291bf15cbf778f0"),
    ("two_coordinate_receipt_sha256", TWO_COORD_RECEIPT,
     "46ae3ee2b93051277c6e1c86dce4c713fb3b397d74cb06c2559ff8e7b98f344e"),
    ("base_receipt_sha256", BASE_RECEIPT,
     "3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1"),
    ("split_receipt_sha256", SPLIT_RECEIPT,
     "559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc"),
    ("gate_load_receipt_sha256", GATE_LOAD_RECEIPT,
     "471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1"),
    ("prior_receipt_sha256", PRIOR_RECEIPT,
     "5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200"),
    ("first_invocation_receipt_sha256", FIRST_INVOCATION_RECEIPT,
     FIRST_INVOCATION_RECEIPT_SHA256),
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
    text = protocol_text()
    start = re.search(BODY_START, text)
    end = re.search(BODY_END, text)
    if start is None or end is None or end.start() <= start.start():
        raise SystemExit("the protocol does not carry both section headings")
    return hashlib.sha256(text[start.start():end.start()].encode("utf-8")).hexdigest()


def protocol_row(key: str) -> str:
    """Read one `| `key` | value |` row of the protocol's declared tables."""
    pattern = re.compile(r"\|\s*`" + re.escape(key) + r"`\s*\|\s*([^|]+?)\s*\|")
    match = pattern.search(protocol_text())
    if match is None:
        raise SystemExit("the protocol does not declare a row for {0}".format(key))
    return match.group(1).strip().strip("`")


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
    two_coord_body = two_coord.protocol_body_digest()
    observed["two_coordinate_body_sha256"] = {"path": TWO_COORD_BODY,
                                              "expected": two_coord.FROZEN_BODY_DIGEST,
                                              "observed": two_coord_body}
    if two_coord_body != two_coord.FROZEN_BODY_DIGEST:
        failures.append("two_coordinate_body_sha256: {0} != {1}".format(
            two_coord_body, two_coord.FROZEN_BODY_DIGEST))
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
    if failures:
        print("REFUSING TO RUN: source binding failed")
        for line in failures:
            print("  " + line)
        print("The probe reads the frozen operators rather than reimplementing them and fails "
              "closed if any bound file changes.")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    return {"declared": {"frozen_body_sha256": declared_body,
                         "executor_sha256": declared_executor},
            "observed": {key: value["observed"] for key, value in observed.items()},
            "rows": observed}


def load_modules():
    """Import the chain's machinery through the spent executors' own loader."""
    try:
        return gate_load.load_modules()
    except SystemExit:
        print("REFUSING TO RUN: the chain's own binding of the frozen operators failed")
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)


base = load_modules()
PHI = base.PHI
PROFILE = split.PROFILE


def frozen_profiles() -> tuple:
    """Section 1.2: the declared seed's two densities, read from the frozen profile table."""
    gamma, iota = base.PROFILES[PROFILE]
    return float(gamma), float(iota)


def declared_profile(state: np.ndarray) -> np.ndarray:
    """Section 1.4: mean over the exterior axis, indexed by the loop sample.

    The composition of the carriers carries three axes -- orientation, exterior, loop -- so the
    declared reduction is the mean over index 1 and the reading is indexed by the loop sample
    k = 0..23. This is the reduction the spent protocol declared, the spent executor transposed
    and the two-coordinate body restored.
    """
    composition = base.frozen.bounded_q(state[0], state[1])
    return composition.mean(axis=1)


def spent_profile(state: np.ndarray) -> np.ndarray:
    """The spent executor's own reduction, carried only to be refused."""
    return spent.composition_profile(state, base)


def groups_of(profile: np.ndarray) -> tuple:
    """The field's own partition of the reading domain: even and odd in the orientation."""
    return 0.5 * (profile[0] + profile[1]), 0.5 * (profile[0] - profile[1])


def reading_of(state: np.ndarray) -> dict:
    """Every declared reading of one state: both groups, their uniform content, the nonuniform
    remainders, the scalar identity and the ray distance."""
    profile = declared_profile(state)
    even, odd = groups_of(profile)
    return {
        "even": float(np.mean(even)),
        "odd": float(np.mean(odd)),
        "even_vector": even,
        "odd_vector": odd,
        "even_nonuniform": float(np.sqrt(np.sum(np.square(even - np.mean(even))))),
        "odd_nonuniform": float(np.sqrt(np.sum(np.square(odd - np.mean(odd))))),
        "scalar": float(prior.coordinate_of(base.projection(state), base)),
        "ray_distance": float(prior.ray_distance_of(base.projection(state), base)),
        "min_state": float(np.min(state)),
        "max_state": float(np.max(state)),
        "q_min": float(np.min(profile)),
        "q_max": float(np.max(profile)),
    }


class SweepSpec:
    """One declared arm of the sweep: a point, a seed, a drive plan and a schedule.

    The plan is a tuple of per-phase coefficient pairs, each held for `phase_steps` steps; the
    drive's direction is `(0, 1)` (the orientation channel) or `(1, 0)` (the carrier channel), and
    the right-hand side is the two-coordinate body's own `kernel_rhs`, so an arm with no drive runs
    the frozen (LB6) line with the arm's own exchange coefficient.
    """

    def __init__(self, index: int, name: str, role: str, exchange: float,
                 imbalance: float = 0.0, load: float = 0.0, plan: tuple = (),
                 steps: int = WINDOW_STEPS, sample_stride: int = SAMPLE_STRIDE,
                 note: str = ""):
        self.index = index
        self.name = name
        self.role = role
        self.exchange = float(exchange)
        self.imbalance = float(imbalance)
        self.load_c = float(load)
        self.plan = tuple(tuple(coefficients) for coefficients in plan) or (NO_DRIVE,)
        self.steps = int(steps)
        self.sample_stride = int(sample_stride)
        self.note = note
        self.modes = STEP_MODES
        self.phase_steps = (CHANNEL_PHASE_STEPS if len(self.plan) > 1 else self.steps)

    def coefficients(self, index: int) -> tuple:
        return self.plan[min(index // self.phase_steps, len(self.plan) - 1)]

    def declared_schedule(self) -> tuple:
        return DECLARED_DT, self.steps * DECLARED_DT, self.steps

    def peak_factor(self) -> float:
        """The largest modulation factor any phase of the plan applies."""
        return max(1.0 + two_coord.DELTA_CARRIER * abs(carrier)
                   + DRIVE_DELTA * abs(orientation)
                   for carrier, orientation in self.plan)


def build_arm_table() -> tuple:
    """Section 3: the declared arms.

    Per declared point, three arms of the same window: the imbalance arm that carries the entry,
    the load arm that carries the window's clock, and the ray arm that must be bit-identically
    silent because its state is the frozen fixed point. One control at fifty times the largest
    swept entry and one witness at twenty-five times it, both on the short window. Two declared
    points with a sign-reversed driven pair and the three-phase reversal the two-coordinate body
    used, so the fraction a reversed channel removes is read at this body's own points.
    """
    arms = []
    index = 1
    for point in EXCHANGE_POINTS:
        tag = "{0:+.4f}".format(point)
        arms.append(SweepSpec(index, "entry@" + tag, "entry", point, imbalance=BETA,
                              note="entry {0}".format(2.0 * point)))
        index += 1
        arms.append(SweepSpec(index, "clock@" + tag, "clock", point, load=LOAD_C,
                              note="the window's own clock"))
        index += 1
        arms.append(SweepSpec(index, "ray@" + tag, "ray", point,
                              note="the frozen fixed point"))
        index += 1
    arms.append(SweepSpec(index, "canfail@+0.5000", "canfail", CANFAIL_EXCHANGE,
                          imbalance=BETA, steps=SHORT_STEPS, sample_stride=SHORT_STRIDE,
                          note="entry {0}".format(CANFAIL_ENTRY)))
    index += 1
    arms.append(SweepSpec(index, "witness@+0.2500", "witness", WITNESS_EXCHANGE,
                          imbalance=BETA, steps=SHORT_STEPS, sample_stride=SHORT_STRIDE,
                          note="entry {0}".format(WITNESS_ENTRY)))
    index += 1
    for point in INJECTOR_POINTS:
        tag = "{0:+.4f}".format(point)
        arms.append(SweepSpec(index, "inject_plus@" + tag, "inject", point, load=LOAD_C,
                              plan=(DRIVE_PLUS, DRIVE_PLUS, DRIVE_PLUS),
                              note="the drive at its own sign"))
        index += 1
        arms.append(SweepSpec(index, "inject_minus@" + tag, "inject", point, load=LOAD_C,
                              plan=(DRIVE_MINUS, DRIVE_MINUS, DRIVE_MINUS),
                              note="the reversed drive, whole window"))
        index += 1
        arms.append(SweepSpec(index, "erase@" + tag, "erase", point, load=LOAD_C,
                              plan=(DRIVE_PLUS, DRIVE_MINUS, NO_DRIVE),
                              note="the reversed channel after the write"))
        index += 1
    return tuple(arms)


ARM_TABLE = build_arm_table()
ENTRY_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "entry")
CLOCK_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "clock")
RAY_ARMS = tuple(arm.name for arm in ARM_TABLE if arm.role == "ray")
CANFAIL_ARM = "canfail@+0.5000"
WITNESS_ARM = "witness@+0.2500"
SAMPLE_KEYS = tuple(str(step) for step in
                    list(range(0, WINDOW_STEPS + 1, SAMPLE_STRIDE)) + [WINDOW_STEPS])
SHORT_KEYS = tuple(str(step) for step in
                   list(range(0, SHORT_STEPS + 1, SHORT_STRIDE)) + [SHORT_STEPS])


def arm_of(name: str):
    for spec in ARM_TABLE:
        if spec.name == name:
            return spec
    raise KeyError(name)


def entry_arm(point: float) -> str:
    return "entry@{0:+.4f}".format(point)


def clock_arm(point: float) -> str:
    return "clock@{0:+.4f}".format(point)


def ray_arm(point: float) -> str:
    return "ray@{0:+.4f}".format(point)


def sweep_seed(spec: SweepSpec) -> np.ndarray:
    """Section 1.2: the declared seed of one arm.

    `f_{a,s} = (E_a / 2)(1 + s beta)` with `E_a` the frozen `on_ray` densities and no exterior or
    loop modulation, then the chain's own load transfer `f_Y <- f_Y + (c/2) rho`,
    `f_I <- f_I - (c/2) rho` per orientation. The imbalance factor is the *same* on both carriers,
    which is what makes `epsilon = e_Y - phi e_I` vanish to round-off and puts the arm's whole
    antisymmetric content on the declared direction; the transfer is the chain's own and preserves
    the total.
    """
    gamma, iota = frozen_profiles()
    state = np.empty((2, 2, base.N_X, N_CHI), dtype=np.float64)
    for position, factor in enumerate((1.0 + spec.imbalance, 1.0 - spec.imbalance)):
        state[0, position] = (gamma / 2.0) * factor
        state[1, position] = (iota / 2.0) * factor
    if spec.load_c != 0.0:
        total = state[0] + state[1]
        half = spec.load_c / 2.0
        loaded = state.copy()
        loaded[0] = state[0] + half * total
        loaded[1] = state[1] - half * total
        return loaded
    return state


def sweep_step(state: np.ndarray, spec: SweepSpec, step: int) -> np.ndarray:
    """One declared step of one arm: the two-coordinate body's own right-hand side."""
    coefficients = spec.coefficients(step)
    return base.rk4_step(state, DECLARED_DT, lambda current: two_coord.kernel_rhs(
        current, split.gate_rate_of(current, base), coefficients, spec.exchange))


def frozen_step(state: np.ndarray, spec: SweepSpec) -> np.ndarray:
    """The frozen (LB6) line itself, for the static comparison."""
    arm = base.Arm(0, "static", PROFILE, spec.modes, 0.0, "mode", N_CHI, False, spec.exchange,
                   0.0, 0.0, "mode", "", "", False)
    return base.carrier_rhs(state, split.gate_rate_of(state, base), arm)


def kernel_lambda_max(spec: SweepSpec) -> float:
    """The step rule's own lambda_max, on the arm's own exchange and peak gate, over the seed's
    own mode (0) and the chain's declared mode (1) so the rule is not weakened by this body's
    choice of a chi-uniform seed."""
    kappa = base.gate_rate(*base.projection(sweep_seed(spec)))
    peak = float(np.max(kappa)) * spec.peak_factor()
    return float(max(abs(value.real) for mode in spec.modes
                     for value in base.mode_spectrum(mode, peak, spec.exchange)))


def conversion_entry(state: np.ndarray) -> float:
    """Section 1.3: the conversion entry `kappa (1 + phi)` of (LB39) at one state.

    `kappa = LAM (1 - q)` is read from the frozen gate at the state's own projection, so the
    window's clock reference is measured from the frozen machinery and the seed rather than typed.
    """
    return float(np.max(base.gate_rate(*base.projection(state)))) * (1.0 + PHI)


def rate_fit(values: tuple, times: tuple) -> dict:
    """Section 1.5: the one declared estimator, applied to every series this body reads.

    A least-squares slope of `ln|v|` on `t` over the arm's own declared samples, so the reading is
    signed (a decaying coordinate gives a positive rate, a growing one a negative rate) and the
    fit's own quality is reported beside it: the maximum relative departure of the fitted
    exponential from the series, the number of samples above the declared readable floor, and
    whether the series held one sign. A rate is issued only when those conditions hold.
    """
    pairs = [(float(t), float(v)) for t, v in zip(times, values) if abs(v) >= READABLE_FLOOR_Q]
    out = {"samples": len(values), "readable": len(pairs), "rate": None,
           "sign_constant": None, "max_relative_residual": None, "span": None}
    if len(pairs) < FIT_MIN_SAMPLES:
        out["reason"] = "fewer than {0} samples above the readable floor".format(
            FIT_MIN_SAMPLES)
        return out
    signs = {1 if value > 0.0 else -1 for _, value in pairs}
    logarithms = np.array([math.log(abs(value)) for _, value in pairs])
    abscissae = np.array([time_value for time_value, _ in pairs])
    slope, intercept = np.polyfit(abscissae, logarithms, 1)
    rate = -float(slope)
    fitted = np.exp(intercept - rate * abscissae)
    observed = np.array([abs(value) for _, value in pairs])
    residual = float(np.max(np.abs(fitted - observed) / observed))
    out.update({"rate": rate, "sign_constant": len(signs) == 1,
                "max_relative_residual": residual,
                "span": [float(abscissae[0]), float(abscissae[-1])],
                "coefficient": float(math.exp(intercept)),
                "first": float(observed[0]), "last": float(observed[-1])})
    return out


def sample_keys(spec: SweepSpec) -> tuple:
    keys = list(range(0, spec.steps + 1, spec.sample_stride))
    if keys[-1] != spec.steps:
        keys.append(spec.steps)
    return tuple(keys)


def arm_record(spec: SweepSpec) -> dict:
    """One declared arm: its seed, its schedule, its sampled readings and its state digests."""
    state = sweep_seed(spec)
    first_digest = hashlib.sha256(np.ascontiguousarray(state).tobytes()).hexdigest()
    wanted = sample_keys(spec)
    samples = {}
    index = 0
    for step in wanted:
        while index < step:
            state = sweep_step(state, spec, index)
            index += 1
        reading = reading_of(state)
        samples[str(step)] = {name: value for name, value in reading.items()
                              if not name.endswith("_vector")}
        samples[str(step)]["index"] = int(step)
        samples[str(step)]["time"] = step * DECLARED_DT
    last_digest = hashlib.sha256(np.ascontiguousarray(state).tobytes()).hexdigest()
    keys = tuple(str(step) for step in wanted)
    return {
        "index": spec.index,
        "name": spec.name,
        "declared": {
            "exchange": spec.exchange,
            "entry": 2.0 * spec.exchange,
            "imbalance": spec.imbalance,
            "load_transfer": spec.load_c,
            "plan": [[float(carrier), float(orientation)]
                     for carrier, orientation in spec.plan],
            "phase_steps": spec.phase_steps,
            "role": spec.role,
            "note": spec.note,
        },
        "schedule": {"dt": DECLARED_DT, "steps": spec.steps,
                     "horizon": spec.steps * DECLARED_DT,
                     "sample_stride": spec.sample_stride,
                     "samples": len(keys),
                     "rule_conformant": bool(
                         DECLARED_DT <= 1.0 / (STEP_SAFETY * kernel_lambda_max(spec)))},
        "state_sha256_first": first_digest,
        "state_sha256_last": last_digest,
        "sample_keys": keys,
        "samples": samples,
    }


def series_of(arm: dict, field: str) -> tuple:
    keys = arm["sample_keys"]
    values = tuple(float(arm["samples"][key][field]) for key in keys)
    times = tuple(float(arm["samples"][key]["time"]) for key in keys)
    return values, times


def fit_of(arm: dict, field: str) -> dict:
    values, times = series_of(arm, field)
    return rate_fit(values, times)


def seed_content(spec: SweepSpec) -> dict:
    """Section 1.4: where the seed's antisymmetric content lies, in the frozen generator's basis.

    The state's orientation-antisymmetric part per carrier is `A_a = (f_{a,+} - f_{a,-}) / 2`,
    averaged over the exterior and the loop; the declared direction is `w0 = (phi, 1)` -- the
    equilibrium ratio, the conversion block's kernel direction -- and the complementary direction is
    `w1 = (1, -phi)`. The seed is declared to lie on `w0`; the fraction on `w1` is gated, and the
    seed's pointwise epsilon is reported as an exact zero.
    """
    state = sweep_seed(spec)
    antisymmetric = 0.5 * (state[:, 0] - state[:, 1])
    content = antisymmetric.mean(axis=(1, 2))
    w0 = np.array((PHI, 1.0))
    w1 = np.array((1.0, -PHI))
    norm = float(np.linalg.norm(content))
    record = {
        "role": spec.role,
        "load_transfer": spec.load_c,
        "content": [float(value) for value in content],
        "norm": norm,
        "w0_fraction": float(abs(np.dot(content, w0)) / (np.linalg.norm(w0) * max(norm, 1e-300))),
        "w1_fraction": float(abs(np.dot(content, w1)) / (np.linalg.norm(w1) * max(norm, 1e-300))),
        "epsilon_pointwise": float(np.max(np.abs(state[0] - PHI * state[1]))),
        "epsilon_declared": None,
        "epsilon_relative_gap": None,
    }
    if spec.load_c != 0.0:
        unloaded = sweep_seed(SweepSpec(spec.index, spec.name, spec.role, spec.exchange,
                                        imbalance=spec.imbalance, load=0.0, plan=spec.plan,
                                        steps=spec.steps, sample_stride=spec.sample_stride,
                                        note=spec.note))
        predicted = ((unloaded[0] - PHI * unloaded[1])
                     + (spec.load_c / 2.0) * (1.0 + PHI) * (unloaded[0] + unloaded[1]))
        measured = state[0] - PHI * state[1]
        record["epsilon_declared"] = float(np.max(np.abs(predicted)))
        record["epsilon_relative_gap"] = float(
            np.max(np.abs(measured - predicted))
            / max(float(np.max(np.abs(predicted))), 1e-300))
    return record


def kernel_points() -> dict:
    """Section 5: the frozen generator at every declared point.

    The entry `2r` is not typed into the verdict: the closed spectrum is built by the frozen
    operator module, its four values are checked against `{0, -2r, -k(1+phi), -k(1+phi)-2r}`, and
    the kernel's dimension and the direction labels are read from the two-coordinate body's own
    check.
    """
    out = {}
    for point in EXCHANGE_POINTS + (CANFAIL_EXCHANGE, WITNESS_EXCHANGE, EXCHANGE_SPENT):
        record = two_coord.kernel_check(point)
        kappa = record["kappa"]
        expected = sorted([0.0, -2.0 * point, -kappa * (1.0 + PHI),
                           -kappa * (1.0 + PHI) - 2.0 * point])
        observed = sorted(float(value.real) for value in record["closed_spectrum"])
        out["{0:+.4f}".format(point)] = {
            "exchange": point,
            "entry": 2.0 * point,
            "kappa": kappa,
            "expected_entry_values": expected,
            "observed_entry_values": observed,
            "multiset_residual": max(abs(left - right)
                                     for left, right in zip(expected, observed)),
            "numeric_residual": float(record["multiset_residual"]),
            "nullity": int(record["nullity"]),
            "symmetric_dimension": int(record["symmetric_dimension"]),
            "antisymmetric_dimension": int(record["antisymmetric_dimension"]),
            "kernel_residual": float(record["kernel_residual"]),
            "directions": record["directions"],
        }
    return out


def preflight() -> dict:
    """Section 1.4: every reading taken before the arms run.

    The pre-flight reads the seeds' own content, the frozen fixed point of the ray seed, the loaded
    seed's conversion entry (the window's clock reference), the drive's one-step action in both
    directions on the loaded seed, and the admissible step sizes.
    """
    free = arm_of(ENTRY_ARMS[0])
    clock = arm_of(CLOCK_ARMS[0])
    ray = arm_of(RAY_ARMS[0])
    free_state, clock_state, ray_state = sweep_seed(free), sweep_seed(clock), sweep_seed(ray)
    plain = sweep_step(clock_state, clock, 0)
    action = {}
    vectors = {}
    for label, drive in (("D", (1.0, 0.0)), ("N", DRIVE_PLUS)):
        driven = SweepSpec(0, "preflight_" + label, "preflight", 0.0, load=LOAD_C,
                           plan=(drive,))
        stepped = sweep_step(clock_state, driven, 0)
        before, after = reading_of(plain), reading_of(stepped)
        action[label] = {"even_action": abs(after["even"] - before["even"]),
                         "odd_action": abs(after["odd"] - before["odd"])}
        vectors[label] = np.concatenate((np.asarray(after["even_vector"])
                                         - np.asarray(before["even_vector"]),
                                         np.asarray(after["odd_vector"])
                                         - np.asarray(before["odd_vector"])))
    ray_frozen = sweep_step(ray_state, ray, 0)
    loaded_total = float(np.sum(np.asarray(sweep_seed(clock))))
    unloaded_total = float(np.sum(np.asarray(free_state)))
    return {
        "seed_free": {"content": seed_content(free), "conversion_entry": None},
        "seed_clock": {"content": seed_content(clock),
                       "conversion_entry": conversion_entry(clock_state)},
        "seed_ray": {"content": seed_content(ray)},
        "drive": {"delta_carrier": two_coord.DELTA_CARRIER, "delta_orientation": DRIVE_DELTA,
                  "action": action,
                  "cosine": spent.cosine_of(vectors["D"], vectors["N"])},
        "ray": {"state_identical": bool(np.array_equal(ray_state, ray_frozen)),
                "max_step": float(np.max(np.abs(ray_frozen - ray_state)))},
        "load": {"declared_transfer": LOAD_C, "loaded_total": loaded_total,
                 "unloaded_total": unloaded_total,
                 "total_residual": abs(loaded_total - unloaded_total),
                 "relative_residual": (abs(loaded_total - unloaded_total)
                                       / max(abs(unloaded_total), 1e-300))},
        "step_rule": {"declared_dt": DECLARED_DT, "safety": STEP_SAFETY,
                      "candidates": list(STEP_CANDIDATES),
                      "modes": list(STEP_MODES),
                      "lambda_max": {spec.name: kernel_lambda_max(spec)
                                     for spec in ARM_TABLE},
                      "admissible": sorted(set(
                          value for value in STEP_CANDIDATES
                          if all(value <= 1.0 / (STEP_SAFETY * kernel_lambda_max(spec))
                                 for spec in ARM_TABLE))),
                      "chosen": max(value for value in STEP_CANDIDATES
                                    if all(value <= 1.0
                                           / (STEP_SAFETY * kernel_lambda_max(spec))
                                           for spec in ARM_TABLE))},
    }


def domain_probe() -> dict:
    """Section 1.4.3: the two-coordinate body's declared-shaped probes, rebuilt here.

    `loop_only` varies the composition in chi and is constant in x; `exterior_only` does the
    reverse. This body's reader resolves the first and averages the second out; the spent reader
    does the opposite; on a state constant in chi the two readers must agree, and this body's
    reader must agree with the two-coordinate body's own on every probe, bit for bit.
    """
    probes = two_coord.domain_probe()
    out = {key: value for key, value in probes.items() if isinstance(value, dict)}
    out["reader_is_not_the_spent_reader"] = bool(probes["reader_is_not_the_spent_reader"])
    out["declared_shapes_24"] = bool(probes["declared_shapes_24"])
    out["chi_uniform_identity"] = bool(probes["chi_uniform_identity"])
    out["chi_uniform_mean_difference"] = float(probes["chi_uniform_mean_difference"])
    state = sweep_seed(arm_of(CLOCK_ARMS[0]))
    shape = state.shape
    n_chi, n_x = shape[base.LOOP_AXIS], shape[base.EXTERIOR_AXIS]
    chi = 2.0 * math.pi * np.arange(n_chi) / n_chi
    x = 2.0 * math.pi * np.arange(n_x) / n_x
    built = {}
    loop_only = np.empty_like(state)
    loop_only[0] = (1.05 + 0.11 * np.cos(chi))[None, None, :] + 0.0 * state[0]
    loop_only[1] = (1.05 + 0.0 * np.cos(chi))[None, None, :] + 0.0 * state[1]
    built["loop_only"] = loop_only
    exterior_only = np.empty_like(state)
    exterior_only[0] = (1.05 + 0.11 * np.cos(x))[None, :, None] + 0.0 * state[0]
    exterior_only[1] = (1.05 + 0.0 * np.cos(x))[None, :, None] + 0.0 * state[1]
    built["exterior_only"] = exterior_only
    uniform = np.empty_like(state)
    uniform[0] = (1.05 + 0.11 * np.cos(x))[None, :, None] + 0.0 * state[0]
    uniform[1] = (1.00 + 0.0 * np.cos(x))[None, :, None] + 0.0 * state[1]
    built["chi_uniform"] = uniform
    identical = True
    for label, probe in built.items():
        mine = declared_profile(probe)
        theirs = two_coord.declared_profile(probe)
        if not np.array_equal(mine, theirs):
            identical = False
        spent_rows = spent_profile(probe)
        out[label] = {
            "declared_shape": tuple(int(value) for value in mine.shape),
            "spent_shape": tuple(int(value) for value in spent_rows.shape),
            "declared_row_spread": float(np.max(mine[0]) - np.min(mine[0])),
            "spent_row_spread": float(np.max(spent_rows[0]) - np.min(spent_rows[0])),
            "declared_mean": float(np.mean(mine[0])),
            "spent_mean": float(np.mean(spent_rows[0])),
        }
    out["readers_identical"] = bool(identical)
    out["declared_shapes_24_here"] = bool(all(
        out[label]["declared_shape"][1] == N_CHI for label in built))
    return out


def decide(arms: dict, preflight_record: dict, points: dict) -> dict:
    """Section 2.5: the declared branches, and every reading they consume.

    The entry branch reads the fitted rate of the declared coordinate against its entry at every
    declared point, through the four declared labels; the clock readings at every point are the
    instrument's own validation and are reported beside them; the injector's law is read from the
    sign-reversed pair and the three-phase reversal at two declared points.
    """
    per_point = {}
    for point in EXCHANGE_POINTS:
        entry_record = arms[entry_arm(point)]
        clock_record = arms[clock_arm(point)]
        entry_fit = fit_of(entry_record, "odd")
        clock_fit = fit_of(clock_record, "ray_distance")
        entry = 2.0 * point
        rate = entry_fit["rate"]
        tolerance = max(abs(entry) * ENTRY_TOL_RELATIVE, ENTRY_ZERO_CEILING)
        clock_reference = conversion_entry(sweep_seed(arm_of(clock_arm(point))))
        per_point["{0:+.4f}".format(point)] = {
            "exchange": point,
            "entry": entry,
            "rate": rate,
            "difference": (None if rate is None else rate - entry),
            "ratio": (None if rate is None or entry == 0.0 else rate / entry),
            "tolerance": tolerance,
            "crossing": bool(entry == 0.0),
            "passed": bool(rate is not None and abs(rate - entry) <= tolerance),
            "fit": entry_fit,
            "clock_rate": clock_fit["rate"],
            "clock_reference": clock_reference,
            "clock_ratio": (None if clock_fit["rate"] is None else
                            clock_fit["rate"] / clock_reference),
            "clock_fit": clock_fit,
            "readable": bool(entry_fit["rate"] is not None
                             and entry_fit["readable"] >= FIT_MIN_SAMPLES),
            "quality": bool(entry_fit["rate"] is not None
                            and entry_fit["sign_constant"]
                            and entry_fit["max_relative_residual"] <= FIT_RESIDUAL_CEILING),
        }
    keys = ["{0:+.4f}".format(point) for point in EXCHANGE_POINTS]
    entries = np.array([2.0 * point for point in EXCHANGE_POINTS])
    complete = all(per_point[key]["rate"] is not None for key in keys)
    rates = np.array([per_point[key]["rate"] if per_point[key]["rate"] is not None else 0.0
                      for key in keys])
    slope = intercept = None
    if complete:
        slope, intercept = np.polyfit(entries, rates, 1)
        slope, intercept = float(slope), float(intercept)

    clock_readings = [per_point[key]["clock_rate"] for key in keys]
    clock_ok = bool(all(value is not None
                        and per_point[key]["clock_ratio"] is not None
                        and abs(per_point[key]["clock_ratio"] - 1.0) <= ENTRY_TOL_RELATIVE
                        for key, value in zip(keys, clock_readings)))
    flat = bool(all(value is not None and abs(value) <= FLAT_CEILING for value in rates))
    positives = [key for key in keys if per_point[key]["entry"] > 0.0]
    negatives = [key for key in keys if per_point[key]["entry"] < 0.0]
    crossing = [key for key in keys if per_point[key]["crossing"]]
    positive_pass = bool(all(per_point[key]["passed"] for key in positives))
    negative_pass = bool(all(per_point[key]["passed"] for key in negatives))
    crossing_pass = bool(all(per_point[key]["passed"] for key in crossing))
    quality_ok = bool(all(per_point[key]["readable"] and per_point[key]["quality"]
                          for key in keys))
    if not quality_ok or not clock_ok:
        branch = "INCONCLUSIVE"
    elif flat:
        branch = "FLAT"
    elif positive_pass and negative_pass and crossing_pass:
        branch = "LINEAR_BOTH_SIDES"
    elif positive_pass != negative_pass and (positive_pass or negative_pass) and crossing_pass:
        branch = "ONE_SIDE_ONLY"
    else:
        branch = "INCONCLUSIVE"

    canfail_fit = fit_of(arms[CANFAIL_ARM], "odd")
    canfail_rate = canfail_fit["rate"]
    canfail_passed = bool(canfail_rate is not None
                          and abs(canfail_rate - CANFAIL_ENTRY)
                          <= CANFAIL_BAND_RELATIVE * abs(CANFAIL_ENTRY)
                          and abs(canfail_rate) >= CANFAIL_FLOOR)
    witness_fit = fit_of(arms[WITNESS_ARM], "odd")
    witness_rate = witness_fit["rate"]
    witness_passed = bool(witness_rate is not None
                          and abs(witness_rate - WITNESS_ENTRY)
                          <= CANFAIL_BAND_RELATIVE * abs(WITNESS_ENTRY))

    injector = {}
    for point in INJECTOR_POINTS:
        tag = "{0:+.4f}".format(point)
        baseline = float(arms[clock_arm(point)]["samples"][str(WINDOW_STEPS)]["odd"])
        plus = arms["inject_plus@" + tag]
        minus = arms["inject_minus@" + tag]
        erase = arms["erase@" + tag]
        final = str(WINDOW_STEPS)
        plus_value = float(plus["samples"][final]["odd"]) - baseline
        minus_value = float(minus["samples"][final]["odd"]) - baseline
        erase_value = float(erase["samples"][final]["odd"]) - baseline
        even_part = 0.5 * (plus_value + minus_value)
        odd_part = 0.5 * (plus_value - minus_value)
        magnitude = max(abs(even_part), abs(odd_part))
        erase_fraction = (None if plus_value == 0.0
                          else 1.0 - abs(erase_value) / abs(plus_value))
        injector["{0:+.4f}".format(point)] = {
            "point": point,
            "baseline": baseline,
            "plus": plus_value,
            "minus": minus_value,
            "erase": erase_value,
            "even_part": even_part,
            "odd_part": odd_part,
            "ratio": (None if even_part == 0.0 else abs(odd_part) / abs(even_part)),
            "erase_fraction": erase_fraction,
            "readable": bool(magnitude >= READABLE_FLOOR_Q),
            "even": bool(magnitude >= READABLE_FLOOR_Q
                         and abs(odd_part) <= INJECTOR_EVEN_CEILING * abs(even_part)),
        }
    if all(record["even"] for record in injector.values()):
        injector_branch = "EVEN_IN_SIGN"
    elif all(record["readable"] for record in injector.values()):
        injector_branch = "SIGN_DEPENDENT"
    else:
        injector_branch = "RESERVED_NO_RESPONSE"

    ray_identical = all(arms[name]["state_sha256_first"] == arms[name]["state_sha256_last"]
                        for name in RAY_ARMS)
    ray_digests = {arms[name]["state_sha256_first"] for name in RAY_ARMS}
    clock_digests = {arms[name]["state_sha256_first"] for name in CLOCK_ARMS}
    clock_samples_identical = all(
        arms[name]["samples"][str(WINDOW_STEPS)]["ray_distance"]
        == arms[CLOCK_ARMS[0]]["samples"][str(WINDOW_STEPS)]["ray_distance"]
        for name in CLOCK_ARMS)
    points_ok = all(record["multiset_residual"] <= SPECTRUM_MULTISET_TOL
                    and record["numeric_residual"] <= REPLICATION_TOL
                    and record["nullity"] == (2 if record["exchange"] == 0.0 else 1)
                    and record["symmetric_dimension"] == 1
                    and record["antisymmetric_dimension"]
                    == (1 if record["exchange"] == 0.0 else 0)
                    and record["kernel_residual"] <= KERNEL_SPAN_TOL
                    for record in points.values())
    return {
        "branch": branch,
        "injector": injector_branch,
        "per_point": per_point,
        "entries": [float(value) for value in entries],
        "rates": [float(value) for value in rates],
        "slope": slope,
        "intercept": intercept,
        "flat": flat,
        "positive_pass": positive_pass,
        "negative_pass": negative_pass,
        "crossing_pass": crossing_pass,
        "quality_ok": quality_ok,
        "clock_ok": clock_ok,
        "clock_readings": clock_readings,
        "clock_reference": preflight_record["seed_clock"]["conversion_entry"],
        "clock_oracle": CONVERSION_CLOCK_ORACLE,
        "clock_oracle_ratio": (None if preflight_record["seed_clock"]["conversion_entry"] is None
                               else preflight_record["seed_clock"]["conversion_entry"]
                               / CONVERSION_CLOCK_ORACLE),
        "points_ok": bool(points_ok),
        "canfail": {"rate": canfail_rate, "entry": CANFAIL_ENTRY, "fit": canfail_fit,
                    "passed": canfail_passed},
        "witness": {"rate": witness_rate, "entry": WITNESS_ENTRY, "fit": witness_fit,
                    "passed": witness_passed, "ratio": (None if witness_rate is None else
                                                        witness_rate / WITNESS_ENTRY)},
        "ray_identical": bool(ray_identical),
        "ray_digests_equal": bool(len(ray_digests) == 1),
        "clock_digests_equal": bool(len(clock_digests) == 1),
        "clock_samples_identical": bool(clock_samples_identical),
        "injector_pair": injector,
        "injector_largest_ratio": max((record["ratio"] or 0.0)
                                      for record in injector.values()),
        "two_coordinate_zero_rate": float(
            -math.log(TWO_COORD_RETAINED_SHARE) / TWO_COORD_CHANNEL_WINDOW),
        "two_coordinate_erase_residual": TWO_COORD_ERASE_RESIDUAL,
        "seed_content": {spec.name: seed_content(spec) for spec in ARM_TABLE
                         if spec.role in ("entry", "clock", "ray", "inject", "erase")},
    }


def seed_declaration(seed_records: dict) -> dict:
    """Section 4, gate 8 as amended: where each seed's antisymmetric content lies and what its
    epsilon is declared to be.

    The pointwise-epsilon condition is a statement about the *sweep* seeds -- section 1.2 builds
    them on the ray -- so it is applied to the entry and ray roles. A seed that carries the load
    transfer has epsilon by construction, and is held instead to the transfer's own declared value
    within `LOAD_TRANSFER_TOL`.
    """
    pure = {name: record["w1_fraction"] for name, record in seed_records.items()}
    on_ray = {name: record["epsilon_pointwise"] for name, record in seed_records.items()
              if record["role"] in ("entry", "ray")}
    loaded = {name: record for name, record in seed_records.items()
              if record["role"] not in ("entry", "ray")}
    load_gap = {name: record["epsilon_relative_gap"] for name, record in loaded.items()}
    passed = (all(value <= SEED_CONTENT_CEILING for value in pure.values())
              and all(value <= SEED_EPSILON_CEILING for value in on_ray.values())
              and all(value is not None and value <= LOAD_TRANSFER_TOL
                      for value in load_gap.values()))
    return {
        "bound": "<= {0} of the content on the complementary direction on every seed, the "
                 "pointwise epsilon within {1} of zero on every entry and ray seed, and a "
                 "load-carrying seed's epsilon within {2} relative of the transfer's own declared "
                 "value".format(SEED_CONTENT_CEILING, SEED_EPSILON_CEILING, LOAD_TRANSFER_TOL),
        "passed": bool(passed),
        "reading": {"w1_fraction": pure,
                    "epsilon_on_ray": on_ray,
                    "epsilon_declared_under_load": {name: record["epsilon_declared"]
                                                    for name, record in loaded.items()},
                    "epsilon_relative_gap_under_load": load_gap},
    }


def gate_rows(arms: dict, decision: dict, preflight_record: dict, domain: dict,
              points: dict, probe_check: dict, budget: dict) -> list:
    """Section 4: every gate with its reading, its bound and its verdict. The branch-selecting
    readings of section 2.5 are not gates."""
    structural = all(
        sample["min_state"] >= 0.0 and math.isfinite(sample["min_state"])
        and math.isfinite(sample["max_state"])
        and 0.0 <= sample["q_min"] <= sample["q_max"] < 1.0
        for arm in arms.values() for sample in arm["samples"].values())
    conformant = all(arm["schedule"]["rule_conformant"] for arm in arms.values())
    shape_ok = (budget["executions"] == DECLARED_EXECUTIONS
                and budget["steps_max"] <= PER_EXECUTION_CAP
                and budget["steps_total"] <= TOTAL_STEP_CAP)
    seed_gate = seed_declaration(decision["seed_content"])
    readable = {
        "entry_coordinate": {name: float(arms[name]["samples"]["0"]["odd"])
                             for name in ENTRY_ARMS},
        "clock_ray_distance": {name: float(arms[name]["samples"]["0"]["ray_distance"])
                               for name in CLOCK_ARMS},
    }
    readable_ok = bool(all(abs(value) >= READABLE_FLOOR_Q
                           for value in readable["entry_coordinate"].values())
                       and all(value >= RAY_READABLE_FLOOR
                               for value in readable["clock_ray_distance"].values()))
    clock_rows = {key: {"rate": decision["per_point"][key]["clock_rate"],
                        "reference": decision["per_point"][key]["clock_reference"],
                        "ratio": decision["per_point"][key]["clock_ratio"]}
                  for key in decision["per_point"]}
    clock_ok = bool(decision["clock_ok"] and decision["clock_digests_equal"]
                    and decision["clock_samples_identical"])
    quality_ok = bool(decision["quality_ok"])
    domain_ok = bool(domain["readers_identical"] and domain["declared_shapes_24_here"]
                     and domain["reader_is_not_the_spent_reader"]
                     and domain["chi_uniform_identity"]
                     and domain["loop_only"]["declared_row_spread"] >= DOMAIN_CHI_FLOOR
                     and domain["exterior_only"]["declared_row_spread"]
                     <= DOMAIN_EXTERIOR_CEILING)
    return [
        {"id": 1, "name": "binding", "reading": "every section-0 row declared against observed",
         "bound": "all exact", "passed": True},
        {"id": 2, "name": "reading domain",
         "reading": {"readers_identical": domain["readers_identical"],
                     "loop_only": [domain["loop_only"]["declared_row_spread"],
                                   domain["loop_only"]["spent_row_spread"]],
                     "exterior_only": [domain["exterior_only"]["declared_row_spread"],
                                       domain["exterior_only"]["spent_row_spread"]],
                     "chi_uniform_mean_difference": domain["chi_uniform_mean_difference"]},
         "bound": "this body's reader is bit-equal to the two-coordinate body's on all three "
                  "probes, is not the spent reader, reads >= {0} on the loop-only probe and "
                  "<= {1} on the exterior-only probe, and the two readers agree on the "
                  "chi-uniform mean".format(DOMAIN_CHI_FLOOR, DOMAIN_EXTERIOR_CEILING),
         "passed": domain_ok},
        {"id": 3, "name": "structure",
         "reading": "minimum and maximum state, and the composition bounds, over every "
                    "recorded state",
         "bound": "nonnegative states, 0 <= q < 1", "passed": bool(structural)},
        {"id": 4, "name": "schedule and shape",
         "reading": {"declared_executions": budget["executions"],
                     "steps_total": budget["steps_total"],
                     "steps_max": budget["steps_max"]},
         "bound": "{0} executions, {1} steps per execution, {2} in total, and dt = {3} <= "
                  "1/({4} lambda_max) on every arm's own exchange".format(
                      DECLARED_EXECUTIONS, PER_EXECUTION_CAP, TOTAL_STEP_CAP, DECLARED_DT,
                      STEP_SAFETY),
         "passed": bool(conformant and shape_ok)},
        {"id": 5, "name": "the entries, read from the frozen closed spectrum",
         "reading": {key: {"expected": record["expected_entry_values"],
                           "observed": record["observed_entry_values"],
                           "multiset_residual": record["multiset_residual"],
                           "numeric_residual": record["numeric_residual"]}
                     for key, record in points.items()},
         "bound": "the four values of each point's mode-0 spectrum equal the declared set "
                  "{{0, -2r, -k(1+phi), -k(1+phi)-2r}} within {0}".format(
                      SPECTRUM_MULTISET_TOL),
         "passed": bool(decision["points_ok"])},
        {"id": 6, "name": "the kernel at every declared point, predicted before the run",
         "reading": {key: {"nullity": record["nullity"],
                           "symmetric": record["symmetric_dimension"],
                           "antisymmetric": record["antisymmetric_dimension"],
                           "kernel_residual": record["kernel_residual"]}
                     for key, record in points.items()},
         "bound": "dim ker(mode 0) = 2 at r = 0 and 1 at every other declared point, the "
                  "surviving direction direction-symmetric, the antisymmetric direction present "
                  "only at the crossing, and one null vector there within {0}".format(
                      KERNEL_SPAN_TOL),
         "passed": bool(decision["points_ok"])},
        {"id": 7, "name": "design probe reproduction", "reading": probe_check,
         "bound": "every declared probe reading within {0} relative".format(PROBE_TOL),
         "passed": bool(probe_check["passed"])},
        {"id": 8, "name": "the seed's antisymmetric content lies on the declared direction",
         "reading": seed_gate["reading"], "bound": seed_gate["bound"],
         "passed": bool(seed_gate["passed"])},
        {"id": 9, "name": "silence on every ray arm",
         "reading": {"ray_arms": {name: [arms[name]["state_sha256_first"][:16],
                                         arms[name]["state_sha256_last"][:16]]
                                  for name in RAY_ARMS},
                     "moving_control": {name: [arms[name]["state_sha256_first"][:16],
                                               arms[name]["state_sha256_last"][:16]]
                                        for name in ENTRY_ARMS[:2]},
                     "control_distinguishable": bool(all(
                         arms[name]["state_sha256_first"] != arms[name]["state_sha256_last"]
                         for name in ENTRY_ARMS[:2]))},
         "bound": "the state is the frozen fixed point: first and last digest equal on every ray "
                  "arm, the same digest at every point, and -- the control that shows the digest "
                  "can tell the difference -- the first entry arm's own first and last digest "
                  "unequal", "passed": bool(
                      decision["ray_identical"] and decision["ray_digests_equal"]
                      and all(arms[name]["state_sha256_first"]
                              != arms[name]["state_sha256_last"] for name in ENTRY_ARMS[:2]))},
        {"id": 10, "name": "readable on every declared arm",
         "reading": readable,
         "bound": "the entry coordinate >= {0} and the clock's ray distance >= {1} at the first "
                  "sample".format(READABLE_FLOOR_Q, RAY_READABLE_FLOOR),
         "passed": readable_ok},
        {"id": 11, "name": "can-fail at fifty times the largest swept entry",
         "reading": {"rate": decision["canfail"]["rate"], "entry": CANFAIL_ENTRY,
                     "fit": decision["canfail"]["fit"]["max_relative_residual"]},
         "bound": "the fitted rate at r = {0} within {1} relative of its entry {2} and above "
                  "{3}".format(CANFAIL_EXCHANGE, CANFAIL_BAND_RELATIVE, CANFAIL_ENTRY,
                               CANFAIL_FLOOR),
         "passed": bool(decision["canfail"]["passed"])},
        {"id": 12, "name": "the window's own clock at every point",
         "reading": {"readings": clock_rows,
                     "digests_equal": decision["clock_digests_equal"],
                     "samples_identical": decision["clock_samples_identical"]},
         "bound": "every point's fitted ray-distance rate within {0} relative of the conversion "
                  "entry measured at its own seed, and the clock arms bit-identical across the "
                  "sweep".format(ENTRY_TOL_RELATIVE),
         "passed": clock_ok},
        {"id": 13, "name": "the fit's own quality on every entry arm",
         "reading": {key: {"readable": decision["per_point"][key]["fit"]["readable"],
                           "samples": decision["per_point"][key]["fit"]["samples"],
                           "residual": decision["per_point"][key]["fit"][
                               "max_relative_residual"],
                           "sign_constant": decision["per_point"][key]["fit"]["sign_constant"]}
                     for key in decision["per_point"]},
         "bound": "at least {0} samples above {1}, one sign throughout, and a fitted exponential "
                  "within {2} relative of the series".format(
                      FIT_MIN_SAMPLES, READABLE_FLOOR_Q, FIT_RESIDUAL_CEILING),
         "passed": quality_ok},
        {"id": 14, "name": "single invocation",
         "reading": {"receipt_absent_at_start": True,
                     "prior_invocation": prior_invocation()},
         "bound": "the receipt was absent at the start and one process wrote it, with the "
                  "invocation before this one archived and bound in section 0 as the section-6 "
                  "amendment requires",
         "passed": bool(not receipt_status()["exists"]
                        and prior_invocation()["exists"]
                        and prior_invocation()["digest"] == FIRST_INVOCATION_RECEIPT_SHA256)},
    ]


def features_of(gates: list, decision: dict) -> dict:
    """Section 2.5 and 2.6: every branch-selecting reading, reported and deliberately not gated."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    return {
        "F1_can_fail_fired": bool(passed[11]),
        "F2_ray_silent": bool(passed[9]),
        "F3_readable": bool(passed[10]),
        "F4_clock_uniform": bool(passed[12]),
        "F5_seed_pure": bool(passed[8]),
        "F6_fit_quality": bool(passed[13]),
        "F7_rate_linear_in_entry": bool(decision["slope"] is not None
                                        and abs(decision["slope"] - 1.0)
                                        <= ENTRY_TOL_RELATIVE),
        "F8_injector_law": decision["injector"],
        "F9_witness_at_twenty_five_times": bool(decision["witness"]["passed"]),
        "F10_erase_fraction_largest": max(
            (record["erase_fraction"] or 0.0) for record in decision["injector_pair"].values()),
        "rate_branch": decision["branch"],
        "injector_branch": decision["injector"],
    }


def status_of(gates: list) -> str:
    """The status conjunction reads the gates only: the branch-selecting features of section 2.5
    select a branch, and every declared branch is a recorded finding."""
    return "PASS" if all(row["passed"] for row in gates) else "FAIL"


def receipt_status() -> dict:
    """Idempotent: read the receipt if it exists and report its own binding."""
    path = os.path.join(ROOT, RECEIPT_PATH)
    if not os.path.exists(path):
        return {"exists": False, "path": RECEIPT_PATH}
    with open(path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    return {"exists": True, "path": RECEIPT_PATH, "digest": digest_of(RECEIPT_PATH),
            "schema": receipt.get("schema"), "status": receipt.get("status"),
            "invocation": receipt.get("invocation"),
            "body": receipt.get("protocol_body_sha256"),
            "executor": receipt.get("executor_sha256")}


def replication(decision: dict, points: dict, domain: dict) -> dict:
    """Section 5: the sweep's readings against the bodies it continues.

    The crossing point's own consistency reading is the two-coordinate receipt's retained share,
    which no rate larger than `-ln(share)/450` can produce; the entries are compared against the
    frozen closed form at every point; the erase fraction is reported beside the 0.66% the
    two-coordinate body's erasure branch read; and the clock's reference is reported beside the
    chain's own recorded clock.
    """
    return {
        "two_coordinate_zero_rate": decision["two_coordinate_zero_rate"],
        "crossing_rate": decision["per_point"]["+0.0000"]["rate"],
        "crossing_fit": decision["per_point"]["+0.0000"]["fit"],
        "crossing_zero_ceiling": ENTRY_ZERO_CEILING,
        "closed_form_residuals": {key: record["multiset_residual"]
                                  for key, record in points.items()},
        "clock_reference": decision["clock_reference"],
        "clock_oracle": decision["clock_oracle"],
        "clock_oracle_ratio": decision["clock_oracle_ratio"],
        "declared_conversion_entry": CONVERSION_ENTRY_DECLARED,
        "erase_fraction": {key: record["erase_fraction"]
                           for key, record in decision["injector_pair"].items()},
        "two_coordinate_erase_residual": decision["two_coordinate_erase_residual"],
        "kernel_labels_free": list(KERNEL_LABELS_FREE),
        "kernel_labels_spent": list(KERNEL_LABELS_SPENT),
        "reader_is_not_the_spent_reader": domain["reader_is_not_the_spent_reader"],
        "slope": decision["slope"],
        "intercept": decision["intercept"],
        "witness": decision["witness"],
    }


def probe_replication(decision: dict) -> dict:
    """Gate 7: the run reproduces the design probe's declared readings."""
    readings = []
    for path in PROBE_READING_ORDER:
        name, field = path.split(":")
        if name.startswith("entry@"):
            key = name.split("@")[1]
            if field == "rate":
                readings.append(decision["per_point"][key]["rate"])
            elif field == "odd_initial":
                readings.append(decision["per_point"][key]["fit"]["first"])
            else:
                readings.append(decision["per_point"][key][field])
        elif name.startswith("clock@"):
            key = name.split("@")[1]
            readings.append(decision["per_point"][key]["clock_rate"])
        elif name.startswith("canfail@"):
            readings.append(decision["canfail"]["rate"])
        elif name.startswith("witness@"):
            readings.append(decision["witness"]["rate"])
        elif name.startswith("inject@"):
            key = name.split("@")[1]
            readings.append(decision["injector_pair"][key][field])
        else:
            readings.append(None)
    mismatches = []
    for position, declared in enumerate(PROBE_READINGS):
        observed = readings[position]
        if declared is None:
            mismatches.append({"position": position, "declared": None,
                               "reason": "the declared reading is not filled"})
            continue
        if observed is None:
            mismatches.append({"position": position, "declared": declared, "observed": None})
            continue
        scale = max(abs(declared), 1.0)
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
    return {"arms": arms, "preflight": preflight(), "domain": domain_probe(),
            "points": kernel_points()}


def assemble(built: dict, binding: dict, started: float) -> dict:
    """Every reading both verdicts read, from the built arms, the pre-flight and the binding.

    Separate from `execute` so the static pass can drive the whole gate, feature and receipt path
    on shaped inputs without paying for the integration; a key this path reads that its producers
    do not carry is then a static failure rather than a lost invocation.
    """
    arms, preflight_record = built["arms"], built["preflight"]
    domain, points = built["domain"], built["points"]
    decision = decide(arms, preflight_record, points)
    probe_check = probe_replication(decision)
    replication_record = replication(decision, points, domain)
    budget = {"executions": len(arms),
              "steps_max": max(arm["schedule"]["steps"] for arm in arms.values()),
              "steps_total": sum(arm["schedule"]["steps"] for arm in arms.values()),
              "declared_dt": DECLARED_DT, "bound_seconds": BOUND_SECONDS,
              "seconds_per_step_measured": SECONDS_PER_STEP_MEASURED,
              "projected_seconds_measured": PROJECTED_SECONDS_MEASURED,
              "projected_seconds_assumed": PROJECTED_SECONDS_ASSUMED}
    gates = gate_rows(arms, decision, preflight_record, domain, points, probe_check, budget)
    features = features_of(gates, decision)
    status = status_of(gates)
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
            "entry_tol_relative": ENTRY_TOL_RELATIVE,
            "entry_zero_ceiling": ENTRY_ZERO_CEILING,
            "flat_ceiling": FLAT_CEILING,
            "fit_residual_ceiling": FIT_RESIDUAL_CEILING,
            "fit_min_samples": FIT_MIN_SAMPLES,
            "clock_tolerance_band": CLOCK_TOLERANCE,
            "canfail_band_relative": CANFAIL_BAND_RELATIVE,
            "canfail_floor": CANFAIL_FLOOR,
            "ray_readable_floor": RAY_READABLE_FLOOR,
            "seed_content_ceiling": SEED_CONTENT_CEILING,
            "injector_even_ceiling": INJECTOR_EVEN_CEILING,
            "probe_tol": PROBE_TOL,
            "replication_tol": REPLICATION_TOL,
            "spectrum_multiset_tol": SPECTRUM_MULTISET_TOL,
            "step_safety": STEP_SAFETY,
            "domain_chi_floor": DOMAIN_CHI_FLOOR,
            "domain_exterior_ceiling": DOMAIN_EXTERIOR_CEILING,
            "load_transfer_tol": LOAD_TRANSFER_TOL,
        },
        "declared_points": {
            "exchanges": list(EXCHANGE_POINTS),
            "entries": list(ENTRY_VALUES),
            "predicted_nullity": {"r = 0": 2, "every other point": 1},
            "kappa_mode_zero": KAPPA_MODE_ZERO,
            "conversion_entry_declared": CONVERSION_ENTRY_DECLARED,
            "conversion_clock_oracle": CONVERSION_CLOCK_ORACLE,
            "entry_exchange": ENTRY_EXCHANGE,
            "exchange_spent": EXCHANGE_SPENT,
            "canfail_exchange": CANFAIL_EXCHANGE,
            "canfail_entry": CANFAIL_ENTRY,
            "witness_exchange": WITNESS_EXCHANGE,
            "witness_entry": WITNESS_ENTRY,
            "injector_points": list(INJECTOR_POINTS),
            "beta": BETA,
            "load_transfer": LOAD_C,
            "loaded_arm_transfer": LOADED_ARM_LOAD,
            "window_units": WINDOW_UNITS,
            "window_steps": WINDOW_STEPS,
            "short_units": SHORT_UNITS,
            "short_steps": SHORT_STEPS,
            "phase_steps": CHANNEL_PHASE_STEPS,
            "drive_delta": DRIVE_DELTA,
            "step_modes": list(STEP_MODES),
            "kernel_labels_free": list(KERNEL_LABELS_FREE),
            "kernel_labels_spent": list(KERNEL_LABELS_SPENT),
        },
        "arm_table": [{"name": spec.name, "index": spec.index, "role": spec.role,
                       "exchange": spec.exchange, "imbalance": spec.imbalance,
                       "load_transfer": spec.load_c,
                       "plan": [[float(carrier), float(orientation)]
                                for carrier, orientation in spec.plan],
                       "steps": spec.steps, "note": spec.note} for spec in ARM_TABLE],
        "arms": arms,
        "preflight": preflight_record,
        "domain": domain,
        "points": points,
        "replication": replication_record,
        "decision": decision,
        "features": features,
        "gates": gates,
        "budget": budget,
        "status": status,
        "runtime_seconds": time.time() - started,
        "frozen_sources": {key: value["path"] for key, value in binding["rows"].items()},
    }
    return {"receipt": receipt, "status": status, "arms": arms, "decision": decision,
            "gates": gates, "features": features, "preflight": preflight_record,
            "domain": domain, "points": points, "budget": budget,
            "replication": replication_record, "probe_check": probe_check}


def prior_invocation() -> dict:
    """The archived first invocation this body's amendment binds, or its absence."""
    path = os.path.join(ROOT, FIRST_INVOCATION_RECEIPT)
    if not os.path.exists(path):
        return {"exists": False, "path": FIRST_INVOCATION_RECEIPT}
    with open(path, encoding="utf-8") as handle:
        receipt = json.load(handle)
    return {"exists": True, "path": FIRST_INVOCATION_RECEIPT,
            "digest": digest_of(FIRST_INVOCATION_RECEIPT),
            "status": receipt.get("status"),
            "gates_failed": [row["name"] for row in receipt.get("gates", [])
                             if not row.get("passed")],
            "receipt": receipt.get("protocol_body_sha256")}


def execute() -> int:
    started = time.time()
    if receipt_status()["exists"]:
        print("REFUSING TO RUN: {0} already exists; this body is invoked once per freeze and a "
              "further invocation is refused outright.".format(RECEIPT_PATH))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    if not prior_invocation()["exists"]:
        print("REFUSING TO RUN: the archived first invocation {0} is absent; the section-6 "
              "amendment that permits this invocation requires it."
              .format(FIRST_INVOCATION_RECEIPT))
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    binding = check_binding()
    print("bindings: every section-0 row matches")
    outcome = assemble(build(), binding, started)
    receipt, status = outcome["receipt"], outcome["status"]
    decision, points = outcome["decision"], outcome["points"]
    print("status: " + status)
    print("points: entries {0}".format(decision["entries"]))
    print("rates: {0}".format(decision["rates"]))
    print("slope {0}, intercept {1}".format(decision["slope"], decision["intercept"]))
    print("branch: {0}; injector: {1}".format(decision["branch"], decision["injector"]))
    print("nullity at r = 0: {0}; at r = {1}: {2}; at r = {3}: {4}".format(
        points["+0.0000"]["nullity"], EXCHANGE_SPENT, points["+0.6000"]["nullity"],
        WITNESS_EXCHANGE, points["{0:+.4f}".format(WITNESS_EXCHANGE)]["nullity"]))
    print("clock: reference {0} (chain oracle {1}), readings {2}".format(
        decision["clock_reference"], decision["clock_oracle"], decision["clock_readings"]))
    print("can-fail at r = {0}: rate {1} against entry {2}".format(
        CANFAIL_EXCHANGE, decision["canfail"]["rate"], CANFAIL_ENTRY))
    print("witness at r = {0}: rate {1} against entry {2}".format(
        WITNESS_EXCHANGE, decision["witness"]["rate"], WITNESS_ENTRY))
    print("injector pair: " + json.dumps(decision["injector_pair"]))
    print("domain: readers identical {0}, loop-only {1} vs {2}, exterior-only {3} vs {4}"
          .format(outcome["domain"]["readers_identical"],
                  outcome["domain"]["loop_only"]["declared_row_spread"],
                  outcome["domain"]["loop_only"]["spent_row_spread"],
                  outcome["domain"]["exterior_only"]["declared_row_spread"],
                  outcome["domain"]["exterior_only"]["spent_row_spread"]))
    for row in outcome["gates"]:
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


def shaped_arms() -> dict:
    """Section 4: arms of the declared shape, from the real seeds.

    Every declared arm is seeded for real and its sampled readings carry the fields the gate,
    feature and receipt path reads, with a declared decaying series standing in for the
    integration. This is the separator the static pass mutates: a key the gate path reads and the
    producers below do not carry is a failure here, before any invocation is spent on it.
    """
    arms = {}
    for spec in ARM_TABLE:
        state = sweep_seed(spec)
        reading = reading_of(state)
        samples = {}
        for position, step in enumerate(sample_keys(spec)):
            decay = math.exp(-0.01 * (position + 1))
            samples[str(step)] = {
                "even": reading["even"],
                "odd": (0.0 if spec.role == "ray" else 4.0e-3 * decay),
                "even_nonuniform": reading["even_nonuniform"],
                "odd_nonuniform": reading["odd_nonuniform"],
                "scalar": reading["scalar"],
                "ray_distance": max(reading["ray_distance"], 1.0e-3) * decay,
                "min_state": reading["min_state"], "max_state": reading["max_state"],
                "q_min": reading["q_min"], "q_max": reading["q_max"],
                "index": int(step), "time": step * DECLARED_DT,
            }
        arms[spec.name] = {
            "index": spec.index, "name": spec.name,
            "declared": {"exchange": spec.exchange, "entry": 2.0 * spec.exchange,
                         "imbalance": spec.imbalance, "load_transfer": spec.load_c,
                         "plan": [[float(carrier), float(orientation)]
                                  for carrier, orientation in spec.plan],
                         "phase_steps": spec.phase_steps, "role": spec.role,
                         "note": spec.note},
            "schedule": {"dt": DECLARED_DT, "steps": spec.steps,
                         "horizon": spec.steps * DECLARED_DT,
                         "sample_stride": spec.sample_stride,
                         "samples": len(sample_keys(spec)), "rule_conformant": True},
            "state_sha256_first": ("0" * 64 if spec.role in ("ray", "clock")
                                   else "{0:064d}".format(spec.index)),
            "state_sha256_last": ("0" * 64 if spec.role in ("ray", "clock")
                                  else "{0:064d}".format(spec.index)),
            "sample_keys": tuple(str(step) for step in sample_keys(spec)),
            "samples": samples,
        }
    return arms


def shaped_binding() -> dict:
    return {"declared": {"frozen_body_sha256": FROZEN_BODY_DIGEST,
                         "executor_sha256": protocol_row("executor_sha256")},
            "observed": {}, "rows": {}}


def dry_run() -> list:
    """Section 4: drive the gate, feature and receipt path on shaped inputs.

    The invocation reaches the gate path only after every arm has been integrated, so a key that
    path reads and its producers do not carry costs a whole invocation to discover. This pass
    builds arms of the declared shape from the real seeds, hands the assembly the real pre-flight,
    domain and kernel readings, and requires the gate table, the feature record, the branch labels
    and the written payload to have their declared shape. Its verdicts are not readings and are
    discarded; any exception, or any departure from the declared shape, is a static failure.
    """
    failures = []
    built = {"arms": shaped_arms(), "preflight": preflight(), "domain": domain_probe(),
             "points": kernel_points()}
    try:
        outcome = assemble(built, shaped_binding(), time.time())
        payload = sanitize(outcome["receipt"])
    except Exception as error:  # noqa: BLE001 - any failure here is a static failure
        failures.append("the gate, feature and receipt path fails on shaped inputs: "
                        "{0}: {1}".format(type(error).__name__, error))
        return failures
    if len(outcome["gates"]) != 14:
        failures.append("the gate table carries {0} rows, not 14".format(
            len(outcome["gates"])))
    expected = {"F1_can_fail_fired", "F2_ray_silent", "F3_readable", "F4_clock_uniform",
                "F5_seed_pure", "F6_fit_quality", "F7_rate_linear_in_entry",
                "F8_injector_law", "F9_witness_at_twenty_five_times",
                "F10_erase_fraction_largest", "rate_branch", "injector_branch"}
    if set(outcome["features"]) != expected:
        failures.append("the feature record carries {0}, not the declared 12".format(
            sorted(outcome["features"])))
    if outcome["decision"]["branch"] not in RATE_LABELS:
        failures.append("the rate branch is {0}, not one of the declared labels".format(
            outcome["decision"]["branch"]))
    if outcome["decision"]["injector"] not in INJECTOR_LABELS:
        failures.append("the injector branch is {0}, not one of the declared labels".format(
            outcome["decision"]["injector"]))
    if payload.get("status") not in ("PASS", "FAIL"):
        failures.append("the receipt payload carries no status")
    if payload.get("schema") != RECEIPT_SCHEMA:
        failures.append("the receipt payload carries the wrong schema")
    if len(payload.get("arms", {})) != DECLARED_EXECUTIONS:
        failures.append("the receipt payload carries {0} arms, not {1}".format(
            len(payload.get("arms", {})), DECLARED_EXECUTIONS))
    return failures


def self_check() -> int:
    """Static, derivation and pre-flight checks. Writes nothing; safe to run again."""
    failures = []
    check_binding()
    entry_spec = arm_of(entry_arm(EXCHANGE_POINTS[-1]))
    clock_spec = arm_of(clock_arm(0.0))
    ray_spec = arm_of(ray_arm(0.0))
    state = sweep_seed(entry_spec)
    clock_state = sweep_seed(clock_spec)
    ray_state = sweep_seed(ray_spec)

    # Section 1.2: the declared seed has the frozen profile's own ratio, zero epsilon pointwise,
    # and the load transfer is the chain's own and preserves the total.
    gamma, iota = frozen_profiles()
    if abs(gamma - PHI * iota) > 1.0e-15:
        failures.append("the frozen profile is not the equilibrium ratio: {0} vs {1}".format(
            gamma, PHI * iota))
    free_epsilon = float(np.max(np.abs(state[0] - PHI * state[1])))
    if free_epsilon > SEED_EPSILON_CEILING:
        failures.append("the declared seed's pointwise epsilon is {0}, above the declared "
                        "round-off ceiling {1}".format(free_epsilon, SEED_EPSILON_CEILING))
    local_total = ray_state[0] + ray_state[1]
    predicted_epsilon = ((ray_state[0] - PHI * ray_state[1])
                         + (LOAD_C / 2.0) * (1.0 + PHI) * local_total)
    measured_epsilon = clock_state[0] - PHI * clock_state[1]
    transfer_gap = float(np.max(np.abs(measured_epsilon - predicted_epsilon))
                         / max(float(np.max(np.abs(predicted_epsilon))), 1e-300))
    if transfer_gap > LOAD_TRANSFER_TOL:
        failures.append("the loaded seed's epsilon is not the declared transfer's own: relative "
                        "gap {0}".format(transfer_gap))
    record = preflight()
    if record["load"]["relative_residual"] > LOAD_TRANSFER_TOL:
        failures.append("the load transfer does not preserve the total: {0}".format(
            record["load"]["relative_residual"]))
    if abs(record["load"]["declared_transfer"] - LOAD_C) > 1.0e-15:
        failures.append("the pre-flight's load is not the declared one")

    # Section 1.2: the no-drive step is the frozen (LB6) line, exactly, at two exchanges.
    for exchange in (EXCHANGE_FREE := ENTRY_EXCHANGE, EXCHANGE_SPENT):
        spec = SweepSpec(0, "static", "static", exchange, imbalance=BETA)
        seed = sweep_seed(spec)
        theirs = base.carrier_rhs(seed, split.gate_rate_of(seed, base),
                                  base.Arm(0, "static", PROFILE, spec.modes, 0.0, "mode",
                                           N_CHI, False, exchange, 0.0, 0.0, "mode", "", "",
                                           False))
        mine = two_coord.kernel_rhs(seed, split.gate_rate_of(seed, base), NO_DRIVE, exchange)
        if not np.array_equal(mine, theirs):
            failures.append("the no-drive step is not the frozen (LB6) line at r = {0}; max "
                            "difference {1}".format(exchange,
                                                    float(np.max(np.abs(mine - theirs)))))

    # Section 1.3 and 1.4: the declared reader is the exterior mean over 24 loop samples, is not
    # the spent reader, and agrees with the two-coordinate body's reader bit for bit.
    profile = declared_profile(clock_state)
    if profile.shape != (2, N_CHI):
        failures.append("the declared profile is not (2, {0}): {1}".format(N_CHI,
                                                                          profile.shape))
    if spent_profile(clock_state).shape != (2, base.N_X):
        failures.append("the spent reader does not read {0} coordinates: {1}".format(
            base.N_X, spent_profile(clock_state).shape))
    if not np.array_equal(profile, two_coord.declared_profile(clock_state)):
        failures.append("this body's reader differs from the two-coordinate body's reader")

    # Section 1.2: the ray seed is the frozen fixed point, and the driven arms are not.
    if not record["ray"]["state_identical"]:
        failures.append("the ray seed is not the frozen fixed point")
    if record["drive"]["action"]["N"]["odd_action"] <= 0.0:
        failures.append("the orientation drive has no one-step action on the loaded seed")

    # Section 1.5: the declared estimator is signed, and its own two limits are exact.
    rising = rate_fit(tuple(math.exp(0.5 * t) for t in range(8)),
                      tuple(float(t) for t in range(8)))
    falling = rate_fit(tuple(math.exp(-0.25 * t) for t in range(8)),
                       tuple(float(t) for t in range(8)))
    if rising["rate"] is None or abs(rising["rate"] + 0.5) > 1.0e-9:
        failures.append("the estimator does not read a rising series: {0}".format(
            rising["rate"]))
    if falling["rate"] is None or abs(falling["rate"] - 0.25) > 1.0e-9:
        failures.append("the estimator does not read a falling series: {0}".format(
            falling["rate"]))
    if not (rising["rate"] < 0.0 < falling["rate"]):
        failures.append("the estimator does not carry the sign of the rate")

    # Section 2.3 and section 6: every declared threshold agrees with its protocol row.
    declared = {
        "readable_floor_q": READABLE_FLOOR_Q,
        "entry_tol_relative": ENTRY_TOL_RELATIVE,
        "entry_zero_ceiling": ENTRY_ZERO_CEILING,
        "flat_ceiling": FLAT_CEILING,
        "fit_residual_ceiling": FIT_RESIDUAL_CEILING,
        "fit_min_samples": FIT_MIN_SAMPLES,
        "canfail_band_relative": CANFAIL_BAND_RELATIVE,
        "canfail_floor": CANFAIL_FLOOR,
        "ray_readable_floor": RAY_READABLE_FLOOR,
        "seed_content_ceiling": SEED_CONTENT_CEILING,
        "seed_epsilon_ceiling": SEED_EPSILON_CEILING,
        "injector_even_ceiling": INJECTOR_EVEN_CEILING,
        "probe_tol": PROBE_TOL,
        "domain_chi_floor": DOMAIN_CHI_FLOOR,
        "domain_exterior_ceiling": DOMAIN_EXTERIOR_CEILING,
        "beta": BETA,
        "load_transfer_tol": LOAD_TRANSFER_TOL,
        "load_transfer": LOAD_C,
        "drive_delta": DRIVE_DELTA,
        "window_units": WINDOW_UNITS,
        "window_steps": WINDOW_STEPS,
        "sample_stride": SAMPLE_STRIDE,
        "short_units": SHORT_UNITS,
        "short_steps": SHORT_STEPS,
        "phase_steps": CHANNEL_PHASE_STEPS,
        "canfail_exchange": CANFAIL_EXCHANGE,
        "canfail_entry": CANFAIL_ENTRY,
        "witness_exchange": WITNESS_EXCHANGE,
        "witness_entry": WITNESS_ENTRY,
        "declared_executions": DECLARED_EXECUTIONS,
        "per_execution_cap": PER_EXECUTION_CAP,
        "total_step_cap": TOTAL_STEP_CAP,
        "bound_seconds": BOUND_SECONDS,
        "kappa_mode_zero": KAPPA_MODE_ZERO,
        "conversion_entry_declared": CONVERSION_ENTRY_DECLARED,
        "conversion_clock_oracle": CONVERSION_CLOCK_ORACLE,
        "exchange_spent": EXCHANGE_SPENT,
        "entry_exchange": ENTRY_EXCHANGE,
        "two_coordinate_retained_share": TWO_COORD_RETAINED_SHARE,
        "two_coordinate_channel_window": TWO_COORD_CHANNEL_WINDOW,
        "two_coordinate_erase_residual": TWO_COORD_ERASE_RESIDUAL,
    }
    for key, value in declared.items():
        try:
            declared_value = declared_number(key)
        except SystemExit as error:
            failures.append(str(error))
            continue
        if abs(declared_value - float(value)) > max(1e-15, abs(float(value)) * 1e-12):
            failures.append("protocol row {0} reads {1}, the executor declares {2}".format(
                key, declared_value, value))

    # Section 1.4 and 5: the pre-flight's own readings, and the points the prediction is at.
    points = kernel_points()
    for key, point in points.items():
        if point["multiset_residual"] > SPECTRUM_MULTISET_TOL:
            failures.append("the closed spectrum at {0} does not carry the declared entries"
                            .format(key))
        if point["numeric_residual"] > REPLICATION_TOL:
            failures.append("the stored generator at {0} disagrees with the closed form"
                            .format(key))
    if points["+0.0000"]["nullity"] != 2 or points["+0.6000"]["nullity"] != 1:
        failures.append("the declared prediction is not what the frozen generator carries")
    if record["step_rule"]["chosen"] != DECLARED_DT:
        failures.append("the step rule does not select {0}: {1}".format(
            DECLARED_DT, record["step_rule"]["chosen"]))
    if STEP_CANDIDATES[0] in record["step_rule"]["admissible"]:
        failures.append("the coarsest declared candidate {0} passes the rule, so the declared dt "
                        "is not the largest admissible one".format(STEP_CANDIDATES[0]))
    if len(ARM_TABLE) != DECLARED_EXECUTIONS:
        failures.append("the arm table carries {0} arms, not {1}".format(
            len(ARM_TABLE), DECLARED_EXECUTIONS))
    steps_total = sum(spec.steps for spec in ARM_TABLE)
    if steps_total > TOTAL_STEP_CAP or max(spec.steps for spec in ARM_TABLE) > PER_EXECUTION_CAP:
        failures.append("the declared schedule exceeds its caps: {0}".format(steps_total))

    # Section 4: the gate, feature and receipt path, driven on shaped inputs.
    failures.extend(dry_run())
    if failures:
        print("static check: FAIL")
        for line in failures:
            print("  " + line)
        return EXIT_STATIC_CHECK
    print("static check: bindings, the declared seed and its direction, the frozen (LB6) line, "
          "the declared reader, the signed estimator, the threshold rows, the ray fixed point, "
          "the step rule, the declared entries and the gate, feature and receipt path all agree")
    return EXIT_PASS


def design_probe() -> int:
    """Section 1.5: the readings the declared floors, bands and bounds are chosen against."""
    built = build()
    arms = built["arms"]
    decision = decide(arms, built["preflight"], built["points"])
    print("design probe: readings in the order of PROBE_READING_ORDER")
    for position, path in enumerate(PROBE_READING_ORDER):
        name, field = path.split(":")
        if name.startswith("entry@"):
            key = name.split("@")[1]
            if field == "rate":
                value = decision["per_point"][key]["rate"]
            elif field == "odd_initial":
                value = decision["per_point"][key]["fit"]["first"]
            else:
                value = decision["per_point"][key][field]
        elif name.startswith("clock@"):
            value = decision["per_point"][name.split("@")[1]]["clock_rate"]
        elif name.startswith("canfail@"):
            value = decision["canfail"]["rate"]
        elif name.startswith("witness@"):
            value = decision["witness"]["rate"]
        else:
            value = decision["injector_pair"][name.split("@")[1]][field]
        print("  {0:>30}  {1!r}".format(path, value))
    print("points:")
    for key, record in decision["per_point"].items():
        print("  {0}  entry {1!r}  rate {2!r}  ratio {3!r}  residual {4!r}  readable {5}  "
              "clock {6!r} vs {7!r}".format(
                  key, record["entry"], record["rate"], record["ratio"],
                  record["fit"]["max_relative_residual"], record["fit"]["readable"],
                  record["clock_rate"], record["clock_reference"]))
    print("slope {0!r}, intercept {1!r}, branch {2}, injector {3}".format(
        decision["slope"], decision["intercept"], decision["branch"], decision["injector"]))
    print("clock reference {0!r} (chain oracle {1!r}, declared entry {2!r})".format(
        decision["clock_reference"], decision["clock_oracle"], CONVERSION_ENTRY_DECLARED))
    print("can-fail: rate {0!r} against entry {1!r}; witness: rate {2!r} against entry {3!r}"
          .format(decision["canfail"]["rate"], CANFAIL_ENTRY, decision["witness"]["rate"],
                  WITNESS_ENTRY))
    for key, record in decision["injector_pair"].items():
        print("injector {0}: plus {1!r}, minus {2!r}, erase {3!r}, even {4!r}, odd {5!r}, "
              "ratio {6!r}, erase_fraction {7!r}".format(
                  key, record["plus"], record["minus"], record["erase"], record["even_part"],
                  record["odd_part"], record["ratio"], record["erase_fraction"]))
    for key, record in decision["seed_content"].items():
        print("seed {0}: w0 {1!r}, w1 {2!r}, epsilon_pointwise {3!r}".format(
            key, record["w0_fraction"], record["w1_fraction"], record["epsilon_pointwise"]))
    print("readable floors: entry odd at t=0 {0!r}, clock ray distance at t=0 {1!r}".format(
        {name: arms[name]["samples"]["0"]["odd"] for name in ENTRY_ARMS},
        {name: arms[name]["samples"]["0"]["ray_distance"] for name in CLOCK_ARMS}))
    print("ray digests equal: {0}; clock digests equal: {1}".format(
        decision["ray_digests_equal"], decision["clock_digests_equal"]))
    print("step rule lambda_max: {0}".format(
        {name: value for name, value in built["preflight"]["step_rule"]["lambda_max"].items()}))
    print("step rule admissible: {0}".format(
        built["preflight"]["step_rule"]["admissible"]))
    print("runtime: the invocation's own measured seconds per step is {0}".format(
        SECONDS_PER_STEP_MEASURED))
    return EXIT_PASS


def freeze() -> int:
    """Print the two digests and the section-0 rows the freeze pass pastes in."""
    print("| `frozen_body_sha256` | `{0}` |".format(protocol_body_digest()))
    print("| `executor_sha256` | `{0}` |".format(digest_of(PROBE_PATH)))
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--static", action="store_true",
                        help="run the static checks, write nothing and stop")
    parser.add_argument("--design-probe", action="store_true",
                        help="print the readings the declared floors are chosen against")
    parser.add_argument("--freeze", action="store_true",
                        help="print the two section-0 digests")
    arguments = parser.parse_args(argv)
    if arguments.static:
        return self_check()
    if arguments.design_probe:
        return design_probe()
    if arguments.freeze:
        return freeze()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
