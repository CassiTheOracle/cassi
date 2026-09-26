"""Does the gate write, and does what it writes stay? The loop-carrier composition
coordinate under a split gate that is held and then removed.

One protocol, one invocation. The executor is frozen with `computations/loop-carrier-
attractor-write-successor-prereg.md` in the same commit and refuses to run unless the
protocol body's digest, its own digest, and the digests of every imported module and
receipt agree with the rows of section 0.

Two families share one run and one seed family.

Family (i) -- the write, replicated. The spent protocol's arms, horizons, fits and law,
with one correction: every arm's distance from the ray is recorded, the anchors included,
so the attribution gate that left the spent run at `FAIL` is readable here. Verdict:
`WRITES`, `PERTURBS_ONLY` or `INCONCLUSIVE`.

Family (ii) -- retention. The same split is held to the long horizon, then removed and
the carrier is integrated on. The post-release readings are fitted with the successor
receipt's relaxation rate held, as in family (i), and the fitted offset is read against
the offset the same split wrote in family (i). A written attractor that stays leaves the
offset; a driven state that exists only while it is held decays back at the measured
rate. Verdict: `STORES`, `RELEASES`, `MOOT` or `INCONCLUSIVE`.

    python computations/verify_loop_carrier_attractor_write_successor.py --self-check
    python computations/verify_loop_carrier_attractor_write_successor.py --design-probe
    timeout 900 python computations/verify_loop_carrier_attractor_write_successor.py
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

# The corrected predecessor is imported as a library: its arm machinery, its two fits and
# its branch rule are the code family (i) replicates, and its frozen body is bound here by
# digest. The two spent executors come in through it for their own constructions.
import verify_loop_carrier_attractor_write as prior  # noqa: E402
import verify_loop_carrier_gate_load as gate_load  # noqa: E402
import verify_loop_carrier_projection_split as split  # noqa: E402

# Section 0: the bound sources, all by digest. The predecessor's body and executor are the
# two that moved after its own invocation, and its receipt is bound as the oracle family
# (i) must reproduce.
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

PROTOCOL_PATH = "computations/loop-carrier-attractor-write-successor-prereg.md"
PROBE_PATH = "computations/verify_loop_carrier_attractor_write_successor.py"
RECEIPT_PATH = "runs/loop_carrier_attractor_write_successor/verification.json"
INVOCATION = ("timeout 900 python "
              "computations/verify_loop_carrier_attractor_write_successor.py")
RECEIPT_SCHEMA = "cassi.loop-carrier-attractor-write-successor.v1"
BOUND_SECONDS = 900.0

# Section 0 of the protocol declares both hashes: this file's, and the digest of the frozen
# body (everything from "## 1." to just before "## 8."). The two are cross-bound without a
# fix point, because section 0 sits outside the body range. Filled by the freeze pass.
FROZEN_BODY_DIGEST = "23fb4e9a545793752db259324c87a71da9045cbb04221d0c60ef9c50b6003372"
BODY_START = r"(?m)^## 1\."
BODY_END = r"(?m)^## 8\."

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_ARGUMENTS = 2
EXIT_PRE_EXECUTION_BLOCK = 3
EXIT_STATIC_CHECK = 4

# Section 2.3: the declared thresholds. The write family's floors and bands are the
# predecessor's, carried unchanged; the retention family's two shares are new and are the
# only thresholds this protocol adds.
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
RETENTION_SHARE = 0.5
RELEASE_SHARE = 0.05
MIN_RETAINED = 2
ACTION_FLOOR_LIVE = prior.ACTION_FLOOR_LIVE
ACTION_CEIL_SILENT = prior.ACTION_CEIL_SILENT
ANCHOR_RAY_TOL = prior.ANCHOR_RAY_TOL
LOAD_TOL = prior.LOAD_TOL
LOAD_ABS_FLOOR = prior.LOAD_ABS_FLOOR
STEP_SAFETY = prior.STEP_SAFETY
SECONDS_PER_STEP_ASSUMED = prior.SECONDS_PER_STEP_ASSUMED
SECONDS_PER_STEP_MEASURED = 6.665e-4
PROJECTED_SECONDS_ASSUMED = 415.0
PROJECTED_SECONDS_MEASURED = 331.0
# The declared hold: the write must be established to below one percent of its own
# transient before it is removed, which is the same fraction the horizon set is declared
# against.
HOLD_MIN_MULTIPLE = 5.0
HOLD_MIN_SECONDS = HOLD_MIN_MULTIPLE / NU_REFERENCE
# Section 1.5: the predecessor's measured law, read from its receipt and declared here as
# litterals, used by gate 6's magnitude check and by gate 17's replication.
WRITE_LAW_COEFFICIENT = 4.3424057234641914e-4
WRITE_LAW_EXPONENT = 1.0302448806878108
WRITE_LAW_INSTRUMENT = 4.129022977646817e-9
REPLICATION_TOL = 1.0e-15
ANCHOR_RAY_AT_HOLD = 1.3442651683720991e-3
# Section 1.5: the design probe's retention readings, level by level in the order of
# RETENTION_ORDER, declared before the run; gate 20 checks the run reproduces them.
PROBE_RETENTION_OFFSETS = (-3.3358050312383746e-07, -3.3587960350257283e-06,
                          -3.5889430143274970e-05, -5.9244410183651049e-04)

PER_EXECUTION_CAP = 50000
TOTAL_STEP_CAP = 600000
DECLARED_EXECUTIONS = 17

# Section 3: the declared schedules. The two anchors run the full hold-and-release span so
# that one run of each serves both families as their unsplit reference; the write-family
# arms run the hold span alone, and their readings are the prefix of the longer run.
DECLARED_DT = prior.DECLARED_DT
SHORT_DT, SHORT_HORIZON, SHORT_STEPS = prior.SHORT_DT, prior.SHORT_HORIZON, prior.SHORT_STEPS
REPLICATION_DT = prior.REPLICATION_DT
REPLICATION_HORIZON = prior.REPLICATION_HORIZON
REPLICATION_STEPS = prior.REPLICATION_STEPS
HOLD_HORIZON, HOLD_STEPS = prior.LONG_HORIZON, prior.LONG_STEPS
RELEASE_HORIZON, RELEASE_STEPS = 2.0 * prior.LONG_HORIZON, 2 * prior.LONG_STEPS
HORIZONS = prior.HORIZONS
SAMPLE = prior.SAMPLE
RELEASE_SAMPLE = tuple(HOLD_STEPS + index for index in SAMPLE)

DECADES = prior.DECADES
LARGEST_SPLIT = prior.LARGEST_SPLIT
SWEEP_ORDER = prior.SWEEP_ORDER
LARGEST_LOAD = prior.LARGEST_LOAD
ANCHOR_ARM = prior.ANCHOR_ARM
LARGEST_SPLIT_ARM = prior.LARGEST_SPLIT_ARM
RAY_ANCHOR_ARM = prior.RAY_ANCHOR_ARM
RAY_SILENCE_ARM = prior.RAY_SILENCE_ARM
CLOCK_ARM = prior.CLOCK_ARM
STEP_NOISE_ARM = prior.STEP_NOISE_ARM
REPLICATION_ARM = prior.REPLICATION_ARM
RETENTION_LEVELS = (1.0e-3, 1.0e-2, 1.0e-1, 1.0)
RETENTION_ORDER = ("retain_1", "retain_2", "retain_3", "retain_supersplit")
RETENTION_LARGEST_ARM = "retain_supersplit"
RETENTION_RAY_ARM = "retain_ray"
PROFILE = prior.PROFILE
STEP_CANDIDATES = prior.STEP_CANDIDATES

ORACLE_RAY_RHO = prior.ORACLE_RAY_RHO
ORACLE_REPLICATION_RHO = prior.ORACLE_REPLICATION_RHO
ORACLE_REPLICATION_FINAL = prior.ORACLE_REPLICATION_FINAL
ORACLE_REPLICATION_LAMBDA = prior.ORACLE_REPLICATION_LAMBDA
ORACLE_RAY_LOAD = prior.ORACLE_RAY_LOAD
ORACLE_CLOCK = prior.ORACLE_CLOCK

WRITE_BRANCHES = ("PERSIST", "TRANS", "UNRESOLVED", "BELOW_FLOOR")
RETENTION_BRANCHES = ("RETAINED", "RELEASED", "PARTIAL", "BELOW_FLOOR", "MOOT")
WRITE_VERDICTS = ("WRITES", "PERTURBS_ONLY", "INCONCLUSIVE")
RETENTION_VERDICTS = ("STORES", "RELEASES", "MOOT", "INCONCLUSIVE")
JOINT_LABELS = ("memory", "knob", "no-write", "undecided")


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
    # The predecessor's own ten rows are the strongest available statement that the chain
    # family (i) replicates is intact, and it costs one call: its refusal is a refusal here.
    try:
        prior.check_binding()
    except SystemExit:
        problems.append("the predecessor's own binding of the chain failed")
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


class SuccessorSpec(prior.ArmSpec):
    """One declared arm of section 3, on this protocol's own two schedules."""

    def __init__(self, index: int, name: str, role: str, load_c: float, delta_g: float,
                 schedule_key: str = "hold", twin: str = "", hold_steps: int = 0):
        prior.ArmSpec.__init__(self, index, name, role, load_c, delta_g, schedule_key, twin)
        self.hold_steps = int(hold_steps)

    def declared_schedule(self) -> tuple:
        if self.schedule_key == "short":
            return SHORT_DT, SHORT_HORIZON, SHORT_STEPS
        if self.schedule_key == "replication":
            return REPLICATION_DT, REPLICATION_HORIZON, REPLICATION_STEPS
        if self.schedule_key == "hold":
            return DECLARED_DT, HOLD_HORIZON, HOLD_STEPS
        return DECLARED_DT, RELEASE_HORIZON, RELEASE_STEPS

    def released(self):
        """The same arm with the split removed: the step the release phase takes."""
        return prior.ArmSpec(self.index, self.name, self.role, self.load_c, 0.0,
                             self.schedule_key, self.twin)


def build_arm_table() -> tuple:
    arms = [
        SuccessorSpec(1, "ray_short", "oracle", 0.0, 0.0, "short"),
        SuccessorSpec(2, "successor_replication", "oracle", 0.0, 0.0, "replication"),
        SuccessorSpec(3, RAY_ANCHOR_ARM, "anchor", 0.0, 0.0, "release"),
        SuccessorSpec(4, ANCHOR_ARM, "anchor", LARGEST_LOAD, 0.0, "release"),
        SuccessorSpec(5, RAY_SILENCE_ARM, "silence", 0.0, LARGEST_SPLIT, "hold",
                      RAY_ANCHOR_ARM),
    ]
    index = 6
    for position, level in enumerate(DECADES):
        arms.append(SuccessorSpec(index, "decade_{0}".format(position + 1), "sweep",
                                  LARGEST_LOAD, level, "hold", ANCHOR_ARM))
        index += 1
    arms.append(SuccessorSpec(index, LARGEST_SPLIT_ARM, "canfail", LARGEST_LOAD,
                              LARGEST_SPLIT, "hold", ANCHOR_ARM))
    index += 1
    arms.append(SuccessorSpec(index, RETENTION_RAY_ARM, "silence", 0.0, LARGEST_SPLIT,
                              "release", RAY_ANCHOR_ARM, HOLD_STEPS))
    index += 1
    for position, level in enumerate(RETENTION_LEVELS):
        name = RETENTION_ORDER[position]
        arms.append(SuccessorSpec(index, name, "retention", LARGEST_LOAD, level,
                                  "release", ANCHOR_ARM, HOLD_STEPS))
        index += 1
    return tuple(arms)


ARM_TABLE = build_arm_table()
WRITE_ARMS = tuple(arm for arm in ARM_TABLE if arm.schedule_key == "hold")
RETENTION_ARMS = tuple(arm for arm in ARM_TABLE if arm.schedule_key == "release"
                       and arm.hold_steps > 0)
HOLD_ARMS = tuple(arm for arm in ARM_TABLE if arm.role == "anchor")
TWIN_NAMES = tuple(sorted({arm.twin for arm in ARM_TABLE if arm.twin if arm.schedule_key == "hold"}))


def coordinate_of(projection: np.ndarray, base) -> float:
    return prior.coordinate_of(projection, base)


def ray_distance_of(projection: np.ndarray, base) -> float:
    return prior.ray_distance_of(projection, base)


def action_of(load_c: float, delta_g: float, base) -> dict:
    return prior.action_of(load_c, delta_g, base)


def arm_record(spec, base, anchor_series, release_from) -> dict:
    """One declared arm: its schedule, its coordinate series, its structure and its fits.

    Family (i)'s arms and the two anchors stop at the hold horizon; the retention arms step
    on with the split removed at the declared index. `release_from` is that index, or None.
    """
    state = gate_load.loaded_seed(spec, base)
    dt, horizon, steps = spec.declared_schedule()
    projection = base.projection(state)
    kappa = base.gate_rate(projection[0], projection[1])
    lambda_max = float(base.arm_lambda_max(split.proxy_arm(spec, base), kappa))
    conformant = bool(dt <= 1.0 / (STEP_SAFETY * lambda_max) and dt in STEP_CANDIDATES)
    comparison = gate_load.load_comparison(spec, gate_load.load_of(state, base))
    released = spec.released()

    sampled = SAMPLE if steps + 1 > SAMPLE[-1] else ()
    canonical = base.canonical_initial(PROFILE)
    series = np.empty(steps + 1)
    rho, minima, projections, low, high = [], [], [], [], []
    annihilation, idempotence = [], []
    hold_ray = None
    for index in range(steps + 1):
        current = base.projection(state)
        series[index] = coordinate_of(current, base)
        rho.append(gate_load.rho_of(current, canonical))
        minima.append(float(np.min(state)))
        projections.append(float(np.min(current)))
        composition = base.frozen.bounded_q(current[0], current[1])
        low.append(float(np.min(composition)))
        high.append(float(np.max(composition)))
        annihilation.append(gate_load.annihilation_of(state, base))
        idempotence.append(base.relative_residual(
            base.projection(base.lift(current, state.shape[base.LOOP_AXIS])), current))
        # Section 3.3: the anchor's own distance from the ray at the hold horizon, the
        # quantity the spent protocol's gate 12 could not read from its own run.
        if release_from is None and steps > HOLD_STEPS and index == HOLD_STEPS:
            hold_ray = ray_distance_of(current, base)
        if index == steps:
            break
        active = released if (release_from is not None and index >= release_from) else spec
        state = split.split_step(state, dt, active, base)
        canonical = base.canonical_step(canonical, dt)

    reading = {
        "index": spec.index,
        "name": spec.name,
        "role": spec.role,
        "declared": {
            "load_transfer": spec.load_c,
            "delta_g": spec.delta_g,
            "schedule_key": spec.schedule_key,
            "twin": spec.twin,
            "hold_steps": spec.hold_steps,
            "release_index": release_from,
        },
        "load": comparison,
        "schedule": {
            "dt": dt,
            "horizon": horizon,
            "steps": steps,
            "lambda_max": lambda_max,
            "rule_conformant": conformant,
            "samples": list(sampled),
            "release_samples": list(RELEASE_SAMPLE) if release_from is not None else [],
        },
        "rho": {"max": float(np.max(rho)), "final": float(rho[-1]),
                "peak_time": float(int(np.argmax(rho)) * dt)},
        "structure": {
            "min_state": float(np.min(minima)),
            "min_projection": float(np.min(projections)),
            "q_min": float(np.min(low)),
            "q_max": float(np.max(high)),
            "annihilation_max": float(np.max(annihilation)),
            "idempotence_max": float(np.max(idempotence)),
        },
        "ray_distance": ray_distance_of(base.projection(state), base),
        "ray_distance_at_hold": hold_ray,
        "coordinate": {"initial": float(series[0]), "final": float(series[-1]),
                       "at_horizons": ([float(series[index]) for index in sampled]
                                       if (sampled and release_from is None) else None),
                       "at_release_horizons": (
                           [float(series[index]) for index in RELEASE_SAMPLE]
                           if release_from is not None else None),
                       "at_hold_horizons": (
                           [float(series[index]) for index in SAMPLE]
                           if release_from is not None else None),
                       "at_release_epoch": (float(series[release_from])
                                            if release_from is not None else None)},
        "delta": None,
        "branch": None,
        "self_twin": anchor_series is None,
        "steps_recorded": int(steps + 1),
        "_coordinate_series": series,
        "_rho_series": (rho if spec.name == CLOCK_ARM else None),
    }
    if anchor_series is not None:
        difference = series - anchor_series
        if release_from is None and sampled:
            readings = [float(difference[index]) for index in sampled]
            peak_index = int(np.argmax(np.abs(difference)))
            reading["delta"] = {
                "at_horizons": readings,
                "horizons": list(HORIZONS),
                "peak": float(np.max(np.abs(difference))),
                "peak_time": float(peak_index * dt),
            }
            reading["branch"] = prior.classify(readings)
        elif release_from is not None:
            held_readings = [float(difference[index]) for index in SAMPLE]
            readings = [float(difference[index]) for index in RELEASE_SAMPLE]
            reading["delta"] = {
                "at_horizons": readings,
                "at_hold_horizons": held_readings,
                "horizons": list(HORIZONS),
                "peak": float(np.max(np.abs(readings))),
                "peak_time": float(int(np.argmax(np.abs(readings))) * dt),
            }
    return reading


def classify_retention(readings, written, write_branch: str) -> dict:
    """Section 2.2: the retention branch, from the two fits of the post-release readings.

    The written magnitude is family (i)'s own fitted offset at the same split size, so the
    ratio is a fraction of what the gate actually wrote on this seed and not of a nominal
    level. Where family (i) did not persist there is nothing to retain and the level is
    recorded `MOOT` rather than graded.
    """
    values = np.asarray(readings, dtype=np.float64)
    peak = float(np.max(np.abs(values)))
    terminal = float(values[-1])
    held = prior.fit_held(values)
    free = prior.fit_free(values)
    reading = {
        "peak": peak,
        "terminal": terminal,
        "held": held,
        "free": free,
        "rate_ratio": free["rate"] / NU_REFERENCE,
        "transient_prediction": float(np.exp(-NU_REFERENCE * (HORIZONS[-1] - HORIZONS[-2]))),
        "written": written,
        "written_branch": write_branch,
        "share_held": (abs(held["offset"]) / abs(written) if written else None),
        "share_free": (abs(free["offset"]) / abs(written) if written else None),
        "residual_held": held["residual"],
        "residual_free": free["residual"],
    }
    if write_branch != "PERSIST":
        reading["branch"] = "MOOT"
        reading["reason"] = ("family (i) reads {0} at this split size, so no displaced "
                             "attractor exists to retain".format(write_branch))
        return reading
    if peak < READABLE_FLOOR_Q:
        reading["branch"] = "BELOW_FLOOR"
        reading["reason"] = "the post-release peak is below the readable floor"
        return reading
    within = held["residual"] <= RESIDUAL_BAND and free["residual"] <= RESIDUAL_BAND
    retained = (abs(held["offset"]) >= RETENTION_SHARE * abs(written)
                and abs(free["offset"]) >= RETENTION_SHARE * abs(written) and within)
    released = (abs(held["offset"]) <= RELEASE_SHARE * abs(written)
                and abs(free["offset"]) <= RELEASE_SHARE * abs(written) and within
                and 1.0 / CLOCK_TOLERANCE <= reading["rate_ratio"] <= CLOCK_TOLERANCE)
    if retained:
        reading["branch"] = "RETAINED"
        reading["reason"] = ("both fits keep at least {0} of the written offset after the "
                             "split is removed".format(RETENTION_SHARE))
    elif released:
        reading["branch"] = "RELEASED"
        reading["reason"] = ("both fits leave at most {0} of the written offset and the "
                             "free rate is {1} times the measured clock".format(
                                 RELEASE_SHARE, round(reading["rate_ratio"], 4)))
    else:
        reading["branch"] = "PARTIAL"
        reading["reason"] = ("the held fit keeps {0} of the written offset, the free fit "
                             "{1}, the free rate {2} times the clock, the residuals {3} and "
                             "{4}".format(_round(reading["share_held"]),
                                          _round(reading["share_free"]),
                                          round(reading["rate_ratio"], 4),
                                          round(held["residual"], 4),
                                          round(free["residual"], 4)))
    return reading


def _round(value):
    return None if value is None else round(value, 4)


def read_clock(rho_series, dt, start_index, end_index) -> dict:
    return prior.clock_of(rho_series, dt, start_index, end_index)


def read_oracle() -> dict:
    return prior.read_oracle()


def write_verdict(branches, persisting, decaying, largest_branch) -> str:
    return prior.verdict_of(branches, persisting, decaying, largest_branch)


def retention_verdict(branches, largest_branch, write_verdict_label) -> str:
    """Section 2.4's second family: the same shape of sufficient condition."""
    retained = [name for name in RETENTION_ORDER if branches[name] == "RETAINED"]
    released = [name for name in RETENTION_ORDER if branches[name] == "RELEASED"]
    if write_verdict_label == "PERTURBS_ONLY":
        return "MOOT"
    if largest_branch == "RETAINED" and len(retained) >= MIN_RETAINED:
        return "STORES"
    if largest_branch == "RELEASED" and len(released) >= MIN_RETAINED:
        return "RELEASES"
    return "INCONCLUSIVE"


def joint_label(write_label, retention_label) -> str:
    if write_label == "PERTURBS_ONLY":
        return "no-write"
    if write_label == "WRITES" and retention_label == "STORES":
        return "memory"
    if write_label == "WRITES" and retention_label == "RELEASES":
        return "knob"
    return "undecided"


def decide(arms: dict) -> dict:
    """Sections 2.4 and 2.5: both families' branches, laws, instruments and verdicts."""
    write_branches = {name: arms[name]["branch"]["branch"] for name in SWEEP_ORDER}
    persisting = [name for name in SWEEP_ORDER if write_branches[name] == "PERSIST"]
    decaying = [name for name in SWEEP_ORDER if write_branches[name] == "TRANS"]
    measured = [name for name in SWEEP_ORDER if write_branches[name] != "BELOW_FLOOR"]
    levels = [arms[name]["declared"]["delta_g"] for name in SWEEP_ORDER]
    law = None
    if len(persisting) >= MIN_READABLE:
        law = prior.law_of([arms[name]["declared"]["delta_g"] for name in persisting],
                           [abs(arms[name]["branch"]["held"]["offset"])
                            for name in persisting])
    write_label = write_verdict(write_branches, persisting, decaying,
                                write_branches[LARGEST_SPLIT_ARM])

    written_of = {arms[name]["declared"]["delta_g"]: abs(arms[name]["branch"]["held"]["offset"])
                  for name in SWEEP_ORDER}
    write_arm_of_level = {arms[name]["declared"]["delta_g"]: name for name in SWEEP_ORDER}
    for name in RETENTION_ORDER:
        level = arms[name]["declared"]["delta_g"]
        arms[name]["branch"] = classify_retention(
            arms[name]["delta"]["at_horizons"], written_of.get(level),
            write_branches[write_arm_of_level[level]])
    retention_branches = {name: arms[name]["branch"]["branch"] for name in RETENTION_ORDER}
    retention_label = retention_verdict(retention_branches,
                                        retention_branches[RETENTION_LARGEST_ARM],
                                        write_label)
    return {
        "write": {
            "branches": write_branches,
            "persisting": persisting,
            "decaying": decaying,
            "measured": measured,
            "largest_split": LARGEST_SPLIT_ARM,
            "largest_split_branch": write_branches[LARGEST_SPLIT_ARM],
            "law": law,
            "law_issued": bool(law is not None),
            "law_arm_count": len(persisting),
            "corroboration": prior.corroboration_of(arms, levels),
            "verdict": write_label,
        },
        "retention": {
            "branches": retention_branches,
            "retained": [name for name in RETENTION_ORDER
                         if retention_branches[name] == "RETAINED"],
            "released": [name for name in RETENTION_ORDER
                         if retention_branches[name] == "RELEASED"],
            "largest_split": RETENTION_LARGEST_ARM,
            "largest_split_branch": retention_branches[RETENTION_LARGEST_ARM],
            "law": None,
            "verdict": retention_label,
        },
        "joint": joint_label(write_label, retention_label),
    }


def retention_law(arms: dict, branches: dict) -> dict:
    """Section 2.2: the same log-space fit over the levels that were graded."""
    graded = [name for name in RETENTION_ORDER if branches[name] in ("RETAINED", "RELEASED",
                                                                     "PARTIAL")]
    if len(graded) < MIN_READABLE:
        return {"issued": False, "reason": "{0} graded levels against {1} declared".format(
            len(graded), MIN_READABLE), "arms": graded}
    levels = [arms[name]["declared"]["delta_g"] for name in graded]
    readings = [abs(arms[name]["branch"]["held"]["offset"]) for name in graded]
    fitted = prior.law_of(levels, readings)
    return {"issued": True, "arms": graded, "fit": fitted["fit"], "label": fitted["label"],
            "reasons": fitted["reasons"], "jumps": fitted["jumps"],
            "instrument": fitted["instrument"]}


def predecessor_replication(arms: dict, receipt: dict) -> dict:
    """Gate 17: family (i)'s readings against the predecessor receipt, arm by arm.

    The arms are the predecessor's own construction and the anchors are the same runs
    carried further, so every horizon-indexed value must be reproduced exactly; only the
    anchors' terminal state differs, and that difference is excluded by construction.
    """
    checked, mismatches = [], []
    for name in [arm.name for arm in ARM_TABLE if arm.schedule_key == "short"
                 or arm.schedule_key == "replication"
                 or (arm.schedule_key == "hold" and arm.role != "anchor")]:
        expected = receipt["arms"][name]
        observed = arms[name]
        pairs = [("coordinate.at_horizons", expected["coordinate"]["at_horizons"],
                  observed["coordinate"]["at_horizons"])]
        if expected["delta"] is not None and observed["delta"] is not None:
            pairs.append(("delta.at_horizons", expected["delta"]["at_horizons"],
                          observed["delta"]["at_horizons"]))
            pairs.append(("delta.peak", expected["delta"]["peak"], observed["delta"]["peak"]))
            pairs.append(("branch", expected["branch"]["branch"],
                          observed["branch"]["branch"]))
            for key in ("offset", "amplitude", "residual", "rate"):
                pairs.append(("held.{0}".format(key), expected["branch"]["held"][key],
                              observed["branch"]["held"][key]))
                pairs.append(("free.{0}".format(key), expected["branch"]["free"][key],
                              observed["branch"]["free"][key]))
            pairs.append(("share_held", expected["branch"]["share_held"],
                          observed["branch"]["share_held"]))
        for key in ("coordinate.at_horizons", "delta.at_horizons", "delta.peak", "branch",
                    "held.offset", "held.amplitude", "held.residual", "held.rate",
                    "free.offset", "free.amplitude", "free.residual", "free.rate",
                    "share_held"):
            checked.append("{0}:{1}".format(name, key))
        for key, want, got in pairs:
            if want != got:
                mismatches.append("{0}:{1}: {2} against {3}".format(name, key, want, got))
    for name in (RAY_ANCHOR_ARM, ANCHOR_ARM):
        expected = receipt["arms"][name]
        observed = arms[name]
        checked.append("{0}:coordinate.at_horizons".format(name))
        if expected["coordinate"]["at_horizons"] != observed["coordinate"]["at_horizons"]:
            mismatches.append("{0}:coordinate.at_horizons differs".format(name))
    return {"checked": checked, "count": len(checked), "mismatches": mismatches,
            "passed": not mismatches}


def family_identity(arms: dict) -> dict:
    """Gate 22: the retention arms' held phase against the write arms' own readings.

    The two families are one construction. A retention arm runs the same seed, load, split
    and step as the write arm at the same split size up to the declared hold, so its held
    readings must be that arm's readings bit for bit. A release that fired early, or a held
    step that was not the split's own step, would break the equality while leaving every
    other gate standing.
    """
    write_arm_of_level = {arm.delta_g: arm.name for arm in ARM_TABLE
                          if arm.schedule_key == "hold" and arm.role != "anchor"}
    pairs = [(RETENTION_RAY_ARM, RAY_SILENCE_ARM)]
    for name in RETENTION_ORDER:
        pairs.append((name, write_arm_of_level[arms[name]["declared"]["delta_g"]]))
    checked, mismatches = [], []
    for retention_name, write_name in pairs:
        expected = arms[write_name]["delta"]["at_horizons"]
        observed = arms[retention_name]["delta"]["at_hold_horizons"]
        checked.append("{0}:{1}".format(retention_name, write_name))
        if expected != observed:
            mismatches.append("{0}: the held readings differ from {1}".format(
                retention_name, write_name))
    return {"checked": checked, "count": len(checked), "mismatches": mismatches,
            "passed": not mismatches}


def probe_replication(arms: dict) -> dict:
    """Gate 20: the retention readings against the design probe's declared literals."""
    if not PROBE_RETENTION_OFFSETS:
        return {"checked": [], "mismatches": ["the protocol declares no probe literals"],
                "passed": False}
    mismatches, checked = [], []
    for name, expected in zip(RETENTION_ORDER, PROBE_RETENTION_OFFSETS):
        observed = arms[name]["branch"]["held"]["offset"]
        checked.append(name)
        if abs(observed - expected) > REPLICATION_TOL * max(1.0, abs(expected)):
            mismatches.append("{0}: {1} against {2}".format(name, observed, expected))
    return {"checked": checked, "mismatches": mismatches, "passed": not mismatches}


def gate_rows(arms: dict, action: dict, comparison_ok: bool, budget: dict, clocks: dict,
              clock_read: dict, oracle: dict, decision: dict, replication: dict,
              probe_check: dict, family: dict) -> list:
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
    hold_tail = float(np.exp(-NU_REFERENCE * HOLD_HORIZON))
    declared_levels = [arm for arm in ARM_TABLE
                       if arm.name in SWEEP_ORDER and arm.delta_g in DECADES
                       + (LARGEST_SPLIT,)]
    retention_levels = [arm for arm in ARM_TABLE if arm.name in RETENTION_ORDER]
    adequacy = (len(HORIZONS) == HORIZON_COUNT and distinct == len(HORIZONS)
                and span >= MIN_SPAN and tail <= TAIL_FRACTION
                and HORIZONS[-1] >= declared_threshold
                and len(declared_levels) >= MIN_READABLE
                and min(WRITE_LAW_COEFFICIENT * arm.delta_g ** WRITE_LAW_EXPONENT
                        for arm in declared_levels) >= READABLE_FLOOR_Q
                and HOLD_HORIZON >= HOLD_MIN_SECONDS
                and hold_tail <= TAIL_FRACTION
                and min(WRITE_LAW_COEFFICIENT * arm.delta_g ** WRITE_LAW_EXPONENT
                        for arm in retention_levels) >= READABLE_FLOOR_Q)
    silence_write = max(abs(value) for value in
                        arms[RAY_SILENCE_ARM]["delta"]["at_horizons"])
    silence_release = max(abs(value) for value in
                          arms[RETENTION_RAY_ARM]["delta"]["at_horizons"])
    firer_write = arms[LARGEST_SPLIT_ARM]["delta"]["peak"]
    firer_release = arms[RETENTION_LARGEST_ARM]["delta"]["peak"]
    rows = [
        {"id": 1, "name": "binding", "reading": "thirteen rows declared against observed, "
         "all exact, and the predecessor's own ten rows agree", "bound": "exact",
         "passed": True},
        {"id": 2, "name": "structure", "reading": "minimum state and projection, the "
         "composition bounds, and the annihilation and idempotence maxima over every "
         "recorded state of both families", "bound": "nonnegative states, 0 <= q < 1",
         "passed": bool(structural)},
        {"id": 3, "name": "anchor load", "reading": {
            "measured": arms[ANCHOR_ARM]["load"]["measured"], "receipt": oracle["ray_load"],
            "declared_literal": arms[ANCHOR_ARM]["load"]["predicted"]},
         "bound": "relative {0} against the section 67 receipt".format(LOAD_TOL),
         "passed": bool(comparison_ok
                        and abs(arms[ANCHOR_ARM]["load"]["measured"] - oracle["ray_load"])
                        <= LOAD_TOL * oracle["ray_load"])},
        {"id": 4, "name": "action live", "reading": action["live"]["relative"],
         "bound": ">= {0}".format(ACTION_FLOOR_LIVE),
         "passed": bool(action["live"]["relative"] >= ACTION_FLOOR_LIVE)},
        {"id": 5, "name": "action silent", "reading": action["silent"]["relative"],
         "bound": "<= {0}".format(ACTION_CEIL_SILENT),
         "passed": bool(action["silent"]["relative"] <= ACTION_CEIL_SILENT)},
        {"id": 6, "name": "horizon adequacy, both phases", "reading": {
            "horizons": list(HORIZONS), "distinct": distinct, "span_nats": span,
            "tail": tail, "declared_threshold": declared_threshold,
            "hold_horizon": HOLD_HORIZON, "hold_min_seconds": HOLD_MIN_SECONDS,
            "hold_tail": hold_tail,
            "declared_levels": len(declared_levels),
            "retention_levels": len(retention_levels),
            "smallest_write_magnitude": min(
                WRITE_LAW_COEFFICIENT * arm.delta_g ** WRITE_LAW_EXPONENT
                for arm in declared_levels)},
         "bound": "count {0}, distinct, span >= {1}, tail <= {2}, T_max >= {3}, hold >= "
                  "{4} with its own tail <= {2}".format(HORIZON_COUNT, MIN_SPAN,
                                                        TAIL_FRACTION,
                                                        round(declared_threshold, 3),
                                                        round(HOLD_MIN_SECONDS, 3)),
         "passed": bool(adequacy)},
        {"id": 7, "name": "write clock", "reading": {
            "fitted": clocks["write"]["rate"], "reference": clocks["write"]["reference"],
            "ratio": clocks["write"]["ratio"], "window": clocks["write"]["window"],
            "receipt_read": clock_read["read"],
            "receipt_equal": clock_read["equal_to_declared"]},
         "bound": "factor {0} of the declared rate, read live from the receipt".format(
             NU_TOLERANCE),
         "passed": bool(clocks["write"]["passed"] and clock_read["equal_to_declared"])},
        {"id": 8, "name": "release clock", "reading": {
            "fitted": clocks["release"]["rate"], "reference": clocks["release"]["reference"],
            "ratio": clocks["release"]["ratio"], "window": clocks["release"]["window"]},
         "bound": "factor {0} of the declared rate on the release phase".format(
             NU_TOLERANCE),
         "passed": bool(clocks["release"]["passed"])},
        {"id": 9, "name": "schedule conformance", "reading": "dt against the rule on every "
         "arm's own loaded projection", "bound": "dt <= 1/(40 lambda_max), declared set",
         "passed": bool(conformant)},
        {"id": 10, "name": "declared shape", "reading": budget,
         "bound": "{0} executions, {1} per execution, {2} total".format(
             DECLARED_EXECUTIONS, PER_EXECUTION_CAP, TOTAL_STEP_CAP),
         "passed": bool(shape_ok)},
        {"id": 11, "name": "silence on the ray, write phase", "reading": silence_write,
         "bound": "<= {0} at every horizon".format(SILENCE_FLOOR_Q),
         "passed": bool(silence_write <= SILENCE_FLOOR_Q)},
        {"id": 12, "name": "silence on the ray, release phase", "reading": silence_release,
         "bound": "<= {0} at every horizon".format(SILENCE_FLOOR_Q),
         "passed": bool(silence_release <= SILENCE_FLOOR_Q)},
        {"id": 13, "name": "can-fail at the largest split, write phase",
         "reading": firer_write, "bound": ">= {0}".format(READABLE_FLOOR_Q),
         "passed": bool(firer_write >= READABLE_FLOOR_Q)},
        {"id": 14, "name": "can-fail at the largest split, release phase",
         "reading": firer_release, "bound": ">= {0}".format(READABLE_FLOOR_Q),
         "passed": bool(firer_release >= READABLE_FLOOR_Q)},
        {"id": 15, "name": "anchors at the ray", "reading": {
            RAY_ANCHOR_ARM: arms[RAY_ANCHOR_ARM]["ray_distance"],
            ANCHOR_ARM: arms[ANCHOR_ARM]["ray_distance"]},
         "bound": "<= {0} at each anchor's own final state".format(ANCHOR_RAY_TOL),
         "passed": bool(all(arms[name]["ray_distance"] is not None
                            and arms[name]["ray_distance"] <= ANCHOR_RAY_TOL
                            for name in (RAY_ANCHOR_ARM, ANCHOR_ARM)))},
        {"id": 16, "name": "anchor at the ray, at the hold horizon",
         "reading": arms[ANCHOR_ARM]["ray_distance_at_hold"],
         "bound": "equal to {0} within {1}".format(ANCHOR_RAY_AT_HOLD, REPLICATION_TOL),
         "passed": bool(arms[ANCHOR_ARM]["ray_distance_at_hold"] is not None
                        and abs(arms[ANCHOR_ARM]["ray_distance_at_hold"]
                                - ANCHOR_RAY_AT_HOLD)
                        <= REPLICATION_TOL * ANCHOR_RAY_AT_HOLD)},
        {"id": 17, "name": "predecessor replication", "reading": {
            "checked": replication["count"], "mismatches": len(replication["mismatches"])},
         "bound": "every horizon-indexed reading of the twelve predecessor arms exact",
         "passed": bool(replication["passed"])},
        {"id": 18, "name": "cross-protocol oracle",
         "reading": arms[STEP_NOISE_ARM]["rho"]["max"],
         "bound": "bit-identical to {0}".format(ORACLE_RAY_RHO),
         "passed": bool(arms[STEP_NOISE_ARM]["rho"]["max"] == ORACLE_RAY_RHO)},
        {"id": 19, "name": "cross-executor oracle",
         "reading": [arms[REPLICATION_ARM]["rho"]["max"],
                     arms[REPLICATION_ARM]["rho"]["final"],
                     arms[REPLICATION_ARM]["schedule"]["lambda_max"]],
         "bound": "bit-identical to {0}, {1}, {2}".format(ORACLE_REPLICATION_RHO,
                                                          ORACLE_REPLICATION_FINAL,
                                                          ORACLE_REPLICATION_LAMBDA),
         "passed": bool(arms[REPLICATION_ARM]["rho"]["max"] == ORACLE_REPLICATION_RHO
                        and arms[REPLICATION_ARM]["rho"]["final"]
                        == ORACLE_REPLICATION_FINAL
                        and arms[REPLICATION_ARM]["schedule"]["lambda_max"]
                        == ORACLE_REPLICATION_LAMBDA)},
        {"id": 20, "name": "design-probe replication", "reading": {
            "checked": probe_check["checked"], "mismatches": probe_check["mismatches"]},
         "bound": "the retention offsets equal the declared literals within {0}".format(
             REPLICATION_TOL),
         "passed": bool(probe_check["passed"])},
        {"id": 21, "name": "single invocation", "reading": "receipt absent at start, one "
         "process, pid recorded", "bound": "structural", "passed": True},
        {"id": 22, "name": "family identity", "reading": {
            "checked": family["count"], "mismatches": len(family["mismatches"])},
         "bound": "the retention arms' held readings equal the write arms' own, exactly",
         "passed": bool(family["passed"])},
    ]
    return rows


def features_of(gates: list, decision: dict) -> dict:
    """Section 4.2: the thirteen features, each readable off a gate or off the decision."""
    passed = {row["id"]: bool(row["passed"]) for row in gates}
    return {
        "F1": passed[13],
        "F2": passed[11],
        "F3": passed[18] and passed[19],
        "F4": passed[7],
        "F5": passed[8],
        "F6": passed[15],
        "F7": passed[14],
        "F8": passed[17],
        "F9": passed[12],
        "F10": passed[16],
        "F11": bool(decision["write"]["largest_split_branch"] in ("PERSIST", "TRANS")),
        "F12": bool(decision["retention"]["largest_split_branch"] in RETENTION_BRANCHES),
        "F13": passed[22],
        "write_verdict_candidate": decision["write"]["verdict"],
        "retention_verdict_candidate": decision["retention"]["verdict"],
        "joint_candidate": decision["joint"],
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
                        ("prior_body", PRIOR_EXECUTOR), ("prior_executor", PRIOR_EXECUTOR),
                        ("bound_module", BOUND_MODULE), ("base_probe", BASE_PROBE),
                        ("split_executor", SPLIT_EXECUTOR),
                        ("gate_load_executor", GATE_LOAD_EXECUTOR),
                        ("base_receipt", BASE_RECEIPT), ("split_receipt", SPLIT_RECEIPT),
                        ("gate_load_protocol", GATE_LOAD_PROTOCOL),
                        ("gate_load_receipt", GATE_LOAD_RECEIPT),
                        ("prior_receipt", PRIOR_RECEIPT)):
        if key == "protocol":
            observed[key] = protocol_body_digest()
        elif key == "prior_body":
            observed[key] = prior.protocol_body_digest()
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


def build():
    """Run every declared arm once, in order, and return the readings both families read."""
    base = load_modules()
    oracle = read_oracle()
    clock_read = prior.read_clock()
    if not clock_read["equal_to_declared"]:
        raise SystemExit(EXIT_PRE_EXECUTION_BLOCK)
    action = {"live": action_of(LARGEST_LOAD, LARGEST_SPLIT, base),
              "silent": action_of(0.0, LARGEST_SPLIT, base)}
    reduction = gate_load.reduction_residual(
        SuccessorSpec(0, "reduction", "reduction", 0.0, 0.0), base)
    arms, traces, rho_series = {}, {}, {}
    for spec in ARM_TABLE:
        anchor_series = None
        if spec.twin:
            series = traces[spec.twin]
            anchor_series = series[:spec.declared_schedule()[2] + 1]
        reading = arm_record(spec, base, anchor_series, spec.hold_steps or None)
        series = reading.pop("_coordinate_series")
        rho = reading.pop("_rho_series")
        if spec.name in TWIN_NAMES:
            traces[spec.name] = series
        arms[spec.name] = reading
        if spec.name == CLOCK_ARM:
            rho_series["anchor"] = rho
        if rho is not None:
            rho_series[spec.name] = rho
        label = reading["branch"]["branch"] if reading["branch"] else reading["role"]
        print("{0:<20} {1:<11} steps {2:>6} peak {3:.6e}".format(
            spec.name, label, reading["schedule"]["steps"], reading["delta"]["peak"]
            if reading["delta"] else reading["rho"]["max"]))
    return {"base": base, "arms": arms, "action": action, "reduction": reduction,
            "oracle": oracle, "clock_read": clock_read, "rho": rho_series}


def finish(built) -> dict:
    """The readings both families need, the two clocks, the decision and the gates."""
    arms = built["arms"]
    step = DECLARED_DT
    clocks = {
        "write": prior.clock_of(built["rho"]["anchor"], step, SAMPLE[0], SAMPLE[-1]),
        "release": prior.clock_of(built["rho"]["anchor"], step, RELEASE_SAMPLE[0],
                                  RELEASE_SAMPLE[-1]),
    }
    decision = decide(arms)
    decision["retention"]["law"] = retention_law(arms, decision["retention"]["branches"])
    comparison_ok = all(arm["load"]["passed"] for arm in arms.values())
    budget = {
        "executions": len(arms),
        "steps_total": int(sum(arm["schedule"]["steps"] for arm in arms.values())),
        "steps_max": int(max(arm["schedule"]["steps"] for arm in arms.values())),
        "per_execution_cap": PER_EXECUTION_CAP,
        "total_cap": TOTAL_STEP_CAP,
        "declared_executions": DECLARED_EXECUTIONS,
        "projected_seconds_assumed": PROJECTED_SECONDS_ASSUMED,
        "projected_seconds_measured": PROJECTED_SECONDS_MEASURED,
        "seconds_per_step_assumed": SECONDS_PER_STEP_ASSUMED,
        "seconds_per_step_measured": SECONDS_PER_STEP_MEASURED,
    }
    replication = predecessor_replication(arms, load_json(PRIOR_RECEIPT))
    probe_check = probe_replication(arms)
    family = family_identity(arms)
    gates = gate_rows(arms, built["action"], comparison_ok, budget, clocks,
                      built["clock_read"], built["oracle"], decision, replication,
                      probe_check, family)
    features = features_of(gates, decision)
    status = status_of(gates, features)
    return {"clocks": clocks, "decision": decision, "budget": budget,
            "replication": replication, "probe_check": probe_check, "family": family,
            "gates": gates, "features": features, "status": status,
            "comparison_ok": comparison_ok}


def execute() -> int:
    started = time.time()
    binding = check_binding()
    if os.path.exists(os.path.join(ROOT, RECEIPT_PATH)):
        print("REFUSING TO RUN: {0} already exists; the stopping rule allows no second "
              "invocation on a recorded result".format(RECEIPT_PATH))
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
        },
        "binding": binding,
        "thresholds": {
            "readable_floor_q": READABLE_FLOOR_Q,
            "silence_floor_q": SILENCE_FLOOR_Q,
            "persist_share": PERSIST_SHARE,
            "trans_share": TRANS_SHARE,
            "retention_share": RETENTION_SHARE,
            "release_share": RELEASE_SHARE,
            "residual_band": RESIDUAL_BAND,
            "clock_tolerance": CLOCK_TOLERANCE,
            "nu_reference": NU_REFERENCE,
            "nu_tolerance": NU_TOLERANCE,
            "tail_fraction": TAIL_FRACTION,
            "min_span": MIN_SPAN,
            "horizon_count": HORIZON_COUNT,
            "horizons": list(HORIZONS),
            "min_readable": MIN_READABLE,
            "min_persist": MIN_PERSIST,
            "min_retained": MIN_RETAINED,
            "action_floor_live": ACTION_FLOOR_LIVE,
            "action_ceiling_silent": ACTION_CEIL_SILENT,
            "anchor_ray_tolerance": ANCHOR_RAY_TOL,
            "hold_min_multiple": HOLD_MIN_MULTIPLE,
            "hold_min_seconds": HOLD_MIN_SECONDS,
            "load_tolerance": LOAD_TOL,
            "step_safety": STEP_SAFETY,
            "step_candidates": list(STEP_CANDIDATES),
            "write_law_coefficient": WRITE_LAW_COEFFICIENT,
            "write_law_exponent": WRITE_LAW_EXPONENT,
            "write_law_instrument": WRITE_LAW_INSTRUMENT,
            "anchor_ray_at_hold": ANCHOR_RAY_AT_HOLD,
            "replication_tolerance": REPLICATION_TOL,
        },
        "arm_table": [
            {"index": arm.index, "name": arm.name, "role": arm.role,
             "load_transfer": arm.load_c, "delta_g": arm.delta_g,
             "schedule_key": arm.schedule_key, "twin": arm.twin,
             "hold_steps": arm.hold_steps,
             "schedule": list(arm.declared_schedule())}
            for arm in ARM_TABLE
        ],
        "arms": arms,
        "action": built["action"],
        "reduction": {"residual": built["reduction"], "bound": 0.0},
        "clock": {"write": result["clocks"]["write"],
                  "release": result["clocks"]["release"],
                  "declared": built["clock_read"]},
        "oracle": built["oracle"],
        "fits": {
            "law_held": decision["write"]["law"],
            "corroboration": decision["write"]["corroboration"],
            "retention": decision["retention"]["law"],
        },
        "decision": {
            "write": {key: value for key, value in decision["write"].items()
                      if key != "corroboration"},
            "retention": decision["retention"],
            "joint": decision["joint"],
        },
        "replication": {"predecessor": result["replication"],
                        "design_probe": result["probe_check"],
                        "family_identity": result["family"]},
        "gates": result["gates"],
        "features": result["features"],
        "budget": result["budget"],
        "verdicts": {
            "write": decision["write"]["verdict"] if passed else None,
            "write_law": (decision["write"]["law"]["label"]
                          if (passed and decision["write"]["law"]) else None),
            "instrument": (decision["write"]["law"]["instrument"]
                           if (passed and decision["write"]["law"]) else None),
            "retention": decision["retention"]["verdict"] if passed else None,
            "joint": decision["joint"] if passed else None,
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
    print("write: {0}".format(receipt["verdicts"]["write"]))
    print("retention: {0}".format(receipt["verdicts"]["retention"]))
    print("joint: {0}".format(receipt["verdicts"]["joint"]))
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


def witness_tables() -> dict:
    """Section 5.2: the synthetic readings the two rules must separate.

    The retention witness is the whole point of the horizon declaration: a written offset
    that stays, one that decays at the measured rate, and one that does both must reach
    three different labels on the same five horizons.
    """
    times = np.array(HORIZONS, dtype=np.float64)
    written = 5.0e-4
    return {
        "retained": [written] * len(HORIZONS),
        "released": list(written * np.exp(-NU_REFERENCE * times)),
        "partial": list(0.3 * written + 0.7 * written * np.exp(-NU_REFERENCE * times)),
        "below_floor": [1.0e-15] * len(HORIZONS),
    }


def self_check() -> int:
    """Static, derivation and pre-flight checks. Writes nothing; safe to run again."""
    problems = []
    print("self-check: binding")
    check_binding()
    print("self-check: protocol rows against this executor's constants")
    rows = (
        ("bound_seconds", BOUND_SECONDS), ("declared_executions", DECLARED_EXECUTIONS),
        ("per_execution_cap", PER_EXECUTION_CAP), ("total_step_cap", TOTAL_STEP_CAP),
        ("readable_floor_q", READABLE_FLOOR_Q), ("silence_floor_q", SILENCE_FLOOR_Q),
        ("persist_share", PERSIST_SHARE), ("trans_share", TRANS_SHARE),
        ("retention_share", RETENTION_SHARE), ("release_share", RELEASE_SHARE),
        ("min_retained", MIN_RETAINED), ("residual_band", RESIDUAL_BAND),
        ("clock_tolerance", CLOCK_TOLERANCE), ("nu_reference", NU_REFERENCE),
        ("nu_tolerance", NU_TOLERANCE), ("tail_fraction", TAIL_FRACTION),
        ("min_span", MIN_SPAN), ("horizon_count", HORIZON_COUNT),
        ("min_readable", MIN_READABLE), ("min_persist", MIN_PERSIST),
        ("action_floor_live", ACTION_FLOOR_LIVE),
        ("action_ceiling_silent", ACTION_CEIL_SILENT),
        ("anchor_ray_tolerance", ANCHOR_RAY_TOL), ("load_tolerance", LOAD_TOL),
        ("step_safety", STEP_SAFETY), ("hold_min_multiple", HOLD_MIN_MULTIPLE),
        ("write_law_coefficient", WRITE_LAW_COEFFICIENT),
        ("write_law_exponent", WRITE_LAW_EXPONENT),
        ("write_law_instrument", WRITE_LAW_INSTRUMENT),
        ("anchor_ray_at_hold", ANCHOR_RAY_AT_HOLD),
        ("replication_tolerance", REPLICATION_TOL),
    )
    for key, value in rows:
        declared = declared_number(key)
        if declared != value:
            problems.append("the protocol declares {0} = {1}, this executor holds {2}".format(
                key, declared, value))
    if declared_literal_tuple("horizons") != tuple(HORIZONS):
        problems.append("the protocol declares {0} horizons and this executor holds "
                        "{1}".format(declared_literal_tuple("horizons"), HORIZONS))
    if declared_literal_tuple("retention_levels") != tuple(RETENTION_LEVELS):
        problems.append("the protocol declares retention levels {0} against {1}".format(
            declared_literal_tuple("retention_levels"), RETENTION_LEVELS))
    if not PROBE_RETENTION_OFFSETS or len(PROBE_RETENTION_OFFSETS) != len(RETENTION_ORDER):
        problems.append("the protocol declares no design-probe retention literals")
    else:
        declared_offsets = declared_literal_tuple("probe_retention_offsets")
        if declared_offsets != tuple(PROBE_RETENTION_OFFSETS):
            problems.append("the protocol's probe offsets {0} disagree with this "
                            "executor's {1}".format(declared_offsets,
                                                    PROBE_RETENTION_OFFSETS))
    print("self-check: the imported chain's own thresholds and the horizon arithmetic")
    if prior.READABLE_FLOOR_Q != READABLE_FLOOR_Q:
        problems.append("the imported fit filters readings above {0}".format(
            prior.READABLE_FLOOR_Q))
    if prior.NU_REFERENCE != NU_REFERENCE:
        problems.append("the imported fits hold a different rate")
    span = float(NU_REFERENCE * (HORIZONS[-1] - HORIZONS[0]))
    if span < MIN_SPAN:
        problems.append("the horizon set spans {0} relaxation times".format(span))
    if float(np.exp(-NU_REFERENCE * HORIZONS[-1])) > TAIL_FRACTION:
        problems.append("the horizon set's tail is above the declared fraction")
    if HORIZONS[-1] < float(np.log(1.0 / TAIL_FRACTION) / NU_REFERENCE):
        problems.append("the last horizon is below the declared threshold")
    if HOLD_HORIZON < HOLD_MIN_SECONDS:
        problems.append("the hold horizon {0} is below the declared minimum {1}".format(
            HOLD_HORIZON, HOLD_MIN_SECONDS))
    if float(np.exp(-NU_REFERENCE * HOLD_HORIZON)) > TAIL_FRACTION:
        problems.append("the hold horizon leaves more than the declared fraction of the "
                        "write transient")
    if RELEASE_SAMPLE[0] != HOLD_STEPS + SAMPLE[0]:
        problems.append("the release samples are not offset by the hold")
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
    for arm in ARM_TABLE:
        if arm.twin:
            twin = [other for other in ARM_TABLE if other.name == arm.twin]
            if not twin or twin[0].index >= arm.index:
                problems.append("{0}'s twin {1} does not precede it".format(arm.name, arm.twin))
            elif twin[0].role != "anchor" or twin[0].load_c != arm.load_c:
                problems.append("{0}'s twin is not an anchor on the same load".format(arm.name))
        elif arm.role not in ("anchor", "oracle"):
            problems.append("{0} declares no twin and is not an anchor or an oracle".format(
                arm.name))
    if [arm.name for arm in ARM_TABLE if arm.name in SWEEP_ORDER] != list(SWEEP_ORDER):
        problems.append("the sweep family is not the declared order")
    if [arm.name for arm in ARM_TABLE if arm.name in RETENTION_ORDER] != list(RETENTION_ORDER):
        problems.append("the retention family is not the declared order")
    if [arm.delta_g for arm in ARM_TABLE if arm.name in RETENTION_ORDER] != list(
            RETENTION_LEVELS):
        problems.append("the retention arms do not carry the declared split sizes")
    for arm in ARM_TABLE:
        if arm.schedule_key == "hold" and arm.role not in ("anchor",) \
                and arm.declared_schedule()[2] + 1 <= SAMPLE[-1]:
            problems.append("{0} is read at the declared horizons but runs only {1}".format(
                arm.name, arm.declared_schedule()[2]))
    print("self-check: the retention branch rule is reachable in every branch, on synthetic "
          "readings")
    table = witness_tables()
    written = abs(table["retained"][0])
    expected = {"retained": "RETAINED", "released": "RELEASED", "partial": "PARTIAL",
                "below_floor": "BELOW_FLOOR"}
    for key, wanted in expected.items():
        values = table[key]
        reading = classify_retention(values, written, "PERSIST")
        if reading["branch"] != wanted:
            problems.append("the retention rule labels a synthetic {0} as {1}".format(
                key, reading["branch"]))
    moot = classify_retention(table["retained"], written, "TRANS")
    if moot["branch"] != "MOOT":
        problems.append("the retention rule does not record a moot level where family (i) "
                        "did not persist")
    print("self-check: the write branch rule and its fragility, through the imported rule")
    for structure, labels in prior.WITNESS_LABELS.items():
        for ratio, wanted in zip(prior.WITNESS_RATIOS, labels):
            rate = NU_REFERENCE * ratio
            times = np.array(HORIZONS, dtype=np.float64)
            if structure == "transient":
                values = prior.WITNESS_AMPLITUDE * np.exp(-rate * times)
            elif structure == "shift":
                values = prior.WITNESS_OFFSET * (1.0 - np.exp(-rate * times))
            else:
                values = (prior.WITNESS_OFFSET * (1.0 - np.exp(-rate * times))
                          + prior.WITNESS_AMPLITUDE * np.exp(-rate * times))
            reading = prior.classify(values)
            if reading["branch"] != wanted:
                problems.append("the imported write rule labels a synthetic {0} at rate "
                                "ratio {1} as {2}".format(structure, ratio,
                                                          reading["branch"]))
    fragility = prior.classify(prior.WITNESS_AMPLITUDE
                               * np.exp(-1.024 * NU_REFERENCE
                                        * np.array(HORIZONS, dtype=np.float64)))
    if fragility["branch"] != "TRANS":
        problems.append("the write rule no longer rescues the fragility witness: {0}".format(
            fragility["branch"]))
    print("self-check: the verdict vocabularies are reachable in every branch")
    if write_verdict({"supersplit_load": "PERSIST", "decade_1": "PERSIST"},
                     ["decade_1", "supersplit_load"], [], "PERSIST") != "WRITES":
        problems.append("the write verdict rule no longer reaches WRITES")
    if write_verdict({"supersplit_load": "TRANS"}, [], list(SWEEP_ORDER), "TRANS") \
            != "PERTURBS_ONLY":
        problems.append("the write verdict rule no longer reaches PERTURBS_ONLY")
    if write_verdict({"supersplit_load": "UNRESOLVED"}, [], [], "UNRESOLVED") \
            != "INCONCLUSIVE":
        problems.append("the write verdict rule no longer reaches INCONCLUSIVE")
    retained = {name: "RETAINED" for name in RETENTION_ORDER}
    if retention_verdict(retained, "RETAINED", "WRITES") != "STORES":
        problems.append("the retention rule no longer reaches STORES")
    released = {name: "RELEASED" for name in RETENTION_ORDER}
    if retention_verdict(released, "RELEASED", "WRITES") != "RELEASES":
        problems.append("the retention rule no longer reaches RELEASES")
    if retention_verdict(retained, "RETAINED", "PERTURBS_ONLY") != "MOOT":
        problems.append("the retention rule no longer reaches MOOT")
    partial = {name: "PARTIAL" for name in RETENTION_ORDER}
    if retention_verdict(partial, "PARTIAL", "WRITES") != "INCONCLUSIVE":
        problems.append("the retention rule no longer reaches INCONCLUSIVE")
    for write_label, retention_label, wanted in (("WRITES", "STORES", "memory"),
                                                 ("WRITES", "RELEASES", "knob"),
                                                 ("PERTURBS_ONLY", "MOOT", "no-write"),
                                                 ("INCONCLUSIVE", "MOOT", "undecided")):
        if joint_label(write_label, retention_label) != wanted:
            problems.append("the joint rule returns {0} where the table says {1}".format(
                joint_label(write_label, retention_label), wanted))
    print("self-check: the decision rule reads every gate and every feature")
    if status_of([{"id": 1, "passed": True}], {"F1": True}) != "PASS":
        problems.append("the status rule does not return PASS on an all-true set")
    if status_of([{"id": 1, "passed": False}], {"F1": True}) != "FAIL":
        problems.append("the status rule does not return FAIL on a false gate")
    sample_gates = [{"id": index, "name": "gate {0}".format(index), "reading": "sample",
                     "bound": "sample", "passed": True} for index in range(1, 23)]
    for row in sample_gates:
        if "passed" not in row or "reading" not in row:
            problems.append("gate {0} does not carry the status".format(row["id"]))
    labels = features_of(sample_gates, {"write": {"largest_split_branch": "PERSIST",
                                                  "verdict": "WRITES"},
                                        "retention": {"largest_split_branch": "RETAINED",
                                                      "verdict": "STORES"},
                                        "joint": "memory"})
    for key in ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F11", "F12",
                "F13"):
        if key not in labels:
            problems.append("feature {0} does not carry the status".format(key))
    print("self-check: the seeded-state action, the reduction and the released step")
    base = load_modules()
    action = {"live": action_of(LARGEST_LOAD, LARGEST_SPLIT, base),
              "silent": action_of(0.0, LARGEST_SPLIT, base)}
    if action["live"]["relative"] < ACTION_FLOOR_LIVE:
        problems.append("the split's action at the largest load is below the floor")
    if action["silent"]["relative"] > ACTION_CEIL_SILENT:
        problems.append("the split's action on the ray seed is above the ceiling")
    reduction = gate_load.reduction_residual(
        SuccessorSpec(0, "reduction", "reduction", 0.0, 0.0), base)
    if reduction != 0.0:
        problems.append("the split right-hand side does not reduce to the successor's own")
    probe_spec = SuccessorSpec(0, "release_probe", "retention", LARGEST_LOAD,
                               LARGEST_SPLIT, "release", "", HOLD_STEPS)
    state = gate_load.loaded_seed(probe_spec, base)
    plain = split.split_step(state, DECLARED_DT, probe_spec.released(), base)
    reference = split.split_step(
        state, DECLARED_DT, prior.ArmSpec(0, "release_probe", "retention", LARGEST_LOAD,
                                          0.0, "release", ""), base)
    if not np.array_equal(plain, reference):
        problems.append("the released step is not the anchor's own step")
    held = split.split_step(state, DECLARED_DT, probe_spec, base)
    if np.array_equal(held, plain):
        problems.append("the held step and the released step are the same state: the "
                        "release would test nothing")
    print("self-check: the clock and the oracle literals against the bound receipts")
    clock_read = prior.read_clock()
    if not clock_read["equal_to_declared"]:
        problems.append("the successor receipt's relaxation rate is not the declared one")
    oracle = read_oracle()
    if oracle["ray_load"] != ORACLE_RAY_LOAD:
        problems.append("the declared oracle load is not section 67's receipt value")
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
    """Section 1.5: the readings the declared floors, bands and horizons are chosen
    against. Runs both families once and writes nothing.

    This is design work, not an invocation: it writes no receipt, it is not gated, and the
    run is expected to reproduce it because it is the same construction on the same seed.
    """
    built = build()
    result = finish(built)
    arms = built["arms"]
    print()
    print("design probe: family (i), the write")
    for name in SWEEP_ORDER:
        branch = arms[name]["branch"]
        print("  {0:<20} {1:<11} Dinf_held {2:>13.6e} free {3:>13.6e} peak {4:.6e} "
              "share {5} ratio {6}".format(
                  name, branch["branch"], branch["held"]["offset"],
                  branch["free"]["offset"], branch["peak"], _round(branch["share_held"]),
                  round(branch["rate_ratio"], 4)))
    law = result["decision"]["write"]["law"]
    if law:
        print("  law {0} coefficient {1:.16e} exponent {2:.16e} instrument {3:.16e}".format(
            law["label"], law["fit"]["coefficient"], law["fit"]["exponent"],
            law["instrument"]))
    print()
    print("design probe: family (ii), retention")
    for name in RETENTION_ORDER:
        arm = arms[name]
        branch = arm["branch"]
        readings = arm["delta"]["at_horizons"]
        print("  {0:<20} {1:<11} written {2:>13.6e} Dinf_held {3:>13.6e} free {4:>13.6e} "
              "share {5} ratio {6}".format(
                  name, branch["branch"], branch["written"], branch["held"]["offset"],
                  branch["free"]["offset"], _round(branch["share_held"]),
                  round(branch["rate_ratio"], 4)))
        print("      residual_held {0:.6e} residual_free {1:.6e}".format(
            branch["residual_held"], branch["residual_free"]))
        print("      post-release readings {0}".format(
            ["{0:.9e}".format(value) for value in readings]))
        print("      held-phase readings   {0}".format(
            ["{0:.9e}".format(value) for value in arm["delta"]["at_hold_horizons"]]))
    print("  verdicts: write {0}, retention {1}, joint {2}".format(
        result["decision"]["write"]["verdict"], result["decision"]["retention"]["verdict"],
        result["decision"]["joint"]))
    print()
    print("design probe: clocks")
    for key in ("write", "release"):
        clock = result["clocks"][key]
        print("  {0:<8} fitted {1:.16e} reference {2:.16e} ratio {3:.6f} window {4}".format(
            key, clock["rate"], clock["reference"], clock["ratio"], clock["window"]))
    print("design probe: predecessor replication")
    print("  checked {0}, mismatches {1}".format(result["replication"]["count"],
                                                 len(result["replication"]["mismatches"])))
    for item in result["replication"]["mismatches"][:8]:
        print("    {0}".format(item))
    print("design probe: gates and status")
    for row in result["gates"]:
        print("  gate {0:>2} {1:<40} {2}".format(row["id"], row["name"],
                                                 "pass" if row["passed"] else "FAIL"))
    print("  status {0}".format(result["status"]))
    print("  budget {0} arms, {1} steps, largest {2}".format(
        result["budget"]["executions"], result["budget"]["steps_total"],
        result["budget"]["steps_max"]))
    offsets = [arms[name]["branch"]["held"]["offset"] for name in RETENTION_ORDER]
    written = [arms[name]["branch"]["written"] for name in RETENTION_ORDER]
    print("  probe_retention_offsets = {0}".format(
        ", ".join("{0:.16e}".format(value) for value in offsets)))
    print("  probe_retention_written = {0}".format(
        ", ".join("{0:.16e}".format(value) for value in written)))
    return EXIT_PASS


def freeze() -> int:
    """Print the two digests and the section-0 rows the freeze pass pastes in."""
    print("frozen_body_sha256 = {0}".format(protocol_body_digest()))
    print("executor_sha256    = {0}".format(digest_of(PROBE_PATH)))
    print("prior_body         = {0}".format(prior.protocol_body_digest()))
    print("prior_executor     = {0}".format(digest_of(PRIOR_EXECUTOR)))
    print("gate_load_body     = {0}".format(gate_load.protocol_body_digest()))
    print("prior_receipt      = {0}".format(digest_of(PRIOR_RECEIPT)))
    return EXIT_PASS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--design-probe", action="store_true")
    parser.add_argument("--freeze", action="store_true")
    arguments = parser.parse_args(argv)
    if arguments.self_check:
        return self_check()
    if arguments.design_probe:
        return design_probe()
    if arguments.freeze:
        return freeze()
    return execute()


if __name__ == "__main__":
    raise SystemExit(main())
